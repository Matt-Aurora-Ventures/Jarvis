# Setup Chrome for Remote Debugging
# Creates shortcut to launch Chrome with debugging enabled

 = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
:USERPROFILE '.chrome-automation'

# Create user data directory
New-Item -ItemType Directory -Force -Path  = Join-Path  = New-Object -ComObject WScript.Shell
.CreateShortcut(.TargetPath = .Arguments = "--remote-debugging-port="""
" -ForegroundColor Cyan
