# Sonnet 5.5 and Sol 6.1 preparation

Future campaign slots now select `claude-sonnet-5-5` and `gpt-6.1-sol` with explicit medium reasoning effort. Six lab entrypoint fixtures, six native Harbor adapter fixtures and four independent-verifier controls pass without provider requests. Account access, live request acceptance, provider response identity and attributable billing remain **unverified**. No execution is authorized.

## Compatibility and frozen runtime

| Harness | Selected version | Necessary change | Offline evidence |
| --- | --- | --- | --- |
| Claude Code | 2.1.319, upgraded from 2.1.83 | Native binary install; explicit medium effort | Messages tool loop, adaptive thinking and signed replay |
| Codex | 0.167.0, upgraded from 0.155.1 | Explicit medium effort | Responses custom `functions.exec` tool loop and terminal event |
| Pi | 0.73.1 retained | Explicit metadata for both exact IDs; hash-guarded adaptive detection and retention of empty signed thinking | Actual SDK session and native CLI both pass |
| OpenCode | 1.18.29 retained | Explicit Sonnet metadata and medium variant | Messages tool loop and signed replay |
| mini-SWE-agent | 2.4.6 retained; LiteLLM 1.108.1 | Native `LitellmResponseModel` for Sol; Responses usage normalization; genuine MCP dependency closure | Actual lab Python entrypoint and native CLI submission |

OpenCode 1.19.5 was rejected: two fresh-container native checks completed output but emitted EPIPE and exited 1. Reward alone did not qualify it. Pi's two source edits fail closed if the upstream provider file hash or replacement anchors change. This is an owned compatibility delta, not a new upstream Pi version. Historical/default model behavior remains separately represented.

Use the immutable Linux/arm64 IDs in [lab-runtime-lock.json](lab-runtime-lock.json) explicitly for campaigns. They derive from the [native runtime lock](../harbor-native-2026-11/runtime-lock.json), with the synthetic Harbor input removed. Existing image tags are unchanged. Public NPM artifact preparation used registry networking without credentials; final image assembly and all protocol tests used Docker network `none`. Package versions, integrity values, inventories and source hashes are recorded. These local image IDs are not portable registry manifest digests.

Sonnet requires adaptive thinking, no sampling/budget parameters and intact empty signed-thinking replay. Sol tool calling requires Responses, without sampling parameters at medium effort. Pi's context/output metadata is complete; native per-request output ceilings still differ across harnesses. Equal effort names do not equalize inference behavior.

## Evidence and limits

[Lab smoke evidence](sdk-smoke-evidence.json) invokes the actual lab adapters or SDK entrypoints with loopback transport instrumentation, fake credentials, private HOME and no host mounts. [Native evidence](../harbor-native-2026-11/native-smoke-evidence.json) exercises actual pinned Harbor setup/run/trace conversion, not a full native-agent Harbor Trial. [Control evidence](../harbor-native-2026-11/control-evidence.json) separately exercises four real Harbor Trials against a common isolated verifier; rewards are1/0/0/0 on the representative mini image. No layer establishes real-model task performance.

The strict provider fixture rejects obsolete Sonnet parameters, dropped signed-thinking history and Sol Chat Completions tool calls. Codex's HTTP-only fixture exercises native WebSocket-to-SSE fallback; it does not qualify the live WebSocket path. Harbor Pi uses generated custom-endpoint metadata for the fixture; the direct-provider profile is independently probed. All fixture token/cost fields are **synthetic**, never measured billing. Missing response identity and incomplete accounting remain unknown in the lab parsers.

Raw logs and prepared task packages are retained locally under ignored `.cache/`, bound by checked-in hash manifests. The aggregate validator requires those exact local artifacts. A clean checkout must rebuild/rematerialize/retest locally; a JSON summary alone cannot prove those missing bytes.

## Pilot budget

| Proposed program | Slots | Per attempt target | Total target |
| --- | ---: | ---: | ---: |
| Current campaigns | 3 Anthropic + 3 OpenAI | USD 2 | USD 12 |
| Refreshed native Harbor | 3 Anthropic + 3 OpenAI | USD 2 | USD 12 |
| Combined, separate allocations | 12 | USD 2 | USD 24 |

Both models list USD 2 input / USD 10 output per million tokens at standard global rates. Conditions and primary sources are in [model-migration.json](model-migration.json) and [pilot-budget.json](pilot-budget.json). At 500K aggregate input + 30K output per pilot, with each request at most 272K input and no caching, six campaign pilots cost USD 7.80 arithmetically (previous selection USD 7.38). A 30% Sonnet tokenizer sensitivity makes USD 8.97. These are scenarios, not forecasts or measurements. One Sol request at 500K input + 30K output costs USD 2.45 because of long-context pricing and exceeds the target.

No reserve, automatic extra attempts or transfers. Run sequentially only after separate authorization, with settled attributable billing before admission. Unknown costs block the next slot. Failures consume spend; observed targets can be exceeded by in-flight calls or delayed billing. The 36 comparison slots remain unauthorized, with USD 72 nominal task-target arithmetic only. Task contracts were not edited.

## Preservation and offline verification

[previous-campaign/](previous-campaign/) contains the exact eight files from the previous selection. [preservation-before.json](preservation-before.json) seals 1470 historical result/Harbor files; existing records, traces and the previous native pilot are byte-identical. The six refreshed native records have new IDs and remain `prepared`, with no measured outcomes. The 42 campaign slots remain unstarted without run IDs.

From the repository root, using the pinned Harbor Python environment and Node on PATH:

```sh
python experiments/common/model-refresh-2026-11/check_migration.py
python -m unittest discover -s experiments/common/harbor-native-2026-11 -p 'test_*.py'
node --test experiments/common/harbor-native-2026-11/mock-provider.test.mjs experiments/*/adapter.test.mjs
npm run check
```

To repeat protocol tests after changing code/images, run `sdk-smoke.py --docker-host <local Unix socket>` and the new native revision's `offline_smoke.py` / `verify_controls.py` commands described in its README. Freeze and seal a new revision before any live execution; do not rewrite historical prepared records.
