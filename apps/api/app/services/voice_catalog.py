from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VoiceOption:
    id: str
    gender: str
    age_group: str
    description: str


VOICE_OPTIONS = (
    VoiceOption("Leda", "female", "25-30", "молодой, лёгкий"),
    VoiceOption("Sulafat", "female", "25-30", "мягкий, тёплый"),
    VoiceOption("Achernar", "female", "25-30", "мягкий, спокойный"),
    VoiceOption("Zephyr", "female", "25-30", "светлый, живой"),
    VoiceOption("Erinome", "female", "30-35", "ясный, спокойный"),
    VoiceOption("Aoede", "female", "30-35", "лёгкий, непринуждённый"),
    VoiceOption("Despina", "female", "30-35", "плавный, мягкий"),
    VoiceOption("Autonoe", "female", "35-40", "ясный, светлый"),
    VoiceOption("Kore", "female", "35-40", "уверенный, собранный"),
    VoiceOption("Vindemiatrix", "female", "35-40", "деликатный, мягкий"),
    VoiceOption("Pulcherrima", "female", "40+", "прямой, выразительный"),
    VoiceOption("Gacrux", "female", "40+", "зрелый, уверенный"),
    VoiceOption("Rasalgethi", "male", "20-25", "молодой, спокойный"),
    VoiceOption("Orus", "male", "25-30", "ровный, уверенный"),
    VoiceOption("Zubenelgenubi", "male", "25-30", "неформальный, естественный"),
    VoiceOption("Alnilam", "male", "30-35", "сдержанный, уверенный"),
    VoiceOption("Sadaltager", "male", "35-40", "знающий, спокойный"),
    VoiceOption("Umbriel", "male", "35-40", "мягкий, непринуждённый"),
    VoiceOption("Enceladus", "male", "35-40", "тихий, с придыханием"),
    VoiceOption("Iapetus", "male", "40+", "ясный, зрелый"),
    VoiceOption("Sadachbia", "male", "40+", "живой, выразительный"),
)

VOICE_BY_ID = {voice.id: voice for voice in VOICE_OPTIONS}


def is_supported_voice(voice_id: str) -> bool:
    return voice_id in VOICE_BY_ID


def is_voice_compatible(voice_id: str, character_gender: str) -> bool:
    voice = VOICE_BY_ID.get(voice_id)
    if not voice:
        return False
    return character_gender not in {"female", "male"} or voice.gender == character_gender


def catalog_payload() -> list[dict[str, str]]:
    return [asdict(voice) for voice in VOICE_OPTIONS]
