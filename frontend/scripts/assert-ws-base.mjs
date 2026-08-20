import assert from "node:assert/strict";
import { resolveWsBase } from "../src/utils/resolveWsBase.js";

const baked = "wss://baked-backend.example.com";
const fromQuery = "wss://query-backend.example.com/ws/realtime/abc";

const resolved = resolveWsBase({
  wssQuery: fromQuery,
  viteWsBase: baked,
  apiQuery: "https://api-param.example.com",
});

assert.equal(
  resolved,
  "wss://query-backend.example.com",
  "?wss= must win over baked VITE_WS_BASE"
);

const withoutWss = resolveWsBase({
  wssQuery: "",
  viteWsBase: baked,
  apiQuery: "https://api-param.example.com",
});
assert.equal(withoutWss, baked, "VITE_WS_BASE used when ?wss= missing");

console.log("wsBase priority assertions passed");
