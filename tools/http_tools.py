"""HTTP request tool for the web scraper agent."""

from typing import Literal

import httpx
from agents import function_tool

from storage import log_tool_call


@function_tool(strict_mode=False)  # headers is dict[str, str]; strict schema disallows additionalProperties
async def http_request(
    url: str,
    method: Literal["GET", "POST", "HEAD"] = "GET",
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    """Fetch a URL with an HTTP request. Use for static or simple pages.

    Args:
        url: Full URL to request (e.g. https://example.com/page).
        method: HTTP method. Use GET for normal pages, POST for form submissions, HEAD for metadata only.
        headers: Optional request headers as key-value pairs (e.g. User-Agent, Accept).
        timeout_seconds: Request timeout in seconds.

    Returns:
        Response body as text. For HEAD requests, returns status and headers summary.
    """
    args = {"url": url, "method": method, "headers": headers, "timeout_seconds": timeout_seconds}
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers=headers or {},
        ) as client:
            response = await client.request(method, url)
            response.raise_for_status()

            if method == "HEAD":
                result = f"Status: {response.status_code}\n" f"Headers: {dict(response.headers)}"
            else:
                result = response.text
        log_tool_call(url=url, tool_name="http_request", arguments=args, result=result)
        return result
    except httpx.HTTPStatusError as e:
        result = f"HTTP error {e.response.status_code} for {url}: {e.response.text[:2000]}"
        log_tool_call(url=url, tool_name="http_request", arguments=args, result=result)
        return result
    except httpx.RequestError as e:
        result = f"Request failed for {url}: {e!s}"
        log_tool_call(url=url, tool_name="http_request", arguments=args, result=result)
        return result
    except Exception as e:
        result = f"Error fetching {url}: {e!s}"
        log_tool_call(url=url, tool_name="http_request", arguments=args, result=result)
        return result
