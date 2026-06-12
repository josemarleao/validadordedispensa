"""Regras assistidas por IA – análise de conteúdo complementar às regras determinísticas.
# Inclui double-check: IA confirma ou descarta cada INCONFORME/PENDÊNCIA gerada pelas regras.

Estratégia:
  - Uma chamada por documento analisa TODOS os aspectos que a regex não consegue avaliar:
    (a) campos estruturais (checkboxes, opções) não extraídos pelo OCR
    (b) aspectos qualitativos (adequação, substância, coerência)
  - Os itens retornados pela IA com nome EXATO igual a um item determinístico substituem
    esse item na lista final (PENDÊNCIA → CONFORME/INCONFORME via IA).

Documentos cobertos:
  - DFD
  - TR Serviços
  - TR Aquisições
  - Tabela de Preços Orçados
  - Orçamentos / Propostas
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import date
from typing import TypeVar
from domain.processo import ProcessoExtraido
from domain.tr_unificado import TRServicosExtraido, TRAquisicoesExtraido
from schemas.responses import ResultadoItem, StatusRegra, Providencia
from .base import ok, inconforme, pendencia, normalizar_rotulo_regra
from ai.analyzer import analisar

log = logging.getLogger(__name__)



_DOC_DFD    = "DFD"
_DOC_TR     = "Termo de Referência"
_DOC_PRECOS = "Tabela de Preços Orçados"
_DOC_ORC    = "Orçamentos / Propostas"

_MORA_MAX  = 0.5
_INEX_MAX  = 30.0
_DOUBLE_CHECK_MAX_ITENS_POR_LOTE = 4
_DOUBLE_CHECK_MAX_CARACTERES_BLOCO = 5500
_DOUBLE_CHECK_CLASSIFICACOES_PRESENTE = {
    "PRESENTE_EQUIVALENTE",
    "PRESENTE_VARIACAO_FORMA",
}
T = TypeVar("T")

_DOUBLE_CHECK_TERMOS: dict[str, dict[str, list[str]]] = {
    _DOC_TR: {
        "1.1 – Objeto": ["objeto", "descrição do objeto", "objeto da contratação", "especificação do objeto"],
        "Fundamentação": ["fundamentação", "justificativa", "motivação da contratação", "razão da contratação"],
        "2.1.1 – Base Legal": ["base legal", "lei 14.133", "lei nº 14.133", "art. 75"],
        "2.1.1 – Artigo": ["art. 75", "inciso i", "inciso ii", "base legal"],
        "2.1.1 – Artigo/Inciso": ["art. 75", "inciso i", "inciso ii", "fundamento legal"],
        "2.1.2 – Divulgação": ["portal mpba", "divulgação", "aviso prévio", "publicação", "e-mail", "telefone", "@mpba.mp.br"],
        "2.1.2 – Divulgação Opção B": ["portal mpba", "publicar", "divulgação", "opção b", "e-mail", "@mpba.mp.br", "telefone", "prazo"],
        "2.2.1 – Hab. Jurídica": ["habilitação jurídica", "documentação jurídica"],
        "2.2.2 – Fiscal/Social/Trabalhista": ["regularidade fiscal", "certidão federal", "certidão estadual", "cndt", "fgts"],
        "Apenso I – Planilha de Itens": ["apenso i", "planilha de itens", "planilha de serviços", "quantidade", "valor estimado"],
        "1.6/1.7 – Formalização": ["formalização", "nota de empenho", "instrumento substitutivo", "contrato", "ata de registro"],
        "Responsável / Assinatura": ["responsável", "elaboração", "assinatura", "cargo"],
        "1.3 – Natureza do Objeto": ["natureza do objeto", "serviço continuado", "serviço parcelado", "execução imediata"],
        "1.4 – Natureza do Objeto": ["natureza do objeto", "fornecimento imediato", "fornecimento parcelado", "fornecimento continuado"],
        "3.1 – Regime de Execução": ["regime de execução", "preço global", "preço unitário"],
        "3.4 – Prazo de Execução": ["prazo de execução", "prazo para execução", "cronograma"],
        "3.5 – Garantia do Serviço": ["garantia do serviço", "garantia legal", "garantia contratada"],
        "3.6 – Subcontratação": ["subcontratação", "vedada", "admitida"],
        "3.7 – Subcontratação": ["subcontratação", "vedada", "admitida"],
        "3.6.1 – Garantia do Produto": ["garantia do produto", "garantia legal", "cdc", "apenso ii"],
        "3.13 – Vigência da Contratação": ["vigência da contratação", "vigência", "prazo de vigência"],
        "3.14 – Vigência da Contratação": ["vigência da contratação", "vigência", "prazo de vigência"],
        "3.16 – Garantia Contratual": ["garantia contratual", "seguro garantia", "caução", "performance bond"],
        "3.7.4 – Multas": ["multa", "mora", "inexecução total", "penalidade"],
        "3.9.4 – Multas": ["multa", "mora", "inexecução total", "penalidade"],
        # TR Serviços – análise abrangente (Jan/2026)
        "1.1 – Indicação do Objeto": ["objeto", "indicação do objeto", "sistema de registro de preços", "apenso i"],
        "1.2 – Justificativa do Quantitativo Definido": ["quantitativo", "quantidade", "justificativa do quantitativo"],
        "1.3 – Natureza do Objeto": ["natureza do objeto", "serviço continuado", "parcelado", "imediato", "pontual", "por escopo"],
        "1.4 – Fundamentação da Contratação": ["fundamentação", "justificativa", "motivação", "necessidade"],
        "1.5 – Descrição da Solução como um Todo": ["solução", "descrição da solução"],
        "1.6 – Formalização da Contratação": ["formalização", "nota de empenho", "instrumento substitutivo", "ata de registro", "contrato formal"],
        "2.1 – Fundamentação Legal (Forma de Seleção)": ["base legal", "art. 75", "dispensa", "inciso", "eletrônica", "tradicional", "b.1", "b.2"],
        "2.2.1 – Habilitação Jurídica": ["habilitação jurídica", "pessoa jurídica", "pessoa física"],
        "2.2.2 – Habilitação Fiscal, Social e Trabalhista": ["regularidade fiscal", "certidão federal", "cndt", "fgts", "trabalhista"],
        "2.2.3 – Habilitação Técnica": ["habilitação técnica", "atestado", "certidão técnica", "visita", "vistoria", "inscrição"],
        "2.2.4 – Habilitação Econômico-Financeira": ["habilitação econômico", "balanço", "capital social", "patrimônio"],
        "3.1 – Regime de Execução": ["regime de execução", "preço global", "preço unitário"],
        "3.2 – Prazo para Retirada da Nota de Empenho": ["nota de empenho", "prazo para retirada", "3.2.1"],
        "3.3 – Forma de Execução": ["local de execução", "agendamento", "dias e horários", "endereço", "cep"],
        "3.4 – Prazo(s) de Execução": ["prazo de execução", "prazo para execução", "cronograma", "prorrogação do prazo"],
        "3.5 – Regras de Garantia": ["garantia do serviço", "garantia legal", "garantia contratada", "chamado", "atendimento"],
        "3.6 – Possibilidade ou Não de Subcontratação": ["subcontratação", "vedada", "admitida", "subcontratar"],
        "3.7 – Modelo de Gestão e Fiscalização Contratual": ["fiscalização", "gestão contratual", "multa", "mora", "inexecução", "penalidade", "3.7.4"],
        "3.8 – Condições de Recebimento do Objeto": ["recebimento provisório", "recebimento definitivo", "3.8.1", "3.8.2"],
        "3.9 – Dos Preços": ["preços", "valor mensal", "valor unitário", "valor global", "custos", "encargos"],
        "3.10 – Regras de Faturamento": ["faturamento", "nota fiscal", "periodicidade", "parcela", "mensal"],
        "3.11 – Regras para Pagamento e Atualização Monetária": ["pagamento", "atualização monetária", "3.11"],
        "3.12 – Reajustamento": ["reajustamento", "reajuste", "inpc", "índice", "correção"],
        "3.13.1 – Vigência da ARP": ["ata de registro de preços", "arp", "vigência da ata", "3.13.1"],
        "3.13.3 – Possibilidade de Prorrogação de Prazo de Vigência": ["prorrogação", "prazo de vigência", "admitida", "não admitida", "3.13.3"],
        "3.14.1 – Obrigações da Contratada — Gerais": ["obrigações da contratada", "3.14.1.3", "3.14.1.5", "inserir prazo"],
        "3.14.2 – Obrigações da Contratada — Específicas": ["obrigações específicas da contratada", "3.14.2"],
        "3.15.2 – Obrigações do Contratante — Específicas": ["obrigações do contratante", "contratante", "3.15.2"],
        "3.16 – Indicação sobre a Necessidade de Garantia Contratual": ["garantia contratual", "seguro garantia", "caução", "3.16"],
        "3.17 – Informações Orçamentárias": ["informações orçamentárias", "orçamentário", "3.17"],
        "3.18 – Responsável pelo Preenchimento": ["responsável", "matrícula", "assinatura", "servidor", "unidade administrativa"],
        "AP-I – Apenso I (Tabela de Itens de Serviço)": ["apenso i", "tabela de itens", "catser", "unidade de medida", "parametrização"],
        "AP-II – Apenso II (Especificações Técnicas)": ["apenso ii", "especificações técnicas", "especificação técnica"],
        # TR Aquisições – análise abrangente (Jan/2026)
        "1.1 – Indicação do Objeto": ["objeto", "indicação do objeto", "bem de luxo", "apenso i", "ato normativo"],
        "1.2 – Indicação de Marca e/ou Modelo": ["marca", "modelo", "referência", "exclusivo", "equivalente"],
        "1.3 – Justificativa do Quantitativo": ["quantitativo", "quantidade", "justificativa do quantitativo"],
        "1.4 – Natureza do Objeto": ["natureza do objeto", "imediato", "parcelado", "continuado", "fornecimento"],
        "1.5 – Fundamentação da Contratação": ["fundamentação", "justificativa", "motivação", "necessidade"],
        "1.6 – Descrição da Solução como um Todo": ["solução", "descrição da solução"],
        "1.7 – Formalização da Contratação": ["formalização", "nota de empenho", "instrumento substitutivo", "ata de registro"],
        "2.1 – Fundamentação Legal (Forma de Seleção)": ["base legal", "art. 75", "dispensa", "inciso", "eletrônica", "tradicional"],
        "2.2.1 – Habilitação Jurídica": ["habilitação jurídica", "pessoa jurídica", "pessoa física"],
        "2.2.3 – Habilitação Técnica": ["habilitação técnica", "atestado", "certidão técnica", "requisitos técnicos"],
        "2.2.4 – Habilitação Econômico-Financeira": ["habilitação econômico", "balanço", "capital social", "patrimônio"],
        "3.1 – Prazo para Retirada da Nota de Empenho": ["nota de empenho", "prazo para retirada", "retirada"],
        "3.2 – Forma de Execução": ["forma de execução", "prazo de entrega", "local de entrega", "agendamento", "horário"],
        "3.3 – Regras sobre Montagem": ["montagem", "desmontado", "montado", "instalação do fornecedor"],
        "3.4 – Regras para Instalação": ["instalação", "instalar", "prazo de instalação"],
        "3.5 – Prazo de Validade para Bens Perecíveis": ["validade", "perecível", "prazo de validade", "embalagem"],
        "3.6 – Regras de Garantia": ["garantia", "prazo de garantia", "fabricante", "atendimento", "chamado"],
        "3.7 – Possibilidade de Subcontratação": ["subcontratação", "vedada", "admitida", "subcontratar"],
        "3.8 – Modelo de Gestão e Fiscalização Contratual": ["fiscalização", "gestão contratual", "multa", "mora", "inexecução", "penalidade"],
        "3.9 – Condições de Recebimento do Objeto": ["recebimento provisório", "recebimento definitivo", "condições de recebimento"],
        "3.10 – Dos Preços": ["preços", "valor unitário", "custos", "encargos"],
        "3.11 – Regras de Faturamento": ["faturamento", "nota fiscal", "periodicidade", "parcela"],
        "3.13 – Reajustamento": ["reajustamento", "reajuste", "inpc", "índice", "correção"],
        "3.14.1 – Vigência da ARP": ["ata de registro de preços", "arp", "vigência da ata"],
        "3.14.2 – Definição de Vigência da Contratação": ["vigência da contratação", "vigência", "prazo de vigência", "data de início"],
        "3.14.3 – Possibilidade de Prorrogação de Prazo de Vigência": ["prorrogação", "prazo de vigência", "admitida", "não admitida"],
        "3.15.1 – Obrigações da Contratada — Gerais": ["obrigações da contratada", "contratada", "3.15.1"],
        "3.15.2 – Obrigações da Contratada — Específicas": ["obrigações específicas", "3.15.2"],
        "3.16.2 – Obrigações do Contratante — Específicas": ["obrigações do contratante", "contratante", "3.16.2"],
        "3.17 – Necessidade de Garantia Contratual": ["garantia contratual", "seguro garantia", "caução", "3.17"],
        "3.19 – Responsável pelo Preenchimento": ["responsável", "matrícula", "assinatura", "servidor", "unidade administrativa"],
        "AP-I – Apenso I (Tabela de Itens)": ["apenso i", "tabela de itens", "catmat", "pdm", "especificação"],
        "AP-II – Apenso II (Especificações Técnicas)": ["apenso ii", "especificações técnicas", "especificação técnica"],
    },
    _DOC_DFD: {
        "Objeto": ["objeto", "objeto da futura contratação", "descrição da demanda"],
        "Justificativa PCA": ["pca", "plano de contratações anual", "justificativa"],
        "Coerência Geral": ["unidade solicitante", "unidade gestora", "responsável", "superior imediato"],
    },
    _DOC_PRECOS: {
        "Motivação dos Fornecedores": ["motivação", "justificativa", "fornecedores consultados"],
    },
}


def _ia(item: ResultadoItem) -> ResultadoItem:
    return item.model_copy(update={"via_ia": True})


def _de_avaliacao(documento: str, av: dict) -> ResultadoItem:
    """Converte um item da resposta JSON da IA em ResultadoItem."""
    nome = av.get("item", "Análise IA")
    obs  = av.get("observacao", "")
    if av.get("conforme"):
        return _ia(ok(documento, nome, obs or "Conforme."))
    return _ia(inconforme(documento, nome, obs or "Não conforme."))


def _limpar_bloco(texto: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _extrair_trechos_relevantes(
    texto: str,
    termos: list[str],
    *,
    janela: int = 500,
    max_trechos: int = 6,
) -> str:
    """Monta um contexto compacto com trechos próximos aos termos relevantes.

    Isso ajuda a IA a reconhecer informação equivalente em modelos antigos,
    mesmo quando a nomenclatura ou a ordem das seções diverge do template atual.
    """
    if not texto:
        return ""

    trechos: list[str] = []
    vistos: set[tuple[int, int]] = set()
    for termo in termos:
        for match in re.finditer(re.escape(termo), texto, re.IGNORECASE):
            ini = max(0, match.start() - janela)
            fim = min(len(texto), match.end() + janela)
            chave = (ini // 100, fim // 100)
            if chave in vistos:
                continue
            vistos.add(chave)
            trechos.append(f"[trecho relacionado a '{termo}']\n{_limpar_bloco(texto[ini:fim])}")
            if len(trechos) >= max_trechos:
                return "\n\n".join(trechos)
    return "\n\n".join(trechos)


def _montar_contexto_double_check(
    texto: str,
    doc: str,
    itens: list[ResultadoItem],
) -> str:
    if not texto:
        return ""

    termos_doc = _DOUBLE_CHECK_TERMOS.get(doc, {})
    termos: list[str] = []
    for item in itens:
        termos.extend(termos_doc.get(item.item, []))
        termos.append(item.item)

    partes: list[str] = []
    if len(texto) <= 9000:
        partes.append(texto)
    else:
        partes.append(texto[:3000])
        trechos = _extrair_trechos_relevantes(texto, termos)
        if trechos:
            partes.append(trechos)
        partes.append(texto[-1800:])

    return _limpar_bloco("\n\n[...]\n\n".join(p for p in partes if p))


def _iterar_lotes(itens: list[T], tamanho: int) -> list[list[T]]:
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


def _agrupar_blocos_texto(
    blocos: list[str],
    *,
    max_caracteres: int = _DOUBLE_CHECK_MAX_CARACTERES_BLOCO,
    max_paginas_por_grupo: int = 4,
) -> list[str]:
    """Agrupa páginas em blocos controlados para reduzir latência/timeout."""
    grupos: list[str] = []
    atual: list[str] = []
    tamanho_atual = 0

    for bloco in blocos:
        bloco = _limpar_bloco(bloco)
        if not bloco:
            continue

        excede_chars = tamanho_atual + len(bloco) > max_caracteres
        excede_paginas = len(atual) >= max_paginas_por_grupo
        if atual and (excede_chars or excede_paginas):
            grupos.append("\n\n".join(atual))
            atual = []
            tamanho_atual = 0

        atual.append(bloco)
        tamanho_atual += len(bloco)

    if atual:
        grupos.append("\n\n".join(atual))

    return grupos


def _selecionar_grupos_relevantes(
    grupos: list[str],
    doc: str,
    itens: list[ResultadoItem],
    *,
    limite_grupos: int = 3,
) -> list[str]:
    if not grupos:
        return []

    termos_doc = _DOUBLE_CHECK_TERMOS.get(doc, {})
    termos: list[str] = []
    for item in itens:
        termos.extend(termos_doc.get(item.item, []))
        termos.append(item.item)

    if not termos:
        return grupos[:limite_grupos]

    pontuados: list[tuple[int, int, str]] = []
    for idx, grupo in enumerate(grupos):
        texto = grupo.lower()
        score = sum(texto.count(termo.lower()) for termo in termos)
        pontuados.append((score, -idx, grupo))

    selecionados = [grupo for score, _, grupo in sorted(pontuados, reverse=True) if score > 0][:limite_grupos]
    if selecionados:
        return selecionados

    # Fallback seguro: começo, meio e fim dão contexto macro mesmo sem match literal.
    indices = sorted({0, len(grupos) // 2, len(grupos) - 1})
    return [grupos[i] for i in indices[:limite_grupos]]


def _descricao_double_check(
    observacao: str,
    evidencia: str | None = None,
) -> str:
    partes = [p.strip() for p in (observacao, evidencia) if p and p.strip()]
    return " Evidência: ".join(partes) if partes else (
        "Verificado pela IA — informação localizada no documento, em formato diverso do modelo atual."
    )


def _aplicar_revisao_double_check(
    item: ResultadoItem,
    revisao: dict | None,
) -> ResultadoItem:
    if not revisao:
        return item

    classificacao = (revisao.get("classificacao") or "").strip().upper()
    observacao = (revisao.get("observacao") or "").strip()
    evidencia = (revisao.get("evidencia") or "").strip()

    if classificacao == "AUSENTE":
        # Se a IA confirma que a informação está ausente, converte para INCONFORME
        return item.model_copy(update={
            "status": StatusRegra.INCONFORME,
            "descricao": _descricao_double_check(observacao or "Informação não localizada no documento.", evidencia),
            "via_ia": True,
            "providencia": Providencia.CORRIGIR,
        })

    if classificacao in _DOUBLE_CHECK_CLASSIFICACOES_PRESENTE:
        return item.model_copy(update={
            "status": StatusRegra.CONFORME,
            "descricao": _descricao_double_check(observacao, evidencia),
            "via_ia": True,
            "providencia": Providencia.PROSSEGUIR,
        })

    if classificacao == "PRESENTE_COM_RESSALVA":
        return item.model_copy(update={
            "descricao": _descricao_double_check(observacao, evidencia),
            "via_ia": True,
        })

    if classificacao == "NAO_FOI_POSSIVEL_AFERIR":
        # Mantém status original mas marca como revisado pela IA
        return item.model_copy(update={
            "descricao": f"{item.descricao} (IA: não foi possível aferir com o contexto disponível)",
            "via_ia": True,
        })

    return item


# ─────────────────────────────────────────────────────────────────────────────
# DFD
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_dfd(processo: ProcessoExtraido) -> list[ResultadoItem]:
    log.info("_analisar_dfd() chamado - DFD presente: %s, texto_original presente: %s", 
             bool(processo.dfd), bool(processo.dfd and processo.dfd.texto_original))
    
    dfd = processo.dfd
    if not dfd or not dfd.texto_original:
        log.warning("DFD ou texto_original ausente, retornando vazio")
        return []

    # Prepara contexto para análise de coerência DFD × TR
    contexto_dfd = dfd.texto_original
    if processo.tr and processo.tr.objeto:
        contexto_dfd += f"\n\nOBJETO DO TR:\n{processo.tr.objeto}"

    pergunta = """Analise o DFD (Documento de Formalização da Demanda) e avalie:

