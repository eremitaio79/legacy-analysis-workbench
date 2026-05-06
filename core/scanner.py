from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from typing import List, Dict
from pathlib import Path
from typing import Optional

import math
from collections import defaultdict

IGNORAR = {
    ".git",
    "vendor",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode"
}
def encontrar_arquivo_por_nome(path: str, nome_arquivo: str) -> Optional[Path]:
    base = Path(path)
    if not base.exists():
        return None

    nome_alvo = nome_arquivo.lower()

    for arquivo in base.rglob("*.php"):
        if arquivo.name.lower() == nome_alvo:
            return arquivo

    return None


def encontrar_arquivo_da_action(path: str, classe: str) -> Optional[Path]:
    """
    Tenta localizar o controller/arquivo principal a partir da action/classe do SIGBOARD.

    Exemplos:
    - Indicadorv2 -> Indicadorv2CTR.php
    - PropostaMetaReg -> PropostaMetaRegCTR.php
    """

    classe = (classe or "").strip()
    if not classe:
        return None

    candidatos = [
        f"{classe}CTR.php",
        f"{classe}.php",
    ]

    for candidato in candidatos:
        achado = encontrar_arquivo_por_nome(path, candidato)
        if achado:
            return achado

    # fallback: busca por ocorrência parcial no nome do arquivo
    base = Path(path)
    classe_lower = classe.lower()

    for arquivo in base.rglob("*.php"):
        nome = arquivo.name.lower()
        if nome == f"{classe_lower}ctr.php" or nome == f"{classe_lower}.php":
            return arquivo

    for arquivo in base.rglob("*.php"):
        nome = arquivo.name.lower()
        if classe_lower in nome and nome.endswith(".php"):
            return arquivo

    return None


def listar_php(path: str) -> List[Path]:
    """
    Lista arquivos PHP ignorando pastas irrelevantes.
    """
    base = Path(path)

    if not base.exists():
        raise Exception(f"Caminho não encontrado: {path}")

    arquivos = []

    for arquivo in base.rglob("*.php"):
        if any(pasta in IGNORAR for pasta in arquivo.parts):
            continue
        arquivos.append(arquivo)

    return arquivos


@dataclass
class ScanFileMetadata:
    absolute_path: str
    relative_path: str
    extension: str
    size_bytes: int
    line_count: int
    modified_at: float


@dataclass
class ScanFinding:
    rule_id: str
    title: str
    severity: str  # critical | warning | info
    category: str
    line_number: int
    matched_text: str
    message: str


@dataclass
class ScanFileResult:
    metadata: ScanFileMetadata
    findings: List[ScanFinding] = field(default_factory=list)


@dataclass
class ScanProjectResult:
    project_path: str
    php_files_total: int
    findings_total: int
    findings_by_severity: Dict[str, int]
    findings_by_category: Dict[str, int]
    files: List[ScanFileResult]
    top_problematic_files: List[Dict[str, object]]
    tree_lines: List[str]


