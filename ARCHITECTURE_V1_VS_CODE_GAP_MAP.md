# Freshy Architecture v1.0 vs Current Code — Detailed Gap Map

**Date:** 2026-09-17  
**Architecture source of truth:** `FRESHY_Architecture_v1.0.md`  
**Visual / draft companion:** `freshy AI architecture.txt` (same v1.0 at end + older drafts)  
**Current implementation under review:**  
`extracted-freshy-ai/freshy-ai-assistant-v6.0.5-phase6a-memory-speech-hotfix/`  
**Declared product version:** 6.0.5 — Phase 6A Memory Speech Hotfix  

---

## 0. Executive verdict

| Question | Answer |
|---|---|
| Is v6.0.5 the full Architecture v1.0? | **No** |
| What is v6.0.5 really? | A **working modular-monolith desktop assistant snapshot** with chat, multi-provider AI, allowlisted tools, SQLite memory, STT/TTS, and optional Gemini Live |
| How much of the 27-module target exists? | Roughly **~30–40% conceptually present**, **~15–25% production-shaped** |
| Biggest missing pillars | Full **Policy/Approval Engine**, **Planner + bounded Agent Runtime**, **4-path Request Router**, **Runtime Supervisor**, **Event/Workflow bus**, **Verification engine**, **Plugin lifecycle** |
| Biggest existing strengths | Fail-soft design, allowlisted tools (not free shell), multi-provider router, memory safety filters, explicit-tool-request checks, good automated tests for current scope, Flutter + web dual UI |
| Recommended stance | Treat Architecture v1.0 as **target OS design**. Treat v6.0.5 as **Phase 1–4 prototype base**, not final system |

### Scorecard (Architecture v1.0 compliance)

| Area | Score | Notes |
|---|---:|---|
| Input / chat path | 6/10 | Text strong; voice strong on Windows, limited on Linux |
| Identity / admission | 2/10 | Session IDs only; no real auth |
| Request routing | 4/10 | Local-first + AI fallback; not Fast/Core/Agent/Event |
| Model gateway | 7/10 | Multi-provider + cooldown/fallback present |
| Tools + execution safety | 6/10 | Allowlist + schema validation; narrow tool set |
| Policy / approval | 3/10 | Implicit security blocks; no first-class policy engine |
| Planning / agent loop | 2/10 | Single-turn tool call (max ~2); no planner/tasks |
| Verify / recover | 2/10 | Tool success flags only; no evidence engine |
| Memory | 7/10 | SQLite + modes + secret/injection filters |
| Voice I/O | 7/10 | Rich on Windows; Linux degrade |
| Live voice | 6/10 | Gemini Live present; still preview-grade |
| Runtime supervisor | 2/10 | FastAPI lifespan only |
| Automation / events | 1/10 | Absent |
| Observability / audit | 3/10 | Logs + memory audit partial |
| Eval / CI culture | 6/10 | Many unit tests; not full arch eval suite |
| Plugins | 1/10 | Absent |
| **Overall architecture fit** | **~3.5 / 10** | Solid assistant MVP ≠ full v1.0 OS |

---

## 1. What the two artifacts are

### 1.1 Architecture v1.0 (target)

Three critical design decisions:

1. **Policy engine lives outside the LLM** (deterministic). Model proposes; policy authorizes.
2. **Intelligent Request Router** with four paths: **FAST / CORE / AGENT / EVENT**.
3. **Runtime Supervisor + modular monolith + 6-phase build**.

Eight non-negotiable principles:

- Default Deny / Least Privilege  
- LLM Proposes, Policy Decides  
- Read ≠ Write  
- Verify, Don't Trust  
- External Content = Untrusted  
- Local-Only Data  
- Bounded Autonomy  
- Approval Is Specific  

Shape: **one application, clear modules**, in-process event bus first — **not 27 microservices**.

### 1.2 Current code v6.0.5 (reality)

Three runtimes in one zip:

| Layer | Stack | Role |
|---|---|---|
| `freshy_core/` | Python FastAPI | Real desktop brain: chat, tools, memory, voice, live |
| `freshy_app/` | Flutter Windows | Native desktop UI (orb, chat, settings) |
| `src/` + `server.ts` | React + Express/Vite | Desktop **web preview** (no native Windows actions) |

**Actual request path today (simplified):**

