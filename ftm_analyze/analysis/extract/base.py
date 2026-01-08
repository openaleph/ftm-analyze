from typing import Generator, TypeAlias

from anystore.logging import get_logger
from followthemoney import Property
from ftmq.util import clean_name
from rigour.names import (
    Name,
    normalize_name,
    remove_org_prefixes,
    remove_person_prefixes,
    tag_person_name,
)

from ftm_analyze.analysis.country import location_country
from ftm_analyze.analysis.util import (
    TAG_COMPANY,
    TAG_COUNTRY,
    TAG_LOCATION,
    TAG_PERSON,
)

log = get_logger(__name__)

NAME_MAX_LENGTH = 100
NAME_MIN_LENGTH = 8

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

NERs: TypeAlias = Generator[tuple[Property, str], None, None]


def clean_entity_prefix(name: str) -> str:
    name = remove_org_prefixes(name)
    return remove_person_prefixes(name)


def test_name(text) -> bool:
    text = clean_name(text)
    if text is None or len(text) > NAME_MAX_LENGTH:
        return False
    text = clean_entity_prefix(text)
    if text is None or len(text) < NAME_MIN_LENGTH:
        return False
    # check if at least 1 letter in it
    return any(a.isalpha() for a in text)


def ner_result(prop: str, value: str, engine: str) -> NERs:
    """Process a NER result and yield normalized entities."""
    prop_ = NER_TYPES.get(prop)
    if prop_ is not None and test_name(value):
        if prop_ in (TAG_COMPANY, TAG_PERSON, TAG_LOCATION):
            log.debug(f"NER {engine}: [{prop_}] {value}")
            yield prop_, value
        if prop_ == TAG_LOCATION:
            for country in location_country(value):
                yield TAG_COUNTRY, country


def validate_person_name(name: str) -> bool:
    """Validate a person name if it contains at least one name symbol"""
    for _ in tag_person_name(Name(name), normalize_name).symbols:
        return True
    return False
