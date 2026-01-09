"""Unified aggregator for extraction results."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Generator

from anystore.logging import get_logger
from rigour.names import normalize_name

from ftm_analyze.analysis.aggregate.confidence import ConfidenceScorer
from ftm_analyze.analysis.extract.base import (
    TAG_LOC,
    TAG_ORG,
    TAG_PER,
    ExtractionResult,
)

log = get_logger(__name__)

MAX_RESULTS = 10_000

# Tags that should use name normalization for deduplication
NER_TAGS = {TAG_PER, TAG_ORG, TAG_LOC}


@dataclass
class AggregatedResult:
    """Aggregated extraction result with deduplication."""

    key: str
    tag: str
    values: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    max_confidence: float | None = None

    def add_value(
        self, value: str, source: str, confidence: float | None = None
    ) -> None:
        """Add a value to this aggregated result."""
        self.values.add(value)
        self.sources.add(source)
        if confidence is not None:
            if self.max_confidence is None or confidence > self.max_confidence:
                self.max_confidence = confidence


class Aggregator:
    """Unified aggregator for all extraction results.

    Handles deduplication, optional confidence filtering, and tracing.
    """

    def __init__(
        self,
        use_confidence: bool = True,
        confidence_threshold: float | None = None,
    ):
        self.results: dict[tuple[str, str], AggregatedResult] = {}
        self.scorer = (
            ConfidenceScorer(threshold=confidence_threshold) if use_confidence else None
        )
        self._count = 0

        # Tracing data
        self.accepted_count = 0
        self.rejected_count = 0
        self.rejection_reasons: dict[str, int] = defaultdict(int)

    def _make_key(self, result: ExtractionResult) -> str | None:
        """Generate deduplication key for a result."""
        value: str | None = result.value
        if not value:
            return None

        # Use name normalization for NER tags
        if result.tag in NER_TAGS:
            # First clean via FTM type system if we have a prop
            if result.prop:
                value = result.prop.type.node_id_safe(value)
            # Then normalize the name
            return normalize_name(value) if value else None

        # For patterns, use FTM type cleaning
        if result.prop:
            return result.prop.type.node_id_safe(value)

        return value

    def add(self, result: ExtractionResult) -> bool:
        """Add an extraction result.

        Returns True if the result was accepted, False if rejected.
        """
        # Limit total results to prevent memory issues
        if self._count >= MAX_RESULTS:
            self.rejection_reasons["max_results_exceeded"] += 1
            self.rejected_count += 1
            return False

        key = self._make_key(result)
        if not key:
            self.rejection_reasons["invalid_key"] += 1
            self.rejected_count += 1
            return False

        lookup_key = (key, result.tag)

        # Get or create aggregated result
        if lookup_key not in self.results:
            self.results[lookup_key] = AggregatedResult(key=key, tag=result.tag)
            self._count += 1

        self.results[lookup_key].add_value(
            result.value,
            result.source,
            result.confidence,
        )
        self.accepted_count += 1
        return True

    def iter_results(self) -> Generator[AggregatedResult, None, None]:
        """Iterate over aggregated results, applying confidence filtering."""
        for agg_result in self.results.values():
            if not agg_result.values:
                continue

            # Apply confidence filtering for NER results
            if self.scorer and agg_result.tag in NER_TAGS:
                if not self.scorer.is_valid(agg_result.values):
                    log.debug(
                        "Confidence filter rejected",
                        tag=agg_result.tag,
                        values=agg_result.values,
                    )
                    continue

                log.debug(
                    "Aggregated result",
                    tag=agg_result.tag,
                    key=agg_result.key,
                    values=agg_result.values,
                    sources=agg_result.sources,
                )

            yield agg_result

    def get_trace_summary(self) -> dict[str, int | dict[str, int]]:
        """Get tracing summary for debugging."""
        return {
            "total_added": self.accepted_count + self.rejected_count,
            "accepted": self.accepted_count,
            "rejected": self.rejected_count,
            "unique_results": len(self.results),
            "rejection_reasons": dict(self.rejection_reasons),
        }

    def __len__(self) -> int:
        return len(self.results)
