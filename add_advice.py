"""CLI script to add scraping advice to the SQLite database."""

import sys

from storage import add_advice, get_advice


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: python add_advice.py <domain> <advice>\n"
            "Example: python add_advice.py example.com 'Use playwright_get_content with wait_until networkidle'\n"
            "\n"
            "To list existing advice:\n"
            "  python add_advice.py --list [domain]\n"
            "Example: python add_advice.py --list example.com",
            file=sys.stderr,
        )
        sys.exit(1)

    if sys.argv[1] == "--list":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        advice_list = get_advice(domain=domain)
        if not advice_list:
            print(f"No advice found" + (f" for domain '{domain}'" if domain else ""))
            return
        print(f"Scraping advice{' for ' + domain if domain else ''}:\n")
        for a in advice_list:
            print(f"[{a['created_at']}] {a['domain']}: {a['advice']}")
        return

    domain = sys.argv[1]
    advice = " ".join(sys.argv[2:])

    try:
        advice_id = add_advice(domain, advice)
        print(f"Added advice (ID: {advice_id}) for domain '{domain}': {advice}")
    except Exception as e:
        print(f"Error adding advice: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
