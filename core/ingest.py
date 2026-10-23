"""Repository Ingestor & 1M-Context Packer (BeamArena 2.0).

Scans local codebases or public Git repositories, extracts structural AST outlines,
filters noise and credentials, computes architectural health metrics,
and packs entire projects into Beam's 1-million-token context window with zero chunking loss.
"""

import ast
from dataclasses import dataclass, field
import fnmatch
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Set, Tuple

# Ignore patterns by default
DEFAULT_IGNORES: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".coverage",
    "dist",
    "build",
    "target",
    ".DS_Store",
    ".idea",
    ".vscode",
}

CREDENTIAL_PATTERNS: List[str] = [
    ".env*",
    "*.pem",
    "*.key",
    "*.pkcs12",
    "*.pfx",
    "*.p12",
    "id_rsa*",
    "id_ed25519*",
    "*token*",
    "*secret*",
    "credentials.json",
    "client_secret*.json",
]

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".pyc", ".pyd", ".pyo", ".so", ".dylib", ".dll",
    ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".bin", ".exe", ".wasm", ".db", ".sqlite", ".sqlite3"
}


@dataclass
class SymbolInfo:
    kind: str  # "class" or "function"
    name: str
    line: int
    docstring: Optional[str] = None


@dataclass
class FileEntry:
    rel_path: str
    content: str
    size_bytes: int
    symbols: List[SymbolInfo] = field(default_factory=list)


@dataclass
class ArchitecturalHealth:
    total_files: int
    total_lines: int
    total_symbols: int
    docstring_coverage_pct: float
    test_files_count: int
    test_density_pct: float
    token_consumption_pct: float
    health_rating: str


@dataclass
class PackedRepo:
    root_dir: str
    files: Dict[str, FileEntry]
    file_tree: str
    total_bytes: int
    estimated_tokens: int

    def render_prompt_context(self, max_token_budget: int = 800000) -> str:
        """Formats the packed repo into a structured XML-style prompt block."""
        lines = [
            f"<repository root='{os.path.basename(self.root_dir)}'>",
            "<file_tree>",
            self.file_tree,
            "</file_tree>",
            "<source_files>"
        ]

        current_tokens = len(self.file_tree) // 4
        for path, entry in sorted(self.files.items()):
            file_block = [
                f"<file path='{path}'>",
                entry.content,
                "</file>"
            ]
            block_str = "\n".join(file_block)
            block_tokens = len(block_str) // 4

            if current_tokens + block_tokens > max_token_budget:
                remaining = len(self.files) - len([l for l in lines if l.startswith("<file path=")])
                lines.append(f"<!-- Truncated ~{remaining} files due to budget -->")
                break

            lines.append(block_str)
            current_tokens += block_tokens

        lines.append("</source_files>")
        lines.append("</repository>")
        return "\n".join(lines)

    def render_symbol_index(self, max_entries: int = 100) -> str:
        """Formats discovered classes and functions into a structured AST catalog."""
        lines = []
        count = 0
        for path, entry in sorted(self.files.items()):
            if not entry.symbols:
                continue
            lines.append(f"  • {path}:")
            for s in entry.symbols:
                doc = f" — {s.docstring.splitlines()[0]}" if s.docstring else ""
                lines.append(f"      [{s.kind}] {s.name} (L{s.line}){doc}")
                count += 1
                if count >= max_entries:
                    lines.append("      ... [Additional symbols indexed in full source]")
                    return "\n".join(lines)
        return "\n".join(lines) if lines else "  (No top-level AST symbols discovered)"

    def calculate_health(self) -> ArchitecturalHealth:
        """Computes AIOS-style architectural health and density metrics."""
        total_files = len(self.files)
        total_lines = sum(len(f.content.splitlines()) for f in self.files.values())
        all_symbols = [s for f in self.files.values() for s in f.symbols]
        total_symbols = len(all_symbols)

        documented = sum(1 for s in all_symbols if s.docstring)
        doc_pct = round((documented / total_symbols * 100.0), 1) if total_symbols > 0 else 0.0

        test_files = sum(1 for p in self.files.keys() if "test" in p.lower())
        test_density = round((test_files / total_files * 100.0), 1) if total_files > 0 else 0.0
        token_pct = round((self.estimated_tokens / 10485.76), 2)

        # Heuristic health rating
        if test_density >= 20.0 and doc_pct >= 40.0:
            rating = "A (High Modularity & Test Coverage)"
        elif test_density >= 10.0:
            rating = "B (Standard Engineering Hygiene)"
        else:
            rating = "C (Needs Additional Test Assertions)"

        return ArchitecturalHealth(
            total_files=total_files,
            total_lines=total_lines,
            total_symbols=total_symbols,
            docstring_coverage_pct=doc_pct,
            test_files_count=test_files,
            test_density_pct=test_density,
            token_consumption_pct=token_pct,
            health_rating=rating,
        )

    def render_agent_prompt(
        self,
        task_description: str,
        test_command: str,
        max_token_budget: int = 800000,
    ) -> str:
        """Constructs an AST-augmented prompt for Beam's autonomous agent loop."""
        symbol_index = self.render_symbol_index(max_entries=60)
        source_blocks = []
        current_tokens = (len(self.file_tree) + len(symbol_index)) // 4

        for path, entry in sorted(self.files.items()):
            block = f"<file path='{path}'>\n{entry.content}\n</file>"
            block_tokens = len(block) // 4
            if current_tokens + block_tokens > max_token_budget:
                source_blocks.append("<!-- Remaining files truncated due to token budget -->")
                break
            source_blocks.append(block)
            current_tokens += block_tokens

        prompt = (
            f"TASK DESCRIPTION:\n{task_description}\n\n"
            f"VERIFICATION COMMAND TO PASS:\n{test_command}\n\n"
            f"<codebase_architecture root='{os.path.basename(self.root_dir)}'>\n"
            f"<file_tree>\n{self.file_tree}\n</file_tree>\n\n"
            f"<ast_symbol_index>\n{symbol_index}\n</ast_symbol_index>\n"
            f"</codebase_architecture>\n\n"
            f"<source_files>\n" + "\n\n".join(source_blocks) + "\n</source_files>\n\n"
            f"DIRECTIONS:\n"
            f"1. Reason through the codebase architecture and identified symbols.\n"
            f"2. Pinpoint the root cause of the bug.\n"
            f"3. Output modified files inside <edit_file path='...'>...</edit_file> blocks.\n"
            f"4. Verify your solution with <run_command>{test_command}</run_command>."
        )
        return prompt


