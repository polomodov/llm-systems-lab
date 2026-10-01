# rocm-preflight-01 — Подготовка ROCm 7.2 для ЛР02

Сессия: `rocm-preflight-01`
Дата preflight: 2026-10-01

Подготовительная работа **перед** повторным прохождением `LAB02-hardware` после
установки user-space стека ROCm 7.2. ЛР02 запрещает менять систему в ходе сбора
паспорта, поэтому установка вынесена в отдельную сессию и каталог.

Связанные документы:

- `docs/labs/LAB02-hardware.md` — паспорт машины (ЛР02)
- `docs/labs/README.md` — общий практикум
- `docs/local-model-runtime.md` — runbook для gfx1151 и стек ROCm
- `experiments/local-models/measurements/LAB02-first-pass/` — предыдущая
  итерация ЛР02 (ROCm не установлен, Vulkan/ROCm `unavailable`)

## Цель

Включить ROCm userspace (`rocminfo`, `hipconfig`, HIP runtime) так, чтобы:

1. Не пересобирать ядро и не ставить DKMS.
2. Не менять активный `amdgpu`/`amdxcp` модули и `/dev/kfd`.
3. Не трогать BIOS carve-out, TTM pages_limit и профиль питания.
4. Сделать установку **обратимой**: pin-файл лежит в этой папке,
   `rocm.list` и GPG-ключ не менялись.
5. Снять повторный паспорт машины в новой сессии `LAB02-after-rocm`.

## Текущее состояние машины (preflight)

| Поле | Значение | Источник |
| --- | --- | --- |
| Машина | GTR Pro (GTRP112) | `raw/product-name.txt`, `raw/cpu.txt` |
| CPU / OEM | AMD Ryzen AI Max+ 395 w/ Radeon 8060S, 16 cores / 32 threads | `raw/cpu.txt` |
| OS | Ubuntu 24.04.4 LTS (noble) | `raw/os-release.txt` |
| Kernel | `7.0.0-34-generic` (Ubuntu 24.04 HWE, custom) | `raw/kernel.txt` |
| BIOS | `06/10/2026` | `raw/bios-version.txt`, `raw/bios-date.txt` |
| MemTotal | 134 153 334 784 bytes (124.94 GiB) | `raw/memory.txt`, `raw/meminfo.txt` |
| TTM pages_limit | 26 214 400 × 4096 = 100.00 GiB | `raw/ttm-pages-limit.txt` |
| VRAM carve-out | 0.50 GiB | `raw/card1-mem_info_vram_total` |
| GTT total | 100.00 GiB (равен TTM cap) | `raw/card1-mem_info_gtt_total` |
| GPU | PCI `1002:1586` (gfx1151 / RDNA 3.5), `card1` | `raw/pci.txt` |
| Render node | `/dev/dri/renderD128` → `card1` | `raw/dev-dri.txt`, `raw/pci.txt` |
| `/dev/kfd` | присутствует, mode 0660 root:render | `raw/dev-kfd.txt` |
| amdgpu driver | загружен, 32 ref-count | `raw/lsmod.txt` |
| Vulkan (`vulkaninfo`) | RADV GFX1151, API 1.4.318, driver 25.2.8 | `raw/vulkan-summary.txt`, `raw/vulkan-full.txt` |
| ROCm (`rocminfo`, `hipconfig`) | **отсутствует** (`OSError: [Errno 2]`) | `raw/rocminfo.txt`, `raw/hipconfig.txt` |
| rocm.list | `https://repo.radeon.com/rocm/apt/7.2 noble main` (подключён) | `raw/etc-apt-sources.list.d-rocm.list` |
| GPG-ключ | `/etc/apt/keyrings/rocm.gpg` (подключён) | локальная проверка |
| Уже установленные ROCm-пакеты | `libdrm-amdgpu1` 2.4.125 (Ubuntu), `xserver-xorg-video-amdgpu` 23.0.0 | `raw/dpkg-before.txt` |

Совместимость с gfx1151 по матрице AMD 7.14.1:

