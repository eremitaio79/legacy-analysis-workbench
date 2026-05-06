from __future__ import annotations

import json
from typing import Any, Dict


def montar_prompt_comentario_dados(
    perfil_dados: Dict[str, Any] | None = None,
    estrutura_tabela: Dict[str, Any] | None = None,
) -> str:
    partes = []
    partes.append(
        "Você é um analista técnico sênior especializado em sistemas legados PHP com SQL Server, "
        "engenharia reversa de bancos corporativos e diagnóstico de integridade de dados."
    )
    partes.append("")
    partes.append("Analise as informações abaixo e responda em português técnico claro e objetivo.")
    partes.append("")
    partes.append("Objetivos da análise:")
    partes.append("1. Explicar o que a tabela aparenta representar no negócio.")
    partes.append("2. Apontar sinais de workflow, histórico, auditoria, consolidação ou staging.")
    partes.append("3. Destacar riscos estruturais e hipóteses plausíveis.")
    partes.append("4. Sugerir próximos passos de investigação técnica.")
    partes.append("")
    partes.append("Regras importantes:")
    partes.append("- Não invente fatos não sustentados.")
    partes.append("- Diferencie claramente observação, inferência e hipótese.")
    partes.append("- Seja específico ao citar nomes de colunas ou padrões.")
    partes.append("- Quando houver indícios de modelagem implícita pela aplicação, mencione isso.")
    partes.append("")

    if estrutura_tabela:
        partes.append("### ESTRUTURA DA TABELA")
        partes.append(json.dumps(estrutura_tabela, ensure_ascii=False, indent=2))
        partes.append("")

    if perfil_dados:
        partes.append("### PERFIL DE DADOS")
        partes.append(json.dumps(perfil_dados, ensure_ascii=False, indent=2))
        partes.append("")

    partes.append("Formato desejado da resposta em português do brasil:")
    partes.append("")
    partes.append("## 1. Leitura geral")
    partes.append("## 2. Sinais estruturais importantes")
    partes.append("## 3. Riscos e hipóteses")
    partes.append("## 4. Próximos passos")
    partes.append("")
    partes.append("Se houver indícios fortes de algo como auditoria, workflow, integração ou consolidação, explique por quê.")

    return "\n".join(partes)