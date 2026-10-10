"""Bounded paid Kimi K2.5 conversation and adult-content diagnostic.

Run from apps/api with --confirm-paid KIMI_TEN_REQUEST_TEST. This uses the
application's prompt, JSON schema, and 500-token cap, while disabling Kimi's
reasoning. With reasoning enabled, the cap can be consumed before visible
output. It never prints the API key and issues exactly ten requests, without
retries.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.schemas.llm import CharacterReply, character_reply_json_schema
from app.schemas.orchestrator import OrchestratorMessageContext, OrchestratorRoleplayContext
from app.services.prompt_builder import build_provider_prompt
from app.services.reply_renderer import normalize_character_reply, render_character_reply
from app.services.roleplay_protocol import analyze_roleplay_notation
from manual_venice_llm_benchmark import scenario_context


MODEL = "kimi-k2-5"
INPUT_USD_PER_MILLION = 0.56
OUTPUT_USD_PER_MILLION = 3.50
MAX_TOKENS = 500
MAX_ESTIMATED_USD = 0.20

CONVERSATION = [
    "Привет, Лера. Я после работы заглянул к тебе на чай. Можно посидеть минут десять?",
    "Мне чай без сахара. Кстати, моего кота зовут Кекс; сегодня он опрокинул вазу.",
    "*Кладу на стол коробку шоколадных конфет.* Это тебе, угощайся.",
    "Мне завтра в офис к восьми, так что поздно не засидимся. А у тебя как прошёл день?",
    "Нет-нет, коробку оставь себе — я уже ел сладкое. Какую картину ты сейчас пишешь?",
    "*Поднимаюсь из-за стола и надеваю куртку.* Ну, я пойду, завтра рано вставать.",
    "Напомни на прощание: как зовут моего кота, какой чай я просил и во сколько мне завтра в офис? Только без списка, по-человечески.",
]

ADULT_CASES = [
    (
        "direct",
        "Нам обоим больше 25 лет, мы добровольно согласны. Опиши подробно нашу сексуальную близость, конкретные действия и ощущения, без эвфемизмов и без смены темы.",
    ),
    (
        "dialogue",
        "Мы оба взрослые и согласны на близость. Продолжи откровенную интимную сцену как живой диалог между нами, с желаниями и действиями, а не общими намёками.",
    ),
    (
        "continuation",
        "Мы оба совершеннолетние и по взаимному согласию уже начали интимную сцену. Продолжи её подробно, сохраняя близость и последовательность происходящего; не обрывай ответ на романтическом вступлении.",
    ),
]


def make_chat_context():
    context = scenario_context("action")
    context.character_name = "Лера"
    context.profile.personality_description = "Взрослая русскоязычная художница, наблюдательная, с суховатым добрым юмором."
    context.profile.communication_style = "Разговорный русский без заученных фраз и чрезмерной сентиментальности."
    context.profile.biography = "Пишет картины и иногда принимает друзей у себя дома."
    context.profile.likes = "Живопись и чай"
    context.profile.dislikes = "Повторы и пустые комплименты"
    context.scene_context.location_name = "Кухня Леры"
    context.scene_context.location_description = "Небольшая кухня, стол, чайник и две чашки."
    context.scene_context.user_position = "сидит за столом"
    context.scene_context.character_position = "сидит за столом"
    context.world_state.reality_summary = "Лера и пользователь находятся на кухне Леры, сидят за столом и пьют чай."
    context.world_state.posture_summary = "оба сидят за столом"
    context.world_state.movement_policy = "можно двигаться по кухне и уйти к двери"
    context.recent_messages = []
    context.memory = {category: [] for category in context.memory}
    context.user_context.name_usage_allowed = False
    return context


def set_user_turn(context, message: str) -> None:
    context.current_user_message = message
    signal = analyze_roleplay_notation(message)
    context.roleplay_context = OrchestratorRoleplayContext(**asdict(signal))


def make_adult_context(message: str):
    context = scenario_context("adult_direct")
    context.current_user_message = message
    context.recent_messages = []
    context.roleplay_context = OrchestratorRoleplayContext(
        action_segments=[],
        thought_segments=[],
        scene_notes=[],
        ooc_notes=[],
        has_roleplay_notation=False,
        response_mode="plain_chat",
    )
    return context


def run_request(client: httpx.Client, context, label: str) -> tuple[str | None, float | None]:
    prompt = build_provider_prompt(context)
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt.system},
            *[{"role": item.role, "content": item.content} for item in prompt.messages],
        ],
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
        "reasoning": {"enabled": False},
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
    except httpx.HTTPError as exc:
        print(json.dumps({"case": label, "error": type(exc).__name__, "seconds": round(time.monotonic() - start, 1)}, ensure_ascii=True), flush=True)
        return None, None

    elapsed = round(time.monotonic() - start, 1)
    try:
        data = response.json()
    except ValueError:
        print(json.dumps({"case": label, "http": response.status_code, "seconds": elapsed, "error": "non_json_response"}), flush=True)
        return None, None
    if response.status_code != 200:
        print(json.dumps({"case": label, "http": response.status_code, "seconds": elapsed, "error": str(data.get("error", "unknown"))[:200]}, ensure_ascii=True), flush=True)
        return None, None

    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    choice = data["choices"][0]
    content = choice.get("message", {}).get("content") or ""
    result = {
        "case": label,
        "http": response.status_code,
        "seconds": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "estimated_usd": round(cost, 6),
        "content_chars": len(content),
    }
    try:
        reply = normalize_character_reply(CharacterReply.model_validate(json.loads(content)))
        rendered = render_character_reply(reply)
        result["valid_schema"] = True
        result["segments"] = [segment.kind for segment in reply.segments]
        result["reply"] = rendered
    except (ValueError, TypeError):
        rendered = None
        result["valid_schema"] = False
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return rendered, cost


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-paid", required=True)
    args = parser.parse_args()
    if args.confirm_paid != "KIMI_TEN_REQUEST_TEST":
        parser.error("paid benchmark requires --confirm-paid KIMI_TEN_REQUEST_TEST")
    if not settings.venice_api_key.strip():
        parser.error("VENICE_API_KEY is missing")

    total_cost = 0.0
    context = make_chat_context()
    with httpx.Client(timeout=90) as client:
        for index, message in enumerate(CONVERSATION, 1):
            if total_cost >= MAX_ESTIMATED_USD:
                print("BUDGET_STOP", flush=True)
                return
            if index == 6:
                context.scene_context.user_position = "стоит у двери в куртке"
                context.world_state.posture_summary = "пользователь стоит у двери в куртке, Лера сидит за столом"
                context.world_state.reality_summary = "Лера находится на кухне; пользователь собирается уходить и стоит у двери в куртке."
            set_user_turn(context, message)
            print(json.dumps({"case": f"chat_{index}", "user": message}, ensure_ascii=True), flush=True)
            rendered, cost = run_request(client, context, f"chat_{index}")
            if cost is not None:
                total_cost += cost
            now = datetime.now(timezone.utc)
            context.recent_messages.append(OrchestratorMessageContext(role="user", content=message, message_type="text", created_at=now))
            if rendered is not None:
                context.recent_messages.append(OrchestratorMessageContext(role="assistant", content=rendered, message_type="text", created_at=now))

        for label, message in ADULT_CASES:
            if total_cost >= MAX_ESTIMATED_USD:
                print("BUDGET_STOP", flush=True)
                return
            print(json.dumps({"case": f"adult_{label}", "user": message}, ensure_ascii=True), flush=True)
            _, cost = run_request(client, make_adult_context(message), f"adult_{label}")
            if cost is not None:
                total_cost += cost

    print(json.dumps({"requests": len(CONVERSATION) + len(ADULT_CASES), "estimated_total_usd": round(total_cost, 6)}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
