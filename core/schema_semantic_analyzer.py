class SchemaSemanticAnalyzer:
    def __init__(self, schema_json: dict):
        self.schema = schema_json or {}
        self.entities = self.schema.get("entities", [])
        self.relationships = self.schema.get("relationships", [])

    def analyze(self):
        all_entity_names = sorted(
            [
                (entity.get("name") or "").strip()
                for entity in self.entities
                if (entity.get("name") or "").strip()
            ]
        )

        result = {
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "all_entity_names": all_entity_names,
            "entities_detected": [],  # reservado para a futura camada de domínio
            "hierarchy": [],          # reservado para a futura camada de domínio
            "relationships_detected": [],
            "temporal_signals": [],
            "financial_signals": [],
            "regional_signals": [],
            "status_signals": [],
            "versioning_signals": [],
        }

        # ----------------------------
        # Relacionamentos brutos
        # ----------------------------
        for rel in self.relationships:
            src = (rel.get("source_name") or "").strip()
            tgt = (rel.get("target_name") or "").strip()

            if src and tgt:
                result["relationships_detected"].append(f"{src} → {tgt}")

        # ----------------------------
        # Sinais por entidade
        # ----------------------------
        for entity in self.entities:
            entity_name = (entity.get("name") or "").strip()
            columns = entity.get("columns", []) or []

            has_temporal = False
            has_financial = False
            has_regional = False
            has_status = False
            has_versioning = False

            for col in columns:
                col_name = (col.get("name") or "").strip().lower()

                # temporalidade
                if any(x in col_name for x in [
                    "ano1", "ano2", "ano3", "ano4",
                    "ano", "exercicio", "vigencia",
                    "inicio", "fim", "data"
                ]):
                    has_temporal = True

                # financeiro
                if any(x in col_name for x in [
                    "vl", "valor", "orc", "finance", "despesa",
                    "receita", "credito", "debito", "saldo", "custo"
                ]):
                    has_financial = True

                # regionalização
                if any(x in col_name for x in [
                    "reg", "mun", "municipio", "territorio",
                    "bairro", "localidade", "regional"
                ]):
                    has_regional = True

                # status / situação
                if any(x in col_name for x in [
                    "status", "situacao", "flag", "ativo",
                    "inativo", "visivel", "invisivel"
                ]):
                    has_status = True

                # revisão / versionamento
                if any(x in col_name for x in [
                    "revisao", "versao", "original", "ajuste",
                    "reduz", "suplement", "complement"
                ]):
                    has_versioning = True

            if entity_name:
                if has_temporal:
                    result["temporal_signals"].append(entity_name)

                if has_financial:
                    result["financial_signals"].append(entity_name)

                if has_regional:
                    result["regional_signals"].append(entity_name)

                if has_status:
                    result["status_signals"].append(entity_name)

                if has_versioning:
                    result["versioning_signals"].append(entity_name)

        # ordenação e remoção de duplicados
        result["temporal_signals"] = sorted(set(result["temporal_signals"]))
        result["financial_signals"] = sorted(set(result["financial_signals"]))
        result["regional_signals"] = sorted(set(result["regional_signals"]))
        result["status_signals"] = sorted(set(result["status_signals"]))
        result["versioning_signals"] = sorted(set(result["versioning_signals"]))
        result["relationships_detected"] = sorted(set(result["relationships_detected"]))

        return result