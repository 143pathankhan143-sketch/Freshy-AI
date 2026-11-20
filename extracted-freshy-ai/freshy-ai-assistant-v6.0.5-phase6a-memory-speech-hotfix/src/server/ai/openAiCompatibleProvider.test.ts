import assert from "node:assert/strict";
import test from "node:test";
import { OpenAiCompatibleProvider } from "./openAiCompatibleProvider";

test("provider-agnostic tool history is sent as user context", async () => {
  const requestBodies: Array<Record<string, unknown>> = [];
  const fakeFetch = async (_url: unknown, init?: RequestInit) => {
    requestBodies.push(JSON.parse(String(init?.body ?? "{}")));
    return {
      ok: true,
      json: async () => ({ choices: [{ message: { content: "ok" } }] }),
      text: async () => "",
    } as Response;
  };
  const provider = new OpenAiCompatibleProvider(
    "groq",
    "https://api.example.com/v1",
    "configured-key",
    "model",
    1000,
    100,
    0.3,
    fakeFetch as typeof fetch,
  );
  const result = await provider.generate([
    { role: "user", content: "Do the safe action" },
    { role: "tool", content: "[TOOL_RESULT] success=true", name: "open_application" },
  ]);
  assert.equal(result.success, true);
  const messages = (requestBodies[0]?.messages ?? []) as Array<Record<string, unknown>>;
  assert.equal(messages.at(-1)?.role, "user");
  assert.match(String(messages.at(-1)?.content), /TOOL_RESULT/);
  assert.equal("name" in (messages.at(-1) ?? {}), false);
});
