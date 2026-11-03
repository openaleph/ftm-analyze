import re
import typing
from functools import cache
from typing import Generator

from ftmq.util import EntityProxy

from ftm_analyze.analysis.extract.base import NERs, get_device, ner_result
from ftm_analyze.settings import Settings

if typing.TYPE_CHECKING:
    from gliner import GLiNER

settings = Settings()

LABELS = ["person", "organization", "location"]

# GLiNER's default ("whitespace") word splitter, its `max_len` counts these
WORDS = re.compile(r"\w+(?:[-_]\w+)*|\S")
SENTENCES = re.compile(r"(?<=[.!?])\s+")


@cache
def _get_model() -> "GLiNER":
    from gliner import GLiNER

    return GLiNER.from_pretrained(settings.gliner_model, map_location=get_device())


def chunk_text(text: str, size: int) -> Generator[tuple[int, int], None, None]:
    """Pack sentences into chunks of max `size` words (as GLiNER counts them),
    overlong sentences are split at word boundaries. Yields the (start, end)
    offsets of the chunks in `text`."""
    start: int | None = None
    end = length = 0
    sentence_start = 0
    for separator in [*SENTENCES.finditer(text), None]:
        sentence_end = separator.start() if separator else len(text)
        spans = [m.span() for m in WORDS.finditer(text, sentence_start, sentence_end)]
        for i in range(0, len(spans), size):
            part = spans[i : i + size]
            if start is not None and length + len(part) > size:
                yield start, end
                start, length = None, 0
            if start is None:
                start = part[0][0]
            end = part[-1][1]
            length += len(part)
        sentence_start = separator.end() if separator else len(text)
    if start is not None:
        yield start, end


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using GLiNER zero-shot NER."""
    model = _get_model()
    # GLiNER silently truncates its input to `max_len` words (384), so longer
    # texts are split into chunks of that size (sentence packed, to not cut
    # names in half)
    chunks = list(chunk_text(text, model.config.max_len))
    results = model.inference(
        [text[start:end] for start, end in chunks],
        LABELS,
        threshold=settings.gliner_threshold,
    )
    for (offset, _), entities in zip(chunks, results):
        for ent in entities:
            yield from ner_result(
                ent["label"],
                ent["text"],
                "GLiNER",
                offset + ent["start"],
                offset + ent["end"],
            )
