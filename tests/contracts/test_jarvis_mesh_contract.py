from pathlib import Path


def test_jarvis_mesh_contract_files_and_methods_exist():
    lib = Path("contracts/jarvis-mesh/programs/jarvis-mesh/src/lib.rs")
    assert lib.exists()
    content = lib.read_text(encoding="utf-8")
    assert "initialize_mesh" in content
    assert "register_node" in content
    assert "submit_consensus" in content
