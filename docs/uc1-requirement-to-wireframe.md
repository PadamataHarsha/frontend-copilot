# UC1: Requirement to Wireframe Generator

## 1. Overview

UC1 converts a textual frontend requirement into a validated, low-fidelity screen wireframe. The backend uses a prompt and Groq-hosted model to produce structured JSON, normalizes the model result, validates it with Pydantic, and returns it to the React frontend for rendering.

- UC1 generates **one requested screen**.
- It does not generate final production UI code.
- Retrieval-augmented generation (RAG) and agents are outside UC1 V1.

## 2. Real-world problem

Business requirements and initial wireframes are often separated by interpretation, repeated meetings, and manual redraws. A stakeholder may describe a workflow only in prose, while a UX or frontend team must infer screen scope, information hierarchy, fields, actions, validation, history, review, and result states. This can introduce delays and ambiguous interpretations before implementation begins.

UC1 reduces that translation gap by producing a machine-readable draft of the requested screen for rapid human review.

## 3. Manual process today

Requirement gathering
→ business analysis
→ UX interpretation
→ wireframe creation
→ stakeholder review
→ revisions

## 4. AI-assisted process

Requirement
→ React frontend
→ Vite proxy
→ FastAPI endpoint
→ prompt
→ Groq model
→ JSON parsing
→ normalization
→ Pydantic validation
→ wireframe renderer

The UI submits the requirement to `/api/wireframe/generate` in development, and Vite rewrites that path to `/wireframe/generate` on FastAPI. The API response is checked again in the browser before rendering.

## 5. Actors and human review

| Actor | Responsibility |
|---|---|
| Product owner | Defines the desired outcome and reviews scope and business meaning. |
| Business analyst | Clarifies requirements, coverage, rules, validation, and exceptions. |
| UX designer | Reviews hierarchy, grouping, interactions, accessibility, and usability. |
| Frontend engineer | Uses the approved structure to plan implementation and production components. |
| Reviewer | Confirms that the result is faithful to the requirement and contains no unsupported scope. |

AI output is a starting point, not an approved design or implementation specification. It requires human review before implementation.

## 6. AI input

### Request contract

```http
POST /wireframe/generate
```

```json
{
  "requirement": "string"
}
```

The backend Pydantic request model is `WireframeRequest(requirement: str)`. It requires a `requirement` field and a string value. The actual backend request schema does not declare an explicit minimum length or maximum character count.

The frontend additionally trims submitted text, rejects an empty or whitespace-only requirement, and limits the textarea to 2,000 characters with `maxLength={2000}`. Missing fields, wrong value types, or malformed requests are handled by FastAPI/Pydantic as validation errors, normally with HTTP 422.

## 7. Prompt design

The system prompt defines UC1 as a frontend UX architecture task that produces one low-fidelity screen:

- Generate only the requested screen, not an entire application.
- Do not add Home or Dashboard unless explicitly requested.
- Add Header, Navigation, Sidebar, Breadcrumb, Footer, or Menu only when explicitly required for an application shell, portal-wide navigation, or movement between multiple screens.
- Do not add analytics, reports, exports, chat, admin, authentication, notifications, or settings unless requested.
- Every explicitly requested capability must appear in at least one section.
- Do not omit requested actions, validation, history, review, approval, rejection, cancellation, status, or result behavior.
- Include only requested or necessary UI.
- Avoid duplicate or overlapping sections.
- Prefer 3 to 6 meaningful sections, with up to 8 when necessary for complete coverage.
- Group related fields into logical sections.
- Use `Form` once per logical form, not once per field.
- Split sections only for distinct purposes such as details, review, actions, history, validation, or result.
- Use `Stepper` only for explicitly sequential workflows.
- Put business meaning in section titles and not in component names.
- Verify explicit requirement coverage before responding.
- Return JSON only, without prose, markdown, or extra keys.

The canonical prompt also requests a JSON object with `screen_name` and `sections`; no secrets or API keys are included in prompts or user-facing output.

## 8. Structured output schema

```json
{
  "screen_name": "string",
  "sections": [
    {
      "title": "string",
      "components": ["string"]
    }
  ]
}
```

Validation rules include:

- `screen_name` must be a non-empty string.
- `sections` must contain from 1 to 8 items.
- Each section `title` must be a non-empty string.
- Each section `components` list must contain from 1 to 10 items.
- Component values must be strings; whitespace-only components are removed during normalization.
- Exact duplicate section titles and component lists are removed.
- Meaningful repeated components are preserved, even when the same canonical name appears more than once.

The Pydantic schemas validate the normalized payload before it reaches the router response.

