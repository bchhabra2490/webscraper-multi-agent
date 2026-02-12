"""Tool to search scrape history stored in SQLite."""

from agents import function_tool

from storage import search_history, update_step_outcome


@function_tool
def search_scrape_history(
    domain: str | None = None,
    url_contains: str | None = None,
    limit: int = 30,
) -> str:
    """Search the agent's scrape history. Returns requests grouped by prompt, with all tool calls for each request shown as an array.

    Call this when the user asks what we did before for a site, or to avoid repeating the same steps. Domain can be partial (e.g. 'example.com' or 'github').

    Args:
        domain: Filter by domain (e.g. 'example.com', 'github.com'). Partial match; omit to get all domains.
        url_contains: Optional substring to filter URLs (e.g. '/docs', 'login').
        limit: Maximum number of requests to return (default 30, max 100).

    Returns:
        Formatted history: each request shows prompt, domain, success status, and all steps (tool calls) as an array.
    """
    limit = max(1, min(limit, 100))
    requests = search_history(domain=domain, url_contains=url_contains, limit=limit)
    if not requests:
        return "No scrape history found." + (
            f" (domain like '{domain or 'any'}', url containing '{url_contains or 'any'}')"
            if domain or url_contains
            else ""
        )

    lines: list[str] = []
    for req in requests:
        prompt = req["prompt"]
        domain_val = req.get("domain") or "(unknown)"
        success_val = req.get("success")
        success_str = "✅ Success" if success_val == 1 else "❌ Failed" if success_val == 0 else "⏳ Unknown"
        created_at = req.get("created_at", "")
        final_result = req.get("final_result")

        lines.append(f"Request #{req['id']}: {prompt}")
        lines.append(f"  Domain: {domain_val} | Status: {success_str} | Created: {created_at}")
        if final_result:
            result_preview = final_result[:200] + "..." if len(final_result) > 200 else final_result
            lines.append(f"  Final result: {result_preview}")

        steps = req.get("steps", [])
        if steps:
            lines.append(f"  Steps ({len(steps)} tool calls):")
            for step in steps:
                step_id = step.get("step_id", "?")
                url = step.get("url", "")
                tool_name = step.get("tool_name", "")
                timestamp = step.get("timestamp", "")
                outcome = step.get("led_to_data")
                if outcome is None:
                    outcome_str = "unknown"
                elif outcome:
                    outcome_str = "helpful"
                else:
                    outcome_str = "not helpful"
                notes = step.get("evaluator_notes") or ""
                notes_part = f" | notes={notes}" if notes else ""
                summary = step.get("result_summary", "")[:150]
                if len(step.get("result_summary", "")) > 150:
                    summary += "..."
                lines.append(f"    [{step_id}] {tool_name} | {url} | {timestamp} | outcome={outcome_str}{notes_part}")
                lines.append(f"      args: {step.get('arguments_json', '{}')}")
                lines.append(f"      result: {summary}")
        else:
            lines.append("  Steps: (none)")

        lines.append("")  # blank line between requests

    return "Scrape history (one row per prompt, steps as array):\n\n" + "\n".join(lines).rstrip()


@function_tool
def get_additional_learnings() -> str:
    """Get the additional learnings from the agent. This is a file that contains the additional learnings of the agent.

    Args:
        None.
    """
    print("Getting additional learnings...")
    with open("additional_learnings.txt", "r") as f:
        return f.read()


@function_tool
def mark_scrape_step_outcome(
    request_id: int,
    step_id: int,
    led_to_data: bool,
    notes: str | None = None,
) -> str:
    """Mark whether a specific step (tool call) within a scrape request helped fetch the requested data.

    Use this from the evaluator agent after you decide which tool calls contributed to a successful scrape.

    Args:
        request_id: The ID of the scrape request (shown by search_scrape_history as Request #...).
        step_id: The step index within that request's steps array (shown as [0], [1], etc. in search_scrape_history).
        led_to_data: True if this call helped produce useful data, False if it did not.
        notes: Optional explanation (e.g. 'http_request returned empty body, not useful',
               or 'playwright_scroll finally loaded the full article list').

    Returns:
        A short confirmation message.
    """
    from storage import update_step_outcome

    update_step_outcome(request_id=request_id, step_id=step_id, led_to_data=led_to_data, evaluator_notes=notes)
    label = "helpful" if led_to_data else "not helpful"
    return f"Updated request {request_id}, step {step_id} as {label}." + (f" Notes: {notes}" if notes else "")
