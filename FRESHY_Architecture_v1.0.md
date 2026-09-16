# 🤖 FRESHY — MASTER ARCHITECTURE v1.0

> **Recommendation:** Yeh architecture tumhare banaye hue saare versions (simple flow → 15-layer → 18-layer → 23-layer → 26-layer) ka final aur sabse mature version hai. Baaki sab iske *drafts* hain. Isme 3 aise critical design decisions hain jo pehle versions mein nahi the:
>
> 1. **Policy / Permission Engine LLM ke BAHAR hai (deterministic).** LLM sirf action *propose* karta hai; execute karne ki permission policy engine deti hai. LLM apne aapko permission nahi de sakta.
> 2. **Intelligent Request Router (Fast / Core / Agent / Event).** Har request bhaari agent loop se nahi guzarti — simple cheezein fast path se nikal jaati hain, complex cheezein agent path mein.
> 3. **Runtime Supervisor + Modular Monolith + 6-phase build.** Production-grade lifecycle (startup / shutdown / crash recovery) aur realistic MVP (27 alag servers nahi, ek app ke andar clear modules).
>
> **Implementation shape:** Modular monolith. Shuruaat mein ek application ke andar clear modules rakho. Event bus pehle *in-process* ho sakta hai — 27 separate servers ki zaroorat nahi.

---

## 🧭 Core Design Principles (ye sabse important hain)

| Principle | Meaning |
|---|---|
| **Default Deny / Least Privilege** | Kuch allowlist na ho to block. Har tool ko minimum zaroorat bhara access mile. |
| **LLM Proposes, Policy Decides** | Model action suggest kare, execute authority alag deterministic gate se mile. |
| **Read ≠ Write** | File/network read aur write permission alag-alag check honi chahiye. |
| **Verify, Don't Trust** | "Model ne bola done" = proof nahi hai. Actual state check karo. |
| **External Content = Untrusted** | Web pages, tool output, file content = data hain, instruction nahi. Inse system permission override nahi ho sakti. |
| **Local-Only Data** | Local-only marked data cloud ko silently fallback nahi kar sakta. |
| **Bounded Autonomy** | Max steps, retry limits, deadline, cost budget. Self-expansion / self-granted access mana hai. |
| **Approval Is Specific** | Approval action + arguments + expiry ke saath bound hoti hai. Changed action → recheck. |

---

## 🗺️ High-Level Flow

```
👤 USER / AUTHORIZED EVENT
        │
        ▼
NORMALIZE REQUEST
        │
        ▼
AUTHENTICATE + ADMIT + SET SCOPE
        │
        ▼
ROUTE REQUEST  ──► FAST PATH | CORE PATH | AGENT PATH | EVENT PATH
        │
        ▼
SCOPED CONTEXT + AUTHORIZED MEMORY
        │
        ▼
CHECK CAPABILITIES → PROPOSE PLAN → PROPOSE TOOL ACTION
        │
        ▼
VALIDATE TOOL + ARGS → POLICY + PRIVACY CHECK
        │
   ┌────┴────┐
 BLOCK   NEED APPROVAL / ALLOW
   │            │
 EXPLAIN     WAIT FOR USER → (DENIED=STOP | APPROVED=CHECKPOINT+EXECUTE)
                   │
                   ▼
              OBSERVE → VERIFY
                   │
        ┌──────────┼──────────┐
     SUCCESS    PARTIAL     UNKNOWN / FAILED
        │          │              │
   PERSIST RESULT  └──► RECORD STATE → RECOVER/REPLAN? → STOP/ASK
        │
   MORE STEPS? ──YES──► NEXT ACTION (recheck policy)
        │
       NO
        ▼
CONTROLLED MEMORY UPDATE → RESPONSE ENGINE → TEXT / VOICE → 👤 USER
```

---

## 📦 Module Breakdown (27 Modules)

### PART A — INPUT, IDENTITY & ROUTING

**01. 🎙️ Perception & Input Gateway**
- Text / microphone / audio stream / app interface input.
- STT adapters: Whisper / Vosk / cloud STT. VAD, wake word, language detection (Hindi / Hinglish / English).
- Input validation, size limits, request IDs, source label (USER / DEVICE / WEBHOOK / SCHEDULE).
- **Output:** Normalized Request / Event.

**02. 🎤 Speaker Identity Service** *(voice input only)*
- Consent-based voice enrollment → speaker embeddings → personal voice profile.
- Runtime verification: speaker match, confidence, anti-spoof signals.
- Voice match = identity signal, **NOT** strong authentication. Text/API use their own auth.

