<#
НОУС · src/forge/win/fetch-fido.ps1 — фаза fetch Windows-ветки форжа.
Спека: docs/spec/implementation/03-windows-iso.md · Пины: manifests/pins.yaml (ADR-0006)
Запуск (Windows-хост владельца, pwsh 7):
  pwsh -NoProfile -File src/forge/win/fetch-fido.ps1 -OutputDir <каталог>

Что делает:
  1. Читает пины forge.fido / forge.windows-image из manifests/pins.yaml — единственный
     источник репозитория и версий (хардкод URL/версий в коде запрещён, спека 01).
  2. Скачивает Fido.ps1 из пиннутого релиза пиннутого репозитория (репо — из пина).
     Тег берётся из пина; если тег в пине null — запрашивается последний релиз через
     официальное GitHub-API того же пиннутого репозитория. Нюанс релизов Fido
     (проверено по релизам, 2026-10-29): ассет — только Fido.ps1.lzma (pwsh нативно
     LZMA не распаковывает), поэтому скрипт скачивается из исходников ТОГО ЖЕ тега
     (raw.githubusercontent.com) и именно его SHA256 фиксируется/сверяется пином.
  3. Протокол TOFU (ADR-0006, спека 01): если forge.fido.sha256 = null — значения
     tag/sha256 фиксируются в stdout-отчёте («TOFU-фиксация: …») и прогон продолжается;
     если пин задан — сверяем, расхождение = отказ.
  4. Вызывает Fido (-Win/-Rel/-Ed/-Lang/-Arch -GetUrl) для получения ОФИЦИАЛЬНОЙ ссылки
     Microsoft. Никаких URL Microsoft в коде нет — только через Fido. Скачивает ISO
     во временный каталог (-OutputDir), считает SHA256, сверяет с пином
     forge.windows-image.iso_sha256 (если задан; иначе TOFU-фиксация).
  5. Печатает JSON-отчёт { source_url, iso_path, sha256, fido_tag, fido_sha256, tofu_fixed }
     как последнюю строку stdout и сохраняет его в <OutputDir>/fetch-report.json.

