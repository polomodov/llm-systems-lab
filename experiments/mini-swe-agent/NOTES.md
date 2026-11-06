# Notes · mini-SWE-agent

No runs yet.

2026-09-21 — offline verification of the built image on the operator’s machine (Docker Engine 29.5.2, host darwin/arm64), without keys or provider requests: the profile’s version command in a read-only container returned exactly the pinned version 2.4.6. Verified local image ID: `sha256:92f5d2d5624cfb17d3a46cd8a4895673d06d5b3c2b86317a75e58f1c534f54d6`. Rebuilding may produce a different ID; retain one image for a series. This checks installation, not a task result.