IMPORTANTE: Ignore completamente erros de formatação, OCR ou digitação (ex: "Dede.zação" em vez de "Dedetização"). Considere que o texto pode ter problemas de extração do PDF. Avalie APENAS o conteúdo substantivo. NÃO aponte erros de OCR/OCR como inconformidade.

1. "Objeto" – a descrição do objeto é específica e suficiente para identificar o que será contratado? (ignore erros de formatação/OCR, NÃO aponte erros de digitação como inconformidade. NÃO analise especificações técnicas detalhadas, quantitativos por unidade ou parâmetros de qualidade exigidos - esses pontos são verificados em outras partes do documento como planilha de itens e especificações técnicas)
2. "Justificativa PCA" – se a contratação não está prevista no PCA, a justificativa é plausível?
3. "Coerência Geral" – objeto, unidade, responsável e superior são coerentes entre si? (ignore erros de formatação/OCR, NÃO aponte erros de digitação como inconformidade)
4. "Coerência DFD × TR" – o objeto descrito no DFD é coerente com o objeto do Termo de Referência (TR)? VERIFIQUE RIGOROSAMENTE: 
   - O local/destinatário (cidade, promotoria, unidade) deve ser IGUAL em ambos os documentos. Se o DFD menciona uma cidade/promotoria e o TR menciona outra cidade/promotoria DIFERENTE, é INCONFORME.
   - A natureza da contratação deve ser consistente: se DFD menciona "confecção e instalação" (serviço) e TR menciona "aquisição" (compra), é INCONFORME.
   - O objeto principal deve ser o mesmo. Se os textos são muito diferentes e não descrevem a mesma essência da contratação, é INCONFORME.
   Considere que o DFD pode ser mais sucinto, mas deve descrever essencialmente a mesma contratação para o MESMO local/destinatário. Textos padronizados (declarações institucionais, observações padrão) não devem ser considerados como parte do núcleo descritivo do objeto.

