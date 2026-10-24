"""CXR AI Teaching Sandbox — local web app.

Run:  pip install -r requirements.txt && python app.py   (then open http://127.0.0.1:7860)
Teaching and research only — not a clinical device.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sandbox import model

ROOT = Path(__file__).parent
SAMPLES_DIR = ROOT / "samples"
STATIC_DIR = ROOT / "static"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"}
DISCLAIMER = "Teaching and research only — not a clinical device."

log = logging.getLogger("sandbox")
SAMPLES = {s["id"]: s for s in json.loads((SAMPLES_DIR / "samples.json").read_text())}

app = FastAPI(title="CXR AI Teaching Sandbox", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/samples")
def list_samples() -> dict:
    return {"samples": list(SAMPLES.values()), "labels": model.all_labels(), "disclaimer": DISCLAIMER}


def as_payload(result: model.Result) -> dict:
    return {
        "findings": [{"label": f.label, "score": f.score} for f in result.findings],
        "cam_label": result.cam_label,
        "image": "data:image/png;base64," + base64.b64encode(result.image_png).decode(),
        "overlay": "data:image/png;base64," + base64.b64encode(result.overlay_png).decode(),
        "has_tube_position_output": False,
        "disclaimer": DISCLAIMER,
    }


@app.post("/api/analyse")
async def analyse(sample_id: str | None = Form(None), cam_label: str | None = Form(None),
                  file: UploadFile | None = File(None)) -> dict:
    if cam_label is not None and cam_label not in model.all_labels():
        raise HTTPException(400, "Unknown heatmap label.")
    if sample_id:
        if sample_id not in SAMPLES:
            raise HTTPException(404, "Unknown sample.")
        data = (SAMPLES_DIR / SAMPLES[sample_id]["file"]).read_bytes()
    elif file is not None:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(415, "Please upload a PNG, JPEG, WebP or BMP image (not DICOM).")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image is larger than 10 MB.")
    else:
        raise HTTPException(400, "Choose a sample or upload an image.")
    try:
        result = model.analyse(data, cam_label=cam_label)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception:  # keep server details out of the response
        log.exception("analysis failed")
        raise HTTPException(500, "The model could not analyse this image.")
    return as_payload(result)  # uploads are processed in memory and never stored


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    model.load_model()  # download weights (~30 MB) on first run, before serving
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
