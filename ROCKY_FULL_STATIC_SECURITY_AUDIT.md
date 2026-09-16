# R.O.C.K.Y Source Archive — Full Static Security & Quality Audit

**Audited file:** `R.O.C.K.Y-main.zip`  
**SHA-256:** `73d183eead2e88bd5373259d5df3c185633f80fc1353fcd37f2c01fcb25e4286`  
**Audit type:** Source-level static audit; no source files modified.  
**Important scope note:** This upload is the GitHub source archive, **not** the binary release asset `ROCKY_AI_Assistant_free_v1.0.zip`. Therefore this report does not certify any packaged `.exe`.

## Executive verdict

- **Safe to run on a primary Windows PC:** **NO**
- **Ready for public release:** **NO**
- **Ready to merge directly into Freshy AI:** **NO**
- **Useful as a reference/inspiration:** **YES, selectively**
- **Obvious malware found in readable source:** **No obvious miner, credential stealer, reverse shell, webhook exfiltrator, or startup persistence was found.**
- **Still dangerous:** The program intentionally exposes file deletion, arbitrary Python execution, LLM-generated host code execution, messaging, screen/file upload to Gemini, and LAN remote commands without adequate permission or sandbox controls.

The largest problem is not a classic malware signature; it is an unsafe agent architecture in which a model or weakly authenticated LAN client can trigger high-impact host actions.

## Archive and integrity checks

| Check | Result |
|---|---|
| ZIP CRC/integrity | PASS |
| Archive path traversal entries | None found |
| Symlinks in ZIP | None found |
| Native binaries (`.exe`, `.dll`, `.msi`, `.bat`, `.cmd`, `.ps1`) | None found |
| Python source files | 29 |
| Python source lines | ~5,693 |
| Committed `.pyc` files | 81 |
| Python syntax compilation | PASS under Python 3.13.5 |
| Syntax warnings | 1 (`actions/send_message.py:122`, invalid escape `\M`) |
| PNG integrity | All three PNGs have valid chunk CRCs and no trailing payload |
| Automated tests | None found |
| CI workflow | None found |
| Antivirus scan | Not performed; no AV scanner was available in the audit environment |
| Windows GUI/mic/audio execution | Not performed; static Linux-side audit only |

## Critical findings

### C-01 — LAN dashboard can remotely trigger powerful assistant tools

**Evidence**

- `dashboard/server.py:12` binds to `0.0.0.0:8000`.
- `dashboard/server.py:21-27` uses only a six-digit PIN.
- `dashboard/server.py:39-43` serves plain HTTP.
- `dashboard/server.py:114` puts the PIN in the WebSocket query string.
- `dashboard/server.py:182-210` accepts remote commands and queues them for the assistant.
- There is no server-side PIN expiry, attempt limit, IP lockout, client permission scope, origin validation, or command-rate limit.

**Impact**

Anyone on the same network who obtains or guesses the PIN can issue commands to an assistant that can delete files, execute Python, send messages, capture the screen, and operate the desktop. The QR overlay expiration in `ui.py` is only visual; the server key remains valid until manually regenerated.

**Required fix**

Default to `127.0.0.1`; make LAN access opt-in; use TLS or a secure tunnel; use a 128-bit one-time token with server-side TTL and one-time consumption; rate-limit attempts; validate origins; establish an authenticated session; and require explicit desktop approval for high-risk commands.

---

### C-02 — Browser-side script injection in the remote dashboard

**Evidence**

- `dashboard/server.py:126` appends untrusted `msg.speaker` and `msg.text` using `innerHTML`.
- `dashboard/server.py:173-179` inserts the `key` query parameter directly into a JavaScript string in `/auto-login`.

**Impact**

Crafted assistant/user content or a crafted URL can execute JavaScript in the phone dashboard, steal the PIN/session, alter commands, or impersonate logs.

**Required fix**

Use DOM nodes and `textContent`, never `innerHTML` for transcript data. JSON-encode values rather than interpolating them into JavaScript. Add a strict Content Security Policy.

---

### C-03 — LLM-generated code executes directly on the host

**Evidence**

- `actions/desktop.py:83-101` executes generated code using `exec(compile(...))`.
- The alleged sandbox exposes full `Path`, `pyautogui`, and on Windows `ctypes`; these APIs can write/delete files and invoke native functionality.
- There is no mandatory user preview or approval before execution.

