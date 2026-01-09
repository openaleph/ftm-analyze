"""Core logic for entity analysis."""

from typing import Generator, Iterable

from anystore.decorators import error_handler
from anystore.io import logged_items
from anystore.logging import get_logger
from followthemoney.proxy import EntityProxy

from ftm_analyze.analysis.analyzer import Analyzer
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()


@error_handler(logger=log)
def analyze_entity(
    entity: EntityProxy,
    resolve_mentions: bool | None = settings.resolve_mentions,
    annotate: bool | None = settings.annotate,
    validate_names: bool | None = settings.validate_names,
    refine_mentions: bool | None = settings.refine_mentions,
    refine_locations: bool | None = settings.refine_locations,
) -> Generator[EntityProxy, None, None]:
    """Analyze an Entity.

    Args:
        entity: The entity proxy to analyze
        resolve_mentions: Convert known mentions into actual entities via juditha
        annotate: Annotate extracted patterns, names and mentions in indexText
        validate_names: Validate names against juditha name datasets
        refine_mentions: Use juditha ML classifier to refine NER tags
        refine_locations: Refine locations using geonames

    Yields:
        A generator of entity fragments (mentions, resolved entities, etc.)
    """
    analyzer = Analyzer(
        entity,
        use_juditha_lookup=resolve_mentions,
        annotate=annotate,
        use_juditha_validator=validate_names,
        use_juditha_classifier=refine_mentions,
        use_geonames=refine_locations,
    )
    analyzer.feed(entity)
    yield from analyzer.flush()


def analyze_entities(
    entities: Iterable[EntityProxy],
    resolve_mentions: bool | None = settings.resolve_mentions,
    annotate: bool | None = settings.annotate,
    validate_names: bool | None = settings.validate_names,
    refine_mentions: bool | None = settings.refine_mentions,
    refine_locations: bool | None = settings.refine_locations,
) -> Generator[EntityProxy, None, None]:
    """Analyze multiple entities.

    Args:
        entities: Iterable of entity proxies to analyze
        resolve_mentions: Convert known mentions into actual entities via juditha
        annotate: Annotate extracted patterns, names and mentions in indexText
        validate_names: Validate names against juditha name datasets
        refine_mentions: Use juditha ML classifier to refine NER tags
        refine_locations: Refine locations using geonames

    Yields:
        A generator of entity fragments from all analyzed entities
    """
    for e in logged_items(entities, "Analyze", 10, item_name="Entity", logger=log):
        yield from analyze_entity(
            e,
            resolve_mentions=resolve_mentions,
            annotate=annotate,
            validate_names=validate_names,
            refine_mentions=refine_mentions,
            refine_locations=refine_locations,
        )
