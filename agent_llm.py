#!/usr/bin/env python3
"""Lab 5, Part 2: Ollama advisory agent with deterministic safety gate."""

import json
import subprocess
import urllib.error
import urllib.request

MIN_REPLICAS = 1
MAX_REPLICAS = 4
DEPLOYMENT = "static-site"
MODEL = "llama3.2:1b"
VALID_ACTIONS = {"ALERT", "SCALE_UP", "SCALE_DOWN", "DO_NOTHING"}
DEFAULT_POLICY = (
    "above 95% = ALERT; above 70% and replicas < 4 = SCALE_UP; "
    "below 25% and replicas > 1 = SCALE_DOWN; otherwise = DO_NOTHING"
)


def kubectl(*args: str) -> str:
    cmd = ["microk8s", "kubectl", *args]
    try:
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.STDOUT
        ).strip()
    except FileNotFoundError as exc:
        raise RuntimeError("microk8s is not installed or is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"kubectl failed: {exc.output.strip()}") from exc


def get_replicas(deployment: str) -> int:
    return int(kubectl(
        "get", "deployment", deployment,
        "-o", "jsonpath={.spec.replicas}",
    ))


class ReflexAgent:
    def percept(self, cpu: float, replicas: int) -> str:
        if cpu > 95:
            return "ALERT"
        if cpu > 70 and replicas < MAX_REPLICAS:
            return "SCALE_UP"
        if cpu < 25 and replicas > MIN_REPLICAS:
            return "SCALE_DOWN"
        return "DO_NOTHING"

    def execute_action(self, action: str) -> None:
        if action not in VALID_ACTIONS:
            raise ValueError(f"Unknown action: {action}")
        replicas = get_replicas(DEPLOYMENT)
        if action == "SCALE_UP":
            target = min(replicas + 1, MAX_REPLICAS)
            print(kubectl("scale", "deployment", DEPLOYMENT, f"--replicas={target}"))
        elif action == "SCALE_DOWN":
            target = max(replicas - 1, MIN_REPLICAS)
            print(kubectl("scale", "deployment", DEPLOYMENT, f"--replicas={target}"))
        elif action == "ALERT":
            print("ALERT: CPU is above 95%; no automatic scaling")
        else:
            print("No change required")


def ask_ollama(cpu: float, replicas: int, policy: str) -> dict:
    prompt = f"""You advise Kubernetes scaling.
CPU: {cpu}%; replicas: {replicas}.
Rules: {policy}
Reply as JSON only, with keys action and reason.
The action must be one of: SCALE_UP, SCALE_DOWN, DO_NOTHING, ALERT.
Keep the reason brief."""
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Ollama is unavailable or timed out") from exc

    advice = json.loads(result["response"])
    action = advice.get("action")
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid LLM action: {action}")
    return advice


def read_cpu() -> float:
    value = float(input("Enter simulated CPU percentage (0-100): "))
    if not 0 <= value <= 100:
        raise ValueError("CPU percentage must be between 0 and 100")
    return value


def main() -> None:
    reflex_agent = ReflexAgent()
    cpu = read_cpu()
    replicas = get_replicas(DEPLOYMENT)
    policy = input(f"Policy [{DEFAULT_POLICY}]: ").strip() or DEFAULT_POLICY

    safe_action = reflex_agent.percept(cpu, replicas)
    print(f"Reflex agent decision: {safe_action}")

    try:
        advice = ask_ollama(cpu, replicas, policy)
        llm_action = advice["action"]
        print(f"LLM agent decision: {llm_action}")
        print(f"LLM justification: {advice.get('reason', 'No reason provided')}")
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"LLM advice unavailable: {error}")
        llm_action = safe_action

    approved_action = llm_action if llm_action == safe_action else safe_action
    if llm_action != safe_action:
        print("Safety gate: disagreement; using reflex decision")

    reflex_agent.execute_action(approved_action)
    print(f"Replicas after action: {get_replicas(DEPLOYMENT)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
