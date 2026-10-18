# ЛР36. SPACE: паспорт хоста, развёртывание в Kind и smoke-тесты

## Паспорт

| Поле | Значение |
| --- | --- |
| Предпосылка | Завершённая [ЛР01](LAB01-reproducibility.md); доступ к целевой машине с sudo |
| Стенды | A: Ryzen AI Max+ 395 / 128 GB / Linux (тот же, что в [ЛР02](LAB02-hardware.md)); B: HONOR MagicBook X16, Ryzen 7 PRO 8845HS / 32 GB / Ubuntu |
| Платформа | `polomodov/SPACE` (форк `perplexityai/SPACE`), закреплённый commit; профиль E0: Linux x86_64 + KVM + Firecracker 1.15.1 |
| Минимум | Паспорт хоста, полная установка, `first_sandbox.py`, baseline `smoke-kind-e2e.sh`, typed smoke `native`, teardown — на **каждом** стенде отдельной сессией |
| Расширения | `smoke-kind-typed.sh ecw` и `all` (на B по шардам), `smoke-spaced-rest.sh`, таймлайн bring-up |
| Время | Ориентир 3–6 часов оператора на стенд; первая сборка Rust-воркспейса — основная часть |
| Готовность | `target-machine`; сочетание «стенд + commit SPACE» `unverified` до первой сессии |
| Начальное состояние | Учебный manifest — `not-started` |

Сессии называйте по стенду: `ryzen-01`, `honor-01`. Повтор на том же стенде — новая сессия (`ryzen-02`), а не перезапись.

## Цель

Поднять локальный SPACE (Kind + Firecracker) на каждой машине без изменения кода платформы, получить воспроизводимые вердикты набора smoke и измерить, сколько времени, памяти и диска стоит развёртывание. Результат работы — допуск стенда к ЛР37–42.

## Проверяемая гипотеза

На обоих стендах установка по `docs/installation.md` проходит без правок кода SPACE, `examples/first_sandbox.py` печатает `Hello from SPACE`, а `smoke-kind-e2e.sh` и `smoke-kind-typed.sh native` завершаются с кодом `0`. На стенде B для этого достаточно ограничить параллелизм Tilt (`SPACE_TILT_MAX_PARALLEL_UPDATES=1`).

Опровержение — OOM, таймаут apiserver Kind, отказ preflight или ненулевой код smoke при этих настройках. Код `42` у typed smoke означает пропуск из-за окружения, а не прохождение; он не подтверждает гипотезу.

## Подготовка

- Прочитайте в репозитории SPACE: `docs/installation.md`, `docs/first-sandbox.md`, `infra/space/kind/README.md` (разделы Smoke test и Kind apiserver timeouts), `docs/troubleshooting.md#local-installation`. Сводка на русском лежит в проектных заметках, но при расхождении прав репозиторий.
- Установщик ставит пакеты через sudo, запускает privileged-контейнеры, создаёт loop-устройства и правила nft. На стенде A не запускайте одновременно серии ЛР04–07 и остановите inference-серверы: Kind и сборка делят ту же память.
- На стенде A запишите выделение UMA под GPU из паспорта ЛР02: от него зависит, сколько RAM видит Linux.
- На стенде B подключите питание и отключите сон на время сборки.
- Не публикуйте в отчёте серийные номера, внешние адреса, пароль консоли и bearer-токены.

Создайте отчёт и закрепите версию SPACE:

```bash
npm run lab:new -- --lab LAB36 --session ryzen-01
LAB_DIR="$PWD/experiments/space/measurements/LAB36-ryzen-01"
git clone https://github.com/polomodov/SPACE.git ~/src/SPACE
git -C ~/src/SPACE rev-parse HEAD > "$LAB_DIR/raw/space-revision.txt"
```

Все команды SPACE ниже выполняются из `~/src/SPACE` в одной сессии bash (по SSH — внутри `tmux`).

## Порядок выполнения

