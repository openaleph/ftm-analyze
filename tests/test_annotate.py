from followthemoney import model

from ftm_analyze.analysis.util import TAG_COUNTRY, TAG_EMAIL, TAG_NAME, TAG_PERSON
from ftm_analyze.annotate import (
    Annotation,
    Annotator,
    clean_text,
    get_symbols,
    make_fingerprints,
)


def test_annotate(documents):
    assert clean_text("lorem [foo. x](bar) \n ipsum") == "lorem foo. x bar ipsum"

    a = Annotation(value="Mrs. Jane Doe")
    assert a.value == "Mrs. Jane Doe"
    assert not a.fingerprints
    assert not a.repl
    assert a.annotate("Mrs. Jane Doe") == "Mrs. Jane Doe"
    a = Annotation(value="Mrs. Jane Doe", props={TAG_NAME.name})
    assert a.fingerprints == {"mrs. jane doe", "doe jane"}
    assert (
        a.repl
        == "[Mrs. Jane Doe](f_doe+jane&f_mrs.+jane+doe&p_namesMentioned&q_12573029&q_12791967&q_1682564&q_37110043&q_5407747)"
    )
    a = Annotation(value="Mrs. Jane Doe", props={TAG_PERSON.name})
    assert a.fingerprints == {"mrs. jane doe", "doe jane"}
    annotated = "[Mrs. Jane Doe](f_doe+jane&f_mrs.+jane+doe&p_namesMentioned&p_peopleMentioned&q_12573029&q_12791967&q_1682564&q_37110043&q_5407747&s_LegalEntity&s_Person)"
    assert a.repl == annotated
    assert annotated in a.annotate("lorem ipsum Mrs. Jane Doe dolor")

    doc = documents[0]
    annotator = Annotator(doc)
    annotator.add_tag(TAG_EMAIL, "info@fooddrinkeurope.eu")
    tested = False
    for text in annotator.get_texts():
        if "[info@fooddrinkeurope.eu](p_emailMentioned)" in text:
            tested = True
    assert tested

    # ignore non mentions
    annotator.add_tag(TAG_COUNTRY, "fr")
    assert "info@fooddrinkeurope.eu" in annotator.annotations
    assert "fr" not in annotator.annotations


def test_annotate_symbols():
    JANE = "Mrs. Jane Doe"
    DARC = "IDIO Daten Import Export GmbH"
    assert get_symbols(JANE) == {
        "1682564",
        "5407747",
        "12791967",
        "37110043",
        "12573029",
    }
    assert get_symbols(DARC) == {"EXPORT", "LLC", "IMPORT"}
