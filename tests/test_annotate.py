from followthemoney import model

from ftm_analyze.analysis.util import TAG_COUNTRY, TAG_EMAIL, TAG_NAME, TAG_PERSON
from ftm_analyze.annotate import (
    Annotation,
    Annotator,
    clean_text,
    get_symbol_annotations,
)


def test_annotate(documents):
    assert (
        clean_text("lorem [foo. x](bar) \n <div class='1'>ipsum</div>")
        == "lorem foo. x bar ipsum"
    )

    a = Annotation(value="Mrs. Jane Doe")
    assert a.value == "Mrs. Jane Doe"
    assert not a.repl
    assert a.annotate("Mrs. Jane Doe") == "Mrs. Jane Doe"
    a = Annotation(value="Mrs. Jane Doe", props={TAG_NAME.name})
    assert a.repl == "[Mrs. Jane Doe](LEG&Q12573029&Q12791967&Q1682564&Q37110043)"
    a = Annotation(value="Mrs. Jane Doe", props={TAG_PERSON.name})
    annotated = "[Mrs. Jane Doe](LEG&PER&Q12573029&Q12791967&Q1682564&Q37110043)"
    assert a.repl == annotated
    assert annotated in a.annotate("lorem ipsum Mrs. Jane Doe dolor")

    doc = documents[0]
    annotator = Annotator(doc)
    annotator.add_tag(TAG_EMAIL, "info@fooddrinkeurope.eu")
    tested = False
    for text in annotator.get_texts():
        if "[info@fooddrinkeurope.eu](EMAIL)" in text:
            tested = True
    assert tested

    # ignore non mentions
    annotator.add_tag(TAG_COUNTRY, "fr")
    assert "info@fooddrinkeurope.eu" in annotator.annotations
    assert "fr" not in annotator.annotations


def test_annotate_symbols():
    JANE = "Mrs. Jane Doe"
    DARC = "IDIO Daten Import Export GmbH"
    assert get_symbol_annotations(model["Person"], JANE) == {
        "Q1682564",
        "Q12791967",
        "Q37110043",
        "Q12573029",
    }
    assert get_symbol_annotations(model["Company"], DARC) == {
        "SYM_EXPORT",
        "SYM_IMPORT",
        "ORG_LLC",
    }


def test_annotate_invalid():
    text = "foo [Jane Doe](bar)"
    a = Annotation(value="Jane", props={TAG_NAME.name})
    assert a.annotate(text) == text
