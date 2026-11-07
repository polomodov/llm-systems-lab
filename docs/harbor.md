# Harbor track

This page maps the Harbor work under `experiments/common/`. The track runs agents through [Harbor](https://github.com/harbor-framework/harbor), pinned to version 0.25.0 at commit `ff2a1ef48070a8df374669138e4d4db79b77f013` in [`harbor-interop/lock.json`](../experiments/common/harbor-interop/lock.json). It is separate from the lab coordinator's campaigns.

No model request has been made on this track. All evidence so far is offline: fixtures, synthetic tasks and a loopback mock provider. Current record counts are in [status.md](status.md).

## Directories

| Directory | Purpose | State |
| --- | --- | --- |
| [`harbor-interop`](../experiments/common/harbor-interop/README.md) | Exports one historical Pi run for inspection and exercises a synthetic task with a separate verifier | Finished experiment; also holds the Harbor version lock |
| [`harbor-native-pilot`](../experiments/common/harbor-native-pilot/README.md) | First six-slot native adapter pilot | Historical: kept byte for byte, superseded by the next row. Its six prepared records stay as they are |
| [`harbor-native-2026-11`](../experiments/common/harbor-native-2026-11/README.md) | The same task with `claude-sonnet-5-5` and `gpt-6.1-sol` | **Current pilot.** Six prepared records, USD 12 target, spending not authorized |
| [`model-refresh-2026-11`](../experiments/common/model-refresh-2026-11/README.md) | Migration report and offline qualification for those models | Reference |
| [`pilot-execution`](../experiments/common/pilot-execution/README.md) | Runs exactly one authorized Trial, and hands finished work to an independent evaluator | Current tooling |
| [`campaigns/2026-11-first-comparison`](../experiments/common/campaigns/2026-11-first-comparison/README.md) | Draft plan for the comparison campaigns: 6 pilots and 36 comparison runs, 18 each for Anthropic and OpenAI | Preparation only, not frozen |

The two `harbor-native-*` directories share 18 identical files. This is deliberate: sealed records must keep their exact inputs. Do not merge them.

## What blocks the first paid run

From [`hn-o01-review-evidence.json`](../experiments/common/pilot-execution/hn-o01-review-evidence.json), `remaining_live_gates`, for the first slot, HN-O01 (see [`HN-O01.md`](../experiments/common/pilot-execution/HN-O01.md)):

1. An independent nested-call inventory or a verified complete stream, before full permission qualification. Until then the counter stays unknown.
2. A separate spending permit for the exact run, with an approved project and API key ID, an expiry and all current instrumentation hashes.
3. A project and key used only by this run for the entire UTC cost bucket, a billing reviewer, full exports, two stable snapshots and justified finality.
4. Live model and API acceptance, and response identity on the native transport. Unknowns stay unknown.

There is no automatic retry, second native slot or campaign promotion. T002 and T004 runs also need an independent evaluator; see [`EVALUATION.md`](../experiments/common/pilot-execution/EVALUATION.md).

## Hash-protected files

Changing these invalidates recorded evidence. Do not edit them to make a fix convenient.

- [`preservation.json`](../experiments/common/pilot-execution/preservation.json) covers `harbor-interop`, both `harbor-native-*` directories, `model-refresh-2026-11` and `results/runs`.
- `hn-o01-review-evidence.json`, the newest checkpoint `check_offline.py` selects, covers the `pilot-execution` sources, **`package.json`** and **`docs/harness-ledger.md`**. Changing either of the last two makes `check_offline.py` report `Evidence changed` until the evidence is recorded again, which needs Docker and the local logs under `pilot-execution/.cache/`. Earlier checkpoints in that directory no longer match the sources; this is expected.
- An execution authorization binds `single_trial.py`, `common.py` and `accounting.py`.

## Tests

Python suites in these directories import Harbor, so they run in their own CI job and not in `npm test`:

```bash
mise exec -- node scripts/test-harbor.mjs --setup
```

```bash
mise exec -- node scripts/test-harbor.mjs
```

`--setup` installs the locked versions into the ignored `.cache/harbor-test/`, without any model request or task run.

## Known issue

`harbor-interop/bootstrap.py` fails on macOS with the mise Python: `venv.create` copies the interpreter, and the copy cannot find `libpython`. Observed on Python 3.12.12 on 2026-11-07; Linux is unverified. The file is hash-protected, so it is not fixed in place. `scripts/test-harbor.mjs --setup` does not depend on it, but it also skips the viewer build that `harbor-interop/view.py` needs for browsing.
