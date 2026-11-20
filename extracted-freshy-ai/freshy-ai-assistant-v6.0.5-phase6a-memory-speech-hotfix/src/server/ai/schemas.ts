export type ChatRole = "user" | "assistant" | "system" | "tool";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  name?: string;
}

export interface ToolRequest {
  name: string;
  arguments: Record<string, unknown>;
  callId?: string;
}

export interface ProviderTool {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export interface ProviderResponse {
  success: boolean;
  content: string;
  toolCalls: ToolRequest[];
  providerName: string;
  modelName: string;
  errorCode?: string;
  errorMessage?: string;
}

export interface ProviderAttempt {
  provider: string;
  status: string;
}

export interface SearchResult {
  title: string;
  url: string;
  content: string;
  score?: number;
}

export interface AssistantRequest {
  message: string;
  session_id?: string;
  allow_web_search?: boolean;
}

export interface AssistantResponse {
  success: boolean;
  reply: string;
  intent_name: string;
  confidence: number;
  action_executed: boolean;
  freshy_status: "idle" | "speaking";
  details: Record<string, unknown>;
  provider: string;
  model: string | null;
  used_web_search: boolean;
  sources: SearchResult[];
  fallback_chain: ProviderAttempt[];
  tool_used: string | null;
  tts_requested: boolean;
  error_code: string | null;
  user_safe_error?: string | null;
  memory_used?: boolean;
  memory_count?: number;
  memory_pending?: boolean;
}

export interface ToolResult {
  success: boolean;
  output: string;
  error?: string;
  sources?: SearchResult[];
}
