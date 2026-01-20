# Firefox DexScreener Fix Script
$profilePath = "C:\Users\lucid\AppData\Roaming\Mozilla\Firefox\Profiles\pcw9eleg.dev-edition-default"

# Find dexscreener storage
Write-Host "Checking dexscreener site data..."
$dexFolders = Get-ChildItem -Path "$profilePath\storage\default" -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*dexscreener*' }
if ($dexFolders) {
    Write-Host "Found dexscreener storage:"
    $dexFolders | ForEach-Object { Write-Host "  - $($_.FullName)" }
} else {
    Write-Host "No dexscreener storage found"
}

# Check for extensions that might interfere
Write-Host "`nChecking installed extensions..."
$extensionsPath = "$profilePath\extensions.json"
if (Test-Path $extensionsPath) {
    $extensions = Get-Content $extensionsPath | ConvertFrom-Json
    $addonNames = $extensions.addons | Select-Object -ExpandProperty defaultLocale -ErrorAction SilentlyContinue | Select-Object -ExpandProperty name -ErrorAction SilentlyContinue
    if ($addonNames) {
        Write-Host "Installed extensions:"
        $addonNames | ForEach-Object { Write-Host "  - $_" }
    }
}

# Check network security preferences
Write-Host "`nNetwork-related preferences:"
$prefs = Get-Content "$profilePath\prefs.js" -ErrorAction SilentlyContinue
$networkPrefs = $prefs | Select-String -Pattern "network\.(websocket|http|security|cors)"
if ($networkPrefs) {
    $networkPrefs | ForEach-Object { Write-Host "  $($_.Line)" }
} else {
    Write-Host "  No custom network preferences"
}

# Check tracking protection exceptions
Write-Host "`nTracking protection exceptions:"
$etpPrefs = $prefs | Select-String -Pattern "privacy\.trackingprotection"
if ($etpPrefs) {
    $etpPrefs | ForEach-Object { Write-Host "  $($_.Line)" }
}

Write-Host "`nDone. If Firefox is open, close it and run this script to clear site data."
