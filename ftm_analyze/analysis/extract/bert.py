"""BERT/Transformers NER extractor."""

import typing

from ftm_analyze.analysis.extract.base import (
    ExtractionContext,
    ExtractionResults,
    make_ner_result,
)
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from transformers import Pipeline

settings = Settings()


class BertExtractor:
    """Extract named entities using BERT transformers."""

    name = "bert"

    def __init__(self, model: str | None = None):
        self.model = model or settings.bert_model
        self._pipeline: "Pipeline | None" = None

    def _get_pipeline(self) -> "Pipeline":
        """Lazy load the transformers pipeline."""
        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline(
                "ner", model=self.model, aggregation_strategy="simple"
            )
        return self._pipeline

    def extract(self, context: ExtractionContext) -> ExtractionResults:
        """Extract named entities from text using BERT."""
        ner = self._get_pipeline()
        results = ner(context.text)

        for res in results:
            yield from make_ner_result(res["entity_group"], res["word"], self.name)
