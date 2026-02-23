[Net.ServicePointManager]::CheckCertificateRevocationList = $false
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    $r = Invoke-WebRequest -Uri 'https://api.telegram.org' -UseBasicParsing -TimeoutSec 10
    Write-Output "SUCCESS - Status: $($r.StatusCode)"
} catch {
    Write-Output "FAILED: $($_.Exception.Message)"
}
