#!/usr/bin/env python3
"""Create a readable Aruba firmware precheck PDF from archived AWX JSON."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether


def generate(src, dst):
    data = json.loads(Path(src).read_text(encoding='utf-8'))
    required = data.get('required_commands', [])
    optional = data.get('optional_commands', [])
    outputs = data.get('results', [])
    commands = required + optional
    if len(outputs) != len(commands):
        raise ValueError('Incoherence entre le nombre de commandes et de resultats')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleOrange', parent=styles['Title'], fontSize=17, leading=21, textColor=colors.HexColor('#17324D'), spaceAfter=12))
    styles.add(ParagraphStyle(name='BodyCompact', parent=styles['BodyText'], fontSize=9, leading=13, spaceAfter=5))
    styles.add(ParagraphStyle(name='Cmd', parent=styles['Heading3'], fontSize=10, leading=14, textColor=colors.HexColor('#17324D'), spaceBefore=10, spaceAfter=4))
    styles.add(ParagraphStyle(name='SmallMono', fontName='Courier', fontSize=7, leading=9, spaceAfter=4))
    doc = SimpleDocTemplate(str(dst), pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=18*mm, bottomMargin=18*mm)
    story = [Paragraph('ORANGE LAB RUN - IEC', styles['TitleOrange']), Paragraph('Précheck firmware Aruba AOS-S — Rapport de collecte', styles['Heading2']), Spacer(1, 8)]
    meta = [
        ('Équipement', data.get('hostname', '')),
        ('Adresse IP', data.get('ip', '')),
        ('Job AWX', str(data.get('awx_job', ''))),
        ('Commandes essentielles', str(len(required))),
        ('Commandes complémentaires', str(len(optional))),
        ('Contrôle automatique VSF', 'Non effectué'),
    ]
    table = Table([[Paragraph(escape(k), styles['BodyCompact']), Paragraph(escape(v), styles['BodyCompact'])] for k, v in meta], colWidths=[63*mm, 107*mm])
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (0,-1), colors.HexColor('#EFF3F7')), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING',(0,0),(-1,-1),7), ('TOPPADDING',(0,0),(-1,-1),7), ('LINEBELOW',(0,0),(-1,-1),0.25,colors.HexColor('#D7DEE6'))]))
    story.extend([table, Spacer(1, 13), Paragraph('Résultats des commandes', styles['Heading2'])])
    for idx, (command, output) in enumerate(zip(commands, outputs), 1):
        text = output if isinstance(output, str) else str(output or '')
        status = 'COLLECTÉE' if text.strip() and not any(x in text for x in ('Invalid input','Invalid command','Unknown command')) else 'À VÉRIFIER'
        story.append(Paragraph(f'{idx:02d}. {escape(command)} — {status}', styles['Cmd']))
        # Short extracts only: full CLI is retained in the single TXT file.
        excerpt = '\n'.join(text.splitlines()[:8])[:750] if text else '(sortie vide)'
        story.append(Paragraph(escape(excerpt).replace(' ', '&nbsp;').replace('\n', '<br/>'), styles['SmallMono']))
    story.extend([Spacer(1, 12), Paragraph('Ce document résume la collecte. La transcription intégrale est conservée dans precheck_cli_session.txt. Le contrôle VSF et l’autorisation de mise à jour firmware ne sont pas couverts par ce rapport.', styles['BodyCompact'])])
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(17*mm, 11*mm, 'ORANGE LAB RUN - IEC | AWX | Rapport de précheck')
        canvas.drawRightString(193*mm, 11*mm, f'Page {doc.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    generate(args.input, args.output)