1. **Паспорт хоста (только чтение).**

   ```bash
   { uname -a; cat /etc/os-release; nproc; grep -m1 'model name' /proc/cpuinfo;
     grep -c -w svm /proc/cpuinfo; grep -E 'MemTotal|SwapTotal' /proc/meminfo;
     ls -l /dev/kvm /dev/net/tun; grep -w btrfs /proc/filesystems; losetup -f;
     docker info --format '{{.ServerVersion}} {{.DockerRootDir}} {{.CgroupVersion}}';
     df -h "$(docker info --format '{{.DockerRootDir}}')" "$HOME"; } > "$LAB_DIR/raw/host.txt" 2>&1
   ```

   Нет `/dev/kvm` или флага `svm` — проверьте, включена ли виртуализация в BIOS, и остановитесь с blocker. Внутри VM нужен nested virtualization; для этой работы ожидается bare metal.

2. **Протокол до запуска.** Сохраните `raw/protocol.md`: commit SPACE, стенд, значение `SPACE_TILT_MAX_PARALLEL_UPDATES`, порядок шагов, какие smoke входят в минимум, правило остановки (первая ошибка фазы).

3. **Инструменты и Firecracker.** Запишите время и пик памяти каждой фазы:

   ```bash
   set +eu; set -o pipefail
   export PATH="$HOME/.local/bin:$PATH" INSTALL_DIR="$HOME/.local/bin"; mkdir -p "$INSTALL_DIR"
   unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN DD_API_KEY EPPO_SDK_KEY
   export SPACE_VENDOR_ROOT="$HOME/.local/share/space/vendor" SPACE_KIND_CLUSTER=space-local
   /usr/bin/time -v bash infra/space/kind/scripts/install-prereqs.sh > "$LAB_DIR/raw/prereqs.txt" 2>&1
   /usr/bin/time -v bash infra/space/kind/scripts/install-fc-vendor.sh > "$LAB_DIR/raw/fc-vendor.txt" 2>&1
   ```

4. **Bring-up кластера.** Параллельно ведите фоновые наблюдения памяти и таймлайн:

   ```bash
   vmstat -t 5 > "$LAB_DIR/raw/vmstat-bootstrap.txt" & VMSTAT=$!
   python3 scripts/benchmarks/kind-bringup-timeline.py watch "$LAB_DIR/raw/timeline" & TIMELINE=$!
   # На стенде B: export SPACE_TILT_MAX_PARALLEL_UPDATES=1
   /usr/bin/time -v bash infra/space/kind/scripts/bootstrap.sh > "$LAB_DIR/raw/bootstrap.txt" 2>&1
   kill $VMSTAT $TIMELINE
   ```

   Падение на этом шаге фиксируйте вместе с последними 200 строками лога и состоянием подов (`kubectl --context kind-space-local -n space get pods -o wide`). Повтор после исправления окружения — новая попытка в `planned_attempts`.

5. **Готовность и первая песочница.**

   ```bash
   export SPACE_API_URL=http://127.0.0.1:8080 SPACE_DATA_PLANE_URL=http://127.0.0.1:8090
   kubectl --context kind-space-local -n space wait --for=condition=complete job/space-seed-publish --timeout=300s
   for ds in $(bash infra/space/kind/lib/node-services.sh daemonsets); do
     kubectl --context kind-space-local -n space rollout status "ds/$ds" --timeout=300s; done
   curl --noproxy '*' -fsS "$SPACE_API_URL/openapi-m1.json" | jq -e '.openapi and .paths' >/dev/null && echo "API ok"
   export SPACE_API_TOKEN="$(jq -nc '{email:"root@local",password:"password"}' |
     curl --noproxy '*' -fsS -H 'Content-Type: application/json' --data-binary @- \
     "$SPACE_API_URL/auth/v1/sessions" | jq -er .token)"
   python3 examples/first_sandbox.py 2>&1 | tee "$LAB_DIR/raw/first-sandbox.txt"
   ```

   Успех — строки `Hello from SPACE` и `Command completed successfully`. На вопрос об удалении ответьте `y`. Токен в лог не попадает; проверьте это командой `grep -rlF -- "$SPACE_API_TOKEN" "$LAB_DIR/raw" || echo clean` (ожидается `clean`).

6. **Smoke по ступеням.** Каждая ступень — отдельная строка таблицы с кодом выхода.

   ```bash
   SKIP_BOOTSTRAP=1 bash scripts/tests/smoke-kind-e2e.sh > "$LAB_DIR/raw/smoke-e2e.txt" 2>&1; echo "e2e=$?" >> "$LAB_DIR/raw/exit-codes.txt"
   SKIP_BOOTSTRAP=1 bash scripts/tests/smoke-kind-typed.sh native > "$LAB_DIR/raw/smoke-native.txt" 2>&1; echo "native=$?" >> "$LAB_DIR/raw/exit-codes.txt"
   ```

   Расширение: `smoke-kind-typed.sh ecw`, затем `all`. На стенде B полный `all` гоняйте по шардам `all 1/2` и `all 2/2` последовательно; шарды против одного кластера одновременно не запускаются. `smoke-spaced-rest.sh` — по команде из раздела Smoke test `infra/space/kind/README.md`.

