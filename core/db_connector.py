import socket

import pyodbc

from core.config import get_db_config, validate_db_config


def get_connection_string(environment: str | None = None) -> str:
    config = get_db_config(environment)
    missing = validate_db_config(environment)

    if missing:
        raise ValueError(
            f"Configuração incompleta do banco '{config['environment']}': "
            f"{', '.join(missing)}"
        )

    conn_str = (
        f"DRIVER={{{config['driver']}}};"
        f"SERVER={config['server']};"
        f"DATABASE={config['database']};"
        f"UID={config['username']};"
        f"PWD={config['password']};"
        f"Encrypt={'yes' if config['encrypt'] else 'no'};"
        f"TrustServerCertificate={'yes' if config['trust_server_certificate'] else 'no'};"
        f"Connection Timeout={config['timeout']};"
    )
    return conn_str


def get_connection(environment: str | None = None) -> pyodbc.Connection:
    conn_str = get_connection_string(environment=environment)
    return pyodbc.connect(conn_str)


def _normalize_server_host(server_value: str) -> str:
    """
    Normaliza o nome do servidor para tentar resolver IP.
    Exemplos:
    - SERVIDOR\\INSTANCIA -> SERVIDOR
    - SERVIDOR,1433 -> SERVIDOR
    """
    host = (server_value or "").strip()

    if "\\" in host:
        host = host.split("\\", 1)[0]

    if "," in host:
        host = host.split(",", 1)[0]

    return host.strip()


def _resolve_server_ip(*candidates: str) -> str:
    """
    Tenta resolver IP a partir de múltiplos candidatos.
    Aceita hostname ou IP direto.
    """
    for raw in candidates:
        host = _normalize_server_host(raw)

        if not host or host == "-":
            continue

        if host.lower() in {"localhost", ".", "(local)"}:
            continue

        # Já é um IP
        try:
            socket.inet_aton(host)
            return host
        except OSError:
            pass

        # Tenta resolver DNS
        try:
            return socket.gethostbyname(host)
        except Exception:
            continue

    return "-"


def get_connection_info(connection, environment: str | None = None) -> dict:
    query = """
        SELECT
            @@SERVERNAME AS [server_name],
            DB_NAME() AS [database_name],
            HOST_NAME() AS [host_name],
            SUSER_SNAME() AS [login_name]
    """
    cursor = connection.cursor()
    cursor.execute(query)
    row = cursor.fetchone()

    server_name = row.server_name if row and row.server_name else "-"
    database_name = row.database_name if row and row.database_name else "-"
    host_name = row.host_name if row and row.host_name else "-"
    login_name = row.login_name if row and row.login_name else "-"

    configured_server = "-"
    if environment:
        try:
            config = get_db_config(environment)
            configured_server = config.get("server", "-")
        except Exception:
            configured_server = "-"

    server_ip = _resolve_server_ip(server_name, configured_server)

    return {
        "server_name": server_name,
        "server_ip": server_ip,
        "database_name": database_name,
        "host_name": host_name,
        "login_name": login_name,
        "configured_server": configured_server,
    }