SCAN_RULES = [
    {
        "rule_id": "debug_var_dump",
        "title": "Uso de var_dump",
        "severity": "warning",
        "category": "debug",
        "pattern": re.compile(r"\bvar_dump\s*\(", re.IGNORECASE),
        "message": "Uso de var_dump encontrado no código.",
    },
    {
        "rule_id": "debug_print_r",
        "title": "Uso de print_r",
        "severity": "warning",
        "category": "debug",
        "pattern": re.compile(r"\bprint_r\s*\(", re.IGNORECASE),
        "message": "Uso de print_r encontrado no código.",
    },
    {
        "rule_id": "debug_die_exit",
        "title": "Uso de die/exit",
        "severity": "warning",
        "category": "debug",
        "pattern": re.compile(r"\b(die|exit)\s*\(", re.IGNORECASE),
        "message": "Uso de die/exit encontrado no código.",
    },
    {
        "rule_id": "hardcoded_login_session",
        "title": "Login hardcoded em sessão",
        "severity": "critical",
        "category": "seguranca",
        "pattern": re.compile(
            r"""\$_SESSION\s*\[\s*['"]login['"]\s*\]\s*([=!]==?|===)\s*['"][^'"]+['"]""",
            re.IGNORECASE,
        ),
        "message": "Comparação direta de login em sessão encontrada.",
    },
    {
        "rule_id": "invalid_superglobal_session",
        "title": "Superglobal inválida $SESSION",
        "severity": "critical",
        "category": "erro-provavel",
        "pattern": re.compile(r"(?<!_)\$SESSION\b"),
        "message": "Uso de $SESSION encontrado. O correto provavelmente é $_SESSION.",
    },
    {
        "rule_id": "invalid_superglobal_generic",
        "title": "Superglobal inválida",
        "severity": "critical",
        "category": "erro-provavel",
        "pattern": re.compile(r"(?<!_)\$(GET|POST|REQUEST|SERVER)\b"),
        "message": "Uso de superglobal sem underscore encontrado.",
    },
    {
        "rule_id": "direct_request_usage",
        "title": "Uso direto de $_REQUEST",
        "severity": "warning",
        "category": "input",
        "pattern": re.compile(r"\$_REQUEST\b", re.IGNORECASE),
        "message": "Uso direto de $_REQUEST encontrado.",
    },
    {
        "rule_id": "suspicious_comment",
        "title": "Comentário suspeito",
        "severity": "info",
        "category": "comentario",
        "pattern": re.compile(
            r"(mock|mocado|tempor[aá]rio|remover depois|gambiarra|hotfix|teste r[aá]pido)",
            re.IGNORECASE,
        ),
        "message": "Comentário suspeito encontrado.",
    },
    {
        "rule_id": "sql_inline",
        "title": "SQL inline",
        "severity": "warning",
        "category": "sql",
        "pattern": re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|EXEC|MERGE)\b", re.IGNORECASE),
        "message": "Possível SQL inline encontrado.",
    },
]


def analisar_arquivo_php(base_path: str, arquivo: Path) -> ScanFileResult:
    stat = arquivo.stat()
    relative_path = str(arquivo.relative_to(Path(base_path)))
    content = arquivo.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    metadata = ScanFileMetadata(
        absolute_path=str(arquivo),
        relative_path=relative_path,
        extension=arquivo.suffix.lower(),
        size_bytes=stat.st_size,
        line_count=len(lines),
        modified_at=stat.st_mtime,
    )

    findings: List[ScanFinding] = []

    for line_number, line in enumerate(lines, start=1):
        findings.extend(_aplicar_regras_linha(line_number, line))

        possivel_erro = _detectar_possivel_falta_ponto_virgula(line_number, line)
        if possivel_erro:
            findings.append(possivel_erro)

    if metadata.line_count > 2000:
        findings.append(
            ScanFinding(
                rule_id="large_file",
                title="Arquivo muito grande",
                severity="info",
                category="estrutura",
                line_number=1,
                matched_text="",
                message=f"Arquivo com {metadata.line_count} linhas.",
            )
        )

    return ScanFileResult(metadata=metadata, findings=findings)


def consolidar_resultado_scan(project_path: str, resultados: List[ScanFileResult]) -> ScanProjectResult:
    findings_total = 0
    findings_by_severity: Dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    findings_by_category: Dict[str, int] = {}

    for item in resultados:
        for finding in item.findings:
            findings_total += 1
            findings_by_severity[finding.severity] = findings_by_severity.get(finding.severity, 0) + 1
            findings_by_category[finding.category] = findings_by_category.get(finding.category, 0) + 1

    top_problematic_files = _build_top_problematic_files(resultados)
    tree_lines = _build_tree_lines(Path(project_path))

    return ScanProjectResult(
        project_path=project_path,
        php_files_total=len(resultados),
        findings_total=findings_total,
        findings_by_severity=findings_by_severity,
        findings_by_category=findings_by_category,
        files=resultados,
        top_problematic_files=top_problematic_files,
        tree_lines=tree_lines,
    )


