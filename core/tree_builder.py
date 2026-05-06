from pathlib import Path
from typing import Dict, List


def _basename(path_str: str) -> str:
    if not path_str:
        return ""
    return Path(path_str).name


def construir_arvore_dependencias(dados: Dict) -> List[str]:
    """
    Monta uma árvore textual das dependências do método, suportando segundo nível.
    """
    linhas = []

    raiz = dados.get("assinatura") or "metodo()"
    linhas.append(raiz)

    filhos = []

    # Includes resolvidos
    for item in dados.get("includes_resolvidos", []):
        nome = item.get("caminho_relativo") or item.get("instrucao") or "include"
        status = "OK" if item.get("existe") else "NÃO ENCONTRADO"
        filhos.append({
            "texto": f"include {nome} [{status}]",
            "subitens": []
        })

    # Dependências externas
    for item in dados.get("dependencias_externas", []):
        classe = item.get("classe", "ClasseDesconhecida")
        metodo = item.get("metodo", "metodo")
        metodo_info = item.get("metodo_encontrado")
        status = "OK" if metodo_info else "NÃO RESOLVIDO"

        subitens = []

        arquivo_classe = item.get("arquivo_classe", "")
        if arquivo_classe:
            subitens.append(f"arquivo: {_basename(arquivo_classe)}")

        if metodo_info:
            assinatura = metodo_info.get("assinatura", "")
            linhas_metodo = f"{metodo_info.get('linha_inicio', '?')}-{metodo_info.get('linha_fim', '?')}"
            if assinatura:
                subitens.append(f"assinatura: {assinatura}")
            subitens.append(f"linhas: {linhas_metodo}")

        sn = item.get("segundo_nivel")
        if sn:
            for ch in sn.get("chamadas", [])[:6]:
                classe_ch = ch.get("classe", "")
                if classe_ch:
                    subitens.append(f"chama: {classe_ch}::{ch['metodo']}()")
                else:
                    subitens.append(f"chama: {ch['objeto']}->{ch['metodo']}()")

            for tb in sn.get("tabelas", [])[:6]:
                subitens.append(f"tabela: {tb}")

            for pr in sn.get("procedures", [])[:4]:
                subitens.append(f"procedure: {pr}")

            for inc in sn.get("includes", [])[:4]:
                subitens.append(f"include: {inc}")

            for ac in sn.get("actions", [])[:4]:
                if "." in ac and not ac.lower().startswith(("_dbo.", "_ppa.", "gp.", "aux.")):
                    subitens.append(f"action: {ac}")

            for q in sn.get("queries_completas", [])[:3]:
                primeira_linha = q.get("sql", "").splitlines()[0] if q.get("sql") else ""
                if primeira_linha:
                    subitens.append(f"query: {primeira_linha[:80]}")

        filhos.append({
            "texto": f"{classe}::{metodo}() [{status}]",
            "subitens": subitens
        })

    # Tabelas do método principal
    for tabela in dados.get("tabelas", []):
        filhos.append({
            "texto": f"tabela {tabela}",
            "subitens": []
        })

    # Procedures do método principal
    for proc in dados.get("procedures", []):
        filhos.append({
            "texto": f"procedure {proc}",
            "subitens": []
        })

    # Actions do método principal
    for action in dados.get("actions", []):
        if "." in action and not action.lower().startswith(("_dbo.", "_ppa.", "gp.", "aux.")):
            filhos.append({
                "texto": f"action {action}",
                "subitens": []
            })

    # Queries do método principal
    for q in dados.get("queries_completas", [])[:5]:
        primeira_linha = q.get("sql", "").splitlines()[0] if q.get("sql") else ""
        if primeira_linha:
            filhos.append({
                "texto": f"query {primeira_linha[:80]}",
                "subitens": []
            })

    total = len(filhos)

    for i, filho in enumerate(filhos):
        ultimo = i == total - 1
        galho = "└──" if ultimo else "├──"
        linhas.append(f"{galho} {filho['texto']}")

        subitens = filho.get("subitens", [])
        for j, sub in enumerate(subitens):
            prefixo = "    " if ultimo else "│   "
            sub_galho = "└──" if j == len(subitens) - 1 else "├──"
            linhas.append(f"{prefixo}{sub_galho} {sub}")

    return linhas