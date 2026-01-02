# Antigravity / Google IDX Development Environment
# MiniMax M2.1 + Trading Bot Configuration
# 
# Place this file at: .idx/dev.nix in your project root
# The IDX environment will automatically rebuild with these settings

{ pkgs, ... }: {
  # Core packages
  packages = [
    # Python 3.11 with essential packages
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.requests
    pkgs.python311Packages.pandas
    pkgs.python311Packages.numpy
    
    # Development tools
    pkgs.git
    pkgs.curl
    pkgs.jq
  ];

  # Bootstrap script - runs on environment creation
  bootstrap = {
    enable = true;
    command = ''
      # Install trading and AI dependencies
      pip install --user \
        ccxt \
        openai \
        requests \
        pandas \
        numpy \
        python-dotenv \
        aiohttp
      
      echo "✓ Trading dependencies installed"
      echo "✓ MiniMax M2.1 environment ready"
    '';
  };

  # Environment variables for MiniMax M2.1 integration
  env = {
    # OpenRouter configuration (primary - cheapest via aggregator)
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";
    OPENROUTER_MODEL = "minimax/minimax-m2.1";
    
    # MiniMax model settings
    MINIMAX_MODEL = "minimax/minimax-m2.1";
    MINIMAX_CONTEXT_WINDOW = "200000";
    MINIMAX_MAX_OUTPUT_TOKENS = "8192";
    
    # Local fallback (Ollama)
    OLLAMA_BASE_URL = "http://localhost:11434";
    OLLAMA_MODEL = "llama3.2:3b";
    
    # Default provider routing
    DEFAULT_AI_PROVIDER = "minimax";
    AI_FALLBACK_PROVIDER = "ollama";
    
    # Cost controls
    DAILY_SPEND_LIMIT_USD = "5.00";
    
    # Python path
    PYTHONPATH = ".";
  };

  # IDX-specific configuration
  idx = {
    # Recommended extensions
    extensions = [
      "ms-python.python"
      "ms-python.vscode-pylance"
      "ms-python.debugpy"
    ];
    
    # Workspace settings
    workspace = {
      onCreate = {
        default.openFiles = ["core/life_os_router.py" "README.md"];
      };
    };
    
    # Disable previews (not a web app)
    previews = {
      enable = false;
    };
  };
}
