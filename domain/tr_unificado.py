"""Schema unificado TR – SERVIÇOS + AQUISIÇÕES com discriminador Pydantic v2."""

from __future__ import annotations
import re
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Seções comuns a ambos os tipos de TR
# ─────────────────────────────────────────────────────────────────────────────

class HabilitacaoExtraida(BaseModel):
    juridica_pj: bool = False
    juridica_pf: bool = False
    fiscal_certidao_federal: bool = False
    fiscal_certidao_estadual: bool = False
    fiscal_certidao_municipal: bool = False
    fiscal_cndt: bool = False
    fiscal_fgts: bool = False
    tecnica_opcao: Optional[str] = None      # "A" | "B"
    tecnica_requisitos: Optional[str] = None
    econom_opcao: Optional[str] = None       # "A" | "B" | "C" | "D" | "E"
    econom_justificativa: Optional[str] = None
    econom_percentual_d: Optional[float] = None


class DivulgacaoExtraida(BaseModel):
    opcao: Optional[str] = None              # "A" | "B"
    justificativa_a: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    prazo_dias_uteis: Optional[int] = None


class BaseLegalExtraida(BaseModel):
    cita_lei_14133_2021: bool = False
    artigo_inciso: Optional[str] = None      # "art. 75, inciso I" | "art. 75, inciso II"


class TRBase(BaseModel):
    """Campos comuns a TR Serviços e TR Aquisições (modelos MPBA Jan/2026)."""
    objeto: Optional[str] = None
    justificativa_quantitativo: Optional[str] = None
    fundamentacao: Optional[str] = None
    descricao_solucao: Optional[str] = None
    base_legal: BaseLegalExtraida = BaseLegalExtraida()
    divulgacao: DivulgacaoExtraida = DivulgacaoExtraida()
    habilitacao: HabilitacaoExtraida = HabilitacaoExtraida()
    contem_texto_verde: bool = False
    contem_texto_roxo: bool = False
    responsavel_nome: Optional[str] = None
    responsavel_assinatura: Optional[str] = None
    declara_nao_bem_de_luxo: bool = False
    # Apenso I – obrigatório em ambos os tipos de TR (modelo MPBA Jan/2026)
    apenso_i_presente: bool = False
    # Prazo mínimo entre NE e início: ≥ 10 du (Ato Normativo MPBA 048/2024)
    prazo_nota_empenho_dias_uteis: Optional[int] = None
    # Formalização – seção 1.6 (Serviços) / 1.7 (Aquisições)
    # "A" = NE/instrumento substitutivo (correto para DL sem contrato)
    # "B" = instrumento formal de contrato (INCONFORME para DL sem contrato)
    # "C" | "D" = ATA (INCONFORME para DL sem contrato)
    formalizacao_opcao: Optional[str] = None
    blocos_texto: list[str] = []
    # Texto bruto do documento – preservado para análise por IA
    texto_original: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# TR – SERVIÇOS
# ─────────────────────────────────────────────────────────────────────────────

class TRServicosExtraido(TRBase):
    """TR Serviços – campos conforme modelo MPBA Jan/2026."""
    tipo_tr: Literal["SERVICOS"] = "SERVICOS"

    # Item 1.2 – Código de Serviços (CATSER) / Ramo de Atividade (PDM)
    codigo_pdm_servicos: Optional[str] = None
    # Item 1.3 – Natureza do Objeto
    # "A" = imediata/pontual/por escopo | "B" = parcelada
    # "C" = continuada (exige subopcao C.1–C.4 e justificativa)
    natureza_objeto: Optional[str] = None
    natureza_objeto_c_subopcao: Optional[str] = None   # "C1"|"C2"|"C3"|"C4"
    natureza_objeto_c_justificativa: Optional[str] = None
    # Engenharia (quando aplicável – sem seção dedicada no modelo geral)
    eh_engenharia: bool = False
    engenharia_b1: Optional[str] = None          # descrição técnica
    engenharia_b2: Optional[str] = None          # ART/RRT
    # Item 3.1 – Regime de Execução
    # "A" = empreitada preço global | "B" = empreitada preço unitário | "C" = outro
    regime_execucao: Optional[str] = None
    # Item 3.2 – Prazo para Retirada da Nota de Empenho (≥ 10 du – Ato Normativo 048/2024)
    prazo_nota_empenho: Optional[int] = None     # dias úteis
    # Item 3.3.1 – Local de Execução
    local_execucao: Optional[str] = None
    cep_execucao: Optional[str] = None
    vigencia_dias: Optional[int] = None
    # Item 3.4 – Prazo(s) de Execução
    prazo_execucao_dias: Optional[int] = None
    # Item 3.5 – Regras de Garantia do Serviço
    # "A" = CDC não aplicável | "B" = garantia legal (CDC) | "C" = garantia contratada
    # "D" = híbrido (legal + contratada) | "E" = definições no Apenso II
    garantia_opcao: Optional[str] = None
    garantia_justificativa: Optional[str] = None  # obrigatória para C e D
    # Item 3.6 – Subcontratação
    # "A" = vedada | "B" = admitida parcialmente
    subcontratacao_opcao: Optional[str] = None
    # Item 3.13 – Vigência da Contratação
    vigencia_opcao: Optional[str] = None
    # Item 3.16 – Garantia Contratual (performance bond – caução/seguro-garantia)
    # "A" = não será exigida | "B" = será exigida (percentual ≤ 5%, excep. até 10%)
    garantia_contratual_opcao: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# TR – AQUISIÇÕES
# ─────────────────────────────────────────────────────────────────────────────

