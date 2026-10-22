"""Repository Ingestor & 1M-Context Packer.

Scans local codebases, extracts structural AST outlines, filters noise,
and packs entire projects into Beam's 1-million-token context window.
"""

import ast
from dataclasses import dataclass, field
import os
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


class RepoIngestor:
    def __init__(self, ignores: Optional[Set[str]] = None):
        self.ignores = ignores or DEFAULT_IGNORES

    def is_binary(self, filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in BINARY_EXTENSIONS

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
            # Fall back safely if AST parsing encounters syntax errors
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
        # Approximate 1 token ~= 4 chars of code
        estimated_tokens = (total_bytes + len(file_tree_str)) // 4

        return PackedRepo(
            root_dir=root_dir,
            files=files,
            file_tree=file_tree_str,
            total_bytes=total_bytes,
            estimated_tokens=estimated_tokens
        )
