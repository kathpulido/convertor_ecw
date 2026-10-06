# -*- coding: utf-8 -*-
"""Construye ConversorECW.exe (portable, sin dependencias) en un Windows con Python 3.11+ (64 bits).
Uso:  py construir_exe.py
"""
import json, os, re, subprocess, sys, urllib.request, shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(AQUI, "_build_venv")
PYV = f"cp{sys.version_info.major}{sys.version_info.minor}"
API = "https://api.github.com/repos/cgohlke/gdal.whl/releases?per_page=30&page={}"


def run(*a):
    print(">", " ".join(a)); subprocess.check_call(a)


def buscar_wheel_gdal():
    for pag in range(1, 6):
        req = urllib.request.Request(API.format(pag), headers={"User-Agent": "conv-ecw"})
        rels = json.load(urllib.request.urlopen(req))
        if not rels:
            break
        for r in rels:
            for a in r["assets"]:
                if re.fullmatch(rf"(?i)gdal-3\.11\.\d+-{PYV}-{PYV}-win_amd64\.whl", a["name"]):
                    return a["browser_download_url"]
    sys.exit(f"No se encontró wheel de GDAL 3.11 para {PYV}. Usa Python 3.11-3.13 de 64 bits.")


def main():
    if os.name != "nt":
        sys.exit("Este script debe ejecutarse en Windows.")
    if not os.path.isdir(VENV):
        run(sys.executable, "-m", "venv", VENV)
    py = os.path.join(VENV, "Scripts", "python.exe")
    url = buscar_wheel_gdal()
    print("GDAL:", url)
    run(py, "-m", "pip", "install", "-U", "pip")
    run(py, "-m", "pip", "install", url)
    run(py, "-m", "pip", "install", "gdal-ecw>=3.11,<3.12", "pillow", "numpy", "pyinstaller")
    run(py, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "ConversorECW", "--collect-all", "osgeo",
        "--distpath", os.path.join(AQUI, "dist"),
        "--workpath", os.path.join(VENV, "work"), "--specpath", VENV,
        os.path.join(AQUI, "conversor_ecw.py"))
    print("\nListo:", os.path.join(AQUI, "dist", "ConversorECW.exe"))


if __name__ == "__main__":
    main()
