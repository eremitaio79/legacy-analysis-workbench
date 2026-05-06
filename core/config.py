import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _norm_path(value: str, fallback: Path | str) -> str:
    raw = (value or "").strip()
    if not raw:
        raw = str(fallback)

    return str(Path(raw).expanduser().resolve())


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"

SIGBOARD_PROJECT_PATH = _norm_path(
    os.getenv("SIGBOARD_PROJECT_PATH"),
    PROJECT_ROOT / "sample_legacy_app",
)

SIGBOARD_OUTPUT_DIR = _norm_path(
    os.getenv("SIGBOARD_OUTPUT_DIR"),
    PROJECT_ROOT / "out",
)

SIGBOARD_REPORT_DIR = os.getenv("SIGBOARD_REPORT_DIR", "reports").strip() or "reports"
SIGBOARD_DEFAULT_MD_NAME = os.getenv("SIGBOARD_DEFAULT_MD_NAME", "analysis.md").strip() or "analysis.md"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

SIGBOARD_AI_PROVIDER = os.getenv("SIGBOARD_AI_PROVIDER", "gemini").strip().lower()
SIGBOARD_AI_MODEL = os.getenv("SIGBOARD_AI_MODEL", "gemini-2.5-flash").strip()
SIGBOARD_AI_FALLBACK_MODEL = os.getenv("SIGBOARD_AI_FALLBACK_MODEL", "gemini-2.5-flash-lite").strip()
SIGBOARD_AI_PROMPT_FILE = os.getenv("SIGBOARD_AI_PROMPT_FILE", "ai_analysis_prompt.txt").strip()

SIGBOARD_DEFAULT_DEEP = _to_int(os.getenv("SIGBOARD_DEFAULT_DEEP"), 1)
SIGBOARD_DEFAULT_CONTEXTO = _to_int(os.getenv("SIGBOARD_DEFAULT_CONTEXTO"), 1)

SIGBOARD_AI_CACHE_ENABLED = _to_bool(os.getenv("SIGBOARD_AI_CACHE_ENABLED"), True)
SIGBOARD_AI_CACHE_DIR = _norm_path(
    os.getenv("SIGBOARD_AI_CACHE_DIR"),
    PROJECT_ROOT / ".cache" / "ai",
)

SIGBOARD_VERBOSE = _to_bool(os.getenv("SIGBOARD_VERBOSE"), True)

# =========================================================
# Banco de dados
# =========================================================

SIGBOARD_DB_ACTIVE = os.getenv("SIGBOARD_DB_ACTIVE", "homolog").strip().lower() or "homolog"
SIGBOARD_DB_DRIVER = os.getenv("SIGBOARD_DB_DRIVER", "ODBC Driver 17 for SQL Server").strip() or "ODBC Driver 17 for SQL Server"
SIGBOARD_DB_TRUST_CERTIFICATE = _to_bool(os.getenv("SIGBOARD_DB_TRUST_CERTIFICATE"), True)
SIGBOARD_DB_ENCRYPT = _to_bool(os.getenv("SIGBOARD_DB_ENCRYPT"), False)
SIGBOARD_DB_TIMEOUT = _to_int(os.getenv("SIGBOARD_DB_TIMEOUT"), 15)


def _db_env(prefix: str) -> dict:
    return {
        "server": os.getenv(f"{prefix}_SERVER", "").strip(),
        "database": os.getenv(f"{prefix}_DATABASE", "").strip(),
        "username": os.getenv(f"{prefix}_USERNAME", "").strip(),
        "password": os.getenv(f"{prefix}_PASSWORD", "").strip(),
    }


SIGBOARD_DB_HOMOLOG = _db_env("SIGBOARD_DB_HOMOLOG")
SIGBOARD_DB_PROD = _db_env("SIGBOARD_DB_PROD")


def get_db_config(environment: str | None = None) -> dict:
    """
    Retorna a configuração do ambiente de banco solicitado.

    Ambientes suportados:
    - homolog
    - prod
    - production
    """
    env_name = (environment or SIGBOARD_DB_ACTIVE).strip().lower()

    if env_name == "homolog":
        config = SIGBOARD_DB_HOMOLOG
        resolved_env = "homolog"
    elif env_name in {"prod", "production", "producao", "produção"}:
        config = SIGBOARD_DB_PROD
        resolved_env = "prod"
    else:
        raise ValueError(
            f"Ambiente de banco inválido: '{environment}'. Use 'homolog' ou 'prod'."
        )

    return {
        "environment": resolved_env,
        "driver": SIGBOARD_DB_DRIVER,
        "trust_server_certificate": SIGBOARD_DB_TRUST_CERTIFICATE,
        "encrypt": SIGBOARD_DB_ENCRYPT,
        "timeout": SIGBOARD_DB_TIMEOUT,
        **config,
    }


def validate_db_config(environment: str | None = None) -> list[str]:
    """
    Retorna uma lista com os campos ausentes da configuração do banco.
    """
    config = get_db_config(environment)
    missing = []

    for field in ("server", "database", "username", "password"):
        if not config.get(field):
            missing.append(field)

    return missing
