"""HTTP server for the panel."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config


class Question(BaseModel):
    question: str


class Augment(BaseModel):
    name: str


def create_app(coach) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    def index():
        return FileResponse(config.WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/state")
    def state():
        return coach.view()

    @app.post("/api/refresh")
    def refresh():
        coach.request("the player asked for a fresh plan", urgent=True)
        return {"ok": True}

    @app.post("/api/screen")
    def read_screen():
        coach.read_screen()
        return {"ok": True}

    @app.post("/api/augment")
    def took_augment(body: Augment):
        coach.took_augment(body.name)
        return {"ok": True}

    @app.post("/api/ask")
    def ask(body: Question):
        question = body.question.strip()[:500]
        if not question:
            return {"answer": ""}
        try:
            return {"answer": coach.ask(question)}
        except Exception as exc:
            return {"answer": "", "error": str(exc)}

    return app
