# Payment Receipts Agent

FastAPI scaffold for a receipt generation service.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Routes

- `GET /health` - health check
- `POST /chat` - chatbot entrypoint with receipt intent detection
- `POST /receipts` - trigger receipt generation

## Knowledge Base

- Edit [knowledge.md](knowledge.md) to change the chatbot fallback context and trigger examples.
