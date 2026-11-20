import { AssistantOrchestrator } from "./assistantOrchestrator";
import { loadAiConfig } from "./config";
import { ConversationStore } from "./conversationStore";
import { GeminiProvider } from "./geminiProvider";
import { OpenAiCompatibleProvider } from "./openAiCompatibleProvider";
import { ProviderRouter } from "./providerRouter";
import { SafeToolRegistry } from "./safeToolRegistry";
import { TavilySearch } from "./tavilySearch";
import { PersistentMemoryStore } from "../memory/persistentMemoryStore";

export function createAssistantOrchestrator(
  env: NodeJS.ProcessEnv = process.env,
): AssistantOrchestrator {
  const config = loadAiConfig(env);
  const providers = [
    new OpenAiCompatibleProvider(
      "groq",
      env.GROQ_BASE_URL || "https://api.groq.com/openai/v1",
      env.GROQ_API_KEY || "",
      env.GROQ_MODEL || "llama-3.3-70b-versatile",
      config.requestTimeoutMs,
      config.maxOutputTokens,
      config.temperature,
    ),
    new OpenAiCompatibleProvider(
      "mistral",
      env.MISTRAL_BASE_URL || "https://api.mistral.ai/v1",
      env.MISTRAL_API_KEY || "",
      env.MISTRAL_MODEL || "mistral-small-latest",
      config.requestTimeoutMs,
      config.maxOutputTokens,
      config.temperature,
    ),
    new GeminiProvider(
      env.GEMINI_API_KEY || "",
      env.GEMINI_MODEL || "gemini-2.5-flash",
      config.requestTimeoutMs,
      config.maxOutputTokens,
      config.temperature,
    ),
    new OpenAiCompatibleProvider(
      "sambanova",
      env.SAMBANOVA_BASE_URL || "https://api.sambanova.ai/v1",
      env.SAMBANOVA_API_KEY || "",
      env.SAMBANOVA_MODEL || "Meta-Llama-3.3-70B-Instruct",
      config.requestTimeoutMs,
      config.maxOutputTokens,
      config.temperature,
    ),
  ];
  const search = new TavilySearch(
    env.TAVILY_API_KEY || "",
    config.tavilyTimeoutMs,
    config.tavilyMaxResults,
    config.tavilySearchDepth,
  );
  const memory = new PersistentMemoryStore(config.memoryFilePath ?? ".freshy-data/web-preview-memory.json", {
    enabled: config.memoryEnabled ?? true,
    mode: config.memoryMode ?? "ask_before_saving",
    persistConversations: config.memoryPersistConversations ?? true,
    autoProfileDetection: config.memoryAutoProfileDetection ?? true,
    maxItems: config.memoryMaxItems ?? 500,
    maxItemCharacters: config.memoryMaxItemCharacters ?? 2000,
    recallLimit: config.memoryRecallLimit ?? 6,
    recallCharacters: config.memoryRecallCharacters ?? 2500,
  });
  return new AssistantOrchestrator(
    new ProviderRouter(providers, config),
    new ConversationStore(
      config.maxHistoryMessages,
      config.maxHistoryCharacters,
      memory,
    ),
    search,
    new SafeToolRegistry(search),
    config,
    memory,
  );
}

export * from "./assistantOrchestrator";
export * from "./config";
export * from "./conversationStore";
export * from "./geminiProvider";
export * from "./openAiCompatibleProvider";
export * from "./providerBase";
export * from "./providerRouter";
export * from "./safeToolRegistry";
export * from "./schemas";
export * from "./tavilySearch";

export * from "../memory/persistentMemoryStore";
