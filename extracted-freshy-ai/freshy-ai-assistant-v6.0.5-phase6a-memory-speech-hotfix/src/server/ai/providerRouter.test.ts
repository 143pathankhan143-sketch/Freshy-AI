import assert from "node:assert/strict";
import test from "node:test";
import type { AiConfig } from "./config";
import type { AiProvider } from "./providerBase";
import { ProviderRouter } from "./providerRouter";
import type {
  ChatMessage,
  ProviderResponse,
  ProviderTool,
} from "./schemas";

class FakeProvider implements AiProvider {
  calls = 0;

  constructor(
    readonly providerName: string,
    readonly modelName: string,
    private readonly configured: boolean,
    private readonly responses: ProviderResponse[],
  ) {}

  isConfigured(): boolean {
    return this.configured;
  }
  supportsTools(): boolean {
    return true;
  }
  healthCheck(): boolean {
    return this.configured;
  }
  normalizeError(): string {
    return "unknown_provider_error";
  }
  async generate(
    _messages: ChatMessage[],
    _systemInstruction?: string,
    _tools?: ProviderTool[],
  ): Promise<ProviderResponse> {
    const index = Math.min(this.calls, this.responses.length - 1);
    this.calls += 1;
    return this.responses[index];
  }
}

const config: AiConfig = {
  enabled: true,
  providerOrder: ["groq", "mistral", "gemini", "sambanova"],
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

function response(
  providerName: string,
  success: boolean,
  errorCode?: string,
): ProviderResponse {
  return {
    success,
    content: success ? `${providerName} answer` : "",
    toolCalls: [],
    providerName,
    modelName: `${providerName}-model`,
    errorCode,
  };
}

test("router skips missing provider and falls back in configured order", async () => {
  const groq = new FakeProvider("groq", "g", false, [response("groq", false)]);
  const mistral = new FakeProvider("mistral", "m", true, [
    response("mistral", false, "rate_limited"),
  ]);
  const gemini = new FakeProvider("gemini", "x", true, [response("gemini", true)]);
  const router = new ProviderRouter(
    [groq, mistral, gemini],
    config,
    () => 1000,
    async () => {},
  );
  const result = await router.route([{ role: "user", content: "hello" }]);
  assert.equal(result.response.providerName, "gemini");
  assert.deepEqual(result.fallbackChain, [
    { provider: "groq", status: "missing_key" },
    { provider: "mistral", status: "rate_limited" },
    { provider: "gemini", status: "success" },
    { provider: "sambanova", status: "unsupported_provider" },
  ].slice(0, 3));
  assert.equal(mistral.calls, 1);
  assert.equal(gemini.calls, 1);
});

test("cooldown provider is skipped without an emergency retry", async () => {
  let now = 1000;
  const groq = new FakeProvider("groq", "g", true, [
    response("groq", false, "timeout"),
  ]);
  const router = new ProviderRouter(
    [groq],
    { ...config, providerOrder: ["groq"] },
    () => now,
    async () => {},
  );
  await router.route([{ role: "user", content: "first" }]);
  const second = await router.route([{ role: "user", content: "second" }]);
  assert.equal(groq.calls, 1);
  assert.equal(second.fallbackChain[0]?.status, "cooldown");
  now += 60001;
  await router.route([{ role: "user", content: "third" }]);
  assert.equal(groq.calls, 2);
});
