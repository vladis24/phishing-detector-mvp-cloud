"""Collect a page and emit structural feature measurements as JSON."""
import argparse
import json
from pathlib import Path
from crawler.browser import collect_page, PageSnapshot
from extractor.features import extract_structural_features, delta_features
from extractor.derived import extract_derived_features
from extractor.network_features import extract_network_features
from extractor.temporal import extract_temporal_features, LATE_CHANGE_MS


def analyze_snapshot(snapshot: PageSnapshot, late_ms: int = LATE_CHANGE_MS) -> dict:
    """Extract each checkpoint once and assemble compatible output sections."""
    checkpoints = [{"checkpoint_ms": point.checkpoint_ms, "elapsed_ms": point.elapsed_ms,
                    "url": point.url, "profile": extract_structural_features(point.html, point.url)}
                   for point in snapshot.checkpoints]
    if not checkpoints:
        raise ValueError("Snapshot must contain checkpoints")
    early, rendered = checkpoints[0]["profile"], checkpoints[-1]["profile"]
    return {
        "url": snapshot.url, "final_url": snapshot.final_url, "status_code": snapshot.status_code,
        "early_dom": early, "rendered": rendered, "delta": delta_features(early, rendered),
        "derived": extract_derived_features(early, rendered),
        "temporal": extract_temporal_features(checkpoints, late_ms),
        "network": extract_network_features(snapshot.final_url, snapshot.requested_urls,
                                             snapshot.requests_after_domcontentloaded),
    }


def main() -> None:
    """Run passive collection with configurable DCL-relative checkpoints."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--checkpoints-ms", help="e.g. 0,500,1000,2000")
    parser.add_argument("--late-ms", type=int, default=LATE_CHANGE_MS)
    parser.add_argument("--output", type=Path, default=Path("sample_result.json"))
    args = parser.parse_args()
    if args.late_ms < 0:
        parser.error("--late-ms must be non-negative")
    offsets = tuple(map(int, args.checkpoints_ms.split(","))) if args.checkpoints_ms else None
    result = analyze_snapshot(collect_page(args.url, checkpoints_ms=offsets), args.late_ms)
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    args.output.write_text(content, encoding="utf-8")
    print(content)
    print(f"\nSaved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()

