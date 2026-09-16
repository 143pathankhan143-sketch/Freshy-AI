# 📱 FRESHY — FLUTTER MOBILE BUILD PLAN v1.0
> Base: `FRESHY_Architecture_v1.0.md` (27 modules, modular monolith)
> Target: **Flutter mobile app** (Android-first)
> Rule: **Har phase ek hi baithak mein complete ho sake** — isliye har phase mein Entry Criteria, Scope IN, Scope OUT, DoD (Definition of Done) aur Demo script hai.

---

# PART 1 — Architecture Review (honest opinion)

## ✅ Jo zabardast hai (inhe chhedna nahi hai)

| # | Decision | Kyun sahi hai |
|---|---|---|
| 1 | **Policy Engine LLM ke BAHAR (deterministic)** | Ye is doc ka sabse strong point hai. LLM sirf propose karta hai, execute ka authority code deta hai. Prompt injection se bachne ka yahi ek reliable tareeka hai. |
| 2 | **Intelligent Request Router (Fast/Core/Agent/Event)** | Har "time kya hai" ko agent loop mein bhejna paisa + battery dono jalana hai. Ye decision mobile pe aur bhi critical hai. |
| 3 | **Modular Monolith (27 servers nahi)** | Sahi MVP decision. Mobile ke liye to aur bhi sahi — poora core ek hi Dart codebase mein rahega. |
| 4 | **Verify, Don't Trust + Approval = action+args+expiry** | "Model ne bola done" ko proof na maanna — ye agents ke sabse common failure (false completion) ko rokta hai. |
| 5 | **Bounded Autonomy (steps/budget/deadline)** | Mobile pe cost aur battery dono ke liye zaroori. |
| 6 | **Runtime Supervisor (startup reconcile)** | Mobile mein app kabhi bhi kill ho sakti hai — ye concept mobile pe *aur zyada* important hai, server se bhi zyada. |

**Concept score: 9/10.** Safety design genuinely production-grade socha gaya hai.

## ⚠️ Jo problem hai (mobile ke liye fix karna padega)

1. **Tech Mapping poora Python/Web hai** — doc mein Flask/FastAPI, Python client, gTTS, `.env`, "Phase 1 = web app" likha hai. Flutter ke liye ye **0% applicable** hai. Doc ka apna "Next step" (web app banana) tumhare mobile goal se contradict karta hai. → Fix: **Part 3 ka Flutter mapping** use karo.
2. **`.env` secrets mobile pe GALAT hai** — APK ke andar bundled keys koi bhi extract kar sakta hai. → Fix: `flutter_secure_storage` (Android Keystore / iOS Keychain) + `--dart-define` dev injection. Public release se pehle API-proxy consider karna (Phase 7 note).
3. **Mobile background limits ka zikr hi nahi** — ye sabse bada architectural gap hai:
   - Phone **webhook directly receive nahi kar sakta** → Phase 5 ke automation/webhooks ke liye ek chhota cloud endpoint (FCM push ke through) zaroori hai.
   - Android `WorkManager` ke periodic jobs minimum **15 min** interval ke hote hain; exact-time jobs ke liye alag strategy chahiye.
   - iOS pe background execution bahut restricted hai → **Android-first** decision.
4. **On-device heavy models (Whisper/open-weight LLM) mobile MVP ke liye realistic nahi** — battery/RAM khayenge. → MVP: platform STT (`speech_to_text`) + cloud LLM. Local models Phase 7 ka optional experiment.
5. **27 modules → phases ka mapping missing hai** — doc mein 6-phase table hai, par ye nahi bataya ki kaunsa module kis phase mein banta hai. Bina iske "ek phase ek baar mein complete" possible nahi. → Fix: **Part 4 coverage matrix**.
6. **Mobile-specific cheezein missing hain:** offline/degraded behavior, push notifications, biometric auth, mic permission UX, Play Store data-safety, app lifecycle mapping. → Sab phases mein add kar diye hain.

**Verdict:** Architecture *soch* ke level pe excellent hai — principles bilkul mat badalna. Par *implementation* section Python-web ke liye likha gaya tha. Neeche ka plan wahi architecture Flutter pe sahi tareeke se utarta hai.

---

# PART 2 — Key Decisions & Assumptions

> ⚠️ Ye maine assume kiye hain. Koi bhi galat ho to batao, plan update kar dunga.