```text
User message
  → size/empty validation
  → memory control commands (remember/forget/…)
  → rule-based local intents (greeting/time/app/website)
  → if no cloud provider keys → safe offline reply
  → else: recall memory + optional Tavily pre-search
  → provider router (Groq → Mistral → Gemini → SambaNova)
  → optional single tool call (max loop ~2)
       only if user message explicitly authorizes that tool
       only if tool is registered + args validate
  → reply (+ TTS request flag)
```

This is a **pragmatic single-turn assistant loop**, not the full Master Control Loop.

---

## 2. Module-by-module gap map (all 27)

Legend:

| Status | Meaning |
|---|---|
| **DONE** | Present and roughly matches intent for current phase |
| **PARTIAL** | Exists but thinner / different shape than v1.0 |
| **STUB** | Naming or tiny piece only |
| **MISSING** | Not implemented |

---

### PART A — Input, Identity & Routing

#### 01. Perception & Input Gateway — **PARTIAL**

| v1.0 expects | v6.0.5 has |
|---|---|
| Text / mic / audio stream / app interface | Text chat APIs; Flutter voice; Live PCM path |
| STT: Whisper / Vosk / cloud | Whisper + Vosk hybrid (`voice_input_service.py`, `whisper_service.py`) |
| VAD, wake word, language detect (Hi/Hinglish/En) | VAD + silence windows; wake-ish settings; language settings |
| Normalize request with source label, size limits, request IDs | Message size limits; `session_id`; weak/no formal Normalized Request object or source enum |

**Gap:** No unified Perception module API. Web preview cannot do real mic. No formal request envelope (`source=USER|DEVICE|WEBHOOK|SCHEDULE`).

**Code anchors:** `main.py` voice endpoints, `voice_input_service.py`, Flutter `FreshyApiService`, web `App.tsx`.

---

#### 02. Speaker Identity Service — **MISSING / STUB**

| v1.0 expects | v6.0.5 has |
|---|---|
| Consent enrollment, embeddings, anti-spoof | `voice_profiles/` folder + profile manager hooks for **TTS clone / XTTS**, not speaker-auth identity |
| Voice match as soft identity signal only | Not used as admission control |

**Gap:** No speaker verification gate before sensitive actions.

---

#### 03. Identity, Session & Request Admission — **STUB**

| v1.0 expects | v6.0.5 has |
|---|---|
| Login, tokens, passkeys, roles, scopes | Free-string `session_id` (e.g. `default-session`, `desktop-web-preview`) |
| Rate limits, guest mode, replay protection | Basic input length cap only |
| Stronger auth for sensitive actions | None |

**Gap:** Anyone who can reach `127.0.0.1:8000` can call APIs. Fine for local MVP; **not** Architecture admission.

**Risk note:** Core currently binds `0.0.0.0` in this Linux preview patch — acceptable only inside sandbox; production must stay localhost or authenticated.

---

#### 04. Intelligent Request Router (FAST/CORE/AGENT/EVENT) — **PARTIAL**

| Path | v1.0 meaning | v6.0.5 equivalent |
|---|---|---|
| FAST | Simple local capability | Rule intents: GREETING, TIME_DATE, OPEN_APP, OPEN_WEBSITE + memory control phrases |
| CORE | Chat / knowledge / retrieval | Provider chat + memory recall + optional search context |
| AGENT | Multi-step plan/tools | **Missing** (only 1–2 tool hops, no task object) |
| EVENT | Scheduled/authorized workflows | **Missing** |

**What exists that is good:**

- Local intents short-circuit before spending provider/search credits.  
- Tools not offered unless message looks action-like (`_may_offer_tools`).  
- Unsolicited tool calls blocked (`_explicit_tool_request`).

**Gap:** No named router module, no complexity classifier, no clarification path as first-class route, no EVENT path, FAST still shares same process without formal route metadata.

**Code anchors:** `intents.py`, `assistant_orchestrator._handle_local`, `handle_request`.

---

### PART B — Context, Intelligence & Action Control

#### 05. Context & Trust Manager — **PARTIAL**

| v1.0 expects | v6.0.5 has |
|---|---|
| Scoped, source-tagged context budget | Conversation history store + sanitize; memory recall snippet; web search note |
| Trust labels; external = untrusted | System prompt marks web/tool text untrusted; strips tool markup from history |
| Workspace isolation | Single local DB; no multi-user/workspace model |

