"""
Playwright-based end-to-end tests for the CKC Web UI.

These tests require a running CKC server at http://127.0.0.1:8000.
Install with: pip install playwright && playwright install chromium

Run: pytest tests/test_e2e_playwright.py -v --headed  (to see browser)
Run: pytest tests/test_e2e_playwright.py -v            (headless)
"""

from __future__ import annotations

import os

import pytest

try:
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError:
    pytest.skip("playwright not installed; skipping E2E tests", allow_module_level=True)

BASE_URL = os.environ.get("CKC_E2E_URL", "http://127.0.0.1:8000")
SAMPLE_PROJECT = os.environ.get("CKC_E2E_PROJECT", "")


@pytest.fixture(scope="session")
def browser():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    page.goto(BASE_URL, wait_until="networkidle")
    yield page
    page.close()


class TestPageLoad:
    """Verify the application loads and core DOM elements are present."""

    def test_title(self, page: Page):
        expect(page).to_have_title("CKC | 3D Code Knowledge Explorer")

    def test_meta_description(self, page: Page):
        meta = page.locator('meta[name="description"]')
        expect(meta).to_have_attribute("content", lambda c: "CKC" in c)

    def test_favicon_present(self, page: Page):
        link = page.locator('link[rel="icon"]')
        expect(link).to_have_count(1)

    def test_header_visible(self, page: Page):
        header = page.locator("header.app-header")
        expect(header).to_be_visible()

    def test_brand_text(self, page: Page):
        brand = page.locator(".brand-name")
        expect(brand).to_have_text("CKC")

    def test_3d_canvas_present(self, page: Page):
        canvas = page.locator("#graph-3d canvas")
        expect(canvas).to_have_count(1)

    def test_no_console_errors(self, page: Page):
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1000)
        assert len(errors) == 0, f"Console errors: {errors}"


class TestWelcomeOverlay:
    """Verify the welcome overlay appears when no project is loaded."""

    def test_welcome_shown_on_fresh_load(self, browser):
        context = browser.new_context()
        page = context.new_page()
        # Clear localStorage to simulate first visit
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.removeItem('ckc_project_path')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        welcome = page.locator("#welcome-overlay")
        expect(welcome).to_be_visible()
        page.close()
        context.close()


class TestSearchWorkflow:
    """Verify search autocomplete and node selection."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_project(self, page: Page):
        has_project = page.evaluate("!!window.state?.currentProject")
        if not has_project:
            pytest.skip("No project loaded; set CKC_E2E_PROJECT to test search")

    def test_search_focus_on_slash(self, page: Page):
        page.keyboard.press("/")
        search = page.locator("#command-bar")
        expect(search).to_be_focused()

    def test_search_autocomplete(self, page: Page):
        search = page.locator("#command-bar")
        search.click()
        search.fill("config")
        page.wait_for_timeout(500)
        dropdown = page.locator("#search-results-dropdown")
        expect(dropdown).not_to_have_class("closed")

    def test_search_result_click_opens_inspector(self, page: Page):
        search = page.locator("#command-bar")
        search.click()
        search.fill("config")
        page.wait_for_timeout(500)
        first_result = page.locator(".search-result-item").first
        first_result.click()
        panel = page.locator("#context-panel")
        expect(panel).not_to_have_class("closed")


class TestKeyboardShortcuts:
    """Verify global keyboard shortcuts."""

    def test_escape_closes_search_dropdown(self, page: Page):
        search = page.locator("#command-bar")
        search.click()
        search.fill("test")
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
        dropdown = page.locator("#search-results-dropdown")
        expect(dropdown).to_have_class(lambda c: "closed" in c)

    def test_l_opens_layers(self, page: Page):
        page.keyboard.press("l")
        popover = page.locator("#layers-popover")
        expect(popover).not_to_have_class("closed")

    def test_p_opens_project(self, page: Page):
        page.keyboard.press("p")
        popover = page.locator("#project-popover")
        expect(popover).not_to_have_class("closed")


class TestPopovers:
    """Verify popovers open/close and have correct ARIA attributes."""

    def test_project_popover_aria_expanded(self, page: Page):
        btn = page.locator("#project-pill-btn")
        expect(btn).to_have_attribute("aria-expanded", "false")
        btn.click()
        expect(btn).to_have_attribute("aria-expanded", "true")

    def test_layers_popover_aria_expanded(self, page: Page):
        btn = page.locator("#layers-toggle-btn")
        expect(btn).to_have_attribute("aria-expanded", "false")
        btn.click()
        expect(btn).to_have_attribute("aria-expanded", "true")

    def test_index_popover_aria_expanded(self, page: Page):
        btn = page.locator("#header-index-btn")
        expect(btn).to_have_attribute("aria-expanded", "false")
        btn.click()
        expect(btn).to_have_attribute("aria-expanded", "true")

    def test_escape_closes_all_popovers(self, page: Page):
        page.locator("#project-pill-btn").click()
        page.keyboard.press("Escape")
        expect(page.locator("#project-popover")).to_have_class(lambda c: "closed" in c)


class TestAPI:
    """Verify API endpoints respond correctly via browser fetch."""

    def test_health_endpoint(self, page: Page):
        result = page.evaluate("fetch('/api/health').then(r => r.json())")
        assert result["status"] == "ok"

    def test_samples_endpoint(self, page: Page):
        result = page.evaluate("fetch('/api/samples').then(r => r.json())")
        assert isinstance(result.get("samples"), list)

    def test_invalid_project_returns_400(self, page: Page):
        result = page.evaluate(
            "fetch('/api/status?project=').then(r => ({status: r.status}))"
        )
        assert result["status"] == 400

    def test_system_path_rejected(self, page: Page):
        result = page.evaluate(
            "fetch('/api/status?project=/etc').then(r => ({status: r.status}))"
        )
        assert result["status"] == 400


class TestGraphLegend:
    """Verify the graph legend behaves correctly."""

    def test_legend_hidden_when_no_project(self, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.removeItem('ckc_project_path')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        legend = page.locator("#graph-legend")
        expect(legend).to_have_class(lambda c: "hidden" in c)
        page.close()
        context.close()


class TestResponsive:
    """Verify responsive behavior at narrow viewports."""

    def test_480px_header_icons_only(self, browser):
        context = browser.new_context(viewport={"width": 480, "height": 800})
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        # At 480px, button text labels should be hidden
        btn_text = page.locator(".header-right .btn span")
        if btn_text.count() > 0:
            for i in range(btn_text.count()):
                expect(btn_text.nth(i)).not_to_be_visible()
        page.close()
        context.close()
