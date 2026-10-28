# src/forge/linux — Linux-ветка форжа (равноправная)

Спека: [docs/spec/implementation/04-linux-iso.md](../../../docs/spec/implementation/04-linux-iso.md)
Тикет: 0004 (фаза R4) · Субъект: forge-builder-linux

## Планируемая структура (фиксируется спекой, появляется по тикету)

```
fetch/        # netinst по пинам (Debian 12 firmware; SHA256 против официального SHA256SUMS)
templates/    # preseed.cfg.j2 — confirm_nooverwrite=true, без автостирания
build/        # xorriso-гибрид (BIOS+UEFI: -isohybrid-mbr + eltorito-alt-boot)
```

Инварианты: no-autowipe; плейсхолдеры вместо секретов в шаблонах;
артефакт всегда с SHA256 + логом сырых команд.
