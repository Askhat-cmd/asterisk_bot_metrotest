import re
from typing import Callable, List, Tuple


def _compile_rules() -> List[Tuple[re.Pattern, str]]:
    raw_rules = [
        # unify dashes & spaces
        (r"[–—−]", "-"),
        (r"\s+", " "),

        # kN variants → кН
        (r"\b(к\s?эн|ка-эн|кэ-эн|к\s?ен|к\s?э\s?н|кэн|кн|кило\s?ньютоны?)\b", "кН"),

        # Pressure & stress
        (r"\b(м\s?п\s?а|мэ-пэ-а|эм-пэ-а|мегапаскал[ьяеы]?|мега\s?паскал[ьяеы]?)\b", "МПа"),
        (r"\b(к\s?п\s?а|кэ-пэ-а|килопаскал[ьяеы]?|кило\s?паскал[ьяеы]?)\b", "кПа"),
        (r"\b(паскал[ьяеы]?|па)\b", "Па"),
        (r"\b(н(ь?ютон)?\s*(?:/|на)\s*мм\s*(?:\^?2|²)|ньютон\s+на\s+миллиметр\s+квадратн[а-я]*)\b", "Н/мм²"),

        # Frequency
        (r"\b(герц|герцы|гц)\b", "Гц"),

        # Newton & moments
        (r"\bньютон[а-я]*\b", "Н"),
        (r"\b(ньюто[нн][ -]?метр[а-я]*|н\s?м)\b", "Н·м"),
        (r"\b(ньюто[нн][ -]?миллиметр[а-я]*|н\s?мм)\b", "Н·мм"),

        # Lengths
        (r"\bмиллиметр[а-я]*\b", "мм"),
        (r"\bmm\b", "мм"),
        (r"\bсантиметр[а-я]*\b", "см"),
        (r"\bcm\b", "см"),
        (r"\bметр[а-я]*\b", "м"),

        # Speeds
        (r"\b(миллиметров\s+в\s+минуту|мм\s+в\s+минуту)\b", "мм/мин"),
        (r"\b(миллиметров\s+в\s+секунду|мм\s+в\s+секунду|мм/с)\b", "мм/с"),
        (r"\b(метров\s+в\s+секунду)\b", "м/с"),
        (r"\b(r\s?p\s?m|оборотов?\s+в\s+минуту|об/мин)\b", "об/мин"),

        # Mass
        (r"\bкилограмм[а-я]*\b", "кг"),
        (r"\bkg\b", "кг"),
        (r"\bграмм[а-я]*\b", "г"),
        (r"\bтонн[а-я]*\b", "т"),

        # Temperature & percent
        (r"\bградус(ов)?\s+цельсия\b", "°C"),
        (r"\bпо\s+цельсию\b", "°C"),
        (r"\bпроцент(ов)?\b", "%"),

        # Power / electrical / energy
        (r"\b(ватт(а|ов)?|w)\b", "Вт"),
        (r"\b(киловатт(а|ов)?|к\s?вт|kw)\b", "кВт"),
        (r"\b(кВт\s*[·xx]\s*ч|киловатт\s*час[а-я]*|квтч)\b", "кВт·ч"),
        (r"\b(вольт(а|ов)?|v)\b", "В"),
        (r"\b(ампер(а|ов)?|amp(?:s)?)\b", "А"),
        (r"\b(ом(а|ов)?|ohm|Ω)\b", "Ом"),

        # Flow & pressure alt units
        (r"\b(литр(ов)?\s*в\s*минуту|л/?мин|l/?min)\b", "л/мин"),
        (r"\b(бар|bar)\b", "бар"),
        (r"\b(кгс\s*/\s*см\s*(?:\^?2|²)|килограмм\s*силы\s*на\s*сантиметр\s*квадратн[а-я]*)\b", "кгс/см²"),

        # Sound
        (r"\b(децибел(а|ов)?|дб|db)\b", "дБ"),

        # Clean slashes
        (r"\s+/\s+", "/"),
    ]

    rules: List[Tuple[re.Pattern, str]] = []
    for pattern, repl in raw_rules:
        rules.append((re.compile(pattern, flags=re.IGNORECASE), repl))
    return rules


_RULES = _compile_rules()


def normalize(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, repl in _RULES:
        result = pattern.sub(repl, result)
    return result.strip()


