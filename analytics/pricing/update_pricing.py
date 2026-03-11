#!/usr/bin/env python3
"""update_pricing.py -- Manually update analytics/pricing/pricing.json.

This script provides a simple CLI to inspect and patch individual model rates in
pricing.json.  It does NOT call any external pricing API automatically, because
Azure AI pricing is subject to change and any automated scraping would require
accepting Terms of Service conditions that differ by region and agreement type.

Workflow:
1. Check current rates on https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
2. Run this script to update the affected model(s).
3. Commit the updated pricing.json.

Usage examples:
    # List all current rates
    python update_pricing.py list

    # Update a model's input/output rate
    python update_pricing.py update gpt-4o --version 2024-08-06 \
        --input-rate 0.0025 --output-rate 0.01

    # Add a brand-new model entry
    python update_pricing.py add o3-mini --version 2025-06-01 \
        --display-name "o3-mini" --input-rate 0.0011 --output-rate 0.0044
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PRICING_FILE = Path(__file__).parent / "pricing.json"


def load() -> dict:
    return json.loads(PRICING_FILE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    data["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    PRICING_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] Saved {PRICING_FILE}")


def cmd_list(args: argparse.Namespace) -> None:  # noqa: ARG001
    data = load()
    print(f"{'Model':<35} {'Version':<15} {'Input/1K':>10} {'Output/1K':>10} {'Cached/1K':>12}")
    print("-" * 85)
    for model in data["models"]:
        for ver in model["versions"]:
            cached = ver.get("cached_input_rate")
            print(
                f"{model['id']:<35} {ver['version']:<15}"
                f" {'$' + str(ver['input_rate']):>10}"
                f" {'$' + str(ver['output_rate']):>10}"
                f" {'$' + str(cached) if cached is not None else 'n/a':>12}"
            )


def cmd_update(args: argparse.Namespace) -> None:
    data = load()
    for model in data["models"]:
        if model["id"] != args.model_id:
            continue
        for ver in model["versions"]:
            if ver["version"] != args.version:
                continue
            if args.input_rate is not None:
                ver["input_rate"] = args.input_rate
            if args.output_rate is not None:
                ver["output_rate"] = args.output_rate
            if args.cached_input_rate is not None:
                ver["cached_input_rate"] = args.cached_input_rate
            save(data)
            print(f"[ok] Updated {args.model_id} v{args.version}")
            return
        print(f"[error] Version '{args.version}' not found for model '{args.model_id}'", file=sys.stderr)
        sys.exit(1)
    print(f"[error] Model '{args.model_id}' not found", file=sys.stderr)
    sys.exit(1)


def cmd_add(args: argparse.Namespace) -> None:
    data = load()
    # Find existing model entry or create a new one
    target: dict | None = next((m for m in data["models"] if m["id"] == args.model_id), None)
    if target is None:
        target = {"id": args.model_id, "display_name": args.display_name or args.model_id, "versions": []}
        data["models"].append(target)
    new_version: dict = {
        "version": args.version,
        "input_rate": args.input_rate,
        "output_rate": args.output_rate,
        "cached_input_rate": args.cached_input_rate,
    }
    target["versions"].append(new_version)
    save(data)
    print(f"[ok] Added {args.model_id} v{args.version}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update analytics/pricing/pricing.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all current rates")

    p_update = sub.add_parser("update", help="Update rates for an existing model version")
    p_update.add_argument("model_id", help="Model ID, e.g. gpt-4o")
    p_update.add_argument("--version", required=True, help="Version string, e.g. 2024-08-06")
    p_update.add_argument("--input-rate", type=float, default=None)
    p_update.add_argument("--output-rate", type=float, default=None)
    p_update.add_argument("--cached-input-rate", type=float, default=None)

    p_add = sub.add_parser("add", help="Add a new model or version")
    p_add.add_argument("model_id", help="Model ID")
    p_add.add_argument("--version", required=True)
    p_add.add_argument("--display-name", default=None)
    p_add.add_argument("--input-rate", type=float, required=True)
    p_add.add_argument("--output-rate", type=float, required=True)
    p_add.add_argument("--cached-input-rate", type=float, default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {"list": cmd_list, "update": cmd_update, "add": cmd_add}
    handlers[args.command](args)


if __name__ == "__main__":
    main()
