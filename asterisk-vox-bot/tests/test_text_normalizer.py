from app.backend.utils import text_normalizer


def test_normalize_replaces_units_and_trims_whitespace():
    raw_text = "  м п а и миллиметр  "
    normalized = text_normalizer.normalize(raw_text)
    assert normalized == "МПа и мм"


def test_normalize_handles_empty_input():
    assert text_normalizer.normalize("") == ""
    assert text_normalizer.normalize(None) is None
