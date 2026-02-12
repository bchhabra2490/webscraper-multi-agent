"""Convert markdown batch results to HTML news site format."""

import re
import sys
from datetime import datetime
from pathlib import Path


def parse_markdown(md_content: str) -> dict:
    """Parse markdown content and extract metadata and prompts."""
    lines = md_content.split("\n")

    metadata = {}
    prompts = []
    current_prompt = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Parse metadata
        if line.startswith("**Date:**"):
            metadata["date"] = line.replace("**Date:**", "").strip()
        elif line.startswith("**Generated:**"):
            metadata["generated"] = line.replace("**Generated:**", "").strip()
        elif line.startswith("**Total prompts:**"):
            metadata["total"] = int(line.replace("**Total prompts:**", "").strip())
        elif line.startswith("**Successful:**"):
            metadata["successful"] = int(line.replace("**Successful:**", "").strip())
        elif line.startswith("**Failed:**"):
            metadata["failed"] = int(line.replace("**Failed:**", "").strip())

        # Parse prompt sections
        elif line.startswith("## Prompt"):
            if current_prompt:
                prompts.append(current_prompt)

            # Extract status
            status_match = re.search(r"(✅ Success|❌ Failed)", line)
            status = "success" if status_match and "Success" in status_match.group() else "failed"

            current_prompt = {
                "number": len(prompts) + 1,
                "status": status,
                "prompt": "",
                "timestamp": "",
                "result": "",
                "error": "",
            }

        elif current_prompt:
            if line.startswith("**Prompt:**"):
                current_prompt["prompt"] = line.replace("**Prompt:**", "").strip()
            elif line.startswith("**Timestamp:**"):
                current_prompt["timestamp"] = line.replace("**Timestamp:**", "").strip()
            elif line.startswith("**Result:**"):
                # Collect result content until closing ```
                i += 1  # Move to next line
                if i < len(lines) and lines[i].strip() == "":
                    i += 1  # Skip empty line
                if i < len(lines) and lines[i].strip().startswith("```"):
                    i += 1  # Skip opening ```
                result_lines = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    result_lines.append(lines[i])
                    i += 1
                # i now points to closing ```, will be incremented by outer loop
                current_prompt["result"] = "\n".join(result_lines).strip()
            elif line.startswith("**Error:**"):
                # Collect error content until closing ```
                i += 1  # Move to next line
                if i < len(lines) and lines[i].strip() == "":
                    i += 1  # Skip empty line
                if i < len(lines) and lines[i].strip().startswith("```"):
                    i += 1  # Skip opening ```
                error_lines = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    error_lines.append(lines[i])
                    i += 1
                # i now points to closing ```, will be incremented by outer loop
                current_prompt["error"] = "\n".join(error_lines).strip()

        i += 1

    if current_prompt:
        prompts.append(current_prompt)

    return {"metadata": metadata, "prompts": prompts}


