"""Resolution pipeline for processing mentions through composable stages."""

from dataclasses import dataclass, field
from typing import Any, Generator, Protocol

from anystore.logging import get_logger
from followthemoney import model
from followthemoney.schema import Schema
from ftmq.util import EntityProxy

from ftm_analyze.analysis.resolve.mention import Mention

log = get_logger(__name__)


@dataclass
class ResolutionContext:
    """Context passed through resolution stages."""

    entity: EntityProxy
    languages: list[str] = field(default_factory=list)
    countries: set[str] = field(default_factory=set)

    # Caches for expensive lookups (shared across stages)
    _cache: dict[str, Any] = field(default_factory=dict)

    def get_schema(self, schema_name: str) -> Schema | None:
        """Get FTM schema by name."""
        return model.get(schema_name)


class ResolutionStage(Protocol):
    """Protocol for resolution pipeline stages.

    Each stage can:
    - Modify mention attributes (resolved_values, canonical_value, etc.)
    - Reject mentions by calling mention.reject()
    - Pass through unchanged
    """

    name: str

    def process(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Process a mention and return the (possibly modified) mention."""
        ...


class ResolutionPipeline:
    """Composable pipeline for mention resolution.

    Processes mentions through a series of stages. Each stage can modify
    the mention or reject it. Processing stops early if a mention is rejected.
    """

    def __init__(self, stages: list[ResolutionStage] | None = None):
        self.stages = stages or []

    def add_stage(self, stage: ResolutionStage) -> "ResolutionPipeline":
        """Add a stage to the pipeline. Returns self for chaining."""
        self.stages.append(stage)
        return self

    def resolve(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Process a single mention through all stages.

        Returns the mention after processing. Check mention.is_rejected
        to determine if the mention should be discarded.
        """
        for stage in self.stages:
            if mention.is_rejected:
                log.debug(
                    "Mention rejected",
                    stage=mention.rejection_stage,
                    reason=mention.rejection_reason,
                )
                break

            mention = stage.process(mention, context)

        return mention

    def resolve_all(
        self,
        mentions: list[Mention],
        context: ResolutionContext,
    ) -> Generator[Mention, None, None]:
        """Process multiple mentions, yielding only valid ones."""
        for mention in mentions:
            resolved = self.resolve(mention, context)
            if not resolved.is_rejected:
                yield resolved

    def __len__(self) -> int:
        return len(self.stages)

    def __repr__(self) -> str:
        stage_names = [s.name for s in self.stages]
        return f"<ResolutionPipeline stages={stage_names}>"
