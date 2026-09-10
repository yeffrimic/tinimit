# Tinimit — trabajo pendiente

> *tinimit* = "comunidad / pueblo" en K'iche'. (Antes: "Aldea Salud".)

> Lo ya hecho y verificado está en `README.md`. Este documento es solo lo que falta.
> Plan original aprobado: `~/.claude/plans/idea-principal-pivoteemos-sobre-floating-llama.md`

---

## Contexto en una línea

Kiosko web (`prototipo/kiosk.html`) + hub FastAPI (`hub/`) con inferencia médica 100 %
local sobre QVAC/MedPsy. **Fases 1–4 listas + extras** (interfaz de dos modos, backend,
enlace comprimido real, SQLite en dos niveles, panel de conversaciones, mapa de insumos
por localidad, idioma K'iche' —mecanismo—, conversaciones agrupadas, guardia
anti-inyección). Falta: **grabar el video** (lo hace el usuario) y opcionalmente las
traducciones K'iche' validadas + el stretch de Pears.

## Estado para presentar — checklist

| | |
|---|---|
| ✅ | Kiosko: menú ↔ conversación, motivos guiados, texto libre, EMERGENCIA con relevo, cola offline, selector ES·K'ICHE' |
| ✅ | Conversaciones: agrupadas por `conversacion_id`, guardadas en el dispositivo, "✚ Nueva consulta", reabrir con contexto; el panel las abre completas |
| ✅ | Hub: MedPsy-4B local, 3 modos clínicos, respaldo curado, señales de alarma |
| ✅ | Guardia anti-inyección / fuera de tema (no llama al modelo, no filtra nada del sistema) — `test_medical.py` |
| ✅ | Enlace comprimido real (codec DEFLATE+dicc + airtime Semtech), números por respuesta |
| ✅ | SQLite `device.db`/`hub.db` + sync + "simular caída del enlace" |
| ✅ | Panel: alertas con sonido, mapa de consultas, conversaciones, buscador |
| ✅ | `/insumos`: aldea + 5 lugares, inventario editable, cobertura por localidad |
| ✅ | Docs: `README.md`, `docs/arquitectura.md`, `docs/hardware.md`, `docs/idiomas-maya.md`, `docs/rendimiento.md` (carga/TTFT/tok-s medidos) |
| ✅ | `LICENSE` MIT · README con la tabla "Categoría Psy de QVAC — cumplimiento" (cada requisito) |
| ✅ | `hub/tools/perf_log.py` — registro de rendimiento estructurado reproducible |
| ✅ | Pruebas: `test_store` `test_enlace` `test_plantillas` `test_medical` en verde |
| ⬜ | **Video ≤ 5 min** (lo graba el usuario) → pegar el enlace en README + CONTINUAR |
| ⬜ | Opcional: 68 frases clínicas K'iche' validadas (mecanismo listo, faltan las traducciones) |
| ⬜ | Opcional / bonus: **Pears** — replicar alertas a un hub par y/o delegar inferencia (libs bundleadas en el worker) |

Arranque para la demo: `bash hub/run.sh` → kiosko `/`, panel `/panel`, insumos `/insumos`.
Datos de ejemplo: `python hub/tools/seed_demo.py --reset` (12 personas, 30 conversaciones,
2 emergencias abiertas).

## Reglas del challenge que siguen importando

- **Inferencia 100 % en dispositivo o entre pares. Enrutar inferencia a una API en la
  nube DESCALIFICA.** La nube solo para UI/transporte.
- **Entrega: antes del 11 sep, 08:00 hora de Panamá.** Repo accesible al jurado +
  **video ≤ 5 min** con enlace sin credenciales (es lo primero que revisan).
- **Toda base preexistente debe declararse en el README** (ya está en `README.md`).
- Evaluación: Technical 35 / Innovation 25 / Impact 20 / Design 10 / Completion 10.
- **Bonus**: usar **Pears** (Holepunch) para comunicación o delegación de inferencia P2P.

