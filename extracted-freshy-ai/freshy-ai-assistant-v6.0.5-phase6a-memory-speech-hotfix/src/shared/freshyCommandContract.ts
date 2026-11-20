export type FreshyIntentName =
  | "GREETING"
  | "TIME_DATE"
  | "OPEN_APP"
  | "OPEN_WEBSITE"
  | "UNKNOWN";

export interface FreshyIntent {
  name: FreshyIntentName;
  confidence: number;
  parameters: Record<string, unknown>;
  explanation: string;
}

export interface PreviewExecution {
  success: boolean;
  action_executed: false;
  reply: string;
  details: Record<string, unknown>;
}

const WAKE_PREFIX =
  /^(?:hello|hallo|helo)\s+(?:freshy|fresh|freshly|freshee|frashi|freddy|crashy|crazy)\b[\s,.-]*/i;
const ALLOWED_HOSTS = ["google.com", "youtube.com", "github.com", "wikipedia.org"];

export function normalizeCommandText(text: string): string {
  return String(text ?? "")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function removeFreshyWakePrefix(text: string): {
  matched: boolean;
  command: string;
} {
  const raw = String(text ?? "").trim();
  if (!WAKE_PREFIX.test(raw)) {
    return { matched: false, command: raw };
  }
  return {
    matched: true,
    command: raw.replace(WAKE_PREFIX, "").trim(),
  };
}

function isAllowedWebsite(value: string): boolean {
  try {
    const parsed = new URL(value.includes("://") ? value : `https://${value}`);
    if (!["http:", "https:"].includes(parsed.protocol)) return false;
    const host = parsed.hostname.toLocaleLowerCase().replace(/\.$/, "");
    return ALLOWED_HOSTS.some(
      (domain) => host === domain || host.endsWith(`.${domain}`),
    );
  } catch {
    return false;
  }
}

export function parseRuleBasedIntent(text: string): FreshyIntent {
  const wake = removeFreshyWakePrefix(text);
  const rawCommand = (wake.command || String(text ?? "")).trim();
  const lowerRaw = rawCommand.toLocaleLowerCase();
  const clean = normalizeCommandText(rawCommand);

  if (wake.matched && !wake.command) {
    return {
      name: "GREETING",
      confidence: 0.98,
      parameters: { raw_text: text },
      explanation: "Freshy wake phrase detected.",
    };
  }

  // Preserve :// and URL paths before normalizing punctuation.
  const rawUrlMatch = lowerRaw.match(
    /^(?:please\s+)?(?:open|go\s+to|launch|visit|kholo)\s+(https?:\/\/\S+)(?:\s+in\s+my\s+browser)?$/i,
  );
  if (rawUrlMatch) {
    return {
      name: "OPEN_WEBSITE",
      confidence: 0.98,
      parameters: { url: rawUrlMatch[1], target: rawUrlMatch[1] },
      explanation: "Explicit URL detected for local allowlist validation.",
    };
  }

  if (
    /^(?:(?:hello|hi|hey|greetings|good morning|good evening)(?: freshy)?(?: how are you)?|namaste(?: kaise ho)?|freshy|who are you|kaise ho|kya haal(?: hai)?)$/i.test(
      clean,
    )
  ) {
    return {
      name: "GREETING",
      confidence: 0.95,
      parameters: { raw_text: text },
      explanation: "Rule-based greeting keyword match.",
    };
  }

  // Do not match broad words like "today". "AI news today" must reach search.
  if (
    /^(?:what(?: is|s)? the current time(?: right now| now)?|what time is it(?: right now| now)?|current time|time|clock|kya time(?: hai)?|time kya(?: hai)?|kitne baje(?: hain)?|what(?: is|s)? (?:today s |the )?date|what date is it|current date|date|what day is it|aaj kya date(?: hai)?)$/i.test(
      clean,
    )
  ) {
    return {
      name: "TIME_DATE",
      confidence: 0.95,
      parameters: {},
      explanation: "Rule-based time/date keyword match.",
    };
  }

  if (
    /^(?:(?:please )?(?:open|launch|start) notepad(?: app)?(?: for me)?|notepad(?: kholo| open| chalu)?)$/i.test(
      clean,
    )
  ) {
    return {
      name: "OPEN_APP",
      confidence: 0.98,
      parameters: { app_name: "notepad" },
      explanation: "Rule-based open Notepad match.",
    };
  }

  if (
    /^(?:(?:please )?(?:open|launch|start) (?:calculator|calc)(?: app)?(?: for me)?|(?:calculator|calc)(?: kholo| open)?)$/i.test(
      clean,
    )
  ) {
    return {
      name: "OPEN_APP",
      confidence: 0.98,
      parameters: { app_name: "calculator" },
      explanation: "Rule-based open Calculator match.",
    };
  }

  const unsafeApp = clean.match(
    /^(?:please )?(?:open|launch|start|kholo) (command prompt|cmd|powershell|terminal|registry editor|regedit)(?: app)?$/i,
  );
  if (unsafeApp) {
    return {
      name: "OPEN_APP",
      confidence: 0.99,
      parameters: { app_name: unsafeApp[1].toLocaleLowerCase() },
      explanation: "App request detected for local allowlist validation.",
    };
  }

  const prefixWebMatch = clean.match(
    /^(?:please )?(?:open|go to|launch|visit|kholo)\s+(google|youtube|github|wikipedia|website|browser)(?: in my browser)?$/i,
  );
  const suffixWebMatch = clean.match(
    /^(google|youtube|github|wikipedia|website|browser)\s+(?:kholo|open|launch|visit)$/i,
  );
  const target = prefixWebMatch?.[1] ?? suffixWebMatch?.[1];
  if (target) {
    const knownUrls: Record<string, string> = {
      google: "https://www.google.com",
      youtube: "https://www.youtube.com",
      github: "https://www.github.com",
      wikipedia: "https://www.wikipedia.org",
      website: "https://www.google.com",
      browser: "https://www.google.com",
    };
    const normalizedTarget = target.toLocaleLowerCase();
    return {
      name: "OPEN_WEBSITE",
      confidence: 0.95,
      parameters: { url: knownUrls[normalizedTarget], target: normalizedTarget },
      explanation: "Rule-based open website match.",
    };
  }

  const genericSite = clean.match(
    /^(?:please )?(?:open|visit|go to|kholo) ([a-z0-9_-]+)(?: site| website)$/i,
  );
  if (genericSite) {
    const site = genericSite[1].toLocaleLowerCase();
    return {
      name: "OPEN_WEBSITE",
      confidence: 0.9,
      parameters: { url: `https://${site}.com`, target: site },
      explanation: "Website request detected for local allowlist validation.",
    };
  }

  return {
    name: "UNKNOWN",
    confidence: 0.5,
    parameters: { query: text },
    explanation: "No rule match. Safe fallback active.",
  };
}

export function executePreviewIntent(
  intentName: FreshyIntentName,
  parameters: Record<string, unknown>,
  now = new Date(),
): PreviewExecution {
  if (intentName === "GREETING") {
    return {
      success: true,
      action_executed: false,
      reply:
        "Hello! I am Freshy. The Freshy desktop web preview is active. Native Windows actions run only through the Flutter and Python desktop application.",
      details: { action: "GREETING", test_mode: "desktop_web_preview" },
    };
  }

  if (intentName === "TIME_DATE") {
    const time = now.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
    });
    const date = now.toLocaleDateString("en-IN", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    return {
      success: true,
      action_executed: false,
      reply: `The current local time is ${time} on ${date}.`,
      details: { time, date, action: "TIME_DATE", test_mode: "desktop_web_preview" },
    };
  }

  if (intentName === "OPEN_APP") {
    const appName = String(parameters.app_name ?? "").toLocaleLowerCase();
    if (appName === "notepad" || appName === "calculator") {
      return {
        success: true,
        action_executed: false,
        reply: `${appName === "notepad" ? "Notepad" : "Calculator"} command recognized. The Windows action is intentionally not executed in desktop web preview.`,
        details: {
          app: appName,
          status: "recognized_not_executed",
          test_mode: "desktop_web_preview",
        },
      };
    }
    return {
      success: false,
      action_executed: false,
      reply: `Security block: '${appName}' is not in Freshy's web preview allowlist.`,
      details: { allowed: ["notepad", "calculator"], test_mode: "desktop_web_preview" },
    };
  }

  if (intentName === "OPEN_WEBSITE") {
    const url = String(parameters.url ?? "https://www.google.com");
    if (!isAllowedWebsite(url)) {
      return {
        success: false,
        action_executed: false,
        reply: "Security block: website domain is not allowlisted.",
        details: { url, allowed_domains: ALLOWED_HOSTS, test_mode: "desktop_web_preview" },
      };
    }
    return {
      success: true,
      action_executed: false,
      reply: `Website command recognized for ${url}. Opening it is intentionally skipped in desktop web preview.`,
      details: {
        url,
        status: "recognized_not_executed",
        test_mode: "desktop_web_preview",
      },
    };
  }

  return {
    success: false,
    action_executed: false,
    reply: `Freshy heard: '${String(parameters.query ?? "")}'. Try Hello Freshy, time, Notepad, Calculator, Google, YouTube, or GitHub.`,
    details: { action: "UNKNOWN_FALLBACK", test_mode: "desktop_web_preview" },
  };
}
