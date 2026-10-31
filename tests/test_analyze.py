import json

from followthemoney import model
from followthemoney.types import registry
from juditha import get_store
from juditha.io import load_proxies

from ftm_analyze import logic
from ftm_analyze.analysis.extract import extract_juditha
from ftm_analyze.analysis.util import TAG_COMPANY
from ftm_analyze.annotate.annotator import ZWJ


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
    body_text = str(doc.first("bodyText"))
    circ_suffix = (
        f"{ZWJ}__LEG__{ZWJ}__ORG__"
        f"{ZWJ}__circularplasticsalliance__{ZWJ}__SYM_ALLIANCE__"
    )
    assert (
        f"Circular{circ_suffix} Plastics{circ_suffix} Alliance{circ_suffix}"
        in body_text
    )

    doc = res[documents[0].id]
    assert f"info@fooddrinkeurope.eu{ZWJ}__EMAIL__" in str(doc.first("bodyText"))


def test_analyze_extract_known_names(monkeypatch, tmp_path):
    monkeypatch.setenv("JUDITHA_URI", str(tmp_path / "juditha.db"))
    get_store.cache_clear()
    known = tmp_path / "known.ftm.json"
    known.write_text(
        json.dumps(
            {
                "id": "bfv",
                "schema": "PublicBody",
                "properties": {"name": ["Bundesamt für Verfassungsschutz"]},
            }
        )
    )
    load_proxies(known, sync=True)

    text = "Das Bundesamt für Verfassungsschutz hat heute den Bericht vorgestellt."
    assert list(extract_juditha(text)) == [
        (TAG_COMPANY, "Bundesamt für Verfassungsschutz", "PublicBody")
    ]

    def _analyze(extract_known_names):
        entity = model.make_entity("PlainText")
        entity.id = "test-known"
        entity.add("bodyText", text * 2)
        return list(
            logic.analyze_entity(
                entity, annotate=True, extract_known_names=extract_known_names
            )
        )

    # spacy finds it, but the fasttext confidence filter drops it
    res = _analyze(extract_known_names=False)
    assert [e.schema.name for e in res] == ["PlainText"]
    assert not res[-1].get("companiesMentioned")

    # known names skip the confidence filter and become entities, not mentions
    res = _analyze(extract_known_names=True)
    assert [e.schema.name for e in res] == ["PublicBody", "PlainText"]
    public_body, doc = res
    assert public_body.first("proof") == "test-known"
    assert "bundesamt für verfassungsschutz" in public_body.get("name")
    assert "bundesamt für verfassungsschutz" in doc.get("companiesMentioned")
    assert f"Bundesamt{ZWJ}__LEG__{ZWJ}__ORG__" in doc.first("bodyText")

    def _analyze_table(*cells):
        table = model.make_entity("Table")
        table.id = "test-table"
        table.add("indexText", cells)
        return list(logic.analyze_entity(table, extract_known_names=True))

    # tables are not NER'd, but known names are extracted from their cells
    res = _analyze_table("Bundesamt für Verfassungsschutz", "Köln", "2023")
    assert [e.schema.name for e in res] == ["PublicBody", "Table"]
    public_body, table = res
    assert public_body.first("proof") == "test-table"
    assert "bundesamt für verfassungsschutz" in table.get("companiesMentioned")

    # names don't match across cells
    res = _analyze_table("Bundesamt für", "Verfassungsschutz")
    assert [e.schema.name for e in res] == ["Table"]


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
    assert f"+919988111222{ZWJ}__PHONE__" in str(entity.first("bodyText"))


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
    assert f"CH5604835012345678009{ZWJ}__IBAN__" in doc.first("bodyText")


def test_analyze_extract_location():
    text = "Jane Doe lives in New York City"
    entity = model.make_entity("PlainText")
    entity.id = "test"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    assert entity.first("locationMentioned", "New York City")
    assert "lives in [New York City](LOC)"


def test_analyze_language_preservation():
    text = "C'est le caniche d'Emmanuel Macron. " * 2
    entity = model.make_entity("PlainText")
    entity.id = "test2"
    entity.add("bodyText", text)

    entity = [e for e in logic.analyze_entity(entity, overwrite_lang=False)][-1]
    # if the detectedLanguage property is not set, it should be detected
    assert entity.get("detectedLanguage") == ["fra"]

    entity.set("detectedLanguage", "ron")
    # do not overwrite the detectedLanguage
    entity = [e for e in logic.analyze_entity(entity, overwrite_lang=False)][-1]
    # if the property is set, it should be preserved
    assert entity.get("detectedLanguage") == ["ron", "fra"]

    entity.set("detectedLanguage", "ron")
    # finally, overwrite the detectedLanguage
    entity = [e for e in logic.analyze_entity(entity, overwrite_lang=True)][-1]
    # the property should be corrected
    assert entity.get("detectedLanguage") == ["fra"]
