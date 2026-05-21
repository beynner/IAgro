"""Geração de PDFs do módulo Vendas (Mai/2026 — 2026-05-21).

Dois layouts:
    - INDIVIDUAL: 1 página por pedido, idêntico ao do Sankhya (header + cliente
      + tabela CÓDIGO/DESCRIÇÃO/UN/QTD/VLR UNIT/CX + obs + totais).
    - CONSOLIDADO: 1 PDF agregado de N pedidos com tabela CÓDIGO/DESCRIÇÃO/UN/
      QTD TOTAL KG/QTD TOTAL CX/Nº PEDIDOS ordenado por CODPROD.

Dados de entrada vêm de ``oracle_conn.obter_dados_pedido_completo_para_impressao``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# Página A4 retrato
PAGE_W, PAGE_H = A4
MARGIN_L = 10 * mm
MARGIN_R = 10 * mm
MARGIN_T = 10 * mm
MARGIN_B = 10 * mm

CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


def _fmt_brl(v: float) -> str:
    """Formata número como R$ BR (1.234,56)."""
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.2f}"
    return s.replace(',', '#').replace('.', ',').replace('#', '.')


def _fmt_qtd(v: float, casas: int = 2) -> str:
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.{casas}f}"
    return s.replace(',', '#').replace('.', ',').replace('#', '.')


def _fmt_data(dt) -> str:
    if not dt:
        return ''
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%y %H:%M')
    s = str(dt)
    return s[:16]


def _fmt_cnpj(s: str) -> str:
    """Formata 14 dígitos como XX.XXX.XXX/XXXX-XX (ou retorna como veio)."""
    if not s:
        return ''
    digits = ''.join(ch for ch in str(s) if ch.isdigit())
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return str(s)


def _fmt_cep(s: str) -> str:
    if not s:
        return ''
    digits = ''.join(ch for ch in str(s) if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    return str(s)


def _draw_text(c, x: float, y: float, text: str, size: int = 9, bold: bool = False):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    c.drawString(x, y, text or '')


def _box(c, x: float, y: float, w: float, h: float, fill: tuple | None = None):
    """Retângulo com borda preta. fill opcional (R, G, B em 0-1)."""
    if fill:
        c.setFillColorRGB(*fill)
        c.rect(x, y, w, h, stroke=1, fill=1)
        c.setFillColorRGB(0, 0, 0)
    else:
        c.rect(x, y, w, h, stroke=1, fill=0)


# ============================================================================
# LAYOUT INDIVIDUAL — 1 página por pedido, igual ao Sankhya
# ============================================================================

def _render_pagina_individual(
    c: canvas.Canvas,
    dados: dict,
    pesos_fallback: dict | None = None,
) -> None:
    """Renderiza 1 pedido completo numa página do canvas atual.

    Se ``pesos_fallback`` for fornecido, itens com ``qtd_caixas=0`` recebem
    ``CEIL(qtdneg / peso_fallback[codprod])`` antes da renderização.
    """
    pedido  = dados['pedido']
    empresa = dados['empresa'] or {}
    cliente = dados['cliente'] or {}
    itens   = dados.get('itens') or []

    # Aplica fallback de pesos in-place (cópia rasa do item pra não mutar o dict original)
    if pesos_fallback:
        itens_ajustados = []
        for it in itens:
            it = dict(it)
            if not it.get('qtd_caixas'):
                peso_ref = pesos_fallback.get(it.get('codprod'))
                if peso_ref and peso_ref > 0:
                    qtd = float(it.get('qtdneg') or 0)
                    it['qtd_caixas'] = int(-(-qtd // peso_ref))
            itens_ajustados.append(it)
        itens = itens_ajustados

    y = PAGE_H - MARGIN_T

    # ---- Header: "PEDIDO DE VENDA" + Empresa + Número/Data ----
    header_h = 22 * mm
    _box(c, MARGIN_L, y - header_h, CONTENT_W, header_h)

    # Título centralizado superior direito
    c.setFont('Helvetica-Bold', 18)
    c.drawRightString(MARGIN_L + CONTENT_W - 5 * mm, y - 8 * mm, 'PEDIDO DE VENDA')

    # Empresa
    razao = (empresa.get('razao') or empresa.get('nome_fantasia') or '').strip()
    _draw_text(c, MARGIN_L + 3 * mm, y - 13 * mm,
               f"EMPRESA: {razao}", size=9, bold=True)

    # Linha número/data
    numnota_str = str(pedido.get('numnota') or pedido.get('nunota') or '')
    _draw_text(c, MARGIN_L + 3 * mm, y - 19 * mm,
               f"NÚMERO: {numnota_str}", size=9, bold=True)
    c.drawRightString(MARGIN_L + CONTENT_W - 5 * mm, y - 19 * mm,
                      f"DATA: {_fmt_data(pedido.get('dtneg'))}")

    y -= header_h

    # ---- Bloco cliente ----
    cliente_h = 26 * mm
    _box(c, MARGIN_L, y - cliente_h, CONTENT_W, cliente_h)

    cliente_label = f"{cliente.get('codparc')}-{(cliente.get('nome') or '').strip()}"
    if cliente.get('razao') and cliente.get('razao') != cliente.get('nome'):
        cliente_label += f" / {cliente.get('razao')}"
    _draw_text(c, MARGIN_L + 3 * mm, y - 5 * mm,
               f"CLIENTE: {cliente_label}", size=9, bold=True)

    # 2 colunas: esquerda (CNPJ/END/CIDADE/FONE) | direita (IE/BAIRRO/CEP/FAX)
    col_esq_x = MARGIN_L + 3 * mm
    col_dir_x = MARGIN_L + CONTENT_W / 2 + 3 * mm

    _draw_text(c, col_esq_x, y - 10 * mm,
               f"CNPJ: {_fmt_cnpj(cliente.get('cgc_cpf'))}", size=8, bold=True)
    _draw_text(c, col_dir_x, y - 10 * mm,
               f"IE: {cliente.get('ie') or ''}", size=8, bold=True)

    _draw_text(c, col_esq_x, y - 14 * mm,
               f"END: {cliente.get('endereco') or ''}", size=8, bold=True)
    _draw_text(c, col_dir_x, y - 14 * mm,
               f"BAIRRO: {cliente.get('bairro') or ''}", size=8, bold=True)

    cid = cliente.get('cidade') or ''
    uf  = cliente.get('uf') or ''
    cidade_uf = f"{cid}-{uf}" if uf else cid
    _draw_text(c, col_esq_x, y - 18 * mm,
               f"CIDADE: {cidade_uf}", size=8, bold=True)
    _draw_text(c, col_dir_x, y - 18 * mm,
               f"CEP: {_fmt_cep(cliente.get('cep'))}", size=8, bold=True)

    _draw_text(c, col_esq_x, y - 22 * mm,
               f"FONE: {cliente.get('fone') or ''}", size=8, bold=True)
    _draw_text(c, col_dir_x, y - 22 * mm,
               f"FAX: {cliente.get('fax') or ''}", size=8, bold=True)

    y -= cliente_h

    # ---- Header tabela: "PRODUTOS / SERVIÇOS" ----
    titulo_h = 5 * mm
    _box(c, MARGIN_L, y - titulo_h, CONTENT_W, titulo_h, fill=(0.85, 0.85, 0.85))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(MARGIN_L + CONTENT_W / 2, y - 3.5 * mm,
                        'PRODUTOS / SERVIÇOS')
    y -= titulo_h

    # ---- Cabeçalho colunas (CÓDIGO | DESCRIÇÃO | UN | QTD | VLR UNIT | CX) ----
    col_h    = 5 * mm
    col_x0   = MARGIN_L
    col_w_cod  = 16 * mm
    col_w_un   = 14 * mm
    col_w_qtd  = 22 * mm
    col_w_vlr  = 22 * mm
    col_w_cx   = 22 * mm
    col_w_desc = CONTENT_W - col_w_cod - col_w_un - col_w_qtd - col_w_vlr - col_w_cx

    cols = [
        ('CÓDIGO',   col_w_cod,  'C'),
        ('DESCRIÇÃO', col_w_desc, 'L'),
        ('UN',       col_w_un,   'C'),
        ('QTD',      col_w_qtd,  'R'),
        ('VLR UNIT', col_w_vlr,  'R'),
        ('CX',       col_w_cx,   'R'),
    ]

    _box(c, col_x0, y - col_h, CONTENT_W, col_h, fill=(0.92, 0.92, 0.92))
    c.setFont('Helvetica-Bold', 8)
    x_cursor = col_x0
    for nome, w, _align in cols:
        # linha vertical separadora
        if x_cursor > col_x0:
            c.line(x_cursor, y, x_cursor, y - col_h)
        c.drawCentredString(x_cursor + w / 2, y - 3.5 * mm, nome)
        x_cursor += w
    y -= col_h

    # ---- Linhas dos itens ----
    linha_h = 4.2 * mm
    c.setFont('Helvetica', 8)
    total_qtd_kg = 0.0
    total_qtd_cx = 0
    for it in itens:
        if y - linha_h < MARGIN_B + 30 * mm:  # reserva pro bloco de totais
            # Nova página — re-desenha header da tabela
            c.showPage()
            y = PAGE_H - MARGIN_T
            _box(c, col_x0, y - col_h, CONTENT_W, col_h, fill=(0.92, 0.92, 0.92))
            c.setFont('Helvetica-Bold', 8)
            x_cursor2 = col_x0
            for nome, w, _align in cols:
                if x_cursor2 > col_x0:
                    c.line(x_cursor2, y, x_cursor2, y - col_h)
                c.drawCentredString(x_cursor2 + w / 2, y - 3.5 * mm, nome)
                x_cursor2 += w
            y -= col_h
            c.setFont('Helvetica', 8)

        _box(c, col_x0, y - linha_h, CONTENT_W, linha_h)
        x_cursor = col_x0
        total_qtd_kg += float(it.get('qtdneg') or 0)
        total_qtd_cx += int(it.get('qtd_caixas') or 0)
        valores = [
            (str(it['codprod']),                    col_w_cod,  'C'),
            (it['descrprod'],                        col_w_desc, 'L'),
            (it['codvol'],                           col_w_un,   'C'),
            (_fmt_qtd(it['qtdneg'], casas=0),        col_w_qtd,  'R'),  # sem decimal
            (_fmt_qtd(it['vlrunit'], casas=2),       col_w_vlr,  'R'),
            (str(it['qtd_caixas']) if it['qtd_caixas'] else '', col_w_cx, 'R'),
        ]
        for txt, w, align in valores:
            if x_cursor > col_x0:
                c.line(x_cursor, y, x_cursor, y - linha_h)
            cx = x_cursor + w / 2
            cx_left = x_cursor + 1.5 * mm
            cx_right = x_cursor + w - 1.5 * mm
            ty = y - 3 * mm
            if align == 'L':
                c.drawString(cx_left, ty, str(txt or ''))
            elif align == 'R':
                c.drawRightString(cx_right, ty, str(txt or ''))
            else:
                c.drawCentredString(cx, ty, str(txt or ''))
            x_cursor += w

        y -= linha_h

    # ---- Linha de TOTAIS destacada (verde Agromil + borda superior espessa) ----
    if y - linha_h < MARGIN_B + 44 * mm:
        c.showPage()
        y = PAGE_H - MARGIN_T

    # Pequeno gap sutil entre o último produto e a linha de TOTAIS
    y -= 1.5 * mm

    total_h = 7 * mm
    # Fundo verde Agromil sutil
    _box(c, col_x0, y - total_h, CONTENT_W, total_h, fill=(0.86, 0.91, 0.83))
    # Borda superior espessa pra separar visualmente da tabela acima
    c.setLineWidth(1.8)
    c.line(col_x0, y, col_x0 + CONTENT_W, y)
    c.setLineWidth(0.5)  # restaura default pras próximas operações
    c.setFont('Helvetica-Bold', 10)
    x_cursor = col_x0
    valores_totais = [
        ('',                                            col_w_cod,  'C'),
        ('TOTAIS:',                                      col_w_desc, 'L'),
        ('',                                            col_w_un,   'C'),
        (_fmt_qtd(total_qtd_kg, casas=0),                col_w_qtd,  'R'),
        ('',                                            col_w_vlr,  'R'),
        (str(total_qtd_cx) if total_qtd_cx else '',     col_w_cx,   'R'),
    ]
    for txt, w, align in valores_totais:
        if x_cursor > col_x0:
            c.line(x_cursor, y, x_cursor, y - total_h)
        ty = y - 4.5 * mm
        if align == 'L':
            c.drawString(x_cursor + 1.5 * mm, ty, str(txt or ''))
        elif align == 'R':
            c.drawRightString(x_cursor + w - 1.5 * mm, ty, str(txt or ''))
        else:
            c.drawCentredString(x_cursor + w / 2, ty, str(txt or ''))
        x_cursor += w
    y -= total_h

    # Gap vertical pra separar a linha de TOTAIS do bloco OBSERVAÇÃO/TOTAIS abaixo
    y -= 5 * mm

    # ---- Espaço pra próxima página caso a tabela ocupou tudo ----
    if y - 32 * mm < MARGIN_B:
        c.showPage()
        y = PAGE_H - MARGIN_T

    # ---- Bloco final: Observação + Totais ----
    bloco_h = 30 * mm
    meio = MARGIN_L + CONTENT_W * 0.62

    # Esquerda — Observação
    _box(c, MARGIN_L, y - 5 * mm, meio - MARGIN_L, 5 * mm, fill=(0.85, 0.85, 0.85))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(MARGIN_L + (meio - MARGIN_L) / 2, y - 3.5 * mm, 'OBSERVAÇÃO')
    _box(c, MARGIN_L, y - bloco_h, meio - MARGIN_L, bloco_h - 5 * mm)
    obs = (pedido.get('observacao') or '').strip()
    if obs:
        # Quebra simples por largura
        c.setFont('Helvetica', 8)
        # divide em linhas de ~80 chars
        linhas_obs = []
        atual = ''
        for word in obs.split():
            if len(atual) + len(word) + 1 > 80:
                linhas_obs.append(atual)
                atual = word
            else:
                atual = f"{atual} {word}".strip()
        if atual:
            linhas_obs.append(atual)
        for idx, linha in enumerate(linhas_obs[:6]):
            c.drawString(MARGIN_L + 3 * mm, y - 9 * mm - idx * 4 * mm, linha)

    # Direita — Totais
    _box(c, meio, y - 5 * mm, CONTENT_W + MARGIN_L - meio, 5 * mm, fill=(0.85, 0.85, 0.85))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(meio + (CONTENT_W + MARGIN_L - meio) / 2, y - 3.5 * mm, 'TOTAIS')
    _box(c, meio, y - bloco_h, CONTENT_W + MARGIN_L - meio, bloco_h - 5 * mm)

    total_prods = sum(it['vlrtot'] for it in itens)
    rotulos = [
        ('TOTAL SERVIÇOS',  _fmt_brl(0.00)),
        ('TOTAL PRODUTOS',  _fmt_brl(total_prods)),
        ('DESCONTO TOTAL',  _fmt_brl(0.00)),
        ('VALOR LÍQUIDO',   _fmt_brl(pedido.get('vlrnota') or total_prods)),
    ]
    base_y = y - 9 * mm
    for idx, (lbl, val) in enumerate(rotulos):
        ty = base_y - idx * 5 * mm
        c.setFont('Helvetica-Bold', 8)
        c.drawString(meio + 3 * mm, ty, lbl)
        c.setFont('Helvetica', 8)
        c.drawRightString(CONTENT_W + MARGIN_L - 3 * mm, ty, val)


def gerar_pdf_pedidos_individual(
    lista_dados: list[dict],
    pesos_fallback: dict | None = None,
) -> bytes:
    """Recebe lista de pedidos completos (cada item = dict do
    ``obter_dados_pedido_completo_para_impressao``) e retorna PDF com 1 página
    por pedido.

    Args:
        lista_dados: pedidos completos.
        pesos_fallback: dict ``{codprod: peso}`` opcional pra preencher CX
            nos itens onde a venda não tem ``TGFITE.PESO`` populado.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Pedidos de Venda')

    if not lista_dados:
        _draw_text(c, MARGIN_L, PAGE_H - MARGIN_T - 10 * mm,
                   'Nenhum pedido selecionado para impressão.', size=11)
    else:
        for idx, dados in enumerate(lista_dados):
            if idx > 0:
                c.showPage()
            _render_pagina_individual(c, dados, pesos_fallback=pesos_fallback)

    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