Responda APENAS com JSON:
{"avaliacoes": [{"item": "...", "conforme": true/false, "observacao": "..."}]}

Omita itens que não se aplicam."""

    r = await analisar(pergunta, contexto_dfd, max_tokens=600)
    if not r:
        return []
    return [_de_avaliacao(_DOC_DFD, av) for av in r.get("avaliacoes", [])]


# ─────────────────────────────────────────────────────────────────────────────
# TR Serviços — análise abrangente de conformidade (Jan/2026)
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_tr_servicos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tr = processo.tr
    if not isinstance(tr, TRServicosExtraido) or not tr.texto_original:
        return []

    # Contexto: DFD (se disponível, até 3000 chars) + TR completo
    ctx_partes: list[str] = []
    tem_dfd = bool(processo.dfd and processo.dfd.texto_original)
    if tem_dfd:
        ctx_partes.append(
            "=== DOCUMENTO DE FORMALIZAÇÃO DA DEMANDA (DFD) ===\n"
            + processo.dfd.texto_original[:3000]  # type: ignore[union-attr]
        )
    ctx_partes.append(
        "=== TERMO DE REFERÊNCIA – SERVIÇOS ===\n"
        + tr.texto_original
    )
    contexto = "\n\n".join(ctx_partes)

    regra_1_1_de = (
        "(d) DFD fornecido: SIM. (e) verificar se o tópico '1. Objeto da Futura Contratação' "
        "do DFD está em congruência com o objeto de 1.1 do TR (mesmo assunto/objeto)."
        if tem_dfd else
        "(d) DFD fornecido: NÃO — registrar 'DFD não fornecido' na observação e marcar conforme. "
        "(e) não aplicável."
    )

    pergunta = (
        "## PAPEL\n"
        "Você é analista de conformidade documental especializado em contratações públicas regidas pela "
        "Lei Federal nº 14.133/2021 e Lei Estadual/BA nº 14.634/2023, no âmbito do MPBA. "
        "Verifique presença, completude e coerência formal dos campos do TR de SERVIÇOS. "
        "Não emita juízo de mérito sobre adequação técnica ou suficiência jurídica.\n\n"

        "## MARCADORES DE NÃO PREENCHIMENTO\n"
        "Considere NÃO PREENCHIDO qualquer campo com: [inserir texto], [Inserir ...], [Indicar ...], "
        "[Informar ...], [Especificar.], [justificar ...], [inserir prazo], [inserir endereço], "
        "xxxx, xxx, xx, xx,xx, _____, ( ) sem marcação em campo de escolha, Ex.:, Ex.1:, Ex.2:, "
        "(escolher UMA opção), (PREENCHER, CONFORME O CASO), (Se houver), E / OU residual, "
        "INSERIR ASSINATURA DIGITAL, 202x não substituído, e-mail/telefone incompleto. "
        "Considere 'marcada' apenas quando houver (X), (x), [X], ☑ ou marca equivalente. ( ) vazio = não marcada. "
        "REGRA DE PREVALÊNCIA: quando um campo de escolha tiver opção inequivocamente marcada, "
        "placeholders das opções NÃO marcadas do mesmo campo NÃO geram inconformidade.\n\n"

        "## REGRAS (avaliar nesta ordem exata)\n"
        f"1.1 – Indicação do Objeto: (a) prestação de serviços descrita concretamente, placeholder substituído; "
        "(b) expressão 'através do Sistema de Registro de Preços' resolvida — mantida somente se 1.6 = C ou D, "
        "excluída se 1.6 = A ou B; (c) remissão ao Apenso I atendida pela existência do Apenso I preenchido; "
        f"{regra_1_1_de}\n"
        "1.2 – Justificativa do Quantitativo Definido: indicação objetiva de como se chegou às quantidades "
        "de serviços; 'Ex.:' removido.\n"
        "1.3 – Natureza do Objeto: UMA opção marcada (A=prestação imediata/pontual/por escopo, B=parcelada, "
        "C=serviços continuados); se C: UMA subopção marcada entre C.1, C.2, C.3 e C.4, E justificativa "
        "para enquadramento como serviço continuado preenchida.\n"
        "1.4 – Fundamentação da Contratação: motivação/necessidade da contratação descrita, "
        "placeholder substituído.\n"
        "1.5 – Descrição da Solução como um Todo: solução descrita integralmente; 'Ex.1:' e 'Ex.2:' removidos.\n"
        "1.6 – Formalização da Contratação: UMA opção marcada (A=empenho/instrumento substitutivo, "
        "B=instrumento formal de contrato, C=ARP e posteriores empenhos/instrumentos substitutivos, "
        "D=ARP e posteriores instrumentos formais de contrato); se C ou D: unidade gerenciadora indicada, "
        "abrangência territorial com UMA opção marcada (Salvador / Salvador e RMS / Outro indicado), "
        "e possibilidade de adesão (SIM ou NÃO) marcada.\n"
        "2.1 – Fundamentação Legal (Forma de Seleção): SOMENTE opção B (dispensa não eletrônica/tradicional) "
        "é aceita — marcação de A ou ausência = NÃO CONFORME; NÃO avalie subcampos A.1 a A.6 em nenhuma hipótese; "
        "inciso do art. 75 preenchido; se B: B.1 (justificativa para dispensa tradicional preenchida) e B.2 "
        "(UMA opção — I=não divulgar com justificativa, ou II=divulgar com e-mail, telefone e prazo ≥ 3 dias úteis "
        "preenchidos, expresso em dias úteis sem data certa).\n"
        "2.2.1 – Habilitação Jurídica: ao menos UMA opção marcada (A=pessoa jurídica e/ou B=pessoa física).\n"
        "2.2.2 – Habilitação Fiscal, Social e Trabalhista: disposições A, B, B.1, C, D, E mantidas "
        "integralmente — texto invariável, não comporta exclusão.\n"
        "2.2.3 – Habilitação Técnica: UMA opção marcada (A=não será exigida ou B=será exigida); se B: "
        "cada bloco mantido está integralmente preenchido (DECLARAÇÃO com subitens b) a e) preenchidos — "
        "local de visita, unidade responsável, telefone, e-mail, data-limite; ATESTADO/CERTIDÃO com critérios "
        "preenchidos; REGISTRO/INSCRIÇÃO com tabela preenchida; PROVA de lei especial com tabela preenchida; "
        "'Outro documento' art. 67 indicado e justificado); blocos não utilizados, conectores 'E / OU' "
        "residuais e orientações excluídos.\n"
        "2.2.4 – Habilitação Econômico-Financeira: ao menos UMA opção marcada (A=não exigida, B, C ou D); "
        "se A marcada simultaneamente com B/C/D = PENDÊNCIA; se C: percentual preenchido e ≤ 10%; "
        "se D: exigência indicada e justificada (art. 69).\n"
        "3.1 – Regime de Execução: UMA opção marcada (A=empreitada por preço global, "
        "B=empreitada por preço unitário, C=outro com indicação preenchida).\n"
        "3.2 – Prazo para Retirada da Nota de Empenho: em 3.2.1, prazo preenchido e alternativa "
        "'[úteis ou corridos]' resolvida para uma única forma de contagem.\n"
        "3.3 – Forma de Execução: (3.3.1) local(is) de execução com endereço completo e CEP; "
        "(3.3.2) UMA opção (A=não se aplica ou B=sim; se B: unidade responsável e dias/horários preenchidos, "
        "'Ex.:' removido, e 'Outras Regras' preenchidas ou com 'Não se aplica'); "
        "(3.3.3) UMA opção sobre agendamento (A=não se aplica ou B=sim; se B: unidade, telefone, "
        "e-mail preenchidos e antecedência mínima preenchida ou 'Não se aplica'); "
        "(3.3.4) UMA opção (A=não se aplica ou B=aplica-se com texto preenchido).\n"
        "3.4 – Prazo(s) de Execução: UMA opção marcada (A, B ou C); se A: A.1 tabela preenchida "
        "(descrição, prazo e úteis/corridos marcado por linha), A.2 UMA opção (I=recebimento do empenho "
        "ou II=outro com texto informado e 'Ex.:' removido), A.3 prazo total preenchido ou 'Não se aplica', "
        "A.4 UMA opção sobre prorrogação (I=não ou II=sim); se B: regras textuais preenchidas; "
        "se C: Apenso II existe e contém definições de prazo de execução.\n"
        "3.5 – Regras de Garantia: (3.5.1) UMA opção marcada (A=não se aplica, B=garantia legal/CDC, "
        "C=garantia contratada, D=híbrido, E=definições no Apenso II); se C: justificativa preenchida; "
        "se D: justificativa e indicação dos itens com garantia legal e contratada preenchidas; "
        "se E: Apenso II existente e preenchido; se C ou D, avaliar também: (3.5.2.1) UMA opção "
        "(A=contratado ou B=fabricante com justificativa); (3.5.2.2) UMA opção (A=dias ou B=meses com "
        "número, ou C=vigência contratual) com justificativa do prazo; (3.5.2.3) UMA opção "
        "(A=horas ou B=dias com número e úteis/corridos, ou C=outro indicado); (3.5.2.4) UMA opção "
        "(A=assistência em zona urbana/metropolitana de Salvador, B=município indicado, C=a critério da contratada, "
        "D=on site com prazo em horas e justificativa, E=outra especificada); (3.5.2.5) UMA opção "
        "(A=não se aplica ou B=aplica-se com texto preenchido).\n"
        "3.6 – Possibilidade ou Não de Subcontratação: UMA opção marcada (A=vedada ou "
        "B=admitida parcialmente); se B: parcela(s) subcontratável(eis) indicada(s) e condições preenchidas.\n"
        "3.7 – Modelo de Gestão e Fiscalização Contratual: (3.7.1) disposições 3.7.1.1 a 3.7.1.6 mantidas — "
        "texto invariável; (3.7.2) UMA opção (A=não se aplica ou B=disposições específicas preenchidas, "
        "numeração iniciando em 3.7.2.1); (3.7.3) infrações e sanções mantidas — texto invariável; "
        "(3.7.4) UMA opção (A=disposições padrão mantidas sem alteração: moratória 0,5%/dia, "
        "compensatórias 20% e 30%, multa 10% — ou B=disposições específicas com 3.7.4.1 a 3.7.4.4 preenchidos, "
        f"sem 'xxx', cada um entre {_MORA_MAX}% e {_INEX_MAX}% do valor global — se B com percentuais fora "
        "desta faixa = PENDÊNCIA).\n"
        "3.8 – Condições de Recebimento do Objeto: (3.8.1) prazo de recebimento provisório preenchido em dias "
        "corridos (mín. 1 dia; 'Não se aplica' é vedado) e UMA opção de termo inicial marcada "
        "(A=da finalização dos serviços, B=da entrega da fatura, C=outro indicado); "
        "(3.8.2) prazo de recebimento definitivo preenchido em dias corridos; "
        "(3.8.3) UMA opção (A=não se aplica ou B=prazo; se B: UMA subopção — B.1=horas ou B.2=dias com "
        "número e úteis/corridos, ou B.3=outro indicado); (3.8.4) disposições 3.8.4.1 a 3.8.4.6 mantidas — "
        "texto invariável.\n"
        "3.9 – Dos Preços: (3.9.1) UMA opção (A=preços englobam todos os custos, com A.1 invariável mantido "
        "e A.2 preenchido ou com 'Não se aplica'; ou B=itens/custos não inclusos com texto preenchido); "
        "(3.9.2) UMA opção marcada (A=valor mensal fixo, B=valor unitário por serviços, "
        "C=valor global contratado, D=outro indicado com 'Ex.:' removido).\n"
        "3.10 – Regras de Faturamento: (3.10.1) UMA opção marcada (A=mensal, B=múltiplos faturamentos, "
        "C=parcela única, D=parcelado, E=outro); se C: UMA subopção (C.1=ao final da execução ou "
        "C.2=outro indicado); se D: UMA subopção preenchida (D.1=quantidade de parcelas ou D.2=montantes); "
        "se E: indicação preenchida; (3.10.2) UMA opção (A=não se aplica ou B=regras/documentos preenchidos).\n"
        "3.11 – Regras para Pagamento e Atualização Monetária: disposições 3.11.1 a 3.11.7.1 mantidas — "
        "texto invariável, nenhum campo aberto.\n"
        "3.12 – Reajustamento: UMA opção marcada (A=passível de reajustamento, B=não cabível na vigência "
        "originária, C=não cabível); se A: índice oficial com UMA opção marcada (A.1=INPC/IBGE ou "
        "A.2=outro indicado); se B: índice oficial com UMA opção marcada (B.1=INPC/IBGE ou B.2=outro); "
        "se C: justificativa preenchida.\n"
        "3.13.1 – Vigência da ARP: UMA opção marcada (A=não se aplica ou B=vigência da ARP); se B: prazo "
        "≤ 12 meses preenchido e possibilidade de prorrogação com UMA opção (NÃO ou SIM, total ≤ 2 anos); "
        "verificar coerência com 1.6 — se 1.6=C ou D deve ser B; se 1.6=A ou B deve ser A (incoerência = PENDÊNCIA).\n"
        "3.13.3 – Possibilidade de Prorrogação de Prazo de Vigência: UMA opção marcada "
        "(A=não será admitida ou B=admitida mediante aditivo com justificativa preenchida; 'Ex.1:' e 'Ex.2:' removidos).\n"
        "3.14.1 – Obrigações da Contratada — Gerais: disposições 3.14.1.1 a 3.14.1.20 mantidas; "
        "itens 3.14.1.3 e 3.14.1.5 devem conter prazo efetivamente preenchido (placeholder '[inserir prazo]' "
        "substituído).\n"
        "3.14.2 – Obrigações da Contratada — Específicas: UMA opção marcada (A=não existem ou "
        "B=obrigações específicas indicadas).\n"
        "3.15.2 – Obrigações do Contratante — Específicas: UMA opção marcada (A=não existem ou "
        "B=específicas indicadas); NÃO classifique a numeração interna '3.16.1.x' como inconformidade — "
        "é erro tipográfico do próprio modelo.\n"
        "3.16 – Necessidade de Garantia Contratual: UMA opção marcada (A=não será exigida ou B=será exigida); "
        "se B: B.1 com UMA opção (I=5% ou II=outro percentual >5% e ≤10% com justificativa); B.2 com prazo "
        "de apresentação preenchido; B.3 com UMA opção de duração (I=mesma da contratação ou II=dias/meses "
        "após a vigência com número preenchido).\n"
        "3.17 – Informações Orçamentárias: remissão aos formulários de informações orçamentárias mantida — "
        "texto invariável.\n"
        "3.18 – Responsável pelo Preenchimento: matrícula, nome e unidade administrativa preenchidos; "
        "identificar se há assinatura (em imagem ou digital) no campo correspondente.\n"
        "AP-I – Apenso I (Tabela de Itens de Serviço): tabela preenchida (item, descrição do serviço, "
        "unidade de medida, quantidade e código CATSER com descrição), sem 'xxxx'/'xx'; "
        "a tabela complementar 'PARAMETRIZAÇÃO ENTRE OBJETO E CÓDIGO(S) CATSER' — exclusiva da dispensa "
        "eletrônica — deve ter sido excluída (sua permanência = NÃO CONFORME).\n"
        "AP-II – Apenso II (Especificações Técnicas Detalhadas): se houver especificações técnicas detalhadas, "
        "texto preenchido; caso contrário, Apenso II deve ter sido excluído; se 3.4=C ou 3.5.1=E, "
        "o Apenso II deve existir e estar preenchido (ausência = NÃO CONFORME).\n\n"

        "## INSTRUÇÃO DE SAÍDA\n"
        "Avalie CADA regra acima. Use 'pendencia': true para ambiguidades objetivas (ex.: duas opções onde "
        "só cabe uma; incoerência entre subtópicos; campo condicional incompleto). "
        "Responda APENAS com JSON válido, sem texto adicional:\n"
        '{"avaliacoes":[{"item":"<ID exato – Título exato>","conforme":true,"pendencia":false,'
        '"observacao":"<evidência literal curta ou descrição da falha, até 120 chars>"}]}\n'
        "Inclua TODOS os itens avaliados (conformes e não conformes). "
        "Use os nomes de 'item' EXATAMENTE como escritos nas regras acima."
    )

    r = await analisar(pergunta, contexto, max_tokens=2200)
    if not r:
        return []
    return [_de_avaliacao_aquisicao(av) for av in r.get("avaliacoes", [])]


# ─────────────────────────────────────────────────────────────────────────────
# TR Aquisições — análise abrangente de conformidade (Jan/2026)
# ─────────────────────────────────────────────────────────────────────────────

def _de_avaliacao_aquisicao(av: dict) -> ResultadoItem:
    nome = av.get("item", "Análise IA")
    obs  = av.get("observacao", "")
    if av.get("pendencia"):
        return _ia(pendencia(_DOC_TR, nome, obs or "Verificar."))
    if av.get("conforme"):
        return _ia(ok(_DOC_TR, nome, obs or "Conforme."))
    return _ia(inconforme(_DOC_TR, nome, obs or "Não conforme."))


async def _analisar_tr_aquisicoes(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tr = processo.tr
    if not isinstance(tr, TRAquisicoesExtraido) or not tr.texto_original:
        return []

    # Contexto: DFD (se disponível, até 3000 chars) + TR completo
    ctx_partes: list[str] = []
    tem_dfd = bool(processo.dfd and processo.dfd.texto_original)
    if tem_dfd:
        ctx_partes.append(
            "=== DOCUMENTO DE FORMALIZAÇÃO DA DEMANDA (DFD) ===\n"
            + processo.dfd.texto_original[:3000]  # type: ignore[union-attr]
        )
    ctx_partes.append(
        "=== TERMO DE REFERÊNCIA – AQUISIÇÕES ===\n"
        + tr.texto_original
    )
    contexto = "\n\n".join(ctx_partes)

    regra_1_1_d = (
        "(d) verificar coerência do objeto com o campo '1. Objeto da Futura Contratação' do DFD fornecido "
        "(conforme = coerente)."
        if tem_dfd else
        "(d) DFD não fornecido — informar na observação e marcar conforme."
    )

    pergunta = (
        "## PAPEL\n"
        "Você é analista de conformidade documental especializado em contratações públicas regidas pela "
        "Lei Federal nº 14.133/2021 e Lei Estadual/BA nº 14.634/2023, no âmbito do MPBA. "
        "Verifique presença, completude e coerência formal dos campos. "
        "Não emita juízo de mérito sobre adequação técnica ou suficiência jurídica.\n\n"

        "## MARCADORES DE NÃO PREENCHIMENTO\n"
        "Considere NÃO PREENCHIDO qualquer campo com: [inserir texto], [Inserir ...], [Indicar ...], xxxx, "
        "_____, ( ) sem marcação, Ex.:, (PREENCHER, CONFORME O CASO), INSERIR ASSINATURA DIGITAL, "
        "202x não substituído, e-mail/telefone incompleto. "
        "Considere 'marcada' apenas quando houver (X), (x), [X], ☑ ou marca equivalente no início da linha. "
        "( ) vazio = não marcada. Se alguma opção estiver marcada, desconsidere placeholder residual.\n\n"

        "## REGRAS (avaliar nesta ordem exata)\n"
        f"1.1 – Indicação do Objeto: (a) objeto descrito concretamente; "
        "(b) declaração de que NÃO é bem de luxo (Ato Normativo nº 004/2024) presente; "
        "(c) remissão ao Apenso I presente; "
        f"{regra_1_1_d}\n"
        "1.2 – Indicação de Marca e/ou Modelo: exatamente UMA opção marcada (A=não se aplica, B=exclusiva, "
        "C=referência/equivalente); se B ou C, justificativa e subitens com marca/modelo preenchidos.\n"
        "1.3 – Justificativa do Quantitativo: indicação objetiva de como se chegou às quantidades; "
        "'Ex.:' removido.\n"
        "1.4 – Natureza do Objeto: UMA opção marcada (A=imediato, B=parcelado, C=continuado); "
        "se C, justificativa da continuidade preenchida.\n"
        "1.5 – Fundamentação da Contratação: motivação/necessidade descrita de forma substantiva "
        "(não apenas texto de modelo).\n"
        "1.6 – Descrição da Solução como um Todo: solução descrita integralmente; 'Ex.:' removido.\n"
        "1.7 – Formalização da Contratação: UMA opção marcada (A, B, C ou D); se C ou D, unidade "
        "gerenciadora, abrangência territorial (UMA opção) e adesão (SIM ou NÃO) preenchidos.\n"
        "2.1 – Fundamentação Legal (Forma de Seleção): SOMENTE opção B (dispensa não eletrônica/tradicional) "
        "é aceita — marcação de A ou ausência de marcação = NÃO CONFORME; inciso do art. 75 preenchido; "
        "se B: B.1 preenchida, B.2 com opção I ou II (se II: e-mail, telefone e prazo ≥ 3 dias úteis preenchidos).\n"
        "2.2.1 – Habilitação Jurídica: ao menos UMA opção marcada (A — pessoa jurídica e/ou B — pessoa física).\n"
        "2.2.3 – Habilitação Técnica: UMA opção marcada (A=não exigida ou B=exigida); se B, requisitos "
        "aplicáveis preenchidos e blocos não utilizados excluídos.\n"
        "2.2.4 – Habilitação Econômico-Financeira: ao menos UMA opção marcada (A, B, C ou D); "
        "se C, percentual ≤ 10%; se D, exigência indicada e justificada (art. 69).\n"
        "3.1 – Prazo para Retirada da Nota de Empenho: prazo preenchido e definido 'úteis' ou 'corridos'.\n"
        "3.2 – Forma de Execução: (3.2.1) prazo de entrega preenchido e úteis/corridos definido; "
        "(3.2.2) UMA opção (A=recebimento do empenho ou B=outro; se B, texto informado); "
        "(3.2.3) UMA opção sobre prorrogação do prazo de entrega (NÃO ou SIM); "
        "(3.2.4) local(is) de entrega com endereço completo e CEP; "
        "(3.2.5) dias e horários de entrega informados, 'Ex.:' removido; "
        "(3.2.6) UMA opção sobre necessidade de agendamento (NÃO ou SIM); "
        "(3.2.7) setor responsável pelo agendamento/recepção indicado; "
        "(3.2.8) telefone e e-mail de contato preenchidos; "
        "(3.2.9) UMA opção (A=não se aplica ou B=aplica-se; se B, regras de embalagem preenchidas e 'Ex.' removidos); "
        "(3.2.10) UMA opção (A=não se aplica ou B=aplica-se; se B, demais regras preenchidas).\n"
        "3.3 – Regras sobre Montagem: UMA opção marcada (A=montados/sem montagem, B=desmontados, "
        "C=montagem pelo fornecedor); se C: C.1 (prazo com UMA opção), C.2 (dias/horários) e C.3 "
        "(local com UMA opção) preenchidos.\n"
        "3.4 – Regras para Instalação: UMA opção marcada (A=sem instalação ou B=instalação pelo fornecedor); "
        "se B: B.1 (prazo com UMA opção), B.2 (dias/horários) e B.3 (local com UMA opção) preenchidos.\n"
        "3.5 – Prazo de Validade para Bens Perecíveis: UMA opção marcada (A=não se aplica, "
        "B=validade da embalagem, C=com decurso máximo); se C, tabela de item/lote, prazo mínimo e "
        "decurso máximo preenchida.\n"
        "3.6 – Regras de Garantia: (3.6.1) UMA opção marcada (A a E); se C ou D: justificativa preenchida "
        "e verificar 3.6.2.1 (UMA opção A=contratado ou B=fabricante; se B, justificativa), "
        "3.6.2.2 (UMA opção A/B/C com justificativa do prazo), 3.6.2.3 (UMA opção com horas/dias e "
        "úteis/corridos definidos), 3.6.2.4 (UMA opção A a E; se D, prazo e justificativa preenchidos); "
        "(3.6.2.5) UMA opção (A=não se aplica ou B=aplica-se; se B, preenchido).\n"
        "3.7 – Possibilidade de Subcontratação: UMA opção marcada (A=vedada ou B=admitida parcial); "
        "se B: parcela subcontratável e regras/condições preenchidas.\n"
        "3.8 – Modelo de Gestão e Fiscalização Contratual: (3.8.1) texto invariável mantido; "
        "(3.8.2) UMA opção (A=não se aplica ou B=disposições específicas preenchidas); "
        "(3.8.3) texto invariável mantido; "
        "(3.8.4) UMA opção (A=percentuais padrão ou B=específicos); se B: confirmar que percentuais "
        f"estão entre {_MORA_MAX}% e {_INEX_MAX}% (fora desta faixa = PENDÊNCIA) e que os 4 subitens "
        "3.8.4.1 a 3.8.4.4 estão preenchidos.\n"
        "3.9 – Condições de Recebimento do Objeto: (3.9.1) prazo de recebimento provisório preenchido "
        "e UMA opção marcada (A=da entrega ou B=outro); (3.9.2) prazo de recebimento definitivo em dias "
        "corridos preenchido; (3.9.3) UMA opção (A=não se aplica ou B=prazo; se B, horas/dias e "
        "úteis/corridos definidos).\n"
        "3.10 – Dos Preços: (3.10.1) UMA opção marcada (A=engloba todos os custos ou B=itens não inclusos) "
        "e demais regramentos preenchidos ou 'Não se aplica'; (3.10.2) UMA opção marcada "
        "(A=valor unitário ou B=outro).\n"
        "3.11 – Regras de Faturamento: (3.11.1) UMA opção marcada (A a E); se D, quantidade e montantes "
        "das parcelas preenchidos; se E, indicação preenchida; (3.11.2) UMA opção (A=não se aplica ou "
        "B=regras/documentos preenchidos).\n"
        "3.13 – Reajustamento: UMA opção marcada (A=passível, B=não cabível na vigência originária, "
        "C=não cabível com justificativa); se A ou B: índice oficial com UMA opção marcada (INPC/IBGE ou "
        "outro indicado); se C: justificativa preenchida.\n"
        "3.14.1 – Vigência da ARP: UMA opção marcada (A=não se aplica ou B=vigência da ARP); "
        "se A, CONFORME; se B: prazo de vigência (≤ 1 ano) preenchido e prorrogação com UMA opção "
        "(NÃO ou SIM, limite total 2 anos) marcada.\n"
        "3.14.2 – Definição de Vigência da Contratação: UMA opção (A=sem contrato ou B=com contrato) "
        "e UMA subopção (A.1–A.4 ou B.1/B.2) com prazos/datas preenchidos; em A.3/A.4 e B com data "
        "certa, a data deve ser posterior à previsão de empenho/assinatura e sem '202x'.\n"
        "3.14.3 – Possibilidade de Prorrogação de Prazo de Vigência: UMA opção marcada "
        "(A=não admitida ou B=admitida com justificativa preenchida).\n"
        "3.15.1 – Obrigações da Contratada — Gerais: itens 3.15.1.3 e 3.15.1.5 devem conter algum "
        "prazo preenchido.\n"
        "3.15.2 – Obrigações da Contratada — Específicas: UMA opção marcada (A=não existem ou "
        "B=específicas indicadas).\n"
        "3.16.2 – Obrigações do Contratante — Específicas: UMA opção marcada (A=não existem ou "
        "B=específicas indicadas).\n"
        "3.17 – Necessidade de Garantia Contratual: UMA opção marcada (A=não exigida ou B=exigida); "
        "se B: percentual com UMA opção (5% ou outro ≤ 10% com justificativa), prazo de apresentação "
        "preenchido e B.3 com UMA opção de duração no seguro-garantia.\n"
        "3.19 – Responsável pelo Preenchimento: matrícula, nome e unidade administrativa preenchidos; "
        "identificar se há assinatura digital ou espaço para assinatura no documento.\n"
        "AP-I – Apenso I (Tabela de Itens): tabela preenchida (item, descrição, unidade, quantidade, "
        "PDM com descrição, CATMAT com descrição), sem xxxx/xx; se dispensa não eletrônica (opção B "
        "em 2.1), tabela de parametrização CATMAT deve ter sido excluída.\n"
        "AP-II – Apenso II (Especificações Técnicas): se houver especificações detalhadas, texto "
        "preenchido; caso contrário, Apenso II deve ter sido excluído — se presente mas vazio, "
        "NÃO CONFORME.\n\n"

        "## INSTRUÇÃO DE SAÍDA\n"
        "Avalie CADA regra acima. Use 'pendencia': true para ambiguidades objetivas (ex.: dois campos "
        "obrigatórios onde só cabe um, campo condicional incompleto). "
        "Responda APENAS com JSON válido, sem texto adicional:\n"
        '{"avaliacoes":[{"item":"<ID exato – Título exato>","conforme":true,"pendencia":false,'
        '"observacao":"<evidência literal curta ou descrição da falha, até 120 chars>"}]}\n'
        "Inclua TODOS os itens avaliados (conformes e não conformes). "
        "Use os nomes de 'item' EXATAMENTE como escritos nas regras acima."
    )

    r = await analisar(pergunta, contexto, max_tokens=2000)
    if not r:
        return []
    return [_de_avaliacao_aquisicao(av) for av in r.get("avaliacoes", [])]


# ─────────────────────────────────────────────────────────────────────────────
# Tabela de Preços Orçados
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_tabela_precos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tp = processo.tabela_precos
    if not tp:
        return []

    ctx_parts = []
    # Objeto da contratação — vem do TR; fallback para descrição_solucao
    objeto_tr = None
    if processo.tr:
        objeto_tr = processo.tr.objeto or getattr(processo.tr, "descricao_solucao", None)
    if objeto_tr:
        ctx_parts.append(f"Objeto da contratação: {objeto_tr[:200]}")
    if tp.motivacao_fornecedores:
        ctx_parts.append(f"Motivação para escolha dos fornecedores: {tp.motivacao_fornecedores}")
    if tp.metodologia_menor_preco is not None:
        ctx_parts.append(f"Metodologia menor preço: {'Sim' if tp.metodologia_menor_preco else 'Não identificada'}")
    if tp.responsavel_nome:
        ctx_parts.append(f"Responsável: {tp.responsavel_nome}")
    if not ctx_parts:
        return []

    contexto = "\n".join(ctx_parts)

    pergunta = """Analise os dados da Tabela de Preços Orçados e avalie:

