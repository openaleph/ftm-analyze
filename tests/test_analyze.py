from ftm_analyze import logic


def test_analyze(documents):
    res = [e for e in logic.analyze_entities(documents)]
    assert len(res) > len(documents)


def test_analyze_convert_mentions(documents):
    res = {e.id: e for e in logic.analyze_entities(documents, resolve_mentions=False)}
    mention = res["2e4168096c5b1ad089d402457fc34a3b5d383240"]
    assert mention.schema.is_a("Mention")
    resolved_id = mention.first("resolved")

    res = {e.id: e for e in logic.analyze_entities(documents, resolve_mentions=True)}
    assert res[resolved_id].schema.is_a("Organization")