def render_scan_markdown(result: ScanProjectResult) -> str:
    linhas: List[str] = []

    linhas.append("# Scanner Inteligente do Projeto")
    linhas.append("")
    linhas.append("## Resumo")
    linhas.append(f"- Projeto: `{result.project_path}`")
    linhas.append(f"- Arquivos PHP analisados: **{result.php_files_total}**")
    linhas.append(f"- Achados totais: **{result.findings_total}**")
    linhas.append(f"- Críticos: **{result.findings_by_severity.get('critical', 0)}**")
    linhas.append(f"- Warnings: **{result.findings_by_severity.get('warning', 0)}**")
    linhas.append(f"- Info: **{result.findings_by_severity.get('info', 0)}**")
    linhas.append("")

    linhas.append("## Achados por categoria")
    for categoria, total in sorted(result.findings_by_category.items(), key=lambda x: (-x[1], x[0])):
        linhas.append(f"- **{categoria}**: {total}")
    linhas.append("")

    linhas.append("## Arquivos mais problemáticos")
    if result.top_problematic_files:
        for item in result.top_problematic_files[:15]:
            linhas.append(
                f"- `{item['relative_path']}` | total={item['total_findings']} | "
                f"critical={item['critical']} | warning={item['warning']} | info={item['info']}"
            )
    else:
        linhas.append("- Nenhum arquivo problemático encontrado.")
    linhas.append("")

    linhas.append("## Estrutura resumida de pastas")
    linhas.append("```text")
    linhas.extend(result.tree_lines[:200])
    linhas.append("```")
    linhas.append("")

    linhas.append("## Achados detalhados")
    detalhes = [f for f in result.files if f.findings]

    if not detalhes:
        linhas.append("- Nenhum achado encontrado.")
    else:
        for arquivo in detalhes:
            linhas.append(f"### {arquivo.metadata.relative_path}")
            linhas.append("")
            linhas.append(
                f"- Linhas: {arquivo.metadata.line_count} | Tamanho: {arquivo.metadata.size_bytes} bytes"
            )
            linhas.append("")
            for finding in arquivo.findings[:80]:
                linhas.append(
                    f"- **[{finding.severity.upper()}]** linha {finding.line_number} | "
                    f"{finding.title} | {finding.message}"
                )
                if finding.matched_text:
                    linhas.append(f"  - Trecho: `{finding.matched_text}`")
            linhas.append("")

    return "\n".join(linhas)


