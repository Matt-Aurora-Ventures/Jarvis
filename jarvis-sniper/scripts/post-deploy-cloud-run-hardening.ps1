param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$Service = "ssrkr8tiv",
  [string]$TimeoutSeconds = "900",
  [string]$Memory = "1Gi"
)

$ErrorActionPreference = "Stop"

Write-Host "[hardening] Updating Cloud Run service $Service in $Project/$Region ..."
gcloud run services update $Service `
  --project $Project `
  --region $Region `
  --timeout $TimeoutSeconds `
  --memory $Memory `
  --quiet | Out-Null

Write-Host "[hardening] Verifying runtime settings..."
$svcJson = gcloud run services describe $Service `
  --project $Project `
  --region $Region `
  --format=json

$svc = $svcJson | ConvertFrom-Json
$actualTimeout = [string]$svc.spec.template.spec.timeoutSeconds
$actualMemory = [string]$svc.spec.template.spec.containers[0].resources.limits.memory

Write-Host "[hardening] timeoutSeconds=$actualTimeout memory=$actualMemory"
if ($actualTimeout -ne $TimeoutSeconds -or $actualMemory -ne $Memory) {
  throw "Cloud Run hardening validation failed (expected timeout=$TimeoutSeconds, memory=$Memory)"
}

Write-Host "[hardening] Completed."
