from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)


PHP_EXTENSIONS = {".php", ".inc", ".phtml"}


# =========================================================
# Dataclasses
# =========================================================


@dataclass
class MethodCallInfo:
    target: str
    method: str
    line: int


@dataclass
class StaticCallInfo:
    class_name: str
    method: str
    line: int


@dataclass
class NewClassInfo:
    class_name: str
    line: int


@dataclass
class SqlBlockInfo:
    sql: str
    line: int
    tables: List[str] = field(default_factory=list)


@dataclass
class MethodInfo:
    name: str
    visibility: str
    start_line: int
    end_line: int
    parameters: List[str] = field(default_factory=list)
    body: str = ""
    calls: List[MethodCallInfo] = field(default_factory=list)
    static_calls: List[StaticCallInfo] = field(default_factory=list)
    new_instances: List[NewClassInfo] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    sql_blocks: List[SqlBlockInfo] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class FachadaAnalysisResult:
    input_value: str
    resolved_path: str
    class_name: Optional[str]
    namespace: Optional[str]
    total_lines: int
    public_methods_count: int
    methods: List[MethodInfo] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    new_instances: List[NewClassInfo] = field(default_factory=list)
    static_calls: List[StaticCallInfo] = field(default_factory=list)
    sql_blocks: List[SqlBlockInfo] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    target_method: Optional[str] = None
    target_method_found: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================
# Analyzer
# =========================================================


