import os

def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")

import time
from typing import Iterable, Optional

from rich.panel import Panel
from rich.console import Console
from rich.live import Live
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.prompt import Confirm
from rich.prompt import Prompt


console = Console()

def _limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def print_lento(linhas: Iterable[str], delay: float = 0.1) -> None:
    """
    Imprime linhas uma a uma, com pequeno atraso.
    Bom para dar sensação de construção progressiva da tela.
    """
    for linha in linhas:
        console.print(linha)
        time.sleep(delay)


def success(msg: str) -> None:
    console.print(f"[bold green]{msg}[/bold green]")


def warning(msg: str) -> None:
    console.print(f"[bold yellow]{msg}[/bold yellow]")


def error(msg: str) -> None:
    console.print(f"[bold red]{msg}[/bold red]")


def info(msg: str) -> None:
    console.print(f"[cyan]{msg}[/cyan]")


def status(texto: str) -> Status:
    """
    Retorna um contexto Rich para spinner/status.
    Uso:
        with ui.status("Consultando IA..."):
            ...
    """
    return console.status(texto)


def live_table(
    titulo: str,
    colunas: list[tuple[str, Optional[str], Optional[int], Optional[str]]],
    linhas: list[list[str]],
    delay: float = 0.01,
    expand: bool = False,
    refresh_per_second: int = 12,
) -> None:
    """
    Renderiza uma tabela crescendo linha a linha usando Rich Live.

    colunas:
        [
            ("Nome da coluna", "estilo", largura_ou_None, justify_ou_None),
            ...
        ]

    linhas:
        [
            ["valor1", "valor2", ...],
            ...
        ]
    """
    tabela = Table(title=titulo, expand=expand)

    for titulo_col, estilo, largura, justify in colunas:
        kwargs = {}

        if estilo:
            kwargs["style"] = estilo
        if largura:
            kwargs["width"] = largura
        if justify:
            kwargs["justify"] = justify

        tabela.add_column(titulo_col, **kwargs)

    with Live(tabela, console=console, refresh_per_second=refresh_per_second):
        for linha in linhas:
            tabela.add_row(*linha)
            if delay > 0:
                time.sleep(delay)


def typewriter_text(texto: str, delay: float = 0.1) -> None:
    """
    Efeito de digitação caractere a caractere.
    Útil para títulos curtos ou mensagens especiais.
    """
    acumulado = Text()

    with Live(acumulado, console=console, refresh_per_second=40) as live:
        for ch in texto:
            acumulado.append(ch)
            live.update(acumulado)
            time.sleep(delay)



def _renderizar_sobre():
    limpar_tela()

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Legacy Analysis Workbench[/bold cyan]\n"
            "[dim]AI-assisted reverse engineering and legacy system analysis[/dim]",
            border_style="blue",
        )
    )

    console.print()

    console.print(
        Panel.fit(
            "[bold yellow]Public Case Study Edition[/bold yellow]\n"
            "[white]Legacy modernization, architecture analysis, and applied AI[/white]",
            border_style="yellow",
        )
    )

    console.print()

    console.print(
        Panel(
            "[white]This workbench was built to help engineers inspect large legacy systems "
            "with more structure, less guesswork, and better use of AI.\n\n"
            "It combines static analysis, schema inspection, UI flow tracing, "
            "and generated technical commentary into one operational tool.[/white]",
            title="About",
            border_style="cyan",
        )
    )

    console.print(
        Panel(
            "[bold]Code analysis:[/bold] PHP legacy surfaces, includes, facades, flows\n"
            "[bold]Data analysis:[/bold] SQL Server schemas, procedures, and table inspection\n"
            "[bold]AI:[/bold] structured prompts, commentary, and cache-aware execution\n"
            "[bold]Outputs:[/bold] Markdown reports, semantic maps, and cross-analysis",
            title="Capabilities",
            border_style="magenta",
        )
    )

    console.print(
        Panel(
            "- Reverse engineering workflows\n"
            "- Legacy modernization support\n"
            "- Structured AI collaboration\n"
            "- Domain mapping from technical assets\n"
            "- Faster onboarding into complex systems",
            title="Strengths",
            border_style="green",
        )
    )

    console.print()
    console.print("[dim]Pressione Enter para voltar...[/dim]")
    input()


def confirm(pergunta: str, default: bool = True) -> bool:
    sufixo = "[S/n]" if default else "[s/N]"

    while True:
        resposta = Prompt.ask(f"{pergunta} {sufixo}", default="s" if default else "n").strip().lower()

        if resposta in {"s", "sim"}:
            return True

        if resposta in {"n", "nao", "não"}:
            return False

        warning("Resposta inválida. Digite 's' para sim ou 'n' para não.")


def etapa(titulo: str, mensagem: str, border_style: str = "cyan") -> None:
    console.print(
        Panel.fit(
            mensagem,
            title=titulo,
            border_style=border_style,
        )
    )
