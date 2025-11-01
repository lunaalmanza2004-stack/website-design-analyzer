# app/services/report.py
# ------------------------------------------------------------
# PDF limpio:
#  - Header azul con fecha UTC
#  - Subtítulo "Report generated for: <URL>" + Title
#  - Página 1: Screenshot a ancho útil (slicing si es muy largo)
#  - Página 2: Tabla de KPIs + Gráfico lineal de métricas (0–100)
#  - Página 3: Recommendations
#
# Firma compatible con app/app.py:
#   build_pdf(out_path, screenshot_path, url, page_title,
#             overall_score, label, breakdown, tips, public_app_url)
# ------------------------------------------------------------
import os
import io
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
LINE_H = 6 * mm

# Colores por métrica (coinciden con la UI)
METRIC_COLORS = {
    "Typography": colors.HexColor("#60A5FA"),
    "Color & Contrast": colors.HexColor("#F87171"),
    "Layout & Structure": colors.HexColor("#FBBF24"),
    "Responsive": colors.HexColor("#34D399"),
    "Accessibility": colors.HexColor("#A78BFA"),
}

ORDER = ["Typography", "Color & Contrast", "Layout & Structure", "Responsive", "Accessibility"]

# ------------------------------------------------------------
# Dibujo básico
# ------------------------------------------------------------
def _draw_header(c: canvas.Canvas, title: str, when_text: str):
    bar_h = 14 * mm
    c.setFillColor(colors.HexColor("#2563EB"))
    c.roundRect(MARGIN, PAGE_H - MARGIN - bar_h, PAGE_W - 2*MARGIN, bar_h, 6, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN + 8, PAGE_H - MARGIN - bar_h + 4, title)

    if when_text:
        c.setFont("Helvetica", 10)
        c.drawRightString(PAGE_W - MARGIN - 8, PAGE_H - MARGIN - bar_h + 6, when_text)

def _kv(c: canvas.Canvas, x: float, y: float, k: str, v: str):
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.black)
    c.drawString(x, y, k)
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#0B0F24"))
    c.drawString(x + 70, y, v or "—")

def _wrap_lines(c: canvas.Canvas, text: str, font: str, size: int, max_w: float) -> List[str]:
    c.setFont(font, size)
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines

def _draw_img_buf(c: canvas.Canvas, pil_img: Image.Image, x: float, y: float, w: float, h: float):
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=92, optimize=True)
    buf.seek(0)
    c.drawImage(ImageReader(buf), x, y, width=w, height=h, preserveAspectRatio=False, mask='auto')

# ------------------------------------------------------------
# Screenshot a ancho útil con slicing
# ------------------------------------------------------------
def _draw_screenshot_sliced(c: canvas.Canvas, img_path: str, top_free_px: float, first_page: bool):
    usable_w = PAGE_W - 2 * MARGIN
    usable_h = PAGE_H - 2 * MARGIN

    im = Image.open(img_path).convert("RGB")
    img_w, img_h = im.size

    scale = usable_w / float(img_w)
    scaled_w = usable_w
    scaled_h = img_h * scale

    first_page_room = usable_h - top_free_px if first_page else usable_h
    y_cursor = PAGE_H - MARGIN - top_free_px

    if scaled_h <= first_page_room + 0.1:
        resized = im.resize((int(scaled_w), int(scaled_h)), Image.LANCZOS)
        _draw_img_buf(c, resized, MARGIN, y_cursor - scaled_h, scaled_w, scaled_h)
        im.close()
        return

    slice_h_pts = max(1, first_page_room if first_page else usable_h)
    slice_h_px = max(1, int(slice_h_pts / scale))

    y_px = 0
    first = True
    while y_px < img_h:
        h_px = min(slice_h_px, img_h - y_px)
        box = (0, y_px, img_w, y_px + h_px)
        chunk = im.crop(box)
        chunk_h_pts = h_px * scale
        if first:
            _draw_img_buf(c, chunk.resize((int(scaled_w), int(chunk_h_pts)), Image.LANCZOS),
                          MARGIN, y_cursor - chunk_h_pts, scaled_w, chunk_h_pts)
            first = False
        else:
            c.showPage()
            _draw_header(c, "Website Design Analyzer — Report", "")
            _draw_img_buf(c, chunk.resize((int(scaled_w), int(chunk_h_pts)), Image.LANCZOS),
                          MARGIN, PAGE_H - MARGIN - chunk_h_pts, scaled_w, chunk_h_pts)
        y_px += h_px
    im.close()

# ------------------------------------------------------------
# Tabla de scores
# ------------------------------------------------------------
def _table_scores(c: canvas.Canvas, x: float, y_top: float, rows: List[List[str]], w: float):
    table = Table(rows, colWidths=[w * 0.6, w * 0.4])
    table.setStyle(TableStyle([
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 11),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E5F0FF")),
        ("FONT", (0,1), (-1,-1), "Helvetica", 10),
        ("TEXTCOLOR", (0,1), (-1,-1), colors.HexColor("#0B0F24")),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#BFD7FF")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.HexColor("#F6FAFF")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (1,1), (1,-1), "RIGHT"),
    ]))
    tw, th = table.wrapOn(c, w, PAGE_H)
    table.drawOn(c, x, y_top - th)
    return th

