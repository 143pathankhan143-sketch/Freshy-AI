export interface AiConfig {
  enabled: boolean;
  providerOrder: string[];
  requestTimeoutMs: number;
  maxRetries: number;
  cooldownMs: number;
  maxHistoryMessages: number;
  maxHistoryCharacters: number;
  maxInputCharacters: number;
  maxOutputTokens: number;
  temperature: number;
  webSearchEnabled: boolean;
  tavilyTimeoutMs: number;
  tavilyMaxResults: number;
  tavilySearchDepth: "basic" | "advanced";
  memoryEnabled?: boolean;
  memoryMode?: "ask_before_saving" | "auto_safe" | "manual_only" | "disabled";
  memoryFilePath?: string;
  memoryPersistConversations?: boolean;
  memoryAutoProfileDetection?: boolean;
  memoryMaxItems?: number;
  memoryMaxItemCharacters?: number;
  memoryRecallLimit?: number;
  memoryRecallCharacters?: number;
}

function boolEnv(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) return fallback;
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return fallback;
}

function intEnv(
  value: string | undefined,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum
    ? parsed
    : fallback;
}

function floatEnv(
  value: string | undefined,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  const parsed = Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum
    ? parsed
    : fallback;
}

export function providerOrderFromEnv(value: string | undefined): string[] {
  const supported = new Set(["groq", "mistral", "gemini", "sambanova"]);
  const output: string[] = [];
  for (const item of (value ?? "groq,mistral,gemini,sambanova").split(",")) {
    const name = item.trim().toLowerCase();
    if (supported.has(name) && !output.includes(name)) output.push(name);
  }
  return output.length > 0
    ? output
    : ["groq", "mistral", "gemini", "sambanova"];
}

export function loadAiConfig(env: NodeJS.ProcessEnv = process.env): AiConfig {
  const depth = env.TAVILY_SEARCH_DEPTH?.trim().toLowerCase();
  return {
    enabled: boolEnv(env.AI_ENABLED, true),
    providerOrder: providerOrderFromEnv(env.AI_PROVIDER_ORDER),
    requestTimeoutMs:
      intEnv(env.AI_REQUEST_TIMEOUT_SECONDS, 25, 1, 300) * 1000,
    maxRetries: intEnv(env.AI_MAX_RETRIES, 1, 0, 3),
    cooldownMs:
      intEnv(env.AI_PROVIDER_COOLDOWN_SECONDS, 60, 1, 3600) * 1000,
    maxHistoryMessages: intEnv(env.AI_MAX_HISTORY_MESSAGES, 16, 2, 100),
    maxHistoryCharacters: intEnv(
      env.AI_MAX_HISTORY_CHARACTERS,
      24000,
      1000,
      100000,
    ),
    maxInputCharacters: intEnv(env.AI_MAX_INPUT_CHARACTERS, 12000, 100, 50000),
    maxOutputTokens: intEnv(env.AI_MAX_OUTPUT_TOKENS, 1200, 64, 10000),
    temperature: floatEnv(env.AI_TEMPERATURE, 0.3, 0, 2),
    webSearchEnabled: boolEnv(env.WEB_SEARCH_ENABLED, true),
    tavilyTimeoutMs: intEnv(env.TAVILY_TIMEOUT_SECONDS, 15, 1, 60) * 1000,
    tavilyMaxResults: intEnv(env.TAVILY_MAX_RESULTS, 5, 1, 20),
    tavilySearchDepth: depth === "advanced" ? "advanced" : "basic",
    memoryEnabled: boolEnv(env.MEMORY_ENABLED, true),
    memoryMode: (["ask_before_saving", "auto_safe", "manual_only", "disabled"] as const).includes(
      (env.MEMORY_MODE?.trim().toLowerCase() || "ask_before_saving") as
        | "ask_before_saving"
        | "auto_safe"
        | "manual_only"
        | "disabled",
    )
      ? ((env.MEMORY_MODE?.trim().toLowerCase() || "ask_before_saving") as
          | "ask_before_saving"
          | "auto_safe"
          | "manual_only"
          | "disabled")
      : "ask_before_saving",
    memoryFilePath:
      env.MEMORY_NODE_FILE_PATH?.trim() || ".freshy-data/web-preview-memory.json",
    memoryPersistConversations: boolEnv(env.MEMORY_PERSIST_CONVERSATIONS, true),
    memoryAutoProfileDetection: boolEnv(env.MEMORY_AUTO_PROFILE_DETECTION, true),
    memoryMaxItems: intEnv(env.MEMORY_MAX_ITEMS, 500, 10, 5000),
    memoryMaxItemCharacters: intEnv(
      env.MEMORY_MAX_ITEM_CHARACTERS,
      2000,
      100,
      10000,
    ),
    memoryRecallLimit: intEnv(env.MEMORY_RECALL_LIMIT, 6, 1, 20),
    memoryRecallCharacters: intEnv(
      env.MEMORY_RECALL_CHARACTERS,
      2500,
      250,
      12000,
    ),
  };
}
