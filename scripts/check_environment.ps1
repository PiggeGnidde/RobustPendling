# Read-only diagnostics: no installation, file writes or environment changes.
[CmdletBinding()]
param()

function Show-Tool {
    param(
        [string]$Label,
        [string[]]$Names,
        [string[]]$VersionArguments = @('--version')
    )

    Write-Output "`n=== $Label ==="
    $seen = @{}
    $found = $false
    $working = $false
    foreach ($name in $Names) {
        $commands = @(Get-Command $name -All -CommandType Application -ErrorAction SilentlyContinue)
        foreach ($command in $commands) {
            $path = $command.Source
            if ($seen.ContainsKey($path)) { continue }
            $seen[$path] = $true
            $found = $true
            Write-Output "Path: $path"
            try {
                # Java prints its version to stderr; collect both streams.
                $version = & $path @VersionArguments 2>&1
                $exitCode = $LASTEXITCODE
                foreach ($line in $version) { Write-Output "$line" }
                if ($exitCode -eq 0) {
                    $working = $true
                } else {
                    Write-Output "Version command failed (exit code $exitCode)."
                }
            } catch {
                Write-Output "Could not run: $($_.Exception.Message)"
            }
        }
    }
    if (-not $found) {
        Write-Output 'Not found in PATH. An installation elsewhere is not ruled out.'
    } elseif (-not $working) {
        Write-Output 'Found in PATH, but no candidate returned a successful version check.'
    } else {
        Write-Output 'Available: at least one successful version check.'
    }
}

Write-Output 'RobustPendling environment check (read-only; tools resolved from PATH)'
Show-Tool -Label 'Python' -Names @('python', 'python3')
Show-Tool -Label 'Java' -Names @('java') -VersionArguments @('-version')
Show-Tool -Label 'Git' -Names @('git')
Show-Tool -Label 'GDAL' -Names @('gdalinfo', 'ogrinfo', 'gdal')
