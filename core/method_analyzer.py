import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from core.sql_extractor import extrair_queries_completas


SUPERGLOBAIS = ["$_REQUEST", "$_GET", "$_POST", "$_SESSION", "$_FILES", "$_SERVER", "$_COOKIE"]

METODOS_RUIDOSOS = {
    "prepare",
    "bindvalue",
    "execute",
    "fetch",
    "fetchall",
    "query",
    "closecursor",
}


def localizar_metodo_em_arquivo(arquivo: Path, nome_metodo: str) -> Optional[Tuple[int, int, str, List[str]]]:
    """
    Localiza um método por nome em um arquivo PHP e retorna:
    - linha inicial
    - linha final
    - bloco completo do método
    - linhas do arquivo
    """
    try:
        linhas = arquivo.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None

    padrao = re.compile(
        rf"^\s*(public|protected|private)?\s*function\s+{re.escape(nome_metodo)}\s*\(",
        re.IGNORECASE
    )

    linha_inicio = None
    for i, linha in enumerate(linhas):
        if padrao.search(linha):
            linha_inicio = i
            break

    if linha_inicio is None:
        return None

    abertura_idx = None
    for i in range(linha_inicio, len(linhas)):
        if "{" in linhas[i]:
            abertura_idx = i
            break

    if abertura_idx is None:
        return None

    nivel = 0
    linha_fim = None
    encontrou_primeira_abertura = False

    for i in range(abertura_idx, len(linhas)):
        linha = linhas[i]

        for ch in linha:
            if ch == "{":
                nivel += 1
                encontrou_primeira_abertura = True
            elif ch == "}":
                nivel -= 1

            if encontrou_primeira_abertura and nivel == 0:
                linha_fim = i
                break

        if linha_fim is not None:
            break

    if linha_fim is None:
        return None

    bloco = "\n".join(linhas[linha_inicio:linha_fim + 1])

    return linha_inicio + 1, linha_fim + 1, bloco, linhas


def extrair_assinatura(bloco: str) -> str:
    m = re.search(
        r"^\s*((public|protected|private)?\s*function\s+\w+\s*\(.*?\))",
        bloco,
        re.IGNORECASE | re.MULTILINE
    )
    return m.group(1).strip() if m else ""


def extrair_parametros(assinatura: str) -> List[str]:
    m = re.search(r"\((.*)\)", assinatura, re.DOTALL)
    if not m:
        return []

    conteudo = m.group(1).strip()
    if not conteudo:
        return []

    params = [p.strip() for p in conteudo.split(",")]
    return [p for p in params if p]


def extrair_superglobais(bloco: str) -> List[str]:
    encontrados = []
    for item in SUPERGLOBAIS:
        if item in bloco:
            encontrados.append(item)
    return encontrados


def extrair_instanciacoes(bloco: str) -> List[Dict]:
    """
    Encontra padrões como:
    $oFachada = new FachadaBD();
    """
    padrao = re.compile(
        r"(?P<variavel>\$\w+)\s*=\s*new\s+(?P<classe>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
        re.IGNORECASE
    )

    resultados = []
    for m in padrao.finditer(bloco):
        resultados.append({
            "variavel": m.group("variavel"),
            "classe": m.group("classe")
        })

    return resultados


def extrair_chamadas_metodos(bloco: str) -> List[Dict]:
    """
    Encontra padrões como:
    $oFachada->recuperarAlgo(...)
    """
    padrao = re.compile(
        r"(?P<objeto>\$\w+)\s*->\s*(?P<metodo>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
        re.IGNORECASE
    )

    resultados = []
    vistos = set()

    for m in padrao.finditer(bloco):
        chave = (m.group("objeto"), m.group("metodo"))
        if chave in vistos:
            continue
        vistos.add(chave)

        resultados.append({
            "objeto": m.group("objeto"),
            "metodo": m.group("metodo")
        })

    return resultados


def filtrar_chamadas_ruidosas(chamadas: List[Dict]) -> List[Dict]:
    """
    Remove chamadas muito genéricas/técnicas que costumam poluir a análise.
    """
    resultado = []

    for ch in chamadas:
        metodo = ch.get("metodo", "").strip().lower()
        objeto = ch.get("objeto", "").strip().lower()

        if metodo in METODOS_RUIDOSOS and objeto in {"$stm", "$stmt", "$conn", "$pdo"}:
            continue

        resultado.append(ch)

    return resultado