## Decisiones vigentes (no volver a discutir)

| Tema | Decisión |
|---|---|
| Modelo | **MedPsy-4B de QVAC** (`HEALTHCARE_4B_MEDICAL_Q4_K_M`), razonamiento en `<think>` que el hub descarta. Alternativas por `ALDEA_MODEL`: MedPsy-1.7B, MedGemma-4B. El hub filtra respuestas con mezcla de idiomas y cae al texto curado. |
| Recursos de la aldea | **Por localidad y por aldea**: varios puntos (puesto de salud lejano, minifarmacia, botiquín comunitario, promotora, tienda), cada uno con su inventario y sector. La IA recibe lo cercano al sector de la persona y recomienda primero eso, no el puesto a 2 horas. |
| Simulador de dispositivo | Nada de Wokwi ni firmware. Todo corre en la laptop; la demo sirve la página localmente y se narra cómo va en el ESP32 real (`docs/hardware.md`). |
| Enlace hoy | WiFi/HTTP local. El **códec de compresión debe ser real** y demostrarse con bytes/tramas. Un módulo `link` aísla el transporte para pasar a LoRa después. |
| Topología del video | Con **repetidor**: salto Aldea → Repetidor → Hub, simulado en `link.py`. |
| Almacenamiento | Dos niveles: `device.db` (aldea) + `hub.db` (central) + `sync_device_to_hub()`. En la demo ambos son archivos en la laptop. |
| Identidad | MAC del teléfono, sin login. En web = MAC simulada por navegador; en ESP32 real = `esp_wifi_ap_get_sta_list()` + leases DHCP. |
| Idioma | Español completo + **K'iche' (`quc`)** por `hub/plantillas/`. El modelo razona en español y elige; el texto maya sale de plantillas **curadas y validadas** (ALMG/MSPAS), nunca del modelo. No hay traducción automática local es→maya en QVAC. Lo no traducido: español marcado. |
| Pears | **Stretch goal**, solo si el flujo base queda sólido. Worker Bare bundleado en `~/.cache/qvac/worker/0.19.0/node_modules/` ya trae `hyperswarm`, `hyperbee`, `hypercore`, `corestore`. |
| SBC real | QVAC soporta `linux-arm64` + CPU-only. El usuario aún no tiene la SBC → el hub corre en la laptop para el hackathon. |

## Arquitectura objetivo

```
  Kiosko (navegador del vecino)          Hub central (laptop, luego SBC)
  +-----------------------------+        +-------------------------------------+
  | kiosk.html (SoftAP en ESP32)|        | server.py (FastAPI)        [hecho]  |
  |  alta por MAC        [hecho] |        |  qvac_engine.py -> MedPsy    [hecho] |
  |  motivos + guiado   [hecho] |        |  medical.py (3 modos)      [hecho]  |
  |  fetch a /api/*     [hecho] |==LoRa==|  codec.py (DEFLATE+dicc)   [hecho]  |
  |  chat + EMERGENCIA  [hecho] | (hoy:  |  link.py (tramas, airtime) [hecho]  |
  |  cola offline       [hecho] |  WiFi) |  store.py -> device/hub.db [hecho]  |
  +-----------------------------+        |  panel.html               [hecho]  |
                                          +-------------------------------------+
                        (stretch) mesh/ Node + hyperswarm/hyperbee:
                        replica alertas de emergencia a un hub par con señal
```

---

## Idioma maya — mecanismo hecho, faltan las traducciones

El mecanismo completo está (ver `README.md` y `docs/idiomas-maya.md`): `hub/plantillas/`
(esquema + resolver), `lang` enrutado por `medical.py`, `idioma_respuesta` en la
respuesta, selector `ES · K'ICHE'` y burbujas de español marcadas en el kiosko. El
modelo razona en español y clasifica; **nunca genera texto maya**.

Objetivo: **K'iche' (`quc`)**. Estado: 0/68 cadenas clínicas traducidas (solo
`langName` y un saludo tentativo).

