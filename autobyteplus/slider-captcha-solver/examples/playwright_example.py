"""Minimal example: solve a slider captcha with Playwright.

pip install slider-captcha-solver[playwright]
playwright install chromium
"""
from playwright.sync_api import sync_playwright
from slider_captcha_solver import try_solve_slider

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com/login")
    # ... fill credentials and submit until the captcha appears ...

    if try_solve_slider(page, max_attempts=3):
        print("captcha solved, continuing login...")
        # ... wait for redirect / session ...
    else:
        print("auto-solve failed, fall back to manual handling")

    browser.close()
