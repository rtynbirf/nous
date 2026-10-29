<#
НОУС · src/forge/win/build.ps1 — главный конвейер Windows-ветки форжа.
Спека: docs/spec/implementation/03-windows-iso.md · ТЗ §1/§3 · safe-defaults (спека 06)

Запуск на Windows-хосте владельца (pwsh 7):
  pwsh -NoProfile -File src/forge/win/build.ps1 -TargetDir D:\out
Точка входа верхнего уровня: pwsh -NoProfile -File src/forge/forge.ps1 -Target win
Тесты без скачивания (уже скачанный ISO):
  pwsh -NoProfile -File src/forge/win/build.ps1 -TargetDir D:\out -SkipDownload -IsoPath C:\iso\win11.iso

Фазы: fetch → extract → render → inject → build → verify → emit.
Каждая фаза печатает сырые выводы команд (аксиома «карта=территория») в stdout и в
build-log.txt рядом с артефактом. Запись — только во временный каталог и NOUS_TARGET_DIR
(-TargetDir). Носители хоста не трогаются; WillWipeDisk=false проверяется дважды
(после render и перед build) — инвариант manifests/safe-defaults.yaml.
#>
[CmdletBinding()]
param(
  # Каталог вывода артефактов (NOUS_TARGET_DIR; по умолчанию $env:NOUS_TARGET_DIR или <репо>\dist)
  [string]$TargetDir = "",
  # Локаль / язык интерфейса / часовой пояс / индекс редакции Pro в install.wim.
  # Индекс по умолчанию 6 — типовой для Windows 11 Pro на многосборочном носителе;
  # сверьте своим носителем: DISM /Get-WimInfo /WimFile:<iso-корень>\sources\install.wim
  [string]$Locale = "ru-RU",
  [string]$UiLanguage = "ru-RU",
  [string]$TimeZone = "Russian Standard Time",
  [string]$KeyIndex = "6",
  # Не скачивать: использовать уже скачанный ISO (для тестов/повторов)
  [switch]$SkipDownload,
  [string]$IsoPath = "",
  # Явный путь к oscdimg.exe (иначе — поиск в стандартных местах Windows ADK)
  [string]$OscdimgPath = "",
  # Релиз для Fido -Rel (пробрасывается в fetch-fido.ps1)
  [string]$FidoRelease = "Latest"
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$script:RepoRoot = (Resolve-Path (Join-Path (Join-Path $PSScriptRoot '..') '..')).Path
$script:DateTag = Get-Date -Format 'yyyy-MM-dd'
$script:TimeTag = Get-Date -Format 'yyyyMMdd-HHmmss'

# --- Каталог вывода: NOUS_TARGET_DIR (спеки 03/05) → <дата> ---
if (-not $TargetDir) { $TargetDir = $env:NOUS_TARGET_DIR }
if (-not $TargetDir) { $TargetDir = Join-Path $script:RepoRoot 'dist' }
$script:EmitDir = Join-Path $TargetDir ("win\" + $script:DateTag)
New-Item -ItemType Directory -Force -Path $script:EmitDir | Out-Null

# --- Временный каталог конвейера; лог сразу пишем в EmitDir (лог живёт рядом с артефактом) ---
$script:TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("nous-build-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $script:TempDir | Out-Null
$script:LogPath = Join-Path $script:EmitDir 'build-log.txt'
Remove-Item -LiteralPath $script:LogPath -ErrorAction SilentlyContinue

function Log { param([string]$Message)
  $line = "[forge] $Message"
  Write-Host $line
  Add-Content -LiteralPath $script:LogPath -Value $line -Encoding utf8
}
function Log-Raw { param([string]$Line)   # сырые выводы команд — без префикса
  Write-Host $Line
  Add-Content -LiteralPath $script:LogPath -Value $Line -Encoding utf8
}
function Die {
  param([string]$Message)
  Log "FAIL: $Message"
  Write-Host "[forge] лог: $($script:LogPath)"
  exit 1
}
function Assert-NativeExit {
  param([string]$What)
  if ($LASTEXITCODE -ne 0) { Die "$What завершился с кодом $LASTEXITCODE — сырой вывод выше" }
}

# --- Инвариант safe-defaults (спека 06): wipe запрещён. Гейт вызывается ДВАЖДЫ:
# после render и прямо перед oscdimg — «одна защита — не защита» (спека 03).
# Проверяем ОБЕ формы: элементную (реальная схема unattend) и строку с кавычками
# (на случай копипасты из примеров) — инверсия дефолта не проходит ни в каком виде.
function Assert-AutounattendInvariant {
  param([Parameter(Mandatory)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { Die "нет файла ответа установки: $Path" }
  $xml = Get-Content -LiteralPath $Path -Raw
  if ($xml -match 'WillWipeDisk\s*=\s*"true"') {
    Die "инвариант oobe_will_wipe_disk=false нарушен: в $Path есть WillWipeDisk=«true» — сборка запрещена (safe-defaults, спека 06)"
  }
  if ($xml -match '<WillWipeDisk>\s*true\s*</WillWipeDisk>') {
    Die "инвариант oobe_will_wipe_disk=false нарушен: в $Path есть <WillWipeDisk>true</WillWipeDisk> — сборка запрещена (safe-defaults, спека 06)"
  }
  if ($xml -notmatch '<WillWipeDisk>\s*false\s*</WillWipeDisk>') {
    Die "в $Path нет явного <WillWipeDisk>false</WillWipeDisk> — сборка запрещена (safe-defaults, спека 06)"
  }
  if ($xml -match '<(PlainText|Password)[\s>]') {
    Die "в $Path обнаружены Password/PlainText — НОУС не вшивает пароли (ТЗ §7)"
  }
  Log "инвариант safe-defaults: <WillWipeDisk>false</WillWipeDisk> есть, wipe=«true»/паролей нет — ОК ($Path)"
}

Log "НОУС-форж · Windows-ветка · спека 03 · тикет 0003"
Log "репозиторий: $script:RepoRoot"
Log "emit (NOUS_TARGET_DIR): $script:EmitDir"
Log "temp: $script:TempDir"
Log "лог сырых команд: $script:LogPath"
Log ("параметры: Locale=$Locale UiLanguage=$UiLanguage TimeZone='$TimeZone' KeyIndex=$KeyIndex SkipDownload=$SkipDownload")

# ============================== ФАЗА fetch ==============================
Log "--- фаза fetch: получение образа по пинам (Fido) ---"
$script:FetchReport = $null
if ($SkipDownload) {
  if (-not $IsoPath) { Die "-SkipDownload требует -IsoPath (путь к уже скачанному ISO)" }
  if (-not (Test-Path -LiteralPath $IsoPath)) { Die "нет ISO: $IsoPath" }
  Log "SkipDownload: используем готовый ISO: $IsoPath"
} else {
  $fetchScript = Join-Path $PSScriptRoot 'fetch-fido.ps1'
  if (-not (Test-Path -LiteralPath $fetchScript)) { Die "нет fetch-fido.ps1: $fetchScript" }
  $pwshExe = if ($PSHOME -and (Test-Path (Join-Path $PSHOME 'pwsh.exe'))) { Join-Path $PSHOME 'pwsh.exe' } else { 'pwsh' }
  $fetchArgs = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
    '-File', $fetchScript, '-OutputDir', $script:TempDir,
    # локаль передаётся как есть: fetch-fido.ps1 сам нормализует её в официальное имя языка Fido
    '-Language', $UiLanguage, '-FidoRelease', $FidoRelease)
  Log ("вызов: $pwshExe " + ($fetchArgs -join ' '))
  $fetchOut = & $pwshExe @fetchArgs *>&1
  $fetchExit = $LASTEXITCODE
  foreach ($line in @($fetchOut)) { Log ("fetch-fido| " + "$line") }
  if ($fetchExit -ne 0) { Die "fetch-fido.ps1 завершился с кодом $fetchExit" }
  $reportPath = Join-Path $script:TempDir 'fetch-report.json'
  if (Test-Path -LiteralPath $reportPath) {
    $script:FetchReport = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
  } else {
    # страховка: последний JSON-объект в stdout fetch-fido
    $jsonLine = @($fetchOut) | Where-Object { "$_" -match '^\s*\{' } | Select-Object -Last 1
    if (-not $jsonLine) { Die "fetch-fido не оставил ни fetch-report.json, ни JSON в stdout" }
    $script:FetchReport = "$jsonLine" | ConvertFrom-Json
  }
  $IsoPath = $script:FetchReport.iso_path
  Log ("fetch-отчёт: source_url={0} sha256={1} fido_tag={2} tofu_fixed={3}" -f `
    $script:FetchReport.source_url, $script:FetchReport.sha256, $script:FetchReport.fido_tag, $script:FetchReport.tofu_fixed)
}
$script:IsoPath = (Resolve-Path -LiteralPath $IsoPath).Path
$isoItem = Get-Item -LiteralPath $script:IsoPath
$isoSha256 = (Get-FileHash -LiteralPath $script:IsoPath -Algorithm SHA256).Hash.ToLowerInvariant()
Log ("сырой факт: ISO {0}; размер {1} байт; SHA256 {2}" -f $script:IsoPath, $isoItem.Length, $isoSha256)

# ============================== ФАЗА extract ==============================
Log "--- фаза extract: Mount-DiskImage + Copy-Item во временный каталог ---"
$extractDir = Join-Path $script:TempDir 'iso-extract'
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
$mounted = $null
try {
  Log "Mount-DiskImage -ImagePath $script:IsoPath -PassThru"
  $mounted = Mount-DiskImage -ImagePath $script:IsoPath -PassThru
  $volume = $mounted | Get-Volume
  Log ("сырой факт: Get-Volume → DriveLetter={0} FileSystem={1} Size={2}" -f $volume.DriveLetter, $volume.FileSystem, $volume.Size)
  $srcRoot = "$($volume.DriveLetter):\"
  Log "Copy-Item $srcRoot* → $extractDir (несколько ГиБ)"
  Copy-Item -Path (Join-Path $srcRoot '*') -Destination $extractDir -Recurse -Force
} finally {
  if ($mounted) {
    try { Dismount-DiskImage -ImagePath $script:IsoPath | Out-Null; Log "Dismount-DiskImage — ОК" }
    catch { Log "WARN: Dismount-DiskImage не удался: $_ (образ может остаться смонтированным)" }
  }
}
$files = @(Get-ChildItem -LiteralPath $extractDir -Recurse -File)
$sum = ($files | Measure-Object -Sum Length).Sum
Log ("сырой факт: извлечено {0} файлов, {1} байт" -f $files.Count, $sum)

# Пути загрузочных образов El Torito для -bootdata: BIOS (etfsboot.com) и UEFI (efisys.bin)
$etfsboot = Join-Path $extractDir 'boot\etfsboot.com'
$efisys = Join-Path $extractDir 'efi\microsoft\boot\efisys.bin'
if (-not (Test-Path -LiteralPath $etfsboot)) {
  $bootDir = Join-Path $extractDir 'boot'
  Log ("boot/: " + (@(Get-ChildItem -LiteralPath $bootDir -ErrorAction SilentlyContinue | ForEach-Object Name) -join ', '))
  Die "не найден $etfsboot — структура образа не совпала с картой"
}
if (-not (Test-Path -LiteralPath $efisys)) {
  $efiDir = Join-Path $extractDir 'efi\microsoft\boot'
  Log ("efi/microsoft/boot/: " + (@(Get-ChildItem -LiteralPath $efiDir -ErrorAction SilentlyContinue | ForEach-Object Name) -join ', '))
  Die "не найден $efisys — структура образа не совпала с картой"
}
Log "BIOS-загрузчик: $etfsboot ($((Get-Item -LiteralPath $etfsboot).Length) байт)"
Log "UEFI-загрузчик: $efisys ($((Get-Item -LiteralPath $efisys).Length) байт)"

# ============================== ФАЗА render ==============================
Log "--- фаза render: подстановка токенов в autounattend.template.xml ---"
$templatePath = Join-Path $script:RepoRoot 'src\forge\win\autounattend.template.xml'
$template = Get-Content -LiteralPath $templatePath -Raw
# Нативный string replace (без regex). Значения — ТОЛЬКО параметры скрипта;
# паролей, учётных записей и серийников в значениях нет по определению (ТЗ §7).
$rendered = $template.Replace('__LOCALE__', $Locale).Replace('__UI_LANG__', $UiLanguage).Replace('__TIMEZONE__', $TimeZone).Replace('__KEY_INDEX__', $KeyIndex)
$leftover = @([regex]::Matches($rendered, '__[A-Z0-9_]+__') | ForEach-Object { $_.Value } | Select-Object -Unique)
if ($leftover.Count -gt 0) { Die "в отрендеренном XML остались неизвестные токены: $($leftover -join ', ')" }
$renderedPath = Join-Path $script:TempDir 'autounattend.xml'
Set-Content -LiteralPath $renderedPath -Value $rendered -Encoding utf8BOM
Log "render: $templatePath → $renderedPath ($((Get-Item -LiteralPath $renderedPath).Length) байт)"
Assert-AutounattendInvariant $renderedPath
Log "сырой отрендеренный XML (далее — в лог):"
foreach ($xmlLine in ($rendered -split "`r?`n")) { Log-Raw $xmlLine }

# ============================== ФАЗА inject ==============================
Log "--- фаза inject: autounattend.xml в корень дерева образа ---"
$injectedPath = Join-Path $extractDir 'autounattend.xml'
Copy-Item -LiteralPath $renderedPath -Destination $injectedPath -Force
$inj = Get-Item -LiteralPath $injectedPath
Log ("сырой факт: {0}; размер {1} байт; SHA256 {2}" -f $inj.FullName, $inj.Length, (Get-FileHash -LiteralPath $injectedPath -Algorithm SHA256).Hash.ToLowerInvariant())

# ============================== ФАЗА build ==============================
Log "--- фаза build: oscdimg с двойной загрузочной записью (BIOS+UEFI) ---"
# Второй гейт инварианта — прямо перед сборкой (спека 03: «одна защита — не защита»).
Assert-AutounattendInvariant $injectedPath

if ($OscdimgPath) {
  $oscdimgExe = $OscdimgPath
} else {
  $adkParents = @(${env:ProgramFiles(x86)}, $env:ProgramFiles) | Where-Object { $_ }
  $candidates = @($adkParents | ForEach-Object {
    Join-Path $_ 'Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe'
  })
  $oscdimgExe = @($candidates | Where-Object { Test-Path -LiteralPath $_ }) | Select-Object -First 1
  if (-not $oscdimgExe) {
    Die "oscdimg не найден; установите Windows ADK (функция Deployment Tools) или укажите -OscdimgPath; см. src/forge/win/README.md"
  }
}
$oscdimgVersion = (Get-Item -LiteralPath $oscdimgExe).VersionInfo.FileVersion
Log "oscdimg: $oscdimgExe (версия: $oscdimgVersion)"

# Эталон аргументной строки — спека 03. -bootdata передаётся ОДНИМ аргументом:
# сегменты p0 (BIOS/El Torito, etfsboot.com) и pEF (UEFI, efisys.bin) склеены '#'.
# Кавычки ВНУТРИ значения недопустимы: pwsh экранирует их как \" и oscdimg
# не распарсит; аргумент с пробелами pwsh заключает в кавычки целиком сам.
$bootData = "2#p0,e,b$etfsboot#pEF,e,b$efisys"
$outIso = Join-Path $script:TempDir ("nous-win11-{0}-{1}.iso" -f $Locale.ToLowerInvariant(), $script:TimeTag)
$oscdimgArgs = @('-m', '-o', '-u2', '-udfver102', "-bootdata:$bootData", $extractDir, $outIso)
$cmdline = $oscdimgExe + ' ' + (($oscdimgArgs | ForEach-Object { if ("$_" -match '\s') { '"' + $_ + '"' } else { "$_" } }) -join ' ')
Log "КОМАНДА (печатаем до исполнения): $cmdline"
& $oscdimgExe @oscdimgArgs *>&1 | ForEach-Object { Log-Raw "$_" }
Assert-NativeExit 'oscdimg'
Log ("сырой факт: выход {0}; размер {1} байт" -f $outIso, (Get-Item -LiteralPath $outIso).Length)

# ============================== ФАЗА verify ==============================
Log "--- фаза verify: xorriso-гейты (если найдены bash+xorriso) или честные raw-факты ---"
$outIsoItem = Get-Item -LiteralPath $outIso
$outSha256 = (Get-FileHash -LiteralPath $outIso -Algorithm SHA256).Hash.ToLowerInvariant()
Log ("сырой факт: размер {0} байт; SHA256 {1}" -f $outIsoItem.Length, $outSha256)

$bashCmd = Get-Command bash -ErrorAction SilentlyContinue
$haveXorriso = $false
if ($bashCmd) {
  if ($bashCmd.Source -like '*System32\bash.exe') {
    Log "обнаружен WSL-bash ($($bashCmd.Source)) — verify-iso.sh не вызываем (несовместимый перевод путей)"
  } else {
    $probe = & $bashCmd.Source -lc 'command -v xorriso' 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) { $haveXorriso = $true; Log "xorriso: $probe" }
    else { Log "bash есть, xorriso нет — El Torito-гейты недоступны" }
  }
} else {
  Log "bash не найден — El Torito-гейты недоступны"
}
if ($haveXorriso) {
  # git-bash: запрет MSYS-преобразования путей, иначе /autounattend.xml мутирует
  $env:MSYS_NO_PATHCONV = '1'
  $env:MSYS2_ARG_CONV_EXCL = '*'
  Log "вызов: bash src/lib/verify-iso.sh <iso> /autounattend.xml"
  & $bashCmd.Source "$script:RepoRoot\src\lib\verify-iso.sh" $outIso '/autounattend.xml' *>&1 | ForEach-Object { Log-Raw "$_" }
  Assert-NativeExit 'verify-iso.sh'
} else {
  Log "WARN: El Torito-гейты требуют xorriso — гейты загрузочных записей НЕ выполнены; ниже raw-факты (размер, SHA256)"
}

# ============================== ФАЗА emit ==============================
Log "--- фаза emit: артефакты в NOUS_TARGET_DIR ---"
# Сырой отчёт El Torito (если verify выполнялся) — рядом с артефактом:
# генеалогия загрузочных записей, спека 05 (пока ISO ещё во временном каталоге).
$eltoritoReport = "$outIso.eltorito-report.txt"
if (Test-Path -LiteralPath $eltoritoReport) {
  Copy-Item -LiteralPath $eltoritoReport -Destination (Join-Path $script:EmitDir 'eltorito-report.txt') -Force
  Log "сохранён сырой отчёт El Torito: eltorito-report.txt"
}
$finalIso = Join-Path $script:EmitDir (Split-Path $outIso -Leaf)
Move-Item -LiteralPath $outIso -Destination $finalIso -Force
$finalSha = (Get-FileHash -LiteralPath $finalIso -Algorithm SHA256).Hash.ToLowerInvariant()
$shaLine = "$finalSha  $(Split-Path $finalIso -Leaf)"
Set-Content -LiteralPath (Join-Path $script:EmitDir 'SHA256SUMS') -Value $shaLine -Encoding ascii
Log "SHA256SUMS: $shaLine"
if ($script:FetchReport) {
  $fetchReportCopy = Join-Path $script:EmitDir 'fetch-report.json'
  Copy-Item -LiteralPath (Join-Path $script:TempDir 'fetch-report.json') -Destination $fetchReportCopy -Force
  Log ("происхождение: fetch-report.json (fido_tag={0}, fido_sha256={1}, source_url={2})" -f `
    $script:FetchReport.fido_tag, $script:FetchReport.fido_sha256, $script:FetchReport.source_url)
}
Log "итоговое содержимое $script:EmitDir :"
Get-ChildItem -LiteralPath $script:EmitDir | ForEach-Object { Log ("  {0} — {1} байт" -f $_.Name, $_.Length) }
Log "готово: $finalIso"
Log "лог сырых команд: $script:LogPath"
Log "временный каталог (для разбора инцидентов, можно удалить): $script:TempDir"
