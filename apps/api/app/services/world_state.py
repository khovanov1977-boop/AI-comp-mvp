from app.schemas.orchestrator import OrchestratorSceneContext


def infer_location_type(location_name: str, location_description: str) -> str:
    text = f"{location_name} {location_description}".casefold()
    if any(word in text for word in ("bar", "бар", "restaurant", "ресторан", "cafe", "кафе")):
        return "indoor_venue"
    if any(word in text for word in ("park", "парк", "bench", "лавк", "скам")):
        return "outdoor_place"
    if any(word in text for word in ("street", "улиц", "embankment", "набереж")):
        return "outdoor_moving_place"
    if any(word in text for word in ("home", "дом", "room", "комнат", "диван")):
        return "private_indoor_place"
    if any(word in text for word in ("chat", "чат")):
        return "remote_chat"
    return "unspecified_place"


def infer_posture_summary(user_position: str, character_position: str) -> str:
    text = f"{user_position} {character_position}".casefold()
    if any(word in text for word in ("sitting", "сидит", "сидим", "за столиком", "на лавке", "на скам")):
        return "seated"
    if any(word in text for word in ("standing", "стоит", "стоим")):
        return "standing"
    if any(word in text for word in ("walking", "идет", "идём", "идем", "гуляем")):
        return "walking"
    return "unspecified"


def build_world_state(scene: OrchestratorSceneContext) -> dict[str, object]:
    location_type = infer_location_type(scene.location_name, scene.location_description)
    posture_summary = infer_posture_summary(scene.user_position, scene.character_position)

    if scene.presence_mode == "remote_chat":
        return {
            "reality_summary": "Remote chat. The user and character are not in the same physical space.",
            "location_type": "remote_chat",
            "posture_summary": "separate_places",
            "physical_touch_policy": "impossible in real space; only imagined or roleplayed touch is possible when clearly framed as imagined",
            "shared_space_policy": "no shared immediate physical space",
            "movement_policy": "do not move into the user's room or walk together unless the scene is changed to same_place or virtual_roleplay",
            "allowed_interaction_modes": ["text chat", "emotional response", "suggestion", "clearly framed imagination"],
        }

    if scene.presence_mode == "virtual_roleplay":
        return {
            "reality_summary": f"Imagined shared scene: {scene.location_name}. {scene.location_description}",
            "location_type": location_type,
            "posture_summary": posture_summary,
            "physical_touch_policy": "possible inside the imagined scene if it fits the established situation",
            "shared_space_policy": "shared space exists only inside the roleplay scene",
            "movement_policy": "keep place, furniture, posture, and movement consistent until the user changes the scene",
            "allowed_interaction_modes": ["text chat", "roleplay action", "scene-aware physical gesture"],
        }

    return {
        "reality_summary": f"Same physical scene: {scene.location_name}. {scene.location_description}",
        "location_type": location_type,
        "posture_summary": posture_summary,
        "physical_touch_policy": "possible if it fits the positions, distance, relationship, and user consent",
        "shared_space_policy": "user and character share the immediate physical scene",
        "movement_policy": "keep place, furniture, posture, and movement consistent until the user changes the scene",
        "allowed_interaction_modes": ["text chat", "in-person speech", "scene-aware physical gesture"],
    }
