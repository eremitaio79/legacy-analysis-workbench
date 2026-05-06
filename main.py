import os
import re
import time
from pathlib import Path

import pandas as pd

import typer
from core import ui
from core.method_flow import MethodFlowAnalyzer

from rich.live import Live
from rich.columns import Columns
from rich.align import Align
from rich.text import Text
from rich.rule import Rule
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.panel import Panel
from rich.prompt import Prompt

from core.scanner import (
    buscar_texto_em_arquivo,
    encontrar_arquivo_do_metodo,
    encontrar_arquivo_da_action,
    analisar_arquivo_php,
    consolidar_resultado_scan,
    gerar_relatorios_scan_segmentados,
    listar_php,
)

from core.writer import salvar_markdown
from core.method_analyzer import analisar_metodo_em_arquivo
from core.deps_writer import salvar_relatorio_dependencias
from core.class_resolver import resolver_chamadas_externas
from core.include_resolver import resolver_includes
from core.tree_builder import construir_arvore_dependencias
from core.url_parser import parse_sigboard_url
from core.ai_analyzer import (
    AIAnalysisInput,
    GeminiAnalyzer,
    GeminiAnalyzerError,
)

from core.config import (
    SIGBOARD_PROJECT_PATH,
    SIGBOARD_OUTPUT_DIR,
    SIGBOARD_REPORT_DIR,
    SIGBOARD_DEFAULT_MD_NAME,
    SIGBOARD_AI_PROVIDER,
    SIGBOARD_AI_MODEL,
    SIGBOARD_AI_PROMPT_FILE,
    SIGBOARD_DEFAULT_DEEP,
    SIGBOARD_DEFAULT_CONTEXTO,
    SIGBOARD_AI_CACHE_ENABLED,
    SIGBOARD_AI_CACHE_DIR,
)

from core.include_analyzer import (
    extrair_caminho_include,
    resolver_caminho_include,
    analisar_arquivo_include,
    render_markdown_include,
)
from core.method_analyzer import analisar_metodo_em_arquivo

from core.include_script_analyzer import (
    analisar_include_script,
    render_markdown_include_script,
)

from core.data_inspector import (
    carregar_dataframe,
    analisar_dataframe,
    render_markdown_data_inspector,
)

from core.db_schema_inspector import (
    analisar_estrutura_tabela,
    render_markdown_schema_inspector,
)

from core.data_ai_commentary import montar_prompt_comentario_dados
from core.ai_analyzer import GeminiAnalyzer, GeminiAnalyzerError

from core.data_anomaly_detector import (
    analisar_anomalias_tabela,
    render_markdown_anomalias,
)

from core.data_anomaly_ai_commentary import montar_prompt_comentario_anomalias

from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from core.data_radar import (
    listar_tabelas_banco,
    analisar_tabela_no_radar,
    render_markdown_data_radar,
)

from core.fachada_analyzer import FachadaAnalyzer
from rich import print
from rich.panel import Panel
import json

from core.fachada_analyzer import FachadaAnalyzer
from core.fachada_writer import write_fachada_report

from core.model_analyzer import ModelAnalyzer
from core.model_writer import write_model_report

from core.ai_analyzer import GeminiAnalyzer, GeminiAnalyzerError
from core.fachada_analyzer import FachadaAnalyzer
from core.fachada_ai_commentary import FachadaAICommentary
from core.fachada_writer import write_fachada_report

from core.db_connector import get_connection
from core.procedure_analyzer import ProcedureAnalyzer
from core.procedure_writer import ProcedureWriter

from core.config import SIGBOARD_DB_ACTIVE

from core.db_connector import get_connection, get_connection_info

from core.config import SIGBOARD_OUTPUT_DIR, SIGBOARD_REPORT_DIR

from core.procedure_ai_commentary import generate_procedure_ai_commentary

from core.ui import _renderizar_sobre, _limpar_tela

from core.action_runner import run_safe
from core.exceptions import RequiredInputError, SigboardToolsError
from core.input_utils import normalize_menu_option, require_non_empty

from core.code_health_ai_commentary import CodeHealthAICommentary

from core.schema_semantic_analyzer import SchemaSemanticAnalyzer
from core.writers.schema_semantic_writer import write_schema_semantic_report
from core.knowledge_file_manager import KnowledgeFileManager
from core.graphml_to_json_converter import GraphMLToJsonConverter

from core.domain_loader import DomainLoader
from core.schema_domain_cross_analyzer import SchemaDomainCrossAnalyzer
from core.writers.schema_domain_cross_writer import write_schema_domain_cross_report

from core.domain_map_generator import DomainMapGenerator
from core.writers.domain_map_writer import write_domain_map
from core.domain_map_refiner import DomainMapRefiner
from core.schema_cross_ai_commentary import SchemaCrossAICommentaryService
from core.domain_inventory_builder import DomainInventoryBuilder
from core.writers.domain_inventory_writer import write_domain_inventory

from core.ui_flow_analyzer import UIFlowAnalyzer
from core.action_trace_analyzer import ActionTraceAnalyzer
from core.ui_flow_ai_commentary import UIFlowAICommentary

current_db_env = SIGBOARD_DB_ACTIVE
CURRENT_AI_MODEL = SIGBOARD_AI_MODEL

app = typer.Typer(help="AI-assisted tools for legacy system analysis.")
console = Console()


@app.callback()
def main():
    pass


# =========================================================
# Helpers gerais
# =========================================================

def destacar_termo(texto: str, termo: str, case_sensitive: bool = False) -> str:
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.escape(termo)

    return re.sub(
        pattern,
        lambda m: f"[bold black on yellow]{m.group(0)}[/bold black on yellow]",
        texto,
        flags=flags
    )


def _normalizar_nome_relatorio(nome: str | None, fallback: str) -> str:
    """
    Remove extensão .md se o usuário já informou e devolve apenas o nome-base.
    """
    nome_limpo = (nome or "").strip()

    if not nome_limpo:
        nome_limpo = fallback

    if nome_limpo.lower().endswith(".md"):
        nome_limpo = nome_limpo[:-3]

    return nome_limpo.strip()


def _montar_relatorio_ui_flow_markdown(dados: dict) -> str:
    linhas = []

    linhas.append("# Relatório de Dependências + Fluxo UI")
    linhas.append("")

    linhas.append("## Método analisado")
    linhas.append(f"- Arquivo: `{dados.get('arquivo', '-')}`")
    linhas.append(f"- Assinatura: `{dados.get('assinatura', '-')}`")
    linhas.append(f"- Linhas: {dados.get('linha_inicio', '-')} - {dados.get('linha_fim', '-')}")
    linhas.append("")

    linhas.append("## Includes resolvidos")
    includes_resolvidos = dados.get("includes_resolvidos", []) or []
    if includes_resolvidos:
        for item in includes_resolvidos:
            status = "OK" if item.get("existe") else "NÃO ENCONTRADO"
            linhas.append(f"- `{item.get('instrucao', '-')}` → {status}")
            if item.get("caminho_resolvido"):
                linhas.append(f"  - caminho: `{item['caminho_resolvido']}`")
    else:
        linhas.append("- Nenhum")
    linhas.append("")

    linhas.append("## Trace automático de actions da UI")
    traces = dados.get("ui_action_traces", []) or []
    if traces:
        for trace in traces:
            linhas.append(f"### {trace.get('backend_hint', '-')}")
            if trace.get("arquivo_classe"):
                linhas.append(f"- Arquivo: `{trace['arquivo_classe']}`")
            if trace.get("assinatura"):
                linhas.append(f"- Assinatura: `{trace['assinatura']}`")
            if trace.get("linha_inicio") and trace.get("linha_fim"):
                linhas.append(f"- Linhas: {trace['linha_inicio']} - {trace['linha_fim']}")

            tabelas = trace.get("tabelas", []) or []
            if tabelas:
                linhas.append("- Tabelas:")
                for tb in tabelas:
                    linhas.append(f"  - `{tb}`")

            queries = trace.get("queries_completas", []) or []
            if queries:
                linhas.append("- Queries completas:")
                for q in queries[:5]:
                    linhas.append(f"  - Tipo: `{q.get('tipo', 'desconhecido')}`")
                    linhas.append("```sql")
                    linhas.append(q.get("sql", "").strip())
                    linhas.append("```")
            linhas.append("")
    else:
        linhas.append("- Nenhuma action rastreada")
        linhas.append("")

    ai_commentary = (dados.get("ui_flow_ai_commentary") or "").strip()
    if ai_commentary:
        linhas.append("## Laudo narrativo com IA")
        linhas.append("")
        linhas.append(ai_commentary)
        linhas.append("")

    return "\n".join(linhas)


def _data_inspector_schema_semantico_json(current_db_env: str):
    manager = KnowledgeFileManager(base_path="knowledge")

    json_path = manager.select_schema_json(console)

    if not json_path:
        return

    with ui.status("🧠 Lendo JSON do schema..."):
        with open(json_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)

    with ui.status("🔎 Executando análise semântica do schema..."):
        analyzer = SchemaSemanticAnalyzer(schema_data)
        result = analyzer.analyze()

    # output_dir = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / "schema_semantic"
    output_dir = Path("reports/schema_semantic")
    output_dir.mkdir(parents=True, exist_ok=True)

    nome_saida = f"schema_semantic_{json_path.parent.name}_{json_path.stem}"
    output_file = output_dir / f"{json_path.stem}.md"

    with ui.status("📝 Gerando relatório Markdown..."):
        output_file = write_schema_semantic_report(
            result,
            output_dir,
            file_name=f"{json_path.stem}.md",
            domain=json_path.parent.name
        )

    console.print()
    console.print(Panel(
        f"[bold]Arquivo JSON:[/bold] {json_path}\n"
        f"[bold]Domínio:[/bold] {json_path.parent.name}\n"
        f"[bold]Entidades principais detectadas:[/bold] {len(result.get('entities_detected', []))}\n"
        f"[bold]Relações hierárquicas:[/bold] {len(result.get('hierarchy', []))}\n"
        f"[bold]Sinais temporais:[/bold] {len(set(result.get('temporal_signals', [])))}\n"
        f"[bold]Sinais financeiros:[/bold] {len(set(result.get('financial_signals', [])))}\n"
        f"[bold]Sinais regionais:[/bold] {len(set(result.get('regional_signals', [])))}",
        title="🧠 Schema Semantic Analyzer",
        expand=False,
        border_style="cyan",
    ))

    if result.get("entities_detected"):
        console.print("\n[bold]Entidades principais:[/bold]")
        for item in result["entities_detected"]:
            console.print(f"  - {item}")

    if result.get("hierarchy"):
        console.print("\n[bold]Hierarquia detectada:[/bold]")
        for item in result["hierarchy"]:
            console.print(f"  - {item}")

    ui.success("✅ Análise semântica do schema concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {output_file}")


def _gerar_parecer_ia_schema_cross():
    if not _verificar_config_ia():
        return

    cross_dir = Path("reports/schema_cross")

    if not cross_dir.exists():
        console.print("[yellow]A pasta reports/schema_cross não existe ainda.[/yellow]")
        return

    cross_files = sorted(
        [
            p for p in cross_dir.glob("*.md")
            if not p.stem.endswith("_ia")
        ]
    )

    if not cross_files:
        console.print("[yellow]Nenhum relatório de cruzamento encontrado em reports/schema_cross.[/yellow]")
        return

    tabela = Table(title="📂 Relatórios de cruzamento disponíveis")
    tabela.add_column("Nº", justify="right", style="cyan")
    tabela.add_column("Arquivo", style="white")
    tabela.add_column("Tamanho", justify="right", style="green")

    for i, file in enumerate(cross_files, start=1):
        size_kb = file.stat().st_size / 1024
        tabela.add_row(str(i), file.name, f"{size_kb:.1f} KB")

    console.print(tabela)

    escolha = Prompt.ask(
        "[bold]Escolha o relatório de cruzamento[/bold]",
        choices=[str(i) for i in range(1, len(cross_files) + 1)],
    )

    selected_file = cross_files[int(escolha) - 1]
    domain_name = selected_file.stem.replace("_cross", "").strip().lower()

    prefer_cache = _pedir_modo_cache()
    provider = _pedir_provider_ia()
    model = _pedir_modelo_ia(provider)

    with ui.status("📖 Lendo relatório de cruzamento..."):
        cross_markdown = selected_file.read_text(encoding="utf-8")

    with ui.status("🤖 Gerando parecer técnico com IA..."):
        service = SchemaCrossAICommentaryService(
            provider=provider,
            model=model,
            prompt_file="schema_cross_ai_analysis_prompt.txt",
        )
        ai_commentary = service.generate(
            cross_markdown=cross_markdown,
            domain_name=domain_name,
            prefer_cache=prefer_cache,
        )

    output_file = selected_file.with_name(f"{selected_file.stem}_ia.md")
    output_file.write_text(ai_commentary, encoding="utf-8")

    console.print()
    ui.success("✅ Parecer técnico com IA gerado com sucesso.")
    console.print(f"[bold blue]📝 Arquivo salvo em:[/bold blue] {output_file}")


def _build_ui_flow_trace_payload(
    entrada: str,
    info: dict,
    dados: dict,
    ui_results: list,
) -> dict:
    return {
        "entrada_original": entrada,
        "tipo_entrada": info.get("tipo"),
        "classe": info.get("classe"),
        "metodo": info.get("metodo"),
        "arquivo_metodo_inicial": dados.get("arquivo"),
        "assinatura_metodo_inicial": dados.get("assinatura"),
        "linhas_metodo_inicial": {
            "inicio": dados.get("linha_inicio"),
            "fim": dados.get("linha_fim"),
        },
        "includes_originais": dados.get("includes", []),
        "includes_resolvidos": dados.get("includes_resolvidos", []),
        "ui_results": ui_results,
        "ui_action_traces": dados.get("ui_action_traces", []),
        "queries_completas_metodo_inicial": dados.get("queries_completas", []),
        "sql_suspeito_metodo_inicial": dados.get("sql_suspeito", []),
        "tabelas_metodo_inicial": dados.get("tabelas", []),
        "procedures_metodo_inicial": dados.get("procedures", []),
        "chamadas_metodo_inicial": dados.get("chamadas", []),
    }


def _gerar_inventario_dominios():
    with ui.status("📚 Mapeando domínios semânticos..."):
        builder = DomainInventoryBuilder(
            knowledge_dir="knowledge",
            cross_dir="reports/schema_cross",
        )
        items = builder.build()

    if not items:
        console.print("[yellow]Nenhum domínio encontrado para inventário.[/yellow]")
        return

    output_file = Path("reports/domain_inventory.md")

    with ui.status("📝 Gerando inventário consolidado..."):
        write_domain_inventory(items, output_file)

    maduros = sum(1 for x in items if x["maturity"] == "maduro")
    parciais = sum(1 for x in items if x["maturity"] == "parcial")
    rasos = sum(1 for x in items if x["maturity"] == "raso")
    estruturais = sum(1 for x in items if x["maturity"] == "estrutural")
    sem_init = sum(1 for x in items if x["maturity"] == "semântico inicial")
    nao_iniciados = sum(1 for x in items if x["maturity"] == "não iniciado")

    console.print()
    console.print(Panel(
        f"[bold]Total de domínios:[/bold] {len(items)}\n"
        f"[bold green]Maduros:[/bold green] {maduros}\n"
        f"[bold yellow]Parciais:[/bold yellow] {parciais}\n"
        f"[bold magenta]Semântico inicial:[/bold magenta] {sem_init}\n"
        f"[bold cyan]Estrutural:[/bold cyan] {estruturais}\n"
        f"[bold red]Rasos:[/bold red] {rasos}\n"
        f"[bold white]Não iniciados:[/bold white] {nao_iniciados}",
        title="📚 Inventário de Domínios",
        expand=False,
        border_style="blue",
    ))

    ui.success("✅ Inventário de domínios gerado com sucesso.")
    console.print(f"[bold blue]📝 Arquivo salvo em:[/bold blue] {output_file}")


def _gerar_domain_map_semantico():
    manager = KnowledgeFileManager(base_path="knowledge")

    domain = manager.select_domain(console)
    if not domain:
        return

    all_files = manager.list_json_files(domain)
    schema_candidates = [
        p for p in all_files
        if "domain_map" not in p.stem.lower()
    ]

    if not schema_candidates:
        console.print(
            f"[yellow]Nenhum JSON estrutural encontrado em knowledge/{domain}.[/yellow]"
        )
        return

    table = Table(title=f"📂 JSONs estruturais do domínio: {domain}")
    table.add_column("Nº", justify="right", style="cyan")
    table.add_column("Arquivo", style="white")
    table.add_column("Tamanho", justify="right", style="green")

    for i, file in enumerate(schema_candidates, start=1):
        size_kb = file.stat().st_size / 1024
        table.add_row(str(i), file.name, f"{size_kb:.1f} KB")

    console.print(table)

    choice = Prompt.ask(
        "[bold]Escolha o JSON estrutural[/bold]",
        choices=[str(i) for i in range(1, len(schema_candidates) + 1)],
    )

    schema_json = schema_candidates[int(choice) - 1]

    with ui.status("🧠 Lendo JSON estrutural..."):
        with open(schema_json, "r", encoding="utf-8") as f:
            schema_data = json.load(f)

    with ui.status("🔎 Gerando domain map semântico inicial..."):
        generator = DomainMapGenerator(schema_data, domain_name=domain)
        raw_domain_map = generator.generate()

    with ui.status("🧹 Refinando domain map semântico..."):
        domain_map = DomainMapRefiner(raw_domain_map).refine()

    domain_clean = domain.lstrip("_")
    output_path = Path("knowledge") / domain / f"{domain_clean}_domain_map.json"

    with ui.status("💾 Salvando domain map..."):
        write_domain_map(domain_map, output_path)

    console.print()
    console.print(Panel(
        f"[bold]Domínio:[/bold] {domain}\n"
        f"[bold]Schema estrutural:[/bold] {schema_json.name}\n"
        f"[bold]Entidades refinadas:[/bold] {len(domain_map.get('entities', {}))}\n"
        f"[bold]Relações refinadas:[/bold] {len(domain_map.get('relacoes', []))}\n"
        f"[bold]Regras candidatas:[/bold] {len(domain_map.get('regras_candidatas', []))}",
        title="🧠 Domain Map Generator",
        expand=False,
        border_style="green",
    ))

    ui.success("✅ Domain map semântico refinado gerado com sucesso.")
    console.print(f"[bold blue]📝 Arquivo salvo em:[/bold blue] {output_path}")


