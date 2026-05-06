from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from core.fachada_analyzer import FachadaAnalysisResult, MethodInfo


def write_fachada_report(
    result: FachadaAnalysisResult,
    output_path: str | Path,
    detailed: bool = True,
    ai_commentary: str | None = None,
) -> Path:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    md = []
    md.append(f"# Fachada Analyzer - {result.class_name or 'Classe não identificada'}")
    md.append("")
    md.append("## Resumo")
    md.append("")
    md.append(f"- **Entrada informada:** `{result.input_value}`")
    md.append(f"- **Arquivo analisado:** `{result.resolved_path}`")
    md.append(f"- **Classe:** `{result.class_name or 'não identificada'}`")
    md.append(f"- **Namespace:** `{result.namespace or 'não identificado'}`")
    md.append(f"- **Total de linhas:** `{result.total_lines}`")
    md.append(f"- **Métodos públicos:** `{result.public_methods_count}`")
    md.append(f"- **Dependências encontradas:** `{len(result.dependencies)}`")
    md.append(f"- **Tabelas encontradas:** `{len(result.tables)}`")
    md.append(f"- **Blocos SQL detectados:** `{len(result.sql_blocks)}`")
    md.append("")

    md.append("## Pontos de atenção")
    md.append("")
    if result.warnings:
        for warning in result.warnings:
            md.append(f"- {warning}")
    else:
        md.append("- Nenhum ponto de atenção automático foi identificado.")
    md.append("")

    md.append("## Métodos públicos")
    md.append("")
    if result.methods:
        for method in result.methods:
            md.extend(_render_method_summary(method))
    else:
        md.append("- Nenhum método público encontrado.")
    md.append("")

    md.append("## Dependências")
    md.append("")
    md.extend(_render_dependencies(result))
    md.append("")

    md.append("## Tabelas envolvidas")
    md.append("")
    if result.tables:
        for table in sorted(set(result.tables)):
            md.append(f"- `{table}`")
    else:
        md.append("- Nenhuma tabela identificada.")
    md.append("")

    md.append("## Métodos com SQL")
    md.append("")
    methods_with_sql = [m for m in result.methods if m.sql_blocks]
    if methods_with_sql:
        for method in methods_with_sql:
            md.append(
                f"- `{method.name}` — {len(method.sql_blocks)} bloco(s) SQL, "
                f"{len(method.tables)} tabela(s) detectada(s)"
            )
    else:
        md.append("- Nenhum método com SQL detectado.")
    md.append("")

    md.append("## Blocos SQL detectados no arquivo")
    md.append("")
    if result.sql_blocks:
        for i, block in enumerate(result.sql_blocks, start=1):
            md.append(f"### SQL #{i}")
            md.append("")
            md.append(f"- **Linha aproximada:** `{block.line}`")
            if block.tables:
                md.append(f"- **Tabelas:** {', '.join(f'`{t}`' for t in block.tables)}")
            else:
                md.append("- **Tabelas:** não identificadas")
            md.append("")
            md.append("```sql")
            md.append(block.sql.strip() if block.sql else "-- SQL vazio --")
            md.append("```")
            md.append("")
    else:
        md.append("- Nenhum bloco SQL identificado no arquivo.")
        md.append("")

    if detailed:
        md.append("## Detalhamento por método")
        md.append("")
        if result.methods:
            for method in result.methods:
                md.extend(_render_method_detail(method))
        else:
            md.append("- Nenhum método público encontrado.")
            md.append("")

    if ai_commentary:
        md.append("## Comentário técnico com IA")
        md.append("")
        md.append(ai_commentary.strip())
        md.append("")

    output_file.write_text("\n".join(md), encoding="utf-8")
    return output_file


def _render_method_summary(method: MethodInfo) -> list[str]:
    lines = []

    assinatura = f"`{method.name}({', '.join(method.parameters)})`" if method.parameters else f"`{method.name}()`"
    lines.append(f"- {assinatura}")
    lines.append(f"  - **Linhas:** `{method.start_line}-{method.end_line}`")
    lines.append(f"  - **Chamadas de método:** `{len(method.calls)}`")
    lines.append(f"  - **Chamadas estáticas:** `{len(method.static_calls)}`")
    lines.append(f"  - **Instâncias criadas:** `{len(method.new_instances)}`")
    lines.append(f"  - **Blocos SQL:** `{len(method.sql_blocks)}`")

    if method.tables:
        tabelas = ", ".join(f"`{t}`" for t in sorted(set(method.tables)))
        lines.append(f"  - **Tabelas:** {tabelas}")
    else:
        lines.append("  - **Tabelas:** nenhuma identificada")

    if method.notes:
        lines.append("  - **Observações:**")
        for note in method.notes:
            lines.append(f"    - {note}")

    lines.append("")
    return lines