| # | Decision | Reason |
|---|---|---|
| D1 | **Android-first**, iOS codebase ready rahega par test/release baad mein | iOS background restrictions Phase 5 ko kaafi limit karte hain; testing ke liye ek device kaafi |
| D2 | **Solo developer** (AI-assisted coding) | Timeboxes isi hisaab se hain |
| D3 | **Phase 0–4 tak koi backend NAHI** — app directly cloud LLM APIs (Gemini/Groq) call karegi | Personal-use MVP; infra cost zero |
| D4 | **Phase 5 mein minimal serverless** (Firebase: FCM + 1-2 Cloud Functions) — sirf webhook/push ke liye | Phone webhook receive nahi kar sakta, ye physics hai 😄 |
| D5 | MVP mein **on-device LLM nahi** | Battery/RAM/quality tradeoff MVP ke liye sahi nahi |
| D6 | **Personal use MVP → Phase 7 mein Play Store release** | Release ke apne checks hote hain (data safety, policies) |
| D7 | Responses **Hindi / Hinglish / English** | Architecture ka requirement |

---

# PART 3 — Flutter Tech Stack (Module → Tech Mapping)

| Architecture piece | Flutter/Dart tech |
|---|---|
| **Core brain (Router, Planner, Agent, Policy, Memory)** | **Pure Dart packages** (no Flutter import) → unit-testable bina emulator ke; kal ko backend mein bhi lift ho sakta hai |
| State management | Riverpod (+ Freezed for models) |
| Navigation | go_router |
| Local DB (18/19 — state, checkpoints, memory) | **drift** (SQLite, type-safe) |
| Secrets (23) | **flutter_secure_storage** (Keystore/Keychain); dev keys `--dart-define` se |
| HTTP + streaming | **dio** (SSE streaming for LLM tokens) |
| Model Gateway (07) | `google_generative_ai` (Gemini) + Groq via REST; unified `LlmProvider` interface |
| STT (01) | `speech_to_text` (platform engines — Hindi/English support); Whisper experiment Phase 7 |
| TTS (17) | `flutter_tts` (platform voices); queue + barge-in app-level |
| Notifications + reminders | `flutter_local_notifications` (+ exact alarms for scheduled tasks) |
| Background jobs (20) | `workmanager` (Android WorkManager) + exact alarm strategy |
| Push / webhook bridge (20/21) | `firebase_messaging` + Cloud Function endpoint (Phase 5) |
| Biometric auth (03) | `local_auth` (fingerprint for sensitive approvals) |
| Event Bus (21) | In-process: typed Dart **Streams** (broadcast) + drift-persisted outbox |
| Crash + observability (25) | Phase 1: structured file logs; Phase 6: **Sentry** + audit DB |
| Testing (26) | `flutter_test`, `mocktail`, `integration_test`; eval suite = mocked-LLM golden tasks in CI |
| CI | GitHub Actions: `flutter analyze` + `dart test` + APK build on every push |

### Project structure (monorepo, local packages)

```
freshy/
├── apps/
│   └── freshy_app/            # Flutter UI (screens, widgets, voice UI)
├── packages/
│   ├── freshy_core/           # PURE DART: router, planner, agent runtime,
│   │                          #   policy engine, context, memory, tool registry
│   ├── freshy_tools/          # tool implementations (time, notes, reminder...)
│   └── freshy_infra/          # drift DB, secure storage, HTTP/LLM gateway, logging
├── docs/adr/                  # Architecture Decision Records (har bada decision yahan)
└── .github/workflows/         # CI
```

> **Kyun packages?** `freshy_core` mein Flutter ka ek bhi import nahi hoga → policy engine, planner, agent loop sab `dart test` se milliseconds mein test honge. Ye is project ka sabse important structural decision hai.

---

# PART 4 — 27 Modules → Phase Coverage Matrix

