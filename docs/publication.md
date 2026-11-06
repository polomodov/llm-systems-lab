# Publication and archive provenance

The code is distributed under [MIT](../LICENSE), copyright © 2026 polomodov.
Third-party models, CLIs, dependencies and quoted material retain their own
licenses; this repository's MIT license does not change their terms.

## Sanitized history

During publication preparation on 2026-11-06, branch history was rewritten:
personal Git email addresses were replaced with GitHub noreply addresses and
the owner's author name with `polomodov`. Home directories, the machine
hostname, confirmed LAN addresses in access logs and personal Claude Code
session links were replaced with neutral values. Public project and author
names, loopback addresses, network allowlists and test addresses were preserved.

Affected measurement archives and run records are derivative copies.
Their adjacent `privacy-redaction.json` files list the original and published
SHA-256 values of changed files. LAB archives also disclose the limitation
in `PUBLICATION-REDACTION.md`, and run records disclose it in `notes`.
Input, artifact and evaluation integrity hashes were recomputed for the new
bytes; local deployment fingerprints changed along with the paths.
Integrity checks remain enabled.

Runs and evaluations were not repeated. Verdicts, tokens, cost, duration and
other numerical results were preserved. Measured external model and binary
hashes, execution timestamps and source revisions describe the original
experiment. They are not evidence of a new run or hashes of sanitized logs.
Workspaces absent from Git were not reconstructed. The original history is
kept in a separate private backup and is not part of the published ancestry.

## English project, original evidence

Current documentation, task contracts, agent specifications, comments and
tool output are maintained in English. Saved model responses, measurement
logs, sealed run inputs and historical commits retain their original language
as research evidence. Compatibility parsers and multilingual test data may
contain source-language literals.

Translating a task changes its input bytes and can change model behavior.
New English contracts and prompts therefore define new experimental
conditions. Historical runs retain their original sealed contracts and
fingerprints; the language migration does not relabel them as English runs.
The comparison report continues to separate runs by their actual inputs.

## Repository migration

The public repository is [polomodov/llm-systems-lab](https://github.com/polomodov/llm-systems-lab).
It was created from the sanitized `main` ancestry, without importing the
source repository's pull-request refs, issues, Actions logs or artifacts.
The source repository remains private. This avoids publishing its old
GitHub-managed refs, which an ordinary history rewrite cannot remove.

Commit SHAs changed during sanitization. Prefer a fresh clone when continuing
work. Do not merge old unsanitized branches or force-push them into this
repository: doing so would reintroduce the original metadata. Transfer any
needed uncommitted work as a reviewed patch, without its old history. Use a
public Git identity for new commits:

```bash
git clone https://github.com/polomodov/llm-systems-lab.git
cd llm-systems-lab
git config --local user.name polomodov
git config --local user.email 6575406+polomodov@users.noreply.github.com
mise trust
mise install
mise run verify
```

`mise.local.toml` and `.mise.local.toml` are ignored by Git. Secrets remain in
`.env`; mise does not load it. Tool versions and check commands are documented
in the [README](../README.md#requirements-and-images).

## Limits of history cleanup

Rewriting branches does not erase old clones, forks, cached SHAs or
GitHub-managed `refs/pull/*` in the original repository. Cleaning PR descriptions
does not rewrite their stored commits. [GitHub documents these limitations
and the Support process](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
Support does not promise removal of non-sensitive data. The new public
repository excludes those original refs; separately retained private copies
still exist.
