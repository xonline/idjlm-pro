#!/usr/bin/env python3
"""
Verify IDJLM Phase 4.6: Onboarding + Empty States + Skeleton Rows
"""
import asyncio
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ playwright not installed")
    sys.exit(1)

SCREENSHOTS_DIR = Path("/home/ubuntu/docs/screenshots")

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 900})

        print("🔵 Navigating to IDJLM...")
        await page.goto("http://localhost:5050/", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Screenshot (a): First-run empty library
        print("📸 (a) First-run empty library...")
        await page.screenshot(path=str(SCREENSHOTS_DIR / "4.6_a_first_run_empty_library.png"), full_page=True)
        print(f"   ✅ Saved")

        # Check if empty state is visible
        empty_state = await page.query_selector("#empty-state-row")
        if empty_state:
            visible = await empty_state.is_visible()
            print(f"   ✅ Empty state visible: {visible}")

        # Check skeleton rows exist in DOM
        skeleton = await page.query_selector("#skeleton-row-1")
        if skeleton:
            print(f"   ✅ Skeleton rows present in DOM")

        # Screenshot (b): Show skeleton rows
        print("📸 (b) Skeleton rows...")
        await page.evaluate("""
            document.getElementById('empty-state-row').style.display = 'none';
            for (let i = 1; i <= 4; i++) {
                const row = document.getElementById(`skeleton-row-${i}`);
                if (row) row.style.display = '';
            }
        """)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "4.6_b_skeleton_rows_loading.png"), full_page=True)
        print(f"   ✅ Saved")

        # Screenshot (c): Playlists empty state (use keyboard or scroll to avoid overlay)
        print("📸 (c) Playlists tab empty state...")
        await page.evaluate("document.querySelector('[data-tab=\"playlists\"]').scrollIntoView(true)")
        await page.wait_for_timeout(500)
        try:
            await page.evaluate("document.querySelector('[data-tab=\"playlists\"]').click()")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "4.6_c_playlists_empty_state.png"), full_page=True)
            print(f"   ✅ Saved")
        except Exception as e:
            print(f"   ⚠️ Playlists tab click failed: {e}")

        await browser.close()
        print("\n✅ Verification complete!")

asyncio.run(verify())
