"""Playwright tools for scraping JS-rendered and dynamic pages."""

import asyncio
from typing import Literal

from agents import function_tool
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright

from storage import log_tool_call

# Short timeout when capturing page state after a navigation timeout (avoid hanging again)
_PAGE_STATE_TIMEOUT_MS = 5000


async def _get_page_state_and_content(page, format: Literal["text", "html"] = "text") -> str:
    """Get current page URL, title, and content. Uses a short timeout so we don't hang."""
    parts = []
    try:
        current_url = page.url
        parts.append(f"Current URL: {current_url}")
    except Exception as e:
        parts.append(f"Current URL: (unable to get: {e})")
    try:
        title = await asyncio.wait_for(page.title(), timeout=_PAGE_STATE_TIMEOUT_MS / 1000)
        parts.append(f"Page title: {title}")
    except Exception as e:
        parts.append(f"Page title: (unable to get: {e})")
    try:
        if format == "text":
            body = await page.locator("body").inner_text(timeout=_PAGE_STATE_TIMEOUT_MS)
            content = body
        else:
            content = await asyncio.wait_for(page.content(), timeout=_PAGE_STATE_TIMEOUT_MS / 1000)
        parts.append(f"Content ({len(content)} chars):\n{content[:50_000]}")
        if len(content) > 50_000:
            parts.append(f"\n... [truncated at 50k chars, total {len(content)}]")
    except Exception as e:
        parts.append(f"Content: (unable to get: {e})")
    return "\n".join(parts)


@function_tool
async def playwright_navigate(
    url: str,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout_seconds: float = 30.0,
) -> str:
    """Open a URL in a headless browser and wait for the page to load. Use for JS-heavy or dynamic sites.

    Call this first if you need to interact with a page before scraping. For just getting content,
    prefer playwright_get_content.

    Args:
        url: Full URL to open (e.g. https://example.com).
        wait_until: When to consider navigation done: 'load' (default), 'domcontentloaded', or 'networkidle'.
        timeout_seconds: Navigation timeout in seconds.

    Returns:
        Status message with page title and URL after navigation.
    """
    args = {"url": url, "wait_until": wait_until, "timeout_seconds": timeout_seconds}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            print("Tool call: playwright_navigate")
            try:
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until=wait_until, timeout=timeout_seconds * 1000)
                except PlaywrightTimeoutError as e:
                    state = await _get_page_state_and_content(page, "text")
                    result = f"Navigation timed out after {timeout_seconds}s ({e!s}). Page state and content:\n{state}"
                    log_tool_call(url=url, tool_name="playwright_navigate", arguments=args, result=result)
                    return result
                title = await page.title()
                result = f"Navigated to {url}. Page title: {title}"
                log_tool_call(url=url, tool_name="playwright_navigate", arguments=args, result=result)
                return result
            finally:
                await browser.close()
    except Exception as e:
        result = f"Playwright navigation failed for {url}: {e!s}"
        log_tool_call(url=url, tool_name="playwright_navigate", arguments=args, result=result)
        return result


