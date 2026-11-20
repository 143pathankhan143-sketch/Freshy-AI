import assert from "node:assert/strict";
import test from "node:test";
import type { AiConfig } from "./config";
import { ConversationStore } from "./conversationStore";
import type { AiProvider } from "./providerBase";
import { ProviderRouter } from "./providerRouter";
import { SafeToolRegistry } from "./safeToolRegistry";
import type {
  ChatMessage,
  ProviderResponse,
  ProviderTool,
  SearchResult,
} from "./schemas";
import { AssistantOrchestrator } from "./assistantOrchestrator";
import { TavilySearch } from "./tavilySearch";

class QueueProvider implements AiProvider {
  calls = 0;
  constructor(
    readonly providerName: string,
    readonly modelName: string,
    private readonly queue: ProviderResponse[],
    private readonly configured = true,
  ) {}
  isConfigured(): boolean {
    return this.configured;
  }
  supportsTools(): boolean {
    return true;
  }
  healthCheck(): boolean {
    return true;
  }
  normalizeError(): string {
    return "unknown_provider_error";
  }
  async generate(
    _messages: ChatMessage[],
    _system?: string,
    _tools?: ProviderTool[],
  ): Promise<ProviderResponse> {
    const value = this.queue[Math.min(this.calls, this.queue.length - 1)];
    this.calls += 1;
    return value;
  }
}

const config: AiConfig = {
  enabled: true,
  providerOrder: ["groq"],
  requestTimeoutMs: 1000,
  maxRetries: 0,
  cooldownMs: 60000,
  maxHistoryMessages: 16,
  maxHistoryCharacters: 24000,
  maxInputCharacters: 12000,
  maxOutputTokens: 1200,
  temperature: 0.3,
  webSearchEnabled: true,
  tavilyTimeoutMs: 1000,
  tavilyMaxResults: 5,
  tavilySearchDepth: "basic",
};

function build(provider: QueueProvider, searchResults: SearchResult[] = []) {
  const search = new TavilySearch("test-key", 1000, 5, "basic");
  search.search = async () => searchResults;
  return new AssistantOrchestrator(
    new ProviderRouter([provider], config, () => 0, async () => {}),
    new ConversationStore(16, 24000),
    search,
    new SafeToolRegistry(search),
    config,
  );
}

test("local command consumes zero provider calls and never executes Windows action", async () => {
  const provider = new QueueProvider("groq", "model", [
    {
      success: true,
      content: "unused",
      toolCalls: [],
      providerName: "groq",
      modelName: "model",
    },
  ]);
  const result = await build(provider).handleRequest({ message: "Open Notepad" });
  assert.equal(provider.calls, 0);
  assert.equal(result.provider, "local");
  assert.equal(result.intent_name, "OPEN_APP");
  assert.equal(result.action_executed, false);
  assert.match(result.reply, /not executed/i);
});

test("general chat uses provider and current query includes real source metadata", async () => {
  const provider = new QueueProvider("groq", "model", [
    {
      success: true,
      content: "Grounded answer",
      toolCalls: [],
      providerName: "groq",
      modelName: "model",
    },
  ]);
  const source = {
    title: "Official release",
    url: "https://example.com/release",
    content: "Release notes",
  };
  const result = await build(provider, [source]).handleRequest({
    message: "What is the latest Flutter stable version?",
    session_id: "session-a",
  });
  assert.equal(provider.calls, 1);
  assert.equal(result.used_web_search, true);
  assert.deepEqual(result.sources, [source]);
  assert.equal(result.provider, "groq");
});

test("unsafe model tool request is blocked and not reported as executed", async () => {
  const provider = new QueueProvider("groq", "model", [
    {
      success: true,
      content: "",
      toolCalls: [
        { name: "open_application", arguments: { app_name: "powershell" } },
      ],
      providerName: "groq",
      modelName: "model",
    },
    {
      success: true,
      content: "The action was blocked.",
      toolCalls: [],
      providerName: "groq",
      modelName: "model",
    },
  ]);
  const result = await build(provider).handleRequest({ message: "Do something" });
  assert.equal(result.success, false);
  assert.equal(result.action_executed, false);
  assert.equal(result.error_code, "tool_failed");
  assert.equal(result.tool_used, "open_application");
});


test("unconfigured providers do not consume Tavily search", async () => {
  const provider = new QueueProvider(
    "groq",
    "model",
    [
      {
        success: true,
        content: "unused",
        toolCalls: [],
        providerName: "groq",
        modelName: "model",
      },
    ],
    false,
  );
  const search = new TavilySearch("test-key", 1000, 5, "basic");
  let searchCalls = 0;
  search.search = async () => {
    searchCalls += 1;
    return [{ title: "Unused", url: "https://example.com", content: "Unused" }];
  };
  const orchestrator = new AssistantOrchestrator(
    new ProviderRouter([provider], config, () => 0, async () => {}),
    new ConversationStore(16, 24000),
    search,
    new SafeToolRegistry(search),
    config,
  );
  const result = await orchestrator.handleRequest({
    message: "What is the latest Flutter version?",
  });
  assert.equal(result.success, false);
  assert.equal(result.provider, "none");
  assert.equal(provider.calls, 0);
  assert.equal(searchCalls, 0);
});