| Mod | Module | Phase (version-wise) |
|---|---|---|
| 01 | Perception & Input | **P1** (text) → **P4** (voice/STT) |
| 02 | Speaker Identity | **P7** (optional — sirf zaroorat pade to) |
| 03 | Identity & Admission | **P1** (single-user device profile) → **P4** (biometric for sensitive) |
| 04 | Request Router | **P1** (core path) → **P2** (fast path) → **P3** (agent path) → **P5** (event path) |
| 05 | Context & Trust Manager | **P3** (basic) → **P4** (budget, summarization, trust labels) |
| 06 | Freshy Core (understanding) | **P1** |
| 07 | Model Gateway | **P1** (1 provider) → **P3** (fallback) → **P7** (multi-provider routing) |
| 08 | Goal & Task Manager | **P3** |
| 09 | Planner | **P3** |
| 10 | Tool Registry | **P2** |
| 11 | Agent Runtime | **P3** |
| 12 | Policy & Approval Engine | **P2** (core) — har phase extend hota hai, rewrite nahi |
| 13 | Sandboxed Execution | **P2** |
| 14 | Observation & Normalization | **P2** |
| 15 | Verification & Recovery | **P2** (basic) → **P3** (full recovery) |
| 16 | Response Engine | **P1** (v0) → **P4** (language/detail polish) |
| 17 | Voice Output (TTS) | **P4** |
| 18 | Durable State & Checkpoints | **P1** (basic) → **P3** (checkpoints + crash resume) |
| 19 | Memory & Knowledge | **P4** |
| 20 | Automation & Workflows | **P5** |
| 21 | Event Bus | **P3** (in-process) → **P5** (persisted + external events) |
| 22 | Concurrency & Resources | **P3** (single worker queue) → **P5** (background throttle) |
| 23 | Secrets & Config | **P0** (setup) → **P1** (use) |
| 24 | Privacy & Governance | Principles **P0** se; formal export/delete/redaction **P6** |
| 25 | Health & Observability | **P1** (logs) → **P6** (audit, traces, Sentry, cost dashboard) |
| 26 | Evaluation | **Continuous** (har phase ke DoD mein tests); formal eval suite **P6** |
| 27 | Plugin Lifecycle | **P7** (manifest-based feature packs — mobile pe dynamic code loading allowed nahi, honest note) |

✅ Koi module drop nahi hua — sab cover hain, bas versions mein split hain.

---

# PART 5 — Phase Plan (Phase 0 → Phase 7)

> Format har phase ka same hai: **Entry → Goal → Scope IN → Scope OUT → Tasks → DoD → Demo → Timebox**.
> "Scope OUT" deliberately likha hai — scope creep is project ka sabse bada killer hoga.

---

## 🟢 PHASE 0 — Blueprint & Skeleton (koi feature nahi, sirf neev)

**Entry:** Kuch nahi — yahi起点 hai.
**Goal:** Project skeleton + saare foundational decisions locked + CI green. Baad ke har phase ka kaam yahan se directly start ho.

**Scope IN:**
- [ ] Flutter stable + Android SDK + physical device/emulator setup
- [ ] GitHub repo + branch strategy (`main` + `phase/N` branches)
- [ ] Monorepo scaffold: `apps/freshy_app` + `packages/freshy_core` (pure Dart) + `packages/freshy_infra`
- [ ] `analysis_options.yaml` (strict lints), folder conventions
- [ ] CI: GitHub Actions → analyze + test + debug APK build
- [ ] Secrets infra: `SecretStore` wrapper over `flutter_secure_storage` + `--dart-define` dev fallback; `.env` kabhi commit nahi hoga
- [ ] API keys register: **Gemini (free tier)** + **Groq (free tier)**
- [ ] ADR docs: `docs/adr/0001-stack.md` (D1–D7 decisions record)
- [ ] App shell: name "Freshy", placeholder theme/icon, empty Home screen

**Scope OUT:** ❌ Chat, LLM calls, DB, tools, voice — kuch bhi functional nahi.

**DoD:**
1. `flutter run` se app device pe khulti hai (empty home)
2. CI pipeline green (analyze + test + APK)
3. Secret round-trip test pass: key save → app kill → reopen → key read ✅
4. ADR-0001 committed with D1–D7

**Demo:** App launch + settings placeholder + CI badge green.
**Timebox:** 2–3 din.

---

## 🟢 PHASE 1 — Foundation Chat (text in → model out)

**Entry:** Phase 0 DoD complete.
**Goal:** Ek reliable, streaming chat app — history persist ho, provider switch ho, errors gracefully handle hon. Ye "walking skeleton" hai jispe baaki sab chadhega.

