class SigplanToolsError(Exception):
    """Erro base da aplicação."""


class InputValidationError(SigplanToolsError):
    """Erro de validação de entrada do usuário."""


class RequiredInputError(InputValidationError):
    """Campo obrigatório não informado."""


class InvalidOptionError(InputValidationError):
    """Opção de menu inválida."""


class OperationCancelledError(SigplanToolsError):
    """Operação cancelada pelo usuário."""


class SigplanToolsError(Exception):
    """Erro base da aplicação."""


class InputValidationError(SigplanToolsError):
    """Erro de validação de entrada do usuário."""