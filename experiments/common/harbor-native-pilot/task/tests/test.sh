#!/bin/sh
set -eu
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
python /tests/evaluate.py
