from __future__ import annotations

from typing import List

from core.ai_analyzer import GeminiAnalyzer, GeminiAnalyzerError


class CodeHealthAICommentary:
    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        prompt_file: str = "code_health_ai_analysis_prompt.txt",
    ) -> None:
        self.analyzer = analyzer
        self.prompt_file = prompt_file

    def generate(self, scan_result) -> str:
        payload = self._build_payload(scan_result)

        try:
            response = self.analyzer.analyze_free_text(payload)
        except GeminiAnalyzerError as exc:
            raise RuntimeError(f"Erro na análise IA: {exc}") from exc

        return response.strip()

    # ---------------------------------------------
    # Montagem inteligente do input
    # ---------------------------------------------

    def _build_payload(self, scan_result) -> str:
        summary = self._build_summary(scan_result)
        top_files = self._build_top_files(scan_result)
        categories = self._build_categories(scan_result)
        samples = self._build_samples(scan_result)

        return f"""
ANÁLISE DE SAÚDE DE CÓDIGO - SIGBOARD

## RESUMO
{summary}

## CATEGORIAS DE PROBLEMAS
{categories}

## ARQUIVOS MAIS CRÍTICOS
{top_files}

## AMOSTRAS DE PROBLEMAS
{samples}

---

Com base nas informações acima:

1. Faça um diagnóstico técnico do sistema
2. Identifique os principais riscos
3. Aponte padrões recorrentes
4. Diferencie problemas pontuais de problemas estruturais
5. Sugira um plano de ação priorizado
6. Seja direto, técnico e objetivo
"""

    def _build_summary(self, r) -> str:
        return f"""
Arquivos analisados: {r.php_files_total}
Achados totais: {r.findings_total}

Críticos: {r.findings_by_severity.get('critical', 0)}
Warnings: {r.findings_by_severity.get('warning', 0)}
Info: {r.findings_by_severity.get('info', 0)}
"""

    def _build_categories(self, r) -> str:
        linhas = []
        for cat, total in sorted(r.findings_by_category.items(), key=lambda x: -x[1]):
            linhas.append(f"- {cat}: {total}")
        return "\n".join(linhas)

    def _build_top_files(self, r) -> str:
        linhas = []
        for item in r.top_problematic_files[:10]:
            linhas.append(
                f"- {item['relative_path']} | total={item['total_findings']} | "
                f"critical={item['critical']} | warning={item['warning']}"
            )
        return "\n".join(linhas)

    def _build_samples(self, r) -> str:
        samples: List[str] = []

        for file in r.files:
            for f in file.findings[:3]:
                samples.append(
                    f"{file.metadata.relative_path} | linha {f.line_number} | {f.title}"
                )
            if len(samples) >= 25:
                break

        return "\n".join(samples[:25])