# ============================================================================
# LAYOUT CONSOLIDADO — N pedidos agregados em 1 PDF
# ============================================================================

def gerar_pdf_pedidos_consolidado(
    lista_dados: list[dict],
    titulo: str = 'CONSOLIDAÇÃO DE PEDIDOS',
    subtitulo: str = '',
    pesos_fallback: dict | None = None,
) -> bytes:
    """Recebe lista de pedidos completos e retorna PDF agregado por CODPROD.

    Args:
        lista_dados: pedidos completos de
            ``obter_dados_pedido_completo_para_impressao``.
        titulo: título principal do PDF.
        subtitulo: linha extra sob o título (ex.: período).
        pesos_fallback: dict ``{codprod: peso}`` opcional pra calcular caixas
            quando a venda não tem ``TGFITE.PESO`` populado. Vem de
            ``consultar_pesos_referencia_por_codprods`` aplicado pelo caller.

    Cabeçalho: título + subtítulo + data + nº de pedidos.
    Tabela: CÓDIGO | DESCRIÇÃO | UN | QTD TOTAL | CAIXAS | Nº PEDIDOS.
    Linha de totais fixa no rodapé da tabela.
    Lista dos pedidos consolidados ao final.
    """
    pesos_fallback = pesos_fallback or {}
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Consolidação de Pedidos')

    if not lista_dados:
        _draw_text(c, MARGIN_L, PAGE_H - MARGIN_T - 10 * mm,
                   'Nenhum pedido selecionado para consolidação.', size=11)
        c.showPage()
        c.save()
        pdf_bytes = buf.getvalue()
        buf.close()
        return pdf_bytes

    # Agrega por CODPROD
    por_prod: dict[int, dict] = {}
    for dados in lista_dados:
        for it in (dados.get('itens') or []):
            cp = it['codprod']
            slot = por_prod.setdefault(cp, {
                'codprod':    cp,
                'descrprod':  it['descrprod'],
                'codvol':     it['codvol'],
                'qtd_total':  0.0,
                'qtd_caixas': 0,
                'pedidos':    set(),
            })
            slot['qtd_total']  += float(it['qtdneg'] or 0)
            slot['qtd_caixas'] += int(it['qtd_caixas'] or 0)
            slot['pedidos'].add(dados['pedido']['nunota'])

    # Aplica fallback de pesos pra produtos sem caixas calculadas
    total_qtd_geral = 0.0
    total_cx_geral  = 0
    for slot in por_prod.values():
        if slot['qtd_caixas'] == 0 and pesos_fallback:
            peso_ref = pesos_fallback.get(slot['codprod'])
            if peso_ref and peso_ref > 0:
                # CEIL via floor-div negativa
                slot['qtd_caixas'] = int(-(-float(slot['qtd_total']) // float(peso_ref)))
        total_qtd_geral += slot['qtd_total']
        total_cx_geral  += slot['qtd_caixas']

    linhas = sorted(por_prod.values(), key=lambda r: r['codprod'])

    y = PAGE_H - MARGIN_T

    # ---- Header ----
    header_h = 22 * mm
    _box(c, MARGIN_L, y - header_h, CONTENT_W, header_h)

    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(MARGIN_L + CONTENT_W / 2, y - 8 * mm, titulo)
    if subtitulo:
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(MARGIN_L + CONTENT_W / 2, y - 14 * mm, subtitulo)

    _draw_text(c, MARGIN_L + 3 * mm, y - 19 * mm,
               f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
               size=9, bold=True)
    total_pedidos = len(lista_dados)
    c.drawRightString(MARGIN_L + CONTENT_W - 5 * mm, y - 19 * mm,
                      f"{total_pedidos} pedido{'s' if total_pedidos != 1 else ''} consolidado{'s' if total_pedidos != 1 else ''}")

    y -= header_h

    # ---- Header tabela ----
    titulo_h = 5 * mm
    _box(c, MARGIN_L, y - titulo_h, CONTENT_W, titulo_h, fill=(0.85, 0.85, 0.85))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(MARGIN_L + CONTENT_W / 2, y - 3.5 * mm,
                        'CONSOLIDADO POR PRODUTO')
    y -= titulo_h

    col_h    = 5 * mm
    col_x0   = MARGIN_L
    col_w_cod  = 16 * mm
    col_w_un   = 14 * mm
    col_w_qtd  = 28 * mm
    col_w_cx   = 22 * mm
    col_w_ped  = 20 * mm
    col_w_desc = CONTENT_W - col_w_cod - col_w_un - col_w_qtd - col_w_cx - col_w_ped

    cols = [
        ('CÓDIGO',     col_w_cod,  'C'),
        ('DESCRIÇÃO',  col_w_desc, 'L'),
        ('UN',         col_w_un,   'C'),
        ('QTD TOTAL',  col_w_qtd,  'R'),
        ('CAIXAS',     col_w_cx,   'R'),
        ('Nº PED.',    col_w_ped,  'R'),
    ]

    def _draw_header_consolidado(y_in):
        _box(c, col_x0, y_in - col_h, CONTENT_W, col_h, fill=(0.92, 0.92, 0.92))
        c.setFont('Helvetica-Bold', 8)
        xc = col_x0
        for nome, w, _a in cols:
            if xc > col_x0:
                c.line(xc, y_in, xc, y_in - col_h)
            c.drawCentredString(xc + w / 2, y_in - 3.5 * mm, nome)
            xc += w
        return y_in - col_h

    y = _draw_header_consolidado(y)

    # ---- Linhas consolidadas ----
    linha_h = 4.2 * mm
    c.setFont('Helvetica', 8)
    for slot in linhas:
        if y - linha_h < MARGIN_B + 30 * mm:
            c.showPage()
            y = PAGE_H - MARGIN_T
            y = _draw_header_consolidado(y)
            c.setFont('Helvetica', 8)

        _box(c, col_x0, y - linha_h, CONTENT_W, linha_h)
        x_cursor = col_x0
        valores = [
            (str(slot['codprod']),                col_w_cod,  'C'),
            (slot['descrprod'],                    col_w_desc, 'L'),
            (slot['codvol'],                       col_w_un,   'C'),
            (_fmt_qtd(slot['qtd_total'], casas=0), col_w_qtd,  'R'),
            (str(slot['qtd_caixas']) if slot['qtd_caixas'] else '', col_w_cx, 'R'),
            (str(len(slot['pedidos'])),            col_w_ped,  'R'),
        ]
        for txt, w, align in valores:
            if x_cursor > col_x0:
                c.line(x_cursor, y, x_cursor, y - linha_h)
            ty = y - 3 * mm
            if align == 'L':
                c.drawString(x_cursor + 1.5 * mm, ty, str(txt or ''))
            elif align == 'R':
                c.drawRightString(x_cursor + w - 1.5 * mm, ty, str(txt or ''))
            else:
                c.drawCentredString(x_cursor + w / 2, ty, str(txt or ''))
            x_cursor += w
        y -= linha_h

    # ---- Linha de TOTAIS destacada (verde Agromil + borda superior espessa) ----
    if y - linha_h < MARGIN_B + 27 * mm:
        c.showPage()
        y = PAGE_H - MARGIN_T
        y = _draw_header_consolidado(y)

    # Pequeno gap sutil entre o último produto e a linha de TOTAIS
    y -= 1.5 * mm

    total_h = 7 * mm
    # Fundo verde Agromil sutil
    _box(c, col_x0, y - total_h, CONTENT_W, total_h, fill=(0.86, 0.91, 0.83))
    # Borda superior espessa pra separar visualmente da tabela acima
    c.setLineWidth(1.8)
    c.line(col_x0, y, col_x0 + CONTENT_W, y)
    c.setLineWidth(0.5)  # restaura default
    c.setFont('Helvetica-Bold', 10)
    x_cursor = col_x0
    valores_totais = [
        ('',                                            col_w_cod,  'C'),
        ('TOTAIS:',                                      col_w_desc, 'L'),
        ('',                                            col_w_un,   'C'),
        (_fmt_qtd(total_qtd_geral, casas=0),            col_w_qtd,  'R'),
        (str(total_cx_geral) if total_cx_geral else '', col_w_cx,   'R'),
        (str(len(lista_dados)),                          col_w_ped,  'R'),
    ]
    for txt, w, align in valores_totais:
        if x_cursor > col_x0:
            c.line(x_cursor, y, x_cursor, y - total_h)
        ty = y - 4.5 * mm
        if align == 'L':
            c.drawString(x_cursor + 1.5 * mm, ty, str(txt or ''))
        elif align == 'R':
            c.drawRightString(x_cursor + w - 1.5 * mm, ty, str(txt or ''))
        else:
            c.drawCentredString(x_cursor + w / 2, ty, str(txt or ''))
        x_cursor += w
    y -= total_h

    # Gap vertical antes do bloco "PEDIDOS CONSOLIDADOS"
    y -= 5 * mm

    # ---- Lista de pedidos consolidados ----
    if y - 30 * mm < MARGIN_B:
        c.showPage()
        y = PAGE_H - MARGIN_T

    _box(c, MARGIN_L, y - 5 * mm, CONTENT_W, 5 * mm, fill=(0.85, 0.85, 0.85))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(MARGIN_L + CONTENT_W / 2, y - 3.5 * mm,
                        'PEDIDOS CONSOLIDADOS')
    y -= 5 * mm

    c.setFont('Helvetica', 8)
    for dados in lista_dados:
        if y - 4 * mm < MARGIN_B:
            c.showPage()
            y = PAGE_H - MARGIN_T
        p = dados['pedido']
        cli = (dados.get('cliente') or {}).get('nome', '') or ''
        numnota = p.get('numnota') or p.get('nunota')
        c.drawString(MARGIN_L + 3 * mm, y - 3 * mm,
                     f"· Pedido {numnota}  —  {cli}")
        y -= 4 * mm

    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
