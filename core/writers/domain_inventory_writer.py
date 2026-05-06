from __future__ import annotations

from datetime import datetime
from pathlib import Path


def write_domain_inventory(items: list[dict], output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# 📚 Inventário de Maturidade Semântica dos Schemas\n\n")
        f.write(f"Gerado em: {datetime.now()}\n\n")

        f.write("| Domínio | Estrutural | Domain Map | Cross | Cross IA | Maturidade | Observação |\n")
        f.write("|---|---:|---:|---:|---:|---|---|\n")

        for item in items:
            f.write(
                f"| {item['domain']} "
                f"| {'✔' if item['structural_json'] else '—'} "
                f"| {'✔' if item['domain_map_json'] else '—'} "
                f"| {'✔' if item['cross_md'] else '—'} "
                f"| {'✔' if item['cross_ia_md'] else '—'} "
                f"| {item['maturity']} "
                f"| {item['note']} |\n"
            )

        f.write("\n## 🧭 Critérios de Maturidade\n\n")
        f.write("- **não iniciado**: sem JSON estrutural\n")
        f.write("- **estrutural**: possui JSON estrutural, mas sem domain map\n")
        f.write("- **semântico inicial**: possui domain map, mas sem cruzamento\n")
        f.write("- **parcial**: pipeline existe, mas ainda com aderência ou cobertura limitada\n")
        f.write("- **maduro**: aderência forte e pipeline completo com parecer IA\n")

    return output_file