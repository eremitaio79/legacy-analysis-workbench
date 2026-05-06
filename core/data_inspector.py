from __future__ import annotations

import re
import warnings
from typing import Any, Dict, List, Optional

import pandas as pd

from core.db_connector import get_connection


def montar_query_tabela(nome_tabela: str, limit: int = 200) -> str:
    nome_tabela = nome_tabela.strip()
    return f"SELECT TOP {int(limit)} * FROM {nome_tabela}"


def carregar_dataframe(
    tabela: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 200,
) -> pd.DataFrame:
    if not tabela and not query:
        raise ValueError("Informe uma tabela ou uma query.")

    if query:
        sql = limpar_query_sql(query)
    else:
        sql = montar_query_tabela(tabela or "", limit=limit)

    with get_connection() as conn:
        # Silencia warning conhecido do pandas com conexão pyodbc
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="pandas only supports SQLAlchemy connectable.*",
                category=UserWarning,
            )
            df = pd.read_sql(sql, conn)

    return df


def serializar_valor(valor: Any) -> str:
    if pd.isna(valor):
        return "NULL"
    texto = str(valor)
    return texto[:120]


def detectar_colunas_nulas(df: pd.DataFrame) -> List[Dict[str, Any]]:
    resultado = []

    total = len(df)
    if total == 0:
        return resultado

    for col in df.columns:
        qtd = int(df[col].isna().sum())
        perc = round((qtd / total) * 100, 2) if total else 0.0
        resultado.append({
            "coluna": str(col),
            "nulos": qtd,
            "percentual": perc,
        })

    resultado.sort(key=lambda x: (-x["nulos"], x["coluna"]))
    return resultado


def detectar_cardinalidade(df: pd.DataFrame) -> List[Dict[str, Any]]:
    resultado = []

    total = len(df)

    for col in df.columns:
        distintos = int(df[col].nunique(dropna=True))
        perc = round((distintos / total) * 100, 2) if total else 0.0
        resultado.append({
            "coluna": str(col),
            "distintos": distintos,
            "percentual_distintos": perc,
        })

    resultado.sort(key=lambda x: (-x["distintos"], x["coluna"]))
    return resultado


def detectar_duplicidades_por_coluna(df: pd.DataFrame) -> List[Dict[str, Any]]:
    resultado = []

    if df.empty:
        return resultado

    for col in df.columns:
        serie = df[col]
        if serie.isna().all():
            continue

        duplicados = int(serie.duplicated(keep=False).sum())
        unicos = int(serie.nunique(dropna=True))

        resultado.append({
            "coluna": str(col),
            "duplicados": duplicados,
            "valores_unicos": unicos,
        })

    resultado.sort(key=lambda x: (-x["duplicados"], x["coluna"]))
    return resultado


def nome_coluna_parece_data(nome_coluna: str) -> bool:
    nome = (nome_coluna or "").strip().lower()

    pistas = [
        "data",
        "dt_",
        "_dt",
        "date",
        "ano",
        "mes",
        "exercicio",
        "vigencia",
        "periodo",
        "prazo",
    ]

    return any(p in nome for p in pistas)


def tentar_converter_datas_seguro(serie: pd.Series) -> Optional[pd.Series]:
    """
    Tenta converter apenas séries que realmente têm cara de data.
    Evita warnings do pandas em colunas texto arbitrárias.
    """
    nao_nulos = serie.dropna()

    if nao_nulos.empty:
        return None

    # usa uma amostra pequena para decidir
    amostra = nao_nulos.astype(str).head(20)

    # heurística: precisa haver boa chance de formato de data
    padrao_data = amostra.str.match(
        r"""^\d{4}[-/]\d{1,2}[-/]\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2})?)?$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$""",
        na=False,
    )

    # se poucos valores parecem data, aborta
    if padrao_data.sum() < max(3, int(len(amostra) * 0.5)):
        return None

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format, so each element will be parsed individually.*",
            category=UserWarning,
        )
        convertida = pd.to_datetime(serie, errors="coerce")

    if convertida.notna().sum() == 0:
        return None

    return convertida


def detectar_datas(df: pd.DataFrame) -> List[Dict[str, Any]]:
    resultado = []

    for col in df.columns:
        serie = df[col]

        if pd.api.types.is_datetime64_any_dtype(serie):
            if serie.dropna().empty:
                continue
            resultado.append({
                "coluna": str(col),
                "min": str(serie.min()),
                "max": str(serie.max()),
            })
            continue

        # só tenta converter object se o nome da coluna sugerir data/tempo
        if serie.dtype == object and nome_coluna_parece_data(str(col)):
            convertida = tentar_converter_datas_seguro(serie)
            if convertida is not None and not convertida.dropna().empty:
                resultado.append({
                    "coluna": str(col),
                    "min": str(convertida.min()),
                    "max": str(convertida.max()),
                })

    return resultado


def obter_amostra(df: pd.DataFrame, linhas: int = 10) -> List[Dict[str, str]]:
    if df.empty:
        return []

    amostra_df = df.head(linhas).copy()
    registros: List[Dict[str, str]] = []

    for _, row in amostra_df.iterrows():
        item = {}
        for col in amostra_df.columns:
            item[str(col)] = serializar_valor(row[col])
        registros.append(item)

    return registros


