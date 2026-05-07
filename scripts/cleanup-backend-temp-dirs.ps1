param(
  [switch]$DryRun,
  [switch]$SkipPermissionRepair
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $repoRoot "backend"

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $DryRun -and -not (Test-IsAdministrator)) {
  Write-Host "Administrator permission is required to repair ACLs and move protected temp directories to Recycle Bin."
  Write-Host "Requesting UAC elevation..."

  $argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$PSCommandPath`""
  )

  if ($SkipPermissionRepair) {
    $argList += "-SkipPermissionRepair"
  }

  Start-Process -FilePath "powershell.exe" -ArgumentList $argList -Verb RunAs -WorkingDirectory $repoRoot
  exit 0
}

if (-not (Test-Path -LiteralPath $backend -PathType Container)) {
  throw "Backend directory not found: $backend"
}

$targets = @(
  Get-ChildItem -LiteralPath $backend -Force -Directory |
    Where-Object { $_.Name -like "tmp*" } |
    Sort-Object Name
)

$resolved = @($targets | ForEach-Object { Resolve-Path -LiteralPath $_.FullName })

foreach ($path in $resolved) {
  $value = $path.Path
  if (-not ($value.StartsWith($backend + [IO.Path]::DirectorySeparatorChar))) {
    throw "Refuse outside backend directory: $value"
  }
}

if ($resolved.Count -eq 0) {
  Write-Host "No backend/tmp* directories found."
  exit 0
}

Write-Host "Target backend/tmp* directories:"
$resolved | ForEach-Object { Write-Host (" - " + $_.Path) }

if ($DryRun) {
  Write-Host ""
  Write-Host "Dry run only. Re-run without -DryRun to send these directories to Windows Recycle Bin."
  exit 0
}

Add-Type -AssemblyName Microsoft.VisualBasic

function Send-ToRecycleBin {
  param([Parameter(Mandatory = $true)][string]$Path)

  [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
    $Path,
    [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
    [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
  )

  return -not (Test-Path -LiteralPath $Path)
}

function Repair-TempDirectoryAcl {
  param([Parameter(Mandatory = $true)][string]$Path)

  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  Write-Host ("Repair permissions: {0}" -f $Path)

  & takeown.exe /F $Path /R /D Y | Out-Null
  & icacls.exe $Path /grant "${identity}:(OI)(CI)F" /T /C | Out-Null
  & attrib.exe -R -S -H $Path /S /D | Out-Null
}

$moved = 0
$repaired = 0
$failed = New-Object System.Collections.Generic.List[string]

foreach ($path in $resolved) {
  try {
    if (Send-ToRecycleBin -Path $path.Path) {
      $moved += 1
      continue
    }

    if (-not $SkipPermissionRepair) {
      Repair-TempDirectoryAcl -Path $path.Path
      $repaired += 1
      if (Send-ToRecycleBin -Path $path.Path) {
        $moved += 1
        continue
      }
    }

    $failed.Add($path.Path)
  } catch {
    if (-not $SkipPermissionRepair -and (Test-Path -LiteralPath $path.Path)) {
      try {
        Repair-TempDirectoryAcl -Path $path.Path
        $repaired += 1
        if (Send-ToRecycleBin -Path $path.Path) {
          $moved += 1
          continue
        }
      } catch {
        $failed.Add(("{0} :: {1}" -f $path.Path, $_.Exception.Message))
        continue
      }
    }
    $failed.Add(("{0} :: {1}" -f $path.Path, $_.Exception.Message))
  }
}

Write-Host ""
Write-Host ("Moved to Recycle Bin: {0}" -f $moved)
Write-Host ("Permission repairs attempted: {0}" -f $repaired)

if ($failed.Count -gt 0) {
  Write-Host ("Failed: {0}" -f $failed.Count)
  $failed | ForEach-Object { Write-Host (" - " + $_) }
  Write-Host ""
  Write-Host "If failures remain, run PowerShell as Administrator and execute the same command again."
  exit 1
}

Write-Host "Done."
