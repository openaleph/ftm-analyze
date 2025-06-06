from collections import defaultdict

from anystore.logging import get_logger

from ftm_analyze.analysis.ft_type_model import FTTypeModel
from ftm_analyze.settings import Settings

log = get_logger(__name__)
settings = Settings()


class TagAggregatorFasttext(object):
    def __init__(
        self,
        model_path=settings.ner_type_model_path,
        confidence: float | None = settings.ner_type_model_confidence,
    ):
        self.values = defaultdict(set)
        self.model = FTTypeModel(str(model_path))
        self.confidence = confidence

    def add(self, prop, value):
        if value is None:
            return
        key = prop.type.node_id_safe(value)
        self.values[(key, prop)].add(value)

    def results(self):
        for (key, prop), values in self.values.items():
            values.discard(None)
            if not values:
                continue
            values = list(values)
            labels, confidences = self.model.confidence(values)
            if not self.confidence:
                # very messy
                yield (key, prop, values)
                continue
            for label, confidence in zip(labels, confidences):
                if label == "trash" or (
                    self.confidence and confidence < self.confidence
                ):
                    break
            else:
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
