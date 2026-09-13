from app.schemas.llm import CharacterReply, CharacterReplySegment, plain_character_reply
from app.services.response_sanitizer import clean_assistant_text, sanitize_assistant_reply


AUDIO_TAGS = {
    "laugh": "[laughs]",
    "giggle": "[giggles]",
    "sigh": "[sighs]",
    "gasp": "[gasp]",
    "cough": "[cough]",
    "cry": "[crying]",
    "whisper": "[whispers]",
    "short_pause": "[short pause]",
    "smile": "[amused]",
}


def normalize_character_reply(reply: CharacterReply | str) -> CharacterReply:
    if isinstance(reply, str):
        return plain_character_reply(sanitize_assistant_reply(reply))

    segments = []
    for segment in reply.segments:
        text = clean_assistant_text(segment.text)
        if not text:
            continue
        segments.append(
            CharacterReplySegment(
                kind=segment.kind,
                text=text,
                audio_cue=segment.audio_cue if segment.kind in {"speech", "action"} else "none",
            )
        )
    if not segments:
        return plain_character_reply("Я рядом. Давай продолжим.")
    return CharacterReply(segments=segments, delivery=reply.delivery)


def render_character_reply(reply: CharacterReply) -> str:
    rendered = []
    for segment in reply.segments:
        if segment.kind == "speech":
            rendered.append(segment.text)
        elif segment.kind == "action":
            rendered.append(f"*{segment.text}*")
        elif segment.kind == "thought":
            rendered.append(f"~{segment.text}~")
        elif segment.kind == "scene_note":
            rendered.append(f"[scene: {segment.text}]")
        else:
            rendered.append(f"((OOC: {segment.text}))")
    return sanitize_assistant_reply(" ".join(rendered))


def build_spoken_transcript(reply: CharacterReply) -> str:
    parts = []
    for segment in reply.segments:
        audio_tag = AUDIO_TAGS.get(segment.audio_cue) if segment.kind in {"speech", "action"} else None
        if audio_tag:
            parts.append(audio_tag)
        if segment.kind == "speech":
            parts.append(segment.text)
    return " ".join(parts).strip()
