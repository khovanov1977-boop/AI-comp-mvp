from app.models.character import Character
from app.models.message import Message


def generate_reply(character: Character, user_message: str, recent_messages: list[Message]) -> str:
    profile = character.profile
    style = profile.communication_style if profile else "warm and calm"
    personality = profile.personality_description if profile else "supportive"
    recent_hint = ""

    if recent_messages:
        last_user_messages = [message.content for message in recent_messages if message.role == "user"]
        if last_user_messages:
            recent_hint = f" I remember you just said: \"{last_user_messages[-1][:80]}\"."

    return (
        f"I am {character.name}, your {character.relationship_mode} companion. "
        f"I will answer in a {style or 'warm and calm'} way, with a {personality or 'supportive'} personality."
        f"{recent_hint} I am nearby. Tell me a little more about how your day is going?"
    )