**03. 🪪 Identity, Session & Request Admission**
- User / device / session identity. Login, tokens, passkeys, session expiry.
- Authenticated principal, roles, permission scope.
- Event source auth, replay protection, rate limits, guest restrictions.
- Unknown identity → restricted mode / request auth. Sensitive actions → stronger auth.

**04. 🔀 Intelligent Request Router**
- Classify request, estimate complexity, detect ambiguity, ask clarification if needed.
- **FAST PATH** → simple local capability. **CORE PATH** → chat / knowledge / retrieval. **AGENT PATH** → multi-step / planning / tool use. **EVENT PATH** → authorized workflow / scheduled job.
- Every route preserves identity, scope, privacy rules. Fast path NEVER bypasses tool permission checks.

---

### PART B — CONTEXT, INTELLIGENCE & ACTION CONTROL

**05. 🧩 Context & Trust Manager**
- Conversation / request / task / goal / time context + authorized user preferences + device/environment state.
- Context budget, summarization, relevance filtering, source/timestamp/trust labels, data classification.
- User & workspace isolation. External files/web/tool output = **untrusted**; cannot override system permissions.
- **Output:** Scoped, source-tagged context.

**06. 🧠 Freshy Core — Request Understanding**
- Intent, desired outcome, constraints, preferences, ambiguity detection, capability awareness.
- Decide: RESPOND / CLARIFY / PROPOSE TOOL ACTION / CREATE TASK.
- Core proposes actions; **cannot grant itself permissions**.

**07. 🤖 Model Gateway & Provider Orchestration**
- Unified model interface. Cloud APIs (Gemini / Groq / OpenRouter / SambaNova / Mistral) + open-weight / local models.
- Route by: capability, quality, latency, cost, context. Structured output, streaming, tool-calling compatibility.
- Health checks, rate limits, circuit breakers. Fallback preserves privacy rules + data residency.
- Local-only data → never silently fall back to cloud. Invalid output → reject/repair within retry limits.

**08. 🎯 Goal & Task Manager**
- User-authorized goals: scope, priority, deadline, completion criteria, dependencies, progress.
- States: `CREATED → READY → RUNNING → WAITING_APPROVAL → COMPLETED / PARTIAL / FAILED / CANCELLED / EXPIRED`.
- Time/cost/step budgets, approval requirements. Goal change outside scope → new authority.

**09. 📋 Planner**
- Goal → steps → dependencies → proposed tool actions.
- Consult available capabilities BEFORE committing to a plan. Define expected results + verification checks.
- Estimate risk / cost / required permissions. Sequential / parallel where safe.
- Replan using observed evidence. Unsupported goal → clarify / narrow / explain limit.
- **Output:** Structured plan — NOT executable authority.

**10. 🔧 Capability & Tool Registry**
- Capability catalog: AVAILABLE / UNAVAILABLE / RESTRICTED / DEGRADED.
- Every tool defines: name, version, description, typed I/O schema, required permissions, allowed resource scope, risk, timeout, cost estimate, side effects, idempotency, retry rules, verification method, sandbox profile, execution adapter, health status.
- Registry metadata controlled by trusted application code.

**11. 🤖 Agent Runtime — Bounded Task Controller**
- Load task → plan → propose action → request authorization → execute approved action → observe → verify → update state.
- Max steps, retry limits, deadline, cost budget, cancellation, pause/resume, human escalation.
- **MVP:** single agent. Later: specialist / parallel / sub-agents IF tests show value.
- Sub-agent permissions ⊆ parent. Delegation cannot expand scope or reset budgets. No unbounded retry / self-expansion.

**12. 🔐 Policy, Permission & Approval Engine**
- **Deterministic enforcement OUTSIDE the LLM.**
- Check identity, session, task scope, tool permission. Validate arguments (file paths, URLs, destinations). Check data sensitivity, network rules, resource limits. Classify side effects, detect required approval.
- Default deny, least privilege, allowlisted resources. Read and write checked separately.
- Approval shows: action, target, data, cost, risk. Bound to specific action + args + expiry. Changed action/retry/fallback → recheck.
- `❌ BLOCK | ⚠️ ASK APPROVAL | ✅ AUTHORIZE`.

