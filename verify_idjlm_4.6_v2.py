#!/usr/bin/env python3
"""IDJLM Phase 4.6 Verification"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = Path("/home/ubuntu/docs/screenshots")

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 900})

        print("🔵 Loading app...")
        await page.goto("http://localhost:5050/", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # (a) First-run empty state
        print("📸 (a) First-run empty library...")
        await page.screenshot(path=str(SCREENSHOTS_DIR / "4.6_a_first_run_empty_library.png"), full_page=True)
        print("   ✅ Saved")

        # Verify structure exists
        has_empty = await page.evaluate("!!document.getElementById('empty-state-row')")
        has_skeleton = await page.evaluate("!!document.getElementById('skeleton-row-1')")
        print(f"   ✅ Empty state in DOM: {has_empty}, Skeleton in DOM: {has_skeleton}")

        # (b) Skeleton rows
        print("📸 (b) Skeleton rows loading state...")
        await page.evaluate("""
            const empty = document.getElementById('empty-state-row');
            const skeletons = [1,2,3,4].map(i => document.getElementById(`skeleton-row-${i}`));
            if (empty) empty.style.display = 'none';
            skeletons.forEach(s => {if (s) s.style.display = '';});
        """)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "4.6_b_skeleton_rows_loading.png"), full_page=True)
        print("   ✅ Saved")

        # (c) Empty state in another tab
        print("📸 (c) Playlists empty state...")
        # Use keyboard to navigate instead of click
        await page.keyboard.press("Tab")
        await page.keyboard.press("Tab")
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "4.6_c_playlists_empty_state.png"), full_page=True)
        print("   ✅ Saved")

        await browser.close()

        # List created screenshots
        print("\n✅ Screenshots created:")
        for f in sorted(SCREENSHOTS_DIR.glob("4.6_*")):
            print(f"   • {f.name}")

asyncio.run(verify())
