from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="AI Content Processing Pipeline")

app.include_router(router)