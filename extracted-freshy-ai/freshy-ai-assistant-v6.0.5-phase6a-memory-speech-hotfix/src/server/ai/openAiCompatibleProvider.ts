import type { AiProvider } from "./providerBase";
import type {
  ChatMessage,
  ProviderResponse,
  ProviderTool,
  ToolRequest,
} from "./schemas";

export type FetchLike = typeof fetch;

function safeError(value: unknown): string {
  return String(value ?? "Unknown provider error")
    .replace(/(bearer\s+)[\w.+/=-]+/gi, "$1[REDACTED]")
    .replace(/(api[_ -]?key\s*[:=]?\s*)[^\s,;]+/gi, "$1[REDACTED]")
    .slice(0, 240);
}

function normalizeContent(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (!Array.isArray(value)) return "";
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        return typeof record.text === "string"
          ? record.text
          : typeof record.content === "string"
            ? record.content
            : "";
      }
      return "";
    })
    .filter(Boolean)
    .join("\n")
    .trim();
}

export class OpenAiCompatibleProvider implements AiProvider {
  constructor(
    public readonly providerName: string,
    private readonly baseUrl: string,
    private readonly apiKey: string,
    public readonly modelName: string,
    private readonly timeoutMs: number,
    private readonly maxOutputTokens: number,
    private readonly temperature: number,
    private readonly fetchFn: FetchLike = fetch,
  ) {}

  isConfigured(): boolean {
    const key = this.apiKey.trim().toLowerCase();
    return Boolean(
      key &&
        ![
          "my_groq_api_key",
          "my_mistral_api_key",
          "my_sambanova_api_key",
        ].includes(key) &&
        this.modelName.trim(),
    );
  }

  supportsTools(): boolean {
    return true;
  }

  healthCheck(): boolean {
    return this.isConfigured();
  }

  normalizeError(error: unknown): string {
    if (error instanceof Error && error.name === "AbortError") return "timeout";
    const text = String(error ?? "").toLowerCase();
    if (/401|unauthori|api key/.test(text)) return "authentication_error";
    if (/403|permission/.test(text)) return "permission_error";
    if (/429|rate limit|quota/.test(text)) return "rate_limited";
    if (/404|model.*not found|invalid model/.test(text)) return "invalid_model";
    if (/400|422|bad request|invalid request/.test(text)) return "invalid_request";
    if (/timeout|abort/.test(text)) return "timeout";
    if (/500|502|503|504|unavailable/.test(text)) return "provider_unavailable";
    if (/fetch|network|econn/.test(text)) return "network_error";
    return "unknown_provider_error";
  }

  async generate(
    messages: ChatMessage[],
    systemInstruction?: string,
    tools?: ProviderTool[],
  ): Promise<ProviderResponse> {
    if (!this.isConfigured()) {
      return {
        success: false,
        content: "",
        toolCalls: [],
        providerName: this.providerName,
        modelName: this.modelName,
        errorCode: "missing_key",
        errorMessage: "Provider is not configured.",
      };
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const url = this.baseUrl.replace(/\/$/, "").endsWith("/chat/completions")
        ? this.baseUrl.replace(/\/$/, "")
        : `${this.baseUrl.replace(/\/$/, "")}/chat/completions`;
      const formatted = [
        ...(systemInstruction
          ? [{ role: "system", content: systemInstruction }]
          : []),
        ...messages.map((message) => ({
          // ConversationStore keeps provider-agnostic tool result text, not the
          // original OpenAI tool_call_id. Sending it as a user context message
          // avoids an invalid standalone role=tool payload.
          role: message.role === "tool" ? "user" : message.role,
          content: message.content,
          ...(message.role !== "tool" && message.name
            ? { name: message.name }
            : {}),
        })),
      ];
      const response = await this.fetchFn(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.modelName,
          messages: formatted,
          temperature: this.temperature,
          max_tokens: this.maxOutputTokens,
          ...(tools && tools.length > 0
            ? { tools, tool_choice: "auto" }
            : {}),
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const body = (await response.text()).slice(0, 240);
        throw new Error(`HTTP ${response.status}: ${body}`);
      }
      const payload = (await response.json()) as Record<string, unknown>;
      const choices = Array.isArray(payload.choices) ? payload.choices : [];
      const first = choices[0] as Record<string, unknown> | undefined;
      const message =
        first?.message && typeof first.message === "object"
          ? (first.message as Record<string, unknown>)
          : {};
      const content = normalizeContent(message.content);
      const toolCalls: ToolRequest[] = [];
      for (const raw of Array.isArray(message.tool_calls)
        ? message.tool_calls
        : []) {
        if (!raw || typeof raw !== "object") continue;
        const record = raw as Record<string, unknown>;
        const fn =
          record.function && typeof record.function === "object"
            ? (record.function as Record<string, unknown>)
            : {};
        if (typeof fn.name !== "string") continue;
        let args: Record<string, unknown> = {};
        try {
          const value =
            typeof fn.arguments === "string"
              ? JSON.parse(fn.arguments)
              : fn.arguments;
          if (value && typeof value === "object" && !Array.isArray(value)) {
            args = value as Record<string, unknown>;
          }
        } catch {
          args = {};
        }
        toolCalls.push({
          name: fn.name,
          arguments: args,
          callId: typeof record.id === "string" ? record.id : undefined,
        });
      }
      if (!content && toolCalls.length === 0) {
        return {
          success: false,
          content: "",
          toolCalls: [],
          providerName: this.providerName,
          modelName: this.modelName,
          errorCode: "malformed_response",
          errorMessage: "Provider returned an empty response.",
        };
      }
      return {
        success: true,
        content,
        toolCalls,
        providerName: this.providerName,
        modelName: this.modelName,
      };
    } catch (error) {
      return {
        success: false,
        content: "",
        toolCalls: [],
        providerName: this.providerName,
        modelName: this.modelName,
        errorCode: this.normalizeError(error),
        errorMessage: safeError(error),
      };
    } finally {
      clearTimeout(timer);
    }
  }
}