**Gap:** No structured Context object with classification tags, budgets as policy, or per-workspace isolation.

---

#### 06. Freshy Core — Request Understanding — **PARTIAL**

| v1.0 expects | v6.0.5 has |
|---|---|
| Intent / outcome / constraints / RESPOND·CLARIFY·TOOL·TASK | Rule parser for few intents; otherwise LLM free-form |
| Cannot self-grant permissions | True in spirit via tool registry allowlist |

**Gap:** No explicit decision enum or task specification object. Ambiguity → model improvises, not structured CLARIFY.

**Code anchors:** `AssistantOrchestrator`, `RuleBasedIntentParser`, optional `GeminiIntentAnalyzer` (legacy/secondary).

---

#### 07. Model Gateway & Provider Orchestration — **DONE (strong PARTIAL→DONE for MVP)**

| v1.0 expects | v6.0.5 has |
|---|---|
| Unified providers + routing by capability/cost/latency | `ProviderRouter` order: groq, mistral, gemini, sambanova |
| Health, rate limits, circuit breakers | Cooldown after failures; timeout/retry config |
| Local-only data never silent cloud fallback | No explicit data-residency classifier yet; keys from env |
| Structured output / tool calling | Native tools + `[TOOL_CALL]` text fallback parser |

**Gap:** No OpenRouter adapter yet (mentioned in architecture drafts). No local open-weight path. No capability-based routing beyond fixed order. No hard “local-only field” enforcement layer.

**Code anchors:** `ai/provider_router.py`, `openai_compatible_provider.py`, `gemini_provider.py`, Node mirrors under `src/server/ai/`.

---

#### 08. Goal & Task Manager — **MISSING**

No task entities, states (`CREATED→…→COMPLETED`), budgets, deadlines, or approval-waiting task state.

Current system is **turn-based**, not **goal-based**.

---

#### 09. Planner — **MISSING**

No goal→steps→dependencies→proposed actions structure.  
No expected-result definitions for verification.  
Model may emit one tool call; that is not a planner.

---

#### 10. Capability & Tool Registry — **PARTIAL (good MVP)**

| v1.0 expects | v6.0.5 has |
|---|---|
| Rich tool metadata: risk, timeout, cost, side effects, idempotency, sandbox profile, verification method, health | Name + description + pydantic args schema + handler |
| Catalog states AVAILABLE/RESTRICTED/… | Implicit: registered or “Security Block” |
| Trusted app-owned metadata | Yes — code-registered only |

**Registered tools today (only 4):**

1. `get_time_date`  
2. `open_application` (notepad | calculator)  
3. `open_website` (google/youtube/github/wikipedia allowlist)  
4. `web_search` (Tavily)

**Gap:** Metadata too thin for policy engine. No file read/write tool, telegram, browser automation, etc. (correctly absent until policy exists).

**Code anchors:** `tools/registry.py`, `tools/schemas.py`, Node `safeToolRegistry.ts`.

---

#### 11. Agent Runtime — Bounded Task Controller — **STUB / MISSING**

| v1.0 expects | v6.0.5 has |
|---|---|
| plan → authorize → execute → observe → verify → loop | `for _ in range(2):` tool hop inside `handle_request` |
| max steps, cancel, pause, escalate | Duplicate tool fingerprint block; no cancel token / task UI |
| sub-agents later | None |

**Gap:** This is the heart of Architecture Master Loop and is largely absent.

---

#### 12. Policy, Permission & Approval Engine — **PARTIAL (critical gap)**

| v1.0 expects | v6.0.5 has |
|---|---|
| Deterministic engine **outside** LLM | Security checks **inside** orchestrator + registry + executor (good instinct, wrong shape) |
| BLOCK / ASK APPROVAL / AUTHORIZE | Mostly hard allow/deny; **no user approval card flow** for risky actions |
| Read≠Write separate; arg path/URL validation | URL domain allowlist; app allowlist; arg pydantic validation |
| Approval bound to action+args+expiry | Not implemented |
| Default deny | Yes for unknown tools/domains/apps |

**What is already aligned with spirit of v1.0 (keep these):**

