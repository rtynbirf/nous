<#
НОУС · src/forge/forge.ps1 — точка входа форжа на Windows-хосте (ТЗ §1).
Тонкий диспетчер: базовые сырые факты хоста (выжимка systeminfo: версия ОС,
архитектура, диск каталога вывода — ТОЛЬКО чтение) → вызов win/build.ps1.

Запуск (pwsh 7, Windows-хост владельца):
  pwsh -NoProfile -File src/forge/forge.ps1 -Target win -TargetDir D:\out
Тесты без скачивания:
  pwsh -NoProfile -File src/forge/forge.ps1 -Target win -SkipDownload -IsoPath C:\iso\win11.iso

Linux-ветка — forge.sh (субъект forge-builder-linux, фаза R4); этим диспетчером не запускается.
#>
[CmdletBinding()]
param(
  # Цель форжа; Windows-хост исполняет только «win»
  [string]$Target = 'win',
  [string]$TargetDir = '',
  [string]$Locale = 'ru-RU',
  [switch]$SkipDownload,
  [string]$IsoPath = ''
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

function Say { param([string]$m) Write-Host "[forge] $m" }

$repoRoot = (Resolve-Path (Join-Path (Join-Path $PSScriptRoot '..') '..')).Path
Say "НОУС-форж · точка входа Windows-хоста (ТЗ §1) · цель: $Target"
if ($Target -ne 'win') {
  Say "FAIL: диспетчер Windows-хоста исполняет только -Target win; linux — src/forge/forge.sh (фаза R4, отдельный субъект)"
  exit 1
}

# --- Probe-подсказка (аксиома «карта=территория»): базовые сырые факты хоста.
# ТОЛЬКО чтение: ничего не изменяем, никуда не пишем. src/forge/probe/probe.sh —
# bash-модуль Linux-ветки (спека 02, фаза R2): на Windows-хосте не применим,
# поэтому выжимка снимается штатным systeminfo этой же машины.
$probeScript = Join-Path $repoRoot 'src\forge\probe\probe.sh'
$bashCmd = Get-Command bash -ErrorAction SilentlyContinue
if ((Test-Path -LiteralPath $probeScript) -and $bashCmd) {
  Say "probe.sh найден ($probeScript), но bash-probe применим к Linux-хостам (спека 02); ниже — базовые сырые факты Windows"
} else {
  Say "probe.sh отсутствует или не применим (фаза R2 — отдельный тикет); базовые сырые факты:"
}

# Архитектура — сырой факт среды процесса
Write-Host "PROCESSOR_ARCHITECTURE=$env:PROCESSOR_ARCHITECTURE"

# Выжимка systeminfo: печатаются НЕПОВРЕЖДЁННЫЕ строки вывода (без пересказа,
# аксиома 2). Метки на обоих языках локализации Windows (en/ru).
try {
  $sysinfo = & systeminfo.exe *>&1
  $picked = @($sysinfo | Where-Object {
    "$_" -match '^\s*(OS Name|OS Version|OS Configuration|System Type|Название ОС|Версия ОС|Тип системы)\s*:'
  })
  foreach ($line in $picked) { Write-Host "$line" }
  if ($picked.Count -eq 0) {
    Say "WARN: выжимка systeminfo пуста (нестандартная локализация вывода) — версия ОС из среды:"
    Write-Host "OSVersion=$([System.Environment]::OSVersion.VersionString)"
  }
} catch {
  Say "WARN: systeminfo недоступен на этом хосте: $_"
}

# Диск каталога вывода: факт читается (DriveInfo), записи не выполняется.
# Каталог ещё не создаётся — это делает build.ps1; здесь только наблюдение.
$probeTarget = $TargetDir
if (-not $probeTarget) { $probeTarget = $env:NOUS_TARGET_DIR }
if (-not $probeTarget) { $probeTarget = Join-Path $repoRoot 'dist' }
try {
  $driveRoot = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($probeTarget))
  $di = New-Object System.IO.DriveInfo($driveRoot)
  Write-Host ("TargetDir={0}; диск={1}; файловая система={2}; свободно={3:N1} ГиБ из {4:N1} ГиБ" -f
    $probeTarget, $di.Name, $di.DriveFormat, ($di.AvailableFreeSpace / 1GB), ($di.TotalSize / 1GB))
} catch {
  Write-Host "TargetDir=$probeTarget; диск: факт недоступен ($_)"
}

# --- Диспетчеризация: вызов build.ps1 отдельным pwsh-процессом — честные коды
# возврата ($LASTEXITCODE) и изоляция состояния.
$buildScript = Join-Path $PSScriptRoot 'win\build.ps1'
if (-not (Test-Path -LiteralPath $buildScript)) { Say "FAIL: нет конвейера: $buildScript"; exit 1 }
$pwshExe = if ($PSHOME -and (Test-Path (Join-Path $PSHOME 'pwsh.exe'))) { Join-Path $PSHOME 'pwsh.exe' } else { 'pwsh' }
$argList = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $buildScript)
if ($TargetDir) { $argList += @('-TargetDir', $TargetDir) }
if ($Locale) { $argList += @('-Locale', $Locale) }
if ($IsoPath) { $argList += @('-IsoPath', $IsoPath) }
if ($SkipDownload) { $argList += '-SkipDownload' }
Say "вызов: $pwshExe $($argList -join ' ')"
& $pwshExe @argList
exit $LASTEXITCODE
