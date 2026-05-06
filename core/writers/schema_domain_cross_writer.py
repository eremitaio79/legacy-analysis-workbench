from datetime import datetime
from pathlib import Path


def write_schema_domain_cross_report(
    result: dict,
    output_dir: Path,
    file_name: str = "schema_domain_cross.md",
):
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / file_name

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(
            f"# 🔀 Cruzamento Schema × Domínio — {str(result.get('domain_name', '')).upper()}\n\n"
        )
        f.write(f"Gerado em: {datetime.now()}\n\n")

        expected_entities = result.get("expected_entities", [])
        found_entities = result.get("found_entities", [])
        missing_entities = result.get("missing_entities", [])

        expected_relationships = result.get("expected_relationships", [])
        expected_relationship_edges = result.get("expected_relationship_edges", [])
        found_relationships = result.get("found_relationships", [])
        missing_relationships = result.get("missing_relationships", [])

        inferred_rules = result.get("inferred_rules", [])

        f.write("## 📊 Aderência\n\n")
        f.write(
            f"- Entidades esperadas encontradas: {result.get('adherence_entities_percent', 0)}%\n"
        )
        f.write(
            f"- Relacionamentos esperados encontrados: {result.get('adherence_relationships_percent', 0)}%\n"
        )
        f.write(f"- Total de entidades esperadas: {len(expected_entities)}\n")
        f.write(f"- Total de entidades encontradas: {len(found_entities)}\n")
        f.write(f"- Total de relacionamentos esperados: {len(expected_relationship_edges)}\n")
        f.write(f"- Total de relacionamentos encontrados: {len(found_relationships)}\n")

        f.write(f"\n## 📦 Entidades Esperadas ({len(expected_entities)})\n\n")
        if expected_entities:
            for item in expected_entities:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhuma entidade esperada definida no domain map._\n")

        f.write(f"\n## ✅ Entidades Encontradas ({len(found_entities)})\n\n")
        if found_entities:
            for item in found_entities:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhuma entidade esperada foi encontrada no schema._\n")

        f.write(f"\n## ❌ Entidades Ausentes ({len(missing_entities)})\n\n")
        if missing_entities:
            for item in missing_entities:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhuma entidade ausente._\n")

        f.write(f"\n## 🕸️ Relacionamentos Esperados ({len(expected_relationships)})\n\n")
        if expected_relationships:
            for item in expected_relationships:
                f.write(
                    f"- {item.get('origem', '')} → {item.get('destino', '')} "
                    f"[{item.get('tipo', 'relaciona_com')}]\n"
                )
        else:
            f.write("_Nenhum relacionamento esperado definido no domain map._\n")

        f.write(f"\n## ✅ Relacionamentos Encontrados ({len(found_relationships)})\n\n")
        if found_relationships:
            for item in found_relationships:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhum relacionamento esperado foi encontrado no schema._\n")

        f.write(f"\n## ❌ Relacionamentos Ausentes ({len(missing_relationships)})\n\n")
        if missing_relationships:
            for item in missing_relationships:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhum relacionamento ausente._\n")

        f.write(f"\n## 🧠 Regras de Negócio Candidatas ({len(inferred_rules)})\n\n")
        if inferred_rules:
            for item in inferred_rules:
                f.write(f"### {item.get('rule', '')}\n\n")

                f.write(f"- Confiança: {item.get('confidence', 'baixa')}\n")
                evidences = item.get("evidences", [])
                if evidences:
                    f.write("- Evidências:\n")
                    for ev in evidences:
                        f.write(f"  - {ev}\n")
                else:
                    f.write("- Evidências: nenhuma evidência estrutural forte encontrada.\n")
                f.write("\n")
        else:
            f.write("_Nenhuma regra candidata foi definida no domain map._\n")

        f.write("\n---\n")
        f.write("## 📌 Leitura do Resultado\n\n")
        f.write(
            "- A aderência de entidades mostra quantas entidades semânticas esperadas aparecem no schema estrutural.\n"
        )
        f.write(
            "- A aderência de relacionamentos considera a presença estrutural de pares origem → destino no schema.\n"
        )
        f.write(
            "- As regras candidatas recebem confiança com base em sinais estruturais detectados na análise semântica genérica.\n"
        )

    return file_path