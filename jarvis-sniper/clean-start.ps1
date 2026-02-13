# Kill any processes on port 3001 and 3002
$ports = @(3001, 3002)
foreach ($port in $ports) {
    $connections = netstat -ano | Select-String ":$port\s" | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Sort-Object -Unique
    foreach ($pid in $connections) {
        if ($pid -and $pid -ne '0') {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "Killed PID $pid on port $port"
            } catch {}
        }
    }
}
# Remove lock file
Remove-Item -Force "$PSScriptRoot\.next\dev\lock" -ErrorAction SilentlyContinue
Write-Host "Lock removed. Run: npm run dev"