## 9. Canonical component vocabulary

The prompt permits only these canonical component names:

- Header
- Navigation
- Sidebar
- Breadcrumb
- Card
- SummaryCard
- Form
- TextInput
- NumberInput
- TextArea
- DatePicker
- Select
- SearchInput
- Checkbox
- RadioGroup
- Button
- Table
- List
- Tabs
- Stepper
- Alert
- Modal
- Pagination
- StatusBadge
- Timeline

Unknown non-empty component strings are not removed by normalization in every case, but the system prompt directs the model to use this vocabulary and Pydantic currently validates component values as strings rather than enum values.

## 10. Backend architecture

| File | Responsibility |
|---|---|
| `backend/app/main.py` | Creates the FastAPI application, enables CORS, registers the wireframe router, and exposes a health endpoint. |
| `backend/app/routers/wireframe_router.py` | Exposes `POST /wireframe/generate` and passes the validated request requirement to the service. |
| `backend/app/services/wireframe_service.py` | Coordinates provider calls, bounded retries and repair, JSON parsing, normalization, Pydantic validation, call-budget enforcement, logging, and safe HTTP error mapping. |
| `backend/app/clients/llm_client.py` | Builds the OpenAI-compatible Groq client, sends chat-completion requests with JSON-object response mode, and maps provider exceptions to typed failures. |
| `backend/app/core/config.py` | Loads private environment configuration and creates the validated LLM configuration used at runtime. |
| `backend/app/prompts/wireframe_prompt.py` | Supplies the one-screen, canonical-component system prompt. |
| Pydantic schemas | `WireframeRequest` validates request input; `WireframeResponse` and `Section` validate the returned wireframe structure. |

## 11. Frontend architecture

| Element | Responsibility |
|---|---|
| `RequirementForm` | Collects and clears the requirement, provides quick starts, shows the 2,000-character limit, submits the form, and exposes loading state. |
| `WireframeGenerator` | Coordinates page state for requirement, result, loading, and errors. |
| `WireframeRenderer` | Renders the browser-like wireframe canvas and the expandable JSON preview. |
| `WireframeSection` | Renders a titled section and its ordered component placeholders. |
| `ComponentPlaceholder` | Presents one canonical component name as a visual low-fidelity placeholder. |
| `JsonPreview` | Shows formatted structured response JSON and provides copy behavior. |
| `LoadingState` | Displays generation progress. |
| `ErrorState` | Displays a safe, user-facing generation error. |
| `EmptyState` | Displays the initial canvas state before generation. |
| API client | Uses Axios with the configured base URL and a 70-second request timeout. |
| Runtime response validation | Checks the returned object, `screen_name`, and `sections` before the UI accepts it for rendering. |

The development Vite proxy maps `/api` to `http://127.0.0.1:8000` and rewrites `/api` from the request path.

## 12. Model and provider

- Provider: **Groq**
- Selected model: **`qwen/qwen3.8-27b`**
- API protocol: OpenAI-compatible chat completions
- Default temperature: `0.1`

The model was selected for better controlled reliability on this UC1 prompt, provider-format requirements, and evaluation schema. It achieved 10/10 in the controlled model reliability test. The earlier `openai/gpt-oss-20b` model was less reliable for this task.

This comparison is limited to UC1's prompt, schema, and evaluation cases. It does not claim that `qwen/qwen3.8-27b` is universally better than every alternative model.

## 13. Reliability controls

- The provider call budget is limited to **two complete() calls**.
- One bounded retry is available for eligible temporary or generation failures.
- One repair opportunity is available for empty, malformed, or schema-invalid output.
- Retry and repair share the same two-call budget. They are not separate budgets.
- Provider and output failures are classified into typed categories before HTTP mapping.
- Retry delays are bounded; `Retry-After` values are applied only within the implementation's allowed delay range.
- There is no mock or fabricated fallback wireframe.
- Provider implementation details and raw provider error messages are not exposed directly to users.

## 14. Output normalization

The service normalizes model output before Pydantic validation:

- Trims leading and trailing whitespace from the screen name and section titles.
- Trims component strings.
- Removes blank component strings.
- Normalizes recognized aliases case-insensitively.
- Rejects sections or payloads that exceed the 8-section and 10-component limits.
- Removes exact duplicate sections based on the normalized title and component list.
- Preserves repeated meaningful components rather than globally deduplicating them.

Known alias examples include:

