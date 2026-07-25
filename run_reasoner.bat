@echo off
chcp 65001 >nul
set PYTHONUTF8=1
REM ===========================================================
REM  LEDS cross-backend robustness run (SECOND LLM backend).
REM  Reuses the already-completed default (deepseek-chat) results and runs
REM  ONLY the deepseek-reasoner backend. Outputs are model-namespaced
REM  (results/logs/<exp>_deepseek-reasoner.json, summary_deepseek-reasoner.json)
REM  so existing chat data is NOT overwritten. Idempotent: a config with an
REM  existing real reasoner log is reused, not re-run.
REM  This file is ASCII-only on purpose (cmd mis-parses non-ASCII .bat).
REM  Requires: set DEEPSEEK_API_KEY=sk-xxxx
REM ===========================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found. Install Python and enable "Add to PATH".
    goto :fail
)
if "%DEEPSEEK_API_KEY%"=="" (
    echo [ERROR] DEEPSEEK_API_KEY is not set; real backend comparison needs it.
    echo         Run first:  set DEEPSEEK_API_KEY=sk-xxxx
    goto :fail
)

REM Second backend: reasoning model. stage2 auto-skips response_format/temperature
REM for reasoning models and relies on robust JSON extraction.
set LEDS_MODEL=deepseek-reasoner

echo [cross-backend] Running second backend %LEDS_MODEL% (chat results untouched)...
REM Runs all four experiments by default for a complete robustness table.
REM To limit cost, append e.g.:  --configs exp1_scalefree exp2_hub_defense
python src\cross_backend.py
if errorlevel 1 goto :fail

echo.
echo Done: results\summary_deepseek-reasoner.json
echo (comparison table printed above; send that JSON back to fold into the paper)
echo.
pause
exit /b 0

:fail
echo [ERROR] cross-backend run failed, please check the output above.
echo.
pause
exit /b 1