def gerar_relatorios_scan_segmentados(result: ScanProjectResult, output_file: str) -> str:
    output_path = Path(output_file)
    base_dir = output_path.with_suffix("")
    base_dir.mkdir(parents=True, exist_ok=True)

    arquivos_dir = base_dir / "arquivos"
    arquivos_dir.mkdir(parents=True, exist_ok=True)

    generated_files: List[tuple[str, str]] = []

    # 00 - resumo geral
    resumo_filename = "00_resumo_geral.md"
    resumo_lines = [
        "# Scanner Inteligente do Projeto",
        "",
        "## Resumo",
        f"- Projeto: `{result.project_path}`",
        f"- Arquivos PHP analisados: **{result.php_files_total}**",
        f"- Achados totais: **{result.findings_total}**",
        f"- Críticos: **{result.findings_by_severity.get('critical', 0)}**",
        f"- Warnings: **{result.findings_by_severity.get('warning', 0)}**",
        f"- Info: **{result.findings_by_severity.get('info', 0)}**",
        "",
    ]
    (base_dir / resumo_filename).write_text("\n".join(resumo_lines), encoding="utf-8")
    generated_files.append(("Resumo geral", resumo_filename))

    # 01 - categorias
    categorias_filename = "01_categorias.md"
    categorias_lines = ["# Achados por categoria", ""]
    for categoria, total in sorted(result.findings_by_category.items(), key=lambda x: (-x[1], x[0])):
        categorias_lines.append(f"- **{categoria}**: {total}")
    categorias_lines.append("")
    (base_dir / categorias_filename).write_text("\n".join(categorias_lines), encoding="utf-8")
    generated_files.append(("Achados por categoria", categorias_filename))

    # 02 - top arquivos
    top_filename = "02_top_arquivos.md"
    top_lines = ["# Top arquivos mais problemáticos", ""]
    if result.top_problematic_files:
        for item in result.top_problematic_files:
            top_lines.append(
                f"- `{item['relative_path']}` | total={item['total_findings']} | "
                f"critical={item['critical']} | warning={item['warning']} | info={item['info']}"
            )
    else:
        top_lines.append("- Nenhum arquivo problemático encontrado.")
    top_lines.append("")
    (base_dir / top_filename).write_text("\n".join(top_lines), encoding="utf-8")
    generated_files.append(("Top arquivos mais problemáticos", top_filename))

    # 03 - estrutura de pastas
    estrutura_filename = "03_estrutura_pastas.md"
    estrutura_lines = ["# Estrutura resumida de pastas", "", "```text"]
    estrutura_lines.extend(result.tree_lines[:300])
    estrutura_lines.append("```")
    estrutura_lines.append("")
    (base_dir / estrutura_filename).write_text("\n".join(estrutura_lines), encoding="utf-8")
    generated_files.append(("Estrutura resumida de pastas", estrutura_filename))

    # 10/11/12 - por severidade
    severity_files: List[tuple[str, str]] = []
    for severity, filename, label in [
        ("critical", "10_achados_criticos.md", "Achados críticos"),
        ("warning", "11_achados_warning.md", "Achados warning"),
        ("info", "12_achados_info.md", "Achados info"),
    ]:
        lines = [f"# Achados {severity.upper()}", ""]
        total_severity = 0

        for file_result in result.files:
            achados = [f for f in file_result.findings if f.severity == severity]
            if not achados:
                continue

            total_severity += len(achados)
            lines.append(f"## {file_result.metadata.relative_path}")
            lines.append("")
            for finding in achados:
                lines.append(
                    f"- linha {finding.line_number} | **{finding.title}** | {finding.message}"
                )
                if finding.matched_text:
                    lines.append(f"  - Trecho: `{finding.matched_text}`")
            lines.append("")

        if total_severity == 0:
            lines.append("Nenhum achado encontrado.")
            lines.append("")

        (base_dir / filename).write_text("\n".join(lines), encoding="utf-8")
        generated_files.append((label, filename))
        severity_files.append((label, filename))

    # arquivos individuais
    arquivos_com_achados = [f for f in result.files if f.findings]
    generated_file_details: List[tuple[str, str]] = []

    for file_result in arquivos_com_achados:
        safe_name = (
            file_result.metadata.relative_path
            .replace("\\", "_")
            .replace("/", "_")
            .replace(":", "_")
        )
        output_md = arquivos_dir / f"{safe_name}.md"

        lines = [
            f"# {file_result.metadata.relative_path}",
            "",
            "## Metadados",
            f"- Caminho absoluto: `{file_result.metadata.absolute_path}`",
            f"- Extensão: `{file_result.metadata.extension}`",
            f"- Tamanho: `{file_result.metadata.size_bytes}` bytes",
            f"- Linhas: `{file_result.metadata.line_count}`",
            "",
            "## Achados",
            "",
        ]

        for finding in file_result.findings:
            lines.append(
                f"- **[{finding.severity.upper()}]** linha {finding.line_number} | "
                f"{finding.title} | {finding.message}"
            )
            if finding.matched_text:
                lines.append(f"  - Trecho: `{finding.matched_text}`")

        lines.append("")
        output_md.write_text("\n".join(lines), encoding="utf-8")

        generated_file_details.append(
            (file_result.metadata.relative_path, f"arquivos/{output_md.name}")
        )

    # 00 - índice
    indice_lines = [
        "# Índice do Scanner Inteligente",
        "",
        "## Visão geral",
        "",
        f"- Projeto analisado: `{result.project_path}`",
        f"- Arquivos PHP analisados: **{result.php_files_total}**",
        f"- Achados totais: **{result.findings_total}**",
        "",
        "## Relatórios principais",
        "",
    ]

    for label, filename in generated_files:
        indice_lines.append(f"- [{label}]({filename})")

    indice_lines.append("")
    indice_lines.append("## Arquivos individuais com achados")
    indice_lines.append("")

    if generated_file_details:
        for relative_path, link in generated_file_details:
            indice_lines.append(f"- [{relative_path}]({link})")
    else:
        indice_lines.append("- Nenhum arquivo individual com achados foi gerado.")

    indice_lines.append("")

    (base_dir / "00_indice.md").write_text("\n".join(indice_lines), encoding="utf-8")

    return str(base_dir)


