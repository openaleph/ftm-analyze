import typing
from functools import cache

from ftmq.util import EntityProxy

from ftm_analyze.analysis.extract.base import NERs, get_device, ner_result
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from transformers import Pipeline

settings = Settings()

# Without a stride, the pipeline silently truncates the input to the model's
# max length (512 tokens). With it, the whole text is processed in windows
# overlapping by this many tokens, and entities found twice in the overlap are
# merged by the pipeline.
STRIDE = 64
# Fallback for tokenizers that don't define their max length (e.g.
# `fhswf/bert_de_ner`), otherwise the input isn't split into windows at all
# and the model fails on inputs longer than its position embeddings
MAX_LENGTH = 512


@cache
def _get_pipeline() -> "Pipeline":
    from transformers import pipeline
    from transformers.tokenization_utils_base import VERY_LARGE_INTEGER

    ner = pipeline(
        "ner",
        model=settings.bert_model,
        aggregation_strategy="simple",
        stride=STRIDE,
        device=get_device(),
    )
    if ner.tokenizer.model_max_length >= VERY_LARGE_INTEGER:
        ner.tokenizer.model_max_length = MAX_LENGTH
    return ner


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using BERT transformers."""
    ner = _get_pipeline()
    results = ner(text)
    for res in results:
        # the text at the offsets, not `word` (re-decoded tokens: `##rich`)
        start, end = res["start"], res["end"]
        yield from ner_result(res["entity_group"], text[start:end], "BERT", start, end)
