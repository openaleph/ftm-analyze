from functools import lru_cache

import spacy
from anystore.logging import get_logger
from fingerprints import clean_entity_prefix
from followthemoney.types import registry
from normality import collapse_spaces
from rigour.langs import list_to_alpha3

from ftm_analyze.analysis.country import location_country
from ftm_analyze.analysis.util import TAG_COMPANY, TAG_COUNTRY, TAG_LOCATION, TAG_PERSON
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()

NAME_MAX_LENGTH = 100
NAME_MIN_LENGTH = 4
# https://spacy.io/api/annotation#named-entities
SPACY_TYPES = {
    "PER": TAG_PERSON,
    "PERSON": TAG_PERSON,
    "ORG": TAG_COMPANY,
    "LOC": TAG_LOCATION,
    "GPE": TAG_LOCATION,
}
NER_MODELS = settings.ner_models.model_dump()


def clean_name(text):
    if text is None or len(text) > NAME_MAX_LENGTH:
        return
    text = clean_entity_prefix(text)
    text = collapse_spaces(text)
    if text is None or len(text) <= NAME_MIN_LENGTH or " " not in text:
        return
    return text


@lru_cache(maxsize=5)
def _load_model(model):
    """Load the spaCy model for the specified language"""
    return spacy.load(model)


def get_models(entity):
    """Iterate over the NER models applicable to the given entity."""
    languages = entity.get_type_values(registry.language)
    models = set()
    for lang in list_to_alpha3(languages):
        model = NER_MODELS.get(lang)
        if model is not None:
            models.add(model)
    for model in models:
        yield _load_model(model)


def extract_entities(entity, text):
    for model in get_models(entity):
        # log.debug("NER tagging %d chars (%s)", len(text), model.lang)
        doc = model(text)
        for ent in doc.ents:
            prop = SPACY_TYPES.get(ent.label_)
            if prop is None:
                continue
            if prop in (TAG_COMPANY, TAG_PERSON):
                name = clean_name(ent.text)
                yield (prop, name)
            if prop == TAG_LOCATION:
                for country in location_country(ent.text):
                    yield (TAG_COUNTRY, country)
