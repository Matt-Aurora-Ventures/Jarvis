# Get Moltbook Claim URL from VPS
$password = "bhjhbHBujbxbvxd57272#####"
$host = "72.61.7.126"
$user = "root"

# Use plink if available, otherwise try ssh with expect-like input
if (Get-Command plink -ErrorAction SilentlyContinue) {
    $output = echo y | plink -ssh -pw $password $user@$host "cat /root/clawd/secrets/moltbook.json"
    Write-Output $output
} else {
    # Try with PowerShell SSH (requires manual password entry workaround)
    Write-Host "Connecting to VPS at $host..."

    # Create temp file with password
    $tempFile = [System.IO.Path]::GetTempFileName()
    Set-Content -Path $tempFile -Value $password -NoNewline

    # Use password from file
    $cmd = "type `"$tempFile`" | ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password $user@$host 'cat /root/clawd/secrets/moltbook.json' 2>&1"
    $output = Invoke-Expression $cmd

    # Clean up
    Remove-Item $tempFile -Force

    Write-Output $output
}
