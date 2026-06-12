"""Classificação e segmentação dos documentos dentro do PDF."""

from __future__ import annotations
import re
import unicodedata
import logging
from enum import Enum
from dataclasses import dataclass, field
from .extractor import PaginaExtraida, DocumentoExtraido

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de documentos reconhecidos
# ─────────────────────────────────────────────────────────────────────────────

class TipoDoc(str, Enum):
    DFD                   = "DFD"
    TR_SERVICOS           = "TR_SERVICOS"
    TR_AQUISICOES         = "TR_AQUISICOES"
    TABELA_PRECOS         = "TABELA_PRECOS"
    ORCAMENTO             = "ORCAMENTO"
    CARTAO_CNPJ           = "CARTAO_CNPJ"
    CONTRATO_SOCIAL       = "CONTRATO_SOCIAL"
    SICAF                 = "SICAF"
    CERTIDAO              = "CERTIDAO"
    COMPROVANTE_BANCARIO  = "COMPROVANTE_BANCARIO"
    DECLARACAO            = "DECLARACAO"
    EXECUTOR_ORCAMENTARIO = "EXECUTOR_ORCAMENTARIO"
    MEMORIA_CALCULO       = "MEMORIA_CALCULO"
    DEMONSTRATIVO_FIPLAN  = "DEMONSTRATIVO_FIPLAN"
    MANIFESTACAO_GESTOR   = "MANIFESTACAO_GESTOR"
    MANIFESTACAO_CIENCIA  = "MANIFESTACAO_CIENCIA"
    DESCONHECIDO          = "DESCONHECIDO"


