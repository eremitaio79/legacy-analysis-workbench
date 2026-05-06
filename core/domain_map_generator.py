from __future__ import annotations


class DomainMapGenerator:
    def __init__(self, schema_json: dict, domain_name: str):
        self.schema = schema_json or {}
        self.domain_name = (domain_name or "").strip().lower()
        self.entities = self.schema.get("entities", [])
        self.relationships = self.schema.get("relationships", [])

    def generate(self) -> dict:
        valid_entities = self._get_valid_entities()
        valid_entity_names = sorted(valid_entities.keys())

        semantic_entities = {}
        for entity_name in valid_entity_names:
            semantic_entities[entity_name] = {
                "descricao": self._infer_entity_description(entity_name),
                "categoria": self._infer_entity_category(entity_name),
            }

        semantic_relationships = []
        for rel in self.relationships:
            origem = (rel.get("source_name") or "").strip().lower()
            destino = (rel.get("target_name") or "").strip().lower()

            origem = self._normalize_candidate_name(origem)
            destino = self._normalize_candidate_name(destino)

            if not origem or not destino:
                continue

            if origem not in valid_entities or destino not in valid_entities:
                continue

            semantic_relationships.append({
                "origem": origem,
                "destino": destino,
                "tipo": self._infer_relationship_type(origem, destino),
            })

        semantic_relationships = self._deduplicate_relationships(semantic_relationships)

        return {
            "schema": self.domain_name.lstrip("_"),
            "dominio": self._infer_domain_title(),
            "entities": semantic_entities,
            "relacoes": semantic_relationships,
            "regras_candidatas": self._infer_candidate_rules(valid_entities),
            "sinais_esperados": self._infer_expected_signals(),
        }

    def _get_valid_entities(self) -> dict[str, dict]:
        result = {}

        for entity in self.entities:
            raw_name = (entity.get("name") or "").strip().lower()
            if not raw_name:
                continue

            normalized = self._normalize_candidate_name(raw_name)
            if not normalized:
                continue

            if normalized not in result:
                result[normalized] = entity
                continue

            current_score = self._entity_quality_score(normalized, result[normalized])
            candidate_score = self._entity_quality_score(normalized, entity)

            if candidate_score > current_score:
                result[normalized] = entity

        return result

    def _normalize_candidate_name(self, name: str) -> str:
        n = (name or "").strip().lower()
        if not n:
            return ""

        noisy_prefixes = ("x_", "w_", "z_")
        noisy_suffixes = (
            "_copia",
            "_copy",
            "_temp",
            "_tmp",
            "_old",
            "_old2",
            "_new",
            "_bk",
            "_507",
        )

        for prefix in noisy_prefixes:
            if n.startswith(prefix):
                return ""

        for suffix in noisy_suffixes:
            if n.endswith(suffix):
                n = n[: -len(suffix)]

        alias_map = {
            "meta_descricao": "metadescritiva",
            "objetivo_descricao": "objdescritivo",
        }
        n = alias_map.get(n, n)

        if len(n) < 2:
            return ""

        return n

    def _entity_quality_score(self, normalized_name: str, entity: dict) -> int:
        raw_name = (entity.get("name") or "").strip().lower()
        columns = entity.get("columns", []) or []

        score = 0

        if raw_name == normalized_name:
            score += 50

        if not any(x in raw_name for x in ["temp", "copia", "copy", "old", "new", "_bk", "x_", "w_", "z_"]):
            score += 20

        score += min(len(columns), 30)

        return score

    def _infer_domain_title(self) -> str:
        mapping = {
            "_ppa": "Plano Plurianual",
            "ppa": "Plano Plurianual",
            "_oge": "Orçamento Geral do Estado",
            "oge": "Orçamento Geral do Estado",
            "_pae": "Planejamento Estratégico",
            "pae": "Planejamento Estratégico",
            "_pggp": "Programa de Gestão Governamental",
            "pggp": "Programa de Gestão Governamental",
        }
        return mapping.get(self.domain_name, self.domain_name.strip("_").upper())

    def _infer_entity_description(self, entity_name: str) -> str:
        n = entity_name.lower()

        # PAE específico
        if self.domain_name in {"_pae", "pae"}:
            if "processo" in n:
                return "Entidade associada ao fluxo de processos do planejamento."
            if "despacho" in n:
                return "Entidade associada ao registro de despacho ou movimentação de processo."
            if "notificacao" in n:
                return "Entidade associada a notificações do fluxo."
            if "tipodocumento" in n or "documento" in n:
                return "Entidade associada à classificação documental."
            if "departamento" in n or "orgao" in n or "setor" in n:
                return "Entidade associada à estrutura organizacional."
            if "acesso" in n or "usuario" in n or "grupo" in n or "perfil" in n:
                return "Entidade associada a controle de acesso e permissões."
            if "tag" in n:
                return "Entidade associada à classificação ou etiquetagem de processos."

        # genérico / outros domínios
        if "diretriz" in n:
            return "Entidade associada a direcionamento estratégico."
        if "programaobjetivo" in n:
            return "Entidade associada a objetivos vinculados a programas."
        if n == "programa" or "programa" in n:
            return "Entidade associada à organização programática do domínio."
        if n == "acao" or "acao" in n:
            return "Entidade associada à execução operacional."
        if "meta" in n:
            return "Entidade associada a metas físicas, qualitativas ou financeiras."
        if "indicador" in n:
            return "Entidade associada à medição de desempenho."
        if "fonte" in n:
            return "Entidade associada à origem de recursos ou detalhamento financeiro."
        if "regiao" in n or "municip" in n:
            return "Entidade associada à regionalização ou recorte territorial."
        if "status" in n:
            return "Entidade associada à classificação de estado ou situação."
        if "config" in n:
            return "Entidade associada a configuração sistêmica."
        return "Entidade estrutural identificada no schema."

    def _infer_entity_category(self, entity_name: str) -> str:
        n = entity_name.lower()

        # PAE específico
        if self.domain_name in {"_pae", "pae"}:
            if any(x in n for x in ["processo", "despacho", "notificacao"]):
                return "operacional"
            if any(x in n for x in ["orgao", "departamento", "setor", "unidade"]):
                return "organizacional"
            if any(x in n for x in ["acesso", "usuario", "grupo", "perfil", "permissao"]):
                return "controle_acesso"
            if any(x in n for x in ["tag", "tipodocumento", "documento"]):
                return "classificacao"

        if any(x in n for x in ["diretriz", "eixo", "objetivoestrategico"]):
            return "estrategica"
        if any(x in n for x in ["programa", "acao", "objetivo"]):
            return "operacional"
        if any(x in n for x in ["fonte", "valor", "teto", "despesa", "finance"]):
            return "financeira"
        if any(x in n for x in ["meta", "indicador"]):
            return "monitoramento"
        if any(x in n for x in ["regiao", "municip", "territ"]):
            return "territorial"
        if any(x in n for x in ["status", "config"]):
            return "controle"
        return "geral"

    def _infer_relationship_type(self, origem: str, destino: str) -> str:
        origem_l = origem.lower()
        destino_l = destino.lower()

        # PAE específico
        if self.domain_name in {"_pae", "pae"}:
            if "despacho" in origem_l and "processo" in destino_l:
                return "tramita_em"
            if "notificacao" in origem_l and ("usuario" in destino_l or "grupo" in destino_l):
                return "notifica"
            if "processo" in origem_l and ("departamento" in destino_l or "orgao" in destino_l):
                return "pertence_a"
            if "tag" in origem_l and "processo" in destino_l:
                return "classifica"
            if origem_l == destino_l and any(x in origem_l for x in ["grupo", "modulo", "transacao"]):
                return "auto_relaciona"

        if "meta" in origem_l:
            return "detalha"
        if "fonte" in origem_l:
            return "detalha"
        if "indicador" in origem_l:
            return "mede"
        if "regiao" in origem_l or "municip" in origem_l:
            return "regionaliza"
        if "programaobjetivo" in origem_l and "programa" in destino_l:
            return "pertence_a"
        if origem_l == "acao" and "programa" in destino_l:
            return "pertence_a"
        if origem_l == "acao" and "objetivo" in destino_l:
            return "pode_vincular_a"
        return "relaciona_com"

    def _infer_candidate_rules(self, valid_entities: dict[str, dict]) -> list[str]:
        rules = []
        entity_names = list(valid_entities.keys())

        # PAE específico
        if self.domain_name in {"_pae", "pae"}:
            if any("processo" in e for e in entity_names):
                rules.append("O domínio possui gestão de processos.")
            if any("despacho" in e for e in entity_names):
                rules.append("O domínio possui tramitação ou despacho associado a processos.")
            if any("notificacao" in e for e in entity_names):
                rules.append("O domínio possui envio ou controle de notificações.")
            if any(x in e for e in entity_names for x in ["acesso", "usuario", "grupo", "perfil"]):
                rules.append("O domínio possui controle de acesso por usuários, grupos ou permissões.")
            if any(x in e for e in entity_names for x in ["tag", "tipodocumento", "documento"]):
                rules.append("O domínio possui mecanismos de classificação documental ou temática.")

        if self._has_any(valid_entities, ["ano1", "ano2", "ano3", "ano4"], search_columns=True):
            rules.append("O domínio possui distribuição temporal em múltiplos anos, possivelmente com planejamento plurianual.")

        if self._has_any(valid_entities, ["fonte", "valor", "vl", "teto"], search_columns=True):
            rules.append("O domínio possui componentes financeiros com detalhamento por valores e possivelmente por fonte de recurso.")

        if self._has_any(valid_entities, ["revisao", "original", "ajuste", "reducao"], search_columns=True):
            rules.append("O domínio possui sinais de revisão, versionamento ou ajuste de valores/metas.")

        if self._has_any(valid_entities, ["regiao", "municip", "territ"], search_columns=True):
            rules.append("O domínio possui regionalização ou recorte territorial.")

        if any("programa" in e for e in entity_names) and any(e == "acao" or "acao" in e for e in entity_names):
            rules.append("Há indícios de uma estrutura hierárquica entre programa e ação.")

        if any("objetivo" in e for e in entity_names) and any("meta" in e for e in entity_names):
            rules.append("Há indícios de associação entre objetivos e metas.")

        if any("indicador" in e for e in entity_names):
            rules.append("Há entidades voltadas à medição de desempenho por indicadores.")

        return sorted(dict.fromkeys(rules))

    def _infer_expected_signals(self) -> dict:
        return {
            "temporalidade": ["ano", "ano1", "ano2", "ano3", "ano4", "exercicio", "inicio", "fim"],
            "financeiro": ["valor", "vl", "fonte", "orcamento", "despesa", "receita", "teto"],
            "regionalizacao": ["regiao", "municipio", "territorio", "regional"],
            "status": ["status", "ativo", "inativo", "flag", "situacao"],
            "versionamento": ["revisao", "versao", "original", "ajuste", "reducao"],
        }

    def _has_any(self, valid_entities: dict[str, dict], terms: list[str], search_columns: bool = False) -> bool:
        names_joined = " ".join(valid_entities.keys()).lower()
        if any(term in names_joined for term in terms):
            return True

        if not search_columns:
            return False

        for entity in valid_entities.values():
            for col in entity.get("columns", []):
                col_name = (col.get("name") or "").strip().lower()
                if any(term in col_name for term in terms):
                    return True

        return False

    def _deduplicate_relationships(self, relationships: list[dict]) -> list[dict]:
        seen = set()
        result = []

        for rel in relationships:
            key = (
                rel.get("origem", ""),
                rel.get("destino", ""),
                rel.get("tipo", ""),
            )
            if key not in seen:
                seen.add(key)
                result.append(rel)

        return result