# ------------------------------------------------------------
# Gráfico lineal (0–100) con puntos y etiquetas
# ------------------------------------------------------------
def _line_chart(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    w: float,
    h: float,
    series: List[Tuple[str, float]],
):
    """
    Dibuja un gráfico lineal sencillo:
      - Eje Y 0–100 con grid 0,25,50,75,100
      - Puntos por métrica conectados
      - Etiquetas abajo
    """
    # Marco
    c.setLineWidth(0.7)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(x, y_top - h, w, h, stroke=1, fill=0)

    # Grid horizontal
    c.setLineWidth(0.5)
    for v in [0, 25, 50, 75, 100]:
        yy = (y_top - h) + (v/100.0)*h
        c.setStrokeColor(colors.HexColor("#E5E7EB") if v not in (0,100) else colors.HexColor("#CBD5E1"))
        c.line(x, yy, x + w, yy)
        # labels Y
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#6B7280"))
        c.drawString(x - 18, yy - 3, f"{v}")

    if not series:
        return

    # Puntos (distribución uniforme en X)
    n = len(series)
    step = w / max(1, n - 1)
    pts = []
    for i, (_, val) in enumerate(series):
        xx = x + i * step
        val = max(0, min(100, float(val)))
        yy = (y_top - h) + (val/100.0)*h
        pts.append((xx, yy))

    # Línea
    c.setStrokeColor(colors.HexColor("#2563EB"))
    c.setLineWidth(1.4)
    for i in range(len(pts) - 1):
        c.line(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])

    # Puntos y etiquetas de valor
    for (xx, yy), (name, val) in zip(pts, series):
        # punto
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor("#2563EB")); c.setLineWidth(1)
        c.circle(xx, yy, 2.8, stroke=1, fill=1)
        # valor
        lab = f"{int(round(val))}"
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#1F2937"))
        c.drawString(xx - 6, min(y_top - 7, yy + 6), lab)

    # Etiquetas X (métricas)
    c.setFont("Helvetica", 8)
    for i, (name, _) in enumerate(series):
        xx = x + i * step
        c.setFillColor(METRIC_COLORS.get(name, colors.HexColor("#6B7280")))
        c.drawCentredString(xx, y_top - h - 12, name.split()[0])  # primera palabra para no recargar

# ------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------
def _recommendations(c: canvas.Canvas, tips: List[str], y_start: float):
    y = y_start
    x = MARGIN
    w = PAGE_W - 2*MARGIN

    c.setFont("Helvetica-Bold", 12); c.setFillColor(colors.black)
    c.drawString(x, y - 12, "Recommendations")
    y -= 18

    if not tips:
        c.setFont("Helvetica-Oblique", 10); c.setFillColor(colors.HexColor("#222833"))
        c.drawString(x, y - 10, "No recommendations. Looks great!")
        return

    c.setFont("Helvetica", 10); c.setFillColor(colors.HexColor("#222833"))
    for tip in tips:
        if y - 14 < MARGIN:
            c.showPage(); _draw_header(c, "Website Design Analyzer — Report", ""); y = PAGE_H - MARGIN - 18*mm
            c.setFont("Helvetica", 10); c.setFillColor(colors.HexColor("#222833"))
        # viñeta
        c.setFillColor(colors.HexColor("#2563EB"))
        c.circle(x + 2, y - 6, 2, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#222833"))
        lines = _wrap_lines(c, tip, "Helvetica", 10, w - 14)
        c.drawString(x + 10, y - 10, lines[0])
        yy = y - 10
        for ln in lines[1:]:
            yy -= 12
            c.drawString(x + 10, yy, ln)
        y = yy - 8

# ------------------------------------------------------------
# API principal
# ------------------------------------------------------------
def build_pdf(
    out_path: str,
    screenshot_path: Optional[str],
    url: str,
    page_title: str,
    overall_score: float,
    label: str,
    breakdown: Dict[str, float],
    tips: List[str],
    public_app_url: Optional[str],   # ignorado (dejamos el subtítulo "Report generated for")
):
    when_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    c = canvas.Canvas(out_path, pagesize=A4)

    # ===== Página 1: encabezado + meta + screenshot =====
    _draw_header(c, "Website Design Analyzer — Report", when_str)

    y = PAGE_H - MARGIN - 18 * mm
    c.setFont("Helvetica", 10); c.setFillColor(colors.HexColor("#0B0F24"))
    c.drawString(MARGIN, y, f"Report generated for: {url or '—'}")
    y -= LINE_H
    _kv(c, MARGIN, y, "Title:", page_title or "—")
    y -= 8

    drew_any_image = False
    top_used = (PAGE_H - y - MARGIN)
    if screenshot_path and os.path.isfile(screenshot_path):
        try:
            _draw_screenshot_sliced(c, screenshot_path, top_used, first_page=True)
            drew_any_image = True
        except Exception:
            pass
    if not drew_any_image:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(colors.HexColor("#0B0F24"))
        c.drawString(MARGIN, y, "Screenshot could not be rendered.")

    # ===== Página 2: Scores + Line Chart =====
    c.showPage()
    _draw_header(c, "Website Design Analyzer — Report", when_str)
    y = PAGE_H - MARGIN - 18 * mm

    rows = [["Metric", "Score"]]
    rows.append(["Overall", f"{int(round(overall_score))}/100" + (f" — {label}" if label else "")])
    for k in ORDER:
        if k in breakdown:
            rows.append([k, f"{int(round(breakdown.get(k, 0))):d}/100"])
    for k, v in breakdown.items():
        if k not in ORDER:
            rows.append([k, f"{int(round(v))}/100"])

    th = _table_scores(c, MARGIN, y, rows, w=PAGE_W - 2*MARGIN)
    y -= (th + 18)

    # Gráfico lineal
    series = []
    for k in ORDER:
        if k in breakdown:
            series.append((k, float(breakdown[k])))
    chart_h = 60 * mm
    _line_chart(c, MARGIN, y, PAGE_W - 2*MARGIN, chart_h, series)

    # ===== Página 3: Recommendations =====
    c.showPage()
    _draw_header(c, "Website Design Analyzer — Report", when_str)
    y = PAGE_H - MARGIN - 18 * mm
    _recommendations(c, tips or [], y)

    c.save()
