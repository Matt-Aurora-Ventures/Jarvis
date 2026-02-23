Get-NetFirewallRule | Where-Object { $_.DisplayName -like '*Telegram*' } | Select-Object DisplayName, Action, Direction, Enabled | Format-Table -AutoSize
