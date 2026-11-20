import type {
  ChatMessage,
  ProviderResponse,
  ProviderTool,
} from "./schemas";

export interface AiProvider {
  readonly providerName: string;
  readonly modelName: string;
  isConfigured(): boolean;
  supportsTools(): boolean;
  healthCheck(): boolean;
  normalizeError(error: unknown): string;
  generate(
    messages: ChatMessage[],
    systemInstruction?: string,
    tools?: ProviderTool[],
  ): Promise<ProviderResponse>;
}
