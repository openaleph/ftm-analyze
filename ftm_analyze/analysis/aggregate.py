from collections import defaultdict

from anystore.logging import get_logger
from followthemoney import Property
from juditha import validate_name
from juditha.validate import Tag
from rigour.names import normalize_name

from ftm_analyze.analysis.extract import test_name
from ftm_analyze.analysis.ft_type_model import FTTypeModel
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()


def get_tag(prop: Property) -> Tag | None:
    if prop.name == "peopleMentioned":
        return "PER"
    if prop.name == "companiesMentioned":
        return "ORG"
    if prop.name == "locationMentioned":
        return "LOC"


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
        validate_names: bool | None = settings.validate_names,
    ):
        self.values = defaultdict(set)
        self.model = FTTypeModel(str(model_path))
        self.confidence = confidence
        self.validate_names = validate_names

    def add(self, prop, value):
        if not test_name(value):
            return
        key = prop.type.node_id_safe(value)
        self.values[(key, prop)].add(value)

    def results(self):
        for (key, prop), values in self.values.items():
            values.discard(None)
            if not values:
                continue
            values = list(filter(bool, map(normalize_name, values)))
            if not self.confidence and not self.validate_names:
                # very messy
                yield (key, prop, values)
            else:
                labels, confidences = self.model.confidence(values)
                if not _skip_result(labels, confidences, self.confidence):
                    tag = get_tag(prop)
                    if tag is not None and self.validate_names:
                        values = [v for v in values if validate_name(v, tag)]
                    if values:
                        log.debug(
                            f"Fasttext: [{prop}]",
                            labels=labels,
                            confidences=confidences,
                            values=values,
                            validate_names=self.validate_names,
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

    def results(self):
        for (key, prop), values in self.values.items():
            yield (key, prop, values)

    def __len__(self):
        return len(self.values)
