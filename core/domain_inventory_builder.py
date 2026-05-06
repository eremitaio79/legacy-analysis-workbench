from __future__ import annotations

from pathlib import Path
import re


class DomainInventoryBuilder:
    def __init__(self, knowledge_dir: str = "knowledge", cross_dir: str = "reports/schema_cross"):
        self.knowledge_dir = Path(knowledge_dir)
        self.cross_dir = Path(cross_dir)

    def build(self) -> list[dict]:
        if not self.knowledge_dir.exists():
            return []

        domains = sorted([p for p in self.knowledge_dir.iterdir() if p.is_dir()])

        items = []
        for domain_dir in domains:
            domain = domain_dir.name
            domain_clean = domain.lstrip("_")

            structural_json = domain_dir / f"{domain_clean}.json"
            domain_map_json = domain_dir / f"{domain_clean}_domain_map.json"

            cross_md = self.cross_dir / f"{domain_clean}_cross.md"
            cross_ia_md = self.cross_dir / f"{domain_clean}_cross_ia.md"

            adherence_entities = None
            adherence_relationships = None
            rule_count = 0

            if cross_md.exists():
                content = cross_md.read_text(encoding="utf-8", errors="ignore")
                adherence_entities = self._extract_percentage(
                    content,
                    r"Entidades esperadas encontradas:\s*([\d.,]+)%"
                )
                adherence_relationships = self._extract_percentage(
                    content,
                    r"Relacionamentos esperados encontrados:\s*([\d.,]+)%"
                )
                rule_count = self._extract_count(
                    content,
                    r"## 🧠 Regras de Negócio Candidatas \((\d+)\)"
                )

            maturity = self._classify_maturity(
                has_structural=structural_json.exists(),
                has_domain_map=domain_map_json.exists(),
                has_cross=cross_md.exists(),
                has_cross_ia=cross_ia_md.exists(),
                adherence_entities=adherence_entities,
                adherence_relationships=adherence_relationships,
                rule_count=rule_count,
            )

            note = self._build_note(
                adherence_entities=adherence_entities,
                adherence_relationships=adherence_relationships,
                rule_count=rule_count,
                maturity=maturity,
            )

            items.append({
                "domain": domain,
                "structural_json": structural_json.exists(),
                "domain_map_json": domain_map_json.exists(),
                "cross_md": cross_md.exists(),
                "cross_ia_md": cross_ia_md.exists(),
                "adherence_entities": adherence_entities,
                "adherence_relationships": adherence_relationships,
                "rule_count": rule_count,
                "maturity": maturity,
                "note": note,
            })

        return items

    def _extract_percentage(self, text: str, pattern: str) -> float | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        raw = match.group(1).replace(",", ".").strip()
        try:
            return float(raw)
        except ValueError:
            return None

    def _extract_count(self, text: str, pattern: str) -> int:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0

    def _classify_maturity(
            self,
            has_structural: bool,
            has_domain_map: bool,
            has_cross: bool,
            has_cross_ia: bool,
            adherence_entities: float | None,
            adherence_relationships: float | None,
            rule_count: int,
    ) -> str:
        if not has_structural:
            return "não iniciado"

        if not has_domain_map:
            return "estrutural"

        if not has_cross:
            return "semântico inicial"

        if not has_cross_ia:
            return "parcial"

        ent = adherence_entities or 0.0
        rel = adherence_relationships or 0.0

        # domínio maduro clássico
        if ent >= 95 and rel >= 90 and rule_count >= 3:
            return "maduro"

        # domínio maduro enxuto: alta aderência, pipeline completo, mas poucas regras
        if ent >= 95 and rel >= 90 and rule_count >= 2:
            return "maduro"

        if ent >= 70 or rel >= 50 or rule_count >= 1:
            return "parcial"

        return "raso"

    def _build_note(
            self,
            adherence_entities: float | None,
            adherence_relationships: float | None,
            rule_count: int,
            maturity: str,
    ) -> str:
        if maturity == "não iniciado":
            return "Sem JSON estrutural."
        if maturity == "estrutural":
            return "Possui apenas JSON estrutural."
        if maturity == "semântico inicial":
            return "Possui domain map, mas ainda sem cruzamento."
        if maturity == "raso":
            return "Pipeline existe, mas a semântica ainda está fraca."

        parts = []
        if adherence_entities is not None:
            parts.append(f"entidades {adherence_entities:.2f}%")
        if adherence_relationships is not None:
            parts.append(f"relacionamentos {adherence_relationships:.2f}%")
        if rule_count is not None:
            parts.append(f"{rule_count} regras")

        if maturity == "maduro" and rule_count <= 2:
            parts.append("domínio enxuto")

        return ", ".join(parts) if parts else "Sem observações."