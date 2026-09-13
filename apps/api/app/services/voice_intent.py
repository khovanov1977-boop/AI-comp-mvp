import re


NEGATIVE_VOICE_PATTERNS = (
    re.compile(
        r"\bне\s+(?:присылай(?:те)?|отправляй(?:те)?|скидывай(?:те)?|записывай(?:те)?|"
        r"говори(?:те)?|отвечай(?:те)?|произноси(?:те)?|озвучивай(?:те)?)\b"
    ),
    re.compile(r"\bбез\s+(?:голосов\w*|аудио(?:сообщ\w*)?|войс\w*)\b"),
    re.compile(r"\bтолько\s+(?:текстом|текст)\b"),
    re.compile(r"\bне\s+(?:хочу|надо|нужно)\b.*\b(?:голосов\w*|аудио(?:сообщ\w*)?|войс\w*)\b"),
    re.compile(r"\b(?:голосов\w*|аудио(?:сообщ\w*)?|войс\w*)\b.*\bне\s+(?:надо|нужно)\b"),
)

VOICE_MEDIUM_PATTERN = re.compile(r"\b(?:голосов\w*|аудио(?:сообщ\w*)?|войс\w*|голосом|вслух)\b")
VOICE_REQUEST_PATTERNS = (
    re.compile(
        r"\b(?:пришли(?:те)?|отправь(?:те)?|скинь(?:те)?|запиши(?:те)?|"
        r"записать|прислать|отправить)\b"
    ),
    re.compile(
        r"\b(?:скажи(?:те)?|ответь(?:те)?|повтори(?:те)?|расскажи(?:те)?|"
        r"произнеси(?:те)?|прочитай(?:те)?)\b"
    ),
    re.compile(r"\bозвуч(?:ь|ьте|ить)\b"),
    re.compile(r"\b(?:хочу|можно|давай)\s+(?:мне\s+)?(?:голосов\w*|аудио(?:сообщ\w*)?|войс\w*)\b"),
    re.compile(r"\b(?:хочу|можно|дай|давай|могу|можешь|можете)\b.*\b(?:услышать|послушать)\b"),
)


def should_generate_voice_reply(message: str) -> bool:
    normalized = " ".join(message.casefold().replace("ё", "е").split())
    if not normalized or any(pattern.search(normalized) for pattern in NEGATIVE_VOICE_PATTERNS):
        return False
    if re.search(r"\b(?:услышать|послушать)\b.*\b(?:твой|ваш)?\s*голос\b", normalized):
        return True
    if re.search(r"\bозвуч(?:ь|ить)\b", normalized):
        return True
    if not VOICE_MEDIUM_PATTERN.search(normalized):
        return False
    return any(pattern.search(normalized) for pattern in VOICE_REQUEST_PATTERNS)
