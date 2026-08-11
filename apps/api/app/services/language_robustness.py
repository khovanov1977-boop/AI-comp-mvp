from dataclasses import dataclass


SLANG_DICTIONARY = {
    "имхо": "in my opinion",
    "лол": "laughing / joking",
    "кринж": "awkward or embarrassing",
    "краш": "romantic crush",
    "вайб": "mood or atmosphere",
    "чил": "relaxed time",
    "чилить": "to relax",
    "зашло": "liked it / it worked emotionally",
    "жиза": "very relatable",
    "рофл": "joke, teasing, irony",
    "агриться": "to get angry or irritated",
    "сорян": "sorry, informal",
    "ок": "okay",
    "хз": "I do not know / uncertain",
    "щас": "now / in a moment",
    "ща": "now / in a moment",
    "норм": "fine / okay",
    "спс": "thanks",
    "пж": "please",
    "плиз": "please",
    "lol": "laughing / joking",
    "lmao": "strong laughter",
    "idk": "I do not know / uncertain",
    "btw": "by the way",
    "imo": "in my opinion",
    "vibe": "mood or atmosphere",
}

SMILEY_MEANINGS = {
    ":)": "friendly warmth or a light smile",
    ":-)": "friendly warmth or a light smile",
    ")": "soft smile in Russian chat style, if context supports it",
    "))": "stronger friendly smile or amusement",
    ";)": "playful wink",
    ";-)": "playful wink",
    ":(": "sadness or disappointment",
    ":-(": "sadness or disappointment",
    "(": "sadness in Russian chat style, if context supports it",
    "((": "stronger sadness or disappointment",
}

COMMON_TYPO_HINTS = (
    ("превед", "привет"),
    ("счас", "сейчас"),
    ("щас", "сейчас"),
    ("чо", "что"),
    ("че", "что"),
    ("шо", "что"),
    ("нинаю", "не знаю"),
    ("незнаю", "не знаю"),
    ("пжл", "пожалуйста"),
    ("пж", "пожалуйста"),
)


@dataclass(frozen=True)
class LanguageSignal:
    slang_terms: dict[str, str]
    smileys: dict[str, str]
    typo_hints: dict[str, str]
    has_colloquial_language: bool
    guidance: str


def _find_terms(text: str, dictionary: dict[str, str]) -> dict[str, str]:
    lowered = text.casefold()
    return {term: meaning for term, meaning in dictionary.items() if term.casefold() in lowered}


def _find_typos(text: str) -> dict[str, str]:
    lowered = text.casefold()
    return {source: target for source, target in COMMON_TYPO_HINTS if source in lowered}


def analyze_language_robustness(message: str) -> LanguageSignal:
    slang_terms = _find_terms(message, SLANG_DICTIONARY)
    smileys = _find_terms(message, SMILEY_MEANINGS)
    typo_hints = _find_typos(message)
    has_colloquial_language = bool(slang_terms or smileys or typo_hints)

    guidance = (
        "Interpret slang, smileys, typos, and colloquial phrasing generously. "
        "Do not correct the user's spelling unless they ask. "
        "If meaning is ambiguous, infer the most natural conversational meaning or ask softly."
    )

    return LanguageSignal(
        slang_terms=slang_terms,
        smileys=smileys,
        typo_hints=typo_hints,
        has_colloquial_language=has_colloquial_language,
        guidance=guidance,
    )
