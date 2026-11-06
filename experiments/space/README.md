# SPACE: Firecracker sandboxes as an agent execution environment

> **Frozen on 2026-11-05.** The lab guide is retained, but new `lab:new` sessions are disabled: the SPACE track has no measurements or implementation and is being separated into a training repository. Unfreezing requires a separate decision recorded in the [course status](../../docs/labs/README.md#frozen-infrastructure-tracks).

Directory for the [LAB36–42 track](../../docs/labs/README.md#space-track). [SPACE](https://github.com/polomodov/SPACE) is an open sandbox platform based on Firecracker microVMs (a fork of `perplexityai/SPACE`, Apache 2.0). This track tests its behavior underneath this lab’s agent harnesses. It is not a harness: there is no `harness.json` here, and there should not be one.

Status: **lab guides ready; no measurements**. SPACE compatibility with the test machines is `unverified` until the first LAB36 session. A SPACE runner backend has not been implemented; LAB37 creates it.

## Test environments

| Environment | Machine | Role |
| --- | --- | --- |
| A, `ryzen-NN` sessions | Ryzen AI Max+ 395 / 128 GB / Linux, the same machine as LAB02 | Full smoke test, campaigns, and agents with a local model |
| B, `honor-NN` sessions | HONOR MagicBook X16, Ryzen 7 PRO 8845HS / 32 GB / Ubuntu | Minimal profile and memory-limit investigation |

Both require Linux x86_64 with `/dev/kvm` (AMD-V enabled in BIOS), `/dev/net/tun`, Docker with privileged containers, loop devices, and btrfs. Requirements and installation steps are in the SPACE repository’s `docs/installation.md`.

## Contents

| Path | Contents | Introduced in |
| --- | --- | --- |
| `measurements/LABxx-session/` | Reports created with `npm run lab:new -- --lab LAB36 --session ryzen-01` | LAB36–42 |
| `recipes/` | SPACE template recipes built from harness images | LAB37 |
| `tools/` | exec/files tool server over the SPACE API | LAB38 |
| `bench/` | Time-to-first-command measurement tool | LAB40 |
| `egress/` | Egress profile and synthetic probes | LAB41 |
| `campaign/` | Parallel-series scheduler | LAB42 |

Each lab creates the subdirectories it needs. Every component added to a harness or runner receives a [ledger](../../docs/harness-ledger.md) row in the same change.

## Rules

- Pin SPACE by commit hash in every report; pin templates by image digest and template content hash.
- Keep SPACE bearer tokens, console passwords, and provider keys out of reports, raw artifacts, and commits.
- Configuration changes apply only to the local Kind instance on the current test machine.
- Numbers from SPACE documentation are platform developers’ claims; identify our own measurements by run ID or session.
