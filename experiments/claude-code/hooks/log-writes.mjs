#!/usr/bin/env node
// Наблюдаемость: журнал всех записей файлов в trace/writes.log рядом с рабочим каталогом.
import { appendFileSync, mkdirSync } from "node:fs";
let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let ev = {};
  try { ev = JSON.parse(raw); } catch {}
  const path = ev.tool_input?.file_path ?? ev.tool_input?.path ?? "?";
  try { mkdirSync("../trace", { recursive: true }); appendFileSync("../trace/writes.log", `${new Date().toISOString()} ${ev.tool_name ?? "?"} ${path}\n`); } catch {}
  process.exit(0);
});
