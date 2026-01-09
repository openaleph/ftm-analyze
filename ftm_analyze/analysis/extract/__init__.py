"""Extraction module for NER and pattern extraction."""

from ftm_analyze.analysis.extract.base import (
    NER_LABEL_MAP,
    TAG_EMAIL,
    TAG_IBAN,
    TAG_LOC,
    TAG_ORG,
    TAG_OTHER,
    TAG_PER,
    TAG_PHONE,
    TAG_TO_PROP,
    ExtractionContext,
    ExtractionResult,
    ExtractionResults,
    Extractor,
    make_ner_result,
    normalize_label,
    test_name,
    validate_person_name,
)
from ftm_analyze.analysis.extract.bert import BertExtractor
from ftm_analyze.analysis.extract.flair import FlairExtractor
from ftm_analyze.analysis.extract.gliner import GlinerExtractor
from ftm_analyze.analysis.extract.patterns import PatternExtractor
from ftm_analyze.analysis.extract.spacy import SpacyExtractor

__all__ = [
    "ExtractionResult",
    "ExtractionContext",
    "ExtractionResults",
    "Extractor",
    "make_ner_result",
    "normalize_label",
    "test_name",
    "validate_person_name",
    "TAG_PER",
    "TAG_ORG",
    "TAG_LOC",
    "TAG_EMAIL",
    "TAG_PHONE",
    "TAG_IBAN",
    "TAG_OTHER",
    "NER_LABEL_MAP",
    "TAG_TO_PROP",
    "SpacyExtractor",
    "FlairExtractor",
    "BertExtractor",
    "GlinerExtractor",
    "PatternExtractor",
]