def _data_inspector_schema_cross_domain(current_db_env: str):
    manager = KnowledgeFileManager(base_path="knowledge")

    domain = manager.select_domain(console)
    if not domain:
        return

    # Lista apenas JSONs estruturais, ignorando domain maps
    all_files = manager.list_json_files(domain)
    schema_candidates = [
        p for p in all_files
        if "domain_map" not in p.stem.lower()
    ]

    if not schema_candidates:
        console.print(
            f"[yellow]Nenhum JSON estrutural encontrado em knowledge/{domain}.[/yellow]"
        )
        return

    table = Table(title=f"📂 JSONs estruturais do domínio: {domain}")
    table.add_column("Nº", justify="right", style="cyan")
    table.add_column("Arquivo", style="white")
    table.add_column("Tamanho", justify="right", style="green")

    for i, file in enumerate(schema_candidates, start=1):
        size_kb = file.stat().st_size / 1024
        table.add_row(str(i), file.name, f"{size_kb:.1f} KB")

    console.print(table)

    choice = Prompt.ask(
        "[bold]Escolha o schema estrutural[/bold]",
        choices=[str(i) for i in range(1, len(schema_candidates) + 1)],
    )

    schema_json = schema_candidates[int(choice) - 1]

    with ui.status("🧠 Lendo schema estrutural..."):
        with open(schema_json, "r", encoding="utf-8") as f:
            schema_data = json.load(f)

    with ui.status("🔎 Executando análise semântica genérica..."):
        semantic_result = SchemaSemanticAnalyzer(schema_data).analyze()

    with ui.status("📚 Carregando domain map..."):
        domain_map = DomainLoader(base_path="knowledge").load(domain)

    with ui.status("🔀 Cruzando schema com o domínio..."):
        cross_result = SchemaDomainCrossAnalyzer(
            schema_analysis=semantic_result,
            domain_map=domain_map,
        ).analyze()

    output_dir = Path("reports/schema_cross")
    output_file = write_schema_domain_cross_report(
        cross_result,
        output_dir=output_dir,
        file_name=f"{schema_json.stem}_cross.md",
    )

    console.print()
    console.print(Panel(
        f"[bold]Domínio:[/bold] {domain}\n"
        f"[bold]Schema estrutural:[/bold] {schema_json.name}\n"
        f"[bold]Entidades esperadas:[/bold] {len(cross_result.get('expected_entities', []))}\n"
        f"[bold]Entidades encontradas:[/bold] {len(cross_result.get('found_entities', []))}\n"
        f"[bold]Relacionamentos esperados:[/bold] {len(cross_result.get('expected_relationships', []))}\n"
        f"[bold]Relacionamentos encontrados:[/bold] {len(cross_result.get('found_relationships', []))}\n"
        f"[bold]Aderência de entidades:[/bold] {cross_result.get('adherence_entities_percent', 0)}%\n"
        f"[bold]Aderência de relacionamentos:[/bold] {cross_result.get('adherence_relationships_percent', 0)}%",
        title="🔀 Schema × Domínio",
        expand=False,
        border_style="magenta",
    ))

    ui.success("✅ Cruzamento schema × domínio concluído.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {output_file}")


def _importar_graphml_para_json():
    graphml_path = Path("graphml")

    if not graphml_path.exists():
        console.print("[red]Pasta 'graphml' não encontrada.[/red]")
        return

    graphml_files = sorted(graphml_path.glob("*.graphml"))

    if not graphml_files:
        console.print("[yellow]Nenhum arquivo .graphml encontrado na pasta atual.[/yellow]")
        return

    tabela = Table(title="📂 Arquivos GraphML disponíveis (graphml/)")

    tabela.add_column("Nº", justify="right", style="cyan")
    tabela.add_column("Arquivo", style="white")
    tabela.add_column("Tamanho", justify="right", style="green")

    for i, f in enumerate(graphml_files, start=1):
        size_kb = f.stat().st_size / 1024
        tabela.add_row(str(i), f.name, f"{size_kb:.1f} KB")

    console.print(tabela)

    escolha = Prompt.ask(
        "[bold]Escolha o arquivo[/bold]",
        choices=[str(i) for i in range(1, len(graphml_files) + 1)]
    )

    selected_file = graphml_files[int(escolha) - 1]

    # escolher domínio
    manager = KnowledgeFileManager()
    domain = manager.select_domain(console)

    if not domain:
        return

    output_dir = Path("knowledge") / domain
    output_dir.mkdir(parents=True, exist_ok=True)

    with ui.status("🔄 Convertendo GraphML para JSON..."):
        converter = GraphMLToJsonConverter(selected_file)
        result = converter.convert()

    output_file = output_dir / f"{selected_file.stem}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        import json
        json.dump(result, f, indent=2, ensure_ascii=False)

    console.print()
    ui.success("✅ Conversão concluída.")
    console.print(f"[bold blue]Arquivo salvo em:[/bold blue] {output_file}")


def _salvar_modelo_no_env(novo_modelo: str):
    env_path = Path(".env")

    if not env_path.exists():
        console.print("[yellow]Arquivo .env não encontrado. Alteração mantida apenas nesta sessão.[/yellow]")
        return

    conteudo = env_path.read_text(encoding="utf-8", errors="ignore")

    if re.search(r"^SIGBOARD_AI_MODEL=", conteudo, flags=re.MULTILINE):
        conteudo = re.sub(
            r"^SIGBOARD_AI_MODEL=.*$",
            f"SIGBOARD_AI_MODEL={novo_modelo}",
            conteudo,
            flags=re.MULTILINE,
        )
    else:
        if not conteudo.endswith("\n"):
            conteudo += "\n"
        conteudo += f"SIGBOARD_AI_MODEL={novo_modelo}\n"

    env_path.write_text(conteudo, encoding="utf-8")
    console.print("[bold green]✔ Modelo salvo no .env com sucesso.[/bold green]")


def _alterar_modelo_ia():
    global CURRENT_AI_MODEL

    modelos_disponiveis = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
    ]

    console.print("\n[bold magenta]Alteração de modelo de IA[/bold magenta]")
    console.print(f"[cyan]Modelo atual:[/cyan] {CURRENT_AI_MODEL}\n")

    for idx, modelo in enumerate(modelos_disponiveis, start=1):
        marcador = " [green](atual)[/green]" if modelo == CURRENT_AI_MODEL else ""
        console.print(f"[bold]{idx}[/bold] - {modelo}{marcador}")

    console.print("\n[dim]Você também pode digitar manualmente o nome completo do modelo.[/dim]")

    escolha = input("\nEscolha um número ou digite o nome do modelo: ").strip()

    if not escolha:
        console.print("[yellow]Nenhuma alteração realizada.[/yellow]")
        return

    if escolha.isdigit():
        idx = int(escolha)
        if 1 <= idx <= len(modelos_disponiveis):
            novo_modelo = modelos_disponiveis[idx - 1]
        else:
            console.print("[red]Opção inválida.[/red]")
            return
    else:
        novo_modelo = escolha

    CURRENT_AI_MODEL = novo_modelo

    console.print(f"\n[bold green]✔ Modelo de IA alterado para:[/bold green] {CURRENT_AI_MODEL}")

    salvar = input("Deseja salvar essa alteração no .env? (s/n): ").strip().lower()
    if salvar == "s":
        _salvar_modelo_no_env(CURRENT_AI_MODEL)



def run_procedure_analysis_with_ai(procedure_name: str, environment: str) -> None:
    procedure_name = require_non_empty(
        procedure_name,
        "Informe o nome da procedure."
    )

    conn = None

    try:
        console.print(
            Panel.fit(
                f"[bold cyan]Procedure Analyzer + IA[/bold cyan]\n"
                f"Procedure: [yellow]{procedure_name}[/yellow]\n"
                f"Ambiente: [yellow]{environment}[/yellow]"
            )
        )

        with ui.status("[bold yellow]Lendo metadados e dependências da procedure...[/bold yellow]"):
            conn = get_connection(environment=environment)

            analyzer = ProcedureAnalyzer(connection=conn, environment=environment)
            writer = ProcedureWriter()

            analysis = analyzer.analyze(procedure_name)

            if not analysis:
                raise SigboardToolsError("Nenhuma análise foi retornada para a procedure informada.")

        with ui.status("[bold magenta]Interpretando comportamento com IA...[/bold magenta]"):
            ai_commentary = generate_procedure_ai_commentary(
                analysis=analysis,
                provider=SIGBOARD_AI_PROVIDER,
                model=CURRENT_AI_MODEL,
                prompt_file="procedure_ai_analysis_prompt.txt",
                prefer_cache=True,
            )

        if not ai_commentary or not str(ai_commentary).strip():
            raise SigboardToolsError("A IA não retornou comentário técnico para a procedure.")

        analysis["ai_commentary"] = ai_commentary

        with ui.status("[bold green]Gerando relatório Markdown...[/bold green]"):
            output_path = writer.write(analysis)

        console.print()
        console.print("[bold green]Resumo da análise[/bold green]")
        console.print(f"Procedure: [cyan]{analysis['schema']}.{analysis['procedure']}[/cyan]")
        console.print(f"Linhas: [yellow]{analysis['lines']}[/yellow]")
        console.print(f"Parâmetros: [yellow]{analysis['parameter_count']}[/yellow]")
        console.print(f"Classificação: [magenta]{analysis['classification']}[/magenta]")
        console.print(f"Operações: [white]{', '.join(analysis['operations']) or '-'}[/white]")
        console.print(f"Tabelas lidas: [cyan]{len(analysis['tables']['read'])}[/cyan]")
        console.print(f"Tabelas escritas: [cyan]{len(analysis['tables']['write'])}[/cyan]")

        if analysis["warnings"]:
            console.print("\n[bold red]Pontos de atenção[/bold red]")
            for warning in analysis["warnings"]:
                console.print(f"- [red]{warning}[/red]")
        else:
            console.print("\n[green]Nenhum warning importante encontrado.[/green]")

        console.print("\n[bold cyan]Comentário técnico com IA gerado com sucesso.[/bold cyan]")
        console.print(f"\n[bold green]Relatório gerado em:[/bold green] {output_path}")

    finally:
        if conn is not None:
            conn.close()



def obter_info_banco(environment: str) -> tuple[str, str, str]:
    conn = None
    try:
        conn = get_connection(environment=environment)
        info = get_connection_info(conn, environment=environment)
        return info["server_name"], info["database_name"], info["server_ip"]

    except Exception:
        return "-", "-", "-"

    finally:
        if conn:
            conn.close()



def run_procedure_analysis(procedure_name: str, environment: str = "homolog") -> None:
    procedure_name = require_non_empty(
        procedure_name,
        "Informe o nome da procedure."
    )

    conn = None

    try:
        console.print(Panel.fit(
            f"[bold cyan]Procedure Analyzer[/bold cyan]\n"
            f"Procedure: [yellow]{procedure_name}[/yellow]\n"
            f"Ambiente: [yellow]{environment}[/yellow]"
        ))

        with ui.status("[bold cyan]Analisando procedure...[/bold cyan]"):
            conn = get_connection(environment=environment)

            analyzer = ProcedureAnalyzer(connection=conn, environment=environment)
            writer = ProcedureWriter(output_dir=Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / "procedures")

            analysis = analyzer.analyze(procedure_name)

            if not analysis:
                raise SigboardToolsError("Nenhuma análise foi retornada para a procedure informada.")

            output_path = writer.write(analysis)

        console.print()
        console.print("[bold green]Resumo da análise[/bold green]")
        console.print(f"Procedure: [cyan]{analysis['schema']}.{analysis['procedure']}[/cyan]")
        console.print(f"Linhas: [yellow]{analysis['lines']}[/yellow]")
        console.print(f"Parâmetros: [yellow]{analysis['parameter_count']}[/yellow]")
        console.print(f"Classificação: [magenta]{analysis['classification']}[/magenta]")
        console.print(f"Operações: [white]{', '.join(analysis['operations']) or '-'}[/white]")
        console.print(f"Tabelas lidas: [cyan]{len(analysis['tables']['read'])}[/cyan]")
        console.print(f"Tabelas escritas: [cyan]{len(analysis['tables']['write'])}[/cyan]")
        console.print(f"Procedures chamadas: [cyan]{len(analysis['calls']['procedures'])}[/cyan]")
        console.print(f"Funções chamadas: [cyan]{len(analysis['calls']['functions'])}[/cyan]")

        if analysis["warnings"]:
            console.print("\n[bold red]Pontos de atenção[/bold red]")
            for warning in analysis["warnings"]:
                console.print(f"- [red]{warning}[/red]")
        else:
            console.print("\n[green]Nenhum warning importante encontrado.[/green]")

        console.print(f"\n[bold green]Relatório gerado em:[/bold green] {output_path}")

    finally:
        if conn is not None:
            conn.close()


def escolher_ambiente_banco(
    current_db_env: str,
    current_db_server: str = "-",
    current_db_database: str = "-",
    current_db_ip: str = "-",
) -> tuple[str, str, str, str]:
    console.print()
    console.print(
        Panel(
            "[bold cyan]Selecionar banco de dados[/bold cyan]\n\n"
            "[1] homologação\n"
            "[2] produção\n\n"
            f"Atual: [yellow]{_format_db_env_label(current_db_env)}[/yellow]\n"
            f"Servidor atual: [cyan]{current_db_server or '-'}[/cyan]\n"
            f"Banco atual: [cyan]{current_db_database or '-'}[/cyan]",
            title="Banco",
            border_style="yellow",
            expand=False,
        )
    )

    mapa = {
        "1": "homolog",
        "2": "prod",
        "homolog": "homolog",
        "homologacao": "homolog",
        "homologação": "homolog",
        "prod": "prod",
        "producao": "prod",
        "produção": "prod",
    }

    try:
        escolha = require_non_empty(
            input("Ambiente: "),
            "Informe o ambiente desejado: 1 para homologação ou 2 para produção."
        ).lower()
    except RequiredInputError as exc:
        console.print(f"\n[yellow]{exc}[/yellow]")
        console.print("[yellow]Mantendo banco atual.[/yellow]")
        _pausar()
        return current_db_env, current_db_server, current_db_database, current_db_ip

    if escolha not in mapa:
        console.print("\n[red]Opção inválida. Mantendo banco atual.[/red]")
        _pausar()
        return current_db_env, current_db_server, current_db_database, current_db_ip

    novo_env = mapa[escolha]
    conn = None

    try:
        conn = get_connection(environment=novo_env)
        info = get_connection_info(conn, environment=novo_env)

        server_name = info["server_name"]
        database_name = info["database_name"]
        host_name = info["host_name"]
        login_name = info["login_name"]
        server_ip = info["server_ip"]

        console.print(
            Panel(
                f"[bold green]Conexão validada com sucesso[/bold green]\n\n"
                f"Ambiente selecionado: [yellow]{_format_db_env_label(novo_env)}[/yellow]\n"
                f"Servidor: [cyan]{server_name} ({server_ip})[/cyan]\n"
                f"Banco: [cyan]{database_name}[/cyan]\n"
                f"Usuário SQL: [cyan]{login_name}[/cyan]\n"
                f"Host cliente: [cyan]{host_name}[/cyan]",
                title="Confirmação de conexão",
                border_style="green",
                expand=False,
            )
        )

        _pausar()
        return novo_env, server_name, database_name, server_ip

    except Exception as exc:
        console.print(
            f"\n[bold red]Falha ao validar conexão com o ambiente "
            f"{_format_db_env_label(novo_env)}:[/bold red] {exc}"
        )
        console.print("[yellow]Mantendo banco atual.[/yellow]")
        _pausar()
        return current_db_env, current_db_server, current_db_database, current_db_ip

    finally:
        if conn is not None:
            conn.close()


def _imprimir_resultado_anomalias(resultado: dict):
    console.print()
    console.print(Panel(
        f"[bold]Origem:[/bold] {resultado['origem']}\n"
        f"[bold]Linhas:[/bold] {resultado['linhas']}\n"
        f"[bold]Total de anomalias:[/bold] {resultado['total_anomalias']}\n"
        f"[bold]Chave sugerida:[/bold] {', '.join(resultado.get('chave_sugerida', [])) or 'nenhuma'}",
        title="🚨 Anomalias da Tabela",
        expand=False,
        border_style="red",
    ))

    achados = resultado.get("anomalias", [])
    if not achados:
        console.print("\n[green]Nenhuma anomalia relevante detectada.[/green]")
        return

    console.print("\n[bold]Achados:[/bold]")
    for item in achados[:30]:
        coluna = item.get("coluna", "")
        descricao = item.get("descricao", "")

        if coluna:
            console.print(f"  ⚠️ [yellow]{coluna}[/yellow] → {descricao}")
        else:
            console.print(f"  ⚠️ {descricao}")

        time.sleep(0.003)

    if len(achados) > 30:
        console.print("  - ...")


def _imprimir_resultado_data_radar(resultado: dict):
    console.print()
    console.print(Panel(
        f"[bold]Schemas:[/bold] {', '.join(resultado.get('schemas', [])) or 'todos'}\n"
        f"[bold]Limite por tabela:[/bold] {resultado.get('limit_por_tabela', 0)}\n"
        f"[bold]Total de tabelas lidas:[/bold] {resultado.get('total_tabelas_lidas', 0)}\n"
        f"[bold]Sucesso:[/bold] {resultado.get('total_ok', 0)}\n"
        f"[bold]Erros:[/bold] {resultado.get('total_erros', 0)}",
        title="📡 SIGBOARD Data Radar",
        expand=False,
        border_style="cyan",
    ))

    ranking = resultado.get("ranking", []) or []

    console.print("\n[bold]Top tabelas suspeitas:[/bold]")
    if ranking:
        for idx, item in enumerate(ranking[:20], start=1):
            anomalias = item.get("anomalias_resultado", {}) or {}
            total_anomalias = anomalias.get("total_anomalias", 0)
            console.print(
                f"  {idx:02d}. [yellow]{item['tabela']}[/yellow] "
                f"| score={item['score']} "
                f"| linhas={item['linhas_lidas']} "
                f"| anomalias={total_anomalias}"
            )
            time.sleep(0.003)
    else:
        console.print("  - nenhuma")

    erros = resultado.get("erros", []) or []
    console.print("\n[bold]Erros:[/bold]")
    if erros:
        for item in erros[:20]:
            console.print(f"  ❌ {item['tabela']} → {item['erro']}")
            time.sleep(0.003)
        if len(erros) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhum")


