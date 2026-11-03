from ftmq.util import EntityProxy

from ftm_analyze.analysis.extract.base import NERs, get_device, ner_result


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using Flair."""
    import flair
    import torch
    from flair.nn import Classifier
    from flair.splitter import SegtokSentenceSplitter

    flair.device = torch.device(get_device())
    splitter = SegtokSentenceSplitter()
    sentences = splitter.split(text)
    tagger = Classifier.load("ner")
    tagger.predict(sentences)
    for sentence in sentences:
        for label in sentence.get_labels():
            span = label.data_point
            # span offsets are relative to the sentence
            yield from ner_result(
                label.value,
                span.text,
                "Flair",
                sentence.start_position + span.start_position,
                sentence.start_position + span.end_position,
            )
