@echo off
chcp 65001 >nul
set PYTHONUTF8=1
REM ===========================================================
REM  LEDS reproducibility pipeline (Windows one-click runner).
REM  Idempotent: every stage first checks whether usable results already
REM  exist (real API data). If so it SKIPS re-running. No prompts at all.
REM  A stage runs only when its output is missing, unparsable, or was a
REM  previous mock/offline run. This file is ASCII-only on purpose:
REM  cmd.exe mis-parses .bat files that contain non-ASCII characters.
REM  Set the API key first for real-LLM runs:
REM      set DEEPSEEK_API_KEY=sk-xxxx
REM  Without a key, the engine auto-falls back to offline mock mode.
REM ===========================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found. Install Python and enable "Add to PATH".
    goto :fail
)

echo [1/7] Installing dependencies...
pip install networkx matplotlib requests -q
if errorlevel 1 goto :fail

echo [2/7] Stage 1: generate frozen static graphs...
python src\check_done.py data\exp2_hub_defense.json
if errorlevel 1 (
    python src\stage1_generator.py
    if errorlevel 1 goto :fail
) else (
    echo   [skip] static graph configs already exist
)

echo [3/7] Stage 2: simulation engine (run only if missing/non-real)...
call :runexp exp1_smallworld
if errorlevel 1 goto :fail
call :runexp exp1_scalefree
if errorlevel 1 goto :fail
call :runexp exp2_edge_defense
if errorlevel 1 goto :fail
call :runexp exp2_hub_defense
if errorlevel 1 goto :fail

echo [4/7] Stage 3: evaluation (local aggregation, always refreshed)...
python src\stage3_evaluate.py
if errorlevel 1 goto :fail

echo [5/7] Exp III: baselines (run only if missing/non-real)...
python src\check_done.py results\baselines.json --require-api
if errorlevel 1 (
    python src\baselines.py --config data\exp1_scalefree.json --mc-runs 5
    if errorlevel 1 goto :fail
) else (
    echo   [skip] baseline data already present and real
)

echo [6/7] Exp IV: scalability (run only if missing)...
python src\check_done.py results\scalability.json
if errorlevel 1 (
    python src\scalability.py
    if errorlevel 1 goto :fail
) else (
    echo   [skip] scalability data already present
)

echo [7/7] Exp I add-on: Temperature=0 determinism probe (auto, no prompt)...
python src\check_done.py results\determinism_probe.json --require-api
if errorlevel 1 (
    echo   [run] real-API probe ^(~2800 calls, please wait^)...
    python src\determinism_probe.py --config data\exp1_scalefree.json --runs 3
    if errorlevel 1 goto :fail
) else (
    echo   [skip] probe data already present and real
)

echo.
echo All done. Results are in results\ ^(skipped stages reused prior real data^).
echo.
pause
exit /b 0

REM ---- subroutine: one Stage 2 experiment (skip if real data exists) ----
:runexp
python src\check_done.py results\logs\%1.json --require-api
if not errorlevel 1 (
    echo   [skip] %1 already present and real
    exit /b 0
)
echo   [run] %1 ...
python src\stage2_engine.py --config data\%1.json
exit /b %errorlevel%

:fail
echo [ERROR] pipeline failed, please check the output above.
echo.
pause
exit /b 1
