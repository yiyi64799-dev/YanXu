param(
    [Parameter(Mandatory=$true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [Parameter(Mandatory=$true)][ValidatePattern('^https://.+')][string]$SupabaseUrl,
    [string]$Channel = 'stable',
    [string]$ReleaseNotes = '稳定性与体验更新',
    [string]$MinSupportedAndroid = '2.1.0',
    [string]$PythonPath = 'python'
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$output = Join-Path $workspace "artifacts\v$Version"
if (Test-Path -LiteralPath $output) { throw "输出目录已存在，请先归档后再构建：$output" }
New-Item -ItemType Directory -Path $output | Out-Null

$desktopDist = Join-Path $output 'desktop-dist'
$desktopWork = Join-Path $output 'desktop-work'
$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $workspace '.build_deps'
try {
    & $PythonPath -m PyInstaller --distpath $desktopDist --workpath $desktopWork (Join-Path $workspace 'FocusCalendarV5.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Windows 构建失败' }
} finally { $env:PYTHONPATH = $oldPythonPath }
$windowsZip = Join-Path $output "YanXu-$Version-windows.zip"
Compress-Archive -Path (Join-Path $desktopDist 'YanXu\*') -DestinationPath $windowsZip -CompressionLevel Optimal

$signing = Join-Path $env:LOCALAPPDATA 'YanXu\signing\keystore.properties'
if (-not (Test-Path -LiteralPath $signing)) { throw "缺少正式签名配置：$signing" }
$oldJavaHome = $env:JAVA_HOME; $oldAndroidHome = $env:ANDROID_HOME
$env:JAVA_HOME = (Get-ChildItem -LiteralPath (Join-Path $workspace '.toolchains\jdk21') -Directory | Select-Object -First 1).FullName
$env:ANDROID_HOME = Join-Path $workspace '.toolchains\android-sdk'
try {
    Push-Location (Join-Path $workspace 'mobile')
    try { & npm run android:release; if ($LASTEXITCODE -ne 0) { throw 'Android Release 构建失败' } }
    finally { Pop-Location }
} finally { $env:JAVA_HOME = $oldJavaHome; $env:ANDROID_HOME = $oldAndroidHome }
$androidApk = Join-Path $output "YanXu-$Version.apk"
Copy-Item -LiteralPath (Join-Path $workspace 'mobile\android\app\build\outputs\apk\release\app-release.apk') -Destination $androidApk

$base = $SupabaseUrl.TrimEnd('/')
$manifest = [ordered]@{
    version = $Version
    channel = $Channel
    release_notes = $ReleaseNotes
    published_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    desktop = [ordered]@{ url = "$base/storage/v1/object/public/yanxu-releases/$(Split-Path $windowsZip -Leaf)"; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $windowsZip).Hash.ToLowerInvariant() }
    android = [ordered]@{ url = "$base/storage/v1/object/public/yanxu-releases/$(Split-Path $androidApk -Leaf)"; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $androidApk).Hash.ToLowerInvariant(); min_supported_version = $MinSupportedAndroid }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $output 'manifest.json')
Write-Host "构建完成：$output"

