from pathlib import Path
from typing import Dict


def salvar_relatorio_dependencias(dados: Dict, caminho_saida: str) -> None:
    path = Path(caminho_saida)
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas = []
    linhas.append("# Relatório de dependências do método\n")
    linhas.append(f"**Arquivo:** `{dados['arquivo']}`  ")
    linhas.append(f"**Linhas:** {dados['linha_inicio']} a {dados['linha_fim']}  ")
    linhas.append(f"**Assinatura:** `{dados['assinatura']}`\n")

    linhas.append("## Parâmetros")
    if dados["parametros"]:
        for item in dados["parametros"]:
            linhas.append(f"- `{item}`")
    else:
        linhas.append("- Nenhum")
    linhas.append("")

    linhas.append("## Superglobais")
    if dados["superglobais"]:
        for item in dados["superglobais"]:
            linhas.append(f"- `{item}`")
    else:
        linhas.append("- Nenhuma")
    linhas.append("")

    linhas.append("## Instanciações")
    if dados["instanciacoes"]:
        for item in dados["instanciacoes"]:
            linhas.append(f"- `{item['variavel']}` => `{item['classe']}`")
    else:
        linhas.append("- Nenhuma")
    linhas.append("")

    linhas.append("## Chamadas de métodos")
    if dados["chamadas"]:
        for item in dados["chamadas"]:
            classe = f" ({item['classe']})" if item["classe"] else ""
            linhas.append(f"- `{item['objeto']}->{item['metodo']}()`{classe}")
    else:
        linhas.append("- Nenhuma")
    linhas.append("")

    linhas.append("## Includes / Requires")
    if dados["includes"]:
        for item in dados["includes"]:
            linhas.append(f"- `{item}`")
    else:
        linhas.append("- Nenhum")
    linhas.append("")

    linhas.append("## Includes resolvidos")
    includes_resolvidos = dados.get("includes_resolvidos", [])
    if includes_resolvidos:
        for item in includes_resolvidos:
            linhas.append(f"### `{item['instrucao']}`")
            linhas.append(f"- Caminho relativo: `{item['caminho_relativo'] or 'não identificado'}`")
            linhas.append(f"- Caminho resolvido: `{item['caminho_resolvido'] or 'não resolvido'}`")
            linhas.append(f"- Existe: `{'sim' if item['existe'] else 'não'}`")
            if item["existe"]:
                linhas.append(f"- Linhas: {item['linhas']}")
                linhas.append(f"- Tamanho (bytes): {item['tamanho_bytes']}")
            linhas.append("")
    else:
        linhas.append("- Nenhum")
        linhas.append("")

    linhas.append("## Actions")
    if dados["actions"]:
        for item in dados["actions"]:
            linhas.append(f"- `{item}`")
    else:
        linhas.append("- Nenhuma")
    linhas.append("")

    linhas.append("## Tabelas")
    if dados["tabelas"]:
        for item in dados["tabelas"]:
            linhas.append(f"- `{item}`")
    else:
        linhas.append("- Nenhuma")
    linhas.append("")

    linhas.append("## Procedures")
    if dados["procedures"]:
        for item in dados["procedures"]:
            linhas.append(f"- `{item}`")
    else:
        linhas.append("- Nenhuma")
    linhas.append("")

    linhas.append("## SQL suspeito")
    if dados["sql_suspeito"]:
        linhas.append("```sql")
        for item in dados["sql_suspeito"]:
            linhas.append(item)
        linhas.append("```")
    else:
        linhas.append("- Nenhum")
    linhas.append("")

    linhas.append("## Queries completas encontradas no método")

    queries = dados.get("queries_completas", [])

    if queries:
        for i, q in enumerate(queries, start=1):

            linhas.append("")
            linhas.append(f"  - query #{i}")

            if q.get("variavel"):
                linhas.append(f"    variável: {q['variavel']}")

            if q.get("metodo"):
                linhas.append(f"    método: {q['metodo']}")

            linhas.append("    SQL:")
            linhas.append("    ```sql")

            for linha_sql in q.get("sql", "").splitlines():
                linhas.append(f"    {linha_sql}")

            linhas.append("    ```")
            linhas.append("")

    else:
        linhas.append("- Nenhuma")
        linhas.append("")



    linhas.append("## Dependências externas resolvidas")
    externas = dados.get("dependencias_externas", [])
    if externas:
        for item in externas:
            linhas.append(f"### `{item['classe']}::{item['metodo']}()`")
            linhas.append(f"- Objeto: `{item['objeto']}`")
            if item["arquivo_classe"]:
                linhas.append(f"- Arquivo da classe: `{item['arquivo_classe']}`")
            else:
                linhas.append("- Arquivo da classe: não encontrado")

            if item["metodo_encontrado"]:
                linhas.append(f"- Método encontrado em: `{item['metodo_encontrado']['arquivo']}`")
                linhas.append(
                    f"- Linhas: {item['metodo_encontrado']['linha_inicio']} a {item['metodo_encontrado']['linha_fim']}")
                linhas.append(f"- Assinatura: `{item['metodo_encontrado']['assinatura']}`")
            else:
                linhas.append("- Método na classe: não encontrado")

            sn = item.get("segundo_nivel")
            if sn:
                linhas.append("- Segundo nível:")
                if sn.get("chamadas"):
                    linhas.append("  - Chamadas:")
                    for ch in sn["chamadas"]:
                        classe = f" ({ch['classe']})" if ch.get("classe") else ""
                        linhas.append(f"    - `{ch['objeto']}->{ch['metodo']}()`{classe}")
                if sn.get("tabelas"):
                    linhas.append("  - Tabelas:")
                    for tb in sn["tabelas"]:
                        linhas.append(f"    - `{tb}`")
                if sn.get("procedures"):
                    linhas.append("  - Procedures:")
                    for pr in sn["procedures"]:
                        linhas.append(f"    - `{pr}`")
                if sn.get("includes"):
                    linhas.append("  - Includes:")
                    for inc in sn["includes"]:
                        linhas.append(f"    - `{inc}`")
                if sn.get("actions"):
                    linhas.append("  - Actions:")
                    for ac in sn["actions"]:
                        linhas.append(f"    - `{ac}`")
            linhas.append("")
    else:
        linhas.append("- Nenhuma")
        linhas.append("")


    linhas.append("## Árvore de dependências")
    arvore = dados.get("arvore_dependencias", [])
    if arvore:
        linhas.append("```text")
        linhas.extend(arvore)
        linhas.append("```")
    else:
        linhas.append("- Não gerada")
    linhas.append("")

    linhas.append("## Bloco completo")
    linhas.append("```php")
    linhas.append(dados["bloco"])
    linhas.append("```")
    linhas.append("")

    path.write_text("\n".join(linhas), encoding="utf-8")