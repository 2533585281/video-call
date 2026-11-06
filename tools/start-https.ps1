# Home phone: https://<this-computer>:12394
# Cert download: http://<this-computer>:12392/cert-help.html
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
node .\https-proxy.mjs
