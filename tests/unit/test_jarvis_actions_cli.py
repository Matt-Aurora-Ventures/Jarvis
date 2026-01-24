from pathlib import Path

from jarvis_cli.main import build_parser


def test_actions_cli_parses_list() -> None:
    parser = build_parser()
    args = parser.parse_args(["actions", "list"])
    assert args.command == "actions"
    assert args.actions_command == "list"


def test_actions_cli_journal_output(tmp_path: Path, capsys, monkeypatch) -> None:
    journal_path = tmp_path / "action_journal.jsonl"
    monkeypatch.setenv("ACTION_JOURNAL_PATH", str(journal_path))
    parser = build_parser()
    args = parser.parse_args(["actions", "journal", "--tail", "1"])
    exit_code = args.func(args)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == ""