def _aplicar_regras_linha(line_number: int, line: str) -> List[ScanFinding]:
    findings: List[ScanFinding] = []

    for rule in SCAN_RULES:
        if rule["pattern"].search(line):
            findings.append(
                ScanFinding(
                    rule_id=rule["rule_id"],
                    title=rule["title"],
                    severity=rule["severity"],
                    category=rule["category"],
                    line_number=line_number,
                    matched_text=line.strip()[:220],
                    message=rule["message"],
                )
            )

    return findings


def _detectar_possivel_falta_ponto_virgula(line_number: int, line: str) -> Optional[ScanFinding]:
    stripped = line.strip()

    if not stripped:
        return None

    if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
        return None

    if stripped.endswith((";", "{", "}", ":", ",")):
        return None

    if re.match(r"^(if|elseif|else|for|foreach|while|switch|case|default|function|class)\b", stripped):
        return None

    if re.match(r"^(return|echo|\$[A-Za-z_])", stripped):
        if "=" in stripped or stripped.startswith("return ") or stripped.startswith("echo "):
            return ScanFinding(
                rule_id="possible_missing_semicolon",
                title="Possível falta de ponto e vírgula",
                severity="info",
                category="sintaxe-suspeita",
                line_number=line_number,
                matched_text=stripped[:220],
                message="Linha suspeita de instrução PHP sem ponto e vírgula ao final.",
            )

    return None


def _build_top_problematic_files(resultados: List[ScanFileResult]) -> List[Dict[str, object]]:
    ranking: List[Dict[str, object]] = []

    for item in resultados:
        critical = sum(1 for f in item.findings if f.severity == "critical")
        warning = sum(1 for f in item.findings if f.severity == "warning")
        info = sum(1 for f in item.findings if f.severity == "info")
        total = len(item.findings)

        if total == 0:
            continue

        score = (critical * 5) + (warning * 3) + info

        ranking.append(
            {
                "relative_path": item.metadata.relative_path,
                "total_findings": total,
                "critical": critical,
                "warning": warning,
                "info": info,
                "score": score,
            }
        )

    ranking.sort(key=lambda x: (-x["score"], -x["critical"], -x["warning"], x["relative_path"]))
    return ranking[:20]


def _build_tree_lines(root: Path, max_depth: int = 4, max_children: int = 25) -> List[str]:
    lines: List[str] = [root.name]

    def walk(current: Path, prefix: str = "", depth: int = 0) -> None:
        if depth >= max_depth:
            return

        try:
            children = sorted(
                [p for p in current.iterdir() if not any(parte in IGNORAR for parte in p.parts)],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except Exception:
            return

        if len(children) > max_children:
            children = children[:max_children]

        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{child.name}")

            if child.is_dir():
                extension = "    " if is_last else "│   "
                walk(child, prefix + extension, depth + 1)

    walk(root)
    return lines


def buscar_texto_em_arquivo(
    arquivo: Path,
    termo: str,
    case_sensitive: bool = False,
    linhas_contexto: int = 1
) -> List[Dict]:
    """
    Procura um texto dentro de um arquivo e retorna as ocorrências com contexto.
    """
    resultados = []

    try:
        linhas = arquivo.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return resultados

    termo_cmp = termo if case_sensitive else termo.lower()

    for numero_linha, linha in enumerate(linhas, start=1):
        linha_cmp = linha if case_sensitive else linha.lower()

        if termo_cmp in linha_cmp:
            inicio = max(0, numero_linha - 1 - linhas_contexto)
            fim = min(len(linhas), numero_linha + linhas_contexto)

            contexto = []
            for i in range(inicio, fim):
                contexto.append({
                    "numero": i + 1,
                    "conteudo": linhas[i]
                })

            resultados.append({
                "arquivo": str(arquivo),
                "linha": numero_linha,
                "trecho": linha.strip(),
                "contexto": contexto
            })

    return resultados

def encontrar_arquivo_do_metodo(path: str, nome_metodo: str) -> Optional[Path]:
    """
    Varre os arquivos PHP e retorna o primeiro arquivo que contém a assinatura do método.
    """
    arquivos = listar_php(path)
    assinatura = f"function {nome_metodo}("

    for arquivo in arquivos:
        try:
            conteudo = arquivo.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if assinatura in conteudo:
            return arquivo

    return None