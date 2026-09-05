from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


PROFILE_COLUMNS = {
    "biography": "TEXT NOT NULL DEFAULT ''",
    "likes": "TEXT NOT NULL DEFAULT ''",
    "dislikes": "TEXT NOT NULL DEFAULT ''",
    "language": "VARCHAR NOT NULL DEFAULT 'ru'",
    "user_nickname": "VARCHAR NOT NULL DEFAULT ''",
    "warmth": "INTEGER NOT NULL DEFAULT 50",
    "initiative": "INTEGER NOT NULL DEFAULT 50",
    "playfulness": "INTEGER NOT NULL DEFAULT 50",
    "directness": "INTEGER NOT NULL DEFAULT 50",
    "emotionality": "INTEGER NOT NULL DEFAULT 50",
    "rationality": "INTEGER NOT NULL DEFAULT 50",
}

USER_COLUMNS = {
    "formal_name": "VARCHAR NOT NULL DEFAULT ''",
    "preferred_name": "VARCHAR NOT NULL DEFAULT ''",
    "casual_name": "VARCHAR NOT NULL DEFAULT ''",
    "vocative_name": "VARCHAR NOT NULL DEFAULT ''",
    "age": "INTEGER NULL",
    "city": "VARCHAR NOT NULL DEFAULT ''",
    "country": "VARCHAR NOT NULL DEFAULT ''",
    "timezone": "VARCHAR NOT NULL DEFAULT 'Europe/Moscow'",
    "language": "VARCHAR NOT NULL DEFAULT 'ru'",
}

SCENE_COLUMNS = {
    "id": "VARCHAR PRIMARY KEY",
    "character_id": "VARCHAR UNIQUE NOT NULL REFERENCES characters(id)",
    "presence_mode": "VARCHAR NOT NULL DEFAULT 'remote_chat'",
    "location_name": "VARCHAR NOT NULL DEFAULT 'Private chat'",
    "location_description": "TEXT NOT NULL DEFAULT ''",
    "time_description": "TEXT NOT NULL DEFAULT ''",
    "user_position": "VARCHAR NOT NULL DEFAULT 'at their own place'",
    "character_position": "VARCHAR NOT NULL DEFAULT 'at their own place'",
    "context_started_at": "TIMESTAMP NULL",
    "context_timestamp_basis": "VARCHAR NOT NULL DEFAULT 'utc'",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

MESSAGE_COLUMNS = {
    "audio_url": "TEXT NOT NULL DEFAULT ''",
    "audio_mime_type": "VARCHAR NOT NULL DEFAULT ''",
    "audio_duration_ms": "INTEGER NULL",
}


def legacy_local_timestamp_to_utc(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def normalize_legacy_finished_scene_memory(content: str) -> str:
    marker = "Scene-ending exchange:"
    if marker not in content:
        return content

    prefix, exchange_and_tail = content.split(marker, 1)
    exchange, separator, _tail = exchange_and_tail.partition(" This is shared past experience")
    user_statements = [
        part.strip()
        for part in exchange.split(" | ")
        if part.strip().startswith("user:")
    ]
    normalized_parts = [prefix.strip()]
    if user_statements:
        normalized_parts.append(
            "Past-scene user statements (historical; relative time words belong to that old scene): "
            + " | ".join(user_statements)
        )
    if separator or prefix.strip():
        normalized_parts.append(
            "This is shared past experience, not the current physical scene. Its old place, positions, "
            "relative dates, plans, and unfinished actions must never be treated as current."
        )
    return " ".join(normalized_parts)


def ensure_dev_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    profile_columns = {column["name"] for column in inspector.get_columns("character_profiles")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    scene_exists = inspector.has_table("character_scenes")
    memory_exists = inspector.has_table("memories")
    message_exists = inspector.has_table("messages")
    scene_columns = {column["name"] for column in inspector.get_columns("character_scenes")} if scene_exists else set()
    message_columns = {column["name"] for column in inspector.get_columns("messages")} if message_exists else set()
    needs_context_timestamp_migration = scene_exists and "context_timestamp_basis" not in scene_columns

    with engine.begin() as connection:
        for column_name, column_definition in PROFILE_COLUMNS.items():
            if column_name not in profile_columns:
                connection.execute(
                    text(f"ALTER TABLE character_profiles ADD COLUMN {column_name} {column_definition}")
                )
        for column_name, column_definition in USER_COLUMNS.items():
            if column_name not in user_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_definition}"))

        if message_exists:
            for column_name, column_definition in MESSAGE_COLUMNS.items():
                if column_name not in message_columns:
                    connection.execute(text(f"ALTER TABLE messages ADD COLUMN {column_name} {column_definition}"))

        if not scene_exists:
            column_sql = ", ".join(f"{column_name} {column_definition}" for column_name, column_definition in SCENE_COLUMNS.items())
            connection.execute(text(f"CREATE TABLE character_scenes ({column_sql})"))
            connection.execute(text("CREATE INDEX ix_character_scenes_character_id ON character_scenes (character_id)"))
        else:
            for column_name, column_definition in SCENE_COLUMNS.items():
                if column_name not in scene_columns:
                    connection.execute(
                        text(f"ALTER TABLE character_scenes ADD COLUMN {column_name} {column_definition}")
                    )

            if needs_context_timestamp_migration:
                legacy_scenes = list(
                    connection.execute(
                        text(
                            "SELECT id, context_started_at FROM character_scenes "
                            "WHERE context_started_at IS NOT NULL"
                        )
                    ).mappings()
                )
                for legacy_scene in legacy_scenes:
                    connection.execute(
                        text(
                            "UPDATE character_scenes "
                            "SET context_started_at = :context_started_at, context_timestamp_basis = 'utc' "
                            "WHERE id = :scene_id"
                        ),
                        {
                            "context_started_at": legacy_local_timestamp_to_utc(
                                legacy_scene["context_started_at"]
                            ),
                            "scene_id": legacy_scene["id"],
                        },
                    )

        if memory_exists:
            legacy_memories = list(
                connection.execute(
                    text(
                        "SELECT id, content FROM memories "
                        "WHERE memory_type = 'life_event' AND content LIKE '%Scene-ending exchange:%'"
                    )
                ).mappings()
            )
            for legacy_memory in legacy_memories:
                connection.execute(
                    text("UPDATE memories SET content = :content WHERE id = :memory_id"),
                    {
                        "content": normalize_legacy_finished_scene_memory(legacy_memory["content"]),
                        "memory_id": legacy_memory["id"],
                    },
                )
