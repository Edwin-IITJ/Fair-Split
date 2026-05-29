# Prompt Log — Fair Split

## Key Architectural Decision

**Q: Did you let the model do the arithmetic, or extract structured data and compute totals in code?**

**A: Extract structured data → compute in code.**

Reason: LLMs are unreliable at multi-step arithmetic, especially with proportional splits and rounding. A model that hallucinates a total does so confidently — there's no error signal. By forcing the model to only extract structured JSON (items, assignments, people, bill totals) and then computing everything deterministically in Python, I get:
1. Reproducible results (same input → same output, always)
2. Auditable arithmetic (I can verify every calculation)
3. Clear separation of concerns (LLM = OCR + NLP; Python = math)
4. The `flags[]` and `reconciliation` fields actually catch real errors instead of papering over them

---

## Prompt Iterations

**v1** — "Extract all items from this receipt and split them per the description. Return JSON."
→ Problem: Model returned inconsistent JSON shapes. Sometimes computed totals itself (wrong). No structure enforcement.

**v2** — Added explicit JSON schema in the prompt. Instructed model to return raw numbers only, no computed totals.
→ Problem: Model still tried to compute `total` for each person. Results were wrong 40% of the time on proportional tax splits.

**v3** — Explicitly said "Do NOT compute arithmetic yourself." Added instruction to return `assignments` array (item → who shared it). Removed all total/share fields from the expected JSON output.
→ Problem: Model would occasionally put `null` for `paid_by` even when payer was clearly named. Model also confused "I" with a literal name.

**v4** — Added explicit instruction: "If payer is not stated, set paid_by to null and add a flag." Added: "Resolve 'I'/'me' from context; if unresolvable, flag it." Added regex to strip markdown code fences from response.
→ Problem: On messy receipts, model would sometimes merge two line items into one (e.g., "Raita x2 ₹120" → extracted as single item "Raita" at ₹60).

**v5** — Added: "Extract each line item exactly as it appears. Do not merge or split quantities. If an item has Qty > 1, extract the total amount for that row, not per-unit price."
→ Problem: Ambiguous descriptions like "the rest of us" weren't being resolved — model left them as-is in `shared_by`.

**v6 (final)** — Added: "Resolve ambiguous groups like 'rest of us', 'everyone', 'all of us' to the explicit list of all named people minus any exceptions mentioned. State your interpretation in `flags_raw`."
→ Result: Stable across all 4 sample receipts. Passes reconciliation on R1–R4.

---

## Where the AI Was Wrong (3 Examples)

**Example 1 — Misread price**
Receipt: R1. Cappuccino shown as ₹180.
Model response: `{"name": "Cappuccino", "amount": 130}`
Caught by: Reconciliation check — extracted items summed to ₹990, printed subtotal was ₹1040. Flag shown: "₹50 unexplained."
Fixed by: Asking the model to re-read with higher temperature=0 (greedy decoding), also added instruction to read prices as the rightmost number on each line.

**Example 2 — Hallucinated item**
Receipt: R3 (Daily Grind). Description said "Pizza, pasta and garlic bread shared equally."
Model response: included `{"item": "Side Salad", "shared_by": ["Ishaan", "Meera", "Rohit"]}` in assignments.
No "Side Salad" exists on the bill.
Caught by: Backend's item-matching loop — `"Side Salad" not found in extracted items` → flag added.
Fixed by: Prompt now says "Only include items that appear verbatim on the bill in the assignments array."

**Example 3 — Botched proportional split**
Early version had the model compute `tax_share` per person itself.
On R4 (Spice Route with discount), model allocated tax before subtracting discount, giving each person a higher tax share than correct.
Correct: GST = 5% on (subtotal + service − discount). Tax base was ₹1368, model used ₹1520.
Caught by: Manual verification against R4 ground truth (grand total ₹1436 didn't match).
Fixed by: Removing all arithmetic from the model's responsibility. Python now computes every share.
