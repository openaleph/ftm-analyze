from ftm_analyze.analysis.analyzer import Mention
from ftm_analyze.analysis.refine import clean_name, is_rigour_org
from ftm_analyze.analysis.util import TAG_PERSON


def test_refine_names():
    assert is_rigour_org("IDIO Daten Import Export GmbH")
    assert not is_rigour_org("Jane Doe")

    assert clean_name("the european union", "ORG") == "european union"


def test_refine_legal_form():
    # a legal form in the name makes it an organization, whatever the NER tag
    mention = Mention(
        key="hirak",
        entity_id="doc",
        prop=TAG_PERSON,
        original_values={"Hirak e.V."},
        ner_tag="PER",
    )
    mention.resolve(resolve_mentions=False, refine_locations=False)
    assert mention.ner_tag == "ORG"
    entity = mention.to_entity()
    assert entity is not None
    assert entity.first("detectedSchema") == "Organization"
