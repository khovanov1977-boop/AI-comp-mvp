from app.models.character import Character
from app.models.message import Message


def generate_reply(character: Character, user_message: str, recent_messages: list[Message]) -> str:
    profile = character.profile
    style = (profile.communication_style if profile else "") or "warm and thoughtful"
    is_russian = any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in user_message)
    normalized_message = user_message.lower()
    user_message_count = len([message for message in recent_messages if message.role == "user"])

    if is_russian:
        if any(word in normalized_message for word in ["привет", "здравствуй", "добрый"]):
            return f"Привет. Я здесь, {character.name} слушает. Что у тебя сегодня на душе?"

        if "?" in user_message:
            return "Хороший вопрос. Я бы не спешила с ответом: сначала хочется понять, что для тебя в этом самое важное."

        variants = [
            "Понимаю. Расскажи чуть подробнее, я хочу уловить не только факты, но и настроение.",
            "Я рядом. В этом звучит что-то важное для тебя, давай разберем спокойно.",
            "Слышу тебя. Что в этой ситуации больше всего зацепило?",
            f"Мне нравится, что ты говоришь об этом прямо. Я отвечу в своем стиле: {style}.",
        ]
        return variants[user_message_count % len(variants)]

    if any(word in normalized_message for word in ["hello", "hi", "hey"]):
        return f"Hi. {character.name} is here with you. What is on your mind today?"

    if "?" in user_message:
        return "That is a good question. I would rather slow down and understand what matters most to you here."

    variants = [
        "I hear you. Tell me a little more, especially the part that feels most important.",
        "I am here with you. Let's take it one step at a time.",
        "That sounds meaningful. What stayed with you most about it?",
        f"I will keep the tone {style}, but I will not over-explain myself every time.",
    ]
    return variants[user_message_count % len(variants)]
