import re


class MethodFlowAnalyzer:

    def build_steps(self, method_code: str) -> list:
        """
        Gera uma sequência simples de passos lógicos do método.
        Baseado em heurísticas.
        """

        steps = []

        # Entrada HTTP
        if re.search(r"\$_(REQUEST|GET|POST)", method_code):
            steps.append("Lê parâmetros da requisição HTTP")

        # Sessão
        if "$_SESSION" in method_code:
            steps.append("Consulta ou altera dados de sessão")

        # Instancia objetos
        if re.search(r"\bnew\s+[A-Za-z_][A-Za-z0-9_]*", method_code):
            steps.append("Instancia objetos auxiliares ou fachadas")

        # Condicionais
        if re.search(r"\bif\s*\(", method_code):
            steps.append("Executa validações e decisões condicionais")

        # Loops
        if re.search(r"\b(foreach|for|while)\s*\(", method_code):
            steps.append("Processa estruturas de repetição")

        # SQL
        if re.search(r"\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b", method_code, re.I):
            steps.append("Executa operações de banco de dados")

        # Includes
        if re.search(r"\b(include|require|include_once|require_once)\b", method_code):
            steps.append("Inclui arquivos auxiliares")

        # Return
        if re.search(r"\breturn\b", method_code):
            steps.append("Retorna resultado")

        if not steps:
            steps.append("Executa lógica interna do método")

        return steps


    def to_mermaid(self, steps: list) -> str:
        """
        Converte a sequência de passos em um diagrama Mermaid.
        """

        lines = []
        lines.append("flowchart TD")
        lines.append("    A[Início]")

        previous = "A"

        for i, step in enumerate(steps, start=1):

            node = f"N{i}"

            safe_step = step.replace('"', "'")

            lines.append(f'    {previous} --> {node}["{safe_step}"]')

            previous = node

        lines.append(f'    {previous} --> Z[Fim]')

        return "\n".join(lines)