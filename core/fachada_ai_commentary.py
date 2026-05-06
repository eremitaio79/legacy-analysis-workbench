from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional

from core.ai_analyzer import GeminiAnalyzer
from core.fachada_analyzer import FachadaAnalysisResult, MethodInfo


DEFAULT_FACHADA_AI_PROMPT_FILE = "fachada_ai_analysis_prompt.txt"


class FachadaAICommentary:
    """
    Gera comentário técnico com IA a partir do resultado estrutural do FachadaAnalyzer.
    Usa o GeminiAnalyzer existente via analyze_free_text().
    """

    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        prompt_file: str = DEFAULT_FACHADA_AI_PROMPT_FILE,
    ) -> None:
        self.analyzer = analyzer
        self.prompt_file = prompt_file

    def generate(
        self,
        result: FachadaAnalysisResult,
        prefer_cache: bool = True,
        max_methods: int = 12,
        include_sql_snippets: bool = True,
    ) -> str:
        prompt = self._build_prompt(
            result=result,
            max_methods=max_methods,
            include_sql_snippets=include_sql_snippets,
        )

        cache_key = self._build_cache_key(
            result=result,
            max_methods=max_methods,
            include_sql_snippets=include_sql_snippets,
        )

        return self.analyzer.analyze_free_text(
            prompt=prompt,
            use_cache_key=cache_key,
            prefer_cache=prefer_cache,
            max_output_tokens=8192,
        )

    def _build_prompt(
        self,
        result: FachadaAnalysisResult,
        max_methods: int,
        include_sql_snippets: bool,
    ) -> str:
        template = self._load_prompt_template()
        payload = self._build_payload(
            result=result,
            max_methods=max_methods,
            include_sql_snippets=include_sql_snippets,
        )

        return (
            f"{template.strip()}\n\n"
            f"=== DADOS ESTRUTURAIS DA FACHADA ===\n"
            f"{payload}\n"
        )

    def _load_prompt_template(self) -> str:
        prompt_path = Path("prompts") / self.prompt_file

        if not prompt_path.exists():
            return (
                "Você é um especialista em manutenção de sistemas legados PHP 7.3 com SQL Server 2008.\n"
                "Analise tecnicamente a fachada com base apenas nos dados estruturais fornecidos.\n"
                "Explique a responsabilidade provável da fachada, métodos críticos, riscos, acoplamentos,\n"
                "mistura de responsabilidades, indícios de dívida técnica e por onde começar a manutenção.\n"
                "Responda em português, com objetividade, clareza e utilidade prática.\n"
                "Quando fizer inferências, diga explicitamente que são inferências.\n"
            )

        return prompt_path.read_text(encoding="utf-8")

    def _build_payload(
        self,
        result: FachadaAnalysisResult,
        max_methods: int,
        include_sql_snippets: bool,
    ) -> str:
        ranked_methods = self._rank_relevant_methods(result.methods)
        selected_methods = ranked_methods[:max_methods]

        payload = {
            "classe": result.class_name,
            "arquivo": result.resolved_path,
            "namespace": result.namespace,
            "metodo_alvo": result.target_method,
            "total_linhas": result.total_lines,
            "metodos_publicos": result.public_methods_count,
            "dependencias_total": len(result.dependencies),
            "tabelas_total": len(result.tables),
            "sql_blocks_total": len(result.sql_blocks),
            "warnings": result.warnings,
            "dependencias": result.dependencies[:120],
            "tabelas": result.tables[:120],
            "metodos_relevantes": [
                self._serialize_method(
                    method=m,
                    include_sql_snippets=include_sql_snippets,
                )
                for m in selected_methods
            ],
        }

        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _serialize_method(
        self,
        method: MethodInfo,
        include_sql_snippets: bool,
    ) -> dict:
        size = method.end_line - method.start_line + 1

        method_payload = {
            "nome": method.name,
            "linhas": {
                "inicio": method.start_line,
                "fim": method.end_line,
                "tamanho": size,
            },
            "parametros": method.parameters,
            "calls_count": len(method.calls),
            "static_calls_count": len(method.static_calls),
            "new_instances_count": len(method.new_instances),
            "includes_count": len(method.includes),
            "requires_count": len(method.requires),
            "sql_blocks_count": len(method.sql_blocks),
            "tabelas": method.tables,
            "notes": method.notes,
            "new_instances": [n.class_name for n in method.new_instances[:20]],
            "static_calls": [
                f"{s.class_name}::{s.method}()"
                for s in method.static_calls[:20]
            ],
            "method_calls": [
                f"{c.target}->{c.method}()"
                for c in method.calls[:20]
            ],
        }

        if include_sql_snippets and method.sql_blocks:
            method_payload["sql_preview"] = [
                {
                    "line": block.line,
                    "tables": block.tables,
                    "sql": self._truncate_sql(block.sql),
                }
                for block in method.sql_blocks[:3]
            ]

        return method_payload

    def _truncate_sql(self, sql: str, max_chars: int = 1200) -> str:
        value = (sql or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip() + "\n-- [SQL truncado]"

    def _rank_relevant_methods(self, methods: List[MethodInfo]) -> List[MethodInfo]:
        def score(method: MethodInfo):
            size = method.end_line - method.start_line + 1
            sql_count = len(method.sql_blocks)
            call_count = len(method.calls) + len(method.static_calls)
            new_count = len(method.new_instances)
            notes_count = len(method.notes)

            return (
                sql_count > 0,
                sql_count,
                size,
                call_count,
                new_count,
                notes_count,
                method.name.lower(),
            )

        return sorted(methods, key=score, reverse=True)

    def _build_cache_key(
        self,
        result: FachadaAnalysisResult,
        max_methods: int,
        include_sql_snippets: bool,
    ) -> str:
        payload = {
            "type": "fachada_ai_commentary",
            "class_name": result.class_name,
            "resolved_path": result.resolved_path,
            "target_method": result.target_method,
            "warnings": result.warnings,
            "dependencies": result.dependencies,
            "tables": result.tables,
            "methods": [
                {
                    "name": m.name,
                    "start_line": m.start_line,
                    "end_line": m.end_line,
                    "parameters": m.parameters,
                    "notes": m.notes,
                    "tables": m.tables,
                    "calls_count": len(m.calls),
                    "static_calls_count": len(m.static_calls),
                    "new_instances_count": len(m.new_instances),
                    "sql_blocks": [
                        {
                            "line": b.line,
                            "tables": b.tables,
                            "sql": b.sql if include_sql_snippets else "",
                        }
                        for b in m.sql_blocks
                    ],
                }
                for m in result.methods
            ],
            "model": self.analyzer.model,
            "provider": self.analyzer.provider,
            "prompt_file": self.prompt_file,
            "max_methods": max_methods,
            "include_sql_snippets": include_sql_snippets,
        }

        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        class_name = (result.class_name or "sem_classe").strip()
        target_method = (result.target_method or "fachada_completa").strip()

        safe_name = "".join(
            ch if ch.isalnum() or ch in {"_", "-"} else "_"
            for ch in f"fachada_ai__{class_name}__{target_method}"
        )

        return f"{safe_name}__{digest}"