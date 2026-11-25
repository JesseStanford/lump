# update.ps1 - bring local folders up to date with GitHub, without git.
#
# Put this file in the folder that should CONTAIN the repo folder, then run:
#     .\update.ps1
#
# It downloads the branch as a zip, unpacks it, and mirrors it into
# <this folder>\lump. "Mirror" means the local folder ends up identical to GitHub:
# changed files are overwritten and local files that are not on GitHub are DELETED,
# except inside the folders named in $keep. Keep your own working files in
# lump\work, lump\data, lump\runs or lump\export.
#
# One-time setup: a GitHub token in the user environment variable GITHUB_TOKEN
# (see the notes at the bottom of this file).

# ---------------- CHANGE THESE FOUR LINES FOR ANOTHER PROJECT ----------------
$owner  = "JesseStanford"                  # the account or organisation that owns the repos
$repos  = @("lump")                        # one or more repo names
$branch = "main"                           # the branch to download
$keep   = @("data", "runs", "export", "work", ".venv", "__pycache__")   # local-only folder names, never touched
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"            # stop at the first error instead of carrying on
$root = $PSScriptRoot                      # the folder this script sits in

# 1. Find the token: this session first, then the saved user variable.
$token = $env:GITHUB_TOKEN
if (-not $token) { $token = [Environment]::GetEnvironmentVariable("GITHUB_TOKEN", "User") }
if (-not $token) { throw "No GITHUB_TOKEN set. See the one-time setup at the bottom of update.ps1." }
$headers = @{ Authorization = "Bearer $token"; "User-Agent" = "repo-update" }

foreach ($repo in $repos) {
    # 2. A clean temporary folder for the download.
    $tmp = Join-Path $env:TEMP "$repo-update"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    New-Item -ItemType Directory $tmp | Out-Null
    $zip = Join-Path $tmp "$branch.zip"

    # 3. Download the branch as a zip from the GitHub API and unpack it.
    Write-Host "Downloading $repo ..."
    Invoke-WebRequest -Uri "https://api.github.com/repos/$owner/$repo/zipball/$branch" -Headers $headers -OutFile $zip
    Expand-Archive $zip -DestinationPath $tmp
    $src = Get-ChildItem $tmp -Directory | Select-Object -First 1   # the zip holds one folder: <owner>-<repo>-<commit>
    $sha = ($src.Name -split "-")[-1]                               # the commit id is the last part of its name

    # 4. Mirror that folder into <root>\<repo>, leaving the $keep folders alone.
    $dst = Join-Path $root $repo
    if (-not (Test-Path $dst)) { New-Item -ItemType Directory $dst | Out-Null }
    robocopy $src.FullName $dst /MIR /XD $keep /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $repo (code $LASTEXITCODE)" }   # codes 0-7 are success

    # 5. Record which commit is now on disk, and clean up.
    Set-Content (Join-Path $dst "VERSION.txt") "$repo $branch @ $sha  (updated $(Get-Date -Format s))"
    Remove-Item $tmp -Recurse -Force
    Write-Host "  $repo is now at $sha"
}
Write-Host "Done."

# ---------------------------- ONE-TIME SETUP ----------------------------------
# 1. On github.com: Settings > Developer settings > Personal access tokens >
#    Fine-grained tokens > Generate new token. Give it access to the repos above
#    with the permission "Contents: Read-only". Copy the token.
# 2. In PowerShell, once (replace the text in quotes with your token):
#        [Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "paste-token-here", "User")
#    Then close and reopen PowerShell.
# 3. If PowerShell refuses to run the script, once:
#        Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# A token is needed for private repos. For a public repo you can delete the three
# token lines and the -Headers part, but an existing token works for both.
