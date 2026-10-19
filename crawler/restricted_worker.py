"""Private worker protocol; stdin is configuration, stdout is a snapshot or error."""
from dataclasses import asdict
import json
import sys
from playwright.sync_api import TimeoutError as BrowserTimeout
from crawler.browser import collect_page
from crawler.restricted import RestrictedLimits


def main():
    try:
        args = json.load(sys.stdin)
        snapshot = collect_page(args["url"], timeout_ms=args["timeout_ms"], checkpoints_ms=args["schedule"],
            restricted=True, restricted_limits=RestrictedLimits(**args["limits"]), _in_restricted_worker=True,
            network_policy=args.get("network_policy"))
        result = asdict(snapshot)
    except Exception as exc:
        result = {"error": str(exc), "timeout": isinstance(exc, BrowserTimeout),
                  "operational": getattr(exc, "operational", {"mode": "restricted-v1"})}
    sys.stdout.write(json.dumps(result, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
