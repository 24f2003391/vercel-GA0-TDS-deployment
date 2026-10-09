
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Allow POST requests from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# The JSON file is in the repository root.
DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "q-vercel-latency.json"
)

with DATA_FILE.open("r", encoding="utf-8") as f:
    DATA = json.load(f)


class Query(BaseModel):
    regions: list[str]
    threshold_ms: float


def percentile(values, q):
    """Calculate a percentile using linear interpolation."""
    values = sorted(values)
    if not values:
        return None

    position = (len(values) - 1) * q / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)

    return (
        values[lower]
        + (position - lower)
        * (values[upper] - values[lower])
    )


@app.post("/")
def latency(query: Query):
    results = {}

    for region in query.regions:
        rows = [
            row for row in DATA
            if row["region"] == region
        ]

        if not rows:
            results[region] = {
                "avg_latency": None,
                "p95_latency": None,
                "avg_uptime": None,
                "breaches": 0,
            }
            continue

        latencies = [
            float(row["latency_ms"]) for row in rows
        ]
        uptimes = [
            float(row["uptime_pct"]) for row in rows
        ]

        results[region] = {
            "avg_latency": round(
                sum(latencies) / len(latencies), 2
            ),
            "p95_latency": round(
                percentile(latencies, 95), 2
            ),
            "avg_uptime": round(
                sum(uptimes) / len(uptimes), 3
            ),
            "breaches": sum(
                latency > query.threshold_ms
                for latency in latencies
            ),
        }

    return {"regions": results}
