#!/usr/bin/env python3
"""Lab 5, Part 1: bounded rule-based Kubernetes scaling agent."""

import subprocess

MIN_REPLICAS = 1
MAX_REPLICAS = 4
DEPLOYMENT = "static-site"
VALID_ACTIONS = {"ALERT", "SCALE_UP", "SCALE_DOWN", "DO_NOTHING"}


def kubectl(*args: str) -> str:
    """Run MicroK8s kubectl and return standard output."""
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
    """Return the desired replica count of a Deployment."""
    value = kubectl(
        "get", "deployment", deployment,
        "-o", "jsonpath={.spec.replicas}",
    )
    return int(value)


class Agent:
    def __init__(self, minimum: int = 1, maximum: int = 4) -> None:
        self._min_replicas = minimum
        self._max_replicas = maximum

    def percept(self, cpu: float, replicas: int) -> str:
        """Choose an action using current CPU and desired replicas."""
        if cpu > 95:
            return "ALERT"
        if cpu > 70 and replicas < self._max_replicas:
            return "SCALE_UP"
        if cpu < 25 and replicas > self._min_replicas:
            return "SCALE_DOWN"
        return "DO_NOTHING"

    def execute_action(self, command: str) -> None:
        """Execute a validated action."""
        if command not in VALID_ACTIONS:
            raise ValueError(f"Unknown action: {command}")

        replicas = get_replicas(DEPLOYMENT)
        if command == "SCALE_UP":
            target = min(replicas + 1, self._max_replicas)
            output = kubectl(
                "scale", "deployment", DEPLOYMENT, f"--replicas={target}"
            )
            print(f"Agent: scaled up: {output}")
        elif command == "SCALE_DOWN":
            target = max(replicas - 1, self._min_replicas)
            output = kubectl(
                "scale", "deployment", DEPLOYMENT, f"--replicas={target}"
            )
            print(f"Agent: scaled down: {output}")
        elif command == "ALERT":
            print("Agent: ALERT - CPU is above 95%; no automatic scaling")
        else:
            print("Agent: no change required")


def read_cpu() -> float:
    value = float(input("Enter simulated CPU percentage (0-100): "))
    if not 0 <= value <= 100:
        raise ValueError("CPU percentage must be between 0 and 100")
    return value


def main() -> None:
    agent = Agent(MIN_REPLICAS, MAX_REPLICAS)
    cpu = read_cpu()
    replicas = get_replicas(DEPLOYMENT)
    print(f"Current replicas: {replicas}; simulated CPU: {cpu}%")
    action = agent.percept(cpu, replicas)
    print(f"Agent decision: {action}")
    agent.execute_action(action)
    print(f"Replicas after action: {get_replicas(DEPLOYMENT)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
