from pathlib import Path


def test_deploy_script_uses_eth_runtime_env_and_keeps_unsafe_automation_disabled():
    repo_root = Path(__file__).resolve().parents[3]
    script = (repo_root / "scripts" / "deploy_investments_cloud_run.ps1").read_text(
        encoding="utf-8"
    )

    assert "ETH_RPC_URL=" in script
    assert "BASE_RPC_URL=" not in script
    assert "ENABLE_BRIDGE_AUTOMATION=false" in script
    assert "ENABLE_STAKING_AUTOMATION=false" in script
    assert '${Service}:latest' in script
    assert 'if ($LASTEXITCODE -ne 0)' in script
