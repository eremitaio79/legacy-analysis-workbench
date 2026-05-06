class SigboardToolsError(Exception):
    """Erro base da aplicação."""


class InputValidationError(SigboardToolsError):
    """Erro de validação de entrada do usuário."""


class RequiredInputError(InputValidationError):
    """Campo obrigatório não informado."""


class InvalidOptionError(InputValidationError):
    """Opção de menu inválida."""


class OperationCancelledError(SigboardToolsError):
    """Operação cancelada pelo usuário."""
