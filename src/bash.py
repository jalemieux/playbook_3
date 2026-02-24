import subprocess


def execute_bash(command: str, timeout: int = 30) -> str:
    """Run a bash command and return combined stdout + stderr."""
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return output if output else f"[exit code: {result.returncode}]"
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout}s: {command}")
