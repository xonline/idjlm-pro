"""
IDJLM 1.2 screenshot harness — final.

Captures three states:
  v4.2.0-opsbar-idle.png       — fresh load, no ops running
  v4.2.0-opsbar-single.png    — one chip (analysis-like)
  v4.2.0-opsbar-multiple.png  — four concurrent chips at varying %
"""
import asyncio
import os
from playwright.async_api import async_playwright

OUT_DIR = "/home/ubuntu/projects/idjlm/docs/screenshots"
URL = "http://localhost:5050/"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )
        page = await context.new_page()
        page.on("pageerror", lambda err: print(f"[pageerror] {err}"))
        await page.goto(URL, wait_until="networkidle", timeout=15000)
        await page.wait_for_function("window.opsbar !== undefined", timeout=5000)
        await page.wait_for_timeout(2400)  # splash fade-out then settle

        # === IDLE: stats bar visible, no chips ===
        bar = await page.evaluate("""() => {
          const sb = document.getElementById('library-stats-bar');
          const r = sb.getBoundingClientRect();
          return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""")
        await page.screenshot(path=os.path.join(OUT_DIR, "v4.2.0-opsbar-idle.png"),
                              clip={"x": int(bar['x']) - 12, "y": int(bar['y']) - 12,
                                    "width": int(bar['w']) + 24, "height": int(bar['h']) + 24})
        print("✓ idle screenshot saved")

        # === MULTIPLE concurrent chips ===
        await page.evaluate("""() => {
          const h1 = window.opsbar.registerOp({id: 'demo-analyze', label: 'Analysing audio', kind: 'analyze'});
          window.opsbar.progress(h1, 18, 30, '');
          const h2 = window.opsbar.registerOp({id: 'demo-classify', label: 'Classifying genres', kind: 'classify'});
          window.opsbar.progress(h2, 42, 80, 'Rekordbox mapping');
          const h3 = window.opsbar.registerOp({id: 'demo-write', label: 'Writing tags', kind: 'write'});
          window.opsbar.progress(h3, 5, 12, 'ID3v2.4');
          const h4 = window.opsbar.registerOp({id: 'demo-cue', label: 'Analysing cue points', kind: 'cue'});
          window.opsbar.progress(h4, 1, 1, 'clave detection');
        }""")
        await page.wait_for_timeout(200)
        chip_count = await page.evaluate("document.querySelectorAll('.opsbar-chip').length")
        if chip_count < 4:
            raise RuntimeError(f"expected 4 chips concurrent, got {chip_count}")
        print(f"✓ concurrent chip count = {chip_count}")

        bar2 = await page.evaluate("""() => {
          const sb = document.getElementById('library-stats-bar');
          const r = sb.getBoundingClientRect();
          return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""")
        await page.screenshot(path=os.path.join(OUT_DIR, "v4.2.0-opsbar-multiple.png"),
                              clip={"x": int(bar2['x']) - 12, "y": int(bar2['y']) - 12,
                                    "width": int(bar2['w']) + 24, "height": int(bar2['h']) + 24})
        print("✓ multiple-chip screenshot saved")

        # === SINGLE chip: dismiss three, leaving one ===
        await page.evaluate("""() => {
          const cancels = document.querySelectorAll('.opsbar-chip-cancel');
          for (let i = 0; i < cancels.length - 1; i++) cancels[i].click();
        }""")
        await page.wait_for_timeout(1400)  # auto-remove after cancel/error
        chip_count_after = await page.evaluate("document.querySelectorAll('.opsbar-chip').length")
        print(f"✓ chips after cancelling 3 of 4 = {chip_count_after}")
        bar3 = await page.evaluate("""() => {
          const sb = document.getElementById('library-stats-bar');
          const r = sb.getBoundingClientRect();
          return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""")
        await page.screenshot(path=os.path.join(OUT_DIR, "v4.2.0-opsbar-single.png"),
                              clip={"x": int(bar3['x']) - 12, "y": int(bar3['y']) - 12,
                                    "width": int(bar3['w']) + 24, "height": int(bar3['h']) + 24})
        print("✓ single-chip screenshot saved")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
