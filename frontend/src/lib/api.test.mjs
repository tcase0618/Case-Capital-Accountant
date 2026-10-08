import assert from "node:assert/strict";
import test from "node:test";
import { api, setApiToken } from "./api.js";

test("operator token is optional, sent for protected calls, and cleared", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ status: "ok" }) };
  };
  try {
    setApiToken("");
    await api.runReportMachineOnce();
    assert.equal(calls.at(-1).options.headers.Authorization, undefined);
    setApiToken(" runtime-test-token ");
    await api.runReportMachineOnce();
    assert.equal(calls.at(-1).options.method, "POST");
    assert.equal(calls.at(-1).options.headers.Authorization, "Bearer runtime-test-token");
    setApiToken("");
    await api.marketQuote("TEST");
    assert.equal(calls.at(-1).options.headers.Authorization, undefined);
  } finally {
    setApiToken("");
    globalThis.fetch = originalFetch;
  }
});
