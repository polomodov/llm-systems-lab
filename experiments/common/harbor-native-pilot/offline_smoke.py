#!/usr/bin/env python3
"""Run pinned native Harbor adapter lifecycles against loopback fixtures only.

No Harbor Trial is constructed: verify_controls.py separately qualifies the
complete task/verifier boundary. This checks native setup, tool use and ATIF.
"""
import sys
from pathlib import Path
# The historical source-inspection script is named inspect.py; do not shadow
# Python's inspect module while importing Harbor/Pydantic.
sys.path = [p for p in sys.path if Path(p).resolve() != Path(__file__).resolve().parent]
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import socket
from types import SimpleNamespace
from uuid import uuid4

BASE = Path(__file__).resolve().parent
DOCKER = shutil.which("docker")


async def command(*args, timeout=180):
    process=await asyncio.create_subprocess_exec(*map(str,args),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        out,err=await asyncio.wait_for(process.communicate(),timeout)
    except (asyncio.TimeoutError,asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    return SimpleNamespace(return_code=process.returncode,stdout=out.decode(errors="replace"),stderr=err.decode(errors="replace"))


class OfflineEnvironment:
    default_user="1000:1000"
    def __init__(self, name, docker_host, extra_env):
        self.name=name
        self.docker_host=docker_host
        self.extra_env=extra_env
        self.commands=[]
    async def docker(self,*args,**kwargs):
        if DOCKER is None:
            raise RuntimeError("docker is not installed")
        return await command(DOCKER,"--host",self.docker_host,*args,**kwargs)
    async def exec(self, command, user=None, env=None, cwd=None, timeout_sec=None, **kwargs):
        self.commands.append({"command":command,"user":user or self.default_user,"cwd":cwd or "/app","env_names":sorted({**self.extra_env,**(env or {})}),"timeout_sec":timeout_sec or 120})
        args=["exec","--user",user or self.default_user,"--workdir",cwd or "/app"]
        for key,value in {**self.extra_env,**(env or {})}.items():
            args.extend(["--env",f"{key}={value}"])
        return await self.docker(*args,self.name,"bash","-c",command,timeout=timeout_sec or 120)
    async def upload_file(self,source_path,target_path):
        result=await self.docker("cp",str(source_path),f"{self.name}:{target_path}")
        if result.return_code:raise RuntimeError(result.stderr)
    async def download_dir(self,source_dir,target_dir):
        Path(target_dir).mkdir(parents=True,exist_ok=True)
        result=await self.docker("cp",f"{self.name}:{source_dir}/.",str(target_dir))
        if result.return_code:raise RuntimeError(result.stderr)


def terminal_event(harness, logs):
    if harness=="mini-swe-agent":
        native=json.loads((logs/"mini-swe-agent.trajectory.json").read_text())
        status=native["info"].get("exit_status")
        if status!="Submitted":
            raise ValueError(f"mini did not submit: {status}")
        return status
    events=[]
    for line in (logs/f"{harness}.txt").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        raise ValueError("Native terminal trace is missing")
    last=events[-1]
    passed={
        "codex":last.get("type")=="turn.completed",
        "claude-code":last.get("type")=="result" and last.get("subtype")=="success" and last.get("is_error") is False,
        "opencode":last.get("type")=="step_finish" and last.get("part",{}).get("reason")=="stop",
        "pi":last.get("type")=="agent_end" and (last.get("messages") or [{}])[-1].get("stopReason")=="stop",
    }
    if not passed[harness]:
        raise ValueError(f"Native trace did not terminate successfully: {last.get('type')}")
    return last["type"]


async def run_slot(slot,lock,host,output):
    from harbor.agents.factory import AgentFactory
    from harbor.models.agent.name import AgentName
    from harbor.models.agent.context import AgentContext
    from harbor.utils.trajectory_validator import TrajectoryValidator
    name="harbor-native-smoke-"+uuid4().hex
    logs=output/slot["slot_id"]
    logs.mkdir(parents=True)
    fake={"HARBOR_OFFLINE_FIXTURE_KEY":"offline-fixture-not-a-secret","HOME":"/home/agent","LITELLM_LOCAL_MODEL_COST_MAP":"True","DISABLE_AUTOUPDATER":"1","OPENCODE_DISABLE_AUTOUPDATE":"true",**slot.get("planned_env",{})}
    environment=OfflineEnvironment(name,host,fake)
    record={"slot_id":slot["slot_id"],"harness":slot["harness"],"model":slot["wire_model_id"],"status":"failed","raw_directory":str(logs.relative_to(BASE)),"provider_requests":0,"synthetic_protocol_usage":True}
    try:
        image=lock["images"][slot["harness"]]["image_id"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}",image):
            raise ValueError("Offline smoke requires a local immutable image ID")
        record["image_id"]=image
        # Native setup explicitly requests root mkdir/chown/chmod. These three
        # capabilities serve setup; the task process and its tools stay UID1000.
        started=await environment.docker("run","--detach","--rm","--pull=never","--name",name,"--network","none","--user","1000:1000","--cap-drop","ALL","--cap-add","CHOWN","--cap-add","DAC_OVERRIDE","--cap-add","FOWNER","--security-opt","no-new-privileges","--cpus","1","--memory","2g","--pids-limit","256","--entrypoint","sleep",image,"infinity")
        if started.return_code:raise RuntimeError(started.stderr)
        inspect=await environment.docker("inspect",name,"--format","{{json .HostConfig.NetworkMode}}")
        assert json.loads(inspect.stdout)=="none"
        record["docker_network"]="none"
        mounts=await environment.docker("inspect",name,"--format","{{json .Mounts}}")
        assert json.loads(mounts.stdout)==[],"Unexpected container mount"
        record["host_mounts"]=[]
        record["setup_capabilities"]=["CHOWN","DAC_OVERRIDE","FOWNER"]
        await environment.upload_file(BASE/"mock-provider.mjs","/tmp/mock-provider.mjs")
        prepared=await environment.exec("mkdir -p /logs/agent /app/output; node /tmp/mock-provider.mjs > /logs/agent/mock-server.log 2>&1 &")
        assert prepared.return_code==0,prepared.stderr
        await asyncio.sleep(0.2)
        kwargs=dict(slot["planned_kwargs"])
        fmt="anthropic_messages" if slot["provider"]=="anthropic" else slot.get("model_api_format","openai_responses")
        # Anthropic's SDK appends /v1; OpenCode's AI SDK expects it in baseURL.
        fixture_base="http://127.0.0.1:8768"+("" if slot["provider"]=="anthropic" and slot["harness"]!="opencode" else "/v1")
        record["fixture_base_url"]=fixture_base
        record["fixture_model_api_format"]=fmt
        agent=AgentFactory.create_agent_from_name(AgentName(slot["harbor_agent"]),logs_dir=logs/"agent",model_name=slot["model_name"],base_url=fixture_base,model_api_format=fmt,model_api_key_name="HARBOR_OFFLINE_FIXTURE_KEY",extra_env=fake,**kwargs)
        (logs/"agent").mkdir()
        await asyncio.wait_for(agent.setup(environment),30)
        record["harbor_detected_version"]=agent.version()
        probe=await environment.exec(agent.get_version_command())
        observed=agent.parse_version((probe.stdout or "")+"\n"+(probe.stderr or ""))
        assert probe.return_code==0 and observed==slot["version"],f"Independently detected version mismatch: {observed}"
        record["observed_version"]=observed
        if agent.version()!=observed:
            record["native_version_detection_limitation"]="Pinned Pi writes version to stderr; pinned Harbor reads stdout only. Independent exact-version gate uses both streams without modifying the CLI or adapter."
        context=AgentContext()
        instruction=(BASE/"task/instruction.md").read_text()
        record["instruction_sha256"]=hashlib.sha256(instruction.encode()).hexdigest()
        await asyncio.wait_for(agent.run(instruction,environment,context),100)
        record["native_process_exit_code"]=0
        await environment.download_dir("/logs/agent",logs/"agent")
        record["native_terminal_event"]=terminal_event(slot["harness"],logs/"agent")
        agent.populate_context_post_run(context)
        artifact=await environment.exec("cat /app/output/result.json; cat /app/output/model-tool.json")
        lines=artifact.stdout.splitlines()
        assert artifact.return_code==0,artifact.stderr
        assert json.loads(lines[0])==["apple","banana","pear"]
        assert json.loads(lines[1])=={"fixture":True,"uid":1000,"tool_executed":True,"cap_eff":"0000000000000000"}
        await environment.download_dir("/app/output",logs/"artifact")
        input_bytes=await environment.exec("cat /app/input.json")
        assert input_bytes.return_code==0
        record["input_sha256"]=hashlib.sha256(input_bytes.stdout.encode()).hexdigest()
        assert record["input_sha256"]==hashlib.sha256((BASE/"task/environment/input.json").read_bytes()).hexdigest(),"Public input changed"
        record["artifact_verified"]=True
        record["tool_executed_as_uid"]=1000
        record["task_effective_capabilities"]=[]
        trajectory=logs/"agent/trajectory.json"
        validator=TrajectoryValidator()
        assert validator.validate(trajectory),validator.get_errors()
        atif=json.loads(trajectory.read_text())
        assert any(s.get("tool_calls") and s.get("observation",{}).get("results") for s in atif["steps"]),"Native ATIF lacks observed tool operation"
        record["atif_schema"]=atif["schema_version"]
        record["atif_agent"]={k:atif["agent"].get(k) for k in ["name","version","model_name"]}
        record["atif_step_count"]=len(atif["steps"])
        record["native_trace_complete"]=True
        if slot["harness"]=="pi":
            await environment.download_dir("/tmp/harbor-pi-agent",logs/"fixture-pi-config")
            record["fixture_route_limitation"]="Harbor generates provider harbor-endpoint in isolated PI_CODING_AGENT_DIR. Its model metadata/defaults and settings lookup differ from the frozen direct-provider profile; only transport/tool/trace plumbing is qualified here."
        record["status"]="passed"
    except Exception as error:
        record["error"]=str(error) or type(error).__name__
    finally:
        try:
            await environment.download_dir("/logs/agent",logs/"agent")
        except Exception as error:
            record["log_collection_error"]=str(error) or type(error).__name__
        finally:
            removed=await environment.docker("rm","--force",name)
            record["cleanup_confirmed"]=removed.return_code==0 or "No such container" in removed.stderr
            (logs/"commands.json").write_text(json.dumps(environment.commands,indent=2)+"\n")
    request_file=logs/"agent/mock-requests.jsonl"
    requests=[json.loads(line) for line in request_file.read_text().splitlines()] if request_file.exists() else []
    record["fixture_requests"]=len(requests)
    record["observed_request_models"]=sorted({r.get("model") for r in requests if r.get("model")})
    record["observed_request_paths"]=sorted({r["path"] for r in requests})
    record["observed_request_settings"]=[r.get("settings",{}) for r in requests]
    if record["observed_request_models"]!=[slot["wire_model_id"]]:record["status"]="failed";record["model_error"]="Fixture model IDs differ from requested ID"
    if not record["cleanup_confirmed"]:record["status"]="failed"
    manifest={str(p.relative_to(logs)):{"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size} for p in sorted(logs.rglob("*")) if p.is_file()}
    (logs/"evidence-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    record["evidence_manifest_sha256"]=hashlib.sha256((logs/"evidence-manifest.json").read_bytes()).hexdigest()
    record["evidence_files"]={name:data for name,data in manifest.items() if name=="commands.json" or name.startswith("artifact/") or name.startswith("agent/") and (name.endswith(".jsonl") or name.endswith("trajectory.json") or name.endswith(".txt"))}
    return record


def slot_configuration_sha256(plan):
    slots=[{k:v for k,v in slot.items() if k not in {"status","run_id","image_id"}} for slot in plan["slots"]]
    return hashlib.sha256(json.dumps(slots,sort_keys=True,separators=(",",":")).encode()).hexdigest()


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-host",required=True)
    parser.add_argument("--slot")
    parser.add_argument("--runtime-lock",type=Path,default=BASE/"runtime-lock.json")
    args=parser.parse_args()
    if not args.docker_host.startswith("unix://"):
        raise ValueError("Local Unix Docker only")
    os.environ.clear()
    os.environ.update({"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(BASE / ".cache/smoke-home"), "HARBOR_TELEMETRY": "0", "LITELLM_LOCAL_MODEL_COST_MAP": "True"})
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
    # Harbor imports run on the host. Forbid their IP socket connections too;
    # native CLIs and the loopback fixture live in network=none containers.
    def no_host_ip_connections(event,args):
        if event=="socket.connect" and args[0].family!=socket.AF_UNIX:
            raise RuntimeError("Host IP connections are disabled during offline smoke")
    sys.addaudithook(no_host_ip_connections)
    runtime_bytes=args.runtime_lock.read_bytes()
    plan_bytes=(BASE/"plan.json").read_bytes()
    lock=json.loads(runtime_bytes)
    plan=json.loads(plan_bytes)
    expected={"HN-O01","HN-A01","HN-A02","HN-A03","HN-O02","HN-O03"}
    if len(plan["slots"])!=6 or {slot["slot_id"] for slot in plan["slots"]}!=expected:
        raise ValueError("Expected exactly the six frozen pilot slots")
    checkout=BASE.with_name("harbor-interop")/".cache/harbor"
    commit=await command("/usr/bin/git","-C",checkout,"rev-parse","HEAD")
    if commit.return_code or commit.stdout.strip()!=plan["harbor_commit"]:
        raise ValueError("Pinned Harbor checkout commit mismatch")
    output=BASE/".cache/native-smoke"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True)
    (output/"plan.json").write_bytes(plan_bytes)
    (output/"runtime-lock.json").write_bytes(runtime_bytes)
    component_paths=[BASE/"offline_smoke.py",BASE/"mock-provider.mjs",BASE/"task/instruction.md",BASE/"task/environment/input.json"]
    component_hashes={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in component_paths}
    slot_hash=slot_configuration_sha256(plan)
    records=[]
    for slot in plan["slots"]:
        if args.slot and slot["slot_id"]!=args.slot:continue
        result=await run_slot(slot,lock,args.docker_host,output)
        records.append(result);print(json.dumps(result),flush=True)
    assert records,"No selected slots"
    components_stable=component_hashes=={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in component_paths}
    runtime_stable=runtime_bytes==args.runtime_lock.read_bytes()
    slots_stable=slot_hash==slot_configuration_sha256(json.loads((BASE/"plan.json").read_text()))
    report={
        "kind":"native-harbor-offline-fixture-lifecycle-evidence",
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "harbor_commit":plan["harbor_commit"],
        "plan_sha256":hashlib.sha256(plan_bytes).hexdigest(),
        "slot_configuration_sha256":slot_hash,
        "runtime_lock_sha256":hashlib.sha256(runtime_bytes).hexdigest(),
        "frozen_inputs_stable":{"components":components_stable,"runtime_lock":runtime_stable,"slot_configuration":slots_stable},
        "frozen_input_directory":str(output.relative_to(BASE)),
        "provider_requests":0,
        "real_credentials_read":False,
        "paid_runs":0,
        "host_ip_connections":"blocked by Python audit hook; Docker client uses local Unix socket",
        "scope":"Actual pinned Harbor agent setup/run/populate_context with custom Docker exec environment and deterministic in-container loopback protocol fixture. Not a Harbor Trial, live-model qualification, measured usage or billing.",
        "transport_deviation":"Fixture-only base_url override; Pi uses Harbor-generated isolated harbor-endpoint metadata/settings instead of the direct-provider profile, which is separately verified in runtime evidence.",
        "usage_and_cost":"Response token fields are constant synthetic protocol fixtures. Any native usage/cost derived from them is synthetic and must never be imported as real billing or campaign performance.",
        "offline_limits":{"agent_timeout_s":100,"max_fixture_requests":16,"memory":"2g","cpus":1,"pids":256},
        "components_sha256":component_hashes,
        "slots":records,
    }
    (output/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    if not args.slot:(BASE/"native-smoke-evidence.json").write_text(json.dumps(report,indent=2)+"\n")
    return 0 if all(r["status"]=="passed" for r in records) and components_stable and runtime_stable and slots_stable else 1


if __name__=="__main__":raise SystemExit(asyncio.run(main()))
