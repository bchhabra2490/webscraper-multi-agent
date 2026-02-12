"""SQLite storage for scrape history: one row per prompt with JSON array of steps."""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_DB_PATH: Path | None = None
_RESULT_SUMMARY_MAX = 500

# Thread-local storage for current request_id
_thread_local = threading.local()


def get_current_request_id() -> int | None:
    """Get the current request_id from thread-local storage."""
    return getattr(_thread_local, "request_id", None)


def set_current_request_id(request_id: int | None) -> None:
    """Set the current request_id in thread-local storage."""
    _thread_local.request_id = request_id


def get_db_path() -> Path:
    """Return the path to the SQLite DB file; create parent dir if needed."""
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = Path(__file__).resolve().parent / "scraper_memory.db"
    return _DB_PATH


def _domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or ""
        return netloc.lower().lstrip("www.") or "(no domain)"
    except Exception:
        return "(unknown)"


def get_advice_for_domain(domain: str) -> str:
    """
    Get stored scraping advice for a domain and format it as a string.
    Returns empty string if no advice found.

    Args:
        domain: Domain name (e.g. 'example.com'). Will be normalized.

    Returns:
        Formatted advice string, or empty string if none found.
    """
    domain = domain.strip().lower().lstrip("www.")
    advice_list = get_advice(domain=domain, limit=10)
    if not advice_list:
        return ""
    # Format: "[Advice for example.com: Use playwright_get_content with wait_until networkidle]"
    advice_texts = [a["advice"] for a in advice_list]
    return f"[Advice for {domain}: {'; '.join(advice_texts)}]"


def init_db() -> None:
    """Create the scrape_requests and scraping_advice tables. Drops old scrape_history table."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        # Drop old table if it exists
        conn.execute("DROP TABLE IF EXISTS scrape_history")

        # New table: one row per prompt/request with JSON array of steps
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scrape_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                domain TEXT,
                steps_json TEXT NOT NULL,
                final_result TEXT,
                success INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scrape_requests_domain ON scrape_requests(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scrape_requests_created_at ON scrape_requests(created_at)")

        # Scraping advice table (unchanged)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scraping_advice (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                advice TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scraping_advice_domain ON scraping_advice(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scraping_advice_created_at ON scraping_advice(created_at)")


def start_scrape_request(prompt: str) -> int:
    """
    Create a new scrape request row and return its ID.
    Call this at the start of a new scraping prompt/request.

    Args:
        prompt: The user's prompt/request text.

    Returns:
        The request ID (primary key).
    """
    init_db()
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO scrape_requests (prompt, steps_json)
            VALUES (?, ?)
            """,
            (prompt, json.dumps([])),
        )
        request_id = cursor.lastrowid
        set_current_request_id(request_id)
        return request_id


