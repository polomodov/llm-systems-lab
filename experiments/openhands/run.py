"""Upstream OpenHands Agent/Conversation with native terminal and file tools."""
import json
import os
import sys

from pydantic import SecretStr
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool
from openhands.tools.terminal.definition import TerminalAction

if "--help" in sys.argv:
    print("OpenHands SDK adapter: run.py <JSON: model, provider, turns, prompt>")
    sys.exit(0)

smoke = '--smoke' in sys.argv
launch = {"model": "openai/gpt-4.1-2025-04-14", "provider": "openai", "turns": 1} if smoke else json.loads(sys.argv[1])
credential = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}[launch["provider"]]
llm = LLM(model=launch["model"], api_key=SecretStr("offline-smoke-placeholder" if smoke else os.environ[credential]), usage_id="agent")
agent = Agent(llm=llm, tools=[Tool(name=TerminalTool.name), Tool(name=FileEditorTool.name)])
errors = []

def emit(event):
    print(json.dumps(event, default=str), flush=True)

def on_event(event):
    raw = event.model_dump(mode="json", exclude_none=True)
    emit({"type": "openhands_event", "event": raw})
    if raw.get("code"):
        errors.append(raw["code"])

conversation = Conversation(
    agent=agent, workspace=os.getcwd(), callbacks=[on_event], visualizer=None,
    max_iteration_per_run=launch["turns"], persistence_dir=None,
)
if smoke:
    conversation.send_message("Initialize native tools for offline smoke; do not run the agent.")
    try:
        result = conversation.agent.tools_map[TerminalTool.name](TerminalAction(command="printf sdk-ready"), conversation)
        assert "sdk-ready" in result.model_dump_json()
        print("OpenHands SDK conversation and native terminal initialized offline; no model call")
    finally:
        conversation.close()
    sys.exit(0)
failed = False
try:
    conversation.send_message(launch["prompt"])
    conversation.run()
except Exception as error:
    failed = True
    print(str(error), file=sys.stderr)
finally:
    state = conversation.state
    status = state.execution_status.value
    # Native iteration exhaustion is an ordinary bounded stop; provider failures are not.
    stop = errors[-1] if errors else ("error" if failed else status)
    failed = failed or (status == "error" and stop != "MaxIterationsReached")
    emit({"type": "lab_openhands_result", "metrics": llm.metrics.model_dump(mode="json"),
          "sessionId": str(state.id), "stopReason": stop, "error": failed})
    conversation.close()
sys.exit(1 if failed else 0)
