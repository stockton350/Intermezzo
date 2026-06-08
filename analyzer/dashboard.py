#!/usr/bin/env python3
"""
Local dashboard for chess game analysis results.

Usage:
    python dashboard.py [--csv analysis.csv] [--json summary.json] [--port 5000]
"""

import argparse
import csv
import json
import os
from collections import defaultdict

from flask import Flask, render_template, abort

app = Flask(__name__)

CSV_PATH = "analysis.csv"
JSON_PATH = "summary.json"


def load_data(csv_path: str, json_path: str) -> tuple[dict, list[dict]]:
    if not os.path.exists(json_path):
        abort(404, description=f"summary.json not found at {json_path}. Run analyze.py first.")
    with open(json_path, encoding="utf-8") as f:
        summary = json.load(f)

    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["move_number"] = int(row["move_number"])
                row["centipawn_loss"] = float(row["centipawn_loss"])
                rows.append(row)

    return summary, rows


def cpl_by_move(rows: list[dict]) -> list[dict]:
    """Average centipawn loss per move number across all games."""
    bucket = defaultdict(list)
    for row in rows:
        mn = row["move_number"]
        if mn <= 40:
            bucket[mn].append(row["centipawn_loss"])
    result = []
    for mn in sorted(bucket):
        result.append({
            "move": mn,
            "avg_cpl": round(sum(bucket[mn]) / len(bucket[mn]), 1),
            "count": len(bucket[mn]),
        })
    return result


@app.route("/")
def index():
    summary, rows = load_data(app.config["CSV_PATH"], app.config["JSON_PATH"])
    move_cpl = cpl_by_move(rows)
    return render_template("index.html", summary=summary, move_cpl=move_cpl)


def main():
    parser = argparse.ArgumentParser(description="Chess analysis dashboard")
    parser.add_argument("--csv", default=CSV_PATH)
    parser.add_argument("--json", default=JSON_PATH)
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    app.config["CSV_PATH"] = args.csv
    app.config["JSON_PATH"] = args.json

    print(f"Dashboard running at http://localhost:{args.port}")
    app.run(debug=False, port=args.port)


if __name__ == "__main__":
    main()
