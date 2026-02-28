param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$Service = "ssrkr8tiv",
  [string]$PerpsBaseUrl,
  [string]$InvestmentsBaseUrl,
  [string]$InvestmentsAdminToken,
  [string]$XaiFrontierModel = "grok-4-latest"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PerpsBaseUrl)) { throw "Missing -PerpsBaseUrl" }
if ([string]::IsNullOrWhiteSpace($InvestmentsBaseUrl)) { throw "Missing -InvestmentsBaseUrl" }
if ([string]::IsNullOrWhiteSpace($InvestmentsAdminToken)) { throw "Missing -InvestmentsAdminToken" }

$envVars = @(
  "PERPS_SERVICE_BASE_URL=$PerpsBaseUrl",
  "INVESTMENTS_SERVICE_BASE_URL=$InvestmentsBaseUrl",
  "INVESTMENTS_ADMIN_TOKEN=$InvestmentsAdminToken",
  "XAI_FRONTIER_MODEL=$XaiFrontierModel",
  "NEXT_PUBLIC_ENABLE_PERPS=true",
  "NEXT_PUBLIC_ENABLE_INVESTMENTS=true"
) -join ","

Write-Host "[sniper] Updating Cloud Run env for $Service"
gcloud run services update $Service `
  --project $Project `
  --region $Region `
  --update-env-vars $envVars `
  --quiet | Out-Null

Write-Host "[sniper] Cloud Run env update complete."
