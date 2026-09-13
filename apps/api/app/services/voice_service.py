import re

from app.models.character import Character
from app.models.message import Message
from app.providers.stt_factory import get_stt_provider
from app.providers.tts_base import SynthesizedSpeech
from app.providers.tts_factory import get_tts_provider
from app.providers.tts_openrouter import TTSConfigurationError, TTSProviderError
from app.schemas.llm import CharacterReply, CharacterReplyDelivery, plain_character_reply
from app.services.reply_renderer import build_spoken_transcript
from app.services.voice_catalog import is_supported_voice
from app.services.voice_storage import save_voice_file


PREVIEW_TEXT = (
    "Привет. День был непростой, но всё закончилось хорошо. "
    "Расскажи, как прошёл твой вечер?"
)

KNOWN_RUSSIAN_NAME_PRONUNCIATIONS = {
    "леша": "лёша",
    "леш": "лёш",
    "леши": "лёши",
    "леше": "лёше",
    "лешу": "лёшу",
    "лешей": "лёшей",
    "леха": "лёха",
    "лех": "лёх",
    "лехе": "лёхе",
    "леху": "лёху",
    "лехой": "лёхой",
    "алена": "алёна",
    "артем": "артём",
    "семен": "семён",
    "федор": "фёдор",
    "петр": "пётр",
}

EMOTION_DIRECTIONS = {
    "neutral": "neutral and present",
    "warm": "warm",
    "amused": "gently amused",
    "embarrassed": "slightly embarrassed",
    "tender": "tender",
    "concerned": "calm and concerned",
    "sad": "sad",
    "angry": "angry but controlled",
    "afraid": "afraid",
    "excited": "excited",
    "serious": "serious",
    "sarcastic": "lightly sarcastic",
    "curious": "curious and engaged",
    "tired": "tired",
}

PACE_DIRECTIONS = {
    "slow": "Use a slightly slow pace.",
    "natural": "Use a natural conversational pace.",
    "fast": "Use a slightly quick pace without rushing.",
}

INTENSITY_DIRECTIONS = {
    "subtle": "Keep the emotion subtle.",
    "balanced": "Keep the emotion natural and balanced.",
    "strong": "Let the emotion be clearly audible without theatrical overacting.",
}


def _apply_source_case(value: str, source: str) -> str:
    if source.isupper():
        return value.upper()
    if source[:1].isupper():
        return value[:1].upper() + value[1:]
    return value


def normalize_russian_pronunciation(character: Character, text: str) -> str:
    replacements = dict(KNOWN_RUSSIAN_NAME_PRONUNCIATIONS)
    user = character.user
    known_names = [character.name]
    if user:
        known_names.extend(
            [
                user.display_name,
                user.formal_name,
                user.preferred_name,
                user.casual_name,
                user.vocative_name,
            ]
        )
    for name in known_names:
        canonical = name.strip()
        if "ё" in canonical.casefold():
            replacements[canonical.casefold().replace("ё", "е")] = canonical.casefold()

    normalized = text
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = re.sub(
            rf"(?<!\w){re.escape(source)}(?!\w)",
            lambda match, target=target: _apply_source_case(target, match.group(0)),
            normalized,
            flags=re.IGNORECASE,
        )
    return normalized


def _scene_for_tts(character: Character) -> str:
    scene = character.scene
    if not scene or scene.presence_mode == "remote_chat":
        return "A personal voice message in a private chat."
    location = scene.location_name.strip() or "the active scene"
    if scene.presence_mode == "same_place":
        return f"The character is speaking naturally to the user nearby at {location}."
    return f"The character is speaking within the active roleplay scene at {location}."


def build_gemini_tts_input(character: Character, reply: CharacterReply) -> str:
    transcript = normalize_russian_pronunciation(character, build_spoken_transcript(reply))
    if not transcript:
        raise TTSProviderError("The character reply contains no spoken words")

    gender_profile = "woman" if character.gender == "female" else "man"
    delivery = reply.delivery
    emotion = EMOTION_DIRECTIONS[delivery.emotion]
    pace = PACE_DIRECTIONS[delivery.pace]
    intensity = INTENSITY_DIRECTIONS[delivery.intensity]
    return (
        "# AUDIO PROFILE\n"
        f"A native Russian-speaking {gender_profile} using the selected voice in a natural private conversation.\n\n"
        "# SCENE\n"
        f"{_scene_for_tts(character)}\n\n"
        "# DIRECTOR'S NOTES\n"
        f"Overall delivery is {emotion}. {pace} {intensity} "
        "Perform bracketed audio cues briefly and organically. Do not use an announcer voice.\n\n"
        "# TRANSCRIPT\n"
        f"{transcript}"
    )


def synthesize_character_speech(character: Character, reply: CharacterReply) -> SynthesizedSpeech:
    voice_id = character.profile.voice_id if character.profile else ""
    if not is_supported_voice(voice_id):
        raise TTSConfigurationError("Choose a voice in the character settings before sending a voice message")
    return get_tts_provider().synthesize(build_gemini_tts_input(character, reply), voice_id)


def prepare_character_voice(character: Character, message: Message, reply: CharacterReply) -> Message:
    voice_id = character.profile.voice_id if character.profile else ""
    if not is_supported_voice(voice_id):
        raise TTSConfigurationError("Choose a voice in the character settings before sending a voice message")
    message.voice_generation_input = build_gemini_tts_input(character, reply)
    message.voice_generation_voice_id = voice_id
    message.voice_generation_status = "pending"
    message.voice_generation_error = ""
    return message


def attach_prepared_character_voice(message: Message) -> Message:
    if not message.voice_generation_input or not is_supported_voice(message.voice_generation_voice_id):
        raise TTSConfigurationError("Saved voice generation data is unavailable")
    speech = get_tts_provider().synthesize(
        message.voice_generation_input,
        message.voice_generation_voice_id,
    )
    audio_url, mime_type = save_voice_file(message.character_id, speech.audio_bytes, speech.mime_type)
    message.message_type = "voice"
    message.audio_url = audio_url
    message.audio_mime_type = mime_type
    message.transcription_status = "not_applicable"
    message.voice_generation_status = "completed"
    message.voice_generation_error = ""
    message.voice_generation_input = ""
    message.voice_generation_voice_id = ""
    return message


def attach_character_voice(character: Character, message: Message, reply: CharacterReply) -> Message:
    prepare_character_voice(character, message, reply)
    return attach_prepared_character_voice(message)


def synthesize_voice_preview(voice_id: str) -> SynthesizedSpeech:
    if not is_supported_voice(voice_id):
        raise TTSConfigurationError("Unsupported character voice")
    preview_reply = plain_character_reply(PREVIEW_TEXT)
    preview_reply.delivery = CharacterReplyDelivery(
        emotion="warm",
        pace="natural",
        intensity="subtle",
    )
    provider_input = (
        "# AUDIO PROFILE\n"
        "A native Russian-speaking person using the selected voice in a natural private conversation.\n\n"
        "# SCENE\n"
        "A relaxed personal voice message.\n\n"
        "# DIRECTOR'S NOTES\n"
        "Warm, neutral and unforced. Use a natural conversational pace. Do not use an announcer voice.\n\n"
        "# TRANSCRIPT\n"
        f"{build_spoken_transcript(preview_reply)}"
    )
    return get_tts_provider().synthesize(provider_input, voice_id)


def speech_to_text(audio_bytes: bytes, mime_type: str) -> str:
    return get_stt_provider().transcribe(audio_bytes, mime_type)
