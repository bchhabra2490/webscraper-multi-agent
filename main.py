"""Run the scraper (single agent) or evaluator+scraper multi-agent system."""

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv

from agents import Runner

from agent import evaluator_agent, scraper_agent
from storage import set_current_request_id, start_scrape_request, update_request_final_result

load_dotenv()


@dataclass
class ScraperContext:
    """Context passed to agents, containing today's date and other runtime info."""

    today_date: str  # ISO format: YYYY-MM-DD
    request_id: int | None = None  # Current scrape request ID


def get_context(prompt: str) -> ScraperContext:
    """Create context with today's date and start a new scrape request."""
    request_id = start_scrape_request(prompt)
    return ScraperContext(today_date=date.today().isoformat(), request_id=request_id)


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in your environment.", file=sys.stderr)
        sys.exit(1)

    prompt = sys.argv[1] if len(sys.argv) > 1 else "Scrape https://example.com and summarize what the page is about."

    # Create context with today's date and start a new request
    context = get_context(prompt)

    # Use --scraper to run only the scraper agent; default is evaluator (orchestrator + scraper)
    if "--scraper" in sys.argv:
        sys.argv.remove("--scraper")
        prompt = sys.argv[1] if len(sys.argv) > 1 else prompt
        print(f"[Scraper only] Prompt: {prompt}\n")
        result = await Runner.run(scraper_agent, prompt, context=context)
    else:
        print(f"[Evaluator + Scraper] Prompt: {prompt}\n")
        result = await Runner.run(evaluator_agent, prompt, context=context)
        # Update final result and success status
        if context.request_id:
            success = result.final_output and not any(
                keyword in result.final_output.lower()
                for keyword in ["error", "failed", "timeout", "unable", "cannot"]
            )
            update_request_final_result(context.request_id, final_result=result.final_output, success=success)

    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
