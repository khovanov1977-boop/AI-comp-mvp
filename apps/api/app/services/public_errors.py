from app.config import settings


def unexpected_error_message(exc: Exception) -> str:
    if settings.beta_safe_errors:
        return "Внутренняя ошибка сервера. Попробуйте позже."
    return str(exc) or exc.__class__.__name__
