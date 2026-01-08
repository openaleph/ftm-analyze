import typing

from anystore.functools import weakref_cache as cache
from ftmq.util import EntityProxy

from ftm_analyze.analysis.extract.base import NERs, ner_result
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from gliner import GLiNER

settings = Settings()

LABELS = ["person", "organization", "location"]


@cache
def _get_model() -> "GLiNER":
    from gliner import GLiNER

    return GLiNER.from_pretrained(settings.gliner_model)


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using GLiNER zero-shot NER."""
    model = _get_model()
    entities = model.predict_entities(text, LABELS, threshold=settings.gliner_threshold)
    for ent in entities:
        yield from ner_result(ent["label"], ent["text"], "GLiNER")