**Scope IN (modules: 01-text, 03-v0, 04-v0, 06-v0, 07-v1, 16-v0, 18-v0, 25-v0):**
- [ ] `freshy_core`: `NormalizedRequest`, `RequestRouter` v0 (sab kuch CORE PATH), `LlmProvider` interface
- [ ] `freshy_infra`: Gemini provider (streaming SSE), Groq provider; timeout/retry/error taxonomy (rate-limit vs auth vs network)
- [ ] drift DB: `conversations`, `messages` tables + `ChatRepository`
- [ ] UI: Chat screen (streaming bubble), conversation list, Settings (API key entry → secure storage, provider/model picker)
- [ ] Response engine v0: markdown render; error pe honest Hindi/Hinglish message ("kya hua, kya nahi hua")
- [ ] Structured request-ID logs (rotating file) + per-message token usage store
- [ ] Tests: gateway contract tests (mock server), repository tests

**Scope OUT:** ❌ Tools, policy, planner, voice, memory, automation, multi-user.

**DoD:**
1. Cold chat with streaming works (Gemini + Groq dono)
2. App force-kill → reopen → poori history intact
3. Settings se provider switch live kaam karta hai
4. Wrong API key → clear Hinglish error, crash nahi
5. Token usage har message pe record hota hai
6. CI green

**Demo script:** Naya conversation → "Freshy kaun hai?" → streaming reply → app kill → reopen → history dikhti hai → Groq pe switch → reply.
**Timebox:** 1.5–2 hafte.

---

## 🟢 PHASE 2 — Controlled Tools (Policy Engine ka janm) ⭐

**Entry:** Phase 1 DoD complete.
**Goal:** Freshy pehli baar *kuch karta* hai — par har action policy gate se guzarta hai. Ye is project ka safety heart hai, isliye is phase mein tests sabse zyada honge.

**Scope IN (modules: 04-fast path, 10, 12, 13, 14, 15-v0, 23):**
- [ ] **Tool Registry**: `ToolDescriptor` — name, version, typed I/O schema, required permissions, risk level, timeout, side-effects, idempotency, verification method
- [ ] **Tools v1 (4 tools):**
  1. `get_time` (risk: none → FAST PATH, bina LLM)
  2. `calculator` (safe expression eval)
  3. `notes_write` / `notes_read` (sirf app sandbox dir; path-escape validation)
  4. `reminder_create` (flutter_local_notifications schedule)
- [ ] **Policy Engine (PURE DART, zero LLM):** rules table → `BLOCK | ASK | ALLOW`; default deny; read/write alag check; args validation; unregistered tool = hard block
- [ ] **Approval UI:** bottom sheet — action + target + args + risk dikhe; Approve/Deny; approval ticket = hash(action+args) + 60s expiry; args badle → re-approval
- [ ] **Function-calling loop v0:** LLM tool propose kare → policy → execute → result wapas → final answer (single-turn)
- [ ] **Observation normalizer:** secrets redact, output size cap, source+timestamp tag
- [ ] **Verification v0:** file likha → read-back check; reminder → actually scheduled check
- [ ] Tests: **policy matrix (kam se kam 12 cases)**, approval expiry test, "tool ne jhooth bola" test (fake success → verification catch kare)

**Scope OUT:** ❌ Multi-step planning, agent loop, checkpoints, voice, memory.

**DoD:**
1. "Abhi time kya hai" → FAST PATH, LLM call hi nahi hoti (logs se prove)
2. "Note likho: doodh lana hai" → approval sheet → approve → file bani + read-back verified
3. Unregistered tool maango → clean block explanation
4. Approval 60s expire → re-approval maangta hai
5. Policy matrix tests 100% pass; CI green

**Demo script:** Time (fast) → note write (approval flow) → deny karke dikhao → blocked tool attempt.
**Timebox:** 2 hafte.

---

## 🟢 PHASE 3 — Reliable Agent (Planner + Bounded Loop + Crash Recovery) 🧠

**Entry:** Phase 2 DoD complete.
**Goal:** Multi-step tasks — plan dikhe, bounded loop chale, **app beech mein kill ho jaye to task resume ho**. Master control loop ka asli dil yahan banta hai.