def _executar_fachada_ai(
    entrada: str,
    path: str,
    out: str | None = None,
):
    entrada = require_non_empty(
        entrada,
        "Informe o nome da fachada, caminho do arquivo PHP ou Classe.metodo."
    )
    path = require_non_empty(path, "Caminho do projeto não informado.")

    analyzer = FachadaAnalyzer(base_dir=path)

    with ui.status("[bold cyan]Preparando análise da fachada com IA...[/bold cyan]"):
        parsed = analyzer._parse_target(entrada)
        target_method = parsed.get("method")
        class_or_path = parsed.get("class_or_path")

        proceed_with_full_fachada = True
        method_exists = True

        if target_method:
            with ui.status("[bold cyan]Localizando fachada/CTR...[/bold cyan]"):
                resolved_path = analyzer._resolve_target(class_or_path)

            with ui.status("[bold cyan]Verificando método alvo na fachada...[/bold cyan]"):
                content = resolved_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                method_exists = analyzer._target_method_exists(lines, target_method)

    if target_method and not method_exists:
        ui.etapa(
            "Método não encontrado",
            f"[yellow]O método alvo '{target_method}' não foi encontrado na fachada.[/yellow]\n"
            f"[white]A análise pode continuar usando a CTR/fachada inteira antes do comentário com IA.[/white]",
            border_style="yellow",
        )

        proceed_with_full_fachada = ui.confirm(
            "Deseja continuar com a análise completa da fachada?",
            default=True,
        )

        if not proceed_with_full_fachada:
            raise SigboardToolsError("Análise de fachada com IA cancelada pelo usuário.")

    result = analyzer.analyze(
        entrada,
        proceed_with_full_fachada_if_method_missing=proceed_with_full_fachada,
    )

    if not result:
        raise SigboardToolsError(
            "Nenhum resultado foi retornado para a análise da fachada com IA."
        )

    resumo = {
        "classe": result.class_name,
        "arquivo": result.resolved_path,
        "linhas": result.total_lines,
        "metodos_publicos": result.public_methods_count,
        "dependencias": len(result.dependencies),
        "tabelas": len(result.tables),
        "queries_sql": len(result.sql_blocks),
        "warnings": result.warnings,
    }

    console.print(
        Panel.fit(
            json.dumps(resumo, ensure_ascii=False, indent=2),
            title="Fachada Analyzer + IA",
            border_style="magenta",
        )
    )

    prefer_cache = _pedir_modo_cache()

    try:
        gemini = GeminiAnalyzer(
            provider=SIGBOARD_AI_PROVIDER,
            model=CURRENT_AI_MODEL,
            prompt_file=SIGBOARD_AI_PROMPT_FILE,
        )
    except GeminiAnalyzerError as exc:
        raise SigboardToolsError(f"Erro ao inicializar IA: {exc}") from exc

    commentary_service = FachadaAICommentary(
        analyzer=gemini,
        prompt_file="fachada_ai_analysis_prompt.txt",
    )

    console.print("\n[bold magenta]🤖 Gerando comentário técnico com IA...[/bold magenta]")

    try:
        ai_commentary = commentary_service.generate(
            result=result,
            prefer_cache=prefer_cache,
            max_methods=12,
            include_sql_snippets=True,
        )
    except GeminiAnalyzerError as exc:
        raise SigboardToolsError(f"Falha na análise IA da fachada: {exc}") from exc

    if not ai_commentary or not str(ai_commentary).strip():
        raise SigboardToolsError("A IA não retornou comentário técnico para a fachada.")

    fallback_nome = f"fachada_ai_{result.class_name or 'analise'}"
    nome_base = _normalizar_nome_relatorio(out, fallback=fallback_nome)

    pasta_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR
    pasta_saida.mkdir(parents=True, exist_ok=True)

    arquivo_resumido = pasta_saida / f"{nome_base}_resumido.md"
    arquivo_detalhado = pasta_saida / f"{nome_base}_detalhado.md"

    write_fachada_report(
        result=result,
        output_path=arquivo_resumido,
        detailed=False,
        ai_commentary=ai_commentary,
    )

    write_fachada_report(
        result=result,
        output_path=arquivo_detalhado,
        detailed=True,
        ai_commentary=ai_commentary,
    )

    console.print("\n[bold green]✔ Comentário IA gerado com sucesso.[/bold green]")
    console.print(f"[bold green]✔ Relatório resumido gerado:[/bold green] {arquivo_resumido}")
    console.print(f"[bold green]✔ Relatório detalhado gerado:[/bold green] {arquivo_detalhado}")


def _normalizar_nome_relatorio(nome: str | None, fallback: str) -> str:
    nome_limpo = (nome or "").strip()

    if not nome_limpo:
        nome_limpo = fallback

    if nome_limpo.lower().endswith(".md"):
        nome_limpo = nome_limpo[:-3]

    return nome_limpo.strip()


def _executar_model_analyzer(
    entrada: str,
    path: str,
    out: str | None = None,
):
    entrada = require_non_empty(
        entrada,
        "Informe o nome do model ou caminho do arquivo PHP."
    )
    path = require_non_empty(path, "Caminho do projeto não informado.")

    analyzer = ModelAnalyzer(base_dir=path)

    with ui.status("[bold green]Localizando model...[/bold green]"):
        resolved_path = analyzer._resolve_target(entrada)

    if not resolved_path.exists():
        raise SigboardToolsError(f"Arquivo não encontrado: {resolved_path}")

    with ui.status("[bold green]Preparando leitura do model...[/bold green]"):
        result = analyzer.analyze(str(resolved_path))

    if not result:
        raise SigboardToolsError(
            "Nenhum resultado foi retornado para a análise do model."
        )

    resumo = {
        "classe": result.class_name,
        "arquivo": result.resolved_path,
        "package": result.package,
        "sgbd": result.sgbd,
        "tabela": result.table_name,
        "linhas": result.total_lines,
        "campos": len(result.fields),
        "metodos": len(result.methods),
        "getters": len(result.getters),
        "setters": len(result.setters),
        "warnings": result.warnings,
    }

    console.print(
        Panel.fit(
            json.dumps(resumo, ensure_ascii=False, indent=2),
            title="Model Analyzer",
            border_style="green",
        )
    )

    fallback_nome = f"model_{result.class_name or 'analise'}"
    nome_base = _normalizar_nome_relatorio(out, fallback=fallback_nome)

    pasta_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR
    pasta_saida.mkdir(parents=True, exist_ok=True)

    arquivo_resumido = pasta_saida / f"{nome_base}_resumido.md"
    arquivo_detalhado = pasta_saida / f"{nome_base}_detalhado.md"

    write_model_report(
        result=result,
        output_path=arquivo_resumido,
        detailed=False,
    )

    write_model_report(
        result=result,
        output_path=arquivo_detalhado,
        detailed=True,
    )

    console.print(f"\n[bold green]✔ Relatório resumido gerado:[/bold green] {arquivo_resumido}")
    console.print(f"[bold green]✔ Relatório detalhado gerado:[/bold green] {arquivo_detalhado}")


def _executar_fachada_analyzer(
    entrada: str,
    path: str,
    out: str | None = None,
):
    entrada = require_non_empty(
        entrada,
        "Informe o nome da fachada, caminho do arquivo PHP ou Classe.metodo."
    )
    path = require_non_empty(path, "Caminho do projeto não informado.")

    analyzer = FachadaAnalyzer(base_dir=path)

    with ui.status("[bold cyan]Preparando análise da fachada...[/bold cyan]"):
        parsed = analyzer._parse_target(entrada)
        target_method = parsed.get("method")
        class_or_path = parsed.get("class_or_path")

        proceed_with_full_fachada = True
        method_exists = True

        if target_method:
            resolved_path = analyzer._resolve_target(class_or_path)
            content = resolved_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            method_exists = analyzer._target_method_exists(lines, target_method)

    if target_method and not method_exists:
        ui.etapa(
            "Método não encontrado",
            f"[yellow]O método alvo '{target_method}' não foi encontrado na fachada.[/yellow]\n"
            f"[white]A análise pode continuar usando a CTR/fachada inteira.[/white]",
            border_style="yellow",
        )

        proceed_with_full_fachada = ui.confirm(
            "Deseja continuar com a análise completa da fachada?",
            default=True,
        )

        if not proceed_with_full_fachada:
            raise SigboardToolsError("Análise de fachada cancelada pelo usuário.")

    result = analyzer.analyze(
        entrada,
        proceed_with_full_fachada_if_method_missing=proceed_with_full_fachada,
    )

    if not result:
        raise RequiredInputError(
            "Nenhum resultado foi retornado para a análise da fachada."
        )

    resumo = {
        "classe": result.class_name,
        "arquivo": result.resolved_path,
        "linhas": result.total_lines,
        "metodos_publicos": result.public_methods_count,
        "dependencias": len(result.dependencies),
        "tabelas": len(result.tables),
        "queries_sql": len(result.sql_blocks),
        "warnings": result.warnings,
    }

    console.print(
        Panel.fit(
            json.dumps(resumo, ensure_ascii=False, indent=2),
            title="Fachada Analyzer",
            border_style="cyan",
        )
    )

    fallback_nome = f"fachada_{result.class_name or 'analise'}"
    nome_base = _normalizar_nome_relatorio(out, fallback=fallback_nome)

    pasta_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR
    pasta_saida.mkdir(parents=True, exist_ok=True)

    arquivo_resumido = pasta_saida / f"{nome_base}_resumido.md"
    arquivo_detalhado = pasta_saida / f"{nome_base}_detalhado.md"

    write_fachada_report(
        result=result,
        output_path=arquivo_resumido,
        detailed=False,
    )

    write_fachada_report(
        result=result,
        output_path=arquivo_detalhado,
        detailed=True,
    )

    console.print(f"\n[bold green]✔ Relatório resumido gerado:[/bold green] {arquivo_resumido}")
    console.print(f"[bold green]✔ Relatório detalhado gerado:[/bold green] {arquivo_detalhado}")


def _data_inspector_radar_banco(current_db_env: str):
    schemas_raw = Prompt.ask(
        "[bold]Schemas para analisar (ex: gp,_ppa,_dbo) ou ENTER para todos[/bold]",
        default=""
    ).strip()

    schemas = [s.strip() for s in schemas_raw.split(",") if s.strip()] if schemas_raw else []

    incluir_views = Prompt.ask(
        "[bold]Incluir views? (s/n)[/bold]",
        choices=["s", "n"],
        default="n"
    ).strip().lower() == "s"

    limite_str = Prompt.ask(
        "[bold]Quantidade máxima de linhas por tabela[/bold]",
        default="200"
    ).strip()
    try:
        limit_por_tabela = int(limite_str)
    except Exception:
        limit_por_tabela = 200

    max_tabelas_str = Prompt.ask(
        "[bold]Máximo de tabelas (0 = todas)[/bold]",
        default="0"
    ).strip()
    try:
        max_tabelas = int(max_tabelas_str)
    except Exception:
        max_tabelas = 0

    with ui.status("🧭 Listando tabelas do banco..."):
        tabelas = listar_tabelas_banco(
            schemas=schemas,
            incluir_views=incluir_views,
        )

    if max_tabelas > 0:
        tabelas = tabelas[:max_tabelas]

    if not tabelas:
        console.print("[yellow]Nenhuma tabela encontrada para análise.[/yellow]")
        return

    resultados = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )

    with progress:
        task_id = progress.add_task("📡 Varredura do banco em andamento...", total=len(tabelas))

        for item in tabelas:
            tabela = item["full_name"]
            progress.update(task_id, description=f"📡 Analisando {tabela}")

            resultado = analisar_tabela_no_radar(
                tabela=tabela,
                limit=limit_por_tabela,
            )
            resultados.append(resultado)

            progress.advance(task_id)

    ranking = sorted(
        [r for r in resultados if r.get("ok")],
        key=lambda x: (-x["score"], x["tabela"])
    )
    erros = [r for r in resultados if not r.get("ok")]

    resultado_final = {
        "schemas": schemas,
        "incluir_views": incluir_views,
        "limit_por_tabela": limit_por_tabela,
        "total_tabelas_lidas": len(resultados),
        "total_ok": len(ranking),
        "total_erros": len(erros),
        "ranking": ranking,
        "erros": erros,
        "resultados": resultados,
    }

    with ui.status("📝 Gerando relatório do radar..."):
        md = render_markdown_data_radar(resultado_final)

    nome_schemas = "_".join(schemas) if schemas else "todos"
    nome_relatorio = f"data_radar_{nome_schemas}.md"
    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_data_radar(resultado_final)
    ui.success("✅ Varredura do banco concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")



def _imprimir_resultado_data_inspector(resultado: dict):
    console.print()
    console.print(Panel(
        f"[bold]Origem:[/bold] {resultado['origem']}\n"
        f"[bold]Linhas:[/bold] {resultado['linhas']}\n"
        f"[bold]Colunas:[/bold] {resultado['colunas']}",
        title="📊 SIGBOARD Data Inspector",
        expand=False,
        border_style="cyan",
    ))

    ui.print_lento(
        [
            "",
            f"🧱 Colunas encontradas: {len(resultado.get('nomes_colunas', []))}",
            f"🕳️ Colunas com nulos avaliadas: {len(resultado.get('nulos', []))}",
            f"🧬 Cardinalidade calculada: {len(resultado.get('cardinalidade', []))}",
            f"🪞 Duplicidades por coluna: {len(resultado.get('duplicidades_por_coluna', []))}",
            f"📅 Faixas de datas detectadas: {len(resultado.get('datas', []))}",
            f"🔢 Estatísticas numéricas: {len(resultado.get('estatisticas_numericas', []))}",
            "",
        ],
        delay=0.02
    )

    console.print("\n[bold]Colunas:[/bold]")
    for col in resultado.get("nomes_colunas", [])[:30]:
        console.print(f"  - {col}")
        time.sleep(0.003)
    if len(resultado.get("nomes_colunas", [])) > 30:
        console.print("  - ...")

    console.print("\n[bold]Top colunas com nulos:[/bold]")
    nulos = [x for x in resultado.get("nulos", []) if x["nulos"] > 0]
    if nulos:
        for item in nulos[:15]:
            console.print(f"  ⚠️ {item['coluna']} → {item['nulos']} nulos ({item['percentual']}%)")
            time.sleep(0.003)
    else:
        console.print("  - nenhuma")

    console.print("\n[bold]Top cardinalidade:[/bold]")
    for item in resultado.get("cardinalidade", [])[:15]:
        console.print(
            f"  🧬 {item['coluna']} → {item['distintos']} distintos ({item['percentual_distintos']}%)"
        )
        time.sleep(0.003)

    console.print("\n[bold]Faixas de datas:[/bold]")
    datas = resultado.get("datas", [])
    if datas:
        for item in datas[:15]:
            console.print(f"  📅 {item['coluna']} → {item['min']} até {item['max']}")
            time.sleep(0.003)
    else:
        console.print("  - nenhuma")

    console.print("\n[bold]Amostra:[/bold]")
    amostra = resultado.get("amostra", [])
    if amostra:
        for i, row in enumerate(amostra[:3], start=1):
            console.print(f"  [cyan]Linha {i}[/cyan]")
            for col, val in row.items():
                console.print(f"    - {col}: {val}")
            time.sleep(0.004)
    else:
        console.print("  - nenhuma")


