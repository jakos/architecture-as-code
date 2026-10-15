import pytest

# Repository-local variables, as listed by `git rev-parse --local-env-vars`. Git exports
# some of them (GIT_DIR at least) into hooks, so a pre-push run of the tests would point
# their own `git init`, `git config` and `git add` at the real repository instead of tmp_path.
GIT_LOCAL_ENV_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE",
    "GIT_PREFIX",
    "GIT_SHALLOW_FILE",
    "GIT_COMMON_DIR",
)


@pytest.fixture(autouse=True)
def _isolate_from_outer_git(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in GIT_LOCAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
