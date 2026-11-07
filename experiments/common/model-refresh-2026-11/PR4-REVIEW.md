# PR4 review corrections

The review of preparation commit `9b8d3be344f75168a40b520fae3930235541089c` found a stale Claude build argument, historical evidence attributed to upgraded versions, blocking Node subprocess calls in an async fixture runner, and Sonar security/duplication findings.

## Corrections and repeated verification

- The root build example now supplies Claude 2.1.319 consistently with its tag and Dockerfile. The pin audit checks explicit documented build arguments as well as tags; a regression rejects a stale argument with a current tag.
- September evidence again names Claude 2.1.83 and Codex 0.155.1. November qualification and Claude's required native install are documented separately. Historical image IDs and original smoke files were not changed.
- The local fixture instrumentation now uses `asyncio.create_subprocess_exec`, bounded communication, and child reaping on failure/cancellation. Smaller helpers separate setup, commands, artifacts, trace parsing and cleanup. Two regressions exercise event-loop responsiveness, stdin parsing, nonzero exit and timeout. They run in the ordinary offline Python CI task.
- All six actual lab entrypoint fixtures were repeated successfully under Docker network none with fake keys and no mounts. The previous raw fixture logs remain in their original local cache directories; original source/summary bytes remain in the preparation commit. The unchanged six native/four verifier evidence is revalidated, not represented as new execution.

[review-checks.json](review-checks.json) records current offline validation. [offline-checks.json](offline-checks.json) is the original preparation checkpoint at `9b8d3be`; source paths/hashes in that checkpoint describe that commit, not the later refactored runner. Neither report establishes live account access, actual model identity or billing.

## Sonar review decisions

The two S6505 findings are **accepted**, not labeled false positive. Claude 2.1.319 requires native-binary postinstall: preparation with `--ignore-scripts` failed its version gate. Installation is confined to credential-free public-package image preparation; NPM artifact integrity, immutable final images and inventories are retained. GitHub builds and network-disabled version probes passed. This is an explicit supply-chain exception, not a rule suppression or an unrecorded runtime change.

The two S5443 findings are false positives for shared-host temporary files. The paths are inside a fresh UUID-named Docker container, with no host mounts, network none, fake credentials and checked cleanup. The mock provider is uploaded before the native agent starts. `/tmp/harbor-pi-agent` is read after the fixture to retain generated non-secret configuration; it is not a predictable host temp file. No host HOME or auth configuration is reused.

Duplication was entirely against the retained previous experiment. `.sonarcloud.properties` removes exactly nine named predecessor source/test files from **duplication comparison only**, plus the already excluded historical evaluator and sealed inputs. All refreshed files remain in duplication analysis. Both revisions remain in security/reliability analysis. There is no broad directory exclusion, issue suppression or lowered gate threshold. The 1470-file preservation manifest still validates the old bytes; frozen packages and prepared records are not rewritten to refactor history.

The predecessor paths are: `accounting.py`, `check_preparation.py`, `materialize.py`, `mock-provider.mjs`, `mock-provider.test.mjs`, `offline_smoke.py`, `test_accounting.py`, `test_offline_smoke.py`, and `verify_controls.py`, all under `experiments/common/harbor-native-pilot/`.

## Preservation and spending

No file under `results/runs/`, `harbor-native-pilot/` or `harbor-interop/` changed during this review follow-up. All 42 campaign slots remain unstarted; all 12 old/new native preparation records remain unexecuted. The separate USD 12 + USD 12 pilot targets and all execution/activation prohibitions are unchanged. No provider calls, real credential reads or paid runs occurred.
