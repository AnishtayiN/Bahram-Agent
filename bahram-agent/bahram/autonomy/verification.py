from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


class VerificationType:
    COMMAND = "command"
    FILE_EXISTS = "file_exists"
    CONTENT_CHECK = "content_check"
    TEST_EXECUTION = "test_execution"
    SCHEMA_VALIDATION = "schema_validation"
    CUSTOM = "custom"


@dataclass
class VerificationResult:
    passed: bool
    verification_type: str
    details: str = ""
    duration_ms: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "verification_type": self.verification_type,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "evidence": self.evidence,
        }


class VerificationEngine:
    def __init__(self) -> None:
        self._custom_verifiers: dict[str, Callable] = {}

    def register_verifier(self, name: str, fn: Callable) -> None:
        self._custom_verifiers[name] = fn

    async def verify(
        self,
        result: str,
        criteria: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[VerificationResult]:
        results = []
        for criterion in criteria:
            v_type = criterion.get("type", "")
            params = criterion.get("params", {})
            start = time.time()

            try:
                if v_type == VerificationType.COMMAND:
                    vr = await self._verify_command(params)
                elif v_type == VerificationType.FILE_EXISTS:
                    vr = await self._verify_file_exists(params)
                elif v_type == VerificationType.CONTENT_CHECK:
                    vr = await self._verify_content_check(result, params)
                elif v_type == VerificationType.TEST_EXECUTION:
                    vr = await self._verify_test_execution(params)
                elif v_type == VerificationType.SCHEMA_VALIDATION:
                    vr = await self._verify_schema(result, params)
                elif v_type == VerificationType.CUSTOM:
                    vr = await self._verify_custom(result, params, context)
                else:
                    vr = VerificationResult(
                        passed=False,
                        verification_type=v_type,
                        details=f"Unknown verification type: {v_type}",
                    )
            except Exception as e:
                vr = VerificationResult(
                    passed=False,
                    verification_type=v_type,
                    details=f"Verification error: {e}",
                )

            vr.duration_ms = (time.time() - start) * 1000
            results.append(vr)

        return results

    async def _verify_command(self, params: dict[str, Any]) -> VerificationResult:
        command = params.get("command", "")
        expected_exit = params.get("expected_exit_code", 0)
        timeout = params.get("timeout", 30)

        if not command:
            return VerificationResult(
                passed=False, verification_type=VerificationType.COMMAND,
                details="No command specified",
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            exit_code = proc.returncode or 0

            passed = exit_code == expected_exit
            return VerificationResult(
                passed=passed,
                verification_type=VerificationType.COMMAND,
                details=f"Exit code: {exit_code} (expected {expected_exit})",
                evidence={
                    "exit_code": exit_code,
                    "stdout": stdout.decode()[-2000:],
                    "stderr": stderr.decode()[-1000:],
                },
            )
        except asyncio.TimeoutError:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COMMAND,
                details=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COMMAND,
                details=f"Command failed: {e}",
            )

    async def _verify_file_exists(self, params: dict[str, Any]) -> VerificationResult:
        path = params.get("path", "")
        should_exist = params.get("exists", True)

        if not path:
            return VerificationResult(
                passed=False, verification_type=VerificationType.FILE_EXISTS,
                details="No path specified",
            )

        exists = os.path.exists(path)
        passed = exists == should_exist

        return VerificationResult(
            passed=passed,
            verification_type=VerificationType.FILE_EXISTS,
            details=f"File {'exists' if exists else 'not found'}: {path}",
            evidence={"path": path, "exists": exists},
        )

    async def _verify_content_check(self, result: str, params: dict[str, Any]) -> VerificationResult:
        expected_content = params.get("contains", "")
        not_contains = params.get("not_contains", "")
        min_length = params.get("min_length", 0)
        max_length = params.get("max_length", 0)

        checks_passed = True
        details = []

        if expected_content:
            if expected_content not in result:
                checks_passed = False
                details.append(f"Missing expected content: '{expected_content[:100]}'")
            else:
                details.append("Contains expected content")

        if not_contains:
            if not_contains in result:
                checks_passed = False
                details.append(f"Contains forbidden content: '{not_contains[:100]}'")
            else:
                details.append("Does not contain forbidden content")

        if min_length > 0 and len(result) < min_length:
            checks_passed = False
            details.append(f"Result too short: {len(result)} < {min_length}")

        if max_length > 0 and len(result) > max_length:
            checks_passed = False
            details.append(f"Result too long: {len(result)} > {max_length}")

        return VerificationResult(
            passed=checks_passed,
            verification_type=VerificationType.CONTENT_CHECK,
            details="; ".join(details) if details else "No content checks specified",
            evidence={"result_length": len(result), "preview": result[:500]},
        )

    async def _verify_test_execution(self, params: dict[str, Any]) -> VerificationResult:
        test_command = params.get("command", "python -m pytest --tb=short -q")
        timeout = params.get("timeout", 120)

        try:
            proc = await asyncio.create_subprocess_shell(
                test_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            exit_code = proc.returncode or 0
            output = stdout.decode()

            passed = exit_code == 0
            return VerificationResult(
                passed=passed,
                verification_type=VerificationType.TEST_EXECUTION,
                details=f"Tests {'passed' if passed else 'failed'} (exit {exit_code})",
                evidence={
                    "exit_code": exit_code,
                    "output": output[-3000:],
                    "stderr": stderr.decode()[-1000:],
                },
            )
        except asyncio.TimeoutError:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.TEST_EXECUTION,
                details=f"Tests timed out after {timeout}s",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.TEST_EXECUTION,
                details=f"Test execution error: {e}",
            )

    async def _verify_schema(self, result: str, params: dict[str, Any]) -> VerificationResult:
        schema = params.get("schema", {})
        try:
            data = json.loads(result)
            required_fields = schema.get("required", [])
            missing = [f for f in required_fields if f not in data]
            if missing:
                return VerificationResult(
                    passed=False,
                    verification_type=VerificationType.SCHEMA_VALIDATION,
                    details=f"Missing required fields: {missing}",
                    evidence={"data_keys": list(data.keys()) if isinstance(data, dict) else []},
                )
            return VerificationResult(
                passed=True,
                verification_type=VerificationType.SCHEMA_VALIDATION,
                details="Schema validation passed",
            )
        except json.JSONDecodeError:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.SCHEMA_VALIDATION,
                details="Result is not valid JSON",
            )

    async def _verify_custom(
        self, result: str, params: dict[str, Any], context: dict[str, Any] | None
    ) -> VerificationResult:
        verifier_name = params.get("name", "")
        verifier_fn = self._custom_verifiers.get(verifier_name)
        if not verifier_fn:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.CUSTOM,
                details=f"Unknown custom verifier: {verifier_name}",
            )

        try:
            if asyncio.iscoroutinefunction(verifier_fn):
                passed = await verifier_fn(result, params, context)
            else:
                passed = verifier_fn(result, params, context)
            return VerificationResult(
                passed=bool(passed),
                verification_type=VerificationType.CUSTOM,
                details=f"Custom verifier '{verifier_name}' {'passed' if passed else 'failed'}",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.CUSTOM,
                details=f"Custom verifier error: {e}",
            )
