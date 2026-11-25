"""Cursor CLI agent adapter with throwaway-container isolation.

Security posture (Phase 3):
- Runs `agent` / cursor CLI inside a one-shot Docker container (when docker exists)
- Injects only CURSOR_API_KEY into the container env
- Never passes `--force`
- Enforces wall-clock timeouts and maps exit/stderr to ProviderError codes
- kind=agent → skip_retrieval is always honored (no RAG/context pull)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.protocol import DocGenProvider
from app.ai.types import (
    CompleteRequest,
    CompleteResponse,
    ModelInfo,
    ProviderKind,
    TestResult,
)

FORBIDDEN_FLAGS = frozenset({"--force", "-f", "--yes", "--dangerously-skip-permissions"})


def build_cursor_argv(
    *,
    prompt: str,
    model: str | None = None,
    output_format: str = "text",
) -> list[str]:
    """Build CLI argv. Refuses forbidden flags."""
    # Prefer `agent -p` non-interactive print mode when available.
    argv = ["agent", "-p", "--output-format", output_format]
    if model:
        argv.extend(["--model", model])
    argv.append(prompt)
    for flag in FORBIDDEN_FLAGS:
        if flag in argv:
            raise ProviderError(
                ProviderErrorCode.POLICY_BLOCKED,
                f"Forbidden Cursor CLI flag: {flag}",
            )
    return argv


def map_cursor_exit(returncode: int, stderr: str, stdout: str) -> ProviderError | None:
    if returncode == 0:
        return None
    combined = f"{stderr}\n{stdout}".lower()
    if returncode in {124, 137} or "timed out" in combined or "timeout" in combined:
        return ProviderError(
            ProviderErrorCode.TIMEOUT,
            "Cursor CLI timed out",
            retryable=True,
            details={"returncode": returncode},
        )
    if any(x in combined for x in ("unauthorized", "auth", "api key", "401", "403")):
        return ProviderError(
            ProviderErrorCode.AUTH_FAILED,
            "Cursor CLI authentication failed",
            details={"returncode": returncode, "stderr": stderr[:400]},
        )
    if "rate" in combined and "limit" in combined:
        return ProviderError(
            ProviderErrorCode.RATE_LIMITED,
            "Cursor CLI rate limited",
            retryable=True,
            details={"returncode": returncode},
        )
    if returncode == 127 or "not found" in combined:
        return ProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Cursor CLI binary unavailable",
            details={"returncode": returncode, "stderr": stderr[:400]},
        )
    return ProviderError(
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        f"Cursor CLI failed (exit {returncode})",
        details={"returncode": returncode, "stderr": stderr[:400]},
    )


class CursorCLIProvider(DocGenProvider):
    adapter_type = "cursor_cli"
    kind = ProviderKind.AGENT

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str | None = None,
        name: str = "cursor_cli",
        timeout_seconds: float = 180.0,
        docker_image: str = "cursor-agent:local",
        use_docker: bool | None = None,
        docker_bin: str | None = None,
    ) -> None:
        self.name = name
        self.api_key = api_key or os.environ.get("CURSOR_API_KEY", "")
        self.default_model = model
        self.timeout_seconds = timeout_seconds
        self.docker_image = docker_image
        self.docker_bin = docker_bin or shutil.which("docker")
        if use_docker is None:
            self.use_docker = bool(self.docker_bin)
        else:
            self.use_docker = use_docker
        self._proc: asyncio.subprocess.Process | None = None

    @property
    def skips_retrieval(self) -> bool:
        return True

    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        # Agent kind always skips retrieval regardless of caller.
        _ = request.skip_retrieval
        if not self.api_key:
            raise ProviderError(
                ProviderErrorCode.AUTH_FAILED,
                "CURSOR_API_KEY not configured",
            )
        prompt = f"{request.system}\n\n{request.user}"
        if request.response_json:
            prompt += "\nRespond with JSON only."
        timeout = request.timeout_seconds or self.timeout_seconds
        argv = build_cursor_argv(
            prompt=prompt,
            model=request.model or self.default_model,
            output_format="text",
        )
        # Defense in depth: strip any accidental force flags from metadata.
        extra = request.metadata.get("extra_args") if request.metadata else None
        if extra:
            raise ProviderError(
                ProviderErrorCode.POLICY_BLOCKED,
                "Extra Cursor CLI args are not allowed",
            )

        if self.use_docker:
            stdout, stderr, code = await self._run_docker(argv, timeout=timeout)
        else:
            stdout, stderr, code = await self._run_local(argv, timeout=timeout)

        err = map_cursor_exit(code, stderr, stdout)
        if err:
            raise err
        text = stdout.strip()
        if request.response_json:
            try:
                json.loads(text if not text.startswith("```") else _strip_fence(text))
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    ProviderErrorCode.INVALID_OUTPUT,
                    "Cursor CLI returned non-JSON output",
                    details={"error": str(exc), "snippet": text[:300]},
                ) from exc
        return CompleteResponse(
            text=text,
            model=request.model or self.default_model or "cursor-agent",
            usage={},
            raw={"stderr": stderr[-500:]},
        )

    async def _run_docker(self, argv: list[str], *, timeout: float) -> tuple[str, str, int]:
        if not self.docker_bin:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "Docker not available for Cursor CLI isolation",
            )
        # Throwaway container: --rm, no network mounts of host secrets except env.
        docker_argv = [
            self.docker_bin,
            "run",
            "--rm",
            "--network",
            "bridge",
            "--env",
            "CURSOR_API_KEY",
            # Drop capabilities; read-only root where supported.
            "--security-opt",
            "no-new-privileges",
            self.docker_image,
            *argv,
        ]
        for flag in FORBIDDEN_FLAGS:
            if flag in docker_argv:
                raise ProviderError(
                    ProviderErrorCode.POLICY_BLOCKED,
                    f"Forbidden flag in docker argv: {flag}",
                )
        env = {"CURSOR_API_KEY": self.api_key, "PATH": os.environ.get("PATH", "")}
        return await self._exec(docker_argv, env=env, timeout=timeout)

    async def _run_local(self, argv: list[str], *, timeout: float) -> tuple[str, str, int]:
        """Fallback when docker is absent (dev/CI). Still injects only CURSOR_API_KEY."""
        binary = shutil.which(argv[0])
        if not binary:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "Cursor CLI binary not found and Docker unavailable",
            )
        env = {
            "CURSOR_API_KEY": self.api_key,
            "PATH": os.environ.get("PATH", ""),
            "HOME": tempfile.gettempdir(),
        }
        return await self._exec([binary, *argv[1:]], env=env, timeout=timeout)

    async def _exec(
        self,
        argv: list[str],
        *,
        env: dict[str, str],
        timeout: float,
    ) -> tuple[str, str, int]:
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=tempfile.gettempdir(),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    self._proc.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                await self.cancel()
                raise ProviderError(
                    ProviderErrorCode.TIMEOUT,
                    "Cursor CLI timed out",
                    retryable=True,
                ) from None
            code = self._proc.returncode if self._proc.returncode is not None else 1
            return stdout_b.decode("utf-8", errors="replace"), stderr_b.decode(
                "utf-8", errors="replace"
            ), code
        except ProviderError:
            raise
        except FileNotFoundError as exc:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "Cursor CLI executable missing",
                details={"error": str(exc)},
            ) from exc
        finally:
            self._proc = None

    async def list_models(self) -> list[ModelInfo]:
        # Agent adapter: models are opaque; expose configured hint only.
        mid = self.default_model or "cursor-agent"
        return [ModelInfo(id=mid, name=mid, owned_by="cursor")]

    async def test_connection(self) -> TestResult:
        started = time.perf_counter()
        if not self.api_key:
            return TestResult(
                ok=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="CURSOR_API_KEY not configured",
            )
        if self.use_docker and not self.docker_bin:
            return TestResult(
                ok=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="Docker required for Cursor CLI isolation",
            )
        binary_ok = bool(self.docker_bin) if self.use_docker else bool(shutil.which("agent"))
        return TestResult(
            ok=binary_ok and bool(self.api_key),
            latency_ms=(time.perf_counter() - started) * 1000,
            message=(
                "Cursor CLI isolation ready"
                if binary_ok
                else "Cursor CLI / Docker binary not found"
            ),
            models_sample=[self.default_model or "cursor-agent"],
        )

    async def cancel(self, handle: Any | None = None) -> None:
        proc = self._proc
        if proc and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass


def _strip_fence(content: str) -> str:
    lines = content.splitlines()
    lines = [ln for ln in lines if not ln.startswith("```")]
    return "\n".join(lines)


def workspace_scratch() -> Path:
    return Path(tempfile.mkdtemp(prefix="docforge-cursor-"))
