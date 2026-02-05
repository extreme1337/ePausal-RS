import re
import PyPDF2
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.units import cm
from datetime import datetime, timedelta, date
from decimal import Decimal
import csv
import json


def get_client_ip(request):
    """Dobij IP adresu klijenta"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# ============================================
# DOCUMENT GENERATION
# ============================================
def formatiraj_iznos(iznos, valuta):
    if valuta == "BAM":
        return f"{iznos} KM"
    elif valuta == "EUR":
        return f"€{iznos}"
    elif valuta == "USD":
        return f"${iznos}"
    return f"{iznos} {valuta}"


def generate_invoice_doc(faktura):
    """Generiši Word fakturu kao HTML"""

    # Kreiraj HTML za stavke
    stavke_html = ""
    # Koristimo related_name='stavke' na InvoiceItem modelu
    stavke = faktura.stavke.all()

    for index, stavka in enumerate(stavke, start=1):
        stavke_html += f"""
            <tr>
                <td style="text-align: center; border: 1px solid #000; padding: 8px;">{index}.</td>
                <td style="border: 1px solid #000; padding: 8px;">{stavka.opis}</td>
                <td style="text-align: center; border: 1px solid #000; padding: 8px;">{stavka.jedinica_mjere}</td>
                <td style="text-align: center; border: 1px solid #000; padding: 8px;">{stavka.kolicina}</td>
                <td style="text-align: right; border: 1px solid #000; padding: 8px;">{stavka.cijena_po_jedinici:,.2f}</td>
                <td style="text-align: right; border: 1px solid #000; padding: 8px;">{stavka.ukupna_cijena:,.2f}</td>
            </tr>"""

    # Osnovni HTML šablon
    html = f"""<!DOCTYPE html>
