# Open educational episodes

These are artificial tasks for learning and experiment design. They are **not registered in `tasks/`**, are not an external benchmark and do not establish any model's quality. Checks here are open; participants may read them. The prohibition on reading `tasks/*/check/` remains in force for real repository tasks.

| Directory | Skill | Initial state |
| --- | --- | --- |
| [multi-file-bug](multi-file-bug/episode.md) | Fix order normalization and atomic stock updates | Three open scenarios should fail, two should pass |
| [interface-migration](interface-migration/episode.md) | Migrate API, pagination and consumer | Three open scenarios should fail, one should pass |
| [conflicting-sources](conflicting-sources/episode.md) | Dossier with conflicting measurements and changed conditions | Only sources exist; the answer must be created |
| [judge-calibration](judge-calibration/episode.md) | Independently evaluate four anonymized educational responses | Responses deliberately differ in rubric compliance |

Node episodes require Node.js ≥22 and Bash, with no dependencies or network. Work on a copy inside a new educational report. Example for LAB21; run from the repository root once per new session:

```bash
npm run lab:new -- --lab LAB21 --session memory-pilot
LAB_DIR='experiments/local-models/measurements/LAB21-memory-pilot'
EPISODE_DIR="$LAB_DIR/raw/multi-file-bug"
test ! -e "$EPISODE_DIR" && cp -R docs/labs/episodes/multi-file-bug "$EPISODE_DIR"
```

If copying fails, choose a new session; do not continue over a previous experiment. First save the initial result, then modify allowed files in the **copy**, not the source fixture. The check command is identical for `multi-file-bug` and `interface-migration`:

```bash
(
  set -o noclobber
  if node "$EPISODE_DIR/check.mjs" > "$LAB_DIR/raw/initial-check.json"; then
    printf '0\n' > "$LAB_DIR/raw/initial-check.exit"
  else
    printf '%s\n' "$?" > "$LAB_DIR/raw/initial-check.exit"
  fi
)
```

Initial exit 1 and contract-listed failures are expected: they describe the educational defect. After fixing it, run the check into **new** `final-check.json` and `final-check.exit` files. Exit 1 alone is insufficient: module-loading failure is not the intended scenario failure. Compare names and actual results of all scenarios.

Open checks cover only listed cases. Propose additional checks in the report, explain changes and attach a diff. Do not edit the public check to make it green; keep additional checks in a separate file.

A real agent series first needs separate registration of a new task ID: immutable contract, snapshot preparation, workspace seed, allowed actions, independent evaluation and lifecycle checks. Do not substitute a `docs/labs/episodes` path for `--task T002` or present a manual educational session as `results/runs/<run-id>`. Registration must not modify existing `tasks/*/task.md` or read their hidden checks. LAB21–24 define additional engineering conditions; shared guide: [report completeness](../report-validation.md), educational simulation: [offline practice](../practice.md).