7. **Ресурсы после прогона.** `docker system df`, `du -sh "$SPACE_VENDOR_ROOT"`, `df -h` — в `raw/disk-after.txt`.

8. **Teardown.**

   ```bash
   SPACE_KIND_CLUSTER=space-local bash infra/space/kind/scripts/teardown.sh > "$LAB_DIR/raw/teardown.txt" 2>&1
   kind get clusters >> "$LAB_DIR/raw/teardown.txt"
   ```

   Кэши образов и артефакты Firecracker остаются; запишите их размер. Удалять общие кэши Docker эта работа не требует.

## Таблицы результатов

**Паспорт хоста**

| Поле | Стенд A | Стенд B |
| --- | --- | --- |
| CPU, ядра/потоки, `svm` | | |
| MemTotal / swap / UMA | | |
| Ядро, дистрибутив | | |
| Docker, cgroup, data root, свободно | | |
| `/dev/kvm`, `/dev/net/tun`, btrfs, loop | | |
| Commit SPACE | | |

**Фазы установки**

| Фаза | Стенд | Wall-clock, s | Max RSS, KiB | Пик used RAM по vmstat, MiB | Диск до/после, GiB | Код выхода |
| --- | --- | --- | --- | --- | --- | --- |
| install-prereqs | | | | | | |
| install-fc-vendor | | | | | | |
| bootstrap | | | | | | |

**Smoke**

| Ступень | Стенд | Код (0/42/1) | Passed | Skipped | Failed | Первая ошибка |
| --- | --- | --- | --- | --- | --- | --- |
| first_sandbox.py | | | | | | |
| smoke-kind-e2e | | | | | | |
| typed native | | | | | | |
| typed ecw (расш.) | | | | | | |
| typed all / шарды (расш.) | | | | | | |

## Что сдать

- По отчёту на стенд (`LAB36-ryzen-NN`, `LAB36-honor-NN`) с заполненными таблицами и `raw/protocol.md`.
- Raw: `host.txt`, логи фаз, `vmstat`, таймлайн, `first-sandbox.txt`, логи smoke, `exit-codes.txt`, `teardown.txt`.
- Список упавших сценариев с первой строкой ошибки и ссылкой на лог.
- Раздел «Различия стендов» в отчёте второй сессии: что пришлось изменить на B по сравнению с A и почему.

## Критерии завершения

- Минимум выполнен на стенде: `first_sandbox.py` успешен, `smoke-kind-e2e` и `typed native` завершились кодом `0`, teardown подтверждён.
- Каждая ступень имеет код выхода и лог; `42` не засчитан как pass.
- Пик памяти и время bootstrap измерены, а не оценены.
- В raw нет токенов, пароля и приватных адресов.
- Если стенд не прошёл, отчёт имеет статус `blocked` с точной причиной; допуск к ЛР37–42 для него не выдаётся.

## Контрольные вопросы

1. Какая фаза задаёт пик памяти и на каком стенде запас минимален?
2. Чем пропуск окружения (`42`) отличается от прохождения и почему CI считает их по-разному?
3. Почему шарды typed smoke нельзя запускать параллельно против одного кластера?
4. Что из паспорта хоста объясняет различие времени bootstrap между стендами?
5. Какие ресурсы остаются на диске после teardown и как их безопасно удалить отдельно?

## Источники

- SPACE: `docs/installation.md`, `docs/first-sandbox.md`, `docs/troubleshooting.md`, `docs/execution-environments.md`.
- SPACE: `infra/space/kind/README.md`, `scripts/tests/smoke-kind-e2e.sh`, `scripts/tests/smoke-kind-typed.sh`, `scripts/benchmarks/kind-bringup-timeline.py`.
- Этот репозиторий: [ЛР02](LAB02-hardware.md) (паспорт стенда A), [протокол](../method.md), [проверка отчёта](report-validation.md).
