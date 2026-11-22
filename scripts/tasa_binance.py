#!/usr/bin/env python3
"""Anota una lectura de la tasa USDT/VES (Binance P2P) en tasas_binance.json.

Uso:  python3 scripts/tasa_binance.py <respuesta_vzla.json> <tasas_binance.json>

Lee el campo data.usdt.rate de la respuesta de Vzla.io (bolivares por 1 USDT).
NO usa data.computed.average.rate (es el punto medio entre BCV y USDT).
El token NO se usa aqui: la consulta la hace el workflow con el secreto VZLA_TOKEN.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

DIAS_GUARDADOS = 400          # historial maximo que se conserva en el archivo
MIN_VALIDO, MAX_VALIDO = 1, 1_000_000


def fallar(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        fallar("uso: tasa_binance.py <respuesta.json> <tasas_binance.json>")
    ruta_resp, ruta_out = sys.argv[1], sys.argv[2]

    try:
        with open(ruta_resp, encoding="utf-8") as f:
            resp = json.load(f)
    except Exception as e:
        fallar("la respuesta no es un JSON valido (%s)" % type(e).__name__)

    data = resp.get("data") if isinstance(resp, dict) else None
    usdt = data.get("usdt") if isinstance(data, dict) else None
    if not isinstance(usdt, dict):
        fallar("la respuesta no trae data.usdt. Claves recibidas: %s"
               % (sorted(data.keys()) if isinstance(data, dict) else "sin data"))

    # Se imprime lo que trae data.usdt (datos de mercado, sin credenciales)
    # para poder confirmar en el log si el valor es compra, venta u otro.
    visibles = {k: v for k, v in usdt.items()
                if isinstance(v, (str, int, float, bool, type(None)))}
    print("data.usdt =", json.dumps(visibles, ensure_ascii=False))

    try:
        valor = float(usdt.get("rate"))
    except (TypeError, ValueError):
        fallar("data.usdt.rate no es un numero")
    if not (MIN_VALIDO < valor < MAX_VALIDO):
        fallar("data.usdt.rate fuera de rango: %r" % valor)
    valor = round(valor, 4)

    ahora = datetime.now(timezone.utc)
    caracas = ahora - timedelta(hours=4)           # Venezuela: UTC-4 todo el año
    lectura = {
        "t": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "f": caracas.strftime("%Y-%m-%d"),         # dia (hora de Caracas)
        "h": caracas.strftime("%H:%M"),            # hora de Caracas
        "v": valor,
        "o": os.environ.get("GITHUB_EVENT_NAME", "local"),
    }

    lecturas = []
    if os.path.exists(ruta_out):
        try:
            with open(ruta_out, encoding="utf-8") as f:
                lecturas = json.load(f).get("lecturas", [])
        except Exception:
            fallar("tasas_binance.json existe pero no se pudo leer; no se sobrescribe")

    lecturas.append(lectura)
    corte = (caracas - timedelta(days=DIAS_GUARDADOS)).strftime("%Y-%m-%d")
    lecturas = [l for l in lecturas if l.get("f", "") >= corte]
    lecturas.sort(key=lambda l: l.get("t", ""))

    filas = ",\n".join("  " + json.dumps(l, ensure_ascii=False, separators=(",", ":"))
                       for l in lecturas)
    cuerpo = (
        '{\n "version":1,\n "zona":"America/Caracas",\n "campo":"data.usdt.rate",\n'
        ' "actualizado":"%s",\n "lecturas":[\n%s\n ]\n}\n'
        % (lectura["t"], filas)
    )
    json.loads(cuerpo)                              # verificacion antes de escribir

    carpeta = os.path.dirname(os.path.abspath(ruta_out))
    fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cuerpo)
    os.replace(tmp, ruta_out)
    print("Lectura anotada: %s %s Bs %.4f (%d lecturas en el archivo)"
          % (lectura["f"], lectura["h"], valor, len(lecturas)))


if __name__ == "__main__":
    main()
