import type { AiConfig } from "./config";
import type { AiProvider } from "./providerBase";
import type {
  ChatMessage,
  ProviderAttempt,
  ProviderResponse,
  ProviderTool,
} from "./schemas";

const TRANSIENT = new Set([
  "rate_limited",
  "timeout",
  "network_error",
  "provider_unavailable",
]);
const FATAL = new Set([
  "authentication_error",
  "permission_error",
  "missing_key",
  "invalid_model",
  "invalid_request",
]);

export class ProviderRouter {
  readonly providers = new Map<string, AiProvider>();
  private readonly cooldowns = new Map<string, number>();

  constructor(
    providers: AiProvider[],
    private readonly config: AiConfig,
    private readonly now: () => number = Date.now,
    private readonly sleep: (ms: number) => Promise<void> = (ms) =>
      new Promise((resolve) => setTimeout(resolve, ms)),
  ) {
    for (const provider of providers) {
      this.providers.set(provider.providerName, provider);
    }
  }

  hasAvailableProvider(): boolean {
    if (!this.config.enabled) return false;
    const seen = new Set<string>();
    for (const name of this.config.providerOrder) {
      if (seen.has(name)) continue;
      seen.add(name);
      const provider = this.providers.get(name);
      if (provider?.isConfigured() && !this.isCooldown(name)) return true;
    }
    return false;
  }

  isCooldown(name: string): boolean {
    const end = this.cooldowns.get(name) ?? 0;
    if (end > 0 && end <= this.now()) {
      this.cooldowns.delete(name);
      return false;
    }
    return end > this.now();
  }

  private setCooldown(name: string): void {
    this.cooldowns.set(name, this.now() + this.config.cooldownMs);
  }

  private async executeWithRetry(
    provider: AiProvider,
    messages: ChatMessage[],
    systemInstruction?: string,
    tools?: ProviderTool[],
  ): Promise<ProviderResponse> {
    let retry = 0;
    while (true) {
      const response = await provider.generate(messages, systemInstruction, tools);
      if (
        response.success ||
        FATAL.has(response.errorCode ?? "") ||
        !TRANSIENT.has(response.errorCode ?? "") ||
        retry >= this.config.maxRetries
      ) {
        return response;
      }
      retry += 1;
      await this.sleep(Math.min(retry * 250, 1000));
    }
  }

  async route(
    messages: ChatMessage[],
    systemInstruction?: string,
    tools?: ProviderTool[],
  ): Promise<{ response: ProviderResponse; fallbackChain: ProviderAttempt[] }> {
    const fallbackChain: ProviderAttempt[] = [];
    if (!this.config.enabled) {
      return {
        response: {
          success: false,
          content: "",
          toolCalls: [],
          providerName: "none",
          modelName: "",
          errorCode: "ai_disabled",
          errorMessage: "AI routing is disabled.",
        },
        fallbackChain,
      };
    }

    const seen = new Set<string>();
    for (const name of this.config.providerOrder) {
      if (seen.has(name)) continue;
      seen.add(name);
      const provider = this.providers.get(name);
      if (!provider) {
        fallbackChain.push({ provider: name, status: "unsupported_provider" });
        continue;
      }
      if (!provider.isConfigured()) {
        fallbackChain.push({ provider: name, status: "missing_key" });
        continue;
      }
      if (this.isCooldown(name)) {
        fallbackChain.push({ provider: name, status: "cooldown" });
        continue;
      }
      const response = await this.executeWithRetry(
        provider,
        messages,
        systemInstruction,
        tools,
      );
      fallbackChain.push({
        provider: name,
        status: response.success ? "success" : response.errorCode ?? "failed",
      });
      if (response.success) return { response, fallbackChain };
      if (TRANSIENT.has(response.errorCode ?? "")) this.setCooldown(name);
    }

    return {
      response: {
        success: false,
        content: "",
        toolCalls: [],
        providerName: "none",
        modelName: "",
        errorCode: "all_providers_failed",
        errorMessage: "No configured AI provider completed the request.",
      },
      fallbackChain,
    };
  }

  status(): Record<string, unknown> {
    const providers: Record<string, unknown> = {};
    for (const [name, provider] of this.providers) {
      const remaining = Math.max(
        0,
        Math.floor(((this.cooldowns.get(name) ?? 0) - this.now()) / 1000),
      );
      providers[name] = {
        configured: provider.isConfigured(),
        model: provider.modelName,
        cooldown_active: remaining > 0,
        cooldown_remaining_seconds: remaining,
      };
    }
    return {
      ai_enabled: this.config.enabled,
      provider_order: this.config.providerOrder,
      providers,
    };
  }
}
