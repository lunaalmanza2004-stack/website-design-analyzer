# app/services/screenshot.py
import os
import sys
import asyncio
from playwright.async_api import async_playwright
from .utils import ensure_dir

# En Windows usa Proactor (soporta subprocess)
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

async def _shoot(url: str, out_path: str, width=1440, height=900):
    ensure_dir(os.path.dirname(out_path))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-dev-shm-usage",
            "--no-sandbox"
        ])
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        # Cargar la página (algunas webs bloquean 'networkidle'); usa domcontentloaded y espera un poco.
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # Si no llega a networkidle, continuamos igual
        await page.screenshot(path=out_path, full_page=True)
        title = await page.title()
        html = await page.content()
        await browser.close()
        return {"title": title, "html": html}

def capture_screenshot(url: str, out_path: str):
    # Ejecuta la corrutina con un loop válido en cualquier hilo.
    try:
        return asyncio.run(_shoot(url, out_path))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_shoot(url, out_path))
        finally:
            loop.close()
