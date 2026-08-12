$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$tracked = Get-ChildItem -LiteralPath $workspace -Recurse -File | Where-Object {
    $_.Extension -in @('.py','.ts','.js','.java','.json','.xml','.gradle','.properties','.sql','.md','.ps1','.yml','.yaml','.toml','.txt') -and
    $_.FullName -notmatch '\\(\.git|node_modules|\.gradle|build[^\\]*|release[^\\]*|dist|artifacts|\.toolchains|\.build_deps)\\'
}
$patterns = @(
    'eyJ[a-zA-Z0-9_-]{40,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}',
    'sb_secret_[a-zA-Z0-9_-]+',
    'service_role\s*[:=]\s*["''][^"'']+',
    'storePassword\s*=\s*.+',
    'keyPassword\s*=\s*.+'
)
$findings = foreach ($file in $tracked) {
    foreach ($pattern in $patterns) { Select-String -LiteralPath $file.FullName -Pattern $pattern -AllMatches -ErrorAction SilentlyContinue }
}
if ($findings) { $findings | Select-Object Path,LineNumber,Line; throw '敏感信息扫描发现疑似密钥，请人工复核。' }
Write-Host '敏感信息扫描通过（仍需在发布前人工复核 staged diff）。'

