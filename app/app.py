# app/app.py
import os
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, session,
    send_file, url_for, flash
)
from dotenv import load_dotenv
from PIL import Image

# --- Importes "duros" que sí necesitamos al arrancar
from app.services.screenshot import capture_screenshot
from app.services.report import build_pdf

# ----------------------------------------------------------------------
# Init / config
# ----------------------------------------------------------------------
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'secret-dev')

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')

DRIVE_PARENT = os.environ.get('DRIVE_PARENT_FOLDER_ID')  # opcional
SHEETS_ID   = os.environ.get('SHEETS_SPREADSHEET_ID')    # opcional
PUBLIC_APP_URL = os.environ.get('PUBLIC_APP_URL')        # opcional
SUPPORT_PHONE = os.environ.get('SUPPORT_PHONE', '+573001234567')  # para tel:

# Historial en memoria (simple)
HISTORY = []

# Variables globales disponibles en todas las plantillas Jinja2
@app.context_processor
def inject_globals():
    # 'config' apunta a os.environ para usar config.get('VAR') en plantillas
    return {'SUPPORT_PHONE': SUPPORT_PHONE, 'config': os.environ}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def label_for(score: int):
    # Etiquetas simples por umbral (puedes ajustar a tu gusto)
    # Mantengo el orden de mayor a menor
    LABELS = [
        (90, "Excellent"),
        (80, "Great"),
        (70, "Good"),
        (60, "Fair"),
        (0,  "Needs work"),
    ]
    for th, lab in LABELS:
        if score >= th:
            return lab
    return "Needs work"


def _safe_imports_for_analyze():
    """
    Importa módulos opcionales *dentro* de la ruta /analyze para no romper el arranque.
    Devuelve tuplas de funciones o None si no existen.
    """
    extract_palette = None
    make_scores = None
    recommendations = None
    analyze_typography = analyze_layout = analyze_responsive = analyze_accessibility = None
    upload_file = None
    append_log = None

    # scoring básico (si tienes app.services.scoring)
    try:
        from app.services.scoring import make_scores, recommendations  # type: ignore
    except Exception:
        make_scores = None
        recommendations = None

    # insights (si tienes app.services.insights)
    try:
        from app.services.insights import (
            analyze_typography, analyze_layout, analyze_responsive, analyze_accessibility
        )  # type: ignore
    except Exception:
        analyze_typography = analyze_layout = analyze_responsive = analyze_accessibility = None

    # paleta (si tienes app.services.palette)
    try:
        from app.services.palette import extract_palette  # type: ignore
    except Exception:
        extract_palette = None

    # Drive (si tienes app.services.drive)
    try:
        from app.services.drive import upload_file  # type: ignore
    except Exception:
        upload_file = None

    # Sheets (si tienes app.services.sheets)
    try:
        from app.services.sheets import append_log  # type: ignore
    except Exception:
        append_log = None

    return {
        "extract_palette": extract_palette,
        "make_scores": make_scores,
        "recommendations": recommendations,
        "analyze_typography": analyze_typography,
        "analyze_layout": analyze_layout,
        "analyze_responsive": analyze_responsive,
        "analyze_accessibility": analyze_accessibility,
        "upload_file": upload_file,
        "append_log": append_log,
    }



@app.get("/")
def index():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('dashboard.html', history=HISTORY)


# ------------------ Auth: Login / Logout ------------------------------
@app.get("/login")
def login():
    return render_template('login.html')

@app.post("/login")
def do_login():
    email = request.form.get('email')
    pwd = request.form.get('password')
    if email == ADMIN_EMAIL and pwd == ADMIN_PASSWORD:
        session['user'] = {'email': email}
        return redirect(url_for('index'))
    flash('Invalid credentials')
    return redirect(url_for('login'))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))


# ------------------ Auth: Register (demo) -----------------------------
@app.get("/register")
def register():
    return render_template('register.html')

@app.post("/register")
def register_post():
    flash('Account created (demo). Please sign in.')
    return redirect(url_for('login'))


# ------------------ Auth: Forgot password (demo) ----------------------
@app.get("/forgot")
def forgot():
    return render_template('forgot.html')

@app.post("/forgot")
def forgot_post():
    email = request.form.get('email') or ''
    flash(f'Password reset link sent to {email} (demo).')
    return redirect(url_for('login'))


# ------------------ Auth: Google (placeholder) ------------------------
@app.get("/auth/google")
def google_auth():
    if not os.environ.get('GOOGLE_CLIENT_ID'):
        flash('Google Sign-In is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env')
        return redirect(url_for('login'))
    flash('Google Sign-In flow placeholder (configure OAuth to enable).')
    return redirect(url_for('login'))