def log_tool_call(
    url: str,
    tool_name: str,
    arguments: dict,
    result: str,
    request_id: int | None = None,
) -> None:
    """
    Append a tool call step to a scrape request's JSON array.
    If request_id is None, uses the current thread-local request_id.

    Args:
        url: URL that was scraped.
        tool_name: Name of the tool used.
        arguments: Tool arguments dict.
        result: Tool result text.
        request_id: Optional request ID. If None, uses thread-local value.
    """
    init_db()
    if request_id is None:
        request_id = get_current_request_id()
        if request_id is None:
            # Fallback: create a new request with a generic prompt
            request_id = start_scrape_request("(auto-created from tool call)")

    domain = _domain_from_url(url)
    args_json = json.dumps(arguments, default=str)
    summary = result[:_RESULT_SUMMARY_MAX] + ("..." if len(result) > _RESULT_SUMMARY_MAX else "")

    step = {
        "step_id": None,  # Will be set to index in array
        "url": url,
        "domain": domain,
        "tool_name": tool_name,
        "arguments": arguments,
        "arguments_json": args_json,
        "result": result,
        "result_summary": summary,
        "timestamp": datetime.now().isoformat(),
        "led_to_data": None,
        "evaluator_notes": None,
    }

    with sqlite3.connect(get_db_path()) as conn:
        # Get current steps
        cur = conn.execute("SELECT steps_json, domain FROM scrape_requests WHERE id = ?", (request_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Scrape request {request_id} not found")
        steps_json, current_domain = row

        steps: list[dict] = json.loads(steps_json)
        step["step_id"] = len(steps)
        steps.append(step)

        # Update domain if not set (use first URL's domain)
        new_domain = current_domain or domain

        # Update the row
        conn.execute(
            """
            UPDATE scrape_requests
            SET steps_json = ?, domain = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (json.dumps(steps, default=str), new_domain, request_id),
        )


def update_request_final_result(request_id: int, final_result: str | None = None, success: bool | None = None) -> None:
    """
    Update a scrape request's final result and success status.

    Args:
        request_id: The ID of the scrape request.
        final_result: The final result text from the evaluator.
        success: Whether the request was successful.
    """
    init_db()
    fields: list[str] = []
    params: list[Any] = []
    if final_result is not None:
        fields.append("final_result = ?")
        params.append(final_result)
    if success is not None:
        fields.append("success = ?")
        params.append(1 if success else 0)
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    params.append(request_id)

    set_clause = ", ".join(fields)
    with sqlite3.connect(get_db_path()) as conn:
        conn.execute(f"UPDATE scrape_requests SET {set_clause} WHERE id = ?", params)


def update_step_outcome(
    request_id: int,
    step_id: int,
    led_to_data: bool | None = None,
    evaluator_notes: str | None = None,
) -> None:
    """
    Update a specific step's outcome within a scrape request's JSON array.

    Args:
        request_id: The ID of the scrape request.
        step_id: The step index within the steps array.
        led_to_data: True if this step helped fetch data, False if not, None to leave unchanged.
        evaluator_notes: Optional notes about why it did or didn't help.
    """
    init_db()
    if led_to_data is None and evaluator_notes is None:
        return

    with sqlite3.connect(get_db_path()) as conn:
        # Get current steps
        cur = conn.execute("SELECT steps_json FROM scrape_requests WHERE id = ?", (request_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Scrape request {request_id} not found")
        steps_json = row[0]
        steps: list[dict] = json.loads(steps_json)

        if step_id < 0 or step_id >= len(steps):
            raise ValueError(f"Step {step_id} not found in request {request_id}")

        # Update the step
        if led_to_data is not None:
            steps[step_id]["led_to_data"] = led_to_data
        if evaluator_notes is not None:
            steps[step_id]["evaluator_notes"] = evaluator_notes

        # Update the row
        conn.execute(
            """
            UPDATE scrape_requests
            SET steps_json = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (json.dumps(steps, default=str), request_id),
        )


def search_history(
    domain: str | None = None,
    url_contains: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Query scrape requests. Returns full request objects with their steps arrays.

    Args:
        domain: Filter by domain (partial match with LIKE).
        url_contains: Filter by URL substring (searches within steps).
        limit: Maximum number of requests to return.

    Returns:
        List of dicts with keys: id, prompt, domain, steps (parsed list), final_result, success, created_at, updated_at.
    """
    init_db()
    domain = (domain or "").strip().lower() if domain else None
    url_contains = (url_contains or "").strip() or None
    limit = max(1, min(limit, 500))

    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Build query
        query = """
            SELECT id, prompt, domain, steps_json, final_result, success, created_at, updated_at
            FROM scrape_requests
            WHERE 1=1
        """
        params: list[Any] = []

        if domain:
            query += " AND domain LIKE ?"
            params.append(f"%{domain}%")

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()

        # Parse steps_json and filter by url_contains if needed
        results = []
        for row in rows:
            row_dict = dict(row)
            steps = json.loads(row_dict["steps_json"])

            # Filter by url_contains if specified
            if url_contains:
                matching_steps = [s for s in steps if url_contains.lower() in s.get("url", "").lower()]
                if not matching_steps:
                    continue
                # Optionally filter steps to only matching ones, or keep all
                # For now, keep all steps but only include request if any step matches

            row_dict["steps"] = steps
            del row_dict["steps_json"]  # Remove raw JSON, keep parsed version
            results.append(row_dict)

    return results


def add_advice(domain: str, advice: str) -> int:
    """
    Add scraping advice for a domain. Returns the ID of the inserted row.

    Args:
        domain: Domain name (e.g. 'example.com', 'github.com'). Will be normalized to lowercase.
        advice: Advice text (e.g. 'Use playwright_get_content with wait_until networkidle for this site').

    Returns:
        The ID of the inserted advice row.
    """
    init_db()
    domain = domain.strip().lower().lstrip("www.")
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO scraping_advice (domain, advice)
            VALUES (?, ?)
            """,
            (domain, advice),
        )
        return cursor.lastrowid


def get_advice(domain: str | None = None, limit: int = 50) -> list[dict]:
    """
    Query scraping advice. If domain is provided, returns advice for that domain (partial match).
    If domain is None, returns all advice.

    Args:
        domain: Domain to filter by (e.g. 'example.com', 'github'). Partial match with LIKE.
        limit: Maximum number of results (default 50, max 500).

    Returns:
        List of dicts with keys: id, domain, advice, created_at.
    """
    init_db()
    domain = (domain or "").strip().lower() if domain else None
    limit = max(1, min(limit, 500))

    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if domain:
            cur.execute(
                """
                SELECT id, domain, advice, created_at
                FROM scraping_advice
                WHERE domain LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"%{domain}%", limit),
            )
        else:
            cur.execute(
                """
                SELECT id, domain, advice, created_at
                FROM scraping_advice
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
