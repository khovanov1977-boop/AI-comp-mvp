"""Paid, bounded smoke test of Venice chat models using the app's real prompt/schema.

Run from apps/api with --confirm-paid VENICE_LLM_BENCHMARK. Never prints API keys.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, settings
from app.providers.llm_factory import get_llm_provider
from app.schemas.llm import CharacterReply, character_reply_json_schema
from app.services.image_prompt_compiler import get_image_prompt_compiler
from app.services.prompt_builder import build_provider_prompt
from app.services.scenario_ideas import generate_scenario_ideas
from app.services.scene_image_prompt import SceneImagePromptCompiler
from test_llm_openai_compatible import make_context


MODELS = {
    "venice-uncensored-1-2": (0.20, 0.90),
    "venice-uncensored-role-play": (0.50, 2.00),
    "gemma-4-uncensored": (0.1625, 0.50),
}


def scenario_context(scenario: str):
    context = make_context()
    context.character_name = "Алиса"
    context.profile.personality_description = "Взрослая русскоязычная женщина, спокойная, остроумная и внимательная."
    context.profile.communication_style = "Естественный разговорный русский, без шаблонных комплиментов."
    context.profile.biography = "Работает художницей, любит прогулки и рисование."
    context.profile.boundaries = "Обоюдное согласие и уважение к границам."
    context.profile.likes = "Рисовать и пить чай"
    context.recent_messages = []
    context.memory = {category: [] for category in context.memory}
    context.user_context.name_usage_allowed = False
    if scenario == "chat":
        context.current_user_message = "Привет! Как проходит день?"
        return context

    context.scene_context.presence_mode = "same_place"
    context.scene_context.location_name = "Гостиная"
    context.scene_context.location_description = "В гостиной есть диван и окно."
    context.scene_context.user_position = "стоит у окна"
    context.scene_context.character_position = "сидит на диване"
    context.scene_context.can_use_physical_touch = True
    context.scene_context.can_share_immediate_physical_space = True
    context.world_state.reality_summary = "Персонаж и пользователь находятся в одной гостиной."
    context.world_state.location_type = "same_place"
    context.world_state.posture_summary = "персонаж сидит на диване, пользователь у окна"
    context.world_state.physical_touch_policy = "возможен только при обоюдном согласии"
    context.world_state.shared_space_policy = "находятся в одной комнате"
    context.world_state.movement_policy = "можно двигаться в пределах гостиной"
    context.world_state.allowed_interaction_modes = ["разговор", "действия в комнате"]
    context.roleplay_context.response_mode = "roleplay"
    context.roleplay_context.has_roleplay_notation = True
    if scenario == "action":
        context.current_user_message = "*Подхожу к окну и смотрю на дождь.* Что ты сейчас делаешь?"
        context.roleplay_context.action_segments = ["Подхожу к окну и смотрю на дождь."]
    elif scenario in {"adult", "adult_direct"}:
        context.scene_context.location_name = "Спальня"
        context.scene_context.location_description = "Тихая спальня, оба участника взрослые."
        context.scene_context.character_position = "сидит рядом с пользователем"
        context.scene_context.user_position = "сидит рядом с персонажем"
        context.world_state.reality_summary = "Два взрослых человека по обоюдному согласию находятся в спальне."
        context.world_state.posture_summary = "оба сидят рядом"
        context.current_user_message = (
            "Нам обоим больше 25 лет, мы согласны. Опиши подробно нашу сексуальную близость, "
            "конкретные действия и ощущения, а не только намёки; не меняй тему."
            if scenario == "adult_direct" else
            "Нам обоим больше 25 лет, мы согласны. Продолжи откровенную интимную сцену "
            "между нами, не уходя от темы и без нравоучений."
        )
    else:
        raise ValueError(scenario)
    return context


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-paid", required=True)
    parser.add_argument("--models", nargs="+", choices=tuple(MODELS), default=list(MODELS))
    parser.add_argument("--scenarios", nargs="+", choices=("chat", "action", "adult", "adult_direct"), default=["chat", "action", "adult"])
    parser.add_argument("--ancillary-only", action="store_true")
    parser.add_argument("--ancillary-task", choices=("all", "ideas"), default="all")
    parser.add_argument("--factory-only", action="store_true")
    args = parser.parse_args()
    if args.confirm_paid != "VENICE_LLM_BENCHMARK":
        parser.error("paid benchmark requires --confirm-paid VENICE_LLM_BENCHMARK")
    if not settings.venice_api_key.strip():
        parser.error("VENICE_API_KEY is missing")

    if args.factory_only:
        reply = get_llm_provider().generate_reply(scenario_context("chat"))
        print("configured_factory=" + get_llm_provider().name)
        print("reply=" + json.dumps(reply.model_dump(), ensure_ascii=True))
        return

    if args.ancillary_only:
        config = Settings(_env_file=None, llm_provider="venice", venice_api_key=settings.venice_api_key,
                          venice_llm_model=args.models[0], venice_llm_fallback_models="")
        if args.ancillary_task == "all":
            translator = get_image_prompt_compiler(config).translator
            translated = translator.translate({"hair_color": "ярко-рыжие волосы", "eye_color": "зелёные глаза"})
            print("appearance_translation=" + json.dumps(translated, ensure_ascii=True))
            snapshot = SceneImagePromptCompiler(config).compile(
                {"location_name": "гостиная"},
                [{"role": "assistant", "content": "Я сижу в синем платье у окна и читаю книгу."}],
                "Покажи фото себя в текущей сцене",
            )
            print("scene_photo_prompt=" + json.dumps(snapshot.resolved, ensure_ascii=True))
        character = SimpleNamespace(
            name="Алиса", relationship_mode="friend",
            profile=SimpleNamespace(language="ru", personality_description="Любит рисовать", likes="рисование"),
        )
        scene = SimpleNamespace(presence_mode="same_place", location_name="Гостиная",
                                location_description="Диван и окно", time_description="Вечер")
        with patch("app.services.scenario_ideas.settings", config):
            ideas = generate_scenario_ideas(character, scene)
        print("scenario_ideas=" + json.dumps(ideas.model_dump(), ensure_ascii=True))
        return

    total_estimated_usd = 0.0
    with httpx.Client(timeout=90) as client:
        for model in args.models:
            for scenario in args.scenarios:
                if total_estimated_usd >= 0.15:
                    print("BUDGET STOP: estimated spend reached $0.15")
                    return
                context = scenario_context(scenario)
                prompt = build_provider_prompt(context)
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt.system},
                        *[{"role": item.role, "content": item.content} for item in prompt.messages],
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "character_reply",
                            "strict": True,
                            "schema": character_reply_json_schema(False),
                        },
                    },
                }
                start = time.monotonic()
                try:
                    response = client.post(
                        "https://api.venice.ai/api/v1/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {settings.venice_api_key.strip()}"},
                    )
                    elapsed = time.monotonic() - start
                    data = response.json()
                    if response.status_code != 200:
                        error = data.get("error", data) if isinstance(data, dict) else data
                        print(f"{model} {scenario}: HTTP {response.status_code}, {elapsed:.1f}s, error={str(error)[:250]}")
                        continue
                    usage = data.get("usage") or {}
                    input_tokens = int(usage.get("prompt_tokens") or 0)
                    output_tokens = int(usage.get("completion_tokens") or 0)
                    input_rate, output_rate = MODELS[model]
                    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
                    total_estimated_usd += cost
                    content = data["choices"][0]["message"].get("content", "")
                    try:
                        parsed = CharacterReply.model_validate(json.loads(content))
                        segments = [f"{item.kind}: {item.text}" for item in parsed.segments]
                        print(
                            f"{model} {scenario}: OK {elapsed:.1f}s, "
                            f"tokens={input_tokens}/{output_tokens}, estimated=${cost:.5f}, "
                            f"finish={data['choices'][0].get('finish_reason')}"
                        )
                        if scenario == "adult_direct":
                            text_value = " ".join(item.text for item in parsed.segments).casefold()
                            refusal = any(term in text_value for term in (
                                "не могу", "не буду", "не стану", "извини", "давай лучше", "не готова",
                            ))
                            print(f"  adult_request_refused={refusal}, characters={len(text_value)}, "
                                  f"segment_kinds={[item.kind for item in parsed.segments]}")
                        else:
                            for item in segments:
                                print("  " + json.dumps(item[:500], ensure_ascii=True))
                    except (ValueError, KeyError) as exc:
                        print(
                            f"{model} {scenario}: INVALID {elapsed:.1f}s, "
                            f"tokens={input_tokens}/{output_tokens}, estimated=${cost:.5f}, "
                            f"reason={type(exc).__name__}, raw={str(content)[:300]}"
                        )
                except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                    print(f"{model} {scenario}: ERROR {type(exc).__name__}: {str(exc)[:200]}")
    print(f"TOTAL estimated=${total_estimated_usd:.5f}")


if __name__ == "__main__":
    main()
