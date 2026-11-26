"""Shared helpers for HTTP-based forge adapters."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import httpx

from app.providers.base import CloneResult


async def git_shallow_clone(
    *,
    clone_url: str,
    ref: str,
    sha: str,
    dest: Path,
    depth: int,
    provider: str,
    full_name: str,
) -> CloneResult:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        "--depth",
        str(depth),
        "--branch",
        ref,
        clone_url,
        str(dest),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _out, err = await proc.communicate()
    if proc.returncode != 0:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            str(depth),
            clone_url,
            str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {err.decode()}")
        checkout = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(dest),
            "checkout",
            sha,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await checkout.communicate()
        if checkout.returncode != 0:
            raise RuntimeError(f"git checkout {sha} failed")
    return CloneResult(
        path=dest,
        commit_sha=sha,
        ref=ref,
        provider=provider,
        full_name=full_name,
    )


async def ensure_client(
    client: httpx.AsyncClient | None,
    *,
    headers: dict[str, str],
    owns: bool,
) -> tuple[httpx.AsyncClient, bool]:
    if client is None:
        return httpx.AsyncClient(timeout=60.0, headers=headers), True
    return client, owns
