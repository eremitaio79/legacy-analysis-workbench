import re
from pathlib import Path
from typing import List, Dict


def extrair_caminho_include(include_stmt: str) -> str:
    """
    Extrai o caminho textual de include/require, se houver string literal.
    Ex:
    include("controle/arquivo.php")
    require_once 'x/y/z.php'
    """
    m = re.search(r"""['"]([^'"]+\.php(?:\.php)?)['"]""", include_stmt, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def resolver_includes(arquivo_origem: str, includes: List[str], raiz_projeto: str) -> List[Dict]:
    """
    Resolve includes/require a partir do arquivo de origem e da raiz do projeto.
    """
    resultados = []
    origem = Path(arquivo_origem)
    raiz = Path(raiz_projeto)

    for item in includes:
        caminho_rel = extrair_caminho_include(item)

        resultado = {
            "instrucao": item,
            "caminho_relativo": caminho_rel,
            "caminho_resolvido": "",
            "existe": False,
            "linhas": 0,
            "tamanho_bytes": 0,
        }

        if not caminho_rel:
            resultados.append(resultado)
            continue

        candidato_raiz = raiz / caminho_rel
        candidato_relativo = origem.parent / caminho_rel

        alvo = None
        if candidato_raiz.exists():
            alvo = candidato_raiz
        elif candidato_relativo.exists():
            alvo = candidato_relativo

        if alvo and alvo.exists():
            resultado["caminho_resolvido"] = str(alvo.resolve())
            resultado["existe"] = True

            try:
                texto = alvo.read_text(encoding="utf-8", errors="ignore")
                resultado["linhas"] = len(texto.splitlines())
            except Exception:
                resultado["linhas"] = 0

            try:
                resultado["tamanho_bytes"] = alvo.stat().st_size
            except Exception:
                resultado["tamanho_bytes"] = 0

        else:
            resultado["caminho_resolvido"] = str(candidato_raiz)

        resultados.append(resultado)

    return resultados