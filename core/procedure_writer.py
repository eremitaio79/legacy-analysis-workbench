from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.config import SIGPLAN_OUTPUT_DIR, SIGPLAN_REPORT_DIR


class ProcedureWriter:
    """
    Gera relatório Markdown para análise de stored procedures.
    """

    def __init__(self, output_dir: str | Path | None = None) -> None:
        if output_dir is None:
            output_dir = Path(SIGPLAN_OUTPUT_DIR) / SIGPLAN_REPORT_DIR

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, analysis: Dict[str, Any]) -> Path:
        schema = analysis.get("schema", "_dbo")
        procedure = analysis.get("procedure", "procedure")
        safe_name = self._safe_filename(f"{schema}.{procedure}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = f"procedure_{safe_name}_{timestamp}.md"
        output_path = self.output_dir / filename

        content = self.render(analysis)
        output_path.write_text(content, encoding="utf-8")

        return output_path

    def render(self, analysis: Dict[str, Any]) -> str:
        procedure = analysis.get("procedure", "-")
        schema = analysis.get("schema", "-")
        environment = analysis.get("environment", "-")
        created_at = analysis.get("created_at", "-")
        modified_at = analysis.get("modified_at", "-")
        object_id = analysis.get("object_id", "-")
        lines = analysis.get("lines", 0)
        parameter_count = analysis.get("parameter_count", 0)
        classification = analysis.get("classification", "-")
        operations = analysis.get("operations", []) or []
        warnings = analysis.get("warnings", []) or []
        sql_text = analysis.get("sql_text", "") or ""

        tables = analysis.get("tables", {}) or {}
        calls = analysis.get("calls", {}) or {}
        resources = analysis.get("resources", {}) or {}
        catalog_dependencies = analysis.get("catalog_dependencies", {}) or {}
        parameters = analysis.get("parameters", []) or []
        variables = analysis.get("variables", []) or []

        read_tables = tables.get("read", []) or []
        write_tables = tables.get("write", []) or []
        all_tables = tables.get("all", []) or []
        temp_tables = tables.get("temp", []) or []
        table_variables = tables.get("table_variables", []) or []

        procedure_calls = calls.get("procedures", []) or []
        function_calls = calls.get("functions", []) or []
        dependency_objects = catalog_dependencies.get("objects", []) or []
        queries_extracted = analysis.get("queries_extracted", {}) or {}
        ai_commentary = analysis.get("ai_commentary", "") or ""

        md: List[str] = []

        md.append(f"# Análise de Procedure: `{schema}.{procedure}`")
        md.append("")
        md.append("## Resumo")
        md.append("")
        md.append(f"- **Ambiente:** {environment}")
        md.append(f"- **Schema:** {schema}")
        md.append(f"- **Procedure:** {procedure}")
        md.append(f"- **Object ID:** {object_id}")
        md.append(f"- **Criada em:** {created_at}")
        md.append(f"- **Modificada em:** {modified_at}")
        md.append(f"- **Linhas:** {lines}")
        md.append(f"- **Qtd. de parâmetros:** {parameter_count}")
        md.append(f"- **Qtd. de tabelas detectadas:** {len(all_tables)}")
        md.append(f"- **Qtd. de procedures chamadas:** {len(procedure_calls)}")
        md.append(f"- **Qtd. de funções chamadas:** {len(function_calls)}")
        md.append(f"- **Classificação:** `{classification}`")
        md.append(f"- **Operações detectadas:** {', '.join(operations) if operations else '-'}")
        md.append("")

        md.append("## Parâmetros")
        md.append("")
        if parameters:
            md.append("| Nome | Tipo | Output | Default |")
            md.append("|---|---|---:|---:|")
            for param in parameters:
                md.append(
                    f"| `{param.get('name', '-')}` "
                    f"| `{param.get('data_type', '-')}` "
                    f"| {'Sim' if param.get('is_output') else 'Não'} "
                    f"| {'Sim' if param.get('has_default') else 'Não'} |"
                )
        else:
            md.append("_Nenhum parâmetro encontrado._")
        md.append("")

        md.append("## Tabelas Envolvidas")
        md.append("")
        md.append(f"- **Leitura:** {len(read_tables)}")
        md.append(f"- **Escrita:** {len(write_tables)}")
        md.append(f"- **Temporárias:** {len(temp_tables)}")
        md.append(f"- **Table variables:** {len(table_variables)}")
        md.append("")

        md.append("### Tabelas de leitura")
        md.append("")
        md.extend(self._render_bullet_list(read_tables, empty="_Nenhuma tabela de leitura detectada._"))
        md.append("")

        md.append("### Tabelas de escrita")
        md.append("")
        md.extend(self._render_bullet_list(write_tables, empty="_Nenhuma tabela de escrita detectada._"))
        md.append("")

        md.append("### Temp tables")
        md.append("")
        md.extend(self._render_bullet_list(temp_tables, empty="_Nenhuma temp table detectada._"))
        md.append("")

        md.append("### Table variables")
        md.append("")
        md.extend(self._render_bullet_list(table_variables, empty="_Nenhuma table variable detectada._"))
        md.append("")

        md.append("## Dependências")
        md.append("")

        md.append("### Procedures chamadas")
        md.append("")
        md.extend(self._render_bullet_list(procedure_calls, empty="_Nenhuma chamada de procedure detectada._"))
        md.append("")

        md.append("### Funções chamadas")
        md.append("")
        md.extend(self._render_bullet_list(function_calls, empty="_Nenhuma função detectada._"))
        md.append("")

        md.append("### Dependências catalogadas")
        md.append("")
        md.extend(self._render_bullet_list(dependency_objects, empty="_Nenhuma dependência catalogada encontrada._"))
        md.append("")

        md.append("## Recursos SQL Detectados")
        md.append("")
        if resources:
            md.append("| Recurso | Detectado |")
            md.append("|---|---:|")
            for label, value in self._resource_rows(resources):
                md.append(f"| {label} | {'Sim' if value else 'Não'} |")
        else:
            md.append("_Nenhum recurso analisado._")
        md.append("")

        md.append("## Variáveis Declaradas")
        md.append("")
        md.extend(self._render_bullet_list(variables, empty="_Nenhuma variável declarada detectada._"))
        md.append("")

        md.append("## Pontos de Atenção")
        md.append("")
        if warnings:
            for warning in warnings:
                md.append(f"- ⚠️ {warning}")
        else:
            md.append("_Nenhum warning relevante encontrado._")
        md.append("")

        md.append("## Observações Técnicas")
        md.append("")
        md.append("- Esta análise é **estática** e foi feita apenas por leitura de metadados e definição SQL.")
        md.append("- A ferramenta **não executa a procedure**.")
        md.append("- Dependências em SQL dinâmico podem não ser totalmente detectadas.")
        md.append("- Regras baseadas em regex podem gerar falsos positivos ou não capturar todos os casos complexos.")
        md.append("")

        md.append("## Queries Extraídas")
        md.append("")

        self._append_query_blocks(md, "SELECT", queries_extracted.get("select", []))
        self._append_query_blocks(md, "INSERT", queries_extracted.get("insert", []))
        self._append_query_blocks(md, "UPDATE", queries_extracted.get("update", []))
        self._append_query_blocks(md, "DELETE", queries_extracted.get("delete", []))
        self._append_query_blocks(md, "MERGE", queries_extracted.get("merge", []))


        md.append("## Comentário Técnico com IA")
        md.append("")

        if ai_commentary.strip():
            md.append(ai_commentary.strip())
        else:
            md.append("_Nenhum comentário com IA foi gerado._")
        md.append("")


        md.append("## SQL da Procedure")
        md.append("")
        md.append("```sql")
        md.append(sql_text.rstrip())
        md.append("```")
        md.append("")

        return "\n".join(md).rstrip() + "\n"

    def _render_bullet_list(self, items: Iterable[str], empty: str) -> List[str]:
        items = list(items)
        if not items:
            return [empty]
        return [f"- `{item}`" for item in items]

    def _resource_rows(self, resources: Dict[str, Any]) -> List[tuple[str, bool]]:
        ordered_labels = [
            ("dynamic_sql", "SQL dinâmico"),
            ("cursor", "Cursor"),
            ("transaction", "Transações"),
            ("try_catch", "TRY/CATCH"),
            ("nolock", "NOLOCK"),
            ("temp_tables", "Temp tables"),
            ("table_variables", "Table variables"),
            ("merge", "MERGE"),
            ("cte", "CTE"),
        ]

        rows: List[tuple[str, bool]] = []
        for key, label in ordered_labels:
            rows.append((label, bool(resources.get(key))))
        return rows

    def _safe_filename(self, value: str) -> str:
        allowed = []
        for char in value:
            if char.isalnum() or char in {"-", "_", "."}:
                allowed.append(char)
            else:
                allowed.append("_")
        return "".join(allowed).strip("._") or "procedure"


    def _append_query_blocks(self, md: List[str], title: str, queries: List[str]) -> None:
        md.append(f"### {title}")
        md.append("")

        if not queries:
            md.append("_Nenhuma query extraída._")
            md.append("")
            return

        for idx, query in enumerate(queries, start=1):
            md.append(f"#### {title} #{idx}")
            md.append("")
            md.append("```sql")
            md.append(query.rstrip())
            md.append("```")
            md.append("")