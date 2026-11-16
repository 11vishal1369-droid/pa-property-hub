import os
import logging
from core import db, client
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import data
import core_routes
import ops_routes
import round2
import firebase_sync
from seed import run_seed

app = FastAPI(title="PA Super Admin API")


@app.get("/api/")
async def root():
    return {"message": "PA Super Admin API", "status": "ok"}


app.include_router(core_routes.router)
app.include_router(ops_routes.router)
app.include_router(round2.router)
app.include_router(round2.app)
app.include_router(firebase_sync.router)
app.include_router(data.router)

app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO)


@app.on_event("startup")
async def startup():
    await run_seed()
    await round2.migrate_round2()
    await round2.migrate_round8()
    await firebase_sync.start()
    await firebase_sync.publish_fees()


@app.on_event("shutdown")
async def shutdown():
    client.close()
