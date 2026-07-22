from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from km_agents.evaluation import EvaluationDataError, RunRecord, generate_report


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "evaluation" / "corpus" / "v1" / "manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and report the 72 synthetic KM Agents evaluation runs."
    )
    parser.add_argument("--results", type=Path, required=True, help="JSONL result records")
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST, help="Synthetic corpus manifest"
    )
    parser.add_argument("--output", type=Path, required=True, help="Report JSON destination")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        runs = _read_runs(args.results)
        report = generate_report(manifest, runs)
    except (OSError, json.JSONDecodeError, EvaluationDataError) as exc:
        print(f"Evaluation report failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote report for {report['observed_run_count']} synthetic runs to {args.output}",
        file=sys.stderr,
    )
    return 0


def _read_runs(path: Path) -> list[RunRecord]:
    records: list[RunRecord] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationDataError(f"Invalid JSON on results line {number}") from exc
        try:
            records.append(RunRecord.from_json(value))
        except EvaluationDataError as exc:
            raise EvaluationDataError(f"Invalid results line {number}: {exc}") from exc
    return records


if __name__ == "__main__":
    raise SystemExit(main())
