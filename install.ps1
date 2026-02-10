<#
.SYNOPSIS
    JianYing skill installation script (ASCII version)
    Deploys to $HOME\.gemini\antigravity\skills
    Supports Git-less installation via Multi-Proxy ZIP fallback
#>

$ErrorActionPreference = "Stop"

# ================= UI Helpers =================
function Print-Header {
    param($text)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "   $text" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Print-Step {
    param($text)
    Write-Host "[Executing] $text ..." -ForegroundColor Yellow
}

function Print-Success {
    param($text)
    Write-Host "[Success] $text" -ForegroundColor Green
}

function Print-Error {
    param($text)
    Write-Host "[Error] $text" -ForegroundColor Red
}

function Assert-Command {
    param($cmd)
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ================= Helper: Download and Extract ZIP =================
function Install-ProjectViaZip {
    param($Name, $RepoUrl, $TargetDir)

    # List of reliable GitHub proxies for China
    $Proxies = @(
        "https://ghproxy.cn/",
        "https://gh-proxy.com/",
        "https://mirror.ghproxy.com/",
        "https://github.moeyy.xyz/",
        "https://ghp.ci/"
    )

    $TempZip = Join-Path $env:TEMP "$Name.zip"
    $ExtractPath = Join-Path $env:TEMP "extract_$Name"
    $DownloadSuccess = $false

    # Force TLS 1.2
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    foreach ($Proxy in $Proxies) {
        $ZipUrl = "$($Proxy)$($RepoUrl.Replace('.git', '/archive/refs/heads/main.zip'))"
        Print-Step "Attempting download via: $Proxy"

        try {
            if (Test-Path $TempZip) { Remove-Item $TempZip -Force }
            Invoke-WebRequest -Uri $ZipUrl -OutFile $TempZip -UseBasicParsing -TimeoutSec 30
            if ((Get-Item $TempZip).Length -gt 10kb) {
                $DownloadSuccess = $true
                break
            }
        } catch {
            Write-Host "  Proxy $Proxy failed, trying next..." -ForegroundColor Gray
        }
    }

    if (-not $DownloadSuccess) {
        throw "Failed to download $Name ZIP from all available proxies. Please check your network or install Git."
    }

    try {
        Print-Step "Extracting $Name..."
        if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Force -Recurse }
        Expand-Archive -Path $TempZip -DestinationPath $ExtractPath -Force

        $SubFolder = Get-ChildItem -Path $ExtractPath -Directory | Select-Object -First 1
        if (Test-Path $TargetDir) { Remove-Item $TargetDir -Force -Recurse }
        Move-Item -Path $SubFolder.FullName -Destination $TargetDir -Force

        Print-Success "Installed $Name via ZIP fallback"
    } finally {
        if (Test-Path $TempZip) { Remove-Item $TempZip -Force }
        if (Test-Path $ExtractPath) { Remove-Item $ExtractPath -Force -Recurse }
    }
}

# ================= Main Logic =================
try {
    Print-Header "Antigravity Global Skill Installation"
    $HasGit = Assert-Command "git"
    if (-not $HasGit) {
        Write-Host "Note: Git not found. Using Multi-Proxy ZIP mode." -ForegroundColor Gray
    }

    # 1. Locate global skills directory
    $GlobalSkillsDir = "$HOME\.gemini\antigravity\skills"
    if (-not (Test-Path $GlobalSkillsDir)) {
        New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
    }

    $OriginalDir = Get-Location
    Set-Location $GlobalSkillsDir
    Print-Success "Located directory: $GlobalSkillsDir"

    # ================= Clone/Update Projects =================
    $Projects = @(
        @{ Name = "jianying-editor"; Repo = "https://github.com/luoluoluo22/jianying-editor-skill.git" },
        @{ Name = "antigravity-api-skill"; Repo = "https://github.com/luoluoluo22/antigravity-api-skill.git" },
        @{ Name = "grok-media-skill"; Repo = "https://github.com/luoluoluo22/grok-media-skill.git" }
    )

    foreach ($P in $Projects) {
        Print-Step "Deploying: $($P.Name)"
        $P_Path = Join-Path $GlobalSkillsDir $P.Name

        if ($HasGit) {
            if (-not (Test-Path $P_Path)) {
                git clone $P.Repo $P.Name
            } else {
                Push-Location $P_Path; git pull; Pop-Location
                Print-Success "Updated $($P.Name) via Git"
            }
        } else {
            Install-ProjectViaZip -Name $P.Name -RepoUrl $P.Repo -TargetDir $P_Path
        }
    }

    # ================= Install Python Dependencies =================
    Print-Header "Installing Python Dependencies"
    if (Assert-Command "pip") {
        pip install requests pymediainfo pillow uiautomation playwright pynput edge-tts --quiet
        Print-Success "Python environment ready"
    }

    # ================= Set Environment Variables =================
    $MainSkillPath = Join-Path $GlobalSkillsDir "jianying-editor"
    [Environment]::SetEnvironmentVariable("JY_SKILL_ROOT", $MainSkillPath, "User")
    $env:JY_SKILL_ROOT = $MainSkillPath
    Print-Success "Environment variable JY_SKILL_ROOT set"

    # ================= Sync to Editors =================
    Print-Header "Detecting Editors"
    $OtherEditors = @(
        @{ Name = "Trae"; Path = "$HOME\.trae\skills" },
        @{ Name = "Claude Code"; Path = "$HOME\.claude\skills" }
    )

    foreach ($Editor in $OtherEditors) {
        $EditorBase = Split-Path $Editor.Path
        if (Test-Path $EditorBase) {
            Print-Success "Found $($Editor.Name)"
            if (-not (Test-Path $Editor.Path)) {
                New-Item -ItemType Directory -Path $Editor.Path -Force | Out-Null
            }

            foreach ($P in $Projects) {
                $Source = Join-Path $GlobalSkillsDir $P.Name
                $Target = Join-Path $Editor.Path $P.Name
                if (Test-Path $Target) { Remove-Item $Target -Force -Recurse -ErrorAction SilentlyContinue }
                try {
                    New-Item -ItemType SymbolicLink -Path $Target -Value $Source -ErrorAction Stop | Out-Null
                    Print-Success "Linked $($P.Name) for $($Editor.Name)"
                } catch {
                    Print-Error "Link failed (Admin rights needed): $Target"
                }
            }
        }
    }

    Set-Location $OriginalDir
    Print-Header "Installation Finished!"

} catch {
    Print-Error "Error occurred: $_"
    if ($OriginalDir) { Set-Location $OriginalDir }
    exit 1
}
