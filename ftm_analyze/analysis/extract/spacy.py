"""spaCy NER extractor."""

from functools import lru_cache

from followthemoney.types import registry
from rigour.langs import list_to_alpha3

from ftm_analyze.analysis.extract.base import (
    ExtractionContext,
    ExtractionResults,
    make_ner_result,
)
from ftm_analyze.settings import Settings

settings = Settings()
SPACY_MODELS = settings.spacy_models.model_dump()


@lru_cache(maxsize=5)
def _load_model(model: str):
    """Load the spaCy model for the specified language."""
    import spacy

    return spacy.load(model)


class SpacyExtractor:
    """Extract named entities using spaCy NER models."""

    name = "spacy"

    def __init__(self, default_lang: str | None = None):
        self.default_lang = default_lang or settings.ner_default_lang

    def _get_models(self, context: ExtractionContext):
        """Iterate over the NER models applicable to the given entity."""
        languages = context.entity.get_type_values(registry.language)
        models = set()
        for lang in list_to_alpha3(languages):
            model = SPACY_MODELS.get(lang)
            if model is not None:
                models.add(model)
        if not models:
            models.add(SPACY_MODELS[self.default_lang])
        for model in models:
            yield _load_model(model)

    def extract(self, context: ExtractionContext) -> ExtractionResults:
        """Extract named entities from text using spaCy."""
        for model in self._get_models(context):
            doc = model(context.text)
            for ent in doc.ents:
                yield from make_ner_result(ent.label_, ent.text, self.name)