**Scope IN (modules: 04-agent path, 05-v0, 08, 09, 11, 15-full, 18-full, 21-in-process, 22-v0):**
- [ ] **Task Manager:** states (`CREATED→READY→RUNNING→WAITING_APPROVAL→COMPLETED/PARTIAL/FAILED/CANCELLED`), step/time budgets
- [ ] **Planner:** LLM se structured JSON plan (schema-validated); plan banne se pehle capability check; har step pe expected result + verification method; invalid plan → repair retry (max 2)
- [ ] **Agent Runtime:** bounded loop (max steps, deadline, budget) → **har action pe policy re-check** → execute → observe → verify → next; pause/cancel/resume
- [ ] **Checkpoints:** har step ke baad drift mein persist; **startup reconciliation** — app khulte hi RUNNING tasks detect → resume ya user se poochho
- [ ] **Event Bus v1:** typed in-process streams + correlation IDs
- [ ] **Task UI:** task list + task detail (plan steps, live status per step, evidence dikhe), Pause/Cancel buttons
- [ ] **Worker queue v0:** ek background worker, foreground ko priority
- [ ] **Model Gateway v2:** provider fallback (Gemini fail → Groq), privacy rules preserve
- [ ] Tests: **kill-mid-task resume (integration test)**, step-budget enforcement, tool-fail → replan, cancel propagation

**Scope OUT:** ❌ Voice, long-term memory, automation/scheduling, parallel agents, sub-agents.

**DoD:**
1. 3-step task (research-ish → note save → reminder) end-to-end complete, har step ka evidence UI mein dikhe
2. **Task ke beech app force-kill → reopen → task resume/ask** ⭐ (ye is phase ka headline test hai)
3. Cancel dabate hi loop rukta hai (naya action nahi)
4. Step budget khatam → task PARTIAL + honest explanation
5. Sab CI green

**Demo script:** Multi-step task start → step 2 pe app kill → reopen → resume → complete → task detail mein evidence trail.
**Timebox:** 2–3 hafte (sabse heavy phase — ye deliberate hai).

---

## 🟢 PHASE 4 — Personal Assistant (Voice + Memory + Preferences)

**Entry:** Phase 3 DoD complete.
**Goal:** Freshy ab *personal* hai — bol ke baat karo, wo tumhari preferences yaad rakhe, sensitive actions pe fingerprint maange.

**Scope IN (modules: 01-voice, 03-biometric, 05-full, 16-full, 17, 19):**
- [ ] **STT:** `speech_to_text` — Hindi + Hinglish + English recognition; push-to-talk + continuous mode; mic permission UX (pehli baar explain karo)
- [ ] **TTS:** `flutter_tts` — language/voice select, speech queue, stop button, **barge-in** (user bole → TTS turant ruke)
- [ ] **Voice Mode UI:** mic button, listening/thinking/speaking states, "stop speaking ≠ cancel task" rule
- [ ] **Memory Service:** preferences ("mujhe chhote answers chahiye"), verified facts, task history; **controlled writes** (explicit confirmation ke bina memory write nahi); memory screen (view/edit/delete entries); user isolation
- [ ] **Context Manager full:** context budget + sliding summarization; external content = untrusted tag (tool output se system prompt override nahi ho sakta)
- [ ] **Biometric gate:** `local_auth` — sensitive risk wale approvals pe fingerprint (Phase 2 ke approval flow mein hook)
- [ ] **Onboarding:** language choice, voice choice, permissions walkthrough
- [ ] Tests: memory isolation, context budget truncation, barge-in, preference-changes-behavior test

**Scope OUT:** ❌ Speaker identity (module 02 — P7 optional), automation, web research tools, multi-user.

**DoD:**
1. Voice round-trip: bol ke poochho → Hindi/Hinglish reply text + voice dono
2. "Mujhe short answers chahiye" bolo → preference save → agle answers visibly chhote
3. Memory screen se preference delete → behavior wapas
4. Sensitive action → fingerprint prompt; fail → block
5. Barge-in: TTS bolte hue interrupt karo → turant ruke, task cancel NA ho
6. CI green

**Demo script:** Voice mode on → "kal subah 8 baje mujhe gym yaad dilana" → approval (+fingerprint) → reminder set → "mujhe chhote jawab dena" → next answer chhota.
**Timebox:** 2 hafte.

---

## 🟢 PHASE 5 — Automation & Events (jab Freshy khud kaam kare) ⏰

**Entry:** Phase 4 DoD complete.
**Goal:** Scheduled + event-driven tasks — app band ho tab bhi. Ye pehla phase hai jisme chhota cloud piece aata hai (majboori hai — phone webhook sun nahi sakta).

