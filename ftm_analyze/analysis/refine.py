"""
This tries to refine NER labels from spacy against some more data we know of,
mainly rigour name tagging and optionally reference name datasets via `juditha`.
It is a mix of hard-coded heuristics and a juditha-backed lookup (if
configured), and results seem to be slightly better than pure spacy output
"""

from functools import lru_cache
from typing import Callable

import jellyfish
import juditha
from anystore.logging import get_logger
from followthemoney import Property
from geonames_tagger.tagger import Location, tag_locations
from geonames_tagger.util import text_norm
from rigour.names import (
    NameTypeTag,
    SymbolCategory,
    analyze_names,
    remove_obj_prefixes,
    remove_org_prefixes,
    remove_person_prefixes,
    tokenize_name,
)

from ftm_analyze.analysis.util import (
    NER_TAG,
    SCHEMA_NER,
    TAG_COMPANY,
    TAG_LOCATION,
    TAG_NAME,
    TAG_PERSON,
)

log = get_logger(__name__)
LRU = 10_000

TYPE_PROPS: dict[NER_TAG, Property] = {
    "PER": TAG_PERSON,
    "ORG": TAG_COMPANY,
    "LOC": TAG_LOCATION,
    "OTHER": TAG_NAME,
}
PROPS_NER_TAGS: dict[Property, NER_TAG] = {v: k for k, v in TYPE_PROPS.items()}


@lru_cache(LRU)
def classify_mention(name: str, ner_tag: NER_TAG) -> NER_TAG:
    if is_rigour_person(name):
        return "PER"
    if is_rigour_org(name):
        return "ORG"
    if ner_tag == "LOC" and refine_location(name):
        return "LOC"
    # juditha 4.x replaced the standalone `predict_schema` fasttext classifier
    # with `juditha.lookup`, which returns a single Result whose `common_schema`
    # we project back into our coarse NER tag space.
    result = juditha.lookup(name)
    if result is not None and result.score > 0.9:
        guess_ner = SCHEMA_NER.get(result.common_schema, "OTHER")
        if guess_ner in ("LOC", "OTHER"):
            if ner_tag != "LOC":  # original was not loc
                return "OTHER"
        if ner_tag == "ORG" and guess_ner == "PER":
            if len(name) > 20:  # FIXME keep ORG label for longer names
                return "ORG"
        return guess_ner
    guess = classify_name_rigour(name)
    if guess == "ORG":
        return "ORG"
    return "OTHER"


@lru_cache(LRU)
def classify_name_rigour(name: str) -> NER_TAG:
    """hard core classify by rigour name symbols. This should only used as a
    last resort and in combination with other classifying logic."""
    if is_rigour_person(name):
        return "PER"
    if is_rigour_org(name):
        return "ORG"
    # n = Name(name)
    # seen = 0
    # required = max(len(n.parts) // 2, 2)
    # for part in n.parts:
    #     if seen >= required:
    #         return "PER"
    #     for tagged in analyze_names(NameTypeTag.PER, [part.form]):
    #         for symbol in tagged.symbols:
    #             if symbol.category == SymbolCategory.NAME:
    #                 seen += 1
    #                 break
    return "OTHER"


@lru_cache(LRU)
def is_rigour_person(name: str) -> bool:
    """Test if a name exclusively has person name symbols"""
    name = remove_person_prefixes(name)
    tokens_ = tokenize_name(name)
    tokens = [t for t in tokens_ if len(t) > 2]
    if len(tokens_) > len(tokens):
        return False
    seen = 0
    for token in tokens:
        # rigour 2: `tag_person_name` is gone; `analyze_names` is the unified
        # entry point and returns a set of tagged `Name` objects per batch.
        # Single-token inputs collapse to a single Name, so the `for tagged`
        # loop runs at most once.
        for tagged in analyze_names(NameTypeTag.PER, [token]):
            for symbol in tagged.symbols:
                if symbol.category == SymbolCategory.NAME:
                    seen += 1
                    break
    return seen == len(tokens)


@lru_cache(LRU)
def is_rigour_org(name: str) -> bool:
    """Test if a name contains org type symbols"""
    for tagged in analyze_names(NameTypeTag.ORG, [name]):
        for symbol in tagged.symbols:
            if symbol.category == SymbolCategory.ORG_CLASS:
                return True
    return False


@lru_cache(LRU)
def clean_name(
    name: str, type_: NER_TAG, normalizer: Callable[..., str | None] | None = None
) -> str:
    if normalizer:
        name = normalizer(name) or ""
    if not name:
        return name
    if type_ == "PER":
        return remove_person_prefixes(name)
    if type_ == "ORG":
        return remove_org_prefixes(name)
    return remove_obj_prefixes(name)


@lru_cache(LRU)
def refine_location(name: str) -> Location | None:
    """Refine extracted locations against geonames_tagger"""
    # Christina is a valid location in canada...
    if is_rigour_person(name):
        return
    try:
        for result in tag_locations(name):
            if jellyfish.jaro_similarity(text_norm(name), result.name) > 0.9:
                return result
    except Exception as e:  # automaton data not found
        log.error(
            f"Could not load geonames-tagger: `{e}`. Make sure local "
            "automaton.json data exists!"
        )
        return