<html lang="sr">
<head>
    <meta charset="UTF-8">
    <title>Faktura {faktura.broj_fakture}</title>
    <style>
        @page {{ size: A4; margin: 1.5cm; }}
        body {{ 
            font-family: 'DejaVu Sans', Arial, sans-serif; 
            font-size: 10pt; 
            line-height: 1.4; 
            color: #333;
        }}
        .header {{ border-bottom: 2px solid #2563eb; padding-bottom: 10px; margin-bottom: 25px; }}
        .company-name {{ font-size: 13pt; font-weight: bold; color: #1e40af; text-transform: uppercase; }}
        .invoice-title {{ text-align: right; font-size: 18pt; font-weight: bold; color: #1e40af; margin: 20px 0; }}
        .info-grid {{ width: 100%; margin-bottom: 30px; }}
        .items-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .items-table th {{ 
            background-color: #f1f5f9; 
            border: 1px solid #000; 
            padding: 10px; 
            font-size: 9pt;
            text-transform: uppercase;
        }}
        .total-row {{ font-weight: bold; background-color: #f8fafc; font-size: 11pt; }}
        .footer-note {{ margin-top: 40px; font-size: 8pt; color: #666; border-top: 1px solid #eee; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="company-name">{faktura.izdavalac_naziv}</div>
        <div>{faktura.izdavalac_adresa}, {faktura.izdavalac_mjesto}</div>
        <div style="margin-top: 5px;">
            {f'<strong>JIB:</strong> {faktura.izdavalac_jib} | ' if faktura.izdavalac_jib else ''}
            {f'<strong>Bank account:</strong> {faktura.izdavalac_racun}' if faktura.izdavalac_racun else ''}
            {f'<br><strong>IBAN:</strong> {faktura.izdavalac_iban}' if hasattr(faktura, "izdavalac_iban") and faktura.izdavalac_iban else ''}
        </div>
    </div>
    
    <div class="invoice-title">INVOICE / RAČUN br. {faktura.broj_fakture}</div>
    
    <table class="info-grid">
        <tr>
            <td style="width: 60%; vertical-align: top;">
                <strong>BILL TO / KUPAC:</strong><br>
                <div style="font-size: 11pt; margin-top: 5px;">
                    <strong>{faktura.primalac_naziv}</strong><br>
                    {faktura.primalac_adresa}<br>
                    {faktura.primalac_mjesto}
                    {f'<br><strong>JIB: {faktura.primalac_jib}</strong>' if faktura.primalac_jib else ''}
                </div>
            </td>
            <td style="width: 40%; text-align: right; vertical-align: top;">
                <strong>Date / Datum:</strong> {faktura.datum_izdavanja.strftime('%d.%m.%Y')}<br>
                {f'<strong>Place / Mjesto:</strong> {faktura.mjesto_izdavanja}<br>' if faktura.mjesto_izdavanja else ''}
                <strong>Currency / Valuta:</strong> {faktura.valuta}
            </td>
        </tr>
    </table>
    
    <table class="items-table">
        <thead>
            <tr>
                <th style="width: 5%">No.</th>
                <th style="width: 45%">Description / Opis usluge</th>
                <th style="width: 10%">Unit / JM</th>
                <th style="width: 10%">Qty / Kol.</th>
                <th style="width: 15%">Price / Cijena</th>
                <th style="width: 15%">Total / Iznos ({faktura.valuta})</th>
            </tr>
        </thead>
        <tbody>
            {stavke_html}
            <tr class="total-row">
                <td colspan="5" style="text-align: right; border: 1px solid #000; padding: 10px;">
                    TOTAL / UKUPNO ZA UPLATU:
                </td>
                <td style="text-align: right; border: 1px solid #000; padding: 10px; color: #1e40af;">
                    {faktura.ukupno_sa_pdv:,.2f} {faktura.valuta}
                </td>
            </tr>
        </tbody>
    </table>
    
    <div style="margin-top: 20px; font-style: italic; font-size: 9pt;">
        Napomena: PDV nije obračunat prema članu 44. stav 1. Zakona o PDV-u (Mali obveznik).<br>
        <em>Note: VAT not charged according to local tax regulations for small businesses.</em>
    </div>

    <table style="width: 100%; margin-top: 60px;">
        <tr>
            <td style="width: 50%;">
                <div style="border-top: 1px solid #000; width: 200px; text-align: center; padding-top: 5px;">
                    Issued by / Fakturisao
                </div>
            </td>
            <td style="width: 50%; text-align: right;">
                <div style="display: inline-block; border: 1px dashed #ccc; padding: 20px; text-align: center;">
                    L.S. / M.P.
                </div>
            </td>
        </tr>
    </table>

    <div class="footer-note">
        Generated by ePauša RS - Softver za preduzetnike
    </div>
</body>
</html>"""

    return html


def generate_payment_slip_png(uplatnica, korisnik):
    """Generiši PNG uplatnicu - tačan RS format"""

    if uplatnica.primalac == "PURS":
        racun_primaoca = "562008000000557"
        naziv_primaoca = "PORESKA UPRAVA REPUBLIKE SRPSKE"
        proracunska_org = "711112"
    else:
        racun_primaoca = "551000000005078"
        naziv_primaoca = "FOND ZDRAVSTVENOG OSIGURANJA RS"
        proracunska_org = "711121"

    racun_posiljaoca = korisnik.racun.replace("-", "")
    poziv_na_broj = korisnik.jib

    img = Image.new("RGB", (2100, 700), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_small = ImageFont.truetype("arial.ttf", 15)
        font_bold = ImageFont.truetype("arialbd.ttf", 17)
        font_italic = ImageFont.truetype("ariali.ttf", 13)
    except:
        font_small = ImageFont.load_default()
        font_bold = font_small
        font_italic = font_small

    # Okvir
    draw.rectangle([10, 10, 2090, 690], outline="black", width=2)
    draw.line([(582, 10), (582, 690)], fill="black", width=1)
    draw.line([(10, 438), (582, 438)], fill="black", width=1)

    # LIJEVA STRANA
    draw.text(
        (25, 38), "Uplatio je (ime, adresa i telefon)", fill="black", font=font_small
    )
    draw.line([(25, 58), (560, 58)], fill="black", width=1)
    draw.text((25, 78), korisnik.ime, fill="black", font=font_bold)
    draw.line([(25, 88), (560, 88)], fill="black", width=1)
    draw.line([(25, 118), (560, 118)], fill="black", width=1)

    draw.text((25, 138), "Svrha doznake", fill="black", font=font_small)
    draw.line([(25, 158), (560, 158)], fill="black", width=1)
    draw.text((25, 178), uplatnica.svrha, fill="black", font=font_bold)
    draw.line([(25, 188), (560, 188)], fill="black", width=1)
    draw.line([(25, 218), (560, 218)], fill="black", width=1)

    draw.text((25, 238), "Primalac/Primalac", fill="black", font=font_small)
    draw.line([(25, 258), (560, 258)], fill="black", width=1)
    draw.text((25, 278), naziv_primaoca, fill="black", font=font_bold)
    draw.line([(25, 288), (560, 288)], fill="black", width=1)
    draw.line([(25, 318), (560, 318)], fill="black", width=1)

    draw.text((25, 338), "Mjesto i datum uplate", fill="black", font=font_small)
    datum_str = uplatnica.datum.strftime("%d%m%Y")
    draw_number_boxes(draw, datum_str, 400, 323, 8, 21, 24, font_bold)

    draw.text((25, 468), "Potpis i pečat", fill="black", font=font_small)
    draw.text((25, 486), "nalogodavatelja", fill="black", font=font_small)
    draw.line([(25, 520), (350, 520)], fill="black", width=1)

    draw.rectangle([400, 452, 570, 652], outline="black", width=1)
    draw.text((455, 545), "Pečat banke", fill="black", font=font_small)

    draw.text((25, 668), "Potpis", fill="black", font=font_small)
    draw.text((25, 686), "ovlaštene osobe/lica", fill="black", font=font_small)
    draw.line([(25, 710), (350, 710)], fill="black", width=1)

    # DESNA STRANA
    draw.text((598, 28), "Račun", fill="black", font=font_small)
    draw.text((598, 43), "pošiljatelja/pošiljaoca", fill="black", font=font_small)
    draw_number_boxes(draw, racun_posiljaoca, 755, 23, 18, 21, 24, font_bold)

    draw.text((598, 78), "Račun", fill="black", font=font_small)
    draw.text((598, 93), "primaoca/primaoca", fill="black", font=font_small)
    draw_number_boxes(draw, racun_primaoca, 755, 73, 18, 21, 24, font_bold)

    draw.text((598, 138), "KM", fill="black", font=font_bold)
    draw.line([(650, 148), (1810, 148)], fill="black", width=1)
    cio, dec = str(uplatnica.iznos).split(".")
    draw.text((1200, 135), cio, fill="black", font=font_bold)
    draw.text((1310, 135), ",", fill="black", font=font_bold)
    draw.text((1360, 135), dec, fill="black", font=font_bold)
    draw.rectangle([1820, 132, 1838, 150], outline="black", width=1)
    draw.text((1845, 138), "HITNO", fill="black", font=font_small)

    draw.text(
        (598, 175), "samo za uplate javnih prihoda", fill="black", font=font_italic
    )
    draw.rectangle([728, 180, 1918, 201], outline="black", width=1)

    draw.text((598, 218), "Broj poreznog", fill="black", font=font_small)
    draw.text((598, 233), "obveznika", fill="black", font=font_small)
    draw_number_boxes(draw, poziv_na_broj[:13], 748, 208, 13, 23, 26, font_bold)

    draw.text((1332, 218), "Vrsta", fill="black", font=font_small)
    draw.text((1332, 233), "uplate", fill="black", font=font_small)
    draw_number_boxes(draw, "", 1405, 208, 2, 23, 26, font_bold)

    draw.rectangle([1227, 255, 1577, 393], outline="black", width=1)
    draw.text((1310, 273), "Porezni period", fill="black", font=font_italic)

    draw.text((598, 298), "Vrsta prihoda", fill="black", font=font_small)
    draw_number_boxes(draw, "", 725, 283, 3, 23, 26, font_bold)
    draw.text((1240, 310), "Od", fill="black", font=font_small)
    draw_number_boxes(draw, "", 1285, 295, 8, 23, 26, font_bold)

    draw.text((1240, 360), "Do", fill="black", font=font_small)
    draw_number_boxes(draw, "", 1285, 345, 8, 23, 26, font_bold)

    draw.text((598, 365), "Općina", fill="black", font=font_small)
    draw_number_boxes(draw, "14", 672, 350, 2, 23, 26, font_bold)

    draw.text((780, 358), "Proračunska/budžetska", fill="black", font=font_small)
    draw.text((780, 373), "organizacija", fill="black", font=font_small)
    draw.rectangle([1005, 350, 1115, 376], fill="#CCCCCC", outline="black", width=1)
    draw_number_boxes(draw, proracunska_org, 1120, 350, 6, 23, 26, font_bold)

    draw.text((598, 428), "Poziv", fill="black", font=font_small)
    draw.text((598, 443), "na broj", fill="black", font=font_small)
    draw_number_boxes(draw, poziv_na_broj, 705, 418, 13, 23, 26, font_bold)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"nalog-uplate-{uplatnica.primalac}-{uplatnica.datum}.png"
    return ContentFile(buffer.read(), name=filename)


def draw_number_boxes(draw, text, x, y, count, width, height, font):
    """Crta kutije sa brojevima"""
    gap = 1
    for i in range(count):
        char = text[i] if i < len(text) else ""
        box_x = x + (i * (width + gap))

        draw.rectangle([box_x, y, box_x + width, y + height], outline="black", width=1)

        if char and char != " ":
            try:
                text_bbox = draw.textbbox((0, 0), char, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                text_x = box_x + (width - text_width) // 2
                text_y = y + (height - text_height) // 2
                draw.text((text_x, text_y), char, fill="black", font=font)
            except:
                draw.text(
                    (box_x + width // 2 - 5, y + 5), char, fill="black", font=font
                )


def generate_bilans_csv(bilans, korisnik, prihodi):
    """Generiši CSV bilans"""
    buffer = BytesIO()
    buffer.write("\ufeff".encode("utf-8"))

    content = f"""BILANS USPJEHA - ePauša RS

Korisnik,{korisnik.ime}
Email,{korisnik.user.email}
Datum kreiranja,{bilans.datum_kreiranja.strftime('%d.%m.%Y')}
Period,Od {bilans.od_mjesec} do {bilans.do_mjesec}
Broj mjeseci,{prihodi.count()}
Čuva se do,{bilans.datum_isteka.strftime('%d.%m.%Y')}

PRIHODI PO MJESECIMA
Mjesec,Iznos (KM),Porez 2% (KM),Doprinosi (KM),Neto (KM)
"""

    for prihod in prihodi:
        porez = prihod.iznos * Decimal("0.02")
        doprinosi = Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal(
            str(settings.STOPA_DOPRINOSA)
        )
        neto = prihod.iznos - porez - doprinosi
        content += f"{prihod.mjesec},{prihod.iznos},{porez},{doprinosi},{neto}\n"

    content += f"""
REKAPITULACIJA
Stavka,Iznos (KM)
Ukupan prihod,{bilans.ukupan_prihod}
Porez (2%),{bilans.porez}
Doprinosi (70%),{bilans.doprinosi}
Ukupne obaveze,{bilans.porez + bilans.doprinosi}
Neto dohodak,{bilans.neto}
Prosječna mjesečna zarada,{bilans.neto / prihodi.count() if prihodi.count() > 0 else 0}

Generisano,{bilans.datum_kreiranja.strftime('%d.%m.%Y %H:%M:%S')}
Sistem,ePauša RS © 2025
"""

    buffer.write(content.encode("utf-8"))
    buffer.seek(0)

    filename = f"bilans-{bilans.od_mjesec}-{bilans.do_mjesec}.csv"
    return ContentFile(buffer.read(), name=filename)


# ============================================
# GODIŠNJI IZVJEŠTAJ PDF
# ============================================


def generate_godisnji_izvjestaj_pdf(korisnik, godina):
    """Generiši godišnji izvještaj za PURS u PDF formatu"""
    buffer = BytesIO()
    p = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 20)
    p.drawString(2 * cm, height - 3 * cm, "GODIŠNJI IZVJEŠTAJ ZA PORESKU UPRAVU")

    p.setFont("Helvetica", 12)
    y = height - 5 * cm

    p.drawString(2 * cm, y, f"Ime i prezime: {korisnik.ime}")
    y -= 0.7 * cm
    p.drawString(2 * cm, y, f"JIB: {korisnik.jib}")
    y -= 0.7 * cm
    p.drawString(2 * cm, y, f"Godina: {godina}")
    y -= 1.5 * cm

    p.line(2 * cm, y, width - 2 * cm, y)
    y -= 1 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, y, "I. PRIHODI PO MJESECIMA")
    y -= 1 * cm

    p.setFont("Helvetica", 11)
    prihodi = korisnik.prihodi.filter(mjesec__startswith=str(godina)).order_by("mjesec")

    ukupan_prihod = Decimal("0")
    for prihod in prihodi:
        p.drawString(2 * cm, y, f"{prihod.mjesec}")
        p.drawString(10 * cm, y, f"{prihod.iznos:,.2f} KM")
        ukupan_prihod += prihod.iznos
        y -= 0.6 * cm

    y -= 0.5 * cm
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2 * cm, y, "UKUPAN PRIHOD:")
    p.drawString(10 * cm, y, f"{ukupan_prihod:,.2f} KM")
    y -= 1.5 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, y, "II. OBAVEZE")
    y -= 1 * cm

    porez = ukupan_prihod * Decimal("0.02")
    doprinosi = (
        Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal("0.70") * prihodi.count()
    )
    neto = ukupan_prihod - porez - doprinosi

    p.setFont("Helvetica", 11)
    p.drawString(2 * cm, y, f"Porez na dohodak (2%):")
    p.drawString(10 * cm, y, f"{porez:,.2f} KM")
    y -= 0.7 * cm
    p.drawString(2 * cm, y, f"Doprinosi (70%):")
    p.drawString(10 * cm, y, f"{doprinosi:,.2f} KM")
    y -= 1.5 * cm

    p.setFont("Helvetica-Bold", 12)
    p.drawString(2 * cm, y, f"NETO DOHODAK:")
    p.drawString(10 * cm, y, f"{neto:,.2f} KM")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer


# ============================================
# CHART DATA
# ============================================


def get_chart_data_prihodi(korisnik):
    """Generiši podatke za Chart.js"""
    prihodi = korisnik.prihodi.all().order_by("mjesec")

    labels = [p.mjesec for p in prihodi]
    data_prihodi = [float(p.iznos) for p in prihodi]
    data_porez = [float(p.iznos * Decimal("0.02")) for p in prihodi]
    data_neto = [
        float(
            p.iznos
            - (p.iznos * Decimal("0.02"))
            - (Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal("0.70"))
        )
        for p in prihodi
    ]

    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Prihodi",
                "data": data_prihodi,
                "borderColor": "rgb(59, 130, 246)",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "fill": True,
            },
            {
                "label": "Porez",
                "data": data_porez,
                "borderColor": "rgb(249, 115, 22)",
                "backgroundColor": "rgba(249, 115, 22, 0.1)",
                "fill": True,
            },
            {
                "label": "Neto",
                "data": data_neto,
                "borderColor": "rgb(34, 197, 94)",
                "backgroundColor": "rgba(34, 197, 94, 0.1)",
                "fill": True,
            },
        ],
    }


# ============================================
# PREDICTIVE ANALYTICS
# ============================================


def generate_income_predictions(korisnik):
    """Generiši predikcije prihoda za naredna 3 mjeseca"""
    from decimal import Decimal
    from .models import PredictiveAnalytics

    prihodi = korisnik.prihodi.order_by("mjesec")

    if prihodi.count() < 3:
        return []

    # UZMI POSLEDNJIH 6 MESECI (bez negativnog indeksa)
    last_prihodi = list(prihodi.order_by("-mjesec")[:6])
    last_prihodi.reverse()  # da ostane hronološki redosled

    iznosi = [float(p.iznos) for p in last_prihodi]

    avg = sum(iznosi) / len(iznosi)

    trend = 0
    if len(iznosi) >= 2:
        trend = (iznosi[-1] - iznosi[0]) / len(iznosi)

    predictions = []

    last_month = prihodi.last().mjesec
    year, month = map(int, last_month.split("-"))

    for i in range(1, 4):
        month += 1
        if month > 12:
            month = 1
            year += 1

        predicted_amount = avg + (trend * i)
        confidence = max(50, 95 - (i * 10))

        pred, created = PredictiveAnalytics.objects.update_or_create(
            korisnik=korisnik,
            mjesec=f"{year}-{str(month).zfill(2)}",
            defaults={
                "predicted_income": Decimal(str(round(predicted_amount, 2))),
                "confidence": Decimal(confidence),
            },
        )
        predictions.append(pred)

    return predictions


# ============================================
# CHART DATA
# ============================================


def get_chart_data_prihodi(korisnik):
    """Generiši podatke za Chart.js"""
    prihodi = korisnik.prihodi.all().order_by("mjesec")

    labels = [p.mjesec for p in prihodi]
    data_prihodi = [float(p.iznos) for p in prihodi]
    data_porez = [float(p.iznos * Decimal("0.02")) for p in prihodi]
    data_neto = [
        float(
            p.iznos
            - (p.iznos * Decimal("0.02"))
            - (Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal("0.70"))
        )
        for p in prihodi
    ]

    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Prihodi",
                "data": data_prihodi,
                "borderColor": "rgb(59, 130, 246)",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "fill": True,
            },
            {
                "label": "Porez",
                "data": data_porez,
                "borderColor": "rgb(249, 115, 22)",
                "backgroundColor": "rgba(249, 115, 22, 0.1)",
                "fill": True,
            },
            {
                "label": "Neto",
                "data": data_neto,
                "borderColor": "rgb(34, 197, 94)",
                "backgroundColor": "rgba(34, 197, 94, 0.1)",
                "fill": True,
            },
        ],
    }


# ============================================
# OCR PROCESSING
# ============================================
def parse_bank_statement_pdf(pdf_file):
    """
    Poboljšani parser koji koristi pdfplumber kao primarni alat za Atos i NLB.
    """
    import pdfplumber
    import re
    from decimal import Decimal
    from datetime import datetime, date

    transakcije = []
    full_text = ""

    try:
        pdf_file.seek(0)
        # Pokušavamo sa pdfplumber jer PyPDF2 često griješi kod kolona
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"

        # Ako pdfplumber ne izvuče ništa, probaj PyPDF2 (rezervna varijanta)
        if not full_text.strip():
            import PyPDF2

            pdf_file.seek(0)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            for page in pdf_reader.pages:
                full_text += page.extract_text()

        # --- DEBUG: Odkomentariši liniju ispod ako i dalje ne radi da vidiš šta parser vidi ---
        # print("DEBUG TEXT:\n", full_text)

        # 1. Pronalaženje datuma
        datum_match = re.search(
            r"(?:na dan|Datum izvoda|Datum)[:\s]+(\d{2})\.(\d{2})\.(\d{4})",
            full_text,
            re.IGNORECASE,
        )
        if not datum_match:
            datum_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", full_text)

        datum = date.today()
        if datum_match:
            dan, mj, god = datum_match.groups()
            datum = date(int(god), int(mj), int(dan))

        # 2. ATOS BANKA - LOGIKA
        # Tražimo red koji sadrži PROMET i dva decimalna broja na kraju
        # Poboljšani regex koji ignoriše sve između riječi PROMET i cifara
        atos_pattern = re.compile(
            r"UKUPAN\s+PROMET.*?([\d\.,]+\.\d{2})\s+([\d\.,]+\.\d{2})",
            re.IGNORECASE | re.DOTALL,
        )

        atos_match = atos_pattern.search(full_text)

        if atos_match:
            # Čistimo brojeve od zareza (separator hiljada)
            val1_raw = atos_match.group(1).replace(",", "")
            val2_raw = atos_match.group(2).replace(",", "")

            rashod = Decimal(val1_raw)
            prihod = Decimal(val2_raw)

            if rashod > 0:
                transakcije.append(
                    {"datum": datum, "opis": "Ukupno rashodi (Atos)", "iznos": -rashod}
                )
            if prihod > 0:
                transakcije.append(
                    {"datum": datum, "opis": "Ukupno prihodi (Atos)", "iznos": prihod}
                )

            if transakcije:
                return transakcije

        # 3. NLB BANKA - LOGIKA
        nlb_match = re.search(
            r"(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+\d{1,3}(?:\.\d{3})*,\d{2}\s*Ukupno duguje",
            full_text,
        )

        if nlb_match:
            rashod_str = nlb_match.group(1).replace(".", "").replace(",", ".")
            prihod_str = nlb_match.group(2).replace(".", "").replace(",", ".")

            rashod = Decimal(rashod_str)
            prihod = Decimal(prihod_str)

            if rashod > 0:
                transakcije.append(
                    {"datum": datum, "opis": "Ukupno rashodi (NLB)", "iznos": -rashod}
                )
            if prihod > 0:
                transakcije.append(
                    {"datum": datum, "opis": "Ukupno prihodi (NLB)", "iznos": prihod}
                )

            return transakcije

    except Exception as e:
        print(f"❌ Parser error: {str(e)}")

    return []




# ============================================
# AUDIT & RATE LIMITING
# ============================================


def log_audit(
    user, model_name, object_id, action, old_value=None, new_value=None, request=None
):
    """Kreiraj audit log entry"""
    from .models import AuditLog

    ip_address = None
    if request:
        ip_address = get_client_ip(request)

    AuditLog.objects.create(
        user=user,
        model_name=model_name,
        object_id=object_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )


def check_rate_limit(user, action, limit=10, period_minutes=60):
    """Provjeri rate limit"""
    from .models import SystemLog

    time_threshold = timezone.now() - timedelta(minutes=period_minutes)
    recent_actions = SystemLog.objects.filter(
        user=user, action=action, timestamp__gte=time_threshold
    ).count()

    if recent_actions >= limit:
        return (
            False,
            f"Rate limit exceeded: maksimalno {limit} akcija u {period_minutes} minuta",
        )

    return True, None


