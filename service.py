"""FastAPI service to expose the daily scraping report and trigger batch runs.

- GET /          → serve latest HTML report (news-style page)
- POST /run-batch → run batch scraper + regenerate markdown + HTML

Designed to be deployed on Railway with:
  uvicorn service:app --host 0.0.0.0 --port ${PORT:-8000}

The service includes a built-in scheduler that runs the batch job daily at 8 AM UTC.
You can also trigger it manually via POST /run-batch.
"""

import logging
import os
from pathlib import Path
from typing import Any, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from main import ScraperContext, get_context
from run_batch import generate_markdown, load_prompts, run_prompt
from generate_html import generate_html, parse_markdown

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Scraping News Service", version="1.0.0")

PROMPTS_FILE = Path("prompts.txt")
OUTPUT_MD = Path("results/output.md")
OUTPUT_HTML = Path("results/output.html")

# Scheduler for daily batch runs
scheduler = AsyncIOScheduler()


@app.get("/", response_class=HTMLResponse)
async def get_report() -> HTMLResponse:
    """Serve the latest HTML report as a news-style page."""
    if not OUTPUT_HTML.exists():
        raise HTTPException(status_code=404, detail="Report not generated yet.")

    html = OUTPUT_HTML.read_text(encoding="utf-8")
    return HTMLResponse(content=html, media_type="text/html")


async def run_batch_job() -> dict[str, Any]:
    """Internal function to run the batch scraper. Called by scheduler or endpoint."""
    logger.info("Starting batch scraping job...")

    if not PROMPTS_FILE.exists():
        error_msg = f"Prompts file not found at {PROMPTS_FILE}"
        logger.error(error_msg)
        return {"status": "error", "error": error_msg}

    try:
        prompts: List[str] = load_prompts(PROMPTS_FILE, raise_on_error=True)
        if not prompts:
            error_msg = "No prompts found in prompts file"
            logger.error(error_msg)
            return {"status": "error", "error": error_msg}

        results: list[Any] = []

        logger.info(f"Running {len(prompts)} prompt(s)...")
        for i, prompt in enumerate(prompts, 1):
            logger.info(f"[{i}/{len(prompts)}] Processing: {prompt[:60]}...")
            # Create a new context (and request) for each prompt
            context: ScraperContext = get_context(prompt)
            result = await run_prompt(prompt, context)
            results.append(result)
            if result.success:
                logger.info(f"  ✅ Success")
            else:
                logger.warning(f"  ❌ Failed: {result.error}")

        # Generate markdown
        OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
        generate_markdown(results, OUTPUT_MD)
        logger.info(f"Markdown written to: {OUTPUT_MD}")

        # Generate HTML
        md_content = OUTPUT_MD.read_text(encoding="utf-8")
        data = parse_markdown(md_content)
        generate_html(data, OUTPUT_HTML)
        logger.info(f"HTML written to: {OUTPUT_HTML}")

        return {
            "status": "ok",
            "prompts": len(prompts),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "output_md": str(OUTPUT_MD),
            "output_html": str(OUTPUT_HTML),
        }
    except Exception as e:
        error_msg = f"Batch job failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "error": error_msg}


@app.post("/run-batch")
async def run_batch_endpoint() -> JSONResponse:
    """Run the batch scraper and regenerate markdown + HTML.

    Can be called manually or by Railway cron webhook.
    """
    result = await run_batch_job()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return JSONResponse(result)


@app.on_event("startup")
async def startup_event():
    """Start the scheduler when the app starts."""
    # Check if scheduler is disabled (for Railway cron webhook alternative)
    if os.environ.get("DISABLE_SCHEDULER", "false").lower() == "true":
        logger.info("Built-in scheduler disabled (DISABLE_SCHEDULER=true)")
        return

    # Schedule daily batch run at 8 AM UTC (adjust timezone if needed)
    # Cron format: minute hour day month day-of-week
    # Set CRON_SCHEDULE env var to override (e.g. "0 8 * * *" for 8 AM UTC)
    cron_schedule = os.environ.get("CRON_SCHEDULE", "0 2 * * *")  # Default: 2 AM UTC daily

    # Parse cron schedule (format: "minute hour day month day-of-week")
    parts = cron_schedule.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
        scheduler.add_job(
            run_batch_job,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone="UTC",
            ),
            id="daily_batch",
            name="Daily batch scraping job",
            replace_existing=True,
        )
        logger.info(f"Scheduled daily batch job at {hour}:{minute} UTC (cron: {cron_schedule})")
    else:
        logger.warning(f"Invalid CRON_SCHEDULE format: {cron_schedule}. Using default 8 AM UTC.")
        scheduler.add_job(
            run_batch_job,
            trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
            id="daily_batch",
            name="Daily batch scraping job",
            replace_existing=True,
        )

    scheduler.start()
    logger.info("Scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the scheduler when the app shuts down."""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
