from pathlib import Path
from typing import List, Dict


def salvar_markdown(resultados: List[Dict], termo: str, caminho_saida: str) -> None:
    """
    Salva os resultados em Markdown.
    """
    path = Path(caminho_saida)
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas = []
    linhas.append("# Relatório de busca\n")
    linhas.append(f"**Termo pesquisado:** `{termo}`\n")
    linhas.append(f"**Total de ocorrências:** {len(resultados)}\n")

    for i, item in enumerate(resultados, start=1):
        linhas.append(f"## {i}. {item['arquivo']}")
        linhas.append(f"- Linha encontrada: {item['linha']}")
        linhas.append("### Contexto")
        linhas.append("```php")

        for ctx in item.get("contexto", []):
            prefixo = ">>" if ctx["numero"] == item["linha"] else "  "
            linhas.append(f"{prefixo} {ctx['numero']:>5}: {ctx['conteudo']}")

        linhas.append("```\n")

    path.write_text("\n".join(linhas), encoding="utf-8")