**Impact**

Prompt injection or a model error can modify/delete files, operate the GUI, access sensitive data, or execute arbitrary native actions. The Python dictionary called a “sandbox” is not a security boundary.

**Required fix**

Replace host-side `exec` with a narrow action DSL. For genuinely generated code, use a separate low-privilege process/container/VM with no network by default, filesystem allowlists, strict resource limits, a visible preview, and explicit user confirmation.

---

### C-04 — Dev agent allows arbitrary command and package execution

**Evidence**

- `actions/dev_agent.py:226-228` joins model-provided file paths without verifying resolved-path containment.
- `actions/dev_agent.py:238-271` installs model-provided dependencies.
- `actions/dev_agent.py:294-318` runs a model-provided command on the host.
- `actions/dev_agent.py:327-347` automatically installs missing modules.
- Timeouts may be treated as success rather than failure.

**Impact**

A generated `../` path can escape the project directory; model output can overwrite arbitrary files, install a malicious/typosquatted package, or run arbitrary commands. Global package installation can also corrupt the user’s Python environment.

**Required fix**

Resolve and validate every path against a project root; use a per-project virtual environment; allowlist commands and packages; reject pip flags/URLs; pin hashes; run in a low-privilege sandbox; kill the full process tree on timeout; and require user approval.

---

### C-05 — Arbitrary local Python files can be executed

**Evidence**

- `actions/file_processor.py:456-474` runs any selected `.py` file via `subprocess`.
- The file path is broadly model/user-controlled and has no safe-directory policy.

**Impact**

A downloaded or malicious Python file can execute with the user’s privileges.

**Required fix**

Disable this action by default. Use a separate sandbox, safe-directory allowlist, explicit confirmation, no network, time/memory limits, and a clear command preview.

---

### C-06 — Permanent deletion without confirmation or undo

**Evidence**

- `actions/file_controller.py:87-124` uses `unlink()` and `shutil.rmtree()`.
- Matching can be fuzzy/substring based.
- The action is exposed to the model in `main.py`.

**Impact**

The assistant can permanently delete the wrong file or directory, with no recycle-bin recovery and no mandatory confirmation.

**Required fix**

Use the recycle bin, exact resolved paths, protected-root deny rules, full-path confirmation, and an undo/audit record.

## High-severity findings

### H-01 — Weather calls accidentally invoke browser control; direct browser tool is unreachable

`main.py:497-502` invokes `browser_control()` inside the weather branch because of indentation. No separate `elif name == "browser_control"` dispatcher branch exists.

**Impact:** Weather requests can trigger unexpected browser behavior, while direct browser-control tool calls return “unknown tool.”

**Fix:** Add a separate dispatcher branch and contract tests for every declared tool.

### H-02 — API-key storage paths and schemas disagree

- Main app: `config/config.json`, keys `api_key` or `gemini_api_key` (`main.py:49-75`).
- Settings UI: writes relative `config/config.json` with `api_key` (`settings.py:158-170`).
- Several tools: read `config/api_keys.json` with `gemini_api_key`.

**Impact:** The app may start while computer vision, desktop, file, and dev tools fail. Starting from a shortcut can write the key to the wrong working directory. Keys are stored as plaintext JSON.

**Fix:** Use one secrets service and one absolute path; store secrets in Windows Credential Manager/DPAPI; migrate legacy names; use atomic writes and restrictive ACLs.

### H-03 — Desktop text-command box does not send commands

`ui.py:1254-1263` clears and logs the text but never calls the command callback.

**Impact:** The visible input appears functional but performs no AI action.

**Fix:** Emit a Qt signal/callback to the processing thread and display a disconnected/error state.

### H-04 — QR “auto-login” does not actually log in

`/auto-login` writes `jarvis_pin` to localStorage, but the root page never reads it. The secret also remains in the URL/localStorage.

**Fix:** Use a short-lived one-time token exchanged for an HttpOnly session cookie; do not place long-lived secrets in URLs/localStorage.

### H-05 — “Search” produces a fabricated generic report

`actions/browser_control.py:28-50` opens Google, then writes a canned AI/technology summary without reading search results.

**Impact:** Users can be told research was completed when no evidence was retrieved.

