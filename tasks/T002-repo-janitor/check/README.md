# Hidden check T002 (do not expose to the agent)

The operator runs `check.sh <run-dir>` for a prepared run with Node.js 22+, npm and Git. It clones `janitor/<run-id>` into a temporary directory and:

1. Compares the original test file SHA-256 with the coordinator input snapshot. Additional tests are allowed.
2. Runs original tests by filename and separately runs `npm test` in a clean clone. The initial `npm test` passes `test/*.test.js` files to Node. The standard library is sufficient for validation. The script checks the lodash version in `package.json`.
3. Checks `slugify` behavior, absence of `console.log` in sources, the lodash version, and coverage of all three defects in the report.

The script prints Node/npm versions, the failure stage and full test output. Preserve diagnostics with `bash tasks/T002-repo-janitor/check/check.sh "$run_dir" > "$run_dir/trace/t002-check.log" 2>&1` and use the log when filling `check_output`.

Exit `0` means pass; `1` means a contract violation or failed check; `2` means check-setup failure. If the test runner could not start, inspect the log before assigning a verdict. New attempts require a fresh input snapshot with the corrected test invocation.
