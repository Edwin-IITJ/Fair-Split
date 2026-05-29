# Fair Split — Restaurant Bill Splitter

A tool that takes a receipt image + plain-English description of who had what, and returns a fully-reconciled per-person split including tax, service charge, discounts, and a settle-up.

## Architecture

```
Frontend (fair-split.html)
    └── POST /split (JSON: receipt_base64 + description)
              ↓
        FastAPI Backend (main.py)
              ↓
        Gemini 2.0 Flash (Vision + NLP)
        → Extracts: items, assignments, people, bill totals
              ↓
        Python arithmetic engine
        → Computes: proportional tax/service/discount per person
        → Validates: reconciliation, flags mismatches
              ↓
        Returns exact output JSON schema
```

**Key decision:** The LLM only does structured data extraction (OCR + NLP). All arithmetic is Python.

## Local Setup

```bash
# 1. Clone / navigate to project directory
cd fair-split/project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Gemini API key
export GEMINI_API_KEY="your_key_here"

# 4. Start the server
uvicorn main:app --reload --port 8000

# 5. Open fair-split.html in your browser
# Set the endpoint to: http://localhost:8000/split
```

## Deploy to Render.com (Free)

1. Push this folder to a GitHub repo
2. Go to render.com → New Web Service → Connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `GEMINI_API_KEY = <your key>`
6. Deploy!
7. Update the endpoint in `fair-split.html` to your Render URL

## Deploy to Railway.app

```bash
railway login
railway init
railway add
railway up
railway variables set GEMINI_API_KEY=your_key
```

## API Contract

**POST /split**
```json
{
  "receipt_base64": "<base64 encoded image, no data-URI prefix>",
  "description": "<plain English who-had-what string>"
}
```

**Response:**
```json
{
  "per_person": [
    {"name": "Ravi", "items": ["Cappuccino", "Grilled Chicken Sandwich"], "subtotal": 440, "tax_share": 23, "service_share": 22, "discount_share": 0, "total": 485}
  ],
  "grand_total": 1147,
  "reconciliation": {"sum_of_person_totals": 1147, "matches_bill": true},
  "paid_by": "Sameer",
  "settle_up": [{"from": "Ravi", "to": "Sameer", "amount": 485}],
  "assumptions": ["Sameer absorbs ₹1 rounding difference"],
  "flags": []
}
```

## Sample Receipts

See R1–R4 in the assignment PDF. All four receipts pass reconciliation.

## Deliverables

1. ✅ `fair-split.html` — Frontend (upload image, paste description, see result)
2. ✅ `main.py` — FastAPI backend with Gemini Vision integration
3. ✅ `PROMPT_LOG.md` — Prompt iteration log + arithmetic decision
4. ✅ `EDGE_CASES.md` — 15 edge cases considered with verification status
