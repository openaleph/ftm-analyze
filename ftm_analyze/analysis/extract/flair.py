"""Flair NER extractor."""

from ftm_analyze.analysis.extract.base import (
    ExtractionContext,
    ExtractionResults,
    make_ner_result,
)


class FlairExtractor:
    """Extract named entities using Flair NER."""

    name = "flair"

    def __init__(self):
        self._tagger = None
        self._splitter = None

    def _ensure_loaded(self):
        """Lazy load Flair components."""
        if self._tagger is None:
            from flair.nn import Classifier
            from flair.splitter import SegtokSentenceSplitter

            self._splitter = SegtokSentenceSplitter()
            self._tagger = Classifier.load("ner")

    def extract(self, context: ExtractionContext) -> ExtractionResults:
        """Extract named entities from text using Flair."""
        self._ensure_loaded()

        sentences = self._splitter.split(context.text)
        self._tagger.predict(sentences)

        for sentence in sentences:
            for label in sentence.get_labels():
                yield from make_ner_result(
                    label.value, label.data_point.text, self.name
                )
