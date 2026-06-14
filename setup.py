"""Empacotamento da aplicação como bundle .app no macOS (py2app).

Uso (a partir da raiz do projeto, com a venv ativa):

    # Modo alias (rápido, para uso local — usa a venv atual):
    python setup.py py2app -A

    # Bundle standalone (distribuível):
    python setup.py py2app

O bundle inclui ``NSLocationUsageDescription`` no Info.plist, condição
necessária para o macOS revelar SSID/BSSID das redes via CoreWLAN.
"""

from setuptools import setup

APP = ["run_app.py"]
DATA_FILES: list = []

OPTIONS = {
    "argv_emulation": False,
    "packages": ["app"],
    "includes": ["CoreWLAN", "CoreLocation"],
    "plist": {
        "CFBundleName": "WiFi Sensing",
        "CFBundleDisplayName": "WiFi Sensing",
        "CFBundleIdentifier": "br.com.wifisensing.app",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "11.0",
        "NSLocationUsageDescription": (
            "O WiFi Sensing usa sua localização para identificar o nome (SSID) "
            "e o endereço (BSSID) das redes Wi-Fi vizinhas durante a análise."
        ),
        "NSLocationWhenInUseUsageDescription": (
            "O WiFi Sensing usa sua localização para identificar o nome (SSID) "
            "e o endereço (BSSID) das redes Wi-Fi vizinhas durante a análise."
        ),
    },
}

setup(
    app=APP,
    name="WiFiSensing",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
