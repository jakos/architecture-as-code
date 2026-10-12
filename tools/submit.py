"""Submit a model change from an editor container: validate, commit, push a model/* branch.

Runs inside the B1 editor containers (PoC), where the clone is checked out on a branch
`model/<user>/<yyyy-mm-dd>-<slug>`. It validates the model with the tool's own validator,
commits only the `.c4` files of the model directory (a layout `.snap` file and anything else
under it is skipped and listed, ADR 0008), pushes the branch to `origin` and PRINTS the
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
MODEL_SUFFIX = ".c4"

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


def model_pathspec(path: str) -> str:
    """Git pathspec for the `.c4` files under the model directory, at any depth."""
    return f":(glob){path.rstrip('/')}/**/*{MODEL_SUFFIX}"


def parse_status(porcelain: str) -> tuple[list[str], list[str]]:
    """Split `git status --porcelain --ignored` lines into (model files, skipped files).

    Model files are changed, not ignored `.c4` files; everything else (a layout `.snap`,
    an ignored file, a note) is skipped.
    """
    model: list[str] = []
    skipped: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        flags, name = line[:2], line[3:]
        if " -> " in name:  # rename: the new name is what gets committed
            name = name.split(" -> ", 1)[1]
        name = name.strip().strip('"')
        if flags != "!!" and name.endswith(MODEL_SUFFIX):
            model.append(name)
        else:
            skipped.append(name)
    return model, skipped


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


def submit(
    tool: str, path: str, repo: Path, message: str, run: Runner = subprocess.run
) -> list[str]:
    """Validate, commit the changed `.c4` files and push the branch; print the PR command.

    Returns the paths (relative to the repo) that were left out of the commit.
    """
    head = _git(run, repo, "rev-parse", "--abbrev-ref", "HEAD")
    if head.returncode != 0:
        raise _fail(head, "reading the current branch")
    branch = check_branch(head.stdout.strip())
    spec = refspec(branch)

    status = _git(run, repo, "status", "--porcelain", "--ignored", "-uall", "--", path)
    if status.returncode != 0:
        raise _fail(status, "git status")
    changed, skipped = parse_status(status.stdout)
    if not changed:
        raise SubmitError(f"nothing to submit: no changed {MODEL_SUFFIX} files under {path}")

    for cmd in validator_commands(tool, path):
        print(f"$ {shlex.join(cmd)}")
        proc = run(cmd, cwd=validator_cwd(repo, path), capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise _fail(proc, shlex.join(cmd))

    pathspec = model_pathspec(path)
    for what, args in (
        ("git add", ("add", "--", pathspec)),
        ("git commit", ("commit", "-m", message, "--", pathspec)),
        ("git push", ("push", "origin", spec)),
    ):
        proc = _git(run, repo, *args)
        if proc.returncode != 0:
            raise _fail(proc, what)

    for name in skipped:
        print(f"skipped (not committed): {name}")
    print(f"pushed {branch} to origin")
    print("PR not opened (PoC mode). To open it from a machine with GitHub access, run:")
    print(f"  {pr_command(branch, message)}")
    return skipped


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
