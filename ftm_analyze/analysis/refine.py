"""
This cleans names per NER label (rigour prefixes) and refines locations
against geonames. The NER labels themselves are only re-classified by a legal
form in the name (rigour org class symbols, e.g. GmbH, e.V.): other heuristics
(person names, fastText) see the name only, not its context, and turned out to
be worse than the NER model's label.
"""

from functools import lru_cache
from typing import Callable

import jellyfish
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
)

from ftm_analyze.analysis.util import (
    NER_TAG,
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
    # no person name check: Christina is a valid location in canada, but so
    # are Berlin or Köln person names, and the NER model saw the context
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
