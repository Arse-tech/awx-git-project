#!/usr/bin/env python3

import re
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Preformatted,
    KeepTogether,
)


# ---------------------------------------------------------------------------
# COULEURS / CHARTE
# ---------------------------------------------------------------------------

ORANGE = colors.HexColor("#F16E00")
DARK = colors.HexColor("#2D2D2D")
MEDIUM_GREY = colors.HexColor("#666666")
LIGHT_GREY = colors.HexColor("#F3F3F3")
BORDER_GREY = colors.HexColor("#D0D0D0")
GREEN = colors.HexColor("#2E7D32")
RED = colors.HexColor("#C62828")
WHITE = colors.white


# ---------------------------------------------------------------------------
# OUTILS
# ---------------------------------------------------------------------------

def extract_value(pattern, text, default="Non disponible"):
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        return value if value else default
    return default


def extract_command_section(content, command):
    """
    Extrait la sortie située après :
        hostname# show xxx
    jusqu'à la prochaine commande ou la fin de session.
    """
    pattern = (
        rf"^[^\n#]+#\s*{re.escape(command)}\s*\n"
        rf"(.*?)(?="
        rf"\n-{{5,}}\n"
        rf"\n?[^\n#]+#\s*show\s+"
        rf"|\n[^\n#]+#\s*$"
        rf"|\n={{5,}}\n\s*FIN DE LA SESSION CLI"
        rf"|\Z)"
    )

    match = re.search(
        pattern,
        content,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return ""


def parse_interfaces(section):
    interfaces = []

    for line in section.splitlines():

        line = line.rstrip()

        if not line.strip():
            continue

        # Les lignes de données commencent par un numéro de port :
        # 1/1, 1/21-Trk1, 2/1, etc.
        if not re.match(r"^\s*\d+/\d+", line):
            continue

        # Découpage approximatif adapté à "show interfaces brief"
        parts = line.split()

        if len(parts) < 4:
            continue

        port = parts[0]

        # Recherche de l'état Up/Down
        status = "Inconnu"

        for item in parts:
            if item.lower() == "up":
                status = "Up"
                break
            if item.lower() == "down":
                status = "Down"
                break

        # Type : généralement deuxième colonne
        interface_type = parts[1] if len(parts) > 1 else "-"

        # Recherche du mode/vitesse
        speed = "-"

        for item in parts:
            if "FDx" in item or "HDx" in item:
                speed = item
                break

        interfaces.append(
            {
                "port": port,
                "type": interface_type,
                "status": status,
                "speed": speed,
                "raw": line.strip(),
            }
        )

    return interfaces


def parse_vlans(section):
    vlans = []

    for line in section.splitlines():

        line = line.strip()

        if not re.match(r"^\d+\s+", line):
            continue

        # Exemple :
        # 1 DEFAULT_VLAN | Port-based No No

        match = re.match(
            r"^(\d+)\s+(.+?)\s+\|\s+(\S+)\s+(\S+)\s+(\S+)",
            line,
        )

        if match:
            vlans.append(
                {
                    "id": match.group(1),
                    "name": match.group(2).strip(),
                    "status": match.group(3),
                    "voice": match.group(4),
                    "jumbo": match.group(5),
                }
            )

    return vlans


# ---------------------------------------------------------------------------
# EN-TETE / PIED DE PAGE
# ---------------------------------------------------------------------------

def draw_header_footer(canvas, doc):

    canvas.saveState()

    width, height = landscape(A4)

    # Barre supérieure
    canvas.setFillColor(ORANGE)
    canvas.rect(
        0,
        height - 7 * mm,
        width,
        7 * mm,
        stroke=0,
        fill=1,
    )

    # Pied de page
    canvas.setStrokeColor(BORDER_GREY)
    canvas.line(
        15 * mm,
        11 * mm,
        width - 15 * mm,
        11 * mm,
    )

    canvas.setFillColor(MEDIUM_GREY)
    canvas.setFont("Helvetica", 7.5)

    canvas.drawString(
        15 * mm,
        6 * mm,
        "ORANGE LAB RUN - IEC | Rapport généré automatiquement par AWX"
    )

    canvas.drawRightString(
        width - 15 * mm,
        6 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()


# ---------------------------------------------------------------------------
# GENERATION DU PDF
# ---------------------------------------------------------------------------

def generate_pdf(txt_file, pdf_file, hostname, ip_address):

    with open(txt_file, "r", encoding="utf-8") as file:
        cli_content = file.read()

    # -----------------------------------------------------------------------
    # EXTRACTION DES SECTIONS
    # -----------------------------------------------------------------------

    version_section = extract_command_section(
        cli_content,
        "show version"
    )

    system_section = extract_command_section(
        cli_content,
        "show system"
    )

    interfaces_section = extract_command_section(
        cli_content,
        "show interfaces brief"
    )

    vlan_section = extract_command_section(
        cli_content,
        "show vlan"
    )

    # -----------------------------------------------------------------------
    # EXTRACTION DES INFORMATIONS SYSTEME
    # -----------------------------------------------------------------------

    software_version = extract_value(
        r"Software revision\s*:\s*(.+)",
        system_section,
    )

    if software_version == "Non disponible":
        software_version = extract_value(
            r"\b(WC\.\d+\.\d+\.\d+)\b",
            version_section,
        )

    serial_number = extract_value(
        r"Serial Number\s*:\s*(.+)",
        system_section,
    )

    uptime = extract_value(
        r"Up Time\s*:\s*(.+)",
        system_section,
    )

    cpu = extract_value(
        r"CPU Util \(%\)\s*:\s*(.+)",
        system_section,
    )

    base_mac = extract_value(
        r"Base MAC Addr\s*:\s*(.+)",
        system_section,
    )

    boot_image = extract_value(
        r"Boot Image\s*:\s*(.+)",
        version_section,
    )

    boot_rom = extract_value(
        r"Boot ROM Version\s*:\s*(.+)",
        version_section,
    )

    device_role = extract_value(
        r"Role\s*:\s*(.+)",
        cli_content,
        default="Non défini",
    )

    collection_date = extract_value(
        r"Date collecte\s*:\s*(.+)",
        cli_content,
        default=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )

    # -----------------------------------------------------------------------
    # PARSING INTERFACES / VLAN
    # -----------------------------------------------------------------------

    interfaces = parse_interfaces(interfaces_section)
    vlans = parse_vlans(vlan_section)

    interfaces_up = [
        interface
        for interface in interfaces
        if interface["status"] == "Up"
    ]

    interfaces_down = [
        interface
        for interface in interfaces
        if interface["status"] == "Down"
    ]

    trunks = [
        interface
        for interface in interfaces
        if "trk" in interface["port"].lower()
    ]

    # -----------------------------------------------------------------------
    # DOCUMENT
    # -----------------------------------------------------------------------

    document = SimpleDocTemplate(
        pdf_file,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=17 * mm,
        title=f"Rapport réseau Aruba - {hostname}",
        author="ORANGE LAB RUN - IEC",
        subject="Rapport automatisé de collecte réseau AWX",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        textColor=DARK,
        alignment=TA_LEFT,
        spaceAfter=3 * mm,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=MEDIUM_GREY,
        spaceAfter=5 * mm,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=DARK,
        spaceBefore=4 * mm,
        spaceAfter=3 * mm,
    )

    normal_style = ParagraphStyle(
        "NormalReport",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=DARK,
    )

    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=MEDIUM_GREY,
    )

    cli_style = ParagraphStyle(
        "CLI",
        fontName="Courier",
        fontSize=6.2,
        leading=7.8,
        textColor=colors.black,
        backColor=colors.HexColor("#F7F7F7"),
        borderColor=BORDER_GREY,
        borderWidth=0.4,
        borderPadding=6,
    )

    elements = []

    # -----------------------------------------------------------------------
    # PAGE 1 - SYNTHESE
    # -----------------------------------------------------------------------

    elements.append(
        Paragraph(
            "RAPPORT DE COLLECTE RÉSEAU",
            title_style,
        )
    )

    elements.append(
        Paragraph(
            "ArubaOS-Switch | Collecte automatisée AWX / SSH",
            subtitle_style,
        )
    )

    # Bandeau équipement

    equipment_data = [
        [
            Paragraph("<b>ÉQUIPEMENT</b>", small_style),
            Paragraph("<b>ADRESSE IP</b>", small_style),
            Paragraph("<b>STATUT</b>", small_style),
            Paragraph("<b>DATE DE COLLECTE</b>", small_style),
        ],
        [
            Paragraph(f"<b>{hostname}</b>", normal_style),
            Paragraph(ip_address, normal_style),
            Paragraph("<b>SUCCÈS</b>", normal_style),
            Paragraph(collection_date, normal_style),
        ],
    ]

    equipment_table = Table(
        equipment_data,
        colWidths=[
            70 * mm,
            45 * mm,
            35 * mm,
            75 * mm,
        ],
    )

    equipment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREY),
                ("TEXTCOLOR", (0, 0), (-1, 0), MEDIUM_GREY),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TEXTCOLOR", (2, 1), (2, 1), GREEN),
            ]
        )
    )

    elements.append(equipment_table)
    elements.append(Spacer(1, 5 * mm))

    # Informations système

    elements.append(
        Paragraph(
            "1. Synthèse système",
            section_style,
        )
    )

    system_data = [
        [
            Paragraph("<b>Constructeur</b>", small_style),
            Paragraph("<b>Rôle</b>", small_style),
            Paragraph("<b>Version logicielle</b>", small_style),
            Paragraph("<b>Boot image</b>", small_style),
        ],
        [
            "Aruba",
            device_role,
            software_version,
            boot_image,
        ],
        [
            Paragraph("<b>Uptime</b>", small_style),
            Paragraph("<b>CPU</b>", small_style),
            Paragraph("<b>Numéro de série</b>", small_style),
            Paragraph("<b>Base MAC</b>", small_style),
        ],
        [
            uptime,
            f"{cpu} %" if cpu != "Non disponible" else cpu,
            serial_number,
            base_mac,
        ],
    ]

    system_table = Table(
        system_data,
        colWidths=[
            58 * mm,
            58 * mm,
            58 * mm,
            58 * mm,
        ],
    )

    system_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREY),
                ("BACKGROUND", (0, 2), (-1, 2), LIGHT_GREY),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, 1), 9),
                ("FONTSIZE", (0, 3), (-1, 3), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    elements.append(system_table)
    elements.append(Spacer(1, 5 * mm))

    # Synthèse interfaces

    elements.append(
        Paragraph(
            "2. Synthèse des interfaces",
            section_style,
        )
    )

    counters = [
        [
            Paragraph("<b>TOTAL</b>", small_style),
            Paragraph("<b>UP</b>", small_style),
            Paragraph("<b>DOWN</b>", small_style),
            Paragraph("<b>TRUNKS</b>", small_style),
            Paragraph("<b>VLAN</b>", small_style),
        ],
        [
            str(len(interfaces)),
            str(len(interfaces_up)),
            str(len(interfaces_down)),
            str(len(trunks)),
            str(len(vlans)),
        ],
    ]

    counter_table = Table(
        counters,
        colWidths=[42 * mm] * 5,
    )

    counter_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("TEXTCOLOR", (1, 1), (1, 1), GREEN),
                ("TEXTCOLOR", (2, 1), (2, 1), RED),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    elements.append(counter_table)
    elements.append(Spacer(1, 5 * mm))

    # Interfaces actives

    elements.append(
        Paragraph(
            "3. Interfaces actives",
            section_style,
        )
    )

    if interfaces_up:

        active_data = [
            ["Port", "Type", "État", "Vitesse"]
        ]

        for interface in interfaces_up:
            active_data.append(
                [
                    interface["port"],
                    interface["type"],
                    interface["status"],
                    interface["speed"],
                ]
            )

        active_table = Table(
            active_data,
            colWidths=[
                50 * mm,
                60 * mm,
                40 * mm,
                55 * mm,
            ],
            repeatRows=1,
        )

        active_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TEXTCOLOR", (2, 1), (2, -1), GREEN),
                    ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        elements.append(active_table)

    else:
        elements.append(
            Paragraph(
                "Aucune interface active détectée.",
                normal_style,
            )
        )

    # -----------------------------------------------------------------------
    # PAGE 2 - VLAN
    # -----------------------------------------------------------------------

    elements.append(PageBreak())

    elements.append(
        Paragraph(
            "4. VLAN",
            title_style,
        )
    )

    elements.append(
        Paragraph(
            f"Configuration VLAN détectée sur {hostname}",
            subtitle_style,
        )
    )

    if vlans:

        vlan_data = [
            ["VLAN ID", "Nom", "Type / Statut", "Voice", "Jumbo"]
        ]

        for vlan in vlans:
            vlan_data.append(
                [
                    vlan["id"],
                    vlan["name"],
                    vlan["status"],
                    vlan["voice"],
                    vlan["jumbo"],
                ]
            )

        vlan_table = Table(
            vlan_data,
            colWidths=[
                30 * mm,
                75 * mm,
                55 * mm,
                35 * mm,
                35 * mm,
            ],
            repeatRows=1,
        )

        vlan_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), DARK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        elements.append(vlan_table)

    else:
        elements.append(
            Paragraph(
                "Aucun VLAN n'a pu être extrait automatiquement.",
                normal_style,
            )
        )

    elements.append(Spacer(1, 8 * mm))

    # Informations techniques complémentaires

    elements.append(
        Paragraph(
            "5. Informations techniques complémentaires",
            section_style,
        )
    )

    technical_data = [
        ["Paramètre", "Valeur"],
        ["Boot ROM", boot_rom],
        ["Boot image", boot_image],
        ["Version logicielle", software_version],
        ["Base MAC", base_mac],
        ["Numéro de série", serial_number],
        ["Source inventaire", "AWX - Inventaire dynamique MySQL"],
        ["Méthode de collecte", "SSH / ansible.netcommon.network_cli"],
    ]

    technical_table = Table(
        technical_data,
        colWidths=[
            70 * mm,
            155 * mm,
        ],
        repeatRows=1,
    )

    technical_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    elements.append(technical_table)

    # -----------------------------------------------------------------------
    # ANNEXE CLI
    # -----------------------------------------------------------------------

    elements.append(PageBreak())

    elements.append(
        Paragraph(
            "ANNEXE — SORTIES CLI BRUTES",
            title_style,
        )
    )

    elements.append(
        Paragraph(
            "Les sorties ci-dessous sont conservées pour traçabilité, diagnostic "
            "et comparaison avec les collectes ultérieures.",
            subtitle_style,
        )
    )

    cli_sections = [
        ("show version", version_section),
        ("show system", system_section),
        ("show interfaces brief", interfaces_section),
        ("show vlan", vlan_section),
    ]

    for command, content in cli_sections:

        elements.append(
            Paragraph(
                f"{hostname}# {command}",
                section_style,
            )
        )

        if content:
            elements.append(
                Preformatted(
                    content,
                    cli_style,
                    maxLineLength=150,
                )
            )
        else:
            elements.append(
                Paragraph(
                    "Sortie non disponible.",
                    normal_style,
                )
            )

        elements.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # GENERATION
    # -----------------------------------------------------------------------

    document.build(
        elements,
        onFirstPage=draw_header_footer,
        onLaterPages=draw_header_footer,
    )

    print(f"PDF professionnel généré : {pdf_file}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) != 5:
        print(
            "Usage: generate_cli_pdf.py "
            "<input.txt> <output.pdf> <hostname> <ip>"
        )
        sys.exit(1)

    generate_pdf(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
    )
