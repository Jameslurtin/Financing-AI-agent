"""Optional browser integration check: pip install playwright, then run this file."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, "GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}
server = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", "8001"],
                          cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for attempt in range(60):
        try:
            if httpx.get("http://127.0.0.1:8001/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        raise RuntimeError("Test server did not start")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8001")
        page.get_by_role("button", name="Equipment", exact=True).click()
        page.get_by_role("button", name="Run assessment").click()
        page.locator("#result-content").wait_for(state="visible")
        assert page.locator("#result-category").inner_text() == "Equipment financing or leasing"
        assert page.locator("#fallback-notice").is_visible()
        with page.expect_download() as download:
            page.locator("#download-button").click()
        data = json.loads(Path(download.value.path()).read_text())
        assert data["assessment"]["recommended_financing"] == "Equipment financing or leasing"
        page.get_by_role("button", name="Human review", exact=True).click()
        assert page.locator("#result-content").is_hidden()
        page.get_by_role("button", name="Run assessment").click()
        page.locator("#review-notice").wait_for(state="visible")
        assert page.locator("#result-badge").inner_text() == "Human review needed"
        page.get_by_role("button", name="Cash flow", exact=True).click()
        page.get_by_role("radio", name="AI agent").check()
        page.get_by_role("button", name="Run assessment").click()
        page.locator("#result-content").wait_for(state="visible")
        assert page.locator("#result-category").inner_text() == "Invoice financing or factoring"
        assert page.locator("#detail-workflow").text_content() == "AI agent"
        page.locator('[name="requested_amount"]').fill("0")
        assert not page.locator('[name="requested_amount"]').evaluate("el => el.checkValidity()")
        page.get_by_role("button", name="Equipment", exact=True).click()
        page.route("**/agent-evaluate", lambda route: route.abort())
        page.get_by_role("button", name="Run assessment").click()
        page.locator("#form-error").wait_for(state="visible")
        assert page.locator("#submit-button").is_enabled()
        page.unroute("**/agent-evaluate")
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name="Run assessment").click()
        page.locator("#result-content").wait_for(state="visible")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not errors, errors
        page.screenshot(path=str(ROOT / "frontend-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1100})
        page.screenshot(path=str(ROOT / "frontend-desktop.png"), full_page=True)
        browser.close()
    print("Browser checks passed: both workflows, examples, review, fallback, download, validation, network error, mobile layout; no JS errors.")
finally:
    server.terminate()
    server.wait(timeout=10)

