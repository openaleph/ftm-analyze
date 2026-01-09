from functools import lru_cache

from followthemoney.types import registry
from ftmq.util import EntityProxy
from rigour.langs import list_to_alpha3

from ftm_analyze.analysis.extract.base import NERs, ner_result
from ftm_analyze.settings import Settings

settings = Settings()
SPACY_MODELS = settings.spacy_models.model_dump()


@lru_cache(maxsize=5)
def _load_model(model):
    """Load the spaCy model for the specified language"""
    import spacy

    return spacy.load(model)


def _get_models(entity: EntityProxy):
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
        yield _load_model(model)


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using spaCy."""
    for model in _get_models(entity):
        doc = model(text)
        for ent in doc.ents:
            yield from ner_result(ent.label_, ent.text, "Spacy")