**13. ⚡ Sandboxed Execution Engine**
- Execute *registered tools*, not unrestricted model text. Revalidate authorization at execution boundary.
- Scoped credentials supplied by trusted adapters. Restricted filesystem / network / isolation.
- Timeout, cancellation, resource cleanup. Idempotency keys. Unknown outcome → inspect state before repeat.
- **Output:** Execution record + captured result.

**14. 👁️ Observation & Result Normalization**
- Tool output, exit status, API response, process/file/app/device state.
- Normalize, attach source + timestamp, redact secrets, bound output size.
- Returned content = data, not trusted instruction.
- **Output:** Evidence for verification.

**15. 🔍 Verification & Recovery Engine**
- Compare expected result vs observed evidence. Schema checks, tests, read-back, state comparison.
- Partial failure / unexpected side effects / uncertainty handled.
- Prefer deterministic checks. "Model said done" ≠ completion.
- VERIFIED → complete. PARTIAL → record/recover/ask. UNKNOWN → inspect/report. FAILED → bounded recovery/stop.
- Every new tool action returns through policy engine.

---

### PART C — RESPONSE & VOICE OUTPUT

**16. 💬 Response Engine**
- Hindi / Hinglish / English + user-preferred detail level.
- Clearly state: what was done, what was NOT done, what remains unknown, sources, failure explanation, next options.
- Distinguish planned / attempted / verified actions. No credentials in responses. Specific, understandable approval prompts.

**17. 🔊 Voice Output Engine**
- TTS adapter, voice + language selection. Local / approved cloud TTS, streaming, speech queue.
- Barge-in, stop/mute, mic echo handling. Sensitive content → prefer private display.
- Stop speaking ≠ cancel task. Explicit cancellation routes to runtime controller.

---

### PART D — SHARED INFRASTRUCTURE

**18. 🗃️ Durable State & Checkpoint Store**
- Task state, plan versions, step status, approval records, workflow state, execution IDs, cancellation state.
- Persist before/after important boundaries. Transactions, checkpoints, crash resume.
- After crash: reconcile pending actions before retry. DB transaction ≠ atomic external API action.

**19. 🧠 Memory & Knowledge Service**
- Working context, session summaries, long-term preferences, verified facts, task history, optional semantic retrieval.
- Source / timestamp / owner / confidence / expiry. Access control before retrieval. User/workspace isolation.
- Explicit preferences / useful outcomes → controlled writes. External instructions cannot become trusted policy memory. Memory storage does NOT auto-train model weights.

**20. ⚙️ Automation & Workflow Service**
- Trigger → validate event → condition → authorized task.
- One-time / recurring / cron / webhook / device / app event. Foreground / background jobs.
- Each workflow: owner, scope, permissions, limits, expiration, notification rules, pause/disable, approval policy.
- Permission revoked → future execution blocked. Event content ≠ user instruction.

**21. 🚌 Event Bus & Delivery Control**
- Typed events, event IDs, task/request correlation, source identity, timestamp, schema version.
- Producer → validated event → queue → authorized consumer. Acks, deduplication, backpressure, bounded retries, dead-letter queue.
- Consumers tolerate duplicate delivery. Avoid assuming exactly-once.

**22. 🧵 Concurrency & Resource Manager**
- Priority queue, worker pool, scheduling. CPU/RAM/GPU/storage/network/provider quotas.
- Locks, semaphores, per-user/per-task budgets, conflicting-action detection, bounded parallelism.
- Timeouts, cancellation propagation, cleanup. Foreground responsiveness + background throttle.

**23. 🔑 Secrets & Configuration Manager**
- API keys, OAuth tokens, provider/tool config. OS keychain / secret store, rotation, scoped credentials.
- Schema validation, versioning, safe runtime reload. Dev/test/prod separation.
- Credentials only to authorized adapters. Never deliberately insert secrets into model context. Redaction + tests for accidental log/UI exposure.

**24. 🛡️ Privacy & Data Governance**
- Classification: Public / Private / Sensitive. Consent, purpose limits, data minimization.
- Encryption at rest / in transit, access control. Provider/tool egress checks before sending data.
- Local-only policies, voice protection, retention, export/correction/deletion. Applies to context, memory, logs, tools, TTS.

**25. 🩺 Health, Observability & Audit**
- Provider / tool / queue / DB / worker health. Latency, cost, token usage, errors, resource metrics.
- Correlated action trace: Request → Plan → Approval → Tool → Evidence → Final Status.
- Structured decision summaries (not hidden model thoughts). Redacted logs, retention limits, integrity-protected audit for sensitive actions. Alerts, circuit breakers, controlled recovery.