1. "Motivação dos Fornecedores" – a justificativa para escolha dos fornecedores é objetiva (não é genérica como 'empresas do ramo')?

Responda APENAS com JSON:
{"avaliacoes": [{"item": "...", "conforme": true/false, "observacao": "..."}]}

Omita itens sem informação suficiente."""

    r = await analisar(pergunta, contexto, max_tokens=400)
    if not r:
        return []
    return [_de_avaliacao(_DOC_PRECOS, av) for av in r.get("avaliacoes", [])]




# ─────────────────────────────────────────────────────────────────────────────
# Orçamentos / Propostas
# ---------------------------------------------------------------------

async def _analisar_orcamentos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    if not processo.orcamentos or not processo.tr:
        return []

    objeto = processo.tr.objeto or ""
    valores = [
        f"  - {o.razao_social or 'Empresa ' + str(i)}: R$ {o.valor_total:,.2f}"
        for i, o in enumerate(processo.orcamentos, 1)
        if o.valor_total
    ]
    if not valores or not objeto:
        return []

    contexto = f"Objeto da contratação: {objeto}\n\nValores propostos:\n" + "\n".join(valores)

    pergunta = """Avalie as propostas:

1. "Compatibilidade Valores × Objeto" - os valores propostos são compatíveis com o mercado para o objeto descrito?
2. "Variação entre Propostas" - a variação entre propostas é razoável (sem valores idênticos suspeitos ou discrepância extrema)?