Границы: запись — только в -OutputDir; носители хоста не трогаем (safe-defaults, спека 06).
#>
[CmdletBinding()]
param(
  # Каталог для временных файлов и ISO (по умолчанию — системный temp)
  [string]$OutputDir = "",
  # Язык образа в терминах ОС (локаль; по умолчанию ru-RU). Нюанс Fido
  # (проверено по исходнику Fido, 2026-10-29): -Lang матчится по ИМЕНИ языка из
  # официального списка Microsoft ($language.Name -match $Lang), коды вида "ru-ru"
  # списком имён не находятся — поэтому ниже локаль нормализуется в официальное
  # имя (см. фазу 3). Полный список: Fido.ps1 -Win 11 -Rel List -Ed Pro -Lang List.
  [string]$Language = "ru-RU",
  # Путь к manifests/pins.yaml (по умолчанию — корень репозитория)
  [string]$PinsPath = "",
  # Релиз для Fido -Rel (по умолчанию Latest — сам Fido берёт свежий из списка)
  [string]$FidoRelease = "Latest"
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$script:RepoRoot = (Resolve-Path (Join-Path (Join-Path $PSScriptRoot '..') '..')).Path
if (-not $PinsPath) { $PinsPath = Join-Path $script:RepoRoot 'manifests\pins.yaml' }
if (-not $OutputDir) {
  $OutputDir = Join-Path ([System.IO.Path]::GetTempPath()) ("nous-fetch-" + [guid]::NewGuid().ToString('N'))
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$script:ReportPath = Join-Path $OutputDir 'fetch-report.json'
$script:TofuFixed = $false

function Log { param([string]$Message) Write-Host "[fetch-fido] $Message" }
function Die { param([string]$Message) Log "FAIL: $Message"; exit 1 }

# --- Пины: разбор ограниченного подмножества YAML, которого достаточно для
# manifests/pins.yaml (вложенные отображения со скалярами, кавычки, inline- и
# хвостовые комментарии). Сложные структуры не поддерживаем сознательно: при
# расширении pins.yaml нужна калибровка (спека 01), а не тихий дрейф парсера.
function Convert-PinScalar {
  param([string]$Raw)
  $v = $Raw.Trim()
  if ($v -match '^"([^"]*)"\s*(#.*)?$') { return $Matches[1] }
  if ($v -match "^'([^']*)'\s*(#.*)?$") { return $Matches[1] }
  $v = ($v -split '\s+#', 2)[0].Trim()   # хвостовой комментарий вне кавычек
  switch ($v) {
    'null'  { return $null }
    '~'     { return $null }
    'true'  { return $true }
    'false' { return $false }
    default { return $v }
  }
}

function Read-Pins {
  param([Parameter(Mandatory)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { Die "нет файла пинов: $Path — форж без пинов не работает (ADR-0006)" }
  $pins = @{}
  $stack = New-Object System.Collections.Generic.List[object]
  foreach ($rawLine in [System.IO.File]::ReadAllLines($Path)) {
    $line = $rawLine -replace "`t", '  '
    if ($line.Trim().Length -eq 0 -or $line -match '^\s*#') { continue }
    if ($line -notmatch '^(\s*)([A-Za-z0-9_/-]+):(.*)$') {
      Die "pins.yaml: строка вне поддержанного подмножества YAML: $rawLine"
    }
    $indent = $Matches[1].Length
    $key = $Matches[2]
    $valueRaw = $Matches[3].Trim()
    while ($stack.Count -gt 0 -and $stack[$stack.Count - 1].indent -ge $indent) { $stack.RemoveAt($stack.Count - 1) }
    $prefix = ($stack | ForEach-Object { $_.key }) -join '.'
    $full = if ($prefix) { "$prefix.$key" } else { $key }
    # Вложенное отображение = значение пустое ИЛИ состоит из одного inline-
    # комментария ("forge: # ..."). Иначе секция с комментарием после двоеточия
    # считается скаляром и вся её вложенность выпадает из пинов (реальный кейс
    # строки "forge:" в manifests/pins.yaml).
    if ($valueRaw.Length -eq 0 -or $valueRaw.StartsWith('#')) {
      $stack.Add([pscustomobject]@{ key = $key; indent = $indent }) | Out-Null
    } else {
      $pins[$full] = Convert-PinScalar -Raw $valueRaw
    }
  }
  return $pins
}

function Get-Pin {
  param([hashtable]$Pins, [string]$Name)
  if (-not $Pins.ContainsKey($Name)) { Die "пин $Name отсутствует в manifests/pins.yaml — не выдумываем (аксиома 2)" }
  return $Pins[$Name]
}

# ============================== ФАЗА 1: пины ==============================
$pins = Read-Pins -Path $PinsPath
$fidoRepo     = Get-Pin $pins 'forge.fido.repo'
$fidoStatus   = Get-Pin $pins 'forge.fido.status'
$fidoPinTag   = Get-Pin $pins 'forge.fido.tag'
$fidoPinSha   = Get-Pin $pins 'forge.fido.sha256'
$editionPin   = Get-Pin $pins 'forge.windows-image.edition'
$imgChannel   = Get-Pin $pins 'forge.windows-image.channel'
$imgPinSha    = Get-Pin $pins 'forge.windows-image.iso_sha256'
Log "пины: forge.fido.repo=$fidoRepo status=$fidoStatus tag=$fidoPinTag sha256=$fidoPinSha"
Log "пины: forge.windows-image.edition='$editionPin' channel='$imgChannel' iso_sha256=$imgPinSha"
if (-not $fidoRepo) { Die "пин forge.fido.repo пуст — канал не пиннут, работа запрещена (спека 01)" }

# ======================= ФАЗА 2: релиз и Fido.ps1 ========================
# Тег из пина; если null — последний релиз официального GitHub-API канала
# пиннутого репозитория. Хост api.github.com — документированный транспорт
# GitHub для пиннутого репозитория; сам репозиторий/тег — только из пинов.
if ($fidoPinTag) {
  $apiUrl = "https://api.github.com/repos/$fidoRepo/releases/tags/$fidoPinTag"
} else {
  $apiUrl = "https://api.github.com/repos/$fidoRepo/releases/latest"
}
Log "GET $apiUrl (сырой факт ниже)"
$rel = Invoke-RestMethod -Uri $apiUrl -Headers @{ 'User-Agent' = 'nous-forge-pin-reader' } -TimeoutSec 60
$fidoTag = $rel.tag_name
Log "сырой факт: tag_name=$fidoTag; ассеты релиза:"
foreach ($asset in @($rel.assets)) {
  Log ("  asset: name={0} size={1} url={2}" -f $asset.name, $asset.size, $asset.browser_download_url)
}
if (-not $fidoTag) { Die "GitHub API не вернул tag_name для $fidoRepo (сырой вывод выше)" }

# Ассет релиза — Fido.ps1.lzma (без нативной распаковки LZMA в pwsh), поэтому
# берём скрипт из исходников того же тега: raw.githubusercontent.com — официальный
# канал содержимого репозитория по пиннутому тегу.
$fidoUrl = "https://raw.githubusercontent.com/$fidoRepo/$fidoTag/Fido.ps1"
$fidoScript = Join-Path $OutputDir 'Fido.ps1'
Log "GET $fidoUrl → $fidoScript"
Invoke-WebRequest -Uri $fidoUrl -OutFile $fidoScript -Headers @{ 'User-Agent' = 'nous-forge-pin-reader' }
$head = (Get-Content -LiteralPath $fidoScript -TotalCount 2) -join ' / '
Log "сырой факт: начало файла: $head"

$fidoSha256 = (Get-FileHash -LiteralPath $fidoScript -Algorithm SHA256).Hash.ToLowerInvariant()
Log "SHA256 Fido.ps1: $fidoSha256"
if ($fidoPinSha) {
  if ($fidoSha256 -ne $fidoPinSha.ToLowerInvariant()) {
    Die "SHA256 Fido.ps1 ($fidoSha256) не совпал с пином forge.fido.sha256 ($fidoPinSha) — стоп, тикет security (спека 01)"
  }
  Log "сверка с пином forge.fido.sha256 — ОК"
} else {
  Log "TOFU-фиксация: forge.fido.tag = $fidoTag"
  Log "TOFU-фиксация: forge.fido.sha256 = $fidoSha256"
  Log "TOFU-фиксация: внесите значения в manifests/pins.yaml тикетом калибровки (спека 01)"
  $script:TofuFixed = $true
}

# =================== ФАЗА 3: официальная ссылка через Fido ===================
# Параметры образа разбираем из пина forge.windows-image.edition ("Windows 11 Pro x64").
if ($editionPin -notmatch '^Windows\s+(\d+)\s+(.+?)\s+(x64|x86|arm64)$') {
  Die "пин forge.windows-image.edition ('$editionPin') не разбирается в -Win/-Ed/-Arch — нужна калибровка"
}
$winMajor = $Matches[1]
$edition = $Matches[2]
$arch = $Matches[3]
# Нормализация локали в официальное имя языка Fido (см. комментарий к -Language;
# исходник Fido: $language.Name -match $Lang). Карта минимальна сознательно —
# дефолтная ветка НОУС: ru-RU → Russian. Иные значения уходят в Fido как есть:
# при неверном имени Fido честно падает с подсказкой '-Lang List' — тихой
# подмены языка нет, соответствие имени проверяет сам Fido при прогоне.
$fidoLangNames = @{ 'ru-ru' = 'Russian' }
$fidoLang = $Language
if ($fidoLangNames.ContainsKey($Language.ToLowerInvariant())) {
  $fidoLang = $fidoLangNames[$Language.ToLowerInvariant()]
  Log "язык: '$Language' → официальное имя для Fido: '$fidoLang'"
}
Log "образ: -Win $winMajor -Ed $edition -Lang $fidoLang -Arch $arch (-Rel $FidoRelease)"

$pwshExe = if ($PSHOME -and (Test-Path (Join-Path $PSHOME 'pwsh.exe'))) { Join-Path $PSHOME 'pwsh.exe' } else { 'pwsh' }
# Только документированный интерфейс Fido (-Win/-Rel/-Ed/-Lang/-Arch/-GetUrl/
# -PlatformArch; по исходнику Fido: -PlatformArch отключает медленный WMI-запрос
# автоопределения архитектуры). -GetUrl: Fido возвращает ссылку в output-поток
# (return $winLink.Url) вместо открытия браузера.
$fidoArgs = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
  '-File', $fidoScript, '-Win', $winMajor, '-Rel', $FidoRelease,
  '-Ed', $edition, '-Lang', $fidoLang, '-Arch', $arch, '-PlatformArch', $arch, '-GetUrl')
Log ("фаза fido-get-url: $pwshExe " + ($fidoArgs -join ' '))
$fidoOut = & $pwshExe @fidoArgs *>&1
$fidoExit = $LASTEXITCODE
foreach ($line in @($fidoOut)) { Log ("fido| " + "$line") }
if ($fidoExit -ne 0) {
  Die "Fido завершился с кодом $fidoExit (сырой вывод выше). Если дело в языке: полный список — Fido.ps1 -Win $winMajor -Rel List -Ed $edition -Lang List -Arch $arch"
}
$sourceUrl = $null
foreach ($line in @($fidoOut)) {
  $s = "$line".Trim()
  if ($s -match '^https?://') { $sourceUrl = $s }
}
if (-not $sourceUrl) { Die "Fido не вернул ссылку (-GetUrl) — сырой вывод выше" }
Log "официальная ссылка (получена через Fido, не хардкод): $sourceUrl"

# ========================== ФАЗА 4: скачивание ISO ==========================
# Ссылки Microsoft временны (fwlink/BLOB на несколько дней) — скачиваем сразу.
$ProgressPreference = 'SilentlyContinue'   # прогресс IWR замедляет большие файлы; факты — в отчёте
$isoPath = Join-Path $OutputDir ("nous-win11-{0}.iso" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Log "GET $sourceUrl → $isoPath (ожидаемо ~5–6 ГиБ)"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
Invoke-WebRequest -Uri $sourceUrl -OutFile $isoPath -Headers @{ 'User-Agent' = 'nous-forge-pin-reader' }
$sw.Stop()
$isoItem = Get-Item -LiteralPath $isoPath
Log ("сырой факт: размер ISO = {0} байт ({1:N2} ГиБ); загрузка заняла {2:0.0} c" -f $isoItem.Length, ($isoItem.Length / 1GB), $sw.Elapsed.TotalSeconds)

$isoSha256 = (Get-FileHash -LiteralPath $isoPath -Algorithm SHA256).Hash.ToLowerInvariant()
Log "SHA256 ISO: $isoSha256"
if ($imgPinSha) {
  if ($isoSha256 -ne $imgPinSha.ToLowerInvariant()) {
    Die "SHA256 ISO ($isoSha256) не совпал с пином forge.windows-image.iso_sha256 ($imgPinSha) — стоп (спека 01/03)"
  }
  Log "сверка с пином forge.windows-image.iso_sha256 — ОК"
} else {
  Log "TOFU-фиксация: forge.windows-image.iso_sha256 = $isoSha256 (зафиксируйте калибровкой)"
  $script:TofuFixed = $true
}

# ============================ ФАЗА 5: отчёт ============================
$report = [ordered]@{
  source_url  = $sourceUrl
  iso_path    = $isoPath
  sha256      = $isoSha256
  fido_tag    = $fidoTag
  fido_sha256 = $fidoSha256
  tofu_fixed  = [bool]$script:TofuFixed
}
$json = $report | ConvertTo-Json -Compress
Set-Content -LiteralPath $script:ReportPath -Value $json -Encoding utf8
Log "JSON-отчёт сохранён: $script:ReportPath"
Write-Output $json   # последняя строка stdout — машинночитаемый отчёт