**Scope IN (modules: 04-event path, 20, 21-full, 22-full):**
- [ ] Firebase project: **FCM** + 1 Cloud Function (webhook receiver → push)
- [ ] **Workflow Service:** trigger (time / recurring / app-event / push) → condition → authorized task; har workflow ka owner, scope, permissions, expiry, pause/disable
- [ ] **Android scheduling:** exact-time tasks via exact alarm + notification action; recurring via `workmanager` (15-min minimum constraint documented); **device reboot ke baad bhi schedule zinda**
- [ ] **Event path:** FCM push → validated event → EVENT PATH → task (with normal policy checks — event content ≠ user instruction)
- [ ] **Revocation:** workflow ki permission revoke → future runs blocked (test ke saath)
- [ ] **Automation UI:** workflow list + template-based create (v1: "daily morning summary", "reminder+action") + run history
- [ ] Result notifications (app band ho to local notification se result)
- [ ] iOS reality doc: background behavior limitations honestly documented
- [ ] Tests: scheduled fire (emulator clock trick), revocation blocks run, duplicate push → dedupe

**Scope OUT:** ❌ Visual workflow builder, third-party integrations ka mela, iOS push optimization, multi-device sync.

**DoD:**
1. "Roz subah 8 baje aaj ka plan summary" → **app closed + phone locked** → 8 baje chalta hai, notification aata hai (Android device pe prove)
2. Device reboot → schedule survive
3. Webhook test (curl → Cloud Function → FCM → app) → task create → policy check → result
4. Workflow disable/revoke → next scheduled run block + log
5. Duplicate event → ek hi baar execute
6. CI green

**Demo script:** Daily workflow banao → emulator clock aage karo → notification → revoke karo → next run blocked.
**Timebox:** 2 hafte.

---

## 🟢 PHASE 6 — Hardening, Privacy & Eval (release-worthy banana) 🛡️

**Entry:** Phase 5 DoD complete.
**Goal:** Nya feature nahi — **bharosa**. Privacy controls, audit trail, formal eval suite (including prompt-injection), crash reporting, performance pass.

**Scope IN (modules: 24, 25-full, 26-formal):**
- [ ] **Data classification:** Public / Private / Sensitive / **Local-only** tags; local-only data kabhi cloud provider ko nahi jaata (egress check + test)
- [ ] **Redaction pipeline:** logs + LLM context se secrets/PII redact (automated tests)
- [ ] **Export / Delete:** user apna saara data export (JSON) aur delete kar sake — ek screen
- [ ] **Audit & traces:** Request → Plan → Approval → Tool → Evidence → Status ka correlated trail; filterable Audit screen; cost/token dashboard
- [ ] **Sentry:** crash + error reporting (redacted)
- [ ] **Eval suite (CI mein, mocked LLM):**
  - ~20 golden task scenarios (success criteria ke saath)
  - **Prompt-injection corpus** (tool output / file content / web text mein "ignore previous instructions" style attacks) → sab BLOCK hone chahiye
  - False-completion tests (tool fail hua, agent "done" na bole)
  - Metrics: task success %, unauthorized actions (=0 target), avg cost/task
- [ ] **Performance pass:** cold start, memory, jank, battery — real device numbers record
- [ ] Security review: APK mein koi plaintext key nahi (test), allowlist enforcement re-verify
- [ ] DoD report: eval numbers ka ek `EVAL_REPORT.md`

**Scope OUT:** ❌ Naye tools, naye providers, UI redesign.

**DoD:**
1. Eval suite CI mein green: injection attacks **100% blocked**, unauthorized actions **0**
2. Export screen → valid JSON; Delete → DB clean (test prove kare)
3. Local-only marked data cloud request mein nahi jaata (test)
4. Sentry pe test crash dikhe
5. Cold start + memory numbers documented (target: cold start < 3s)
6. `EVAL_REPORT.md` committed

**Demo:** Audit screen ka trail dikhao → injection attack try karo → block + audit entry → export JSON.
**Timebox:** 1.5–2 hafte.

---

## 🟢 PHASE 7 — Expansion & Release (duniya ke liye) 🚀

**Entry:** Phase 6 DoD complete + eval report acceptable.
**Goal:** Multi-provider, optional experiments, aur **Play Store release**.

