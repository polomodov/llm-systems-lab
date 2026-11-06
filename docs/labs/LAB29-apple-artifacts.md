# LAB29. Pinning GGUF and MLX artifacts

## Profile

| Field | Value |
| --- | --- |
| Type / readiness | Artifact preparation / `target-machine` |
| Time | 1–3 hours plus downloads |
| Prerequisites | LAB28 and the shared Apple protocol |
| Minimum | One source model, one GGUF and one MLX variant, or a documented MLX blocker |

## Objective

Produce verifiable weight and input-protocol manifests suitable for reruns on Mac and comparison with Ryzen.

## Hypothesis

Reproducible artifacts for both engines are available for the selected source model. An identical model name does not guarantee identical weights, tokenizer, quantization or template.

## Preparation

```sh
npm run lab:new -- --lab LAB29 --session apple-artifacts
export LAB_DIR='experiments/local-models/measurements/LAB29-apple-artifacts'
npm run --silent local:plan -- --hardware apple-m5-max-128gb-macos --engine all --format json \
  > "$LAB_DIR/raw/candidates.json"
```

Follow the [shared protocol](../../experiments/local-models/apple/README.md). Choose a small candidate for the first smoke test and set SSD/memory limits before downloading. `artifact-required` means MLX weights must be located, not that the model is prohibited. The catalog is shared; inclusion does not prove Metal or MLX architecture support.

## Procedure

1. Select the source repository and **full immutable commit**, then separate repositories/revisions for GGUF and MLX. Save the model card/config, license, file list and conversion provenance. For a GGUF comparison with Ryzen, use exactly the already pinned files and hashes; do not substitute another build with the same quant name.

2. Download only the selected revisions with the storage provider's standard client; record the command and client version in `raw/acquisition.txt`. Do not save secrets. If weights already exist, record the provenance of the local copy. Keep models outside Git/evidence. Set `MODEL_DIR` to a separate directory for **one** variant: all shards, config/tokenizer/template, no other models. `ARTIFACT_NAME` is `gguf` or `mlx`:

   ```sh
   export MODEL_DIR='/absolute/path/to/pinned-model'
   export ARTIFACT_NAME='gguf'
   python3 - "$MODEL_DIR" "$LAB_DIR/raw/$ARTIFACT_NAME-files.json" <<'PY'
   import hashlib, json, pathlib, sys
   root = pathlib.Path(sys.argv[1]).resolve()
   if not root.is_dir():
       raise SystemExit('MODEL_DIR must exist')
   rows = []
   for path in sorted(root.rglob('*')):
       if not path.is_file():
           continue
       relative = path.relative_to(root).as_posix()
       if any(p.startswith('.') for p in pathlib.PurePosixPath(relative).parts):
           continue  # exclude client metadata and hidden files, never include credentials
       digest = hashlib.sha256()
       with path.open('rb') as source:
           for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
               digest.update(block)
       rows.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()})
   if not rows:
       raise SystemExit('No artifact files')
   with pathlib.Path(sys.argv[2]).open('x') as out:
       json.dump({'files': rows, 'total_bytes': sum(r['bytes'] for r in rows)}, out, indent=2)
   PY
   ```

   Repeat for MLX with a new name. All expected shards must be present; hashing an incomplete directory does not establish completeness. Compare SHA with publisher metadata if available. Local hashes establish repeatability of these bytes, not automatically their provenance.

3. Write `raw/artifact-manifest.json`: source model/revision; repository/revision, format, quantization (also bits/group_size and exceptions for MLX), file list/hash evidence, tokenizer/template hashes, license, conversion command/version or reason unknown for each variant. Extract the embedded GGUF tokenizer/template with the pinned runtime and save separately; the GGUF hash fixes the bytes but does not replace a description of template overrides.

4. Compare chat templates, special tokens, thinking/reasoning, EOS and output caps. A template change is a separate configuration. If the MLX source revision is not established, a single-factor comparison is impossible: label it a deployment comparison or blocker; do not invent provenance.

5. Check SSD usage and the rough memory plan. MLX file size is not peak memory; GGUF size does not transfer to MLX. The GPU budget remains unknown until the smoke test. Repeated hashes must match; a corrupt shard prevents admission.

## Results tables

| Variant | Source revision | Artifact revision | Quant / group size | Files / bytes / SHA evidence | Template hash | Admission |
| --- | --- | --- | --- | --- | --- | --- |
| GGUF | | | | | | |
| MLX | | | | | | |

## Deliverables

Report, TSV, manifest v2, acquisition commands, cards/config, hash lists and `artifact-manifest.json`. Do not include weights in the report. `conditions.model_artifact_manifest` references the manifest; explain missing fields.

## Completion criteria

- [ ] Revisions are immutable; all shards accounted for and verified.
- [ ] GGUF and MLX have separate format/quant/size records.
- [ ] Tokenizer/template and source provenance established or explicitly unknown.
- [ ] No capacity claim without a hardware smoke test.
- [ ] Submission checked with `lab:check --mode submission`.

## Review questions

1. Why can GGUF Q4 and MLX 4-bit differ in quality and memory use?
2. What does SHA establish, and what does it not establish?
3. How does a template override change comparison conditions?
4. Why do MoE active parameters not determine total weight size?

## Sources

- [Shared model catalog](../local-model-candidates.md).
- [MLX-LM: models and conversion](https://github.com/ml-explore/mlx-lm).
- [Hugging Face: pinned download](https://huggingface.co/docs/huggingface_hub/guides/download).
- The operator must attach model cards and revision URLs for the selected variants.
