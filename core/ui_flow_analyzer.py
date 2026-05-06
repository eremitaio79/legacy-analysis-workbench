import re
from pathlib import Path


class UIFlowAnalyzer:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def analyze_html_for_actions(self, file_path: str, recursive_depth: int = 0, max_depth: int = 1) -> dict:
        path = Path(file_path)

        if not path.exists():
            return {"error": f"Arquivo não encontrado: {file_path}"}

        content = path.read_text(encoding="utf-8", errors="ignore")
        content_norm = self._normalize_content(content)

        onclicks = self._extract_onclicks(content_norm)
        actions_in_content = self.extract_actions(content_norm)
        actions_in_onclicks = self.extract_actions_from_onclicks(onclicks)
        includes_internos = self._extract_include_paths(content_norm)
        clickable_elements = self._extract_clickable_elements(content_norm)
        dynamic_loads = self._extract_dynamic_loads(content_norm)

        merged_actions = self._merge_actions(actions_in_content + actions_in_onclicks)

        for elem in clickable_elements:
            for action in elem.get("actions", []):
                merged_actions.append(action)

        for load in dynamic_loads:
            for action in load.get("actions", []):
                merged_actions.append(action)

        merged_actions = self._merge_actions(merged_actions)

        result = {
            "arquivo": str(path),
            "modals": self._extract_modals(content_norm),
            "buttons": self._extract_buttons(content_norm),
            "links": self._extract_links_with_text(content_norm),
            "clickable_elements": clickable_elements,
            "onclicks": onclicks,
            "data_attrs": self._extract_data_attrs(content_norm),
            "actions": merged_actions,
            "endpoints": self.trace_possible_endpoints(content_norm),
            "includes_internos": includes_internos,
            "includes_relevantes": [],
            "dynamic_loads": dynamic_loads,
        }

        if recursive_depth < max_depth:
            result["includes_relevantes"] = self._analyze_relevant_includes(
                includes_internos=includes_internos,
                recursive_depth=recursive_depth + 1,
                max_depth=max_depth,
            )

        return result

    def _analyze_relevant_includes(self, includes_internos: list[str], recursive_depth: int, max_depth: int) -> list[dict]:
        analisados = []

        for include_path in includes_internos:
            if not self._is_relevant_include(include_path):
                continue

            resolved = self._resolve_include_path(include_path)
            if not resolved or not resolved.exists():
                analisados.append({
                    "include": include_path,
                    "caminho_resolvido": str(resolved) if resolved else None,
                    "status": "não encontrado",
                    "analise": None,
                })
                continue

            analise = self.analyze_html_for_actions(
                str(resolved),
                recursive_depth=recursive_depth,
                max_depth=max_depth,
            )

            analisados.append({
                "include": include_path,
                "caminho_resolvido": str(resolved),
                "status": "ok",
                "analise": analise,
            })

        return analisados

    def _is_relevant_include(self, include_path: str) -> bool:
        value = (include_path or "").strip().lower()

        relevant_tokens = [
            "modal_",
            "financeiro",
            "detalhe",
            "resultado",
            "consulta",
            "decreto",
            "encaminhamento",
        ]

        return any(token in value for token in relevant_tokens)

    def _resolve_include_path(self, include_path: str) -> Path | None:
        raw = (include_path or "").strip()
        if not raw:
            return None

        candidate = Path(raw)

        if candidate.is_absolute():
            return candidate

        normalized = raw.replace("\\", "/")
        return self.base_dir / normalized

    def _normalize_content(self, content: str) -> str:
        return content.replace("\r\n", "\n").replace("\r", "\n")

    def _extract_modals(self, content: str):
        pattern = r'id="([^"]*modal[^"]*)"'
        return list(dict.fromkeys(re.findall(pattern, content, re.IGNORECASE)))

    def _extract_buttons(self, content: str):
        pattern = r'<button\b([^>]*)>(.*?)</button>'
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)

        cleaned = []
        for attrs, inner in matches:
            texto = self._clean_html_text(inner)
            if texto:
                cleaned.append(texto)

        return list(dict.fromkeys(cleaned))

    def _extract_links_with_text(self, content: str):
        pattern = r'<a\b([^>]*)>(.*?)</a>'
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)

        links = []
        for attrs, inner in matches:
            texto = self._clean_html_text(inner)
            if not texto:
                continue

            attrs_map = self._extract_tag_attrs(attrs)

            links.append({
                "text": texto,
                "href": attrs_map.get("href", ""),
                "onclick": attrs_map.get("onclick", ""),
                "class": attrs_map.get("class", ""),
                "id": attrs_map.get("id", ""),
            })

        unique = []
        seen = set()
        for item in links:
            key = (
                item["text"],
                item["href"],
                item["onclick"],
                item["class"],
                item["id"],
            )
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique

    def _extract_clickable_elements(self, content: str):
        elements = []

        # ----------------------------
        # 1. LINKS (<a>)
        # ----------------------------
        for link in self._extract_links_with_text(content):
            raw_source = f"{link.get('href', '')} {link.get('onclick', '')}"
            actions = self.extract_actions(raw_source)

            onclick = link.get("onclick", "")
            js_meta = self._extract_js_call(onclick)
            js_behavior = self._classify_js_behavior(onclick)

            elements.append({
                "type": "a",
                "label": link.get("text", ""),
                "class": link.get("class", ""),
                "id": link.get("id", ""),
                "onclick": onclick,
                "href": link.get("href", ""),
                "actions": actions,
                "js_function": js_meta.get("name"),
                "js_args": js_meta.get("args", []),
                "js_behavior": js_behavior,
                "priority": self._infer_priority(link.get("class", ""), link.get("text", "")),
                "semantic_hint": self._infer_semantic_hint(link.get("text", ""), onclick),
            })

        # ----------------------------
        # 2. INPUTS CLICÁVEIS
        # ----------------------------
        elements.extend(self._extract_input_clickables(content))

        # ----------------------------
        # 3. ELEMENTOS GENÉRICOS COM onclick
        # ----------------------------
        generic_pattern = r'<(div|span|li|p|h1|h2|h3|h4|h5|h6)\b([^>]*)>(.*?)</\1>'
        generic_matches = re.findall(generic_pattern, content, re.IGNORECASE | re.DOTALL)

        for tag, attrs, inner in generic_matches:
            attrs_map = self._extract_tag_attrs(attrs)

            onclick = attrs_map.get("onclick", "").strip()
            if not onclick:
                continue

            texto = self._clean_html_text(inner)
            if not texto:
                continue

            actions = self.extract_actions(onclick)
            js_meta = self._extract_js_call(onclick)
            js_behavior = self._classify_js_behavior(onclick)

            elements.append({
                "type": tag.lower(),
                "label": texto,
                "class": attrs_map.get("class", ""),
                "id": attrs_map.get("id", ""),
                "onclick": onclick,
                "href": "",
                "actions": actions,
                "js_function": js_meta.get("name"),
                "js_args": js_meta.get("args", []),
                "js_behavior": js_behavior,
                "priority": self._infer_priority(attrs_map.get("class", ""), texto),
                "semantic_hint": self._infer_semantic_hint(texto, onclick),
            })

        # ----------------------------
        # 4. FILTRO E DEDUPLICAÇÃO
        # ----------------------------
        filtered = []
        seen = set()

        for item in elements:
            label = (item.get("label") or "").strip()
            if not label:
                continue

            key = (
                item.get("type", ""),
                label,
                item.get("class", ""),
                item.get("id", ""),
                item.get("onclick", ""),
                item.get("href", ""),
            )

            if key not in seen:
                seen.add(key)
                filtered.append(item)

        return filtered

    def _extract_input_clickables(self, content: str):
        pattern = r'<input\b([^>]*)>'
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)

        items = []
        for attrs in matches:
            attrs_map = self._extract_tag_attrs(attrs)
            input_type = (attrs_map.get("type", "") or "").strip().lower()

            if input_type not in {"button", "submit"}:
                continue

            label = attrs_map.get("value", "") or attrs_map.get("title", "")
            label = label.strip()
            if not label:
                continue

            onclick = attrs_map.get("onclick", "")
            raw_source = f"{attrs_map.get('href', '')} {onclick}"
            actions = self.extract_actions(raw_source)

            js_meta = self._extract_js_call(onclick)
            js_behavior = self._classify_js_behavior(onclick)

            items.append({
                "type": "input",
                "label": label,
                "class": attrs_map.get("class", ""),
                "id": attrs_map.get("id", ""),
                "onclick": onclick,
                "href": attrs_map.get("href", ""),
                "actions": actions,
                "js_function": js_meta.get("name"),
                "js_args": js_meta.get("args", []),
                "js_behavior": js_behavior,
                "priority": self._infer_priority(attrs_map.get("class", ""), label),
                "semantic_hint": self._infer_semantic_hint(label, onclick),
            })

        return items


    def _extract_clickable_elements(self, content: str):
        elements = []

        # anchors
        for link in self._extract_links_with_text(content):
            raw_source = f"{link.get('href', '')} {link.get('onclick', '')}"
            actions = self.extract_actions(raw_source)

            onclick = link.get("onclick", "")
            js_meta = self._extract_js_call(onclick)
            js_behavior = self._classify_js_behavior(onclick)

            elements.append({
                "type": "a",
                "label": link.get("text", ""),
                "class": link.get("class", ""),
                "id": link.get("id", ""),
                "onclick": onclick,
                "href": link.get("href", ""),
                "actions": actions,
                "js_function": js_meta.get("name"),
                "js_args": js_meta.get("args", []),
                "js_behavior": js_behavior,
                "priority": self._infer_priority(link.get("class", ""), link.get("text", "")),
                "semantic_hint": self._infer_semantic_hint(link.get("text", ""), onclick),
            })

        # inputs clicáveis
        elements.extend(self._extract_input_clickables(content))

        # elementos genéricos com onclick
        generic_pattern = r'<(div|span|li|p|h1|h2|h3|h4|h5|h6)\b([^>]*)>(.*?)</\1>'
        generic_matches = re.findall(generic_pattern, content, re.IGNORECASE | re.DOTALL)

        for tag, attrs, inner in generic_matches:
            attrs_map = self._extract_tag_attrs(attrs)
            onclick = attrs_map.get("onclick", "").strip()
            if not onclick:
                continue

            texto = self._clean_html_text(inner)
            if not texto:
                continue

            actions = self.extract_actions(onclick)
            js_meta = self._extract_js_call(onclick)

            elements.append({
                "type": tag.lower(),
                "label": texto,
                "class": attrs_map.get("class", ""),
                "id": attrs_map.get("id", ""),
                "onclick": onclick,
                "href": "",
                "actions": actions,
                "js_function": js_meta.get("name"),
                "js_args": js_meta.get("args", []),
                "priority": self._infer_priority(attrs_map.get("class", ""), texto),
                "semantic_hint": self._infer_semantic_hint(texto, onclick),
            })

        filtered = []
        seen = set()

        for item in elements:
            label = (item.get("label") or "").strip()
            if not label:
                continue

            key = (
                item.get("type", ""),
                label,
                item.get("class", ""),
                item.get("id", ""),
                item.get("onclick", ""),
                item.get("href", ""),
            )
            if key not in seen:
                seen.add(key)
                filtered.append(item)

        return filtered

    def _extract_onclicks(self, content: str):
        patterns = [
            r'onclick="([^"]+)"',
            r"onclick='([^']+)'",
        ]

        resultados = []
        for pattern in patterns:
            resultados.extend(re.findall(pattern, content, re.IGNORECASE | re.DOTALL))

        resultados = [re.sub(r"\s+", " ", item).strip() for item in resultados if item.strip()]
        return list(dict.fromkeys(resultados))

    def _extract_data_attrs(self, content: str):
        pattern = r'(data-[a-zA-Z0-9_-]+)="([^"]+)"'
        matches = re.findall(pattern, content, re.IGNORECASE)
        return list(dict.fromkeys([f"{k}={v}" for k, v in matches]))

    def _extract_include_paths(self, content: str):
        pattern = r'include(?:_once)?\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        return list(dict.fromkeys(re.findall(pattern, content, re.IGNORECASE)))

    def find_js_calls(self, content: str):
        pattern = r'([a-zA-Z0-9_]+)\('
        return list(dict.fromkeys(re.findall(pattern, content)))

    def extract_actions(self, content: str):
        encontrados = []

        matches = re.findall(
            r'action=([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)([^"\']*)',
            content,
            re.IGNORECASE,
        )

        for classe, metodo, raw_params in matches:
            params = self._parse_action_params(raw_params)

            encontrados.append({
                "classe": classe,
                "metodo": metodo,
                "params": params,
                "raw_params": raw_params.strip(),
                "backend_hint": self._build_backend_hint(classe, metodo, params),
            })

        return self._merge_actions(encontrados)

    def extract_actions_from_onclicks(self, onclicks: list[str]):
        encontrados = []

        for oc in onclicks:
            matches = re.findall(
                r'action=([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)([^"\']*)',
                oc,
                re.IGNORECASE,
            )

            for classe, metodo, raw_params in matches:
                params = self._parse_action_params(raw_params)

                encontrados.append({
                    "classe": classe,
                    "metodo": metodo,
                    "params": params,
                    "raw_params": raw_params.strip(),
                    "backend_hint": self._build_backend_hint(classe, metodo, params),
                })

        return self._merge_actions(encontrados)

    def _parse_action_params(self, raw_params: str) -> dict:
        raw = (raw_params or "").strip()
        if not raw:
            return {}

        raw = raw.strip("&? ")
        raw = raw.replace("&amp;", "&")

        params = {}

        for chunk in raw.split("&"):
            chunk = chunk.strip()
            if not chunk:
                continue

            if "=" in chunk:
                key, value = chunk.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key:
                    params[key] = value
            else:
                params[chunk] = ""

        return params

    def _build_backend_hint(self, classe: str, metodo: str, params: dict) -> str:
        base = f"{classe}CTR::{metodo}()"
        if not params:
            return base

        params_text = ", ".join(f"{k}={v}" for k, v in params.items())
        return f"{base} [{params_text}]"

    def trace_possible_endpoints(self, content: str):
        endpoints = []

        patterns = [
            r'action=([a-zA-Z0-9_.&=-]+)',
            r'url:\s*"([^"]+)"',
            r"url:\s*'([^']+)'",
        ]

        for pattern in patterns:
            endpoints.extend(re.findall(pattern, content, re.IGNORECASE))

        endpoints = [re.sub(r"\s+", " ", item).strip() for item in endpoints if item.strip()]
        return list(dict.fromkeys(endpoints))

    def _clean_html_text(self, text: str) -> str:
        value = re.sub(r"<[^>]+>", " ", text or "")
        value = re.sub(r"&nbsp;", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _extract_tag_attrs(self, attrs: str) -> dict:
        data = {}
        for key, value in re.findall(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)="([^"]*)"', attrs or "", re.IGNORECASE):
            data[key.lower()] = value
        for key, value in re.findall(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)='([^']*)'", attrs or "", re.IGNORECASE):
            data[key.lower()] = value
        return data

    def _extract_js_call(self, onclick: str) -> dict:
        raw = (onclick or "").strip()
        if not raw:
            return {"name": None, "args": []}

        match = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\((.*)\)', raw)
        if not match:
            return {"name": None, "args": []}

        name = match.group(1).strip()
        args_raw = match.group(2).strip()

        args = self._split_js_args(args_raw)

        return {
            "name": name,
            "args": args,
        }

    def _extract_dynamic_loads(self, content: str):
        results = []

        pattern = re.compile(
            r"""recuperaConteudoDinamico\s*\(
                \s*([^,]*?)\s*,                      # 1º argumento
                \s*('(?:\\'|[^'])*'|"(?:\\"|[^"])*"|[^,]+)\s*,   # endpoint
                \s*('(?:\\'|[^'])*'|"(?:\\"|[^"])*"|[^,\)]+)     # target
            """,
            re.IGNORECASE | re.VERBOSE | re.DOTALL,
        )

        for match in pattern.finditer(content):
            raw_endpoint = (match.group(2) or "").strip()
            raw_target = (match.group(3) or "").strip()

            endpoint = self._strip_quotes(raw_endpoint)
            target = self._strip_quotes(raw_target)

            actions = self.extract_actions(endpoint)

            results.append({
                "loader_function": "recuperaConteudoDinamico",
                "endpoint": endpoint,
                "target": target,
                "actions": actions,
            })

        unique = []
        seen = set()

        for item in results:
            key = (item["endpoint"], item["target"])
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique


    def _split_js_args(self, args_raw: str) -> list[str]:
        if not args_raw:
            return []

        parts = []
        current = []
        in_single = False
        in_double = False
        depth = 0

        for ch in args_raw:
            if ch == "'" and not in_double:
                in_single = not in_single
                current.append(ch)
                continue

            if ch == '"' and not in_single:
                in_double = not in_double
                current.append(ch)
                continue

            if ch == "(" and not in_single and not in_double:
                depth += 1
                current.append(ch)
                continue

            if ch == ")" and not in_single and not in_double and depth > 0:
                depth -= 1
                current.append(ch)
                continue

            if ch == "," and not in_single and not in_double and depth == 0:
                value = "".join(current).strip()
                if value:
                    parts.append(self._strip_quotes(value))
                current = []
                continue

            current.append(ch)

        tail = "".join(current).strip()
        if tail:
            parts.append(self._strip_quotes(tail))

        return parts

    def _strip_quotes(self, value: str) -> str:
        v = (value or "").strip()
        if len(v) >= 2 and ((v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"'))):
            return v[1:-1]
        return v

    def _infer_priority(self, css_class: str, label: str) -> str:
        raw = f"{css_class or ''} {label or ''}".lower()

        high_tokens = [
            "small-box-footer",
            "detalhamento",
            "financeiro",
            "repasse",
            "decreto",
            "remanejamento",
        ]
        medium_tokens = [
            "btn",
            "link",
            "modal",
            "consultar",
            "listar",
        ]

        if any(token in raw for token in high_tokens):
            return "high"
        if any(token in raw for token in medium_tokens):
            return "medium"
        return "normal"

    def _infer_semantic_hint(self, label: str, onclick: str) -> str | None:
        raw = f"{label or ''} {onclick or ''}".lower()

        if "repasse" in raw and "remanejamento" in raw:
            return "detalhamento_repasse_remanejamento"

        if "decreto" in raw:
            return "detalhamento_decreto"

        if "detalhamento" in raw:
            return "detalhamento_generico"

        if "mostraritensdetalhamento" in raw:
            return "funcao_js_detalhamento"

        return None

    def _classify_js_behavior(self, onclick: str) -> str:
        raw = (onclick or "").lower()

        if not raw:
            return "unknown"

        if "action=" in raw or "recuperaconteudodinamico" in raw or "$.ajax" in raw:
            return "backend_trigger"

        if any(x in raw for x in ["show(", "hide(", "style.display", ".text(", "#tab"]):
            return "dom_toggle"

        if "datatable" in raw:
            return "datatable_init"

        return "unknown"

    def _merge_actions(self, actions: list[dict]):
        unicos = []
        vistos = set()

        for item in actions:
            chave = (
                item["classe"].lower(),
                item["metodo"].lower(),
                tuple(sorted((item.get("params") or {}).items())),
            )
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(item)

        return unicos