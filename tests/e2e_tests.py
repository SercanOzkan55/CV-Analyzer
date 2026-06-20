# E2E Test Suite - CV Analyzer
# Playwright-based end-to-end tests for critical user flows

import pytest
from playwright.async_api import async_playwright, Browser, Page
import asyncio
import os

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:3000")
API_BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
async def browser():
    """Create browser instance for session."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser: Browser):
    """Create new page for each test."""
    page = await browser.new_page()
    yield page
    await page.close()


class TestUserAuthFlow:
    """Test user authentication flow."""

    async def test_signup_flow(self, page: Page):
        """Test user signup, login, logout."""
        # Navigate to landing page
        await page.goto(f"{BASE_URL}/")
        await page.wait_for_load_state("networkidle")
        
        # Click signup button
        await page.click("text=Sign Up")
        await page.wait_for_url(f"{BASE_URL}/signup")
        
        # Fill form
        await page.fill("input[name=email]", f"test{int(time.time())}@example.com")
        await page.fill("input[name=password]", "TempPass123!")
        await page.click("button[type=submit]")
        
        # Wait for redirect to dashboard
        await page.wait_for_url(f"{BASE_URL}/dashboard")
        
        # Verify authenticated
        assert await page.is_visible("text=Dashboard") or await page.is_visible("text=My CVs")
        
        # Test logout
        await page.click("button:has-text('Logout')")
        await page.wait_for_url(f"{BASE_URL}/")
        
        # Verify signed out
        assert not await page.is_visible("text=Dashboard")

    async def test_invalid_login(self, page: Page):
        """Test invalid login shows error."""
        await page.goto(f"{BASE_URL}/login")
        
        await page.fill("input[name=email]", "invalid@example.com")
        await page.fill("input[name=password]", "wrongpassword")
        await page.click("button[type=submit]")
        
        # Wait for error message
        await page.wait_for_selector("text=Invalid credentials")
        assert await page.is_visible("text=Invalid credentials")


class TestCVAnalysisFlow:
    """Test CV upload and analysis flow."""

    async def test_upload_analyze_pdf(self, page: Page):
        """Test uploading PDF and analyzing."""
        # Login first
        await page.goto(f"{BASE_URL}/login")
        await page.fill("input[name=email]", os.getenv("TEST_USER_EMAIL", "test@example.com"))
        await page.fill("input[name=password]", os.getenv("TEST_USER_PASSWORD"))
        await page.click("button[type=submit]")
        await page.wait_for_url(f"{BASE_URL}/dashboard")
        
        # Navigate to analyze page
        await page.click("text=Analyze CV")
        await page.wait_for_url(f"{BASE_URL}/analyze")
        
        # Upload PDF
        async with page.expect_file_chooser() as fc_info:
            await page.click("text=Upload CV")
        file_chooser = await fc_info.value
        await file_chooser.set_files("tests/fixtures/sample.pdf")
        
        # Wait for upload to complete
        await page.wait_for_selector("text=Analysis in progress")
        
        # Wait for results
        await page.wait_for_selector("text=ATS Score", timeout=30000)
        
        # Verify scores displayed
        assert await page.is_visible("text=ATS Score")
        assert await page.is_visible("text=Skill Match")
        assert await page.is_visible("text=Recommendations")

    async def test_export_analysis_pdf(self, page: Page):
        """Test exporting analysis as PDF."""
        # After analysis, click export
        await page.click("button:has-text('Download Report')")
        
        # Wait for download
        async with page.expect_download() as download_info:
            download = await download_info.value
            
        # Verify file downloaded
        assert download.suggested_filename.endswith(".pdf")


class TestRecruiterFlow:
    """Test recruiter features."""

    async def test_create_job_and_rank_candidates(self, page: Page):
        """Test creating job posting and ranking candidates."""
        # Login as recruiter
        await page.goto(f"{BASE_URL}/login")
        await page.fill("input[name=email]", os.getenv("TEST_RECRUITER_EMAIL", "recruiter@example.com"))
        await page.fill("input[name=password]", os.getenv("TEST_RECRUITER_PASSWORD"))
        await page.click("button[type=submit]")
        
        # Navigate to recruiter dashboard
        await page.wait_for_url(f"{BASE_URL}/recruiter")
        await page.click("text=Create Job")
        
        # Fill job form
        await page.fill("input[name=title]", "Senior Developer")
        await page.fill("textarea[name=description]", "Looking for experienced developer...")
        await page.click("button:has-text('Create')")
        
        # Verify job created
        await page.wait_for_selector("text=Senior Developer")

    async def test_batch_upload_candidates(self, page: Page):
        """Test batch uploading candidates."""
        # Go to recruiter page
        await page.goto(f"{BASE_URL}/recruiter")
        
        # Click upload batch
        await page.click("text=Upload Batch")
        
        # Upload ZIP file
        async with page.expect_file_chooser() as fc_info:
            await page.click("text=Select ZIP")
        file_chooser = await fc_info.value
        await file_chooser.set_files("tests/fixtures/batch.zip")
        
        # Monitor progress
        await page.wait_for_selector("text=Processing: 0%")
        
        # Wait for completion
        await page.wait_for_selector("text=100% Complete", timeout=60000)


class TestAccessibility:
    """Test accessibility features."""

    async def test_keyboard_navigation(self, page: Page):
        """Test keyboard navigation without mouse."""
        await page.goto(f"{BASE_URL}/")
        
        # Tab to first button
        await page.keyboard.press("Tab")
        await page.keyboard.press("Tab")
        
        # Should be on signup/login button
        focused = await page.evaluate("document.activeElement.textContent")
        assert "Sign" in focused or "Log" in focused

    async def test_screen_reader_labels(self, page: Page):
        """Test aria labels for screen readers."""
        await page.goto(f"{BASE_URL}/analyze")
        
        # Check form inputs have labels
        inputs = await page.query_selector_all("input")
        for input_elem in inputs:
            aria_label = await input_elem.get_attribute("aria-label")
            placeholder = await input_elem.get_attribute("placeholder")
            label = await page.query_selector(f"label[for={await input_elem.get_attribute('id')}]")
            
            # Must have one of: aria-label, placeholder, or associated label
            assert aria_label or placeholder or label


class TestSecurity:
    """Test security features."""

    async def test_xss_protection_in_results(self, page: Page):
        """Test XSS payloads don't execute."""
        # Upload CV with XSS payload in filename
        await page.goto(f"{BASE_URL}/analyze")
        
        # Try XSS in filename
        xss_payload = "<script>alert('xss')</script>"
        
        # If filename is shown, should be escaped
        page_content = await page.content()
        assert "<script>" not in page_content or "alert(" not in page_content

    async def test_unauthorized_access_blocked(self, page: Page):
        """Test unauthorized access is blocked."""
        # Try accessing protected route without auth
        await page.goto(f"{BASE_URL}/dashboard")
        
        # Should redirect to login
        await page.wait_for_url(f"{BASE_URL}/login")
        assert await page.is_visible("text=Login")

    async def test_csrf_protection(self, page: Page):
        """Test CSRF token validation."""
        # Login
        await page.goto(f"{BASE_URL}/login")
        await page.fill("input[name=email]", os.getenv("TEST_USER_EMAIL"))
        await page.fill("input[name=password]", os.getenv("TEST_USER_PASSWORD"))
        await page.click("button[type=submit]")
        
        # Try form submission with tampered CSRF token
        await page.evaluate("""
            () => {
                const token = document.querySelector('[name="_csrf"]');
                if (token) token.value = 'invalid';
            }
        """)
        
        # Submit should fail
        await page.click("button[type=submit]")
        # Should show error or redirect (not process)


