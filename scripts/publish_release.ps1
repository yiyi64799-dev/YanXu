param(
    [Parameter(Mandatory=$true)][ValidatePattern('^https://.+')][string]$SupabaseUrl,
    [Parameter(Mandatory=$true)][string]$ReleaseDirectory
)
$ErrorActionPreference = 'Stop'
$secret = $env:SUPABASE_SERVICE_ROLE_KEY
if ([string]::IsNullOrWhiteSpace($secret)) { throw '请只在当前终端设置 SUPABASE_SERVICE_ROLE_KEY 环境变量。' }
$directory = (Resolve-Path -LiteralPath $ReleaseDirectory).Path
$manifestPath = Join-Path $directory 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw '发布目录缺少 manifest.json' }
$manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
$headers = @{ Authorization = "Bearer $secret"; apikey = $secret }
$base = $SupabaseUrl.TrimEnd('/')

try {
    Invoke-RestMethod -Method Get -Uri "$base/storage/v1/bucket/yanxu-releases" -Headers $headers | Out-Null
} catch {
    $bucket = @{ id='yanxu-releases'; name='yanxu-releases'; public=$true; file_size_limit=314572800 } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/storage/v1/bucket" -Headers $headers -ContentType 'application/json' -Body $bucket | Out-Null
}

function Send-ReleaseObject([string]$Path, [string]$ContentType) {
    $name = Split-Path $Path -Leaf
    $uploadHeaders = $headers.Clone(); $uploadHeaders['x-upsert'] = 'true'
    Invoke-WebRequest -Method Post -Uri "$base/storage/v1/object/yanxu-releases/$name" -Headers $uploadHeaders -ContentType $ContentType -InFile $Path | Out-Null
    Write-Host "已上传：$name"
}
$windows = Join-Path $directory (Split-Path $manifest.desktop.url -Leaf)
$android = Join-Path $directory (Split-Path $manifest.android.url -Leaf)
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $windows).Hash.ToLowerInvariant() -ne $manifest.desktop.sha256) { throw 'Windows ZIP 哈希与 manifest 不一致' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $android).Hash.ToLowerInvariant() -ne $manifest.android.sha256) { throw 'Android APK 哈希与 manifest 不一致' }
Send-ReleaseObject $windows 'application/zip'
Send-ReleaseObject $android 'application/vnd.android.package-archive'
Send-ReleaseObject $manifestPath 'application/json'
Write-Host '发布完成；manifest.json 最后上传，客户端现在可以发现新版。'


