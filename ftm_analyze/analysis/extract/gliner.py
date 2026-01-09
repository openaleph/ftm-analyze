"""GLiNER zero-shot NER extractor."""

import typing

from ftm_analyze.analysis.extract.base import (
    ExtractionContext,
    ExtractionResults,
    make_ner_result,
)
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from gliner import GLiNER

settings = Settings()

DEFAULT_LABELS = ["person", "organization", "location"]


class GlinerExtractor:
    """Extract named entities using GLiNER zero-shot NER."""

    name = "gliner"

    def __init__(
        self,
        model: str | None = None,
        labels: list[str] | None = None,
        threshold: float | None = None,
    ):
        self.model_name = model or settings.gliner_model
        self.labels = labels or DEFAULT_LABELS
        self.threshold = threshold or settings.gliner_threshold
        self._model: "GLiNER | None" = None

    def _get_model(self) -> "GLiNER":
        """Lazy load the GLiNER model."""
        if self._model is None:
            from gliner import GLiNER

            self._model = GLiNER.from_pretrained(self.model_name)
        return self._model

    def extract(self, context: ExtractionContext) -> ExtractionResults:
        """Extract named entities from text using GLiNER."""
        model = self._get_model()
        entities = model.predict_entities(
            context.text, self.labels, threshold=self.threshold
        )

        for ent in entities:
            yield from make_ner_result(ent["label"], ent["text"], self.name)
