from followthemoney import model
from followthemoney.types import registry
from juditha import get_store
from juditha.io import load_proxies

from ftm_analyze import logic


def _analyze_entity(entity):
    results = [e for e in logic.analyze_entity(entity)]
    return results[-1]


def test_analyze(documents):
    res = [e for e in logic.analyze_entities(documents)]
    assert len(res) > len(documents)


def test_analyze_convert_mentions(fixtures_path, documents, monkeypatch, tmp_path):
    monkeypatch.setenv("JUDITHA_URI", str(tmp_path / "juditha.db"))
    get_store.cache_clear()
    load_proxies(fixtures_path / "juditha.ftm.json", sync=True)

    res = {e.id: e for e in logic.analyze_entities(documents)}
    mention = res["960330b10c91e2f38d80049a868f9665351d229a"]
    assert mention.schema.is_a("Mention")
    resolved_id = mention.first("resolved")
    assert resolved_id not in res
    assert len(res) == 15

    res = {e.id: e for e in logic.analyze_entities(documents, resolve_mentions=True)}
    assert len(res) == 15
    org = res[resolved_id]
    assert org.schema.is_a("Organization")
    doc = res[org.first("proof")]
    assert "[Circular Plastics Alliance](LEG&ORG&SYM_ALLIANCE)" in str(
        doc.first("indexText")
    )

    doc = res[documents[0].id]
    assert "[info@fooddrinkeurope.eu](EMAIL)" in str(doc.first("indexText"))


def test_analyze_ner_extract():
    text = "Das ist der Pudel von Angela Merkel. "
    text = text * 5
    entity = model.make_entity("PlainText")
    entity.id = "test1"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    names = entity.get_type_values(registry.name)
    assert "angela merkel" in names, names


def test_analyze_language_tagging():
    text = "C'est le caniche d'Emmanuel Macron. " * 2
    entity = model.make_entity("PlainText")
    entity.id = "test2"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    names = entity.get_type_values(registry.name)
    assert "emmanuel macron" in names, names
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
    assert "[+919988111222](PHONE)" in str(entity.first("indexText"))


def test_analyze_extract_iban():
    text = "Mr. Flubby Flubber has the bank account CH5604835012345678009"
    entity = model.make_entity("PlainText")
    entity.id = "test"
    entity.add("bodyText", text)
    results = {e.schema.name: e for e in logic.analyze_entity(entity)}
    bank_account = results["BankAccount"]
    assert bank_account.caption == "CH5604835012345678009"
    assert (
        bank_account.first("iban")
        == bank_account.first("accountNumber")
        == "CH5604835012345678009"
    )
    assert bank_account.id == "iban-ch5604835012345678009"
    assert bank_account.first("proof") == "test"
    assert "ch" in bank_account.countries
    doc = results["PlainText"]
    assert "[CH5604835012345678009](IBAN)" in doc.first("indexText")


def test_analyze_extract_location():
    text = "Jane Doe lives in New York City"
    entity = model.make_entity("PlainText")
    entity.id = "test"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    assert entity.first("locationMentioned", "New York City")
    assert "lives in [New York City](LOC)"
