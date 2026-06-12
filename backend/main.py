"""FastAPI web app to view and control a Gecko in.touch2 spa's temperature.

Run with:  uvicorn backend.main:app --host 0.0.0.0 --port 8000

Environment variables:
  SPA_DEMO=1            Use the built-in fake spa (no hardware needed).
  SPA_ADDRESS=1.2.3.4   Optional fixed spa IP (helps across subnets/VLANs).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .spa import DemoSpaController, SpaController

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _build_controller():
    if os.environ.get("SPA_DEMO", "").lower() in ("1", "true", "yes"):
        logging.getLogger("swimspa").info("starting in DEMO mode (no hardware)")
        return DemoSpaController()
    return SpaController(spa_address=os.environ.get("SPA_ADDRESS"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    controller = _build_controller()
    await controller.start()
    app.state.controller = controller
    try:
        yield
    finally:
        await controller.stop()


app = FastAPI(title="Swim Spa Control", lifespan=lifespan)


@app.get("/api/status")
async def get_status():
    return app.state.controller.status()


@app.post("/api/temperature/up")
async def temperature_up():
    return await app.state.controller.step_up()


@app.post("/api/temperature/down")
async def temperature_down():
    return await app.state.controller.step_down()


@app.post("/api/temperature")
async def set_temperature(payload: dict):
    return await app.state.controller.set_temperature(float(payload["value"]))


@app.post("/api/device/{device_id}")
async def set_device(device_id: str, payload: dict):
    """Control a pump/light/blower. Body: {"mode": "HI"} or {"on": true}."""
    return await app.state.controller.set_device(
        device_id, mode=payload.get("mode"), on=payload.get("on")
    )


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")
