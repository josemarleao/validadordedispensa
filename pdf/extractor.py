"""Extração de texto de PDF – estratégia híbrida por página com fallback OCR.

Pipeline:
  1. pymupdf   – executa em todo o PDF (rápido, melhor ToUnicode)
  2. pdfplumber – executa em todo o PDF (melhor para tabelas)
  3. Fusão por página: escolhe o extrator com maior score de qualidade por página
  4. pdftotext  – fallback global se os dois anteriores falharem totalmente
  5. OCR        – apenas para páginas com texto ausente ou encoding corrompido,
                  com pré-processamento Pillow para máxima qualidade
"""

from __future__ import annotations
import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False
    log.warning("pdfplumber não instalado.")

try:
    import fitz  # pymupdf
    _PYMUPDF_OK = True
except ImportError:
    _PYMUPDF_OK = False
    log.warning("pymupdf não instalado.")

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    _OCR_OK = True
except ImportError:
    _OCR_OK = False
    log.warning("pdf2image/pytesseract não instalados – OCR indisponível.")

try:
    from PIL import Image, ImageFilter, ImageEnhance
    _PILLOW_OK = True
except ImportError:
    _PILLOW_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Estruturas de dados
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PaginaExtraida:
    numero: int
    texto: str
    via_ocr: bool = False
    tem_texto: bool = False

    def __post_init__(self) -> None:
        self.texto = _sanitizar(self.texto)
        self.tem_texto = bool(self.texto.strip())


@dataclass
class DocumentoExtraido:
    """Agrupamento de páginas classificadas como um mesmo documento."""
    tipo: str
    paginas: list[int]
    texto_completo: str
    confianca: float = 0.0
    metadados: dict = field(default_factory=dict)
    textos_paginas: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Sanitização e qualidade de texto
# ─────────────────────────────────────────────────────────────────────────────

_PALAVRAS_PT = {
    "de", "da", "do", "das", "dos", "para", "que", "com", "por", "em",
    "no", "na", "nos", "nas", "um", "uma", "os", "as", "ao",
    "se", "nao", "ou", "e", "ser", "ter", "seu", "sua",
    "este", "esta", "mais", "como", "mas", "foi",
    "pela", "pelo", "pelos", "pelas", "entre", "apos", "ate", "sem",
    "processo", "contrato", "valor", "prazo", "data", "objeto",
    "servico", "empresa", "fiscal", "gestor", "termo", "referencia",
    "dispensa", "licitacao", "unidade", "demandante", "proposta",
    "documento", "assinatura", "cargo", "nome", "total", "item",
}


def _sanitizar(texto: str) -> str:
    """Remove bytes de controle e normaliza whitespace."""
    if not texto:
        return ""
    # Remove null bytes e caracteres de controle (exceto \t, \n, \r, \f)
    texto = re.sub(r"[\x00-\x08\x0b\x0e-\x1f\x7f]", "", texto)
    # Normaliza form-feed para newline
    texto = texto.replace("\f", "\n")
    # Colapsa espaços múltiplos na mesma linha
    linhas = [re.sub(r"[ \t]{2,}", " ", linha) for linha in texto.splitlines()]
    # Remove linhas com só espaços
    linhas = [ln.rstrip() for ln in linhas]
    # Reune, colapsando mais de 2 newlines consecutivas
    resultado = "\n".join(linhas)
    resultado = re.sub(r"\n{3,}", "\n\n", resultado)
    return resultado.strip()


def _score_texto(texto: str) -> float:
    """Score de qualidade do texto extraído (0.0 = inútil, 1.0 = excelente).

    Combina comprimento, proporção alfa-numérica e presença de palavras PT.
    Usado para escolher entre dois candidatos de extração para a mesma página.
    """
    if not texto or not texto.strip():
        return 0.0

    # Bytes de controle = encoding corrompido → score zero
    if re.search(r"[\x00-\x08\x0b\x0e-\x1f\x7f]", texto):
        return 0.0

    chars = [c for c in texto if not c.isspace()]
    if not chars:
        return 0.0

    alnum = sum(1 for c in chars if c.isalnum())
    proporcao_alnum = alnum / len(chars)

    # Texto com proporção alfa-numérica muito baixa = símbolos aleatórios
    if proporcao_alnum < 0.20:
        return 0.0

    # Score de comprimento (cap em 3000 chars)
    score_len = min(len(texto.strip()) / 3000, 1.0)

    # Score de qualidade alfa-numérica
    score_qual = min(proporcao_alnum, 1.0)

    # Score de presença de palavras PT (cap em 10 hits)
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    palavras = re.findall(r"[a-z]{2,}", sem_acento)
    if palavras:
        hits = sum(1 for p in palavras if p in _PALAVRAS_PT)
        score_pt = min(hits / 10, 1.0)
    else:
        score_pt = 0.0

    return round(score_len * 0.35 + score_qual * 0.40 + score_pt * 0.25, 4)


