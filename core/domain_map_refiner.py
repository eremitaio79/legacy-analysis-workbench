from __future__ import annotations


class DomainMapRefiner:
    def __init__(self, domain_map: dict):
        self.domain_map = domain_map or {}
        self.schema = (self.domain_map.get("schema") or "").strip().lower()

    def refine(self) -> dict:
        schema = self.domain_map.get("schema", "")
        dominio = self.domain_map.get("dominio", "")
        entities = self.domain_map.get("entities", {}) or {}
        relacoes = self.domain_map.get("relacoes", []) or []
        sinais_esperados = self.domain_map.get("sinais_esperados", {}) or {}

        canonical_map = {}
        aliases_map = {}

        # ----------------------------
        # ENTIDADES
        # ----------------------------
        for entity_name, payload in entities.items():
            canonical = self._canonical_name(entity_name)
            if not canonical:
                continue

            aliases_map.setdefault(canonical, set()).add(entity_name)

            if canonical not in canonical_map:
                canonical_map[canonical] = {
                    "descricao": self._refined_description(canonical),
                    "categoria": self._refined_category(canonical),
                }

        refined_entities = {}

        for canonical, payload in sorted(canonical_map.items()):
            original_entity = entities.get(canonical, {})

            refined_entities[canonical] = {
                "descricao": payload["descricao"],
                "categoria": payload["categoria"],
                "aliases": sorted(aliases_map.get(canonical, set())),

                # 🔥 PRESERVAÇÃO DE ENRIQUECIMENTO MANUAL
                "dimensoes_relacionadas": original_entity.get("dimensoes_relacionadas", []),
                "medidas": original_entity.get("medidas", []),
            }

        # ----------------------------
        # RELAÇÕES
        # ----------------------------
        refined_relacoes = []
        seen_rel = set()

        for rel in relacoes:
            origem = self._canonical_name(rel.get("origem", ""))
            destino = self._canonical_name(rel.get("destino", ""))

            if not origem or not destino:
                continue

            if origem not in refined_entities or destino not in refined_entities:
                continue

            tipo = self._refined_relationship_type(origem, destino, rel.get("tipo", ""))

            key = (origem, destino, tipo)
            if key in seen_rel:
                continue
            seen_rel.add(key)

            refined_relacoes.append({
                "origem": origem,
                "destino": destino,
                "tipo": tipo,
            })

        # 🔥 MERGE COM RELAÇÕES MANUAIS
        manual_relacoes = self.domain_map.get("relacoes", [])
        combined_relacoes = refined_relacoes.copy()

        existing_keys = {
            (r["origem"], r["destino"], r["tipo"])
            for r in combined_relacoes
        }

        for rel in manual_relacoes:
            origem = self._canonical_name(rel.get("origem", ""))
            destino = self._canonical_name(rel.get("destino", ""))

            if not origem or not destino:
                continue

            tipo = rel.get("tipo", "relaciona_com")

            key = (origem, destino, tipo)

            if key not in existing_keys:
                combined_relacoes.append({
                    "origem": origem,
                    "destino": destino,
                    "tipo": tipo,
                })
                existing_keys.add(key)

        refined_relacoes = sorted(
            combined_relacoes,
            key=lambda x: (x["origem"], x["destino"], x["tipo"])
        )

        # ----------------------------
        # REGRAS
        # ----------------------------
        generated_rules = self._refined_candidate_rules(refined_entities, refined_relacoes)
        manual_rules = self.domain_map.get("regras_candidatas", [])

        regras_candidatas = sorted(set(manual_rules + generated_rules))

        # ----------------------------
        # RESULTADO FINAL
        # ----------------------------
        return {
            "schema": schema,
            "dominio": dominio,
            "entities": refined_entities,
            "relacoes": refined_relacoes,
            "regras_candidatas": regras_candidatas,
            "sinais_esperados": sinais_esperados,
        }

    # ============================
    # HELPERS
    # ============================

    def _canonical_name(self, name: str) -> str:
        n = (name or "").strip().lower()
        if not n:
            return ""

        discard_contains = [
            "originais",
            "intacta",
            "teste",
            "backup",
        ]
        if any(x in n for x in discard_contains):
            return ""

        if n.startswith(("x_", "w_", "z_")):
            return ""

        suffixes = [
            "_copia",
            "_copy",
            "_temp",
            "_tmp",
            "_old",
            "_old2",
            "_new",
            "_bk",
            "_ppa_anterior",
            "_507",
            "_view",
        ]
        for suffix in suffixes:
            if n.endswith(suffix):
                n = n[: -len(suffix)]

        return n

    def _refined_description(self, entity_name: str) -> str:
        return "Entidade semântica refinada a partir do schema estrutural."

    def _refined_category(self, entity_name: str) -> str:
        return "geral"

    def _refined_relationship_type(self, origem: str, destino: str, current_type: str) -> str:
        if current_type and current_type != "relaciona_com":
            return current_type
        return "relaciona_com"

    def _refined_candidate_rules(self, entities: dict, relacoes: list[dict]) -> list[str]:
        rules = []

        if any("valor" in e or "mes" in e for e in entities):
            rules.append("O domínio possui dados distribuídos ao longo do tempo.")

        if relacoes:
            rules.append("O domínio possui relações semânticas entre entidades.")

        return rules
