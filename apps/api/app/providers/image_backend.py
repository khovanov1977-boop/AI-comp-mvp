"""Selection between configured image backends; OpenRouter remains available."""

from app.config import Settings, settings
from app.providers.image_openrouter import OpenRouterImageProvider, image_configuration_error as openrouter_configuration_error
from app.providers.image_venice import VeniceImageProvider, venice_configuration_error


def image_configuration_error(config: Settings = settings, provider_name: str | None = None) -> str:
    name = provider_name or config.image_provider
    if name == "openrouter":
        return openrouter_configuration_error(config.model_copy(update={"image_provider": name}))
    if name == "venice":
        return venice_configuration_error(config.model_copy(update={"image_provider": name}))
    return "Генерация выключена. Укажите IMAGE_PROVIDER=venice или IMAGE_PROVIDER=openrouter в .env."


def model_for_stage(stage: str, config: Settings = settings, provider_name: str | None = None) -> str:
    name = provider_name or config.image_provider
    if name == "venice":
        return (config.venice_image_model if stage == "face" else config.venice_image_edit_model).strip()
    return config.image_model.strip()


def create_image_provider(provider_name: str, config: Settings = settings):
    selected = config.model_copy(update={"image_provider": provider_name})
    if provider_name == "venice":
        return VeniceImageProvider(selected)
    if provider_name == "openrouter":
        return OpenRouterImageProvider(selected)
    raise ValueError("Unsupported image provider")
