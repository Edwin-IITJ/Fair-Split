# Prompt Log: Fair Split

## Key Design Decision

**Did you let the model do the arithmetic, or extract structured data and compute the totals in code?**

Extract structured data, then compute in code.

Reasons:
1. LLMs are unreliable at multi-step arithmetic, especially with proportional splits and rounding. A model that hallucinates a total does so confidently with no error signal.
2. By forcing the model to extract structured JSON only (items, assignments, people, bill totals), all arithmetic is deterministic Python.
3. Same input always produces the same output.
4. The `flags[]` and `reconciliation` fields catch real errors instead of papering over them.

---

## Prompt Iterations

**v1**: "Extract all items from this receipt and split them per the description. Return JSON."

Problem: Model returned inconsistent JSON shapes. Sometimes computed totals itself (wrong). No structure enforcement.

**v2**: Added explicit JSON schema. Instructed model to return raw numbers only, not computed totals.

Problem: Model still tried to compute `total` for each person. Results were wrong roughly 40% of the time on proportional tax splits.

**v3**: Explicitly added "Do NOT compute arithmetic yourself." Added `assignments` array (item to shared_by list). Removed all total/share fields from the expected output.

Problem: Model would occasionally set `paid_by` to null even when the payer was clearly named. Model also treated "I" as a literal name.

**v4**: Added: "If payer is not stated, set paid_by to null and add a flag." Added: "Resolve 'I'/'me' from context; if unresolvable, flag it." Added regex on the backend to strip markdown code fences from the response.

Problem: On messy receipts, model would sometimes merge two line items into one (e.g. "Raita x2 Rs.120" extracted as a single item "Raita" at Rs.60 instead of Rs.120).

**v5**: Added: "Extract each line item exactly as it appears. Do not merge or split quantities. If an item has Qty > 1, extract the total amount for that row, not the per-unit price."

Problem: Ambiguous descriptions like "the rest of us" were left as-is in `shared_by` rather than being resolved.

**v6 (current)**: Added: "Resolve ambiguous groups like 'rest of us', 'everyone', 'all of us' to the explicit list of all named people minus any exceptions mentioned. State your interpretation in `flags_raw`."

Result: Stable across all four sample receipts. Passes reconciliation on R1-R4.

---

## Where the AI Was Wrong (Three Examples)

**Example 1: Misread price**

Receipt: R1. Cappuccino shown as Rs.180.
Model extracted: `{"name": "Cappuccino", "amount": 130}`
Caught by: Reconciliation check. Extracted items summed to Rs.990, printed subtotal was Rs.1040. Flag: "Rs.50 unexplained."
Fixed by: Set temperature=0 (greedy decoding). Also added instruction to read prices as the rightmost number on each row.

**Example 2: Hallucinated item**

Receipt: R3 (Daily Grind). Description: "Pizza, pasta and garlic bread shared equally."
Model included `{"item": "Side Salad", "shared_by": ["Ishaan", "Meera", "Rohit"]}` in assignments.
No "Side Salad" on the bill.
Caught by: Backend item-matching loop. "Side Salad not found in extracted items" flag added.
Fixed by: Prompt now says "Only include items that appear verbatim on the bill in the assignments array."

**Example 3: Botched proportional split**

Early version had the model compute `tax_share` per person.
On R4 (Spice Route with discount), model allocated tax before subtracting the discount, giving inflated tax shares.
Correct: GST base = subtotal + service - discount = Rs.1368. Model used Rs.1520.
Caught by: Manual verification against R4 ground truth (grand total Rs.1436 did not match).
Fixed by: Removed all arithmetic from the model's responsibility. Python now computes every share.
