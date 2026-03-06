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
    assert 'XAI_API_KEY=${XaiApiKeySecret}:latest' in script
    assert 'if ($LASTEXITCODE -ne 0)' in script


def test_cloud_build_context_excludes_local_temp_artifacts():
    repo_root = Path(__file__).resolve().parents[3]
    gcloudignore = repo_root / ".gcloudignore"

    assert gcloudignore.exists()

    content = gcloudignore.read_text(encoding="utf-8")
    assert "temp/" in content
    assert "node_modules/" in content
    assert "jarvis-sniper/.next/" in content
    assert ".playwright-cli/" in content


def test_investments_dockerfile_does_not_copy_the_entire_repo():
    repo_root = Path(__file__).resolve().parents[3]
    dockerfile = (repo_root / "services" / "investments" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "COPY . ." not in dockerfile
    assert "COPY services/investments ./services/investments" in dockerfile
