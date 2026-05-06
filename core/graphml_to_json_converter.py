import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


class GraphMLToJsonConverter:
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.tree = ET.parse(self.file_path)
        self.root = self.tree.getroot()

        self.ns = {
            "g": "http://graphml.graphdrawing.org/xmlns",
            "y": "http://www.yworks.com/xml/graphml",
        }

    def convert(self) -> dict:
        entities = self._extract_nodes()
        relationships = self._extract_edges(entities)

        return {
            "entities": list(entities.values()),
            "relationships": relationships,
        }

    def _extract_nodes(self) -> dict:
        entities = {}

        for node in self.root.findall(".//g:node", self.ns):
            node_id = node.attrib.get("id", "").strip()
            if not node_id:
                continue

            table_name = self._extract_table_name(node)
            raw_columns = self._extract_columns_block(node)

            if not table_name:
                continue

            columns = self._parse_columns(raw_columns)

            entities[node_id] = {
                "id": node_id,
                "name": self._normalize_name(table_name),
                "columns": columns,
            }

        return entities

    def _extract_edges(self, entities: dict) -> list[dict]:
        relationships = []

        for idx, edge in enumerate(self.root.findall(".//g:edge", self.ns)):
            source = (edge.attrib.get("source") or "").strip()
            target = (edge.attrib.get("target") or "").strip()

            if not source or not target:
                continue

            if source not in entities or target not in entities:
                continue

            relationships.append(
                {
                    "id": edge.attrib.get("id") or f"edge{idx}",
                    "source_id": source,
                    "source_name": entities[source]["name"],
                    "target_id": target,
                    "target_name": entities[target]["name"],
                }
            )

        return relationships

    def _extract_table_name(self, node) -> str:
        xpath = (
            './/y:NodeLabel[@configuration="com.yworks.entityRelationship.label.name"]'
        )
        label = node.find(xpath, self.ns)

        if label is None:
            return ""

        text = self._collect_text(label)
        return text.strip()

    def _extract_columns_block(self, node) -> str:
        xpath = (
            './/y:NodeLabel[@configuration="com.yworks.entityRelationship.label.attributes"]'
        )
        label = node.find(xpath, self.ns)

        if label is None:
            return ""

        text = self._collect_text(label)
        return text.strip()

    def _collect_text(self, element) -> str:
        # Captura o texto antes dos filhos e ignora lixo de marcação interna do yWorks.
        parts = []
        if element.text:
            parts.append(element.text)

        # Se quiser capturar tails de filhos, descomente abaixo.
        # for child in element:
        #     if child.tail:
        #         parts.append(child.tail)

        return "".join(parts)

    def _parse_columns(self, raw_columns: str) -> list[dict]:
        if not raw_columns:
            return []

        columns = []
        lines = [line.strip() for line in raw_columns.splitlines() if line.strip()]

        for line in lines:
            # Ignora fragmentos de marcação que podem vazar do XML
            if line.startswith("<") or line.startswith("y:"):
                continue

            if ":" in line:
                col_name, col_type = line.split(":", 1)
                columns.append(
                    {
                        "name": self._normalize_name(col_name),
                        "type": self._normalize_type(col_type),
                    }
                )
            else:
                columns.append(
                    {
                        "name": self._normalize_name(line),
                        "type": "unknown",
                    }
                )

        return columns

    def _normalize_name(self, value: str) -> str:
        return (
            (value or "")
            .strip()
            .replace(" ", "_")
            .replace("/", "_")
            .lower()
        )

    def _normalize_type(self, value: str) -> str:
        raw = (value or "").strip().lower()

        mapping = {
            "int": "int4",
            "integer": "int4",
            "smallint": "int2",
            "bigint": "int8",
            "bit": "bpchar(1)",
            "datetime": "timestamp",
            "float": "numeric(15, 3)",
        }

        return mapping.get(raw, raw)


if __name__ == "__main__":
    # teste rápido opcional
    origem = Path("graphml/ppa.graphml")
    destino = Path("knowledge/ppa/ppa.json")

    converter = GraphMLToJsonConverter(origem)
    result = converter.convert()

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"JSON gerado em: {destino}")
    print(f"Entidades: {len(result['entities'])}")
    print(f"Relacionamentos: {len(result['relationships'])}")