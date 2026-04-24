"""Processamento paralelo de PDF para otimização de performance."""

import asyncio
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from pdf.extractor import extrair_paginas

log = logging.getLogger(__name__)


@dataclass
class PageProcessingResult:
    """Resultado do processamento de uma página."""
    pagina_num: int
    segmentos: List[Any]
    tem_texto: bool
    via_ocr: bool
    processing_time: float


def should_skip_ocr(texto: str, min_length: int = 100) -> bool:
    """Verifica se OCR deve ser pulado baseado no texto existente."""
    return len(texto.strip()) >= min_length


def process_page_parallel(page_data: Any, page_num: int, ocr_enabled: bool) -> PageProcessingResult:
    """Processa uma única página em paralelo (sem cache para evitar erros de importação)."""
    import time
    start_time = time.time()
    
    try:
        # Verificar se página já tem texto extraído
        texto = getattr(page_data, 'texto', '')
        via_ocr = getattr(page_data, 'via_ocr', False)
        
        # Segmentar a página - usar API existente
        from api.saneamento import segmentar_pdf
        segmentos = segmentar_pdf([page_data])
        
        processing_time = time.time() - start_time
        
        return PageProcessingResult(
            pagina_num=page_num,
            segmentos=segmentos,
            tem_texto=bool(texto and texto.strip()),
            via_ocr=via_ocr,
            processing_time=processing_time
        )
        
    except Exception as e:
        log.error(f"Erro processando página {page_num}: {e}")
        return PageProcessingResult(
            pagina_num=page_num,
            segmentos=[],
            tem_texto=False,
            via_ocr=False,
            processing_time=time.time() - start_time
        )


async def process_pages_parallel(
    paginas: List[Any], 
    ocr_enabled: bool = True,
    max_workers: int = 8
) -> List[PageProcessingResult]:
    """Processa múltiplas páginas em paralelo."""
    
    if not paginas:
        return []
    
    log.info(f"Iniciando processamento paralelo de {len(paginas)} páginas com {max_workers} workers")
    
    # Usar ThreadPoolExecutor para processamento CPU-bound
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Criar tarefas para cada página
        futures = [
            executor.submit(process_page_parallel, page, i, ocr_enabled)
            for i, page in enumerate(paginas)
        ]
        
        # Coletar resultados na ordem de conclusão
        results = []
        for future in as_completed(futures):
            try:
                result = future.result(timeout=30)  # Timeout de 30s por página
                results.append(result)
            except Exception as e:
                log.error(f"Erro no processamento paralelo: {e}")
                # Adicionar resultado vazio para manter ordem
                results.append(PageProcessingResult(
                    pagina_num=len(results),
                    segmentos=[],
                    tem_texto=False,
                    via_ocr=False,
                    processing_time=0
                ))
    
    # Ordenar resultados por número da página
    results.sort(key=lambda x: x.pagina_num)
    
    total_time = sum(r.processing_time for r in results)
    log.info(f"Processamento paralelo concluído em {total_time:.2f}s")
    
    return results


def merge_segment_results(results: List[PageProcessingResult]) -> List[Any]:
    """Mescla os resultados de segmentação de todas as páginas."""
    todos_segmentos = []
    
    for result in results:
        if result.segmentos:
            todos_segmentos.extend(result.segmentos)
    
    log.info(f"Mesclados {len(todos_segmentos)} segmentos de {len(results)} páginas")
    return todos_segmentos


def get_processing_stats(results: List[PageProcessingResult]) -> Dict[str, Any]:
    """Retorna estatísticas do processamento."""
    if not results:
        return {}
    
    total_pages = len(results)
    pages_with_text = sum(1 for r in results if r.tem_texto)
    pages_ocr = sum(1 for r in results if r.via_ocr)
    total_time = sum(r.processing_time for r in results)
    avg_time = total_time / total_pages if total_pages > 0 else 0
    
    return {
        "total_pages": total_pages,
        "pages_with_text": pages_with_text,
        "pages_ocr": pages_ocr,
        "total_processing_time": total_time,
        "average_time_per_page": avg_time,
        "parallel_efficiency": total_time / (avg_time * total_pages) if avg_time > 0 else 1.0
    }
