"""Geonames-based location refinement stage."""

from functools import lru_cache

import jellyfish
from anystore.logging import get_logger
from geonames_tagger.tagger import Location, tag_locations
from geonames_tagger.util import text_norm

from ftm_analyze.analysis.resolve.mention import Mention
from ftm_analyze.analysis.resolve.pipeline import ResolutionContext
from ftm_analyze.analysis.resolve.stages.rigour import is_rigour_person

log = get_logger(__name__)
LRU = 10_000


@lru_cache(LRU)
def refine_location(name: str) -> Location | None:
    """Refine extracted locations against geonames_tagger."""
    # Person names that happen to match locations (e.g., "Christina" in Canada)
    if is_rigour_person(name):
        return None

    try:
        for result in tag_locations(name):
            if jellyfish.jaro_similarity(text_norm(name), result.name) > 0.9:
                return result
    except Exception as e:
        log.error(
            f"Could not load geonames-tagger: `{e}`. Make sure local "
            "automaton.json data exists!"
        )
        return None
    return None


class GeonamesStage:
    """Refine location mentions using geonames data.

    This stage:
    - Validates that LOC mentions are actual known locations
    - Adds canonical location names
    - Rejects person names that were misclassified as locations
    """

    name = "geonames"

    def __init__(self, reject_unmatched: bool = False):
        """Initialize geonames stage.

        Args:
            reject_unmatched: If True, reject LOC mentions not found in geonames
        """
        self.reject_unmatched = reject_unmatched

    def process(self, mention: Mention, context: ResolutionContext) -> Mention:
        """Refine location mentions against geonames."""
        # Only process location mentions
        if mention.ner_tag != "LOC":
            return mention

        values = mention.resolved_values or mention.values
        if not values:
            return mention

        # Try to match any value against geonames
        for value in values:
            location = refine_location(value)
            if location:
                log.debug("Geonames matched", value=value, location=location.name)
                mention.canonical_value = location.name

                # Add the country if available
                if location.country_code:
                    context.countries.add(location.country_code)

                return mention

        # No match found
        if self.reject_unmatched:
            mention.reject("Location not found in geonames", self.name)

        return mention
