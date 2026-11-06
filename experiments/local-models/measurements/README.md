# Local-model measurements: archive outside the working tree

Before 2026-11-05 this directory held 98 `LABxx-session` bundles (about 150 MB, including binary `.sse`/`.bin` traces and server `.log` files). They made the lab repository heavy and are not required for its main `new-run → prepare-run → run → judge-run → compare` lifecycle.

The archive remains in Git history. Personal metadata was sanitized for publication on 2026-11-06; affected bundles contain `privacy-redaction.json` and `PUBLICATION-REDACTION.md`. Measurements were not rerun and numerical results were preserved. See the [transformation limits](../../../docs/publication.md). The last sanitized-history commit containing the measurement tree is:

```
a12e9f430f8b4bd19f1d316811a63b7caca9e4cc
```

Documentation links use permalinks to that commit. To extract a separate repository or release artifact:

```bash
git fetch origin a12e9f430f8b4bd19f1d316811a63b7caca9e4cc
git archive --format=tar.gz --prefix=local-models-measurements/ \
  -o local-models-measurements-a12e9f430f8b.tar.gz \
  a12e9f430f8b4bd19f1d316811a63b7caca9e4cc experiments/local-models/measurements
```

The archive also retains Mac-lab exporter regressions in `experiments/local-models/test_lab3x_*.py`, which consumed these bundles. Exporters in `apple/*.py` remain in the working tree.

New reports from `npm run lab:new` are still created here. Move large series to a separate measurement repository before publication, leaving a link and summary here. Original archived reports and traces retain their source language as research evidence.
