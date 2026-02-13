param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$Service = "ssrkr8tiv",
  [string]$TimeoutSeconds = "900",
  [string]$Memory = "1Gi",
  [string]$TagPrefix = "fh-"
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
$latestReadyRevision = [string]$svc.status.latestReadyRevisionName
$actualTimeout = [string]$svc.spec.template.spec.timeoutSeconds
$actualMemory = [string]$svc.spec.template.spec.containers[0].resources.limits.memory

Write-Host "[hardening] latestReadyRevision=$latestReadyRevision timeoutSeconds=$actualTimeout memory=$actualMemory"
if ($actualTimeout -ne $TimeoutSeconds -or $actualMemory -ne $Memory) {
  throw "Cloud Run hardening validation failed (expected timeout=$TimeoutSeconds, memory=$Memory)"
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

