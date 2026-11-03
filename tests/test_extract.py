import pytest

from ftm_analyze.analysis.extract import base


def test_extract_test_name():
    # no minimum length: short names like party acronyms or towns are kept
    assert base.test_name("AfD")
    assert base.test_name("Jena")
    # but a name needs a letter and max 100 chars
    assert not base.test_name("1234")
    assert not base.test_name("a" * 101)


def test_extract_get_device(monkeypatch):
    monkeypatch.setattr(base.settings, "device", "cuda:1")
    assert base.get_device() == "cuda:1"
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(base.settings, "device", None)
    assert base.get_device() == ("cuda" if torch.cuda.is_available() else "cpu")


def test_extract_offsets():
    from followthemoney import model

    from ftm_analyze.analysis.extract import extract_spacy

    text = "Angela Merkel reiste von Berlin nach Paris."
    entity = model.make_entity("PlainText")
    entity.add("language", "deu")
    spans = list(extract_spacy(entity, text))
    assert spans
    for span in spans:
        assert text[span.start : span.end] == span.value


def test_extract_juditha_single_words(monkeypatch):
    from juditha.model import Mention

    from ftm_analyze.analysis.extract import Span, extract_juditha
    from ftm_analyze.analysis.extract import juditha as extract
    from ftm_analyze.analysis.util import TAG_LOCATION, TAG_PERSON

    text = "Minister Carius in Thüringen, Simon Berlin"
    mentions = [
        Mention(text="Carius", start=9, end=15, schema="Address"),
        Mention(text="Thüringen", start=19, end=28, schema="Address"),
        Mention(text="Simon Berlin", start=30, end=42, schema="Person"),
    ]

    class Store:
        def extract(self, text):
            return iter(mentions)

    monkeypatch.setattr(extract.juditha, "get_store", lambda: Store())
    # a single word shorter than 8 chars is left to NER
    assert list(extract_juditha(text)) == [
        Span(TAG_LOCATION, "Thüringen", 19, 28, "Address"),
        Span(TAG_PERSON, "Simon Berlin", 30, 42, "Person"),
    ]
