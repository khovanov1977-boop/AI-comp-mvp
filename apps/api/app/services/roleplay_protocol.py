import re
from dataclasses import dataclass


ACTION_PATTERN = re.compile(r"(?<!\*)\*([^*\r\n]+?)\*(?!\*)")
THOUGHT_PATTERN = re.compile(r"~([^~\r\n]+?)~")
SCENE_NOTE_PATTERN = re.compile(r"\[(?:scene|сцена)\s*:\s*([^\]]+?)\]", re.IGNORECASE)
OOC_PAREN_PATTERN = re.compile(
    r"\(\(\s*(?:(?:ooc|вне роли)\s*:?\s*)?(.+?)\s*\)\)",
    re.IGNORECASE | re.DOTALL,
)
OOC_BRACKET_PATTERN = re.compile(
    r"\[(?:ooc|вне роли)\s*:\s*([^\]]+?)\]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RoleplaySignal:
    action_segments: list[str]
    thought_segments: list[str]
    scene_notes: list[str]
    ooc_notes: list[str]
    has_roleplay_notation: bool
    response_mode: str


def _extract(pattern: re.Pattern[str], message: str) -> list[str]:
    return [match.strip() for match in pattern.findall(message) if match.strip()]


def analyze_roleplay_notation(message: str) -> RoleplaySignal:
    ooc_notes = [
        *_extract(OOC_PAREN_PATTERN, message),
        *_extract(OOC_BRACKET_PATTERN, message),
    ]
    message_without_ooc = OOC_PAREN_PATTERN.sub("", message)
    message_without_ooc = OOC_BRACKET_PATTERN.sub("", message_without_ooc)
    action_segments = _extract(ACTION_PATTERN, message_without_ooc)
    thought_segments = _extract(THOUGHT_PATTERN, message_without_ooc)
    scene_notes = _extract(SCENE_NOTE_PATTERN, message_without_ooc)
    has_roleplay_notation = bool(action_segments or thought_segments or scene_notes or ooc_notes)
    ooc_only = bool(ooc_notes) and not re.search(r"\w", message_without_ooc, re.UNICODE)

    if ooc_only:
        response_mode = "ooc_only"
    elif has_roleplay_notation:
        response_mode = "mirror_roleplay"
    else:
        response_mode = "plain_chat"

    return RoleplaySignal(
        action_segments=action_segments,
        thought_segments=thought_segments,
        scene_notes=scene_notes,
        ooc_notes=ooc_notes,
        has_roleplay_notation=has_roleplay_notation,
        response_mode=response_mode,
    )
