import {
  executePreviewIntent,
  type FreshyIntentName,
} from "../../shared/freshyCommandContract";
import type { ProviderTool, ToolResult } from "./schemas";
import { TavilySearch } from "./tavilySearch";

const ALLOWED_HOSTS = [
  "google.com",
  "youtube.com",
  "github.com",
  "wikipedia.org",
];

function objectArgs(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function allowedUrl(value: string): boolean {
  try {
    const parsed = new URL(value.includes("://") ? value : `https://${value}`);
    if (!["http:", "https:"].includes(parsed.protocol)) return false;
    const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
    return ALLOWED_HOSTS.some(
      (domain) => host === domain || host.endsWith(`.${domain}`),
    );
  } catch {
    return false;
  }
}

export class SafeToolRegistry {
  constructor(private readonly search: TavilySearch) {}

  providerTools(includeWebSearch: boolean): ProviderTool[] {
    const tools: ProviderTool[] = [
      {
        type: "function",
        function: {
          name: "get_time_date",
          description: "Get the current local date and time.",
          parameters: {
            type: "object",
            properties: {},
            additionalProperties: false,
          },
        },
      },
      {
        type: "function",
        function: {
          name: "open_application",
          description:
            "Recognize an allowlisted Windows application request in the desktop web preview. Allowed: notepad, calculator. The browser preview never executes the native Windows action.",
          parameters: {
            type: "object",
            properties: {
              app_name: { type: "string", enum: ["notepad", "calculator"] },
            },
            required: ["app_name"],
            additionalProperties: false,
          },
        },
      },
      {
        type: "function",
        function: {
          name: "open_website",
          description:
            "Recognize an allowlisted website request in the desktop web preview. Allowed domains: Google, YouTube, GitHub and Wikipedia. The browser preview does not claim a Windows action executed.",
          parameters: {
            type: "object",
            properties: { url: { type: "string", maxLength: 2000 } },
            required: ["url"],
            additionalProperties: false,
          },
        },
      },
    ];
    if (includeWebSearch) {
      tools.push({
        type: "function",
        function: {
          name: "web_search",
          description: "Search the public web for current information.",
          parameters: {
            type: "object",
            properties: { query: { type: "string", maxLength: 500 } },
            required: ["query"],
            additionalProperties: false,
          },
        },
      });
    }
    return tools;
  }

  async execute(name: string, rawArguments: unknown): Promise<ToolResult> {
    const args = objectArgs(rawArguments);
    if (!args) {
      return {
        success: false,
        output: "",
        error: "Security block: tool arguments must be a JSON object.",
      };
    }

    if (name === "get_time_date") {
      if (Object.keys(args).length > 0) {
        return {
          success: false,
          output: "",
          error: "Security block: get_time_date does not accept arguments.",
        };
      }
      const result = executePreviewIntent("TIME_DATE", {});
      return { success: result.success, output: result.reply };
    }

    if (name === "open_application") {
      if (
        Object.keys(args).some((key) => key !== "app_name") ||
        !["notepad", "calculator"].includes(String(args.app_name ?? ""))
      ) {
        return {
          success: false,
          output: "",
          error: "Security block: application is not allowlisted.",
        };
      }
      const result = executePreviewIntent("OPEN_APP", {
        app_name: args.app_name,
      });
      return { success: result.success, output: result.reply };
    }

    if (name === "open_website") {
      if (
        Object.keys(args).some((key) => key !== "url") ||
        typeof args.url !== "string" ||
        args.url.length > 2000 ||
        !allowedUrl(args.url)
      ) {
        return {
          success: false,
          output: "",
          error: "Security block: website domain is not allowlisted.",
        };
      }
      const normalized = args.url.includes("://")
        ? args.url
        : `https://${args.url}`;
      const result = executePreviewIntent("OPEN_WEBSITE", { url: normalized });
      return { success: result.success, output: result.reply };
    }

    if (name === "web_search") {
      if (
        Object.keys(args).some((key) => key !== "query") ||
        typeof args.query !== "string" ||
        !args.query.trim() ||
        args.query.length > 500
      ) {
        return {
          success: false,
          output: "",
          error: "Security block: invalid web search query.",
        };
      }
      const sources = await this.search.search(args.query);
      if (sources.length === 0) {
        return {
          success: false,
          output: "",
          error: `Web search could not return results (${this.search.lastError ?? "no_results"}).`,
          sources: [],
        };
      }
      return {
        success: true,
        output: sources
          .map(
            (source, index) =>
              `Source ${index + 1}:\nTitle: ${source.title}\nURL: ${source.url}\nSnippet: ${source.content}`,
          )
          .join("\n\n"),
        sources,
      };
    }

    return {
      success: false,
      output: "",
      error: `Security block: tool '${name}' is not registered or permitted.`,
    };
  }
}
