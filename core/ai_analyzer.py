from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types

from core.config import (
    PROMPTS_DIR,
    SIGPLAN_AI_CACHE_ENABLED,
    SIGPLAN_AI_CACHE_DIR,
    SIGPLAN_AI_PROMPT_FILE,
)


DEFAULT_MODEL = "gemini-2.5-flash"


@dataclass
class AIAnalysisInput:
    class_name: str
    method_name: str
    php_code: str
    sql_blocks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    file_path: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class Finding:
    title: str
    severity: str
    description: str


@dataclass
class Suggestion:
    title: str
    priority: str
    description: str


@dataclass
class AIAnalysisResult:
    summary: str
    purpose: str
    execution_flow: List[str]
    tables_used: List[str]
    dependencies_used: List[str]
    risks: List[Finding]
    suggestions: List[Suggestion]
    raw_model_text: Optional[str] = None
    from_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GeminiAnalyzerError(Exception):
    pass


class GeminiAnalyzer:
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "gemini",
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
        cache_enabled: bool = SIGPLAN_AI_CACHE_ENABLED,
        cache_dir: str = SIGPLAN_AI_CACHE_DIR,
        prompt_file: str = SIGPLAN_AI_PROMPT_FILE,
    ) -> None:
        self.provider = (provider or "gemini").strip().lower()
        if self.provider != "gemini":
            raise GeminiAnalyzerError(
                f"Provider '{self.provider}' ainda não suportado. No momento, use 'gemini'."
            )

        resolved_key, error = self._resolve_and_validate_api_key(api_key)
        if error:
            raise GeminiAnalyzerError(error)

        self.api_key = resolved_key
        self.model = model
        self.temperature = temperature
        self.cache_enabled = cache_enabled
        self.cache_dir = Path(cache_dir)
        self.prompt_file = prompt_file

        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.client = genai.Client(api_key=self.api_key)

    # -------------------------------------------------------
    # API key
    # -------------------------------------------------------

    @staticmethod
    def _resolve_and_validate_api_key(api_key: Optional[str] = None) -> Tuple[str, str]:
        key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()

        if not key:
            return "", (
                "GEMINI_API_KEY não configurada. "
                "Defina a variável de ambiente ou informe a chave no arquivo .env."
            )

        if len(key) < 20:
            return "", (
                "GEMINI_API_KEY parece inválida ou incompleta. "
                "Verifique se a chave foi copiada corretamente."
            )

        return key, ""

    @classmethod
    def has_valid_api_key(cls, api_key: Optional[str] = None) -> bool:
        _, error = cls._resolve_and_validate_api_key(api_key)
        return not error

    @classmethod
    def get_api_key_error(cls, api_key: Optional[str] = None) -> str:
        _, error = cls._resolve_and_validate_api_key(api_key)
        return error

    # -------------------------------------------------------
    # Prompt
    # -------------------------------------------------------

    @staticmethod
    def list_available_prompts() -> List[str]:
        if not PROMPTS_DIR.exists():
            return []

        arquivos = []
        for item in PROMPTS_DIR.iterdir():
            if item.is_file() and item.suffix.lower() in {".txt", ".md"}:
                arquivos.append(item.name)

        return sorted(arquivos)

    def _load_prompt_template(self) -> str:
        prompt_path = PROMPTS_DIR / self.prompt_file

        if not prompt_path.exists():
            raise GeminiAnalyzerError(
                f"Arquivo de prompt não encontrado: {prompt_path}"
            )

        return prompt_path.read_text(encoding="utf-8")

    def _build_prompt(self, data: AIAnalysisInput) -> str:
        sql_text = "\n\n".join(
            f"-- SQL #{idx + 1}\n{sql}" for idx, sql in enumerate(data.sql_blocks)
        ).strip()

        if not sql_text:
            sql_text = "Nenhum SQL extraído."

        deps_text = "\n".join(f"- {d}" for d in data.dependencies).strip()
        if not deps_text:
            deps_text = "- Nenhuma"

        tables_text = "\n".join(f"- {t}" for t in data.tables).strip()
        if not tables_text:
            tables_text = "- Nenhuma"

        template = self._load_prompt_template()

        return template.format(
            class_name=data.class_name,
            method_name=data.method_name,
            file_path=data.file_path or "não informado",
            source_url=data.source_url or "não informada",
            php_code=data.php_code,
            sql_text=sql_text,
            deps_text=deps_text,
            tables_text=tables_text,
        )

    # -------------------------------------------------------
    # Cache
    # -------------------------------------------------------

    def _build_cache_payload(self, data: AIAnalysisInput) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_file": self.prompt_file,
            "class_name": data.class_name,
            "method_name": data.method_name,
            "php_code": data.php_code,
            "sql_blocks": data.sql_blocks,
            "dependencies": data.dependencies,
            "tables": data.tables,
            "file_path": data.file_path,
            "source_url": data.source_url,
        }

    def _compute_cache_key(self, data: AIAnalysisInput) -> str:
        payload = self._build_cache_payload(data)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _get_cache_file(self, data: AIAnalysisInput) -> Path:
        cache_key = self._compute_cache_key(data)

        class_part = (data.class_name or "sem_classe").strip().replace(" ", "_")
        method_part = (data.method_name or "sem_metodo").strip().replace(" ", "_")
        prefix = f"{class_part}__{method_part}"

        safe_prefix = "".join(
            ch if ch.isalnum() or ch in {"_", "-"} else "_"
            for ch in prefix
        )
        return self.cache_dir / f"{safe_prefix}__{cache_key[:16]}.json"

    def has_cache_for(self, data: AIAnalysisInput) -> bool:
        if not self.cache_enabled:
            return False
        return self._get_cache_file(data).exists()

    def _load_from_cache(self, data: AIAnalysisInput) -> Optional[AIAnalysisResult]:
        if not self.cache_enabled:
            return None

        cache_file = self._get_cache_file(data)
        if not cache_file.exists():
            return None

        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            result = self._coerce_result(payload)
            result.from_cache = True
            return result
        except Exception:
            return None

    def _save_to_cache(self, data: AIAnalysisInput, result: AIAnalysisResult) -> None:
        if not self.cache_enabled:
            return

        cache_file = self._get_cache_file(data)

        try:
            payload = result.to_dict()
            payload["from_cache"] = False
            cache_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def clear_cache(self) -> int:
        if not self.cache_dir.exists():
            return 0

        removidos = 0
        for arquivo in self.cache_dir.glob("*.json"):
            try:
                arquivo.unlink()
                removidos += 1
            except Exception:
                pass

        return removidos

    def get_cache_stats(self) -> Dict[str, Any]:
        if not self.cache_dir.exists():
            return {
                "enabled": self.cache_enabled,
                "cache_dir": str(self.cache_dir),
                "exists": False,
                "files": 0,
            }

        arquivos = list(self.cache_dir.glob("*.json"))
        return {
            "enabled": self.cache_enabled,
            "cache_dir": str(self.cache_dir),
            "exists": True,
            "files": len(arquivos),
        }

    # -------------------------------------------------------
    # Execução principal
    # -------------------------------------------------------

    def analyze(self, data: AIAnalysisInput, prefer_cache: bool = True) -> AIAnalysisResult:
        if prefer_cache:
            cached = self._load_from_cache(data)
            if cached:
                return cached

        prompt = self._build_prompt(data)
        schema = self._build_response_schema()

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=8192,
                ),
            )
        except Exception as exc:
            raise GeminiAnalyzerError(f"Falha ao chamar Gemini: {exc}") from exc

        raw_text = getattr(response, "text", None)

        if not raw_text:
            raise GeminiAnalyzerError("A resposta do Gemini veio vazia.")

        parsed = self._safe_parse_json(raw_text)
        result = self._coerce_result(parsed)
        result.raw_model_text = raw_text
        result.from_cache = False

        self._save_to_cache(data, result)

        return result


    def analyze_free_text(
        self,
        prompt: str,
        use_cache_key: Optional[str] = None,
        prefer_cache: bool = True,
        max_output_tokens: int = 8192,
    ) -> str:
        """
        Executa uma análise livre em texto, sem schema JSON fixo.
        Útil para comentários técnicos sobre dados, estrutura de tabelas,
        includes, scripts JS e outros contextos que não se encaixam no
        AIAnalysisInput tradicional.
        """
        if not prompt or not prompt.strip():
            raise GeminiAnalyzerError("Prompt vazio para analyze_free_text().")

        cache_file = None

        if self.cache_enabled and use_cache_key:
            cache_file = self._get_free_text_cache_file(use_cache_key)

            if prefer_cache and cache_file.exists():
                try:
                    payload = json.loads(cache_file.read_text(encoding="utf-8"))
                    texto = (payload.get("text") or "").strip()
                    if texto:
                        return texto
                except Exception:
                    pass

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )
        except Exception as exc:
            raise GeminiAnalyzerError(f"Falha ao chamar Gemini em analyze_free_text: {exc}") from exc

        raw_text = getattr(response, "text", None)

        if not raw_text or not raw_text.strip():
            raise GeminiAnalyzerError("A resposta do Gemini veio vazia em analyze_free_text().")

        texto_final = raw_text.strip()

        if cache_file:
            try:
                cache_file.write_text(
                    json.dumps(
                        {
                            "text": texto_final,
                            "model": self.model,
                            "provider": self.provider,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

        return texto_final

    def _get_free_text_cache_file(self, cache_key: str) -> Path:
        safe_key = "".join(
            ch if ch.isalnum() or ch in {"_", "-"} else "_"
            for ch in cache_key.strip()
        )
        if not safe_key:
            safe_key = "free_text"

        digest = hashlib.sha256(safe_key.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"free_text__{safe_key[:60]}__{digest}.json"

    # -------------------------------------------------------
    # Renderização
    # -------------------------------------------------------

    def render_markdown(self, result: AIAnalysisResult, source: AIAnalysisInput) -> str:
        lines: List[str] = []

        lines.append(f"# Análise IA — {source.class_name}.{source.method_name}")
        lines.append("")

        if source.file_path:
            lines.append(f"**Arquivo:** `{source.file_path}`  ")
        if source.source_url:
            lines.append(f"**URL de origem:** `{source.source_url}`  ")

        lines.append(f"**Provider:** `{self.provider}`  ")
        lines.append(f"**Modelo:** `{self.model}`  ")
        lines.append(f"**Prompt:** `{self.prompt_file}`  ")
        lines.append(f"**Origem da análise:** `{'cache' if result.from_cache else 'ia'}`  ")

        lines.append("")
        lines.append("## Resumo")
        lines.append(result.summary or "Sem resumo.")
        lines.append("")

        lines.append("## Finalidade")
        lines.append(result.purpose or "Não informada.")
        lines.append("")

        lines.append("## Fluxo de execução")
        if result.execution_flow:
            for step in result.execution_flow:
                lines.append(f"- {step}")
        else:
            lines.append("- Nenhum passo informado.")

        lines.append("")
        lines.append("## Diagrama Mermaid")
        mermaid = self._execution_flow_to_mermaid(result.execution_flow)
        lines.append("```mermaid")
        lines.append(mermaid)
        lines.append("```")

        lines.append("")
        lines.append("## Tabelas utilizadas")
        if result.tables_used:
            for table in result.tables_used:
                lines.append(f"- `{table}`")
        else:
            lines.append("- Nenhuma tabela identificada.")

        lines.append("")
        lines.append("## Dependências")
        if result.dependencies_used:
            for dep in result.dependencies_used:
                lines.append(f"- `{dep}`")
        else:
            lines.append("- Nenhuma dependência identificada.")

        lines.append("")
        lines.append("## Possíveis problemas")
        if result.risks:
            for item in result.risks:
                lines.append(
                    f"- **[{item.severity.upper()}] {item.title}** — {item.description}"
                )
        else:
            lines.append("- Nenhum problema relevante apontado.")

        lines.append("")
        lines.append("## Sugestões de melhoria")
        if result.suggestions:
            for item in result.suggestions:
                lines.append(
                    f"- **[{item.priority.upper()}] {item.title}** — {item.description}"
                )
        else:
            lines.append("- Nenhuma sugestão retornada.")

        lines.append("")
        return "\n".join(lines)

    def _execution_flow_to_mermaid(self, steps: List[str]) -> str:
        if not steps:
            return "flowchart TD\n    A[Início] --> Z[Fim]"

        lines = ["flowchart TD"]
        lines.append("    A[Início]")

        previous = "A"

        for idx, step in enumerate(steps, start=1):
            node = f"N{idx}"
            safe_step = self._sanitize_mermaid_label(step, idx)
            lines.append(f'    {previous} --> {node}["{safe_step}"]')
            previous = node

        lines.append(f"    {previous} --> Z[Fim]")

        return "\n".join(lines)

    def _sanitize_mermaid_label(self, text: Optional[str], idx: int = 0) -> str:
        value = (text or "").strip()
        if not value:
            value = f"Passo {idx}" if idx else "Passo"

        value = value.replace('"', "'")
        value = value.replace("`", "'")
        value = value.replace("\n", " ")
        value = " ".join(value.split())

        return value

    # -------------------------------------------------------
    # Schema
    # -------------------------------------------------------

    def _build_response_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "purpose": {"type": "string"},
                "execution_flow": {"type": "array", "items": {"type": "string"}},
                "tables_used": {"type": "array", "items": {"type": "string"}},
                "dependencies_used": {"type": "array", "items": {"type": "string"}},
                "risks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "severity": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "priority": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
            },
        }

    # -------------------------------------------------------
    # Parsing e coerção
    # -------------------------------------------------------

    def _safe_parse_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiAnalyzerError(
                f"Gemini retornou JSON inválido:\n{text}"
            ) from exc

    def _coerce_result(self, payload: Dict[str, Any]) -> AIAnalysisResult:
        risks = [
            Finding(
                title=r.get("title", ""),
                severity=r.get("severity", "medium"),
                description=r.get("description", ""),
            )
            for r in payload.get("risks", [])
            if isinstance(r, dict)
        ]

        suggestions = [
            Suggestion(
                title=s.get("title", ""),
                priority=s.get("priority", "medium"),
                description=s.get("description", ""),
            )
            for s in payload.get("suggestions", [])
            if isinstance(s, dict)
        ]

        return AIAnalysisResult(
            summary=payload.get("summary", ""),
            purpose=payload.get("purpose", ""),
            execution_flow=payload.get("execution_flow", []),
            tables_used=payload.get("tables_used", []),
            dependencies_used=payload.get("dependencies_used", []),
            risks=risks,
            suggestions=suggestions,
            raw_model_text=payload.get("raw_model_text"),
            from_cache=bool(payload.get("from_cache", False)),
        )