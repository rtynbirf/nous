# Тикет 0008 — Ubuntu 24.04: рецепт пересборки BIOS+UEFI (грунт-факты собраны)

Фаза: R1 калибровка (ubuntu-24.04) · Создан: 2026-10-29 · Предусловия: 0001 (debian-ветка закрыта живым прогоном 40868854559)

## Роль

forge-architect (рецепт), forge-builder-linux (реализация), forge-verifier
(QEMU boot-гейт); исполняет агент с правом workflow_dispatch / человек-владелец.

## Цель

Довести `src/forge/linux/build.sh` (цель ubuntu-2404) до артефакта, проходящего
`verify-iso.sh` (BIOS+UEFI El Torito), с обязательной boot-валидацией.

### Грунт-факты (pycdlib/сырой разбор официального ubuntu-24.04.5-live-server-amd64.iso)

- Дерево НЕ содержит `isolinux/` и `boot/grub/efi.img` — ветка build.sh
  «GRUB-only / honest FAIL» срабатывает корректно (прогон 40869827394).
- `boot/grub/i386-pc/eltorito.img` ЕСТЬ в дереве: extent=1197, size=31169 байт.
- El Torito каталог (сектор 1196): BIOS-запись = no-emul, 4 сектора, RBA=1197
  (= eltorito.img, сразу за каталогом); UEFI-запись (platform 0xef) = no-emul,
  10160 секторов (~20MB ESP), RBA=1992279 — **у хвоста образа, не файл дерева**.
- `EFI/boot/`: bootx64.efi (966KB), grubx64.efi (2.3MB), mmx64.efi (856KB).
- `BOOT/GRUB/`: grub.cfg (573b), i386_pc/, x86_64_efi/, unicode.pf2.
- Семейство рецепта: grub-mkrescue (xorriso `--grub2-mbr` + `--grub2-boot-info`
  + `-append_partition 2 0xef <esp.img>` + `-e '--interval:appended_partition_2:::'`
  + `-partition_offset 16`).

### План реализации

1. CI-шаг инструментов: добавить `grub-pc-bin dosfstools mtools` (boot_hybrid.img,
   mkfs.vfat, mcopy).
2. Фаза BUILD (ubuntu-2404): собрать `esp.img` (~20MB vfat) из `EFI/boot/` +
   grub.cfg через mformat/mcopy; xorriso-рецепт семейства grub-mkrescue (выше).
3. Фаза VERIFY: дополнительно сверить раскладку каталога с эталоном (BIOS 4
   сектора no-emul; UEFI ~10160 секторов no-emul).

## Границы

Разрешено: `src/forge/linux/build.sh` (ветка ubuntu), `.github/workflows/forge.yml`
(шаг инструментов), `tests/test_forge_linux.py`, `state/`, этот тикет.
Запрещено: пины каналов (уже calibrated-live), debian-ветка рецепта, спеки.

## Критерии приёмки

- [ ] Прогон forge.yml ubuntu-2404 в CI: VERIFY зелёный, артефакт получен
- [ ] QEMU-гейт в CI (TCG): ISO стартует в BIOS-режиме до меню GRUB, в UEFI
      (OVMF) — до меню GRUB (доказательство, не предположение)
- [ ] Raw-факты раскладки каталога записаны в build-log и `state/`

## Протокол отчёта

Субъект отчитывается в этот тикет: ссылка на прогон, артефакт, вердикт
верификатора, вывод QEMU-гейта (raw), обновлённый snapshot `state/`.

## ПОЧЕМУ ТОЛЬКО ТАК

- Универсальный « debian-рецепт» на Ubuntu неприменим: раскладка принципиально
  иная (isolinux отсутствует; ESP — appended-раздел на хвосте, не файл).
  Карта обязана совпасть с территорией (аксиома 2) — факты выше собраны
  разбором официального образа, а не выдуманы.
- QEMU-гейт обязателен: Ubuntu-рецепт сложнее debian (ESP-конструирование,
  MBR/GPT-гибрид), «собралось и прошло xorriso» не доказывает загрузку;
  CI обязан дать доказательство до того, как артефакт назван годным (спека 05).
- Пакеты берутся из каркаса сборки (grub-pc-bin и др.), а не выдумываются в
  дереве: организм не подделывает территорию под карту.
