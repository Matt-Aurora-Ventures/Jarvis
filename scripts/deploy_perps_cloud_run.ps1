param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$Service = "jarvis-perps-api",
  [string]$Repository = "gcf-artifacts"
)

$ErrorActionPreference = "Stop"

$image = "$Region-docker.pkg.dev/$Project/$Repository/$Service:latest"
$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$cloudBuildConfig = Join-Path $scriptDir "cloudbuild.perps.yaml"

if (-not (Test-Path $cloudBuildConfig)) {
  throw "[perps] Missing Cloud Build config: $cloudBuildConfig"
}

Write-Host "[perps] Building image: $image"
gcloud builds submit `
  $repoRoot `
  --project $Project `
  --region $Region `
  --config $cloudBuildConfig `
  --substitutions "_IMAGE=$image"

Write-Host "[perps] Deploying Cloud Run service: $Service"
gcloud run deploy $Service `
  --project $Project `
  --region $Region `
  --image $image `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars "JARVIS_RALPH_RUNTIME_DIR=/tmp/jarvis-perps-runtime,FLASK_DEBUG=false" `
  --quiet | Out-Null

$url = gcloud run services describe $Service `
  --project $Project `
  --region $Region `
  --format="value(status.url)"

if ([string]::IsNullOrWhiteSpace($url)) {
  throw "[perps] Failed to resolve deployed service URL"
}

Write-Host "[perps] Live URL: $url"
Write-Host $url