def extrair_includes_requires(bloco: str) -> List[str]:
    padrao = re.compile(
        r"\b(include|include_once|require|require_once)\b\s*(\(|)\s*([^\n;]+)",
        re.IGNORECASE
    )

    resultados = []
    for m in padrao.finditer(bloco):
        resultados.append(m.group(0).strip())

    return resultados


def extrair_actions(bloco: str) -> List[str]:
    """
    Procura actions reais do padrão Classe.metodo.
    Evita confundir schema.tabela com action.
    """
    resultados = set()

    for m in re.finditer(
        r"action=([A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)",
        bloco
    ):
        resultados.add(m.group(1))

    for m in re.finditer(
        r"""['"]([A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)['"]""",
        bloco
    ):
        resultados.add(m.group(1))

    return sorted(resultados)


def extrair_sql_suspeito(bloco: str) -> List[str]:
    """
    Extrai linhas suspeitas de SQL.
    """
    palavras = ("select ", "insert ", "update ", "delete ", "from ", "join ", "exec ", "where ")
    resultados = []

    for linha in bloco.splitlines():
        linha_limpa = linha.strip()
        linha_lower = linha_limpa.lower()

        if any(p in linha_lower for p in palavras):
            resultados.append(linha_limpa)

    return resultados


def extrair_tabelas_e_procedures(bloco: str) -> Dict[str, List[str]]:
    tabelas = set()
    procedures = set()

    for m in re.finditer(r"\b(from|join|update|into)\s+([A-Za-z0-9_\.\[\]]+)", bloco, re.IGNORECASE):
        tabelas.add(m.group(2))

    for m in re.finditer(r"\bexec(?:ute)?\s+([A-Za-z0-9_\.\[\]]+)", bloco, re.IGNORECASE):
        procedures.add(m.group(1))

    return {
        "tabelas": sorted(tabelas),
        "procedures": sorted(procedures)
    }


def mapear_objetos_para_classes(instanciacoes: List[Dict]) -> Dict[str, str]:
    return {item["variavel"]: item["classe"] for item in instanciacoes}


def analisar_metodo_em_arquivo(arquivo: Path, nome_metodo: str) -> Optional[Dict]:
    localizado = localizar_metodo_em_arquivo(arquivo, nome_metodo)
    if not localizado:
        return None

    linha_inicio, linha_fim, bloco, linhas_arquivo = localizado

    assinatura = extrair_assinatura(bloco)
    parametros = extrair_parametros(assinatura)
    superglobais = extrair_superglobais(bloco)
    instanciacoes = extrair_instanciacoes(bloco)

    chamadas = extrair_chamadas_metodos(bloco)
    chamadas = filtrar_chamadas_ruidosas(chamadas)

    includes = extrair_includes_requires(bloco)
    actions = extrair_actions(bloco)
    sql_suspeito = extrair_sql_suspeito(bloco)
    banco = extrair_tabelas_e_procedures(bloco)
    mapa_objetos = mapear_objetos_para_classes(instanciacoes)
    queries_completas = extrair_queries_completas(bloco)

    chamadas_resolvidas = []
    for ch in chamadas:
        chamadas_resolvidas.append({
            "objeto": ch["objeto"],
            "classe": mapa_objetos.get(ch["objeto"], ""),
            "metodo": ch["metodo"]
        })

    total_linhas = max(0, linha_fim - linha_inicio + 1)
    total_queries = len(queries_completas)
    total_chamadas = len(chamadas_resolvidas)
    total_includes = len(includes)

    return {
        "arquivo": str(arquivo),
        "linha_inicio": linha_inicio,
        "linha_fim": linha_fim,
        "assinatura": assinatura,
        "parametros": parametros,
        "superglobais": superglobais,
        "instanciacoes": instanciacoes,
        "chamadas": chamadas_resolvidas,
        "includes": includes,
        "actions": actions,
        "sql_suspeito": sql_suspeito,
        "queries_completas": queries_completas,
        "tabelas": banco["tabelas"],
        "procedures": banco["procedures"],
        "bloco": bloco,
        "codigo": bloco,
        "conteudo": bloco,
        "linhas_arquivo": linhas_arquivo,
        "estatisticas": {
            "total_linhas_metodo": total_linhas,
            "total_parametros": len(parametros),
            "total_superglobais": len(superglobais),
            "total_instanciacoes": len(instanciacoes),
            "total_chamadas": total_chamadas,
            "total_includes": total_includes,
            "total_actions": len(actions),
            "total_tabelas": len(banco["tabelas"]),
            "total_procedures": len(banco["procedures"]),
            "total_queries_completas": total_queries,
            "total_sql_suspeito": len(sql_suspeito),
        }
    }