**Fix:** Integrate a real retrieval/search API, extract sources, cite them, or clearly state that only a browser page was opened.

### H-06 — `open_app` is shell-command injectable

`actions/open_app.py:50-52` passes model-controlled `app_name` into `os.system('start ...')`.

**Impact:** Crafted quotes/shell syntax can execute unintended commands.

**Fix:** Resolve applications from an allowlisted Start Menu/registry catalogue and launch via non-shell `subprocess` arguments.

### H-07 — Sensitive screen, camera, and file content can be sent to Gemini without granular consent

`screen_processor.py`, `computer_control.py`, and `file_processor.py` can upload screenshots, documents, code, audio, images, and data to the Gemini service.

**Impact:** Private material may leave the device without a per-use preview, redaction, or clear scope.

**Fix:** Add a Permission Center, visible preview, per-folder/file scope, sensitive-data redaction, local-only mode, provider disclosure, and activity logging.

### H-08 — Plaintext persistent memory can become persistent prompt injection

`memory/memory_manager.py:5-32` stores arbitrary values in `long_term.json`; the memory is later inserted into the system instruction. The repository already contains personal preference examples.

**Impact:** A malicious remembered value can influence future tool decisions, and personal data is stored unencrypted.

**Fix:** Store typed data, not free-form instructions; validate values; isolate memory as untrusted context; encrypt/protect the store; provide view/edit/delete controls.

### H-09 — Microphone architecture conflicts and does not support true barge-in

`wake_word.py` continuously opens the default microphone and uses Google recognition, while `main.py` separately opens the microphone for Gemini Live. `main.py` suppresses mic capture while the assistant is speaking.

**Impact:** Device contention, duplicated cloud audio processing, silent failures, and inability to interrupt the assistant while it speaks.

**Fix:** One audio capture pipeline; local wake-word detection; clear microphone indicator; surfaced errors/backoff; echo cancellation and proper barge-in.

### H-10 — Hidden compiled-only phone/TV modules contain personal and device-specific data

The archive contains `.pyc`-only `phone_controller` and `tv_controller` modules, with no corresponding source. Static strings include:

- Hardcoded ADB paths.
- A hardcoded phone PIN `123456`.
- Example/personal phone numbers.
- WhatsApp/Instagram/camera automation.
- Hardcoded TV IP addresses and Samsung app IDs.
- Developer machine paths such as `C:\Users\YASH\...`.

**Impact:** Privacy leakage, opaque unauditable behavior, and platform-specific dead code in a public source archive.

**Fix:** Remove all `.pyc` and `__pycache__` files; add `.gitignore`; publish readable source for intended modules; remove/rotate personal identifiers; use configuration rather than hardcoding.

### H-11 — Dependencies are heavy, inconsistent, and incomplete

`requirements.txt` is UTF-16 and pins roughly 100 packages, including both PyQt5 and PyQt6, Flask and FastAPI stacks, Playwright, and many apparently unused packages. Directly imported packages such as `SpeechRecognition`, `pandas`, `pdfplumber`, `PyPDF2`, `python-docx`, and `python-pptx` are not declared.

`setup.py` installs everything globally and downloads Playwright browsers, although the source does not use Playwright.

**Impact:** Installation failures, dependency conflicts, a very large attack surface, and non-reproducible setup.

**Fix:** Convert to UTF-8; list only direct dependencies; split optional extras; use a virtual environment; lock/test supported Python versions; remove unused stacks.

### H-12 — Declared tools and actual implementations do not match

Examples:

- `browser_control` is declared but not correctly dispatched.
- `computer_control` advertises actions it does not implement.
- `youtube_video` advertises summarize/info actions but mainly opens/controls YouTube.
- `send_message` advertises WhatsApp/Telegram but implements WhatsApp-oriented behavior.
- `reminder`, `game_updater`, and `code_helper` are largely stubs.
- `file_controller` advertises move/copy but does not implement them fully.

**Impact:** The model can confidently report success when nothing happened.

**Fix:** Generate tool schemas from implementation contracts; add structured result types; add one test per action; advertise only completed capabilities.

## Medium/correctness findings

