"""JSONL transport around the upstream DefaultAgent and its original mini.yaml."""
import json
import os
import sys

from minisweagent.agents.default import DefaultAgent
from minisweagent.config import builtin_config_dir
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models.litellm_model import LitellmModel
import yaml

if "--help" in sys.argv:
    print("mini-SWE-agent adapter: run.py <JSON: model, turns, prompt>")
    sys.exit(0)

def emit(event):
    print(json.dumps(event, default=str), flush=True)

class TracedAgent(DefaultAgent):
    def add_messages(self, *messages):
        result = super().add_messages(*messages)
        for message in messages:
            emit({"type": "mini_message", "message": message})
        return result

smoke = '--smoke' in sys.argv
launch = {"model": "openai/gpt-4.1-2025-04-14", "turns": 1} if smoke else json.loads(sys.argv[1])
config = yaml.safe_load((builtin_config_dir / "mini.yaml").read_text())
config["agent"].update(step_limit=launch["turns"], cost_limit=0, output_path=None)
# These are SDK/config assembly operations; DefaultAgent owns the whole loop.
model = LitellmModel(**(config.get("model", {}) | {"model_name": launch["model"], "cost_tracking": "default"}))
environment = LocalEnvironment(**(config.get("environment", {}) | {"cwd": os.getcwd()}))
agent = TracedAgent(model, environment, **config["agent"])
if smoke:
    assert environment.execute({"command": "printf sdk-ready"})["output"] == "sdk-ready"
    print("mini-SWE-agent SDK and shell initialized offline; no model call")
    sys.exit(0)
exit_code = 0
try:
    outcome = agent.run(launch["prompt"])
    if outcome.get("exit_status") not in ("Submitted", "LimitsExceeded"):
        exit_code = 1
except Exception:
    # Upstream records the exception in its trajectory; preserve it before exit.
    exit_code = 1
finally:
    emit({"type": "lab_mini_result", "trajectory": agent.serialize()})
sys.exit(exit_code)
