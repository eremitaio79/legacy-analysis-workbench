from datetime import datetime
from pathlib import Path


def write_schema_semantic_report(
    result: dict,
    output_dir: Path,
    file_name: str = "schema_semantic_analysis.md",
    domain: str | None = None
):
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / file_name

    with open(file_path, "w", encoding="utf-8") as f:
        titulo = "🧠 Análise Semântica do Schema"
        if domain:
            titulo += f" — {domain.upper()}"

        f.write(f"# {titulo}\n\n")
        f.write(f"Gerado em: {datetime.now()}\n\n")

        total_entities = result.get("total_entities", 0)
        total_relationships = result.get("total_relationships", 0)

        all_entity_names = result.get("all_entity_names", [])
        relationships_detected = result.get("relationships_detected", [])

        entidades = result.get("entities_detected", [])
        hierarquia = result.get("hierarchy", [])

        temporal = sorted(set(result.get("temporal_signals", [])))
        financeiro = sorted(set(result.get("financial_signals", [])))
        regional = sorted(set(result.get("regional_signals", [])))
        status_signals = sorted(set(result.get("status_signals", [])))
        versioning_signals = sorted(set(result.get("versioning_signals", [])))

        # ----------------------------
        # VISÃO GERAL
        # ----------------------------
        f.write("## 📚 Visão Geral do Schema\n\n")
        f.write(f"- Total de entidades no JSON: {total_entities}\n")
        f.write(f"- Total de relacionamentos no JSON: {total_relationships}\n")
        f.write(f"- Entidades listadas no JSON: {len(all_entity_names)}\n")
        f.write(f"- Relacionamentos estruturais detectados: {len(relationships_detected)}\n")

        # ----------------------------
        # ENTIDADES PRINCIPAIS (reservado para cruzamento futuro)
        # ----------------------------
        f.write(f"\n## 📦 Entidades Principais Detectadas ({len(entidades)})\n\n")
        if entidades:
            for e in entidades:
                f.write(f"- {e}\n")
        else:
            f.write("_Nenhuma entidade principal detectada nesta análise estrutural genérica._\n")

        # ----------------------------
        # ENTIDADES DO JSON
        # ----------------------------
        f.write(f"\n## 🗂️ Entidades Encontradas no JSON ({len(all_entity_names)})\n\n")
        if all_entity_names:
            for name in all_entity_names:
                f.write(f"- {name}\n")
        else:
            f.write("_Nenhuma entidade encontrada no JSON._\n")

        # ----------------------------
        # HIERARQUIA (reservado para cruzamento futuro)
        # ----------------------------
        f.write(f"\n## 🔗 Relações Hierárquicas Detectadas ({len(hierarquia)})\n\n")
        if hierarquia:
            for h in hierarquia:
                f.write(f"- {h}\n")
        else:
            f.write("_Nenhuma relação hierárquica específica detectada nesta análise estrutural genérica._\n")

        # ----------------------------
        # RELACIONAMENTOS ESTRUTURAIS
        # ----------------------------
        f.write(f"\n## 🕸️ Relacionamentos Detectados no JSON ({len(relationships_detected)})\n\n")
        if relationships_detected:
            limite = 200
            for item in relationships_detected[:limite]:
                f.write(f"- {item}\n")

            if len(relationships_detected) > limite:
                restantes = len(relationships_detected) - limite
                f.write(f"\n_... e mais {restantes} relacionamentos._\n")
        else:
            f.write("_Nenhum relacionamento detectado no JSON._\n")

        # ----------------------------
        # SINAIS
        # ----------------------------
        f.write(f"\n## ⏳ Sinais de Temporalidade ({len(temporal)})\n\n")
        if temporal:
            for t in temporal:
                f.write(f"- {t}\n")
        else:
            f.write("_Nenhum sinal temporal identificado._\n")

        f.write(f"\n## 💰 Sinais Financeiros ({len(financeiro)})\n\n")
        if financeiro:
            for item in financeiro:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhum sinal financeiro identificado._\n")

        f.write(f"\n## 🌎 Sinais de Regionalização ({len(regional)})\n\n")
        if regional:
            for item in regional:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhum sinal de regionalização identificado._\n")

        f.write(f"\n## 🚦 Sinais de Status / Situação ({len(status_signals)})\n\n")
        if status_signals:
            for item in status_signals:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhum sinal de status identificado._\n")

        f.write(f"\n## 🧾 Sinais de Revisão / Versionamento ({len(versioning_signals)})\n\n")
        if versioning_signals:
            for item in versioning_signals:
                f.write(f"- {item}\n")
        else:
            f.write("_Nenhum sinal de revisão/versionamento identificado._\n")

        # ----------------------------
        # RESUMO
        # ----------------------------
        f.write("\n---\n")
        f.write("## 📊 Resumo\n\n")
        f.write(f"- Total de entidades no JSON: {total_entities}\n")
        f.write(f"- Total de relacionamentos no JSON: {total_relationships}\n")
        f.write(f"- Entidades listadas no JSON: {len(all_entity_names)}\n")
        f.write(f"- Relacionamentos detectados: {len(relationships_detected)}\n")
        f.write(f"- Entidades principais detectadas: {len(entidades)}\n")
        f.write(f"- Relações hierárquicas detectadas: {len(hierarquia)}\n")
        f.write(f"- Tabelas com temporalidade: {len(temporal)}\n")
        f.write(f"- Tabelas com sinais financeiros: {len(financeiro)}\n")
        f.write(f"- Tabelas com regionalização: {len(regional)}\n")
        f.write(f"- Tabelas com sinais de status: {len(status_signals)}\n")
        f.write(f"- Tabelas com sinais de revisão/versionamento: {len(versioning_signals)}\n")

    return file_path