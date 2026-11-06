# Public HTTPS for when you are away from home.
# The address changes every time this window starts. Do not share it.
# Close this window to take the address offline.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bin = Join-Path $here "cloudflared.exe"
if (-not (Test-Path $bin)) {
  $candidates = @(
    (Join-Path $here "cloudflared-windows-amd64.exe"),
    (Join-Path $env:USERPROFILE "Downloads\cloudflared-windows-amd64.exe")
  )
  $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($found) {
    Copy-Item -LiteralPath $found -Destination $bin
  } else {
    Write-Host "Downloading cloudflared..."
    $url = "https://ghfast.top/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $bin
  }
}
Write-Host "Keep this window open. Scroll up. The phone address is the https line containing trycloudflare.com."
& $bin tunnel --url http://127.0.0.1:12393
