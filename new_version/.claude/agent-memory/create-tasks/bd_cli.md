---
name: bd CLI quirks для проекта new_version
description: Особенности bd (beads) команд в этом проекте — приоритеты, ID-паттерн, parent/deps синтаксис
type: reference
---

## bd CLI в проекте new_version

**ID-схема:** issues создаются с префиксом `new_version-XXX` (где XXX — короткий хеш). Эпики обычно имеют 3-символьный хеш (`new_version-gwb`), задачи под parent — числовой суффикс через точку (`new_version-gwb.1`).

**Приоритеты:** числовые `0-4` (0=critical, 4=backlog), НЕ строки "high"/"medium"/"low". Для P1 эпиков и критичных задач — `--priority=1`. Для дополнительных/verification — `--priority=2`.

**Parent/child:** `--parent=<epic-id>` создаёт задачу под эпиком и получает дочерний ID `<epic-id>.N`. Это работает корректно — задачи автоматически имеют hierarchical связь.

**Зависимости:** `bd dep add <зависимая> <от-кого>` (порядок: что блокируется, потом блокирующее). Альтернативно `bd dep <blocker> --blocks <blocked>`. После `bd dep add` сразу выводится подтверждение `✓ Added dependency: A depends on B (blocks)`.

**Создание с описанием:** `--description` принимает многострочный текст с markdown. Для acceptance criteria — отдельный флаг `--acceptance`. Для design notes — `--design`. Для оценки — `--estimate <минут>`.

**`--silent`** — выводит только ID созданного issue (удобно для bash-скриптинга и парсинга).

**`bd ready`** — показывает unblocked work, эпики тоже попадают в список (если у них нет родителей-блокеров). Это нормально.

**`bd dep cycles`** — проверка циклов, обязательно прогонять после массового создания зависимостей.

**ВАЖНО:** Не путать `--parent` с `--deps`. Parent — иерархия, deps — порядок выполнения. Эпик-фаза получает дочерние задачи через --parent, а зависимости между задачами разных фаз — через `bd dep add`.
