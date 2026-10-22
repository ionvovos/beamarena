"""Sandbox Execution Engine.

Provides an isolated environment for writing files, running tests,
and capturing execution tracebacks safely without corrupting the parent system.
"""

from dataclasses import dataclass
import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional


@dataclass
class ExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0


class Sandbox:
    def __init__(self, base_dir: Optional[str] = None):
        """Initializes a temporary sandbox directory."""
        if base_dir and os.path.exists(base_dir):
            self.root = tempfile.mkdtemp(prefix="beam_sandbox_", dir=base_dir)
        else:
            self.root = tempfile.mkdtemp(prefix="beam_sandbox_")
        self._is_cleaned = False

    def write_file(self, rel_path: str, content: str) -> str:
        """Writes content to a file inside the sandbox, creating parent directories."""
        safe_rel = os.path.normpath(rel_path).lstrip(os.sep)
        target = os.path.join(self.root, safe_rel)

        # Enforce sandbox containment
        if not os.path.abspath(target).startswith(os.path.abspath(self.root)):
            raise ValueError(f"Path traversal attempted: {rel_path}")

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def read_file(self, rel_path: str) -> str:
        """Reads content from a file inside the sandbox."""
        safe_rel = os.path.normpath(rel_path).lstrip(os.sep)
        target = os.path.join(self.root, safe_rel)

        if not os.path.exists(target):
            raise FileNotFoundError(f"File not found in sandbox: {rel_path}")

        with open(target, "r", encoding="utf-8") as f:
            return f.read()

    def list_files(self) -> List[str]:
        """Returns all relative file paths inside the sandbox."""
        files = []
        for dirpath, _, filenames in os.walk(self.root):
            for f in filenames:
                full = os.path.join(dirpath, f)
                rel = os.path.relpath(full, self.root)
                files.append(rel)
        return sorted(files)

    def load_files(self, file_map: Dict[str, str]) -> None:
        """Populates the sandbox with an initial mapping of {rel_path: content}."""
        for path, content in file_map.items():
            self.write_file(path, content)

    def run_command(
        self,
        command: List[str],
        timeout_seconds: float = 15.0,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Runs a command strictly inside the sandbox directory."""
        import time

        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        # Ensure Python can import from current directory
        env["PYTHONPATH"] = self.root + (f":{env.get('PYTHONPATH', '')}" if "PYTHONPATH" in env else "")

        start_time = time.time()
        try:
            proc = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            duration = time.time() - start_time
            return ExecutionResult(
                command=" ".join(command),
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                timed_out=False,
                duration_seconds=round(duration, 3),
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return ExecutionResult(
                command=" ".join(command),
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=(e.stderr or "") + f"\n[Command timed out after {timeout_seconds}s]",
                timed_out=True,
                duration_seconds=round(duration, 3),
            )
        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                command=" ".join(command),
                exit_code=-2,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                timed_out=False,
                duration_seconds=round(duration, 3),
            )

    def cleanup(self) -> None:
        """Removes the temporary sandbox directory."""
        if not self._is_cleaned and os.path.exists(self.root):
            shutil.rmtree(self.root, ignore_errors=True)
            self._is_cleaned = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
