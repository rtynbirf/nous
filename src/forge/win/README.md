# src/forge/win — Windows-ветка форжа

Спека: [docs/spec/implementation/03-windows-iso.md](../../../docs/spec/implementation/03-windows-iso.md)
Тикет: 0003 (фаза R3) · Субъект: forge-builder-win

## Планируемая структура (фиксируется спекой, появляется по тикету)

```
fetch/        # получение образа по пинам (Fido, SHA256 сверка)
templates/    # autounattend.xml.j2 — шаблон с безопасными дефолтами
build/        # oscdimg-сборка (-bootdata: BIOS+UEFI), DISM-операции
```

Инварианты: `WillWipeDisk=false` по умолчанию; источники только из пинов;
артефакт всегда с SHA256 + логом сырых команд.