- Unknown tool → Security Block  
- Invalid args → Security Block  
- Non-allowlisted app/domain → block  
- Unsolicited model tool call → blocked / retried without tools  
- Web/tool content treated as untrusted in prompt  
- Memory refuses secrets + injection-like text  
- Web preview never executes native Windows actions  

**What is missing for real Policy Engine:**

- First-class `PolicyDecision` type  
- Identity/session/task scope inputs  
- Risk classes + approval UX (Flutter/web permission cards)  
- Re-check on retry/fallback/changed args  
- Separate read vs write permissions  
- Audit record per decision  
- No path for “ALLOW once for this exact action”

**Code anchors:** `ToolRegistry.execute_tool`, `CommandExecutor`, `AssistantOrchestrator._explicit_tool_request`, `memory/safety.py`.

---

#### 13. Sandboxed Execution Engine — **PARTIAL**

| v1.0 expects | v6.0.5 has |
|---|---|
| Execute only registered tools; revalidate at boundary | Registry executes only registered handlers |
| FS/network isolation, credentials scoping | Process-local allowlists; **no OS sandbox** |
| Timeouts, idempotency keys, cleanup | Limited; web search has timeout config |
| No arbitrary shell / model code exec | **Correctly avoided** (unlike ROCKY anti-patterns) |

**Gap:** Not a sandbox — an allowlisted in-process executor. Sufficient for current 4 tools; insufficient for browser/OS automation later.

---

#### 14. Observation & Result Normalization — **PARTIAL**

Tool handlers return `ToolResult(success, output, error, metadata)`.  
No general normalizer with redaction bounds, source stamps, or size policy beyond ad-hoc code.

---

#### 15. Verification & Recovery Engine — **MISSING / STUB**

| v1.0 expects | v6.0.5 has |
|---|---|
| Compare expected vs observed evidence | Uses tool `success` / `action_executed` flags |
| PARTIAL / UNKNOWN / FAILED recovery paths | Mostly single-shot failure messages |
| Never trust “model said done” | Prompt instructs not to claim success without tool result — **good**, but no verifier module |

**Gap:** No read-back checks (did Notepad window actually open?), no recovery planner.

---

### PART C — Response & Voice

#### 16. Response Engine — **PARTIAL**

- Replies in EN/Hinglish mix depending on prompts/paths.  
- Action speech helpers avoid raw URLs in spoken confirmations (Phase 6A hotfix intent).  
- Distinguishes some errors with `user_safe_error` / `error_code`.  

**Gap:** No dedicated response module with explicit “planned vs attempted vs verified” rendering contract everywhere.

---

#### 17. Voice Output Engine — **DONE (platform-skewed)**

| Feature | Status |
|---|---|
| TTS providers gemini / xtts / system / text_only | Present |
| Fast-start chunking | Present |
| Queue / stop / status APIs | Present |
| Barge-in / interrupt while speaking | Present on Windows voice pipeline |
| Linux preview | Degrades (no pyttsx3/sounddevice) → text_only / silent |

**Gap vs v1.0:** Sensitive content → private display policy not generalized. Stop-speaking ≠ cancel-task wiring absent because tasks absent.

---

### PART D — Shared Infrastructure

#### 18. Durable State & Checkpoint Store — **STUB**

- Conversation history can persist via memory store settings.  
- No task checkpoints, approval records, crash reconcile of in-flight tool side effects.

---

#### 19. Memory & Knowledge Service — **DONE (strong MVP)**

| Feature | Status |
|---|---|
| SQLite local DB | Yes (`freshy_memory.db`) |
| Modes: ask_before_saving / auto_safe / manual_only / disabled | Yes |
| CRUD + pin + export/import + clear | Yes (API rich) |
| Recall limits | Yes |
| Secret + prompt-injection filters on write | Yes (`memory/safety.py`) |
| Conversation retention | Configured |
| Semantic vector memory | **No** (keyword/simple recall) |
| Multi-workspace ACL | **No** |

**Architecture fit:** One of the closest modules to v1.0 intent for Phase 4–5.

---

#### 20. Automation & Workflow Service — **MISSING**

No cron/webhook/device triggers, no workflow owner/scope/expiry.

---

#### 21. Event Bus & Delivery Control — **MISSING**

No typed events, queues, dedupe, dead-letter. Everything is synchronous HTTP request/response (+ live session internals).

---

#### 22. Concurrency & Resource Manager — **STUB**

