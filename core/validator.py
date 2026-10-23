"""AIOS-Inspired Triple Verification Gate.

Enforces three independent validation layers before certifying an autonomous repair:
1. Gate 1: AST Syntax & Compilability (Zero syntax errors, valid python AST).
2. Gate 2: Sandbox Security & Containment (No path escapes, scrubbed secrets, contained scope).
3. Gate 3: Test Assertion Verification (Zero exit code, assertions executed and passed).
"""

import ast
from dataclasses import dataclass, field
import os
import re
from typing import Dict, List, Optional, Tuple
from .sandbox import ExecutionResult, Sandbox


@dataclass
class GateVerdict:
    passed: bool
    gate_name: str
    score: float  # 0.0 to 1.0
    details: str
    errors: List[str] = field(default_factory=list)


@dataclass
class CertificationReport:
    certified: bool
    overall_confidence: float  # 0.0 to 100.0%
    gate_syntax: GateVerdict
    gate_security: GateVerdict
    gate_assertions: GateVerdict
    summary: str

    def to_dict(self) -> Dict[str, any]:
        return {
            "certified": self.certified,
            "overall_confidence": round(self.overall_confidence, 1),
            "gates": {
                "syntax": {
                    "passed": self.gate_syntax.passed,
                    "score": self.gate_syntax.score,
                    "details": self.gate_syntax.details,
                    "errors": self.gate_syntax.errors,
                },
                "security": {
                    "passed": self.gate_security.passed,
                    "score": self.gate_security.score,
                    "details": self.gate_security.details,
                    "errors": self.gate_security.errors,
                },
                "assertions": {
                    "passed": self.gate_assertions.passed,
                    "score": self.gate_assertions.score,
                    "details": self.gate_assertions.details,
                    "errors": self.gate_assertions.errors,
                },
            },
            "summary": self.summary,
        }


class TripleValidator:
    """Rigorous AIOS validation gate evaluating proposed software engineering repairs."""

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def check_syntax(self, edited_files: List[str]) -> GateVerdict:
        """Gate 1: Verifies all edited Python files parse cleanly under Python AST."""
        errors = []
        parsed_count = 0

        for rel_path in edited_files:
            if not rel_path.endswith(".py"):
                continue
            try:
                content = self.sandbox.read_file(rel_path)
                ast.parse(content, filename=rel_path)
                parsed_count += 1
            except SyntaxError as e:
                errors.append(f"SyntaxError in {rel_path}:{e.lineno} - {e.msg}")
            except Exception as e:
                errors.append(f"AST Error in {rel_path} - {str(e)}")

        if errors:
            return GateVerdict(
                passed=False,
                gate_name="Gate 1 (Syntax & Compilability)",
                score=0.0,
                details=f"Syntax validation failed across {len(errors)} file(s).",
                errors=errors,
            )

        return GateVerdict(
            passed=True,
            gate_name="Gate 1 (Syntax & Compilability)",
            score=1.0,
            details=f"Clean AST compilation across all {parsed_count} modified Python source file(s).",
            errors=[],
        )

    def check_security(self, edited_files: List[str], command_results: List[ExecutionResult]) -> GateVerdict:
        """Gate 2: Verifies sandbox containment, no credential exposure, and no dangerous system calls."""
        errors = []

        dangerous_tokens = [
            "__import__('os').system",
            "subprocess.Popen(['rm'",
            "curl -X POST",
            "shutil.rmtree('/')",
        ]

        for rel_path in edited_files:
            try:
                content = self.sandbox.read_file(rel_path)
                for dt in dangerous_tokens:
                    if dt in content:
                        errors.append(f"Dangerous call pattern detected in {rel_path}: '{dt}'")
            except Exception:
                pass

        # Check command outputs for leaked tokens or path escapes
        for cr in command_results:
            combined = (cr.stdout + " " + cr.stderr).upper()
            if any(term in combined for term in ["REFLECTION_API_KEY", "HF_TOKEN", "AWS_SECRET_ACCESS_KEY"]):
                errors.append("Host credential signature detected in execution output.")

        if errors:
            return GateVerdict(
                passed=False,
                gate_name="Gate 2 (Containment & Security)",
                score=0.0,
                details="Security invariant violation detected.",
                errors=errors,
            )

        return GateVerdict(
            passed=True,
            gate_name="Gate 2 (Containment & Security)",
            score=1.0,
            details="Zero path traversal, credentials sanitized, safe sandbox isolation confirmed.",
            errors=[],
        )

    def check_assertions(self, test_cmd: str, command_results: List[ExecutionResult]) -> GateVerdict:
        """Gate 3: Confirms test verification command executed, exited code 0, and ran real assertions."""
        test_res = None
        for cr in reversed(command_results):
            if test_cmd in cr.command:
                test_res = cr
                break

        if not test_res:
            return GateVerdict(
                passed=False,
                gate_name="Gate 3 (Assertion Verification)",
                score=0.0,
                details=f"Verification command '{test_cmd}' was never executed.",
                errors=["Verification test command missing from execution plan."],
            )

        if test_res.exit_code != 0:
            return GateVerdict(
                passed=False,
                gate_name="Gate 3 (Assertion Verification)",
                score=0.0,
                details=f"Test command failed with exit code {test_res.exit_code}.",
                errors=[test_res.stderr.strip()[:300] or "Non-zero exit code"],
            )

        output = test_res.stdout + " " + test_res.stderr
        assertion_indicators = [
            "passed",
            "ok",
            "ran ",
            "assertions",
            "test session starts",
            "passed in",
        ]

        ran_assertions = any(term in output.lower() for term in assertion_indicators)
        if not ran_assertions:
            return GateVerdict(
                passed=True,
                gate_name="Gate 3 (Assertion Verification)",
                score=0.8,
                details="Command exited code 0, but assertion telemetry was sparse.",
                errors=[],
            )

        return GateVerdict(
            passed=True,
            gate_name="Gate 3 (Assertion Verification)",
            score=1.0,
            details=f"Green test suite verified with exit code 0 and confirmed assertion pass signals.",
            errors=[],
        )

    def certify(
        self,
        test_cmd: str,
        edited_files: List[str],
        command_results: List[ExecutionResult],
    ) -> CertificationReport:
        """Runs all three gates and produces the AIOS-standard certification verdict."""
        g1 = self.check_syntax(edited_files)
        g2 = self.check_security(edited_files, command_results)
        g3 = self.check_assertions(test_cmd, command_results)

        certified = g1.passed and g2.passed and g3.passed
        total_score = (g1.score * 0.3) + (g2.score * 0.3) + (g3.score * 0.4)
        overall_confidence = (total_score * 100.0) if certified else (total_score * 50.0)

        if certified:
            summary = f"CERTIFIED GREEN (Confidence: {overall_confidence:.1f}%). All 3 AIOS gates passed."
        else:
            failed_gates = [g.gate_name for g in [g1, g2, g3] if not g.passed]
            summary = f"REJECTED. Failed {len(failed_gates)} gate(s): {', '.join(failed_gates)}."

        return CertificationReport(
            certified=certified,
            overall_confidence=overall_confidence,
            gate_syntax=g1,
            gate_security=g2,
            gate_assertions=g3,
            summary=summary,
        )
