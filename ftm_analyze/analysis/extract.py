import typing
from functools import lru_cache
from typing import Generator, TypeAlias

from anystore.functools import weakref_cache as cache
from anystore.logging import get_logger
from followthemoney import Property
from followthemoney.types import registry
from ftmq.util import EntityProxy, clean_name
from rigour.langs import list_to_alpha3
from rigour.names import (
    Name,
    normalize_name,
    remove_org_prefixes,
    remove_person_prefixes,
    tag_person_name,
)

from ftm_analyze.analysis.country import location_country
from ftm_analyze.analysis.util import TAG_COMPANY, TAG_COUNTRY, TAG_LOCATION, TAG_PERSON
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from transformers import Pipeline


log = get_logger(__name__)
settings = Settings()

NAME_MAX_LENGTH = 100
NAME_MIN_LENGTH = 8  # hm?
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
}
SPACY_MODELS = settings.spacy_models.model_dump()


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


@lru_cache(maxsize=5)
def _load_spacy_model(model):
    """Load the spaCy model for the specified language"""
    import spacy

    return spacy.load(model)


def get_spacy_models(entity):
    """Iterate over the NER models applicable to the given entity."""
    languages = entity.get_type_values(registry.language)
    models = set()
    for lang in list_to_alpha3(languages):
        model = SPACY_MODELS.get(lang)
        if model is not None:
            models.add(model)
    if not models:  # default
        models.add(SPACY_MODELS[settings.ner_default_lang])
    for model in models:
        yield _load_spacy_model(model)


NERs: TypeAlias = Generator[tuple[Property, str], None, None]


def _ner_result(prop: str, value: str, engine: str) -> NERs:
    prop_ = NER_TYPES.get(prop)
    if prop_ is not None and test_name(value):
        if prop_ in (TAG_COMPANY, TAG_PERSON, TAG_LOCATION):
            log.debug(f"NER {engine}: [{prop_}] {value}")
            yield prop_, value
        if prop_ == TAG_LOCATION:
            for country in location_country(value):
                yield TAG_COUNTRY, country


def extract_ner_spacy(entity, text) -> NERs:
    for model in get_spacy_models(entity):
        # log.debug("NER tagging %d chars (%s)", len(text), model.lang)
        doc = model(text)
        for ent in doc.ents:
            yield from _ner_result(ent.label_, ent.text, "Spacy")


def extract_ner_flair(entity: EntityProxy, text: str) -> NERs:
    """Use flair as NER engine"""
    from flair.nn import Classifier
    from flair.splitter import SegtokSentenceSplitter

    # initialize sentence splitter
    splitter = SegtokSentenceSplitter()
    # use splitter to split text into list of sentences
    sentences = splitter.split(text)
    tagger = Classifier.load("ner")
    tagger.predict(sentences)
    for sentence in sentences:
        for label in sentence.get_labels():
            yield from _ner_result(label.value, label.data_point.text, "Flair")


@cache
def get_bert() -> "Pipeline":
    from transformers import pipeline

    return pipeline("ner", model=settings.bert_model, aggregation_strategy="simple")


def extract_ner_bert(entity: EntityProxy, text: str) -> NERs:
    """Transformers pipeline with BERT model"""
    ner = get_bert()
    results = ner(text)
    for res in results:
        yield from _ner_result(res["entity_group"], res["word"], "BERT")


def validate_person_name(name: str) -> bool:
    """Validate a person name if it contains at least one name symbol"""
    for _ in tag_person_name(Name(name), normalize_name).symbols:
        return True
    return False