| Input alias | Canonical name |
|---|---|
| `EmailInput`, `PhoneInput` | `TextInput` |
| `AddressInput`, `ReasonInput` | `TextArea` |
| `Dropdown` | `Select` |
| `StartDatePicker`, `EndDatePicker` | `DatePicker` |
| `SubmitButton`, `CancelButton`, `ConfirmButton`, `ApproveButton`, `RejectButton` | `Button` |
| `SuccessMessage`, `ErrorMessage`, `ValidationMessage` | `Alert` |
| `HistoryList` | `List` |
| `BalanceCard` | `SummaryCard` |
| `ApprovalCard` | `Card` |

Repeated meaningful components are intentionally preserved. For example:

- `["DatePicker", "DatePicker"]` can represent start and end dates.
- `["Button", "Button"]` can represent submit/cancel or approve/reject actions.

## 15. Error handling

HTTP status mapping comes from the backend implementation:

| Status | Condition |
|---|---|
| 422 | Invalid request body or request type that fails Pydantic/FastAPI validation. |
| 500 | Missing or invalid LLM configuration, including a missing API key or invalid timeout/output-token settings. |
| 502 | Invalid model/provider result or provider rejection, model-not-found, authentication, malformed response, schema-invalid output, bad request, or unexpected provider response. |
| 503 | Temporary provider failure, connection failure, or rate-limit condition. |
| 504 | Model or provider timeout. |

The frontend maps the relevant API statuses to concise retry or configuration guidance and also handles unavailable backends.

## 16. Automated tests

The backend test suite contains **39 unittest methods**. The final verification run executed all 39 tests successfully: **39 passed and 0 failed**.

The suite previously passed 39/39 before later implementation and provider-format changes; this document reports the latest current run rather than the earlier historical count.

Mocked coverage includes:

- Direct successful generation and public response contract
- Authentication, model-not-found, bad-request, and provider errors
- One bounded retry followed by success or terminal failure
- Repair of empty, malformed, and schema-invalid output
- Call-budget enforcement
- Whitespace and blank-component normalization
- Case-insensitive alias normalization
- Duplicate section handling
- Meaningful duplicate component preservation
- HTTP mappings for 500, 502, 503, and 504
- Safe logging and provider-error classification

Automated backend tests mock `LLMClient.complete`; they do **not** call Groq or use live provider credentials.

## 17. Evaluation methodology

The live evaluation script:

- Uses 10 business domains.
- Runs 3 requests per domain.
- Sends 30 total live requests.
- Measures HTTP reliability.
- Validates the public JSON response shape.
- Scores section coverage by matching expected domain terms in section titles.
- Scores component coverage by matching expected canonical component names.
- Detects forbidden-feature terms in the returned screen name, titles, and components.
- Measures request latency.
- Preserves detailed response data and missing-term findings for human review.

Evaluation domains:

1. Employee leave management
2. Domestic fund transfer
3. Patient appointment booking
4. Customer registration
5. E-commerce checkout
6. Flight booking
7. Insurance claim submission
8. Customer support ticket
9. Event registration
10. Loan application

The evaluator uses HTTP success and schema validity as hard gates. Coverage and hallucination results are reported for human and semantic review.

## 18. Actual evaluation results

Verified values from `uc1_evaluation_20261126T113335Z.json`:

| Metric | Target or evaluation gate | Actual value | Result |
|---|---:|---:|---|
| Total requests | 30 live requests | 30 | Complete |
| HTTP success | At least 90% hard gate | 30/30, 100% | Passed |
| Schema validity | At least 90% hard gate | 30/30, 100% | Passed |
| Average section coverage on valid responses | Human-review coverage metric | 87.33% | Reported and reviewed |
| Average component coverage on valid responses | Human-review coverage metric | 94.78% | Reported and reviewed |
| Hallucination-free responses | No forbidden features | 30/30, 100% | Passed |
| Minimum latency | Informational | 0.544 seconds | Reported |
| Median latency | Informational | 8.11525 seconds | Reported |
| Average latency | Informational | 7.22361 seconds | Reported |
| P95 latency | Informational | 12.7607 seconds | Reported |
| Maximum latency | Informational | 13.7071 seconds | Reported |

Domestic fund transfer, patient appointment, flight booking, and support ticket had lower automated section-match scores. These results require human review. They are not recorded as failures merely because terminology matching may under-count semantically equivalent section titles.

## 19. Local setup

Backend:

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

The current Vite development proxy forwards `/api` to `http://127.0.0.1:8000` and rewrites the `/api` prefix. The frontend API client uses that `/api` base URL in development.

## 20. Environment variables

Backend environment template variables:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | Provider identifier; the current implementation expects Groq configuration. |
| `LLM_BASE_URL` | OpenAI-compatible provider base URL. |
| `LLM_MODEL` | Provider model identifier. |
| `LLM_API_KEY` | Private provider API key. |
| `LLM_TIMEOUT_SECONDS` | Provider request timeout in seconds. |
| `LLM_MAX_OUTPUT_TOKENS` | Requested output-token limit, capped in code at 700. |

