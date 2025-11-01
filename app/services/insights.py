# app/services/insights.py
from __future__ import annotations
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple
import re
from PIL import Image
import numpy as np

_font_family_re = re.compile(r"font-family\s*:\s*([^;}{]+)", re.I)
_font_size_re   = re.compile(r"font-size\s*:\s*([0-9.]+)(px|rem|em|%)", re.I)

def _find_font_families(html: str) -> List[str]:
    fams = []
    soup = BeautifulSoup(html or "", "html.parser")
    # 1) Google Fonts / Adobe Fonts hints
    for ln in soup.find_all("link", href=True):
        href = ln["href"]
        if "fonts.googleapis.com" in href:
            # e.g. family=Inter:wght@400;700
            m = re.findall(r"family=([^:&]+)", href)
            fams.extend([x.replace("+", " ") for x in m])
        if "use.typekit.net" in href:
            fams.append("Adobe Fonts (Typekit)")
    # 2) style blocks / inline styles
    for st in soup.find_all("style"):
        for m in _font_family_re.findall(st.get_text() or ""):
            fams.append(m.strip())
    for el in soup.find_all(style=True):
        for m in _font_family_re.findall(el.get("style") or ""):
            fams.append(m.strip())
    # 3) class-based hints (Tailwind etc.)
    class_text = " ".join(" ".join(el.get("class", [])) for el in soup.find_all(True))
    if "font-sans" in class_text: fams.append("sans-serif")
    if "font-serif" in class_text: fams.append("serif")
    if "font-mono" in class_text: fams.append("monospace")

    # Normalize, split stacks: "Inter, system-ui, -apple-system"
    clean = []
    for f in fams:
        parts = [p.strip().strip("'\"") for p in re.split(r",\s*", f)]
        for p in parts:
            if p and p not in clean:
                clean.append(p)
    return clean[:8]

def _find_font_sizes(html: str) -> List[str]:
    sizes = []
    soup = BeautifulSoup(html or "", "html.parser")
    # from style tags
    for st in soup.find_all("style"):
        for m in _font_size_re.findall(st.get_text() or ""):
            sizes.append("".join(m))
    # inline
    for el in soup.find_all(style=True):
        for m in _font_size_re.findall(el.get("style") or ""):
            sizes.append("".join(m))
    # Tailwind style hints
    classes = " ".join(" ".join(el.get("class", [])) for el in soup.find_all(True))
    for cls in re.findall(r"\btext-([xsmlg0-9.-]+)\b", classes):
        sizes.append(f"text-{cls}")
    # normalize unique small set
    out = []
    for s in sizes:
        if s not in out:
            out.append(s)
        if len(out) >= 10:
            break
    return out

def _headings_count(html: str) -> Dict[str, int]:
    soup = BeautifulSoup(html or "", "html.parser")
    return {f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1, 7)}

def analyze_typography(html: str) -> Dict:
    fams  = _find_font_families(html)
    sizes = _find_font_sizes(html)
    heads = _headings_count(html)
    return {
        "families": fams,
        "sizes": sizes,
        "headings": heads,
        "notes": "Detected via link/style/inlines and class hints."
    }

def analyze_layout(pil: Image.Image, html: str) -> Dict:
    # Whitespace ratio by brightness (very light or very dark solids count as negative space)
    im = pil.convert("L")
    arr = np.asarray(im, dtype=np.uint8)
    bright = (arr > 240).sum()
    dark   = (arr < 16).sum()
    total  = arr.size
    whitespace_pct = round(((bright + dark) / total) * 100.0, 2)

    soup = BeautifulSoup(html or "", "html.parser")
    txt = " ".join(" ".join(el.get("class", [])) for el in soup.find_all(True))
    uses_grid = ("grid" in txt) or any("display:grid" in (el.get("style") or "") for el in soup.find_all(style=True))
    uses_flex = ("flex" in txt) or any("display:flex" in (el.get("style") or "") for el in soup.find_all(style=True))

    return {
        "whitespace_pct": whitespace_pct,
        "grid": bool(uses_grid),
        "flex": bool(uses_flex),
        "notes": "Estimated whitespace from luminance extremes; grid/flex via classes/styles."
    }

def analyze_responsive(html: str) -> Dict:
    soup = BeautifulSoup(html or "", "html.parser")
    has_viewport = bool(soup.find("meta", attrs={"name":"viewport"}))
    styles = "\n".join(st.get_text() or "" for st in soup.find_all("style"))
    media_q = len(re.findall(r"@media", styles))
    classes = " ".join(" ".join(el.get("class", [])) for el in soup.find_all(True))
    tw_counts = {
        "sm": classes.count("sm:"),
        "md": classes.count("md:"),
        "lg": classes.count("lg:"),
        "xl": classes.count("xl:"),
        "2xl": classes.count("2xl:")
    }
    notes = "Has viewport meta" if has_viewport else "Missing viewport meta"
    return {"viewport": has_viewport, "media_queries": media_q, "tw": tw_counts, "notes": notes}

def analyze_accessibility(html: str) -> Dict:
    soup = BeautifulSoup(html or "", "html.parser")
    imgs = soup.find_all("img")
    total_imgs = len(imgs)
    no_alt = sum(1 for i in imgs if not i.get("alt"))
    aria  = len(soup.find_all(attrs={"aria-*": True}))  # fallback: count attributes that start with aria-
    # Better aria count:
    aria = sum(1 for el in soup.find_all(True) for a in el.attrs.keys() if str(a).lower().startswith("aria-"))
    roles = sum(1 for el in soup.find_all(attrs={"role": True}))
    labels = len(soup.find_all("label"))
    return {
        "images_total": total_imgs,
        "images_without_alt": no_alt,
        "aria_attrs": aria,
        "roles": roles,
        "labels": labels,
        "notes": "Alt/ARIA/roles/labels counted from DOM."
    }
