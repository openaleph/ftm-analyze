import typing

from anystore.functools import weakref_cache as cache
from ftmq.util import EntityProxy

from ftm_analyze.analysis.extract.base import NERs, ner_result
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from transformers import Pipeline

settings = Settings()


@cache
def _get_pipeline() -> "Pipeline":
    from transformers import pipeline

    return pipeline("ner", model=settings.bert_model, aggregation_strategy="simple")


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using BERT transformers."""
    ner = _get_pipeline()
    results = ner(text)
    for res in results:
        yield from ner_result(res["entity_group"], res["word"], "BERT")
