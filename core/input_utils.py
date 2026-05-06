from rich.prompt import Prompt, Confirm

from core.exceptions import RequiredInputError, InvalidOptionError


def ask_required_text(
    label: str,
    empty_message: str = "Entrada obrigatória não informada."
) -> str:
    value = Prompt.ask(label, default="").strip()
    if not value:
        raise RequiredInputError(empty_message)
    return value


def ask_optional_text(label: str) -> str:
    return Prompt.ask(label, default="").strip()


def ask_menu_option(
    label: str,
    valid_options: set[str],
    invalid_message: str = "Opção inválida."
) -> str:
    value = Prompt.ask(label, default="").strip().upper()

    if not value:
        raise InvalidOptionError("Nenhuma opção foi informada.")

    normalized_options = {opt.upper() for opt in valid_options}
    if value not in normalized_options:
        raise InvalidOptionError(invalid_message)

    return value


def ask_confirmation(label: str, default: bool = False) -> bool:
    return Confirm.ask(label, default=default)


from core.exceptions import InvalidOptionError, RequiredInputError


def require_non_empty(value: str | None, message: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise RequiredInputError(message)
    return normalized


def normalize_menu_option(value: str | None, valid_options: set[str]) -> str:
    normalized = (value or "").strip().lower()

    if not normalized:
        raise InvalidOptionError("Nenhuma opção foi informada.")

    valid_normalized = {opt.strip().lower() for opt in valid_options}
    if normalized not in valid_normalized:
        raise InvalidOptionError("Opção inválida.")

    return normalized