from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
class ModelFieldInfo:
    property_name: str
    visibility: str
    line: int
    db_field: Optional[str] = None
    var_type: Optional[str] = None
    is_primary: Optional[bool] = None
    is_nullable: Optional[bool] = None
    is_auto_increment: Optional[bool] = None
    raw_docblock: str = ""
    annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class ModelMethodInfo:
    name: str
    method_type: str  # getter | setter | other
    line: int
    related_property: Optional[str] = None


@dataclass
class ModelAnalysisResult:
    input_value: str
    resolved_path: str
    class_name: Optional[str]
    package: Optional[str]
    author: Optional[str]
    sgbd: Optional[str]
    table_name: Optional[str]
    total_lines: int
    fields: List[ModelFieldInfo] = field(default_factory=list)
    methods: List[ModelMethodInfo] = field(default_factory=list)
    getters: List[str] = field(default_factory=list)
    setters: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================
# Analyzer
# =========================================================


class ModelAnalyzer:
    """
    Analisador de models do SIGBOARD.

    Entradas suportadas:
    - nome da classe/model: ex. Acaodetalhada
    - caminho direto do arquivo PHP
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()

    # -----------------------------------------------------
    # API pública
    # -----------------------------------------------------

    def analyze(self, target: str) -> ModelAnalysisResult:
        resolved_path = self._resolve_target(target)

        if not resolved_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {resolved_path}")

        content = resolved_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[yellow]{task.fields[current_item]}[/yellow]"),
            TimeElapsedColumn(),
            transient=False,
        ) as progress:
            main_task = progress.add_task(
                "Analisando model...",
                total=7,
                current_item="iniciando...",
            )

            class_name = self._extract_class_name(content)
            progress.update(main_task, current_item=class_name or "classe não identificada")
            progress.advance(main_task)

            header_meta = self._extract_header_metadata(content)
            progress.update(main_task, current_item="metadados do cabeçalho")
            progress.advance(main_task)

            fields = self._extract_fields(lines, progress)
            progress.update(main_task, current_item=f"{len(fields)} campo(s) encontrado(s)")
            progress.advance(main_task)

            methods = self._extract_methods(lines, progress)
            progress.update(main_task, current_item=f"{len(methods)} método(s) encontrado(s)")
            progress.advance(main_task)

            getters = [m.name for m in methods if m.method_type == "getter"]
            setters = [m.name for m in methods if m.method_type == "setter"]
            progress.update(main_task, current_item="getters / setters")
            progress.advance(main_task)

            warnings = self._build_warnings(class_name, header_meta, fields, methods)
            progress.update(main_task, current_item=f"{len(warnings)} warning(s)")
            progress.advance(main_task)

            progress.update(main_task, current_item="concluído")
            progress.advance(main_task)

        return ModelAnalysisResult(
            input_value=target,
            resolved_path=str(resolved_path),
            class_name=class_name,
            package=header_meta.get("package"),
            author=header_meta.get("author"),
            sgbd=header_meta.get("sgbd"),
            table_name=header_meta.get("tabela"),
            total_lines=len(lines),
            fields=fields,
            methods=methods,
            getters=getters,
            setters=setters,
            warnings=warnings,
        )

    # -----------------------------------------------------
    # Resolução do alvo
    # -----------------------------------------------------

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

        preferred_paths: List[Path] = []
        fallback_paths: List[Path] = []

        for path in self.base_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in PHP_EXTENSIONS:
                continue

            path_str = str(path).lower()

            if any(token in path_str for token in ("modelo", "model")):
                preferred_paths.append(path)
            else:
                fallback_paths.append(path)

        search_order = preferred_paths + fallback_paths

        for path in search_order:
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
                f"Não foi possível localizar o model '{class_name}' em {self.base_dir}"
            )

        exact_name = [p for p in candidates if p.stem.lower() == class_name.lower()]
        if exact_name:
            return exact_name[0]

        return candidates[0]

    # -----------------------------------------------------
    # Extrações principais
    # -----------------------------------------------------

    def _extract_class_name(self, content: str) -> Optional[str]:
        match = re.search(
            r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
            content,
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _extract_header_metadata(self, content: str) -> Dict[str, Optional[str]]:
        """
        Extrai metadados do docblock principal da classe.
        """
        result = {
            "author": None,
            "package": None,
            "sgbd": None,
            "tabela": None,
        }

        class_match = re.search(r"\bclass\s+[A-Za-z_][A-Za-z0-9_]*", content, flags=re.IGNORECASE)
        if not class_match:
            return result

        prefix = content[: class_match.start()]
        docblocks = re.findall(r"/\*\*(.*?)\*/", prefix, flags=re.DOTALL)
        if not docblocks:
            return result

        header = docblocks[-1]

        result["author"] = self._extract_annotation_value(header, "author")
        result["package"] = self._extract_annotation_value(header, "package")
        result["sgbd"] = self._extract_annotation_value(header, "SGBD")
        result["tabela"] = self._extract_annotation_value(header, "tabela")

        return result

    def _extract_fields(self, lines: List[str], progress: Progress) -> List[ModelFieldInfo]:
        """
        Captura propriedades e associa o docblock imediatamente anterior.
        """
        fields: List[ModelFieldInfo] = []

        property_pattern = re.compile(
            r"^\s*(private|protected|public)\s+\$([A-Za-z_][A-Za-z0-9_]*)\s*;",
            flags=re.IGNORECASE,
        )

        docblock_ranges = self._collect_docblock_ranges(lines)

        property_candidates: List[Tuple[int, str, str]] = []
        for idx, line in enumerate(lines, start=1):
            match = property_pattern.search(line)
            if match:
                property_candidates.append((idx, match.group(1).lower(), match.group(2)))

        field_task = progress.add_task(
            "Mapeando campos do model...",
            total=max(len(property_candidates), 1),
            current_item="procurando propriedades...",
        )

        if not property_candidates:
            progress.update(field_task, current_item="nenhuma propriedade encontrada")
            return fields

        for idx, (line_no, visibility, property_name) in enumerate(property_candidates, start=1):
            progress.update(
                field_task,
                description="Mapeando campos do model...",
                current_item=f"[{idx}/{len(property_candidates)}] analisando ${property_name} na linha {line_no}",
            )

            raw_docblock = self._find_docblock_for_line(line_no, docblock_ranges)
            annotations = self._parse_docblock_annotations(raw_docblock) if raw_docblock else {}

            field = ModelFieldInfo(
                property_name=property_name,
                visibility=visibility,
                line=line_no,
                db_field=annotations.get("campo"),
                var_type=annotations.get("var"),
                is_primary=self._parse_bool_annotation(annotations.get("primario")),
                is_nullable=self._parse_bool_annotation(annotations.get("nulo")),
                is_auto_increment=self._parse_bool_annotation(annotations.get("auto-increment")),
                raw_docblock=raw_docblock or "",
                annotations=annotations,
            )

            fields.append(field)
            progress.advance(field_task)

        progress.update(field_task, current_item="varredura de campos concluída")
        return fields

    def _extract_methods(self, lines: List[str], progress: Progress) -> List[ModelMethodInfo]:
        methods: List[ModelMethodInfo] = []

        method_pattern = re.compile(
            r"^\s*(public|protected|private)\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            flags=re.IGNORECASE,
        )

        method_candidates: List[Tuple[int, str]] = []
        for idx, line in enumerate(lines, start=1):
            match = method_pattern.search(line)
            if match:
                method_candidates.append((idx, match.group(2)))

        method_task = progress.add_task(
            "Mapeando métodos do model...",
            total=max(len(method_candidates), 1),
            current_item="procurando métodos...",
        )

        if not method_candidates:
            progress.update(method_task, current_item="nenhum método encontrado")
            return methods

        for idx, (line_no, method_name) in enumerate(method_candidates, start=1):
            progress.update(
                method_task,
                description="Mapeando métodos do model...",
                current_item=f"[{idx}/{len(method_candidates)}] analisando {method_name}() na linha {line_no}",
            )

            method_type, related_property = self._classify_method(method_name)

            methods.append(
                ModelMethodInfo(
                    name=method_name,
                    method_type=method_type,
                    line=line_no,
                    related_property=related_property,
                )
            )
            progress.advance(method_task)

        progress.update(method_task, current_item="varredura de métodos concluída")
        return methods

    # -----------------------------------------------------
    # Docblocks
    # -----------------------------------------------------

    def _collect_docblock_ranges(self, lines: List[str]) -> List[Tuple[int, int, str]]:
        """
        Retorna lista de docblocks no formato:
        (linha_inicial, linha_final, conteudo_completo)
        """
        ranges: List[Tuple[int, int, str]] = []
        in_block = False
        start_line = 0
        buffer: List[str] = []

        for idx, line in enumerate(lines, start=1):
            if not in_block and "/**" in line:
                in_block = True
                start_line = idx
                buffer = [line]
                if "*/" in line:
                    ranges.append((start_line, idx, "\n".join(buffer)))
                    in_block = False
                    buffer = []
                continue

            if in_block:
                buffer.append(line)
                if "*/" in line:
                    ranges.append((start_line, idx, "\n".join(buffer)))
                    in_block = False
                    buffer = []

        return ranges

    def _find_docblock_for_line(
        self,
        property_line: int,
        docblock_ranges: List[Tuple[int, int, str]],
    ) -> Optional[str]:
        """
        Procura docblock imediatamente anterior à propriedade.
        Aceita apenas com distância curta, para evitar associações erradas.
        """
        best_match: Optional[str] = None
        best_end_line = -1

        for start, end, content in docblock_ranges:
            if end < property_line and (property_line - end) <= 2:
                if end > best_end_line:
                    best_end_line = end
                    best_match = content

        return best_match

    def _parse_docblock_annotations(self, docblock: str) -> Dict[str, str]:
        annotations: Dict[str, str] = {}

        if not docblock:
            return annotations

        pattern = re.compile(r"@\s*([A-Za-z0-9_\-]+)\s+(.+)")
        for raw_line in docblock.splitlines():
            line = raw_line.strip().lstrip("*").strip()
            if not line.startswith("@"):
                continue

            match = pattern.match(line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                annotations[key] = value

        return annotations

    def _extract_annotation_value(self, docblock: str, annotation_name: str) -> Optional[str]:
        annotations = self._parse_docblock_annotations(docblock)
        return annotations.get(annotation_name)

    # -----------------------------------------------------
    # Regras auxiliares
    # -----------------------------------------------------

    def _parse_bool_annotation(self, value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None

        normalized = value.strip().lower()
        if normalized in {"true", "1", "sim", "yes"}:
            return True
        if normalized in {"false", "0", "nao", "não", "no"}:
            return False
        return None

    def _classify_method(self, method_name: str) -> Tuple[str, Optional[str]]:
        lowered = method_name.lower()

        if lowered.startswith("get") and len(method_name) > 3:
            return "getter", self._guess_property_from_accessor(method_name[3:])

        if lowered.startswith("set") and len(method_name) > 3:
            return "setter", self._guess_property_from_accessor(method_name[3:])

        return "other", None

    def _guess_property_from_accessor(self, suffix: str) -> Optional[str]:
        if not suffix:
            return None

        normalized = suffix[0].lower() + suffix[1:]
        return normalized

    # -----------------------------------------------------
    # Warnings
    # -----------------------------------------------------

    def _build_warnings(
        self,
        class_name: Optional[str],
        header_meta: Dict[str, Optional[str]],
        fields: List[ModelFieldInfo],
        methods: List[ModelMethodInfo],
    ) -> List[str]:
        warnings: List[str] = []

        if not class_name:
            warnings.append("Classe principal não identificada no arquivo.")

        if not header_meta.get("tabela"):
            warnings.append("Metadado @tabela não identificado no cabeçalho da classe.")

        if not header_meta.get("sgbd"):
            warnings.append("Metadado @SGBD não identificado no cabeçalho da classe.")

        if not fields:
            warnings.append("Nenhuma propriedade de model foi encontrada.")

        primary_fields = [f for f in fields if f.is_primary is True]
        auto_increment_fields = [f for f in fields if f.is_auto_increment is True]

        if not primary_fields and fields:
            warnings.append("Nenhum campo primário foi identificado.")

        if len(primary_fields) > 1:
            warnings.append(f"{len(primary_fields)} campos marcados como primários foram encontrados.")

        for field in fields:
            if not field.raw_docblock:
                warnings.append(
                    f"A propriedade ${field.property_name} (linha {field.line}) não possui docblock associado."
                )
                continue

            if not field.db_field:
                warnings.append(
                    f"A propriedade ${field.property_name} (linha {field.line}) não possui anotação @campo."
                )

            if not field.var_type:
                warnings.append(
                    f"A propriedade ${field.property_name} (linha {field.line}) não possui anotação @var."
                )

            if field.is_auto_increment is True and field.is_primary is not True:
                warnings.append(
                    f"A propriedade ${field.property_name} (linha {field.line}) está com auto-increment=true sem ser primária."
                )

        setter_count = sum(1 for m in methods if m.method_type == "setter")
        getter_count = sum(1 for m in methods if m.method_type == "getter")

        if methods and getter_count == 0 and setter_count == 0:
            warnings.append("Nenhum getter/setter foi identificado no model.")

        if auto_increment_fields and len(auto_increment_fields) > 1:
            warnings.append(
                f"{len(auto_increment_fields)} campos marcados como auto-increment foram encontrados."
            )

        return self._dedupe_list(warnings)

    # -----------------------------------------------------
    # Utils
    # -----------------------------------------------------

    def _dedupe_list(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result