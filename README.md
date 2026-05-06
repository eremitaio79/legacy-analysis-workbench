# legacy-analysis-workbench

An AI-assisted Python workbench for understanding legacy systems through static analysis, dependency tracing, schema inspection, UI flow analysis, and domain mapping.

This repository is a sanitized public case study derived from a real internal tool built to accelerate comprehension of a large legacy codebase. Sensitive project identifiers, local paths, generated reports, knowledge snapshots, and environment-specific data were removed before publication.

## Problem context

Legacy systems usually fail documentation long before they fail production.

In the original scenario, the challenge was not simply reading source files. The real difficulty was understanding behavior across multiple layers at once:

- PHP controllers, models, includes, and facades spread across a large codebase
- SQL Server schemas and procedures with business rules hidden in data structures
- UI entry points connected to backend actions through implicit flows
- partial tribal knowledge scattered across teams instead of written in one place
- the need to inspect code quickly enough to support maintenance, diagnosis, and modernization decisions

The usual answers were too weak:

- manual grep is slow and loses context
- one-off scripts solve one question and die immediately after
- raw AI prompting without structured extraction produces charming hallucinations and operational sadness

## Why this application was developed

This application was developed to turn legacy analysis into a repeatable engineering workflow.

Instead of asking engineers to manually stitch together architecture, dependencies, schema clues, and UI behavior, the tool was designed to assemble that picture in layers:

- scan code for structural and risky patterns
- trace methods, actions, includes, and external calls
- inspect tables, relationships, and stored procedures directly from the database
- extract UI-driven backend flows from HTML and JavaScript surfaces
- convert schema material into domain maps and semantic reports
- use AI only after enough structured context has been collected

In short, the point was not "use AI on code." The point was to create a disciplined workbench where AI becomes one instrument inside a broader analysis system.

## Core capabilities

- static scanning for code health, suspicious patterns, and large-file hotspots
- dependency tracing for methods, actions, includes, and external class usage
- AI-assisted technical commentary with prompt files, caching, and structured outputs
- SQL Server schema inspection for columns, primary keys, foreign keys, and indexes
- stored procedure analysis and reporting
- data inspection and anomaly commentary workflows
- UI flow analysis from legacy HTML and JavaScript surfaces
- GraphML-to-JSON conversion for structural knowledge building
- domain map generation and semantic cross-analysis

## Architecture highlights

- `main.py`: CLI commands, interactive menu, orchestration, and report workflows
- `core/scanner.py`: project scanning and rule-based findings for legacy PHP analysis
- `core/ai_analyzer.py`: Gemini integration, prompt handling, structured responses, and cache management
- `core/db_connector.py`: SQL Server connection management and environment-aware access
- `core/db_schema_inspector.py`: schema introspection and table structure reporting
- `core/ui_flow_analyzer.py`: extraction of probable backend flows from UI artifacts
- `core/domain_map_generator.py`: domain inference from structural schema data
- `core/graphml_to_json_converter.py`: GraphML ingestion for domain knowledge workflows
- `prompts/`: prompt templates for specialized AI commentary modes

## Tech stack

- Python
- Typer
- Rich
- pandas
- pyodbc
- Google Gemini API
- SQL Server

## Running locally

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in:

- a legacy project path for source analysis
- an output directory for generated reports
- Gemini API settings
- optional SQL Server connection settings for schema/procedure inspection

### 3. Try the CLI

```powershell
python main.py --help
python main.py hello
python main.py doctor-ia
python main.py scan --path .\sample_legacy_app
```

## Notes on publication

- This public version keeps some internal naming in environment variables for compatibility with the original tool lineage.
- Knowledge snapshots, generated reports, and source-specific GraphML assets were intentionally excluded.
- The original internal project remains private and unchanged.
