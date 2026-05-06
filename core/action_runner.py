from rich.panel import Panel

from core.exceptions import InputValidationError, SigplanToolsError
from core.ui import console


def run_safe(action, *, friendly_name: str = "operação"):
    try:
        return action()

    except InputValidationError as exc:
        console.print(
            Panel.fit(
                f"[yellow]{exc}[/yellow]",
                title=f"{friendly_name} não executada",
                border_style="yellow",
            )
        )

    except KeyboardInterrupt:
        console.print(
            Panel.fit(
                "[yellow]Operação interrompida pelo usuário.[/yellow]",
                title="Interrompido",
                border_style="yellow",
            )
        )

    except SigplanToolsError as exc:
        console.print(
            Panel.fit(
                f"[red]{exc}[/red]",
                title=f"Falha em {friendly_name}",
                border_style="red",
            )
        )

    except Exception as exc:
        console.print(
            Panel.fit(
                f"[red]Erro inesperado:[/red] {exc}",
                title=f"Falha em {friendly_name}",
                border_style="red",
            )
        )