def resumir_tipos(df: pd.DataFrame) -> List[Dict[str, str]]:
    resultado = []
    for col, dtype in df.dtypes.items():
        resultado.append({
            "coluna": str(col),
            "tipo": str(dtype),
        })
    return resultado


def gerar_estatisticas_numericas(df: pd.DataFrame) -> List[Dict[str, Any]]:
    numericas = df.select_dtypes(include=["number"])
    if numericas.empty:
        return []

    stats = []
    desc = numericas.describe().transpose().fillna("")

    for col, row in desc.iterrows():
        stats.append({
            "coluna": str(col),
            "count": serializar_valor(row.get("count")),
            "mean": serializar_valor(row.get("mean")),
            "std": serializar_valor(row.get("std")),
            "min": serializar_valor(row.get("min")),
            "max": serializar_valor(row.get("max")),
        })

    return stats


def limpar_query_sql(query: str) -> str:
    if not query:
        return query

    q = query.strip()

    # remove ; no final, mesmo que haja espaços depois
    q = re.sub(r";+\s*$", "", q)

    # remove aspas externas simples ou duplas
    if (q.startswith('"') and q.endswith('"')) or (q.startswith("'") and q.endswith("'")):
        q = q[1:-1].strip()

    # remove ; novamente, caso estivesse dentro do wrapper externo
    q = re.sub(r";+\s*$", "", q)

    # normaliza multilinha:
    # - remove linhas vazias nas pontas
    # - preserva quebras de linha internas
    linhas = [linha.rstrip() for linha in q.splitlines()]
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    while linhas and not linhas[-1].strip():
        linhas.pop()

    q = "\n".join(linhas).strip()

    return q


def analisar_dataframe(df: pd.DataFrame, origem: str) -> Dict[str, Any]:
    return {
        "origem": origem,
        "linhas": int(len(df)),
        "colunas": int(len(df.columns)),
        "nomes_colunas": [str(c) for c in df.columns],
        "tipos": resumir_tipos(df),
        "nulos": detectar_colunas_nulas(df),
        "cardinalidade": detectar_cardinalidade(df),
        "duplicidades_por_coluna": detectar_duplicidades_por_coluna(df),
        "datas": detectar_datas(df),
        "estatisticas_numericas": gerar_estatisticas_numericas(df),
        "amostra": obter_amostra(df, linhas=10),
    }


def render_markdown_data_inspector(resultado: Dict[str, Any]) -> str:
    md: List[str] = []

    md.append(f"# SIGPLAN Data Inspector — {resultado['origem']}")
    md.append("")
    md.append("## Resumo")
    md.append(f"- Linhas: {resultado['linhas']}")
    md.append(f"- Colunas: {resultado['colunas']}")
    md.append("")

    md.append("## Colunas")
    for col in resultado["nomes_colunas"]:
        md.append(f"- `{col}`")
    md.append("")

    md.append("## Tipos")
    for item in resultado["tipos"]:
        md.append(f"- `{item['coluna']}` → `{item['tipo']}`")
    md.append("")

    md.append("## Nulos")
    if resultado["nulos"]:
        for item in resultado["nulos"][:50]:
            md.append(
                f"- `{item['coluna']}` → {item['nulos']} nulos ({item['percentual']}%)"
            )
    else:
        md.append("- Nenhum dado.")
    md.append("")

    md.append("## Cardinalidade")
    for item in resultado["cardinalidade"][:50]:
        md.append(
            f"- `{item['coluna']}` → {item['distintos']} distintos ({item['percentual_distintos']}%)"
        )
    md.append("")

    md.append("## Duplicidades por coluna")
    for item in resultado["duplicidades_por_coluna"][:50]:
        md.append(
            f"- `{item['coluna']}` → {item['duplicados']} ocorrências duplicadas aparentes"
        )
    md.append("")

    md.append("## Faixa de datas")
    if resultado["datas"]:
        for item in resultado["datas"]:
            md.append(
                f"- `{item['coluna']}` → min `{item['min']}` | max `{item['max']}`"
            )
    else:
        md.append("- Nenhuma coluna de data detectada.")
    md.append("")

    md.append("## Estatísticas numéricas")
    if resultado["estatisticas_numericas"]:
        for item in resultado["estatisticas_numericas"]:
            md.append(
                f"- `{item['coluna']}` → count={item['count']} mean={item['mean']} std={item['std']} min={item['min']} max={item['max']}"
            )
    else:
        md.append("- Nenhuma coluna numérica detectada.")
    md.append("")

    md.append("## Amostra")
    if resultado["amostra"]:
        for i, row in enumerate(resultado["amostra"], start=1):
            md.append(f"### Linha {i}")
            for col, val in row.items():
                md.append(f"- `{col}`: `{val}`")
            md.append("")
    else:
        md.append("- Nenhuma linha encontrada.")
        md.append("")

    return "\n".join(md)