"""Processamento paralelo de IA e saneamento para otimização real de performance."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class AIProcessingResult:
    """Resultado do processamento de IA."""
    segmentos_classificados: List[Any]
    processing_time: float


@dataclass 
class SaneamentoResult:
    """Resultado do saneamento."""
    relatorio: Any
    processing_time: float


def process_ai_classification_parallel(segmentos: List[Any], batch_size: int = 10) -> AIProcessingResult:
    """Processa classificação IA em batches paralelos (sem cache para evitar erros de importação)."""
    import time
    start_time = time.time()
    
    try:
        # Se poucos segmentos, processa sequencialmente
        if len(segmentos) <= batch_size:
            from pdf.ai_classifier import reclassificar_desconhecidos_com_ia
            segmentos_classificados = reclassificar_desconhecidos_com_ia(segmentos)
        else:
            # Divide em batches para processamento paralelo
            from pdf.ai_classifier import reclassificar_desconhecidos_com_ia
            
            # Processar batches em paralelo
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = []
                for i in range(0, len(segmentos), batch_size):
                    batch = segmentos[i:i + batch_size]
                    future = executor.submit(reclassificar_desconhecidos_com_ia, batch)
                    futures.append(future)
                
                # Coletar resultados
                all_classificados = []
                for future in as_completed(futures):
                    try:
                        batch_result = future.result(timeout=120)
                        all_classificados.extend(batch_result)
                    except Exception as e:
                        log.error(f"Erro no batch de IA: {e}")
                        all_classificados.extend(segmentos[i:i + batch_size])
                
                segmentos_classificados = all_classificados
        
        processing_time = time.time() - start_time
        log.info(f"Classificação IA concluída em {processing_time:.2f}s")
        
        return AIProcessingResult(
            segmentos_classificados=segmentos_classificados,
            processing_time=processing_time
        )
        
    except Exception as e:
        log.error(f"Erro na classificação IA paralela: {e}")
        return AIProcessingResult(
            segmentos_classificados=segmentos,
            processing_time=time.time() - start_time
        )


def process_saneamento_parallel(processo: Any) -> SaneamentoResult:
    """Processa saneamento em paralelo se possível."""
    import time
    start_time = time.time()
    
    try:
        # Para otimizar, poderíamos paralelizar regras independentes
        # Por enquanto, mantém sequencial mas com logging melhor
        from rules.saneamento_engine import executar_saneamento_async
        
        # Executar saneamento (já é async)
        relatorio = asyncio.run(executar_saneamento_async(processo))
        
        processing_time = time.time() - start_time
        log.info(f"Saneamento concluído em {processing_time:.2f}s")
        
        return SaneamentoResult(
            relatorio=relatorio,
            processing_time=processing_time
        )
        
    except Exception as e:
        log.error(f"Erro no saneamento: {e}")
        return SaneamentoResult(
            relatorio=None,
            processing_time=time.time() - start_time
        )


async def optimize_pipeline_parallel(segmentos: List[Any], processo: Any) -> tuple:
    """Otimiza o pipeline final com paralelização onde possível."""
    
    log.info("Iniciando pipeline otimizado paralelo")
    
    # Processar classificação IA em paralelo
    ai_task = asyncio.to_thread(
        process_ai_classification_parallel, segmentos, batch_size=15
    )
    
    # Executar ambas tarefas
    ai_result = await ai_task
    
    # Continuar com absorção de desconhecidos
    from pdf.classifier import absorver_desconhecidos
    segmentos_filtrados = absorver_desconhecidos(ai_result.segmentos_classificados)
    segmentos_finais = [s for s in segmentos_filtrados if s.tipo != "DESCONHECIDO"]
    
    # Atualizar processo com segmentos finais
    processo.segmentos = segmentos_finais
    
    # Processar saneamento
    from rules.saneamento_engine import executar_saneamento_async
    relatorio = await executar_saneamento_async(processo)
    
    return segmentos_finais, relatorio, {
        "ai_processing_time": ai_result.processing_time,
        "total_segmentos": len(segmentos),
        "segmentos_classificados": len(ai_result.segmentos_classificados),
        "segmentos_finais": len(segmentos_finais)
    }


def get_optimization_stats(ai_time: float, total_time: float) -> Dict[str, Any]:
    """Retorna estatísticas da otimização."""
    return {
        "ai_processing_time": ai_time,
        "total_processing_time": total_time,
        "ai_efficiency": (ai_time / total_time) * 100 if total_time > 0 else 0,
        "optimization_applied": "parallel_ai_classification"
    }
