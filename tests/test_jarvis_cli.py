from pathlib import Path

from jarvis_cli.bootstrap import BootstrapResult, Bootstrapper
from jarvis_cli.main import build_parser


def test_bootstrap_creates_dirs_and_env(tmp_path: Path) -> None:
    bootstrapper = Bootstrapper(root=tmp_path)
    result = BootstrapResult()
    bootstrapper.ensure_directories(result)
    bootstrapper.ensure_env_file(result)

    assert (tmp_path / "data").exists()
    assert (tmp_path / "logs").exists()
    assert (tmp_path / "secrets").exists()
    assert (tmp_path / ".env").exists()


def test_cli_parser_accepts_profile() -> None:
    parser = build_parser()
    args = parser.parse_args(["up", "--profile", "voice"])
    assert args.profile == "voice"
