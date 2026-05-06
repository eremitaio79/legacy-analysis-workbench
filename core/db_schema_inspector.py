from __future__ import annotations

from typing import Any, Dict, List, Tuple
import pandas as pd
from core.db_connector import get_connection
import warnings
from core.db_connector import get_connection


def split_schema_table(nome: str) -> Tuple[str, str]:
    nome = (nome or "").strip().replace("[", "").replace("]", "")
    if "." in nome:
        schema, tabela = nome.split(".", 1)
        return schema.strip(), tabela.strip()
    return "_dbo", nome.strip()


def _is_nan_like(value: Any) -> bool:
    return pd.isna(value)


def _to_int_or_none(value: Any) -> int | None:
    if _is_nan_like(value):
        return None
    try:
        return int(value)
    except Exception:
        return None


def format_sql_type(col: Dict[str, Any]) -> str:
    data_type = str(col.get("DATA_TYPE") or "").lower()
    char_len = _to_int_or_none(col.get("CHARACTER_MAXIMUM_LENGTH"))
    precision = _to_int_or_none(col.get("NUMERIC_PRECISION"))
    scale = _to_int_or_none(col.get("NUMERIC_SCALE"))

    if data_type in {"varchar", "char", "nvarchar", "nchar", "binary", "varbinary"}:
        if char_len is None:
            return data_type
        if char_len == -1:
            return f"{data_type}(max)"
        return f"{data_type}({char_len})"

    if data_type in {"decimal", "numeric"}:
        if precision is not None and scale is not None:
            return f"{data_type}({precision},{scale})"
        if precision is not None:
            return f"{data_type}({precision})"
        return data_type

    if data_type in {"float", "real"}:
        if precision is not None:
            return f"{data_type}({precision})"
        return data_type

    return data_type



import warnings

def _read_sql(sql: str, params: tuple) -> pd.DataFrame:
    with get_connection() as conn:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="pandas only supports SQLAlchemy connectable.*",
                category=UserWarning,
            )
            return pd.read_sql(sql, conn, params=params)


def obter_colunas_tabela(nome_tabela: str) -> List[Dict[str, Any]]:
    schema, tabela = split_schema_table(nome_tabela)

    sql = """
    SELECT
        c.TABLE_SCHEMA,
        c.TABLE_NAME,
        c.COLUMN_NAME,
        c.ORDINAL_POSITION,
        c.DATA_TYPE,
        c.CHARACTER_MAXIMUM_LENGTH,
        c.NUMERIC_PRECISION,
        c.NUMERIC_SCALE,
        c.IS_NULLABLE,
        c.COLUMN_DEFAULT,
        CAST(sc.is_identity AS INT) AS IS_IDENTITY
    FROM INFORMATION_SCHEMA.COLUMNS c
    INNER JOIN sys.objects o
        ON o.name = c.TABLE_NAME
    INNER JOIN sys.schemas s
        ON s.schema_id = o.schema_id
       AND s.name = c.TABLE_SCHEMA
    INNER JOIN sys.columns sc
        ON sc.object_id = o.object_id
       AND sc.name = c.COLUMN_NAME
    WHERE c.TABLE_SCHEMA = ?
      AND c.TABLE_NAME = ?
    ORDER BY c.ORDINAL_POSITION
    """

    df = _read_sql(sql, (schema, tabela))
    return df.to_dict(orient="records")


def obter_pk_tabela(nome_tabela: str) -> List[Dict[str, Any]]:
    schema, tabela = split_schema_table(nome_tabela)

    sql = """
    SELECT
        tc.CONSTRAINT_NAME,
        kcu.COLUMN_NAME,
        kcu.ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
    INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
       AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
       AND tc.TABLE_NAME = kcu.TABLE_NAME
    WHERE tc.TABLE_SCHEMA = ?
      AND tc.TABLE_NAME = ?
      AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
    ORDER BY kcu.ORDINAL_POSITION
    """

    df = _read_sql(sql, (schema, tabela))
    return df.to_dict(orient="records")


def obter_fks_tabela(nome_tabela: str) -> List[Dict[str, Any]]:
    schema, tabela = split_schema_table(nome_tabela)

    sql = """
    SELECT
        fk.name AS FK_NAME,
        ps.name AS PARENT_SCHEMA,
        pt.name AS PARENT_TABLE,
        pc.name AS PARENT_COLUMN,
        rs.name AS REFERENCED_SCHEMA,
        rt.name AS REFERENCED_TABLE,
        rc.name AS REFERENCED_COLUMN
    FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc
        ON fk.object_id = fkc.constraint_object_id
    INNER JOIN sys.tables pt
        ON fkc.parent_object_id = pt.object_id
    INNER JOIN sys.schemas ps
        ON pt.schema_id = ps.schema_id
    INNER JOIN sys.columns pc
        ON fkc.parent_object_id = pc.object_id
       AND fkc.parent_column_id = pc.column_id
    INNER JOIN sys.tables rt
        ON fkc.referenced_object_id = rt.object_id
    INNER JOIN sys.schemas rs
        ON rt.schema_id = rs.schema_id
    INNER JOIN sys.columns rc
        ON fkc.referenced_object_id = rc.object_id
       AND fkc.referenced_column_id = rc.column_id
    WHERE ps.name = ?
      AND pt.name = ?
    ORDER BY fk.name, pc.column_id
    """

    df = _read_sql(sql, (schema, tabela))
    return df.to_dict(orient="records")


