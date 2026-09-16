# 📱 FRESHY — FLUTTER MOBILE BUILD PLAN v1.1 (Cons → Pros Edition)
> Base: `FRESHY_Flutter_Plan_v1.0.md` + Cons-to-Pros Flip
> Target: **Flutter mobile app** (Android-first, Solo Dev)
> Philosophy: **Har Con ek Feature hai, agar uska Fallback + User Message ho**

---

## 🔄 v1.0 se v1.1 me kya badla?

| v1.0 ka Con | v1.1 me Pro kaise bana |
|---|---|
| Monorepo + 3 packages heavy hai | **Lean Monorepo:** Day 1 single `lib/core/` + pure-dart lint rule. Package split Phase 3B ke baad. Speed = Pro |
| Phase 3 underestimated (2-3 hafte me impossible) | **Split:** 3A = Planner + Task Manager, 3B = Agent Loop + Crash Resume. Mushkil kaam = Moat |
| Free tier rate-limit risk | **Cost Transparency Feature:** Phase 1 se CostTracker + Multi-provider auto-fallback. User ko dikhega "Gemini busy, Groq se try..." |
| Hindi STT/TTS kharab | **Graceful Degradation:** Platform STT primary, confidence <60% pe Cloud Whisper optional. TTS optional toggle. Offline-first Pro |
| Android 14 Exact Alarm permission | **Permission Education:** Pehle value samjhao, phir mango. Deny pe 15-min WorkManager fallback. App toote nahi |
| API Keys device pe insecure | **Dual Mode:** `ApiProxyProvider` interface Day 1 se. Flag se Direct vs Cloudflare Worker Proxy switch. Personal + Public dono ready |
| Timeline optimistic 12-16 hafte | **Demo-Driven:** Har phase = 1 working APK. 8 chhote wins = burnout nahi |

---

# PART 1 — Architecture Review (same, no change)

**Concept Score: 9/10** - Policy Engine LLM ke bahar, Router, Modular Monolith, Verify Don't Trust, Bounded Autonomy, Supervisor - ye principles rock solid hain.

---

# PART 2 — Key Decisions & Assumptions v1.1

| # | Decision | v1.1 Update |
|---|---|---|
| D1 | **Android-first** | Same - iOS codebase ready, test baad me |
| D2 | **Solo developer** | Same - par har phase demo-able APK = motivation |
| D3 | **Backend Strategy** | **UPDATED:** Phase 0 me Firebase project + Cloudflare Worker (free) ka skeleton bana lo. Phase 1-4 tak Direct Mode (device keys), Phase 5 se Proxy Mode (1 flag change). Code me `ApiProxyProvider` Day 1 se |
| D4 | **Phase 5 minimal serverless** | UPDATED: Firebase + Worker ka setup Phase 0 me, use Phase 5 me. Setup ka 3 din Phase 5 me waste nahi hoga |
| D5 | **No on-device LLM in MVP** | Same + Graceful: Platform STT primary, Cloud fallback optional |
| D6 | **Personal MVP → Play Store** | UPDATED: Play Store ready code Day 1 se (proxy interface), release Phase 7 me sirf flag flip |
| D7 | **Hindi/Hinglish/English** | Same + Fallback: Low confidence pe user ko choice do |
| **D8 NEW** | **Cost Transparency** | Phase 1 se har message pe cost + provider dikhega. Ye feature hai, debug tool nahi |
| **D9 NEW** | **Lean Start** | Monorepo folders nahi, lint rules se purity enforce. Packages Phase 3B ke baad split |

---

# PART 3 — Flutter Tech Stack v1.1

| Architecture piece | v1.1 Tech + Flip |
|---|---|
| **Core brain** | `lib/core/` folder (Pure Dart enforced by `analysis_options.yaml` - no Flutter import rule). Phase 3B ke baad `packages/freshy_core` me split |
| State management | Riverpod + Freezed |
| Navigation | go_router |
| Local DB | **drift** (SQLite) - conversations, messages, checkpoints, audit, cost |
| Secrets | `flutter_secure_storage` + `--dart-define` + **`ApiProxyProvider` interface** (DirectProvider vs ProxyProvider) |
| HTTP + streaming | **dio** + SSE |
| Model Gateway | `google_generative_ai` + Groq + **CostTracker + CircuitBreaker** (Phase 1 se). `LlmProvider` interface me `costPerToken` + `healthCheck()` |
| STT | `speech_to_text` (primary) + **Cloud Whisper fallback** (optional, user choice on low confidence) |
| TTS | `flutter_tts` + **optional toggle** (default OFF in Phase 4 start, user ON kare) |
| Notifications | `flutter_local_notifications` + exact alarm + **permission education screen** |
| Background jobs | `workmanager` (15-min fallback) + exact alarm (primary) |
| Push / webhook | `firebase_messaging` + Cloud Function + **Cloudflare Worker Proxy** |
| Biometric | `local_auth` |
| Event Bus | Typed Dart Streams + drift outbox |
| Observability | File logs (P1) + **Cost Dashboard** (P1) + Sentry (P6) |
| Testing | `flutter_test`, `mocktail`, `integration_test` |

