"""Extraction tracer for debugging and visibility into the pipeline."""

from collections import defaultdict

from anystore.logging import get_logger
from anystore.model import BaseModel

log = get_logger(__name__)


class TraceSummary(BaseModel):
    """Summary of extraction pipeline execution."""

    # Extraction stats
    extractions_total: int = 0
    extractions_accepted: int = 0
    extractions_rejected: int = 0
    extractions_by_source: dict[str, int] = {}
    extractions_by_tag: dict[str, int] = {}

    # Aggregation stats
    aggregated_total: int = 0
    aggregated_by_tag: dict[str, int] = {}

    # Resolution stats
    resolution_total: int = 0
    resolution_accepted: int = 0
    resolution_rejected: int = 0
    rejection_by_stage: dict[str, int] = {}
    rejection_by_reason: dict[str, int] = {}

    # Entity creation stats
    entities_created: int = 0
    entities_by_schema: dict[str, int] = {}


class ExtractionTracer:
    """Traces extraction pipeline execution for debugging.

    Collects statistics about extractions, aggregations, resolutions,
    and entity creation to help diagnose issues in the pipeline.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._reset()

    def _reset(self) -> None:
        """Reset all counters."""
        self._extractions_total = 0
        self._extractions_accepted = 0
        self._extractions_rejected = 0
        self._extractions_by_source: dict[str, int] = defaultdict(int)
        self._extractions_by_tag: dict[str, int] = defaultdict(int)
        self._extraction_rejections: dict[str, int] = defaultdict(int)

        self._aggregated_total = 0
        self._aggregated_by_tag: dict[str, int] = defaultdict(int)

        self._resolution_total = 0
        self._resolution_accepted = 0
        self._resolution_rejected = 0
        self._rejection_by_stage: dict[str, int] = defaultdict(int)
        self._rejection_by_reason: dict[str, int] = defaultdict(int)

        self._entities_created = 0
        self._entities_by_schema: dict[str, int] = defaultdict(int)

    def trace_extraction(
        self,
        value: str,
        tag: str,
        source: str,
        accepted: bool,
        reason: str | None = None,
    ) -> None:
        """Trace an extraction event."""
        if not self.enabled:
            return

        self._extractions_total += 1
        self._extractions_by_source[source] += 1

        if accepted:
            self._extractions_accepted += 1
            self._extractions_by_tag[tag] += 1
            log.debug("Extraction accepted", tag=tag, value=value, source=source)
        else:
            self._extractions_rejected += 1
            reason_key = reason or "unknown"
            self._extraction_rejections[reason_key] += 1
            log.debug(
                "Extraction rejected",
                tag=tag,
                value=value,
                source=source,
                reason=reason,
            )

    def trace_aggregation(self, key: str, tag: str, value_count: int) -> None:
        """Trace an aggregation event."""
        if not self.enabled:
            return

        self._aggregated_total += 1
        self._aggregated_by_tag[tag] += 1
        log.debug("Aggregated", tag=tag, key=key, value_count=value_count)

    def trace_resolution(
        self,
        mention_key: str,
        stage: str,
        accepted: bool,
        reason: str | None = None,
        changes: dict[str, str] | None = None,
    ) -> None:
        """Trace a resolution stage event."""
        if not self.enabled:
            return

        self._resolution_total += 1

        if accepted:
            self._resolution_accepted += 1
            if changes:
                log.debug(
                    "Resolution applied",
                    stage=stage,
                    mention_key=mention_key,
                    changes=changes,
                )
        else:
            self._resolution_rejected += 1
            self._rejection_by_stage[stage] += 1
            if reason:
                self._rejection_by_reason[reason] += 1
            log.debug(
                "Resolution rejected",
                stage=stage,
                mention_key=mention_key,
                reason=reason,
            )

    def trace_entity_created(self, schema: str, entity_id: str) -> None:
        """Trace entity creation."""
        if not self.enabled:
            return

        self._entities_created += 1
        self._entities_by_schema[schema] += 1
        log.debug("Entity created", schema=schema, entity_id=entity_id)

    def get_summary(self) -> TraceSummary:
        """Get summary of all traced events."""
        return TraceSummary(
            extractions_total=self._extractions_total,
            extractions_accepted=self._extractions_accepted,
            extractions_rejected=self._extractions_rejected,
            extractions_by_source=dict(self._extractions_by_source),
            extractions_by_tag=dict(self._extractions_by_tag),
            aggregated_total=self._aggregated_total,
            aggregated_by_tag=dict(self._aggregated_by_tag),
            resolution_total=self._resolution_total,
            resolution_accepted=self._resolution_accepted,
            resolution_rejected=self._resolution_rejected,
            rejection_by_stage=dict(self._rejection_by_stage),
            rejection_by_reason=dict(self._rejection_by_reason),
            entities_created=self._entities_created,
            entities_by_schema=dict(self._entities_by_schema),
        )

    def log_summary(self) -> None:
        """Log a summary of the trace."""
        if not self.enabled:
            return

        summary = self.get_summary()
        log.info(
            "Pipeline summary",
            extractions_accepted=summary.extractions_accepted,
            extractions_total=summary.extractions_total,
            aggregated=summary.aggregated_total,
            resolved=summary.resolution_accepted,
            resolution_total=summary.resolution_total,
            entities=summary.entities_created,
        )

    def reset(self) -> None:
        """Reset all counters for a new run."""
        self._reset()
