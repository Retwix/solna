from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import events, gallery, ingest, match, photographers, photos

app = FastAPI(title="Solna API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # V0 dev; tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photographers.router)
app.include_router(events.router)
app.include_router(photos.router)
app.include_router(gallery.router)
app.include_router(match.router)
app.include_router(ingest.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
