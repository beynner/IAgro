"""Renderização de etiquetas SafeTrace/IAgro 100×50mm (Mai/2026).

Cada etiqueta = 1 caixa do pedido. Tamanho fixo 100mm × 50mm landscape,
otimizado pra impressora térmica Zebra ZD220 (203 dpi).

Layout (referência: imagem SafeTrace que o módulo replica):
    - Esquerda: nome do produto + fornecedor + CNPJ + LAT/LONG + endereço
                + CEP + peso líquido + data + lote + origem
    - Sup. direita: QR code (URL pública por lote) + texto "IAgro"
    - Meio direita: código de barras EAN13 (de TGFPRO.REFERENCIA)
    - Rodapé: faixa preta "PRODUTO COM ORIGEM RASTREADA" entre setas

Dados de entrada vêm de ``oracle_conn.consultar_dados_etiqueta_pedido`` +
helper ``calcular_qtd_etiquetas`` pra saber quantas cópias por item.

Privacidade: tudo roda local (reportlab + qrcode em Python puro).
"""

from __future__ import annotations

import os
import logging
from io import BytesIO
from typing import Iterable

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode.eanbc import Ean13BarcodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

import qrcode

logger = logging.getLogger(__name__)

LARGURA_MM = 100
ALTURA_MM  = 50


# --------------------------------------------------------------------------
# Helpers de formatação
# --------------------------------------------------------------------------

def _formatar_data_br(d) -> str:
    if not d:
        return ''
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d')
    return str(d)


def _formatar_cnpj(c) -> str:
    if not c:
        return ''
    s = ''.join(ch for ch in str(c) if ch.isdigit())
    if len(s) == 14:
        return f'{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}'
    if len(s) == 11:
        return f'{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}'
    return str(c)


def _truncar(texto: str, max_chars: int) -> str:
    """Trunca texto pra não vazar da etiqueta. Ellipsis em casos extremos."""
    if not texto:
        return ''
    s = str(texto)
    if len(s) <= max_chars:
        return s
    return s[:max_chars - 1] + '…'


