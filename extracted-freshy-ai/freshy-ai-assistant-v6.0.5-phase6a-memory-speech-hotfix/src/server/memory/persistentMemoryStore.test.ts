import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { PersistentMemoryStore } from "./persistentMemoryStore";

function createStore() {
  const directory = mkdtempSync(join(tmpdir(), "freshy-memory-"));
  const filePath = join(directory, "memory.json");
  const store = new PersistentMemoryStore(filePath, {
    enabled: true,
    mode: "ask_before_saving",
    persistConversations: true,
    autoProfileDetection: true,
    maxItems: 10,
    maxItemCharacters: 2000,
    recallLimit: 6,
    recallCharacters: 2500,
  });
  return { directory, filePath, store };
}

test("memory persists, rejects secrets, and recalls relevant facts", () => {
  const { directory, filePath, store } = createStore();
  try {
    const created = store.create({
      category: "project",
      key: "active_project",
      value: "Freshy AI Assistant",
      tags: ["freshy"],
      importance: 5,
    });
    assert.equal(created.created, true);
    assert.throws(
      () => store.create({ key: "api_key", value: "sk-abcdefghijklmnop" }),
      /cannot be stored/i,
    );
    const reopened = new PersistentMemoryStore(filePath, store.settings);
    assert.equal(reopened.list().length, 1);
    assert.match(reopened.recallContext("Explain my Freshy project").context, /Freshy AI Assistant/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("persistent chat omits secrets and backup import is duplicate safe", () => {
  const { directory, filePath, store } = createStore();
  try {
    store.addConversation("s", "user", "Normal project question");
    store.addConversation("s", "user", "My API key is sk-abcdefghijklmnop");
    assert.equal(store.loadConversation("s").length, 1);

    store.create({ category: "profile", key: "name", value: "Pathan" });
    const backup = store.exportData() as { items: unknown[] };
    const imported = store.importData(backup.items);
    assert.equal(imported.imported, 0);
    assert.equal(imported.skipped, 1);

    const persisted = JSON.parse(readFileSync(filePath, "utf8")) as unknown;
    assert.doesNotMatch(JSON.stringify(persisted), /sk-abcdefghijklmnop/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
