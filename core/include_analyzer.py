import re
from pathlib import Path
from typing import Dict, List, Optional


SUPERGLOBAIS = [
    "$_REQUEST",
    "$_GET",
    "$_POST",
    "$_SESSION",
    "$_FILES",
    "$_SERVER",
    "$_COOKIE",
]


SQL_PATTERNS = [
    ("select_from", re.compile(r"\bselect\b[\s\S]{0,500}?\bfrom\b", re.IGNORECASE)),
    ("insert_into", re.compile(r"\binsert\s+into\b", re.IGNORECASE)),
    ("update_set", re.compile(r"\bupdate\b[\s\S]{0,300}?\bset\b", re.IGNORECASE)),
    ("delete_from", re.compile(r"\bdelete\s+from\b", re.IGNORECASE)),
    ("exec", re.compile(r"\bexec(?:ute)?\b\s+[a-zA-Z_][\w\.]*", re.IGNORECASE)),
    ("call", re.compile(r"\bcall\b\s+[a-zA-Z_][\w\.]*", re.IGNORECASE)),
    ("with_select", re.compile(r"\bwith\b[\s\S]{0,500}?\bas\b[\s\S]{0,500}?\bselect\b", re.IGNORECASE)),
]


def linha_parece_html(linha: str) -> bool:
    s = (linha or "").strip().lower()

    if not s:
        return False

    # tags HTML comuns
    if re.match(r"^</?[a-z][a-z0-9:_-]*\b", s):
        return True

    # linha contendo tag + atributos comuns de HTML
    if "<" in s and ">" in s:
        attrs_html = [
            " id=", " class=", " style=", " name=", " value=", " type=",
            " onclick=", " onchange=", " onsubmit=", " onblur=", " onkeyup=",
            " href=", " src=", " selected", " checked", " disabled",
        ]
        if any(attr in s for attr in attrs_html):
            return True

    # falsos positivos clássicos
    if (
        s.startswith("<select")
        or s.startswith("<option")
        or s.startswith("<input")
        or s.startswith("<form")
        or s.startswith("<div")
        or s.startswith("<span")
        or s.startswith("<table")
        or s.startswith("<tr")
        or s.startswith("<td")
        or s.startswith("<label")
        or s.startswith("<script")
        or s.startswith("<link")
    ):
        return True

    return False


def linha_parece_css_ou_fragmento_visual(linha: str) -> bool:
    s = (linha or "").strip()

    if not s:
        return False

    s_lower = s.lower()

    # blocos simples de CSS
    if s.endswith("{") or s == "}" or s.startswith(".") or s.startswith("#"):
        return True

    css_props = [
        "color:", "background:", "display:", "margin:", "padding:",
        "font-size:", "font-family:", "border:", "width:", "height:",
        "position:", "top:", "left:", "right:", "bottom:",
        "transform:", "transition:", "z-index:", "overflow:",
        "text-align:", "vertical-align:", "float:", "clear:",
    ]
    if any(prop in s_lower for prop in css_props):
        return True

    # evita "from {" ou coisas parecidas
    if re.search(r"\bfrom\s*\{", s_lower):
        return True

    return False


def linha_parece_javascript_ui(linha: str) -> bool:
    s = (linha or "").strip().lower()

    if not s:
        return False

    sinais_js_ui = [
        "$(",
        "document.getelementbyid",
        "document.queryselector",
        "document.queryselectorall",
        ".addeventlistener(",
        ".onclick",
        ".onchange",
        ".onsubmit",
        ".onblur",
        ".onkeyup",
        "function(",
        "=>",
        "fetch(",
        "$.ajax(",
        "$.get(",
        "$.post(",
        "xmlhttprequest",
    ]

    return any(item in s for item in sinais_js_ui)


def normalizar_trecho_sql(linha: str) -> str:
    return re.sub(r"\s+", " ", (linha or "").strip())


def detectar_tipo_sql(linha: str) -> Optional[str]:
    s = linha or ""
    for nome, pattern in SQL_PATTERNS:
        if pattern.search(s):
            return nome
    return None


def linha_parece_sql(linha: str) -> bool:
    s = (linha or "").strip()

    if not s:
        return False

    # ignora contextos claramente não-SQL
    if linha_parece_html(s):
        return False

    if linha_parece_css_ou_fragmento_visual(s):
        return False

    # evita falsos positivos explícitos
    s_lower = s.lower()
    if "<select" in s_lower or "</select>" in s_lower:
        return False

    # JS de interface só entra se tiver padrão SQL forte
    if linha_parece_javascript_ui(s):
        return detectar_tipo_sql(s) is not None

    # exige estrutura mínima de SQL
    return detectar_tipo_sql(s) is not None


