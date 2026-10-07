
#!/usr/bin/env python3

import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Preformatted,
    PageBreak,
)


def add_page_number(canvas, doc):
    canvas.saveState()

    canvas.setFont("Helvetica", 8)

    canvas.drawString(
        15 * mm,
        8 * mm,
        "ORANGE LAB RUN - IEC"
    )

    canvas.drawRightString(
        282 * mm,
        8 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()


def generate_pdf(txt_file, pdf_file, hostname, ip_address):

    with open(txt_file, "r", encoding="utf-8") as file:
        cli_content = file.read()

    document = SimpleDocTemplate(
        pdf_file,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Rapport Aruba - {hostname}",
        author="ORANGE LAB RUN - IEC",
    )

    title_style = ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )

    cli_style = ParagraphStyle(
        "CLI",
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=colors.black,
        backColor=colors.whitesmoke,
        borderColor=colors.lightgrey,
        borderWidth=0.5,
        borderPadding=8,
    )

    elements = []

    elements.append(
        Paragraph(
            "ORANGE LAB RUN - IEC",
            title_style
        )
    )

    elements.append(
        Paragraph(
            "Rapport de collecte réseau - ArubaOS-Switch",
            subtitle_style
        )
    )

    elements.append(Spacer(1, 5 * mm))

    elements.append(
        Paragraph(
            f"<b>Equipement :</b> {hostname}<br/>"
            f"<b>Adresse IP :</b> {ip_address}<br/>"
            f"<b>Collecte :</b> AWX / SSH",
            subtitle_style,
        )
    )

    elements.append(Spacer(1, 8 * mm))

    elements.append(
        Paragraph(
            "SESSION CLI",
            title_style
        )
    )

    elements.append(Spacer(1, 3 * mm))

    elements.append(
        Preformatted(
            cli_content,
            cli_style,
            maxLineLength=140,
        )
    )

    document.build(
        elements,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )


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

    print(f"PDF genere : {sys.argv[2]}")
