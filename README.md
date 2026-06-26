# Payment Receipts Agent

FastAPI scaffold for a receipt generation service.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Routes

- `GET /health` - health check
- `POST /receipts` - trigger receipt generation
