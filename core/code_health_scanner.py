from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


PHP_EXTENSIONS = {".php", ".inc", ".phtml"}


@dataclass
class FileMetadata:
    path: str
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
    file_path: str
    relative_path: str
    line_number: int
    matched_text: str
    message: str


@dataclass
class FileScanResult:
    metadata: FileMetadata
    findings: List[ScanFinding] = field(default_factory=list)


@dataclass
class ProjectTreeNode:
    name: str
    node_type: str  # dir | file
    children: List["ProjectTreeNode"] = field(default_factory=list)


@dataclass
class CodeHealthScanResult:
    project_path: str
    scanned_files: int
    scanned_php_files: int
    findings_total: int
    findings_by_severity: Dict[str, int]
    findings_by_category: Dict[str, int]
    file_results: List[FileScanResult]
    tree_lines: List[str]
    top_problematic_files: List[Dict[str, object]]

    def to_dict(self) -> dict:
        return asdict(self)


class CodeHealthScanner:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()

        self.rules = [
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
                "rule_id": "hardcoded_login_generic",
                "title": "Login hardcoded",
                "severity": "critical",
                "category": "seguranca",
                "pattern": re.compile(
                    r"""\$[A-Za-z_][A-Za-z0-9_]*\s*([=!]==?|===)\s*['"](admin|teste|root|guest|fernando\.altieri|paulo|usuario)['"]""",
                    re.IGNORECASE,
                ),
                "message": "Possível login/usuário hardcoded encontrado.",
            },
            {
                "rule_id": "invalid_superglobal_session",
                "title": "Superglobal inválida $SESSION",
                "severity": "critical",
                "category": "erro-provavel",
                "pattern": re.compile(r"(?<!_)\\$SESSION\b"),
                "message": "Uso de $SESSION encontrado. O correto provavelmente é $_SESSION.",
            },
            {
                "rule_id": "invalid_superglobal_request",
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

    def scan(self) -> CodeHealthScanResult:
        all_files = self._list_all_files()
        php_files = [p for p in all_files if p.suffix.lower() in PHP_EXTENSIONS]

        file_results: List[FileScanResult] = []

        for file_path in php_files:
            file_results.append(self._scan_file(file_path))

        findings = [f for item in file_results for f in item.findings]

        findings_by_severity = {"critical": 0, "warning": 0, "info": 0}
        findings_by_category: Dict[str, int] = {}

        for finding in findings:
            findings_by_severity[finding.severity] = findings_by_severity.get(finding.severity, 0) + 1
            findings_by_category[finding.category] = findings_by_category.get(finding.category, 0) + 1

        top_problematic_files = self._build_top_problematic_files(file_results)
        tree_lines = self._build_tree_lines(self.base_dir)

        return CodeHealthScanResult(
            project_path=str(self.base_dir),
            scanned_files=len(all_files),
            scanned_php_files=len(php_files),
            findings_total=len(findings),
            findings_by_severity=findings_by_severity,
            findings_by_category=findings_by_category,
            file_results=file_results,
            tree_lines=tree_lines,
            top_problematic_files=top_problematic_files,
        )

    def _list_all_files(self) -> List[Path]:
        return [p for p in self.base_dir.rglob("*") if p.is_file()]

    def _scan_file(self, file_path: Path) -> FileScanResult:
        relative_path = str(file_path.relative_to(self.base_dir))

        try:
            stat = file_path.stat()
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            stat = file_path.stat()
            content = ""

        lines = content.splitlines()

        metadata = FileMetadata(
            path=str(file_path),
            relative_path=relative_path,
            extension=file_path.suffix.lower(),
            size_bytes=stat.st_size,
            line_count=len(lines),
            modified_at=stat.st_mtime,
        )

        findings: List[ScanFinding] = []

        for line_number, line in enumerate(lines, start=1):
            findings.extend(self._apply_rules_to_line(file_path, relative_path, line_number, line))

            syntax_warning = self._detect_possible_missing_semicolon(
                file_path=file_path,
                relative_path=relative_path,
                line_number=line_number,
                line=line,
            )
            if syntax_warning:
                findings.append(syntax_warning)

        if metadata.line_count > 2000:
            findings.append(
                ScanFinding(
                    rule_id="large_file",
                    title="Arquivo muito grande",
                    severity="info",
                    category="estrutura",
                    file_path=str(file_path),
                    relative_path=relative_path,
                    line_number=1,
                    matched_text="",
                    message=f"Arquivo com {metadata.line_count} linhas.",
                )
            )

        return FileScanResult(metadata=metadata, findings=findings)

    def _apply_rules_to_line(
        self,
        file_path: Path,
        relative_path: str,
        line_number: int,
        line: str,
    ) -> List[ScanFinding]:
        findings: List[ScanFinding] = []

        for rule in self.rules:
            if rule["pattern"].search(line):
                findings.append(
                    ScanFinding(
                        rule_id=rule["rule_id"],
                        title=rule["title"],
                        severity=rule["severity"],
                        category=rule["category"],
                        file_path=str(file_path),
                        relative_path=relative_path,
                        line_number=line_number,
                        matched_text=line.strip()[:220],
                        message=rule["message"],
                    )
                )

        return findings

    def _detect_possible_missing_semicolon(
        self,
        file_path: Path,
        relative_path: str,
        line_number: int,
        line: str,
    ) -> Optional[ScanFinding]:
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
                    file_path=str(file_path),
                    relative_path=relative_path,
                    line_number=line_number,
                    matched_text=stripped[:220],
                    message="Linha suspeita de instrução PHP sem ponto e vírgula ao final.",
                )

        return None

    def _build_top_problematic_files(self, file_results: List[FileScanResult]) -> List[Dict[str, object]]:
        ranking = []

        for item in file_results:
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

    def _build_tree_lines(self, root: Path, max_depth: int = 4, max_children: int = 25) -> List[str]:
        lines: List[str] = [root.name]

        def walk(current: Path, prefix: str = "", depth: int = 0) -> None:
            if depth >= max_depth:
                return

            try:
                children = sorted(
                    list(current.iterdir()),
                    key=lambda p: (not p.is_dir(), p.name.lower())
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