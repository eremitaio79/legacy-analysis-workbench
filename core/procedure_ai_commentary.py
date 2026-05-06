from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from core.ai_analyzer import GeminiAnalyzer
from core.config import PROMPTS_DIR


def build_procedure_ai_context(analysis: Dict[str, Any]) -> str:
    procedure = analysis.get("procedure", "-")
    schema = analysis.get("schema", "-")
    classification = analysis.get("classification", "-")
    operations = ", ".join(analysis.get("operations", []) or []) or "-"
    warnings = analysis.get("warnings", []) or []
    parameters = analysis.get("parameters", []) or []
    tables = analysis.get("tables", {}) or {}
    calls = analysis.get("calls", {}) or {}
    resources = analysis.get("resources", {}) or {}
    queries_extracted = analysis.get("queries_extracted", {}) or {}

    warnings_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- Nenhum warning relevante"
    params_text = "\n".join(
        f"- {p.get('name', '-')} :: {p.get('data_type', '-')}"
        for p in parameters
    ) if parameters else "- Nenhum parâmetro"

    read_tables = "\n".join(f"- {t}" for t in tables.get("read", []) or []) if tables.get("read") else "- Nenhuma"
    write_tables = "\n".join(f"- {t}" for t in tables.get("write", []) or []) if tables.get("write") else "- Nenhuma"
    proc_calls = "\n".join(f"- {t}" for t in calls.get("procedures", []) or []) if calls.get("procedures") else "- Nenhuma"
    func_calls = "\n".join(f"- {t}" for t in calls.get("functions", []) or []) if calls.get("functions") else "- Nenhuma"

    resources_text = "\n".join(
        f"- {k}: {'sim' if v else 'não'}"
        for k, v in resources.items()
    ) if resources else "- Nenhum"

    extracted_summary = []
    for key in ("select", "insert", "update", "delete", "merge"):
        items = queries_extracted.get(key, []) or []
        extracted_summary.append(f"- {key.upper()}: {len(items)} bloco(s)")
    extracted_queries_text = "\n".join(extracted_summary)

    return f"""
Procedure: {schema}.{procedure}

Classificação: {classification}
Operações detectadas: {operations}

Parâmetros:
{params_text}

Tabelas lidas:
{read_tables}

Tabelas escritas:
{write_tables}

Procedures chamadas:
{proc_calls}

Funções chamadas:
{func_calls}

Recursos SQL detectados:
{resources_text}

Warnings:
{warnings_text}

Resumo das queries extraídas:
{extracted_queries_text}
""".strip()


def build_procedure_ai_prompt(
    analysis: Dict[str, Any],
    prompt_file: str = "procedure_ai_analysis_prompt.txt",
) -> str:
    context = build_procedure_ai_context(analysis)
    prompt_path = Path(PROMPTS_DIR) / prompt_file
    system_prompt = prompt_path.read_text(encoding="utf-8")

    return f"{system_prompt}\n\nContexto da procedure:\n\n{context}"


def generate_procedure_ai_commentary(
    analysis: Dict[str, Any],
    model: str,
    provider: str,
    prompt_file: str = "procedure_ai_analysis_prompt.txt",
    prefer_cache: bool = True,
) -> str:
    final_prompt = build_procedure_ai_prompt(
        analysis=analysis,
        prompt_file=prompt_file,
    )

    analyzer = GeminiAnalyzer(
        provider=provider,
        model=model,
        prompt_file=prompt_file,
    )

    procedure = analysis.get("procedure", "procedure")
    schema = analysis.get("schema", "_dbo")
    cache_key = f"procedure_ai__{schema}__{procedure}"

    return analyzer.analyze_free_text(
        prompt=final_prompt,
        use_cache_key=cache_key,
        prefer_cache=prefer_cache,
        max_output_tokens=4096,
    )