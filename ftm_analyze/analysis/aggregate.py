from collections import defaultdict
from typing import Generator, Iterable, TypeAlias

from anystore.logging import get_logger
from followthemoney import Property
from juditha.model import get_common_schema
from rigour.names import normalize_name

from ftm_analyze.analysis.extract import Span, test_name
from ftm_analyze.analysis.ft_type_model import FTTypeModel
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()

Result: TypeAlias = tuple[str, Property, Iterable[str]]
Results: TypeAlias = Generator[Result, None, None]


def _skip_result(
    labels, confidences, confidence_threshold: float | None = None
) -> bool:
    for label, confidence in zip(labels, confidences):
        if label == "trash" or (
            confidence_threshold and confidence < confidence_threshold
        ):
            return True
    return False


def merge_spans(spans: Iterable[Span]) -> list[Span]:
    """Merge the names found in one text by position: known names (with their
    schema) win over NER results at the same or an overlapping position, a
    single-word known name only at the same position. NER results are not
    merged among each other (e.g. the results of several spaCy models for a
    multilingual text)."""
    spans = set(spans)
    ner = [s for s in spans if s.schema is None]
    known = []
    for span in spans:
        if span.schema is None:
            continue
        # a single word loses to an NER result at another overlapping position,
        # e.g. a longer one containing it (`Alternative für Deutschland` is kept
        # over a known `Deutschland`)
        if len(span.value.split()) < 2 and any(
            s.start < span.end
            and span.start < s.end
            and (s.start, s.end) != (span.start, span.end)
            for s in ner
        ):
            continue
        known.append(span)
    taken = bytearray(max((s.end for s in spans), default=0))
    for span in known:
        taken[span.start : span.end] = b"\x01" * (span.end - span.start)
    return known + [s for s in ner if taken.find(1, s.start, s.end) == -1]


class NameAggregator(object):
    def __init__(self) -> None:
        self.values: defaultdict[tuple[str, Property], set[str]] = defaultdict(set)
        # known names (from the juditha automaton) with their schemata, these
        # skip the confidence filter
        self.schemata: defaultdict[tuple[str, Property], set[str]] = defaultdict(set)
        # opt-in fastText confidence filter for NER results, the model is only
        # loaded if a confidence is set
        self.confidence = settings.ner_type_model_confidence
        self.model = None
        if self.confidence:
            self.model = FTTypeModel(str(settings.ner_type_model_path))

    def add(self, prop: Property, value: str, schema: str | None = None) -> None:
        if not test_name(value):
            return
        key = normalize_name(prop.type.node_id_safe(value))
        if not key:
            return
        self.values[(key, prop)].add(value)
        if schema is not None:
            self.schemata[(key, prop)].add(schema)

    def add_spans(self, spans: Iterable[Span]) -> None:
        """Add the names found in one text, merged by position"""
        for span in merge_spans(spans):
            self.add(span.prop, span.value, schema=span.schema)

    def get_schema(self, key: str, prop: Property) -> str | None:
        """The schema of a known name, or `None` if it is not known"""
        schemata = self.schemata.get((key, prop))
        if schemata:
            schema: str = get_common_schema(*sorted(schemata))
            return schema
        return None

    def results(self) -> Results:
        for (key, prop), values in self.values.items():
            values.discard(None)
            if not values:
                continue
            if self.model is None or (key, prop) in self.schemata:
                yield (key, prop, values)
            else:
                labels, confidences = self.model.confidence(values)
                if not _skip_result(labels, confidences, self.confidence):
                    log.debug(
                        f"Fasttext: [{prop}]",
                        labels=labels,
                        confidences=confidences,
                        values=values,
                    )
                    yield (key, prop, values)

    def __len__(self):
        return len(self.values)


class TagAggregator(object):
    MAX_TAGS = 10000

    def __init__(self):
        self.values = defaultdict(list)

    def add(self, prop, value):
        key = prop.type.node_id_safe(value)
        if key is None:
            return

        if (key, prop) not in self.values:
            if len(self.values) > self.MAX_TAGS:
                return

        self.values[(key, prop)].append(value)

    def results(self) -> Results:
        for (key, prop), values in self.values.items():
            yield key, prop, values

    def __len__(self):
        return len(self.values)
