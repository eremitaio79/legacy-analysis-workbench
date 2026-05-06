from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.ai_analyzer import GeminiAnalyzer, GeminiAnalyzerError


class UIFlowAICommentary:
    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        prompt_file: str = "ui_flow_ai_analysis_prompt.txt",
    ):
        self.analyzer = analyzer
        self.prompt_file = prompt_file

    def _load_prompt_template(self) -> str:
        prompt_path = Path("prompts") / self.prompt_file

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt não encontrado: {prompt_path}")

        return prompt_path.read_text(encoding="utf-8")

    def _build_payload(self, trace_data: dict) -> str:
        template = self._load_prompt_template()

        json_data = json.dumps(trace_data, ensure_ascii=False, indent=2)

        return f"""
{template}

=== DADOS DO TRACE ===

{json_data}
"""

    def _build_cache_key(self, trace_data: dict) -> str:
        raw = json.dumps(trace_data, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"ui_flow_trace__{digest}"

    def generate(self, trace_data: dict, prefer_cache: bool = True) -> str:
        prompt = self._build_payload(trace_data)
        cache_key = self._build_cache_key(trace_data)

        try:
            return self.analyzer.analyze_free_text(
                prompt=prompt,
                use_cache_key=cache_key,
                prefer_cache=prefer_cache,
                max_output_tokens=8192,
            )
        except GeminiAnalyzerError as exc:
            raise RuntimeError(f"Erro na análise IA: {exc}") from exc