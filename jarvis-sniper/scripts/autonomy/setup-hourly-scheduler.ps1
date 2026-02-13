param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$JobName = "jarvis-sniper-autonomy-hourly",
  [string]$BaseUrl = "https://kr8tiv.web.app",
  [string]$Schedule = "5 * * * *",
  [string]$TimeZone = "Etc/UTC",
  [string]$AutonomyJobToken = $env:AUTONOMY_JOB_TOKEN
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($AutonomyJobToken)) {
  throw "Missing AUTONOMY_JOB_TOKEN. Export it before running this script."
}

$uri = "$BaseUrl/api/autonomy/hourly"
$headers = "Authorization=Bearer $AutonomyJobToken,Content-Type=application/json"

Write-Host "[scheduler] Upserting Cloud Scheduler job $JobName -> $uri ($Schedule $TimeZone)" -ForegroundColor Cyan

try {
  gcloud scheduler jobs describe $JobName --project $Project --location $Region --format=json *> $null
  $exists = $LASTEXITCODE -eq 0
} catch {
  $exists = $false
}

if ($exists) {
  gcloud scheduler jobs update http $JobName `
    --project $Project `
    --location $Region `
    --schedule "$Schedule" `
    --time-zone "$TimeZone" `
    --uri "$uri" `
    --http-method POST `
    --update-headers "$headers" `
    --message-body "{}" `
    --quiet | Out-Null
  Write-Host "[scheduler] Updated existing job." -ForegroundColor Green
} else {
  gcloud scheduler jobs create http $JobName `
    --project $Project `
    --location $Region `
    --schedule "$Schedule" `
    --time-zone "$TimeZone" `
    --uri "$uri" `
    --http-method POST `
    --headers "$headers" `
    --message-body "{}" `
    --quiet | Out-Null
  Write-Host "[scheduler] Created new job." -ForegroundColor Green
}

Write-Host "[scheduler] Next run preview:" -ForegroundColor Yellow
gcloud scheduler jobs describe $JobName `
  --project $Project `
  --location $Region `
  --format="value(schedule,timeZone,state,httpTarget.uri)"

