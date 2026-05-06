import re
from pathlib import Path
from typing import Dict, List, Optional


AJAX_PATTERNS = {
    "$.ajax": r"""\$\s*\.ajax\s*\(""",
    "jQuery.ajax": r"""jQuery\s*\.ajax\s*\(""",
    "$.get": r"""\$\s*\.get\s*\(""",
    "$.post": r"""\$\s*\.post\s*\(""",
    "fetch": r"""\bfetch\s*\(""",
    "XMLHttpRequest": r"""\bXMLHttpRequest\b""",
}


def extrair_blocos_script(content: str) -> List[Dict]:
    blocos = []
    pattern = re.compile(
        r"""<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>""",
        re.IGNORECASE | re.DOTALL,
    )

    for i, m in enumerate(pattern.finditer(content), start=1):
        attrs = m.group("attrs") or ""
        body = m.group("body") or ""
        start_line = content[:m.start()].count("\n") + 1

        src_match = re.search(r"""src=["']([^"']+)["']""", attrs, re.IGNORECASE)

        blocos.append({
            "index": i,
            "attrs": attrs.strip(),
            "body": body,
            "start_line": start_line,
            "is_external": bool(src_match),
            "src": src_match.group(1).strip() if src_match else None,
        })

    return blocos


def extrair_scripts_externos(content: str) -> List[str]:
    return sorted(set(re.findall(
        r"""<script\b[^>]*src=["']([^"']+)["']""",
        content,
        re.IGNORECASE,
    )))


def extrair_constantes_js(script: str) -> List[Dict]:
    encontrados = []

    for m in re.finditer(
        r"""\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(["'])(.*?)\2\s*;?""",
        script,
        re.IGNORECASE | re.DOTALL,
    ):
        encontrados.append({
            "nome": m.group(1),
            "valor": m.group(3).strip(),
            "tipo": "string",
        })

    for m in re.finditer(
        r"""\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*([^;]+);""",
        script,
        re.IGNORECASE,
    ):
        nome = m.group(1)
        valor = m.group(2).strip()

        if not any(x["nome"] == nome for x in encontrados):
            encontrados.append({
                "nome": nome,
                "valor": valor,
                "tipo": "expression",
            })

    return encontrados


def extrair_funcoes_js_com_corpo(script: str) -> List[Dict]:
    funcoes = []

    # function nome(...) { ... }
    pattern = re.compile(
        r"""\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\((.*?)\)\s*\{""",
        re.IGNORECASE | re.DOTALL,
    )

    for m in pattern.finditer(script):
        nome = m.group(1)
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        inicio_bloco = m.end() - 1

        corpo = extrair_bloco_chaves(script, inicio_bloco)
        linha = script[:m.start()].count("\n") + 1

        funcoes.append({
            "nome": nome,
            "params": params,
            "linha": linha,
            "corpo": corpo.strip(),
        })

    return funcoes


def extrair_bloco_chaves(texto: str, idx_abertura: int) -> str:
    if idx_abertura < 0 or idx_abertura >= len(texto) or texto[idx_abertura] != "{":
        return ""

    nivel = 0
    inicio = idx_abertura + 1

    for i in range(idx_abertura, len(texto)):
        c = texto[i]
        if c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio:i]

    return ""


