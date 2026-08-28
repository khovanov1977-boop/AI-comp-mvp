import re
from dataclasses import dataclass


UNKNOWN_NAMES = {"", "demo user", "not set", "none", "unknown", "the user"}
FORMAL_RELATIONSHIP_MODES = {"colleague", "mentor"}
NAME_COOLDOWN_ASSISTANT_MESSAGES = 5
EXPLICIT_NAME_REQUEST_MARKERS = (
    "как меня зовут",
    "назови меня",
    "обратись ко мне",
    "обращайся ко мне",
    "используй мое имя",
    "используй моё имя",
    "call me",
    "my name",
    "address me",
    "use my name",
)


@dataclass(frozen=True)
class UserAddressPolicy:
    default_name: str
    direct_address_name: str
    policy: str


@dataclass(frozen=True)
class NameUsageDecision:
    allowed: bool
    reason: str


def normalize_known_name(value: str) -> str:
    candidate = value.strip()
    return "" if candidate.casefold() in UNKNOWN_NAMES else candidate


def build_user_address_policy(
    relationship_mode: str,
    formal_name: str,
    preferred_name: str,
    vocative_name: str,
) -> UserAddressPolicy:
    formal = normalize_known_name(formal_name)
    preferred = normalize_known_name(preferred_name)
    vocative = normalize_known_name(vocative_name)

    if relationship_mode in FORMAL_RELATIONSHIP_MODES:
        default_name = formal or preferred
        return UserAddressPolicy(
            default_name=default_name,
            direct_address_name=default_name,
            policy="formal_by_relationship",
        )

    default_name = preferred or formal
    return UserAddressPolicy(
        default_name=default_name,
        direct_address_name=vocative or default_name,
        policy="preferred_by_relationship",
    )


def contains_name(text: str, name: str) -> bool:
    if not name:
        return False
    normalized_text = text.casefold().replace("ё", "е")
    normalized_name = name.casefold().replace("ё", "е")
    return bool(re.search(rf"(?<!\w){re.escape(normalized_name)}(?!\w)", normalized_text))


def decide_name_usage(
    current_user_message: str,
    recent_messages: list[tuple[str, str]],
    address_policy: UserAddressPolicy,
) -> NameUsageDecision:
    names = {
        name
        for name in (address_policy.default_name, address_policy.direct_address_name)
        if name
    }
    if not names:
        return NameUsageDecision(allowed=False, reason="no_explicit_name_available")

    normalized_message = current_user_message.casefold()
    if any(marker in normalized_message for marker in EXPLICIT_NAME_REQUEST_MARKERS):
        return NameUsageDecision(allowed=True, reason="explicit_user_request")

    checked_assistant_messages = 0
    for role, content in reversed(recent_messages):
        if role != "assistant":
            continue
        checked_assistant_messages += 1
        if any(contains_name(content, name) for name in names):
            return NameUsageDecision(allowed=False, reason="recent_name_cooldown")
        if checked_assistant_messages >= NAME_COOLDOWN_ASSISTANT_MESSAGES:
            break

    return NameUsageDecision(allowed=True, reason="available_but_optional")
