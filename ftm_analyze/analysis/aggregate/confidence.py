"""Confidence scoring using fastText model."""

from pathlib import Path
from typing import Any

import numpy as np
from anystore.logging import get_logger

from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()


class ConfidenceScorer:
    """Score extraction confidence using fastText model.

    Uses the FTM type prediction model to determine if extracted values
    are likely to be valid entity names vs. "trash".
    """

    def __init__(
        self,
        model_path: Path | None = None,
        threshold: float | None = None,
    ):
        self.model_path = model_path or settings.ner_type_model_path
        self.threshold = threshold or settings.ner_type_model_confidence
        self._model: Any = None
        self._max_entropy: float | None = None

    @property
    def model(self) -> Any:
        """Lazy load the fastText model."""
        if self._model is None:
            import fasttext

            fasttext.FastText.eprint = lambda x: None  # Suppress warnings
            self._model = fasttext.load_model(str(self.model_path))
            n_labels = len(self._model.get_labels())
            self._max_entropy = float(np.log(n_labels))
        return self._model

    @property
    def max_entropy(self) -> float:
        """Get max entropy for confidence calculation."""
        if self._max_entropy is None:
            _ = self.model  # Trigger lazy load
        assert self._max_entropy is not None  # Set during model loading
        return self._max_entropy

    def score(self, values: set[str]) -> tuple[list[str], list[float]]:
        """Score a set of values and return labels with confidences.

        Args:
            values: Set of text values to score

        Returns:
            Tuple of (labels, confidences) for each value
        """
        from normality import normalize

        # Clean input like the old FTTypeModel did
        texts = [normalize(v, lowercase=True, latinize=True) or v for v in values]
        # Get all labels for entropy calculation
        labels, scores = self.model.predict(texts, k=-1)

        # Extract top labels
        top_labels = [label[0].replace("__label__", "") for label in labels]

        # Calculate confidence from entropy
        # Lower entropy = higher confidence
        confidences = 1 + (scores * np.log(scores)).sum(axis=1) / self.max_entropy
        return top_labels, confidences.tolist()

    def is_valid(self, values: set[str]) -> bool:
        """Check if values pass confidence threshold.

        Returns False if any value is labeled "trash" or below threshold.
        """
        if not self.threshold:
            return True

        labels, confidences = self.score(values)
        for label, confidence in zip(labels, confidences):
            if label == "trash":
                log.debug(
                    "ConfidenceScorer trash",
                    values=values,
                    confidence=confidence,
                    threshold=self.threshold,
                )
                return False
            if confidence < self.threshold:
                log.debug(
                    "ConfidenceScorer too low",
                    values=values,
                    label=label,
                    confidence=confidence,
                    threshold=self.threshold,
                )
                return False
        return True
