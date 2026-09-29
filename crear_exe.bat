@echo off
REM Usa Python 3.12 (o 3.13 / 3.11) si esta instalado; el 3.14 puede no tener GDAL compilado.
cd /d "%~dp0"
for %%V in (3.12 3.13 3.11) do (
  py -%%V --version >nul 2>&1 && (
    echo Usando Python %%V
    py -%%V construir_exe.py
    goto fin
  )
)
echo No se encontro Python 3.11, 3.12 ni 3.13. Instala Python 3.12 desde python.org/downloads
:fin
pause