- Ядро `7.0.0-34-generic` новее минимума `6.17.0-19.19~24.04.2`
  (Ubuntu HWE), KFD-patches уже в mainline. Статус: **documented**.
- ROCm 7.2 исторически валидирован AMD для Ryzen AI Max 300 (Strix Halo)
  с Ubuntu 24.04.4 (см. `docs/local-model-runtime.md`, таблица фактов).
  ROCm 7.14.1 (released 2026-09-02) в матрице для `gfx1151` прямо не
  перечислен; для этой установки выбран 7.2 как совместимый documented путь.

## Почему apt-pin

`rocm-hip-runtime` (и его транзитивные зависимости) в Depends требуют
**ровно** `rocminfo (= 1.0.0.70200-43~24.04)`. В репозитории `noble/universe`
есть `rocminfo 5.7.1-3build1`, у которой выше строка версии
(`5.7.1` > `1.0.0.70200` лексикографически). Без pin apt выбирает её и
отказывается ставить ROCm-стек.

`rocm-7.2-preferences` добавляет pin `origin "repo.radeon.com"` с приоритетом
1001, что для всех пакетов ROCm репозитория выигрывает у Ubuntu-версий.
Содержимое:

```
Package: *
Pin: origin "repo.radeon.com"
Pin-Priority: 1001
```

**Кавычки вокруг origin обязательны**, **имя файла должно заканчиваться на
`.pref`**. Без кавычек APT молча игнорирует содержимое pin; без расширения
`.pref` APT молча игнорирует весь файл:

```
N: Ignoring file 'rocm-7.2-user-space' in directory '/etc/apt/preferences.d/'
   as it has an invalid filename extension
```

Обе ошибки случились в первой попытке: правильно встали `rocm-core`,
`hsa-rocr`, `hip-runtime-amd`, `comgr`, `rocprofiler-register`, но
`rocminfo` приехал `5.7.1-3build1` (Ubuntu) и потянул за собой
`libhsa-runtime64-1`, `libhsakmt1` тоже из Ubuntu. Запуск такого
`rocminfo` сразу падает: `Agent creation failed. The GPU node has an
unrecognized id.` Исправляется `fix-rocminfo-pin.sh` (см. ниже).

С `-s` (dry-run) проверено, что после pin:

- `minimal` (`rocminfo hsa-rocr hip-runtime-amd`) ставит **11 новых пакетов**
  (без multilib toolchain): `amdgpu-core`, `libncurses-dev`, `rocm-core`,
  `comgr`, `libdrm2-amdgpu`, `libdrm-amdgpu-common`, `libdrm-amdgpu-amdgpu1`,
  `rocprofiler-register`, `hsa-rocr`, `rocminfo`, `hip-runtime-amd`.
- `full` (`rocm-hip-runtime`) добавляет multilib toolchain
  (`gcc-13-multilib`, `g++-13-multilib`, `libc6-i386`, `libc6-x32`, …),
  `rocm-llvm`, `rocm-device-libs`, `openmp-extras-runtime`,
  `rocm-language-runtime` — всего **44 новых пакета**.

Логи dry-run в `raw/apt-simulation-minimal.txt` и `raw/apt-simulation-full.txt`.

## Что именно ставится (user-space, без пересборки ядра)

| Пакет | Версия | Назначение |
| --- | --- | --- |
| `amdgpu-core` | 1:7.2.70200-2278374.24.04 | meta-pkg user-mode AMD driver |
| `libdrm2-amdgpu` | 1:2.4.125.70200 | DRM runtime от AMD (параллельная версия, не заменяет системный `libdrm2`) |
| `libdrm-amdgpu-amdgpu1` | 1:2.4.125.70200 | DRM amdgpu-specific от AMD (параллельная версия) |
| `libdrm-amdgpu-common` | 1.0.0.70200 | PCI ID database от AMD |
| `rocm-core` | 7.2.0.70200 | meta-pkg ROCm 7.2 runtime |
| `comgr` | 3.0.0.70200 | ROCm code object manager |
| `rocprofiler-register` | 0.6.0.70200 | регистрация профайлеров |
| `hsa-rocr` | 1.18.0.70200 | HSA runtime |
| `rocminfo` | 1.0.0.70200 | диагностика ROCm |
| `hip-runtime-amd` | 7.2.26015.70200 | HIP runtime, содержит `hipconfig` |

