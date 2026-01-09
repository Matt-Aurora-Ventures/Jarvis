# MCP Doctor - Server Health Validation

## Overview

The MCP Doctor is a comprehensive diagnostic tool that validates the health and functionality of MCP (Model Context Protocol) servers in the Jarvis autonomy stack. It ensures that all critical MCP components are operational and can reliably perform their functions.

## Available MCP Servers

### Currently Tested Servers

1. **Git Server** (`mcp3_git_*`)
   - Functions: Repository status, commit history, branch operations
   - Status: ✅ **WORKING**
   - Tests: `git status`, `git log`, repository access

2. **System Monitor** (`mcp13_get_*`)
   - Functions: CPU info, memory usage, network statistics
   - Status: ✅ **WORKING**
   - Tests: CPU cores, memory info, platform detection

3. **Obsidian Memory** (`mcp7_*`)
   - Functions: Knowledge graph operations, entity management
   - Status: ✅ **WORKING**
   - Tests: Graph reading, entity creation, search functionality

4. **Shell Server** (`mcp11_shell_execute`)
   - Functions: Command execution, process management
   - Status: ❌ **ISSUE IDENTIFIED**
   - Error: "no sampling handler configured"
   - Impact: Limits autonomous command execution

## Usage

### Basic MCP Health Check
```bash
./bin/lifeos doctor --mcp
```

### Full System Health Check (includes MCP)
```bash
./bin/lifeos doctor
```

### Direct Module Testing
```bash
python3 core/mcp_doctor_simple.py
```

## Test Results Interpretation

### ✅ Healthy Server
- All core functions working
- No errors in test operations
- Expected responses received

### ❌ Unhealthy Server
- Function calls failing
- Error messages indicating configuration issues
- Recommendations provided for remediation

## MCP Configuration

### Configuration File Location
- Path: `lifeos/config/mcp.config.json`
- Contains server definitions, paths, and environment variables

### Key Configuration Elements
```json
{
  "servers": [
    {
      "name": "git",
      "enabled": true,
      "command": "${HOME}/Documents/Jarvis context/venvs/mcp-git/bin/python",
      "args": ["-m", "mcp_server_git", "--repository", "${HOME}/Desktop/LifeOS"]
    },
    {
      "name": "system-monitor", 
      "enabled": true,
      "command": "${HOME}/Documents/Jarvis context/mcp-servers/mcp-monitor/bin/mcp-monitor"
    },
    {
      "name": "obsidian-memory",
      "enabled": true,
      "command": "node",
      "args": ["${HOME}/Documents/Jarvis context/mcp-servers/obsidian-memory-mcp/dist/index.js"],
      "env": {"MEMORY_DIR": "${HOME}/Documents/Obsidian/LifeOSVault"}
    },
    {
      "name": "shell",
      "enabled": true,
      "command": "${HOME}/Documents/Jarvis context/mcp-servers/mcp-shell/node_modules/.bin/mcp-shell-server"
    }
  ]
}
```

## Troubleshooting Guide

### Common Issues

#### 1. Shell Server "no sampling handler configured"
**Symptoms:**
- Shell commands fail with MCP error -32603
- Error: "no sampling handler configured"

**Root Cause:**
- Shell MCP server configuration issue
- Missing or incorrect server startup parameters

**Solutions:**
1. Check shell server path in `mcp.config.json`
2. Verify server binary exists and is executable
3. Restart MCP services
4. Check server logs for detailed errors

#### 2. Git Repository Access Issues
**Symptoms:**
- Git status returns error code 128
- "Not a git repository" errors

**Solutions:**
1. Verify `/Users/burritoaccount/Desktop/LifeOS` is a git repository
2. Check .git directory permissions
3. Ensure git binary is installed and accessible

#### 3. Obsidian Memory Path Issues
**Symptoms:**
- Entity creation fails
- Memory directory not found

**Solutions:**
1. Verify Obsidian vault path exists
2. Check `MEMORY_DIR` environment variable
3. Ensure vault directory is writable

#### 4. System Monitor Permission Issues
**Symptoms:**
- CPU/memory info unavailable
- Permission denied errors

**Solutions:**
1. Check system monitoring permissions
2. Verify psutil dependencies
3. Ensure proper system access rights

## Automated Testing

### Continuous Health Monitoring
The MCP doctor can be integrated into:
- CI/CD pipelines for deployment validation
- Cron jobs for periodic health checks
- Startup scripts for service validation

### Exit Codes
- `0`: All servers healthy
- `1`: One or more servers unhealthy

### JSON Output
For programmatic use:
```bash
./bin/lifeos doctor --mcp --json
```

## Integration with Jarvis

### Autonomous Controller Integration
The MCP doctor results are used by:
- `core/autonomous_controller.py` for capability validation
- `core/cli.py` for user-facing diagnostics
- System health monitoring loops

### Error Recovery
When MCP servers fail:
1. Log detailed error information
2. Attempt server restart procedures
3. Fallback to alternative methods where possible
4. Notify user of critical failures

## Performance Impact

### Test Duration
- Typical run time: 5-15 seconds
- Resource usage: Minimal
- Network usage: None (local testing only)

### Test Frequency Recommendations
- **On startup**: Always run
- **Before critical operations**: Run targeted tests
- **Periodic health checks**: Every 30 minutes (background)
- **After configuration changes**: Immediately run

## Security Considerations

### Test Safety
- All tests are read-only where possible
- No destructive operations performed
- Temporary files created and cleaned up
- No external network calls

### Data Privacy
- Test results contain system information only
- No user data or private content exposed
- Local execution only, no data transmission

## Development Guide

### Adding New Server Tests
1. Create test function in `core/mcp_doctor.py`
2. Follow `MCPDoctorResult` pattern
3. Add to `run_all_tests()` function
4. Update documentation

### Test Function Template
```python
def test_new_server() -> MCPDoctorResult:
    result = MCPDoctorResult("new_server")
    
    try:
        # Test server functionality
        response = new_server_function()
        
        if response and expected_condition:
            result.passed = True
            result.details = {"key": "value"}
        else:
            result.error = "Specific error description"
            
    except Exception as e:
        result.error = str(e)
    
    if not result.passed:
        result.add_recommendation("Specific recommendation")
    
    return result
```

## Version History

- **v1.0**: Initial implementation with git, system-monitor, obsidian-memory tests
- **v1.1**: Added shell server testing and improved error handling
- **v1.2**: Enhanced JSON output and integration capabilities

## Support

For MCP doctor issues:
1. Check this documentation first
2. Run `./bin/lifeos doctor --mcp` for detailed output
3. Review configuration in `lifeos/config/mcp.config.json`
4. Check system logs for additional error details

---

*Last updated: 2025-12-30*
*Jarvis Autonomy Stack - MCP Health Validation*
