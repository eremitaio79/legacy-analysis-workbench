from __future__ import annotations

from pathlib import Path

from core.ai_analyzer import GeminiAnalyzer, GeminiAnalyzerError


class SchemaCrossAICommentaryService:
    def __init__(
        self,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash",
        prompt_file: str = "schema_cross_ai_analysis_prompt.txt",
    ):
        self.analyzer = GeminiAnalyzer(
            provider=provider,
            model=model,
            prompt_file=prompt_file,
        )

    def generate(
        self,
        cross_markdown: str,
        domain_name: str,
        prefer_cache: bool = True,
    ) -> str:
        prompt = self._build_prompt(
            cross_markdown=cross_markdown,
            domain_name=domain_name,
        )

        cache_key = f"schema_cross_ai_{domain_name}".strip("_")

        try:
            return self.analyzer.analyze_free_text(
                prompt=prompt,
                use_cache_key=cache_key,
                prefer_cache=prefer_cache,
            )
        except GeminiAnalyzerError:
            raise
        except Exception as exc:
            raise GeminiAnalyzerError(f"Falha ao gerar comentário IA do cruzamento: {exc}") from exc

    def _build_prompt(self, cross_markdown: str, domain_name: str) -> str:
        return f"""
Você é um analista técnico-funcional especialista em sistemas legados governamentais.

Sua tarefa é revisar um relatório de cruzamento entre schema estrutural e domain map semântico
do domínio "{domain_name}".

Objetivos da análise:
1. Produzir um parecer técnico claro e objetivo.
2. Identificar pontos fortes do domínio modelado.
3. Identificar ruídos, entidades suspeitas, aliases ruins ou excesso de granularidade.
4. Apontar lacunas e inconsistências do mapa semântico.
5. Sugerir melhorias concretas no domain map.
6. Informar se o domínio parece maduro, parcialmente maduro ou ainda raso.

Regras de saída:
- Responda em português.
- Seja técnico, claro e direto.
- Não invente entidades nem fatos que não estejam apoiados no relatório.
- Quando sugerir ajuste, diga exatamente o que melhorar.
- Estruture a resposta em Markdown.
- Use as seções abaixo, exatamente nesta ordem:

# Parecer Técnico IA
## Visão Geral
## Pontos Fortes
## Inconsistências e Ruídos
## Sugestões de Refinamento
## Avaliação de Maturidade do Domínio
## Próximos Passos Recomendados

Relatório base:

{cross_markdown}
""".strip()