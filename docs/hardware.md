# Tinimit en hardware real (ESP32 + LoRa)

Para el hackathon todo corre en la laptop y el "enlace" es HTTP local, pero el
`codec` y el `link` imponen las restricciones reales de LoRa para que los números de
la demo sean verdaderos. Este documento describe cómo se lleva a un dispositivo real.

## Topología

```
  Teléfono del vecino          ESP32 "nodo aldea"            Repetidor           SBC / hub
 ┌───────────┐   WiFi   ┌──────────────────────┐   LoRa    ┌──────────┐  LoRa  ┌──────────────────┐
 │ navegador │◄────────►│ SoftAP + servidor web │─ tramas ─►│ reenvía  │───────►│ radio LoRa (SPI) │
 │ kiosk.html│  local   │ sirve kiosk.html      │  ≤66 B    │ (salto 2)│        │  ↓               │
 │           │          │ codec (C) comprime    │◄──────────│          │◄───────│ reensambla       │
 │           │          │ link  (C) fragmenta   │           └──────────┘        │ codec (Python)   │
 └───────────┘          └──────────────────────┘                               │ gateway → /api/* │
                                                                               │ medical + MedPsy  │
                                                                               │ store (SQLite)   │
                                                                               └──────────────────┘
         (la respuesta hace el mismo camino en reversa, comprimida)
```

**El API HTTP no se reescribe.** Cuando llega LoRa, un `lora_gateway.py` en la SBC
escucha la radio, reensambla + descomprime con `codec.decode`, y llama al FastAPI de
siempre (`POST http://localhost:8000/api/consulta`) o directamente a las funciones de
`medical.py`. La respuesta se comprime, se fragmenta y vuelve por la radio.

## Qué vive en cada lado

| Pieza | ESP32 nodo aldea | Hub / SBC |
|---|---|---|
| `kiosk.html` | sí, en LittleFS (servido por SoftAP) | — |
| `codec` (envelope + DEFLATE + diccionario) | reimplementación en C (miniz o heatshrink) con el **mismo `dictionary.txt`** | `hub/codec.py` |
| `link` (fragmentar, airtime, dwell) | C, habla con el chip SX127x | `hub/link.py` (simulación) |
| `medical.py`, `qvac_engine.py`, `store.py`, modelo | — | solo aquí |

El `dictionary.txt` (`hub/dictionary.txt`, ~7.8 KB) debe ir **byte-idéntico** como
constante en el firmware; regenerarlo con `hub/tools/build_dict.py` tras cualquier
cambio en `hub/guias.py`.

## ¿Cabe `kiosk.html` en un ESP32?

Sí, con muchísimo margen.

| Recurso | Necesidad | ESP32-WROOM-32 (4 MB flash) |
|---|---|---|
| `kiosk.html` | **48 KB** (≈13 KB con gzip) | partición LittleFS ~1.5 MB → **usa ~1–3 %** |
| Firmware (WiFi SoftAP + servidor HTTP + driver SX127x + codec en C) | ~0.7–1.0 MB | partición app ~1.2–1.9 MB → entra |
| `dictionary.txt` | ~8 KB constante en flash/PROGMEM | trivial |
| codec en C | miniz ≈ 6 KB de código / heatshrink ≈ 2 KB | trivial |
| RAM | servir el HTML **por streaming** desde LittleFS (buffer 2–8 KB), no cargarlo entero | ESP32 tiene 320 KB; ~160–200 KB libres con WiFi+SoftAP → bien para 1–2 clientes |

Las **respuestas del modelo no se guardan en el ESP32**: llegan del hub como JSON
(~300–600 B) y se pintan. No hay nada del lado del modelo que "quepa".

Servir con `Content-Encoding: gzip` (pre-comprimir el asset en la imagen) → ~13 KB en
el aire, más rápido en el teléfono.

## Caveat: fuentes web offline

`prototipo/kiosk.html` carga Fraunces / Public Sans / IBM Plex Mono desde
`fonts.googleapis.com` (línea 2). En un SoftAP **sin internet** esa petición falla en
silencio y el CSS cae a `Georgia` / `system-ui` / `ui-monospace` (ya están en las
cadenas `var(--font-*)`). La página queda funcional y legible, solo pierde la
tipografía de exhibición.

Para un kiosko de producción, elegir una:
- **(a)** subsetear y auto-hospedar los `.woff2` en LittleFS (~30–60 KB cada uno,
  ~100–150 KB total — entra, pero es espacio real);
- **(b)** auto-hospedar solo la fuente de titulares y dejar el resto en fuentes del
  sistema;
- **(c)** aceptar el fallback a fuentes del sistema (recomendado para el hackathon:
  borrar la línea 2).

Los emoji de los íconos (🌡️ 🩹 …) los pinta la fuente de emoji **del teléfono**, no
el ESP32, así que no se ven afectados.

## Envelope del `codec` (para la reimplementación en C)

Cabecera fija de 5 bytes, big-endian (`struct.pack(">B H B B", …)`), seguida del
stream DEFLATE crudo (`wbits=-15`, `zdict = dictionary.txt`):

| offset | bytes | campo | valores |
|---|---|---|---|
| 0 | 1 | `tipo` | `consulta`=1, `repregunta`=2, `orientacion`=3, `emergencia`=4, `emergencia_ack`=5, `perfil`=6 |
| 1 | 2 | `id` | uint16 BE, secuencia del hub, wrap mód 65536; el downlink repite el id del uplink |
| 3 | 1 | `prioridad` | `rutina`=0, `urgente`=1, `emergencia`=2 |
| 4 | 1 | `lang` | `es`=0, `cak`=1, `quc`=2 (K'iche'), `kek`=3, `mam`=4 (ISO 639-3) |
| 5 | … | `payload` | DEFLATE crudo del texto UTF-8 |

Cada trama del `link` antepone 3 bytes más: `msg_id(1) · idx(1) · total(1)`, y lleva
hasta 63 bytes del stream del envelope (PHY payload ≤ 66 B → airtime ≤ 390 ms →
cumple el límite de dwell de 400 ms de US915).

## Parámetros de radio asumidos (`hub/link.py`)

LoRa US915, SF9, BW 125 kHz, CR 4/5, preámbulo 8, CRC on, cabecera explícita.
Airtime por la ecuación de Semtech (SX1276 §4.1.1.7): `Tsym = 4.096 ms`,
`Tpreamble = 50.176 ms`, trama de 66 B ≈ **390 ms**. Relevo modelado como
store-and-forward: `airtime_total = 2 · airtime_una_vía + 50 ms`.

EU868 sería distinto: sin límite de dwell pero con 1 % de ciclo de trabajo
(~36 s de aire por hora); permitiría tramas de hasta 222 B.

## Identidad por MAC en hardware real

Hoy la MAC la genera el navegador (`AA:BB:CC:xx:xx:xx` en `localStorage`). En el ESP32
real el JS **no** puede leer la MAC del cliente, así que el **ESP32** la añade al
envelope antes de comprimir, leyéndola de `esp_wifi_ap_get_sta_list()` + los leases
DHCP del SoftAP. El vecino no hace nada.
