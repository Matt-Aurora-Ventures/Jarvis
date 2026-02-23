param(
  [Parameter(Mandatory = $false)]
  [string]$AdminApiKey = $env:XAI_ADMIN_API_KEY,
  [Parameter(Mandatory = $false)]
  [string]$BaseUrl = "https://api.x.ai",
  [Parameter(Mandatory = $false)]
  [string]$KeyName = "jarvis-sniper-runtime",
  [Parameter(Mandatory = $false)]
  [double]$Qps = 0.2,
  [Parameter(Mandatory = $false)]
  [int]$Qpm = 12,
  [Parameter(Mandatory = $false)]
  [int]$Tpm = 120000
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($AdminApiKey)) {
  throw "Missing admin key. Set XAI_ADMIN_API_KEY before running."
}

$headers = @{
  "Authorization" = "Bearer $AdminApiKey"
  "Content-Type"  = "application/json"
}

$payload = @{
  name = $KeyName
  description = "Runtime child key for Jarvis Sniper autonomy batch jobs"
  model_allowlist = @(
    "grok-4-1-fast-reasoning",
    "grok-4-fast-reasoning",
    "grok-4"
  )
  rate_limits = @{
    qps = $Qps
    qpm = $Qpm
    tpm = $Tpm
  }
} | ConvertTo-Json -Depth 8

Write-Host "[xai] Creating restricted runtime key..." -ForegroundColor Cyan
Write-Host "[xai] Limits => qps=$Qps qpm=$Qpm tpm=$Tpm" -ForegroundColor DarkGray

try {
  # Management API endpoint per xAI docs.
  $uri = "$BaseUrl/v1/management/keys"
  $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $payload
  $keyId = $resp.id
  $runtimeKey = $resp.key
  if ([string]::IsNullOrWhiteSpace($runtimeKey)) {
    throw "Management API response missing key material."
  }

  Write-Host "[xai] Success. Key ID: $keyId" -ForegroundColor Green
  Write-Host "[xai] Set Cloud Run env:" -ForegroundColor Yellow
  Write-Host "gcloud run services update ssrkr8tiv --project kr8tiv --region us-central1 --set-env-vars XAI_API_KEY=$runtimeKey" -ForegroundColor White
  Write-Host "[xai] Also set policy envs: XAI_FRONTIER_MODEL, XAI_FRONTIER_FALLBACK_MODELS, XAI_DAILY_BUDGET_USD"
} catch {
  Write-Error "[xai] Failed to provision key via Management API. Check endpoint/payload against latest docs. Error: $($_.Exception.Message)"
  exit 1
}

