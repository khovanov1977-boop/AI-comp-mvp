from dataclasses import dataclass
from hashlib import sha256

from app.models.character import Character, CharacterState


POSITIVE_MARKERS = (
    "спасибо",
    "рад",
    "рада",
    "люблю",
    "нравится",
    "хорошо",
    "класс",
    "здорово",
    "обнимаю",
    "улыбаюсь",
    "thank",
    "love",
    "like",
    "great",
    "good",
    "hug",
)
NEGATIVE_MARKERS = (
    "злюсь",
    "ненавижу",
    "плохо",
    "устал",
    "устала",
    "обид",
    "груст",
    "страш",
    "одинок",
    "не хочу",
    "angry",
    "hate",
    "bad",
    "tired",
    "sad",
    "lonely",
)
CONFLICT_MARKERS = (
    "неправ",
    "ошиб",
    "перепут",
    "не называй",
    "ты не понял",
    "ты не поняла",
    "wrong",
    "mistake",
    "do not call",
    "you misunderstood",
)
AFFECTION_MARKERS = (
    "обнимаю",
    "целую",
    "держу за руку",
    "скучаю",
    "люблю",
    "hug",
    "kiss",
    "miss you",
    "hold your hand",
)
SMILE_MARKERS = (":)", ":-)", ";)", ";-)", ")", "😊", "🙂")


@dataclass(frozen=True)
class StateSignal:
    mood: str
    trust_delta: int
    attachment_delta: int
    energy_delta: int


def clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(value, maximum))


def has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def bounded_jitter(message: str, channel: str) -> int:
    digest = sha256(f"{channel}:{message}".encode("utf-8")).digest()
    return digest[0] % 3 - 1


def analyze_user_message(message: str) -> StateSignal:
    text = message.casefold()
    positive = has_any(text, POSITIVE_MARKERS) or has_any(message, SMILE_MARKERS)
    negative = has_any(text, NEGATIVE_MARKERS)
    conflict = has_any(text, CONFLICT_MARKERS)
    affection = has_any(text, AFFECTION_MARKERS)
    question = "?" in message or any(marker in text for marker in ("как ты", "что думаешь", "what do you think"))

    trust_delta = bounded_jitter(message, "trust")
    attachment_delta = bounded_jitter(message, "attachment")
    energy_delta = -1 + bounded_jitter(message, "energy")
    mood = "attentive"

    if conflict:
        mood = "guarded"
        trust_delta -= 2
        attachment_delta -= 1
        energy_delta -= 1
    elif negative:
        mood = "concerned"
        trust_delta += 0
        attachment_delta += 1
        energy_delta -= 2
    elif affection:
        mood = "warm"
        trust_delta += 1
        attachment_delta += 3
        energy_delta -= 1
    elif positive:
        mood = "warm"
        trust_delta += 2
        attachment_delta += 1
    elif question:
        mood = "curious"
        trust_delta += 1

    return StateSignal(
        mood=mood,
        trust_delta=trust_delta,
        attachment_delta=attachment_delta,
        energy_delta=energy_delta,
    )


def update_state_after_message(character: Character, user_message: str = "") -> CharacterState:
    state = character.state
    signal = analyze_user_message(user_message)

    state.mood = signal.mood
    state.trust_level = clamp(state.trust_level + signal.trust_delta)
    state.attachment_level = clamp(state.attachment_level + signal.attachment_delta)
    state.energy_level = clamp(state.energy_level + signal.energy_delta)
    return state
