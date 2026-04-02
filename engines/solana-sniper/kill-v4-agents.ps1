# Kill v4 continuous-backtest processes
$killPids = @(
    # standard-v4
    28340, 45208, 40556,
    # deep-v4
    26236, 7804, 19068,
    # wide-v4
    30260, 31100, 31880
)

$killed = 0
foreach ($p in $killPids) {
    try {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $p -Force
            Write-Output "Killed PID $p"
            $killed++
        }
    } catch {}
}
Write-Output "Killed $killed v4 processes."
