#!/usr/bin/env python3
"""Aruba AOS-S precheck PDF V2.1. Usage: --input JSON --output PDF.
Requires reportlab. No device commands are executed.
"""
import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Flowable
from reportlab.pdfbase.pdfmetrics import stringWidth

REQUIRED = ['show version','show system','show flash','show interfaces brief','show vlan','show running-config']
OPTIONAL = ['show interfaces status','show system power-supply','show system fans','show cpu','show vsf topology','show time','show spanning-tree','show uptime','show loop-protect','show boot-history']
NAVY = colors.HexColor('#19344c')
PALE = colors.HexColor('#edf2f6')

class CLILine(Flowable):
    def __init__(self, line, font_size=6.4, leading=9):
        super().__init__()
        self.line = line
        self.font_size = font_size
        self.leading = leading
        self.height = leading
    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return (availWidth, self.height)
    def draw(self):
        self.canv.setFont('Courier', self.font_size)
        self.canv.setFillColor(colors.HexColor('#253442'))
        self.canv.drawString(0, 1, self.line)

def remove_echo(raw, command):
    """Remove only the echoed command prefix on a line, preserving the rest of that line."""
    text = str(raw or '').replace('\r\n','\n').replace('\r','\n').replace('\x08','')
    lines = text.split('\n')
    # AOS-S may echo the command before the actual first output line.
    # Strip once only, at the beginning of the output (ignoring empty lines).
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        match = re.match(r'^\s*(?:[^\s#>]+[>#]\s*)?' + re.escape(command) + r'(?=\s|$)', line, re.I)
        if match:
            lines[idx] = line[match.end():].lstrip()
        break
    return '\n'.join(lines)

def wrapped_lines(text, max_width, font_size):
    """Soft-wrap long CLI lines without deleting characters or splitting columns unnecessarily."""
    max_chars = max(20, int(max_width / stringWidth('M','Courier',font_size)))
    for line in text.split('\n'):
        line = line.expandtabs(4)
        if not line:
            yield ' '
        else:
            while len(line) > max_chars:
                yield line[:max_chars]
                line = '    ' + line[max_chars:]
            yield line

def page_footer(canvas, doc):
    canvas.saveState()
    w, _ = landscape(A4)
    canvas.setStrokeColor(colors.HexColor('#cbd5df'))
    canvas.line(16*mm, 12*mm, w-16*mm, 12*mm)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(16*mm, 8*mm, 'ORANGE LAB RUN - IEC | AWX | Précheck Aruba V2.1')
    canvas.drawRightString(w-16*mm, 8*mm, f'Page {doc.page}')
    canvas.restoreState()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    required = data.get('required_commands') or REQUIRED
    optional = data.get('optional_commands') or OPTIONAL
    commands = required + optional
    outputs = data.get('results', [])
    if len(outputs) != len(commands):
        raise ValueError(f'Nombre de sorties incorrect: {len(outputs)} pour {len(commands)} commandes')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MainTitleX', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=17, leading=22, textColor=NAVY, spaceAfter=12))
    styles.add(ParagraphStyle(name='SectionX', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=NAVY, spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name='SmallX', parent=styles['Normal'], fontSize=9, leading=13, spaceAfter=6))
    styles.add(ParagraphStyle(name='CliTitleX', parent=styles['Heading3'], fontSize=9, leading=12, textColor=NAVY, spaceBefore=10, spaceAfter=5))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=landscape(A4), leftMargin=16*mm, rightMargin=16*mm, topMargin=15*mm, bottomMargin=18*mm, title='Précheck firmware Aruba V2.1')
    usable = landscape(A4)[0] - 32*mm
    story = [Paragraph('ORANGE LAB RUN - IEC', styles['MainTitleX']), Paragraph('Précheck firmware Aruba AOS-S | Rapport technique V2.1', styles['SmallX']), Paragraph('01 — Synthèse', styles['SectionX'])]
    meta = [('Équipement',data.get('hostname','')),('Adresse IP',data.get('ip','')),('Job AWX',str(data.get('awx_job',''))),('Commandes',f'{len(commands)} sorties archivées'),('Contrôle VSF','Non effectué automatiquement'),('Mise à jour firmware','Non autorisée par ce rapport')]
    table = Table([[Paragraph(escape(str(a)),styles['SmallX']),Paragraph(escape(str(b)),styles['SmallX'])] for a,b in meta],colWidths=[usable*.28,usable*.72],hAlign='LEFT')
    table.setStyle(TableStyle([('ROWBACKGROUNDS',(0,0),(-1,-1),[PALE,colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story += [table, Paragraph('02 — Matrice de collecte', styles['SectionX'])]
    rows = [['N°','Commande','Catégorie','Statut']]
    for i,(cmd,out) in enumerate(zip(commands,outputs),1):
        bad = not str(out or '').strip() or bool(re.search(r'Invalid input|Invalid command|Unknown command',str(out),re.I))
        rows.append([f'{i:02d}',cmd,'Essentielle' if i <= len(required) else 'Complémentaire','NON VALIDÉE' if bad else 'COLLECTÉE'])
    t = Table(rows,colWidths=[usable*.07,usable*.47,usable*.24,usable*.22],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5)]))
    story += [t, Paragraph('Statut COLLECTÉE : sortie non vide, sans erreur CLI reconnue ; ne constitue pas une validation de conformité.',styles['SmallX']), PageBreak(), Paragraph('03 — Transcription CLI détaillée',styles['SectionX']), Paragraph('Sorties issues du JSON AWX. Échos de commande supprimés uniquement dans ce PDF. Le TXT NFS reste inchangé.',styles['SmallX'])]
    for i,(cmd,raw) in enumerate(zip(commands,outputs),1):
        title = Paragraph(f'{i:02d}. {escape(cmd)}',styles['CliTitleX'])
        clean = remove_echo(raw,cmd)
        if not clean.strip():
            clean = '[SORTIE VIDE]'
        # Landscape A4, Courier 6.4: keeps most wide CLI tables on one line.
        rendered = [CLILine(line) for line in wrapped_lines(clean,usable,6.4)]
        story.append(KeepTogether([title,rendered[0]]))
        story.extend(rendered[1:])
        story.append(Spacer(1,7))
    story += [Paragraph('04 — Conclusion et points de vigilance',styles['SectionX']),Paragraph('Ce document atteste uniquement de la collecte. Vérifier manuellement VSF, la compatibilité du firmware cible, la sauvegarde de configuration et le plan de retour arrière avant toute intervention.',styles['SmallX']),Paragraph('Fichiers NFS : precheck_cli_session.txt, precheck_results.json, precheck_report.txt et precheck_report.pdf.',styles['SmallX'])]
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    print(f'PDF créé : {output}')

if __name__ == '__main__':
    main()
