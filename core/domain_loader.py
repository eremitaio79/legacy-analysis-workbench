import json
from pathlib import Path


class DomainLoader:
    def __init__(self, base_path: str = "knowledge"):
        self.base_path = Path(base_path)

    def load(self, domain: str) -> dict:
        domain = (domain or "").strip().lower()
        if not domain:
            raise ValueError("Domínio não informado.")

        domain_dir = self.base_path / domain
        if not domain_dir.exists() or not domain_dir.is_dir():
            raise FileNotFoundError(
                f"Pasta do domínio não encontrada: {domain_dir}"
            )

        domain_clean = domain.lstrip("_")

        preferred_candidates = [
            domain_dir / f"{domain_clean}_domain_map.json",
            domain_dir / f"{domain}_domain_map.json",
            self.base_path / f"{domain_clean}_domain_map.json",
            self.base_path / f"{domain}_domain_map.json",
        ]

        for path in preferred_candidates:
            if path.exists():
                return self._read_json(path)

        json_files = sorted(domain_dir.glob("*.json"))

        if not json_files:
            raise FileNotFoundError(
                f"Nenhum JSON encontrado na pasta do domínio: {domain_dir}"
            )

        # Prioriza arquivos com "domain_map" no nome
        prioritized = [p for p in json_files if "domain_map" in p.stem.lower()]
        if prioritized:
            return self._read_json(prioritized[0])

        # Fallback: primeiro JSON da pasta
        return self._read_json(json_files[0])

    def _read_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Arquivo de domínio inválido: {path}")

        return data