Frontend environment template variable:

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | API base path; development behavior falls back to `/api`. |

`backend/.env` is private and ignored by Git. The frontend must never receive `LLM_API_KEY` or any Groq credential. Only `.env.example` files are committed; real key values are never placed in source or documentation.

## 21. Running tests

From the repository root, use the existing backend virtual environment:

```bash
cd backend
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q app tests
```

Frontend checks:

```bash
cd frontend
npm run build
npm run lint
```

The automated backend suite mocks provider calls and does not require live Groq access.

## 22. Running evaluation

From the repository root:

```bash
cd /workspaces/codespaces-blank/frontend-copilot

NO_PROXY=127.0.0.1,localhost \
no_proxy=127.0.0.1,localhost \
backend/.venv/bin/python \
  backend/evaluation/evaluate_uc1.py \
  --runs 3 \
  --delay 5
```

The evaluation writes timestamped JSON and CSV results under `backend/evaluation/results/`. JSON contains the summary and every request row; CSV contains the selected row-level summary fields.

## 23. Example request and response

### Leave-management request

```json
{
  "requirement": "Create an employee leave-management screen with annual and sick leave balances, leave type, start date, end date, reason, required-field and date validation, submit and cancel actions, request history, manager approval or rejection, and request status."
}
```

### Representative validated response

```json
{
  "screen_name": "Leave Request",
  "sections": [
    {
      "title": "Leave Balances",
      "components": ["SummaryCard"]
    },
    {
      "title": "Request Details",
      "components": ["Form", "Select", "DatePicker", "DatePicker", "TextArea"]
    },
    {
      "title": "Validation",
      "components": ["Alert"]
    },
    {
      "title": "Submit or Cancel Request",
      "components": ["Button", "Button"]
    },
    {
      "title": "Request History and Status",
      "components": ["Table", "StatusBadge"]
    },
    {
      "title": "Manager Review",
      "components": ["TextArea", "Button", "Button"]
    }
  ]
}
```

The two `DatePicker` entries represent start and end dates. The repeated `Button` entries represent submit/cancel or approve/reject actions. The example is low-fidelity structure only.

## 24. Security considerations

- The API key remains on the backend and is never sent to the frontend.
- `backend/.env` is ignored by Git and must remain private.
- Provider logs do not include requirement text or complete model response content.
- Safe provider-error messages are returned to users instead of raw provider details.
- Request input is limited to a string in the backend and additionally limited to 2,000 characters by the frontend.
- Output is parsed, normalized, and validated by Pydantic before it is accepted.
- Generated content is treated only as data: there is no generated-code execution or evaluation.
- The frontend performs runtime shape validation and does not dynamically execute response values.

## 25. Known limitations

- UC1 produces low-fidelity structure only.
- The current component schema stores component names but no separate label, field purpose, validation metadata, or layout metadata.
- Automated keyword coverage can under-count semantically equivalent section titles.
- Groq latency varies.
- Human UX and business review remain required.
- UC1 has no persistence or generation history.
- UC1 has no authentication.
- UC1 has no database.
- RAG is not implemented.
- Agents are not implemented.
- UC1 has no direct Figma export.
- UC1 does not generate production React code.

## 26. Business value

UC1 can provide:

- Faster requirement visualization into an initial screen structure.
- Earlier detection of missing fields, actions, validation, status, or review flows.
- Reduced initial manual wireframing effort.
- A structured, machine-readable handoff for later frontend use cases.
- More consistent early wireframe structure across similar requirements.

This documentation does not claim unmeasured time or cost savings.

## 27. UC1 completion status

UC1 V1 passed the principal automated live functional gates:

- 100% HTTP reliability in the 30-request evaluation.
- 100% schema validity.
- Component coverage, section coverage, and hallucination-free reporting were completed and require the documented human semantic review.
- The frontend build and lint checks passed.
- Human UX/business review and production deployment remain separate activities.

The final backend unit-test run completed successfully: **39 of 39 tests passed**. The earlier alias-normalization fixture mismatch was corrected without changing the UC1 API contract or runtime behavior.

## 28. Future work

Future enhancements, separate from UC1 V1, may include:

- A rich component schema with type, label, validation, and layout metadata.
- Saved projects and generation history.
- Improved semantic evaluation for section titles and equivalent terminology.
- Figma export.
- A later RAG enhancement.
- A later agent enhancement.

RAG and agents were not implemented in UC1 V1.
