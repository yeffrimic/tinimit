# Arquitectura de Tinimit

*tinimit* = "comunidad / pueblo" en K'iche'.

Orientación médica por chat para aldeas **sin cobertura**, con la inferencia **100 %
local** sobre QVAC. Ningún dato ni ninguna llamada de inferencia sale a internet.

---

## Vista general

```
   VECINO (teléfono)                 NODO DE LA ALDEA              HUB / PUESTO DE SALUD
   ┌───────────────┐   WiFi SoftAP   ┌──────────────┐   LoRa      ┌────────────────────┐
   │  kiosk.html    │◄──────────────►│  ESP32        │◄══════════►│  SBC / laptop       │
   │  (navegador)   │  HTTP local    │  + radio      │  (repetidor │  server.py (FastAPI)│
   │               │                │               │   1 salto)  │  qvac_engine → LLM  │
   │  · alta por MAC│                │  device.db    │             │  medical.py         │
   │  · motivos     │                │  (SQLite)     │─── sync ───►│  hub.db (SQLite)    │
   │  · chat        │                │               │             │  panel.html /insumos│
   │  · EMERGENCIA  │                │  codec + link │             └────────────────────┘
   │  · cola offline│                └──────────────┘
   └───────────────┘

   Hoy (demo): kiosko, nodo y hub corren en la laptop; el "salto LoRa" se simula en
   link.py con la ecuación de airtime de Semtech. En hardware, kiosk.html lo sirve el
   SoftAP del ESP32 y el hub es una SBC linux-arm64 (QVAC corre CPU-only ahí).
```

Ver `docs/hardware.md` para el detalle del ESP32 + LoRa (envelope, MTU, dwell, códec en C).

---

## Componentes

### 1. Kiosko — `prototipo/kiosk.html`

Un solo archivo, sin framework, mobile-first. Dos modos claros:

- **Menú**: botón EMERGENCIA, grilla de 9 motivos, "Tus consultas anteriores".
- **Conversación**: barra con el título del hilo + "✚ Nueva consulta", chat, input.

Estado en `localStorage`: `aldea.mac` (identidad), `aldea.profile` (perfil mínimo),
`aldea.lang`, `aldea.convs` (conversaciones guardadas en el dispositivo),
`aldea.outbox` (cola de envíos sin enlace).

Cada intercambio va a `POST /api/consulta` o `/api/emergencia` con un
`conversacion_id` (uuid del cliente). Sin enlace, se encola y se reintenta.

### 2. Hub — `hub/`

| Archivo | Rol |
|---|---|
| `server.py` | FastAPI. Endpoints `/api/*`, sirve kiosko/panel/insumos, calcula el coste real del enlace por cada respuesta. |
| `qvac_engine.py` | Envuelve el runtime de QVAC. Carga perezosa del modelo, descarta el bloque `<think>` de MedPsy, filtra mezcla de idiomas. |
| `medical.py` | Lógica clínica. 3 modos (guiado / libre / emergencia) + red de seguridad: señales de alarma, anti-inyección, respaldo al texto curado, disclaimer permanente. |
| `guias.py` | Contenido clínico **curado a mano** (repreguntas, orientaciones, primeros auxilios). Nada generado por el modelo. |
| `recursos.py` | Dónde conseguir medicina, **por localidad**: 5 puntos con inventario + hierbas de la zona. |
| `codec.py` | Compresión real: DEFLATE crudo con diccionario preentrenado + envelope de 5 bytes. |
| `link.py` | Simulador del enlace LoRa: airtime por la ecuación de Semtech (SF9/BW125), límite de dwell, fragmentación, saltos. |
| `store.py` | SQLite en dos niveles (`device.db` / `hub.db`) + `sync_device_to_hub()`. Pacientes, conversaciones, consultas, alertas, recursos. |
| `plantillas/` | Capa de idiomas: el modelo razona en español, el texto maya sale de plantillas curadas y validadas. |
| `panel.html` | Panel del puesto de salud: alertas, mapa de consultas, conversaciones (se abren completas), buscador. |
| `insumos.html` | Mapa de la aldea (aldea al centro, 5 lugares alrededor) + inventario editable. |

### 3. Modelo — MedPsy-4B de QVAC (`HEALTHCARE_4B_MEDICAL_Q4_K_M`)

Qwen3-4B-Thinking afinado en salud. Piensa en `<think>` (el hub lo descarta) y responde
en español. El **contenido clínico nunca depende del modelo**: el modelo adapta el tono
de textos ya revisados y, si se sale de rango, se sirve el texto curado.

---

## Flujo de una consulta guiada

```
1. Vecino toca "Fiebre"            → kiosk: nueva conversación (uuid), modo chat
2. POST /api/consulta {motivo,mensajes,conversacion_id}
3. medical.consulta_guiada:
     · ¿señal de alarma en el texto?  → aviso de EMERGENCIA, fin
     · ¿intento de inyección / fuera de tema? → respuesta acotada, sin modelo
     · faltan repreguntas             → devuelve la siguiente (curada)   [estado: seguimiento]
     · repreguntas completas          → orientación curada + frase cálida del modelo
                                        + nota "📍 Dónde conseguirlo" (según el sector) [final]
4. server:
     · codec.encode + link.simular    → bytes / tramas / airtime reales (uplink+downlink)
     · store.registrar_conversacion   → transcripción al día, título = síntoma
     · store.log_consulta (si final)  → fila con los bytes del enlace
5. kiosk: muestra la respuesta + chip del enlace; guarda la conversación en el dispositivo
```

Emergencia: igual, pero prioridad máxima fija, pasos de `FIRST_AID` (curados, siempre) +
una nota corta del modelo, y animación del relevo Aldea → Repetidor → Hub.

---

## Datos y privacidad

- **Identidad** = MAC del teléfono (sin login). En web se simula; en el ESP32 real sale
  de `esp_wifi_ap_get_sta_list()` + leases DHCP.
- **Dos niveles**: cada consulta se escribe primero en `device.db` (el nodo de la aldea)
  y se replica a `hub.db` (el puesto de salud). Si el enlace cae, las filas se acumulan
  en `device.db` y el panel no las ve hasta reconectar (`store.enlace_hub`).
- **Nada sale a la nube.** La inferencia corre en el runtime local de QVAC. La nube, si
  se usa, es solo para servir la interfaz o como túnel de bytes.
- **Conversaciones**: el modelo recibe los *títulos* de las conversaciones previas de la
  persona (no el texto completo). Si retoma una vieja, su transcripción entera viaja
  como contexto.

---

## Red de seguridad (medical.py)

| Situación | Qué hace |
|---|---|
| Palabras de alarma ("no respira", "sangra mucho", "no despierta"…) | corta y manda a EMERGENCIA |
| Intento de sacar al asistente del guion / prompt injection ("ignora tus instrucciones", "qué modelo eres", "actúa como…") | respuesta fija: "solo puedo ayudarte con temas de salud"; **no** se llama al modelo, **no** se revela nada del sistema |
| El modelo responde en otro idioma, con basura, o filtra que es una IA / su prompt | se descarta y se usa el texto curado de `guias.py` |
| El modelo falla o se cae | respaldo curado |
| Siempre | disclaimer permanente, sin diagnóstico definitivo, deriva al puesto de salud |

Cobertura: `hub/test_medical.py`, `hub/test_store.py`, `hub/test_enlace.py`,
`hub/test_plantillas.py`.
