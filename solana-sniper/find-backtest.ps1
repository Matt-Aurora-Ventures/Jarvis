Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -and ($cmd -like '*continuous-backtest*' -or $cmd -like '*tsx*backtest*')) {
        Write-Output "PID=$($_.ProcessId) START=$($_.CreationDate)"
        Write-Output "  CMD=$($cmd.Substring(0, [Math]::Min($cmd.Length, 400)))"
        Write-Output ""
    }
}
