import json
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "g": "http://graphml.graphdrawing.org/xmlns",
    "y": "http://www.yworks.com/xml/graphml",
}

CFG_NAME = "com.yworks.entityRelationship.label.name"
CFG_ATTRS = "com.yworks.entityRelationship.label.attributes"


def clean_text(text: str | None) -> str:
    return (text or "").replace("\r", "").strip()


def parse_columns(raw: str) -> list[dict]:
    cols = []
    for line in clean_text(raw).splitlines():
        line = line.strip()
        if not line:
            continue

        if ":" in line:
            name, dtype = line.split(":", 1)
            cols.append({
                "name": name.strip(),
                "type": dtype.strip()
            })
        else:
            cols.append({
                "name": line,
                "type": None
            })
    return cols


def parse_graphml_yworks(path_graphml: Path) -> dict:
    tree = ET.parse(path_graphml)
    root = tree.getroot()

    entities = []
    entity_map = {}

    for node in root.findall(".//g:node", NS):
        node_id = node.attrib.get("id")
        table_name = None
        raw_columns = ""

        for label in node.findall(".//y:NodeLabel", NS):
            config = label.attrib.get("configuration", "")
            text = clean_text(label.text)

            if config == CFG_NAME:
                table_name = text
            elif config == CFG_ATTRS:
                raw_columns = text

        entity = {
            "id": node_id,
            "name": table_name,
            "columns": parse_columns(raw_columns),
        }

        entities.append(entity)
        entity_map[node_id] = table_name

    relationships = []

    for edge in root.findall(".//g:edge", NS):
        relationships.append({
            "id": edge.attrib.get("id"),
            "source_id": edge.attrib.get("source"),
            "source_name": entity_map.get(edge.attrib.get("source")),
            "target_id": edge.attrib.get("target"),
            "target_name": entity_map.get(edge.attrib.get("target")),
        })

    return {
        "entities": entities,
        "relationships": relationships,
    }


def solicitar_caminho(mensagem: str) -> Path:
    while True:
        caminho = input(mensagem).strip().strip('"')

        if not caminho:
            print("⚠️ Caminho não pode ser vazio.")
            continue

        path = Path(caminho)

        return path


def main():
    print("\n=== CONVERSOR GRAPHML → JSON ===\n")

    input_path = solicitar_caminho("📥 Informe o caminho do arquivo .graphml: ")

    if not input_path.exists():
        print(f"❌ Arquivo não encontrado: {input_path}")
        return

    if input_path.suffix.lower() != ".graphml":
        print("⚠️ O arquivo informado não parece ser .graphml")

    output_path = solicitar_caminho("💾 Informe o caminho para salvar o JSON: ")

    # Garante extensão .json
    if output_path.suffix.lower() != ".json":
        output_path = output_path.with_suffix(".json")

    # Cria pasta se não existir
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n🔄 Processando...")

    try:
        data = parse_graphml_yworks(input_path)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("\n✅ Conversão concluída!")
        print(f"📄 Arquivo salvo em: {output_path}")
        print(f"📊 Entidades: {len(data['entities'])}")
        print(f"🔗 Relacionamentos: {len(data['relationships'])}")

    except Exception as e:
        print("\n❌ Erro durante o processamento:")
        print(str(e))


if __name__ == "__main__":
    main()