class TRAquisicoesExtraido(TRBase):
    """TR Aquisições – campos conforme modelo MPBA Jan/2026."""
    tipo_tr: Literal["AQUISICOES"] = "AQUISICOES"

    # Item 1.2 – Código de Material (CATMAT) e Marca/Modelo
    codigo_catmat: Optional[str] = None
    marca_modelo_opcao: Optional[str] = None     # "A" | "B" | "C"
    marca_modelo_justificativa: Optional[str] = None
    # Item 1.3 – Justificativa da quantidade
    justificativa_quantidade: Optional[str] = None
    # Item 1.4 – Natureza do Objeto
    # "A" = fornecimento imediato | "B" = fornecimento parcelado
    # "C" = fornecimento continuado (exige justificativa)
    natureza_objeto: Optional[str] = None
    natureza_objeto_c_justificativa: Optional[str] = None  # obrigatória para C
    # Item 3.1 – Prazo para Retirada da Nota de Empenho (≥ 10 du – Ato Normativo 048/2024)
    prazo_nota_empenho: Optional[int] = None     # dias úteis
    # Item 3.2.1 – Prazo de Entrega
    prazo_entrega_horas: Optional[int] = None    # quando especificado em horas
    # Item 3.2.4 – Local de Entrega
    local_entrega: Optional[str] = None
    cep_entrega: Optional[str] = None
    vigencia_dias: Optional[int] = None
    # Item 3.3 – Regras sobre Montagem
    # "A" = entregues montados | "B" = desmontados | "C" = desmontados com montagem
    montagem_opcao: Optional[str] = None
    # Item 3.4 – Regras para Instalação
    # "A" = sem instalação | "B" = com instalação
    instalacao_opcao: Optional[str] = None
    # Item 3.6.1 – Regras de Garantia
    # "A" = não se aplica (CDC não aplicável) | "B" = garantia legal (CDC)
    # "C" = garantia contratada (todos os itens) | "D" = híbrido (legal + contratada)
    # "E" = definições no Apenso II
    garantia_opcao: Optional[str] = None
    garantia_justificativa: Optional[str] = None  # obrigatória para C e D
    # Item 3.7 – Subcontratação
    # "A" = vedada | "B" = admitida parcialmente
    subcontratacao_opcao: Optional[str] = None
    # Item 3.14 – Vigência da Contratação
    vigencia_opcao: Optional[str] = None         # "A" (sem instrumento formal) | "B" (com instrumento)


# ─────────────────────────────────────────────────────────────────────────────
# Schema unificado com discriminador
# ─────────────────────────────────────────────────────────────────────────────

