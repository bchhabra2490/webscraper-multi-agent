"""Tool to query scraping advice stored in SQLite."""

from agents import function_tool

from storage import get_advice


@function_tool
def get_scraping_advice(domain: str | None = None, limit: int = 20) -> str:
    """Get scraping advice for a domain from the advice database. Use this to see what guidance has been stored for a site.

    Call this when you need to know if there's specific advice for how to scrape a domain (e.g. which tool to use, what parameters work best).

    Args:
        domain: Filter by domain (e.g. 'example.com', 'github.com'). Partial match; omit to get all advice.
        limit: Maximum number of advice entries to return (default 20, max 100).

    Returns:
        Formatted advice: each entry shows domain, advice text, and timestamp.
    """
    limit = max(1, min(limit, 100))
    advice_list = get_advice(domain=domain, limit=limit)
    if not advice_list:
        return "No scraping advice found." + (f" (domain like '{domain}')" if domain else "")
    lines = []
    for a in advice_list:
        lines.append(f"- [{a['created_at']}] {a['domain']}: {a['advice']}")
    return "Scraping advice:\n\n" + "\n".join(lines)
