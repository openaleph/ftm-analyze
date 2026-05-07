from followthemoney import model, registry

from ftm_analyze.analysis.util import TAG_COUNTRY, TAG_EMAIL, TAG_NAME, TAG_PERSON
from ftm_analyze.annotate import (
    Annotation,
    Annotator,
    clean_text,
    get_symbol_annotations,
)
from ftm_analyze.annotate.annotator import ZWJ


def _marker(code: str) -> str:
    return f"{ZWJ}__{code}__"


def test_annotate(documents):
    # clean_text now only strips HTML and collapses whitespace; brackets pass through
    assert (
        clean_text("lorem [foo. x](bar) \n <div class='1'>ipsum</div>")
        == "lorem [foo. x](bar) ipsum"
    )

    a = Annotation(value="Mrs. Jane Doe")
    assert a.value == "Mrs. Jane Doe"
    assert a.suffix == ""
    assert a.annotate("Mrs. Jane Doe") == "Mrs. Jane Doe"

    a = Annotation(value="Mrs. Jane Doe", props={TAG_NAME.name})
    # TAG_NAME alone: LEG type + entity id derived from slug(normalize_name(value))
    assert a.suffix == _marker("LEG") + _marker("mrsjanedoe")

    a = Annotation(value="Jane Doe", props={TAG_PERSON.name})
    suffix = _marker("LEG") + _marker("PER") + _marker("janedoe")
    assert a.suffix == suffix
    # each surface word carries the full suffix
    out = a.annotate("lorem ipsum Jane Doe dolor")
    assert f"Jane{suffix} Doe{suffix}" in out

    doc = documents[0]
    annotator = Annotator(doc)
    annotator.add_tag(TAG_EMAIL, "info@fooddrinkeurope.eu")
    # patch_entity writes the annotated text back onto the same text properties
    target = model.make_entity(doc.schema)
    target.id = doc.id
    annotator.patch_entity(target)
    tested = False
    for text in target.get_type_values(registry.text):
        if f"info@fooddrinkeurope.eu{_marker('EMAIL')}" in text:
            tested = True
    assert tested

    # ignore non mentions
    annotator.add_tag(TAG_COUNTRY, "fr")
    assert "info@fooddrinkeurope.eu" in annotator.annotations
    assert "fr" not in annotator.annotations


def test_annotate_symbols():
    JANE = "Mrs. Jane Doe"
    DARC = "IDIO Daten Import Export GmbH"
    # NAME-category (Q...) symbols are no longer emitted
    assert get_symbol_annotations(model["Person"], JANE) == set()
    # ORG_CLASS codes lose the 'ORG_' prefix; SYMBOL codes keep 'SYM_'.
    # rigour maps GmbH to the generic LLC org-class.
    assert get_symbol_annotations(model["Company"], DARC) == {
        "SYM_EXPORT",
        "SYM_IMPORT",
        "LLC",
    }


def test_annotate_invalid():
    # applying an annotation on already-decorated text must be a no-op
    # (guarded by the ZWJ lookaround in Annotation.annotate)
    a = Annotation(value="Jane Doe", props={TAG_PERSON.name})
    once = a.annotate("foo Jane Doe bar")
    twice = a.annotate(once)
    assert once == twice


def test_annotate_cross_script():
    # standard tokenizer / whitespace split must handle non-Latin scripts
    a = Annotation(value="Владимир Путин", props={TAG_PERSON.name})
    out = a.annotate("лорем Владимир Путин ипсум")
    suffix = a.suffix
    assert f"Владимир{suffix} Путин{suffix}" in out


def test_annotate_overlapping_surface_forms(documents):
    # longer surface forms decorate first; shorter ones only match standalone
    annotator = Annotator(documents[0])
    annotator.add(Annotation(value="Jane Doe", props={TAG_PERSON.name}))
    annotator.add(Annotation(value="Jane", props={TAG_PERSON.name}))
    out = annotator.annotate_text("Jane Doe met Jane alone")
    assert f"Jane{_marker('LEG')}{_marker('PER')}{_marker('janedoe')} Doe" in out
    assert f"Jane{_marker('LEG')}{_marker('PER')}{_marker('jane')} alone" in out
