"""Batch runner for scraping prompts. Suitable for cron execution.

Reads prompts from a file, runs each through the agent, and consolidates results into markdown.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from agents import Runner

from agent import evaluator_agent
from main import ScraperContext, get_context
from storage import update_request_final_result

load_dotenv()


@dataclass
class PromptResult:
    """Result of running a single prompt."""

    prompt: str
    success: bool
    output: str
    error: str | None = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


def load_prompts(prompts_file: Path, raise_on_error: bool = False) -> list[str]:
    """Load prompts from a file. Supports JSON array or newline-separated text.

    JSON format: ["prompt1", "prompt2", ...]
    Text format: One prompt per line, # for comments, empty lines ignored.

    Args:
        prompts_file: Path to prompts file.
        raise_on_error: If True, raises FileNotFoundError instead of sys.exit (for web service).
    """
    if not prompts_file.exists():
        error_msg = (
            f"Prompts file not found: {prompts_file}. Create prompts.txt or use prompts.txt.example as a template"
        )
        if raise_on_error:
            raise FileNotFoundError(error_msg)
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    content = prompts_file.read_text().strip()
    if not content:
        print(f"Warning: Prompts file is empty: {prompts_file}", file=sys.stderr)
        return []

    # Try JSON first (if file starts with [ or {)
    if content.strip().startswith(("[", "{")):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                prompts = [str(p).strip() for p in data if p and str(p).strip()]
                if prompts:
                    return prompts
            elif isinstance(data, dict) and "prompts" in data:
                prompts = [str(p).strip() for p in data["prompts"] if p and str(p).strip()]
                if prompts:
                    return prompts
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse as JSON: {e}. Trying text format...", file=sys.stderr)

    # Fall back to newline-separated text
    prompts = [line.strip() for line in content.split("\n") if line.strip() and not line.strip().startswith("#")]
    return prompts


async def run_prompt(prompt: str, context: ScraperContext) -> PromptResult:
    """Run a single prompt through the evaluator agent."""
    try:
        result = await Runner.run(evaluator_agent, prompt, context=context)
        # Update final result and success status
        if context.request_id:
            success = result.final_output and not any(
                keyword in result.final_output.lower()
                for keyword in ["error", "failed", "timeout", "unable", "cannot"]
            )
            update_request_final_result(context.request_id, final_result=result.final_output, success=success)
        return PromptResult(
            prompt=prompt,
            success=True,
            output=result.final_output,
        )
    except Exception as e:
        # Update final result with error
        if context.request_id:
            error_msg = str(e)
            update_request_final_result(context.request_id, final_result=error_msg, success=False)
        return PromptResult(
            prompt=prompt,
            success=False,
            output="",
            error=str(e),
        )


def generate_markdown(results: list[PromptResult], output_file: Path) -> None:
    """Generate a markdown file with consolidated results."""
    today = date.today().isoformat()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Scraping Batch Results",
        "",
        f"**Date:** {today}",
        f"**Generated:** {timestamp}",
        f"**Total prompts:** {len(results)}",
        f"**Successful:** {sum(1 for r in results if r.success)}",
        f"**Failed:** {sum(1 for r in results if not r.success)}",
        "",
        "---",
        "",
    ]

    for i, result in enumerate(results, 1):
        status = "✅ Success" if result.success else "❌ Failed"
        lines.extend(
            [
                f"## Prompt {i}: {status}",
                "",
                f"**Prompt:** {result.prompt}",
                f"**Timestamp:** {result.timestamp}",
                "",
            ]
        )

        if result.success:
            lines.extend(
                [
                    "**Result:**",
                    "",
                    "```",
                    result.output,
                    "```",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "**Error:**",
                    "",
                    "```",
                    result.error or "Unknown error",
                    "```",
                    "",
                ]
            )

        lines.append("---")
        lines.append("")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines))
    print(f"Results written to: {output_file}")


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Default paths (can be overridden via env vars or args)
    prompts_file = Path(os.environ.get("PROMPTS_FILE", "prompts.txt"))
    output_file = Path(os.environ.get("OUTPUT_FILE", f"results/results_{date.today().isoformat()}.md"))

    # Allow override via command line
    if len(sys.argv) > 1:
        prompts_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])

    print(f"Loading prompts from: {prompts_file}")
    prompts = load_prompts(prompts_file)
    if not prompts:
        print("No prompts found. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(prompts)} prompt(s)")
    print(f"Output will be written to: {output_file}\n")

    results = []

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] Running: {prompt[:60]}...")
        # Create a new context (and request) for each prompt
        context = get_context(prompt)
        result = await run_prompt(prompt, context)
        results.append(result)
        if result.success:
            print(f"  ✅ Success")
        else:
            print(f"  ❌ Failed: {result.error}")

    print(f"\nGenerating markdown report...")
    generate_markdown(results, output_file)

    # Optionally generate HTML
    if os.environ.get("GENERATE_HTML", "false").lower() == "true" or "--html" in sys.argv:
        print("Generating HTML report...")
        from generate_html import parse_markdown, generate_html

        md_content = output_file.read_text()
        data = parse_markdown(md_content)
        html_file = output_file.with_suffix(".html")
        generate_html(data, html_file)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