def extrair_eventos_inline_html(content: str) -> List[Dict]:
    eventos = []

    tag_pattern = re.compile(r"""<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>""", re.IGNORECASE)
    attr_pattern = re.compile(r"""(on[a-z]+)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

    for tag_match in tag_pattern.finditer(content):
        tag = tag_match.group(1)
        attrs = tag_match.group(2)

        for attr_match in attr_pattern.finditer(attrs):
            evento = attr_match.group(1).lower()
            handler = attr_match.group(2).strip()
            eventos.append({
                "tag": tag,
                "evento": evento,
                "handler": handler,
            })

    return eventos


def extrair_eventos_jquery(script: str) -> List[Dict]:
    eventos = []

    # $(document).on("click", ".classe", function(e) { ... })
    pattern = re.compile(
        r"""\$\s*\(\s*([^)]+)\s*\)\s*\.\s*on\s*\(\s*["']([a-zA-Z]+)["']\s*,\s*["']([^"']+)["']\s*,\s*function\s*\((.*?)\)\s*\{""",
        re.IGNORECASE | re.DOTALL,
    )

    for m in pattern.finditer(script):
        alvo = m.group(1).strip()
        evento = m.group(2).strip().lower()
        seletor = m.group(3).strip()
        params = [p.strip() for p in m.group(4).split(",") if p.strip()]
        inicio_bloco = m.end() - 1
        corpo = extrair_bloco_chaves(script, inicio_bloco)
        linha = script[:m.start()].count("\n") + 1

        eventos.append({
            "tipo": "jquery_on",
            "alvo": alvo,
            "evento": evento,
            "seletor": seletor,
            "params": params,
            "linha": linha,
            "corpo": corpo.strip(),
        })

    return eventos


def extrair_chamadas_ajax_detalhadas(script: str) -> List[Dict]:
    ajax_calls = []

    pattern = re.compile(r"""\$\s*\.ajax\s*\(\s*\{""", re.IGNORECASE)

    for m in pattern.finditer(script):
        linha = script[:m.start()].count("\n") + 1
        obj = extrair_objeto_js(script, m.end() - 1)

        url = extrair_campo_objeto_js(obj, "url")
        method = extrair_campo_objeto_js(obj, "method") or extrair_campo_objeto_js(obj, "type")
        timeout = extrair_campo_objeto_js(obj, "timeout")
        process_data = extrair_campo_objeto_js(obj, "processData")
        content_type = extrair_campo_objeto_js(obj, "contentType")
        data = extrair_campo_objeto_js(obj, "data")

        ajax_calls.append({
            "tipo": "$.ajax",
            "linha": linha,
            "url": url,
            "method": method,
            "timeout": timeout,
            "processData": process_data,
            "contentType": content_type,
            "data": data,
            "raw": obj.strip(),
        })

    return ajax_calls


def extrair_objeto_js(texto: str, idx_abertura: int) -> str:
    if idx_abertura < 0 or idx_abertura >= len(texto) or texto[idx_abertura] != "{":
        return ""

    nivel = 0
    inicio = idx_abertura

    for i in range(idx_abertura, len(texto)):
        c = texto[i]
        if c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio:i + 1]

    return ""


def extrair_campo_objeto_js(obj: str, campo: str) -> Optional[str]:
    if not obj:
        return None

    # string literal
    m = re.search(
        rf"""\b{re.escape(campo)}\s*:\s*(["'])(.*?)\1""",
        obj,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(2).strip()

    # valor simples
    m = re.search(
        rf"""\b{re.escape(campo)}\s*:\s*([^,\n}}]+)""",
        obj,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    return None


def extrair_formdatas(script: str) -> List[Dict]:
    encontrados = []

    for m in re.finditer(
        r"""\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*new\s+FormData\s*\(\s*\)""",
        script,
        re.IGNORECASE,
    ):
        var_name = m.group(1)
        linha = script[:m.start()].count("\n") + 1

        appends = []
        for a in re.finditer(
            rf"""{re.escape(var_name)}\s*\.\s*append\s*\(\s*(["'])(.*?)\1\s*,\s*(.*?)\)\s*;""",
            script,
            re.IGNORECASE | re.DOTALL,
        ):
            appends.append({
                "campo": a.group(2).strip(),
                "valor": re.sub(r"\s+", " ", a.group(3).strip()),
            })

        encontrados.append({
            "variavel": var_name,
            "linha": linha,
            "append_count": len(appends),
            "campos": appends,
        })

    return encontrados


def extrair_seletores_jquery(script: str) -> List[str]:
    seletores = set()

    for m in re.finditer(
        r"""\$\s*\(\s*(["'])(.*?)\1\s*\)""",
        script,
        re.IGNORECASE | re.DOTALL,
    ):
        valor = m.group(2).strip()
        if valor:
            seletores.add(valor)

    return sorted(seletores)


def extrair_swal_calls(script: str) -> List[Dict]:
    encontrados = []

    for m in re.finditer(r"""\bSwal\s*\.\s*fire\s*\(\s*\{""", script, re.IGNORECASE):
        linha = script[:m.start()].count("\n") + 1
        obj = extrair_objeto_js(script, m.end() - 1)

        encontrados.append({
            "linha": linha,
            "title": extrair_campo_objeto_js(obj, "title"),
            "text": extrair_campo_objeto_js(obj, "text"),
            "icon": extrair_campo_objeto_js(obj, "icon"),
            "raw": obj.strip(),
        })

    return encontrados


def extrair_console_calls(script: str) -> List[Dict]:
    encontrados = []

    for m in re.finditer(
        r"""\bconsole\.(log|error|warn|info)\s*\((.*?)\)\s*;""",
        script,
        re.IGNORECASE | re.DOTALL,
    ):
        linha = script[:m.start()].count("\n") + 1
        encontrados.append({
            "linha": linha,
            "tipo": m.group(1).lower(),
            "conteudo": re.sub(r"\s+", " ", m.group(2).strip()),
        })

    return encontrados


def extrair_callbacks_ajax(script: str) -> List[Dict]:
    callbacks = []

    for m in re.finditer(
        r"""\.(done|fail|always)\s*\(\s*function\s*\((.*?)\)\s*\{""",
        script,
        re.IGNORECASE | re.DOTALL,
    ):
        tipo = m.group(1).lower()
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        linha = script[:m.start()].count("\n") + 1
        corpo = extrair_bloco_chaves(script, m.end() - 1)

        callbacks.append({
            "tipo": tipo,
            "linha": linha,
            "params": params,
            "corpo": corpo.strip(),
        })

    return callbacks


def detectar_ajax_resumido(script: str) -> Dict:
    ajax_types: Dict[str, int] = {}
    ajax_total = 0

    for nome, pattern in AJAX_PATTERNS.items():
        matches = re.findall(pattern, script, re.IGNORECASE)
        if matches:
            ajax_types[nome] = len(matches)
            ajax_total += len(matches)

    endpoints = set()

    for m in re.finditer(
        r"""action=([A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)""",
        script,
    ):
        endpoints.add(m.group(1))

    for m in re.finditer(
        r"""url\s*:\s*["']([^"']+)["']""",
        script,
        re.IGNORECASE,
    ):
        endpoints.add(m.group(1).strip())

    for m in re.finditer(
        r"""\b(?:URL_[A-Za-z0-9_]+)\b""",
        script,
        re.IGNORECASE,
    ):
        endpoints.add(m.group(0).strip())

    return {
        "has_ajax": ajax_total > 0,
        "ajax_total": ajax_total,
        "ajax_types": ajax_types,
        "endpoints": sorted(endpoints),
    }


def resumir_fluxo_script(script: str) -> List[str]:
    passos = []

    if "FormData" in script:
        passos.append("Monta payload com FormData.")

    if "$.ajax" in script:
        passos.append("Envia dados via $.ajax.")

    if ".done(" in script:
        passos.append("Trata resposta de sucesso com callback .done().")

    if ".fail(" in script:
        passos.append("Trata falhas com callback .fail().")

    if "Swal.fire" in script:
        passos.append("Exibe feedback visual com SweetAlert.")

    if "console.log" in script or "console.error" in script:
        passos.append("Registra mensagens de depuração no console.")

    if "$(document).on(" in script:
        passos.append("Usa delegação de eventos com jQuery.")

    return passos


def analisar_bloco_script(bloco: Dict) -> Dict:
    body = bloco.get("body", "")

    return {
        "index": bloco["index"],
        "start_line": bloco["start_line"],
        "is_external": bloco["is_external"],
        "src": bloco["src"],
        "constantes": extrair_constantes_js(body),
        "funcoes": extrair_funcoes_js_com_corpo(body),
        "eventos_jquery": extrair_eventos_jquery(body),
        "ajax_calls": extrair_chamadas_ajax_detalhadas(body),
        "formdatas": extrair_formdatas(body),
        "seletores_jquery": extrair_seletores_jquery(body),
        "swal_calls": extrair_swal_calls(body),
        "console_calls": extrair_console_calls(body),
        "callbacks_ajax": extrair_callbacks_ajax(body),
        "ajax_resumo": detectar_ajax_resumido(body),
        "fluxo": resumir_fluxo_script(body),
        "body": body.strip(),
    }


def analisar_include_script(file_path: Path) -> Optional[Dict]:
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    blocos = extrair_blocos_script(content)
    scripts_externos = extrair_scripts_externos(content)
    eventos_inline = extrair_eventos_inline_html(content)

    analises_blocos = []
    funcoes_total = set()
    ajax_total = 0
    ajax_types_total: Dict[str, int] = {}
    endpoints_total = set()

    for bloco in blocos:
        analise = analisar_bloco_script(bloco)
        analises_blocos.append(analise)

        for f in analise["funcoes"]:
            funcoes_total.add(f["nome"])

        ajax_info = analise["ajax_resumo"]
        ajax_total += ajax_info["ajax_total"]

        for nome, qtd in ajax_info["ajax_types"].items():
            ajax_types_total[nome] = ajax_types_total.get(nome, 0) + qtd

        for ep in ajax_info["endpoints"]:
            endpoints_total.add(ep)

        for c in analise["constantes"]:
            valor = c.get("valor")
            if valor and ("action=" in valor or "index.php" in valor):
                endpoints_total.add(valor)

    return {
        "arquivo": str(file_path),
        "linhas": len(content.splitlines()),
        "script_blocks": len([b for b in blocos if not b["is_external"]]),
        "script_blocks_total": len(blocos),
        "scripts_externos": scripts_externos,
        "eventos_inline": eventos_inline,
        "funcoes_js": sorted(funcoes_total),
        "ajax": {
            "has_ajax": ajax_total > 0,
            "ajax_total": ajax_total,
            "ajax_types": ajax_types_total,
            "endpoints": sorted(endpoints_total),
        },
        "blocos_detalhados": analises_blocos,
        "conteudo": content,
    }


def render_markdown_include_script(resultado: Dict, origem: str = "") -> str:
    md: List[str] = []

    md.append(f"# Include Script Analyzer — {resultado['arquivo']}")
    md.append("")

    if origem:
        md.append(f"**Origem:** `{origem}`")
        md.append("")

    md.append("## Estatísticas")
    md.append(f"- Linhas: {resultado['linhas']}")
    md.append(f"- Blocos `<script>` inline: {resultado['script_blocks']}")
    md.append(f"- Blocos `<script>` totais: {resultado['script_blocks_total']}")
    md.append(f"- Scripts externos: {len(resultado['scripts_externos'])}")
    md.append(f"- Eventos inline HTML: {len(resultado['eventos_inline'])}")
    md.append(f"- Funções JavaScript: {len(resultado['funcoes_js'])}")
    md.append(f"- AJAX detectado: {resultado['ajax']['ajax_total']}")
    md.append("")

    md.append("## Scripts externos")
    if resultado["scripts_externos"]:
        for item in resultado["scripts_externos"]:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhum script externo encontrado.")

    md.append("")
    md.append("## Eventos inline HTML")
    if resultado["eventos_inline"]:
        for item in resultado["eventos_inline"]:
            md.append(f"- `<{item['tag']}>` — `{item['evento']}` → `{item['handler']}`")
    else:
        md.append("- Nenhum evento inline encontrado.")

    md.append("")
    md.append("## Endpoints detectados")
    endpoints = resultado.get("ajax", {}).get("endpoints", [])
    if endpoints:
        for item in endpoints:
            md.append(f"- `{item}`")
    else:
        md.append("- Nenhum endpoint detectado.")

    for bloco in resultado.get("blocos_detalhados", []):
        if bloco.get("is_external"):
            continue

        md.append("")
        md.append(f"## Bloco Script #{bloco['index']} (linha {bloco['start_line']})")

        fluxo = bloco.get("fluxo", [])
        if fluxo:
            md.append("### Leitura heurística do fluxo")
            for item in fluxo:
                md.append(f"- {item}")

        consts = bloco.get("constantes", [])
        if consts:
            md.append("")
            md.append("### Constantes")
            for c in consts:
                md.append(f"- `{c['nome']}` = `{c['valor']}`")

        funcoes = bloco.get("funcoes", [])
        if funcoes:
            md.append("")
            md.append("### Funções")
            for f in funcoes:
                params = ", ".join(f.get("params", []))
                md.append(f"- `{f['nome']}({params})` — linha relativa `{f['linha']}`")

        eventos = bloco.get("eventos_jquery", [])
        if eventos:
            md.append("")
            md.append("### Eventos jQuery")
            for e in eventos:
                md.append(
                    f"- alvo `{e['alvo']}` — evento `{e['evento']}` — seletor `{e['seletor']}` — linha relativa `{e['linha']}`"
                )

        formdatas = bloco.get("formdatas", [])
        if formdatas:
            md.append("")
            md.append("### FormData")
            for fd in formdatas:
                md.append(f"- `{fd['variavel']}` — linha relativa `{fd['linha']}` — campos `{fd['append_count']}`")
                for campo in fd["campos"]:
                    md.append(f"  - `{campo['campo']}` ← `{campo['valor']}`")

        ajax_calls = bloco.get("ajax_calls", [])
        if ajax_calls:
            md.append("")
            md.append("### AJAX detalhado")
            for a in ajax_calls:
                md.append(
                    f"- linha relativa `{a['linha']}` — método `{a['method']}` — url `{a['url']}` — timeout `{a['timeout']}`"
                )

        callbacks = bloco.get("callbacks_ajax", [])
        if callbacks:
            md.append("")
            md.append("### Callbacks AJAX")
            for cb in callbacks:
                params = ", ".join(cb.get("params", []))
                md.append(f"- `{cb['tipo']}({params})` — linha relativa `{cb['linha']}`")

        swal = bloco.get("swal_calls", [])
        if swal:
            md.append("")
            md.append("### SweetAlert")
            for s in swal:
                md.append(
                    f"- linha relativa `{s['linha']}` — icon `{s['icon']}` — title `{s['title']}` — text `{s['text']}`"
                )

        console_calls = bloco.get("console_calls", [])
        if console_calls:
            md.append("")
            md.append("### Console")
            for c in console_calls[:20]:
                md.append(f"- linha relativa `{c['linha']}` — `{c['tipo']}` → `{c['conteudo']}`")

        seletores = bloco.get("seletores_jquery", [])
        if seletores:
            md.append("")
            md.append("### Seletores jQuery")
            for s in seletores:
                md.append(f"- `{s}`")

    md.append("")
    return "\n".join(md)