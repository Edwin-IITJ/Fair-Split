# Edge Cases: Fair Split

## Methodology
All computation is done in Python (backend), not by the LLM. The LLM's sole job is structured data extraction from the image + description. Arithmetic is 100% deterministic Python code. This prevents hallucinated totals and floating-point surprises.

---

## Edge Cases Considered

### 1. No Payer Named in Description
- **Input:** Description ends without "X paid" or "X footed the bill"
- **Handling:** `paid_by` is set to `null`; a flag is added: "Payer not identified in description — settle-up cannot be computed". The per-person breakdown is still computed and returned.
- **Verified:** ✅ Tested by omitting payer in description. Settle-up array returns empty, flag appears.

---

### 2. Ambiguous Groups ("the rest of us", "everyone else", "all of us")
- **Input:** "Priya and I shared the pasta. Everyone else had the naan."
- **Handling:** The LLM is instructed to resolve these groups using all names mentioned in the description and add a flag: "'everyone else' interpreted as [Karan, Sara]". The assumption is recorded in `assumptions[]`.
- **Verified:** ✅ Tested with R2's description — "Everything else was common to all four."

---

### 3. Item in Description Not on Bill
- **Input:** Description says "Karan had the dessert platter" but no dessert platter appears on the receipt.
- **Handling:** Flag added: "Item 'dessert platter' in description not found on bill". The item is skipped in the split; other items are split normally.
- **Verified:** ✅ Tested by injecting a fake item name into the description.

---

### 4. Printed Total Doesn't Match Line Item Sum
- **Input:** Receipt shows subtotal ₹1000, but extracted line items sum to ₹980.
- **Handling:** Backend checks `sum(items) vs bill.subtotal`. If difference > ₹1, flag is added: "Extracted line items sum to ₹980 but printed subtotal is ₹1000 — ₹20 unexplained." The printed subtotal is used as the authority for proportional calculations.
- **Verified:** ✅ Tested against bills where OCR misreads a digit.

---

### 5. Bill with No Service Charge
- **Input:** Service charge field is 0 or absent.
- **Handling:** `service_share` for all persons is 0. No flag. Proportional allocation still works — multiplying by 0 = 0.
- **Verified:** ✅ All four sample bills have service charges, tested with a custom receipt with 0 service.

---

### 6. Bill with a Discount Coupon
- **Input:** R4 — "WELCOME15" 15% off discount.
- **Handling:** Discount is extracted as a positive number (228). Backend distributes it proportionally as a negative `discount_share` per person (subtracted from their total). Formula: `discount_share = -discount × (person_subtotal / total_subtotal)`.
- **Verified:** ✅ R4 tested end-to-end.

---

### 7. Multiple People Owing One Payer
- **Input:** 4 people, only 1 paid. R2, R3, R4 all test this.
- **Handling:** `settle_up` array generates one entry per non-payer person, each pointing `from: person → to: payer`.
- **Verified:** ✅ All multi-person receipts tested.

---

### 8. Quantities That Don't Divide Evenly (Rounding)
- **Input:** ₹100 split 3 ways = ₹33.33 each.
- **Handling:** Each person's raw `total` is computed in float, then `round()` to the rupee. Rounding diff is checked: `sum_of_rounded_totals - grand_total`. The person with the largest fractional part absorbs any leftover paise. This is stated in `assumptions[]`.
- **Verified:** ✅ Tested with 3-way split of amounts not divisible by 3 (R1, R3).

---

### 9. Shared Items Across Only a Subset of People
- **Input:** R2 — "Gulab Jamun was shared just by Priya and Karan."
- **Handling:** Assignment `shared_by: ["Priya", "Karan"]` is extracted. Split is `₹120 / 2 = ₹60` each. Aman and Sara pay ₹0 for Gulab Jamun.
- **Verified:** ✅ R2 tested.

---

### 10. Tips or Charges Not Covered by Fairness Rules
- **Input:** A "gratuity" line item or "packaging charge" not covered by tax/service rules.
- **Handling:** These are treated as line items and assigned to whoever the description says. If the description doesn't mention them, the LLM flags it and they go into a "common" pool split equally. Flag added: "Item 'Gratuity' not mentioned in description — split equally."
- **Verified:** ⚠ Partially tested. Relied on LLM to catch. Chose to flag rather than silently assume.

---

### 11. Person Named in Description Not Matched to Any Item
- **Input:** "Four of us: Aman, Priya, Karan, Sara." but the description never mentions what Sara had.
- **Handling:** Sara ends up with `subtotal: 0, total: 0` if no items are assigned to her. This is likely an incomplete description. Flag added: "Person 'Sara' has no items assigned."
- **Verified:** ✅ Edge case tested manually.

---

### 12. "I" or "Me" as a Name
- **Input:** "Priya and I shared the pasta." — "I" is not a name.
- **Handling:** LLM is instructed to resolve "I" / "me" from context (if earlier in the description the narrator named themselves) or add a flag: "'I'/'me' in description could not be resolved to a name."
- **Verified:** ⚠ Works when narrator is named earlier. Fails if narrator is never named. Flag is shown.

---

### 13. Image is Blurry / Unreadable
- **Input:** Low-quality receipt photo where prices are illegible.
- **Handling:** The LLM will either hallucinate prices (bad) or return partial data with a flag. Backend cross-checks: if extracted line items sum diverges >10% from printed total, a strong warning flag is added. Ultimately, garbage-in → garbage-out; flagged in the result.
- **Verified:** ⚠ Tested with a blurred JPEG. LLM sometimes hallucinates. Flag + reconciliation check catches it.

---

### 14. Only One Person (Edge: Trivial Split)
- **Input:** "Just me. I paid."
- **Handling:** One person gets 100% of the bill. Settle-up array is empty (no one owes anyone). No flags.
- **Verified:** ✅ Tested.

---

### 15. Receipt in a Different Language / Currency
- **Input:** Hindi/Tamil receipt or USD receipt.
- **Handling:** Gemini can read multiple languages. Currency symbols are preserved as-is from the bill. No currency conversion is performed. Flag added if currency symbol is not ₹: "Bill appears to use non-INR currency — verify amounts."
- **Verified:** ⚠ Not fully tested. Flagging behavior tested with a USD mock.

---

### 16. Duplicate Item Names on the Same Bill
- **Input:** A bill where the same item appears on two separate rows (e.g. "Naan ×2 ₹120" and "Naan ×3 ₹180" as separate line items, or a reprinted correction row).
- **Handling:** The LLM extracts both rows as separate entries. The backend accumulates their amounts under the same key (`items[name] += amount`) rather than overwriting, so the combined total is used for proportional allocation. If the description assigns the item to different people on each row, both assignments are still processed correctly because the accumulated total is the source of truth.
- **Verified:** ✅ Fixed after identifying that the original dict comprehension silently dropped the first of any two items with matching names.

---
## What I Chose NOT to Handle

| Case | Reason |
|---|---|
| Multi-bill splitting (multiple receipts) | Out of scope per ground rules: "One bill in, one split out." |
| Historical receipts / persistence | Ground rules explicitly forbid auth/history/persistence |
| Tax regimes other than GST (CGST+SGST) | Out of scope — bill convention given in assignment |
| Splitting by percentage ("Aman pays 40%") | Non-standard. Flagged rather than supported. |
