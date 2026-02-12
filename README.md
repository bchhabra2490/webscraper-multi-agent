# Web Scraper Agent

A multi-agent system built with Python and the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python). An **Evaluator** agent orchestrates a **Scraper** agent: it decides what to scrape, evaluates results, and guides the scraper on retries when results are not satisfactory.

## Architecture

- **Evaluator agent** – Receives the user's goal. Calls the scraper (as a tool), then evaluates the result. If the result is not satisfactory (error, timeout, empty, or wrong content), it uses **search_scrape_history** to see what steps the scraper took, then calls the scraper again with specific guidance (e.g. use Playwright, increase timeout, try scroll). Repeats until the result is good or no longer achievable.
- **Scraper agent** – Performs the actual scraping via **HTTP** and **Playwright** tools. Can be run standalone or invoked by the evaluator. All tool calls are logged to SQLite so the evaluator can inspect history.

## Features

- **HTTP tool** (`http_request`) – GET/POST/HEAD for static pages, APIs, or simple HTML.
- **Playwright tools** – For JS-rendered and dynamic sites: `playwright_get_content`, `playwright_navigate`, `playwright_scroll`.
- **Memory (SQLite)** – Every scrape step is stored in `scraper_memory.db`; the evaluator uses **search_scrape_history** (by domain/URL) to inspect steps and guide retries.
- **Scraping advice** – Store domain-specific advice (e.g. "use playwright_get_content with wait_until networkidle") in `scraping_advice` table. The scraper agent **always calls get_scraping_advice before scraping** to retrieve stored advice for the domain and use it to guide the scraping approach.

## Setup

1. **Create a virtual environment and install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers** (required for Playwright tools)

   ```bash
   playwright install chromium
   ```

3. **Set your OpenAI API key**

   ```bash
   export OPENAI_API_KEY=sk-...
   ```

## Usage

**Default: Evaluator + Scraper** (evaluator guides the scraper and retries on failure)

```bash
python main.py "Scrape https://news.ycombinator.com and list the top 5 story titles."
python main.py "Get the main text content from https://example.com"
python main.py "What is on the front page of https://python.org?"
```

The evaluator will call the scraper, check the result, and if needed inspect history and call the scraper again with guidance (e.g. use Playwright, try scroll, increase timeout).

**Scraper only** (single agent, no evaluator):

```bash
python main.py --scraper "Scrape https://example.com and summarize."
```

**Query history** (evaluator or scraper can use the search tool when you ask):

```bash
python main.py "What have we scraped from example.com before?"
```

**Add scraping advice** (store domain-specific guidance):

```bash
python add_advice.py example.com "Use playwright_get_content with wait_until networkidle"
python add_advice.py github.com "Use playwright_scroll with scroll_times=5 for feeds"
```

**List stored advice**:

```bash
python add_advice.py --list
python add_advice.py --list example.com
```

**Batch processing** (run multiple prompts and consolidate results):

```bash
# 1. Create prompts file (text or JSON format)
cp prompts.txt.example prompts.txt
# Edit prompts.txt: one prompt per line, # for comments

# Or use JSON format:
cp prompts.json.example prompts.json
# Edit prompts.json: ["prompt1", "prompt2", ...]

# 2. Run batch processor
python run_batch.py prompts.txt results/output.md

# Generate HTML version automatically
python run_batch.py prompts.txt results/output.md --html

# Or use environment variables
export PROMPTS_FILE=prompts.txt
export OUTPUT_FILE=results/daily_report.md
export GENERATE_HTML=true
python run_batch.py
```

**Generate HTML from markdown** (convert existing markdown to news site format):

```bash
python generate_html.py results/output.md results/output.html
```

**Local cron setup** (optional, for running batch jobs locally on a schedule):

```bash
# Manually add to crontab
crontab -e
# Add this line (runs daily at 2 AM):
# 0 2 * * * cd /path/to/web-scraper-agent && .venv/bin/python run_batch.py >> cron.log 2>&1

# Customize schedule (cron format: minute hour day month weekday)
# Daily at 9 AM: 0 9 * * *
# Every 6 hours: 0 */6 * * *
# Weekly on Monday at 3 AM: 0 3 * * 1
```

**Note:** For Railway deployment, the built-in scheduler handles cron automatically (see Railway deployment section below).

**Railway deployment** (deploy as a web service with automatic daily runs):

See [RAILWAY_DEPLOY.md](RAILWAY_DEPLOY.md) for detailed instructions.

Quick start:
1. Deploy to Railway (connects to GitHub repo)
2. Set `OPENAI_API_KEY` environment variable
3. Service runs automatically with built-in scheduler (8 AM UTC daily)
4. Visit your Railway URL to see the daily HTML report
5. Optional: Set `CRON_SCHEDULE` to customize run time

The service exposes:
- `GET /` → View the latest HTML report (news-style page)
- `POST /run-batch` → Manually trigger batch run

## Project layout

- `service.py` – FastAPI web service for Railway deployment (serves HTML report, runs batch jobs with built-in scheduler).
- `agent.py` – Evaluator and Scraper agents; Scraper exposed as tool to Evaluator.
- `main.py` – CLI entry point (default: run Evaluator; `--scraper` for Scraper only).
- `run_batch.py` – Batch processor: reads prompts from file, runs each through agent, consolidates results to markdown (optionally generates HTML with `--html`).
- `generate_html.py` – Converts markdown batch results to styled HTML news site format.
- `railway.json` / `Procfile` – Railway deployment configuration.
- `RAILWAY_DEPLOY.md` – Detailed Railway deployment guide.
- `prompts.txt.example` / `prompts.json.example` – Example prompts files (copy to `prompts.txt` and edit).
- `storage.py` – SQLite schema and helpers: `log_tool_call`, `search_history`, `add_advice`, `get_advice`.
- `add_advice.py` – CLI script to add/list scraping advice for domains.
- `tools/http_tools.py` – `http_request` function tool (logs to SQLite).
- `tools/playwright_tools.py` – `playwright_navigate` and `playwright_get_content` (log to SQLite).
- `tools/history_tools.py` – `search_scrape_history` tool (query by domain/URL).
- `tools/advice_tools.py` – `get_scraping_advice` tool (query stored advice by domain).
- `tools/context_tools.py` – `get_today_date` tool (access today's date from context).
- `scraper_memory.db` – Created on first run; stores scrape history and scraping advice (gitignored).
- `results/` – Directory for batch processing output markdown files (gitignored).
- `requirements.txt` – Python dependencies.

## Requirements

- Python 3.9+
- OpenAI API key
- Network access for HTTP and Playwright
