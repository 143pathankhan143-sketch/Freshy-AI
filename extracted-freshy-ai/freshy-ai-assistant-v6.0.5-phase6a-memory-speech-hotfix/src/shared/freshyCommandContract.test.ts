import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  executePreviewIntent,
  parseRuleBasedIntent,
  removeFreshyWakePrefix,
} from "./freshyCommandContract";

test("shared preview command contract matches English and Hinglish commands", () => {
  const cases = [
    ["Hello Freshy", "GREETING"],
    ["Hello crazy open calculator", "OPEN_APP"],
    ["Notepad kholo", "OPEN_APP"],
    ["Calculator kholo", "OPEN_APP"],
    ["What time is it?", "TIME_DATE"],
    ["Time kya hai", "TIME_DATE"],
    ["Google kholo", "OPEN_WEBSITE"],
    ["Open YouTube", "OPEN_WEBSITE"],
  ] as const;

  for (const [phrase, expected] of cases) {
    assert.equal(
      parseRuleBasedIntent(phrase).name,
      expected,
      `Unexpected intent for ${phrase}`,
    );
  }
});

test("Desktop web preview parser passes every shared command-contract case", () => {
  const contract = JSON.parse(
    readFileSync("voice_test_contract.json", "utf8"),
  ) as {
    cases: Array<{ phrase: string; expected_intent: string }>;
  };

  assert.ok(contract.cases.length > 0);
  for (const item of contract.cases) {
    assert.equal(
      parseRuleBasedIntent(item.phrase).name,
      item.expected_intent,
      `Contract mismatch for ${item.phrase}`,
    );
  }
});

test("wake phrase and inline command are separated without losing the command", () => {
  assert.deepEqual(removeFreshyWakePrefix("Hello Freshy"), {
    matched: true,
    command: "",
  });
  assert.deepEqual(
    removeFreshyWakePrefix("hello freshly open calculator"),
    {
      matched: true,
      command: "open calculator",
    },
  );
  assert.equal(removeFreshyWakePrefix("Hey Freshy").matched, false);
});

test("desktop web preview never reports native Windows execution", () => {
  const appExecution = executePreviewIntent("OPEN_APP", {
    app_name: "notepad",
  });
  const webExecution = executePreviewIntent("OPEN_WEBSITE", {
    url: "https://www.google.com",
  });

  assert.equal(appExecution.success, true);
  assert.equal(appExecution.action_executed, false);
  assert.equal(appExecution.details.status, "recognized_not_executed");
  assert.equal(webExecution.success, true);
  assert.equal(webExecution.action_executed, false);
});


test("general questions containing today or app names are not local actions", () => {
  assert.equal(parseRuleBasedIntent("What happened in AI news today?").name, "UNKNOWN");
  assert.equal(parseRuleBasedIntent("Explain how Notepad stores text").name, "UNKNOWN");
});

test("explicit URLs are preserved and unsafe domains are blocked in preview", () => {
  const allowed = parseRuleBasedIntent("Open https://www.github.com/openai/example?tab=readme");
  assert.equal(allowed.name, "OPEN_WEBSITE");
  assert.equal(allowed.parameters.url, "https://www.github.com/openai/example?tab=readme");
  assert.equal(executePreviewIntent(allowed.name, allowed.parameters).success, true);

  const unsafe = parseRuleBasedIntent("Open https://google.com.evil.example/path");
  assert.equal(unsafe.name, "OPEN_WEBSITE");
  const blocked = executePreviewIntent(unsafe.name, unsafe.parameters);
  assert.equal(blocked.success, false);
  assert.equal(blocked.action_executed, false);
  assert.match(blocked.reply, /security block/i);
});