def _texto_garbled(texto: str) -> bool:
    """Retorna True se o texto está ausente ou com encoding corrompido.

    Usado como gatilho para OCR — mais preciso que _texto_legivel porque
    não penaliza páginas legítimas com conteúdo predominantemente numérico
    (tabelas de preços, certidões, planilhas).
    """
    if not texto or not texto.strip():
        return True

    if re.search(r"[\x00-\x08\x0b\x0e-\x1f\x7f]", texto):
        return True

    chars = [c for c in texto if not c.isspace()]
    if not chars:
        return True

    alnum = sum(1 for c in chars if c.isalnum())
    # Proporção alfa-numérica < 20% → provável garbage
    if alnum / len(chars) < 0.20:
        return True

    # Menos de 15 letras no texto inteiro = praticamente sem conteúdo real
    letras = sum(1 for c in chars if c.isalpha())
    if letras < 15:
        return True

    return False


def _texto_legivel(texto: str) -> bool:
    """Retorna True se o texto contém vocabulário português reconhecível.

    Critério relaxado vs. versão anterior: aceita 5 palavras PT (era 8) e
    15% de proporção (era 20%). Isso evita que páginas com tabelas numéricas
    sejam falsamente classificadas como ilegíveis.
    """
    if not texto.strip():
        return False
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    palavras = re.findall(r"[a-z]{2,}", sem_acento)
    if not palavras:
        return False
    hits = sum(1 for p in palavras if p in _PALAVRAS_PT)
    proporcao = hits / len(palavras)
    return hits >= 5 and proporcao >= 0.15


# ─────────────────────────────────────────────────────────────────────────────
# Fusão por página
# ─────────────────────────────────────────────────────────────────────────────

def _fusionar_melhores(
    a: list[PaginaExtraida],
    b: list[PaginaExtraida],
) -> list[PaginaExtraida]:
    """Para cada página, escolhe a extração com maior score de qualidade.

    Se um candidato tiver score > outro por margem de 0.05, troca.
    Garante que o melhor de dois extratores seja usado página a página.
    """
    b_idx = {p.numero: p for p in b}
    resultado: list[PaginaExtraida] = []

    for pa in a:
        pb = b_idx.get(pa.numero)
        if pb is None:
            resultado.append(pa)
            continue
        sa = _score_texto(pa.texto)
        sb = _score_texto(pb.texto)
        if sb > sa + 0.05:
            # pdfplumber claramente melhor para esta página
            resultado.append(pb)
        else:
            resultado.append(pa)

    # Páginas presentes em b mas ausentes em a (raro mas possível)
    a_nums = {p.numero for p in a}
    for pb in b:
        if pb.numero not in a_nums:
            resultado.append(pb)

    resultado.sort(key=lambda p: p.numero)
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────

