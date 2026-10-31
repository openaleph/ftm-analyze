from collections import defaultdict
from typing import Generator, Iterable, TypeAlias

from anystore.logging import get_logger
from followthemoney import Property
from juditha.model import get_common_schema
from rigour.names import normalize_name

from ftm_analyze.analysis.extract import test_name
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


class TagAggregatorFasttext(object):
    def __init__(
        self,
        model_path=settings.ner_type_model_path,
        confidence: float | None = settings.ner_type_model_confidence,
    ):
        self.values = defaultdict(set)
        # known names (from the juditha automaton) with their schemata, these
        # skip the confidence filter
        self.schemata: defaultdict[tuple[str, Property], set[str]] = defaultdict(set)
        self.model = FTTypeModel(str(model_path))
        self.confidence = confidence

    def add(self, prop: Property, value: str, schema: str | None = None) -> None:
        if not test_name(value):
            return
        key = normalize_name(prop.type.node_id_safe(value))
        self.values[(key, prop)].add(value)
        if key and schema is not None:
            self.schemata[(key, prop)].add(schema)

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
            if not self.confidence or (key, prop) in self.schemata:
                # very messy
                yield (key, prop, values)
            else:
                labels, confidences = self.model.confidence(values)
                if not _skip_result(labels, confidences, self.confidence):
                    if values:
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
