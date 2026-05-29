# Edge Cases: Fair Split

## Methodology

All arithmetic is computed in Python (`compute_split` in `main.py`), not by the LLM. The LLM extracts structured JSON from the image and description. This means edge cases fall into two categories:

- **Backend-handled:** detected and flagged by `compute_split`, independent of LLM behaviour
- **LLM-handled:** addressed by instructions in the system prompt; backend passes `flags_raw` through to `flags[]`

---

## Edge Cases Considered

### 1. No Payer Named in Description

- **Input:** Description ends without naming who paid.
- **Handling (backend):** `paid_by` is set to null. Flag added: "Payer not identified in description; settle-up cannot be computed". The per-person breakdown is still computed and returned; `settle_up` is an empty array.

---

### 2. Ambiguous Groups ("the rest of us", "everyone else", "all of us")

- **Input:** "Priya and I shared the pasta. Everyone else had the naan."
- **Handling (LLM prompt):** The system prompt instructs the model to resolve these groups using all named people in the description and to record the assumption in `flags_raw`. The backend passes `flags_raw` through to `flags[]`.

---

### 3. Item in Description Not on Bill

- **Input:** Description says "Karan had the dessert platter" but no such item appears on the receipt.
- **Handling (backend):** Each assignment's item name is checked against the extracted items dict. Flag added: "Item 'dessert platter' in description not found on bill". That assignment is skipped; all other items are split normally.

---

### 4. Printed Total Does Not Match Line Item Sum

- **Input:** Receipt shows subtotal 1000 but extracted line items sum to 980.
- **Handling (backend):** `sum(extracted items)` is compared to `bill.subtotal`. If the difference exceeds 1 rupee, a flag is added: "Extracted line items sum to Rs.980 but printed subtotal is Rs.1000, leaving Rs.20 unexplained." The printed subtotal is used as the authority for proportional calculations.

---

### 5. Bill with No Service Charge

- **Input:** Service charge is 0 or absent from the bill.
- **Handling (backend):** `service_charge` defaults to 0. `service_share` for all persons is 0. No flag.

---

### 6. Bill-Level Discount

- **Input:** A percentage coupon applied at the bill level.
- **Handling (backend):** Discount extracted as a positive number. Distributed as a negative `discount_share` per person, proportional to food subtotal: `discount_share = -discount * (person_subtotal / total_subtotal)`.

---

### 7. Multiple People Owing One Payer

- **Input:** Four people; one paid.
- **Handling (backend):** `settle_up` generates one entry per non-payer: `{"from": person, "to": payer, "amount": person_total}`.

---

### 8. Amounts That Do Not Divide Evenly

- **Input:** 100 rupees split three ways.
- **Handling (backend):** Each person's total is computed as a float, then rounded. The difference between the rounded sum and `grand_total` is absorbed by the person with the largest fractional remainder. The absorber is noted in `assumptions[]`.

---

### 9. Shared Items Across a Subset of People

- **Input:** "Gulab Jamun shared just by Priya and Karan."
- **Handling (backend):** Assignment `shared_by: ["Priya", "Karan"]`. Amount divided by 2. Other people pay nothing for that item.

---

### 10. Tips or Charges Not Mentioned in Description

- **Input:** A "Packaging Charge" appears on the bill; the description does not mention it.
- **Handling:** If the LLM does not include the item in any assignment, it is not allocated to any person. No automatic "common pool" splitting occurs in the backend. The item appears as unassigned in the UI's editable breakdown table. The LLM may add a note in `flags_raw` depending on context.

---

### 11. Person Named in Description But No Items Assigned

- **Input:** "Four of us: Aman, Priya, Karan, Sara." Sara is never mentioned for any item.
- **Handling:** Sara appears in `per_person` with `subtotal: 0` and `total: 0`. No explicit flag is raised for this. The breakdown is visible in the result. This typically indicates an incomplete description.

---

### 12. "I" or "Me" as a Name

- **Input:** "Priya and I shared the pasta." The pronoun "I" is not a resolvable name.
- **Handling (LLM prompt):** The model is instructed to resolve "I"/"me" from context if the narrator named themselves earlier in the description, or to add a flag in `flags_raw` if unresolvable. The backend has no name-resolution logic.

---

### 13. Blurry or Low-Quality Image

- **Input:** Prices illegible due to image quality.
- **Handling:** The LLM may extract incorrect prices. The backend's reconciliation check flags this if the extracted line items diverge from the printed subtotal by more than 1 rupee. Beyond that, incorrect extraction produces incorrect output; the reconciliation flag is the primary automated catch.

---

### 14. Only One Person

- **Input:** "Just me. I paid."
- **Handling (backend):** One person receives 100% of all items. The `settle_up` array is empty because there is no other person to settle with.

---

### 15. Receipt in a Different Language or Currency

- **Input:** A bill printed in Hindi, Tamil, or USD.
- **Handling:** Gemini can read multilingual receipts. Currency symbols are preserved as extracted. The backend performs no currency detection or conversion. Whether a foreign-currency flag is raised depends entirely on the LLM's output for that bill.

---

### 16. Duplicate Item Names on the Same Bill

- **Input:** Two separate rows both named "Naan" at different prices.
- **Handling (backend):** Amounts for matching item names are accumulated: `items[name] += amount`. The combined total is used for all downstream calculations. The original implementation used a dict comprehension that silently overwrote the first entry with the second; this was corrected.

---

## What Was Not Handled

| Case | Reason |
|---|---|
| Multi-bill splitting | Out of scope: one bill in, one split out. |
| History or persistence | Ground rules explicitly exclude auth/history/persistence. |
| Tax regimes other than GST | Out of scope for this assignment. |
| Splitting by percentage ("Aman pays 40%") | Non-standard. Flagged rather than supported. |