def _render_dependencies(result: FachadaAnalysisResult) -> list[str]:
    lines = []

    includes = sorted(set(result.includes))
    requires = sorted(set(result.requires))
    new_classes = sorted(set(x.class_name for x in result.new_instances))
    static_classes = sorted(set(x.class_name for x in result.static_calls))
    all_dependencies = sorted(set(result.dependencies))

    lines.append("### Includes")
    lines.append("")
    if includes:
        for item in includes:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Nenhum include identificado.")
    lines.append("")

    lines.append("### Requires")
    lines.append("")
    if requires:
        for item in requires:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Nenhum require identificado.")
    lines.append("")

    lines.append("### Classes instanciadas com `new`")
    lines.append("")
    if new_classes:
        for item in new_classes:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Nenhuma instância identificada.")
    lines.append("")

    lines.append("### Classes com chamadas estáticas")
    lines.append("")
    if static_classes:
        for item in static_classes:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Nenhuma chamada estática identificada.")
    lines.append("")

    lines.append("### Dependências agregadas")
    lines.append("")
    if all_dependencies:
        for item in all_dependencies:
            lines.append(f"- `{item}`")
    else:
        lines.append("- Nenhuma dependência agregada identificada.")
    lines.append("")

    return lines


def _render_method_detail(method: MethodInfo) -> list[str]:
    lines = []

    assinatura = f"{method.name}({', '.join(method.parameters)})" if method.parameters else f"{method.name}()"

    lines.append(f"### `{assinatura}`")
    lines.append("")
    lines.append(f"- **Visibilidade:** `{method.visibility}`")
    lines.append(f"- **Linha inicial:** `{method.start_line}`")
    lines.append(f"- **Linha final:** `{method.end_line}`")
    lines.append(f"- **Tamanho aproximado:** `{method.end_line - method.start_line + 1}` linha(s)")
    lines.append("")

    lines.append("#### Includes / Requires")
    lines.append("")
    if method.includes:
        lines.append("- **Includes:**")
        for item in method.includes:
            lines.append(f"  - `{item}`")
    else:
        lines.append("- **Includes:** nenhum")

    if method.requires:
        lines.append("- **Requires:**")
        for item in method.requires:
            lines.append(f"  - `{item}`")
    else:
        lines.append("- **Requires:** nenhum")
    lines.append("")

    lines.append("#### Classes instanciadas")
    lines.append("")
    if method.new_instances:
        for item in method.new_instances:
            lines.append(f"- `{item.class_name}` (linha ~{item.line})")
    else:
        lines.append("- Nenhuma instância criada.")
    lines.append("")

    lines.append("#### Chamadas estáticas")
    lines.append("")
    if method.static_calls:
        for item in method.static_calls:
            lines.append(f"- `{item.class_name}::{item.method}()` (linha ~{item.line})")
    else:
        lines.append("- Nenhuma chamada estática.")
    lines.append("")

    lines.append("#### Chamadas de métodos")
    lines.append("")
    if method.calls:
        for item in method.calls:
            lines.append(f"- `{item.target}->{item.method}()` (linha ~{item.line})")
    else:
        lines.append("- Nenhuma chamada de método identificada.")
    lines.append("")

    lines.append("#### Tabelas")
    lines.append("")
    if method.tables:
        for table in sorted(set(method.tables)):
            lines.append(f"- `{table}`")
    else:
        lines.append("- Nenhuma tabela identificada.")
    lines.append("")

    lines.append("#### Observações automáticas")
    lines.append("")
    if method.notes:
        for note in method.notes:
            lines.append(f"- {note}")
    else:
        lines.append("- Nenhuma observação automática.")
    lines.append("")

    lines.append("#### SQL detectado")
    lines.append("")
    if method.sql_blocks:
        for i, block in enumerate(method.sql_blocks, start=1):
            lines.append(f"##### SQL #{i}")
            lines.append("")
            lines.append(f"- **Linha aproximada:** `{block.line}`")
            if block.tables:
                lines.append(f"- **Tabelas:** {', '.join(f'`{t}`' for t in block.tables)}")
            else:
                lines.append("- **Tabelas:** não identificadas")
            lines.append("")
            lines.append("```sql")
            lines.append(block.sql.strip() if block.sql else "-- SQL vazio --")
            lines.append("```")
            lines.append("")
    else:
        lines.append("- Nenhum SQL detectado neste método.")
        lines.append("")

    return lines