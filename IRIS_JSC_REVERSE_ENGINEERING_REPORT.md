# IRIS 1.7.3 — JSC Reverse-Engineering Report

## Scope and boundary

This analysis was performed on the user-supplied IRIS 1.7.3 installer for architecture, interoperability, and security understanding. It does not attempt to bypass licensing, authentication, payment controls, or redistribute proprietary source code.

## What was actually extracted

- Reassembled the four split 7z volumes into the original archive.
- Extracted `iris-ai-1.7.3-setup.exe`.
- Identified the setup as an NSIS installer with an embedded 7z payload.
- Carved and extracted the embedded payload beginning at file offset `170931`.
- Extracted `resources/app.asar` and parsed its ASAR header directly.
- The ASAR contains **33,261 files**.
- Extracted the protected main/preload bytecode, readable loaders, renderer bundle, package metadata, and bundled documentation.

## Verified runtime

| Component | Version |
|---|---|
| Electron | 30.5.1 |
| Chromium | 124.0.6367.243 |
| Node.js | 20.16.0 |
| V8 | 12.4.254.20 |

The versions were independently visible in the packaged executable and match the Electron release metadata.

## Protected files

| File | Binary size | Source-length header |
|---|---:|---:|
| `out/main/index.jsc` | 466,296 bytes | 199,355 characters |
| `out/preload/index.jsc` | 7,776 bytes | 2,372 characters |

The loader confirms these are V8 `cachedData` bytecode files. It:

1. enables `--no-lazy` and `--no-flush-bytecode`;
2. reads the `.jsc` buffer;
3. patches the V8 flag hash;
4. builds a dummy source string with the original source length;
5. passes the bytecode to `vm.Script(..., cachedData=...)`;
6. executes the recovered CommonJS wrapper.

## Decompilation experiment

The available Linux Node runtime uses V8 `12.4.254.21-node.26`, while IRIS uses V8 `12.4.254.20` inside Electron 30.5.1.

- Normal cached-data loading was rejected.
- Patching only version and flag hashes was still rejected.
- Forcing additional header fields caused a native V8 deserializer crash, proving that the serialized bytecode layout is not safely interchangeable despite the close patch version.

Therefore, an exact original-JavaScript recovery cannot be honestly claimed from the current Linux runtime. The correct next technical route is an isolated Electron 30.5.1 runtime or controlled Windows VM instrumentation.

## Recovered preload bridge

The small preload bytecode was sufficiently exposed through constants to recover its public interface:

```text
window.iris.startSession(...)
window.iris.getHistory()
window.iris.stopSession()
window.iris.toggleMic(...)
window.iris.onSystemStatus(callback)
window.iris.onSpeakingState(callback)
window.iris.onTranscript(callback)
window.iris.onTranscriptComplete(callback)
window.iris.sendVisionFrame(frame)
```

Deep-research bridge behavior also exposes start/progress/start/done callbacks through channels such as:

```text
trigger-deep-research
deep-research-start
oracle-progress
deep-research-done
```

## Recovered voice architecture

The readable renderer and protected-bytecode constants establish this flow:

```text
AudioWorklet microphone capture
→ buffered PCM audio (`audio/pcm;rate=16000`)
→ live session input
→ Gemini Live native audio response
→ playback queue
→ VAD detects user interruption
→ current output queue is flushed
```

Recovered model identifier:

```text
gemini-3.1-flash-live-preview
```

The main bytecode contains the live-session methods `sendRealtimeInput`, `sendClientContent`, `audioStreamEnd`, `sendToolResponse`, and `toolCall`.

## Recovered provider and search layer

The package and bytecode expose:

- Google Gemini / Gemini Live
- Groq SDK
- Tavily
- Hugging Face inference
- Gemini embeddings (`gemini-embedding-001`)

Visible REST model calls include Gemini content generation and streaming endpoints. API keys are managed through IPC channels `secure-save-keys` and `secure-get-keys`.

## Recovered memory architecture

- LanceDB / `vectordb` local vector storage
- Gemini embeddings
- local `memory.json`
- `saved-user-memory.json`
- long-term memory tools `save_core_memory` and `retrieve_core_memory`
- workspace/folder ingestion with progress and cancellation events

## Recovered tool families

The bytecode exposes tool descriptions and dispatch names for:

- file search/read/write and folder ingestion;
- application launch and window arrangement;
- terminal/process execution;
- browser automation and external web opening;
- clipboard, wallpaper, volume, screenshots, and OCR;
- Gmail authorization, reading, drafting, and sending;
- WhatsApp messaging;
- ADB connection, telemetry, tap/swipe, notifications, screenshots, calls, file transfer, and camera control;
- weather, stocks, navigation, maps, deep research, image generation, widgets, and live code/website generation.

Some tools are gated by FREE/PRO usage checks and emit upgrade overlays.

## Renderer IPC surface

The readable renderer directly references **94 IPC channels**. Important groups include:

### Voice/session

```text
iris:send-text
iris:clear-history
iris:cancel-tool-execution
iris:tool-execution-start
iris:tool-execution-end
iris:missing-api-key
```

### Vault/credentials

```text
check-vault-status
setup-vault-pin
verify-vault-pin
setup-vault-face
verify-vault-face
reset-vault-faces
secure-save-keys
secure-get-keys
verify-server-signature
```

### System and automation

```text
get-system-hwid
get-system-stats
get-installed-apps
open-in-vscode
open-website-external
clipboard-write
terminal-data
```

### ADB/mobile

```text
adb-connect
adb-disconnect
adb-start-stream
adb-stop-stream
adb-tap
adb-swipe
adb-telemetry
adb-get-notifications
```

The complete recovered channel map is in `IRIS_RECOVERED_INTERFACE.json`.

## Recovered network services

Relevant visible endpoints include:

```text
https://hub.irisxai.in
https://hub.irisxai.in/users/google
https://hub.irisxai.in/users/refresh-token
http://localhost:3456/oauth2callback
Google Generative Language API endpoints
Open-Meteo and geocoding APIs
OpenStreetMap Nominatim / OSRM
Yahoo Finance chart API
```

## What is decoded versus not decoded

### Recovered with high confidence

- package layout and dependencies;
- renderer UI bundle;
- preload public API surface;
- IPC channel inventory;
- provider/model names;
- network endpoints;
- tool names and descriptions;
- voice, memory, vault, ADB, Gmail, and research workflows;
- approximate control flow and subsystem boundaries.

### Not recovered exactly

- original TypeScript/JavaScript formatting;
- comments and source maps;
- original local variable names;
- exact implementation of every main-process handler;
- exact source of the protected 199,355-character main module;
- exact source of the protected 2,372-character preload module.

## Honest conclusion

The `.jsc` is not encrypted; it is version-bound serialized V8 bytecode. A one-click source restoration is not available. Nevertheless, the combination of ASAR extraction, renderer analysis, loader analysis, cached-data metadata, string/constants recovery, and IPC mapping has recovered a large portion of IRIS's behavior and architecture without executing the privileged application.
