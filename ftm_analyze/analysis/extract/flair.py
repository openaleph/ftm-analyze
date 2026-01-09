from ftmq.util import EntityProxy

from ftm_analyze.analysis.extract.base import NERs, ner_result


def handle(entity: EntityProxy, text: str) -> NERs:
    """Extract named entities using Flair."""
    from flair.nn import Classifier
    from flair.splitter import SegtokSentenceSplitter

    splitter = SegtokSentenceSplitter()
    sentences = splitter.split(text)
    tagger = Classifier.load("ner")
    tagger.predict(sentences)
    for sentence in sentences:
        for label in sentence.get_labels():
            yield from ner_result(label.value, label.data_point.text, "Flair")
