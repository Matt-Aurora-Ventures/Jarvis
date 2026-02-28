param(
  [string]$Project = "kr8tiv",
  [string]$Region = "us-central1",
  [string]$Service = "jarvis-investments-api",
  [string]$Repository = "gcf-artifacts",
  [string]$DatabaseUrl,
  [string]$RedisUrl,
  [string]$AdminKey,
  [string]$BasketAddress,
  [string]$ManagementWalletKey,
  [string]$SolanaWalletKey,
  [string]$StakingPoolAddress = "",
  [string]$AuthorityRewardAccount = "",
  [string]$BaseRpcUrl = "https://mainnet.base.org",
  [string]$SolanaRpcUrl = "https://api.mainnet-beta.solana.com",
  [string]$BirdeyeApiKey = "",
  [string]$XaiApiKeySecret = "jarvis-xai-runtime-key",
  [string]$AnthropicApiKey = "",
  [string]$OpenAiApiKey = "",
  [bool]$DryRun = $false
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing -DatabaseUrl" }
if ([string]::IsNullOrWhiteSpace($RedisUrl)) { throw "Missing -RedisUrl" }
if ([string]::IsNullOrWhiteSpace($AdminKey)) { throw "Missing -AdminKey" }
if (-not $DryRun) {
  if ([string]::IsNullOrWhiteSpace($BasketAddress)) { throw "Missing -BasketAddress" }
  if ([string]::IsNullOrWhiteSpace($ManagementWalletKey)) { throw "Missing -ManagementWalletKey" }
  if ([string]::IsNullOrWhiteSpace($SolanaWalletKey)) { throw "Missing -SolanaWalletKey" }
  if ([string]::IsNullOrWhiteSpace($AnthropicApiKey)) { throw "Missing -AnthropicApiKey" }
  if ([string]::IsNullOrWhiteSpace($OpenAiApiKey)) { throw "Missing -OpenAiApiKey" }
}

$image = "$Region-docker.pkg.dev/$Project/$Repository/$Service:latest"
$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$cloudBuildConfig = Join-Path $scriptDir "cloudbuild.investments.yaml"

if (-not (Test-Path $cloudBuildConfig)) {
  throw "[investments] Missing Cloud Build config: $cloudBuildConfig"
}

Write-Host "[investments] Building image: $image"
gcloud builds submit `
  $repoRoot `
  --project $Project `
  --region $Region `
  --config $cloudBuildConfig `
  --substitutions "_IMAGE=$image"

$envVars = @(
  "DATABASE_URL=$DatabaseUrl",
  "REDIS_URL=$RedisUrl",
  "INVESTMENT_API_PORT=8080",
  "INVESTMENT_ADMIN_KEY=$AdminKey",
  "DRY_RUN=$($DryRun.ToString().ToLowerInvariant())",
  "BASE_RPC_URL=$BaseRpcUrl",
  "SOLANA_RPC_URL=$SolanaRpcUrl",
  "BIRDEYE_API_KEY=$BirdeyeApiKey",
  "BASKET_ADDRESS=$BasketAddress",
  "MANAGEMENT_WALLET_KEY=$ManagementWalletKey",
  "SOLANA_WALLET_KEY=$SolanaWalletKey",
  "STAKING_POOL_ADDRESS=$StakingPoolAddress",
  "AUTHORITY_REWARD_ACCOUNT=$AuthorityRewardAccount",
  "ANTHROPIC_API_KEY=$AnthropicApiKey",
  "OPENAI_API_KEY=$OpenAiApiKey"
) -join ","

Write-Host "[investments] Deploying Cloud Run service: $Service"
gcloud run deploy $Service `
  --project $Project `
  --region $Region `
  --image $image `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars $envVars `
  --set-secrets "XAI_API_KEY=$XaiApiKeySecret:latest" `
  --quiet | Out-Null

$url = gcloud run services describe $Service `
  --project $Project `
  --region $Region `
  --format="value(status.url)"

if ([string]::IsNullOrWhiteSpace($url)) {
  throw "[investments] Failed to resolve deployed service URL"
}

Write-Host "[investments] Live URL: $url"
Write-Host $url
