"""Where a model being edited lives: the backend interface of the model editor server.

`ModelSource` is "a model being edited on a branch". The editor server (`web_editor.py`) reaches
git and the filesystem only through it; nothing else in the server touches them directly.

`LocalCloneSource` is the one implementation today: a git clone on the local disk, with the
model in a directory of it. The `editor-git-backends` task adds GitHub, GitLab and
local-checkout sources by implementing this protocol.

Stdlib only and no 3.14-only syntax: it runs on the Python 3 shipped in the images.
"""

import contextlib
import io
import os
import re
import subprocess
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Protocol, runtime_checkable

import submit

SUFFIX = ".c4"
SKIPPED_RE = re.compile(r"^skipped \(not committed\): (?P<path>.+)$", re.MULTILINE)

Runner = Callable[..., subprocess.CompletedProcess]
SubmitFn = Callable[..., object]


class SourceError(Exception):
    """A refusal that maps to an HTTP status and a message for the caller."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class SubmitResult:
    """What a submit did: the text it printed and the model files it left out."""

    output: str
    skipped: list[str] = field(default_factory=list)


@runtime_checkable
class ModelSource(Protocol):
    """A model being edited on a branch. Paths are POSIX, relative to the model directory."""

    def branch(self) -> str:
        """Name of the branch the edits go to."""
        ...

    def list_files(self) -> list[str]:
        """All `.c4` files of the model."""
        ...

    def read(self, rel: str) -> str: ...

    def write(self, rel: str, text: str) -> None: ...

    def changes(self) -> list[str]:
        """Changed paths under the model (git status --porcelain lines)."""
        ...

    def workdir(self) -> Path:
        """Directory where `likec4` CLI commands run."""
        ...

    def submit(self, message: str) -> SubmitResult:
        """Validate, commit the changed model files, send the branch. Raises SourceError."""
        ...


def resolve_model_file(model_dir: Path, rel: str) -> Path:
    """Map a relative `.c4` path to a file inside model_dir, or raise a 400."""
    if not rel or "\x00" in rel:
        raise SourceError(HTTPStatus.BAD_REQUEST, "path is missing")
    candidate = Path(rel)
    if candidate.is_absolute() or rel.startswith(("/", "\\")) or ".." in candidate.parts:
        raise SourceError(HTTPStatus.BAD_REQUEST, "path must be relative and stay in the model")
    if candidate.suffix != SUFFIX:
        raise SourceError(HTTPStatus.BAD_REQUEST, f"only {SUFFIX} files can be edited")
    root = model_dir.resolve()
    target = (root / candidate).resolve()  # follows symlinks, so an escaping link is caught
    if root != target and root not in target.parents:
        raise SourceError(HTTPStatus.BAD_REQUEST, "path resolves outside the model directory")
    return target


def list_model_files(model_dir: Path) -> list[str]:
    """Relative POSIX paths of the `.c4` files under model_dir that really live inside it."""
    root = model_dir.resolve()
    found = []
    for item in sorted(root.rglob(f"*{SUFFIX}")):
        if item.is_file() and (root in item.resolve().parents):
            found.append(item.relative_to(root).as_posix())
    return found


def write_atomic(target: Path, text: str) -> None:
    """Write next to the target and rename over it, so readers never see half a file."""
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


class LocalCloneSource:
    """A model in a directory of a local git clone, on the clone's checked-out branch."""

    def __init__(
        self,
        repo: Path,
        path: str,
        run: Runner = subprocess.run,
        submit_fn: SubmitFn = submit.submit,
    ) -> None:
        self.repo = repo
        self.path = path
        self.model_dir = repo / path
        self.run = run
        self.submit_fn = submit_fn
        self.lock = threading.Lock()  # submit prints to stdout; one at a time

    def _git(self, *args: str) -> str:
        proc = self.run(
            ["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=False
        )
        return (proc.stdout or "").strip()

    def branch(self) -> str:
        return self._git("branch", "--show-current")

    def list_files(self) -> list[str]:
        return list_model_files(self.model_dir)

    def read(self, rel: str) -> str:
        target = resolve_model_file(self.model_dir, rel)
        if not target.is_file():
            raise SourceError(HTTPStatus.NOT_FOUND, f"{rel} does not exist")
        return target.read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        target = resolve_model_file(self.model_dir, rel)
        if not target.parent.is_dir():
            raise SourceError(HTTPStatus.BAD_REQUEST, "the directory of that file does not exist")
        write_atomic(target, text)

    def changes(self) -> list[str]:
        out = self._git("status", "--porcelain", "--", self.path)
        return [line for line in out.splitlines() if line.strip()]

    def workdir(self) -> Path:
        return self.model_dir

    def submit(self, message: str) -> SubmitResult:
        buffer = io.StringIO()
        with self.lock, contextlib.redirect_stdout(buffer):
            try:
                self.submit_fn("likec4", self.path, self.repo, message)
            except submit.SubmitError as err:
                raise SourceError(HTTPStatus.UNPROCESSABLE_ENTITY, str(err)) from err
        output = buffer.getvalue().strip()
        prefix = self.path.rstrip("/") + "/"
        skipped = []
        for match in SKIPPED_RE.finditer(output):
            found = match.group("path").strip()
            skipped.append(found[len(prefix) :] if found.startswith(prefix) else found)
        return SubmitResult(output=output, skipped=skipped)
