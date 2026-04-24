"""Schemas de resposta da API."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, computed_field


class Encaminhamento(str, Enum):
    UNIDADE_DEMANDANTE = "UNIDADE DEMANDANTE"
    SGA = "SGA"
    PROSSEGUIR = "PROSSEGUIR"


class StatusRegra(str, Enum):
    CONFORME = "OK"
    INCONFORME = "INCONFORME"
    PENDENCIA = "PENDÊNCIA"


class Providencia(str, Enum):
    DEVOLVER = "Devolver à Unidade Demandante"
    SGA = "Submeter à SGA"
    PROSSEGUIR = "Prosseguir"
    CORRIGIR = "Corrigir"


class ResultadoItem(BaseModel):
    documento: str
    item: str
    status: StatusRegra
    descricao: str
    providencia: Providencia
    via_ia: bool = False  # True quando resultado gerado por análise de IA


class ResumoContagens(BaseModel):
    inconformidades: int
    pendencias: int
    conformes: int


class RelatorioSaneamento(BaseModel):
    processo: str
    tipo: str = "DL não eletrônica – sem contrato"
    resumo: ResumoContagens
    inconformidades: list[ResultadoItem]
    pendencias: list[ResultadoItem]
    documentos_conformes: list[str]
    encaminhamento: Encaminhamento
    observacoes: Optional[str] = None
    
    @computed_field
    @property
    def resultados(self) -> list[dict]:
        """Apenas itens para exibir na tabela (inconformidades e pendências)."""
        itens = []
        
        # Adicionar apenas inconformidades e pendências
        for item in self.inconformidades + self.pendencias:
            item_dict = item.model_dump()
            itens.append(item_dict)
        
        return itens
    
    @computed_field
    @property
    def contadores_display(self) -> dict:
        """Contadores para exibição no frontend."""
        return {
            'nOk': self.resumo.conformes,
            'nInc': self.resumo.inconformidades,
            'nPend': self.resumo.pendencias
        }
    
    @computed_field
    @property
    def contadores_tabela(self) -> dict:
        """Contadores corretos para exibição na tabela."""
        return {
            'conformes': self.resumo.conformes,
            'inconformidades': self.resumo.inconformidades,
            'pendencias': self.resumo.pendencias
        }


class RespostaProcessamento(BaseModel):
    """Resposta completa do endpoint principal."""
    processo_sei: str
    relatorio: RelatorioSaneamento
    documentos_identificados: list[str]
    paginas_processadas: int
    ocr_utilizado: bool