Threading locks around TTS/voice/live singletons. No global worker pool, quotas, or conflict detector.

---

#### 23. Secrets & Configuration Manager — **PARTIAL**

| Feature | Status |
|---|---|
| `.env` + `config.py` | Yes |
| `.gitignore` excludes `.env`, voice/live settings, DB | Yes |
| OS keychain | No |
| UI-managed keys without leaking to `VITE_*` | Documented intent; web preview uses server-side env |
| Redaction tests | Partial (`test_provider_security.py`) |
| Rotation / scoped credentials to adapters only | Informal |

---

#### 24. Privacy & Data Governance — **PARTIAL**

- Memory safety filters.  
- Local DB.  
- Prompt rules for untrusted external text.  
- Missing: formal classification (Public/Private/Sensitive), retention UI beyond basics, export/delete as user rights workflow, egress checker before every provider call with data tags.

---

#### 25. Health, Observability & Audit — **PARTIAL**

| Feature | Status |
|---|---|
| `/health`, `/api/status`, AI/TTS/voice/live status | Yes |
| Memory audit log endpoint | Yes |
| Correlated trace Request→Plan→Approval→Tool→Evidence | **No** |
| Metrics/cost dashboards | Live metrics module exists lightly; not full |
| Integrity-protected audit | No |

---

#### 26. Evaluation & Controlled Improvement — **PARTIAL**

**Strength:** Large test set for current scope:

- API, orchestrator, provider router/security  
- tools, executor, intents  
- memory store/service  
- TTS/voice/live phase tests  
- Node contract tests  

**Gap vs v1.0:** No permission-injection suite as release gate, no crash-recovery tests for tasks, no offline eval harness for model changes, no versioned eval reports.

---

#### 27. Plugin & Connector Lifecycle — **MISSING**

Tools are hard-coded in registry. No install/review/disable/permission-manifest flow.

---

## 3. Cross-cutting architecture features

### 3.1 Master Control Loop

| Loop stage | Code today |
|---|---|
| Normalize request | Light (trim/size) |
| Authenticate + admit + scope | Missing |
| Route request | Informal local vs AI |
| Scoped context + memory | Partial |
| Check capabilities | Implicit tool list |
| Propose plan | Missing |
| Propose tool action | Model or local intent |
| Validate tool + args | Yes |
| Policy + privacy check | Partial allow/deny |
| Approval wait | Missing |
| Checkpoint | Missing |
| Revalidate + execute | Execute only |
| Observe | ToolResult |
| Verify | Flag only |
| Persist / memory update | Conversation + optional memory |
| Response text/voice | Yes |
| Always recheck policy on next step | N/A (no multi-step tasks) |

### 3.2 Runtime Supervisor

| Lifecycle | Code today |
|---|---|
| Startup validate config | dotenv/config load; weak validation |
| Init identity/policy | Missing |
| Register tools | On orchestrator init |
| Reconcile interrupted tasks | Missing |
| Health/quotas monitoring | Passive endpoints only |
| Permission revocation runtime | Missing |
| Graceful drain shutdown | Lifespan stops live/voice/tts |

**Verdict:** FastAPI lifespan ≠ Runtime Supervisor.

### 3.3 Implementation shape

| v1.0 | v6.0.5 |
|---|---|
| Modular monolith | **Yes** (good) |
| In-process modules | **Yes** |
| Clear package boundaries | **Partial** — `ai/`, `memory/`, `tools/`, `live/` exist; policy/planner/supervisor packages absent |
| Dual UI (Flutter + web preview) | Extra vs architecture (fine) |
| Node duplicate orchestrator | Parallel implementation for preview — **drift risk** |

---

## 4. Principle compliance matrix

| Principle | Compliance | Evidence |
|---|---|---|
| Default Deny | **Mostly yes** | Unknown tools/apps/domains blocked |
| LLM Proposes, Policy Decides | **Partial** | LLM can propose; “policy” is scattered allowlists, not engine |
| Read ≠ Write | **Weak** | No read tools yet; no separate permission classes |
| Verify, Don't Trust | **Partial** | Prompt-level; no verifier |
| External Content = Untrusted | **Yes (prompt + history sanitize)** | Needs structural enforcement |
| Local-Only Data | **Weak** | No classifier preventing cloud send |
| Bounded Autonomy | **Partial** | Tool loop cap 2; no task budgets |
| Approval Is Specific | **No** | No approval objects |

