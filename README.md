# Fair Split — Precision Bill Splitting

A tool that takes a photo of a restaurant bill and a plain-English description of who had what, and returns a fair, fully-reconciled per-person split — including tax, service charge, discounts, and a final settle-up.

## Live demo

> Deploy to Render or Railway (see below) and paste your deployed URL into the endpoint field in `fair-split.html`.

## How it works

```
fair-split.html  (frontend)
      │
      └──▶  POST /split  (FastAPI backend)
                  │
                  └──▶  Gemini 2.5 Flash  (Vision + NLP)
                              │  extracts: items, assignments, people, bill totals
                              ▼
                        Python arithmetic engine
                              │  computes: proportional tax / service / discount
                              │  validates: reconciliation, flags mismatches
                              ▼
                        JSON response  →  interactive UI
```

**Key design decision:** The LLM only does structured data extraction (OCR + NLP). All arithmetic is deterministic Python. This prevents hallucinated totals and makes every split auditable.

## Features

- 📸 **Receipt OCR** — upload any JPEG/PNG receipt photo
- 📝 **Plain-English description** — describe who had what in natural language
- ✏️ **Editable breakdown** — correct any AI misassignment via per-item dropdowns
- 🔄 **Live reconciliation** — unassigned amounts update instantly as you edit
- ⚠️ **Flags & assumptions** — AI uncertainties surfaced explicitly, never silently guessed
- 📋 **Copy summary** — one-click plain-text output for group chats
- 🌙 **Light / dark mode**

## Request contract

`POST /split` — `Content-Type: application/json`

```json
{
  "receipt_base64": "<base64-encoded image bytes, no data-URI prefix>",
  "description": "<plain-English who-had-what string>"
}
```

## Response shape

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
  "assumptions": ["'rest of us' interpreted as Ravi, Neha, Sameer"],
  "flags": []
}
```

## Fairness rules

1. Each person pays for the items they consumed.
2. Shared items split **equally** among the people who shared that specific item.
3. Tax + service charge allocated **proportional** to each person's pre-tax food subtotal.
4. A bill-level discount allocated **proportional** to subtotal.
5. Round to the rupee; state in `assumptions` who absorbs the leftover paise.

## Local setup

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd fair-split

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env.local

# 4. Start the server
uvicorn main:app --reload --port 8000

# 5. Open fair-split.html in your browser
#    The endpoint field defaults to http://localhost:8000/split
```

## Deploy to Render (free tier)

1. Push this repo to GitHub
2. [render.com](https://render.com) → **New Web Service** → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment variable: `GEMINI_API_KEY = <your key>`
6. Deploy → update the endpoint field in `fair-split.html` to your Render URL

## Deploy to Railway

```bash
railway login
railway init
railway up
railway variables set GEMINI_API_KEY=your_key
```

## Documentation

| File | Contents |
|---|---|
| [`Documentation/PROMPT_LOG.md`](Documentation/PROMPT_LOG.md) | Prompt iteration log (v1–v6) + arithmetic decision rationale |
| [`Documentation/EDGE_CASES.md`](Documentation/EDGE_CASES.md) | 16 edge cases considered, with handling and verification status |
| [`Documentation/README.md`](Documentation/README.md) | Architecture diagram and API reference |

## Stack

- **Backend:** Python · FastAPI · Gemini 2.5 Flash (Vision)
- **Frontend:** Vanilla HTML / CSS / JS (single file, no build step)
- **Deploy:** Docker · Render · Railway