**Ya incorporado** (ver `docs/idiomas-maya.md` → "Fuentes ya incorporadas"):
- UI de la localización de Firefox de Mozilla (MPL-2.0, revisada por la comunidad):
  K'iche' de Focus for Android (`saludo`="Utz apetem", `guardar`="Uk'olik"…),
  Kaqchikel de Firefox (`guardar`="Tiyak", `volver`="Titzolïx", OK/Cancel/Sí/No…).
- Glosario K'iche' de vocabulario de salud en `hub/plantillas/quc.py` → `GLOSARIO`
  (de Wiktionary Swadesh + diccionario ALMG + Christenson).

Falta:
- **Las 68 frases clínicas en K'iche'** — necesitan un hablante fluido con formación
  en salud comunitaria (traducir palabra por palabra desde el glosario da frases
  peligrosas). Fuentes: ALMG, materiales bilingües del MSPAS, "Manual del promotor"
  de OPS. Lista: `python hub/tools/listar_claves.py quc --solo-clinico`. Al validar
  una, va en `hub/plantillas/quc.py` (`T`) y se activa sola.
- Reflejar las etiquetas/repreguntas validadas en `prototipo/kiosk.html`
  (`I18N.quc`, `GUIAS_OFFLINE` — hoy sin variante `quc`) para el modo sin enlace.
- El `disclaimer` y la nota `📍 Dónde conseguirlo` hoy quedan en español aunque la
  orientación sea K'iche' (respuesta mixta) — traducir también.
- (Opcional) Q'eqchi' / Mam: crear `hub/plantillas/kek.py` / `mam.py` (códigos ya
  reservados en `codec.LANGS`).

## Recursos de la aldea — hecho, pendiente de curar mejor

`hub/recursos.py` tiene **5 puntos** (puesto de salud, minifarmacia, botiquín comunitario
de Panimaché, promotora de Xepiacul, tienda de El Tablón) con su inventario por punto
(tabla `recursos(punto_id, item, ...)` en `store.py`, editable desde el panel y desde
`/insumos`) + ~8 hierbas de la zona. La IA recibe lo que hay **cerca del sector de la
persona** (los puntos locales antes que la minifarmacia del centro, y el puesto de salud
lejano al final) y recomienda lo más cercano; nota `📍 Dónde conseguirlo` en el flujo
guiado. `GET /insumos` = diagrama radial (aldea + 5 lugares), inventario editable por
lugar, cobertura por localidad y "cómo se administran".
Falta:
- **Validar la lista de hierbas** con alguien de la comunidad / herbolario / ALMG.
- Ajustar puntos e inventarios a la aldea real (nombres, distancias, qué tiene cada uno).
- Poder crear/editar puntos desde el panel (hoy el catálogo de puntos es fijo en `recursos.py`).
- Opcional: registrar qué recomendó el modelo para planear el reabastecimiento.

## Mejoras del panel (opcionales, para el video)

- El **mapa** de `panel.html` sigue siendo un layout de posiciones fijas por sector
  (`SECTORES_POS`). `/insumos` tiene un diagrama radial simple (aldea al centro, lugares
  alrededor, sin librerías) que se puede reusar de base para un grafo dirigido por
  fuerza en el panel (sectores ↔ motivos ↔ personas) si hay tiempo.
- El `/panel` quedó reducido a lo esencial (alertas, mapa, **conversaciones**, buscador).
  El inventario se movió a `/insumos`.
- **Conversaciones ✅** hechas: el kiosko agrupa turnos por `conversacion_id`, guarda las
  conversaciones en el dispositivo (título = síntoma + fecha, "✚ Nueva consulta",
  reabrir con contexto), el hub las almacena (`conversaciones` en `store.py`, `/api/panel/
  conversacion*`), el panel muestra la lista con título + fecha y se abren completas, y
  el modelo recibe los títulos de las conversaciones previas. Pendiente opcional:
  traducir a K'iche' los rótulos nuevos ("Consultas anteriores", "Nueva consulta",
  "Retomando…") en `hub/plantillas/quc.py` / `I18N.quc`.
