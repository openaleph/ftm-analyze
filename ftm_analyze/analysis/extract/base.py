from typing import Generator, NamedTuple, TypeAlias

from anystore.logging import get_logger
from followthemoney import Property
from ftmq.util import clean_name
from rigour.names import (
    NameTypeTag,
    analyze_names,
    remove_org_prefixes,
    remove_person_prefixes,
)

from ftm_analyze.analysis.util import TAG_COMPANY, TAG_LOCATION, TAG_PERSON
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()

NAME_MAX_LENGTH = 100

# https://spacy.io/api/annotation#named-entities
NER_TYPES = {
    "PER": TAG_PERSON,
    "B-PER": TAG_PERSON,
    "I-PER": TAG_PERSON,
    "PERSON": TAG_PERSON,
    "ORG": TAG_COMPANY,
    "B-ORG": TAG_COMPANY,
    "I-ORG": TAG_COMPANY,
    "LOC": TAG_LOCATION,
    "B-LOC": TAG_LOCATION,
    "I-LOC": TAG_LOCATION,
    "GPE": TAG_LOCATION,
    # GLiNER labels
    "person": TAG_PERSON,
    "organization": TAG_COMPANY,
    "location": TAG_LOCATION,
}


class Span(NamedTuple):
    """A name found in a text, with its character offsets in that text. Known
    names (from the juditha automaton) carry their schema."""

    prop: Property
    value: str
    start: int
    end: int
    schema: str | None = None


NERs: TypeAlias = Generator[Span, None, None]


def clean_entity_prefix(name: str) -> str:
    name = remove_org_prefixes(name)
    return remove_person_prefixes(name)


def test_name(text) -> bool:
    text = clean_name(text)
    if text is None or len(text) > NAME_MAX_LENGTH:
        return False
    text = clean_entity_prefix(text)
    if text is None:
        return False
    # check if at least 1 letter in it
    return any(a.isalpha() for a in text)


def get_device() -> str:
    """Torch device for the flair, bert and gliner engines"""
    if settings.device:
        return settings.device
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def ner_result(prop: str, value: str, engine: str, start: int, end: int) -> NERs:
    """Process a NER result and yield normalized entities."""
    prop_ = NER_TYPES.get(prop)
    if prop_ is not None and test_name(value):
        if prop_ in (TAG_COMPANY, TAG_PERSON, TAG_LOCATION):
            log.debug(f"NER {engine}: [{prop_}] {value}")
            yield Span(prop_, value, start, end)


def validate_person_name(name: str) -> bool:
    """Validate a person name if it contains at least one name symbol"""
    # rigour 2: tag_person_name → analyze_names(NameTypeTag.PER, ...). One
    # tagged Name with any symbol is enough to call the input a plausible
    # person name.
    for tagged in analyze_names(NameTypeTag.PER, [name]):
        if tagged.symbols:
            return True
    return False
