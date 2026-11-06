# S04 — correction to S03, 2026-09-08

Artificial educational source. Class: correction to operations observation.

S03 states the wrong unit: it should read **17 output tokens/s for one of the requests**, not requests/s. This is neither the average across four requests nor total server throughput. The measurement includes only decode. The numeric value is unchanged; throughput conclusions must be revised. Full logs for all four requests are unavailable.