- Feed por SSE en vez de polling cada 3.5 s.

## FASE 5 — Video (lo hace el usuario)

- **`docs/arquitectura.md`** ✅ · **`docs/hardware.md`** ✅ · **`docs/idiomas-maya.md`** ✅
- **`README.md`** — falta solo pegar el enlace al video cuando exista.
- Guion sugerido (≤ 5 min): consulta guiada → título + historial en el panel →
  reabrir una conversación (contexto) → EMERGENCIA + relevo Aldea→Repetidor→Hub →
  números del enlace comprimido → mapa de insumos por localidad → intento de "hackeo"
  bloqueado → "sin enlace" (cola offline) → (stretch) sync/Pears.
- Subir el video a un enlace público sin login y agregarlo al README.

## STRETCH — Pears / Holepunch (bonus opcional)

**Qué es.** La pila P2P de Holepunch, ya bundleada en el worker Bare de QVAC
(`~/.cache/qvac/worker/0.19.0/node_modules/`: `hyperswarm`, `hyperbee`, `hypercore`,
`corestore`, `autobase`). Sin servidores:
- **hyperswarm** — descubre peers por un "topic" (clave de 32 bytes) en una DHT y abre
  una conexión **directa y cifrada extremo a extremo**, atravesando NAT (hole-punching).
- **hypercore** — log append-only firmado, replicado por bloques (solo lo que falta).
- **hyperbee** — base clave-valor / B-tree sobre un hypercore.

**El hackathon lo valora como extra** ("Se valora de forma adicional el uso de Pears
para la comunicación o la delegación de inferencia entre pares. No es obligatorio").

**Cómo encaja en Tinimit** (2 opciones, cualquiera cuenta):

1. **Replicar alertas de emergencia a un hub par.** Escribir las alertas de `hub.db`
   también en un hyperbee; un "hub regional" con mejor señal se une al mismo topic de
   hyperswarm y lo replica. Aldea aislada → la alerta llega igual en cuanto haya
   cualquier ruta. Demo: 2 procesos `hub` en la laptop, "cortar" el enlace, lanzar una
   emergencia, verla aparecer en el par.
2. **Delegar `completion` a un peer.** Un nodo sin modelo (SBC de otra aldea) pide la
   inferencia a un peer que tiene MedPsy cargado y recibe los tokens de vuelta por la
   conexión de hyperswarm. Cubre literalmente "delegación de inferencia entre pares".
   (El SDK ya tiene `CompletionOrchestrateRequest` / `assess_model_fit` — mirar eso
   primero.)

**Plan mínimo.** `mesh/` = sidecar Node/Bare que abre el swarm y expone un socket local
que el hub Python consume; empezar por la opción 1 (más simple y con demo clara).
Hoy Tinimit corre entero en el dispositivo/LAN y compite igual sin esto.

---

## Cómo retomar en un chat nuevo

Abrir el chat en `/home/yeffrimic/aldea/` y decir algo como:

> "Continúo Tinimit. Lee `README.md` (lo hecho) y `CONTINUAR.md` (lo pendiente).
> Empecemos la **Fase 5** (empaque + video): `docs/arquitectura.md`, `docs/guion-video.md`,
> grabar. O el grafo del panel si hay tiempo."

Notas:
- Venv de QVAC: `~/Documents/qvac/.venv`. Referencia viva del SDK: `~/Documents/qvac/app.py`.
- Arranque del hub: `bash hub/run.sh` → kiosko en `/`, panel en `/panel`.
- Datos de demo para el panel: `python hub/tools/seed_demo.py --reset`.
- Pruebas sin modelo: `python hub/test_enlace.py && python hub/test_store.py`.
- Regla dura: **ninguna llamada de inferencia a la nube.** Verificar con el `grep` del README.
- Si el modelo da `File descriptor could not be locked`: `pkill -f bare-runtime`.
