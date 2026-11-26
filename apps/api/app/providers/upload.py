"""Upload provider — extract ZIP/tarball archives into a working tree."""

from __future__ import annotations

import hashlib
import io
import shutil
import tarfile
import zipfile
from pathlib import Path

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef


class UploadProvider(RepoProvider):
    name = "upload"

    def __init__(
        self,
        *,
        archive_bytes: bytes | None = None,
        archive_path: Path | None = None,
        full_name: str = "upload/local",
        default_branch: str = "main",
    ) -> None:
        if archive_bytes is None and archive_path is None:
            raise ValueError("archive_bytes or archive_path is required for upload")
        self.archive_bytes = archive_bytes
        self.archive_path = archive_path
        self._full_name = full_name
        self.default_branch = default_branch

    def _payload(self) -> bytes:
        if self.archive_bytes is not None:
            return self.archive_bytes
        assert self.archive_path is not None
        return self.archive_path.read_bytes()

    def _sha_for(self, ref: str) -> str:
        digest = hashlib.sha1()  # noqa: S324 — content pin, not security
        digest.update(self._payload())
        digest.update(ref.encode())
        return digest.hexdigest()

    @staticmethod
    def _extract(data: bytes, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(dest)
            return
        # tar / tar.gz / tar.bz2
        bio = io.BytesIO(data)
        try:
            with tarfile.open(fileobj=bio, mode="r:*") as tf:
                # Python 3.12+: filter="data" when available
                try:
                    tf.extractall(dest, filter="data")  # type: ignore[call-arg]
                except TypeError:
                    tf.extractall(dest)
            return
        except tarfile.TarError as exc:
            raise ValueError("Unsupported archive; provide ZIP or tar/tarball") from exc

    @staticmethod
    def _unwrap_single_root(dest: Path) -> None:
        children = [p for p in dest.iterdir() if p.name != "__MACOSX"]
        if len(children) == 1 and children[0].is_dir():
            root = children[0]
            for item in root.iterdir():
                target = dest / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(item), str(target))
            shutil.rmtree(root)

    async def authenticate(self) -> None:
        _ = self._payload()  # ensure readable

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        if query and query.lower() not in self._full_name.lower():
            return []
        return [
            RemoteRepo(
                id=self._sha_for("id")[:12],
                full_name=self._full_name,
                clone_url=f"upload://{self._full_name}",
                default_branch=self.default_branch,
                private=True,
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
        return self._sha_for(ref)

    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        _ = depth
        sha = await self.resolve_ref(full_name, ref)
        if dest.exists():
            shutil.rmtree(dest)
        self._extract(self._payload(), dest)
        self._unwrap_single_root(dest)
        return CloneResult(
            path=dest,
            commit_sha=sha,
            ref=ref,
            provider=self.name,
            full_name=full_name or self._full_name,
        )