**Scope IN (modules: 02-optional, 07-multi, 27-v1):**
- [ ] **Providers:** OpenRouter / Mistral / SambaNova add; router by cost/latency/quality; per-provider circuit breaker
- [ ] **Plugin/feature packs v1:** manifest-based tool packs (Dart-defined, compile-time) — **honest note:** Play Store policy dynamic code loading allow nahi karti, isliye "plugins" = versioned feature packs, hot-loaded code nahi
- [ ] **Optional experiments (sirf agar eval value dikhaye):** on-device model (Gemini Nano / llama.cpp), speaker identity (module 02), multi-agent
- [ ] **Release engineering:** app signing, R8/obfuscation, Play Console setup, **data safety form**, privacy policy page, content policy check (AI apps pe Google ka review strict hai)
- [ ] Internal testing track → beta → staged production rollout + rollback plan
- [ ] Public release ke liye API-key strategy revisit: device keys → **proxy server** consider (keys client pe public app mein safe nahi)

**DoD:**
1. Play Store internal track pe signed build live
2. Data safety form + privacy policy submitted & approved
3. Rollback plan tested (purana version wapas promote)
4. Eval suite release build pe bhi green

**Timebox:** 1–2 hafte.

---

# PART 6 — "Ek Phase, Ek Baar" Rules (cross-phase discipline)

1. **Entry criteria check:** Pichla phase ka DoD 100% green, tabhi naya phase shuru. Aadha-adhura phase lekar aage badhna = technical debt ka compound interest.
2. **Scope OUT sacred hai:** Phase ke beech naya idea aaye → `docs/backlog.md` mein likho, phase mein mat ghusao.
3. **Har phase ka end state = working app:** Koi phase khatam hone pe app demo-able honi chahiye. "Do din mein theek ho jayega" wala state phase-end pe allowed nahi.
4. **Contracts freeze:** Har phase jo interfaces banata hai (e.g., `LlmProvider`, `ToolDescriptor`, policy rules) — agla phase unhe *extend* kare, *rewrite* nahi. Rewrite chahiye → pehle ADR likho.
5. **Naya module chahiye lage → pehle ADR:** Coverage matrix (Part 4) se bahar ka kaam bina likhit decision ke nahi.
6. **Tests phase ka hissa hain, extra nahi:** DoD mein likhe tests pass hue bina phase complete nahi hota. (Module 26 "Evaluation" koi ek phase nahi — har phase ki aadat hai.)

---

# PART 7 — Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| iOS background restrictions | Phase 5 iOS pe limited | Android-first (D1); iOS behavior honestly documented |
| API keys device pe | Extraction possible | Secure storage + personal MVP; public release se pehle proxy (P7) |
| `workmanager` 15-min minimum interval | Exact-time jobs fail | Exact alarm strategy (P5) |
| LLM structured output flaky | Planner/agent break | Schema validation + repair retries (max 2) + fallback provider |
| Scope creep (27 modules ka jaal) | Kabhi complete nahi hoga | Coverage matrix + Scope OUT lists + ADR rule |
| API cost overrun | Paisa | Free tiers + token budgets (P1 se) + cost dashboard (P6) |
| Play Store AI-app review strict | Release delay | Data safety + privacy policy P7 mein pehle se plan |
| Solo burnout | Project stall | Har phase 1.5–3 hafte ka timebox; har phase end pe working app (motivation wapas deta hai) |

---

# PART 8 — Timeline Summary (solo, part-time realistic)

| Phase | Kya | Timebox |
|---|---|---|
| 0 | Blueprint & Skeleton | 2–3 din |
| 1 | Foundation Chat | 1.5–2 hafte |
| 2 | Controlled Tools + Policy ⭐ | 2 hafte |
| 3 | Agent Loop + Crash Recovery 🧠 | 2–3 hafte |
| 4 | Voice + Memory | 2 hafte |
| 5 | Automation & Events | 2 hafte |
| 6 | Hardening & Eval 🛡️ | 1.5–2 hafte |
| 7 | Expansion & Release 🚀 | 1–2 hafte |
| **Total** | | **~12–16 hafte (3–4 mahine)** |

---

# PART 9 — First Step (jab tum bolo)

Phase 0 se shuru karenge:
1. Repo + monorepo scaffold (`apps/` + `packages/`)
2. CI + lints
3. `SecretStore` + Gemini/Groq keys ka setup
4. ADR-0001 (D1–D7 decisions)

> **Bas ek baat confirm karo:** D1–D7 assumptions theek hain? (Android-first, solo, P5 tak minimal backend, personal MVP.) Haan bolo → Phase 0 shuru. 🏗️
