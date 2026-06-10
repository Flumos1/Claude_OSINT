"""
translit.py — генерация вариантов написания ФИО для интеллектуального поиска.

Один человек в разных источниках пишется по-разному: укр/рус кириллица + латинская
транслитерация + перестановки. Поиск по одному варианту теряет совпадения. Этот модуль
генерирует набор вариантов, повышая полноту (recall) без обращения к закрытым данным.
"""
import re

# Украинский → латиница (на базе постанови КМУ №55, спрощено; позиційні є/ї/й/ю/я)
UK_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "y", "і": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "’": "", "'": "",
}
UK_LAT_INIT = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}
UK_LAT_MID = {"є": "ie", "ї": "i", "й": "i", "ю": "iu", "я": "ia"}

# Русский → латиница (BGN/PCGN-ish)
RU_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}
# Кросс-скрипт укр↔рус (для альтернативного кирилличного написания)
UK_TO_RU = str.maketrans({"і": "и", "ї": "и", "є": "е", "ґ": "г"})
RU_TO_UK_HINT = str.maketrans({"ы": "и", "э": "е", "ъ": "'"})


def _translit_word(word: str, table: dict, init: dict = None, mid: dict = None) -> str:
    out, first = [], True
    for ch in word:
        low = ch.lower()
        if first and init and low in init:
            r = init[low]
        elif not first and mid and low in mid:
            r = mid[low]
        else:
            r = table.get(low, low)
        out.append(r.capitalize() if (first and r) else r)
        if r.strip():
            first = False
    return "".join(out)


def to_latin_uk(s: str) -> str:
    return " ".join(_translit_word(w, UK_LAT, UK_LAT_INIT, UK_LAT_MID) for w in s.split())


def to_latin_ru(s: str) -> str:
    return " ".join(_translit_word(w, RU_LAT) for w in s.split())


def name_variants(full: str) -> list[str]:
    """Набор вариантов написания ФИО (кириллица укр/рус + латиница + перестановки)."""
    full = re.sub(r"\s+", " ", full.strip())
    if not full:
        return []
    variants = {full}
    ru_spelling = full.translate(UK_TO_RU)
    variants.add(ru_spelling)
    variants.add(full.translate(RU_TO_UK_HINT))
    # латиница из обоих кирилличных вариантов
    for src in (full, ru_spelling):
        variants.add(to_latin_uk(src))
        variants.add(to_latin_ru(src))
    # перестановка «Прізвище Ім'я» ↔ «Ім'я Прізвище» (первые два токена)
    parts = full.split()
    if len(parts) >= 2:
        variants.add(" ".join([parts[1], parts[0]] + parts[2:]))
    # только прізвище+ім'я (без по-батькові)
    if len(parts) >= 2:
        variants.add(" ".join(parts[:2]))
    return sorted(v for v in variants if v.strip())


if __name__ == "__main__":
    import sys
    for v in name_variants(" ".join(sys.argv[1:]) or "Зеленський Володимир Олександрович"):
        print(v)