---

## 5. Build-phase progress vs Architecture roadmap

Architecture recommended sequence:

| Phase | Architecture deliverable | v6.0.5 reality |
|---|---|---|
| **1 Foundation** | Text, identity/scope, one model, config, state, logs | **Mostly done** except real identity/scope |
| **2 Controlled Tools** | Registry, **policy gate**, time tool, restricted file read, reminders, verification | Registry + time + allowlisted open + search; **policy gate thin**; file/reminders/verify missing |
| **3 Reliable Tasks** | Planner, bounded agent, checkpoints, cancel, recovery | **Largely missing** |
| **4 Personal Assistant** | Voice, scoped memory, preferences, stronger auth | Voice + memory **strong**; stronger auth missing |
| **5 Automation** | Workflows, events, background, revocation | **Missing** |
| **6 Expansion** | More providers/plugins/devices; multi-agent if proven | Extra providers + Live voice arrived **before** phases 2–3 solidification |

**Important insight:** Product versioning jumped to “Phase 6A” for **voice/live/memory features**, while Architecture phases 2–3 (**policy + tasks**) are still behind.  
Name collision: **code “Phase 6A” ≠ architecture “Phase 6 Expansion”.**

---

## 6. Security posture vs Architecture + research audits

| Topic | ROCKY/Stonic lesson | Freshy v6.0.5 |
|---|---|---|
| Arbitrary shell / Python exec | Dangerous | **Avoided** ✅ |
| LAN remote control without auth | Dangerous | Local APIs; Linux preview bind 0.0.0.0 needs care ⚠️ |
| Unrestricted browser/OS control | Dangerous | Only 2 apps + 4 domains ✅ |
| Plaintext secrets in memory | Dangerous | Filtered ✅ |
| LLM code runs on host | Dangerous | Not present ✅ |
| Approval UX for destructive acts | Required | Not built yet ❌ |
| Claim success without evidence | Bad UX/security | Mostly guarded in prompts/tools ✅ |

**Net:** v6.0.5 is **far safer than ROCKY** as a starting point, but still not Architecture-complete secure agent OS.

---

## 7. Platform / runtime gaps (Linux sandbox vs design target)

| Capability | Windows desktop target | This Linux Arena environment |
|---|---|---|
| Flutter UI | Primary | Not available |
| Web preview | Secondary | **Running :3000** |
| Python core | Primary | **Running :8000** |
| Open Notepad/Calculator | Real | Simulated |
| Mic / Vosk / Whisper | Real | Fail-soft / deps optional |
| system TTS | Real | Missing pyttsx3 → degrade |
| Cloud AI | Needs keys | Local intents only until keys set |

These are **environment gaps**, not all architecture gaps — but they affect how we demo and test.

---

## 8. Duplicate surfaces & drift risks

1. **Python orchestrator** vs **Node orchestrator** — two brains for similar chat. Web preview must not silently diverge on safety rules.  
2. **Architecture docs at repo root** vs **code only inside extracted zip** — repo is not yet a clean monorepo layout.  
3. **Version labels:** app 6.0.5 / Flutter 6.0.2 / web 6.0.2 / architecture v1.0 — need a single versioning scheme.  
4. **`freshy AI architecture.txt`** contains old drafts + final v1.0; **MD is canonical** for engineers.

---

## 9. Priority gap backlog (what to build next)

### P0 — Make Architecture real without killing the working app

1. **Extract a real Policy Engine module** (`policy/`)  
   - Input: principal, tool name, args, risk, data tags  
   - Output: `BLOCK | ASK | ALLOW` + reason  
   - Move allowlists out of executor/orchestrator into policy config  
2. **Formal Request Router**  
   - Tag every turn: FAST/CORE/(future AGENT)  
   - Emit route in API response for UI/debug  
3. **Unified NormalizedRequest schema**  
   - `request_id`, `session_id`, `source`, `text`, `locale`, `channel`  
4. **Approval channel (even if only for future high-risk tools)**  
   - API + Flutter/web card: allow/deny once  

### P1 — Close Phase 2 holes

5. Restricted **file read** tool under workspace root  
6. **Reminder** tool with local schedule store (leads into Phase 5)  
7. **Verification** helpers for open-app / open-url (best-effort)  
8. Structured **action trace** log (jsonl/sqlite)  