**26. 🧪 Evaluation & Controlled Improvement**
- Unit / integration / E2E task suites. Permission, prompt-injection, failure, crash-recovery, duplicate-event, cancellation tests.
- Measure: task success, false completion, unauthorized actions, latency, cost, privacy leakage, recovery quality.
- Feedback → curated changes → offline eval → review → versioned release → monitor → rollback if needed.
- No unreviewed self-modification of safety/permissions. Fine-tuning optional, separate, eval-gated.

**27. 🧩 Plugin & Connector Lifecycle Manager**
- Install / review / register / update / disable / remove. Tool manifests, versions, dependencies, compatibility.
- Trusted-source verification, permission review, isolation, health checks, revocation.
- Plugin descriptions do NOT grant execution privileges. New/higher-risk permissions → explicit approval.

---

## 🔄 FRESHY — MASTER CONTROL LOOP (the heart)

```
👤 USER / AUTHORIZED EVENT
        │
        ▼
NORMALIZE REQUEST
        │
        ▼
AUTHENTICATE + ADMIT + SET SCOPE
        │
        ▼
ROUTE REQUEST
   ┌────────────┼────────────┐
   ▼            ▼            ▼
DIRECT TOOL   CONVERSATION   TASK / WORKFLOW
 HANDLER           │              │
   │              ▼              ▼
   │        SCOPED CONTEXT   CREATE / LOAD TASK
   │              │              │
   │              ▼              ▼
   │        ANSWER / CLARIFY  LOAD CONTEXT + AUTHORIZED MEMORY
   │              │              │
   │              │              ▼
   │              │        CHECK CAPABILITIES
   │              │              │
   │              │              ▼
   │              │          PROPOSE PLAN
   │              │              │
   └──────────────┼────► PROPOSE TOOL ACTION
                  │              │
     Tool needed? ┘              ▼
                       VALIDATE TOOL + ARGS
                              │
                              ▼
                   POLICY + PRIVACY CHECK
         ┌────────────────────┼──────────────┐
         ▼                    ▼              ▼
       BLOCK            NEED APPROVAL       ALLOW
         │                    │              │
         ▼                    ▼              │
  EXPLAIN / STOP       WAIT FOR USER        │
                            │                │
              DENIED ───────┤                │
                 │          │ APPROVED       │
                 ▼          └──────┬─────────┘
                STOP               │
                                   ▼
                      CHECKPOINT INTENT
                                   │
                                   ▼
                    REVALIDATE + EXECUTE
                                   │
                                   ▼
                             OBSERVE
                                   │
                                   ▼
                              VERIFY
          ┌──────────────┬─────────┼─────────────┐
          ▼              ▼         ▼             ▼
       SUCCESS        PARTIAL   UNKNOWN        FAILED
          │              │         │             │
          ▼              └─────────┴──────┬──────┘
    PERSIST RESULT                          │
          │                                 ▼
          ▼                       RECORD OBSERVED STATE
     MORE STEPS?                           │
     /         \                           ▼
   YES          NO              RECOVERY POSSIBLE WITHIN SCOPE/LIMITS?
    │            │                    /            \
    ▼            ▼                  YES            NO
NEXT ACTION   COMPLETE            RECOVER/REPLAN  STOP / ASK
    │            │                    │              │
    │            ▼                    │              │
    │     CONTROLLED MEMORY UPDATE     │              │
    │            │                    │              │
    │            ▼                    │              │
    │      RESPONSE ENGINE ◄──────────┼──────────────┘
    │            │                    │
    │        TEXT / VOICE             │
    │            │                    │
    │            ▼                    │
    │          👤 USER                │
    │                                 │
    └──────► PROPOSE TOOL ACTION ◄────┘
              │
              └── ALWAYS RECHECK POLICY
```

> **Autonomous mode:** User ke bina bhi `EVENT → EVENT ENGINE → FRESHY CORE → MEMORY → REASON → PLAN → SAFETY → AGENT → TOOLS → EXECUTE → OBSERVE → VERIFY → MEMORY UPDATE → RESPONSE / NOTIFICATION → USER`.

---

## ⚙️ FRESHY — RUNTIME SUPERVISOR

