from followthemoney import model
from followthemoney.types import registry
from juditha import get_store
from juditha.io import load_proxies

from ftm_analyze import logic
from tests.conftest import FIXTURES_PATH, JUDITHA


def _analyze_entity(entity):
    results = [e for e in logic.analyze_entity(entity)]
    return results[-1]


def test_analyze(documents):
    res = [e for e in logic.analyze_entities(documents)]
    assert len(res) > len(documents)


def test_analyze_convert_mentions(documents, monkeypatch, tmp_path):
    monkeypatch.setenv("JUDITHA_URI", str(tmp_path / "juditha.db"))
    get_store.cache_clear()
    load_proxies(FIXTURES_PATH / JUDITHA)

    res = {e.id: e for e in logic.analyze_entities(documents, resolve_mentions=False)}
    mention = res["2e4168096c5b1ad089d402457fc34a3b5d383240"]
    assert mention.schema.is_a("Mention")
    resolved_id = mention.first("resolved")
    assert resolved_id not in res
    assert len(res) == 7

    res = {e.id: e for e in logic.analyze_entities(documents, resolve_mentions=True)}
    assert len(res) == 7
    org = res[resolved_id]
    assert org.schema.is_a("Organization")
    doc = res[org.first("proof")]
    assert (
        "[Circular Plastics Alliance](f_alliance+circular+plastics&f_circular+plastics+alliance&p_companiesMentioned&p_namesMentioned&s_LegalEntity&s_Organization)"
        in str(doc.first("indexText"))
    )

    doc = res[documents[0].id]
    assert "[info@fooddrinkeurope.eu](p_emailMentioned)" in str(doc.first("indexText"))


def test_analyze_ner_extract():
    text = "Das ist der Pudel von Angela Merkel. "
    text = text * 5
    entity = model.make_entity("PlainText")
    entity.id = "test1"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    names = entity.get_type_values(registry.name)
    assert "Angela Merkel" in names, names


def test_analyze_language_tagging():
    text = "C'est le caniche d'Emmanuel Macron. " * 2
    entity = model.make_entity("PlainText")
    entity.id = "test2"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    names = entity.get_type_values(registry.name)
    assert "Emmanuel Macron" in names, names
    assert entity.get("detectedLanguage") == ["fra"], entity.get(
        "detectedLanguage"
    )  # noqa


def test_analyze_pattern_extract():
    text = "Mr. Flubby Flubber called the number tel:+919988111222 twice"
    entity = model.make_entity("PlainText")
    entity.id = "test3"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    phones = entity.get_type_values(registry.phone)
    assert "+919988111222" in phones
    countries = entity.get_type_values(registry.country)
    assert "in" in countries