### Project Structure v1.1 (Lean Start)

```
freshy/
├── lib/
│   ├── core/               # PURE DART - router, planner, policy, memory, llm interface
│   │   ├── router/
│   │   ├── policy/
│   │   ├── llm/            # LlmProvider, ApiProxyProvider, CostTracker
│   │   └── tools/
│   ├── infra/              # drift, secure_storage, dio
│   ├── features/           # chat, tasks, voice, automation (UI)
│   └── main.dart
├── docs/adr/               # Sirf D1-D9 ke liye, har chhote decision ke liye nahi
├── cloudflare_worker/      # proxy worker (Phase 0 skeleton, Phase 5 active)
└── .github/workflows/      # analyze + test only (APK build Phase 1 se)
```

**Lint Rule for Purity (analysis_options.yaml):**
```yaml
custom_lint:
  rules:
    - no_flutter_import_in_core  # lib/core/ me flutter import = error
```

---

# PART 4 — 27 Modules → Phase Coverage Matrix v1.1

| Mod | Module | Phase v1.1 |
|---|---|---|
| 01 | Perception & Input | **P1** (text) → **P4** (voice + graceful fallback) |
| 03 | Identity & Admission | **P1** (single-user) → **P4** (biometric) |
| 04 | Request Router | **P1** (core) → **P2** (fast) → **P3A** (agent) → **P5** (event) |
| 05 | Context & Trust | **P3A** (basic) → **P4** (budget + trust labels) |
| 06 | Freshy Core | **P1** |
| 07 | Model Gateway | **P1** (1 provider + CostTracker + CircuitBreaker) → **P3A** (fallback) → **P7** (multi) |
| 08 | Goal & Task Manager | **P3A** |
| 09 | Planner | **P3A** (ye alag phase) |
| 10 | Tool Registry | **P2** |
| 11 | Agent Runtime | **P3B** (ye alag phase) |
| 12 | Policy & Approval | **P2** (core) - har phase extend |
| 13 | Sandboxed Execution | **P2** |
| 14 | Observation & Normalization | **P2** |
| 15 | Verification & Recovery | **P2** (basic) → **P3B** (full recovery) |
| 16 | Response Engine | **P1** (v0 + cost display) → **P4** (polish) |
| 17 | Voice Output | **P4** (optional toggle) |
| 18 | Durable State & Checkpoints | **P1** (basic) → **P3B** (checkpoints + crash resume) |
| 19 | Memory & Knowledge | **P4** |
| 20 | Automation & Workflows | **P5** |
| 21 | Event Bus | **P3A** (in-process) → **P5** (persisted) |
| 22 | Concurrency & Resources | **P3B** (single queue) → **P5** (throttle) |
| 23 | Secrets & Config | **P0** (SecretStore + ApiProxyProvider interface) |
| 24 | Privacy & Governance | P0 se principles; formal **P6** |
| 25 | Health & Observability | **P1** (logs + Cost Dashboard) → **P6** (Sentry + audit) |
| 26 | Evaluation | Continuous; formal **P6** |
| 27 | Plugin Lifecycle | **P7** backlog (compile-time packs) |

---

# PART 5 — Phase Plan v1.1 (Cons → Pros)

## 🟢 PHASE 0 — Blueprint & Skeleton [2-3 din]

**Goal:** Lean skeleton + Dual Mode ready + CI green

**Scope IN (Flipped):**
- [ ] Flutter + Android setup
- [ ] **Lean structure:** `lib/core/`, `lib/infra/`, `lib/features/` (packages nahi)
- [ ] **Purity Lint:** `lib/core/` me Flutter import = error
- [ ] CI: `analyze` + `test` only (APK Phase 1 se)
- [ ] **Secrets v1.1:** `SecretStore` + `ApiProxyProvider` interface (DirectProvider + ProxyProvider stub) + `CostTracker` model
- [ ] **Cloud skeleton:** Firebase project create + Cloudflare Worker hello-world (deploy nahi, bas code)
- [ ] ADR-0001: D1-D9 decisions (sirf 1 doc)
- [ ] App shell: "Freshy" name + empty Home

