"""Juditha-based classification, validation, and lookup stages."""

from functools import lru_cache

from anystore.logging import get_logger
from juditha import lookup as juditha_lookup
from juditha import validate_name
from juditha.predict import predict_schema

from ftm_analyze.analysis.resolve.mention import Mention, NerTag
from ftm_analyze.analysis.resolve.pipeline import ResolutionContext
from ftm_analyze.analysis.resolve.stages.rigour import classify_name_rigour

log = get_logger(__name__)
LRU = 10_000


@lru_cache(LRU)
def classify_mention_juditha(name: str, original_tag: NerTag) -> NerTag:
    """Classify a mention using juditha's schema prediction.

    Uses the original NER tag as context for disambiguation.
    """
    for result in predict_schema(name):
        if result.score > 0.9:
            # Handle LOC/OTHER predictions
            if result.ner_tag in ("LOC", "OTHER"):
                if original_tag != "LOC":
                    return "OTHER"

            # Keep ORG for longer names even if juditha predicts PER
            if original_tag == "ORG" and result.ner_tag == "PER":
                if len(name) > 20:
                    return "ORG"

            return result.ner_tag

    # Fall back to rigour classification
    guess = classify_name_rigour(name)
    if guess == "ORG":
        return "ORG"

    return "OTHER"


class JudithaClassifierStage:
    """Classify mentions using juditha's ML model.

    Uses fasttext model trained on FTM entity types to predict
    whether a mention is a person, organization, location, or other.
    """

    name = "juditha_classifier"

    def __init__(self, confidence_threshold: float = 0.9):
        self.confidence_threshold = confidence_threshold

    def process(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Classify mention using juditha prediction."""
        values = mention.resolved_values or mention.values
        if not values:
            return mention

        name = next(iter(values))
        classified_tag = classify_mention_juditha(name, mention.ner_tag)

        if classified_tag != mention.ner_tag:
            log.debug(
                f"Juditha reclassified: {name} [{mention.ner_tag} -> {classified_tag}]"
            )
            mention.ner_tag = classified_tag

        # Reject if classified as OTHER
        if mention.ner_tag == "OTHER":
            mention.reject("Classified as OTHER by juditha", self.name)

        return mention


class JudithaValidatorStage:
    """Validate person names against known name datasets.

    Uses juditha's name validation to check if a PER mention
    contains recognizable name tokens.
    """

    name = "juditha_validator"

    def process(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Validate person names using juditha."""
        # Only validate person mentions
        if mention.ner_tag != "PER":
            return mention

        values = mention.resolved_values or mention.values
        if not values:
            return mention

        name = next(iter(values))

        if not validate_name(name):
            log.debug("Juditha rejected invalid name", name=name)
            mention.reject("Name validation failed", self.name)

        return mention


class JudithaLookupStage:
    """Lookup mentions against known entity datasets.

    Uses juditha's entity lookup to find matching entities
    and potentially resolve to canonical forms.
    """

    name = "juditha_lookup"

    def __init__(self, threshold: float = 0.8):
        """Initialize lookup stage.

        Args:
            threshold: Minimum score for a match
        """
        self.threshold = threshold

    def process(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Lookup mention in juditha entity store."""
        values = mention.resolved_values or mention.values
        if not values:
            return mention

        name = next(iter(values))

        try:
            # Lookup in juditha
            result = juditha_lookup(name, threshold=self.threshold)
            if result and result.score >= self.threshold:
                log.debug("Juditha lookup matched", name=name, caption=result.caption)

                mention.canonical_value = result.caption

                # Add any resolved names
                if result.names:
                    if mention.resolved_values is None:
                        mention.resolved_values = set()
                    mention.resolved_values.update(result.names)

                # Determine schema from schemata
                if result.schemata:
                    mention.resolved_schema = next(iter(result.schemata))

                # Add countries to context
                if result.countries:
                    context.countries.update(result.countries)

        except Exception as e:
            log.debug("Juditha lookup failed", error=str(e))

        return mention
