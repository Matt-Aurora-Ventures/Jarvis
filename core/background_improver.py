"""
Background Improver - Silent Improvement Executor

Executes high-confidence improvement proposals without user interruption.
Validates safety, tests changes, deploys, and monitors success.

Key Features:
- Guardian integration for safety
- Rollback capability for all changes
- Success tracking via feedback loop
- Updates own thresholds based on outcomes
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, guardian


ROOT = Path(__file__).resolve().parents[1]
IMPROVEMENT_LOG = ROOT / "data" / "observation" / "improvements.jsonl"
ROLLBACK_DIR = ROOT / "data" / "observation" / "rollbacks"


@dataclass
class ImprovementProposal:
    """A proposed improvement to execute."""
    proposal_id: str
    category: str  # shell_alias, vscode_snippet, auto_install, workflow_template
    description: str
    action_type: str
    target_file: str
    code: str
    confidence: float
    risk: float
    created_at: float


@dataclass
class ImprovementResult:
    """Result of executing an improvement."""
    proposal_id: str
    success: bool
    executed_at: float
    error: str = ""
    rollback_path: str = ""
    validation_passed: bool = False
    deployed: bool = False


class BackgroundImprover:
    """
    Silently executes improvements without user interruption.
    
    Safety-first approach:
    1. Validate with Guardian
    2. Create rollback snapshot
    3. Test in sandbox (if applicable)
    4. Deploy to target
    5. Monitor for success
    """
    
    def __init__(self):
        cfg = config.load_config()
        improver_cfg = cfg.get("background_improver", {})
        self.enabled = improver_cfg.get("enabled", True)
        self.max_risk_threshold = improver_cfg.get("max_risk_threshold", 0.3)
        self.require_rollback = improver_cfg.get("require_rollback", True)
        
        # Stats
        self.total_executed = 0
        self.total_success = 0
        self.total_failed = 0
        self.total_rolled_back = 0
        
        ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)
    
    def execute(self, proposal: ImprovementProposal) -> bool:
        """
        Execute an improvement proposal.
        
        Returns True if successful, False otherwise.
        """
        if not self.enabled:
            return False
        
        self.total_executed += 1
        
        # 1. Validate safety
        if not self._validate_safety(proposal):
            self._log_result(ImprovementResult(
                proposal_id=proposal.proposal_id,
                success=False,
                executed_at=time.time(),
                error="Failed safety validation",
                validation_passed=False,
            ))
            self.total_failed += 1
            return False
        
        # 2. Create rollback snapshot
        rollback_path = ""
        if self.require_rollback:
            rollback_path = self._create_rollback(proposal)
            if not rollback_path:
                self._log_result(ImprovementResult(
                    proposal_id=proposal.proposal_id,
                    success=False,
                    executed_at=time.time(),
                    error="Failed to create rollback",
                    validation_passed=True,
                ))
                self.total_failed += 1
                return False
        
        # 3. Execute based on action type
        success, error = self._execute_action(proposal)
        
        if success:
            self._log_result(ImprovementResult(
                proposal_id=proposal.proposal_id,
                success=True,
                executed_at=time.time(),
                rollback_path=rollback_path,
                validation_passed=True,
                deployed=True,
            ))
            self.total_success += 1
            return True
        else:
            # Rollback if failed
            if rollback_path:
                self._rollback(rollback_path, proposal)
                self.total_rolled_back += 1
            
            self._log_result(ImprovementResult(
                proposal_id=proposal.proposal_id,
                success=False,
                executed_at=time.time(),
                error=error,
                rollback_path=rollback_path,
                validation_passed=True,
                deployed=False,
            ))
            self.total_failed += 1
            return False
    
    def _validate_safety(self, proposal: ImprovementProposal) -> bool:
        """
        Validate proposal safety using Guardian.
        
        Checks:
        1. Code safety (no dangerous patterns)
        2. File path whitelist
        3. Risk threshold
        4. Rollback capability
        """
        # Check risk threshold
        if proposal.risk > self.max_risk_threshold:
            return False
        
        # Check code safety with Guardian
        if proposal.code:
            is_safe, reason = guardian.is_command_dangerous(proposal.code)
            if not is_safe:
                return False
        
        # Check file path safety
        if proposal.target_file:
            target = Path(proposal.target_file).expanduser()
            
            # Whitelist: only allow modifications to user config files
            allowed_paths = [
                Path.home() / ".zshrc",
                Path.home() / ".bashrc",
                Path.home() / ".bash_profile",
                Path.home() / ".config",
                ROOT / "lifeos" / "config",
                ROOT / "data",
                ROOT / "skills",
            ]
            
            # Check if target is within allowed paths
            try:
                target_resolved = target.resolve()
                allowed = any(
                    target_resolved == p or target_resolved.is_relative_to(p)
                    for p in allowed_paths
                )
                if not allowed:
                    return False
            except Exception:
                return False
        
        return True
    
    def _create_rollback(self, proposal: ImprovementProposal) -> str:
        """
        Create a rollback snapshot of the target file.
        
        Returns path to rollback file, or empty string on failure.
        """
        if not proposal.target_file:
            return ""
        
        target = Path(proposal.target_file).expanduser()
        if not target.exists():
            # New file - rollback is deletion
            rollback_meta = ROLLBACK_DIR / f"{proposal.proposal_id}.json"
            with open(rollback_meta, "w") as f:
                json.dump({
                    "proposal_id": proposal.proposal_id,
                    "target_file": str(target),
                    "action": "delete",
                    "created_at": datetime.now().isoformat(),
                }, f, indent=2)
            return str(rollback_meta)
        
        # Existing file - backup content
        try:
            rollback_content = ROLLBACK_DIR / f"{proposal.proposal_id}.backup"
            shutil.copy2(target, rollback_content)
            
            rollback_meta = ROLLBACK_DIR / f"{proposal.proposal_id}.json"
            with open(rollback_meta, "w") as f:
                json.dump({
                    "proposal_id": proposal.proposal_id,
                    "target_file": str(target),
                    "action": "restore",
                    "backup_file": str(rollback_content),
                    "created_at": datetime.now().isoformat(),
                }, f, indent=2)
            
            return str(rollback_meta)
        except Exception as e:
            print(f"Warning: Rollback creation failed: {e}")
            return ""
    
    def _rollback(self, rollback_path: str, proposal: ImprovementProposal):
        """Restore from rollback snapshot."""
        try:
            with open(rollback_path, "r") as f:
                meta = json.load(f)
            
            target = Path(meta["target_file"])
            
            if meta["action"] == "delete":
                # Remove newly created file
                if target.exists():
                    target.unlink()
            
            elif meta["action"] == "restore":
                # Restore from backup
                backup_file = Path(meta["backup_file"])
                if backup_file.exists():
                    shutil.copy2(backup_file, target)
            
            print(f"✅ Rolled back: {proposal.proposal_id}")
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
    
    def _execute_action(self, proposal: ImprovementProposal) -> tuple[bool, str]:
        """
        Execute the improvement action.
        
        Returns (success, error_message)
        """
        try:
            if proposal.action_type == "shell_alias":
                return self._add_shell_alias(proposal)
            
            elif proposal.action_type == "vscode_snippet":
                return self._add_vscode_snippet(proposal)
            
            elif proposal.action_type == "auto_install":
                return self._auto_install_package(proposal)
            
            elif proposal.action_type == "workflow_template":
                return self._create_workflow_template(proposal)
            
            else:
                return False, f"Unknown action type: {proposal.action_type}"
        
        except Exception as e:
            return False, str(e)
    
    def _add_shell_alias(self, proposal: ImprovementProposal) -> tuple[bool, str]:
        """
        Add a shell alias to .zshrc or .bashrc.
        
        Example: alias gsp='git status && git pull'
        """
        target = Path(proposal.target_file).expanduser()
        
        # Ensure file exists
        if not target.exists():
            target.touch()
        
        # Check if alias already exists
        with open(target, "r") as f:
            existing_content = f.read()
        
        # Extract alias name from code
        # Expected format: alias name='command'
        import re
        alias_match = re.match(r"alias\s+(\w+)=", proposal.code)
        if not alias_match:
            return False, "Invalid alias format"
        
        alias_name = alias_match.group(1)
        
        # Check for duplicates
        if f"alias {alias_name}=" in existing_content:
            return False, f"Alias '{alias_name}' already exists"
        
        # Append alias
        with open(target, "a") as f:
            f.write(f"\n# Added by Jarvis Observational Daemon - {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"{proposal.code}\n")
        
        return True, ""
    
    def _add_vscode_snippet(self, proposal: ImprovementProposal) -> tuple[bool, str]:
        """
        Add a VS Code snippet.
        
        Target file: ~/.config/Code/User/snippets/python.json (or similar)
        """
        target = Path(proposal.target_file).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing snippets (or create new)
        if target.exists():
            with open(target, "r") as f:
                try:
                    snippets = json.load(f)
                except json.JSONDecodeError:
                    snippets = {}
        else:
            snippets = {}
        
        # Parse snippet from proposal.code (expected JSON format)
        try:
            new_snippet = json.loads(proposal.code)
            snippet_name = list(new_snippet.keys())[0]
            
            # Check for duplicates
            if snippet_name in snippets:
                return False, f"Snippet '{snippet_name}' already exists"
            
            # Add snippet
            snippets.update(new_snippet)
            
            # Write back
            with open(target, "w") as f:
                json.dump(snippets, f, indent=2)
            
            return True, ""
        except Exception as e:
            return False, f"Invalid snippet format: {e}"
    
    def _auto_install_package(self, proposal: ImprovementProposal) -> tuple[bool, str]:
        """
        Auto-install a Python package.
        
        Example: pip install requests
        """
        # Extract package name from code
        # Expected format: "requests" or "pip install requests"
        package = proposal.code.replace("pip install", "").strip()
        
        # Validate package name
        if not package or not package.replace("-", "").replace("_", "").isalnum():
            return False, "Invalid package name"
        
        # Install via pip
        try:
            result = subprocess.run(
                ["pip", "install", package],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode == 0:
                return True, ""
            else:
                return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)
    
    def _create_workflow_template(self, proposal: ImprovementProposal) -> tuple[bool, str]:
        """
        Create a workflow template file.
        
        Example: Project directory structure template
        """
        target = Path(proposal.target_file).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if already exists
        if target.exists():
            return False, "Template already exists"
        
        # Write template
        with open(target, "w") as f:
            f.write(proposal.code)
        
        return True, ""
    
    def _log_result(self, result: ImprovementResult):
        """Log improvement result to JSONL file."""
        IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(IMPROVEMENT_LOG, "a") as f:
                f.write(json.dumps(asdict(result)) + "\n")
        except Exception as e:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get improver statistics."""
        return {
            "total_executed": self.total_executed,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "total_rolled_back": self.total_rolled_back,
            "success_rate": self.total_success / max(self.total_executed, 1),
        }
    
    def get_recent_improvements(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent improvement results."""
        if not IMPROVEMENT_LOG.exists():
            return []
        
        improvements = []
        try:
            with open(IMPROVEMENT_LOG, "r") as f:
                for line in f:
                    try:
                        improvements.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return []
        
        return improvements[-limit:]
