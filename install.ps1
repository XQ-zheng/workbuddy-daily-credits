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
    if ($LASTEXITCODE -ne 0) { throw "Git update failed; no setup was run." }
} elseif (Test-Path $Dest) {
    Write-Host "!! $Dest exists but is not a git repo. Move it away and retry." -ForegroundColor Red
    exit 1
} else {
    Write-Host "==> cloning"
    & git clone --depth 1 $Repo $Dest
    if ($LASTEXITCODE -ne 0) { throw "Git clone failed; no setup was run." }
}

foreach ($f in @("SKILL.md", "scripts\claim_all.py", "scripts\wb_auth.py", "scripts\setup_auth.py")) {
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
    if ($LASTEXITCODE -ne 0) { throw "Python version check failed." }
    Write-Host ""
    Write-Host "==> Safe local setup and activity check (non-interactive)"
    & $Py (Join-Path $Dest "scripts\setup_auth.py") --non-interactive
    $SetupCode = $LASTEXITCODE
    if ($SetupCode -eq 0) {
        Write-Host "Authorization and activity check passed. No points were claimed." -ForegroundColor Green
    } else {
        Write-Host "Installed; authorization/check is incomplete. See the masked status above."
        Write-Host "Use official WorkBuddy sign-in if available; this script does not generate a login QR code."
        Write-Host "If you already have your own token, enter it only in the local hidden-input window:"
        Write-Host "  $Py `"$(Join-Path $Dest 'scripts\setup_auth.py')`" --gui"
        Write-Host "Never paste tokens into chat, command arguments, screenshots or logs."
    }
} else {
    Write-Host "!! python not found. Install Python 3.8+ first." -ForegroundColor Red
}
Write-Host ""
Write-Host "Then just say 'again claim my points' style prompt in WorkBuddy,"
Write-Host "or ask it to set up a daily 08:50 automation that reports back."
