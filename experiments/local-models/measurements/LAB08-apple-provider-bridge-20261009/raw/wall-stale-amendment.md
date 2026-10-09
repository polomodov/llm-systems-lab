# Коррекция после настоящего timeout

Исходный retry остаётся aborted. Telemetry gap 913.904 s; configured timeout 900 s, observed agent wall 1056 s. Причина разрыва неизвестна. Старый supervisor и timer сохранены в sealed inputs; их нельзя подтверждать исправленным кодом.

В новой реализации timer проверяет absolute wall deadline каждые ≤250 ms активного host execution; stop идемпотентен и использует тот же Docker env. Native supervisor отказывает при разрыве sample timeline >15 s/движении часов назад и фиксирует idle-sleep assertion command/PID. Новые clock-jump/stale tests прошли, Docker timeout/cancel regression прошла. Эти software proofs не являются новой native квалификацией; во время полной приостановки host код не исполняется. Никаких pmset/kernel настроек не меняли. До следующего T002 требуется отдельная короткая нативная регистрация с новыми guards.
