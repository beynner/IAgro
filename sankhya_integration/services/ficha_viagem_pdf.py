"""Ficha de viagem pra impressão (motorista) — Mai/2026 — 2026-05-29.

Replica o layout do modal HTML print do módulo Logística em PDF reportlab,
permitindo que o operador imprima de aba nova ou anexe ao MDFe Sankhya.

Layout (formato A6 vertical, ~105×148mm):
    - "ROTA" gigante centralizado no topo
    - "VIAGEM Nº NNNN" verde
    - Data por extenso + hora destacada
    - Motorista (nome grande)
    - Ajudantes (linha menor)
    - PLACA GIGANTE centralizada (operador identifica caminhão no pátio)
    - Lista de destinos numerados com seta > e qtd
    - Linha de total
    - Observação geral em quadro
    - Rodapé "IAgro · Logística"

A viagem vem do dict retornado por ``oracle_conn.obter_viagem_detalhe``.
"""
from __future__ import annotations

import logging
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont  # noqa: F401  (registrado se TTF custom)

logger = logging.getLogger(__name__)

# Paleta Agromil
COR_VERDE_AGROMIL = HexColor('#5e7e4a')
COR_VERDE_ESCURO  = HexColor('#3d5230')
COR_TEXTO_FRACO   = HexColor('#6b7280')
COR_BORDA_SUAVE   = HexColor('#cbd5e1')
COR_FUNDO_OBS     = HexColor('#fef9c3')   # amarelo claro pra obs
COR_FUNDO_OBS_BRD = HexColor('#facc15')

DIAS_SEMANA = [
    'domingo', 'segunda-feira', 'terça-feira', 'quarta-feira',
    'quinta-feira', 'sexta-feira', 'sábado',
]


def _formatar_data_extenso(data_iso: str) -> str:
    """'2026-05-29' → 'quinta-feira, 29/05/2026'."""
    if not data_iso:
        return '—'
    try:
        d = datetime.strptime(data_iso, '%Y-%m-%d').date()
        return f'{DIAS_SEMANA[d.weekday() + 1 if d.weekday() < 6 else 0]}, {d.strftime("%d/%m/%Y")}'
    except (ValueError, TypeError):
        return data_iso


def _ajudantes_str(ajudantes: list) -> str:
    """['JULIANO', 'PEDRO'] → 'JULIANO, PEDRO'."""
    if not ajudantes:
        return '—'
    nomes = [a.get('nomeparc') or f'parc {a.get("codparc")}' for a in ajudantes]
    return ', '.join(nomes)


