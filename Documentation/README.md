# Fair Split - Architecture and API Reference

## Architecture

```
Frontend (fair-split.html)
    POST /split  {receipt_base64, description}
          |
    FastAPI  /split endpoint
          |
    Gemini 2.5 Flash: vision OCR + NLP
    Extracts structured JSON: items, assignments, people, bill totals
          |
    compute_split() in main.py
    - per-person subtotals from item assignments
    - proportional tax/service/discount
    - rounding correction
    - settle-up computation
    - reconciliation check
          |
    Response JSON
```

**Key decision:** The LLM extracts structured data; Python computes all arithmetic. This prevents hallucinated totals and makes every result reproducible.

## Local setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env.local

# 3. Start the server
uvicorn main:app --reload --port 8000

# 4. Open fair-split.html in a browser
#    Set the endpoint field to: http://localhost:8000/split
```

## Deploy to Render

1. Push this folder to a GitHub repo.
2. Render dashboard: New Web Service, connect repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment variable: `GEMINI_API_KEY = <your key>`
6. After deploy, update the endpoint field in `fair-split.html` to your Render URL.

## Deploy to Railway

```bash
railway login
railway init
railway up
railway variables set GEMINI_API_KEY=your_key
```

## API contract

### POST /split

Request body:

```json
{
  "receipt_base64": "<base64-encoded image bytes, no data-URI prefix>",
  "description": "<plain-English who-had-what string>"
}
```

Response:

```json
{
  "per_person": [
    {
      "name": "Ravi",
      "items": ["Cappuccino", "Grilled Chicken Sandwich"],
      "subtotal": 440,
      "tax_share": 23,
      "service_share": 22,
      "discount_share": 0,
      "total": 485
    }
  ],
  "grand_total": 1147,
  "reconciliation": { "sum_of_person_totals": 1147, "matches_bill": true },
  "paid_by": "Sameer",
  "settle_up": [{ "from": "Ravi", "to": "Sameer", "amount": 485 }],
  "assumptions": ["Sameer absorbs Rs.1 rounding difference"],
  "flags": []
}
```

The `reconciliation`, `assumptions`, and `flags` fields are always present. `flags` contains anything the system could not resolve cleanly. Nothing is silently guessed.

### GET /health

Returns `{"status": "ok"}`. Used by Render/Railway for uptime checks.

## Deliverables

| File | Description |
|---|---|
| `fair-split.html` | Frontend: upload image, paste description, review and edit assignments, see result |
| `main.py` | FastAPI backend with Gemini Vision integration and arithmetic engine |
| `Documentation/PROMPT_LOG.md` | Prompt iteration log and arithmetic decision rationale |
| `Documentation/EDGE_CASES.md` | Edge cases considered with handling approach |
