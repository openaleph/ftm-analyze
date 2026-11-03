from ftm_analyze.analysis.extract.gliner import WORDS, chunk_text


def _chunks(text, size):
    return [text[start:end] for start, end in chunk_text(text, size)]


def test_chunk_text():
    # 10 words per sentence as GLiNER counts them (incl. the period)
    sentence = "Das Bundesamt für Verfassungsschutz beobachtet die Partei seit Jahren."
    text = " ".join([sentence] * 100)
    chunks = _chunks(text, 35)
    assert len(chunks) > 1
    assert all(len(WORDS.findall(c)) <= 35 for c in chunks)
    # nothing is lost and sentences are not cut
    assert " ".join(chunks) == text
    assert all(c.endswith("Jahren.") for c in chunks)

    # overlong sentences (e.g. pdf tables without punctuation) are split at
    # word boundaries
    text = " ".join(["Bundesamt"] * 100)
    chunks = _chunks(text, 30)
    assert [len(WORDS.findall(c)) for c in chunks] == [30, 30, 30, 10]
    assert " ".join(chunks) == text

    assert _chunks("Kurz.", 384) == ["Kurz."]
    assert _chunks("", 384) == []

    # the offsets are positions in the original text, whatever its whitespace
    text = "Erster Satz.\n\nZweiter  Satz!   Dritter Satz."
    assert _chunks(text, 6) == ["Erster Satz.\n\nZweiter  Satz!", "Dritter Satz."]
