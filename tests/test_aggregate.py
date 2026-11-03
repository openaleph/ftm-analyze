import pytest

from ftm_analyze.analysis import aggregate
from ftm_analyze.analysis.aggregate import NameAggregator, merge_spans
from ftm_analyze.analysis.extract import Span
from ftm_analyze.analysis.util import TAG_COMPANY, TAG_LOCATION, TAG_PERSON


def test_aggregate_merge_spans():
    # known names win over overlapping NER results, longer or shorter
    known = Span(TAG_PERSON, "Bodo Ramelow", 18, 30, "Person")
    ner = Span(TAG_PERSON, "Ministerpräsident Bodo Ramelow", 0, 30)
    assert merge_spans([ner, known]) == [known]
    ner = Span(TAG_PERSON, "Ramelow", 23, 30)
    assert merge_spans([ner, known]) == [known]
    ner = Span(TAG_COMPANY, "Bodo Ramelow SPD", 18, 34)
    assert merge_spans([ner, known]) == [known]

    # at the same position as well
    ner = Span(TAG_LOCATION, "Thüringer Landtag", 0, 17)
    known = Span(TAG_COMPANY, "Thüringer Landtag", 0, 17, "PublicBody")
    assert merge_spans([ner, known]) == [known]

    # a single-word known name only wins at the same position
    known = Span(TAG_LOCATION, "Deutschland", 16, 27, "Address")
    ner = Span(TAG_COMPANY, "Alternative für Deutschland", 0, 27)
    assert merge_spans([ner, known]) == [ner]
    ner = Span(TAG_LOCATION, "Deutschland", 16, 27)
    assert merge_spans([ner, known]) == [known]
    assert merge_spans([known]) == [known]

    # spans that don't overlap are all kept, duplicates are dropped
    a = Span(TAG_PERSON, "Angela Merkel", 0, 13)
    b = Span(TAG_LOCATION, "Berlin", 25, 31)
    merged = merge_spans([a, b, b])
    assert len(merged) == 2 and set(merged) == {a, b}
    assert merge_spans([]) == []

    # NER results are not merged among each other (e.g. several spaCy models)
    de = Span(TAG_LOCATION, "Düsseldorf", 0, 10)
    en = Span(TAG_COMPANY, "Düsseldorf Hirak", 0, 16)
    assert set(merge_spans([de, en])) == {de, en}
    known = Span(TAG_COMPANY, "Düsseldorf Hirak", 0, 16, "Organization")
    assert merge_spans([de, en, known]) == [known]


def test_aggregate_add_spans():
    aggregator = NameAggregator()
    # the fastText filter is opt-in, its model is not loaded by default
    assert aggregator.model is None
    aggregator.add_spans(
        [
            Span(TAG_LOCATION, "Thüringer Landtag", 0, 17),
            Span(TAG_COMPANY, "Thüringer Landtag", 0, 17, "PublicBody"),
        ]
    )
    ((key, prop, values),) = aggregator.results()
    assert prop == TAG_COMPANY
    assert values == {"Thüringer Landtag"}
    assert aggregator.get_schema(key, prop) == "PublicBody"


@pytest.mark.skipif(
    not aggregate.settings.ner_type_model_path.exists(),
    reason="fastText type model not downloaded",
)
def test_aggregate_fasttext_filter(monkeypatch):
    # opt-in: NER results below the confidence are dropped, known names skip it
    monkeypatch.setattr(aggregate.settings, "ner_type_model_confidence", 0.85)
    aggregator = NameAggregator()
    aggregator.add(TAG_PERSON, "Angela Merkel")
    aggregator.add(TAG_COMPANY, "Bundesamt für Verfassungsschutz")
    assert [values for _, _, values in aggregator.results()] == [{"Angela Merkel"}]
    aggregator.add(TAG_COMPANY, "Bundesamt für Verfassungsschutz", "PublicBody")
    assert len(list(aggregator.results())) == 2
