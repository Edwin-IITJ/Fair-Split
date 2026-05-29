# Fair Split

Upload a restaurant receipt photo and describe who had what. Returns a per-person split including tax, service charge, discounts, and a settle-up.

## Architecture

```
Frontend (fair-split.html)
    POST /split  {receipt_base64, description}
          |
    FastAPI backend (main.py)
          |
    Gemini 2.5 Flash: vision OCR + NLP
    Extracts: items, assignments, people, bill totals
          |
    Python arithmetic engine
    Computes: proportional tax/service/discount per person
    Validates: reconciliation, flags mismatches
          |
    JSON response
```

The LLM handles structured data extraction only. All arithmetic is deterministic Python. This keeps results reproducible and every calculation auditable.

## Features

- Receipt OCR via Gemini Vision (JPEG, PNG, WEBP supported)
- Plain-English description of who had what
- Editable item ownership table with live re-computation in the browser
- Reconciliation check on every result
- Flags and assumptions surfaced explicitly; nothing is silently guessed
- Copy summary to clipboard
- Light and dark mode

## API

### Request

`POST /split` with `Content-Type: application/json`

```json
{
  "receipt_base64": "<base64-encoded image bytes, no data-URI prefix>",
  "description": "<plain-English who-had-what string>"
}
```

### Response

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

## Fairness rules

1. Each person pays for the items they consumed.
2. Shared items split equally among the people who shared that specific item.
3. Tax and service charge allocated proportional to each person's pre-tax food subtotal.
4. A bill-level discount allocated proportional to subtotal.
5. Round to the rupee; state in `assumptions` who absorbs the leftover paise.

## Local setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env.local

# Start the server
uvicorn main:app --reload --port 8000

# Open fair-split.html in a browser
# The endpoint field defaults to http://localhost:8000/split
```

## Deploy to Render

1. Push this repo to GitHub.
2. Render dashboard: New Web Service, connect repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set environment variable: `GEMINI_API_KEY = <your key>`
6. Update the endpoint field in `fair-split.html` to your deployed URL.

## Deploy to Railway

```bash
railway login && railway init && railway up
railway variables set GEMINI_API_KEY=your_key
```

## Documentation

| File | Contents |
|---|---|
| [`Documentation/PROMPT_LOG.md`](Documentation/PROMPT_LOG.md) | Prompt iteration log and arithmetic decision rationale |
| [`Documentation/EDGE_CASES.md`](Documentation/EDGE_CASES.md) | Edge cases considered with handling approach |
| [`Documentation/README.md`](Documentation/README.md) | Architecture details and full API reference |

## Stack

- Backend: Python, FastAPI, Gemini 2.5 Flash
- Frontend: Vanilla HTML/CSS/JS (single file, no build step)
- Deploy: Docker, Render, Railway
