from __future__ import annotations

import json
from typing import Any, Dict


def montar_prompt_comentario_anomalias(
    resultado_anomalias: Dict[str, Any],
    estrutura_tabela: Dict[str, Any] | None = None,
) -> str:
    partes = []

    partes.append(
        "Você é um analista técnico sênior especializado em SQL Server, dados legados, "
        "engenharia reversa e diagnóstico de inconsistências em sistemas corporativos."
    )
    partes.append("")
    partes.append("Analise os achados abaixo e responda em português técnico claro.")
    partes.append("")
    partes.append("Objetivos:")
    partes.append("1. Explicar o que os achados sugerem.")
    partes.append("2. Separar observações, inferências e hipóteses.")
    partes.append("3. Destacar riscos funcionais ou de integridade.")
    partes.append("4. Sugerir próximos passos objetivos de investigação.")
    partes.append("")
    partes.append("Regras:")
    partes.append("- Não invente fatos não sustentados.")
    partes.append("- Cite colunas nominalmente quando relevante.")
    partes.append("- Quando houver forte chance de campo descontinuado, staging, auditoria ou carga incompleta, mencione isso.")
    partes.append("- Seja específico e direto.")
    partes.append("")

    if estrutura_tabela:
        partes.append("### ESTRUTURA DA TABELA")
        partes.append(json.dumps(estrutura_tabela, ensure_ascii=False, indent=2))
        partes.append("")

    partes.append("### ANOMALIAS DETECTADAS")
    partes.append(json.dumps(resultado_anomalias, ensure_ascii=False, indent=2))
    partes.append("")

    partes.append("Formato desejado:")
    partes.append("## 1. Leitura geral")
    partes.append("## 2. Achados relevantes")
    partes.append("## 3. Riscos e hipóteses")
    partes.append("## 4. Próximos passos")

    return "\n".join(partes)