# ─────────────────────────────────────────────────────────────────────────────
# Palavras-chave por documento (normalizadas, sem acentos)
#
# Princípios de robustez:
#  • Priorizar frases longas e exclusivas de cada modelo MPBA Jan/2026.
#  • Evitar termos de 1-2 palavras que aparecem em múltiplos documentos
#    (ex: "banco", "agencia", "valor total", "natureza da despesa").
#  • Listas de tamanho similar (~8-12 itens) para que o score proporcional
#    seja comparável entre tipos durante a competição de classificação.
#  • Cada tipo tem pelo menos 2 frases-âncora únicas, reforçadas por _REQUIRED.
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORDS: dict[TipoDoc, list[str]] = {

    # ── DFD ──────────────────────────────────────────────────────────────────
    TipoDoc.DFD: [
        "documento de formalizacao da demanda",
        "dfd",
        "objeto da futura contratacao",
        "tecnologia da informacao e comunicacao",
        "plano de contratacoes anuais",
        "unidade solicitante",
        "unidade gestora do recurso",
        "responsavel pelo preenchimento",
        "justificativa para escolha da forma nao eletronica",
        "superior imediato",
    ],

    # ── TR Serviços ───────────────────────────────────────────────────────────
    # Sem _REQUIRED para maximizar recall em OCR imperfeito.
    # Contém frases comuns a todo TR MPBA + frases exclusivas de serviços.
    TipoDoc.TR_SERVICOS: [
        "termo de referencia",
        "dispensa de licitacao",
        "objeto da contratacao",
        "justificativa da contratacao",
        "fundamentacao da contratacao",
        "habilitacao juridica",
        "qualificacao tecnica",
        # Exclusivos de serviços (modelo Jan/2026)
        "forma de execucao",
        "regime de execucao",
        "servicos continuados",
        "codigo de servicos",
        "local de execucao dos servicos",
        "prestacao dos servicos",
        "empreitada",
        "inicio dos servicos",
    ],

    # ── TR Aquisições ─────────────────────────────────────────────────────────
    # Sem _REQUIRED pelo mesmo motivo que TR_SERVICOS.
    TipoDoc.TR_AQUISICOES: [
        "termo de referencia",
        "dispensa de licitacao",
        "objeto da contratacao",
        "justificativa da contratacao",
        "fundamentacao da contratacao",
        "habilitacao juridica",
        "qualificacao tecnica",
        # Exclusivos de aquisições (modelo Jan/2026)
        "forma de fornecimento",
        "codigo de material",
        "catmat",
        "entrega dos bens",
        "local de entrega",
        "marca e modelo",
        "justificativa da quantidade",
        "apenso i",
    ],

    # ── Tabela de Preços Orçados ──────────────────────────────────────────────
    # Removidos: "metodologia", "valor unitario", "valor total" (presentes em TR e orçamento)
    TipoDoc.TABELA_PRECOS: [
        "tabela de precos orcados",
        "tabela de precos",                          # título sem "orçados" — variante válida
        "aviso previo publicado",
        "propostas recebidas",
        "motivacao para a escolha dos fornecedores",
        "responsavel pela pesquisa",
        "valor global da contratacao",
        "menor preco",
        "pesquisa de precos",
        "fornecedores consultados",
    ],

    # ── Orçamentos / Propostas ────────────────────────────────────────────────
    # Removidos: "dados bancarios" (presente em TR), "prazo de execucao" (presente em TR)
    TipoDoc.ORCAMENTO: [
        "modelo de proposta",
        "proposta comercial",
        "proposta de precos",          # título padrão das propostas MPBA
        "validade da proposta",
        "valor total da proposta",
        "razao social",
        "prazo de entrega",
        "orcamento",
        "cotacao de precos",
        "empresa proponente",
        "cnpj do proponente",
        "dados do fornecedor",         # seção padrão do modelo de proposta MPBA
    ],

    # ── Cartão CNPJ ───────────────────────────────────────────────────────────
    TipoDoc.CARTAO_CNPJ: [
        "cartao cnpj",
        "comprovante de inscricao e de situacao cadastral",
        "situacao cadastral",
        "cnae fiscal",
        "natureza juridica",
        "data de abertura da filial",
        "receita federal do brasil",
        "cadastro nacional da pessoa juridica",
    ],

    # ── Contrato / Estatuto Social ────────────────────────────────────────────
    TipoDoc.CONTRATO_SOCIAL: [
        "contrato social",
        "estatuto social",
        "inscricao no registro de empresas",
        "capital social",
        "socio administrador",
        "objeto social",
        "junta comercial",
        "registro civil das pessoas juridicas",
        "sociedade limitada",
        "sociedade empresaria",
    ],

    # ── SICAF ─────────────────────────────────────────────────────────────────
    TipoDoc.SICAF: [
        "sicaf",
        "sistema de cadastramento unificado de fornecedores",
        "nivel de cadastramento",
        "situacao do fornecedor no sicaf",
        "habilitacao parcial",
        "registro cadastral",
        "comprasnet",
    ],

    # ── Certidões ─────────────────────────────────────────────────────────────
    TipoDoc.CERTIDAO: [
        "certidao negativa de debitos",
        "certidao positiva com efeito de negativa",
        "certidao conjunta",
        "divida ativa da uniao",
        "regularidade fiscal",
        "fazenda estadual",
        "fazenda municipal",
        "debitos trabalhistas",
        "cndt",
        "certificado de regularidade do fgts",
        "crf",
    ],

    # ── Comprovante Bancário ──────────────────────────────────────────────────
    # Removidos: "banco" e "agencia" — presentes em qualquer TR ou orçamento
    TipoDoc.COMPROVANTE_BANCARIO: [
        "dados bancarios",
        "conta corrente",
        "comprovante de conta",
        "titular da conta",
        "comprovante bancario",
        "agencia bancaria",
        "numero da conta",
        "banco titular",
    ],

    # ── Declarações ───────────────────────────────────────────────────────────
    # Mantidos apenas termos que NÃO aparecem em outros documentos do processo
    TipoDoc.DECLARACAO: [
        "declaracao de nao emprego de menor",
        "nao emprega menor de dezoito anos",
        "nao emprega menor de idade",           # título alternativo do modelo MPBA
        "declaracao que nao emprega menor",     # variante de título
        "trabalho noturno perigoso ou insalubre",
        "nao emprega menor de dezesseis anos",
        "resolucao cnmp",
        "resolucao n 37",
        "nao ocupa cargo",
        "nao exerce funcao",
        "declaro para os devidos fins",
        "declaro sob as penas da lei",
    ],

    # ── Executor Orçamentário ─────────────────────────────────────────────────
    # Removido "natureza da despesa" — presente também em DEMONSTRATIVO_FIPLAN
    TipoDoc.EXECUTOR_ORCAMENTARIO: [
        "executor orcamentario",
        "informacoes orcamentarias",
        "dotacao orcamentaria",
        "impacto orcamentario financeiro",
        "percentual da dotacao",
        "fonte de recursos",
        "unidade orcamentaria",
        "exercicio financeiro",
    ],

    # ── Memória de Cálculo ────────────────────────────────────────────────────
    TipoDoc.MEMORIA_CALCULO: [
        "memoria de calculo",
        "limite legal de contratacao",
        "valor comprometido",
        "contratacoes anteriores no exercicio",
        "saldo disponivel para contratacao",
        "art 75 paragrafo 1",
        "teto de contratacao",
    ],

    # ── Demonstrativo FIPLAN ──────────────────────────────────────────────────
    # Removidos: "natureza da despesa", "saldo disponivel" — sobreposição com EXECUTOR
    # "plan60" e "demonstrativo de execucao da despesa" adicionados: o MPBA emite
    # o demonstrativo via sistema PLAN60 e o título real é "Plan60 - Demonstrativo
    # de Execução da Despesa - DED", não "Demonstrativo de Disponibilidade Orçamentária".
    TipoDoc.DEMONSTRATIVO_FIPLAN: [
        "fiplan",
        "plan60",                                   # sistema MPBA
        "demonstrativo de execucao da despesa",     # título real do relatório
        "ded",                                      # sigla do relatório Plan60
        "demonstrativo de disponibilidade orcamentaria",
        "programacao orcamentaria",
        "sistema de administracao financeira",
        "disponibilidade orcamentaria",
        "saldo orcamentario",
        "consulta orcamentaria",
        "unidade gestora fiplan",
    ],

    # ── Manifestação do Gestor Orçamentário ───────────────────────────────────
    # Removidos: "executor orcamentario" (conflito com tipo homônimo),
    #            "valor global da contratacao" (presente em TABELA_PRECOS)
    TipoDoc.MANIFESTACAO_GESTOR: [
        "manifestacao do gestor",
        "gestor orcamentario",
        "codigo pdm",
        "codigo de servicos",
        "fiscal administrativo",
        "fiscal tecnico",
        "designacao do fiscal",
        "nomeacao do fiscal",
        "portaria de designacao",
    ],

    # ── Manifestação de Ciência ───────────────────────────────────────────────
    # "fiscal do contrato"/"gestor do contrato" podem aparecer em TR — protegidos por _REQUIRED
    TipoDoc.MANIFESTACAO_CIENCIA: [
        "manifestacao de ciencia",
        "declaro estar ciente",
        "fiscal do contrato",
        "gestor do contrato",
        "ciente das obrigacoes",
        "ciencia e concordancia",
        "declaro ciencia",
        "termo de ciencia",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Limiares de classificação
#
# _LIMIAR_CONFIANCA = 0.10: permite classificar com 1 keyword em listas de até
# 10 itens (1/10 = 0.10). Necessário para OCR imperfeito onde apenas frases
# simples como "termo de referencia" são reconhecidas com precisão.
# _MIN_HITS = 1: um único hit já é suficiente desde que passe no limiar E no
# _REQUIRED, que garante que esse hit seja uma frase-âncora do documento.
# ─────────────────────────────────────────────────────────────────────────────

_LIMIAR_CONFIANCA = 0.10
# Limiar reduzido para tipos cujo _REQUIRED já foi satisfeito.
# O REQUIRED é a "âncora forte" — encontrá-la já é evidência robusta do tipo;
# o score adicional de keywords funciona apenas como desempate.
_LIMIAR_COM_REQUIRED = 0.07
_MIN_HITS = 1


# ─────────────────────────────────────────────────────────────────────────────
# Keywords obrigatórias (_REQUIRED)
#
# Uma página só pode ser classificada como um determinado tipo se ao menos UMA
# das frases listadas aqui estiver presente no texto normalizado.
#
# Objetivo: bloquear classificações espúrias causadas por termos genéricos
# que aparecem em múltiplos documentos (ex: "banco", "agencia", "valor total").
# TR_SERVICOS e TR_AQUISICOES ficam propositalmente SEM _REQUIRED para maximizar
# recall em PDFs com OCR de baixa qualidade — a competição de score ainda os
# discrimina corretamente quando outros tipos têm _REQUIRED.
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Bloqueadores (_BLOCKERS)
#
# Se QUALQUER uma dessas frases estiver presente no texto, a página NÃO pode
# ser classificada como esse tipo — mesmo que tenha muitos hits de keywords.
#
# Problema resolvido: TR lista certidões exigidas na seção de habilitação
# (ex: "Certidão Negativa de Débitos"), satisfazendo o _REQUIRED do CERTIDAO.
# Solução: se "termo de referencia" está no cabeçalho da página, ela é TR —
# nenhum outro tipo pode vencer.
# ─────────────────────────────────────────────────────────────────────────────

_BLOCKERS: dict[TipoDoc, list[str]] = {
    # Certidão real nunca traz "Termo de Referência" nem "Dispensa de Licitação"
    TipoDoc.CERTIDAO: [
        "termo de referencia",
        "dispensa de licitacao",
    ],
    # Demais documentos da empresa/empresa também não teriam cabeçalho de TR
    TipoDoc.CARTAO_CNPJ: [
        "termo de referencia",
        "dispensa de licitacao",
    ],
    TipoDoc.CONTRATO_SOCIAL: [
        "termo de referencia",
        "dispensa de licitacao",
    ],
    TipoDoc.SICAF: [
        "termo de referencia",
        "dispensa de licitacao",
    ],
    TipoDoc.COMPROVANTE_BANCARIO: [
        "termo de referencia",
        "dispensa de licitacao",
    ],
    TipoDoc.DECLARACAO: [
        # Declarações mencionam "dispensa de licitação" no próprio corpo do texto
        # (ex: "para fins de habilitação na Dispensa de Licitação nº XX/XXXX").
        # Manter apenas "termo de referencia" como bloqueador.
        "termo de referencia",
    ],
    # Tabela de Preços: com _REQUIRED exclusivo ("tabela de precos orcados" /
    # "tabela de precos", "motivacao para a escolha dos fornecedores", etc.) não
    # é necessário manter "termo de referencia" como bloqueador — o próprio texto
    # da tabela pode referenciar o TR no corpo sem ser um TR.
    TipoDoc.TABELA_PRECOS: [],
    TipoDoc.EXECUTOR_ORCAMENTARIO: [
        "termo de referencia",
    ],
    TipoDoc.MEMORIA_CALCULO: [
        "termo de referencia",
    ],
    TipoDoc.DEMONSTRATIVO_FIPLAN: [
        "termo de referencia",
    ],
    TipoDoc.MANIFESTACAO_GESTOR: [
        "termo de referencia",
    ],
    TipoDoc.MANIFESTACAO_CIENCIA: [
        "termo de referencia",
    ],
    # ORCAMENTO não deve ser classificado quando o documento é um TR
    TipoDoc.ORCAMENTO: [
        "termo de referencia",
        "dispensa de licitacao",
    ],
}

_REQUIRED: dict[TipoDoc, list[str]] = {

    TipoDoc.DFD: [
        "documento de formalizacao da demanda",
        "dfd",
    ],

    TipoDoc.TABELA_PRECOS: [
        # "pesquisa de precos" e "fornecedores consultados" aparecem também na
        # seção 2.1 do TR — manter apenas âncoras exclusivas da tabela.
        "tabela de precos orcados",
        "tabela de precos",                          # variante sem "orçados"
        "motivacao para a escolha dos fornecedores",
        "aviso previo publicado",
        "responsavel pela pesquisa",
    ],

    TipoDoc.ORCAMENTO: [
        "proposta comercial",
        "modelo de proposta",
        "proposta de precos",          # título padrão das propostas MPBA
        "validade da proposta",
        "cotacao de precos",
        "valor total da proposta",
        "empresa proponente",
        "dados do fornecedor",         # seção padrão do modelo de proposta MPBA
    ],

    TipoDoc.CARTAO_CNPJ: [
        "comprovante de inscricao e de situacao cadastral",
        "cnae fiscal",
        "cadastro nacional da pessoa juridica",
    ],

    TipoDoc.CONTRATO_SOCIAL: [
        "contrato social",
        "estatuto social",
        "junta comercial",
        "registro civil das pessoas juridicas",
        "sociedade limitada",
        "sociedade empresaria",
    ],

    TipoDoc.SICAF: [
        "sicaf",
        "sistema de cadastramento unificado de fornecedores",
        "situacao do fornecedor no sicaf",
    ],

    TipoDoc.CERTIDAO: [
        # "regularidade fiscal" removida do _REQUIRED: aparece na seção de
        # habilitação de qualquer TR e causava falso-positivo nas suas páginas.
        "certidao negativa de debitos",
        "certidao positiva com efeito de negativa",
        "certidao conjunta",
        "certificado de regularidade do fgts",
        "cndt",
        "divida ativa da uniao",
    ],

    TipoDoc.COMPROVANTE_BANCARIO: [
        "comprovante de conta",
        "titular da conta",
        "comprovante bancario",
        "banco titular",
    ],

    TipoDoc.DECLARACAO: [
        "declaracao de nao emprego de menor",
        "nao emprega menor de dezoito anos",
        "nao emprega menor de idade",           # título alternativo do modelo MPBA
        "declaracao que nao emprega menor",     # variante de título
        "resolucao cnmp",
        "resolucao n 37",
        "declaro para os devidos fins",
        "declaro sob as penas da lei",
    ],

    TipoDoc.EXECUTOR_ORCAMENTARIO: [
        "executor orcamentario",
        "impacto orcamentario financeiro",
        "dotacao orcamentaria",
    ],

    TipoDoc.MEMORIA_CALCULO: [
        "memoria de calculo",
        "limite legal de contratacao",
        "contratacoes anteriores no exercicio",
        "teto de contratacao",
    ],

    TipoDoc.DEMONSTRATIVO_FIPLAN: [
        "fiplan",
        "plan60",                                    # sistema MPBA – âncora estável
        "demonstrativo de execucao da despesa",      # título real do relatório MPBA
        "demonstrativo de disponibilidade orcamentaria",
        "sistema de administracao financeira",
        "unidade gestora fiplan",
    ],

    TipoDoc.MANIFESTACAO_GESTOR: [
        "manifestacao do gestor",
        "gestor orcamentario",
        "designacao do fiscal",
        "nomeacao do fiscal",
    ],

    TipoDoc.MANIFESTACAO_CIENCIA: [
        "manifestacao de ciencia",
        "declaro estar ciente",
        "ciencia e concordancia",
        "ciente das obrigacoes",
        "declaro ciencia",
        "termo de ciencia",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Normalização
# ─────────────────────────────────────────────────────────────────────────────

def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove pontuação e colapsa todo whitespace (incluindo \n) para espaço único.
    # Essencial para que frases-âncora como "certificado de regularidade do fgts"
    # batam mesmo quando o título OCR é quebrado em linhas.
    cleaned = re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Classificação de uma página
# ─────────────────────────────────────────────────────────────────────────────

def classificar_pagina(texto: str) -> tuple[TipoDoc, float]:
    """Retorna (tipo, score 0-1) para a página.

    Algoritmo:
    1. Para cada tipo, conta hits de keywords no texto normalizado.
    2. Tipos com _REQUIRED onde nenhuma frase obrigatória está presente recebem score 0.
    3. O tipo com maior score proporcional vence, desde que supere _LIMIAR_CONFIANCA e _MIN_HITS.
    """
    texto_n = _norm(texto)
    scores: dict[TipoDoc, float] = {}
    hits_count: dict[TipoDoc, int] = {}

    for tipo, kws in _KEYWORDS.items():
        # 1) Bloqueia tipos com frase incompatível presente na página
        blockers = _BLOCKERS.get(tipo)
        if blockers and any(b in texto_n for b in blockers):
            scores[tipo] = 0.0
            hits_count[tipo] = 0
            continue

        # 2) Bloqueia tipos sem keyword âncora obrigatória
        required = _REQUIRED.get(tipo)
        if required and not any(r in texto_n for r in required):
            scores[tipo] = 0.0
            hits_count[tipo] = 0
            continue

        hits = sum(1 for kw in kws if kw in texto_n)
        scores[tipo] = hits / len(kws)
        hits_count[tipo] = hits

    melhor = max(scores, key=scores.get)  # type: ignore[arg-type]

    # Usa limiar reduzido quando o tipo vencedor já satisfez o seu _REQUIRED:
    # a presença de uma âncora obrigatória é evidência forte — o score mínimo
    # adicional só serve como desempate entre tipos igualmente plausíveis.
    req_melhor = _REQUIRED.get(melhor)
    tem_required = bool(req_melhor and any(r in texto_n for r in req_melhor))
    limiar = _LIMIAR_COM_REQUIRED if tem_required else _LIMIAR_CONFIANCA

    if scores[melhor] < limiar or hits_count[melhor] < _MIN_HITS:
        top3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        log.debug("Página DESCONHECIDO – top scores: %s", top3)
        return TipoDoc.DESCONHECIDO, 0.0

    log.debug("Página classificada como %s (score=%.3f, hits=%d)",
              melhor, scores[melhor], hits_count[melhor])
    return melhor, round(scores[melhor], 3)


# ─────────────────────────────────────────────────────────────────────────────
# Segmentação do PDF em documentos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SegmentoPaginas:
    tipo: TipoDoc
    paginas: list[int] = field(default_factory=list)
    textos: list[str] = field(default_factory=list)
    confianca_media: float = 0.0

    @property
    def texto_completo(self) -> str:
        return "\n".join(self.textos)


def segmentar_pdf(paginas: list[PaginaExtraida]) -> list[DocumentoExtraido]:
    """Classifica cada página e agrupa em segmentos contíguos do mesmo tipo."""
    classificacoes: list[tuple[TipoDoc, float]] = [
        classificar_pagina(p.texto) for p in paginas
    ]

    # Agrupar páginas consecutivas do mesmo tipo
    segmentos: list[SegmentoPaginas] = []
    atual: SegmentoPaginas | None = None

    for i, (tipo, score) in enumerate(classificacoes):
        pagina = paginas[i]
        if atual is None or tipo != atual.tipo:
            if atual is not None:
                segmentos.append(atual)
            atual = SegmentoPaginas(tipo=tipo)
        atual.paginas.append(pagina.numero)
        atual.textos.append(pagina.texto)
        atual.confianca_media = (
            (atual.confianca_media * (len(atual.paginas) - 1) + score)
            / len(atual.paginas)
        )

    if atual is not None:
        segmentos.append(atual)

    # Fundir segmentos TR adjacentes: SERVIÇOS e AQUISIÇÕES classificados
    # individualmente por página pertencem ao mesmo documento no processo.
    segmentos = _fundir_segmentos_tr(segmentos)

    # TR: diferenciar SERVIÇOS de AQUISIÇÕES dentro dos segmentos TR (já fundidos)
    for seg in segmentos:
        if seg.tipo in (TipoDoc.TR_SERVICOS, TipoDoc.TR_AQUISICOES):
            seg.tipo = _refinar_tipo_tr(seg.texto_completo)

    # Converter para DocumentoExtraido — inclui DESCONHECIDO para que o
    # fallback de IA possa tentar reclassificá-los antes de descartá-los.
    documentos = [
        DocumentoExtraido(
            tipo=seg.tipo.value,
            paginas=seg.paginas,
            texto_completo=seg.texto_completo,
            confianca=seg.confianca_media,
            textos_paginas=seg.textos,
        )
        for seg in segmentos
    ]

    conhecidos = [(d.tipo, len(d.paginas)) for d in documentos if d.tipo != "DESCONHECIDO"]
    n_desconhecidos = sum(1 for d in documentos if d.tipo == "DESCONHECIDO")
    log.info("Documentos identificados: %s | DESCONHECIDO: %d bloco(s)", conhecidos, n_desconhecidos)
    return documentos


def absorver_desconhecidos(segmentos: list[DocumentoExtraido]) -> list[DocumentoExtraido]:
    """Absorve segmentos DESCONHECIDO nos segmentos conhecidos adjacentes.

    Garante que nenhuma página seja descartada: blocos não identificados são
    mesclados no segmento anterior (ou posterior, se não houver anterior).
    Isso preserva o texto de páginas com tabelas puras, assinaturas digitais,
    separadores do SEI etc. que não contêm keywords de classificação.
    """
    if not segmentos:
        return segmentos

    resultado: list[DocumentoExtraido] = []
    pendentes: list[DocumentoExtraido] = []  # DESCONHECIDOs aguardando destino

    for seg in segmentos:
        if seg.tipo == "DESCONHECIDO":
            pendentes.append(seg)
        else:
            if pendentes:
                if resultado:
                    # Absorve no segmento anterior (continuação mais provável)
                    alvo = resultado[-1]
                    for p in pendentes:
                        alvo.paginas.extend(p.paginas)
                        alvo.textos_paginas.extend(p.textos_paginas)
                        alvo.texto_completo += "\n" + p.texto_completo
                        log.info(
                            "DESCONHECIDO págs %s → absorvido em '%s' (anterior)",
                            p.paginas, alvo.tipo,
                        )
                else:
                    # Sem segmento anterior: absorve no segmento atual (posterior)
                    for p in pendentes:
                        seg.paginas = p.paginas + seg.paginas
                        seg.textos_paginas = p.textos_paginas + seg.textos_paginas
                        seg.texto_completo = p.texto_completo + "\n" + seg.texto_completo
                        log.info(
                            "DESCONHECIDO págs %s → absorvido em '%s' (posterior)",
                            p.paginas, seg.tipo,
                        )
                pendentes = []
            resultado.append(seg)

    # DESCONHECIDOs no final do PDF → absorve no último segmento conhecido
    if pendentes and resultado:
        alvo = resultado[-1]
        for p in pendentes:
            alvo.paginas.extend(p.paginas)
            alvo.textos_paginas.extend(p.textos_paginas)
            alvo.texto_completo += "\n" + p.texto_completo
            log.info(
                "DESCONHECIDO págs %s → absorvido em '%s' (último)",
                p.paginas, alvo.tipo,
            )
    elif pendentes:
        # PDF inteiramente DESCONHECIDO — mantém sem absorção
        resultado.extend(pendentes)

    return resultado


_TR_TIPOS = {TipoDoc.TR_SERVICOS, TipoDoc.TR_AQUISICOES}


def _fundir_segmentos_tr(segmentos: list[SegmentoPaginas]) -> list[SegmentoPaginas]:
    """Funde segmentos TR_SERVICOS/TR_AQUISICOES adjacentes em um único bloco.

    Um processo de DL contém no máximo um TR (seja de serviços ou aquisições).
    Quando o classificador por página oscila entre os dois sub-tipos ao longo
    do documento, segmentos contíguos de TR devem ser tratados como um único
    documento antes de determinar o tipo definitivo pelo texto completo.
    """
    resultado: list[SegmentoPaginas] = []
    i = 0
    while i < len(segmentos):
        seg = segmentos[i]
        if seg.tipo not in _TR_TIPOS:
            resultado.append(seg)
            i += 1
            continue

        # Coleta todos os segmentos TR contíguos
        j = i + 1
        while j < len(segmentos) and segmentos[j].tipo in _TR_TIPOS:
            j += 1

        if j == i + 1:
            # Segmento TR isolado — sem fusão necessária
            resultado.append(seg)
        else:
            # Funde i..j-1
            paginas_todas: list[int] = []
            textos_todos: list[str] = []
            soma_conf = 0.0
            total_pags = 0
            for k in range(i, j):
                paginas_todas.extend(segmentos[k].paginas)
                textos_todos.extend(segmentos[k].textos)
                n = len(segmentos[k].paginas)
                soma_conf += segmentos[k].confianca_media * n
                total_pags += n
            fundido = SegmentoPaginas(
                tipo=seg.tipo,  # tipo provisório; será refinado a seguir
                paginas=paginas_todas,
                textos=textos_todos,
                confianca_media=soma_conf / total_pags,
            )
            resultado.append(fundido)
            log.info(
                "TR fundido: %d segmentos → 1 bloco com páginas %s",
                j - i, paginas_todas,
            )
        i = j
    return resultado


def _refinar_tipo_tr(texto: str) -> TipoDoc:
    """Diferencia TR Serviços de TR Aquisições pelo conteúdo.

    Usa marcadores exclusivos de cada tipo antes de recorrer ao score geral,
    conforme estrutura dos modelos MPBA Jan/2026.
    """
    n = _norm(texto)

    _MARKERS_AQUISICOES = [
        "forma de fornecimento",
        "local de entrega",
        "entrega dos bens",
        "catmat",
        "codigo de material",
        "marca e modelo",
        "justificativa da quantidade",
        # "apenso i" removido: obrigatório em ambos os tipos de TR (modelo MPBA Jan/2026)
    ]
    _MARKERS_SERVICOS = [
        "forma de execucao",
        "regime de execucao",
        "local de execucao",
        "servicos continuados",
        "codigo de servicos",
        "empreitada",
        "inicio dos servicos",
    ]

    hits_aq   = sum(1 for m in _MARKERS_AQUISICOES if m in n)
    hits_serv = sum(1 for m in _MARKERS_SERVICOS if m in n)

    if hits_aq > hits_serv:
        return TipoDoc.TR_AQUISICOES
    if hits_serv > hits_aq:
        return TipoDoc.TR_SERVICOS

    # Empate: fallback para score geral de keywords
    score_serv = sum(1 for kw in _KEYWORDS[TipoDoc.TR_SERVICOS] if kw in n)
    score_aq   = sum(1 for kw in _KEYWORDS[TipoDoc.TR_AQUISICOES] if kw in n)
    if score_aq > score_serv:
        return TipoDoc.TR_AQUISICOES
    return TipoDoc.TR_SERVICOS
