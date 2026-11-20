import type { ChatMessage, ChatRole } from "./schemas";

export interface ConversationPersistence {
  addConversation(
    sessionId: string | undefined,
    role: ChatRole,
    content: string,
    name?: string,
  ): void;
  loadConversation(sessionId: string | undefined): ChatMessage[];
  clearConversation(sessionId: string | undefined): boolean;
}

export class ConversationStore {
  private readonly sessions = new Map<string, ChatMessage[]>();
  private readonly loaded = new Set<string>();

  constructor(
    private readonly maxMessages: number,
    private readonly maxCharacters: number,
    private readonly persistence?: ConversationPersistence,
  ) {}

  private normalizeSessionId(sessionId?: string): string {
    return String(sessionId ?? "default-session").trim().slice(0, 128) ||
      "default-session";
  }

  private ensureLoaded(sessionId?: string): string {
    const key = this.normalizeSessionId(sessionId);
    if (this.loaded.has(key)) return key;
    this.loaded.add(key);
    const persisted = this.persistence?.loadConversation(key) ?? [];
    if (persisted.length > 0) {
      const history = persisted.map((item) => ({ ...item }));
      this.prune(history);
      this.sessions.set(key, history);
    }
    return key;
  }

  private prune(history: ChatMessage[]): void {
    while (history.length > this.maxMessages) history.shift();
    let characters = history.reduce((sum, item) => sum + item.content.length, 0);
    while (history.length > 0 && characters > this.maxCharacters) {
      const removed = history.shift();
      characters -= removed?.content.length ?? 0;
    }
  }

  add(
    sessionId: string | undefined,
    role: ChatRole,
    content: string,
    name?: string,
  ): void {
    let clean = String(content ?? "").trim();
    if (!clean) return;
    if (clean.length > this.maxCharacters) clean = clean.slice(-this.maxCharacters);
    const key = this.ensureLoaded(sessionId);
    const history = this.sessions.get(key) ?? [];
    history.push({ role, content: clean, ...(name ? { name } : {}) });
    this.prune(history);
    this.sessions.set(key, history);
    this.persistence?.addConversation(key, role, clean, name);
  }

  get(sessionId?: string): ChatMessage[] {
    const key = this.ensureLoaded(sessionId);
    const history = this.sessions.get(key) ?? [];
    return history.map((item) => ({ ...item }));
  }

  clear(sessionId?: string): boolean {
    const key = this.normalizeSessionId(sessionId);
    this.loaded.delete(key);
    const memoryCleared = this.sessions.delete(key);
    const persistedCleared = this.persistence?.clearConversation(key) ?? false;
    return memoryCleared || persistedCleared;
  }

  count(): number {
    return this.sessions.size;
  }
}
