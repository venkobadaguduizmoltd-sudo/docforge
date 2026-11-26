"""Generic Git RepoProvider — HTTPS or SSH clone without a forge API."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef
from app.providers.http_forge import git_shallow_clone


def _derive_full_name(url: str) -> str:
    cleaned = url.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.startswith("git@"):
        # git@host:owner/repo
        path = cleaned.split(":", 1)[-1]
        return path
    # https://host/owner/repo
    parts = cleaned.split("://", 1)[-1].split("/", 1)
    return parts[1] if len(parts) > 1 else parts[0]


class GenericGitProvider(RepoProvider):
    name = "generic_git"

    def __init__(
        self,
        *,
        clone_url: str,
        token: str | None = None,
        ssh_key_path: str | None = None,
        default_branch: str = "main",
        full_name: str | None = None,
    ) -> None:
        if not clone_url:
            raise ValueError("clone_url is required for generic_git")
        self.clone_url = clone_url
        self.token = token or ""
        self.ssh_key_path = ssh_key_path
        self.default_branch = default_branch
        self._full_name = full_name or _derive_full_name(clone_url)

    def _auth_url(self) -> str:
        url = self.clone_url
        if self.token and url.startswith("https://"):
            return url.replace("https://", f"https://git:{self.token}@", 1)
        return url

    def _sha_for(self, ref: str) -> str:
        payload = f"generic:{self.clone_url}:{ref}".encode()
        return hashlib.sha1(payload).hexdigest()  # noqa: S324 — pin id only

    async def authenticate(self) -> None:
        if self.clone_url.startswith("git@") and not self.ssh_key_path:
            # SSH without key still allowed if agent/keys exist on host
            return
        if not self.clone_url.startswith(("https://", "http://", "git@", "ssh://")):
            raise ValueError(f"Unsupported clone URL scheme: {self.clone_url}")

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        if query and query.lower() not in self._full_name.lower():
            return []
        return [
            RemoteRepo(
                id=self._sha_for("id")[:12],
                full_name=self._full_name,
                clone_url=self.clone_url,
                default_branch=self.default_branch,
                private=bool(self.token or self.ssh_key_path),
            )
        ]

    async def list_refs(self, full_name: str) -> list[RepoRef]:
        return [
            RepoRef(
                name=self.default_branch,
                sha=self._sha_for(self.default_branch),
                ref_type="branch",
            )
        ]

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        if re.fullmatch(r"[0-9a-f]{40}", ref.lower()):
            return ref.lower()
        # After clone, real SHA is read from git; pre-clone returns deterministic pin
        return self._sha_for(ref)

    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        clone_url = self._auth_url()
        # Use placeholder SHA; replace with actual HEAD after clone
        provisional = await self.resolve_ref(full_name, ref)
        result = await git_shallow_clone(
            clone_url=clone_url,
            ref=ref,
            sha=provisional,
            dest=dest,
            depth=depth,
            provider=self.name,
            full_name=full_name or self._full_name,
        )
        # Read real HEAD SHA
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(dest),
            "rev-parse",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await proc.communicate()
        if proc.returncode == 0:
            sha = out.decode().strip()
            return CloneResult(
                path=result.path,
                commit_sha=sha,
                ref=ref,
                provider=self.name,
                full_name=result.full_name,
            )
        return result
