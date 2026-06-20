#!/usr/bin/env python3
"""Digimon evolution viewer — serves the asset package built under ../assets.

Run:
    python3 server.py            # http://localhost:6519
"""
import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
STATIC = Path(__file__).resolve().parent / "static"

# Use the shared Python access library
sys.path.insert(0, str(ASSETS / "lib" / "python"))
from digimon_data import DigimonDB  # noqa: E402

db = DigimonDB(str(ASSETS))
app = FastAPI(title="Digimon Evolution Viewer")


@app.get("/api/index")
def api_index():
    """Categories + dims (+ device, counts) straight from the manifest."""
    return {
        "totals": db.totals,
        "categories": [
            {
                "id": c.id,
                "label": c.label,
                "device": c.device,
                "dims": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "digimon_count": d.digimon_count,
                        "digitama": f"/assets/data/{c.id}/{d.id}/digitama.gif",
                    }
                    for d in c.dims
                ],
            }
            for c in db.categories()
        ],
    }


@app.get("/api/dim/{category}/{dim_id}")
def api_dim(category: str, dim_id: str):
    """Raw dim.json (already self-contained: digimon + evolutions + lore)."""
    path = ASSETS / "data" / category / dim_id / "dim.json"
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "DIM not found"})
    data = json.loads(path.read_text())
    data["asset_base"] = f"/assets/data/{category}/{dim_id}"
    return data


# Static asset files (sprites, artwork, digitama) live under /assets/...
app.mount("/assets", StaticFiles(directory=str(ASSETS)), name="assets")
# Front-end
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=6519, reload=True)
