from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


def detectar_colunas_muito_nulas(df: pd.DataFrame, limite_percentual: float = 50.0) -> List[Dict[str, Any]]:
    achados = []
    total = len(df)
    if total == 0:
        return achados

    for col in df.columns:
        qtd = int(df[col].isna().sum())
        perc = round((qtd / total) * 100, 2)
        if perc >= limite_percentual:
            achados.append({
                "tipo": "muitos_nulos",
                "coluna": str(col),
                "nulos": qtd,
                "percentual": perc,
                "descricao": f"Coluna com alto percentual de nulos ({perc}%).",
            })

    achados.sort(key=lambda x: (-x["percentual"], x["coluna"]))
    return achados


def detectar_colunas_constantes(df: pd.DataFrame) -> List[Dict[str, Any]]:
    achados = []

    for col in df.columns:
        distintos = int(df[col].nunique(dropna=True))
        if distintos == 1 and len(df) > 0:
            valor = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            achados.append({
                "tipo": "coluna_constante",
                "coluna": str(col),
                "descricao": f"Coluna com um único valor distinto em toda a amostra.",
                "valor": str(valor) if valor is not None else "NULL",
            })

    return achados


def detectar_duplicidade_por_combinacao(df: pd.DataFrame, colunas: List[str]) -> Dict[str, Any] | None:
    if df.empty or not colunas or any(c not in df.columns for c in colunas):
        return None

    dup = df[df.duplicated(subset=colunas, keep=False)].copy()
    if dup.empty:
        return None

    return {
        "tipo": "duplicidade_combinacao",
        "colunas": colunas,
        "quantidade_linhas": int(len(dup)),
        "quantidade_grupos": int(dup.groupby(colunas).ngroups),
        "descricao": f"Foram encontradas duplicidades na combinação {', '.join(colunas)}.",
    }


def sugerir_chave_temporal(df: pd.DataFrame) -> List[str]:
    candidatos = []
    for nome in df.columns:
        n = str(nome).lower()
        if (
            n.endswith("_id")
            or "ano" in n
            or "mes" in n
            or "exercicio" in n
            or "reg_" in n
            or "pro_" in n
            or "pa_" in n
            or "uno_" in n
        ):
            candidatos.append(str(nome))
    return candidatos[:8]


def detectar_numericos_negativos(df: pd.DataFrame) -> List[Dict[str, Any]]:
    achados = []
    numericas = df.select_dtypes(include=["number"])

    for col in numericas.columns:
        qtd_neg = int((numericas[col] < 0).sum())
        if qtd_neg > 0:
            achados.append({
                "tipo": "valores_negativos",
                "coluna": str(col),
                "quantidade": qtd_neg,
                "descricao": f"Coluna contém {qtd_neg} valor(es) negativo(s).",
            })

    return achados


def detectar_outliers_iqr(df: pd.DataFrame) -> List[Dict[str, Any]]:
    achados = []
    numericas = df.select_dtypes(include=["number"])

    for col in numericas.columns:
        serie = numericas[col].dropna()
        if len(serie) < 8:
            continue

        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        limite_inf = q1 - 1.5 * iqr
        limite_sup = q3 + 1.5 * iqr

        qtd = int(((serie < limite_inf) | (serie > limite_sup)).sum())
        if qtd > 0:
            achados.append({
                "tipo": "outlier_iqr",
                "coluna": str(col),
                "quantidade": qtd,
                "limite_inferior": float(limite_inf),
                "limite_superior": float(limite_sup),
                "descricao": f"Coluna contém {qtd} valor(es) fora do intervalo interquartil expandido.",
            })

    return achados


def detectar_gaps_temporais_basicos(df: pd.DataFrame) -> List[Dict[str, Any]]:
    achados = []

    col_ano = None
    col_mes = None

    for col in df.columns:
        n = str(col).lower()
        if col_ano is None and "ano" in n:
            col_ano = str(col)
        if col_mes is None and "mes" in n:
            col_mes = str(col)

    if not col_ano or not col_mes:
        return achados

    try:
        anos = pd.to_numeric(df[col_ano], errors="coerce").dropna().astype(int)
        meses = pd.to_numeric(df[col_mes], errors="coerce").dropna().astype(int)
    except Exception:
        return achados

    if not anos.empty:
        invalidos_ano = anos[(anos < 2000) | (anos > 2100)]
        if not invalidos_ano.empty:
            achados.append({
                "tipo": "ano_fora_faixa",
                "coluna": col_ano,
                "quantidade": int(len(invalidos_ano)),
                "descricao": "Há valores de ano fora da faixa esperada (2000-2100).",
            })

    if not meses.empty:
        invalidos_mes = meses[(meses < 1) | (meses > 12)]
        if not invalidos_mes.empty:
            achados.append({
                "tipo": "mes_fora_faixa",
                "coluna": col_mes,
                "quantidade": int(len(invalidos_mes)),
                "descricao": "Há valores de mês fora da faixa esperada (1-12).",
            })

    return achados


def analisar_anomalias_tabela(df: pd.DataFrame, origem: str = "") -> Dict[str, Any]:
    anomalias: List[Dict[str, Any]] = []

    anomalias.extend(detectar_colunas_muito_nulas(df, limite_percentual=50.0))
    anomalias.extend(detectar_colunas_constantes(df))
    anomalias.extend(detectar_numericos_negativos(df))
    anomalias.extend(detectar_outliers_iqr(df))
    anomalias.extend(detectar_gaps_temporais_basicos(df))

    chave_sugerida = sugerir_chave_temporal(df)
    duplicidade = detectar_duplicidade_por_combinacao(df, chave_sugerida)
    if duplicidade:
        anomalias.append(duplicidade)

    return {
        "origem": origem,
        "linhas": int(len(df)),
        "anomalias": anomalias,
        "chave_sugerida": chave_sugerida,
        "total_anomalias": len(anomalias),
    }


def render_markdown_anomalias(resultado: Dict[str, Any]) -> str:
    md: List[str] = []

    md.append(f"# Anomalias Detectadas — {resultado['origem']}")
    md.append("")
    md.append(f"- Linhas avaliadas: {resultado['linhas']}")
    md.append(f"- Total de anomalias: {resultado['total_anomalias']}")
    md.append(f"- Chave sugerida para análise: {', '.join(resultado.get('chave_sugerida', [])) or 'nenhuma'}")
    md.append("")

    md.append("## Achados")
    if resultado["anomalias"]:
        for item in resultado["anomalias"]:
            coluna = item.get("coluna", "")
            descricao = item.get("descricao", "")

            if coluna:
                md.append(f"- **{coluna}** → {descricao}")
            else:
                md.append(f"- {descricao}")
    else:
        md.append("- Nenhuma anomalia relevante detectada.")
    md.append("")

    return "\n".join(md)