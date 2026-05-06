import re
from pathlib import Path
from typing import Optional, List, Dict

from core.scanner import listar_php
from core.method_analyzer import (
    localizar_metodo_em_arquivo,
    extrair_assinatura,
    analisar_metodo_em_arquivo,
)


def encontrar_arquivo_da_classe(path: str, nome_classe: str) -> Optional[Path]:
    """
    Procura o arquivo PHP que contém a definição da classe.
    """
    arquivos = listar_php(path)
    padrao = re.compile(rf"\bclass\s+{re.escape(nome_classe)}\b", re.IGNORECASE)

    for arquivo in arquivos:
        try:
            conteudo = arquivo.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if padrao.search(conteudo):
            return arquivo

    return None


def localizar_metodo_na_classe(arquivo_classe: Path, nome_metodo: str) -> Optional[Dict]:
    """
    Localiza um método dentro de um arquivo de classe e retorna resumo.
    """
    encontrado = localizar_metodo_em_arquivo(arquivo_classe, nome_metodo)
    if not encontrado:
        return None

    linha_inicio, linha_fim, bloco, _ = encontrado
    assinatura = extrair_assinatura(bloco)

    return {
        "arquivo": str(arquivo_classe),
        "linha_inicio": linha_inicio,
        "linha_fim": linha_fim,
        "assinatura": assinatura,
        "bloco": bloco,
    }


def _resumo_segundo_nivel(path: str, arquivo_classe: Path, nome_metodo: str) -> Optional[Dict]:
    """
    Analisa o método externo encontrado e extrai um resumo de segundo nível.
    """
    dados = analisar_metodo_em_arquivo(arquivo_classe, nome_metodo)
    if not dados:
        return None

    return {
        "assinatura": dados.get("assinatura", ""),
        "linha_inicio": dados.get("linha_inicio", ""),
        "linha_fim": dados.get("linha_fim", ""),
        "instanciacoes": dados.get("instanciacoes", []),
        "chamadas": dados.get("chamadas", []),
        "includes": dados.get("includes", []),
        "actions": dados.get("actions", []),
        "tabelas": dados.get("tabelas", []),
        "procedures": dados.get("procedures", []),
        "superglobais": dados.get("superglobais", []),
        "queries_completas": dados.get("queries_completas", []),
    }


def resolver_chamadas_externas(path: str, chamadas: List[Dict], deep: int = 1) -> List[Dict]:
    """
    Para cada chamada resolvida com classe conhecida, tenta encontrar:
    - arquivo da classe
    - método dentro da classe
    - se deep >= 2, analisa também o conteúdo desse método
    """
    resultados = []
    cache_classes = {}

    for chamada in chamadas:
        classe = chamada.get("classe", "").strip()
        metodo = chamada.get("metodo", "").strip()

        if not classe:
            continue

        if classe not in cache_classes:
            cache_classes[classe] = encontrar_arquivo_da_classe(path, classe)

        arquivo_classe = cache_classes[classe]

        item = {
            "objeto": chamada.get("objeto", ""),
            "classe": classe,
            "metodo": metodo,
            "arquivo_classe": str(arquivo_classe) if arquivo_classe else "",
            "metodo_encontrado": None,
            "segundo_nivel": None,
        }

        if arquivo_classe:
            metodo_info = localizar_metodo_na_classe(arquivo_classe, metodo)
            if metodo_info:
                item["metodo_encontrado"] = metodo_info

                if deep >= 2:
                    item["segundo_nivel"] = _resumo_segundo_nivel(path, arquivo_classe, metodo)

        resultados.append(item)

    return resultados