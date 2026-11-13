import json

from followthemoney import model
from followthemoney.namespace import Namespace
from followthemoney.types import registry
from juditha import get_store
from juditha.io import load_proxies

from ftm_analyze import logic
from ftm_analyze.analysis.analyzer import Mention
from ftm_analyze.analysis.extract import Span, extract_juditha
from ftm_analyze.analysis.util import TAG_COMPANY, TAG_LOCATION
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
    assert len(res) == 67

    res = {e.id: e for e in logic.analyze_entities(documents, resolve_mentions=True)}
    assert len(res) == 67
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
        Span(TAG_COMPANY, "Bundesamt für Verfassungsschutz", 4, 35, "PublicBody")
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

    # spacy finds it as an organization mention
    res = _analyze(extract_known_names=False)
    assert [e.schema.name for e in res] == ["Mention", "PlainText"]
    assert "bundesamt für verfassungsschutz" in res[-1].get("companiesMentioned")

    # the known name at the same position wins: it becomes an entity, and no
    # mention is created from the spacy result
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


def test_analyze_resolve_locations(monkeypatch, tmp_path):
    monkeypatch.setenv("JUDITHA_URI", str(tmp_path / "juditha.db"))
    get_store.cache_clear()
    known = tmp_path / "known.ftm.json"
    proxies = [
        {"id": "GEO:1", "schema": "Address", "properties": {"name": ["New York City"]}},
        {"id": "GEO:2", "schema": "Address", "properties": {"name": ["Ukraine"]}},
        {"id": "org", "schema": "Organization", "properties": {"name": ["Ukraine"]}},
    ]
    known.write_text("\n".join(json.dumps(p) for p in proxies))
    load_proxies(known, sync=True)

    def _resolve(name):
        mention = Mention(
            key=name,
            entity_id="doc",
            prop=TAG_LOCATION,
            original_values={name},
            ner_tag="LOC",
        )
        mention.resolve(resolve_mentions=True)
        return mention.to_entity()

    # a name that is also known as another type stays a location
    entity = _resolve("Ukraine")
    assert entity is not None
    assert entity.schema.name == "Address"
    assert entity.first("proof") == "doc"

    # unknown locations emit nothing, as before
    assert _resolve("Atlantis") is None

    entity = model.make_entity("PlainText")
    entity.id = "test-location"
    entity.add("bodyText", "My friend lives in New York City and works there.")
    *entities, doc = logic.analyze_entity(entity, resolve_mentions=True)
    assert [e.schema.name for e in entities] == ["Address"]
    assert "new york city" in doc.get("locationMentioned")


def test_analyze_location_countries():
    # the countries of found locations go to the document, not into the names
    # or onto the extracted entities
    text = "Angela Merkel reiste von Berlin nach Paris. " * 3
    entity = model.make_entity("PlainText")
    entity.id = "test"
    entity.add("bodyText", text)
    *entities, doc = logic.analyze_entity(entity)
    assert {"de", "fr"} <= set(doc.get("detectedCountry"))
    assert not {"de", "fr"} & set(doc.get_type_values(registry.name))
    assert entities
    for e in entities:
        assert not e.get_type_values(registry.country)


def test_analyze_location_person_names():
    # places that are also person names (Berlin, Weimar) stay locations
    text = "Angela Merkel reiste von Berlin nach Weimar. " * 3
    entity = model.make_entity("PlainText")
    entity.id = "test"
    entity.add("bodyText", text)
    entity = _analyze_entity(entity)
    assert "berlin" in entity.get("locationMentioned")
    assert "berlin" not in entity.get("peopleMentioned")


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


def test_analyze_namespace():
    # OpenAleph stores entities namespaced, the entities created by the
    # analyzer have to be signed, too (openaleph/openaleph#147)
    ns = Namespace("test_dataset")
    text = "Das ist der Pudel von Angela Merkel. " * 5
    text += "Sie hat das Konto CH5604835012345678009."
    entity = model.make_entity("PlainText")
    entity.id = ns.sign("test-ns")
    entity.add("bodyText", text)

    results = list(logic.analyze_entity(entity, namespace="test_dataset"))
    schemata = {e.schema.name for e in results}
    assert {"Mention", "BankAccount", "PlainText"} <= schemata, schemata
    for result in results:
        assert ns.verify(result.id), result.to_dict()
        for prop in result.iterprops():
            if prop.type == registry.entity:
                for value in result.get(prop):
                    assert ns.verify(value), (prop.name, value)
    # the already signed input entity keeps its id
    doc = [e for e in results if e.schema.name == "PlainText"][0]
    assert doc.id == entity.id

    # without a namespace, ids are left as the analyzer creates them
    results = list(logic.analyze_entity(entity))
    mention = [e for e in results if e.schema.is_a("Mention")][0]
    assert not ns.verify(mention.id)
