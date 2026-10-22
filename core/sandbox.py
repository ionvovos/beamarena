"""Sandbox Execution Engine.

Provides an isolated environment for writing files, running tests,
and capturing execution tracebacks safely without corrupting the parent system
or leaking host credentials.
"""

from dataclasses import dataclass
import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Union


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
        self.root = os.path.realpath(self.root)
        self._is_cleaned = False

    def _resolve_safe_path(self, rel_path: str) -> str:
        """Resolves rel_path against sandbox root and strictly verifies containment."""
        # Normalize and remove leading slashes/drives
        safe_rel = os.path.normpath(rel_path).lstrip(os.sep)
        target = os.path.abspath(os.path.join(self.root, safe_rel))
        real_root = os.path.realpath(self.root)
        real_target = os.path.realpath(target)

        # If file doesn't exist yet, check its real parent directory
        if not os.path.exists(real_target):
            parent = os.path.realpath(os.path.dirname(target))
            try:
                if os.path.commonpath([parent, real_root]) != real_root:
                    raise ValueError(f"Path traversal attempted: {rel_path}")
            except ValueError:
                raise ValueError(f"Path traversal attempted: {rel_path}")
        else:
            try:
                if os.path.commonpath([real_target, real_root]) != real_root:
                    raise ValueError(f"Path traversal attempted: {rel_path}")
            except ValueError:
                raise ValueError(f"Path traversal attempted: {rel_path}")

        return target

    def write_file(self, rel_path: str, content: str) -> str:
        """Writes content to a file inside the sandbox, creating parent directories."""
        target = self._resolve_safe_path(rel_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def read_file(self, rel_path: str) -> str:
        """Reads content from a file inside the sandbox."""
        target = self._resolve_safe_path(rel_path)
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

    def _sanitize_env(self, custom_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Creates an isolated subprocess environment stripped of secrets and tokens."""
        # Whitelist safe standard environment variables
        safe_keys = {
            "PATH",
            "SYSTEMROOT",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "PYTHONHASHSEED",
            "TERM",
            "VIRTUAL_ENV",
        }
        sanitized: Dict[str, str] = {}
        for k, v in os.environ.items():
            k_upper = k.upper()
            # Explicitly deny secrets, keys, credentials, tokens
            if any(term in k_upper for term in ["KEY", "TOKEN", "SECRET", "PASS", "CRED", "AUTH"]):
                continue
            if k in safe_keys:
                sanitized[k] = v

        # Contain user home and temp directories inside sandbox
        sanitized["HOME"] = self.root
        sanitized["TMPDIR"] = self.root
        sanitized["TEMP"] = self.root
        sanitized["TMP"] = self.root
        sanitized["PYTHONPATH"] = self.root
        sanitized["PYTHONDONTWRITEBYTECODE"] = "1"

        # Inherit current python venv path if active
        import sys
        venv_bin = os.path.dirname(os.path.abspath(sys.executable))
        prefix_bin = os.path.join(sys.prefix, "bin")
        extra_bins = [b for b in [venv_bin, prefix_bin] if os.path.exists(b)]

        if "PATH" in sanitized:
            paths = sanitized["PATH"].split(os.pathsep)
            for b in reversed(extra_bins):
                if b not in paths:
                    paths.insert(0, b)
            sanitized["PATH"] = os.pathsep.join(paths)
        else:
            sanitized["PATH"] = os.pathsep.join(extra_bins + ["/usr/local/bin", "/usr/bin", "/bin"])

        if custom_vars:
            for k, v in custom_vars.items():
                k_upper = k.upper()
                if not any(term in k_upper for term in ["KEY", "TOKEN", "SECRET", "PASS", "CRED", "AUTH"]):
                    sanitized[k] = v

        return sanitized

    def run_command(
        self,
        command: Union[str, List[str]],
        timeout_seconds: float = 15.0,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Runs a command strictly inside the sandbox directory with scrubbed environment."""
        import time
        import shlex

        if isinstance(command, str):
            try:
                cmd_list = shlex.split(command)
            except ValueError:
                cmd_list = command.split()
            cmd_str = command
        else:
            cmd_list = list(command)
            cmd_str = " ".join(command)

        env = self._sanitize_env(env_vars)
        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd_list,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            duration = time.time() - start_time
            return ExecutionResult(
                command=cmd_str,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                timed_out=False,
                duration_seconds=round(duration, 3),
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return ExecutionResult(
                command=cmd_str,
                exit_code=-1,
                stdout=e.stdout if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", "replace") if e.stdout else ""),
                stderr=((e.stderr if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", "replace") if e.stderr else ""))
                        + f"\n[Command timed out after {timeout_seconds}s]"),
                timed_out=True,
                duration_seconds=round(duration, 3),
            )
        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                command=cmd_str,
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