def extrair_paginas(pdf_bytes: bytes, ocr_enabled: bool = True) -> list[PaginaExtraida]:
    """Extrai texto de cada página do PDF com estratégia em cascata robusta.

    Estratégia (ordem de velocidade/qualidade):
    1. pymupdf   – roda sempre; melhor suporte ToUnicode (SEI/Word), muito rápido.
    2. pdfplumber – roda SOMENTE para páginas onde pymupdf deu baixa qualidade
                    (score < 0.30). Evita dobrar o tempo de extração em PDFs normais.
    3. pdftotext  – fallback global quando ambos falharam totalmente.
    4. OCR        – apenas para páginas com texto ausente ou encoding corrompido.
    """
    if not _PDFPLUMBER_OK and not _PYMUPDF_OK:
        raise RuntimeError("Nenhum extrator de PDF instalado (pdfplumber ou pymupdf).")

    # ── Passo 1: pymupdf (sempre, rápido) ─────────────────────────────────────
    paginas: list[PaginaExtraida] = []
    if _PYMUPDF_OK:
        paginas = _extrair_via_pymupdf(pdf_bytes)

    # ── Passo 2: pdfplumber seletivo para páginas de baixa qualidade ──────────
    # Threshold 0.30: página com score abaixo disso tem texto insuficiente
    # ou mal estruturado pelo pymupdf; vale o custo de tentar pdfplumber.
    _SCORE_MINIMO = 0.30
    paginas_ruins = [p for p in paginas if _score_texto(p.texto) < _SCORE_MINIMO]

    if paginas_ruins and _PDFPLUMBER_OK:
        log.info(
            "pymupdf baixa qualidade em %d/%d pág(s) (score<%.2f) — tentando pdfplumber.",
            len(paginas_ruins), len(paginas), _SCORE_MINIMO,
        )
        candidatos_plumber = _extrair_via_pdfplumber(pdf_bytes)
        if candidatos_plumber:
            plumber_idx = {p.numero: p for p in candidatos_plumber}
            melhorias = 0
            for i, p in enumerate(paginas):
                if _score_texto(p.texto) < _SCORE_MINIMO:
                    pb = plumber_idx.get(p.numero)
                    if pb and _score_texto(pb.texto) > _score_texto(p.texto) + 0.05:
                        paginas[i] = pb
                        melhorias += 1
            if melhorias:
                log.info("pdfplumber melhorou %d pág(s).", melhorias)

    # ── Passo 2b: pdfplumber global quando pymupdf falhou completamente ────────
    elif not paginas and _PDFPLUMBER_OK:
        log.info("pymupdf não produziu páginas — tentando pdfplumber.")
        paginas = _extrair_via_pdfplumber(pdf_bytes)

    # ── Passo 3: pdftotext fallback global ────────────────────────────────────
    if not paginas or not any(p.tem_texto for p in paginas):
        candidato = _extrair_via_pdftotext(pdf_bytes)
        if candidato and any(_texto_legivel(p.texto) for p in candidato):
            log.info("Fallback pdftotext produziu texto legível.")
            paginas = candidato

    if not paginas:
        log.warning("Nenhum extrator nativo produziu páginas.")

    # OCR seletivo — páginas sem texto ou com encoding corrompido (sem palavras PT).
    # Usa _texto_legivel (com limiares relaxados: 5 palavras PT, 15%) para detectar
    # encoding customizado do SEI/Word que produz ASCII embaralhado mas passa em
    # _texto_garbled. Páginas genuinamente numéricas (tabelas de preços) podem ir
    # para OCR desnecessariamente, mas o resultado é equivalente ao texto nativo.
    paginas_para_ocr = [
        p for p in paginas
        if not p.tem_texto or not _texto_legivel(p.texto)
    ]

    n_total = len(paginas)
    n_ocr   = len(paginas_para_ocr)

    if paginas_para_ocr:
        if ocr_enabled and _OCR_OK:
            log.info(
                "%d/%d página(s) com texto ausente/corrompido → OCR.",
                n_ocr, n_total,
            )
            for pag in paginas_para_ocr:
                try:
                    imagens = convert_from_bytes(
                        pdf_bytes,
                        dpi=250,  # 250 dpi: melhor qualidade que 200 sem pico de memória
                        first_page=pag.numero,
                        last_page=pag.numero,
                    )
                    if imagens:
                        img = _preprocessar_ocr(imagens[0])
                        pag.texto = pytesseract.image_to_string(
                            img,
                            lang="por",
                            config="--oem 3 --psm 1",  # LSTM + auto layout
                        )
                        pag.via_ocr = True
                        pag.texto = _sanitizar(pag.texto)
                        pag.tem_texto = bool(pag.texto.strip())
                    del imagens
                except Exception as exc:
                    log.warning("OCR falhou na página %d: %s", pag.numero, exc)
        elif not ocr_enabled:
            log.info("%d pág(s) precisariam de OCR mas OCR está desabilitado.", n_ocr)
        else:
            log.warning("%d pág(s) precisam de OCR mas pytesseract não está instalado.", n_ocr)

    # Último recurso: pdfplumber puro sem validação (mantém estrutura mesmo sem texto)
    if not paginas and _PDFPLUMBER_OK:
        log.warning("Nenhuma extração funcionou — forçando pdfplumber sem validação.")
        paginas = _extrair_via_pdfplumber(pdf_bytes)

    log.info(
        "Extração concluída: %d pág. total | %d nativas legíveis | %d via OCR | %d vazias.",
        len(paginas),
        sum(1 for p in paginas if not p.via_ocr and p.tem_texto),
        sum(1 for p in paginas if p.via_ocr),
        sum(1 for p in paginas if not p.tem_texto),
    )
    return paginas


# ─────────────────────────────────────────────────────────────────────────────
# Pré-processamento de imagem para OCR
# ─────────────────────────────────────────────────────────────────────────────

def _preprocessar_ocr(img: "Image.Image") -> "Image.Image":
    """Aplica pré-processamento Pillow para melhorar a qualidade do OCR.

    Etapas:
    1. Converte para escala de cinza
    2. Aumenta contraste (Tesseract performa melhor em texto com bom contraste)
    3. Leve sharpening para texto borrado
    """
    if not _PILLOW_OK:
        return img
    try:
        img = img.convert("L")                          # escala de cinza
        img = ImageEnhance.Contrast(img).enhance(1.8)   # aumenta contraste
        img = img.filter(ImageFilter.SHARPEN)            # nitidez
        return img
    except Exception as exc:
        log.debug("Pré-processamento OCR falhou (usando imagem original): %s", exc)
        return img


