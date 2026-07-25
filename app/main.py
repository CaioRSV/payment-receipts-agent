import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.services.database import init_db


load_dotenv()


def create_app() -> FastAPI:
    init_db()
    os.makedirs("output", exist_ok=True)
    app = FastAPI(title="Payment Receipts Generator", version="0.1.0")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.mount("/output", StaticFiles(directory="output"), name="output")
    app.include_router(api_router)
    return app


app = create_app()