def generate_html(data: dict, output_file: Path) -> None:
    """Generate HTML news site from parsed data."""
    metadata = data["metadata"]
    prompts = data["prompts"]

    date = metadata.get("date", "Unknown")
    generated = metadata.get("generated", "")
    total = metadata.get("total", 0)
    successful = metadata.get("successful", 0)
    failed = metadata.get("failed", 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scraping News Report - {date}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.7;
            color: #1f2933;
            background: linear-gradient(to bottom, #fdfdfd 0%, #f3f4f6 40%, #edf2f7 100%);
            min-height: 100vh;
        }}
        
        .header {{
            background: linear-gradient(135deg, #e0f2fe 0%, #c7d2fe 40%, #fee2f8 100%);
            color: #111827;
            padding: 3rem 0 2.5rem;
            box-shadow: 0 3px 14px rgba(15, 23, 42, 0.08);
            border-bottom: 1px solid rgba(148, 163, 184, 0.4);
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 2rem;
        }}
        
        .header-content {{
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.6rem;
            margin-bottom: 0.6rem;
            font-weight: 700;
            letter-spacing: -0.4px;
            color: #0f172a;
        }}
        
        .header .subtitle {{
            font-size: 1.05rem;
            opacity: 0.9;
            font-weight: 400;
            color: #374151;
        }}
        
        .stats {{
            display: flex;
            justify-content: center;
            gap: 2.5rem;
            margin-top: 2rem;
            flex-wrap: wrap;
        }}
        
        .stat-item {{
            background: rgba(255,255,255,0.9);
            padding: 0.9rem 1.6rem;
            border-radius: 999px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(148, 163, 184, 0.35);
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
        }}
        
        .stat-item:hover {{
            transform: translateY(-1px);
            background: rgba(255,255,255,1);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
        }}
        
        .stat-value {{
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1.2;
            color: #111827;
        }}
        
        .stat-label {{
            font-size: 0.9rem;
            opacity: 0.9;
            margin-top: 0.1rem;
            font-weight: 500;
            color: #4b5563;
        }}
        
        .content {{
            padding: 2.5rem 0 4rem;
        }}
        
        .article {{
            background: #ffffff;
            margin-bottom: 2.25rem;
            border-radius: 18px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            overflow: hidden;
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
            border: 1px solid rgba(148, 163, 184, 0.35);
        }}
        
        .article:hover {{
            transform: translateY(-4px);
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
            border-color: rgba(129, 140, 248, 0.7);
        }}
        
        .article-header {{
            padding: 1.7rem 2.3rem;
            border-bottom: 1px solid #e5e7eb;
            background: linear-gradient(to bottom, #f9fafb 0%, #ffffff 100%);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1rem;
            cursor: pointer;
        }}
        
        .article-number {{
            font-size: 0.8rem;
            color: #9ca3af;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 0.5rem;
        }}
        
        .article-status {{
            padding: 0.5rem 1.25rem;
            border-radius: 24px;
            font-size: 0.875rem;
            font-weight: 600;
            white-space: nowrap;
            flex-shrink: 0;
        }}

        .article-header-right {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .article-toggle-btn {{
            border: none;
            background: #e0f2fe;
            color: #1d4ed8;
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.35rem 0.9rem;
            border-radius: 999px;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            transition: background 0.15s ease, transform 0.1s ease, box-shadow 0.15s ease;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
        }}

        .article-toggle-btn:hover {{
            background: #dbeafe;
            transform: translateY(-1px);
            box-shadow: 0 3px 6px rgba(15, 23, 42, 0.16);
        }}

        .article-toggle-btn:active {{
            transform: translateY(0);
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
        }}

        .article-toggle-btn span.icon {{
            font-size: 0.85rem;
        }}
        
        .status-success {{
            background: #e0f9f0;
            color: #166534;
            border: 1px solid #bfe9dd;
        }}
        
        .status-failed {{
            background: #fde2e2;
            color: #b91c1c;
            border: 1px solid #f9caca;
        }}
        
        .article-prompt {{
            font-size: 1.4rem;
            font-weight: 600;
            color: #111827;
            margin-top: 0.5rem;
            line-height: 1.5;
            letter-spacing: -0.3px;
        }}
        
        .article-meta {{
            font-size: 0.85rem;
            color: #6b7280;
            margin-top: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .article-meta::before {{
            content: "🕒";
            font-size: 0.75rem;
        }}
        
        .article-body {{
            padding: 2.2rem 2.3rem 2.5rem;
        }}

        .article-body.collapsed {{
            display: none;
        }}
        
        .article-body h3 {{
            color: #4f46e5;
            margin-bottom: 1.5rem;
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 700;
        }}
        
        .article-content {{
            color: #374151;
            line-height: 1.85;
            font-size: 1.0625rem;
            max-width: 100%;
        }}
        
        .article-content p {{
            margin-bottom: 1.25rem;
            text-align: justify;
            hyphens: auto;
        }}
        
        .article-content ul, .article-content ol {{
            margin-left: 1.75rem;
            margin-bottom: 1.5rem;
            padding-left: 0.5rem;
        }}
        
        .article-content li {{
            margin-bottom: 0.75rem;
            line-height: 1.8;
        }}
        
        .article-content ol {{
            list-style-type: decimal;
        }}
        
        .article-content ul {{
            list-style-type: disc;
        }}
        
        .article-content ul ul, .article-content ol ol, .article-content ul ol, .article-content ol ul {{
            margin-top: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .article-content a {{
            color: #2563eb;
            text-decoration: none;
            border-bottom: 2px solid #93c5fd;
            padding-bottom: 1px;
            transition: all 0.2s ease;
            font-weight: 500;
        }}
        
        .article-content a:hover {{
            color: #1e40af;
            border-bottom-color: #2563eb;
            background: #eff6ff;
            padding: 0 2px;
            margin: 0 -2px;
            border-radius: 3px;
        }}
        
        .error-content {{
            background: #fef2f2;
            border-left: 4px solid #f97373;
            padding: 1.5rem;
            border-radius: 8px;
            color: #991b1b;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
            white-space: pre-wrap;
            font-size: 0.9375rem;
            line-height: 1.6;
        }}
        
        .footer {{
            text-align: center;
            padding: 3rem 2rem;
            color: #6b7280;
            font-size: 0.9375rem;
            background: rgba(255,255,255,0.9);
            border-top: 1px solid #e5e7eb;
        }}
        
        .footer p {{
            margin: 0.5rem 0;
        }}
        
        @media (max-width: 768px) {{
            .header {{
                padding: 2rem 0 2rem;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            .header .subtitle {{
                font-size: 1rem;
            }}
            
            .stats {{
                flex-direction: column;
                gap: 1rem;
                margin-top: 1.5rem;
            }}
            
            .stat-item {{
                padding: 0.875rem 1.5rem;
            }}
            
            .article-header {{
                flex-direction: column;
                align-items: flex-start;
                padding: 1.5rem;
            }}
            
            .article-body {{
                padding: 1.5rem;
            }}
            
            .article-prompt {{
                font-size: 1.25rem;
            }}
            
            .container {{
                padding: 0 1.25rem;
            }}
            
            .content {{
                padding: 2rem 0 3rem;
            }}
        }}
        
        @media (prefers-color-scheme: dark) {{
            body {{
                background: linear-gradient(to bottom, #111827 0%, #1f2937 100%);
                color: #f3f4f6;
            }}
            
            .article {{
                background: #1f2937;
                border-color: rgba(255,255,255,0.1);
            }}
            
            .article-header {{
                background: linear-gradient(to bottom, #111827 0%, #1f2937 100%);
                border-color: rgba(255,255,255,0.1);
            }}
            
            .article-prompt {{
                color: #f9fafb;
            }}
            
            .article-content {{
                color: #d1d5db;
            }}
            
            .article-number {{
                color: #9ca3af;
            }}
            
            .article-meta {{
                color: #9ca3af;
            }}
            
            .footer {{
                background: rgba(0,0,0,0.3);
                border-color: rgba(255,255,255,0.1);
                color: #9ca3af;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <div class="header-content">
                <h1>📰 Scraping News Report</h1>
                <div class="subtitle">Automated Web Scraping Results</div>
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value">{total}</div>
                        <div class="stat-label">Total Prompts</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{successful}</div>
                        <div class="stat-label">Successful</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{failed}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                </div>
            </div>
        </div>
    </header>
    
    <main class="content">
        <div class="container">
"""

    for prompt in prompts:
        status_class = "status-success" if prompt["status"] == "success" else "status-failed"
        status_text = "✅ Success" if prompt["status"] == "success" else "❌ Failed"

        html += f"""
            <article class="article">
                <div class="article-header">
                    <div>
                        <div class="article-number">Article #{prompt['number']}</div>
                        <div class="article-prompt">{prompt['prompt']}</div>
                        <div class="article-meta">Generated: {prompt['timestamp']}</div>
                    </div>
                    <div class="article-header-right">
                        <span class="article-status {status_class}">{status_text}</span>
                        <button class="article-toggle-btn" type="button" aria-expanded="true">
                            <span class="icon">▾</span>
                            <span class="label">Hide</span>
                        </button>
                    </div>
                </div>
                <div class="article-body">
"""

        if prompt["status"] == "success":
            html += f"""
                    <h3>Result</h3>
                    <div class="article-content">{format_content(prompt['result'])}</div>
"""
        else:
            html += f"""
                    <h3>Error</h3>
                    <div class="error-content">{escape_html(prompt['error'])}</div>
"""

        html += """
                </div>
            </article>
"""

    html += f"""
        </div>
    </main>
    
    <footer class="footer">
        <div class="container">
            <p>Report generated on {generated}</p>
            <p>Date: {date}</p>
        </div>
    </footer>

    <script>
        // Make each article section toggleable (show/hide result body)
        document.addEventListener('DOMContentLoaded', function () {{
            const articles = document.querySelectorAll('.article');
            articles.forEach(function (article) {{
                const header = article.querySelector('.article-header');
                const body = article.querySelector('.article-body');
                const btn = article.querySelector('.article-toggle-btn');
                const label = btn ? btn.querySelector('.label') : null;
                const icon = btn ? btn.querySelector('.icon') : null;

                if (!header || !body || !btn || !label || !icon) {{
                    return;
                }}

                function setExpanded(expanded) {{
                    if (expanded) {{
                        body.classList.remove('collapsed');
                        btn.setAttribute('aria-expanded', 'true');
                        label.textContent = 'Hide';
                        icon.textContent = '▾';
                    }} else {{
                        body.classList.add('collapsed');
                        btn.setAttribute('aria-expanded', 'false');
                        label.textContent = 'Show';
                        icon.textContent = '▸';
                    }}
                }}

                // Start expanded by default
                setExpanded(true);

                function toggle() {{
                    const isCollapsed = body.classList.contains('collapsed');
                    setExpanded(isCollapsed);
                }}

                // Click on button
                btn.addEventListener('click', function (event) {{
                    event.stopPropagation();
                    toggle();
                }});

                // Click on header area (excluding direct clicks on links)
                header.addEventListener('click', function (event) {{
                    // Don't toggle if clicking a link or the status pill directly
                    const target = event.target;
                    if (target.closest('a') || target.closest('.article-status') || target.closest('.article-toggle-btn')) {{
                        return;
                    }}
                    toggle();
                }});
            }});
        }});
    </script>
</body>
</html>
"""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html)
    print(f"HTML generated: {output_file}")


def format_content(text: str) -> str:
    """Format content text for HTML display."""
    if not text:
        return ""

    # First, escape HTML to prevent XSS
    text = escape_html(text)

    # Then convert URLs to links (after escaping, so URLs are safe)
    url_pattern = r"(https?://[^\s\)]+)"
    text = re.sub(url_pattern, r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', text)

    # Convert numbered lists and bullet points
    lines = text.split("\n")
    formatted_lines = []
    in_list = False
    list_type = None
    consecutive_breaks = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Handle empty lines
        if not stripped:
            consecutive_breaks += 1
            if in_list:
                formatted_lines.append(f"</{list_type}>")
                in_list = False
                list_type = None
            # Only add one break, skip multiple consecutive breaks
            if consecutive_breaks == 1:
                formatted_lines.append("<br>")
            continue

        consecutive_breaks = 0

        # Numbered list items (e.g., "1. Item" or "1) Item")
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if not in_list or list_type != "ol":
                if in_list:
                    formatted_lines.append(f"</{list_type}>")
                formatted_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r"^\d+[\.\)]\s+", "", stripped)
            formatted_lines.append(f"<li>{content}</li>")
        # Bullet points with dash or asterisk
        elif re.match(r"^[-*]\s+", stripped) and not stripped.startswith("---"):
            if not in_list or list_type != "ul":
                if in_list:
                    formatted_lines.append(f"</{list_type}>")
                formatted_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            content = re.sub(r"^[-*]\s+", "", stripped)
            formatted_lines.append(f"<li>{content}</li>")
        else:
            if in_list:
                formatted_lines.append(f"</{list_type}>")
                in_list = False
                list_type = None
            # Regular paragraph
            formatted_lines.append(f"<p>{stripped}</p>")

    if in_list:
        formatted_lines.append(f"</{list_type}>")

    return "\n".join(formatted_lines)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python generate_html.py <input.md> [output.html]", file=sys.stderr)
        print("Example: python generate_html.py results/output.md results/output.html", file=sys.stderr)
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    else:
        output_file = input_file.with_suffix(".html")

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading: {input_file}")
    md_content = input_file.read_text()

    print("Parsing markdown...")
    data = parse_markdown(md_content)

    print(f"Found {len(data['prompts'])} prompt(s)")
    print(f"Generating HTML...")
    generate_html(data, output_file)
    print("Done.")


if __name__ == "__main__":
    main()
