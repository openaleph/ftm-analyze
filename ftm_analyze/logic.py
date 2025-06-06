from typing import Generator, Iterable

from anystore.decorators import error_handler
from anystore.io import logged_items
from anystore.logging import get_logger
from followthemoney.proxy import EntityProxy

from ftm_analyze.analysis.analyzer import Analyzer

log = get_logger(__name__)


@error_handler(logger=log)
def analyze_entity(entity: EntityProxy) -> Generator[EntityProxy, None, None]:
    analyzer = Analyzer(entity)
    analyzer.feed(entity)
    yield from analyzer.flush()


def analyze_entities(
    entities: Iterable[EntityProxy],
) -> Generator[EntityProxy, None, None]:
    for e in logged_items(entities, "Analyze", item_name="Entity", logger=log):
        yield from analyze_entity(e)
