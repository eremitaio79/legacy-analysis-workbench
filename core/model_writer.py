from __future__ import annotations

from pathlib import Path

from core.model_analyzer import ModelAnalysisResult, ModelFieldInfo, ModelMethodInfo


def write_model_report(
    result: ModelAnalysisResult,
    output_path: str | Path,
    detailed: bool = True,
) -> Path:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    md: list[str] = []

    md.append(f"# Model Analyzer - {result.class_name or 'Classe não identificada'}")
    md.append("")

    md.append("## Resumo")
    md.append("")
    md.append(f"- **Entrada informada:** `{result.input_value}`")
    md.append(f"- **Arquivo analisado:** `{result.resolved_path}`")
    md.append(f"- **Classe:** `{result.class_name or 'não identificada'}`")
    md.append(f"- **Package:** `{result.package or 'não identificado'}`")
    md.append(f"- **Author:** `{result.author or 'não identificado'}`")
    md.append(f"- **SGBD:** `{result.sgbd or 'não identificado'}`")
    md.append(f"- **Tabela:** `{result.table_name or 'não identificada'}`")
    md.append(f"- **Total de linhas:** `{result.total_lines}`")
    md.append(f"- **Campos encontrados:** `{len(result.fields)}`")
    md.append(f"- **Métodos encontrados:** `{len(result.methods)}`")
    md.append(f"- **Getters:** `{len(result.getters)}`")
    md.append(f"- **Setters:** `{len(result.setters)}`")
    md.append("")

    md.append("## Pontos de atenção")
    md.append("")
    if result.warnings:
        for warning in result.warnings:
            md.append(f"- {warning}")
    else:
        md.append("- Nenhum ponto de atenção automático foi identificado.")
    md.append("")

    md.append("## Chave primária")
    md.append("")
    primary_fields = [f for f in result.fields if f.is_primary is True]
    if primary_fields:
        for field in primary_fields:
            md.append(
                f"- `${field.property_name}`"
                + (f" → `{field.db_field}`" if field.db_field else "")
            )
    else:
        md.append("- Nenhum campo primário identificado.")
    md.append("")

    md.append("## Campos")
    md.append("")
    if result.fields:
        for field in result.fields:
            md.extend(_render_field_summary(field))
    else:
        md.append("- Nenhum campo identificado.")
    md.append("")

    md.append("## Métodos")
    md.append("")
    if result.methods:
        for method in result.methods:
            md.extend(_render_method_summary(method))
    else:
        md.append("- Nenhum método identificado.")
    md.append("")

    md.append("## Getters")
    md.append("")
    if result.getters:
        for getter in result.getters:
            md.append(f"- `{getter}()`")
    else:
        md.append("- Nenhum getter identificado.")
    md.append("")

    md.append("## Setters")
    md.append("")
    if result.setters:
        for setter in result.setters:
            md.append(f"- `{setter}()`")
    else:
        md.append("- Nenhum setter identificado.")
    md.append("")

    if detailed:
        md.append("## Detalhamento dos campos")
        md.append("")
        if result.fields:
            for field in result.fields:
                md.extend(_render_field_detail(field))
        else:
            md.append("- Nenhum campo identificado.")
            md.append("")

        md.append("## Detalhamento dos métodos")
        md.append("")
        if result.methods:
            for method in result.methods:
                md.extend(_render_method_detail(method))
        else:
            md.append("- Nenhum método identificado.")
            md.append("")

    output_file.write_text("\n".join(md), encoding="utf-8")
    return output_file


def _render_field_summary(field: ModelFieldInfo) -> list[str]:
    lines: list[str] = []

    lines.append(f"- `${field.property_name}`")
    lines.append(f"  - **Visibilidade:** `{field.visibility}`")
    lines.append(f"  - **Linha:** `{field.line}`")
    lines.append(f"  - **Campo BD:** `{field.db_field or 'não identificado'}`")
    lines.append(f"  - **Tipo:** `{field.var_type or 'não identificado'}`")
    lines.append(f"  - **Primário:** `{_fmt_bool(field.is_primary)}`")
    lines.append(f"  - **Nulo:** `{_fmt_bool(field.is_nullable)}`")
    lines.append(f"  - **Auto incremento:** `{_fmt_bool(field.is_auto_increment)}`")
    lines.append("")
    return lines


def _render_field_detail(field: ModelFieldInfo) -> list[str]:
    lines: list[str] = []

    lines.append(f"### `${field.property_name}`")
    lines.append("")
    lines.append(f"- **Visibilidade:** `{field.visibility}`")
    lines.append(f"- **Linha:** `{field.line}`")
    lines.append(f"- **Campo BD:** `{field.db_field or 'não identificado'}`")
    lines.append(f"- **Tipo:** `{field.var_type or 'não identificado'}`")
    lines.append(f"- **Primário:** `{_fmt_bool(field.is_primary)}`")
    lines.append(f"- **Nulo:** `{_fmt_bool(field.is_nullable)}`")
    lines.append(f"- **Auto incremento:** `{_fmt_bool(field.is_auto_increment)}`")
    lines.append("")

    lines.append("#### Anotações")
    lines.append("")
    if field.annotations:
        for key, value in field.annotations.items():
            lines.append(f"- `@{key}` = `{value}`")
    else:
        lines.append("- Nenhuma anotação encontrada.")
    lines.append("")

    lines.append("#### Docblock bruto")
    lines.append("")
    if field.raw_docblock.strip():
        lines.append("```php")
        lines.append(field.raw_docblock.strip())
        lines.append("```")
    else:
        lines.append("- Nenhum docblock associado.")
    lines.append("")

    return lines


def _render_method_summary(method: ModelMethodInfo) -> list[str]:
    lines: list[str] = []
    lines.append(f"- `{method.name}()`")
    lines.append(f"  - **Tipo:** `{method.method_type}`")
    lines.append(f"  - **Linha:** `{method.line}`")
    lines.append(
        f"  - **Propriedade relacionada:** `{method.related_property or 'não inferida'}`"
    )
    lines.append("")
    return lines


def _render_method_detail(method: ModelMethodInfo) -> list[str]:
    lines: list[str] = []
    lines.append(f"### `{method.name}()`")
    lines.append("")
    lines.append(f"- **Tipo:** `{method.method_type}`")
    lines.append(f"- **Linha:** `{method.line}`")
    lines.append(f"- **Propriedade relacionada:** `{method.related_property or 'não inferida'}`")
    lines.append("")
    return lines


def _fmt_bool(value: bool | None) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "não identificado"