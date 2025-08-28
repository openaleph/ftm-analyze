"""Wrap cached rigour taggers loading into thread-safe calls"""

import importlib
import sys
import threading

import cachetools
from anystore.logging import get_logger
from rigour.names import normalize_name, tagging
from rigour.names.tagging import _get_org_tagger, _get_person_tagger

log = get_logger(__name__)
current_thread = threading.current_thread().ident

# Create shared caches and locks for each tagger
_person_tagger_cache = cachetools.LRUCache(maxsize=1)
_person_tagger_lock = threading.RLock()

_org_tagger_cache = cachetools.LRUCache(maxsize=1)
_org_tagger_lock = threading.RLock()

# Store original function implementations without their @cache decorators
original_person_tagger = (
    _get_person_tagger.__wrapped__
    if hasattr(_get_person_tagger, "__wrapped__")
    else _get_person_tagger
)
original_org_tagger = (
    _get_org_tagger.__wrapped__
    if hasattr(_get_org_tagger, "__wrapped__")
    else _get_org_tagger
)

PERSON_TAGGER = original_person_tagger(normalize_name)
ORG_TAGGER = original_org_tagger(normalize_name)


def patch_rigour_taggers():
    """Patch _get_person_tagger and _get_org_tagger for thread safety"""

    # Patch _get_person_tagger
    @cachetools.cached(cache=_person_tagger_cache, lock=_person_tagger_lock)
    def thread_safe_get_person_tagger(*args, **kwargs):
        log.info("Loading thread safe person tagger...", thread=current_thread)
        return PERSON_TAGGER

    tagging._get_person_tagger = thread_safe_get_person_tagger

    # Patch _get_org_tagger
    @cachetools.cached(cache=_org_tagger_cache, lock=_org_tagger_lock)
    def thread_safe_get_org_tagger(*args, **kwargs):
        log.info("Loading thread safe org tagger...", thread=current_thread)
        return ORG_TAGGER

    tagging._get_org_tagger = thread_safe_get_org_tagger


# Apply patches before importing
patch_rigour_taggers()

# Force reload the ftmq.util module that depend on the patched functions
if "ftmq.util" in sys.modules:
    importlib.reload(sys.modules["ftmq.util"])

from ftmq.util import get_name_symbols, get_symbols  # noqa: E402

__all__ = ["get_symbols", "get_name_symbols", "PERSON_TAGGER", "ORG_TAGGER"]
