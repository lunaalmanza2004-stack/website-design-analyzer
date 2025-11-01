from PIL import Image
import numpy as np
from bs4 import BeautifulSoup
import io, re, math

def _contrast_ratio(l1, l2):
    L1, L2 = (l1+0.05, l2+0.05)
    return max(L1, L2) / min(L1, L2)

def _relative_luminance(rgb):
    srgb = np.array(rgb)/255.0
    a = np.where(srgb <= 0.03928, srgb/12.92, ((srgb+0.055)/1.055)**2.4)
    return 0.2126*a[...,0] + 0.7152*a[...,1] + 0.0722*a[...,2]

def analyze_image_colors(pil_image: Image.Image):
    # Sample pixels on a grid
    img = pil_image.resize((256, int(256*pil_image.height/pil_image.width)))
    arr = np.array(img)[..., :3]
    # Estimate overall contrast (stdev of luminance) and dominant hues (k-means-like bins)

    lum = _relative_luminance(arr)
    contrast = float(np.std(lum))
    # Simulate color harmony by counting distinct hue bins
    hsv = np.array(Image.fromarray(arr.astype('uint8')).convert('HSV'))
    hue_bins = np.histogram(hsv[...,0], bins=12, range=(0,255))[0]
    diversity = (hue_bins>arr.size*0.0005).sum() / 12.0
    return contrast, diversity

def analyze_typography(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    texts = soup.find_all(text=True)
    # Proxy: count headings, presence of h1/h2, word lengths, inline styles font-size
    headings = len(soup.find_all(re.compile('^h[1-6]$')))
    h1 = bool(soup.find('h1'))
    h2 = bool(soup.find('h2'))
    inline_sizes = len(soup.select('[style*="font-size"], [class*="text-"]'))
    # Heuristic score 0-100
    score = 50
    score += 10 if h1 else -10
    score += 8 if h2 else 0
    score += min(20, headings*3)
    score += min(20, inline_sizes*0.5)
    return max(0, min(100, score)), {"headings": headings, "has_h1": h1, "has_h2": h2}

def analyze_layout(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    # Proxy: grid/flex usage, sectioning elements, whitespace via br/p length
    grids = len(soup.select('[class*="grid"], [class*="flex"]'))
    sections = len(soup.find_all(['section','article','main','nav','aside','header','footer']))
    paragraphs = len(soup.find_all('p'))
    score = 40 + min(30, grids*2) + min(30, sections*3)
    score = max(0, min(100, score))
    return score, {"grids": grids, "sections": sections, "paragraphs": paragraphs}

def analyze_responsive(html: str):
    # Proxy: presence of meta viewport & CSS classes hints
    viewport = 'viewport' in html.lower()
    md_classes = html.count('md:') + html.count('@media')
    score = 50 + (25 if viewport else -10) + min(35, md_classes*0.5)
    score = max(0, min(100, score))
    return score, {"viewport": viewport, "mq_classes": md_classes}

def analyze_accessibility(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    alts = soup.find_all('img')
    imgs = len(alts)
    with_alt = sum(1 for i in alts if i.get('alt'))
    aria = len(soup.select('[aria-label], [role]'))
    labels = len(soup.find_all('label'))
    score = 40 + min(30, (with_alt/max(1,imgs))*30) + min(30, aria+labels)
    return max(0, min(100, int(score))), {"imgs": imgs, "with_alt": with_alt, "aria_or_role": aria, "labels": labels}

def make_scores(pil_image, html, weights):
    # Image-based metrics
    contrast, diversity = analyze_image_colors(pil_image)
    # Map to 0-100
    color_score = int(min(100, max(0, (contrast*180) + diversity*40)))
    typo_score, typo_meta = analyze_typography(html)
    layout_score, layout_meta = analyze_layout(html)
    resp_score, resp_meta = analyze_responsive(html)
    a11y_score, a11y_meta = analyze_accessibility(html)
    breakdown = {
        'Typography': typo_score,
        'Color & Contrast': color_score,
        'Layout & Structure': layout_score,
        'Responsive': resp_score,
        'Accessibility': a11y_score,
    }
    overall = int(sum(breakdown[k]*weights[k] for k in breakdown))
    meta = {
        'color': {'contrast_sd': float(contrast), 'hue_diversity': float(diversity)},
        'typography': typo_meta,
        'layout': layout_meta,
        'responsive': resp_meta,
        'accessibility': a11y_meta
    }
    return overall, breakdown, meta

def recommendations(breakdown, meta):
    tips = []
    if breakdown['Typography'] < 80:
        tips.append('Improve typographic hierarchy and legibility (ensure clear H1/H2, adequate font sizes, and line-height).')
    if breakdown['Layout & Structure'] < 80:
        tips.append('Optimize whitespace and layout structure; use semantic sections and consistent spacing.')
    if breakdown['Color & Contrast'] < 80:
        tips.append('Increase color contrast and reduce overly similar hues to enhance readability.')
    if breakdown['Responsive'] < 90:
        tips.append('Add or refine responsive breakpoints and viewport meta for small screens.')
    if breakdown['Accessibility'] < 85:
        tips.append('Add ARIA labels, ensure alt text on images, and improve keyboard navigation focus states.')
    if not tips:
        tips.append('Great job! Minor polish only: audit interactive focus styles and motion preferences.')
    return tips
