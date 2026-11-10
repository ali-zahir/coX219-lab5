#!/usr/bin/env python3
"""Lab 5, Part 3: monitoring, decision, safety and orchestration agents."""

import subprocess

MIN_REPLICAS = 1
MAX_REPLICAS = 4
DEPLOYMENT = "static-site"
VALID_ACTIONS = {"ALERT", "SCALE_UP", "SCALE_DOWN", "DO_NOTHING"}


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


class MonitoringAgent:
    def observe(self, cpu: float) -> dict:
        return {"cpu": cpu, "replicas": get_replicas(DEPLOYMENT)}


class DecisionAgent:
    def decide(self, observation: dict) -> str:
        cpu = observation["cpu"]
        replicas = observation["replicas"]
        if cpu > 95:
            return "ALERT"
        if cpu > 70 and replicas < MAX_REPLICAS:
            return "SCALE_UP"
        if cpu < 25 and replicas > MIN_REPLICAS:
            return "SCALE_DOWN"
        return "DO_NOTHING"


class SafetyAgent:
    def validate(self, action: str, replicas: int) -> bool:
        if action not in VALID_ACTIONS:
            return False
        if action == "SCALE_UP":
            return replicas < MAX_REPLICAS
        if action == "SCALE_DOWN":
            return replicas > MIN_REPLICAS
        return True


class ExecutionAgent:
    def execute(self, action: str) -> None:
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


class Orchestrator:
    def __init__(self) -> None:
        self.monitor = MonitoringAgent()
        self.decision = DecisionAgent()
        self.safety = SafetyAgent()
        self.executor = ExecutionAgent()

    def run(self, cpu: float) -> int:
        observation = self.monitor.observe(cpu)
        print(f"Monitoring Agent: {observation}")

        action = self.decision.decide(observation)
        print(f"Decision Agent: {action}")

        approved = self.safety.validate(action, observation["replicas"])
        print(f"Safety Agent: {'APPROVED' if approved else 'REJECTED'}")

        if approved:
            self.executor.execute(action)
        else:
            print("Orchestrator: action rejected; no change made")

        final_replicas = get_replicas(DEPLOYMENT)
        print(f"Orchestrator: verified replicas = {final_replicas}")
        return final_replicas


def read_cpu() -> float:
    value = float(input("Enter simulated CPU percentage (0-100): "))
    if not 0 <= value <= 100:
        raise ValueError("CPU percentage must be between 0 and 100")
    return value


def main() -> None:
    Orchestrator().run(read_cpu())


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
