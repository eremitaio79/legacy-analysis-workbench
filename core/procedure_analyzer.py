from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Set


@dataclass
class ProcedureParameter:
    name: str
    data_type: str
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    is_output: bool = False
    has_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcedureMetadata:
    procedure: str
    schema: str
    object_id: int
    created_at: Optional[str]
    modified_at: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcedureAnalyzer:
    """
    Analisa stored procedures do SQL Server de forma segura, sem executá-las.
    Faz leitura apenas de metadados e definição SQL.
    """

    LARGE_PROCEDURE_LINE_THRESHOLD = 300
    TEMP_TABLE_HEAVY_THRESHOLD = 5

    def _clean_sql_statement(self, stmt: str) -> str:
        stmt = stmt.strip()
        if not stmt:
            return ""

        lines = [line.rstrip() for line in stmt.splitlines()]
        lines = [line for line in lines if line.strip()]

        while lines and lines[0].strip().upper() in {"BEGIN", "END"}:
            lines.pop(0)

        while lines and lines[-1].strip().upper() in {"BEGIN", "END"}:
            lines.pop()

        return "\n".join(lines).strip()

    def _extract_sql_statements(self, sql_text: str) -> Dict[str, List[str]]:
        """
        Extrai blocos SQL principais da procedure.
        Heurística inicial baseada em comandos principais.
        """
        result = {
            "select": [],
            "insert": [],
            "update": [],
            "delete": [],
            "merge": [],
        }

        patterns = {
            "select": r"(?is)\bSELECT\b.*?(?=\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMERGE\b|\Z)",
            "insert": r"(?is)\bINSERT\b.*?(?=\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMERGE\b|\Z)",
            "update": r"(?is)\bUPDATE\b.*?(?=\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMERGE\b|\Z)",
            "delete": r"(?is)\bDELETE\b.*?(?=\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMERGE\b|\Z)",
            "merge": r"(?is)\bMERGE\b.*?(?=\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMERGE\b|\Z)",
        }

        for key, pattern in patterns.items():
            matches = re.findall(pattern, sql_text, flags=re.IGNORECASE | re.DOTALL)
            cleaned_items: List[str] = []
            seen: Set[str] = set()

            for match in matches:
                stmt = self._clean_sql_statement(match)
                if not stmt:
                    continue

                normalized = re.sub(r"\s+", " ", stmt).strip().upper()
                if normalized in seen:
                    continue

                seen.add(normalized)
                cleaned_items.append(stmt)

            result[key] = cleaned_items

        return result


    def __init__(self, connection, environment: str = "unknown"):
        """
        connection: conexão pyodbc já aberta
        environment: identificador do ambiente (homolog/prod/etc)
        """
        self.connection = connection
        self.environment = environment

    # =========================================================
    # API pública
    # =========================================================
    def analyze(self, procedure_name: str) -> Dict[str, Any]:
        """
        Faz análise completa da procedure.
        Aceita:
          - usp_MinhaProcedure
          - _dbo.usp_MinhaProcedure
          - [_dbo].[usp_MinhaProcedure]
        """
        normalized = self._normalize_procedure_name(procedure_name)
        proc_row = self._fetch_procedure_metadata(normalized)

        if not proc_row:
            raise ValueError(
                f"Procedure '{procedure_name}' não encontrada no banco '{self.environment}'."
            )

        metadata = ProcedureMetadata(
            procedure=proc_row["procedure"],
            schema=proc_row["schema"],
            object_id=proc_row["object_id"],
            created_at=str(proc_row["created_at"]) if proc_row["created_at"] else None,
            modified_at=str(proc_row["modified_at"]) if proc_row["modified_at"] else None,
        )

        sql_text = self._fetch_procedure_definition(metadata.object_id)
        if not sql_text:
            raise ValueError(
                f"Não foi possível obter a definição SQL da procedure '{metadata.schema}.{metadata.procedure}'."
            )

        parameters = self._fetch_procedure_parameters(metadata.object_id)
        dependencies = self._fetch_catalog_dependencies(metadata.object_id)

        parsed = self._analyze_sql_text(sql_text)
        warnings = self._build_warnings(parsed)

        result = {
            "environment": self.environment,
            "procedure": metadata.procedure,
            "schema": metadata.schema,
            "object_id": metadata.object_id,
            "created_at": metadata.created_at,
            "modified_at": metadata.modified_at,
            "lines": parsed["line_count"],
            "parameter_count": len(parameters),
            "parameters": [p.to_dict() for p in parameters],
            "tables": {
                "read": sorted(parsed["tables_read"]),
                "write": sorted(parsed["tables_write"]),
                "all": sorted(parsed["tables_all"]),
                "temp": sorted(parsed["temp_tables"]),
                "table_variables": sorted(parsed["table_variables"]),
            },
            "calls": {
                "procedures": sorted(parsed["procedure_calls"]),
                "functions": sorted(parsed["function_calls"]),
            },
            "catalog_dependencies": dependencies,
            "operations": sorted(parsed["operations"]),
            "queries_extracted": parsed["queries_extracted"],
            "resources": parsed["resources"],
            "variables": sorted(parsed["variables"]),
            "classification": self._classify_procedure(parsed["operations"]),
            "warnings": warnings,
            "sql_text": sql_text,
        }

        return result

    # =========================================================
    # Banco - metadados
    # =========================================================
    def _fetch_procedure_metadata(self, procedure_name: str) -> Optional[Dict[str, Any]]:
        """
        Busca a procedure por nome simples ou schema.nome
        """
        schema_name, proc_name = self._split_schema_and_name(procedure_name)

        cursor = self.connection.cursor()

        if schema_name:
            query = """
                SELECT
                    p.object_id,
                    p.name AS procedure_name,
                    s.name AS schema_name,
                    p.create_date,
                    p.modify_date
                FROM sys.procedures p
                INNER JOIN sys.schemas s
                    ON s.schema_id = p.schema_id
                WHERE p.name = ?
                  AND s.name = ?
            """
            cursor.execute(query, (proc_name, schema_name))
        else:
            query = """
                SELECT
                    p.object_id,
                    p.name AS procedure_name,
                    s.name AS schema_name,
                    p.create_date,
                    p.modify_date
                FROM sys.procedures p
                INNER JOIN sys.schemas s
                    ON s.schema_id = p.schema_id
                WHERE p.name = ?
                ORDER BY
                    CASE WHEN s.name = '_dbo' THEN 0 ELSE 1 END,
                    s.name
            """
            cursor.execute(query, (proc_name,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "object_id": row.object_id,
            "procedure": row.procedure_name,
            "schema": row.schema_name,
            "created_at": row.create_date,
            "modified_at": row.modify_date,
        }

    def _fetch_procedure_definition(self, object_id: int) -> str:
        query = """
            SELECT sm.definition
            FROM sys.sql_modules sm
            WHERE sm.object_id = ?
        """
        cursor = self.connection.cursor()
        cursor.execute(query, (object_id,))
        row = cursor.fetchone()
        return row.definition if row and row.definition else ""

    def _fetch_procedure_parameters(self, object_id: int) -> List[ProcedureParameter]:
        query = """
            SELECT
                p.name AS parameter_name,
                t.name AS data_type,
                p.max_length,
                p.precision,
                p.scale,
                p.is_output,
                p.has_default_value
            FROM sys.parameters p
            INNER JOIN sys.types t
                ON p.user_type_id = t.user_type_id
            WHERE p.object_id = ?
            ORDER BY p.parameter_id
        """
        cursor = self.connection.cursor()
        cursor.execute(query, (object_id,))
        rows = cursor.fetchall()

        params: List[ProcedureParameter] = []
        for row in rows:
            params.append(
                ProcedureParameter(
                    name=row.parameter_name,
                    data_type=self._format_sql_type(
                        row.data_type,
                        row.max_length,
                        row.precision,
                        row.scale,
                    ),
                    max_length=row.max_length,
                    precision=row.precision,
                    scale=row.scale,
                    is_output=bool(row.is_output),
                    has_default=bool(row.has_default_value),
                )
            )
        return params

    def _fetch_catalog_dependencies(self, object_id: int) -> Dict[str, List[str]]:
        """
        Dependências catalogadas pelo SQL Server.
        Nem sempre pega tudo, especialmente SQL dinâmico,
        mas ajuda bastante.
        """
        query = """
            SELECT
                COALESCE(OBJECT_SCHEMA_NAME(d.referenced_id), d.referenced_schema_name) AS referenced_schema,
                COALESCE(OBJECT_NAME(d.referenced_id), d.referenced_entity_name) AS referenced_name
            FROM sys.sql_expression_dependencies d
            WHERE d.referencing_id = ?
        """
        cursor = self.connection.cursor()
        cursor.execute(query, (object_id,))
        rows = cursor.fetchall()

        deps: Set[str] = set()
        for row in rows:
            schema_name = row.referenced_schema
            entity_name = row.referenced_name
            if entity_name:
                full_name = f"{schema_name}.{entity_name}" if schema_name else entity_name
                deps.add(full_name)

        return {
            "objects": sorted(deps)
        }

    # =========================================================
    # Parser SQL
    # =========================================================
    def _analyze_sql_text(self, sql_text: str) -> Dict[str, Any]:
        clean_sql = self._strip_comments(sql_text)
        upper_sql = clean_sql.upper()

        operations = self._detect_operations(upper_sql)

        tables_read = self._extract_read_tables(clean_sql)
        tables_write = self._extract_write_tables(clean_sql)
        temp_tables = self._extract_temp_tables(clean_sql)
        table_variables = self._extract_table_variables(clean_sql)
        variables = self._extract_variables(clean_sql)
        procedure_calls = self._extract_procedure_calls(clean_sql)
        function_calls = self._extract_function_calls(clean_sql)

        queries_extracted = self._extract_sql_statements(clean_sql)

        resources = {
            "dynamic_sql": self._detect_dynamic_sql(upper_sql),
            "cursor": bool(re.search(r"\bCURSOR\b", upper_sql)),
            "transaction": bool(
                re.search(r"\bBEGIN\s+TRAN\b|\bBEGIN\s+TRANSACTION\b|\bCOMMIT\b|\bROLLBACK\b", upper_sql)
            ),
            "try_catch": bool(re.search(r"\bBEGIN\s+TRY\b.*\bBEGIN\s+CATCH\b", upper_sql, re.DOTALL)),
            "nolock": bool(re.search(r"\bNOLOCK\b", upper_sql)),
            "temp_tables": bool(temp_tables),
            "table_variables": bool(table_variables),
            "merge": "MERGE" in operations,
            "cte": bool(re.search(r"\bWITH\s+[A-Z_][A-Z0-9_]*\s+AS\s*\(", upper_sql)),
        }

        lines = [line for line in sql_text.splitlines() if line.strip()]

        return {
            "line_count": len(lines),
            "operations": operations,
            "tables_read": tables_read,
            "tables_write": tables_write,
            "tables_all": set(tables_read) | set(tables_write),
            "temp_tables": temp_tables,
            "table_variables": table_variables,
            "variables": variables,
            "procedure_calls": procedure_calls,
            "function_calls": function_calls,
            "queries_extracted": queries_extracted,
            "resources": resources,
            "update_without_where": self._detect_update_without_where(clean_sql),
            "delete_without_where": self._detect_delete_without_where(clean_sql),
        }

    def _detect_operations(self, upper_sql: str) -> Set[str]:
        ops = set()

        if re.search(r"\bSELECT\b", upper_sql):
            ops.add("SELECT")
        if re.search(r"\bINSERT\s+INTO\b", upper_sql):
            ops.add("INSERT")
        if re.search(r"\bUPDATE\b", upper_sql):
            ops.add("UPDATE")
        if re.search(r"\bDELETE\b", upper_sql):
            ops.add("DELETE")
        if re.search(r"\bMERGE\b", upper_sql):
            ops.add("MERGE")

        return ops

    def _extract_read_tables(self, sql_text: str) -> Set[str]:
        tables = set()

        patterns = [
            r"\bFROM\s+([#@\[\]\w\.]+)",
            r"\bJOIN\s+([#@\[\]\w\.]+)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
                table_name = self._clean_identifier(match.group(1))
                if self._is_valid_table_reference(table_name):
                    tables.add(table_name)

        return tables

    def _extract_write_tables(self, sql_text: str) -> Set[str]:
        tables = set()

        patterns = [
            r"\bINSERT\s+INTO\s+([#@\[\]\w\.]+)",
            r"\bUPDATE\s+([#@\[\]\w\.]+)",
            r"\bDELETE\s+FROM\s+([#@\[\]\w\.]+)",
            r"\bMERGE\s+([#@\[\]\w\.]+)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
                table_name = self._clean_identifier(match.group(1))
                if self._is_valid_table_reference(table_name):
                    tables.add(table_name)

        return tables

    def _extract_temp_tables(self, sql_text: str) -> Set[str]:
        found = set()

        for match in re.finditer(r"(?<!\w)(##?\w+)", sql_text, flags=re.IGNORECASE):
            found.add(match.group(1))

        return found

    def _extract_table_variables(self, sql_text: str) -> Set[str]:
        """
        Captura table variables declaradas como:
        DECLARE @MinhaTabela TABLE (...)
        """
        found = set()

        pattern = r"\bDECLARE\s+(@\w+)\s+TABLE\b"
        for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
            found.add(match.group(1))

        return found

    def _extract_variables(self, sql_text: str) -> Set[str]:
        found = set()

        for match in re.finditer(r"\bDECLARE\s+(@\w+)", sql_text, flags=re.IGNORECASE):
            found.add(match.group(1))

        return found

    def _extract_procedure_calls(self, sql_text: str) -> Set[str]:
        """
        Detecta chamadas via EXEC / EXECUTE.
        Ignora exec de variáveis.
        """
        found = set()

        pattern = r"\bEXEC(?:UTE)?\s+([a-zA-Z0-9_\.\[\]#]+)"
        for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
            target = self._clean_identifier(match.group(1))
            if target and not target.startswith("@"):
                found.add(target)

        return found

    def _extract_function_calls(self, sql_text: str) -> Set[str]:
        """
        Heurística simples para funções do tipo:
        _dbo.fnAlgo(...)
        schema.func(...)
        """
        found = set()

        pattern = r"\b([a-zA-Z_][\w\[\]]*\.[a-zA-Z_][\w\[\]]*)\s*\("
        for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
            candidate = self._clean_identifier(match.group(1))
            upper_candidate = candidate.upper()

            if upper_candidate not in {
                "TRY_CONVERT",
                "TRY_CAST",
                "CAST",
                "CONVERT",
                "ISNULL",
                "COALESCE",
                "SUM",
                "AVG",
                "MIN",
                "MAX",
                "COUNT",
                "DATEDIFF",
                "DATEADD",
                "GETDATE",
                "IIF",
                "LEFT",
                "RIGHT",
                "SUBSTRING",
                "UPPER",
                "LOWER",
                "RTRIM",
                "LTRIM",
                "ROW_NUMBER",
                "RANK",
                "DENSE_RANK",
            }:
                found.add(candidate)

        return found

    def _detect_dynamic_sql(self, upper_sql: str) -> bool:
        patterns = [
            r"\bSP_EXECUTESQL\b",
            r"\bEXEC\s*\(@",
            r"\bEXECUTE\s*\(@",
            r"\bSET\s+@\w+\s*=\s*['\"]",
            r"\bSELECT\s+@\w+\s*=",
        ]
        return any(re.search(pattern, upper_sql) for pattern in patterns)

    def _detect_update_without_where(self, sql_text: str) -> bool:
        """
        Heurística simples:
        detecta UPDATE ... sem WHERE antes de ponto e vírgula ou fim.
        """
        pattern = r"\bUPDATE\b.*?(?:;|$)"
        for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE | re.DOTALL):
            stmt = match.group(0)
            if " WHERE " not in stmt.upper():
                return True
        return False

    def _detect_delete_without_where(self, sql_text: str) -> bool:
        pattern = r"\bDELETE\b.*?(?:;|$)"
        for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE | re.DOTALL):
            stmt = match.group(0)
            if " WHERE " not in stmt.upper():
                return True
        return False

    def _classify_procedure(self, operations: Set[str]) -> str:
        read_ops = {"SELECT"}
        write_ops = {"INSERT", "UPDATE", "DELETE", "MERGE"}

        has_read = bool(operations & read_ops)
        has_write = bool(operations & write_ops)

        if has_read and has_write:
            return "read_write"
        if has_write:
            return "write"
        return "read"

    def _build_warnings(self, parsed: Dict[str, Any]) -> List[str]:
        warnings: List[str] = []

        if parsed["resources"]["dynamic_sql"]:
            warnings.append("Uso de SQL dinâmico")

        if parsed["resources"]["cursor"]:
            warnings.append("Uso de cursor")

        if parsed["resources"]["transaction"]:
            warnings.append("Uso de transações")

        if parsed["resources"]["temp_tables"] and len(parsed["temp_tables"]) >= self.TEMP_TABLE_HEAVY_THRESHOLD:
            warnings.append("Uso intenso de temp tables")

        if parsed["delete_without_where"]:
            warnings.append("DELETE sem WHERE detectado")

        if parsed["update_without_where"]:
            warnings.append("UPDATE sem WHERE detectado")

        if parsed["line_count"] >= self.LARGE_PROCEDURE_LINE_THRESHOLD:
            warnings.append("Procedure muito grande")

        if len(parsed["procedure_calls"]) >= 5:
            warnings.append("Múltiplas chamadas para outras procedures")

        return warnings

    # =========================================================
    # Helpers
    # =========================================================
    def _normalize_procedure_name(self, name: str) -> str:
        return name.strip().replace("[", "").replace("]", "")

    def _split_schema_and_name(self, full_name: str) -> tuple[Optional[str], str]:
        parts = full_name.split(".")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return None, full_name.strip()

    def _strip_comments(self, sql_text: str) -> str:
        """
        Remove comentários -- e blocos /* */
        """
        sql_text = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
        sql_text = re.sub(r"--.*?$", " ", sql_text, flags=re.MULTILINE)
        return sql_text

    def _clean_identifier(self, raw: str) -> str:
        return raw.strip().rstrip(",;").replace("[", "").replace("]", "")

    def _is_valid_table_reference(self, value: str) -> bool:
        if not value:
            return False

        invalid = {
            "SELECT",
            "FROM",
            "JOIN",
            "INNER",
            "LEFT",
            "RIGHT",
            "FULL",
            "WHERE",
            "ON",
            "SET",
        }

        return value.upper() not in invalid

    def _format_sql_type(
        self,
        data_type: str,
        max_length: Optional[int],
        precision: Optional[int],
        scale: Optional[int],
    ) -> str:
        dt = (data_type or "").lower()

        if dt in {"varchar", "char", "varbinary", "binary"}:
            if max_length == -1:
                return f"{dt}(max)"
            return f"{dt}({max_length})"

        if dt in {"nvarchar", "nchar"}:
            if max_length == -1:
                return f"{dt}(max)"
            if max_length is not None:
                return f"{dt}({max_length // 2})"
            return dt

        if dt in {"decimal", "numeric"}:
            if precision is not None and scale is not None:
                return f"{dt}({precision},{scale})"
            return dt

        if dt in {"datetime2", "time", "datetimeoffset"}:
            if scale is not None:
                return f"{dt}({scale})"
            return dt

        return dt