TRUnificado = Annotated[
    Union[TRServicosExtraido, TRAquisicoesExtraido],
    Field(discriminator="tipo_tr"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Extrator heurístico
# ─────────────────────────────────────────────────────────────────────────────

_CHECKBOX = r"(?:\(\s*[xX✓✔☒]\s*\)|\[\s*[xX✓✔☒]\s*\]|☑|☒|✓\s*|✔\s*)"

# Padrão de CEP flexível: cobre XX.XXX-XXX, XXXXX-XXX, XXXXX XXX, XXXXXXXX
_PAT_CEP = r"\d{2}\.?\d{3}[-\s]?\d{3}"


def _extrair_cep(texto: str, campo_endereco: Optional[str] = None) -> Optional[str]:
    """Extrai CEP do texto completo ou do campo de endereço.

    Cobre formatos:
    - ``CEP: 41220-145``       (padrão)
    - ``CEP: 41.220-145``      (ponto como separador de milhar)
    - ``CEP: 41220 145``       (espaço)
    - CEP embutido no endereço sem rótulo 'CEP' (busca ``XXXXX-XXX`` no campo)
    """
    # Com rótulo "CEP" em qualquer parte do texto
    m = re.search(r"cep\s*[:\-]?\s*(" + _PAT_CEP + r")", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: dígitos no formato NNNNN-NNN embutidos no campo endereço
    if campo_endereco:
        m = re.search(r"\b(\d{5}-\d{3})\b", campo_endereco)
        if m:
            return m.group(1)
    return None


def _extrair_opcao_ab(
    texto: str,
    ancora: str,
    alternativas_b: list[str] | None = None,
    alternativas_a: list[str] | None = None,
) -> Optional[str]:
    """Detecta qual opção (A ou B) está marcada próximo a uma âncora textual.

    Primeiro procura checkbox + letra adjacente; como fallback, procura
    palavras-chave textuais que indicam a opção sem checkbox explícito.
    """
    # Checkbox direto: "Subcontratação [...] (X) B ..." — mesma linha
    m = re.search(
        ancora + r"[^\n]{0,100}" + _CHECKBOX + r"\s*([ABab])\b",
        texto, re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()
    # Checkbox invertido: "(X) B ... Subcontratação" — mesma linha
    m = re.search(
        _CHECKBOX + r"\s*([ABab])\b[^\n]{0,60}" + ancora,
        texto, re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()
    # Checkbox nas linhas seguintes ao cabeçalho da seção (até 5 linhas)
    # Cobre modelos onde a seção tem o título numa linha e "(X) A" / "( ) B" nas seguintes.
    m = re.search(
        ancora + r"[^\n]*(?:\n[^\n]{0,160}){0,5}" + _CHECKBOX + r"\s*([ABab])\b",
        texto, re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()
    # Fallback textual
    if alternativas_b:
        for alt in alternativas_b:
            if re.search(ancora + r"[^\n]{0,120}" + alt, texto, re.IGNORECASE):
                return "B"
            # span de até 3 linhas
            if re.search(ancora + r"[^\n]*(?:\n[^\n]{0,120}){0,3}" + alt, texto, re.IGNORECASE):
                return "B"
    if alternativas_a:
        for alt in alternativas_a:
            if re.search(ancora + r"[^\n]{0,120}" + alt, texto, re.IGNORECASE):
                return "A"
            if re.search(ancora + r"[^\n]*(?:\n[^\n]{0,120}){0,3}" + alt, texto, re.IGNORECASE):
                return "A"
    return None


def extrair_tr(texto: str, tipo: str, blocos_texto: Optional[list[str]] = None) -> TRUnificado:
    """Extrai campos do TR a partir do texto classificado."""

    def buscar(pattern: str) -> Optional[str]:
        m = re.search(pattern, texto, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    # ── Objeto (seção 1.1) ────────────────────────────────────────────────────
    # Tenta: numeração de seção + linha seguinte; cabeçalho sem número; após dois-pontos
    objeto = buscar(r"1[.\s]+1[^\n]*\n\s*([^\n]{10,300})")
    if not objeto:
        objeto = buscar(r"objeto\s+da\s+contrata[çc][aã]o\s*[:\-]?\s*\n\s*([^\n]{10,300})")
    if not objeto:
        objeto = buscar(r"objeto\s+da\s+contrata[çc][aã]o\s*[:\-]\s*([^\n]{10,300})")
    if not objeto:
        # fallback: primeira linha de conteúdo após o cabeçalho "Objeto"
        objeto = buscar(r"\bobjeto\b[^\n]{0,80}\n\s*([^\n]{15,300})")

    # ── Fundamentação / justificativa ─────────────────────────────────────────
    fundamentacao = buscar(
        r"(?:fundamenta[çc][aã]o|justificativa\s+da\s+contrata[çc][aã]o)\s*[:\-]?\s*\n\s*([^\n]{20,})"
    )
    if not fundamentacao:
        fundamentacao = buscar(
            r"(?:fundamenta[çc][aã]o|justificativa\s+da\s+contrata[çc][aã]o)\s*[:\-]\s*([^\n]{20,})"
        )

    # ── Descrição da solução ──────────────────────────────────────────────────
    descricao_solucao = buscar(
        r"descri[çc][aã]o\s+da\s+solu[çc][aã]o\s*[:\-]?\s*\n\s*([^\n]{20,})"
    )
    if not descricao_solucao:
        descricao_solucao = buscar(
            r"descri[çc][aã]o\s+da\s+solu[çc][aã]o\s*[:\-]\s*([^\n]{20,})"
        )

    # ── Justificativa do quantitativo ─────────────────────────────────────────
    justificativa_quant = buscar(
        r"justificativa\s+(?:do\s+)?quantitativo\s*[:\-]?\s*([^\n]{10,})"
    )

    # ── Responsável pelo TR ───────────────────────────────────────────────────
    # Última ocorrência de nome próprio após "Responsável" (OCR pode variar)
    responsavel = buscar(
        r"respons[aá]vel\s+(?:pelo\s+preenchimento|pela\s+elabora[çc][aã]o)?\s*[:\n]+\s*"
        r"([A-ZÁÉÍÓÚÀÃÕÂÊÔÇÜ][^\n]{5,80})"
    )
    if not responsavel:
        # Fallback: linha após "Responsável:" sem discriminar rótulo
        responsavel = buscar(
            r"respons[aá]vel\s*[:\-]\s*([A-ZÁÉÍÓÚÀÃÕÂÊÔÇÜ][a-záéíóúàãõâêôçü\s]{5,60})"
        )

    # ── Base legal (Lei 14.133/2021) ──────────────────────────────────────────
    # OCR pode suprimir pontuação: "14133/2021", "14 133/2021", "14.133/2021"
    cita_lei = bool(re.search(r"14[.\s]?133[\s/]?2021", texto, re.IGNORECASE))

    artigo = None
    # Padrão flexível para OCR: "art. 75", "art 75", "artigo 75" + "inciso I/II" ou "II" direto.
    # OCR frequentemente renderiza "II" como "I I" (com espaço) — por isso usa i\s*i.
    # Verifica "inciso II" ANTES de "inciso I" (II é mais específico).
    _75_INCISO_II = [
        r"art[^\n]{0,25}75[^\n]{0,40}inc\w*\s+i\s*i\b",  # "inciso II" / "inc. II"
        r"art[^\n]{0,25}75[^\n]{0,20}[,\s]\s*i\s*i\b",   # "Art. 75, II" (sem "inciso")
        r"75[^\n]{0,60}inc\w*\s+i\s*i\b",
        r"75[^\n]{0,40}[,\s]\s*i\s*i\b",
    ]
    _75_INCISO_I = [
        r"art[^\n]{0,25}75[^\n]{0,40}inc\w*\s+i\b(?!\s*i)",
        r"art[^\n]{0,25}75[^\n]{0,20}[,\s]\s*i\b(?!\s*i)",
        r"75[^\n]{0,60}inc\w*\s+i\b(?!\s*i)",
    ]
    for pat in _75_INCISO_II:
        if re.search(pat, texto, re.IGNORECASE):
            artigo = "art. 75, inciso II"
            break
    if not artigo:
        for pat in _75_INCISO_I:
            if re.search(pat, texto, re.IGNORECASE):
                artigo = "art. 75, inciso I"
                break

    # ── Divulgação (seção 2.1.2 — modelo antigo / B.2 — modelo novo) ───────────
    # Modelo antigo: seção "2.1.2", opções A (não publicar) e B (publicar).
    # Modelo novo  : seção "B.2 – DIVULGAÇÃO DE AVISO PARA COTAÇÃO NO PORTAL MPBA",
    #                opções  I (NÃO, com justificativa) e II (SIM, com e-mail/tel/prazo).
    # Internamente mantemos "A"=não publicar e "B"=publicar para consistência.
    div_opcao = None

    # Blocos de contexto — cobrem ambos os modelos
    _DIV_BLOCO_V1 = r"2[.\s]1[.\s]2(?:[^\n]*\n){0,7}"
    _DIV_BLOCO_V2 = r"B\.?\s*2\b[^\n]{0,80}(?:[^\n]*\n){0,10}"
    _DIV_ANCORA   = r"divulga[çc][aã]o[^\n]{0,80}(?:portal|aviso|cota[çc][aã]o)?(?:[^\n]*\n){0,7}"

    # ── Modelo novo (B.2): checkbox + II/SIM → publicar; checkbox + I/NÃO → não publicar
    # Testa modelo novo PRIMEIRO para evitar que "I" roman numeral dispare A no modelo antigo.
    _novo_sim = (
        _DIV_BLOCO_V2
        + r"(?:" + _CHECKBOX + r"[^\n]{0,30}\bII\b|\bII\b[^\n]{0,30}" + _CHECKBOX + r")"
    )
    _novo_nao = (
        _DIV_BLOCO_V2
        + r"(?:" + _CHECKBOX + r"[^\n]{0,30}\bI\b(?!I)|\bI\b(?!I)[^\n]{0,30}" + _CHECKBOX + r")"
    )
    if re.search(_novo_sim, texto, re.IGNORECASE):
        div_opcao = "B"
    elif re.search(_novo_nao, texto, re.IGNORECASE):
        div_opcao = "A"

    # ── Modelo antigo (2.1.2): checkbox + B → publicar; checkbox + A → não publicar
    if div_opcao is None:
        if re.search(
            _DIV_BLOCO_V1 + r"(?:" + _CHECKBOX + r"[^\n]{0,50}\b[Bb]\b|\b[Bb]\b[^\n]{0,50}" + _CHECKBOX + r")"
            r"|" + _CHECKBOX + r"\s*\b[Bb]\b[^\n]{0,80}portal"
            r"|portal[^\n]{0,60}" + _CHECKBOX + r"\s*\b[Bb]\b"
            r"|op[çc][aã]o\s+[Bb]\b",
            texto, re.IGNORECASE,
        ):
            div_opcao = "B"
        elif re.search(
            _DIV_ANCORA + r"(?:" + _CHECKBOX + r"[^\n]{0,50}\b[Bb]\b|\b[Bb]\b[^\n]{0,50}" + _CHECKBOX + r")",
            texto, re.IGNORECASE,
        ):
            div_opcao = "B"
        elif re.search(
            _DIV_BLOCO_V1 + r"(?:" + _CHECKBOX + r"[^\n]{0,50}\b[Aa]\b|\b[Aa]\b[^\n]{0,50}" + _CHECKBOX + r")"
            r"|n[aã]o[^\n]{0,60}portal\s+mpba"
            r"|n[aã]o\s+publicar[^\n]{0,60}portal",
            texto, re.IGNORECASE,
        ):
            div_opcao = "A"
        elif re.search(
            _DIV_ANCORA + r"(?:" + _CHECKBOX + r"[^\n]{0,50}\b[Aa]\b|\b[Aa]\b[^\n]{0,50}" + _CHECKBOX + r")",
            texto, re.IGNORECASE,
        ):
            div_opcao = "A"

    # ── Fallback semântico (qualquer modelo): "publicar no Portal MPBA" / "SIM"
    if div_opcao is None:
        if re.search(
            r"publicar[^\n]{0,80}portal\s+mpba"
            r"|portal\s+mpba[^\n]{0,80}publicar"
            r"|sim[^\n]{0,60}portal\s+mpba",
            texto, re.IGNORECASE,
        ):
            div_opcao = "B"

    # ── Divulgação – campos da Opção B/II (e-mail, telefone, prazo) ──────────
    # Extrai contexto a partir da âncora da seção (até 30 linhas).
    # Tenta modelo novo (B.2) primeiro; se não encontrar, usa 2.1.2.
    _m_div_ctx = re.search(
        r"B\.?\s*2\b[^\n]{0,80}(?:\n[^\n]*){0,30}",
        texto, re.IGNORECASE,
    )
    if not _m_div_ctx:
        _m_div_ctx = re.search(
            r"2[.\s]1[.\s]2[^\n]*(?:\n[^\n]*){0,25}",
            texto, re.IGNORECASE,
        )
    _div_ctx = _m_div_ctx.group(0) if _m_div_ctx else ""

    def _buscar_div(pattern: str) -> Optional[str]:
        """Busca no bloco 2.1.2 primeiro; fallback para busca global."""
        if _div_ctx:
            m = re.search(pattern, _div_ctx, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return buscar(pattern)

    # Prioridade: e-mail com domínio institucional @mpba.mp.br; fallback qualquer e-mail.
    # Inclui variante OCR onde "@" é lido como "O"/"0" com ou sem espaço antes do domínio.
    _PAT_EMAIL_MPBA     = r"[a-zA-Z0-9._%+\-]+@mpba\.mp\.br"
    _PAT_EMAIL_ANY      = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    # Captura o e-mail garbled inteiro num único grupo (para compatibilidade com _buscar_div)
    _PAT_EMAIL_MPBA_OCR = r"([a-zA-Z0-9._%+\-]+[O0o][ \t]*mpba\.mp\.br)"

    def _normalizar_email_ocr(raw: str) -> Optional[str]:
        """Reconstrói e-mail cujo '@' foi corrompido pelo OCR (lido como O/0 + espaço)."""
        m = re.match(r"^([a-zA-Z0-9._%+\-]+)[O0o][ \t]*(mpba\.mp\.br)$", raw.strip(), re.IGNORECASE)
        if m:
            return f"{m.group(1)}@{m.group(2).lower()}"
        return None

    email = _buscar_div(r"e[\-\s]?mail\s*[:\-]?\s*(" + _PAT_EMAIL_MPBA + r")")
    if not email:
        email = _buscar_div(r"(" + _PAT_EMAIL_MPBA + r")")
    if not email:
        # Tenta capturar variante OCR (@ lido como O/0 + espaço) e normaliza
        _raw_ocr = _buscar_div(r"e[\-\s]?mail\s*[:\-]?\s*(" + _PAT_EMAIL_MPBA_OCR + r")")
        if not _raw_ocr:
            _raw_ocr = _buscar_div(r"(" + _PAT_EMAIL_MPBA_OCR + r")")
        if _raw_ocr:
            email = _normalizar_email_ocr(_raw_ocr) or _raw_ocr
    if not email:
        email = _buscar_div(r"e[\-\s]?mail\s*[:\-]?\s*(" + _PAT_EMAIL_ANY + r")")
    if not email:
        email = _buscar_div(r"(" + _PAT_EMAIL_ANY + r")")

    telefone = _buscar_div(r"(?:telefone|fone|tel\.?)\s*[:\-]?\s*(\(?\d{2}\)?\s*\d{4,5}[\-\s]\d{4})")
    if not telefone:
        telefone = _buscar_div(r"(\(?\d{2}\)?\s*\d{4,5}[\-\s]\d{4})")

    # Prazo em dias úteis – múltiplos formatos usados no modelo MPBA
    prazo_du = None
    _PRAZO_DIV_PATS = [
        r"prazo\s*[:\-]?\s*(\d+)\s*\(?[^\)\n]{0,25}\)?\s*dias?\s*[úu]teis",
        r"prazo\s+(?:de\s+)?(?:m[íi]nimo\s+de\s+)?(\d+)\s*dias?\s*[úu]teis",
        r"prazo\s+(?:de\s+)?(?:m[íi]nimo\s+de\s+)?(\d+)\s*d\.?\s*u\.?",
        r"(\d+)\s*\(?(?:tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|quinze|vinte)\)?\s*dias?\s*[úu]teis",
        r"(?:receb(?:imento|er)\s+propostas?)[^\n]{0,40}(\d+)\s*dias?\s*[úu]teis",
        r"(\d+)\s*dias?\s*[úu]teis[^\n]{0,40}(?:propost|receb)",
        r"prazo\s*[:\-]?\s*(\d+)\s*dias?\s*[úu]teis",
    ]
    for _pat in _PRAZO_DIV_PATS:
        _scope = _div_ctx if _div_ctx else texto
        _m = re.search(_pat, _scope, re.IGNORECASE)
        if not _m and _div_ctx:
            _m = re.search(_pat, texto, re.IGNORECASE)
        if _m:
            try:
                prazo_du = int(_m.group(1))
                break
            except (ValueError, IndexError):
                pass

    # ── Habilitação – fiscal/social ───────────────────────────────────────────
    hab = HabilitacaoExtraida(
        fiscal_certidao_federal=bool(
            re.search(
                r"certid[aã]o[^\n]{0,60}(?:federal|receita|pgfn|rfb)"
                r"|d[ií]vida\s+ativa\s+da\s+uni[aã]o"
                r"|certid[aã]o\s+conjunta",
                texto, re.IGNORECASE,
            )
        ),
        fiscal_certidao_estadual=bool(
            re.search(
                r"certid[aã]o[^\n]{0,60}estadual"
                r"|fazenda\s+estadual"
                r"|fazenda\s+p[úu]blica\s+do\s+estado"
                r"|secretaria\s+(?:de\s+estado\s+)?da\s+fazenda"
                r"|regularidade\s+fiscal[^\n]{0,60}estado"
                r"|estado\s+da\s+bahia[^\n]{0,40}certid",
                texto, re.IGNORECASE,
            )
        ),
        fiscal_certidao_municipal=bool(
            re.search(r"certid[aã]o[^\n]{0,60}municipal|fazenda\s+municipal|issqn", texto, re.IGNORECASE)
        ),
        fiscal_cndt=bool(
            re.search(r"\bcndt\b|d[eé]bitos\s+trabalhistas|tst\.jus\.br", texto, re.IGNORECASE)
        ),
        fiscal_fgts=bool(
            re.search(r"\bfgts\b|\bcrf\b|certificado\s+de\s+regularidade", texto, re.IGNORECASE)
        ),
        juridica_pj=bool(re.search(r"pessoa\s+jur[ií]dica", texto, re.IGNORECASE)),
        juridica_pf=bool(re.search(r"pessoa\s+f[ií]sica", texto, re.IGNORECASE)),
    )

    # ── Apenso I ──────────────────────────────────────────────────────────────
    # O Apenso I é uma tabela de itens/serviços sempre ao FINAL do TR.
    # Estratégia em dois níveis:
    #  1. Busca pelo heading explícito em qualquer parte do texto.
    # Nível 1 – heading explícito "APENSO I" (ou variações OCR)
    # Nível 2 – título da tabela indicativa (exclusivo do modelo MPBA Jan/2026)
    # Nível 3 – colunas CATSER/CATMAT/PDM (exclusivas do Apenso I)
    # Nível 4 – estrutura ITEM + DESCRIÇÃO DO BEM/SERVIÇO + UNIDADE + QUANTIDADE
    #
    # IMPORTANTE: o Apenso I NÃO tem coluna de VALOR — a detecção por valor foi
    # removida pois causava falso negativo em todo processo.
    apenso_i = bool(re.search(
        r"ap[eê]\s*nso\s*i\b"           # "APENSO I" — forma canônica
        r"|ap[eê]\s*nso\s+[1l]\b"       # OCR: "APENSO 1" ou "APENSO l"
        r"|ap[eê]ndice\s+i\b"           # "Apêndice I"
        r"|conforme\s+apenso|vide\s+apenso",
        texto, re.IGNORECASE,
    ))

    if not apenso_i:
        # Nível 2: título da tabela — presente nos dois modelos MPBA Jan/2026
        # Serviços: "TABELA INDICATIVA DOS ITENS DE SERVIÇO A SEREM CONTRATADOS"
        # Aquisições: "TABELA INDICATIVA DOS ITENS A SEREM FORNECIDOS"
        apenso_i = bool(re.search(
            r"tabela\s+indicativa\s+dos\s+itens"
            r"|itens?\s+(?:de\s+servi[çc]o\s+)?a\s+serem\s+(?:contratados?|fornecidos?|executados?)",
            texto, re.IGNORECASE,
        ))

    if not apenso_i:
        # Nível 3: colunas de código exclusivas do Apenso I
        # Serviços: "CATSER" | Aquisições: "CATMAT" e "PDM"
        texto_final = texto[-6000:] if len(texto) > 6000 else texto
        tem_catser_catmat = bool(re.search(
            r"\bcat\s*ser\b|\bcatser\b|\bcat\s*mat\b|\bcatmat\b",
            texto_final, re.IGNORECASE,
        ))
        tem_pdm = bool(re.search(r"\bpdm\b", texto_final, re.IGNORECASE))
        apenso_i = tem_catser_catmat or tem_pdm

    if not apenso_i:
        # Nível 4: estrutura das colunas da tabela sem "VALOR"
        # Ambos os modelos têm: ITEM | DESCRIÇÃO DO BEM/SERVIÇO | UNIDADE | QUANTIDADE
        texto_final = texto[-6000:] if len(texto) > 6000 else texto
        tem_descricao_col = bool(re.search(
            r"descri[çc][aã]o\s+do\s+(?:bem|servi[çc]o|item)",
            texto_final, re.IGNORECASE,
        ))
        tem_item_qtd = bool(re.search(
            r"\bitem\b[^\n]{0,150}\b(?:quantidade|quant\.?|qtd\.?)\b"
            r"|\bitem\b[^\n]{0,150}\bunidade\b",
            texto_final, re.IGNORECASE,
        ))
        apenso_i = tem_descricao_col and tem_item_qtd

    # ── Prazo NE em dias úteis (≥ 10 du – Ato Normativo 048/2024) ────────────
    prazo_ne = None
    m_ne = re.search(
        r"prazo\s+(?:para\s+)?(?:in[íi]cio|retirada|entrega|execu[çc][ãa]o)"
        r"[^\n]{0,60}?(\d+)\s*(?:dias?\s*[úu]teis?|du\b)",
        texto, re.IGNORECASE,
    )
    if m_ne:
        prazo_ne = int(m_ne.group(1))
    elif prazo_du and prazo_du >= 10:
        prazo_ne = prazo_du

    # ── Formalização (seção 1.6 Serviços / 1.7 Aquisições) ───────────────────
    # Opção A = NE/instrumento substitutivo | B = instrumento formal | C/D = ATA
    formalizacao_opc = None
    # Busca checkbox na mesma linha OU nas próximas 5 linhas após "formalização"
    m_form = re.search(
        r"formaliza[çc][aã]o[^\n]{0,80}" + _CHECKBOX + r"\s*([A-Da-d])\b"
        r"|formaliza[çc][aã]o[^\n]*(?:\n[^\n]{0,160}){0,5}" + _CHECKBOX + r"\s*([A-Da-d])\b",
        texto, re.IGNORECASE,
    )
    if m_form:
        formalizacao_opc = (m_form.group(1) or m_form.group(2) or "").upper() or None
    if not formalizacao_opc:
        m_form2 = re.search(
            r"(?:1[.\s][67][^\n]{0,60}formaliz|formaliz[^\n]{0,30}1[.\s][67])[^\n]*(?:\n[^\n]{0,160}){0,5}"
            + _CHECKBOX + r"\s*([A-Da-d])\b",
            texto, re.IGNORECASE,
        )
        if m_form2:
            formalizacao_opc = m_form2.group(1).upper()
        elif re.search(
            r"nota\s+de\s+empenho[^\n]{0,60}instrumento\s+substitutivo"
            r"|instrumento\s+substitutivo[^\n]{0,60}nota\s+de\s+empenho",
            texto, re.IGNORECASE,
        ):
            formalizacao_opc = "A"

    # ── Justificativa da forma não eletrônica (art. 75, §3º) ─────────────────
    # Modelo novo: seção "B.1 – JUSTIFICATIVA:" dentro do bloco
    #   "B – DISPENSA NÃO ELETRÔNICA (TRADICIONAL)"
    # Modelo antigo: justificativa após a opção A da seção 2.1.2.
    just_nao_eletronico = buscar(
        # Modelo novo: B.1 - JUSTIFICATIVA: <texto>
        r"B\.?\s*1\s*[-–]?\s*JUSTIFICATIVA\s*[:\-]\s*([^\n]{10,})"
    )
    if not just_nao_eletronico:
        just_nao_eletronico = buscar(
            # Variação: "B.1" seguido de linha com conteúdo (label na linha anterior)
            r"B\.?\s*1\s*[-–]?\s*JUSTIFICATIVA[^\n]*\n\s*([^\n]{10,})"
        )
    if not just_nao_eletronico:
        # Modelo antigo: rótulo explícito de justificativa forma não eletrônica
        just_nao_eletronico = buscar(
            r"justificativa[^\n]{0,60}(?:forma\s+n[aã]o\s+eletr[oô]nica|n[aã]o\s+eletr[oô]nica"
            r"|dispensa\s+(?:n[aã]o\s+eletr[oô]nica|tradicional))[^\n]*[:\-]\s*([^\n]{10,})"
        )
    if not just_nao_eletronico:
        # Modelo antigo (2.1.2 A): opção A com justificativa na mesma linha
        just_nao_eletronico = buscar(
            r"2[.\s]1[.\s]2[^\n]{0,80}[Aa]\b[^\n]{0,30}justificativa\s*[:\-]\s*([^\n]{10,})"
        )
    if not just_nao_eletronico and fundamentacao:
        # Modelo antigo: a justificativa para a forma não eletrônica está no
        # texto corrido da Fundamentação Legal (seção 2.1) — não existe campo rotulado.
        # A fundamentação ela mesma é a justificativa exigida pelo art. 75, §3º.
        just_nao_eletronico = fundamentacao[:200]

    base = TRBase(
        objeto=objeto,
        fundamentacao=fundamentacao,
        descricao_solucao=descricao_solucao,
        justificativa_quantitativo=justificativa_quant,
        responsavel_nome=responsavel,
        base_legal=BaseLegalExtraida(
            cita_lei_14133_2021=cita_lei,
            artigo_inciso=artigo,
        ),
        divulgacao=DivulgacaoExtraida(
            opcao=div_opcao,
            email=email,
            telefone=telefone,
            prazo_dias_uteis=prazo_du,
        ),
        habilitacao=hab,
        declara_nao_bem_de_luxo=bool(
            re.search(r"ato\s+normativo.*004/2024|bem\s+de\s+luxo|n[aã]o\s+[eé]\s+bem\s+de\s+luxo", texto, re.IGNORECASE)
        ),
        apenso_i_presente=apenso_i,
        prazo_nota_empenho_dias_uteis=prazo_ne,
        formalizacao_opcao=formalizacao_opc,
        blocos_texto=blocos_texto or [texto],
        texto_original=texto,
    )

    if tipo == "TR_AQUISICOES":
        catmat = buscar(r"(?:c[oó]digo\s+(?:de\s+)?material|catmat)\s*[:\-]?\s*(\d[\d\s\-.]+)")
        justi_qtd = buscar(
            r"justificativa\s+(?:da\s+quantidade|do\s+quantitativo"
            r"|do\s+quantitativo\s+definido)\s*[:\-]?\s*([^\n]+)"
        ) or buscar(r"1[.\s]3[^\n]{0,60}justificativa[^\n]{0,40}\n\s*([^\n]{10,})")

        # Prazo de entrega em horas (quando especificado)
        prazo_horas = None
        m_h = re.search(r"prazo.*?(\d+)\s*horas?", texto, re.IGNORECASE)
        if m_h:
            prazo_horas = int(m_h.group(1))

        # Natureza do Objeto (seção 1.4) – A: imediato | B: parcelado | C: continuado
        natureza_opc = None
        m_nat = re.search(
            r"1\.4\s+natureza\s+do\s+objeto\s*[:\-]?\s*[^\n]*\(\s*[xX]\s*\)\s*([A-Ca-c])",
            texto, re.IGNORECASE,
        )
        if m_nat:
            natureza_opc = m_nat.group(1).upper()
        else:
            if re.search(r"\(\s*[xX]\s*\)\s*[Cc][^\n]*(?:fornecimento\s+continuado|continuado)", texto, re.IGNORECASE):
                natureza_opc = "C"
            elif re.search(r"\(\s*[xX]\s*\)\s*[Bb][^\n]*(?:fornecimento\s+parcelado|parcelado)", texto, re.IGNORECASE):
                natureza_opc = "B"
            elif re.search(r"\(\s*[xX]\s*\)\s*[Aa][^\n]*(?:fornecimento\s+imediato|imediato)", texto, re.IGNORECASE):
                natureza_opc = "A"

        natureza_c_just = buscar(
            r"(?:1\.4.*continuado|fornecimento\s+continuado)\s*[:\-]?\s*[Ii]nserir[^\n]*\n([^\n]{20,})"
        )

        # Subcontratação (seção 3.7) – A: vedada | B: admitida parcialmente
        subcontrat_aq = _extrair_opcao_ab(
            texto,
            r"subcontrata[çc][aã]o",
            alternativas_b=[r"admitida\s+parcialmente"],
            alternativas_a=[r"vedada"],
        )

        # Montagem (seção 3.3) – A: entregues montados | B: desmontados | C: c/ montagem
        montagem_opc = None
        m_mont = re.search(
            r"3[.\s]3[^\n]{0,60}montagem[^\n]{0,80}" + _CHECKBOX + r"\s*([A-Ca-c])\b",
            texto, re.IGNORECASE,
        )
        if m_mont:
            montagem_opc = m_mont.group(1).upper()
        else:
            if re.search(_CHECKBOX + r"[^\n]{0,10}[Cc][^\n]{0,60}desmontados?\s+com\s+montagem", texto, re.IGNORECASE):
                montagem_opc = "C"
            elif re.search(_CHECKBOX + r"[^\n]{0,10}[Bb][^\n]{0,60}(?:desmontados?|sem\s+montagem)", texto, re.IGNORECASE):
                montagem_opc = "B"
            elif re.search(_CHECKBOX + r"[^\n]{0,10}[Aa][^\n]{0,60}(?:montados?|j[aá]\s+montados?)", texto, re.IGNORECASE):
                montagem_opc = "A"

        # Instalação (seção 3.4) – A: sem instalação | B: com instalação
        instalacao_opc = _extrair_opcao_ab(
            texto,
            r"instala[çc][aã]o",
            alternativas_b=[r"com\s+instala[çc][aã]o", r"instala[çc][aã]o\s+pelo\s+fornecedor"],
            alternativas_a=[r"sem\s+instala[çc][aã]o", r"n[aã]o\s+requer"],
        )

        # Garantia do produto (seção 3.6.1) – A/B/C/D/E
        garantia_opc = None
        m_gar = re.search(
            r"(?:garantia\s+do\s+produto|3[.\s]6[^\n]{0,60}garantia)[^\n]{0,80}" + _CHECKBOX + r"\s*([A-Ea-e])\b",
            texto, re.IGNORECASE,
        )
        if m_gar:
            garantia_opc = m_gar.group(1).upper()
        else:
            m_gar2 = re.search(
                r"garantia[^\n]{0,60}" + _CHECKBOX + r"\s*([A-Ea-e])\b"
                r"|garantia[^\n]{0,40}opç[aã]o\s+([A-Ea-e])\b",
                texto, re.IGNORECASE,
            )
            if m_gar2:
                garantia_opc = (m_gar2.group(1) or m_gar2.group(2)).upper()

        garantia_just = buscar(r"justificativa.*?garantia\s*[:\-]?\s*([^\n]{10,})")

        # Vigência – A: sem instrumento formal | B: com instrumento formal
        vigencia_opc = _extrair_opcao_ab(
            texto,
            r"vig[eê]ncia",
            alternativas_b=[r"instrumento\s+formal"],
            alternativas_a=[r"at[eé]\s+12\s+meses", r"sem\s+instrumento\s+formal"],
        )

        local_entrega_val = buscar(r"local\s+(?:\(is\)\s+)?de\s+entrega\s*[:\-]?\s*([^\n]+)")

        return TRAquisicoesExtraido(
            **base.model_dump(),
            codigo_catmat=catmat,
            marca_modelo_opcao=(
                buscar(r"(?:1[.\s]2[^\n]{0,40}marca|marca\s+e?\s*modelo)[^\n]{0,60}" + _CHECKBOX + r"\s*([A-Ca-c])\b")
                or buscar(r"marca\s+e?\s*modelo[^\n]{0,40}op[cç][aã]o\s*([A-Ca-c])\b")
                # checkbox na linha seguinte ao título da seção 1.2
                or buscar(r"1[.\s]2[^\n]*(?:marca|indica[çc][aã]o)[^\n]*\n(?:[^\n]*\n){0,2}" + _CHECKBOX + r"\s*([A-Ca-c])\b")
            ),
            marca_modelo_justificativa=buscar(
                r"justificativa.*?marca.*?modelo\s*[:\-]?\s*([^\n]+)"
            ),
            justificativa_quantidade=justi_qtd,
            natureza_objeto=natureza_opc,
            natureza_objeto_c_justificativa=natureza_c_just,
            prazo_nota_empenho=prazo_ne,
            prazo_entrega_horas=prazo_horas,
            local_entrega=local_entrega_val,
            cep_entrega=_extrair_cep(texto, local_entrega_val),
            montagem_opcao=montagem_opc,
            instalacao_opcao=instalacao_opc,
            garantia_opcao=garantia_opc,
            garantia_justificativa=garantia_just,
            subcontratacao_opcao=subcontrat_aq,
            vigencia_opcao=vigencia_opc,
        )

    # TR Serviços
    pdm = buscar(r"c[oó]digo\s+(?:de\s+)?servi[cç]os?\s*[:\-]?\s*(\d[\d\s\-.]+)")
    if not pdm:
        pdm = buscar(r"pdm\s*[:\-]?\s*(\d[\d\s\-.]+)")

    # Natureza do Objeto (seção 1.3) – A: imediata/pontual | B: parcelada | C: continuada
    nat_serv = None
    m_nat_s = re.search(
        r"1[.\s]3[^\n]{0,60}natureza[^\n]{0,80}" + _CHECKBOX + r"\s*([A-Ca-c])\b",
        texto, re.IGNORECASE,
    )
    if m_nat_s:
        nat_serv = m_nat_s.group(1).upper()
    else:
        if re.search(_CHECKBOX + r"[^\n]{0,10}[Cc][^\n]{0,60}(?:continuad|servi[cç]os?\s+continuad)", texto, re.IGNORECASE):
            nat_serv = "C"
        elif re.search(_CHECKBOX + r"[^\n]{0,10}[Bb][^\n]{0,60}parcelad", texto, re.IGNORECASE):
            nat_serv = "B"
        elif re.search(_CHECKBOX + r"[^\n]{0,10}[Aa][^\n]{0,60}(?:imediata|pontual|escopo)", texto, re.IGNORECASE):
            nat_serv = "A"

    nat_c_sub = buscar(r"opc[aã]o\s+(c[.\s]?[1-4])\b")
    nat_c_just = buscar(r"justificativa\s*(?:para\s+enquadramento.*?continuad[oa]?)\s*[:\-]?\s*([^\n]{20,})")

    # Prazo de execução dos serviços (seção 3.4 – distinto do prazo NE)
    prazo_exec = None
    m_pex = re.search(
        r"(?:3[.\s]4[^\n]{0,60}prazo|prazo\s+(?:de\s+)?execu[çc][aã]o)\s*[:\-]?\s*(\d+)\s*(?:dias?|meses?)",
        texto, re.IGNORECASE,
    )
    if m_pex:
        prazo_exec = int(m_pex.group(1))
    if not prazo_exec:
        m_pex2 = re.search(
            r"prazo[^\n]{0,40}execu[çc][aã]o[^\n]{0,60}?(\d+)\s*(?:dias?|meses?)"
            r"|(\d+)\s*(?:dias?|meses?)[^\n]{0,40}execu[çc][aã]o",
            texto, re.IGNORECASE,
        )
        if m_pex2:
            prazo_exec = int(m_pex2.group(1) or m_pex2.group(2))

    # Regime de Execução (seção 3.1) – A: preço global | B: preço unitário | C: outro
    regime_exec = None
    m_reg = re.search(
        r"3[.\s]1[^\n]{0,80}" + _CHECKBOX + r"\s*([A-Ca-c])\b",
        texto, re.IGNORECASE,
    )
    if m_reg:
        regime_exec = m_reg.group(1).upper()
    else:
        if re.search(r"regime[^\n]{0,60}(?:pre[çc]o\s+global|empreitada\s+(?:por\s+)?pre[çc]o\s+global)", texto, re.IGNORECASE):
            regime_exec = "A"
        elif re.search(r"regime[^\n]{0,60}(?:pre[çc]o\s+unit[aá]rio|empreitada\s+(?:por\s+)?pre[çc]o\s+unit[aá]rio)", texto, re.IGNORECASE):
            regime_exec = "B"

    # Garantia do Serviço (seção 3.5) – A/B/C/D/E
    garantia_serv = None
    m_gar_s = re.search(
        r"(?:3[.\s]5[^\n]{0,60}garantia|garantia\s+do\s+servi[cç]o)[^\n]{0,80}" + _CHECKBOX + r"\s*([A-Ea-e])\b",
        texto, re.IGNORECASE,
    )
    if m_gar_s:
        garantia_serv = m_gar_s.group(1).upper()
    else:
        m_gar_s2 = re.search(
            r"garantia[^\n]{0,60}" + _CHECKBOX + r"\s*([A-Ea-e])\b"
            r"|garantia[^\n]{0,40}opç[aã]o\s+([A-Ea-e])\b",
            texto, re.IGNORECASE,
        )
        if m_gar_s2:
            garantia_serv = (m_gar_s2.group(1) or m_gar_s2.group(2)).upper()

    garantia_just_serv = buscar(r"justificativa.*?garantia\s*[:\-]?\s*([^\n]{10,})")

    # Garantia Contratual (seção 3.16) – A: não exigida | B: exigida
    garantia_contrat = None
    if re.search(
        r"garantia\s+contratual[^\n]{0,80}" + _CHECKBOX + r"\s*[Bb]\b"
        r"|3[.\s]16[^\n]{0,80}" + _CHECKBOX + r"\s*[Bb]\b",
        texto, re.IGNORECASE,
    ):
        garantia_contrat = "B"
    elif re.search(
        r"garantia\s+contratual[^\n]{0,80}" + _CHECKBOX + r"\s*[Aa]\b"
        r"|3[.\s]16[^\n]{0,80}" + _CHECKBOX + r"\s*[Aa]\b"
        r"|n[aã]o\s+ser[aá]\s+exigida\s+garantia\s+contratual",
        texto, re.IGNORECASE,
    ):
        garantia_contrat = "A"

    # Subcontratação – A: vedada | B: admitida parcialmente
    subcontrat = _extrair_opcao_ab(
        texto,
        r"subcontrata[çc][aã]o",
        alternativas_b=[r"admitida\s+parcialmente"],
        alternativas_a=[r"vedada", r"n[aã]o.*(?:admitida|permitida)"],
    )

    # Vigência – A: sem instrumento formal | B: com instrumento formal
    vigencia_opc = _extrair_opcao_ab(
        texto,
        r"vig[eê]ncia",
        alternativas_b=[r"instrumento\s+formal"],
        alternativas_a=[r"at[eé]\s+12\s+meses", r"sem\s+instrumento\s+formal"],
    )

    # Local de execução – mais flexível para OCR
    local_exec = buscar(r"local\s*(?:\(is\)\s+)?de\s+execu[cç][aã]o\s*(?:dos\s+servi[cç]os?)?\s*[:\-]\s*([^\n]{5,200})")
    if not local_exec:
        local_exec = buscar(r"local\s+de\s+execu[cç][aã]o\s*\n\s*([^\n]{5,200})")

    return TRServicosExtraido(
        **base.model_dump(),
        codigo_pdm_servicos=pdm,
        natureza_objeto=nat_serv,
        natureza_objeto_c_subopcao=nat_c_sub,
        natureza_objeto_c_justificativa=nat_c_just,
        eh_engenharia=bool(
            re.search(r"servi[cç]os?\s+de\s+engenharia", texto, re.IGNORECASE)
        ),
        engenharia_b1=buscar(r"b[.\s]1\s*[:\-]?\s*([^\n]+)"),
        engenharia_b2=buscar(r"b[.\s]2\s*[:\-]?\s*([^\n]+)"),
        regime_execucao=regime_exec,
        prazo_nota_empenho=prazo_ne,
        local_execucao=local_exec,
        cep_execucao=_extrair_cep(texto, local_exec),
        prazo_execucao_dias=prazo_exec,
        garantia_opcao=garantia_serv,
        garantia_justificativa=garantia_just_serv,
        subcontratacao_opcao=subcontrat,
        vigencia_opcao=vigencia_opc,
        garantia_contratual_opcao=garantia_contrat,
    )
