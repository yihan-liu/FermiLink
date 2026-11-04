from __future__ import annotations

from pathlib import Path

import pytest

from fermilink import cli
from fermilink.cli.commands import workflows as workflow_commands


@pytest.mark.parametrize("command", ["exec", "loop"])
@pytest.mark.parametrize("disable_completion_commit", [False, True])
def test_completion_commit_cli_flag(
    command: str,
    disable_completion_commit: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    argv = [command, "finish it"]
    if disable_completion_commit:
        argv.append("--no-completion-commit")
    args = cli._build_parser().parse_args(argv)
    assert args._fermilink_disable_completion_commit is disable_completion_commit

    completion_calls: list[tuple[Path, str]] = []
    checkpoint = {
        "status": "committed",
        "sha": "test-commit",
        "error": "",
        "memory_only": "false",
    }

    def completion_commit(*, repo_dir: Path, mode_name: str) -> dict[str, str]:
        completion_calls.append((repo_dir, mode_name))
        return checkpoint

    monkeypatch.setattr(
        workflow_commands, "_workflow_completion_commit", completion_commit
    )

    result = workflow_commands._attempt_mode_completion_commit(
        repo_dir=tmp_path, args=args, mode_name=command
    )

    if disable_completion_commit:
        assert completion_calls == []
        assert result == {
            "status": "noop",
            "sha": "",
            "error": "",
            "memory_only": "false",
        }
    else:
        assert completion_calls == [(tmp_path, command)]
        assert result == checkpoint
