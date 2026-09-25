"""Selection between configured image backends; OpenRouter remains available."""

from app.config import Settings, settings
from app.providers.image_openrouter import OpenRouterImageProvider, image_configuration_error as openrouter_configuration_error
from app.providers.image_venice import VeniceImageProvider, venice_configuration_error


def image_configuration_error(config: Settings = settings, provider_name: str | None = None) -> str:
    name = provider_name or config.image_provider
    if name == "hybrid":
        if config.grok_image_model.strip() != "x-ai/grok-imagine-image-2.0":
            return "Для лица и фигуры укажите GROK_IMAGE_MODEL=x-ai/grok-imagine-image-2.0."
        openrouter_config = config.model_copy(update={"image_provider": "openrouter", "image_model": config.grok_image_model})
        return openrouter_configuration_error(openrouter_config) or venice_configuration_error(
            config.model_copy(update={"image_provider": "venice"})
        )
    if name == "openrouter":
        model = config.grok_image_model if config.image_provider == "hybrid" else config.image_model
        return openrouter_configuration_error(config.model_copy(update={"image_provider": name, "image_model": model}))
    if name == "venice":
        return venice_configuration_error(config.model_copy(update={"image_provider": name}))
    return "Генерация выключена. Укажите IMAGE_PROVIDER=hybrid, venice или openrouter в .env."


def provider_for_stage(stage: str, config: Settings = settings) -> str:
    if stage not in {"face", "body", "clothing"}:
        raise ValueError("Unsupported appearance stage")
    if config.image_provider == "hybrid":
        return "venice" if stage == "clothing" else "openrouter"
    return config.image_provider


def model_for_stage(stage: str, config: Settings = settings, provider_name: str | None = None) -> str:
    name = provider_name or config.image_provider
    if name == "hybrid":
        return (config.venice_image_edit_model if stage == "clothing" else config.grok_image_model).strip()
    if name == "venice":
        return (config.venice_image_model if stage == "face" else config.venice_image_edit_model).strip()
    return config.image_model.strip()


def create_image_provider(provider_name: str, config: Settings = settings):
    updates = {"image_provider": provider_name}
    if config.image_provider == "hybrid" and provider_name == "openrouter":
        updates["image_model"] = config.grok_image_model
    selected = config.model_copy(update=updates)
    if provider_name == "venice":
        return VeniceImageProvider(selected)
    if provider_name == "openrouter":
        return OpenRouterImageProvider(selected)
    raise ValueError("Unsupported image provider")
