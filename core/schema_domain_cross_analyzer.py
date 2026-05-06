class SchemaDomainCrossAnalyzer:
    def __init__(self, schema_analysis: dict, domain_map: dict):
        self.schema_analysis = schema_analysis or {}
        self.domain_map = domain_map or {}

    def analyze(self) -> dict:
        schema_entities = set(self.schema_analysis.get("all_entity_names", []))
        schema_relationships = set(self.schema_analysis.get("relationships_detected", []))
        schema_columns = set(self.schema_analysis.get("all_columns", []))

        domain_name = (
            self.domain_map.get("schema")
            or self.domain_map.get("dominio")
            or "desconhecido"
        )

        expected_entities = self._extract_expected_entities()
        expected_relationships = self._extract_expected_relationships()
        candidate_rules = self._extract_candidate_rules()

        found_entities = sorted([e for e in expected_entities if e in schema_entities])
        missing_entities = sorted([e for e in expected_entities if e not in schema_entities])

        expected_relationship_edges = sorted(
            {f"{r['origem']} → {r['destino']}" for r in expected_relationships}
        )

        found_relationships = sorted(
            [r for r in expected_relationship_edges if r in schema_relationships]
        )

        # 🔥 NOVO: inferência por colunas
        inferred_relationships = self._infer_relationships_by_columns(
            expected_relationships,
            schema_columns,
        )

        all_found_relationships = sorted(set(found_relationships + inferred_relationships))

        missing_relationships = sorted(
            [r for r in expected_relationship_edges if r not in all_found_relationships]
        )

        adherence_entities = self._safe_percent(len(found_entities), len(expected_entities))
        adherence_relationships = self._safe_percent(
            len(all_found_relationships),
            len(expected_relationship_edges)
        )

        inferred_rules = self._infer_rules(
            candidate_rules=candidate_rules,
            schema_entities=schema_entities,
            schema_relationships=schema_relationships,
        )

        return {
            "domain_name": domain_name,
            "expected_entities": expected_entities,
            "found_entities": found_entities,
            "missing_entities": missing_entities,
            "expected_relationships": expected_relationships,
            "expected_relationship_edges": expected_relationship_edges,
            "found_relationships": all_found_relationships,
            "missing_relationships": missing_relationships,
            "adherence_entities_percent": adherence_entities,
            "adherence_relationships_percent": adherence_relationships,
            "inferred_rules": inferred_rules,
        }

    def _infer_relationships_by_columns(
            self,
            expected_relationships: list[dict],
            schema_columns: set[str],
    ) -> list[str]:

        normalized_columns = set()

        for col in schema_columns:
            col_str = str(col).strip().lower()
            if not col_str:
                continue

            if "." in col_str:
                col_str = col_str.split(".")[-1]

            normalized_columns.add(col_str)

        destination_aliases = {
            "area": ["area_id", "are_id", "ar_id", "area"],
            "item": ["item_id", "ite_id", "it_id", "ide_id", "item", "ide"],
            "tempo": ["tempo_id", "tem_id", "te_id", "tempo", "periodo", "mes", "ano"],
        }

        inferred = []

        for rel in expected_relationships:
            origem = str(rel.get("origem", "")).strip().lower()
            destino = str(rel.get("destino", "")).strip().lower()

            if not origem or not destino:
                continue

            possible_keys = destination_aliases.get(
                destino,
                [
                    f"{destino}_id",
                    f"{destino[:3]}_id",
                    f"{destino[:2]}_id",
                    destino,
                ],
            )

            for key in possible_keys:
                if key.lower() in normalized_columns:
                    inferred.append(f"{origem} → {destino}")
                    break

        return inferred

    def _extract_expected_entities(self) -> list[str]:
        entities = self.domain_map.get("entities", {})

        if isinstance(entities, dict):
            return sorted(
                [str(k).strip().lower() for k in entities.keys() if str(k).strip()]
            )

        if isinstance(entities, list):
            result = []
            for item in entities:
                if isinstance(item, str):
                    result.append(item.strip().lower())
                elif isinstance(item, dict) and item.get("name"):
                    result.append(str(item["name"]).strip().lower())
            return sorted(set(result))

        return []

    def _extract_expected_relationships(self) -> list[dict]:
        relationships = self.domain_map.get("relacoes", [])
        result = []

        for rel in relationships:
            if not isinstance(rel, dict):
                continue

            origem = (rel.get("origem") or "").strip().lower()
            destino = (rel.get("destino") or "").strip().lower()
            tipo = (rel.get("tipo") or "").strip().lower()

            if origem and destino:
                result.append({
                    "origem": origem,
                    "destino": destino,
                    "tipo": tipo or "relaciona_com",
                })

        seen = set()
        deduped = []
        for rel in result:
            key = (rel["origem"], rel["destino"], rel["tipo"])
            if key not in seen:
                seen.add(key)
                deduped.append(rel)

        return sorted(deduped, key=lambda x: (x["origem"], x["destino"], x["tipo"]))

    def _extract_candidate_rules(self) -> list[str]:
        rules = self.domain_map.get("regras_candidatas", [])
        if not isinstance(rules, list):
            return []
        return [str(r).strip() for r in rules if str(r).strip()]

    def _infer_rules(
        self,
        candidate_rules: list[str],
        schema_entities: set[str],
        schema_relationships: set[str],
    ) -> list[dict]:
        temporal = set(self.schema_analysis.get("temporal_signals", []))
        financial = set(self.schema_analysis.get("financial_signals", []))
        regional = set(self.schema_analysis.get("regional_signals", []))
        status = set(self.schema_analysis.get("status_signals", []))
        versioning = set(self.schema_analysis.get("versioning_signals", []))

        inferred = []

        for rule in candidate_rules:
            rule_lower = rule.lower()
            evidences = []

            # ----------------------------
            # Evidências por sinais genéricos
            # ----------------------------
            if any(x in rule_lower for x in ["4 anos", "quadrien", "ano", "plurianual"]):
                if temporal:
                    evidences.append(
                        f"Sinais temporais em: {', '.join(sorted(temporal)[:10])}"
                    )

            if any(x in rule_lower for x in ["valor", "finance", "fonte", "revis", "teto", "orc"]):
                if financial:
                    evidences.append(
                        f"Sinais financeiros em: {', '.join(sorted(financial)[:10])}"
                    )
                if versioning:
                    evidences.append(
                        f"Sinais de revisão/versionamento em: {', '.join(sorted(versioning)[:10])}"
                    )

            if any(x in rule_lower for x in ["região", "regional", "município", "territ", "territorial"]):
                if regional:
                    evidences.append(
                        f"Sinais regionais em: {', '.join(sorted(regional)[:10])}"
                    )

            if any(x in rule_lower for x in ["status", "situação", "avali"]):
                if status:
                    evidences.append(
                        f"Sinais de status em: {', '.join(sorted(status)[:10])}"
                    )

            # ----------------------------
            # Evidências por entidades-chave
            # ----------------------------
            entity_groups = self._expected_entities_for_rule(rule_lower)
            for group in entity_groups:
                if all(entity in schema_entities for entity in group):
                    evidences.append(
                        f"Entidades presentes: {', '.join(group)}"
                    )

            # ----------------------------
            # Evidências por relacionamentos-chave
            # ----------------------------
            rel_groups = self._expected_relationships_for_rule(rule_lower)
            for rel in rel_groups:
                if rel in schema_relationships:
                    evidences.append(f"Relacionamento presente: {rel}")

            inferred.append({
                "rule": rule,
                "evidences": self._dedupe_preserve_order(evidences),
                "confidence": self._confidence_from_evidences(evidences),
            })

        return inferred

    def _expected_entities_for_rule(self, rule_lower: str) -> list[tuple[str, ...]]:
        mappings = []

        if "estrutura programática" in rule_lower or "programas, objetivos e ações" in rule_lower:
            mappings.append(("programa", "programaobjetivo", "acao"))

        if "direcionamento estratégico" in rule_lower or "diretrizes, programas" in rule_lower:
            mappings.append(("diretriz", "diretriz_programa", "programa"))

        if "detalhamento financeiro" in rule_lower or "fontes de recurso" in rule_lower:
            mappings.append(("acaofonte",))
            mappings.append(("despesateto",))
            mappings.append(("tetoorgao",))
            mappings.append(("unidorca_fonteger",))

        if "metas associadas" in rule_lower or "monitoramento" in rule_lower:
            mappings.append(("acaometa",))
            mappings.append(("programaobjetivometa",))
            mappings.append(("opameta",))

        if "indicadores" in rule_lower or "medição de desempenho" in rule_lower:
            mappings.append(("indicador",))

        if "regionalização" in rule_lower or "territorial" in rule_lower:
            mappings.append(("acaoregiao",))
            mappings.append(("tbmeta_e_regioes",))
            mappings.append(("tbpropostametareg",))

        if "ação está semanticamente vinculada ao programa" in rule_lower:
            mappings.append(("acao", "programa"))

        if "objetivos pertencem a programas" in rule_lower:
            mappings.append(("programaobjetivo", "programa"))

        if "metas detalham os objetivos" in rule_lower:
            mappings.append(("programaobjetivometa", "programaobjetivo"))

        return mappings

    def _expected_relationships_for_rule(self, rule_lower: str) -> list[str]:
        mappings = []

        if "ação está semanticamente vinculada ao programa" in rule_lower:
            mappings.append("acao → programa")

        if "objetivos pertencem a programas" in rule_lower:
            mappings.append("programaobjetivo → programa")

        if "metas detalham os objetivos" in rule_lower:
            mappings.append("programaobjetivometa → programaobjetivo")

        if "estrutura programática" in rule_lower or "programas, objetivos e ações" in rule_lower:
            mappings.append("acao → programa")
            mappings.append("programaobjetivo → programa")

        if "direcionamento estratégico" in rule_lower or "diretrizes, programas" in rule_lower:
            mappings.append("diretriz_programa → diretriz")
            mappings.append("diretriz_programa → programa")

        if "regionalização" in rule_lower or "territorial" in rule_lower:
            mappings.append("acaoregiao → acao")
            mappings.append("tbmeta_e_regioes → tbpropostametareg")

        if "indicadores" in rule_lower or "medição de desempenho" in rule_lower:
            mappings.append("indicador → programa")

        return mappings

    def _confidence_from_evidences(self, evidences: list[str]) -> str:
        unique_count = len(self._dedupe_preserve_order(evidences))
        if unique_count >= 3:
            return "alta"
        if unique_count >= 1:
            return "média"
        return "baixa"

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            if item not in seen:

                seen.add(item)
                result.append(item)
        return result

    def _safe_percent(self, found: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round((found / total) * 100, 2)