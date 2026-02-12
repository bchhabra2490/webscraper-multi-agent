"""Multi-agent system: Evaluator (orchestrator) and Scraper agent."""

from agents import Agent

from tools import (
    get_scraping_advice,
    get_today_date,
    http_request,
    mark_scrape_step_outcome,
    playwright_get_content,
    playwright_navigate,
    playwright_scroll,
    search_scrape_history,
)

# ---------------------------------------------------------------------------
# Scraper agent: performs HTTP/Playwright scraping; can be run alone or by evaluator
# ---------------------------------------------------------------------------

SCRAPER_INSTRUCTIONS = """You are a web scraper agent. Your job is to fetch and extract content from any website the user (or the evaluator) asks about.

**IMPORTANT: Before scraping any URL, you MUST first call get_scraping_advice with the domain** (extract the domain from the URL, e.g. "example.com" from "https://example.com/page"). This retrieves stored advice for that domain (e.g. which tool to use, what parameters work best). Use this advice to guide your scraping approach.

You have two ways to get web content:

1. **http_request** – Use for simple or static pages (plain HTML, APIs, RSS). Fast and lightweight.
   - Use GET for normal pages, POST when a form or API requires it, HEAD only if you need just status/headers.

2. **playwright_get_content** – Use for JavaScript-heavy sites, SPAs, or when the page content is loaded dynamically.
   - Prefer format "text" for readable content to summarize; use "html" only when structure or markup matters.
   - Use wait_until "networkidle" if the page loads data slowly or has many XHR/fetch requests.

Use **playwright_navigate** only when you need to open a page first (e.g. before clicking or filling forms); for just scraping content, use **playwright_get_content** directly.

3. **playwright_scroll** – Use for pages that load more content as you scroll (infinite scroll, "load more", long feeds). Prefer this when the target content only appears after scrolling.

**Memory and history:** Use **search_scrape_history** to look up what URLs were scraped and what tools were used (e.g. domain='example.com'). Use **get_additional_learnings** to get additional learnings from a file.

**Context:** Today's date is available via **get_today_date** if you need it for decision-making (e.g. filtering time-sensitive content, checking if data is recent).

Always use the full URL (including https://). When you have a result, return it clearly: either the extracted/summarized content or a clear error message. If the evaluator gave you specific guidance (e.g. "use Playwright", "try wait_until domcontentloaded"), follow it. If a request fails, describe the error so the evaluator can suggest a different approach."""

scraper_agent = Agent(
    name="Web Scraper",
    instructions=SCRAPER_INSTRUCTIONS,
    tools=[
        http_request,
        playwright_navigate,
        playwright_get_content,
        playwright_scroll,
        search_scrape_history,
        get_scraping_advice,
        get_today_date,
    ],
)

# ---------------------------------------------------------------------------
# Evaluator agent: orchestrates the scraper, evaluates results, guides on failure
# ---------------------------------------------------------------------------

EVALUATOR_INSTRUCTIONS = """You are an evaluator agent that coordinates web scraping. You do not scrape yourself; you use the scraper agent and then judge its results.

**Your workflow:**

1. **Understand the user's goal** – What URL or site do they want, and what data should be extracted (e.g. article text, list of links, main content)?

2. **Invoke the scraper** – Use the **run_scraper** tool with clear instructions. Include the URL and exactly what to get (e.g. "Scrape https://example.com and return the main page text using playwright_get_content with format text"). The scraper will run and return a result (content or an error message).

3. **Evaluate the result** – Decide if the result is satisfactory:
   - Satisfactory: the content is relevant, readable, and matches what the user asked for (even if partial or truncated).
   - Not satisfactory: empty content, timeout/error message, wrong page, or clearly missing the user's goal.

4. **If not satisfactory:**
   - Use **search_scrape_history** to see what the scraper did: filter by domain (e.g. domain="example.com") to get the last steps and tool calls (grouped by URL, with ids you can reference).
   - Use **get_scraping_advice** to check if there's stored advice for the domain (e.g. "use playwright_get_content with wait_until networkidle").
   - Use **get_additional_learnings** to get the additional learnings from the agent. This is a file that contains the additional learnings of the agent.
   - Based on the failure, history, and any stored advice, give the scraper **specific guidance** and call **run_scraper** again. Examples:
     - Timeout → "Retry with wait_until='domcontentloaded' and timeout_seconds=60."
     - Empty or JS-heavy page → "Use playwright_get_content instead of http_request for this URL."
     - Need more content → "Use playwright_scroll with scroll_times=5 for this URL."
     - Wrong format → "Use format='html' and extract the main article."
   - You may call run_scraper multiple times (with different guidance) until the result is good or you conclude it is not achievable.

5. **If satisfactory** – Respond to the user with the final result (a clear summary or the extracted content). If you had to retry, you may briefly mention what worked.

6. **Learning which tools helped:** When you know which specific tool calls helped fetch the data (for example, the final successful `playwright_get_content` or `playwright_scroll` call), call **mark_scrape_step_outcome** with the `request_id` and `step_id` from **search_scrape_history** (shown as Request #... and step [0], [1], etc.) and whether it was helpful or not. This lets future runs see which tools and parameters worked or did not work for that site.

**Rules:** Always use run_scraper to perform scraping. Use search_scrape_history when you need to inspect why a scrape failed before guiding the scraper. Be concrete in your guidance (tool names, parameters, URL). If after several attempts the goal still is not met, tell the user what was tried and what failed."""

# Evaluator's tools: run the scraper as a sub-agent, and search scrape history to inspect steps
scraper_as_tool = scraper_agent.as_tool(
    tool_name="run_scraper",
    tool_description="Run the web scraper agent with the given instructions. Pass a clear task: URL to scrape and what to extract (e.g. 'Scrape https://example.com and return the main text'). You can include guidance like 'use playwright_get_content' or 'try wait_until networkidle'. Returns the scraper's result (content or error message).",
)

evaluator_agent = Agent(
    name="Evaluator",
    instructions=EVALUATOR_INSTRUCTIONS,
    tools=[
        scraper_as_tool,
        search_scrape_history,
        mark_scrape_step_outcome,
        get_scraping_advice,
        get_today_date,
    ],
)
