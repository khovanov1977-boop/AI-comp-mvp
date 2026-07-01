import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory


MEMORY_TRIGGERS = [
    "\u044f ",
    "\u043c\u043d\u0435 ",
    "\u043c\u0435\u043d\u044f ",
    "\u043b\u044e\u0431\u043b\u044e",
    "\u043d\u0440\u0430\u0432\u0438\u0442\u0441\u044f",
    "\u0445\u043e\u0447\u0443",
    "\u043f\u043b\u0430\u043d\u0438\u0440\u0443\u044e",
    "\u0440\u0430\u0431\u043e\u0442\u0430\u044e",
    "\u0436\u0438\u0432\u0443",
    "\u0436\u0438\u043b",
    "\u0440\u043e\u0434\u0438\u043b",
    "\u0434\u0435\u043d\u044c \u0440\u043e\u0436\u0434\u0435\u043d",
    "\u0434\u0430\u0442\u0430 \u0440\u043e\u0436\u0434\u0435\u043d",
    "\u043c\u043e\u0439 ",
    "\u043c\u043e\u044f ",
    "i ",
    "my ",
    "love",
    "like",
    "want",
    "plan",
    "work",
    "live",
    "born",
    "birthday",
]

MONTHS = {
    "\u044f\u043d\u0432\u0430\u0440": 1,
    "\u0444\u0435\u0432\u0440\u0430\u043b": 2,
    "\u043c\u0430\u0440\u0442": 3,
    "\u0430\u043f\u0440\u0435\u043b": 4,
    "\u043c\u0430\u044f": 5,
    "\u043c\u0430\u0439": 5,
    "\u0438\u044e\u043d": 6,
    "\u0438\u044e\u043b": 7,
    "\u0430\u0432\u0433\u0443\u0441\u0442": 8,
    "\u0441\u0435\u043d\u0442\u044f\u0431\u0440": 9,
    "\u043e\u043a\u0442\u044f\u0431\u0440": 10,
    "\u043d\u043e\u044f\u0431\u0440": 11,
    "\u0434\u0435\u043a\u0430\u0431\u0440": 12,
}

CITY_PATTERN = re.compile(
    r"(?:\u0432\s+)?(?:\u0433\u043e\u0440\u043e\u0434\u0435|\u0433\u043e\u0440\u043e\u0434|\u0433\.)\s+([^\s,.!?]+(?:[\s-][^\s,.!?]+)?)",
    re.IGNORECASE,
)


def normalize_birth_date(content: str) -> str | None:
    normalized = content.lower()
    if not any(marker in normalized for marker in ["\u0440\u043e\u0434\u0438\u043b", "\u0434\u0435\u043d\u044c \u0440\u043e\u0436\u0434\u0435\u043d", "\u0434\u0430\u0442\u0430 \u0440\u043e\u0436\u0434\u0435\u043d", "born", "birthday"]):
        return None

    year_match = re.search(r"(19|20)\d{2}", normalized)
    if not year_match:
        return None
    year = int(year_match.group(0))

    day_match = re.search(r"\b([0-2]?\d|3[01])\b", normalized)
    if not day_match:
        return None
    day = int(day_match.group(1))

    month = None
    numeric_date = re.search(r"\b([0-2]?\d|3[01])[.\-/ ]([01]?\d)\b", normalized)
    if numeric_date:
        month = int(numeric_date.group(2))
    else:
        for month_name, month_number in MONTHS.items():
            if month_name in normalized:
                month = month_number
                break

    if not month or not 1 <= month <= 12:
        return None

    return f"\u0434\u0430\u0442\u0430 \u0440\u043e\u0436\u0434\u0435\u043d\u0438\u044f {day:02d}.{month:02d}.{year}"


def normalize_location_fact(content: str) -> str | None:
    normalized = content.lower()
    city_match = CITY_PATTERN.search(content)
    if not city_match:
        return None

    city = city_match.group(1).strip(" .,!?:;")
    if not city:
        return None

    if "\u0440\u043e\u0434\u0438\u043b" in normalized:
        return f"\u043c\u0435\u0441\u0442\u043e \u0440\u043e\u0436\u0434\u0435\u043d\u0438\u044f {city}"

    if any(marker in normalized for marker in ["\u0436\u0438\u043b", "\u0436\u0438\u0432\u0443", "\u0436\u0438\u043b\u0430", "\u0436\u0438\u0432\u0443"]):
        age_match = re.search(r"\u0434\u043e\s+(\d{1,3})\s+\u043b\u0435\u0442", normalized)
        if age_match:
            return f"\u043c\u0435\u0441\u0442\u043e \u0436\u0438\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u0430 \u0434\u043e {age_match.group(1)} \u043b\u0435\u0442 {city}"
        return f"\u043c\u0435\u0441\u0442\u043e \u0436\u0438\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u0430 {city}"

    return None


def summarize_memory(content: str) -> str:
    normalized_birth_date = normalize_birth_date(content)
    if normalized_birth_date:
        return normalized_birth_date
    normalized_location = normalize_location_fact(content)
    if normalized_location:
        return normalized_location
    return content.strip()[:240]


def categorize_memory(content: str, summary: str) -> str:
    normalized = f" {content.lower()} "
    if any(marker in normalized for marker in ["\u043b\u044e\u0431\u043b\u044e", "\u043d\u0440\u0430\u0432\u0438\u0442\u0441\u044f", " love", " like"]):
        return "preference"
    if any(marker in normalized for marker in ["\u0440\u043e\u0434\u0438\u043b", "\u0436\u0438\u043b", " born"]) or summary.startswith(
        ("\u0434\u0430\u0442\u0430 \u0440\u043e\u0436\u0434\u0435\u043d\u0438\u044f", "\u043c\u0435\u0441\u0442\u043e \u0440\u043e\u0436\u0434\u0435\u043d\u0438\u044f")
    ):
        return "life_event"
    if any(marker in normalized for marker in ["\u043c\u0435\u0436\u0434\u0443 \u043d\u0430\u043c\u0438", "\u043d\u0430\u0448\u0438 \u043e\u0442\u043d\u043e\u0448\u0435\u043d", "relationship"]):
        return "relationship_note"
    return "user_fact"


def should_store_memory(content: str) -> bool:
    normalized = f" {content.lower()} "
    return len(content.strip()) >= 12 and any(trigger in normalized for trigger in MEMORY_TRIGGERS)


def remember_user_message(db: Session, character_id: str, content: str) -> Memory | None:
    summary = summarize_memory(content)
    if not should_store_memory(content):
        return None

    existing = db.scalar(
        select(Memory).where(
            Memory.character_id == character_id,
            Memory.content == summary,
        )
    )
    if existing:
        return existing

    memory = Memory(
        character_id=character_id,
        memory_type=categorize_memory(content, summary),
        content=summary,
        importance=2,
    )
    db.add(memory)
    return memory


def list_character_memories(db: Session, character_id: str, limit: int = 8) -> list[Memory]:
    return list(
        db.scalars(
            select(Memory)
            .where(Memory.character_id == character_id)
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
            .limit(limit)
        )
    )
