import logging
from contextlib import asynccontextmanager
from logging import getLogger
from app.routes import voice_route

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(name)s :: %(message)s'
)
logger = getLogger(__name__)

def on_server_startup():
    logger.info("Server is starting up...")

def on_server_shutdown():
    logger.info("Server is shutting down...")


@asynccontextmanager
async def lifespan(app: FastAPI):
    on_server_startup()
    yield
    on_server_shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Voice Assistant is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

app.include_router(voice_route.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)