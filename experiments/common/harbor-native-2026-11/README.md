# Refreshed native Harbor qualification

This separate, non-executable revision selects Sonnet 5.5 and GPT-6.1 Sol. The previous [native pilot](../harbor-native-pilot/) remains unchanged. [Plan](plan.json), immutable [images](runtime-lock.json), [packages](package-lock.json) and six new prepared records are sealed. All execution authorization remains false.

Six actual native adapter fixture lifecycles pass: Claude Code, OpenCode and Pi on Anthropic; Codex, mini-SWE-agent and Pi on OpenAI. All send the exact model and medium effort, execute a task tool, produce valid ATIF and reach a successful terminal event. Native harness modes, prompts, tools and turn semantics still differ from the lab. Four separate real Harbor Trial controls pass with rewards 1/0/0/0 against a common isolated verifier on the mini image. These controls do not establish a full native-agent Trial or live-model qualification.

[Migration report](../model-refresh-2026-11/README.md) documents the compatibility changes, rejected OpenCode upgrade, fixture transport differences, preservation and budget scenarios. This revision's six pilots have a separate USD 12 target, no reserve and no spending authorization. The old prepared slots must not be executed as part of this revision. Real identity, usage, independent verdict and settled attributable billing remain required; unknown is not zero.

The task contract/spec/input/evaluator bytes match the previous native task. Its canonical lab registration is reused, while new runtime/model conditions and run IDs are independently sealed. Source helpers for building/probing the unchanged base images remain in the previous directory and are hash-bound by this revision. Accounting documentation and lifecycle semantics are in the preserved [accounting guide](../harbor-native-pilot/ACCOUNTING.md).

From repository root with pinned Harbor 0.25.0 Python and Node on PATH:

```sh
python experiments/common/harbor-native-2026-11/materialize.py --check
python experiments/common/harbor-native-2026-11/check_preparation.py
python -m unittest discover -s experiments/common/harbor-native-2026-11 -p 'test_*.py'
```

Offline fixture execution (fake keys only, Docker network none, no host mounts):

```sh
python experiments/common/harbor-native-2026-11/offline_smoke.py --docker-host <local Unix socket>
python experiments/common/harbor-native-2026-11/verify_controls.py --docker-host <local Unix socket> --docker-plugin-dir experiments/common/harbor-interop/.cache/docker-plugins
```

Read each script's `--help` for subset controls. Repeating these commands replaces local summary evidence and must be followed by aggregate validation; a configuration change requires a new sealed preparation rather than edits to an existing record. Local ignored raw evidence is necessary to reproduce the current aggregate validation. No paid launcher is provided.
