# Financing-AI-Agent

A small educational SME financing API using FastAPI, Pydantic, and Gemini.
Compare deterministic Python orchestration with a bounded Gemini tool-calling
agent. No agent framework, database, or real lending integration is required. A small frontend is served by FastAPI.

## Architecture

```text
SME request -> FastAPI -> Pydantic validation
                              |
                +-------------+----------------+
                |                              |
           /evaluate                    /agent-evaluate
       Python orchestrator                Gemini chat
                |                              |
                |                  model requests Python tools
                |                  SDK executes and returns results
                |                              |
                +------ eligibility / category tools ------+
                                       |
                          Python checks results and review state
                                       |
                     Checked assessment code -> safe explanation
                                       |
                        JSON response / human review flag

Missing key, API failure, incomplete tool use, invalid output
                 -> deterministic fallback -> valid JSON
```

## Features and files

```text
Financing-AI-Agent/
  main.py             FastAPI routes
  models.py           Request validation
  tools.py            Demo eligibility and category functions
  orchestrator.py     Deterministic workflow and result assembly
  agent.py            Gemini configuration, retries, safe explanations
  ai_agent.py         Chat-based automatic tool calling
  static/             HTML, CSS, and JavaScript frontend
  tests/test_api.py   Offline API and real SDK chat-loop tests
  tests/browser_smoke.py  Optional real-browser integration check
  requirements.txt    Six direct dependencies
  .env.example        Safe configuration template
  .gitignore          Excludes secrets, venv and caches
  README.md
  .env                Local secret file, never tracked
```

## Installation and configuration (PowerShell, Python 3.11+)

```powershell
Set-Location C:\Users\james\Desktop\Financing-AI-Agent
# Only if no virtual environment exists:
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# Only for a new checkout without .env; preserve any existing key:
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` locally to set `GEMINI_API_KEY`. Never print or commit it.
Optional `GEMINI_MODEL` defaults to `gemini-3.8-flash`, preserving this project's
previous setting. Model availability depends on your account; this name has not
been verified with a live request during this implementation. A 404 falls back
without retry. Choose a model available to your account if needed.
Without a key, both endpoints work in fallback mode. Restart after changing `.env`.

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs
Frontend: http://127.0.0.1:8000/
Health/basic response: http://127.0.0.1:8000/health

## Three example requests

In another PowerShell window:

```powershell
$body = @{
    company_name = 'ABC Software'
    industry = 'Technology'
    annual_revenue = 100000
    employees = 8
    requested_amount = 20000
    financing_purpose = 'Buy new equipment'
}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/evaluate -ContentType 'application/json' -Body ($body | ConvertTo-Json) | ConvertTo-Json -Depth 6

$body.requested_amount = 50000
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/evaluate -ContentType 'application/json' -Body ($body | ConvertTo-Json) | ConvertTo-Json -Depth 6

$body.requested_amount = 20000
$body.financing_purpose = 'Improve short-term cash flow from unpaid invoices'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/agent-evaluate -ContentType 'application/json' -Body ($body | ConvertTo-Json) | ConvertTo-Json -Depth 6
```

| Example | eligible | recommended_financing | requires_human_review |
| --- | --- | --- | --- |
| Equipment, 20,000 | true | Equipment financing or leasing | false |
| Equipment, 50,000 | false | null | true |
| Invoices, 20,000 | true | Invoice financing or factoring | false |

Use either endpoint for any example. `requested_amount = 0` returns HTTP 422.
Unknown purposes return a review flag and no category. Amount exactly 30% passes.
Amounts must be finite and positive; employees must be a positive integer;
company, industry and purpose must contain non-whitespace text.

## Deterministic workflow

`POST /evaluate` runs `process_financing_request`: check eligibility first, then
recommend a category only if eligible. Ineligible/unknown cases return review
immediately, without Gemini. Otherwise Gemini receives the computed result and
returns a constrained assessment code. Python validates that code and renders a
safe explanation. The LLM does not choose or execute tools on this endpoint.

## Agentic workflow and genuine tool calling

`POST /agent-evaluate` creates a fresh Gemini chat for every attempt.
In `ai_agent.py`, `run_chat()` passes Python callables to `client.chats.create`
and invokes `chat.send_message`. This is where real automatic function calling
occurs: Gemini chooses function calls; the installed SDK executes the callable,
returns its result to Gemini, and requests the next response. It is not a
hard-coded sequence of calls disguised as an agent.

The functions exposed to Gemini are request-bound, zero-argument wrappers named
`check_eligibility` and `recommend_financing`. They call the typed core tools using
validated input. This prevents a model from changing the revenue or amount.
Recommendation is blocked until eligibility has passed. A maximum of four model
calls per attempt bounds the loop. Python requires observed eligibility and,
when eligible, recommendation results before accepting the model's final code.
No tools, incomplete execution, pending calls at the limit, or contradictory
output cause an explicitly reported deterministic fallback.

`tool_calls` records actual wrapper invocations (including failed preconditions
and retry attempts). Logs show `Agent called: ...`; they do not contain request
fields or credentials. The deterministic endpoint has an empty agent trace.

