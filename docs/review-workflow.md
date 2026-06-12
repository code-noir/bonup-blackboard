# Contract Review Workflow

## Purpose

The contract review workflow lets a user provide contract text or a PDF, receive AI analysis, optionally generate a counter-contract, and save the result locally in the frontend.

Primary implementation files:

- `backend/api/ai/views.py`
- `frontend/src/pages/ContractReview.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/App.tsx`

## Route Wiring

Frontend:

- `/review` renders `ContractReview`.
- `/analysis` redirects to `/review`.
- `/counter` redirects to `/review`.

Backend:

- `POST /api/ai/analyze-contract/`
- `POST /api/ai/counter-contract/`

## Upload / Input

The backend accepts:

- `contract_text` in JSON/form data.
- multipart `file`.
- `upload_id` referencing an existing upload owned by the user.

For PDFs, `_extract_pdf_text()` uses `pdfplumber`.

## Analysis Flow

```text
User enters text or selects PDF
  -> frontend calls /api/ai/analyze-contract/
  -> backend builds user message
  -> backend creates AIConversation
  -> backend calls Anthropic with ANALYZE_CONTRACT_PROMPT
  -> backend parses JSON block
  -> frontend receives:
      conversation_id
      summary
      key_terms
      red_flags
      questions
```

## Review UI

`ContractReview.tsx` provides two modes:

- `analysis_only`
- `analysis_plus_counter`

Analysis results are rendered as:

- Analysis Summary
- Key Terms
- Red Flags
- Questions

## Optional Counter Flow

If the user selects `analysis_plus_counter`, the UI requires:

- an analysis result
- counter terms/instructions
- generated counter result before saving

Counter output includes:

- summary
- concerning clauses
- negotiation strategy
- revised contract
- important question/answer items

## Saved Reviews

Saved reviews are stored in `localStorage` under:

- `bb_contract_reviews`
- legacy import from `bb_counter_drafts`

They are not saved to the backend as first-class records.

The dashboard also reads saved reviews from localStorage and displays them under "Saved Contract Reviews".

## AI Behavior

The analysis prompt asks for structured JSON with:

- `summary`
- `key_terms`
- `red_flags`
- `questions`

The backend extracts the first valid JSON object from a fenced block or raw response.

## Outputs

Current output is useful but transient:

- AI conversation is persisted server-side.
- Parsed review/counter result is returned to frontend.
- Saved review drafts are browser-local.
- No backend `ContractReview` model was found.
- No contract, version, clause, or obligation is automatically created by the review page.

## Current Gaps

- Review saving is not backend-persistent.
- The dashboard review list is local to the browser.
- There is no review status lifecycle.
- There is no operator-visible server-side review queue from this workflow.
- Analysis and counter are separate backend endpoints but presented as one frontend workflow.
- The frontend copy says the next backend phase will add billing gate behavior for unsubscribed users.

