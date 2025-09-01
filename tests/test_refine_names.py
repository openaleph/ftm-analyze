from ftm_analyze.analysis.refine import (
    classify_name_rigour,
    clean_name,
    is_rigour_person,
)


def test_refine_names():
    assert classify_name_rigour("IDIO Daten Import Export GmbH") == "ORG"
    assert classify_name_rigour("Jane Doe") == "PER"
    assert classify_name_rigour("Jane Mary Doe") == "PER"
    assert classify_name_rigour("jhkl fsd dsf") == "OTHER"

    assert clean_name("the european union", "ORG") == "european union"

    assert is_rigour_person("Mrs. Jane Doe")
    assert not is_rigour_person("Jane Doe gmbh")
    assert not is_rigour_person("J Doe")
