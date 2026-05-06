from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

import pandas as pd

from core.db_connector import get_connection
from core.data_inspector import carregar_dataframe
from core.data_anomaly_detector import analisar_anomalias_tabela


def listar_tabelas_banco(
    schemas: Optional[List[str]] = None,
    incluir_views: bool = False,
) -> List[Dict[str, Any]]:
    schemas = [s.strip() for s in (schemas or []) if s.strip()]

    if incluir_views:
        filtro_tipo = "o.type IN ('U', 'V')"
    else:
        filtro_tipo = "o.type = 'U'"

    sql = f"""
    SELECT
        s.name AS schema_name,
        o.name AS table_name,
        o.type AS object_type
    FROM sys.objects o
    INNER JOIN sys.schemas s
        ON s.schema_id = o.schema_id
    WHERE {filtro_tipo}
      AND o.is_ms_shipped = 0
    ORDER BY s.name, o.name
    """

    with get_connection() as conn:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="pandas only supports SQLAlchemy connectable.*",
                category=UserWarning,
            )
            df = pd.read_sql(sql, conn)

    if schemas:
        df = df[df["schema_name"].isin(schemas)].copy()

    resultados = []
    for _, row in df.iterrows():
        resultados.append({
            "schema": str(row["schema_name"]),
            "table": str(row["table_name"]),
            "full_name": f"{row['schema_name']}.{row['table_name']}",
            "object_type": str(row["object_type"]),
        })

    return resultados


def calcular_score_anomalias(resultado_anomalias: Dict[str, Any]) -> int:
    score = 0

    pesos = {
        "muitos_nulos": 4,
        "coluna_constante": 2,
        "valores_negativos": 3,
        "outlier_iqr": 3,
        "ano_fora_faixa": 5,
        "mes_fora_faixa": 5,
        "duplicidade_combinacao": 6,
    }

    for item in resultado_anomalias.get("anomalias", []):
        tipo = item.get("tipo", "")
        score += pesos.get(tipo, 1)

    return score


def analisar_tabela_no_radar(
    tabela: str,
    limit: int = 200,
) -> Dict[str, Any]:
    try:
        df = carregar_dataframe(tabela=tabela, limit=limit)
    except Exception as exc:
        return {
            "tabela": tabela,
            "ok": False,
            "erro": str(exc),
            "linhas_lidas": 0,
            "score": 0,
            "anomalias_resultado": None,
        }

    try:
        resultado = analisar_anomalias_tabela(
            df,
            origem=f"Tabela: {tabela} (TOP {limit})"
        )
        score = calcular_score_anomalias(resultado)

        return {
            "tabela": tabela,
            "ok": True,
            "erro": "",
            "linhas_lidas": int(len(df)),
            "score": score,
            "anomalias_resultado": resultado,
        }
    except Exception as exc:
        return {
            "tabela": tabela,
            "ok": False,
            "erro": str(exc),
            "linhas_lidas": int(len(df)),
            "score": 0,
            "anomalias_resultado": None,
        }


def executar_radar_banco(
    schemas: Optional[List[str]] = None,
    incluir_views: bool = False,
    limit_por_tabela: int = 200,
    max_tabelas: Optional[int] = None,
) -> Dict[str, Any]:
    tabelas = listar_tabelas_banco(
        schemas=schemas,
        incluir_views=incluir_views,
    )

    if max_tabelas and max_tabelas > 0:
        tabelas = tabelas[:max_tabelas]

    resultados = []

    for item in tabelas:
        resultado = analisar_tabela_no_radar(
            tabela=item["full_name"],
            limit=limit_por_tabela,
        )
        resultados.append(resultado)

    ranking = sorted(
        [r for r in resultados if r.get("ok")],
        key=lambda x: (-x["score"], x["tabela"])
    )

    erros = [r for r in resultados if not r.get("ok")]

    return {
        "schemas": schemas or [],
        "incluir_views": incluir_views,
        "limit_por_tabela": limit_por_tabela,
        "total_tabelas_lidas": len(resultados),
        "total_ok": len(ranking),
        "total_erros": len(erros),
        "ranking": ranking,
        "erros": erros,
        "resultados": resultados,
    }


def render_markdown_data_radar(resultado: Dict[str, Any]) -> str:
    md: List[str] = []

    md.append("# SIGPLAN Data Radar")
    md.append("")
    md.append("## Resumo")
    md.append(f"- Schemas analisados: {', '.join(resultado.get('schemas', [])) or 'todos'}")
    md.append(f"- Limite por tabela: {resultado.get('limit_por_tabela', 0)}")
    md.append(f"- Total de tabelas lidas: {resultado.get('total_tabelas_lidas', 0)}")
    md.append(f"- Tabelas analisadas com sucesso: {resultado.get('total_ok', 0)}")
    md.append(f"- Tabelas com erro: {resultado.get('total_erros', 0)}")
    md.append("")

    md.append("## Ranking de tabelas suspeitas")
    ranking = resultado.get("ranking", [])
    if ranking:
        for idx, item in enumerate(ranking, start=1):
            anomalias = item.get("anomalias_resultado", {}) or {}
            total_anomalias = anomalias.get("total_anomalias", 0)
            md.append(
                f"{idx}. `{item['tabela']}` → score `{item['score']}` | "
                f"linhas `{item['linhas_lidas']}` | anomalias `{total_anomalias}`"
            )
    else:
        md.append("- Nenhuma tabela analisada com sucesso.")
    md.append("")

    md.append("## Principais achados por tabela")
    if ranking:
        for item in ranking[:20]:
            md.append(f"### {item['tabela']}")
            md.append(f"- Score: {item['score']}")
            md.append(f"- Linhas lidas: {item['linhas_lidas']}")

            anomalias = item.get("anomalias_resultado", {}) or {}
            lista = anomalias.get("anomalias", [])

            if lista:
                for achado in lista[:10]:
                    coluna = achado.get("coluna", "")
                    descricao = achado.get("descricao", "")
                    if coluna:
                        md.append(f"- **{coluna}** → {descricao}")
                    else:
                        md.append(f"- {descricao}")
            else:
                md.append("- Nenhuma anomalia registrada.")
            md.append("")
    else:
        md.append("- Nenhum achado.")
        md.append("")

    md.append("## Erros")
    erros = resultado.get("erros", [])
    if erros:
        for item in erros:
            md.append(f"- `{item['tabela']}` → `{item['erro']}`")
    else:
        md.append("- Nenhum erro.")
    md.append("")

    return "\n".join(md)