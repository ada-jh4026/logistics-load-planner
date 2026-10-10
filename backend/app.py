"""FastAPI application for the city-delivery load planner.

B01 scope: a reproducible backend skeleton exposing the health endpoint only.
The business solver and the rest of the API (CONTRACT.md) are added by later
tasks (B02+). This module must stay importable so tests can build a TestClient
without binding a port.
"""

from fastapi import FastAPI

SCHEMA_VERSION = "0.1"

app = FastAPI(title="city-delivery-load-planner", version=SCHEMA_VERSION)


@app.get("/api/health")
def health() -> dict:
    """Return the protocol version agreed in CONTRACT.md."""
    return {"status": "ok", "schema_version": SCHEMA_VERSION}