@function_tool
async def playwright_scroll(
    url: str,
    scroll_times: int = 3,
    scroll_delay_seconds: float = 0.5,
    direction: Literal["down", "up"] = "down",
    format: Literal["text", "html"] = "text",
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout_seconds: float = 30.0,
    max_length: int = 150_000,
) -> str:
    """Open a URL, scroll the page (e.g. to trigger lazy loading or infinite scroll), then return the page content.

    Use for pages that load more content as you scroll (social feeds, long articles, "load more" lists).
    Scrolls the page repeatedly with a short delay between scrolls so new content can load.

    Args:
        url: Full URL to open and scroll (e.g. https://example.com/feed).
        scroll_times: Number of times to scroll (default 3). More scrolls load more content but take longer.
        scroll_delay_seconds: Seconds to wait after each scroll so content can load (default 0.5).
        direction: 'down' (default) or 'up'.
        format: 'text' returns visible text after scrolling; 'html' returns full page HTML.
        wait_until: When to consider initial page load done before scrolling.
        timeout_seconds: Navigation timeout in seconds.
        max_length: Maximum characters to return; content is truncated to avoid token limits.

    Returns:
        Page content as text or HTML after scrolling, truncated to max_length if needed.
    """
    args = {
        "url": url,
        "scroll_times": scroll_times,
        "scroll_delay_seconds": scroll_delay_seconds,
        "direction": direction,
        "format": format,
        "wait_until": wait_until,
        "timeout_seconds": timeout_seconds,
        "max_length": max_length,
    }
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            print("Tool call: playwright_scroll")
            try:
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until=wait_until, timeout=timeout_seconds * 1000)
                except PlaywrightTimeoutError as e:
                    state = await _get_page_state_and_content(page, format)
                    result = (
                        f"Navigation timed out after {timeout_seconds}s ({e!s}). "
                        f"Page state and content so far:\n{state}"
                    )
                    log_tool_call(url=url, tool_name="playwright_scroll", arguments=args, result=result)
                    return result

                scroll_js = (
                    "window.scrollBy(0, window.innerHeight)"
                    if direction == "down"
                    else "window.scrollBy(0, -window.innerHeight)"
                )
                for _ in range(max(0, scroll_times)):
                    await page.evaluate(scroll_js)
                    await asyncio.sleep(scroll_delay_seconds)

                if format == "text":
                    body = await page.locator("body")
                    content = await body.inner_text()
                else:
                    content = await page.content()

                if len(content) > max_length:
                    content = content[:max_length] + f"\n\n... [truncated, total length {len(content)} chars]"
                log_tool_call(url=url, tool_name="playwright_scroll", arguments=args, result=content)
                return content
            finally:
                await browser.close()
    except Exception as e:
        result = f"Playwright scroll failed for {url}: {e!s}"
        log_tool_call(url=url, tool_name="playwright_scroll", arguments=args, result=result)
        return result


@function_tool
async def playwright_get_content(
    url: str,
    format: Literal["text", "html"] = "text",
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout_seconds: float = 30.0,
    max_length: int = 150_000,
) -> str:
    """Open a URL in a headless browser and return the page content. Use for JS-rendered or SPA sites.

    Renders the page like a real browser (executes JavaScript), then returns either the visible text
    (clean, good for summaries) or the full HTML.

    Args:
        url: Full URL to scrape (e.g. https://example.com).
        format: 'text' returns visible text only (recommended for reading). 'html' returns full page HTML.
        wait_until: When to consider page loaded: 'load', 'domcontentloaded', or 'networkidle'.
        timeout_seconds: Navigation timeout in seconds.
        max_length: Maximum characters to return; content is truncated to avoid token limits.

    Returns:
        Page content as text or HTML, truncated to max_length if needed.
    """
    args = {
        "url": url,
        "format": format,
        "wait_until": wait_until,
        "timeout_seconds": timeout_seconds,
        "max_length": max_length,
    }
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            print("Tool call: playwright_get_content")
            try:
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until=wait_until, timeout=timeout_seconds * 1000)
                except PlaywrightTimeoutError as e:
                    state = await _get_page_state_and_content(page, format)
                    result = (
                        f"Navigation timed out after {timeout_seconds}s ({e!s}). "
                        f"Page state and content so far:\n{state}"
                    )
                    if len(result) > max_length:
                        result = result[:max_length] + f"\n\n... [truncated, total {len(result)} chars]"
                    log_tool_call(url=url, tool_name="playwright_get_content", arguments=args, result=result)
                    return result

                if format == "text":
                    body = await page.locator("body")
                    content = await body.inner_text()
                else:
                    content = await page.content()

                if len(content) > max_length:
                    content = content[:max_length] + f"\n\n... [truncated, total length {len(content)} chars]"
                log_tool_call(url=url, tool_name="playwright_get_content", arguments=args, result=content)
                return content
            finally:
                await browser.close()
    except Exception as e:
        result = f"Playwright scrape failed for {url}: {e!s}"
        log_tool_call(url=url, tool_name="playwright_get_content", arguments=args, result=result)
        return result