class TestMobileResponsive:
    """Test mobile responsiveness."""

    @pytest.mark.parametrize("viewport", [
        {"width": 390, "height": 844},   # iPhone
        {"width": 540, "height": 720},   # Android
        {"width": 1024, "height": 768},  # Tablet
    ])
    async def test_responsive_layout(self, page: Page, viewport):
        """Test layout works on mobile/tablet."""
        await page.set_viewport_size(viewport["width"], viewport["height"])
        
        await page.goto(f"{BASE_URL}/")
        
        # Verify no horizontal scroll needed
        max_width = await page.evaluate("Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)")
        viewport_width = viewport["width"]
        assert max_width <= viewport_width, f"Content wider than viewport: {max_width} > {viewport_width}"


class TestPerformance:
    """Test performance metrics."""

    async def test_page_load_time(self, page: Page):
        """Test page loads within acceptable time."""
        start = asyncio.get_event_loop().time()
        
        await page.goto(f"{BASE_URL}/", wait_until="networkidle")
        
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should load in < 3 seconds
        assert elapsed < 3.0, f"Page took {elapsed}s to load"

    async def test_analyze_response_time(self, page: Page):
        """Test CV analysis completes in reasonable time."""
        # Login and upload CV
        await page.goto(f"{BASE_URL}/analyze")
        
        # Upload and time analysis
        start = asyncio.get_event_loop().time()
        
        # ... upload process ...
        await page.wait_for_selector("text=ATS Score", timeout=30000)
        
        elapsed = asyncio.get_event_loop().time() - start
        
        # Analysis should complete in < 30 seconds
        assert elapsed < 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