def _quebrar_texto(c: canvas.Canvas, texto: str, fonte: str, tamanho: float,
                   largura_max_mm: float) -> list:
    """Quebra texto em linhas que caibam em largura_max_mm.

    Quebra por palavras inteiras quando possível; em palavras gigantes,
    força quebra por char.
    """
    if not texto:
        return ['']
    palavras = texto.split()
    linhas: list = []
    atual = ''
    for p in palavras:
        candidato = (atual + ' ' + p).strip()
        w = c.stringWidth(candidato, fonte, tamanho) / mm
        if w <= largura_max_mm or not atual:
            atual = candidato
            # Se a palavra sozinha é maior que a largura, força quebra
            if c.stringWidth(atual, fonte, tamanho) / mm > largura_max_mm:
                # Re-quebra char-by-char
                acumulado = ''
                for ch in atual:
                    if c.stringWidth(acumulado + ch, fonte, tamanho) / mm > largura_max_mm:
                        linhas.append(acumulado)
                        acumulado = ch
                    else:
                        acumulado += ch
                atual = acumulado
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def gerar_pdf_ficha_viagem(viagem: dict) -> bytes:
    """Gera PDF da ficha pra impressão.

    Args:
        viagem: dict retornado por ``oracle_conn.obter_viagem_detalhe``.

    Returns:
        bytes do PDF (1 página A6 vertical).
    """
    buf = BytesIO()
    largura, altura = A6   # 105 × 148 mm
    c = canvas.Canvas(buf, pagesize=A6)
    c.setTitle(f'Rota - Viagem N {viagem.get("num_viagem", "?")}')

    margem = 7 * mm
    largura_util = largura - 2 * margem

    y = altura - margem

    # ----- Título "ROTA" gigante -----
    c.setFont('Helvetica-Bold', 32)
    c.setFillColor(COR_VERDE_AGROMIL)
    titulo = 'ROTA'
    tw = c.stringWidth(titulo, 'Helvetica-Bold', 32)
    c.drawString((largura - tw) / 2, y - 9 * mm, titulo)
    y -= 12 * mm

    # ----- Viagem Nº -----
    c.setFont('Helvetica-Bold', 14)
    c.setFillColor(COR_VERDE_ESCURO)
    num = f'VIAGEM Nº {viagem.get("num_viagem", "?")}'
    tw = c.stringWidth(num, 'Helvetica-Bold', 14)
    c.drawString((largura - tw) / 2, y - 5 * mm, num)
    y -= 8 * mm

    # ----- Data por extenso -----
    c.setFont('Helvetica', 9)
    c.setFillColor(black)
    data_ext = _formatar_data_extenso(viagem.get('data_viagem', ''))
    tw = c.stringWidth(data_ext, 'Helvetica', 9)
    c.drawString((largura - tw) / 2, y - 4 * mm, data_ext)
    y -= 6 * mm

    # ----- Hora destacada -----
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(COR_VERDE_ESCURO)
    hora = f'Saída às {viagem.get("hora_saida", "??:??")}'
    tw = c.stringWidth(hora, 'Helvetica-Bold', 11)
    c.drawString((largura - tw) / 2, y - 4 * mm, hora)
    y -= 8 * mm

    # ----- Separador -----
    c.setStrokeColor(COR_BORDA_SUAVE)
    c.setLineWidth(0.4)
    c.line(margem, y, largura - margem, y)
    y -= 4 * mm

    # ----- Motorista -----
    c.setFont('Helvetica', 8)
    c.setFillColor(COR_TEXTO_FRACO)
    c.drawString(margem, y, 'MOTORISTA')
    y -= 4 * mm
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(black)
    motorista = viagem.get('motorista_nome') or '—'
    c.drawString(margem, y, motorista[:40])
    y -= 6 * mm

    # ----- Ajudantes -----
    ajudantes = viagem.get('ajudantes') or []
    if ajudantes:
        c.setFont('Helvetica', 8)
        c.setFillColor(COR_TEXTO_FRACO)
        c.drawString(margem, y, f'AJUDANTE{"S" if len(ajudantes) > 1 else ""}')
        y -= 4 * mm
        c.setFont('Helvetica', 9)
        c.setFillColor(black)
        ajud_str = _ajudantes_str(ajudantes)
        linhas_aj = _quebrar_texto(c, ajud_str, 'Helvetica', 9, largura_util / mm)
        for linha_aj in linhas_aj[:2]:   # max 2 linhas
            c.drawString(margem, y, linha_aj)
            y -= 4 * mm

    y -= 2 * mm

    # ----- PLACA GIGANTE centralizada -----
    placa = viagem.get('placa') or '?'
    c.setStrokeColor(COR_VERDE_AGROMIL)
    c.setLineWidth(1.5)
    altura_placa_box = 14 * mm
    c.roundRect(margem, y - altura_placa_box, largura_util, altura_placa_box, 2 * mm, stroke=1, fill=0)
    c.setFont('Courier-Bold', 24)
    c.setFillColor(black)
    tw = c.stringWidth(placa, 'Courier-Bold', 24)
    c.drawString((largura - tw) / 2, y - altura_placa_box + 4.5 * mm, placa)
    y -= altura_placa_box + 4 * mm

    # ----- Destinos -----
    c.setFont('Helvetica', 8)
    c.setFillColor(COR_TEXTO_FRACO)
    c.drawString(margem, y, 'DESTINOS')
    y -= 4 * mm

    destinos = viagem.get('destinos') or []
    total_caixas = 0
    c.setFont('Helvetica', 9)
    c.setFillColor(black)

    for d in destinos:
        if y < 24 * mm:   # se passa do rodapé, para
            break
        nome = d.get('nomeparc') or f'parc {d.get("codparc")}'
        qtd = d.get('qtd_caixas') or 0
        total_caixas += qtd
        ordem = d.get('ordem', '?')
        # Render "> 1. NOME ............. 120cx"
        prefixo = f'> {ordem}. '
        sufixo = f'  {qtd}cx'
        c.setFont('Helvetica-Bold', 9)
        c.drawString(margem, y, prefixo)
        c.setFont('Helvetica', 9)
        sw_pre = c.stringWidth(prefixo, 'Helvetica-Bold', 9)
        sw_suf = c.stringWidth(sufixo, 'Helvetica-Bold', 9)
        max_nome_w = largura_util - sw_pre - sw_suf - 1 * mm
        nome_fit = nome
        while c.stringWidth(nome_fit, 'Helvetica', 9) > max_nome_w and len(nome_fit) > 0:
            nome_fit = nome_fit[:-1]
        if len(nome_fit) < len(nome):
            nome_fit = nome_fit[:-1] + '…'
        c.drawString(margem + sw_pre, y, nome_fit)
        c.setFont('Helvetica-Bold', 9)
        c.setFillColor(COR_VERDE_ESCURO)
        c.drawRightString(largura - margem, y, sufixo.strip())
        c.setFillColor(black)
        y -= 5 * mm

    # ----- Linha de TOTAL -----
    y -= 2 * mm
    c.setStrokeColor(COR_VERDE_AGROMIL)
    c.setLineWidth(0.8)
    c.line(margem, y, largura - margem, y)
    y -= 5 * mm
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(COR_VERDE_ESCURO)
    c.drawString(margem, y, 'TOTAL')
    c.drawRightString(largura - margem, y, f'{total_caixas} caixas')
    y -= 7 * mm

    # ----- Observação (quadro amarelo) -----
    obs = (viagem.get('observacao') or '').strip()
    if obs and y > 24 * mm:
        c.setStrokeColor(COR_FUNDO_OBS_BRD)
        c.setFillColor(COR_FUNDO_OBS)
        # Calcula altura necessária da caixa de observação
        c.setFont('Helvetica', 8)
        linhas_obs = _quebrar_texto(c, obs, 'Helvetica', 8, (largura_util - 4 * mm) / mm)
        alt_obs = max(8 * mm, 3.5 * mm * (len(linhas_obs) + 1) + 4 * mm)
        # Não vazar pro rodapé
        alt_obs = min(alt_obs, y - 16 * mm)
        c.rect(margem, y - alt_obs, largura_util, alt_obs, stroke=1, fill=1)
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(COR_VERDE_ESCURO)
        c.drawString(margem + 1.5 * mm, y - 3 * mm, 'OBSERVAÇÃO')
        c.setFont('Helvetica', 8)
        c.setFillColor(black)
        y_obs = y - 6 * mm
        max_linhas = max(1, int((alt_obs - 6 * mm) / (3.5 * mm)))
        for ln in linhas_obs[:max_linhas]:
            c.drawString(margem + 1.5 * mm, y_obs, ln)
            y_obs -= 3.5 * mm
        y -= alt_obs + 2 * mm

    # ----- Rodapé -----
    c.setFont('Helvetica', 7)
    c.setFillColor(COR_TEXTO_FRACO)
    rodape = 'IAgro · Logística'
    tw = c.stringWidth(rodape, 'Helvetica', 7)
    c.drawString((largura - tw) / 2, 5 * mm, rodape)

    c.showPage()
    c.save()
    return buf.getvalue()