# ─────────────────────────────────────────────────────────────────────────────
# Extratores individuais
# ─────────────────────────────────────────────────────────────────────────────

def _extrair_via_pymupdf(pdf_bytes: bytes) -> list[PaginaExtraida]:
    """Extrai texto via pymupdf — melhor suporte a ToUnicode customizado (SEI/Word)."""
    paginas: list[PaginaExtraida] = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        log.info("pymupdf: PDF com %d página(s).", doc.page_count)
        for i, page in enumerate(doc):
            txt = page.get_text("text") or ""
            paginas.append(PaginaExtraida(numero=i + 1, texto=txt))
        doc.close()
    except Exception as exc:
        log.warning("pymupdf falhou: %s", exc)
    return paginas


def _extrair_via_pdftotext(pdf_bytes: bytes) -> list[PaginaExtraida]:
    """Usa pdftotext (Poppler) como fallback — lida bem com fontes customizadas."""
    import subprocess
    import tempfile
    import os

    paginas: list[PaginaExtraida] = []
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", "-enc", "UTF-8", tmp_path, "-"],
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                return []
            texto_completo = result.stdout.decode("utf-8", errors="replace")
        finally:
            os.unlink(tmp_path)

        partes = texto_completo.split("\f")
        total = len([p for p in partes if p.strip()])
        log.info("pdftotext: PDF com %d página(s).", total)
        for i, parte in enumerate(partes):
            if not parte.strip() and i == len(partes) - 1:
                continue
            paginas.append(PaginaExtraida(numero=i + 1, texto=parte))
    except FileNotFoundError:
        log.debug("pdftotext não está instalado.")
    except Exception as exc:
        log.warning("pdftotext falhou: %s", exc)
    return paginas


def _extrair_via_pdfplumber(pdf_bytes: bytes) -> list[PaginaExtraida]:
    """Extrai texto via pdfplumber — melhor suporte a tabelas e layouts complexos.
    
    Com timeout por página (5s) para evitar travamento em PDFs corrompidos/complexos.
    """
    import asyncio
    import threading
    
    paginas: list[PaginaExtraida] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            log.info("pdfplumber: PDF com %d página(s).", len(pdf.pages))
            for i, page in enumerate(pdf.pages):
                txt = ""
                try:
                    # Extrai com timeout de 5 segundos por página
                    def _extract_safe():
                        return page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                    
                    # Usa threading com timeout para evitar travamento
                    result = [None]
                    def wrapper():
                        result[0] = _extract_safe()
                    
                    thread = threading.Thread(target=wrapper, daemon=True)
                    thread.start()
                    thread.join(timeout=5.0)  # 5 segundos por página
                    
                    if thread.is_alive():
                        log.warning("pdfplumber: timeout na página %d (>5s)", i + 1)
                        txt = ""
                    else:
                        txt = result[0] or ""
                        
                except Exception as exc:
                    log.warning("pdfplumber: falha na página %d: %s", i + 1, exc)
                    txt = ""
                finally:
                    page.flush_cache()
                paginas.append(PaginaExtraida(numero=i + 1, texto=txt))
    except Exception as exc:
        log.warning("pdfplumber falhou: %s", exc)
    return paginas


# ─────────────────────────────────────────────────────────────────────────────
# Limpeza pós-extração
# ─────────────────────────────────────────────────────────────────────────────

def texto_limpo(texto: str) -> str:
    """Limpeza final do texto após extração e OCR.

    - Remove artefatos de OCR comuns (hifens de quebra de linha)
    - Remove linhas duplicadas consecutivas (cabeçalhos repetidos por OCR)
    - Normaliza espaçamento
    """
    if not texto:
        return ""

    # Normaliza form-feed
    texto = texto.replace("\f", "\n")

    # Une palavras quebradas com hífen no fim da linha (artefato OCR)
    texto = re.sub(r"-\s*\n\s*", "", texto)

    # Colapsa espaços múltiplos (mantém newlines)
    texto = re.sub(r"[ \t]{2,}", " ", texto)

    # Colapsa mais de 2 newlines consecutivas
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    # Remove linhas que são só pontos, traços ou underscores (separadores OCR)
    texto = re.sub(r"^[\.\-_=]{4,}\s*$", "", texto, flags=re.MULTILINE)

    return texto.strip()
