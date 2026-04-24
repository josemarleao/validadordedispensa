"""Base de Conhecimento – MPBA Saneamento de Dispensa de Licitação.

Este módulo centraliza todas as referências normativas, estruturas de documentos
oficiais e regras extraídas dos modelos MPBA (Jan/2026). Serve como insumo
único para todos os módulos de validação, garantindo rastreabilidade e respaldo
formal aos resultados gerados pelo sistema.

Documentos de referência incorporados:
  - Modelo DFD (Documento de Formalização de Demanda) – MPBA
  - Termo de Referência – Serviços (Jan/2026) – MPBA
  - Termo de Referência – Aquisições (Jan/2026) – MPBA
  - Tabela de Preços Orçados – MPBA
  - Modelo de Proposta – Aquisições – MPBA
  - Modelo de Proposta – Serviços – MPBA
  - Declaração de Não Emprego de Menor (art. 7º, XXXIII, CF)
  - Declaração Resolução CNMP nº 37/2009
"""

from .normas import (
    NORMAS_GERAIS,
    ESTRUTURA_DFD,
    ESTRUTURA_TR_SERVICOS,
    ESTRUTURA_TR_AQUISICOES,
    ESTRUTURA_TABELA_PRECOS,
    ESTRUTURA_PROPOSTA,
    ESTRUTURA_DECLARACAO_MENOR,
    ESTRUTURA_DECLARACAO_CNMP,
    CERTIDOES_OBRIGATORIAS,
    REGRAS_ORCAMENTOS,
    REGRAS_AVISO_PREVIO,
    REGRAS_DOCUMENTO_BANCARIO,
    REGRAS_PDM_CATMAT,
    REGRAS_GESTOR_FISCAL,
)

__all__ = [
    "NORMAS_GERAIS",
    "ESTRUTURA_DFD",
    "ESTRUTURA_TR_SERVICOS",
    "ESTRUTURA_TR_AQUISICOES",
    "ESTRUTURA_TABELA_PRECOS",
    "ESTRUTURA_PROPOSTA",
    "ESTRUTURA_DECLARACAO_MENOR",
    "ESTRUTURA_DECLARACAO_CNMP",
    "CERTIDOES_OBRIGATORIAS",
    "REGRAS_ORCAMENTOS",
    "REGRAS_AVISO_PREVIO",
    "REGRAS_DOCUMENTO_BANCARIO",
    "REGRAS_PDM_CATMAT",
    "REGRAS_GESTOR_FISCAL",
]
