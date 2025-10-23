import pytest
from app.backend.utils.text_normalizer import normalize

@pytest.mark.parametrize("input_text,expected", [
    ("Есть РЭМ на тысячу килоньютон, скорость 5 миллиметров в секунду при 220 вольт", "Есть РЭМ на тысячу кН, скорость 5 мм/с при 220 В"),
    ("частота 50 герц", "частота 50 Гц"),
    ("рабочее давление 1 мпа", "рабочее давление 1 МПа"),
    ("температура 36.6 градусов", "температура 36.6 градусов"),
])
def test_normalize_basic_rules(input_text, expected):
    assert normalize(input_text) == expected
