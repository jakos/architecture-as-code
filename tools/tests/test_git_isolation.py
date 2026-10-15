import os
import subprocess

from conftest import GIT_LOCAL_ENV_VARS


def test_the_list_matches_what_git_calls_repository_local():
    done = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, check=True
    )
    assert set(done.stdout.split()) <= set(GIT_LOCAL_ENV_VARS)


def test_no_repository_local_variable_reaches_a_test():
    assert not [name for name in GIT_LOCAL_ENV_VARS if name in os.environ]
