// Скрытые тесты T004: полная спецификация из brief.md. Копируется в test/ клона при проверке.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseDuration, formatDuration } from "../src/duration.js";

const rejects = (input) => assert.throws(() => parseDuration(input), TypeError);
const rejectsFormat = (input) => assert.throws(() => formatDuration(input), TypeError);

test("units are case-insensitive", () => assert.equal(parseDuration("1H 30M"), 5400000));
test("surrounding whitespace is tolerated", () => assert.equal(parseDuration(" 90m "), 5400000));
test("tabs between components are tolerated", () => assert.equal(parseDuration("1h\t30m"), 5400000));
test("all five units in one string", () => assert.equal(parseDuration("1d 2h 3m 4s 5ms"), 93784005));
test("components may come in any order", () => assert.equal(parseDuration("30m 1h"), 5400000));
test("milliseconds unit", () => assert.equal(parseDuration("1500ms"), 1500));
test("leading zeros are plain decimal", () => assert.equal(parseDuration("007s"), 7000));
test("repeated unit is rejected", () => rejects("1h1h"));
test("negative number is rejected", () => rejects("-5s"));
test("fraction is rejected", () => rejects("1.5h"));
test("empty and blank strings are rejected", () => { rejects(""); rejects("   "); });
test("garbage, bare number and unknown unit are rejected", () => { rejects("abc"); rejects("90"); rejects("3w"); rejects("1 h"); });
test("non-string input is rejected", () => { rejects(90); rejects(null); rejects(undefined); rejects({}); });
test("format drops zero components and shows ms only when needed", () => {
  assert.equal(formatDuration(86400000), "1d");
  assert.equal(formatDuration(1500), "1s 500ms");
  assert.equal(formatDuration(93784005), "1d 2h 3m 4s 5ms");
  assert.equal(formatDuration(3600000), "1h");
});
test("format of zero is 0ms", () => assert.equal(formatDuration(0), "0ms"));
test("format rejects negative, fractional and non-number input", () => {
  rejectsFormat(-1); rejectsFormat(1.5); rejectsFormat("1"); rejectsFormat(NaN); rejectsFormat(Infinity);
});
test("round trip holds for a range of values", () => {
  for (const value of [0, 1, 999, 1000, 59999, 60000, 3599999, 3600000, 86399999, 86400000, 90061001, 123456789012]) {
    assert.equal(parseDuration(formatDuration(value)), value);
  }
});
