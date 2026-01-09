"""Base classes and protocols for extraction."""

from dataclasses import dataclass, field
from typing import Generator, Protocol, TypeAlias

from anystore.logging import get_logger
from followthemoney import Property
from ftmq.util import EntityProxy, clean_name
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
    TAG_LOCATION,
    TAG_PERSON,
)

log = get_logger(__name__)

NAME_MAX_LENGTH = 100
NAME_MIN_LENGTH = 8

# Standardized tags for extraction results
TAG_PER = "PER"
TAG_ORG = "ORG"
TAG_LOC = "LOC"
TAG_EMAIL = "EMAIL"
TAG_PHONE = "PHONE"
TAG_IBAN = "IBAN"
TAG_OTHER = "OTHER"

# Map NER model labels to standardized tags
NER_LABEL_MAP: dict[str, str] = {
    # spaCy / Flair / BERT labels
    "PER": TAG_PER,
    "B-PER": TAG_PER,
    "I-PER": TAG_PER,
    "PERSON": TAG_PER,
    "ORG": TAG_ORG,
    "B-ORG": TAG_ORG,
    "I-ORG": TAG_ORG,
    "LOC": TAG_LOC,
    "B-LOC": TAG_LOC,
    "I-LOC": TAG_LOC,
    "GPE": TAG_LOC,
    # GLiNER labels
    "person": TAG_PER,
    "organization": TAG_ORG,
    "location": TAG_LOC,
}

# Map tags to FTM properties
TAG_TO_PROP: dict[str, Property] = {
    TAG_PER: TAG_PERSON,
    TAG_ORG: TAG_COMPANY,
    TAG_LOC: TAG_LOCATION,
}


@dataclass
class ExtractionResult:
    """Single extraction result with metadata."""

    value: str
    tag: str  # PER, ORG, LOC, EMAIL, PHONE, IBAN, OTHER
    source: str  # extractor name: "spacy", "gliner", "pattern", etc.
    confidence: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def prop(self) -> Property | None:
        """Get the FTM property for this result's tag."""
        return TAG_TO_PROP.get(self.tag)


@dataclass
class ExtractionContext:
    """Context for extraction operations."""

    entity: EntityProxy
    text: str
    languages: list[str] = field(default_factory=list)


# Type aliases
ExtractionResults: TypeAlias = Generator[ExtractionResult, None, None]


class Extractor(Protocol):
    """Protocol for all extractors (NER and patterns)."""

    name: str

    def extract(self, context: ExtractionContext) -> ExtractionResults:
        """Extract entities from the given context."""
        ...


def clean_entity_prefix(name: str) -> str:
    """Remove common entity prefixes from a name."""
    name = remove_org_prefixes(name)
    return remove_person_prefixes(name)


def test_name(text: str) -> bool:
    """Validate that text is a reasonable entity name."""
    text = clean_name(text)
    if text is None or len(text) > NAME_MAX_LENGTH:
        return False
    text = clean_entity_prefix(text)
    if text is None or len(text) < NAME_MIN_LENGTH:
        return False
    # check if at least 1 letter in it
    return any(a.isalpha() for a in text)


def validate_person_name(name: str) -> bool:
    """Validate a person name if it contains at least one name symbol."""
    for _ in tag_person_name(Name(name), normalize_name).symbols:
        return True
    return False


def normalize_label(label: str) -> str:
    """Normalize NER model label to standard tag."""
    return NER_LABEL_MAP.get(label, TAG_OTHER)


def make_ner_result(
    label: str,
    value: str,
    source: str,
    confidence: float | None = None,
) -> ExtractionResults:
    """Create extraction results from NER output.

    Handles label normalization, validation, and country extraction for locations.
    """
    tag = normalize_label(label)
    if tag == TAG_OTHER:
        return

    if not test_name(value):
        return

    log.debug("NER extraction", source=source, tag=tag, value=value)
    yield ExtractionResult(
        value=value,
        tag=tag,
        source=source,
        confidence=confidence,
    )

    # Also yield countries for location extractions
    if tag == TAG_LOC:
        for country in location_country(value):
            yield ExtractionResult(
                value=country,
                tag="COUNTRY",
                source=source,
                metadata={"from_location": value},
            )
