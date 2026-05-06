from pathlib import Path

from core.scanner import encontrar_arquivo_da_action
from core.method_analyzer import analisar_metodo_em_arquivo


class ActionTraceAnalyzer:
    def __init__(self, project_path: str):
        self.project_path = project_path

    def trace_actions(self, actions: list[dict]) -> list[dict]:
        traces = []

        for action in actions:
            classe = action.get("classe")
            metodo = action.get("metodo")
            params = action.get("params", {}) or {}

            item = {
                "classe": classe,
                "metodo": metodo,
                "params": params,
                "backend_hint": action.get("backend_hint"),
                "arquivo_classe": None,
                "metodo_encontrado": False,
                "assinatura": None,
                "linha_inicio": None,
                "linha_fim": None,
                "queries_completas": [],
                "sql_suspeito": [],
                "tabelas": [],
                "procedures": [],
                "includes": [],
                "erro": None,
            }

            try:
                arquivo = encontrar_arquivo_da_action(self.project_path, classe)

                if not arquivo:
                    item["erro"] = f"Controller/classe '{classe}' não encontrado."
                    traces.append(item)
                    continue

                item["arquivo_classe"] = str(arquivo)

                dados = analisar_metodo_em_arquivo(arquivo, metodo)

                if not dados:
                    item["erro"] = f"Método '{metodo}' não encontrado em '{Path(arquivo).name}'."
                    traces.append(item)
                    continue

                item["metodo_encontrado"] = True
                item["assinatura"] = dados.get("assinatura")
                item["linha_inicio"] = dados.get("linha_inicio")
                item["linha_fim"] = dados.get("linha_fim")
                item["queries_completas"] = dados.get("queries_completas", []) or []
                item["sql_suspeito"] = dados.get("sql_suspeito", []) or []
                item["tabelas"] = dados.get("tabelas", []) or []
                item["procedures"] = dados.get("procedures", []) or []
                item["includes"] = dados.get("includes", []) or []

            except Exception as exc:
                item["erro"] = str(exc)

            traces.append(item)

        return traces

    def collect_actions_from_ui_results(self, ui_results: list[dict]) -> list[dict]:
        all_actions = []

        for item in ui_results:
            analise_ui = item.get("analise_ui", {}) or {}

            all_actions.extend(analise_ui.get("actions", []) or [])

            for load in analise_ui.get("dynamic_loads", []) or []:
                all_actions.extend(load.get("actions", []) or [])

            includes_relevantes = analise_ui.get("includes_relevantes", []) or []
            for include_item in includes_relevantes:
                analise_rec = include_item.get("analise") or {}

                all_actions.extend(analise_rec.get("actions", []) or [])

                for load in analise_rec.get("dynamic_loads", []) or []:
                    all_actions.extend(load.get("actions", []) or [])

            unique = []
            seen = set()

        for action in all_actions:
            key = (
                action.get("classe", "").lower(),
                action.get("metodo", "").lower(),
                tuple(sorted((action.get("params") or {}).items())),
            )
            if key not in seen:
                seen.add(key)
                unique.append(action)

        return unique