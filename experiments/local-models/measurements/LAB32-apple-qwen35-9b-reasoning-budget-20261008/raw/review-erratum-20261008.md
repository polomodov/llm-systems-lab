# Исправление экспортёра после review 08.10.2026

Обработка замечаний PR #18 выполнена без модельных прогонов. Исходный экспортёр и его hash inventory сохранены в файлах `*.before-review-20261008`.

Диагностический экспорт учитывает persisted `not-run` вместе с `planned`: повторная генерация прерванной серии сохраняет blocked и причину незавершённости. Кампании revalidate исходный tool call в JSON response / SSE assembled: ровно один function `lookup_lab_value`, JSON arguments ровно `{"key":"alpha"}`, непустой строковый ID. Followup обязан содержать исходное сообщение assistant и result `LAB_VALUE_42` с тем же tool_call_id. Проверка проходит до перезаписи report/manifest/TSV/summary/hashes. Изменения проверены offline в копиях отчётов; прежний отказ 16K и отдельный допуск 32K сохраняются.

Первичные request/response/SSE/logs/telemetry, register statuses, report/TSV/summary измерений не изменялись. Hash inventory обновлён только для исправленного экспортёра и добавленных review snapshots/этого erratum. Аппаратный GPU budget и полный LAB32 admission по-прежнему неизвестен/false соответственно.