1. `maps_controller.py` treats the literal origin `"mumbai"` as “current location” and drops it.
2. Weather defaults to Mumbai when no location is supplied.
3. Flight search parameters are not robustly URL-encoded.
4. YouTube scraping lacks a timeout and uses brittle regex.
5. Skip-ad coordinate fallback may click the wrong desktop location.
6. `computer_settings.py` does not robustly validate/clamp numeric amounts.
7. WhatsApp sending has no final recipient/message confirmation and may select the wrong contact.
8. “Latest file” attachment logic can leak the wrong file.
9. `actions/send_message.py:122` contains an invalid escape sequence.
10. `file_processor.py` calls `pandas.read_csv(..., errors="replace")`; this is not a valid `read_csv` parameter.
11. Excel sort paths can receive CSV-formatted output.
12. XML is routed to JSON parsing.
13. PDF text extraction may concatenate `None`.
14. FFmpeg commands often do not verify return code and output existence.
15. Archive extraction lacks zip-bomb, file-count, total-size, and destination-containment controls.
16. Several processors load entire files into memory with no size limit.
17. `tempfile.mktemp()` is used, which is race-prone.
18. Desktop organizer/cleanup actions move files without confirmation or rollback.
19. Wallpaper download lacks timeout, scheme restriction, and maximum size.
20. Several UI buttons are visible but not wired.
21. Health/version labels contain hardcoded demo values.
22. A map click injects a “SYSTEM OVERRIDE” prompt rather than invoking a trusted action.
23. `dashboard/index.html` targets `/ws/remote`, but the server exposes `/ws/link`; the file appears dead/mismatched.
24. Bluetooth logic is hardcoded to a device named “Nirvana.”
25. Audio queues need bounded/backpressure-safe handling.
26. The system prompt says tools must not be simulated, but multiple handlers return canned/stub success responses.

## What is genuinely useful for Freshy AI

| R.O.C.K.Y concept | Freshy decision |
|---|---|
| Gemini Live streaming loop | Study/adapt carefully |
| Tool declaration pattern | Reuse the concept, not the dispatcher |
| PyQt UI | Do not merge; keep Freshy UI |
| LAN phone dashboard | Rewrite securely from scratch |
| Remote text commands | Useful behind strong auth/permissions |
| Screen/file processing | Useful only with consent and scoped access |
| Desktop automation | Rebuild as allowlisted actions |
| Dev agent | Do not use until sandboxed |
| Plain JSON memory | Replace with Freshy memory architecture |
| `.pyc` phone/TV modules | Do not import |
| YouTube automation | Not a complete YouTube Studio system |

## Recommended remediation order

### P0 — Before anyone runs it on a real machine

1. Disable/remove LAN dashboard by default.
2. Remove host `exec` and arbitrary Python execution.
3. Disable dev-agent package/command execution.
4. Replace permanent deletion with recycle-bin + confirmation.
5. Fix shell injection in `open_app`.
6. Add per-action permission/confirmation for screen, file, message, and desktop tools.
7. Remove `.pyc`, personal data, and compiled-only modules.

### P1 — Make the core functional

1. Fix dispatcher indentation and tool routing.
2. Centralize API-key configuration.
3. Wire text commands.
4. Replace fake browser research.
5. Align tool schemas with implementations.
6. Add structured error/success results.
7. Fix file-processing correctness issues.

### P2 — Make installation and testing reliable

1. Minimal UTF-8 dependency file.
2. Per-project virtual environment.
3. Unit tests for every tool.
4. Integration tests for permissions and dashboard auth.
5. Windows CI/build pipeline.
6. Signed release artifacts and reproducible hashes.

## Scores

| Area | Score |
|---|---:|
| Concept / demo appeal | 7/10 |
| Code architecture | 4/10 |
| Functional completeness | 3/10 |
| Security | 1.5/10 |
| Privacy controls | 2/10 |
| Reliability | 3/10 |
| Testability | 1/10 |
| Direct Freshy merge suitability | 2/10 |
| Reference value | 6/10 |

## Final decision

This source archive is **not release-ready and should not be run on a primary PC or exposed on a LAN in its current state**. It does not look like an obvious conventional malware project from the readable source, but it contains multiple dangerous agent capabilities with weak or missing security controls. The correct Freshy strategy is to take selected architectural ideas only and implement them within Freshy’s permission, approval, secret-storage, activity-log, and sandbox design.

The exact GitHub release executable remains unaudited until the actual `ROCKY_AI_Assistant_free_v1.0.zip` asset is supplied.