def extrair_sql_suspeito_detalhado(texto: str, limite: int = 50) -> List[Dict]:
    encontrados: List[Dict] = []
    vistos = set()

    for num_linha, linha in enumerate((texto or "").splitlines(), start=1):
        if linha_parece_sql(linha):
            trecho = normalizar_trecho_sql(linha)
            tipo = detectar_tipo_sql(linha)

            chave = (tipo, trecho)
            if trecho and chave not in vistos:
                encontrados.append({
                    "linha": num_linha,
                    "tipo": tipo,
                    "trecho": trecho,
                })
                vistos.add(chave)

            if len(encontrados) >= limite:
                break

    return encontrados


def extrair_sql_suspeito(texto: str, limite: int = 50) -> List[str]:
    encontrados: List[str] = []
    vistos = set()

    for linha in (texto or "").splitlines():
        if linha_parece_sql(linha):
            trecho = normalizar_trecho_sql(linha)

            if trecho and trecho not in vistos:
                encontrados.append(trecho)
                vistos.add(trecho)

            if len(encontrados) >= limite:
                break

    return encontrados


def extrair_caminho_include(include_stmt: str) -> Optional[str]:
    """
    Extrai o caminho do include a partir de expressões como:
    include_once "controle/PropostaMetaReg/programa_objetivo.php";
    require 'controle/x/y.php';
    include("controle/a.php");
    """
    match = re.search(
        r"""(?:include|include_once|require|require_once)\s*(?:\(\s*)?["']([^"']+\.php)["']""",
        include_stmt,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip()


def resolver_caminho_include(project_path: str, include_path: str) -> Path:
    """
    Resolve o caminho do include em relação à raiz do projeto.
    """
    return (Path(project_path) / include_path).resolve()


def detectar_ajax_embutido(content: str) -> Dict:
    ajax_patterns = {
        "$.ajax": r"""\$\s*\.ajax\s*\(""",
        "jQuery.ajax": r"""jQuery\s*\.ajax\s*\(""",
        "$.get": r"""\$\s*\.get\s*\(""",
        "$.post": r"""\$\s*\.post\s*\(""",
        "fetch": r"""\bfetch\s*\(""",
        "XMLHttpRequest": r"""\bXMLHttpRequest\b""",
    }

    ajax_types: Dict[str, int] = {}
    ajax_total = 0

    for nome, pattern in ajax_patterns.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            ajax_types[nome] = len(matches)
            ajax_total += len(matches)

    endpoints = set()

    for m in re.finditer(
        r"""action=([A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)""",
        content,
    ):
        endpoints.add(m.group(1))

    for m in re.finditer(
        r"""url\s*:\s*["']([^"']+)["']""",
        content,
        re.IGNORECASE,
    ):
        endpoints.add(m.group(1).strip())

    for m in re.finditer(
        r"""\$\s*\.\s*(?:get|post)\s*\(\s*["']([^"']+)["']""",
        content,
        re.IGNORECASE,
    ):
        endpoints.add(m.group(1).strip())

    for m in re.finditer(
        r"""\bfetch\s*\(\s*["']([^"']+)["']""",
        content,
        re.IGNORECASE,
    ):
        endpoints.add(m.group(1).strip())

    script_blocks = re.findall(
        r"""<script\b[^>]*>(.*?)</script>""",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    return {
        "has_ajax": ajax_total > 0,
        "ajax_total": ajax_total,
        "ajax_types": ajax_types,
        "endpoints": sorted(endpoints),
        "inline_script_blocks": len(script_blocks),
    }


def analisar_arquivo_include(file_path: Path) -> Optional[Dict]:
    """
    Analisa um arquivo PHP incluído.
    """
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    linhas = content.splitlines()

    includes = re.findall(
        r"""\b(?:include|include_once|require|require_once)\b\s*(?:\(\s*)?["'][^"']+["']""",
        content,
        re.IGNORECASE,
    )

    superglobais = [sg for sg in SUPERGLOBAIS if sg in content]

    sql_suspeito = extrair_sql_suspeito(content)
    sql_suspeito_detalhado = extrair_sql_suspeito_detalhado(content)

    actions = sorted(
        set(
            re.findall(
                r"""action=([A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)""",
                content,
            )
        )
    )

    funcoes = sorted(
        set(
            re.findall(
                r"""\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(""",
                content,
                re.IGNORECASE,
            )
        )
    )

    classes = sorted(
        set(
            re.findall(
                r"""\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b""",
                content,
                re.IGNORECASE,
            )
        )
    )

    scripts = re.findall(
        r"""<script\b[^>]*src=["']([^"']+)["']""",
        content,
        re.IGNORECASE,
    )

    css_links = re.findall(
        r"""<link\b[^>]*href=["']([^"']+)["']""",
        content,
        re.IGNORECASE,
    )

    html_tags_count = len(
        re.findall(r"""<([a-zA-Z][a-zA-Z0-9]*)\b""", content)
    )

    ajax = detectar_ajax_embutido(content)

    return {
        "arquivo": str(file_path),
        "linhas": len(linhas),
        "includes": includes,
        "superglobais": superglobais,
        "sql_suspeito": sql_suspeito,
        "sql_suspeito_detalhado": sql_suspeito_detalhado,
        "actions": actions,
        "funcoes": funcoes,
        "classes": classes,
        "scripts": scripts,
        "css_links": css_links,
        "html_tags_count": html_tags_count,
        "ajax": ajax,
        "conteudo": content,
    }


def render_markdown_include(resultado: Dict, origem_metodo: str = "") -> str:
    md: List[str] = []

    md.append(f"# Análise de Include — {resultado['arquivo']}")
    md.append("")

    if origem_metodo:
        md.append(f"**Origem:** `{origem_metodo}`  ")
        md.append("")

    md.append("## Estatísticas")
    md.append(f"- Linhas: {resultado['linhas']}")
    md.append(f"- Includes internos: {len(resultado['includes'])}")
    md.append(
        f"- Superglobais usadas: "
        f"{', '.join(resultado['superglobais']) if resultado['superglobais'] else 'nenhuma'}"
    )
    md.append(f"- SQL suspeito: {len(resultado['sql_suspeito'])}")
    md.append(f"- Actions encontradas: {len(resultado['actions'])}")
    md.append(f"- Funções declaradas: {len(resultado['funcoes'])}")
    md.append(f"- Classes declaradas: {len(resultado['classes'])}")
    md.append(f"- Tags HTML detectadas: {resultado['html_tags_count']}")
    md.append("")

    md.append("## AJAX detectado")
    ajax = resultado.get("ajax", {}) or {}

    if ajax.get("has_ajax"):
        md.append(f"- Quantidade de ocorrências: {ajax.get('ajax_total', 0)}")

        ajax_types = ajax.get("ajax_types", {})
        if ajax_types:
            md.append("- Tipos encontrados:")
            for nome, qtd in ajax_types.items():
                md.append(f"  - `{nome}`: {qtd}")

        endpoints = ajax.get("endpoints", [])
        if endpoints:
            md.append("")
            md.append("### Endpoints/URLs encontrados")
            for item in endpoints:
                md.append(f"- `{item}`")

        md.append("")
        md.append(f"- Blocos de script inline: {ajax.get('inline_script_blocks', 0)}")
    else:
        md.append("- Nenhum AJAX embutido detectado.")

    md.append("")
    md.append("## Includes internos")
    if resultado["includes"]:
        for item in resultado["includes"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhum include interno encontrado.")

    md.append("")
    md.append("## Actions")
    if resultado["actions"]:
        for item in resultado["actions"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhuma action encontrada.")

    md.append("")
    md.append("## SQL suspeito")
    if resultado["sql_suspeito"]:
        for item in resultado["sql_suspeito"][:20]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhum trecho SQL suspeito encontrado.")

    # seção extra detalhada sem quebrar compatibilidade
    sql_detalhado = resultado.get("sql_suspeito_detalhado", [])
    if sql_detalhado:
        md.append("")
        md.append("### SQL suspeito detalhado")
        for item in sql_detalhado[:20]:
            linha = item.get("linha", "?")
            tipo = item.get("tipo", "desconhecido")
            trecho = item.get("trecho", "")
            md.append(f"- Linha {linha} — `{tipo}` — `{trecho}`")

    md.append("")
    md.append("## Scripts referenciados")
    if resultado["scripts"]:
        for item in resultado["scripts"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhum script externo encontrado.")

    md.append("")
    md.append("## CSS referenciados")
    if resultado["css_links"]:
        for item in resultado["css_links"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhum CSS externo encontrado.")

    md.append("")
    md.append("## Funções declaradas")
    if resultado["funcoes"]:
        for item in resultado["funcoes"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhuma função declarada.")

    md.append("")
    md.append("## Classes declaradas")
    if resultado["classes"]:
        for item in resultado["classes"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhuma classe declarada.")

    md.append("")
    return "\n".join(md)