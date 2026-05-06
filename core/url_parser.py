from typing import Dict, List
from urllib.parse import urlparse, parse_qsl, unquote


def _extrair_query_util(entrada: str) -> str:
    """
    Aceita:
    - URL completa
    - query string pura
    - URL malformada com action duplicado
    """
    texto = entrada.strip()

    # decodifica %xx se houver
    texto = unquote(texto)

    # se já vier só a query
    if texto.startswith("action="):
        return texto

    # tenta parsear como URL
    parsed = urlparse(texto)
    query = parsed.query

    if query:
        # caso normal
        if "action=" in query:
            # se action veio contaminado com outra URL dentro, pegamos a última ocorrência útil
            idx = query.rfind("action=")
            return query[idx:]
        return query

    # fallback: procurar manualmente
    idx = texto.rfind("action=")
    if idx >= 0:
        return texto[idx:]

    return texto


def parse_sigplan_url(entrada: str) -> Dict:
    """
    Extrai:
    - action bruta
    - classe
    - método
    - parâmetros
    """
    query = _extrair_query_util(entrada)

    pares = parse_qsl(query, keep_blank_values=True)

    action_bruta = ""
    parametros = []

    for k, v in pares:
        if k == "action" and not action_bruta:
            action_bruta = v
        else:
            parametros.append({"chave": k, "valor": v})

    # Se action vier contaminada com outra URL/query, tenta recuperar a última action válida
    if "action=" in action_bruta:
        action_bruta = _extrair_query_util(action_bruta)
        subpares = parse_qsl(action_bruta, keep_blank_values=True)
        nova_action = ""
        novos_parametros = []

        for k, v in subpares:
            if k == "action" and not nova_action:
                nova_action = v
            else:
                novos_parametros.append({"chave": k, "valor": v})

        if nova_action:
            action_bruta = nova_action
            parametros = novos_parametros + parametros

    classe = ""
    metodo = ""

    if "." in action_bruta:
        partes = action_bruta.split(".", 1)
        classe = partes[0].strip()
        metodo = partes[1].strip()
    else:
        metodo = action_bruta.strip()

    # remove duplicados mantendo ordem
    vistos = set()
    parametros_unicos: List[Dict] = []
    for p in parametros:
        chave = (p["chave"], p["valor"])
        if chave in vistos:
            continue
        vistos.add(chave)
        parametros_unicos.append(p)

    observacoes = []

    if not classe and metodo:
        observacoes.append("A action não parece estar no formato Classe.metodo.")

    if "http://" in entrada or "https://" in entrada:
        if entrada.count("action=") > 1:
            observacoes.append("A URL parecia duplicada ou malformada; foi feita limpeza automática.")

    return {
        "query_limpa": query,
        "action_bruta": action_bruta,
        "classe": classe,
        "metodo": metodo,
        "parametros": parametros_unicos,
        "observacoes": observacoes,
    }