def obter_indices_tabela(nome_tabela: str) -> List[Dict[str, Any]]:
    schema, tabela = split_schema_table(nome_tabela)

    sql = """
    SELECT
        i.name AS INDEX_NAME,
        i.is_unique AS IS_UNIQUE,
        i.type_desc AS INDEX_TYPE,
        c.name AS COLUMN_NAME,
        ic.key_ordinal AS KEY_ORDINAL
    FROM sys.indexes i
    INNER JOIN sys.index_columns ic
        ON i.object_id = ic.object_id
       AND i.index_id = ic.index_id
    INNER JOIN sys.columns c
        ON ic.object_id = c.object_id
       AND ic.column_id = c.column_id
    INNER JOIN sys.tables t
        ON i.object_id = t.object_id
    INNER JOIN sys.schemas s
        ON t.schema_id = s.schema_id
    WHERE s.name = ?
      AND t.name = ?
      AND i.name IS NOT NULL
    ORDER BY i.name, ic.key_ordinal
    """

    df = _read_sql(sql, (schema, tabela))
    return df.to_dict(orient="records")


def analisar_estrutura_tabela(nome_tabela: str) -> Dict[str, Any]:
    schema, tabela = split_schema_table(nome_tabela)

    colunas = obter_colunas_tabela(nome_tabela)
    pk = obter_pk_tabela(nome_tabela)
    fks = obter_fks_tabela(nome_tabela)
    indices = obter_indices_tabela(nome_tabela)

    pk_cols = {item["COLUMN_NAME"] for item in pk}

    colunas_formatadas = []
    for c in colunas:
        item = dict(c)
        item["SQL_TYPE_FORMATADO"] = format_sql_type(item)
        item["IS_PK"] = item.get("COLUMN_NAME") in pk_cols
        colunas_formatadas.append(item)

    return {
        "schema": schema,
        "tabela": tabela,
        "tabela_completa": f"{schema}.{tabela}",
        "total_colunas": len(colunas_formatadas),
        "total_pk_cols": len(pk),
        "total_fks": len(fks),
        "total_indices": len(indices),
        "colunas": colunas_formatadas,
        "pk": pk,
        "fks": fks,
        "indices": indices,
    }


def render_markdown_schema_inspector(resultado: Dict[str, Any]) -> str:
    md: List[str] = []

    md.append(f"# Estrutura da Tabela — {resultado['tabela_completa']}")
    md.append("")
    md.append("## Resumo")
    md.append(f"- Colunas: {resultado['total_colunas']}")
    md.append(f"- Colunas na PK: {resultado['total_pk_cols']}")
    md.append(f"- Relacionamentos FK: {resultado['total_fks']}")
    md.append(f"- Entradas de índice: {resultado['total_indices']}")
    md.append("")

    md.append("## Colunas")
    for c in resultado["colunas"]:
        extras = []
        if c.get("IS_PK"):
            extras.append("PK")
        if int(c.get("IS_IDENTITY") or 0) == 1:
            extras.append("IDENTITY")
        extras.append("NULL" if str(c.get("IS_NULLABLE")) == "YES" else "NOT NULL")

        default_val = c.get("COLUMN_DEFAULT")
        if default_val is not None and not pd.isna(default_val):
            extras.append(f"DEFAULT {default_val}")

        md.append(
            f"- `{c['COLUMN_NAME']}` → `{c['SQL_TYPE_FORMATADO']}` | {' | '.join(extras)}"
        )

    md.append("## Primary Key")
    if resultado["pk"]:
        for item in resultado["pk"]:
            md.append(
                f"- `{item['CONSTRAINT_NAME']}` → coluna `{item['COLUMN_NAME']}` (ordem {item['ORDINAL_POSITION']})"
            )
    else:
        md.append("- Nenhuma PK encontrada.")
    md.append("")

    md.append("## Foreign Keys")
    if resultado["fks"]:
        for item in resultado["fks"]:
            md.append(
                f"- `{item['FK_NAME']}` → `{item['PARENT_COLUMN']}` "
                f"→ `{item['REFERENCED_SCHEMA']}.{item['REFERENCED_TABLE']}.{item['REFERENCED_COLUMN']}`"
            )
    else:
        md.append("- Nenhuma FK encontrada.")
    md.append("")

    md.append("## Índices")
    if resultado["indices"]:
        for item in resultado["indices"]:
            md.append(
                f"- `{item['INDEX_NAME']}` → coluna `{item['COLUMN_NAME']}` | "
                f"tipo `{item['INDEX_TYPE']}` | unique `{item['IS_UNIQUE']}` | ordem `{item['KEY_ORDINAL']}`"
            )
    else:
        md.append("- Nenhum índice encontrado.")
    md.append("")

    return "\n".join(md)