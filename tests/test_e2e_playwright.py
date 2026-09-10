"""
Playwright-based end-to-end tests for the CKC Web UI.

These tests require a running CKC server at http://127.0.0.1:8000.
Install with: pip install playwright && playwright install chromium

Run: pytest tests/test_e2e_playwright.py -v --headed  (to see browser)
Run: pytest tests/test_e2e_playwright.py -v            (headless)
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

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
        expect(meta).to_have_attribute("content", re.compile(r"CKC"))

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

    def test_folder_browser_opens_by_default(self, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate(
            "sessionStorage.removeItem('ckc_project_path'); "
            "localStorage.removeItem('ckc_project_path')"
        )
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        dialog = page.locator("#folder-browser-dialog")
        expect(dialog).to_be_visible()
        page.close()
        context.close()


class TestFolderBrowserFlow:
    """Verify folder browser dialog interactions, recovery, and dismissal."""

    def test_dialog_closes_on_escape(self, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate(
            "sessionStorage.removeItem('ckc_project_path'); "
            "localStorage.removeItem('ckc_project_path')"
        )
        page.reload(wait_until="networkidle")
        dialog = page.locator("#folder-browser-dialog")
        expect(dialog).to_be_visible()
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        page.close()
        context.close()

    def test_dialog_closes_on_close_button(self, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate(
            "sessionStorage.removeItem('ckc_project_path'); "
            "localStorage.removeItem('ckc_project_path')"
        )
        page.reload(wait_until="networkidle")
        dialog = page.locator("#folder-browser-dialog")
        expect(dialog).to_be_visible()
        page.locator("#browser-close-btn").click()
        expect(dialog).not_to_be_visible()
        page.close()
        context.close()

    def test_quick_nav_buttons_present(self, browser):
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("openFolderBrowser()")
        home_btn = page.locator("#browser-quick-home")
        root_btn = page.locator("#browser-quick-root")
        expect(home_btn).to_be_visible()
        expect(root_btn).to_be_visible()
        page.close()
        context.close()


class TestBYOKConfiguration:
    """Verify BYOK provider configuration dialog and fallback flows."""

    def test_byok_dialog_opens_from_header_pill(self, page: Page):
        btn = page.locator("#header-ai-btn")
        expect(btn).to_be_visible()
        btn.click()
        dialog = page.locator("#byok-dialog")
        expect(dialog).to_be_visible()

    def test_byok_provider_preset_switching(self, page: Page):
        page.locator("#header-ai-btn").click()
        dialog = page.locator("#byok-dialog")
        expect(dialog).to_be_visible()

        # Click Ollama preset
        ollama_pill = page.locator('.provider-pill[data-provider="ollama"]')
        ollama_pill.click()
        base_url_input = page.locator("#byok-base-url")
        expect(base_url_input).to_have_value("http://127.0.0.1:11434/v1")

        # Click LM Studio preset
        lms_pill = page.locator('.provider-pill[data-provider="lm-studio"]')
        lms_pill.click()
        expect(base_url_input).to_have_value("http://127.0.0.1:1234/v1")

    def test_byok_dialog_closes_on_escape(self, page: Page):
        page.locator("#header-ai-btn").click()
        dialog = page.locator("#byok-dialog")
        expect(dialog).to_be_visible()
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()

    def test_byok_skip_button(self, page: Page):
        page.locator("#header-ai-btn").click()
        dialog = page.locator("#byok-dialog")
        expect(dialog).to_be_visible()
        page.locator("#byok-skip-btn").click()
        expect(dialog).not_to_be_visible()


class TestIndexOptionsAndDependencies:
    """Verify index options, AST intelligence guarantees, and dependency constraints."""

    def test_core_engine_banner_visible(self, page: Page):
        page.locator("#header-index-btn").click()
        banner = page.locator(".engine-core-banner")
        expect(banner).to_be_visible()

    def test_defaults_force_off_llm_on_multi_off(self, page: Page):
        page.locator("#header-index-btn").click()
        force_box = page.locator("#force-index")
        llm_box = page.locator("#use-llm")
        multi_box = page.locator("#multimodal-index")

        expect(force_box).not_to_be_checked()
        expect(llm_box).to_be_checked()
        expect(multi_box).not_to_be_checked()

    def test_unchecking_llm_disables_multimodal(self, page: Page):
        page.locator("#header-index-btn").click()
        llm_box = page.locator("#use-llm")
        multi_box = page.locator("#multimodal-index")
        dep_warning = page.locator("#llm-dep-warning")

        expect(llm_box).to_be_checked()
        llm_box.uncheck()
        expect(multi_box).to_be_disabled()
        expect(dep_warning).to_be_visible()

        # Re-check LLM restores capability
        llm_box.check()
        expect(multi_box).not_to_be_disabled()
        expect(dep_warning).not_to_be_visible()


class TestRecentProjects:
    """Verify Recent Projects list and project switching support."""

    def test_recent_projects_section_rendered(self, page: Page):
        page.locator("#project-pill-btn").click()
        section = page.locator("#recent-projects-section")
        expect(section).to_be_visible()
        list_container = page.locator("#recent-projects-list")
        expect(list_container).to_be_visible()


class TestUnindexedProject:
    """Verify selecting an unindexed folder prompts for indexing rather than showing error."""

    def test_unindexed_prompt_shown(self, browser):
        test_dir = Path.cwd() / "examples" / "unindexed-test-repo"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / ".git").mkdir(exist_ok=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"{BASE_URL}?project={test_dir}", wait_until="networkidle")
            page.wait_for_timeout(800)
            prompt = page.locator("#unindexed-overlay")
            expect(prompt).to_be_visible()
            start_btn = page.locator("#unindexed-start-btn")
            expect(start_btn).to_be_visible()
            badge_text = page.locator("#ready-badge .badge-text")
            expect(badge_text).to_have_text("Not indexed")
            page.close()
            context.close()
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


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

    def test_invalid_project_returns_400(self, page: Page):
        result = page.evaluate("fetch('/api/status?project=').then(r => ({status: r.status}))")
        assert result["status"] == 400

    def test_system_path_rejected(self, page: Page):
        result = page.evaluate("fetch('/api/status?project=/etc').then(r => ({status: r.status}))")
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
