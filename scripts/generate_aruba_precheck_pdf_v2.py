#!/usr/bin/env python3
"""Aruba AOS-S AWX precheck V2. Read-only: consumes the existing JSON schema."""
import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted

NAVY = colors.HexColor('#17324D')
ORANGE = colors.HexColor('#E87524')
PALE = colors.HexColor('#F0F4F8')
GREY = colors.HexColor('#526272')
LINE = colors.HexColor('#DCE3EA')


def clean(text, command):
    """Clean command echo in PDF only; never alter the archived original."""
    value = (text or '').replace('\r', '')
    return re.sub(r'^\s*' + re.escape(command) + r'(?=\S)', '', value, count=1, flags=re.I).lstrip('\n')


def match(text, pattern):
    found = re.search(pattern, text, flags=re.I | re.M)
    return found.group(1).strip() if found else 'Non déterminé'


def make_report(src, dst):
    data = json.loads(Path(src).read_text(encoding='utf-8'))
    required = data.get('required_commands', [])
    optional = data.get('optional_commands', [])
    commands = required + optional
    outputs = data.get('results', [])
    if len(commands) != len(outputs):
        raise ValueError('Nombre de commandes et de sorties incohérent')
    by_command = dict(zip(commands, [str(v or '') for v in outputs]))
    version = by_command.get('show version', '')
    flash = by_command.get('show flash', '')
    system = by_command.get('show system', '')
    fans = by_command.get('show system fans', '')
    cpu = by_command.get('show cpu', '')
    vsf = by_command.get('show vsf topology', '')
    power = by_command.get('show system power-supply', '')
    spanning = by_command.get('show spanning-tree', '')
    boot = match(version, r'^Boot Image:\s*(\S+)')
    primary = match(flash, r'^Primary Image\s*:\s*\d+\s+\S+\s+(\S+)')
    secondary = match(flash, r'^Secondary Image\s*:\s*\d+\s+\S+\s+(\S+)')
    active = primary if boot.lower() == 'primary' else secondary if boot.lower() == 'secondary' else match(system, r'^\s*Software revision\s*:\s*(\S+)')
    rom = match(version, r'^Boot ROM Version:\s*(\S+)')
    statuses = []
    for command, raw in zip(commands, outputs):
        value = str(raw or '')
        valid = bool(value.strip()) and not re.search(r'Invalid input|Invalid command|Unknown command', value, re.I)
        statuses.append((command, 'COLLECTÉE' if valid else 'À VÉRIFIER'))
    essential_ok = all(status == 'COLLECTÉE' for _, status in statuses[:len(required)])

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BrandV2', fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=NAVY, spaceAfter=7))
    styles.add(ParagraphStyle(name='SubV2', fontName='Helvetica', fontSize=10, leading=15, textColor=GREY, spaceAfter=12))
    styles.add(ParagraphStyle(name='SectionV2', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=NAVY, spaceBefore=9, spaceAfter=8))
    styles.add(ParagraphStyle(name='BodyV2', fontName='Helvetica', fontSize=9, leading=13, spaceAfter=7))
    styles.add(ParagraphStyle(name='TinyV2', fontName='Helvetica', fontSize=8, leading=11))
    styles.add(ParagraphStyle(name='HeadCellV2', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.white))
    doc = SimpleDocTemplate(str(dst), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=19*mm, bottomMargin=19*mm)
    story = []

    def p(value, style='TinyV2'):
        return Paragraph(escape(str(value)), styles[style])

    def heading(title):
        story.append(Paragraph(escape(title), styles['SectionV2']))

    def table(rows, widths=None, header=False):
        converted = [[p(cell, 'HeadCellV2' if header and idx == 0 else 'TinyV2') for cell in row] for idx, row in enumerate(rows)]
        t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
        commands_style = [('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8), ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6), ('LINEBELOW',(0,0),(-1,-1),0.35,LINE)]
        if header:
            commands_style.append(('BACKGROUND',(0,0),(-1,0),NAVY))
            commands_style.append(('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]))
        else:
            commands_style.append(('BACKGROUND',(0,0),(0,-1),PALE))
        t.setStyle(TableStyle(commands_style))
        story.append(t)

    story += [Paragraph('ORANGE LAB RUN - IEC', styles['BrandV2']), Paragraph('Précheck firmware Aruba AOS-S | Rapport technique V2', styles['SubV2'])]
    heading('01 — Synthèse exécutive')
    table([
        ['Équipement', data.get('hostname','Non déterminé')],
        ['Adresse IP', data.get('ip','Non déterminé')],
        ['Job AWX', data.get('awx_job','Non déterminé')],
        ['Collecte', f'{sum(s == "COLLECTÉE" for _,s in statuses)}/{len(statuses)} commandes collectées'],
        ['Commandes essentielles', f'{len(required)} — {"collecte validée" if essential_ok else "à vérifier"}'],
        ['Contrôle VSF', 'Non effectué automatiquement'],
    ], [56*mm, 118*mm])
    heading('Images firmware et démarrage')
    table([['Paramètre', 'Valeur'], ['Image de démarrage', boot], ['Version active déduite', active], ['Image primaire', primary], ['Image secondaire', secondary], ['Boot ROM', rom]], [72*mm, 102*mm], True)
    story.append(Spacer(1, 12))
    story.append(Paragraph('Résultat : collecte des informations uniquement. Ce rapport ne valide ni la santé VSF, ni la compatibilité d’un firmware cible, ni l’autorisation de mise à jour.', styles['BodyV2']))

    story.append(PageBreak())
    heading('02 — État technique observé')
    fan_states = re.findall(r'^\s*Sys-\d+\s*\|\s*([^|\n]+)', fans, re.M)
    fan_value = ', '.join(x.strip() for x in fan_states) if fan_states else 'Non déterminé'
    cpu_value = match(cpu, r'^\s*1 min ave:\s*(.+)$')
    if cpu_value == 'Non déterminé':
        cpu_value = match(system, r'^\s*CPU Util \(%\)\s*:\s*(.+)$')
    power_value = 'Sortie collectée (consulter la transcription)' if power.strip() else 'Non déterminé'
    vsf_value = 'Topologie collectée (validation non effectuée)' if vsf.strip() else 'Non déterminé'
    stp_value = match(spanning, r'^\s*STP Enabled\s*:\s*(.+)$')
    table([['Élément', 'Observation'], ['Version logicielle', match(system, r'^\s*Software revision\s*:\s*(.+)$')], ['Uptime', match(system, r'^\s*Up Time\s*:\s*(.+)$')], ['CPU', cpu_value], ['Ventilateurs', fan_value], ['Alimentation', power_value], ['VSF', vsf_value], ['Spanning Tree activé', stp_value]], [58*mm,116*mm], True)
    heading('Autres domaines collectés')
    for label, cmd in [('Interfaces', 'show interfaces brief'), ('VLAN', 'show vlan'), ('Protection des boucles', 'show loop-protect'), ('Historique de démarrage', 'show boot-history')]:
        state = next((s for c,s in statuses if c == cmd), 'NON DEMANDÉE')
        story.append(Paragraph(f'<b>{escape(label)} :</b> {escape(state)} — détails disponibles dans la session CLI complète.', styles['BodyV2']))
    story.append(Paragraph('Les états présentés sont des observations issues des commandes. Aucune validation de conformité matérielle ou réseau n’est réalisée automatiquement.', styles['BodyV2']))

    story.append(PageBreak())
    heading('03 — Matrice de collecte des commandes')
    matrix = [['N°', 'Commande', 'Catégorie', 'Statut']]
    for i, (command, state) in enumerate(statuses, 1):
        matrix.append([f'{i:02}', command, 'Essentielle' if i <= len(required) else 'Complémentaire', state])
    table(matrix, [13*mm, 78*mm, 43*mm, 40*mm], True)
    story.append(Spacer(1, 12))
    story.append(Paragraph('Statut « COLLECTÉE » : une sortie non vide a été obtenue sans message d’erreur CLI reconnu. Ce statut ne constitue pas une validation de conformité.', styles['BodyV2']))

    story.append(PageBreak())
    heading('04 — Transcription CLI intégrale')
    story.append(Paragraph('Les sorties ci-dessous proviennent du JSON AWX, sans troncature. Les retours de ligne sont conservés. Le TXT NFS demeure la preuve originale.', styles['BodyV2']))
    cli_style = ParagraphStyle(name='CliFullV2', fontName='Courier', fontSize=6.4, leading=8.5, textColor=NAVY, spaceAfter=3)
    for i, (command, raw) in enumerate(zip(commands, outputs), 1):
        if i > 1:
            story.append(Spacer(1, 10))
        story.append(Paragraph(f'{i:02d}. {escape(command)}', styles['SectionV2']))
        content = str(raw if raw is not None else '') .replace('\r\n', '\n').replace('\r', '\n')
        # Le nettoyage est uniquement cosmétique dans le PDF, pas dans le TXT.
        content = clean(content, command)
        if not content.strip():
            content = '[Aucune sortie CLI]'
        # Preformatted conserve espaces et lignes ; le fractionnement évite
        # les blocs plus hauts qu'une page A4.
        for line in content.split('\n'):
            # Fractionnement des lignes très longues pour ne pas dépasser la page.
            while len(line) > 98:
                story.append(Preformatted(line[:98], cli_style, maxLineLength=98))
                line = line[98:]
            story.append(Preformatted(line if line else ' ', cli_style, maxLineLength=98))

    story.append(PageBreak())
    heading('05 — Conclusion et points de vigilance')
    table([['Contrôle', 'Conclusion'], ['Collecte des commandes essentielles', 'Réussie' if essential_ok else 'À vérifier'], ['Collecte complémentaire', f'{sum(s == "COLLECTÉE" for _,s in statuses[len(required):])}/{len(optional)} collectées'], ['Contrôle automatique VSF', 'Non effectué'], ['Firmware cible et compatibilité', 'Non évalués'], ['Autorisation de mise à jour', 'Non délivrée']], [78*mm, 96*mm], True)
    heading('Points à vérifier avant une intervention')
    for item in ['Évaluer manuellement la topologie et la santé VSF.', 'Confirmer le firmware cible, la compatibilité matérielle et les notes de version.', 'Préparer une sauvegarde de configuration et un plan de retour arrière.', 'Planifier une fenêtre de maintenance et les validations après redémarrage.']:
        story.append(Paragraph('• ' + escape(item), styles['BodyV2']))
    heading('Traçabilité NFS')
    story.append(Paragraph('Répertoire du Job : reports/aruba/' + escape(str(data.get('hostname',''))) + '/job-' + escape(str(data.get('awx_job',''))) + '/', styles['BodyV2']))
    table([['Fichier', 'Contenu'], ['precheck_cli_session.txt', 'Transcription CLI intégrale (source de référence)'], ['precheck_results.json', 'Sorties structurées des commandes'], ['precheck_report.txt', 'Résumé de collecte'], ['precheck_report.pdf', 'Synthèse V2 et sorties CLI intégrales']], [73*mm,101*mm], True)
    story.append(Spacer(1, 12))
    story.append(Paragraph('Aucune modification de configuration ou de firmware n’est exécutée par le précheck.', styles['BodyV2']))

    def footer(canvas, pdf):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(18*mm, 16*mm, 192*mm, 16*mm)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(GREY)
        canvas.drawString(18*mm, 11*mm, 'ORANGE LAB RUN - IEC | AWX | Précheck Aruba V2')
        canvas.drawRightString(192*mm, 11*mm, f'Page {pdf.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    make_report(args.input, args.output)