`rocm-llvm`, `rocm-device-libs`, `openmp-extras-runtime`, `rocm-language-runtime`,
`rocm-hip-runtime` — только при `full`. Они нужны HIP clang toolchain для
**компиляции** HIP-кода; для паспорта ЛР02 и для запуска готовых HIP-приложений
этого не требуется.

## Установка

### Чистая установка (с нуля)

Скрипт `install-rocm-7.2.sh` принимает режим: `minimal` (по умолчанию),
`full`, `status`. Требует `sudo` для шагов 1–5, режим `status` тоже, потому
что `dpkg -l` показывает меньше при обычном пользователе.

```bash
cd experiments/local-models/measurements/rocm-preflight-01
sudo ./install-rocm-7.2.sh minimal
sudo ./install-rocm-7.2.sh status
```

### Исправление установленной системы (если уже ставили)

Если `rocminfo` показывает `Agent creation failed` или
`apt-cache policy rocminfo` показывает `Installed: 5.7.1-3build1`, нужна
починка:

```bash
cd experiments/local-models/measurements/rocm-preflight-01
sudo ./fix-rocminfo-pin.sh
sudo ./install-rocm-7.2.sh status
```

`fix-rocminfo-pin.sh`:

1. Переписывает `/etc/apt/preferences.d/rocm-7.2-user-space` с правильным
   синтаксисом `Pin: origin "repo.radeon.com"`.
2. Удаляет Ubuntu-версии `rocminfo`, `libhsa-runtime64-1`, `libhsakmt1`.
3. `apt-get update`.
4. Ставит `rocminfo=1.0.0.70200-43~24.04` из `repo.radeon.com`.
5. Сохраняет `raw/dpkg-after-fix.txt` и `raw/rocm-tools-after-fix.txt`.

После успешной установки `rocminfo` и `hipconfig` будут доступны в `/usr/bin`
через PATH. Переменные окружения для runtime (если понадобятся):

- `PATH=/opt/rocm-7.2.0/bin:$PATH`
- `LD_LIBRARY_PATH=/opt/rocm-7.2.0/lib:$LD_LIBRARY_PATH`
- `HIP_PLATFORM=amd`

После установки нужно **повторно снять ЛР02** в новой сессии:

```bash
npm run lab:new -- --lab LAB02 --session after-rocm
export LAB_DIR='experiments/local-models/measurements/LAB02-after-rocm'
# повторить шаги 2–7 из docs/labs/LAB02-hardware.md
```

В отчёте новой сессии `rocminfo`, `hipconfig` уже будут заполнены, не как
`unavailable`.

## Откат

Удаление стека и pin-файла:

```bash
sudo apt-get remove --purge amdgpu-core libdrm2-amdgpu libdrm-amdgpu-amdgpu1 \
  libdrm-amdgpu-common rocm-core comgr rocprofiler-register hsa-rocr \
  rocminfo libhsa-runtime64-1 libhsakmt1 hip-runtime-amd rocm-hip-runtime \
  rocm-llvm rocm-device-libs openmp-extras-runtime rocm-language-runtime
sudo rm -f /etc/apt/preferences.d/rocm-7.2-user-space.pref
sudo apt-get autoremove
```

`rocm.list` и GPG-ключ остаются — они не менялись в этой работе.

## Чего эта работа не делает

- Не меняет ядро, BIOS, TTM/GTT и профиль питания.
- Не добавляет DKMS-модули и не пересобирает `amdgpu`.
- Не запускает inference и не ставит модельные веса.
- Не открывает дополнительных сетевых портов и сервисов.
- Не трогает существующий `LAB02-first-pass`.
