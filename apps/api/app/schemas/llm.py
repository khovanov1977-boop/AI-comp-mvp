from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, Field


ReplySegmentKind = Literal["speech", "action", "thought", "scene_note", "ooc"]
AudioCue = Literal[
    "none",
    "laugh",
    "giggle",
    "sigh",
    "gasp",
    "cough",
    "cry",
    "whisper",
    "short_pause",
    "smile",
]
ReplyEmotion = Literal[
    "neutral",
    "warm",
    "amused",
    "embarrassed",
    "tender",
    "concerned",
    "sad",
    "angry",
    "afraid",
    "excited",
    "serious",
    "sarcastic",
    "curious",
    "tired",
]
ReplyPace = Literal["slow", "natural", "fast"]
ReplyIntensity = Literal["subtle", "balanced", "strong"]


class CharacterReplySegment(BaseModel):
    kind: ReplySegmentKind
    text: str = Field(min_length=1)
    audio_cue: AudioCue = "none"


class CharacterReplyDelivery(BaseModel):
    emotion: ReplyEmotion = "neutral"
    pace: ReplyPace = "natural"
    intensity: ReplyIntensity = "balanced"


class CharacterReply(BaseModel):
    segments: list[CharacterReplySegment] = Field(min_length=1)
    delivery: CharacterReplyDelivery = Field(default_factory=CharacterReplyDelivery)


CHARACTER_REPLY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "minItems": 1,
            "description": "Ordered visible reply segments. Keep spoken words separate from actions and thoughts.",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["speech", "action", "thought", "scene_note", "ooc"],
                    },
                    "text": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Segment content without Markdown wrappers or labels.",
                    },
                    "audio_cue": {
                        "type": "string",
                        "enum": [
                            "none",
                            "laugh",
                            "giggle",
                            "sigh",
                            "gasp",
                            "cough",
                            "cry",
                            "whisper",
                            "short_pause",
                            "smile",
                        ],
                        "description": "For speech or action segments: an audible cue at this position, or none. Thoughts, scene notes, and OOC segments use none.",
                    },
                },
                "required": ["kind", "text", "audio_cue"],
                "additionalProperties": False,
            },
        },
        "delivery": {
            "type": "object",
            "properties": {
                "emotion": {
                    "type": "string",
                    "enum": [
                        "neutral",
                        "warm",
                        "amused",
                        "embarrassed",
                        "tender",
                        "concerned",
                        "sad",
                        "angry",
                        "afraid",
                        "excited",
                        "serious",
                        "sarcastic",
                        "curious",
                        "tired",
                    ],
                },
                "pace": {"type": "string", "enum": ["slow", "natural", "fast"]},
                "intensity": {
                    "type": "string",
                    "enum": ["subtle", "balanced", "strong"],
                },
            },
            "required": ["emotion", "pace", "intensity"],
            "additionalProperties": False,
        },
    },
    "required": ["segments", "delivery"],
    "additionalProperties": False,
}


def character_reply_json_schema(voice_reply_requested: bool) -> dict:
    schema = deepcopy(CHARACTER_REPLY_JSON_SCHEMA)
    if voice_reply_requested:
        schema["properties"]["segments"]["items"]["properties"]["kind"]["enum"] = [
            "speech",
            "action",
            "scene_note",
            "ooc",
        ]
    return schema


def plain_character_reply(text: str) -> CharacterReply:
    return CharacterReply(
        segments=[CharacterReplySegment(kind="speech", text=text.strip() or "Я рядом. Давай продолжим.")]
    )