def _gerar_qr_imagem(data: str) -> BytesIO:
    """Gera PNG do QR code em memória. Caller passa pro ImageReader."""
    qr = qrcode.QRCode(
        version=None,                       # auto-fit
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(data or '')
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf


def _resolver_url_rastreio(lote: str) -> str:
    """Substitui {lote} pelo CODAGREGACAO real. Lê de URL_RASTREIO_PUBLICA
    no .env; fallback pra placeholder local se não configurado."""
    template = os.environ.get(
        'URL_RASTREIO_PUBLICA',
        'http://localhost:8000/rastreio-publico/{lote}',
    )
    return template.replace('{lote}', str(lote or ''))


# --------------------------------------------------------------------------
# Desenho de 1 etiqueta
# --------------------------------------------------------------------------

def _desenhar_etiqueta(c: canvas.Canvas, pedido: dict, item: dict) -> None:
    """Renderiza UMA etiqueta na página atual do canvas.

    Não chama showPage — caller controla quantas etiquetas por chamada.
    """
    LX = LARGURA_MM * mm
    LY = ALTURA_MM * mm

    emp        = (pedido or {}).get('empresa') or {}
    descrprod  = _truncar((item.get('descrprod') or '').upper(), 38)
    fornecedor = _truncar(
        emp.get('razao') or emp.get('nome_fantasia') or '', 40
    )
    cgc_raw    = (emp.get('cgc') or '').strip()
    cgc_fmt    = _formatar_cnpj(cgc_raw)
    lat        = emp.get('latitude')
    lng        = emp.get('longitude')
    endereco   = _truncar(emp.get('endereco') or '', 60)
    cep        = (emp.get('cep') or '').strip()
    peso_caixa = item.get('qtdfixada') or 0
    codvol     = item.get('codvol') or 'KG'
    dt         = _formatar_data_br(pedido.get('dtneg'))
    lote       = item.get('codagregacao') or ''
    ean        = (item.get('referencia_ean') or '').strip()

    # === Borda externa ===
    c.setLineWidth(1.0)
    c.rect(0.5 * mm, 0.5 * mm, LX - 1 * mm, LY - 1 * mm)

    # === Bloco texto à esquerda ===
    x_text = 2.5 * mm

    # Título: nome do produto
    c.setFont('Helvetica-Bold', 11)
    c.drawString(x_text, LY - 5.5 * mm, descrprod)

    # Bloco de info — linhas pequenas
    c.setFont('Helvetica-Bold', 7)
    y = LY - 9.5 * mm
    linhas: list[tuple[str, str]] = [
        ('Fornecedor: ', fornecedor),
        ('CNPJ/CPF: ',   cgc_fmt or '—'),
    ]
    if lat is not None and lng is not None:
        linhas.append(('LAT: ', f'{lat}    LONG: {lng}'))
    if endereco:
        linhas.append(('Endereco: ', endereco))
    if cgc_raw and cep:
        linhas.append((
            f'Codigo do Fornecedor: {cgc_raw}    CEP: ', cep
        ))
    elif cgc_raw:
        linhas.append(('Codigo do Fornecedor: ', cgc_raw))
    peso_str = (
        f'{peso_caixa:g} {codvol}'
        if peso_caixa and peso_caixa > 0 else '—'
    )
    linhas.extend([
        ('Peso Liquido: ',                  peso_str),
        ('Data de Producao/Consolidacao: ', dt or '—'),
        ('Lote: ',                          lote or '—'),
        ('Origem: ',                        'BRASIL'),
    ])
    for label, val in linhas:
        c.drawString(x_text, y, f'{label}{val}')
        y -= 3.0 * mm

    # === Bloco lateral direito ===
    qr_size = 13 * mm
    qr_x    = LX - qr_size - 2 * mm
    qr_y    = LY - qr_size - 8 * mm

    # Texto "IAgro" + "rastreio" acima do QR (substitui o "safe TRACE" da
    # etiqueta original — branding nosso)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(qr_x + 1 * mm, qr_y + qr_size + 3.5 * mm, 'IAgro')
    c.setFont('Helvetica-Oblique', 5)
    c.drawString(qr_x + 1 * mm, qr_y + qr_size + 1.2 * mm, 'rastreio')

    # QR code
    try:
        qr_buf = _gerar_qr_imagem(_resolver_url_rastreio(lote))
        c.drawImage(
            ImageReader(qr_buf),
            qr_x, qr_y, width=qr_size, height=qr_size,
            preserveAspectRatio=True, mask='auto',
        )
    except Exception:
        logger.exception("Falha ao gerar QR da etiqueta (lote=%s)", lote)

    # === Barcode EAN13 (entre o bloco esquerdo e o QR) ===
    if ean and len(ean) >= 12:
        try:
            bc = Ean13BarcodeWidget(ean)
            bc.barHeight     = 7 * mm
            bc.barWidth      = 0.30 * mm
            bc.humanReadable = 1
            d = Drawing(35 * mm, 10 * mm)
            d.add(bc)
            renderPDF.draw(d, c, qr_x - 36 * mm, 6 * mm)
        except Exception:
            logger.exception("EAN inválido (%s) — etiqueta sai sem barcode", ean)

    # === Rodapé "PRODUTO COM ORIGEM RASTREADA" ===
    # Faixa preta + texto branco + setas
    c.setFillColorRGB(0, 0, 0)
    c.rect(0, 0, LX, 5 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(
        LX / 2, 1.6 * mm,
        '◀◀  PRODUTO COM ORIGEM RASTREADA  ▶▶',
    )
    # Restaura preto (próxima página)
    c.setFillColorRGB(0, 0, 0)


# --------------------------------------------------------------------------
# API pública do módulo
# --------------------------------------------------------------------------

def gerar_pdf_etiquetas(
    pedido: dict,
    itens_com_copias: Iterable[tuple[dict, int]],
) -> bytes:
    """Gera PDF multi-página, 1 etiqueta por página.

    Args:
        pedido: dict retornado por ``consultar_dados_etiqueta_pedido`` (chave 'pedido').
        itens_com_copias: iterável de tuplas ``(item_dict, qtd_etiquetas)``.
            Cada item gera ``qtd_etiquetas`` páginas consecutivas no PDF.

    Retorna ``bytes`` do PDF pronto pra HttpResponse(content_type='application/pdf').
    Lista vazia → PDF de 0 páginas (caller deve validar antes).
    """
    buf = BytesIO()
    pagesize = (LARGURA_MM * mm, ALTURA_MM * mm)
    c = canvas.Canvas(buf, pagesize=pagesize)
    c.setTitle('Etiquetas IAgro')

    for item, qtd in itens_com_copias:
        n = int(qtd or 0)
        for _ in range(n):
            _desenhar_etiqueta(c, pedido or {}, item or {})
            c.showPage()

    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
