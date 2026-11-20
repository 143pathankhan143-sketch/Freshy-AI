import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";
import { createAssistantOrchestrator } from "./src/server/ai";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());


  const assistantOrchestrator = createAssistantOrchestrator();

  // --- API Routes ---
  app.get("/health", (req, res) => {
    res.json({
      status: "ok",
      app: "Freshy AI Desktop Web Preview",
      version: "6.0.2 - Phase 6 Desktop Web Preview",
      host: "0.0.0.0",
      port: PORT
    });
  });

  app.get("/api/status", (_req, res) => {
    res.json({
      status: "online",
      mode: "Phase 6 desktop web preview",
      native_windows_actions_execute: false,
      python_core_url: "http://127.0.0.1:8000",
      freshy_version: "6.0.2 - Desktop Complete",
      ai: assistantOrchestrator.status(),
    });
  });

  app.get("/api/commands", (req, res) => {
    res.json({
      commands: [
        { phrase: "Hello Freshy / Hi / Hey", intent: "GREETING", description: "Greets Freshy assistant" },
        { phrase: "What time is it / What is today's date?", intent: "TIME_DATE", description: "Returns current local time and date" },
        { phrase: "Open Notepad / Notepad kholo", intent: "OPEN_APP", description: "Launches Windows Notepad" },
        { phrase: "Open Calculator / Calculator kholo", intent: "OPEN_APP", description: "Launches Windows Calculator" },
        { phrase: "Open website (e.g. Open Google / Open YouTube)", intent: "OPEN_WEBSITE", description: "Opens website URL in browser" }
      ]
    });
  });


  // Preview TTS endpoints
  let previewTtsSettings = {
    enabled: true,
    selected_voice: "",
    rate: 175,
    volume: 1.0,
    startup_greeting: true
  };

  app.get("/api/tts/settings", (req, res) => {
    res.json(previewTtsSettings);
  });

  app.post("/api/tts/settings", (req, res) => {
    previewTtsSettings = { ...previewTtsSettings, ...req.body };
    res.json(previewTtsSettings);
  });

  app.get("/api/tts/voices", (req, res) => {
    res.json({
      voices: []
    });
  });

  app.get("/api/tts/status", (req, res) => {
    res.json({
      is_speaking: false,
      queue_size: 0,
      enabled: previewTtsSettings.enabled,
      engine_available: false,
      engine_initializing: false,
      error_status: "Offline Windows SAPI5 voice output runs only through local Python Core",
      current_text: null
    });
  });

  app.post("/api/tts/test", (req, res) => {
    res.json({
      status: "rejected",
      accepted: false,
      reason: "Offline Windows SAPI5 voice output runs only through local Python Core",
      text: req.body?.text || ""
    });
  });

  app.post("/api/tts/stop", (req, res) => {
    res.json({
      status: "error",
      accepted: false,
      reason: "Offline Windows SAPI5 voice output runs only through local Python Core"
    });
  });

  // Preview Voice Input endpoints (Non-simulating stubs)
  let previewVoiceSettings = {
    device_index: null,
    wake_word_enabled: true,
    continuous_listening: false,
    hotkey_enabled: true,
    listening_timeout: 7.0,
    muted: false,
    noise_threshold: 0.02,
  };

  app.get("/api/voice/settings", (req, res) => {
    res.json(previewVoiceSettings);
  });

  app.post("/api/voice/settings", (req, res) => {
    previewVoiceSettings = { ...previewVoiceSettings, ...req.body };
    res.json(previewVoiceSettings);
  });

  app.get("/api/voice/devices", (req, res) => {
    res.json({ devices: [] });
  });

  app.get("/api/voice/status", (req, res) => {
    res.json({
      is_listening: false,
      is_calibrating: false,
      model_loaded: false,
      mic_available: false,
      error_status: "Offline Vosk voice recognition runs only through local Python Core on Windows",
      freshy_status: "idle",
      voice_mode: "disabled",
      session_id: "",
      result_id: 0,
      partial_transcript: "",
      final_transcript: "",
      assistant_reply: "",
      intent: "",
      action_result: {},
      settings: previewVoiceSettings,
      shutdown_state: "active",
    });
  });

  app.post("/api/voice/listen/start", (req, res) => {
    res.status(503).json({
      accepted: false,
      reason: "Offline Vosk voice recognition runs only through local Python Core on Windows"
    });
  });

  app.post("/api/voice/listen/stop", (req, res) => {
    res.json({
      accepted: true,
      reason: "Offline Vosk voice recognition is stopped"
    });
  });

  app.post("/api/voice/calibrate", (req, res) => {
    res.status(500).json({
      success: false,
      reason: "Offline Vosk voice recognition runs only through local Python Core on Windows"
    });
  });

  app.get("/api/memory/status", (_req, res) => {
    res.json(assistantOrchestrator.memory.status());
  });

  app.get("/api/memory/settings", (_req, res) => {
    const settings = assistantOrchestrator.memory.settings;
    res.json({
      enabled: settings.enabled,
      mode: settings.mode,
      persist_conversations: settings.persistConversations,
      auto_profile_detection: settings.autoProfileDetection,
      max_items: settings.maxItems,
      max_item_characters: settings.maxItemCharacters,
      recall_limit: settings.recallLimit,
      recall_characters: settings.recallCharacters,
      conversation_retention_days: 30,
    });
  });

  app.post("/api/memory/settings", (req, res) => {
    try {
      const settings = assistantOrchestrator.memory.updateSettings({
        enabled:
          typeof req.body?.enabled === "boolean" ? req.body.enabled : undefined,
        mode:
          typeof req.body?.mode === "string"
            ? (req.body.mode as
                | "ask_before_saving"
                | "auto_safe"
                | "manual_only"
                | "disabled")
            : undefined,
        persistConversations:
          typeof req.body?.persist_conversations === "boolean"
            ? req.body.persist_conversations
            : undefined,
        autoProfileDetection:
          typeof req.body?.auto_profile_detection === "boolean"
            ? req.body.auto_profile_detection
            : undefined,
        maxItems:
          typeof req.body?.max_items === "number" ? req.body.max_items : undefined,
        maxItemCharacters:
          typeof req.body?.max_item_characters === "number"
            ? req.body.max_item_characters
            : undefined,
        recallLimit:
          typeof req.body?.recall_limit === "number"
            ? req.body.recall_limit
            : undefined,
        recallCharacters:
          typeof req.body?.recall_characters === "number"
            ? req.body.recall_characters
            : undefined,
      });
      res.json({
        enabled: settings.enabled,
        mode: settings.mode,
        persist_conversations: settings.persistConversations,
        auto_profile_detection: settings.autoProfileDetection,
        max_items: settings.maxItems,
        max_item_characters: settings.maxItemCharacters,
        recall_limit: settings.recallLimit,
        recall_characters: settings.recallCharacters,
        conversation_retention_days: 30,
      });
    } catch (error) {
      res.status(400).json({
        detail: error instanceof Error ? error.message : "Invalid memory settings.",
      });
    }
  });

  app.get("/api/memory", (req, res) => {
    const query = typeof req.query.query === "string" ? req.query.query : "";
    const category =
      typeof req.query.category === "string" ? req.query.category : undefined;
    const items = assistantOrchestrator.memory.list(query, category);
    res.json({
      items: items.map((item) => ({
        id: item.id,
        category: item.category,
        key: item.key,
        value: item.value,
        tags: item.tags,
        importance: item.importance,
        pinned: item.pinned,
        source: "web_preview_memory",
        created_at: item.createdAt,
        updated_at: item.updatedAt,
        access_count: item.accessCount,
      })),
      total: items.length,
    });
  });

  app.post("/api/memory", (req, res) => {
    try {
      const result = assistantOrchestrator.memory.create({
        category: req.body?.category,
        key: req.body?.key,
        value: req.body?.value,
        tags: Array.isArray(req.body?.tags) ? req.body.tags : [],
        importance: req.body?.importance,
        pinned: req.body?.pinned,
      });
      res.json({
        created: result.created,
        item: {
          id: result.item.id,
          category: result.item.category,
          key: result.item.key,
          value: result.item.value,
          tags: result.item.tags,
          importance: result.item.importance,
          pinned: result.item.pinned,
          source: "web_preview_memory",
          created_at: result.item.createdAt,
          updated_at: result.item.updatedAt,
          access_count: result.item.accessCount,
        },
      });
    } catch (error) {
      res.status(400).json({
        detail: error instanceof Error ? error.message : "Memory could not be saved.",
      });
    }
  });

  app.put("/api/memory/:memoryId", (req, res) => {
    try {
      const item = assistantOrchestrator.memory.update(req.params.memoryId, {
        category: req.body?.category,
        key: req.body?.key,
        value: req.body?.value,
        tags: Array.isArray(req.body?.tags) ? req.body.tags : undefined,
        importance: req.body?.importance,
        pinned: req.body?.pinned,
      });
      if (!item) {
        res.status(404).json({ detail: "Memory not found." });
        return;
      }
      res.json({
        id: item.id,
        category: item.category,
        key: item.key,
        value: item.value,
        tags: item.tags,
        importance: item.importance,
        pinned: item.pinned,
        source: "web_preview_memory",
        created_at: item.createdAt,
        updated_at: item.updatedAt,
        access_count: item.accessCount,
      });
    } catch (error) {
      res.status(409).json({
        detail: error instanceof Error ? error.message : "Memory update failed.",
      });
    }
  });

  app.delete("/api/memory/:memoryId", (req, res) => {
    if (!assistantOrchestrator.memory.delete(req.params.memoryId)) {
      res.status(404).json({ detail: "Memory not found." });
      return;
    }
    res.json({ status: "ok", deleted: true, memory_id: req.params.memoryId });
  });

  app.post("/api/memory/:memoryId/pin", (req, res) => {
    const pinned = req.query.pinned !== "false";
    const item = assistantOrchestrator.memory.pin(req.params.memoryId, pinned);
    if (!item) {
      res.status(404).json({ detail: "Memory not found." });
      return;
    }
    res.json({
      id: item.id,
      category: item.category,
      key: item.key,
      value: item.value,
      tags: item.tags,
      importance: item.importance,
      pinned: item.pinned,
      source: "web_preview_memory",
      created_at: item.createdAt,
      updated_at: item.updatedAt,
      access_count: item.accessCount,
    });
  });

  app.post("/api/memory/clear", (req, res) => {
    if (req.body?.confirm !== true) {
      res.status(400).json({ detail: "Explicit confirmation is required." });
      return;
    }
    res.json({
      status: "ok",
      deleted_count: assistantOrchestrator.memory.clear(),
    });
  });

  app.post("/api/memory/conversations/clear", (req, res) => {
    if (req.body?.confirm !== true) {
      res.status(400).json({ detail: "Explicit confirmation is required." });
      return;
    }
    const cleared = assistantOrchestrator.memory.clearAllConversations();
    res.json({
      status: "ok",
      deleted_sessions: cleared.sessions,
      deleted_messages: cleared.messages,
    });
  });

  app.get("/api/memory/export", (_req, res) => {
    res.json(assistantOrchestrator.memory.exportData());
  });

  app.post("/api/memory/import", (req, res) => {
    if (!Array.isArray(req.body?.items)) {
      res.status(400).json({ detail: "A memory backup items array is required." });
      return;
    }
    const result = assistantOrchestrator.memory.importData(
      req.body.items,
      req.body?.replace_existing === true,
    );
    res.json({ status: "ok", ...result });
  });

  app.post("/api/conversation/clear", (req, res) => {
    const sessionId =
      typeof req.body?.session_id === "string"
        ? req.body.session_id
        : "default-session";
    assistantOrchestrator.clearConversation(sessionId);
    res.json({
      status: "ok",
      session_id: sessionId,
      message: "Conversation history has been cleared.",
    });
  });

  app.get("/api/ai/status", (_req, res) => {
    res.json(assistantOrchestrator.status());
  });

  app.post("/api/chat", async (req, res) => {
    const message =
      typeof req.body?.message === "string" ? req.body.message.trim() : "";
    if (!message) {
      res.status(400).json({ detail: "Message cannot be empty." });
      return;
    }
    try {
      const response = await assistantOrchestrator.handleRequest({
        message,
        session_id:
          typeof req.body?.session_id === "string"
            ? req.body.session_id
            : "default-session",
        allow_web_search: req.body?.allow_web_search !== false,
      });
      res.json(response);
    } catch (error) {
      console.warn(
        "[Freshy Web Preview] Chat request failed safely:",
        error instanceof Error ? error.name : "unknown_error",
      );
      res.status(500).json({
        success: false,
        reply: "Freshy could not process this request.",
        intent_name: "ERROR",
        confidence: 0,
        action_executed: false,
        freshy_status: "idle",
        details: { error: "internal_server_error" },
        provider: "none",
        model: null,
        used_web_search: false,
        sources: [],
        fallback_chain: [],
        tool_used: null,
        tts_requested: false,
        error_code: "internal_server_error",
      });
    }
  });

  // Vite middleware setup
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        host: "0.0.0.0",
        allowedHosts: true,
        hmr: { clientPort: PORT },
      },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Freshy AI Application running on http://localhost:${PORT}`);
  });
}

startServer();
