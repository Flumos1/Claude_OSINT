param(
  [string]$ProjectName = "claude-osint",
  [string]$Scope = "",
  [string]$VercelToken = $env:VERCEL_TOKEN,
  [string]$KvRestApiUrl = $env:KV_REST_API_URL,
  [string]$KvRestApiToken = $env:KV_REST_API_TOKEN,
  [string]$AdminUser = $env:OSINT_ADMIN_USER,
  [string]$AdminPassword = $env:OSINT_ADMIN_PASSWORD
)

$ErrorActionPreference = "Stop"

function Require-Value($Name, $Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "$Name is required. Pass -$Name or set the matching environment variable."
  }
}

function Invoke-Vercel($ArgsList) {
  $all = @($ArgsList) + @("--token", $VercelToken, "--no-color")
  & vercel @all
  if ($LASTEXITCODE -ne 0) {
    throw "vercel $($ArgsList -join ' ') failed with exit code $LASTEXITCODE"
  }
}

function Add-EnvIfMissing($Name, $Value) {
  $envList = (& vercel env ls production --token $VercelToken --no-color 2>$null) -join "`n"
  if ($envList -match "(?m)^\s*$([regex]::Escape($Name))\s") {
    Write-Host "env $Name already exists in production; keeping existing value"
    return
  }

  Write-Host "adding production env $Name"
  $Value | vercel env add $Name production --token $VercelToken --no-color
  if ($LASTEXITCODE -ne 0) {
    throw "failed to add env $Name"
  }
}

Require-Value "VercelToken" $VercelToken
Require-Value "KvRestApiUrl" $KvRestApiUrl
Require-Value "KvRestApiToken" $KvRestApiToken
Require-Value "AdminUser" $AdminUser
Require-Value "AdminPassword" $AdminPassword

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

Write-Host "checking Vercel auth"
Invoke-Vercel @("whoami")

$linkArgs = @("link", "--yes", "--project", $ProjectName)
if (-not [string]::IsNullOrWhiteSpace($Scope)) {
  $linkArgs += @("--scope", $Scope)
}

Write-Host "linking project $ProjectName"
Invoke-Vercel $linkArgs

Add-EnvIfMissing "OSINT_AUTH" "1"
Add-EnvIfMissing "OSINT_ADMIN_USER" $AdminUser
Add-EnvIfMissing "OSINT_ADMIN_PASSWORD" $AdminPassword
Add-EnvIfMissing "KV_REST_API_URL" $KvRestApiUrl
Add-EnvIfMissing "KV_REST_API_TOKEN" $KvRestApiToken

Write-Host "pulling production settings"
Invoke-Vercel @("pull", "--yes", "--environment=production")

Write-Host "deploying production"
Invoke-Vercel @("deploy", "--prod", "--yes")