**Scope OUT:** Chat, LLM, DB, tools

**DoD:**
1. `flutter run` → empty home
2. CI green
3. `lib/core/` me Flutter import karne pe lint error aaye (prove purity)
4. Secret round-trip + Proxy interface stub test pass

**Demo:** Empty app + lint error demo + CI badge

---

## 🟢 PHASE 1 — Foundation Chat + Cost Transparency [1.5-2 hafte]

**Goal:** Reliable streaming chat + user ko cost dikhe (Trust Feature)

**Scope IN (Flipped):**
- [ ] `core/llm/`: `LlmProvider` + `DirectProvider` (Gemini) + Groq + **CircuitBreaker + CostTracker**
- [ ] `core/router/`: v0 - sab CORE PATH
- [ ] drift: `conversations`, `messages`, `cost_logs`
- [ ] UI: Chat (streaming) + Conversation List + Settings (API key + provider picker) + **Cost Dashboard (small chip: "₹0.02 | Gemini | 1.2s")**
- [ ] Error Handling: Rate-limit → auto fallback → user ko dikhe "Gemini busy, Groq se try kar raha hu"
- [ ] Logs: Request-ID + token usage

**DoD:**
1. Streaming chat works (both providers)
2. Kill → reopen → history intact
3. **Provider fail → auto fallback + UI me message dikhe (ye Pro hai)**
4. Har message pe cost chip dikhe
5. Wrong key → Hinglish error, crash nahi

**Demo:** Chat → provider fail simulation → fallback dikhao → cost dashboard

---

## 🟢 PHASE 2 — Controlled Tools + Policy Heart [2 hafte]

**Goal:** Pehli baar action, par policy gate se. Safety heart.

**Scope IN:**
- [ ] Tool Registry: `ToolDescriptor` (risk, permissions, timeout, verification)
- [ ] Tools v1: `get_time` (FAST PATH, no LLM), `calculator`, `notes_write/read` (sandbox only), `reminder_create`
- [ ] **Policy Engine (Pure Dart):** BLOCK | ASK | ALLOW, default deny, unregistered = hard block
- [ ] Approval UI: Bottom sheet - action+target+args+risk + Approve/Deny + 60s expiry + hash check
- [ ] Function-calling loop v0: LLM propose → policy → execute → result → answer
- [ ] Verification v0: file write → read-back, reminder → scheduled check

**DoD:**
1. "Time kya hai" → FAST PATH, LLM call zero (logs prove)
2. "Note likho" → approval → file + verified
3. Unregistered tool → clean block
4. Approval 60s expiry → re-approval
5. Policy matrix 12+ tests 100% pass

---

## 🟢 PHASE 3A — Planner + Task Manager [1.5 hafte] ⭐ NEW SPLIT

**Goal:** Multi-step sochna, plan dikhana

**Scope IN:**
- [ ] Task Manager: States (CREATED→READY→RUNNING→WAITING→COMPLETED/PARTIAL/FAILED)
- [ ] Planner: LLM se structured JSON plan, schema validation, capability check, repair retry max 2
- [ ] Model Gateway v2: Fallback preserve
- [ ] Task UI: Task list + detail (plan steps visible, no execution yet - dry run mode)
- [ ] Event Bus v1: In-process streams

**DoD:**
1. "Mera birthday plan banao" → 3-step plan dikhe (research→note→reminder) - execution nahi, sirf plan
2. Invalid plan → repair retry → valid ya honest fail
3. Plan ka har step pe expected result + verification method dikhe

**Demo:** Complex query → plan visible → user approve plan

---

## 🟢 PHASE 3B — Agent Loop + Crash Recovery [2 hafte] 🧠

**Goal:** Plan execute ho, beech me app kill ho toh resume ho - YE MOAT HAI

**Scope IN:**
- [ ] Agent Runtime: Bounded loop (max steps, deadline, budget) → har action pe policy re-check
- [ ] Checkpoints: Har step ke baad drift me persist
- [ ] **Startup Reconciliation:** App khulte hi RUNNING tasks detect → Resume dialog
- [ ] Worker Queue v0: Single worker, foreground priority
- [ ] Verification full: Har step ka evidence UI me

