import json
from pathlib import Path


def write_domain_map(domain_map: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(domain_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path