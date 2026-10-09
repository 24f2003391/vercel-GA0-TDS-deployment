
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

app = FastAPI()

# Add CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure CORS headers are present on all responses.
class EnsureCORSHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

app.add_middleware(EnsureCORSHeaders)

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


@app.options("/")
@app.options("/api")
@app.options("/api/latency")
def cors_preflight():
    return JSONResponse(
        content={"ok": True},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.post("/")
@app.post("/api")
@app.post("/api/latency")
async def latency(query: Query):
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
                x > query.threshold_ms for x in latencies
            ),
        }

    return JSONResponse(
    content={"regions": results},
    headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    },
)