```
╔════════════════════════════════════════════════════════════╗
║                  FRESHY RUNTIME SUPERVISOR                 ║
╠════════════════════════════════════════════════════════════╣
║ STARTUP                                                      ║
║  ├─ Validate Configuration                                  ║
║  ├─ Initialize Identity, Policy & Privacy Controls          ║
║  ├─ Connect State Store / Memory / Secret Store            ║
║  ├─ Register Approved Tools & Plugins                      ║
║  ├─ Start Event Consumers / Scheduler / Worker Pool         ║
║  └─ Reconcile Interrupted Tasks Safely                     ║
║                                                             ║
║ RUNTIME                                                      ║
║  ├─ Accept Requests & Authorized Events                    ║
║  ├─ Monitor Health, Quotas & Queue Pressure                ║
║  ├─ Apply Permission Revocations                          ║
║  ├─ Restart Eligible Failed Workers Within Limits         ║
║  ├─ Handle Pause / Cancel / Emergency Stop                 ║
║  └─ Stay Idle When No Work Exists                          ║
║                                                             ║
║ SHUTDOWN                                                     ║
║  ├─ Stop Accepting New Work                                ║
║  ├─ Drain or Cancel Running Tasks                          ║
║  ├─ Persist Checkpoints & Flush Audit Events              ║
║  └─ Release Resources                                      ║
║                                                             ║
║ Continuous Availability ≠ Continuous LLM Thinking          ║
║ Recovery Must Not Override an Intentional User Shutdown    ║
╚════════════════════════════════════════════════════════════╝
```

---

## 🏗️ Implementation Shape (Modular Monolith)

Ek application ke andar clear modules. Pehle in-process event bus. 27 separate servers ki zaroorat nahi.

```
                    FRESHY APPLICATION
                            │
   ┌─────────────┬──────────┼───────────┬──────────────┐
   ▼             ▼          ▼           ▼              ▼
Interfaces     AI / Core   Task Runtime  Security      Infrastructure
   │             │          │           │              │
Text/Voice    Context      Planner     Identity       State Store
App/API       Models       Agent Loop  Policy         Memory Store
Events        Responses    Tools       Privacy        Event Bus
                           Verification Secrets        Scheduler
                                                       Audit / Metrics
```

---

## 🛠️ Recommended Build Sequence

| Phase | Deliverable |
|---|---|
| **1 — Foundation** | Text input, identity/scope, one model, configuration, basic state and logs |
| **2 — Controlled Tools** | Registry, policy gate, time tool, restricted file reading, reminders, verification |
| **3 — Reliable Tasks** | Planner, bounded agent loop, checkpoints, cancellation, safe recovery |
| **4 — Personal Assistant** | Voice, scoped memory, preferences, stronger sensitive-action authentication |
| **5 — Automation** | Durable workflows, authenticated events, background processing and revocation |
| **6 — Expansion** | Additional providers, plugins, device integrations; multi-agent only if tests show value |

---

## 🔌 Practical Tech Mapping (tumhare available tools ke hisaab se)

| Architecture piece | Suggested tech (free / tumhare paas) |
|---|---|
| **Model Gateway (07)** | Gemini / Groq / OpenRouter via unified Python client. Router by task type. |
| **Web / Research Tool** | Tavily (free tier) ya web_search. |
| **File Tool** | Restricted filesystem writes under a root/work folder. |
| **Telegram Tool** | Bot token + chat ID → send to Saved Messages (`chat_id = "me"`). |
| **Voice (17)** | Gemini TTS / gTTS / XTTS local. STT: Whisper / Vosk. |
| **Web UI (Interface)** | Flask/FastAPI + simple HTML/JS chat (no heavy framework). |
| **State/Memory (18/19)** | SQLite + JSON files (MVP); later vector store for semantic memory. |
| **Policy Gate (12)** | Plain Python allowlist + per-tool permission config (no LLM). |
| **Secrets (23)** | `.env` / env vars; never logged or sent to model. |

---

## ✅ Summary — kyun ye best hai

- **Sabse complete:** saare pehle versions ke achhe ideas (loop, memory, planner, tools, voice) isme absorb hain.
- **Sabse safe:** policy engine LLM ke bahar + verify-don't-trust + local-only protection.
- **Sabse practical:** request router (fast/core/agent/event) + modular monolith + 6-phase build = asli MVP ban sakta hai bina over-engineering ke.
- **Sabse production-ready:** runtime supervisor (startup/shutdown/crash recovery) + audit + observability + eval.

> **Next step:** Is architecture ko base maan kar Phase 1 (Foundation) ka working web app banate hain — text input + ek model (Gemini/Groq) + config + basic state. Uske baad Phase 2 mein controlled tools (file + telegram + search) jodenge.
