from pathlib import Path
from typing import Optional

from rich.table import Table
from rich.prompt import Prompt


class KnowledgeFileManager:
    def __init__(self, base_path: str = "knowledge"):
        self.base_path = Path(base_path)

    def ensure_base_exists(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)

    def list_domains(self) -> list[Path]:
        self.ensure_base_exists()
        return sorted([p for p in self.base_path.iterdir() if p.is_dir()])

    def list_json_files(self, domain: str) -> list[Path]:
        domain_path = self.base_path / domain
        if not domain_path.exists() or not domain_path.is_dir():
            return []

        return sorted(domain_path.glob("*.json"))

    def select_domain(self, console) -> Optional[str]:
        domains = self.list_domains()

        if not domains:
            console.print("[yellow]Nenhuma subpasta encontrada em knowledge.[/yellow]")
            return None

        table = Table(title="📚 Domínios disponíveis")
        table.add_column("Nº", justify="right", style="cyan")
        table.add_column("Domínio", style="white")

        for i, domain in enumerate(domains, start=1):
            table.add_row(str(i), domain.name)

        console.print(table)

        choice = Prompt.ask(
            "[bold]Escolha o domínio[/bold]",
            choices=[str(i) for i in range(1, len(domains) + 1)],
        )

        return domains[int(choice) - 1].name

    def select_json_file(self, console, domain: str, title: str = "📂 Arquivos JSON disponíveis") -> Optional[Path]:
        files = self.list_json_files(domain)

        if not files:
            console.print(f"[yellow]Nenhum JSON encontrado em knowledge/{domain}.[/yellow]")
            return None

        table = Table(title=title)
        table.add_column("Nº", justify="right", style="cyan")
        table.add_column("Arquivo", style="white")
        table.add_column("Tamanho", justify="right", style="green")

        for i, file in enumerate(files, start=1):
            size_kb = file.stat().st_size / 1024
            table.add_row(str(i), file.name, f"{size_kb:.1f} KB")

        console.print(table)

        choice = Prompt.ask(
            "[bold]Escolha o arquivo[/bold]",
            choices=[str(i) for i in range(1, len(files) + 1)],
        )

        return files[int(choice) - 1]

    def select_schema_json(self, console) -> Optional[Path]:
        domain = self.select_domain(console)
        if not domain:
            return None

        return self.select_json_file(
            console,
            domain=domain,
            title=f"📂 JSONs do domínio: {domain}",
        )