def _data_inspector_perfil_tabela(current_db_env: str):
    tabela = Prompt.ask("[bold]Informe a tabela (ex: _ppa.Indicador_Analisado)[/bold]").strip()
    if not tabela:
        console.print("[yellow]Nenhuma tabela informada.[/yellow]")
        return

    limite_str = Prompt.ask("[bold]Quantidade máxima de linhas[/bold]", default="200").strip()
    try:
        limite = int(limite_str)
    except Exception:
        limite = 200

    origem = f"Tabela: {tabela} (TOP {limite})"

    with ui.status("🔌 Conectando ao banco e carregando dados..."):
        df = carregar_dataframe(tabela=tabela, limit=limite)

    with ui.status("🧠 Analisando dados com pandas..."):
        resultado = analisar_dataframe(df, origem=origem)

    with ui.status("📝 Gerando relatório Markdown..."):
        md = render_markdown_data_inspector(resultado)

    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / "data_inspector_tabela.md"
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_data_inspector(resultado)
    ui.success("✅ Análise de dados concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _data_inspector_perfil_query():
    query = Prompt.ask("[bold]Cole a query SQL[/bold]").strip()
    if not query:
        console.print("[yellow]Nenhuma query informada.[/yellow]")
        return

    origem = "Query SQL informada"

    with ui.status("🔌 Conectando ao banco e executando query..."):
        df = carregar_dataframe(query=query)

    with ui.status("🧠 Analisando dados com pandas..."):
        resultado = analisar_dataframe(df, origem=origem)

    with ui.status("📝 Gerando relatório Markdown..."):
        md = render_markdown_data_inspector(resultado)

    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / "data_inspector_query.md"
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_data_inspector(resultado)
    ui.success("✅ Análise de dados concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _data_inspector_perfil_query(current_db_env: str):
    query = Prompt.ask("[bold]Cole a query SQL[/bold]").strip()
    if not query:
        console.print("[yellow]Nenhuma query informada.[/yellow]")
        return

    origem = "Query SQL informada"

    with ui.status("🔌 Conectando ao banco e executando query..."):
        df = carregar_dataframe(query=query)

    with ui.status("🧠 Analisando dados com pandas..."):
        resultado = analisar_dataframe(df, origem=origem)

    with ui.status("📝 Gerando relatório Markdown..."):
        md = render_markdown_data_inspector(resultado)

    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / "data_inspector_query.md"
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_data_inspector(resultado)
    ui.success("✅ Análise de dados concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _data_inspector_estrutura_tabela(current_db_env: str):
    tabela = Prompt.ask("[bold]Informe a tabela para inspecionar a estrutura[/bold]").strip()
    if not tabela:
        console.print("[yellow]Nenhuma tabela informada.[/yellow]")
        return

    with ui.status("🧱 Lendo metadados da tabela..."):
        resultado = analisar_estrutura_tabela(tabela)

    with ui.status("📝 Gerando relatório de estrutura..."):
        md = render_markdown_schema_inspector(resultado)

    nome_relatorio = f"schema_{tabela.replace('.', '_')}.md"
    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_schema_inspector(resultado)
    ui.success("✅ Inspeção estrutural concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _data_inspector_estrutura_ia(current_db_env: str):
    tabela = Prompt.ask("[bold]Informe a tabela para estrutura + IA[/bold]").strip()
    if not tabela:
        console.print("[yellow]Nenhuma tabela informada.[/yellow]")
        return

    limite_str = Prompt.ask("[bold]Quantidade máxima de linhas para amostra de dados[/bold]", default="150").strip()
    try:
        limite = int(limite_str)
    except Exception:
        limite = 150

    with ui.status("🧱 Lendo estrutura da tabela..."):
        estrutura = analisar_estrutura_tabela(tabela)

    with ui.status("📊 Carregando amostra de dados..."):
        df = carregar_dataframe(tabela=tabela, limit=limite)

    with ui.status("🧠 Analisando dados..."):
        perfil = analisar_dataframe(df, origem=f"Tabela: {tabela} (TOP {limite})")

    with ui.status("🤖 Montando prompt para IA..."):
        prompt_ia = montar_prompt_comentario_dados(
            perfil_dados=perfil,
            estrutura_tabela=estrutura,
        )

    with ui.status("🤖 Solicitando comentário da IA..."):
        comentario_ia = _comentar_dados_com_ia(
            prompt_ia,
            cache_key=f"schema_ai_{tabela.replace('.', '_')}_{limite}"
        )

    md_estrutura = render_markdown_schema_inspector(estrutura)
    md_dados = render_markdown_data_inspector(perfil)

    md_final = "\n\n".join([
        md_estrutura,
        md_dados,
        "# Comentário da IA",
        "",
        comentario_ia,
        "",
    ])

    nome_relatorio = f"schema_ai_{tabela.replace('.', '_')}.md"
    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório final..."):
        caminho_saida.write_text(md_final, encoding="utf-8")

    _imprimir_resultado_schema_inspector(estrutura)
    console.print("\n[bold]Comentário da IA:[/bold]")
    console.print(comentario_ia)

    ui.success("✅ Estrutura + IA concluídos.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _data_inspector_anomalias(current_db_env: str):
    tabela = Prompt.ask("[bold]Informe a tabela para detectar anomalias[/bold]").strip()
    if not tabela:
        console.print("[yellow]Nenhuma tabela informada.[/yellow]")
        return

    limite_str = Prompt.ask("[bold]Quantidade máxima de linhas para análise[/bold]", default="500").strip()
    try:
        limite = int(limite_str)
    except Exception:
        limite = 500

    with ui.status("📊 Carregando dados da tabela..."):
        df = carregar_dataframe(tabela=tabela, limit=limite)

    with ui.status("🚨 Detectando anomalias..."):
        resultado = analisar_anomalias_tabela(
            df,
            origem=f"Tabela: {tabela} (TOP {limite})"
        )

    with ui.status("📝 Gerando relatório de anomalias..."):
        md = render_markdown_anomalias(resultado)

    nome_relatorio = f"anomalias_{tabela.replace('.', '_')}.md"
    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_anomalias(resultado)
    ui.success("✅ Detecção de anomalias concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _data_inspector_anomalias_ia(current_db_env: str):
    tabela = Prompt.ask("[bold]Informe a tabela para detectar anomalias + IA[/bold]").strip()
    if not tabela:
        console.print("[yellow]Nenhuma tabela informada.[/yellow]")
        return

    limite_str = Prompt.ask("[bold]Quantidade máxima de linhas para análise[/bold]", default="500").strip()
    try:
        limite = int(limite_str)
    except Exception:
        limite = 500

    with ui.status("🧱 Lendo estrutura da tabela..."):
        estrutura = analisar_estrutura_tabela(tabela)

    with ui.status("📊 Carregando dados da tabela..."):
        df = carregar_dataframe(tabela=tabela, limit=limite)

    with ui.status("🚨 Detectando anomalias..."):
        resultado = analisar_anomalias_tabela(
            df,
            origem=f"Tabela: {tabela} (TOP {limite})"
        )

    with ui.status("🤖 Montando prompt para IA..."):
        prompt_ia = montar_prompt_comentario_anomalias(
            resultado_anomalias=resultado,
            estrutura_tabela=estrutura,
        )

    with ui.status("🤖 Solicitando comentário da IA..."):
        comentario_ia = _comentar_dados_com_ia(
            prompt_ia,
            cache_key=f"anomalias_ai_{tabela.replace('.', '_')}_{limite}"
        )

    md_anomalias = render_markdown_anomalias(resultado)
    md_estrutura = render_markdown_schema_inspector(estrutura)

    md_final = "\n\n".join([
        md_estrutura,
        md_anomalias,
        "# Comentário da IA",
        "",
        comentario_ia,
        "",
    ])

    nome_relatorio = f"anomalias_ai_{tabela.replace('.', '_')}.md"
    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório final..."):
        caminho_saida.write_text(md_final, encoding="utf-8")

    _imprimir_resultado_anomalias(resultado)
    console.print("\n[bold]Comentário da IA:[/bold]")
    console.print(comentario_ia)

    ui.success("✅ Anomalias + IA concluídos.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")



def _executar_data_inspector(current_db_env: str):
    while True:
        console.print()

        info = Table.grid(padding=(0, 2))
        info.add_column(style="green", justify="right")
        info.add_column(style="white")

        info.add_row("Projeto", SIGBOARD_PROJECT_PATH)
        info.add_row("Banco ativo", _format_db_env_label(current_db_env))

        console.print(
            Panel(
                info,
                title="📊 SIGBOARD DATA INSPECTOR",
                border_style="green",
                expand=False,
            )
        )

        tabela = Table(title="Análise de Dados", expand=False, border_style="green")
        tabela.add_column("Opção", style="green", width=8, justify="center")
        tabela.add_column("Descrição", style="white")

        tabela.add_row("1", "Perfil de dados por tabela")
        tabela.add_row("2", "Perfil de dados por query")
        tabela.add_row("3", "Estrutura da tabela")
        tabela.add_row("4", "Estrutura da tabela + comentário com IA")
        tabela.add_row("5", "Detectar anomalias na tabela")
        tabela.add_row("6", "Anomalias na tabela + comentário com IA")
        tabela.add_row("7", "Detectar anomalias no banco de dados")
        tabela.add_row("K", "_Avançado -> Gerar domain map semântico a partir do JSON estrutural")
        tabela.add_row("8", "_Avançado -> Análise semântica de schema via JSON")
        tabela.add_row("9", "_Avançado -> Cruzamento schema estrutural × domain map")
        tabela.add_row("L", "_Avançado -> Gerar parecer técnico IA para cruzamento semântico")
        tabela.add_row("M", "_Avançado -> Gerar inventário de maturidade dos domínios")
        tabela.add_row("P", "Analisar procedure")
        tabela.add_row("I", "Analisar procedure + comentário com IA")
        tabela.add_row("0", "Voltar")

        console.print(tabela)
        console.print()

        try:
            modo = normalize_menu_option(
                Prompt.ask("[bold]Modo[/bold]", default="1"),
                {"1", "2", "3", "4", "5", "6", "7", "k", "8", "9", "l", "m", "p", "i", "0"}
            )
        except Exception as exc:
            console.print(f"[red]{exc}[/red]")
            _pausar()
            continue

        if modo == "1":
            run_safe(lambda: _data_inspector_perfil_tabela(current_db_env), friendly_name="perfil de dados por tabela")
            _pausar()
            continue

        elif modo == "2":
            run_safe(lambda: _data_inspector_perfil_query(current_db_env), friendly_name="perfil de dados por query")
            _pausar()
            continue

        elif modo == "3":
            run_safe(lambda: _data_inspector_estrutura_tabela(current_db_env), friendly_name="estrutura da tabela")
            _pausar()
            continue

        elif modo == "4":
            run_safe(lambda: _data_inspector_estrutura_ia(current_db_env), friendly_name="estrutura da tabela com IA")
            _pausar()
            continue

        elif modo == "5":
            run_safe(lambda: _data_inspector_anomalias(current_db_env), friendly_name="anomalias na tabela")
            _pausar()
            continue

        elif modo == "6":
            run_safe(lambda: _data_inspector_anomalias_ia(current_db_env), friendly_name="anomalias na tabela com IA")
            _pausar()
            continue

        elif modo == "7":
            run_safe(lambda: _data_inspector_radar_banco(current_db_env), friendly_name="anomalias no banco")
            _pausar()
            continue

        elif modo == "k":
            run_safe(
                _gerar_domain_map_semantico,
                friendly_name="geração de domain map semântico"
            )
            _pausar()

        elif modo == "8":
            run_safe(
                lambda: _data_inspector_schema_semantico_json(current_db_env),
                friendly_name="análise semântica de schema via JSON"
            )
            _pausar()
            continue

        elif modo == "9":
            run_safe(
                lambda: _data_inspector_schema_cross_domain(current_db_env),
                friendly_name="cruzamento schema x domínio"
            )
            _pausar()
            continue

        elif modo == "l":
            run_safe(
                _gerar_parecer_ia_schema_cross,
                friendly_name="parecer técnico IA do cruzamento semântico"
            )
            _pausar()

        elif modo == "m":
            run_safe(
                _gerar_inventario_dominios,
                friendly_name="inventário de maturidade dos domínios"
            )
            _pausar()

        elif modo == "p":
            def _acao_procedure():
                procedure_name = require_non_empty(
                    Prompt.ask("Nome da procedure"),
                    "Informe o nome da procedure."
                )
                run_procedure_analysis(procedure_name, current_db_env)

            run_safe(_acao_procedure, friendly_name="análise de procedure")
            _pausar()
            continue

        elif modo == "i":
            if not _verificar_config_ia():
                _pausar()
                continue

            def _acao_procedure_ai():
                procedure_name = require_non_empty(
                    Prompt.ask("Nome da procedure"),
                    "Informe o nome da procedure."
                )
                run_procedure_analysis_with_ai(procedure_name, current_db_env)

            run_safe(_acao_procedure_ai, friendly_name="análise de procedure com IA")
            _pausar()
            continue

        elif modo == "0":
            break



def _montar_caminho_relatorio(nome_arquivo: str) -> str:
    nome_arquivo = (nome_arquivo or "").strip()
    if not nome_arquivo:
        return ""

    nome_path = Path(nome_arquivo)

    if nome_path.is_absolute():
        caminho_final = nome_path
    elif nome_path.parent != Path("."):
        caminho_final = Path(SIGBOARD_OUTPUT_DIR) / nome_path
    else:
        caminho_final = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_arquivo

    if caminho_final.suffix.lower() != ".md":
        caminho_final = caminho_final.with_suffix(".md")

    caminho_final = caminho_final.expanduser().resolve()
    caminho_final.parent.mkdir(parents=True, exist_ok=True)

    return str(caminho_final)



def _executar_include_script_analyzer():
    console.print(f"\n[bold cyan]📜 INCLUDE SCRIPT ANALYZER[/bold cyan]")
    console.print(f"[cyan]Projeto:[/cyan] {SIGBOARD_PROJECT_PATH}\n")

    entrada = require_non_empty(
        Prompt.ask("[bold]Informe o caminho do arquivo include .php[/bold]"),
        "Informe o caminho do arquivo include .php."
    )

    caminho_completo = _resolver_caminho_include_direto(SIGBOARD_PROJECT_PATH, entrada)

    if not caminho_completo.exists():
        raise SigboardToolsError(f"Arquivo não encontrado: {caminho_completo}")

    if not caminho_completo.is_file():
        raise SigboardToolsError(f"O caminho informado não é um arquivo: {caminho_completo}")

    console.print(f"[cyan]Arquivo selecionado:[/cyan] {caminho_completo}")

    with ui.status("📂 Lendo e analisando JavaScript do include..."):
        resultado = analisar_include_script(caminho_completo)

    if not resultado:
        raise SigboardToolsError("Não foi possível analisar o arquivo.")

    origem = str(caminho_completo)

    with ui.status("🧠 Gerando relatório estruturado..."):
        md = render_markdown_include_script(resultado, origem=origem)

    try:
        rel_path = caminho_completo.relative_to(Path(SIGBOARD_PROJECT_PATH))
        nome_relatorio = f"include_script_{str(rel_path)}.md"
    except Exception:
        nome_base = caminho_completo.name.replace(".php", "")
        nome_relatorio = f"include_script_{nome_base}.md"

    nome_relatorio = nome_relatorio.replace("/", "_").replace("\\", "_")

    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório Markdown..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_include_script(resultado, origem)
    ui.success("✅ Análise de JavaScript do include concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")



def _imprimir_resultado_include_script(resultado: dict, origem: str):
    console.print()
    console.print(Panel(
        f"[bold]Arquivo:[/bold] {resultado['arquivo']}\n"
        f"[bold]Origem:[/bold] {origem}\n"
        f"[bold]Linhas:[/bold] {resultado['linhas']}",
        title="📜 Include Script Analyzer",
        expand=False,
        border_style="cyan",
    ))

    ajax = resultado.get("ajax", {}) or {}
    blocos = resultado.get("blocos_detalhados", []) or []

    total_eventos_jquery = sum(len(b.get("eventos_jquery", [])) for b in blocos if not b.get("is_external"))
    total_formdatas = sum(len(b.get("formdatas", [])) for b in blocos if not b.get("is_external"))
    total_ajax_calls = sum(len(b.get("ajax_calls", [])) for b in blocos if not b.get("is_external"))
    total_callbacks = sum(len(b.get("callbacks_ajax", [])) for b in blocos if not b.get("is_external"))
    total_swal = sum(len(b.get("swal_calls", [])) for b in blocos if not b.get("is_external"))

    ui.print_lento(
        [
            "",
            f"📦 Blocos <script> inline: {resultado.get('script_blocks', 0)}",
            f"🌍 Scripts externos: {len(resultado.get('scripts_externos', []))}",
            f"🖱️ Eventos inline HTML: {len(resultado.get('eventos_inline', []))}",
            f"🧠 Funções JavaScript: {len(resultado.get('funcoes_js', []))}",
            f"🎯 Eventos jQuery: {total_eventos_jquery}",
            f"📨 FormData: {total_formdatas}",
            f"⚡ AJAX detalhado: {total_ajax_calls}",
            f"🪝 Callbacks AJAX: {total_callbacks}",
            f"💬 SweetAlert: {total_swal}",
            "",
        ],
        delay=0.02
    )

    console.print("\n[bold]Scripts externos:[/bold]")
    scripts_externos = resultado.get("scripts_externos", [])
    if scripts_externos:
        for item in scripts_externos[:20]:
            console.print(f"  🌍 {item}")
            time.sleep(0.004)
        if len(scripts_externos) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhum")

    console.print("\n[bold]Eventos inline HTML:[/bold]")
    eventos_inline = resultado.get("eventos_inline", [])
    if eventos_inline:
        for item in eventos_inline[:20]:
            console.print(
                f"  🖱️ <{item['tag']}> [cyan]{item['evento']}[/cyan] → {item['handler']}"
            )
            time.sleep(0.004)
        if len(eventos_inline) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhum")

    console.print("\n[bold]Endpoints detectados:[/bold]")
    endpoints = ajax.get("endpoints", [])
    if endpoints:
        for item in endpoints[:20]:
            console.print(f"  🎯 {item}")
            time.sleep(0.004)
        if len(endpoints) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhum")

    for bloco in blocos:
        if bloco.get("is_external"):
            continue

        console.print()
        console.print(Panel(
            f"[bold]Bloco:[/bold] #{bloco.get('index')}  \n"
            f"[bold]Linha inicial:[/bold] {bloco.get('start_line')}",
            title="🧩 Script inline",
            expand=False,
            border_style="magenta",
        ))

        fluxo = bloco.get("fluxo", [])
        if fluxo:
            console.print("[bold]Leitura heurística do fluxo:[/bold]")
            for item in fluxo:
                console.print(f"  - {item}")
                time.sleep(0.004)

        constantes = bloco.get("constantes", [])
        console.print("\n[bold]Constantes:[/bold]")
        if constantes:
            for c in constantes[:20]:
                console.print(f"  🔹 {c['nome']} = {c['valor']}")
                time.sleep(0.004)
            if len(constantes) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhuma")

        funcoes = bloco.get("funcoes", [])
        console.print("\n[bold]Funções:[/bold]")
        if funcoes:
            for f in funcoes[:20]:
                params = ", ".join(f.get("params", []))
                console.print(
                    f"  🧠 {f['nome']}({params}) [cyan](linha relativa {f['linha']})[/cyan]"
                )
                time.sleep(0.004)
            if len(funcoes) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhuma")

        eventos_jquery = bloco.get("eventos_jquery", [])
        console.print("\n[bold]Eventos jQuery:[/bold]")
        if eventos_jquery:
            for e in eventos_jquery[:20]:
                console.print(
                    f"  🎯 alvo={e['alvo']} | evento=[green]{e['evento']}[/green] "
                    f"| seletor=[cyan]{e['seletor']}[/cyan] | linha={e['linha']}"
                )
                time.sleep(0.004)
            if len(eventos_jquery) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhum")

        formdatas = bloco.get("formdatas", [])
        console.print("\n[bold]FormData:[/bold]")
        if formdatas:
            for fd in formdatas[:20]:
                console.print(
                    f"  📨 {fd['variavel']} [cyan](linha relativa {fd['linha']})[/cyan] "
                    f"- campos: {fd['append_count']}"
                )
                for campo in fd.get("campos", [])[:20]:
                    console.print(f"      - {campo['campo']} ← {campo['valor']}")
                    time.sleep(0.003)
            if len(formdatas) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhum")

        ajax_calls = bloco.get("ajax_calls", [])
        console.print("\n[bold]AJAX detalhado:[/bold]")
        if ajax_calls:
            for a in ajax_calls[:20]:
                console.print(
                    f"  ⚡ linha={a['linha']} | method={a.get('method')} | url={a.get('url')} "
                    f"| timeout={a.get('timeout')}"
                )
                time.sleep(0.004)
            if len(ajax_calls) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhum")

        callbacks = bloco.get("callbacks_ajax", [])
        console.print("\n[bold]Callbacks AJAX:[/bold]")
        if callbacks:
            for cb in callbacks[:20]:
                params = ", ".join(cb.get("params", []))
                console.print(
                    f"  🪝 {cb['tipo']}({params}) [cyan](linha relativa {cb['linha']})[/cyan]"
                )
                time.sleep(0.004)
            if len(callbacks) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhum")

        swal = bloco.get("swal_calls", [])
        console.print("\n[bold]SweetAlert:[/bold]")
        if swal:
            for s in swal[:20]:
                console.print(
                    f"  💬 linha={s['linha']} | icon={s.get('icon')} | title={s.get('title')} | text={s.get('text')}"
                )
                time.sleep(0.004)
            if len(swal) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhum")

        console_calls = bloco.get("console_calls", [])
        console.print("\n[bold]Console:[/bold]")
        if console_calls:
            for c in console_calls[:20]:
                console.print(
                    f"  🖥️ linha={c['linha']} | {c['tipo']} → {c['conteudo']}"
                )
                time.sleep(0.004)
            if len(console_calls) > 20:
                console.print("  - ...")
        else:
            console.print("  - nenhum")

        seletores = bloco.get("seletores_jquery", [])
        console.print("\n[bold]Seletores jQuery:[/bold]")
        if seletores:
            for s in seletores[:30]:
                console.print(f"  🔎 {s}")
                time.sleep(0.003)
            if len(seletores) > 30:
                console.print("  - ...")
        else:
            console.print("  - nenhum")



def _entrada_parece_arquivo_include(entrada: str) -> bool:
    if not entrada:
        return False

    e = entrada.strip().replace('"', "").replace("'", "")

    # Não tratar URL como arquivo
    if "action=" in e or e.startswith("http://") or e.startswith("https://"):
        return False

    # Se for Classe.metodo puro, não é arquivo
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$", e):
        return False

    # Heurística de arquivo PHP
    return (
        e.lower().endswith(".php")
        or "/" in e
        or "\\" in e
    )


def _resolver_caminho_include_direto(project_root: str, entrada: str) -> Path:
    entrada = entrada.strip().replace('"', "").replace("'", "")
    p = Path(entrada)

    if p.is_absolute():
        return p.resolve()

    return (Path(project_root) / entrada).resolve()


def _imprimir_resultado_include(resultado_include: dict, origem: str):
    console.print()
    console.print(Panel(
        f"[bold]Arquivo:[/bold] {resultado_include['arquivo']}\n"
        f"[bold]Origem:[/bold] {origem}\n"
        f"[bold]Linhas:[/bold] {resultado_include['linhas']}",
        title="📄 Include analisado",
        expand=False,
        border_style="cyan",
    ))

    ui.print_lento(
        [
            "",
            f"📥 Includes internos: {len(resultado_include['includes'])}",
            f"🌐 Superglobais: {len(resultado_include['superglobais'])}",
            f"⚠️ SQL suspeito: {len(resultado_include.get('sql_suspeito_detalhado') or resultado_include.get('sql_suspeito', []))}",
            f"🎬 Actions: {len(resultado_include['actions'])}",
            f"🧠 Funções: {len(resultado_include['funcoes'])}",
            f"🏗️ Classes: {len(resultado_include['classes'])}",
            f"🧩 Tags HTML: {resultado_include['html_tags_count']}",
            "",
        ],
        delay=0.02
    )

    def imprimir_lista(titulo: str, itens: list, emoji: str = "•", limite: int = 20):
        console.print(f"\n[bold]{titulo}:[/bold]")
        if not itens:
            console.print("  - nenhum")
            return

        for item in itens[:limite]:
            console.print(f"  {emoji} {item}")
            time.sleep(0.005)

        if len(itens) > limite:
            console.print("  - ...")

    imprimir_lista("Superglobais", resultado_include["superglobais"], "🌐")
    imprimir_lista("Includes internos", resultado_include["includes"], "📥")
    imprimir_lista("Actions", resultado_include["actions"], "🎬")
    imprimir_lista("Funções declaradas", resultado_include["funcoes"], "🧠")
    imprimir_lista("Classes declaradas", resultado_include["classes"], "🏗️")
    imprimir_lista("Scripts referenciados", resultado_include["scripts"], "📜")
    imprimir_lista("CSS referenciados", resultado_include["css_links"], "🎨")

    console.print("\n[bold]AJAX detectado:[/bold]")
    ajax = resultado_include.get("ajax", {}) or {}

    if ajax.get("has_ajax"):
        console.print(f"  ⚡ Ocorrências: {ajax.get('ajax_total', 0)}")

        ajax_types = ajax.get("ajax_types", {})
        if ajax_types:
            console.print("  [bold]Tipos encontrados:[/bold]")
            for nome, qtd in ajax_types.items():
                console.print(f"    - {nome}: {qtd}")
                time.sleep(0.005)

        endpoints = ajax.get("endpoints", [])
        if endpoints:
            console.print("  [bold]Endpoints/URLs:[/bold]")
            for item in endpoints[:20]:
                console.print(f"    - {item}")
                time.sleep(0.005)

        console.print(f"  🧱 Scripts inline: {ajax.get('inline_script_blocks', 0)}")
    else:
        console.print("  - nenhum AJAX embutido detectado")

    console.print("\n[bold]SQL suspeito:[/bold]")

    sql_detalhado = resultado_include.get("sql_suspeito_detalhado", []) or []
    sql_simples = resultado_include.get("sql_suspeito", []) or []

    if sql_detalhado:
        for item in sql_detalhado[:20]:
            linha = item.get("linha", "?")
            tipo = item.get("tipo", "desconhecido")
            trecho = item.get("trecho", "")

            console.print(
                f"  ⚠️ [cyan]Linha {linha}[/cyan] [magenta]{tipo}[/magenta] → {trecho}"
            )
            time.sleep(0.004)

        if len(sql_detalhado) > 20:
            console.print("  - ...")

    elif sql_simples:
        for item in sql_simples[:20]:
            console.print(f"  ⚠️ {item}")
            time.sleep(0.004)

        if len(sql_simples) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhum")



def _executar_include_inspector():
    console.print(f"\n[bold cyan]🔎 INCLUDE INSPECTOR[/bold cyan]")
    console.print(f"[cyan]Projeto:[/cyan] {SIGBOARD_PROJECT_PATH}\n")

    entrada = require_non_empty(
        Prompt.ask(
            "[bold]Cole a URL do SIGBOARD, informe Classe.metodo ou caminho de include .php[/bold]"
        ),
        "Informe uma URL do SIGBOARD, Classe.metodo ou caminho de include .php."
    )

    # =========================================================
    # MODO DIRETO: caminho de arquivo include
    # =========================================================
    if _entrada_parece_arquivo_include(entrada):
        caminho_completo = _resolver_caminho_include_direto(SIGBOARD_PROJECT_PATH, entrada)

        if not caminho_completo.exists():
            raise SigboardToolsError(f"Arquivo não encontrado: {caminho_completo}")

        if not caminho_completo.is_file():
            raise SigboardToolsError(f"O caminho informado não é um arquivo: {caminho_completo}")

        console.print(f"[cyan]Modo:[/cyan] análise direta de arquivo include")
        console.print(f"[cyan]Arquivo selecionado:[/cyan] {caminho_completo}")

        with ui.status("📂 Lendo e analisando arquivo include..."):
            resultado_include = analisar_arquivo_include(caminho_completo)

        if not resultado_include:
            raise SigboardToolsError("Não foi possível analisar o arquivo.")

        origem = str(caminho_completo)

        with ui.status("🧠 Gerando relatório estruturado..."):
            md = render_markdown_include(
                resultado_include,
                origem_metodo=origem,
            )

        try:
            rel_path = caminho_completo.relative_to(Path(SIGBOARD_PROJECT_PATH))
            nome_relatorio = f"include_direto_{str(rel_path)}.md"
        except Exception:
            nome_base = caminho_completo.name.replace(".php", "")
            nome_relatorio = f"include_direto_{nome_base}.md"

        nome_relatorio = nome_relatorio.replace("/", "_").replace("\\", "_")

        caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)

        with ui.status("💾 Salvando relatório Markdown..."):
            caminho_saida.write_text(md, encoding="utf-8")

        _imprimir_resultado_include(resultado_include, origem)
        ui.success("✅ Análise do include concluída.")
        console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")
        return

    # =========================================================
    # MODO ORIGINAL: URL ou Classe.metodo
    # =========================================================
    with ui.status("🧠 Interpretando entrada..."):
        interpretado = _interpretar_entrada_deps(entrada)

    if not interpretado:
        raise SigboardToolsError("Não foi possível interpretar a entrada.")

    classe = interpretado.get("classe", "").strip()
    metodo = interpretado.get("metodo", "").strip()
    tipo_entrada = interpretado.get("tipo", "").strip()

    if tipo_entrada == "vazio":
        raise RequiredInputError("Informe uma URL do SIGBOARD, Classe.metodo ou caminho de include .php.")

    if tipo_entrada == "qualificado" and not classe:
        raise SigboardToolsError("Classe/action não identificada na entrada informada.")

    if not metodo:
        raise SigboardToolsError("Método não identificado.")

    console.print(f"[cyan]Classe:[/cyan] {classe or '(não identificada)'}")
    console.print(f"[cyan]Método:[/cyan] {metodo}\n")

    project_path = Path(SIGBOARD_PROJECT_PATH)

    with ui.status("📚 Indexando arquivos PHP do projeto..."):
        arquivos_php = list(project_path.rglob("*.php"))

    metodo_encontrado = None

    with ui.status("🔎 Localizando método no projeto..."):
        for arquivo in arquivos_php:
            if classe:
                nome_arq = arquivo.name.lower()
                if classe.lower() not in nome_arq:
                    continue

            resultado = analisar_metodo_em_arquivo(arquivo, metodo)
            if resultado:
                metodo_encontrado = resultado
                break

    if not metodo_encontrado:
        raise SigboardToolsError("Método não encontrado no projeto.")

    includes = metodo_encontrado.get("includes", [])

    if not includes:
        raise SigboardToolsError("Nenhum include encontrado neste método.")

    console.print("[bold]Includes encontrados:[/bold]\n")

    includes_paths = []

    for i, inc in enumerate(includes, 1):
        caminho = extrair_caminho_include(inc)
        if caminho:
            includes_paths.append(caminho)
            console.print(f"[cyan]{i}.[/cyan] {caminho}")

    if not includes_paths:
        raise SigboardToolsError("Nenhum include válido encontrado.")

    escolha = require_non_empty(
        Prompt.ask("\nEscolha o include para analisar", default="1"),
        "Informe o número do include que deseja analisar."
    )

    try:
        idx = int(escolha) - 1
        include_path = includes_paths[idx]
    except Exception:
        raise SigboardToolsError("Escolha inválida.")

    caminho_completo = resolver_caminho_include(SIGBOARD_PROJECT_PATH, include_path)

    console.print(f"\n[cyan]Arquivo selecionado:[/cyan] {caminho_completo}")

    with ui.status("📂 Lendo e analisando arquivo include..."):
        resultado_include = analisar_arquivo_include(caminho_completo)

    if not resultado_include:
        raise SigboardToolsError("Não foi possível analisar o arquivo.")

    origem = f"{classe}.{metodo}" if classe else metodo

    with ui.status("🧠 Gerando relatório estruturado..."):
        md = render_markdown_include(
            resultado_include,
            origem_metodo=origem,
        )

    nome_relatorio = f"include_{classe}_{metodo}.md" if classe else f"include_{metodo}.md"
    nome_relatorio = nome_relatorio.replace("/", "_").replace("\\", "_")

    caminho_saida = Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR / nome_relatorio
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with ui.status("💾 Salvando relatório Markdown..."):
        caminho_saida.write_text(md, encoding="utf-8")

    _imprimir_resultado_include(resultado_include, origem)
    ui.success("✅ Análise do include concluída.")
    console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_saida}")


def _pedir_nome_relatorio(label: str = "📝 Nome do relatório Markdown (sem caminho, opcional)") -> str:
    nome = input(f"{label}: ").strip()
    return _montar_caminho_relatorio(nome) if nome else ""


def _debug_caminhos():
    console.print("\n[bold cyan]DEBUG DE CAMINHOS[/bold cyan]")
    console.print(f"SIGBOARD_PROJECT_PATH = {SIGBOARD_PROJECT_PATH}")
    console.print(f"SIGBOARD_OUTPUT_DIR   = {SIGBOARD_OUTPUT_DIR}")
    console.print(f"SIGBOARD_REPORT_DIR   = {SIGBOARD_REPORT_DIR}")
    console.print(f"Relatórios           = {Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR}")


def _limpar_tela():
    """
    Limpeza mais agressiva para funcionar melhor em Windows/Git Bash/MINGW.
    """
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass

    try:
        console.clear()
    except Exception:
        pass


def _pausar():
    input("\n↩️  Pressione"
          " Enter para voltar ao menu...")
    # _limpar_tela()


# =========================================================
# Helpers de configuração / IA
# =========================================================

def _verificar_config_ia() -> bool:
    if not GeminiAnalyzer.has_valid_api_key():
        erro = GeminiAnalyzer.get_api_key_error()

        console.print("\n[bold red]Configuração de IA inválida.[/bold red]")
        console.print(f"[yellow]{erro}[/yellow]")

        console.print("\n[bold]Como corrigir:[/bold]")
        console.print("1. Crie um arquivo .env na raiz do projeto")
        console.print("2. Adicione a linha:")
        console.print("   GEMINI_API_KEY=sua_chave_aqui")
        console.print("\nOu defina a variável de ambiente antes de executar o programa.")

        return False

    return True


def _pedir_modo_cache() -> bool:
    console.print("\n[bold]💾 Modo da análise IA:[/bold]")
    console.print("1. Fazer nova análise (ignorar cache)")
    console.print("2. Retornar do cache se existir (padrão)")

    escolha = normalize_menu_option(
        input("Escolha [2]: ") or "2",
        {"1", "2"}
    )

    return escolha == "2"


def _listar_providers_disponiveis() -> list[str]:
    return ["gemini"]


def _listar_modelos_por_provider(provider: str) -> list[str]:
    provider = (provider or "").strip().lower()

    if provider == "gemini":
        return [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-1.5-pro",
        ]

    return []


def _pedir_provider_ia() -> str:
    providers = _listar_providers_disponiveis()
    provider_padrao = SIGBOARD_AI_PROVIDER if SIGBOARD_AI_PROVIDER in providers else providers[0]

    console.print("\n[bold]🤖 Provider de IA:[/bold]")
    for idx, item in enumerate(providers, start=1):
        marcador = " (padrão)" if item == provider_padrao else ""
        console.print(f"{idx}. {item}{marcador}")

    escolha = input(f"Escolha [{providers.index(provider_padrao) + 1}]: ").strip()
    if not escolha:
        return provider_padrao

    try:
        pos = int(escolha) - 1
        if 0 <= pos < len(providers):
            return providers[pos]
    except ValueError:
        pass

    return provider_padrao


def _comentar_dados_com_ia(prompt: str, cache_key: str = "data_inspector") -> str:
    try:
        analyzer = GeminiAnalyzer()
        return analyzer.analyze_free_text(
            prompt=prompt,
            use_cache_key=cache_key,
            prefer_cache=True,
        )
    except GeminiAnalyzerError as exc:
        return f"Falha ao gerar comentário com IA: {exc}"
    except Exception as exc:
        return f"Erro inesperado ao gerar comentário com IA: {exc}"


def _perguntar_uso_ia() -> bool:
    while True:
        resp = input("\n🤖 Gerar laudo inteligente do fluxo? (s/n): ")

        if resp in ("s", "sim"):
            return True
        if resp in ("n", "nao", "não"):
            return False

        print("Resposta inválida. Digite 's' ou 'n'.")


def _pedir_modelo_ia(provider: str) -> str:
    modelos = _listar_modelos_por_provider(provider)
    modelo_padrao = CURRENT_AI_MODEL if CURRENT_AI_MODEL in modelos else modelos[0]

    console.print("\n[bold]🧠 Modelo de IA:[/bold]")
    for idx, item in enumerate(modelos, start=1):
        marcador = " (padrão)" if item == modelo_padrao else ""
        console.print(f"{idx}. {item}{marcador}")

    escolha = input(f"Escolha [{modelos.index(modelo_padrao) + 1}]: ").strip()
    if not escolha:
        return modelo_padrao

    try:
        pos = int(escolha) - 1
        if 0 <= pos < len(modelos):
            return modelos[pos]
    except ValueError:
        pass

    return modelo_padrao


def _pedir_prompt_ia() -> str:
    prompts = GeminiAnalyzer.list_available_prompts()

    if not prompts:
        console.print("[yellow]Nenhum prompt disponível em /prompts. Será usado o padrão configurado.[/yellow]")
        return "ai_analysis_prompt.txt"

    prompt_padrao = SIGBOARD_AI_PROMPT_FILE if SIGBOARD_AI_PROMPT_FILE in prompts else prompts[0]

    console.print("\n[bold]📜 Prompt de análise:[/bold]")
    for idx, item in enumerate(prompts, start=1):
        marcador = " (padrão)" if item == prompt_padrao else ""
        console.print(f"{idx}. {item}{marcador}")

    escolha = input(f"Escolha [{prompts.index(prompt_padrao) + 1}]: ").strip()
    if not escolha:
        return prompt_padrao

    try:
        pos = int(escolha) - 1
        if 0 <= pos < len(prompts):
            return prompts[pos]
    except ValueError:
        pass

    return prompt_padrao


def _completar_entrada_deps(entrada: str) -> str:
    entrada = (entrada or "").strip()

    if not entrada:
        raise RequiredInputError(
            "Informe um método, action.método ou URL do SIGBOARD."
        )

    # Se já veio URL, mantém
    if (
        "http://" in entrada
        or "https://" in entrada
        or "action=" in entrada
        or entrada.startswith("?action=")
        or entrada.startswith("index.php?action=")
    ):
        return entrada

    # Se já veio qualificado, mantém
    if "." in entrada:
        return entrada

    # Veio só o nome do método -> pedir classe/action
    console.print("\n[yellow]Foi informado apenas o nome do método.[/yellow]")
    console.print(
        "[yellow]Como existem métodos repetidos no SIGBOARD, informe a classe/action de origem.[/yellow]"
    )

    classe = require_non_empty(
        input("Classe/action de origem (ex.: PropostaMetaReg): "),
        "Informe a classe/action de origem para continuar a análise de dependências."
    )

    return f"{classe}.{entrada}"


def _interpretar_entrada_ai(entrada: str) -> dict:
    entrada = (entrada or "").strip()

    if not entrada:
        return {
            "tipo": "vazio",
            "entrada": "",
            "url": "",
            "classe": "",
            "metodo": "",
            "parametros": [],
            "dados_url": None,
        }

    parece_url = (
        "http://" in entrada
        or "https://" in entrada
        or "action=" in entrada
        or entrada.startswith("?action=")
        or entrada.startswith("index.php?action=")
    )

    if parece_url:
        dados_url = parse_sigboard_url(entrada) or {}

        return {
            "tipo": "url",
            "entrada": entrada,
            "url": entrada,
            "classe": (dados_url.get("classe") or "").strip(),
            "metodo": (dados_url.get("metodo") or "").strip(),
            "parametros": dados_url.get("parametros", []),
            "dados_url": dados_url,
        }

    return {
        "tipo": "metodo",
        "entrada": entrada,
        "url": "",
        "classe": "",
        "metodo": entrada,
        "parametros": [],
        "dados_url": None,
    }


# =========================================================
# Execuções principais
# =========================================================

def _executar_scan(path: str):
    path = require_non_empty(path, "Caminho do projeto não informado.")

    console.print(f"\n[bold cyan]📂 Scanner inteligente do projeto[/bold cyan]")
    console.print(f"[cyan]Projeto:[/cyan] {path}\n")

    salvar_relatorio = ui.confirm("Deseja salvar relatório Markdown ao final?", default=True)
    nome_relatorio = ""
    if salvar_relatorio:
        nome_relatorio = _pedir_nome_relatorio("📝 Nome do relatório Markdown (sem caminho, opcional)")
        if not nome_relatorio:
            nome_relatorio = _montar_caminho_relatorio("legacy_code_health_scan")

    with ui.status("[bold cyan]Indexando arquivos PHP do projeto...[/bold cyan]"):
        arquivos = listar_php(path)

    if not arquivos:
        raise SigboardToolsError("Nenhum arquivo PHP foi encontrado no projeto.")

    resultados = []
    total = len(arquivos)

    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.console import Group

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        expand=True,
    )

    task = progress.add_task(
        "Varrendo arquivos PHP...",
        total=total,
    )

    arquivo_atual_panel = Panel.fit(
        "[yellow]iniciando...[/yellow]",
        title="Arquivo atual",
        border_style="yellow",
    )

    group = Group(progress, arquivo_atual_panel)

    with Live(group, console=console, refresh_per_second=8) as live:
        for arquivo in arquivos:
            relativo = str(arquivo.relative_to(Path(path)))

            arquivo_atual_panel = Panel.fit(
                f"[yellow]{relativo}[/yellow]",
                title="Arquivo atual",
                border_style="yellow",
            )

            live.update(Group(progress, arquivo_atual_panel))

            resultado = analisar_arquivo_php(path, arquivo)
            resultados.append(resultado)

            progress.advance(task)

    resultado_final = consolidar_resultado_scan(path, resultados)
    pasta_saida = ""
    arquivo_indice = ""

    resumo = Table(title="Resumo do Scanner Inteligente", border_style="cyan", expand=False)
    resumo.add_column("Métrica", style="cyan")
    resumo.add_column("Valor", style="white")

    resumo.add_row("Arquivos PHP analisados", str(resultado_final.php_files_total))
    resumo.add_row("Achados totais", str(resultado_final.findings_total))
    resumo.add_row("Críticos", str(resultado_final.findings_by_severity.get("critical", 0)))
    resumo.add_row("Warnings", str(resultado_final.findings_by_severity.get("warning", 0)))
    resumo.add_row("Info", str(resultado_final.findings_by_severity.get("info", 0)))

    console.print()
    console.print(resumo)

    if resultado_final.top_problematic_files:
        ranking = Table(title="Top arquivos mais problemáticos", border_style="yellow", expand=False)
        ranking.add_column("Arquivo", style="white")
        ranking.add_column("Total", style="cyan", justify="right")
        ranking.add_column("Critical", style="red", justify="right")
        ranking.add_column("Warning", style="yellow", justify="right")
        ranking.add_column("Info", style="green", justify="right")

        for item in resultado_final.top_problematic_files[:10]:
            ranking.add_row(
                item["relative_path"],
                str(item["total_findings"]),
                str(item["critical"]),
                str(item["warning"]),
                str(item["info"]),
            )

        console.print()
        console.print(ranking)

    console.print()
    console.print(
        Panel.fit(
            "\n".join(resultado_final.tree_lines[:40]),
            title="Estrutura resumida de pastas",
            border_style="green",
        )
    )

    if salvar_relatorio and nome_relatorio:
        with ui.status("[bold green]Gerando relatórios Markdown segmentados...[/bold green]"):
            pasta_saida = gerar_relatorios_scan_segmentados(resultado_final, nome_relatorio)
            arquivo_indice = str(Path(pasta_saida) / "00_indice.md")

        console.print(f"\n[bold green]✔ Índice dos relatórios gerado:[/bold green] {arquivo_indice}")

    usar_ia = ui.confirm("Deseja gerar parecer técnico com IA?", default=True)

    if usar_ia:
        if not _verificar_config_ia():
            ui.warning("Configuração de IA indisponível. Parecer técnico não será gerado.")
        else:
            if not pasta_saida:
                if nome_relatorio:
                    pasta_saida = str(Path(nome_relatorio).with_suffix(""))
                else:
                    nome_relatorio = _montar_caminho_relatorio("legacy_code_health_scan")
                    pasta_saida = str(Path(nome_relatorio).with_suffix(""))

                Path(pasta_saida).mkdir(parents=True, exist_ok=True)

            if not arquivo_indice:
                arquivo_indice = str(Path(pasta_saida) / "00_indice.md")

            console.print("\n[bold magenta]🤖 Gerando parecer técnico com IA...[/bold magenta]")

            try:
                gemini = GeminiAnalyzer(
                    provider=SIGBOARD_AI_PROVIDER,
                    model=CURRENT_AI_MODEL,
                    prompt_file="code_health_ai_analysis_prompt.txt",
                )

                commentary = CodeHealthAICommentary(analyzer=gemini)

                with ui.status("[bold magenta]Analisando com IA...[/bold magenta]"):
                    ai_text = commentary.generate(resultado_final)

                if not ai_text or not ai_text.strip():
                    raise SigboardToolsError("A IA não retornou conteúdo para o parecer técnico.")

                arquivo_ia = Path(pasta_saida) / "20_parecer_tecnico_ia.md"
                conteudo_md = "\n".join([
                    "# Parecer Técnico com IA",
                    "",
                    ai_text.strip(),
                    "",
                ])
                arquivo_ia.write_text(conteudo_md, encoding="utf-8")

                console.print(f"[bold green]✔ Parecer IA gerado:[/bold green] {arquivo_ia}")

            except Exception as exc:
                console.print(f"[red]Erro na IA:[/red] {exc}")

    ui.success("✅ Scanner inteligente concluído.")


def _executar_radar(termo: str, path: str, out: str = "", case_sensitive: bool = False, contexto: int = 1):
    termo = require_non_empty(termo, "Informe o termo a pesquisar.")
    path = require_non_empty(path, "Caminho do projeto não informado.")

    console.print(f"\n[bold cyan]📡 RADAR SIGBOARD[/bold cyan]")
    console.print(f"[cyan]Projeto:[/cyan] {path}")
    console.print(f"[cyan]Termo:[/cyan] {termo}")
    console.print(f"[cyan]Contexto:[/cyan] {contexto} linha(s)\n")

    arquivos = listar_php(path)
    resultados = []

    with Progress() as progress:
        task = progress.add_task("🛰️  Analisando arquivos...", total=len(arquivos))

        for arquivo in arquivos:
            encontrados = buscar_texto_em_arquivo(
                arquivo,
                termo,
                case_sensitive=case_sensitive,
                linhas_contexto=contexto
            )
            if encontrados:
                resultados.extend(encontrados)

            progress.advance(task)

    if not resultados:
        ui.warning("⚠️  Nenhuma ocorrência encontrada.")
        return

    linhas = []
    for i, item in enumerate(resultados[:30], start=1):
        linhas.append([
            str(i),
            str(item["linha"]),
            item["arquivo"],
            destacar_termo(item["trecho"][:100], termo, case_sensitive=case_sensitive),
        ])

    ui.live_table(
        titulo=f"Ocorrências encontradas para: {termo}",
        colunas=[
            ("Nº", "cyan", 6, "right"),
            ("Linha", "magenta", 8, "right"),
            ("Arquivo", "white", None, None),
            ("Trecho", "green", None, None),
        ],
        linhas=linhas,
        delay=0.0015,
        expand=False,
    )

    if len(resultados) > 30:
        ui.print_lento(["", "... exibindo apenas as primeiras 30 ocorrências", ""], delay=0.01)

    ui.success(f"✅ Total de ocorrências: {len(resultados)}")
    console.print()

    exibir = min(5, len(resultados))
    for i in range(exibir):
        item = resultados[i]

        bloco = []
        for ctx in item.get("contexto", []):
            linha_formatada = destacar_termo(
                ctx["conteudo"],
                termo,
                case_sensitive=case_sensitive
            )

            if ctx["numero"] == item["linha"]:
                bloco.append(f">>> {ctx['numero']:>5}: {linha_formatada}")
            else:
                bloco.append(f"    {ctx['numero']:>5}: {linha_formatada}")

        console.print(
            Panel(
                "\n".join(bloco),
                title=f"🎯 {item['arquivo']} (linha {item['linha']})",
                expand=False
            )
        )
        time.sleep(0.06)

    if out:
        salvar_markdown(resultados, termo, out)
        console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {out}")


def _interpretar_entrada_deps(entrada: str) -> dict:
    entrada = (entrada or "").strip()

    if not entrada:
        return {
            "tipo": "vazio",
            "classe": "",
            "metodo": "",
            "url": "",
        }

    if (
        "http://" in entrada
        or "https://" in entrada
        or "action=" in entrada
        or entrada.startswith("?action=")
        or entrada.startswith("index.php?action=")
    ):
        dados = parse_sigboard_url(entrada) or {}

        return {
            "tipo": "url",
            "classe": (dados.get("classe") or "").strip(),
            "metodo": (dados.get("metodo") or "").strip(),
            "url": entrada,
        }

    if "." in entrada:
        classe, metodo = entrada.split(".", 1)

        return {
            "tipo": "qualificado",
            "classe": classe.strip(),
            "metodo": metodo.strip(),
            "url": "",
        }

    return {
        "tipo": "simples",
        "classe": "",
        "metodo": entrada,
        "url": "",
    }


def _executar_deps(entrada: str, path: str, out: str = "", deep: int = 1):
    entrada = require_non_empty(
        entrada,
        "Informe um método, action.método ou URL do SIGBOARD."
    )
    path = require_non_empty(path, "Caminho do projeto não informado.")

    info = _interpretar_entrada_deps(entrada)

    if not info:
        raise SigboardToolsError("Não foi possível interpretar a entrada informada.")

    classe = info["classe"]
    metodo = info["metodo"]

    if info["tipo"] == "vazio":
        raise RequiredInputError("Informe um método, action.método ou URL do SIGBOARD.")

    if info["tipo"] == "qualificado":
        if not classe:
            raise SigboardToolsError("Classe/action não informada na entrada qualificada.")
        if not metodo:
            raise SigboardToolsError("Método não informado na entrada qualificada.")

    console.print(f"\n[bold cyan]🧩 DEPENDÊNCIAS DO MÉTODO[/bold cyan]")
    console.print(f"[cyan]Projeto:[/cyan] {path}")

    if info["tipo"] == "qualificado":
        console.print(f"[cyan]Entrada:[/cyan] {classe}.{metodo}")
    elif info["tipo"] == "url":
        console.print(f"[cyan]Entrada:[/cyan] URL SIGBOARD")
        console.print(f"[cyan]Classe detectada:[/cyan] {classe or '(não identificada)'}")
        console.print(f"[cyan]Método detectado:[/cyan] {metodo or '(não identificado)'}")
    else:
        console.print(f"[cyan]Método:[/cyan] {metodo}")

    console.print(f"[cyan]Deep:[/cyan] {deep}\n")

    if not metodo:
        raise SigboardToolsError("Nenhum método foi informado ou identificado.")

    arquivo = None

    with Progress() as progress:
        task = progress.add_task("🔎 Localizando método...", total=None)

        if classe:
            arquivo_classe = encontrar_arquivo_da_action(path, classe)

            if not arquivo_classe:
                progress.update(task, completed=1)
                raise SigboardToolsError(f"Controller/classe '{classe}' não encontrado no projeto.")

            dados_teste = analisar_metodo_em_arquivo(arquivo_classe, metodo)
            if not dados_teste:
                progress.update(task, completed=1)
                raise SigboardToolsError(
                    f"O método '{metodo}' não foi encontrado dentro de '{arquivo_classe.name}'."
                )

            arquivo = arquivo_classe
        else:
            arquivo = encontrar_arquivo_do_metodo(path, metodo)

        progress.update(task, completed=1)

    if not arquivo:
        raise SigboardToolsError("Método não encontrado no projeto.")

    dados = analisar_metodo_em_arquivo(arquivo, metodo)

    if not dados:
        raise SigboardToolsError("Não foi possível analisar o método encontrado.")

    # ================================
    # Resolver includes
    # ================================
    includes_resolvidos = resolver_includes(dados["arquivo"], dados["includes"], path)
    dados["includes_resolvidos"] = includes_resolvidos

    # ================================
    # UI FLOW ANALYZER
    # ================================
    ui_analyzer = UIFlowAnalyzer(SIGBOARD_PROJECT_PATH)

    ui_results = []

    for inc in includes_resolvidos:
        caminho = inc.get("caminho_resolvido")

        if not caminho:
            continue

        result = ui_analyzer.analyze_html_for_actions(caminho)

        ui_results.append({
            "arquivo": caminho,
            "analise_ui": result
        })

    # ================================
    # Agregar actions detectadas na UI
    # ================================

    trace_analyzer = ActionTraceAnalyzer(path)
    ui_actions_unicas = trace_analyzer.collect_actions_from_ui_results(ui_results)
    ui_action_traces = trace_analyzer.trace_actions(ui_actions_unicas)
    dados["ui_action_traces"] = ui_action_traces

    # ================================
    # Dependências externas
    # ================================
    dependencias_externas = []
    if deep >= 1:
        with Progress() as progress:
            task = progress.add_task("🔗 Resolvendo dependências externas...", total=None)
            dependencias_externas = resolver_chamadas_externas(path, dados["chamadas"], deep=deep)
            progress.update(task, completed=1)

    dados["dependencias_externas"] = dependencias_externas
    arvore_dependencias = construir_arvore_dependencias(dados)
    dados["arvore_dependencias"] = arvore_dependencias

    titulo_metodo = f"{classe}.{metodo}" if classe else metodo

    console.print(Panel(
        f"[bold]Arquivo:[/bold] {dados['arquivo']}\n"
        f"[bold]Linhas:[/bold] {dados['linha_inicio']} - {dados['linha_fim']}\n"
        f"[bold]Assinatura:[/bold] {dados['assinatura']}",
        title=f"🧠 Método {titulo_metodo}",
        expand=False
    ))

    ui.print_lento(
        [
            "",
            f"⚙️  Parâmetros: {len(dados['parametros'])}",
            f"🌐 Superglobais: {len(dados['superglobais'])}",
            f"🔗 Chamadas: {len(dados['chamadas'])}",
            f"🗄️  Tabelas: {len(dados['tabelas'])}",
            f"📦 Procedures: {len(dados['procedures'])}",
            "",
        ],
        delay=0.025
    )

    def imprimir_lista(titulo: str, itens: list, emoji: str = "•"):
        if not itens:
            console.print(f"\n[bold]{titulo}:[/bold] nenhum")
            return
        console.print(f"\n[bold]{titulo}:[/bold]")
        for item in itens:
            console.print(f"  {emoji} {item}")
            time.sleep(0.004)

    imprimir_lista("Parâmetros", dados["parametros"], "⚙️")
    imprimir_lista("Superglobais", dados["superglobais"], "🌐")
    imprimir_lista("Includes / Requires", dados["includes"], "📥")

    console.print(f"\n[bold]Includes resolvidos:[/bold]")
    if dados["includes_resolvidos"]:
        for item in dados["includes_resolvidos"]:
            instrucao = item["instrucao"]
            caminho = item["caminho_resolvido"] or "não resolvido"
            status = "[green]OK[/green]" if item["existe"] else "[red]NÃO ENCONTRADO[/red]"

            console.print(f"  📄 {instrucao}")
            console.print(f"    status: {status}")
            console.print(f"    caminho: {caminho}")

            if item["existe"]:
                console.print(f"    linhas: {item['linhas']} | tamanho: {item['tamanho_bytes']} bytes")
            time.sleep(0.01)
    else:
        console.print("  - nenhum")

    # ================================
    # PRINT UI FLOW
    # ================================
    console.print("\n[bold cyan]🔎 Análise de Interação UI:[/bold cyan]")

    if ui_results:
        for item in ui_results:
            console.print(f"\n📄 Arquivo: {item['arquivo']}")

            ui_data = item["analise_ui"]

            if ui_data.get("modals"):
                console.print(f"  🧩 Modais: {ui_data['modals']}")

            if ui_data.get("onclicks"):
                console.print(f"  🖱️ onclicks: {ui_data['onclicks']}")

            if ui_data.get("data_attrs"):
                console.print(f"  🧷 data-attrs: {ui_data['data_attrs']}")

            if ui_data.get("includes_internos"):
                console.print("  📥 Includes internos:")
                for inc in ui_data["includes_internos"][:10]:
                    console.print(f"     - {inc}")

            if ui_data.get("actions"):
                console.print("  🔎 Possíveis queries em:")
                for action in ui_data["actions"]:
                    console.print(f"     - {action['backend_hint']}")
                    if action.get("params"):
                        for k, v in action["params"].items():
                            console.print(f"       · parâmetro: {k} = {v}")

            if ui_data.get("endpoints"):
                console.print("  🎯 Endpoints candidatos:")
                for endpoint in ui_data["endpoints"][:10]:
                    console.print(f"     - {endpoint}")

            if ui_data.get("includes_relevantes"):
                console.print("  🧠 Subanálise de includes relevantes:")
                for sub in ui_data["includes_relevantes"]:
                    console.print(f"     📥 {sub.get('include')}")

                    status_sub = sub.get("status", "-")
                    console.print(f"        status: {status_sub}")

                    analise_sub = sub.get("analise") or {}
                    if not analise_sub:
                        continue

                    if analise_sub.get("modals"):
                        console.print(f"        modais: {analise_sub['modals']}")

                    if analise_sub.get("buttons"):
                        console.print(f"        botões: {analise_sub['buttons'][:8]}")

                    if analise_sub.get("links"):
                        console.print("        links clicáveis:")
                        for link in analise_sub["links"][:8]:
                            texto = link.get("text", "")
                            extra = []
                            if link.get("class"):
                                extra.append(f"class={link['class']}")
                            if link.get("id"):
                                extra.append(f"id={link['id']}")
                            sufixo = f" ({', '.join(extra)})" if extra else ""
                            console.print(f"          - {texto}{sufixo}")

                    if analise_sub.get("clickable_elements"):
                        console.print("        elementos clicáveis:")
                        for elem in analise_sub["clickable_elements"][:12]:
                            label = elem.get("label", "")
                            elem_type = elem.get("type", "")
                            css_class = elem.get("class", "")
                            priority = elem.get("priority", "")
                            semantic_hint = elem.get("semantic_hint")

                            extras = []
                            if css_class:
                                extras.append(f"class={css_class}")
                            if priority:
                                extras.append(f"prioridade={priority}")
                            if semantic_hint:
                                extras.append(f"hint={semantic_hint}")

                            extra_text = f" ({', '.join(extras)})" if extras else ""
                            console.print(f"          - [{elem_type}] {label}{extra_text}")

                            if elem.get("onclick"):
                                console.print(f"            onclick: {elem['onclick']}")

                            if elem.get("href"):
                                console.print(f"            href: {elem['href']}")

                            if elem.get("js_function"):
                                console.print(f"            função JS: {elem['js_function']}")

                            if elem.get("js_args"):
                                console.print("            argumentos:")
                                for arg in elem["js_args"]:
                                    console.print(f"              · {arg}")

                            if elem.get("actions"):
                                console.print("            possíveis queries em:")
                                for action in elem["actions"][:5]:
                                    console.print(f"              · {action['backend_hint']}")

                    if analise_sub.get("onclicks"):
                        console.print(f"        onclicks: {analise_sub['onclicks'][:6]}")

                    if analise_sub.get("actions"):
                        console.print("        possíveis queries em:")
                        for action in analise_sub["actions"][:10]:
                            console.print(f"          - {action['backend_hint']}")

                    if analise_sub.get("endpoints"):
                        console.print("        endpoints:")
                        for endpoint in analise_sub["endpoints"][:10]:
                            console.print(f"          - {endpoint}")

                    if analise_sub.get("onclicks"):
                        console.print(f"        onclicks: {analise_sub['onclicks'][:6]}")

                    if analise_sub.get("actions"):
                        console.print("        possíveis queries em:")
                        for action in analise_sub["actions"][:10]:
                            console.print(f"          - {action['backend_hint']}")

                    if analise_sub.get("endpoints"):
                        console.print("        endpoints:")
                        for endpoint in analise_sub["endpoints"][:10]:
                            console.print(f"          - {endpoint}")

                    if ui_data.get("dynamic_loads"):
                        console.print("  📦 Carregamentos dinâmicos detectados:")
                        for load in ui_data["dynamic_loads"][:10]:
                            console.print(f"     - loader: {load.get('loader_function', '-')}")
                            console.print(f"       endpoint: {load.get('endpoint', '-')}")
                            console.print(f"       alvo: {load.get('target', '-')}")
                            if load.get("actions"):
                                console.print("       backend provável:")
                                for action in load["actions"][:5]:
                                    console.print(f"         · {action['backend_hint']}")

                    if analise_sub.get("dynamic_loads"):
                        console.print("        carregamentos dinâmicos:")
                        for load in analise_sub["dynamic_loads"][:10]:
                            console.print(f"          - endpoint: {load.get('endpoint', '-')}")
                            console.print(f"            alvo: {load.get('target', '-')}")
                            if load.get("actions"):
                                console.print("            backend provável:")
                                for action in load["actions"][:5]:
                                    console.print(f"              · {action['backend_hint']}")
    else:
        console.print("  - nenhum evento UI detectado")

    # ================================
    # TRACE AUTOMÁTICO DAS ACTIONS DE UI
    # ================================
    console.print("\n[bold magenta]🧠 Trace automático de actions detectadas na UI:[/bold magenta]")

    if dados.get("ui_action_traces"):
        for trace in dados["ui_action_traces"]:
            console.print(f"\n  🎯 {trace['backend_hint']}")

            if trace.get("params"):
                console.print("     parâmetros:")
                for k, v in trace["params"].items():
                    console.print(f"       - {k} = {v}")

            if trace.get("erro"):
                console.print(f"     [red]erro:[/red] {trace['erro']}")
                continue

            if trace.get("arquivo_classe"):
                console.print(f"     arquivo: {trace['arquivo_classe']}")

            if trace.get("metodo_encontrado"):
                console.print("     status: [green]método encontrado[/green]")
                console.print(f"     assinatura: {trace.get('assinatura')}")
                console.print(
                    f"     linhas: {trace.get('linha_inicio')} - {trace.get('linha_fim')}"
                )
            else:
                console.print("     status: [yellow]método não encontrado[/yellow]")

            if trace.get("tabelas"):
                console.print("     tabelas:")
                for tb in trace["tabelas"][:10]:
                    console.print(f"       - {tb}")

            if trace.get("procedures"):
                console.print("     procedures:")
                for pr in trace["procedures"][:10]:
                    console.print(f"       - {pr}")

            if trace.get("includes"):
                console.print("     includes:")
                for inc in trace["includes"][:10]:
                    console.print(f"       - {inc}")

            if trace.get("queries_completas"):
                console.print("     queries completas:")
                for q in trace["queries_completas"][:3]:
                    etiqueta = q.get("tipo", "query")
                    console.print(f"       - [{etiqueta}]")
                    for linha in q.get("sql", "").splitlines()[:10]:
                        console.print(f"         {linha}")
            elif trace.get("sql_suspeito"):
                console.print("     SQL suspeito:")
                for item_sql in trace["sql_suspeito"][:5]:
                    console.print(f"       - {item_sql}")
    else:
        console.print("  - nenhuma action de UI rastreada")

    imprimir_lista("Actions", dados["actions"], "🎬")
    imprimir_lista("Tabelas", dados["tabelas"], "🗄️")
    imprimir_lista("Procedures", dados["procedures"], "📦")

    console.print(f"\n[bold]Instanciações:[/bold]")
    if dados["instanciacoes"]:
        for item in dados["instanciacoes"]:
            console.print(f"  🏗️  {item['variavel']} => {item['classe']}")
            time.sleep(0.005)
    else:
        console.print("  - nenhuma")

    console.print(f"\n[bold]Chamadas de métodos:[/bold]")
    if dados["chamadas"]:
        for item in dados["chamadas"]:
            classe_item = f" ({item['classe']})" if item["classe"] else ""
            console.print(f"  🔗 {item['objeto']}->{item['metodo']}(){classe_item}")
            time.sleep(0.004)
    else:
        console.print("  - nenhuma")

    if dados["sql_suspeito"]:
        console.print("\n[bold]SQL suspeito:[/bold]")
        for item in dados["sql_suspeito"][:20]:
            console.print(f"  ⚠️  {item}")
            time.sleep(0.003)
        if len(dados["sql_suspeito"]) > 20:
            console.print("  - ...")

    console.print(f"\n[bold]Queries completas encontradas no método:[/bold]")
    queries = dados.get("queries_completas", [])
    if queries:
        for i, q in enumerate(queries[:10], start=1):
            console.print(f"  🧾 query #{i} [{q.get('tipo', 'desconhecido')}]")
            if q.get("variavel"):
                console.print(f"    variável: {q['variavel']}")
            if q.get("metodo"):
                console.print(f"    método: {q['metodo']}")
            console.print("    SQL:")
            for linha in q["sql"].splitlines():
                console.print(f"      {linha}")
            console.print()
            time.sleep(0.02)
    else:
        console.print("  - nenhuma")

    console.print(f"\n[bold]Dependências externas resolvidas:[/bold]")
    if dependencias_externas:
        for item in dependencias_externas:
            cabecalho = f"{item['classe']}::{item['metodo']}()"
            if item["arquivo_classe"]:
                console.print(f"  🔍 [cyan]{cabecalho}[/cyan]")
                console.print(f"    arquivo da classe: {item['arquivo_classe']}")
            else:
                console.print(f"  🔍 [yellow]{cabecalho}[/yellow]")
                console.print(f"    arquivo da classe: não encontrado")

            if item["metodo_encontrado"]:
                mi = item["metodo_encontrado"]
                console.print(f"    método encontrado: {mi['linha_inicio']}-{mi['linha_fim']}")
                console.print(f"    assinatura: {mi['assinatura']}")
            else:
                console.print("    método na classe: não encontrado")

            sn = item.get("segundo_nivel")
            if sn:
                console.print("    segundo nível:")
                if sn.get("chamadas"):
                    console.print("      chamadas:")
                    for ch in sn["chamadas"][:8]:
                        classe_sn = f" ({ch['classe']})" if ch.get("classe") else ""
                        console.print(f"        - {ch['objeto']}->{ch['metodo']}(){classe_sn}")
                if sn.get("tabelas"):
                    console.print("      tabelas:")
                    for tb in sn["tabelas"][:8]:
                        console.print(f"        - {tb}")
                if sn.get("procedures"):
                    console.print("      procedures:")
                    for pr in sn["procedures"][:8]:
                        console.print(f"        - {pr}")
                if sn.get("includes"):
                    console.print("      includes:")
                    for inc in sn["includes"][:5]:
                        console.print(f"        - {inc}")
                if sn.get("actions"):
                    console.print("      actions:")
                    for ac in sn["actions"][:5]:
                        console.print(f"        - {ac}")
                if sn.get("queries_completas"):
                    console.print("      queries:")
                    for q in sn["queries_completas"][:5]:
                        etiqueta = q.get("tipo", "query")
                        console.print(f"        - [{etiqueta}]")
                        for linha in q["sql"].splitlines()[:8]:
                            console.print(f"          {linha}")
                        console.print()
            time.sleep(0.02)
    else:
        console.print("  - nenhuma")

    console.print(f"\n[bold]Árvore de dependências:[/bold]")
    for linha in dados["arvore_dependencias"]:
        console.print(f"  🌳 {linha}")
        time.sleep(0.01)

    # ================================
    # LAUDO DE FLUXO COM IA
    # ================================
    if _verificar_config_ia():
        usar_ia = _perguntar_uso_ia()

        if usar_ia:
            try:
                # console.print("[yellow]DEBUG: laudo IA será chamado agora uma única vez[/yellow]")

                trace_payload = _build_ui_flow_trace_payload(
                    entrada=entrada,
                    info=info,
                    dados=dados,
                    ui_results=ui_results,
                )

                prefer_cache = _pedir_modo_cache()
                provider = _pedir_provider_ia()
                model = _pedir_modelo_ia(provider)

                console.print("\n[bold magenta]🤖 Gerando laudo narrativo do fluxo com IA...[/bold magenta]")

                gemini = GeminiAnalyzer(
                    provider=provider,
                    model=model,
                    prompt_file=SIGBOARD_AI_PROMPT_FILE,
                )

                commentary_service = UIFlowAICommentary(
                    analyzer=gemini,
                    prompt_file="ui_flow_ai_analysis_prompt.txt",
                )

                ai_commentary = commentary_service.generate(
                    trace_data=trace_payload,
                    prefer_cache=prefer_cache,
                )

                if ai_commentary and str(ai_commentary).strip():
                    dados["ui_flow_ai_commentary"] = ai_commentary

                    console.print("\n[bold magenta]🧠 Laudo de fluxo com IA:[/bold magenta]")
                    console.print(ai_commentary)
                else:
                    console.print("\n[yellow]A IA não retornou comentário para o fluxo.[/yellow]")

            except Exception as exc:
                console.print(f"\n[yellow]Não foi possível gerar o laudo com IA:[/yellow] {exc}")

        else:
            console.print("\n[yellow]⏭ Análise com IA ignorada pelo usuário.[/yellow]")

    # ================================
    # SALVAR RELATÓRIO FINAL
    # ================================
    caminho_relatorio = None

    if not out:
        out = _montar_caminho_relatorio("deps_ui_flow_trace.md")

    if out:
        relatorio_md = _montar_relatorio_ui_flow_markdown(dados)
        Path(out).write_text(relatorio_md, encoding="utf-8")
        caminho_relatorio = out

    ui.success("✅ Análise concluída.")

    if caminho_relatorio:
        console.print(f"[bold blue]📝 Relatório salvo em:[/bold blue] {caminho_relatorio}")

    console.print("\n[bold green]↩ Pressione ENTER para voltar ao menu principal.[/bold green]")


def _executar_parse_url(entrada: str):
    dados = parse_sigboard_url(entrada)

    console.print("\n[bold cyan]🔍 PARSER DE URL SIGBOARD[/bold cyan]\n")
    console.print(f"[bold]Action bruta:[/bold] {dados['action_bruta'] or '(vazia)'}")
    console.print(f"[bold]Classe:[/bold] {dados['classe'] or '(não identificada)'}")
    console.print(f"[bold]Método:[/bold] {dados['metodo'] or '(não identificado)'}")

    if dados["parametros"]:
        table = Table(title="Parâmetros da URL")
        table.add_column("Nº", style="cyan", width=6)
        table.add_column("Chave", style="magenta")
        table.add_column("Valor", style="white")

        for i, p in enumerate(dados["parametros"], start=1):
            table.add_row(str(i), p["chave"], p["valor"])

        console.print()
        console.print(table)
    else:
        console.print("\n[yellow]Nenhum parâmetro encontrado.[/yellow]")

    if dados["observacoes"]:
        console.print("\n[bold]Observações:[/bold]")
        for obs in dados["observacoes"]:
            console.print(f"  - {obs}")


def _montar_ai_input(path: str, metodo: str, url: str, deep: int):
    classe = ""
    metodo_final = (metodo or "").strip()
    source_url = (url or "").strip()

    if source_url:
        dados_url = parse_sigboard_url(source_url)
        classe = (dados_url.get("classe") or "").strip()
        metodo_url = (dados_url.get("metodo") or "").strip()

        if not metodo_final:
            metodo_final = metodo_url

    if not metodo_final:
        raise GeminiAnalyzerError("Nenhum método foi informado ou identificado.")

    arquivo = encontrar_arquivo_do_metodo(path, metodo_final)
    if not arquivo:
        raise GeminiAnalyzerError("Método não encontrado no projeto.")

    dados = analisar_metodo_em_arquivo(arquivo, metodo_final)
    if not dados:
        raise GeminiAnalyzerError("Não foi possível analisar o método encontrado.")

    includes_resolvidos = resolver_includes(dados["arquivo"], dados["includes"], path)
    dados["includes_resolvidos"] = includes_resolvidos

    dependencias_externas = []
    if deep >= 1:
        dependencias_externas = resolver_chamadas_externas(path, dados["chamadas"], deep=deep)

    dados["dependencias_externas"] = dependencias_externas
    dados["arvore_dependencias"] = construir_arvore_dependencias(dados)

    php_code = dados.get("codigo", "") or dados.get("conteudo", "") or dados.get("bloco", "") or ""
    if not php_code:
        php_code = (
            f"Assinatura: {dados.get('assinatura', '')}\n"
            f"Linhas: {dados.get('linha_inicio', '?')} - {dados.get('linha_fim', '?')}"
        )

    queries = dados.get("queries_completas", [])
    sql_blocks = [q.get("sql", "").strip() for q in queries if q.get("sql", "").strip()]

    tabelas = list(dict.fromkeys(dados.get("tabelas", [])))
    procedures = list(dict.fromkeys(dados.get("procedures", [])))

    deps_textuais = []

    for ch in dados.get("chamadas", []):
        classe_ch = ch.get("classe") or ""
        obj = ch.get("objeto") or ""
        met = ch.get("metodo") or ""

        if classe_ch:
            deps_textuais.append(f"{classe_ch}::{met}")
        else:
            deps_textuais.append(f"{obj}->{met}")

    for dep in dependencias_externas:
        classe_dep = dep.get("classe", "")
        metodo_dep = dep.get("metodo", "")
        deps_textuais.append(f"{classe_dep}::{metodo_dep}")

    deps_textuais = list(dict.fromkeys([d for d in deps_textuais if d]))

    if procedures:
        tabelas.extend([f"PROC:{p}" for p in procedures])

    ai_input = AIAnalysisInput(
        class_name=classe or "(classe não identificada)",
        method_name=metodo_final,
        php_code=php_code,
        sql_blocks=sql_blocks,
        dependencies=deps_textuais,
        tables=tabelas,
        file_path=dados.get("arquivo"),
        source_url=source_url
    )

    return ai_input


def _executar_ai(
    path: str,
    metodo: str = "",
    url: str = "",
    out: str = "",
    deep: int = 1,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
    prompt_file: str = "ai_analysis_prompt.txt",
    prefer_cache: bool = True,
):
    path = require_non_empty(path, "Caminho do projeto não informado.")

    if not (metodo or "").strip() and not (url or "").strip():
        raise RequiredInputError("Informe um método ou uma URL do SIGBOARD para a análise com IA.")

    console.print(f"\n[bold cyan]🤖 ANÁLISE INTELIGENTE COM IA[/bold cyan]")

    if not _verificar_config_ia():
        return

    classe = ""
    metodo_final = (metodo or "").strip()
    source_url = (url or "").strip()

    if source_url:
        dados_url = parse_sigboard_url(source_url)
        classe = (dados_url.get("classe") or "").strip()
        metodo_url = (dados_url.get("metodo") or "").strip()
        parametros = dados_url.get("parametros", [])

        console.print(f"[cyan]Entrada detectada:[/cyan] URL SIGBOARD")
        console.print(f"[cyan]URL:[/cyan] {source_url}")
        console.print(f"[cyan]Classe detectada:[/cyan] {classe or '(não identificada)'}")
        console.print(f"[cyan]Método detectado:[/cyan] {metodo_url or '(não identificado)'}")

        if parametros:
            nomes = ", ".join(p["chave"] for p in parametros)
            console.print(f"[cyan]Parâmetros detectados:[/cyan] {nomes}")

        if not metodo_final:
            metodo_final = metodo_url
    else:
        console.print(f"[cyan]Entrada detectada:[/cyan] Método")
        console.print(f"[cyan]Método:[/cyan] {metodo_final}")

    if not metodo_final and not source_url:
        raise RequiredInputError("Nenhum método válido foi informado para a análise com IA.")

    console.print(f"[cyan]Projeto:[/cyan] {path}")
    console.print(f"[cyan]Deep:[/cyan] {deep}")
    console.print(f"[cyan]Provider:[/cyan] {provider}")
    console.print(f"[cyan]Modelo:[/cyan] {model}")
    console.print(f"[cyan]Prompt:[/cyan] {prompt_file}")
    console.print(f"[cyan]Modo cache:[/cyan] {'usar cache se existir' if prefer_cache else 'forçar nova análise'}\n")

    try:
        with ui.status("🧪 Preparando dados da análise..."):
            ai_input = _montar_ai_input(path, metodo, url, deep)
    except GeminiAnalyzerError as exc:
        raise SigboardToolsError(f"Erro na preparação da análise: {exc}") from exc
    except Exception as exc:
        raise SigboardToolsError(f"Erro inesperado na preparação: {exc}") from exc

    try:
        analyzer = GeminiAnalyzer(
            provider=provider,
            model=model,
            prompt_file=prompt_file,
        )
    except GeminiAnalyzerError as exc:
        raise SigboardToolsError(f"Erro na configuração da IA: {exc}") from exc

    if prefer_cache and analyzer.has_cache_for(ai_input):
        console.print("[green]💾 Cache disponível para esta análise.[/green]")
    elif prefer_cache:
        console.print("[yellow]⚠️  Nenhum cache encontrado para esta análise. Será feita nova consulta.[/yellow]")

    try:
        with ui.status("🧠 Consultando IA / cache..."):
            result = analyzer.analyze(ai_input, prefer_cache=prefer_cache)
    except GeminiAnalyzerError as exc:
        raise SigboardToolsError(f"Erro na análise IA: {exc}") from exc
    except Exception as exc:
        raise SigboardToolsError(f"Erro inesperado na análise IA: {exc}") from exc

    if not result:
        raise SigboardToolsError("A análise IA não retornou resultado.")

    if result.from_cache:
        ui.info("💾 Origem do resultado: CACHE")
    else:
        ui.info("✨ Origem do resultado: IA")

    console.print(Panel.fit(
        result.summary or "Sem resumo retornado.",
        title="Resumo IA",
        border_style="cyan"
    ))

    console.print(f"\n[bold]🎯 Finalidade:[/bold] {result.purpose or 'Não informada'}")

    console.print("\n[bold]🔄 Fluxo de execução:[/bold]")
    if result.execution_flow:
        for i, passo in enumerate(result.execution_flow, start=1):
            console.print(f"  {i}. {passo}")
            time.sleep(0.01)
    else:
        console.print("  - nenhum")

    console.print("\n[bold]🗄️  Tabelas utilizadas:[/bold]")
    if result.tables_used:
        for t in result.tables_used:
            console.print(f"  - {t}")
            time.sleep(0.006)
    else:
        console.print("  - nenhuma")

    console.print("\n[bold]🔗 Dependências utilizadas:[/bold]")
    if result.dependencies_used:
        for d in result.dependencies_used:
            console.print(f"  - {d}")
            time.sleep(0.006)
    else:
        console.print("  - nenhuma")

    console.print("\n[bold]⚠️  Possíveis problemas:[/bold]")
    if result.risks:
        for r in result.risks:
            sev = (r.severity or "medium").upper()
            console.print(f"  - [{sev}] {r.title}: {r.description}")
            time.sleep(0.01)
    else:
        console.print("  - nenhum problema relevante apontado")

    console.print("\n[bold]💡 Sugestões de melhoria:[/bold]")
    if result.suggestions:
        for s in result.suggestions:
            pri = (s.priority or "medium").upper()
            console.print(f"  - [{pri}] {s.title}: {s.description}")
            time.sleep(0.01)
    else:
        console.print("  - nenhuma sugestão retornada")

    ui.success("✅ Análise inteligente concluída.")

    if out:
        md = analyzer.render_markdown(result, ai_input)
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        console.print(f"[bold blue]📝 Relatório Markdown salvo em:[/bold blue] {out}")


def _executar_doctor_ia():
    console.print("\n[bold cyan]🩺 DOCTOR IA[/bold cyan]\n")

    if GeminiAnalyzer.has_valid_api_key():
        console.print("[green]✓ GEMINI_API_KEY configurada[/green]")
    else:
        console.print("[red]✗ GEMINI_API_KEY ausente ou inválida[/red]")
        console.print(f"[yellow]{GeminiAnalyzer.get_api_key_error()}[/yellow]")

    console.print(f"[cyan]Projeto padrão:[/cyan] {SIGBOARD_PROJECT_PATH}")
    console.print(f"[cyan]Saída padrão:[/cyan] {SIGBOARD_OUTPUT_DIR}")
    console.print(f"[cyan]Pasta de relatórios:[/cyan] {SIGBOARD_REPORT_DIR}")
    console.print(f"[cyan]Modelo IA:[/cyan] {CURRENT_AI_MODEL} [bold yellow][a][/bold yellow]")
    console.print(f"[cyan]Cache habilitado:[/cyan] {'sim' if SIGBOARD_AI_CACHE_ENABLED else 'não'}")
    console.print(f"[cyan]Diretório de cache:[/cyan] {SIGBOARD_AI_CACHE_DIR}")

    try:
        analyzer = GeminiAnalyzer(model=CURRENT_AI_MODEL)
        stats = analyzer.get_cache_stats()
        console.print(f"[cyan]Arquivos em cache:[/cyan] {stats['files']}")
    except GeminiAnalyzerError:
        console.print("[yellow]Não foi possível inspecionar o cache porque a configuração da IA está inválida.[/yellow]")


def _executar_limpar_cache_ia():
    console.print("\n[bold cyan]🧹 LIMPAR CACHE DE IA[/bold cyan]\n")

    if not _verificar_config_ia():
        return

    confirmar = input("Tem certeza que deseja apagar todos os arquivos de cache? (s/n): ").strip().lower()
    if confirmar != "s":
        console.print("[yellow]Operação cancelada.[/yellow]")
        return

    try:
        analyzer = GeminiAnalyzer(model=CURRENT_AI_MODEL)
        removidos = analyzer.clear_cache()
        console.print(f"[bold green]✅ Cache limpo com sucesso.[/bold green] Arquivos removidos: {removidos}")
    except GeminiAnalyzerError as exc:
        console.print(f"[bold red]Erro ao limpar cache:[/bold red] {exc}")


# =========================================================
# CLI commands
# =========================================================

@app.command()
def hello():
    console.print("[bold green]SIGBOARD Tools funcionando.[/bold green]")


@app.command()
def scan(
    path: str = typer.Option(SIGBOARD_PROJECT_PATH, "--path", "-p", help="Caminho do projeto")
):
    _executar_scan(path)


@app.command()
def radar(
    termo: str,
    path: str = typer.Option(SIGBOARD_PROJECT_PATH, "--path", "-p", help="Caminho do projeto"),
    out: str = typer.Option("", "--out", "-o", help="Nome do arquivo Markdown (sem caminho)"),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Busca com diferenciação de maiúsculas/minúsculas"),
    contexto: int = typer.Option(SIGBOARD_DEFAULT_CONTEXTO, "--contexto", "-c", help="Quantidade de linhas antes/depois")
):
    out_final = _montar_caminho_relatorio(out) if out else ""
    _executar_radar(termo, path, out_final, case_sensitive, contexto)


@app.command()
def deps(
    entrada: str = typer.Argument(..., help="Método, action.método ou URL"),
    path: str = typer.Option(SIGBOARD_PROJECT_PATH, "--path", "-p", help="Caminho do projeto"),
    out: str = typer.Option("", "--out", "-o", help="Nome do arquivo Markdown (sem caminho)"),
    deep: int = typer.Option(SIGBOARD_DEFAULT_DEEP, "--deep", "-d", help="Nível de resolução externa (0, 1 ou 2)")
):
    out_final = _montar_caminho_relatorio(out) if out else ""
    _executar_deps(entrada, path, out_final, deep)


@app.command("parse-url")
def parse_url_cmd(entrada: str):
    _executar_parse_url(entrada)


@app.command()
def ai(
    path: str = typer.Option(SIGBOARD_PROJECT_PATH, "--path", "-p", help="Caminho do projeto"),
    metodo: str = typer.Option("", "--metodo", "-m", help="Nome do método"),
    url: str = typer.Option("", "--url", "-u", help="URL do SIGBOARD para extrair Classe.metodo"),
    out: str = typer.Option("", "--out", "-o", help="Nome do arquivo Markdown (sem caminho)"),
    deep: int = typer.Option(SIGBOARD_DEFAULT_DEEP, "--deep", "-d", help="Nível de resolução externa (0, 1 ou 2)"),
    provider: str = typer.Option(SIGBOARD_AI_PROVIDER, "--provider", help="Provider de IA"),
    model: str = typer.Option(CURRENT_AI_MODEL, "--model", help="Modelo de IA"),
    prompt_file: str = typer.Option("ai_analysis_prompt.txt", "--prompt-file", help="Arquivo de prompt em /prompts"),
    prefer_cache: bool = typer.Option(True, "--prefer-cache/--force-new", help="Usar cache se existir ou forçar nova análise")
):
    out_final = _montar_caminho_relatorio(out) if out else ""
    _executar_ai(
        path=path,
        metodo=metodo,
        url=url,
        out=out_final,
        deep=deep,
        provider=provider,
        model=model,
        prompt_file=prompt_file,
        prefer_cache=prefer_cache,
    )


@app.command("doctor-ia")
def doctor_ia_cmd():
    _executar_doctor_ia()


@app.command("clear-cache-ia")
def clear_cache_ia_cmd():
    _executar_limpar_cache_ia()


# =========================================================
# Menu visual
# =========================================================

def _status_api_key_text() -> str:
    return "[green]OK[/green]" if GeminiAnalyzer.has_valid_api_key() else "[red]AUSENTE[/red]"


def _status_cache_text() -> str:
    return "[green]ATIVO[/green]" if SIGBOARD_AI_CACHE_ENABLED else "[yellow]DESATIVADO[/yellow]"


def _renderizar_cabecalho_menu():
    titulo = Text("LEGACY ANALYSIS WORKBENCH", style="bold cyan")
    subtitulo = Text("Reverse engineering and legacy analysis - PHP + SQL Server + AI", style="white")
    bloco = Text.assemble(titulo, "\n", subtitulo)

    console.print(
        Panel(
            Align.center(bloco),
            border_style="cyan",
            padding=(1, 2),
        )
    )


def _imprimir_resultado_schema_inspector(resultado: dict):
    console.print()
    console.print(Panel(
        f"[bold]Tabela:[/bold] {resultado['tabela_completa']}\n"
        f"[bold]Colunas:[/bold] {resultado['total_colunas']}\n"
        f"[bold]PK cols:[/bold] {resultado['total_pk_cols']}\n"
        f"[bold]FKs:[/bold] {resultado['total_fks']}\n"
        f"[bold]Índices:[/bold] {resultado['total_indices']}",
        title="🧱 Estrutura da Tabela",
        expand=False,
        border_style="cyan",
    ))

    console.print("\n[bold]Colunas:[/bold]")
    for c in resultado.get("colunas", [])[:40]:
        nome = c["COLUMN_NAME"]
        tipo = c.get("SQL_TYPE_FORMATADO", c.get("DATA_TYPE", ""))
        nullable = "NULL" if str(c.get("IS_NULLABLE")) == "YES" else "NOT NULL"

        extras = []
        if c.get("IS_PK"):
            extras.append("PK")
        if int(c.get("IS_IDENTITY") or 0) == 1:
            extras.append("IDENTITY")
        extras.append(nullable)

        default_val = c.get("COLUMN_DEFAULT")
        if default_val is not None and not pd.isna(default_val):
            extras.append(f"DEFAULT={default_val}")

        console.print(f"  - {nome} | {tipo} | {' | '.join(extras)}")
        time.sleep(0.003)

    if len(resultado.get("colunas", [])) > 40:
        console.print("  - ...")

    console.print("\n[bold]Primary Key:[/bold]")
    pk = resultado.get("pk", [])
    if pk:
        for item in pk:
            console.print(
                f"  🔑 {item['CONSTRAINT_NAME']} → {item['COLUMN_NAME']} (ordem {item['ORDINAL_POSITION']})"
            )
            time.sleep(0.003)
    else:
        console.print("  - nenhuma")

    console.print("\n[bold]Foreign Keys:[/bold]")
    fks = resultado.get("fks", [])
    if fks:
        for item in fks[:20]:
            console.print(
                f"  🔗 {item['FK_NAME']} → {item['PARENT_COLUMN']} -> "
                f"{item['REFERENCED_SCHEMA']}.{item['REFERENCED_TABLE']}.{item['REFERENCED_COLUMN']}"
            )
            time.sleep(0.003)
        if len(fks) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhuma")

    console.print("\n[bold]Índices:[/bold]")
    idxs = resultado.get("indices", [])
    if idxs:
        for item in idxs[:20]:
            console.print(
                f"  📌 {item['INDEX_NAME']} → {item['COLUMN_NAME']} | "
                f"{item['INDEX_TYPE']} | unique={item['IS_UNIQUE']} | ordem={item['KEY_ORDINAL']}"
            )
            time.sleep(0.003)
        if len(idxs) > 20:
            console.print("  - ...")
    else:
        console.print("  - nenhum")


def _format_db_env_label(env_name: str) -> str:
    env = (env_name or "").strip().lower()
    if env == "homolog":
        return "homologação"
    if env == "prod":
        return "produção"
    return env_name


def _renderizar_status_menu(
    current_db_env: str,
    current_db_server: str,
    current_db_database: str,
    current_db_ip: str,
):
    tabela = Table.grid(padding=(0, 2))
    tabela.add_column(style="bold cyan", justify="right")
    tabela.add_column(style="white")

    tabela.add_row("Projeto", SIGBOARD_PROJECT_PATH)
    tabela.add_row("Provider IA", SIGBOARD_AI_PROVIDER)
    tabela.add_row("Modelo IA", CURRENT_AI_MODEL)
    tabela.add_row("Prompt", SIGBOARD_AI_PROMPT_FILE)
    tabela.add_row("Cache", _status_cache_text())
    tabela.add_row("API Key", _status_api_key_text())
    tabela.add_row("Banco", _format_db_env_label(current_db_env))
    server_display = current_db_server or "-"

    if current_db_ip and current_db_ip != "-":
        server_display = f"{server_display} ({current_db_ip})"

    tabela.add_row("Servidor BD", server_display)

    tabela.add_row("Database", current_db_database or "-")
    tabela.add_row("Relatórios", str(Path(SIGBOARD_OUTPUT_DIR) / SIGBOARD_REPORT_DIR))

    console.print(
        Panel(
            tabela,
            title="Status",
            border_style="blue",
            expand=False,
        )
    )


def _renderizar_opcoes_menu(current_db_env):
    tabela_codigo = Table(title="Análise de Código", expand=True, border_style="cyan")
    tabela_codigo.add_column("Opção", style="bold cyan", width=8, justify="center")
    tabela_codigo.add_column("Descrição", style="white")

    tabela_codigo.add_row("1", "Auditoria técnica do projeto")
    tabela_codigo.add_row("2", "Pesquisa por termo (controller/método/outros)")
    tabela_codigo.add_row("3", "Análise de dependências de método")
    tabela_codigo.add_row("F", "Análise de fachadas/facades")
    tabela_codigo.add_row("G", "Análise de fachada/facade com IA")
    tabela_codigo.add_row("M", "Análise de modelo/model")
    tabela_codigo.add_row("4", "Análise via URL")
    tabela_codigo.add_row("8", "Análise de arquivo include")
    tabela_codigo.add_row("9", "Análise de arquivo JS")
    tabela_codigo.add_row("D", "Análise de dados")

    tabela_ia = Table(title="IA", expand=True, border_style="magenta")
    tabela_ia.add_column("Opção", style="bold magenta", width=8, justify="center")
    tabela_ia.add_column("Descrição", style="white")

    tabela_ia.add_row("5", "Análise inteligente com IA")
    tabela_ia.add_row("6", "Doctor IA")
    tabela_ia.add_row("7", "Limpar Cache de IA")
    tabela_ia.add_row("A", "Alterar modelo de IA")

    tabela_sistema = Table(title="Sistema", expand=True, border_style="yellow")
    tabela_sistema.add_column("Opção", style="bold yellow", width=8, justify="center")
    tabela_sistema.add_column("Descrição", style="white")

    tabela_sistema.add_row("B", f"Alterar banco ({_format_db_env_label(current_db_env)})")
    tabela_sistema.add_row("J", "Importar GraphML para JSON")
    tabela_sistema.add_row("S", "Sobre")
    tabela_sistema.add_row("X", "Sair")

    console.print(Columns([tabela_codigo, tabela_ia, tabela_sistema]))


def _renderizar_rodape_menu():
    console.print(Rule(style="grey50"))
    console.print("[dim]Dica:[/dim] O menu usa automaticamente as configurações do arquivo .env.")
    console.print("[dim]IA:[/dim] Na opção 5, você pode analisar por URL do SIGBOARD ou pelo nome do método.")
    console.print("[dim]Fachada:[/dim] Na opção F, você pode informar nome da fachada, caminho do arquivo ou Classe.metodo.")
    console.print("[dim]Fachada + IA:[/dim] Na opção G, a ferramenta faz a análise estrutural e gera comentário técnico com IA.")
    console.print("[dim]Model:[/dim] Na opção M, você pode informar nome do model ou caminho do arquivo PHP.")


# =========================================================
# Menu principal
# =========================================================

@app.command()
def menu():
    current_db_env = SIGBOARD_DB_ACTIVE
    current_db_server, current_db_database, current_db_ip = obter_info_banco(current_db_env)

    while True:
        _limpar_tela()
        console.print()
        _renderizar_cabecalho_menu()
        _renderizar_status_menu(
            current_db_env,
            current_db_server,
            current_db_database,
            current_db_ip,
        )
        console.print()
        _renderizar_opcoes_menu(current_db_env)
        _renderizar_rodape_menu()

        opcao_raw = input("\nEscolha uma opção: ")
        try:
            opcao = normalize_menu_option(
                opcao_raw,
                {
                    "1", "2", "3", "4", "5", "6", "7", "8", "9",
                    "a", "b", "j", "d", "f", "g", "m", "s", "x"
                },
            )
        except (RequiredInputError, SigboardToolsError, Exception) as exc:
            console.print(f"[red]{exc}[/red]")
            _pausar()
            continue

        if opcao == "1":
            run_safe(lambda: _executar_scan(SIGBOARD_PROJECT_PATH), friendly_name="scanner de arquivos PHP")
            _pausar()

        elif opcao == "2":
            def _acao_radar():
                termo = require_non_empty(
                    input("🎯 Termo a pesquisar (ex.: Indicadorv2.preparaEdicaoCoordenador ou Indicadorv2CTR): "),
                    "Informe o termo a pesquisar."
                )
                out = _pedir_nome_relatorio()

                _executar_radar(
                    termo=termo,
                    path=SIGBOARD_PROJECT_PATH,
                    out=out,
                    case_sensitive=False,
                    contexto=SIGBOARD_DEFAULT_CONTEXTO,
                )

            run_safe(_acao_radar, friendly_name="radar de termos")
            _pausar()

        elif opcao == "3":
            def _acao_deps():
                entrada_deps = require_non_empty(
                    input("Método, action.método ou URL (ex.: preparaLista / PropostaMetaReg.preparaLista): "),
                    "Informe um método, action.método ou URL do SIGBOARD."
                )

                entrada_deps = _completar_entrada_deps(entrada_deps)
                out = _pedir_nome_relatorio()

                _executar_deps(
                    entrada=entrada_deps,
                    path=SIGBOARD_PROJECT_PATH,
                    out=out,
                    deep=SIGBOARD_DEFAULT_DEEP,
                )

            run_safe(_acao_deps, friendly_name="análise de dependências")
            _pausar()

        elif opcao == "f":
            def _acao_fachada():
                entrada_fachada = require_non_empty(
                    input("🏛️ Nome da fachada, caminho do arquivo PHP ou Classe.metodo: "),
                    "Informe o nome da fachada, caminho do arquivo PHP ou Classe.metodo."
                )

                out = _pedir_nome_relatorio()

                _executar_fachada_analyzer(
                    entrada=entrada_fachada,
                    path=SIGBOARD_PROJECT_PATH,
                    out=out,
                )

            run_safe(_acao_fachada, friendly_name="análise de fachadas")
            _pausar()

        elif opcao == "g":
            if not _verificar_config_ia():
                _pausar()
                continue

            def _acao_fachada_ai():
                entrada_fachada = require_non_empty(
                    input("🤖🏛️ Nome da fachada, caminho do arquivo PHP ou Classe.metodo: "),
                    "Informe o nome da fachada, caminho do arquivo PHP ou Classe.metodo."
                )

                out = _pedir_nome_relatorio()

                _executar_fachada_ai(
                    entrada=entrada_fachada,
                    path=SIGBOARD_PROJECT_PATH,
                    out=out,
                )

            run_safe(_acao_fachada_ai, friendly_name="análise de fachada com IA")
            _pausar()

        elif opcao == "m":
            def _acao_model():
                entrada_model = require_non_empty(
                    input("🧩 Nome do model ou caminho do arquivo PHP: "),
                    "Informe o nome do model ou caminho do arquivo PHP."
                )

                out = _pedir_nome_relatorio()

                _executar_model_analyzer(
                    entrada=entrada_model,
                    path=SIGBOARD_PROJECT_PATH,
                    out=out,
                )

            run_safe(_acao_model, friendly_name="análise de model")
            _pausar()

        elif opcao == "4":
            entrada = input("Cole a URL ou query string do SIGBOARD: ").strip()
            _executar_parse_url(entrada)
            analisar = input("\nDeseja rodar deps automaticamente no método encontrado? (s/n): ").strip().lower()
            if analisar == "s":
                out = _pedir_nome_relatorio()
                _executar_deps(
                    entrada=entrada,
                    path=SIGBOARD_PROJECT_PATH,
                    out=out,
                    deep=SIGBOARD_DEFAULT_DEEP,
                )

            _pausar()

        elif opcao == "5":
            if not _verificar_config_ia():
                _pausar()
                continue

            def _acao_ai():
                entrada = require_non_empty(
                    input("🤖 Cole a URL do SIGBOARD ou informe o nome do método: "),
                    "Informe uma URL do SIGBOARD ou o nome do método."
                )

                interpretado = _interpretar_entrada_ai(entrada)
                if interpretado["tipo"] == "vazio":
                    raise RequiredInputError("Nenhuma entrada válida foi informada para análise com IA.")

                url = interpretado["url"]
                metodo = interpretado["metodo"]

                if interpretado["tipo"] == "url":
                    console.print("\n[bold]Entrada interpretada como URL SIGBOARD:[/bold]")
                    console.print(f"  - Classe: {interpretado['classe'] or '(não identificada)'}")
                    console.print(f"  - Método: {interpretado['metodo'] or '(não identificado)'}")
                    if interpretado["parametros"]:
                        console.print("  - Parâmetros:")
                        for p in interpretado["parametros"]:
                            console.print(f"      {p['chave']} = {p['valor']}")
                    else:
                        console.print("  - Parâmetros: nenhum")
                else:
                    console.print("\n[bold]Entrada interpretada como método:[/bold]")
                    console.print(f"  - Método: {metodo}")

                prefer_cache = _pedir_modo_cache()
                out = _pedir_nome_relatorio()

                _executar_ai(
                    path=SIGBOARD_PROJECT_PATH,
                    metodo=metodo,
                    url=url,
                    out=out,
                    deep=SIGBOARD_DEFAULT_DEEP,
                    provider=SIGBOARD_AI_PROVIDER,
                    model=CURRENT_AI_MODEL,
                    prompt_file=SIGBOARD_AI_PROMPT_FILE,
                    prefer_cache=prefer_cache,
                )

            run_safe(_acao_ai, friendly_name="análise inteligente com IA")
            _pausar()

        elif opcao == "6":
            _executar_doctor_ia()
            _pausar()

        elif opcao == "7":
            _executar_limpar_cache_ia()
            _pausar()

        elif opcao == "8":
            run_safe(_executar_include_inspector, friendly_name="include inspector")
            _pausar()

        elif opcao == "9":
            run_safe(_executar_include_script_analyzer, friendly_name="include script analyzer")
            _pausar()

        elif opcao == "a":
            _alterar_modelo_ia()
            _pausar()

        elif opcao == "d":
            run_safe(
                lambda: _executar_data_inspector(current_db_env=current_db_env),
                friendly_name="data inspector"
            )
            _pausar()


        elif opcao == "b":
            current_db_env, current_db_server, current_db_database, current_db_ip = escolher_ambiente_banco(
                current_db_env,
                current_db_server,
                current_db_database,
                current_db_ip,
            )
            continue

        elif opcao.lower() == "j":
            run_safe(
                _importar_graphml_para_json,
                friendly_name="importação GraphML → JSON"
            )
            _pausar()
            continue

        elif opcao.lower() == "s":
            _renderizar_sobre()
            continue

        elif opcao == "x":
            console.print("\n[bold green]🖖 Encerrando SIGBOARD Tools.[/bold green]")
            _limpar_tela()
            break

        else:
            console.print("[red]Opção inválida.[/red]")
            _pausar()


if __name__ == "__main__":
    app()

