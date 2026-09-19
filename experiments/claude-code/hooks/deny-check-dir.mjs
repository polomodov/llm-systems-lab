#!/usr/bin/env node
// Стена L001: блокирует любой доступ к tasks/*/check/ независимо от инструмента.
// Читает JSON события хука из stdin; exit 2 = заблокировать с сообщением в stderr.
let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let ev = {};
  try { ev = JSON.parse(raw); } catch {}
  const input = JSON.stringify(ev.tool_input ?? {});
  if (/tasks\/[^\s"']*\/check\//.test(input) || /\/check\//.test(input) && /tasks/.test(input)) {
    console.error("[L001] Access to tasks/*/check/ is denied by the harness. The hidden check is not part of the task.");
    process.exit(2);
  }
  process.exit(0);
});