Responda APENAS com JSON:
{"avaliacoes": [{"item": "...", "conforme": true/false, "observacao": "..."}]}"""

    r = await analisar(pergunta, contexto, max_tokens=400)
    if not r:
        return []
    return [_de_avaliacao(_DOC_ORC, av) for av in r.get("avaliacoes", [])]


# ---------------------------------------------------------------------
# Orquestrador
# ─────────────────────────────────────────────────────────────────────────────

# Itens determinísticos que a IA pode substituir quando resolvê-los.
# A IA devolve o item com o MESMO nome → remove o determinístico correspondente.
_ITENS_IA_SUBSTITUI = {
    # TR Serviços – análise abrangente (Jan/2026)
    "1.1 – Indicação do Objeto",
    "1.2 – Justificativa do Quantitativo Definido",
    "1.3 – Natureza do Objeto",
    "1.4 – Fundamentação da Contratação",
    "1.5 – Descrição da Solução como um Todo",
    "1.6 – Formalização da Contratação",
    "2.1 – Fundamentação Legal (Forma de Seleção)",
    "2.2.1 – Habilitação Jurídica",
    "2.2.2 – Habilitação Fiscal, Social e Trabalhista",
    "2.2.3 – Habilitação Técnica",
    "2.2.4 – Habilitação Econômico-Financeira",
    "3.1 – Regime de Execução",
    "3.2 – Prazo para Retirada da Nota de Empenho",
    "3.3 – Forma de Execução",
    "3.4 – Prazo(s) de Execução",
    "3.5 – Regras de Garantia",
    "3.6 – Possibilidade ou Não de Subcontratação",
    "3.7 – Modelo de Gestão e Fiscalização Contratual",
    "3.8 – Condições de Recebimento do Objeto",
    "3.9 – Dos Preços",
    "3.10 – Regras de Faturamento",
    "3.11 – Regras para Pagamento e Atualização Monetária",
    "3.12 – Reajustamento",
    "3.13.1 – Vigência da ARP",
    "3.13.3 – Possibilidade de Prorrogação de Prazo de Vigência",
    "3.14.1 – Obrigações da Contratada — Gerais",
    "3.14.2 – Obrigações da Contratada — Específicas",
    "3.15.2 – Obrigações do Contratante — Específicas",
    "3.16 – Indicação sobre a Necessidade de Garantia Contratual",
    "3.17 – Informações Orçamentárias",
    "3.18 – Responsável pelo Preenchimento",
    "AP-I – Apenso I (Tabela de Itens de Serviço)",
    "AP-II – Apenso II (Especificações Técnicas)",
    # TR Aquisições – análise abrangente (Jan/2026)
    "1.1 – Indicação do Objeto",
    "1.2 – Indicação de Marca e/ou Modelo",
    "1.3 – Justificativa do Quantitativo",
    "1.4 – Natureza do Objeto",
    "1.5 – Fundamentação da Contratação",
    "1.6 – Descrição da Solução como um Todo",
    "1.7 – Formalização da Contratação",
    "2.1 – Fundamentação Legal (Forma de Seleção)",
    "2.2.1 – Habilitação Jurídica",
    "2.2.3 – Habilitação Técnica",
    "2.2.4 – Habilitação Econômico-Financeira",
    "3.1 – Prazo para Retirada da Nota de Empenho",
    "3.2 – Forma de Execução",
    "3.3 – Regras sobre Montagem",
    "3.4 – Regras para Instalação",
    "3.5 – Prazo de Validade para Bens Perecíveis",
    "3.6 – Regras de Garantia",
    "3.7 – Possibilidade de Subcontratação",
    "3.8 – Modelo de Gestão e Fiscalização Contratual",
    "3.9 – Condições de Recebimento do Objeto",
    "3.10 – Dos Preços",
    "3.11 – Regras de Faturamento",
    "3.13 – Reajustamento",
    "3.14.1 – Vigência da ARP",
    "3.14.2 – Definição de Vigência da Contratação",
    "3.14.3 – Possibilidade de Prorrogação de Prazo de Vigência",
    "3.15.1 – Obrigações da Contratada — Gerais",
    "3.15.2 – Obrigações da Contratada — Específicas",
    "3.16.2 – Obrigações do Contratante — Específicas",
    "3.17 – Necessidade de Garantia Contratual",
    "3.19 – Responsável pelo Preenchimento",
    "AP-I – Apenso I (Tabela de Itens)",
    "AP-II – Apenso II (Especificações Técnicas)",
    # DFD
    "Objeto",
}

_ITENS_IA_SUBSTITUI_NORM: dict[str, str] = {
    normalizar_rotulo_regra(n): n for n in _ITENS_IA_SUBSTITUI
}


def _canon_item_substituivel(nome: str) -> str | None:
    """Nome canônico em ``_ITENS_IA_SUBSTITUI`` quando a IA varia traços ou espaços."""
    return _ITENS_IA_SUBSTITUI_NORM.get(normalizar_rotulo_regra(nome))


def _chave_revisao_double_check(documento: str, item: str) -> tuple[str, str]:
    return (normalizar_rotulo_regra(documento), normalizar_rotulo_regra(item))


async def aplicar_regras_ia(
    processo: ProcessoExtraido,
    resultados_deterministicos: list[ResultadoItem],
) -> tuple[list[ResultadoItem], list[ResultadoItem]]:
    """Executa todas as análises de IA em paralelo.

    Retorna (deterministicos_filtrados, novos_ia):
    - Itens que a IA resolve (nome exato em _ITENS_IA_SUBSTITUI): remove o determinístico
      e usa o resultado da IA no lugar.
    - Itens qualitativos (sufixo ' (IA)'): adicionados como itens extras.
    """
    tarefas = [
        _analisar_dfd(processo),
        _analisar_tr_servicos(processo),
        _analisar_tr_aquisicoes(processo),
        _analisar_tabela_precos(processo),
        _analisar_orcamentos(processo),
    ]

    resultados = await asyncio.gather(*tarefas, return_exceptions=True)

    novos: list[ResultadoItem] = []
    itens_resolvidos_pela_ia: set[tuple[str, str]] = set()  # (documento, item)

    for res in resultados:
        if isinstance(res, Exception):
            log.warning("Tarefa IA falhou: %s", res)
            continue
        for item in res:
            canon = _canon_item_substituivel(item.item)
            if canon:
                item = item.model_copy(update={"item": canon})
            novos.append(item)
            # Registra itens que a IA resolveu (nome exato, sem sufixo " (IA)")
            if canon:
                itens_resolvidos_pela_ia.add((item.documento, canon))
                log.debug("IA resolveu: [%s] %s → %s", item.documento, canon, item.status.value)

    # Remove dos determinísticos os itens que a IA substituiu
    deterministicos = [
        r for r in resultados_deterministicos
        if (r.documento, r.item) not in itens_resolvidos_pela_ia
    ]

    removidos = len(resultados_deterministicos) - len(deterministicos)
    if removidos:
        log.info("IA substituiu %d item(ns) determinístico(s).", removidos)

    return deterministicos, novos


# ─────────────────────────────────────────────────────────────────────────────
# Double-check: IA confirma ou descarta cada INCONFORME / PENDÊNCIA
# ─────────────────────────────────────────────────────────────────────────────

def _contexto_double_check(
    processo: ProcessoExtraido,
    doc: str,
    itens: list[ResultadoItem],
) -> str:
    """Retorna o melhor contexto disponível para o documento pedido."""
    if doc == _DOC_DFD and processo.dfd and processo.dfd.texto_original:
        grupos = _agrupar_blocos_texto(processo.dfd.blocos_texto or [processo.dfd.texto_original])
        selecionados = _selecionar_grupos_relevantes(grupos, doc, itens)
        return _montar_contexto_double_check("\n\n".join(selecionados), doc, itens)

    if doc == _DOC_TR and processo.tr and processo.tr.texto_original:
        grupos = _agrupar_blocos_texto(processo.tr.blocos_texto or [processo.tr.texto_original])
        selecionados = _selecionar_grupos_relevantes(grupos, doc, itens)
        return _montar_contexto_double_check("\n\n".join(selecionados), doc, itens)

    if doc == _DOC_PRECOS and processo.tabela_precos:
        tp = processo.tabela_precos
        partes: list[str] = tp.blocos_texto[:] if tp.blocos_texto else []
        if tp.aviso_previo_publicado is not None:
            partes.append(f"Aviso prévio publicado: {'Sim' if tp.aviso_previo_publicado else 'Não identificado'}")
        if tp.propostas_recebidas is not None:
            partes.append(f"Propostas recebidas: {tp.propostas_recebidas}")
        if tp.data_orcamento:
            partes.append(f"Data do orçamento: {tp.data_orcamento}")
        if tp.motivacao_fornecedores:
            partes.append(f"Motivação fornecedores: {tp.motivacao_fornecedores[:300]}")
        grupos = _agrupar_blocos_texto(partes)
        selecionados = _selecionar_grupos_relevantes(grupos, doc, itens)
        return _montar_contexto_double_check("\n\n".join(selecionados), doc, itens)

    if doc == _DOC_ORC and processo.orcamentos:
        linhas = [f"Orçamentos encontrados: {len(processo.orcamentos)}"]
        for i, o in enumerate(processo.orcamentos, 1):
            val = f"R$ {o.valor_total:,.2f}" if o.valor_total else "valor não extraído"
            linhas.append(f"  {i}. {o.razao_social or '?'} – CNPJ: {o.cnpj_cpf or '?'} – {val} – data: {o.data_proposta or '?'}")
        return _montar_contexto_double_check("\n".join(linhas), doc, itens)

    if doc == "Certidões" and processo.certidoes:
        return _montar_contexto_double_check(
            json.dumps(processo.certidoes.model_dump(), ensure_ascii=False, default=str),
            doc,
            itens,
        )

    return ""


async def _double_check_doc(
    doc: str,
    itens: list[ResultadoItem],
    contexto: str,
) -> list[dict]:
    """Envia um lote de itens (CONFORME, INCONFORME, PENDÊNCIA) à IA para validação contextual."""
    hoje = date.today().strftime("%d/%m/%Y")
    lista = "\n".join(
        f'{i+1}. "{it.item}" ({it.status.value}): {it.descricao}'
        for i, it in enumerate(itens)
    )
    pergunta = (
        f"Data de hoje: {hoje}.\n"
        f"Você é revisor de saneamento de Dispensa de Licitação (MPBA/Lei 14.133/2021).\n"
        f"O sistema automático classificou os itens abaixo no documento '{doc}'.\n"
        f"Analise o contexto fornecido e faça uma validação refinada de TODOS os itens.\n"
        f"Considere explicitamente que o documento pode seguir MODELO ANTIGO, com outra nomenclatura, "
        f"ordem de seções, redação ou formatação. O foco é verificar se a informação material exigida "
        f"está presente, ainda que em formato diferente do template atual.\n\n"
        f"Classifique cada item usando UMA destas opções:\n"
        f"- AUSENTE: a informação realmente não aparece no documento.\n"
        f"- PRESENTE_VARIACAO_FORMA: a informação está presente, mas em seção/título/formato diverso.\n"
        f"- PRESENTE_EQUIVALENTE: a informação exigida está claramente presente e adequada.\n"
        f"- PRESENTE_COM_RESSALVA: a informação aparece de forma substantiva, mas há insuficiência, "
        f"inconsistência ou dúvida relevante sobre o conteúdo. "
        f"NÃO use esta opção para: artefatos de OCR, texto ilegível/corrompido, "
        f"placeholder de modelo não preenchido (ex.: '[inserir...]', 'xx dias'), "
        f"ou endereço de e-mail com espaço/caractere inválido onde deveria haver '@'.\n"
        f"- NAO_FOI_POSSIVEL_AFERIR: o contexto não permite concluir com segurança.\n\n"
        f"REGRA EXTRA — campos de e-mail: só classifique como PRESENTE_* se houver endereço "
        f"completo e válido (formato usuario@dominio) no texto. Texto garbled ou sem '@' = AUSENTE.\n\n"
        f"Itens para validação:\n{lista}\n\n"
        f"Responda APENAS com JSON — use EXATAMENTE os nomes entre aspas para 'item':\n"
        '{"revisoes":[{"item":"...","classificacao":"AUSENTE|PRESENTE_VARIACAO_FORMA|PRESENTE_EQUIVALENTE|PRESENTE_COM_RESSALVA|NAO_FOI_POSSIVEL_AFERIR","observacao":"...","evidencia":"trecho curto ou referência textual"}]}'
    )
    r = await analisar(pergunta, contexto, max_tokens=800)
    if not r:
        return []
    return [
        {
            "documento": doc,
            "item": rv.get("item", ""),
            "classificacao": rv.get("classificacao", ""),
            "observacao": rv.get("observacao", ""),
            "evidencia": rv.get("evidencia", ""),
        }
        for rv in r.get("revisoes", [])
    ]


async def double_check_inconformidades(
    processo: ProcessoExtraido,
    todos: list[ResultadoItem],
) -> list[ResultadoItem]:
    """Double-check via IA de todos os itens (CONFORME, INCONFORME, PENDÊNCIA) de TR e DFD antes do relatório final.

    Para TR e DFD, todos os status passam pela IA para validação refinada.
    Para outros documentos, apenas INCONFORME/PENDÊNCIA são revisados.
    Quando a IA identifica que a informação exigida está presente em formato
    equivalente ou em modelo antigo, o item é convertido em CONFORME com
    ``via_ia=True`` para rastreabilidade.
    """
    # Para TR e DFD, inclui todos os itens (CONFORME, INCONFORME, PENDÊNCIA)
    # Para outros documentos, apenas INCONFORME/PENDÊNCIA
    problemas = [
        r for r in todos 
        if r.documento in (_DOC_TR, _DOC_DFD) 
        or r.status in (StatusRegra.INCONFORME, StatusRegra.PENDENCIA)
    ]
    if not problemas:
        return todos

    # Agrupa por documento e monta contextos
    por_doc: dict[str, list[ResultadoItem]] = {}
    for item in problemas:
        por_doc.setdefault(item.documento, []).append(item)

    tarefas: list = []
    for doc, itens in por_doc.items():
        for lote in _iterar_lotes(itens, _DOUBLE_CHECK_MAX_ITENS_POR_LOTE):
            ctx = _contexto_double_check(processo, doc, lote)
            if not ctx:
                continue
            tarefas.append(_double_check_doc(doc, lote, ctx))

    if not tarefas:
        return todos

    resultados = await asyncio.gather(*tarefas, return_exceptions=True)

    revisoes_por_item: dict[tuple[str, str], dict] = {}

    for res in resultados:
        if isinstance(res, Exception) or not res:
            continue
        for rv in res:
            key = _chave_revisao_double_check(str(rv.get("documento", "")), str(rv.get("item", "")))
            revisoes_por_item[key] = rv
            if rv.get("classificacao") in _DOUBLE_CHECK_CLASSIFICACOES_PRESENTE:
                log.info(
                    "Double-check: informação confirmada por IA em formato equivalente – [%s] %s",
                    rv["documento"],
                    rv["item"],
                )

    log.info("Double-check IA: %d item(ns) reclassificado(s) como presentes de %d revisado(s).",
             sum(
                 1
                 for rv in revisoes_por_item.values()
                 if rv.get("classificacao") in _DOUBLE_CHECK_CLASSIFICACOES_PRESENTE
             ),
             len(problemas))

    resultado_final: list[ResultadoItem] = []
    for item in todos:
        key = _chave_revisao_double_check(item.documento, item.item)
        resultado_final.append(_aplicar_revisao_double_check(item, revisoes_por_item.get(key)))

    return resultado_final
