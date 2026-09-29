#!/usr/bin/env node
/** Boundary tests for quiet-hours hour logic (matches app.js + quiet_hours.py). */
function inQuietHoursCentralHour(hour) {
  return hour >= 23 || hour < 7;
}

const cases = [
  [22, false],
  [23, true],
  [0, true],
  [6, true],
  [7, false],
  [12, false],
];
let failed = 0;
for (const [hour, expect] of cases) {
  const got = inQuietHoursCentralHour(hour);
  if (got !== expect) {
    console.error(`hour ${hour}: expected ${expect}, got ${got}`);
    failed += 1;
  }
}
function staleServerWouldBlockReadAloud(lastActive, fetchedMsAgo, localQuiet) {
  const fresh = fetchedMsAgo < 120000;
  if (fresh && lastActive === true) return true;
  return localQuiet;
}
if (!staleServerWouldBlockReadAloud(false, 0, true)) {
  console.error("stale poll: local quiet must block read-aloud");
  failed += 1;
}
if (staleServerWouldBlockReadAloud(false, 300000, false)) {
  console.error("stale poll: local not quiet must allow read-aloud");
  failed += 1;
}
if (failed) process.exit(1);
console.log("quiet_hours_js: OK");