See [Google's SDK guidance](https://github.com/googleapis/python-genai) for the
chat-based AFC interface. Installed/tested SDK: `google-genai==2.28.0`.

## Explanations and guardrails

The model returns exactly one JSON assessment code: `potential_match`,
`amount_review`, or `purpose_review`. The server checks it against Python tool
results and renders controlled text with a disclaimer. This deliberately limits
LLM prose: it cannot introduce rates, lender offers, approval probabilities,
guarantees, or supposed Leano rules into the explanation. No raw LLM text is
returned. This is a bounded tool-calling demonstration, not autonomous underwriting.

## Human review

Ineligible requests and unknown purposes set `requires_human_review=true`,
`recommended_financing=null`, and `status="Escalated for human review"`.
This is an escalation signal only: no reviewer is notified, no case is saved,
and no human approval/resume interface exists. A demo operator must inspect the
response. An LLM failure alone does not make an otherwise clear demo case ineligible.

## Error handling and response metadata

Missing keys, API errors, network/timeouts, empty/malformed output and inconsistent
model results fall back safely. Temporary HTTP 408/429/500/502/503/504 and transport
errors get at most three attempts with one- and two-second delays. Other errors
fall back immediately. Each HTTP request has a 15-second timeout; the agent can
make up to four calls per attempt, so its overall latency can exceed 15 seconds.
These read-only tools are safe to repeat. No raw exception bodies are logged.

- `workflow`: the requested workflow, `deterministic` or `agentic`.
- `execution_mode`: `gemini_explanation`, `gemini_tool_calling`,
  `review_without_llm`, or `deterministic_fallback`.
- `llm_fallback`: whether Gemini was unavailable or its result was rejected.
- `tool_calls`: observed agent calls, never invented fallback traces.

Fallback explanations begin with "The AI explanation is currently unavailable."
The eligibility, recommendation and review fields remain usable.

## Tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover the three examples, validation, boundary/unknown purposes, missing
keys, 503/404/network errors, bounded retries, invalid or unsafe model output,
and the SDK's actual automatic function-calling loop. They simulate only the
model/network boundary, including function results sent back to the model.
They make no live Gemini requests or paid calls. Successful live model tool
selection and availability remain unverified. The installed Starlette emits a
TestClient/httpx deprecation warning; it does not fail these tests.

## Safety disclaimer and limitations

**The 30%-of-revenue threshold is a made-up demo heuristic, not a financial
industry rule or a real underwriting policy. This application makes no lending
decision and never guarantees financing.**

Purpose matching uses simple keywords; ambiguous/multiple purposes may be
misclassified. There are no real lender offers, credit checks, risk scoring,
verified company data, currency conversion, durable human review, or production
security controls. Use fictional data for demonstrations. Gemini receives the
submitted request when used. This demo is not ready for public production use.

## Future improvements

Add a real reviewer queue and audit trail, richer purpose matching, live provider
integration tests, and qualified validation of any eventual financial rules.
Keep these outside the current interview demo's scope.

## 60-second interview explanation

"I built a small FastAPI demo for SME financing with two workflows. Pydantic
validates the request. The deterministic endpoint runs Python tools in a fixed
order and asks Gemini for a constrained explanation assessment. The agentic
endpoint gives Gemini two tools through the SDK's chat interface. Gemini chooses
the calls, the SDK runs Python functions and sends the results back, and Python
checks the final result. The tools use the original validated request, so the
model cannot change financial values. A made-up 30-percent revenue threshold and
simple purpose matching demonstrate branching. Ineligible or unknown cases are
flagged for human review, though there is no reviewer queue yet. API failures
use bounded retries and a transparent deterministic fallback. Explanations use
controlled text to avoid invented offers or guarantees. I tested the API and
the real SDK tool loop offline; live model availability is a separate dependency."

## Frontend workspace

The application now includes a responsive HTML/CSS/JavaScript frontend served by
FastAPI. No Node installation, frontend build, or second server is required.

```powershell
Set-Location C:\Users\james\Desktop\Financing-AI-Agent
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open **http://127.0.0.1:8000/** for the application, `/docs` for Swagger, or
`/health` for the JSON health response (previously at `/`).

Frontend files are `static/index.html`, `static/styles.css`, and `static/app.js`.
The form sends requests to the existing API on the same origin. It supports:

- All six company/request fields, with browser and server validation.
- Equipment, cash-flow, and human-review example buttons.
- Guided (`/evaluate`) and agentic (`/agent-evaluate`) workflow selection.
- Loading, network error, review, AI fallback, and successful assessment states.
- Actual execution mode and observed agent tool calls.
- A downloadable JSON assessment for manual sharing with a demo reviewer.
- Responsive layout and keyboard-accessible controls.

Results are held only in the current page, not saved in browser storage. Editing
inputs clears a previous result to prevent confusion. Downloads contain the
submitted company data. The form never requests or exposes your Gemini API key.
The existing limitations still apply: demo rules, no lending approvals, and no
persistent reviewer queue. A working fallback does not prove live Gemini success.

Optional browser integration checks (uses installed Microsoft Edge):

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe tests/browser_smoke.py
```

This starts an isolated server on port 8001 with Gemini disabled, exercises the
actual form and API, checks desktop/mobile behavior and downloads, and stops
the test server. Screenshots are written to `frontend-desktop.png` and
`frontend-mobile.png`. Browser tooling is not required to run the application.



Live verification during frontend implementation: Gemini requested and executed
both tools, then returned 429; other calls returned 503. Both endpoints completed
with valid deterministic fallback assessments. Full live AI completion was not
verified. The interface accurately labels this situation as fallback.