### P2 — Phase 3 heart

9. `Goal` + `Task` models + SQLite  
10. Planner producing step list  
11. Bounded agent loop with cancel + max steps + checkpoint  
12. Runtime Supervisor skeleton (startup checks, idle, shutdown drain)  

### P3 — Phase 5–6 architecture order

13. Event bus (in-process first)  
14. Workflows  
15. Plugin manifests  
16. Multi-agent only after eval proves need  

### Do **not** do early

- Unrestricted shell/code tools  
- Hundreds of Agency Agents loaded every turn  
- Copying IRIS/ROCKY/Stonic privileged patterns  
- Binding core on `0.0.0.0` in real user installs without auth  

---

## 10. Suggested mapping: keep / rewrite / add

| Component | Decision |
|---|---|
| `ProviderRouter` + providers | **Keep** — becomes Module 07 |
| `ToolRegistry` + pydantic schemas | **Keep** — extend metadata for Module 10 |
| `CommandExecutor` allowlists | **Fold into Policy + Execution adapters** |
| `AssistantOrchestrator.handle_request` | **Split**: Router → Core → (Agent later) → Response |
| `memory/*` | **Keep** — Module 19 base |
| `voice_*` / `tts_*` / `live/*` | **Keep** — Modules 01/17 (Windows-first) |
| Flutter + web UIs | **Keep**; add approval/activity panels |
| Node duplicate server AI | **Converge** on Python core as single brain long-term, or generate shared contract tests |
| Policy / Planner / Tasks / Supervisor / Events | **Add new packages** |

---

## 11. One-page target picture

```text
                    ARCHITECTURE v1.0 TARGET
┌─────────────────────────────────────────────────────────────┐
│ Runtime Supervisor                                          │
│  Identity/Admission → Router(FAST/CORE/AGENT/EVENT)         │
│  Context/Trust → Core Understanding → Model Gateway         │
│  Goal/Task → Planner → Agent Runtime                        │
│  Tool Registry → Policy/Approval → Sandboxed Exec           │
│  Observe → Verify → Memory → Response/Voice                 │
│  Event Bus / Workflows / Audit / Plugins                    │
└─────────────────────────────────────────────────────────────┘

                    CURRENT v6.0.5 SLICE
┌─────────────────────────────────────────────────────────────┐
│ FastAPI lifespan                                            │
│  session_id → local intents OR provider chat                │
│  memory recall/control                                      │
│  4 allowlisted tools + explicit-call guard                  │
│  TTS/STT/Live (Windows-oriented)                            │
│  Flutter UI + web preview                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Bottom line

- **`FRESHY_Architecture_v1.0.md`** is the correct north star.  
- **`freshy AI architecture.txt`** confirms the same v1.0 visually and also archives older drafts — do not treat drafts as competing finals.  
- **v6.0.5 code** is a **valuable, relatively safe assistant MVP** with real chat/tools/memory/voice — but it implements only a **slice** of the 27-module system.  
- The largest strategic mistake to avoid: adding more powerful tools (browser/OS/files) **before** Policy Engine + Verification + Task bounds.  
- The largest strategic win available now: **refactor current allowlists + orchestrator guards into Architecture Modules 04/10/12/13** without breaking the running Linux web preview / core demo.

---

## 13. Appendix — key file index (current code)

| Area | Paths |
|---|---|
| Core API | `freshy_core/main.py` |
| Config/secrets | `freshy_core/config.py`, `.env.example` |
| Orchestrator | `freshy_core/ai/assistant_orchestrator.py` |
| Providers | `freshy_core/ai/provider_router.py`, `*_provider.py` |
| Tools | `freshy_core/tools/registry.py`, `schemas.py` |
| Executor | `freshy_core/executor.py` |
| Intents | `freshy_core/intents.py` |
| Memory | `freshy_core/memory/*` |
| Voice/TTS/Live | `voice_input_service.py`, `tts_service.py`, `live/*` |
| Flutter UI | `freshy_app/lib/*` |
| Web preview | `server.ts`, `src/App.tsx`, `src/server/ai/*` |
| Tests | `freshy_core/tests/*`, `src/**/*.test.ts` |
| Architecture | `/FRESHY_Architecture_v1.0.md`, `/freshy AI architecture.txt` |

---

*End of gap map.*