**DoD (Headline Test):**
1. 3-step task end-to-end complete, har step ka evidence UI me
2. **⭐ Task ke beech app force-kill → reopen → Resume dialog → resume → complete**
3. Cancel → loop turant ruke
4. Step budget khatam → PARTIAL + honest explanation

**Demo:** Task start → step 2 pe kill → reopen → resume → complete. Ye video Play Store pe daal sakte ho.

---

## 🟢 PHASE 4 — Personal Assistant (Voice + Memory) [2 hafte]

**Goal:** Personal + Voice, par graceful

**Scope IN (Flipped):**
- [ ] **STT v1.1:** `speech_to_text` primary + **Confidence Check**. <60% pe UI: "Sahi suna nahi, Cloud se try karu? (1 sec)" + mic permission education
- [ ] **TTS v1.1:** `flutter_tts` + **Default OFF**. Settings me toggle "Voice reply". Barge-in (user bole → TTS ruke, task cancel NA ho)
- [ ] Voice Mode UI: listening/thinking/speaking states
- [ ] Memory Service: preferences ("chhote answers"), verified facts, controlled writes (explicit confirm), memory screen view/edit/delete
- [ ] Context Manager full: Budget + summarization + untrusted tag
- [ ] Biometric gate: Sensitive approvals pe fingerprint
- [ ] Onboarding: Language + voice + permissions walkthrough

**DoD:**
1. Voice round-trip: bol ke poochho → reply text + optional voice
2. Low confidence → cloud fallback choice dikhe (Pro)
3. "Short answers chahiye" → preference save → agle answers chhote
4. Sensitive action → fingerprint, fail → block
5. Barge-in works, task cancel nahi

**Demo:** Voice mode → low confidence scenario → fallback choice → preference save

---

## 🟢 PHASE 5 — Automation & Events [2 hafte] ⏰

**Goal:** App band ho tab bhi kaam kare, permission educate karke

**Scope IN (Flipped):**
- [ ] **Cloud Active:** Firebase FCM + Cloud Function (webhook → push) + **Cloudflare Worker Proxy active** (flag flip)
- [ ] **Permission Education Screen:** "Roz 8 baje summary ke liye exact time permission chahiye, warna 15 min late ho sakta hai" + [Allow] [Approximate hi chalega]
- [ ] **Dual Scheduling:** Exact alarm (primary, permission mile toh) + WorkManager 15-min (fallback, permission na mile toh) + UI pe badge "Exact" vs "Approximate"
- [ ] Workflow Service: trigger → condition → task, owner, scope, expiry, pause/disable
- [ ] Event Path: FCM push → validated event → policy check → task
- [ ] Revocation: Workflow revoke → future runs blocked
- [ ] Automation UI: Workflow list + templates ("daily summary") + run history
- [ ] Reboot survive: Device reboot ke baad schedule zinda

**DoD:**
1. Workflow "Roz 8 baje summary" → app closed + locked → 8 baje notification (Exact mode)
2. Permission deny → Approximate mode → 15-min window me chale + UI pe "Approximate" badge (App toota nahi - Pro)
3. Reboot → schedule survive
4. Webhook test: curl → Function → FCM → task → policy check
5. Revoke → next run blocked
6. Duplicate push → dedupe

**Demo:** Permission education screen → Allow → exact schedule → Deny scenario → approximate fallback

---

## 🟢 PHASE 6 — Hardening, Privacy & Eval [1.5-2 hafte] 🛡️

**Goal:** Bharosa + Play Store Ready

**Scope IN:**
- [ ] Data Classification: Public/Private/Sensitive/Local-only tags, local-only kabhi cloud pe nahi (test)
- [ ] Redaction Pipeline: logs + LLM context se secrets/PII redact
- [ ] Export/Delete: One screen JSON export + delete
- [ ] Audit & Traces: Request → Plan → Approval → Tool → Evidence → Status correlated trail + Cost Dashboard full
- [ ] Sentry (redacted)
- [ ] **Eval Suite (CI, mocked LLM):** 20 golden tasks + **Prompt-injection corpus** (100% BLOCK) + False-completion tests + Metrics (success %, unauthorized=0, avg cost)
- [ ] Performance: Cold start, memory, battery - real device numbers
- [ ] Security: APK me plaintext key nahi (test), allowlist re-verify, Proxy mode test
- [ ] EVAL_REPORT.md

**DoD:**
1. Injection attacks 100% blocked, unauthorized 0
2. Export valid JSON, Delete → DB clean
3. Local-only data cloud pe nahi (test prove)
4. Sentry crash dikhe
5. Cold start <3s documented
6. EVAL_REPORT.md committed

---

