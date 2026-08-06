from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


PROFILE_COLUMNS = {
    "biography": "TEXT NOT NULL DEFAULT ''",
    "likes": "TEXT NOT NULL DEFAULT ''",
    "dislikes": "TEXT NOT NULL DEFAULT ''",
    "language": "VARCHAR NOT NULL DEFAULT 'ru'",
    "user_nickname": "VARCHAR NOT NULL DEFAULT ''",
}

USER_COLUMNS = {
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
    "user_position": "VARCHAR NOT NULL DEFAULT 'at their own place'",
    "character_position": "VARCHAR NOT NULL DEFAULT 'at their own place'",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
}


def ensure_dev_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    profile_columns = {column["name"] for column in inspector.get_columns("character_profiles")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    with engine.begin() as connection:
        for column_name, column_definition in PROFILE_COLUMNS.items():
            if column_name not in profile_columns:
                connection.execute(
                    text(f"ALTER TABLE character_profiles ADD COLUMN {column_name} {column_definition}")
                )
        for column_name, column_definition in USER_COLUMNS.items():
            if column_name not in user_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_definition}"))

        if not inspector.has_table("character_scenes"):
            column_sql = ", ".join(f"{column_name} {column_definition}" for column_name, column_definition in SCENE_COLUMNS.items())
            connection.execute(text(f"CREATE TABLE character_scenes ({column_sql})"))
            connection.execute(text("CREATE INDEX ix_character_scenes_character_id ON character_scenes (character_id)"))
