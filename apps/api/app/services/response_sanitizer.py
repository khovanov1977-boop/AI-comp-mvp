import re


TOOL_TAG_PATTERN = re.compile(r"</?\s*tool_call\s*>", re.IGNORECASE)
CONTROL_LINE_PATTERN = re.compile(
    r"^\s*(?:wait|enter|submit|continue)\s*(?:</?\s*tool_call\s*>)?\s*$",
    re.IGNORECASE,
)
INLINE_CONTROL_PATTERN = re.compile(
    r"\b(?:wait|enter|submit|continue)\s*</?\s*tool_call\s*>",
    re.IGNORECASE,
)


def sanitize_assistant_reply(reply: str) -> str:
    cleaned = INLINE_CONTROL_PATTERN.sub("", reply)
    cleaned = TOOL_TAG_PATTERN.sub("", cleaned)
    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip() and not CONTROL_LINE_PATTERN.match(line)]
    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned or "Я рядом. Давай продолжим."