# ------------------ Analyze ------------------------------------------
@app.post("/analyze")
def analyze():
    if not session.get('user'):
        return redirect(url_for('login'))

    url = request.form.get('url', '').strip()
    if not (url.startswith('http://') or url.startswith('https://')):
        flash('Please enter a valid URL including https://')
        return redirect(url_for('index'))

    # Imports perezosos
    deps = _safe_imports_for_analyze()
    extract_palette = deps["extract_palette"]
    make_scores = deps["make_scores"]
    recommendations = deps["recommendations"]
    analyze_typography = deps["analyze_typography"]
    analyze_layout = deps["analyze_layout"]
    analyze_responsive = deps["analyze_responsive"]
    analyze_accessibility = deps["analyze_accessibility"]
    upload_file = deps["upload_file"]
    append_log = deps["append_log"]

    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    out_dir = os.path.join(DATA_DIR, timestamp)
    os.makedirs(out_dir, exist_ok=True)

    shot_path = os.path.join(out_dir, 'screenshot.png')
    pdf_path  = os.path.join(out_dir, 'report.pdf')

    try:
        page_meta = capture_screenshot(url, shot_path)

        if not os.path.exists(shot_path):
            raise RuntimeError('Screenshot not created. Check antivirus exclusions or Playwright installation.')

        pil = Image.open(shot_path)
        html = page_meta.get('html', '') if page_meta else ''

        # ----- Scoring
        if make_scores:
            # WEIGHTS por defecto (si no tienes app.config)
            WEIGHTS = {
                'Typography': 0.22,
                'Color & Contrast': 0.22,
                'Layout & Structure': 0.22,
                'Responsive': 0.18,
                'Accessibility': 0.16,
            }
            overall, breakdown, meta = make_scores(pil, html, WEIGHTS)
        else:
            overall = 75
            breakdown = {
                'Typography': 76, 'Color & Contrast': 74,
                'Layout & Structure': 77, 'Responsive': 75, 'Accessibility': 73
            }
            meta = {}

        label = label_for(int(overall))
        tips_list = recommendations(breakdown, meta) if recommendations else []

        # ----- Palette + Insights (opcionales)
        if extract_palette:
            try:
                palette = extract_palette(pil, max_colors=16, min_percent=0.5)
            except Exception:
                palette = []
        else:
            palette = []

        insights = {}
        try:
            if analyze_typography:    insights['typography']    = analyze_typography(html)
            if analyze_layout:        insights['layout']        = analyze_layout(pil, html) if analyze_layout.__code__.co_argcount >= 2 else analyze_layout(html)
            if analyze_responsive:    insights['responsive']    = analyze_responsive(html)
            if analyze_accessibility: insights['accessibility'] = analyze_accessibility(html)
        except Exception:
            # si algo rompe aquí, seguimos sin insights
            pass

        # ----- PDF (usa tu report.build_pdf con la firma que enviaste)
        build_pdf(
            pdf_path,
            shot_path,
            url,
            page_meta.get('title', ''),
            float(overall),
            label,
            breakdown,
            tips_list,
            PUBLIC_APP_URL
        )

        # ----- Google Drive (opcional)
        drive_links = {}
        if DRIVE_PARENT and upload_file:
            try:
                up_shot = upload_file(shot_path, DRIVE_PARENT)
                up_pdf  = upload_file(pdf_path, DRIVE_PARENT)
                drive_links = {
                    'screenshot': up_shot.get('webViewLink'),
                    'pdf': up_pdf.get('webViewLink')
                }
            except Exception as e:
                drive_links = {'error': str(e)}

        # ----- Google Sheets (opcional)
        if SHEETS_ID and append_log:
            try:
                append_log(
                    SHEETS_ID,
                    [url, datetime.utcnow().isoformat(), int(overall), label, drive_links.get('pdf', '')]
                )
            except Exception:
                pass

        entry = {
            'url': url,
            'when': timestamp,
            'overall': int(overall),
            'overall_deg': int(overall) * 3.6,
            'label': label,
            'breakdown': breakdown,
            'tips': tips_list,
            'palette': palette,
            'insights': insights,
            'files': {'screenshot': shot_path, 'pdf': pdf_path},
            'drive': drive_links
        }
        HISTORY.insert(0, entry)

        session['last_console'] = (
            f"OK\nDATA_DIR={DATA_DIR}\nScreenshot: {shot_path}\nPDF: {pdf_path}\nDrive: {drive_links}"
        )
        return redirect(url_for('index'))

    except Exception as e:
        session['last_console'] = (
            f"ERROR: {e}\nDATA_DIR={DATA_DIR}\nshot_path={shot_path}\npdf_path={pdf_path}"
        )
        flash(f"Analysis failed: {e}")
        return redirect(url_for('index'))


# ------------------ Files / History / Console -------------------------
@app.get("/download/<when>/<kind>")
def download_file(when, kind):
    file_name = 'screenshot.png' if kind == 'screenshot' else 'report.pdf'
    path = os.path.join(DATA_DIR, when, file_name)
    if not os.path.exists(path):
        return f'File not found: {path}', 404
    # Para mostrar imágenes en <img> usamos send_file sin as_attachment
    if kind == 'screenshot':
        return send_file(path, mimetype='image/png')
    return send_file(path, as_attachment=True)

@app.get("/history")
def history():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('history.html', history=HISTORY)

@app.get("/console")
def console():
    return session.get('last_console', 'No logs yet.')

@app.get("/health")
def health():
    return "OK", 200


# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Arranca directo sin Flask CLI para evitar problemas de FLASK_APP
    app.run(debug=True, host="127.0.0.1", port=5000)