## 🟢 PHASE 7 — Expansion & Release [1-2 hafte] 🚀

**Goal:** Multi-provider + Play Store

**Scope IN:**
- [ ] Providers: OpenRouter/Mistral add, router by cost/latency, per-provider circuit breaker
- [ ] Plugin packs v1: Manifest-based (compile-time, dynamic code nahi - Play Store policy)
- [ ] **Proxy Mode Default:** Public build me ProxyProvider default, DirectProvider dev only
- [ ] Release: App signing, R8/obfuscation, Play Console, **Data Safety Form**, Privacy Policy, AI app review prep
- [ ] Internal track → beta → staged rollout + rollback plan
- [ ] Optional experiments: on-device model (Gemini Nano), speaker ID (Module 02) - only if eval value

**DoD:**
1. Play Store internal track signed build live
2. Data safety + privacy policy approved
3. Rollback tested
4. Eval suite release build pe green

---

# PART 6 — Ek Phase Ek Baar Rules v1.1

1.  **Entry 100% Green:** Pichla DoD green tabhi next phase
2.  **Scope OUT Sacred:** Naya idea → `docs/backlog.md`, phase me mat ghusao
3.  **Har Phase End = Working APK:** "2 din me theek hoga" allowed nahi
4.  **Contracts Extend, Rewrite Nahi:** Interface badalna hai toh ADR likho
5.  **Fallback + Message Rule:** Har risky feature ka ek fallback + user ko honest message hona chahiye. Ye rule follow hua toh Con = Pro
6.  **Tests = Phase ka hissa:** DoD tests pass bina phase complete nahi

---

# PART 7 — Risk Register v1.1 (Con → Pro)

| Risk | v1.0 Mitigation | v1.1 Pro Flip |
|---|---|---|
| iOS background | Android-first | Same + honestly doc |
| API keys extraction | Secure storage | **Dual Mode + Cloudflare Worker Proxy** - Public build me key hi nahi hai |
| WorkManager 15-min | Exact alarm | **Education + Fallback** - Exact mile toh exact, nahi toh approximate + badge. App toote nahi |
| LLM JSON flaky | Schema + repair | Same + Dry-run UI Phase 3A me - user plan dekh ke approve kare |
| Scope creep | Coverage matrix | + Lean structure + Split Phase 3 - 8 small wins |
| API cost | Free tiers | **Cost Dashboard Day 1** - Transparency = Trust Feature |
| Play Store AI review strict | P7 me plan | **P0 se ready** - Proxy interface + Data safety doc P6 me |
| Solo burnout | Timebox | **Har phase APK** - Har 2 hafte me dikhane layak app |
| Hindi STT poor | Platform STT | **Confidence + Cloud Choice** - User ko control do, offline-first Pro |

---

# PART 8 — Timeline Summary v1.1

| Phase | Kya | Timebox | Output APK |
|---|---|---|---|
| 0 | Lean Blueprint + Dual Mode Skeleton | 2-3 din | Empty App |
| 1 | Chat + Cost Transparency | 1.5-2 hafte | Chat App |
| 2 | Controlled Tools + Policy | 2 hafte | Tool App |
| 3A | Planner (Dry Run) | 1.5 hafte | Planning App |
| 3B | Agent Loop + Crash Resume (MOAT) | 2 hafte | Resilient Agent App |
| 4 | Voice + Memory (Graceful) | 2 hafte | Personal Assistant App |
| 5 | Automation + Permission Education | 2 hafte | Autonomous App |
| 6 | Hardening + Eval | 1.5-2 hafte | Release-Worthy App |
| 7 | Expansion + Play Store | 1-2 hafte | Public App |
| **Total** | | **~14-18 hafte (3.5-4.5 mahine)** | 8 Working APKs |

Timeline thoda bada hai (3A/3B split ki wajah se) par har 2 hafte me ek working APK milega - motivation ke liye yehi Pro hai.

---

# PART 9 — First Step (Phase 0 v1.1)

Jab bolo tab:
1.  Lean scaffold: `lib/core/`, `lib/infra/`, `lib/features/` + purity lint
2.  CI: analyze + test
3.  `SecretStore` + `ApiProxyProvider` (Direct + Proxy stub) + `CostTracker` model
4.  Firebase + Cloudflare Worker skeleton
5.  ADR-0001 (D1-D9)

**Confirm karo:** D1-D9 theek hain? Flagship Moat = Crash Resume + Cost Transparency + Graceful Degradation. Haan bolo → Phase 0 v1.1 shuru. 🏗️
