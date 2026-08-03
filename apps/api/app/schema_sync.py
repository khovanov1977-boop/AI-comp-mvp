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
