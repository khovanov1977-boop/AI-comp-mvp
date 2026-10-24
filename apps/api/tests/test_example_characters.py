from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.example_catalog import validated_examples
from app.main import app
from app.models.account_usage import AccountUsage
from app.models.appearance import CharacterAppearance
from app.models.character import Character
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.user import User
from app.services.appearance_service import read_appearance
from app.services.example_characters import copy_example, list_ready_examples


def test_example_copy_has_three_selected_images_without_spending_user_allowance():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        assets = root / "examples" / "maria"
        assets.mkdir(parents=True)
        output = BytesIO()
        Image.new("RGB", (20, 30), "#cdbda8").save(output, format="PNG")
        for stage in ("face", "body", "clothing"):
            (assets / f"{stage}.png").write_bytes(output.getvalue())
        (assets / "manifest.json").write_text(json.dumps({
            "clothing": {"status": "accepted", "model": "grok-imagine-image-2-0-edit"}
        }), encoding="utf-8")
        with patch("app.services.example_characters.EXAMPLE_ASSET_ROOT", root / "examples"), \
             patch("app.services.image_storage.IMAGE_STORAGE_ROOT", root / "private"):
            with sessions() as db:
                user = User(email="example@example.com", display_name="Example")
                db.add(user)
                db.commit()
                ready = list_ready_examples()
                assert [item["slug"] for item in ready] == ["maria"]
                first = copy_example(db, user, "maria")
                second = copy_example(db, user, "maria")
                assert first.id != second.id
                assert db.get(AccountUsage, user.id) is None
                assert len(db.scalars(select(Character).where(Character.user_id == user.id)).all()) == 2
                for character in (first, second):
                    appearance = db.get(CharacterAppearance, character.id)
                    assert set(appearance.selections) == {"face", "body", "clothing"}
                    assert set(appearance.published["references"]) == {"face", "body", "clothing"}
                    assert len(db.scalars(select(MediaAsset).where(MediaAsset.character_id == character.id)).all()) == 3
                    clothing_asset = db.get(MediaAsset, appearance.published["references"]["clothing"]["asset_id"])
                    assert clothing_asset.provider == "venice:grok-imagine-image-2-0-edit"
                    assert db.scalars(select(Message).where(Message.character_id == character.id)).all() == []
                    assert all(item["current"] for item in read_appearance(db, character.id)["candidates"])
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_example_route_creates_only_private_character():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TemporaryDirectory() as directory:
        root = Path(directory)
        assets = root / "examples" / "maria"
        assets.mkdir(parents=True)
        output = BytesIO()
        Image.new("RGB", (20, 30), "#cdbda8").save(output, format="PNG")
        for stage in ("face", "body", "clothing"):
            (assets / f"{stage}.png").write_bytes(output.getvalue())
        try:
            with patch("app.main.SessionLocal", sessions), \
                 patch("app.services.example_characters.EXAMPLE_ASSET_ROOT", root / "examples"), \
                 patch("app.services.image_storage.IMAGE_STORAGE_ROOT", root / "private"):
                first, second = TestClient(app), TestClient(app)
                assert first.post("/auth/register", json={"email": "first@example.com", "password": "a secure password", "display_name": "First", "privacy_consent": True}).status_code == 201
                assert second.post("/auth/register", json={"email": "second@example.com", "password": "another password", "display_name": "Second", "privacy_consent": True}).status_code == 201
                assert len(first.get("/examples").json()) == 1
                mounted = next(route.app for route in app.routes if route.path == "/example-files")
                with patch.object(mounted, "all_directories", [root / "examples"]):
                    assert first.get("/example-files/maria/clothing.png").status_code == 200
                created = first.post("/examples/maria/copy")
                assert created.status_code == 200, created.text
                character_id = created.json()["id"]
                assert len(first.get(f"/media/{character_id}").json()) == 3
                assert first.get("/limits").json()["images_count"]["used"] == 0
                assert second.get(f"/characters/{character_id}").status_code == 404
                first.close(); second.close()
        finally:
            app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_all_prepared_examples_copy_with_exactly_three_images():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with TemporaryDirectory() as directory, \
         patch("app.services.image_storage.IMAGE_STORAGE_ROOT", Path(directory) / "private"):
        with sessions() as db:
            user = User(email="catalog@example.com", display_name="Catalog")
            db.add(user)
            db.commit()
            examples = validated_examples()
            assert len(examples) == 10
            for item in examples:
                character = copy_example(db, user, item["slug"])
                assert character.name == item["name"]
                assert len(db.scalars(select(MediaAsset).where(MediaAsset.character_id == character.id)).all()) == 3
            assert db.get(AccountUsage, user.id) is None
    Base.metadata.drop_all(engine)
    engine.dispose()
