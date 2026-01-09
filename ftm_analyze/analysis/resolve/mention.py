"""Mention data class representing an extracted mention."""

from dataclasses import dataclass, field
from typing import Literal, cast

from rigour.names import pick_name

NerTag = Literal["PER", "ORG", "LOC", "OTHER"]
NER_TAGS: set[NerTag] = {"PER", "ORG", "LOC"}


@dataclass
class Mention:
    """Data class representing an extracted mention.

    This is a pure data class - resolution logic is in the pipeline stages.
    """

    key: str
    tag: str  # PER, ORG, LOC, EMAIL, PHONE, IBAN, OTHER
    values: set[str]
    entity_id: str
    sources: set[str] = field(default_factory=set)

    # Resolution state (set by pipeline stages)
    ner_tag: NerTag = "OTHER"
    resolved_values: set[str] | None = None
    canonical_value: str | None = None
    resolved_schema: str | None = None
    resolved_entity_id: str | None = None

    # Validation state
    is_valid: bool = True
    is_rejected: bool = False
    rejection_reason: str | None = None
    rejection_stage: str | None = None

    @property
    def caption(self) -> str:
        """Get the best name for this mention."""
        if self.canonical_value:
            return self.canonical_value
        values = self.resolved_values or self.values
        caption = pick_name(list(values))
        if caption is None:
            raise ValueError("No caption available - empty values")
        return caption

    @property
    def all_names(self) -> set[str]:
        """Get all name variations for this mention."""
        names: set[str] = set()
        names.add(self.caption)
        names.update(self.values)
        if self.resolved_values:
            names.update(self.resolved_values)
        return {n for n in names if n}

    @property
    def annotate_values(self) -> set[str]:
        """Get values suitable for annotation (uses resolved values if available)."""
        values = self.resolved_values or self.values
        return {v for v in values if v}

    def reject(self, reason: str, stage: str) -> None:
        """Mark this mention as rejected."""
        self.is_rejected = True
        self.is_valid = False
        self.rejection_reason = reason
        self.rejection_stage = stage

    @classmethod
    def from_aggregated(
        cls,
        key: str,
        tag: str,
        values: set[str],
        entity_id: str,
        sources: set[str] | None = None,
    ) -> "Mention":
        """Create a Mention from aggregated extraction results."""
        ner_tag: NerTag = cast(NerTag, tag) if tag in NER_TAGS else "OTHER"

        return cls(
            key=key,
            tag=tag,
            values=values,
            entity_id=entity_id,
            sources=sources or set(),
            ner_tag=ner_tag,
        )
