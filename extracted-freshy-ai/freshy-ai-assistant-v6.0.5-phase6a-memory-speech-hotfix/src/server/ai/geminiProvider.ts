import { GoogleGenAI } from "@google/genai";
import type { AiProvider } from "./providerBase";
import type {
  ChatMessage,
  ProviderResponse,
  ProviderTool,
  ToolRequest,
} from "./schemas";

interface GeminiClientLike {
  models: {
    generateContent(request: Record<string, unknown>): Promise<any>;
  };
}

function safeError(value: unknown): string {
  return String(value ?? "Unknown Gemini error")
    .replace(/(api[_ -]?key\s*[:=]?\s*)[^\s,;]+/gi, "$1[REDACTED]")
    .replace(/(bearer\s+)[\w.+/=-]+/gi, "$1[REDACTED]")
    .slice(0, 240);
}

export class GeminiProvider implements AiProvider {
  private readonly client: GeminiClientLike | null;

  constructor(
    private readonly apiKey: string,
    public readonly modelName: string,
    private readonly timeoutMs: number,
    private readonly maxOutputTokens: number,
    private readonly temperature: number,
    client?: GeminiClientLike | null,
  ) {
    if (client !== undefined) {
      this.client = client;
    } else if (this.isConfigured()) {
      this.client = new GoogleGenAI({
        apiKey: this.apiKey,
        httpOptions: { timeout: this.timeoutMs },
      }) as unknown as GeminiClientLike;
    } else {
      this.client = null;
    }
  }

  get providerName(): string {
    return "gemini";
  }

  isConfigured(): boolean {
    const key = this.apiKey.trim().toLowerCase();
    return Boolean(
      key &&
        !["my_gemini_api_key", "my_gemini_api_key_here"].includes(key) &&
        this.modelName.trim(),
    );
  }

  supportsTools(): boolean {
    return true;
  }

  healthCheck(): boolean {
    return this.isConfigured() && this.client !== null;
  }

  normalizeError(error: unknown): string {
    const text = String(error ?? "").toLowerCase();
    if (/401|unauthori|api key/.test(text)) return "authentication_error";
    if (/403|permission/.test(text)) return "permission_error";
    if (/429|quota|rate limit|resource_exhausted/.test(text)) return "rate_limited";
    if (/timeout|deadline|abort/.test(text)) return "timeout";
    if (/404|model.*not found|invalid model/.test(text)) return "invalid_model";
    if (/400|bad request|invalid argument/.test(text)) return "invalid_request";
    if (/500|502|503|504|unavailable/.test(text)) return "provider_unavailable";
    if (/fetch|network|econn/.test(text)) return "network_error";
    return "unknown_provider_error";
  }

  async generate(
    messages: ChatMessage[],
    systemInstruction?: string,
    tools?: ProviderTool[],
  ): Promise<ProviderResponse> {
    if (!this.isConfigured() || !this.client) {
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
    try {
      const contents = messages
        .filter((message) => message.role !== "system")
        .map((message) => ({
          role: message.role === "assistant" ? "model" : "user",
          parts: [{ text: message.content }],
        }));
      const functionDeclarations = (tools ?? []).map((tool) => ({
        name: tool.function.name,
        description: tool.function.description,
        parametersJsonSchema: tool.function.parameters,
      }));
      const response = await this.client.models.generateContent({
        model: this.modelName,
        contents,
        config: {
          temperature: this.temperature,
          maxOutputTokens: this.maxOutputTokens,
          ...(systemInstruction ? { systemInstruction } : {}),
          ...(functionDeclarations.length > 0
            ? { tools: [{ functionDeclarations }] }
            : {}),
        },
      });
      const content = String(response?.text ?? "").trim();
      const rawCalls = Array.isArray(response?.functionCalls)
        ? response.functionCalls
        : Array.isArray(response?.function_calls)
          ? response.function_calls
          : [];
      const toolCalls: ToolRequest[] = rawCalls
        .filter((call: any) => typeof call?.name === "string")
        .map((call: any) => ({
          name: call.name,
          arguments:
            call.args && typeof call.args === "object" && !Array.isArray(call.args)
              ? call.args
              : {},
        }));
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
    }
  }
}
