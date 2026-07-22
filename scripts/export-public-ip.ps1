$ErrorActionPreference = "Stop"

$ip = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json").ip
if (-not $ip) {
    throw "Unable to resolve public IP address."
}

Write-Output "Developer public IPv4: $ip"
Write-Output "Add this value to ALLOWED_PUBLIC_IPS and infra parameter allowedPublicIps if this machine needs Foundry access."
