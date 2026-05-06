import re
from typing import Dict, List


SQL_KEYWORDS = ("select", "insert", "update", "delete", "exec", "with")
SQL_EXEC_METHODS = ("executarquery", "prepare", "query", "exec")


def _normalizar_sql(texto: str) -> str:

    # remove interpolação PHP {$var}
    texto = re.sub(r"\{\$\w+\}", ":var", texto)

    # remove chaves soltas comuns em concatenação
    texto = texto.replace("{", "").replace("}", "")

    linhas = [linha.strip() for linha in texto.splitlines()]
    linhas = [linha for linha in linhas if linha]

    return "\n".join(linhas).strip()


def _parece_sql(texto: str) -> bool:
    inicio = texto.strip().lower()
    return any(inicio.startswith(k) for k in SQL_KEYWORDS)


def extrair_sql_de_variaveis(bloco: str) -> List[Dict]:
    """
    Extrai SQLs atribuídas a variáveis e concatenações simples.

    Exemplos:
      $sql = "SELECT ...";
      $sql .= " FROM ...";
      $sql .= " WHERE ...";
    """
    resultados = []
    acumuladas = {}

    padrao_atribuicao = re.compile(
        r'(?P<var>\$\w+)\s*=\s*"(?P<sql>.*?)"\s*;',
        re.IGNORECASE | re.DOTALL
    )

    padrao_concat = re.compile(
        r'(?P<var>\$\w+)\s*\.\=\s*"(?P<sql>.*?)"\s*;',
        re.IGNORECASE | re.DOTALL
    )

    for m in padrao_atribuicao.finditer(bloco):
        var = m.group("var")
        sql = _normalizar_sql(m.group("sql"))

        if _parece_sql(sql):
            acumuladas[var] = sql

    for m in padrao_concat.finditer(bloco):
        var = m.group("var")
        sql = _normalizar_sql(m.group("sql"))

        if var in acumuladas:
            acumuladas[var] += "\n" + sql

    for var, sql in acumuladas.items():
        resultados.append({
            "tipo": "variavel",
            "variavel": var,
            "sql": _normalizar_sql(sql)
        })

    return resultados


def extrair_sql_direto_em_chamadas(bloco: str) -> List[Dict]:
    """
    Extrai SQL passada diretamente em chamadas como:
      executarQuery("SELECT ...")
      prepare("SELECT ...")
    """
    resultados = []

    padrao = re.compile(
        r'(?P<metodo>\w+)\s*\(\s*"(?P<sql>(?:[^"\\]|\\.)*?)"\s*\)',
        re.IGNORECASE | re.DOTALL
    )

    for m in padrao.finditer(bloco):
        metodo = m.group("metodo")
        sql = _normalizar_sql(m.group("sql"))

        if metodo.lower() in SQL_EXEC_METHODS and _parece_sql(sql):
            resultados.append({
                "tipo": "direto",
                "metodo": metodo,
                "sql": sql
            })

    return resultados


def extrair_uso_de_variavel_sql_em_chamadas(bloco: str, sqls_variaveis: List[Dict]) -> List[Dict]:
    """
    Detecta uso posterior de variáveis SQL em chamadas como:
      executarQuery($sql)
      prepare($sql)
    """
    resultados = []
    mapa_sql = {item["variavel"]: item["sql"] for item in sqls_variaveis if item.get("variavel")}

    padrao_objeto = re.compile(
        r'(?P<objeto>\$\w+)\s*->\s*(?P<metodo>\w+)\s*\(\s*(?P<arg>\$\w+)\s*\)',
        re.IGNORECASE
    )

    padrao_funcao = re.compile(
        r'(?P<metodo>\w+)\s*\(\s*(?P<arg>\$\w+)\s*\)',
        re.IGNORECASE
    )

    for m in padrao_objeto.finditer(bloco):
        metodo = m.group("metodo")
        arg = m.group("arg")

        if metodo.lower() in SQL_EXEC_METHODS and arg in mapa_sql:
            resultados.append({
                "tipo": "variavel_em_chamada",
                "metodo": metodo,
                "variavel": arg,
                "sql": mapa_sql[arg]
            })

    for m in padrao_funcao.finditer(bloco):
        metodo = m.group("metodo")
        arg = m.group("arg")

        if metodo.lower() in SQL_EXEC_METHODS and arg in mapa_sql:
            resultados.append({
                "tipo": "variavel_em_chamada",
                "metodo": metodo,
                "variavel": arg,
                "sql": mapa_sql[arg]
            })

    return resultados


def extrair_queries_completas(bloco: str) -> List[Dict]:
    """
    Extrai e consolida queries encontradas no bloco.
    """
    resultados = []

    sqls_variaveis = extrair_sql_de_variaveis(bloco)
    sqls_diretos = extrair_sql_direto_em_chamadas(bloco)
    sqls_em_chamadas = extrair_uso_de_variavel_sql_em_chamadas(bloco, sqls_variaveis)

    resultados.extend(sqls_variaveis)
    resultados.extend(sqls_diretos)
    resultados.extend(sqls_em_chamadas)

    vistos = set()
    unicos = []

    for item in resultados:
        chave = (
            item.get("tipo", ""),
            item.get("variavel", ""),
            item.get("metodo", ""),
            item.get("sql", "")
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(item)

    return unicos