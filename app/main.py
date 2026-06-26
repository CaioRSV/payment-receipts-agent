from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.router import api_router


load_dotenv()


def create_app() -> FastAPI:
    app = FastAPI(title="Payment Receipts Agent", version="0.1.0")
    app.include_router(api_router)
    return app


app = create_app()
