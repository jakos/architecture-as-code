"""Submit a model change from an editor container: validate, commit, push a model/* branch.

Runs inside the B1 editor containers (PoC), where the clone is checked out on a branch
`model/<user>/<yyyy-mm-dd>-<slug>`. It validates the model with the tool's own validator,
commits only the model directory, pushes the branch to `origin` and PRINTS the
`gh pr create` command. It never runs `gh` and never handles a token: PoC mode.

Stdlib only and no 3.14-only syntax: it also runs on the Python 3 shipped in the images.
"""

import argparse
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

BRANCH_RE = re.compile(r"^model/[a-z0-9][a-z0-9._-]*/\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$")
BRANCH_REF_PREFIX = "refs/heads/model/"
TOOLS = ("likec4",)

Runner = Callable[..., subprocess.CompletedProcess]


class SubmitError(Exception):
    """A refusal with a message meant for the person running `submit`."""


def check_branch(branch: str) -> str:
    """Accept only model/<user>/<yyyy-mm-dd>-<slug>; say why for anything else."""
    if branch == "main":
        raise SubmitError("refusing to submit from 'main': check out a model/* branch")
    if not BRANCH_RE.match(branch):
        raise SubmitError(
            f"branch '{branch}' is not model/<user>/<yyyy-mm-dd>-<slug>; "
            "create one, for example: git switch -c model/ada/2026-10-10-add-notifications"
        )
    return branch


def refspec(branch: str) -> str:
    """The only refspec submit pushes: HEAD to the same-named branch under refs/heads/model/."""
    spec = f"HEAD:refs/heads/{branch}"
    if not spec.split(":", 1)[1].startswith(BRANCH_REF_PREFIX):
        raise SubmitError(f"refusing to push to '{spec}': only {BRANCH_REF_PREFIX}* is allowed")
    return spec


def validator_commands(tool: str, path: str) -> list[list[str]]:
    """Validator invocations for a tool; they run inside the model directory (validator_cwd)."""
    if tool == "likec4":
        return [["likec4", "validate"], ["likec4", "format", "--check"]]
    raise SubmitError(f"unknown tool '{tool}' (expected one of: {', '.join(TOOLS)})")


def validator_cwd(repo: Path, path: str) -> Path:
    """LikeC4 validates the project in its working directory: the model directory."""
    return repo / path


def pr_command(branch: str, title: str) -> str:
    """The command a person (or CI) runs to open the PR. Printed, never executed here."""
    return (
        f"gh pr create --base main --head {shlex.quote(branch)} "
        f"--title {shlex.quote(title)} --fill-verbose"
    )


def _git(run: Runner, repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def _fail(proc: subprocess.CompletedProcess, what: str) -> SubmitError:
    detail = (proc.stdout or "") + (proc.stderr or "")
    return SubmitError(f"{what} failed (exit {proc.returncode}):\n{detail.strip()}")


def submit(tool: str, path: str, repo: Path, message: str, run: Runner = subprocess.run) -> None:
    """Validate, commit the model directory and push the branch; print the PR command."""
    head = _git(run, repo, "rev-parse", "--abbrev-ref", "HEAD")
    if head.returncode != 0:
        raise _fail(head, "reading the current branch")
    branch = check_branch(head.stdout.strip())
    spec = refspec(branch)

    status = _git(run, repo, "status", "--porcelain", "--", path)
    if status.returncode != 0:
        raise _fail(status, "git status")
    if not status.stdout.strip():
        raise SubmitError(f"nothing to submit: no changes under {path}")

    for cmd in validator_commands(tool, path):
        print(f"$ {shlex.join(cmd)}")
        proc = run(cmd, cwd=validator_cwd(repo, path), capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise _fail(proc, shlex.join(cmd))

    for what, args in (
        ("git add", ("add", "--", path)),
        ("git commit", ("commit", "-m", message, "--", path)),
        ("git push", ("push", "origin", spec)),
    ):
        proc = _git(run, repo, *args)
        if proc.returncode != 0:
            raise _fail(proc, what)

    print(f"pushed {branch} to origin")
    print("PR not opened (PoC mode). To open it from a machine with GitHub access, run:")
    print(f"  {pr_command(branch, message)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", required=True, choices=TOOLS)
    parser.add_argument("--path", required=True, help="model directory, relative to the repo")
    parser.add_argument("--repo", default=".", help="clone to submit from (default: cwd)")
    parser.add_argument("-m", "--message", default="", help="commit message and PR title")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    message = args.message or f"model: update {args.path}"
    try:
        submit(args.tool, args.path, repo, message)
    except SubmitError as err:
        print(f"submit: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
