import os, base64, json, re, math
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env.local")
except ImportError:
    pass  # python-dotenv not installed; rely on environment variables
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI(title="Fair Split API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

class SplitRequest(BaseModel):
    receipt_base64: str
    description: str

SYSTEM_PROMPT = """You are a restaurant bill splitting assistant. You will receive:
1. A receipt image (base64 encoded)
2. A plain-English description of who had what and who paid

Your job is to extract all line items from the receipt and compute a fair per-person split.

FAIRNESS RULES (apply exactly):
1. Each person pays for the items they consumed.
2. Shared items split equally among the people who shared that specific item.
3. Tax + service charge allocated proportional to each person's pre-tax food subtotal.
4. A bill-level discount allocated proportional to subtotal (reduce each person's subtotal proportionally).
5. Round to the rupee; note in assumptions who absorbs the leftover paise.

IMPORTANT: Do NOT compute arithmetic yourself. Extract the structured data and return it so code can compute. Return a JSON object with this EXACT structure:

{
  "bill": {
    "items": [
      {"name": "Item Name", "amount": 100}
    ],
    "subtotal": 1000,
    "service_charge": 50,
    "tax": 55,
    "discount": 0,
    "grand_total": 1105,
    "round_off": 0
  },
  "people": ["Name1", "Name2"],
  "paid_by": "Name1",
  "assignments": [
    {"item": "Item Name", "shared_by": ["Name1", "Name2"]}
  ],
  "flags_raw": ["any issues noticed like unmatched items, payer not mentioned, etc."]
}

If payer is not mentioned in the description, set paid_by to null and add a flag.
If an item mentioned in description is not on the bill, add a flag.
If description mentions ambiguous groups like "rest of us" or "everyone else", resolve them and note in flags_raw what assumption you made.
If the bill items don't sum to the printed subtotal, add a flag.

Return ONLY valid JSON. No markdown, no explanation."""

def compute_split(data: dict) -> dict:
    bill = data["bill"]
    people = data["people"]
    paid_by = data.get("paid_by")
    assignments = data["assignments"]
    flags = list(data.get("flags_raw", []))
    assumptions = []

    items = {}
    for _item in bill["items"]:
        _name = _item["name"]
        items[_name] = items.get(_name, 0) + _item["amount"]
    subtotal = bill.get("subtotal", sum(items.values()))
    service = bill.get("service_charge", 0)
    tax = bill.get("tax", 0)
    discount = bill.get("discount", 0)
    grand_total = bill.get("grand_total", subtotal + service + tax - discount)
    round_off = bill.get("round_off", 0)

    # Validate items sum
    extracted_sum = sum(items.values())
    if abs(extracted_sum - subtotal) > 1:
        flags.append(f"Extracted line items sum to ₹{extracted_sum} but printed subtotal is ₹{subtotal} — ₹{abs(extracted_sum - subtotal):.0f} unexplained")

    # Build per-person subtotals
    person_subtotals = {p: 0.0 for p in people}
    person_items = {p: [] for p in people}

    for assignment in assignments:
        item_name = assignment["item"]
        sharers = assignment["shared_by"]
        if item_name not in items:
            flags.append(f"Item '{item_name}' in description not found on bill")
            continue
        amount = items[item_name]
        share = amount / len(sharers)
        for person in sharers:
            if person not in person_subtotals:
                # Unknown person
                flags.append(f"Person '{person}' in assignment not in people list")
                person_subtotals[person] = 0.0
                person_items[person] = []
            label = item_name if len(sharers) == 1 else f"{item_name} (1/{len(sharers)})"
            person_subtotals[person] += share
            person_items[person].append(label)

    total_subtotal = sum(person_subtotals.values())

    # Compute proportional tax/service/discount
    person_totals = {}
    for person in person_subtotals:
        ratio = person_subtotals[person] / total_subtotal if total_subtotal > 0 else 0
        tax_share = tax * ratio
        service_share = service * ratio
        discount_share = -discount * ratio
        raw_total = person_subtotals[person] + tax_share + service_share + discount_share
        person_totals[person] = {
            "name": person,
            "items": person_items[person],
            "subtotal": round(person_subtotals[person]),
            "tax_share": round(tax_share),
            "service_share": round(service_share),
            "discount_share": round(discount_share),
            "_raw_total": raw_total,
            "total": round(raw_total)
        }

    # Handle rounding: sum of rounded totals may differ from grand_total
    sum_totals = sum(v["total"] for v in person_totals.values())
    diff = round(grand_total) - sum_totals
    if diff != 0:
        # The person with the largest raw fractional part absorbs the difference
        absorber = max(person_totals, key=lambda p: abs(person_totals[p]["_raw_total"] - person_totals[p]["total"]))
        person_totals[absorber]["total"] += diff
        assumptions.append(f"{absorber} absorbs ₹{diff} rounding difference")

    # Remove internal key
    for p in person_totals:
        del person_totals[p]["_raw_total"]

    per_person = list(person_totals.values())
    sum_of_totals = sum(v["total"] for v in per_person)
    matches = abs(sum_of_totals - round(grand_total)) <= 1

    # Settle up
    settle_up = []
    if paid_by:
        for p in per_person:
            if p["name"] != paid_by and p["total"] > 0:
                settle_up.append({"from": p["name"], "to": paid_by, "amount": p["total"]})
    else:
        flags.append("Payer not identified in description — settle-up cannot be computed")

    return {
        "per_person": per_person,
        "grand_total": round(grand_total),
        "reconciliation": {
            "sum_of_person_totals": sum_of_totals,
            "matches_bill": matches
        },
        "paid_by": paid_by,
        "settle_up": settle_up,
        "assumptions": assumptions,
        "flags": flags,
        # Supplementary fields for the UI's client-side re-computation engine.
        # Not part of the required contract; purely additive.
        "_items": [{"name": k, "amount": v} for k, v in items.items()],
        "_assignments": [
            {"item": a["item"], "shared_by": list(a.get("shared_by", []))}
            for a in assignments
        ],
        "_people": list(people),
    }

@app.post("/split")
async def split_bill(req: SplitRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        image_bytes = base64.b64decode(req.receipt_base64)

        # Detect image type
        if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = "image/png"
        elif image_bytes[:2] == b'\xff\xd8':
            mime_type = "image/jpeg"
        else:
            mime_type = "image/jpeg"

        image_part = {
            "inline_data": {
                "mime_type": mime_type,
                "data": req.receipt_base64
            }
        }

        prompt = f"{SYSTEM_PROMPT}\n\nDescription: {req.description}"
        response = model.generate_content([prompt, image_part])
        raw = response.text.strip()

        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        raw = raw.strip()

        structured = json.loads(raw)
        result = compute_split(structured)
        return result

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
