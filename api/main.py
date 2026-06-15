from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers import events, gallery, ingest

# V0: create tables on startup. (Switch to Alembic migrations before prod.)
import models  # noqa: F401  (register models on Base)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Solna API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # V0 dev; tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(gallery.router)
app.include_router(ingest.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
