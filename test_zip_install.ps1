# Test script for Multi-Proxy ZIP download strategy
$ErrorActionPreference = "Stop"

function Print-Step { param($text); Write-Host "[Test] $text ..." -ForegroundColor Yellow }
function Print-Success { param($text); Write-Host "[Done] $text" -ForegroundColor Green }

function Test-MultiProxyZipInstall {
    param($Name, $RepoUrl, $TargetDir)

    # Updated proxy list
    $Proxies = @(
        "https://ghproxy.cn/",
        "https://gh-proxy.com/",
        "https://mirror.ghproxy.com/",
        "https://github.moeyy.xyz/",
        "https://ghp.ci/"
    )

    $TempZip = Join-Path $env:TEMP "$Name-test.zip"
    $ExtractPath = Join-Path $env:TEMP "extract_test_$Name"
    $DownloadSuccess = $false

    # Force TLS 1.2
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    try {
        if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Force -Recurse }
        if (Test-Path $TargetDir) { Remove-Item $TargetDir -Force -Recurse }

        # 1. Download Attempt
        foreach ($Proxy in $Proxies) {
            $ZipUrl = "$($Proxy)$($RepoUrl.Replace('.git', '/archive/refs/heads/main.zip'))"
            Print-Step "Attempting download via: $Proxy"

            try {
                if (Test-Path $TempZip) { Remove-Item $TempZip -Force }
                Invoke-WebRequest -Uri $ZipUrl -OutFile $TempZip -UseBasicParsing -TimeoutSec 20

                # Check if file is valid (not a tiny error page)
                if ((Get-Item $TempZip).Length -gt 10kb) {
                    $DownloadSuccess = $true
                    Print-Success "Download successful via $Proxy"
                    break
                }
            } catch {
                Write-Host "  Proxy $Proxy failed or timed out." -ForegroundColor Gray
            }
        }

        if (-not $DownloadSuccess) {
            throw "All proxies failed. Please check your internet connection."
        }

        # 2. Extract
        Print-Step "Extracting ZIP..."
        Expand-Archive -Path $TempZip -DestinationPath $ExtractPath -Force

        # 3. Locate folder
        $SubFolder = Get-ChildItem -Path $ExtractPath -Directory | Select-Object -First 1

        # 4. Move to target
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
        Move-Item -Path "$($SubFolder.FullName)\*" -Destination $TargetDir -Force

        Print-Success "Successfully deployed to $TargetDir"

        # 5. Verify content
        $Files = Get-ChildItem $TargetDir
        Write-Host "Found $($Files.Count) items in target directory." -ForegroundColor Cyan
    }
    finally {
        if (Test-Path $TempZip) { Remove-Item $TempZip -Force }
        if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Force -Recurse }
    }
}

# Run test
$TestPath = Join-Path (Get-Location) "test_deploy_zip"
Test-MultiProxyZipInstall -Name "jianying-editor" -RepoUrl "https://github.com/luoluoluo22/jianying-editor-skill.git" -TargetDir $TestPath
