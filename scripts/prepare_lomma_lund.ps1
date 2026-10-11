[CmdletBinding()]
param([string]$SharedRoot = 'C:\RobustPendling\data')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$osmium = Join-Path $projectRoot '.venv\mamba\envs\robustpendling\Library\bin\osmium.exe'
$sourceDir = Join-Path $SharedRoot 'osm\source'
$extractDir = Join-Path $SharedRoot 'osm\extracts'
$gtfsDir = Join-Path $SharedRoot 'gtfs'
New-Item -ItemType Directory -Force $sourceDir,$extractDir,$gtfsDir | Out-Null
$gtfs = Join-Path $gtfsDir 'skane-20261011.zip'
$expectedGTFS = '6a17c51b0924301eea8466e71d826bd7495199ce3a0de7f4f90d0293b4c13182'
$localGTFS = Join-Path $projectRoot 'data\gtfs\skane.zip'
if (-not (Test-Path $gtfs)) {
    if ((Get-FileHash $localGTFS -Algorithm SHA256).Hash.ToLower() -ne $expectedGTFS) { throw 'GTFS checksum mismatch' }
    Copy-Item -LiteralPath $localGTFS -Destination "$gtfs.tmp"
    Move-Item -LiteralPath "$gtfs.tmp" -Destination $gtfs
}
if ((Get-FileHash $gtfs -Algorithm SHA256).Hash.ToLower() -ne $expectedGTFS) { throw 'Frozen GTFS checksum mismatch' }
$base = 'https://download.geofabrik.de/europe/sweden-261008.osm.pbf'
$source = Join-Path $sourceDir 'sweden-261008.osm.pbf'
foreach ($suffix in @('.md5','')) {
    $target = "$source$suffix"
    if (-not (Test-Path $target)) {
        Invoke-WebRequest -Uri "$base$suffix" -OutFile "$target.tmp"
        Move-Item -LiteralPath "$target.tmp" -Destination $target
    }
}
$expectedMD5 = ((Get-Content "$source.md5" -Raw).Trim() -split '\s+')[0].ToLower()
if ($expectedMD5 -notmatch '^[0-9a-f]{32}$') { throw 'Invalid MD5 manifest' }
if ((Get-FileHash $source -Algorithm MD5).Hash.ToLower() -ne $expectedMD5) { throw 'OSM MD5 mismatch' }
Write-Output "SOURCE MD5 VERIFIED: $expectedMD5"
$extract = Join-Path $extractDir 'lomma_lund-20261008.osm.pbf'
if (-not (Test-Path $extract)) {
    & $osmium extract -b '12.95,55.60,13.30,55.80' -s complete_ways $source -o "$extract.tmp" -f pbf
    if ($LASTEXITCODE -ne 0) { throw 'OSM extract failed' }
    Move-Item -LiteralPath "$extract.tmp" -Destination $extract
}
& $osmium fileinfo -e $extract
if ($LASTEXITCODE -ne 0) { throw 'OSM fileinfo failed' }
& $osmium check-refs $extract
if ($LASTEXITCODE -ne 0) { throw 'OSM check-refs failed' }
Get-FileHash $extract -Algorithm SHA256
