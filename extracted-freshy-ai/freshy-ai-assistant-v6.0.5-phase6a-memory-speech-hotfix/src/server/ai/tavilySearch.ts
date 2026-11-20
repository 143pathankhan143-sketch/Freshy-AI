import type { SearchResult } from "./schemas";
import type { FetchLike } from "./openAiCompatibleProvider";

function clean(value: unknown, limit: number): string {
  return String(value ?? "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, limit);
}

export class TavilySearch {
  lastError: string | null = null;

  constructor(
    private readonly apiKey: string,
    private readonly timeoutMs: number,
    private readonly maxResults: number,
    private readonly searchDepth: "basic" | "advanced",
    private readonly fetchFn: FetchLike = fetch,
  ) {}

  isConfigured(): boolean {
    const key = this.apiKey.trim().toLowerCase();
    return Boolean(
      key && !["my_tavily_api_key", "my_tavily_api_key_here"].includes(key),
    );
  }

  async search(query: string): Promise<SearchResult[]> {
    this.lastError = null;
    const cleanQuery = clean(query, 500);
    if (!cleanQuery) {
      this.lastError = "empty_query";
      return [];
    }
    if (!this.isConfigured()) {
      this.lastError = "missing_key";
      return [];
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetchFn("https://api.tavily.com/search", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: cleanQuery,
          search_depth: this.searchDepth,
          max_results: this.maxResults,
          include_answer: false,
          include_images: false,
          include_raw_content: false,
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        this.lastError =
          response.status === 401 || response.status === 403
            ? "authentication_error"
            : "search_unavailable";
        return [];
      }
      const data = (await response.json()) as Record<string, unknown>;
      const raw = Array.isArray(data.results) ? data.results : [];
      const results: SearchResult[] = [];
      const seen = new Set<string>();
      for (const item of raw.slice(0, this.maxResults)) {
        if (!item || typeof item !== "object") continue;
        const record = item as Record<string, unknown>;
        const url = clean(record.url, 1000);
        try {
          const parsed = new URL(url);
          if (!["http:", "https:"].includes(parsed.protocol)) continue;
        } catch {
          continue;
        }
        if (seen.has(url)) continue;
        seen.add(url);
        const score = Number(record.score);
        results.push({
          title: clean(record.title || "Untitled source", 300),
          url,
          content: clean(record.content, 1500),
          ...(Number.isFinite(score) ? { score } : {}),
        });
      }
      return results;
    } catch (error) {
      this.lastError =
        error instanceof Error && error.name === "AbortError"
          ? "timeout"
          : "network_error";
      return [];
    } finally {
      clearTimeout(timer);
    }
  }
}
