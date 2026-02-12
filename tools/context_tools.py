"""Tool to access runtime context information."""

from typing import Any

from agents import RunContextWrapper, function_tool


@function_tool
def get_today_date(ctx: RunContextWrapper[Any]) -> str:
    """Get today's date in ISO format (YYYY-MM-DD). Use this when you need to know the current date for decision-making.

    Returns:
        Today's date as a string in ISO format (e.g. '2026-02-12').
    """
    # Access context to get today's date
    if hasattr(ctx.context, "today_date"):
        return ctx.context.today_date
    # Fallback if context doesn't have today_date (shouldn't happen, but safe)
    from datetime import date

    return date.today().isoformat()