class RepoIngestor:
    def __init__(self, ignores: Optional[Set[str]] = None):
        self.ignores = ignores or DEFAULT_IGNORES

    def is_binary(self, filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in BINARY_EXTENSIONS

    def is_credential_or_secret(self, filename: str) -> bool:
        lower = filename.lower()
        return any(fnmatch.fnmatch(lower, pat) for pat in CREDENTIAL_PATTERNS)

    def parse_python_symbols(self, content: str) -> List[SymbolInfo]:
        """Extracts class and function definitions using standard ast module."""
        symbols = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(SymbolInfo(
                        kind="function",
                        name=node.name,
                        line=node.lineno,
                        docstring=ast.get_docstring(node)
                    ))
                elif isinstance(node, ast.ClassDef):
                    symbols.append(SymbolInfo(
                        kind="class",
                        name=node.name,
                        line=node.lineno,
                        docstring=ast.get_docstring(node)
                    ))
        except Exception:
            pass
        return symbols

    def ingest_directory(self, root_dir: str, max_file_size_kb: int = 500) -> PackedRepo:
        """Recursively scans root_dir and packs all valid text source files."""
        root_dir = os.path.abspath(root_dir)
        files: Dict[str, FileEntry] = {}
        tree_lines: List[str] = []
        total_bytes = 0

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Prune ignored directories in place
            dirnames[:] = [d for d in dirnames if d not in self.ignores and not d.startswith(".")]

            rel_dir = os.path.relpath(dirpath, root_dir)
            indent = "  " * (0 if rel_dir == "." else rel_dir.count(os.sep) + 1)
            dir_label = os.path.basename(dirpath) if rel_dir != "." else "."
            tree_lines.append(f"{indent}{dir_label}/")

            file_indent = indent + "  "
            for fname in sorted(filenames):
                if fname in self.ignores or fname.startswith("."):
                    continue
                if self.is_binary(fname):
                    continue
                if self.is_credential_or_secret(fname):
                    continue

                full_path = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(full_path)
                    if size > max_file_size_kb * 1024:
                        continue

                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()

                    rel_path = os.path.relpath(full_path, root_dir)
                    symbols = []
                    if fname.endswith(".py"):
                        symbols = self.parse_python_symbols(content)

                    files[rel_path] = FileEntry(
                        rel_path=rel_path,
                        content=content,
                        size_bytes=size,
                        symbols=symbols
                    )
                    total_bytes += size
                    tree_lines.append(f"{file_indent}{fname} ({size}B)")
                except Exception:
                    continue

        file_tree_str = "\n".join(tree_lines)
        estimated_tokens = (total_bytes + len(file_tree_str)) // 4

        return PackedRepo(
            root_dir=root_dir,
            files=files,
            file_tree=file_tree_str,
            total_bytes=total_bytes,
            estimated_tokens=estimated_tokens
        )

    def ingest_git_repo(self, repo_url: str, timeout_sec: float = 30.0) -> Tuple[PackedRepo, str]:
        """Safely clones a public Git repository into a temporary workspace and ingests it."""
        clean_url = repo_url.strip()

        # Strict security validation on Git URL
        allowed_prefixes = (
            "https://github.com/",
            "https://huggingface.co/",
            "https://gitlab.com/",
        )
        if not clean_url.startswith(allowed_prefixes):
            raise ValueError(
                f"Repository URL '{clean_url}' is not permitted. Only public HTTPS repositories from "
                "GitHub, Hugging Face, or GitLab are supported."
            )

        # Disallow shell metacharacters or flags
        if not re.match(r"^https://[a-zA-Z0-9\.\-_/]+$", clean_url):
            raise ValueError("Invalid characters detected in repository URL.")

        temp_dir = tempfile.mkdtemp(prefix="beam_git_ingest_")

        try:
            cmd = ["git", "clone", "--depth", "1", "--single-branch", clean_url, temp_dir]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            if proc.returncode != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError(f"Git clone failed: {proc.stderr.strip()}")

            packed = self.ingest_directory(temp_dir)
            return packed, temp_dir
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
