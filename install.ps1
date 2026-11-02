# WorkBuddy Daily Credits - one-click installer (ASCII only on purpose,
# so Windows PowerShell 5.1 with a GBK code page does not garble this file).
# Usage: irm https://raw.githubusercontent.com/XQ-zheng/workbuddy-daily-credits/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$Repo      = "https://github.com/XQ-zheng/workbuddy-daily-credits.git"
$SkillName = "workbuddy-daily-credits"
$SkillsDir = Join-Path $env:USERPROFILE ".workbuddy\skills"
if ($env:WORKBUDDY_SKILLS_DIR) { $SkillsDir = $env:WORKBUDDY_SKILLS_DIR }
$Dest = Join-Path $SkillsDir $SkillName

Write-Host "==> install dir: $Dest"

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $gitCmd) {
    Write-Host "!! git not found. Install git first: https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $SkillsDir)) { New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null }

if (Test-Path (Join-Path $Dest ".git")) {
    Write-Host "==> already installed, updating"
    & git -C $Dest pull --ff-only
} elseif (Test-Path $Dest) {
    Write-Host "!! $Dest exists but is not a git repo. Move it away and retry." -ForegroundColor Red
    exit 1
} else {
    Write-Host "==> cloning"
    & git clone --depth 1 $Repo $Dest
}

foreach ($f in @("SKILL.md", "scripts\claim_all.py", "scripts\wb_auth.py")) {
    if (-not (Test-Path (Join-Path $Dest $f))) {
        Write-Host "!! missing file: $f - install incomplete" -ForegroundColor Red
        exit 1
    }
}

$Py = $null
foreach ($c in @("python", "python3", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $Py = $c; break }
}

Write-Host ""
Write-Host "OK - installed" -ForegroundColor Green
if ($null -ne $Py) {
    & $Py (Join-Path $Dest "scripts\claim_all.py") --version
    Write-Host ""
    Write-Host "First-time setup (once):"
    Write-Host "  cd `"$Dest`""
    Write-Host "  $Py scripts\wb_auth.py --export-rt --save     # older clients"
    Write-Host "  $Py scripts\wb_auth.py --setup-rt '<token>'   # 5.6.2+ manual"
    Write-Host "  $Py scripts\claim_all.py --check             # read-only check"
} else {
    Write-Host "!! python not found. Install Python 3.8+ first." -ForegroundColor Red
}
Write-Host ""
Write-Host "Then just say 'again claim my points' style prompt in WorkBuddy,"
Write-Host "or ask it to set up a daily 08:50 automation that reports back."
