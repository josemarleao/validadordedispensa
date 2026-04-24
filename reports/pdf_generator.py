"""Geração do Relatório de Saneamento em PDF via ReportLab."""

from __future__ import annotations
import io
from datetime import date
from schemas.responses import RelatorioSaneamento, StatusRegra

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False

# Cores institucionais
_AZUL_MPBA    = colors.HexColor("#003366")
_CINZA_CLARO  = colors.HexColor("#F2F2F2")
_VERDE        = colors.HexColor("#1A7A1A")
_VERMELHO     = colors.HexColor("#CC0000")
_AMARELO_PEND = colors.HexColor("#CC7700")
_BRANCO       = colors.white


def gerar_pdf_relatorio(relatorio: RelatorioSaneamento) -> bytes:
    """Gera o Relatório de Saneamento em PDF e retorna os bytes."""
    if not _REPORTLAB_OK:
        raise RuntimeError("reportlab não instalado. Execute: pip install reportlab")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Relatório de Saneamento – {relatorio.processo}",
    )

    estilos = getSampleStyleSheet()
    # Estilos customizados
    est_titulo = ParagraphStyle(
        "Titulo",
        parent=estilos["Title"],
        fontSize=14,
        textColor=_AZUL_MPBA,
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    est_subtitulo = ParagraphStyle(
        "Subtitulo",
        parent=estilos["Normal"],
        fontSize=10,
        textColor=_AZUL_MPBA,
        spaceAfter=2,
        alignment=TA_CENTER,
    )
    est_secao = ParagraphStyle(
        "Secao",
        parent=estilos["Heading2"],
        fontSize=11,
        textColor=_AZUL_MPBA,
        spaceBefore=10,
        spaceAfter=4,
    )
    est_normal = ParagraphStyle(
        "Normal2",
        parent=estilos["Normal"],
        fontSize=9,
        spaceAfter=2,
    )
    est_rodape = ParagraphStyle(
        "Rodape",
        parent=estilos["Normal"],
        fontSize=7,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )

    story = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    story.append(Paragraph("MINISTÉRIO PÚBLICO DO ESTADO DA BAHIA – MPBA", est_titulo))
    story.append(Paragraph("Assessoria de Contratações – Saneamento Automatizado por IA", est_subtitulo))
    story.append(HRFlowable(width="100%", thickness=2, color=_AZUL_MPBA))
    story.append(Spacer(1, 0.3 * cm))

    # ── Identificação do processo ─────────────────────────────────────────────
    story.append(Paragraph("RELATÓRIO DE SANEAMENTO", est_secao))
    dados_id = [
        ["Processo SEI:", relatorio.processo],
        ["Tipo:", relatorio.tipo],
        ["Data do Relatório:", date.today().strftime("%d/%m/%Y")],
        ["Encaminhamento:", relatorio.encaminhamento.value],
    ]
    tbl_id = Table(dados_id, colWidths=[5 * cm, 12 * cm])
    tbl_id.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_CINZA_CLARO, _BRANCO]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_id)

    # ── Resumo ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("RESUMO", est_secao))
    dados_res = [
        ["Inconformidades", "Pendências", "Conformes", "Total de Verificações"],
        [
            Paragraph(f'<font color="#{_hex(_VERMELHO)}"><b>{relatorio.resumo.inconformidades}</b></font>', est_normal),
            Paragraph(f'<font color="#{_hex(_AMARELO_PEND)}"><b>{relatorio.resumo.pendencias}</b></font>', est_normal),
            Paragraph(f'<font color="#{_hex(_VERDE)}"><b>{relatorio.resumo.conformes}</b></font>', est_normal),
            str(relatorio.resumo.inconformidades + relatorio.resumo.pendencias + relatorio.resumo.conformes),
        ],
    ]
    tbl_res = Table(dados_res, colWidths=[4.25 * cm] * 4)
    tbl_res.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL_MPBA),
        ("TEXTCOLOR",  (0, 0), (-1, 0), _BRANCO),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl_res)

    # ── Documentos Conformes ──────────────────────────────────────────────────
    if relatorio.documentos_conformes:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("DOCUMENTOS CONFORMES", est_secao))
        for doc in relatorio.documentos_conformes:
            story.append(Paragraph(f"✓  {doc}", est_normal))

    # ── Inconformidades ───────────────────────────────────────────────────────
    if relatorio.inconformidades:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("INCONFORMIDADES", est_secao))
        header = ["#", "Documento", "Item", "Descrição", "Providência"]
        dados = [header]
        for i, inc in enumerate(relatorio.inconformidades, 1):
            dados.append([
                str(i),
                inc.documento,
                inc.item,
                Paragraph(inc.descricao, est_normal),
                inc.providencia.value,
            ])
        story.append(_tabela_resultados(dados, _VERMELHO))

    # ── Pendências ────────────────────────────────────────────────────────────
    if relatorio.pendencias:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("PENDÊNCIAS", est_secao))
        header = ["#", "Documento", "Item", "Descrição", "Providência"]
        dados = [header]
        for i, pend in enumerate(relatorio.pendencias, 1):
            dados.append([
                str(i),
                pend.documento,
                pend.item,
                Paragraph(pend.descricao, est_normal),
                pend.providencia.value,
            ])
        story.append(_tabela_resultados(dados, _AMARELO_PEND))

    # ── Observações ───────────────────────────────────────────────────────────
    if relatorio.observacoes:
        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        story.append(Paragraph(f"<i>{relatorio.observacoes}</i>", est_normal))

    # ── Rodapé ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=_AZUL_MPBA))
    story.append(Paragraph(
        f"Documento gerado automaticamente por Inteligência Artificial – MPBA Saneamento DL  |  "
        f"Gerado em {date.today().strftime('%d/%m/%Y')}  |  "
        "Este relatório não substitui a análise técnico-jurídica humana.",
        est_rodape,
    ))

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hex(cor) -> str:
    """Retorna hex de 6 dígitos sem prefixo para uso em Paragraph markup."""
    # hexval() retorna '0xRRGGBB' – descartamos os 2 primeiros chars '0x'
    return cor.hexval()[2:]


def _tabela_resultados(dados: list, cor_header):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    t = Table(
        dados,
        colWidths=[0.7 * cm, 3.5 * cm, 3.5 * cm, 6.5 * cm, 3.0 * cm],
        repeatRows=1,
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), cor_header),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_CINZA_CLARO, _BRANCO]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("WORDWRAP",    (0, 0), (-1, -1), True),
    ]))
    return t