class FachadaAnalyzer:
    """
    Analisador de fachadas do SIGBOARD.

    Entradas suportadas:
    - nome da fachada: ex. FachadaIndicadorBD
    - caminho direto do arquivo PHP
    - Classe.metodo
    """

    def _target_method_exists(self, lines: List[str], target_method: str) -> bool:
        pattern = re.compile(
            rf"""^\s*public\s+function\s+{re.escape(target_method)}\s*\(""",
            flags=re.IGNORECASE,
        )

        for line in lines:
            if pattern.search(line):
                return True

        return False

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()

    # -----------------------------------------------------
    # API pública
    # -----------------------------------------------------

    def analyze(
        self,
        target: str,
        proceed_with_full_fachada_if_method_missing: bool = True,
    ) -> FachadaAnalysisResult:
        resolved_target = self._parse_target(target)
        resolved_path = self._resolve_target(resolved_target["class_or_path"])
        target_method = resolved_target["method"]

        if not resolved_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {resolved_path}")

        content = resolved_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        target_method_found = True
        analyze_full_fachada = False

        if target_method:
            target_method_found = self._target_method_exists(lines, target_method)
            analyze_full_fachada = not target_method_found and proceed_with_full_fachada_if_method_missing

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[yellow]{task.fields[current_item]}[/yellow]"),
            TimeElapsedColumn(),
            transient=False,
        ) as progress:
            main_task = progress.add_task(
                "Analisando fachada...",
                total=9,
                current_item="iniciando...",
            )

            namespace = self._extract_namespace(content)
            progress.update(main_task, current_item="namespace")
            progress.advance(main_task)

            class_name = self._extract_class_name(content)
            progress.update(
                main_task,
                current_item=class_name or "classe não identificada",
            )
            progress.advance(main_task)

            if target_method:
                if target_method_found:
                    progress.update(
                        main_task,
                        current_item=f"método alvo '{target_method}' localizado",
                    )
                elif analyze_full_fachada:
                    progress.update(
                        main_task,
                        current_item=f"método '{target_method}' não encontrado; analisando CTR inteira",
                    )
                else:
                    progress.update(
                        main_task,
                        current_item=f"método '{target_method}' não encontrado",
                    )
                progress.advance(main_task)
            else:
                progress.update(main_task, current_item="análise da fachada completa")
                progress.advance(main_task)

            file_includes, file_requires = self._extract_includes_requires(content)
            progress.update(main_task, current_item="includes / requires")
            progress.advance(main_task)

            methods = self._extract_methods(lines, progress)

            if target_method and target_method_found:
                methods = [m for m in methods if m.name.lower() == target_method.lower()]

            progress.update(
                main_task,
                current_item=f"{len(methods)} método(s) selecionado(s)",
            )
            progress.advance(main_task)

            file_news = self._extract_new_instances(content)
            file_static_calls = self._extract_static_calls(content)
            progress.update(main_task, current_item="dependências globais")
            progress.advance(main_task)

            file_sql_blocks = self._extract_sql_blocks(content)
            progress.update(main_task, current_item="SQL do arquivo")
            progress.advance(main_task)

            all_tables = self._collect_tables(file_sql_blocks, methods)
            dependencies = self._collect_dependencies(
                file_includes=file_includes,
                file_requires=file_requires,
                file_news=file_news,
                file_static_calls=file_static_calls,
                methods=methods,
            )
            progress.update(main_task, current_item="agregando tabelas e dependências")
            progress.advance(main_task)

            warnings = self._build_warnings(
                class_name=class_name,
                methods=methods,
                total_lines=len(lines),
                target_method=target_method,
                target_method_found=target_method_found,
                analyze_full_fachada=analyze_full_fachada,
            )
            progress.update(main_task, current_item="concluído")
            progress.advance(main_task)

        return FachadaAnalysisResult(
            input_value=target,
            resolved_path=str(resolved_path),
            class_name=class_name,
            namespace=namespace,
            total_lines=len(lines),
            public_methods_count=len(methods),
            methods=methods,
            includes=file_includes,
            requires=file_requires,
            new_instances=file_news,
            static_calls=file_static_calls,
            sql_blocks=file_sql_blocks,
            tables=all_tables,
            dependencies=dependencies,
            warnings=warnings,
            target_method=target_method,
            target_method_found=target_method_found,
        )

    # -----------------------------------------------------
    # Resolução do alvo
    # -----------------------------------------------------

    def _parse_target(self, target: str) -> Dict[str, Optional[str]]:
        raw = target.strip()

        is_possible_class_method = (
            "." in raw
            and not raw.lower().endswith(".php")
            and "/" not in raw
            and "\\" not in raw
        )

        if is_possible_class_method:
            class_name, method_name = raw.split(".", 1)
            return {
                "class_or_path": class_name.strip(),
                "method": method_name.strip(),
            }

        return {
            "class_or_path": raw,
            "method": None,
        }

    def _resolve_target(self, target: str) -> Path:
        raw = target.strip()

        if raw.lower().endswith(".php") or "/" in raw or "\\" in raw:
            path = Path(raw)
            if not path.is_absolute():
                path = (self.base_dir / path).resolve()
            return path

        return self._resolve_by_name(raw)

    def _resolve_by_name(self, class_name: str) -> Path:
        candidates: List[Path] = []

        for path in self.base_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in PHP_EXTENSIONS:
                continue

            if path.stem.lower() == class_name.lower():
                candidates.append(path)
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            class_match = re.search(
                rf"\bclass\s+{re.escape(class_name)}\b",
                content,
                flags=re.IGNORECASE,
            )
            if class_match:
                candidates.append(path)

        if not candidates:
            raise FileNotFoundError(
                f"Não foi possível localizar a fachada '{class_name}' em {self.base_dir}"
            )

        exact_name = [p for p in candidates if p.stem.lower() == class_name.lower()]
        if exact_name:
            return exact_name[0]

        return candidates[0]

    # -----------------------------------------------------
    # Extrações principais
    # -----------------------------------------------------

    def _extract_namespace(self, content: str) -> Optional[str]:
        match = re.search(r"\bnamespace\s+([^;]+);", content)
        return match.group(1).strip() if match else None

    def _extract_class_name(self, content: str) -> Optional[str]:
        match = re.search(
            r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
            content,
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _extract_includes_requires(self, content: str) -> Tuple[List[str], List[str]]:
        includes: List[str] = []
        requires: List[str] = []

        include_pattern = re.compile(
            r"""\b(include|include_once)\s*\(?\s*['"]([^'"]+)['"]\s*\)?\s*;?""",
            flags=re.IGNORECASE,
        )
        require_pattern = re.compile(
            r"""\b(require|require_once)\s*\(?\s*['"]([^'"]+)['"]\s*\)?\s*;?""",
            flags=re.IGNORECASE,
        )

        for match in include_pattern.finditer(content):
            includes.append(match.group(2).strip())

        for match in require_pattern.finditer(content):
            requires.append(match.group(2).strip())

        return sorted(set(includes)), sorted(set(requires))

    def _extract_methods(
        self,
        lines: List[str],
        progress: Progress,
    ) -> List[MethodInfo]:
        methods: List[MethodInfo] = []

        public_method_pattern = re.compile(
            r"""^\s*public\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)""",
            flags=re.IGNORECASE,
        )

        method_candidates: List[Tuple[int, str, str]] = []
        for idx, line in enumerate(lines, start=1):
            match = public_method_pattern.search(line)
            if match:
                method_candidates.append((idx, match.group(1), match.group(2)))

        total_methods = max(len(method_candidates), 1)
        method_task = progress.add_task(
            "Mapeando métodos públicos...",
            total=total_methods,
            current_item="procurando métodos...",
        )

        if not method_candidates:
            progress.update(method_task, current_item="nenhum método público encontrado")
            return methods

        for idx, (start_line, method_name, raw_params) in enumerate(method_candidates, start=1):
            progress.update(
                method_task,
                description="Mapeando métodos públicos...",
                current_item=f"[{idx}/{len(method_candidates)}] analisando {method_name}() na linha {start_line}",
            )

            progress.update(
                method_task,
                current_item=f"[{idx}/{len(method_candidates)}] extraindo corpo de {method_name}()",
            )
            end_line, body = self._extract_method_body(lines, start_line)

            method = MethodInfo(
                name=method_name,
                visibility="public",
                start_line=start_line,
                end_line=end_line,
                parameters=self._split_parameters(raw_params),
                body=body,
            )

            method.includes, method.requires = self._extract_includes_requires(body)
            method.new_instances = self._extract_new_instances(body, base_line=start_line)
            method.static_calls = self._extract_static_calls(body, base_line=start_line)
            method.calls = self._extract_method_calls(body, base_line=start_line)
            method.sql_blocks = self._extract_sql_blocks(body, base_line=start_line)
            method.tables = self._collect_tables(method.sql_blocks)
            method.notes = self._detect_method_notes(method)

            progress.update(
                method_task,
                current_item=f"[{idx}/{len(method_candidates)}] consolidando dependências de {method_name}()",
            )

            methods.append(method)
            progress.advance(method_task)

        progress.update(method_task, current_item="varredura de métodos concluída")
        return methods

    def _extract_method_body(self, lines: List[str], start_line: int) -> Tuple[int, str]:
        joined = "\n".join(lines)
        char_offsets = self._line_char_offsets(lines)
        start_pos = char_offsets[start_line - 1]

        brace_pos = joined.find("{", start_pos)
        if brace_pos == -1:
            return start_line, ""

        depth = 0
        end_pos = brace_pos
        in_single = False
        in_double = False
        escaped = False

        for i in range(brace_pos, len(joined)):
            ch = joined[i]

            if escaped:
                escaped = False
                continue

            if ch == "\\":
                escaped = True
                continue

            if ch == "'" and not in_double:
                in_single = not in_single
                continue

            if ch == '"' and not in_single:
                in_double = not in_double
                continue

            if in_single or in_double:
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break

        body = joined[brace_pos : end_pos + 1]
        end_line = joined.count("\n", 0, end_pos) + 1
        return end_line, body

    def _split_parameters(self, raw_params: str) -> List[str]:
        raw = raw_params.strip()
        if not raw:
            return []

        parts = [p.strip() for p in raw.split(",")]
        return [p for p in parts if p]

    # -----------------------------------------------------
    # Dependências e chamadas
    # -----------------------------------------------------

    def _extract_new_instances(self, content: str, base_line: int = 1) -> List[NewClassInfo]:
        pattern = re.compile(r"\bnew\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        results: List[NewClassInfo] = []

        for match in pattern.finditer(content):
            line = base_line + content.count("\n", 0, match.start())
            results.append(NewClassInfo(class_name=match.group(1), line=line))

        return self._dedupe_new_instances(results)

    def _extract_static_calls(self, content: str, base_line: int = 1) -> List[StaticCallInfo]:
        pattern = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        results: List[StaticCallInfo] = []

        for match in pattern.finditer(content):
            line = base_line + content.count("\n", 0, match.start())
            results.append(
                StaticCallInfo(
                    class_name=match.group(1),
                    method=match.group(2),
                    line=line,
                )
            )

        return self._dedupe_static_calls(results)

    def _extract_method_calls(self, content: str, base_line: int = 1) -> List[MethodCallInfo]:
        pattern = re.compile(r"(\$[A-Za-z_][A-Za-z0-9_]*)->([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        results: List[MethodCallInfo] = []

        for match in pattern.finditer(content):
            line = base_line + content.count("\n", 0, match.start())
            results.append(
                MethodCallInfo(
                    target=match.group(1),
                    method=match.group(2),
                    line=line,
                )
            )

        return self._dedupe_method_calls(results)

    # -----------------------------------------------------
    # SQL
    # -----------------------------------------------------

    def _extract_sql_blocks(self, content: str, base_line: int = 1) -> List[SqlBlockInfo]:
        sql_blocks: List[SqlBlockInfo] = []

        string_pattern = re.compile(
            r'("([^"\\]|\\.|"")*"|\'([^\'\\]|\\.|\'\')*\')',
            flags=re.DOTALL,
        )

        sql_keyword_pattern = re.compile(
            r"\b(SELECT|INSERT|UPDATE|DELETE|EXEC|WITH|MERGE)\b",
            flags=re.IGNORECASE,
        )

        for match in string_pattern.finditer(content):
            raw_literal = match.group(0)
            literal_content = raw_literal[1:-1]

            if not sql_keyword_pattern.search(literal_content):
                continue

            line = base_line + content.count("\n", 0, match.start())
            sql = self._normalize_sql(literal_content)
            tables = self._extract_tables_from_sql(sql)

            sql_blocks.append(SqlBlockInfo(sql=sql, line=line, tables=tables))

        return self._dedupe_sql_blocks(sql_blocks)

    def _normalize_sql(self, sql: str) -> str:
        sql = sql.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
        sql = re.sub(r"[ \t]+", " ", sql)
        sql = re.sub(r"\n\s+", "\n", sql)
        return sql.strip()

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        patterns = [
            r"\bFROM\s+([A-Za-z0-9_\.\[\]]+)",
            r"\bJOIN\s+([A-Za-z0-9_\.\[\]]+)",
            r"\bUPDATE\s+([A-Za-z0-9_\.\[\]]+)",
            r"\bINTO\s+([A-Za-z0-9_\.\[\]]+)",
            r"\bDELETE\s+FROM\s+([A-Za-z0-9_\.\[\]]+)",
            r"\bMERGE\s+([A-Za-z0-9_\.\[\]]+)",
        ]

        tables: Set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, sql, flags=re.IGNORECASE):
                table = match.group(1).strip()
                if table.upper() not in {"SELECT", "FROM", "JOIN"}:
                    tables.add(table)

        return sorted(tables)

    # -----------------------------------------------------
    # Agregações
    # -----------------------------------------------------

    def _collect_tables(
        self,
        file_sql_blocks: Optional[List[SqlBlockInfo]] = None,
        methods: Optional[List[MethodInfo]] = None,
    ) -> List[str]:
        tables: Set[str] = set()

        if file_sql_blocks:
            for block in file_sql_blocks:
                tables.update(block.tables)

        if methods:
            for method in methods:
                tables.update(method.tables)

        return sorted(tables)

    def _collect_dependencies(
        self,
        file_includes: List[str],
        file_requires: List[str],
        file_news: List[NewClassInfo],
        file_static_calls: List[StaticCallInfo],
        methods: List[MethodInfo],
    ) -> List[str]:
        deps: Set[str] = set()

        deps.update(file_includes)
        deps.update(file_requires)

        for item in file_news:
            deps.add(item.class_name)

        for item in file_static_calls:
            deps.add(item.class_name)

        for method in methods:
            deps.update(method.includes)
            deps.update(method.requires)

            for item in method.new_instances:
                deps.add(item.class_name)

            for item in method.static_calls:
                deps.add(item.class_name)

        return sorted(deps)

    def _build_warnings(
            self,
            class_name: Optional[str],
            methods: List[MethodInfo],
            total_lines: int,
            target_method: Optional[str] = None,
            target_method_found: bool = True,
            analyze_full_fachada: bool = False,
    ) -> List[str]:
        warnings: List[str] = []

        if not class_name:
            warnings.append("Classe principal não identificada no arquivo.")

        if target_method and not target_method_found:
            if analyze_full_fachada:
                warnings.append(
                    f"O método alvo '{target_method}' não foi encontrado. A análise prosseguiu com a fachada inteira."
                )
            else:
                warnings.append(
                    f"O método alvo '{target_method}' não foi encontrado na fachada."
                )

        if not methods:
            if not target_method:
                warnings.append("Nenhum método público foi encontrado.")
            elif target_method_found:
                warnings.append("Nenhum método público foi encontrado.")

        if total_lines > 5000:
            warnings.append("Arquivo muito grande: revisão manual recomendada em trechos críticos.")

        big_methods = [m for m in methods if (m.end_line - m.start_line) > 200]
        if big_methods:
            warnings.append(f"{len(big_methods)} método(s) público(s) possuem mais de 200 linhas.")

        methods_with_sql = [m for m in methods if m.sql_blocks]
        if methods_with_sql:
            warnings.append(f"{len(methods_with_sql)} método(s) público(s) contêm SQL embutido.")

        methods_with_many_calls = [
            m for m in methods if (len(m.calls) + len(m.static_calls)) > 15
        ]
        if methods_with_many_calls:
            warnings.append(
                f"{len(methods_with_many_calls)} método(s) possuem alta densidade de chamadas."
            )

        return warnings

    def _detect_method_notes(self, method: MethodInfo) -> List[str]:
        notes: List[str] = []
        body = method.body

        if "$_GET" in body or "$_POST" in body or "$_REQUEST" in body:
            notes.append("Usa superglobais de entrada diretamente.")

        if "header(" in body or "echo " in body or "print " in body:
            notes.append("Possível mistura de regra de negócio com saída HTTP/UI.")

        if method.sql_blocks:
            notes.append("Executa ou monta SQL dentro do método.")

        if any("Persistencia" in n.class_name for n in method.new_instances):
            notes.append("Instancia camada de persistência diretamente.")

        if any("Fachada" in n.class_name for n in method.new_instances):
            notes.append("Encadeia chamadas com outras fachadas.")

        if len(method.calls) + len(method.static_calls) > 15:
            notes.append("Alta densidade de chamadas; fluxo potencialmente complexo.")

        return notes

    # -----------------------------------------------------
    # Utils
    # -----------------------------------------------------

    def _line_char_offsets(self, lines: List[str]) -> List[int]:
        offsets = []
        current = 0
        for line in lines:
            offsets.append(current)
            current += len(line) + 1
        return offsets

    def _dedupe_new_instances(self, items: List[NewClassInfo]) -> List[NewClassInfo]:
        seen = set()
        result = []
        for item in items:
            key = (item.class_name, item.line)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _dedupe_static_calls(self, items: List[StaticCallInfo]) -> List[StaticCallInfo]:
        seen = set()
        result = []
        for item in items:
            key = (item.class_name, item.method, item.line)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _dedupe_method_calls(self, items: List[MethodCallInfo]) -> List[MethodCallInfo]:
        seen = set()
        result = []
        for item in items:
            key = (item.target, item.method, item.line)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _dedupe_sql_blocks(self, items: List[SqlBlockInfo]) -> List[SqlBlockInfo]:
        seen = set()
        result = []
        for item in items:
            key = (item.sql, item.line)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result