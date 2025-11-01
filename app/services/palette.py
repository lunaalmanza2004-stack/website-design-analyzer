from PIL import Image
from collections import Counter
from typing import List, Dict, Tuple
import colorsys
import numpy as np

try:

    from skimage import filters
except Exception:
    filters = None

def _rgb_to_hex(t):
    return "#{:02X}{:02X}{:02X}".format(*t)

def _downscale(img: Image.Image, max_side=640) -> Image.Image:
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1.0:
        return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img.copy()

def _top_saturated(img: Image.Image, k: int = 8, sat_thr: float = 0.50, val_min: float = 0.22):
    """
    Colores muy saturados, aunque sean pequeños (útil para logos/CTAs).
    """
    base = _downscale(img, 600).convert("RGB")
    arr = np.asarray(base, dtype=np.uint8)
    r, g, b = [arr[..., i].astype(np.float32)/255.0 for i in range(3)]
    # HSV
    h = np.zeros_like(r)
    s = np.zeros_like(r)
    v = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    diff = v - minc + 1e-8
    s = diff / (v + 1e-8)
    # Filtro por saturación/valor
    mask = (s >= sat_thr) & (v >= val_min)
    if not np.any(mask):
        return []
    rgbs = arr[mask].reshape(-1, 3)
    cnt = Counter(map(tuple, rgbs))
    out = []
    for rgb, _ in cnt.most_common(50):
        out.append({"hex": _rgb_to_hex(rgb), "pct": 0.0, "rgb": rgb})
        if len(out) >= k:
            break
    return out

def _edge_accent_colors(img: Image.Image, k: int = 8, edge_top_ratio: float = 0.15, sat_thr=0.45, val_min=0.20):
    """
    Colores cerca de bordes (logos/textos), para captar detalles chicos.
    """
    if filters is None:
        return []
    base = _downscale(img, 640).convert("RGB")
    gray = np.asarray(base.convert("L"), dtype=np.float32)/255.0
    sob = filters.sobel(gray)
    # Selecciona top % de bordes
    thr = np.quantile(sob, 1.0 - edge_top_ratio)
    mask_edge = sob >= thr
    arr = np.asarray(base, dtype=np.uint8)
    if not np.any(mask_edge):
        return []
    edge_rgbs = arr[mask_edge].reshape(-1, 3)

    # Filtra por saturación
    r, g, b = edge_rgbs[:,0]/255.0, edge_rgbs[:,1]/255.0, edge_rgbs[:,2]/255.0
    v = np.maximum.reduce([r,g,b])
    minc = np.minimum.reduce([r,g,b])
    s = (v - minc) / (v + 1e-8)
    good = (s >= sat_thr) & (v >= val_min)
    if not np.any(good):
        return []

    pick = edge_rgbs[good]
    cnt = Counter(map(tuple, map(tuple, pick)))
    out = []
    for rgb, _ in cnt.most_common(50):
        out.append({"hex": _rgb_to_hex(rgb), "pct": 0.0, "rgb": rgb})
        if len(out) >= k:
            break
    return out

def extract_palette(pil_image: Image.Image, max_colors: int = 16, min_percent: float = 0.5):
    """
    Mezcla:
      1) Dominantes (ADAPTIVE) con % >= min_percent
      2) Muy saturados (aunque chicos)
      3) Cerca de bordes (logos/íconos), con filtro de saturación
    """
    base = _downscale(pil_image, 768).convert("RGB")

    # Dominantes
    pal = base.convert("P", palette=Image.ADAPTIVE, colors=max_colors).convert("RGB")
    pixels = list(pal.getdata())
    total = len(pixels)
    cnt = Counter(pixels)
    dominant = []
    for rgb, n in cnt.most_common(max_colors):
        pct = (n / total) * 100.0
        if pct >= min_percent:
            dominant.append({"hex": _rgb_to_hex(rgb), "pct": round(pct, 2), "rgb": rgb})

    # Saturados (brand hints)
    sat = _top_saturated(base, k=8, sat_thr=0.48, val_min=0.24)
    # Bordes + saturados
    edge = _edge_accent_colors(base, k=10, edge_top_ratio=0.12, sat_thr=0.42, val_min=0.22)

    # Merge únicos por hex manteniendo orden
    seen = set()
    out = []
    for item in (dominant + sat + edge):
        if item["hex"] not in seen:
            seen.add(item["hex"])
            out.append(item)

    if not out and cnt:
        rgb, n = next(iter(cnt.items()))
        out = [{"hex": _rgb_to_hex(rgb), "pct": 100.0, "rgb": rgb}]
    return out[:28]
