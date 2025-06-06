import logging

from banal import ensure_list
from countrytagger import tag_place

log = logging.getLogger(__name__)


def location_country(location) -> list[str]:
    res = tag_place(location)
    if res is None:
        return []
    return ensure_list(res[2])
