param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$Service = "ssrkr8tiv",
  [string]$TimeoutSeconds = "900",
  [string]$Memory = "1Gi",
  [string]$MaxInstances = "1",
  [string]$TagPrefix = "fh-",
  # Keep autonomy + batch audit flags persistent across Firebase framework redeploys.
  # These are intentionally NON-secret (secrets remain in Secret Manager bindings).
  [string]$AutonomyAuditBucket = "kr8tiv-sniper-autonomy-audit",
  [string]$AutonomyEnabled = "true",
  [string]$AutonomyApplyOverrides = "false",
  [string]$XaiBatchEnabled = "true",
  [string]$XaiFrontierModel = "grok-4-1-fast-reasoning",
  [string]$XaiDailyBudgetUsd = "10",
  [string]$XaiHourlyMaxInputTokens = "150000",
  [string]$XaiHourlyMaxOutputTokens = "30000",
  [string]$XaiKeyRateQps = "0.2",
  [string]$XaiKeyRateQpm = "12",
  [string]$XaiKeyRateTpm = "120000"
)

$ErrorActionPreference = "Stop"

Write-Host "[hardening] Updating Cloud Run service $Service in $Project/$Region ..."
$envVars = @(
  "AUTONOMY_ENABLED=$AutonomyEnabled",
  "AUTONOMY_APPLY_OVERRIDES=$AutonomyApplyOverrides",
  "AUTONOMY_AUDIT_BUCKET=$AutonomyAuditBucket",
  "XAI_BATCH_ENABLED=$XaiBatchEnabled",
  "XAI_FRONTIER_MODEL=$XaiFrontierModel",
  "XAI_DAILY_BUDGET_USD=$XaiDailyBudgetUsd",
  "XAI_HOURLY_MAX_INPUT_TOKENS=$XaiHourlyMaxInputTokens",
  "XAI_HOURLY_MAX_OUTPUT_TOKENS=$XaiHourlyMaxOutputTokens",
  "XAI_KEY_RATE_QPS=$XaiKeyRateQps",
  "XAI_KEY_RATE_QPM=$XaiKeyRateQpm",
  "XAI_KEY_RATE_TPM=$XaiKeyRateTpm"
) -join ","

gcloud run services update $Service `
  --project $Project `
  --region $Region `
  --timeout $TimeoutSeconds `
  --memory $Memory `
  --max-instances $MaxInstances `
  --update-env-vars $envVars `
  --quiet | Out-Null

Write-Host "[hardening] Verifying runtime settings..."
$svcJson = gcloud run services describe $Service `
  --project $Project `
  --region $Region `
  --format=json

$svc = $svcJson | ConvertFrom-Json
$latestReadyRevision = [string]$svc.status.latestReadyRevisionName
$actualTimeout = [string]$svc.spec.template.spec.timeoutSeconds
$actualMemory = [string]$svc.spec.template.spec.containers[0].resources.limits.memory
$actualMaxScale = [string]$svc.spec.template.metadata.annotations."autoscaling.knative.dev/maxScale"

Write-Host "[hardening] latestReadyRevision=$latestReadyRevision timeoutSeconds=$actualTimeout memory=$actualMemory maxScale=$actualMaxScale"
if ($actualTimeout -ne $TimeoutSeconds -or $actualMemory -ne $Memory -or $actualMaxScale -ne $MaxInstances) {
  throw "Cloud Run hardening validation failed (expected timeout=$TimeoutSeconds, memory=$Memory, maxScale=$MaxInstances)"
}

if ([string]::IsNullOrWhiteSpace($latestReadyRevision)) {
  throw "Cloud Run hardening validation failed (missing latestReadyRevision)"
}

Write-Host "[hardening] Repointing Firebase Hosting tags ($TagPrefix*) to $latestReadyRevision ..."
$fhTags = @(
  $svc.status.traffic `
    | Where-Object { $_.tag -and ([string]$_.tag).StartsWith($TagPrefix) } `
    | ForEach-Object { [string]$_.tag }
) | Sort-Object -Unique

if ($fhTags.Count -gt 0) {
  $updateTagsArg = ($fhTags | ForEach-Object { "$_=$latestReadyRevision" }) -join ","
  gcloud run services update-traffic $Service `
    --project $Project `
    --region $Region `
    --update-tags $updateTagsArg `
    --quiet | Out-Null

  $postJson = gcloud run services describe $Service `
    --project $Project `
    --region $Region `
    --format=json
  $post = $postJson | ConvertFrom-Json

  foreach ($tag in $fhTags) {
    $bound = @($post.status.traffic | Where-Object { $_.tag -eq $tag })
    if ($bound.Count -eq 0) {
      throw "Tag retarget failed: missing tag '$tag' after update-traffic"
    }
    $boundRev = [string]$bound[0].revisionName
    Write-Host "[hardening] tag '$tag' -> $boundRev"
    if ($boundRev -ne $latestReadyRevision) {
      throw "Tag retarget failed: tag '$tag' still points to '$boundRev' (expected '$latestReadyRevision')"
    }
  }
} else {
  Write-Host "[hardening] No tags with prefix '$TagPrefix' found; skipping tag repoint."
}

Write-Host "[hardening] Completed."

