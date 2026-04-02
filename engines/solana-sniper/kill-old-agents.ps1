# Kill all non-v4 continuous-backtest processes
$killPids = @(
    # Original (no instance)
    42904, 32116, 42112,
    # v1 standard
    44420, 2368, 29612,
    # v1 deep
    38028, 40292, 13112,
    # v1 wide
    33680, 42416, 41172,
    # v2 standard
    50300, 50140, 51068,
    # v2 deep
    44920, 13144, 30056,
    # v2 wide
    50836, 29764, 50940,
    # v3 standard
    38784, 52444, 37132,
    # v3 deep
    29704, 26164, 49760,
    # v3 wide
    32800, 50760, 51320
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
    } catch {
        # Process already gone
    }
}
Write-Output ""
Write-Output "Killed $killed processes. v4 agents preserved."
