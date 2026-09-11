# Tinimit

> *tinimit* — "comunidad / pueblo" en K'iche'.

Orientación médica por chat para aldeas remotas **sin cobertura**, con la inferencia
corriendo **100 % local** sobre [QVAC](https://qvac.tether.io).

Un dispositivo barato (ESP32 + radio LoRa) se instala en la aldea y da su propia WiFi.
Los vecinos abren un **chat web** en el teléfono y hacen una **consulta o alerta médica**.
El texto se **comprime** y viaja por un enlace de largo alcance hasta un **hub central**
que hace la inferencia con un modelo médico local y devuelve la respuesta comprimida.
Todas las consultas quedan **registradas** identificando a la persona por la **MAC del
teléfono** (sin login), con un perfil mínimo. Los datos viven en el dispositivo y en el
hub, **nunca en la nube**.

Proyecto para el **Decentralized AI Hackathon** — *Sovereign Intelligence at the Edge*
(ISD Summit + Tether/QVAC, 9–11 sep 2026). Compite en el **ranking general** (donde el
tema del evento es la soberanía de la IA en el borde) y en la **categoría Psy de QVAC**
(MedPsy en función central). Licencia **MIT** (`LICENSE`). Regla dura: *enrutar
inferencia a una API en la nube descalifica*; la nube solo para servir la interfaz o el
almacenamiento no sensible.

- **Demo (video ≤ 5 min):** https://www.tiktok.com/@yeffrimic/video/7684117435041074450 
- **Registro de rendimiento** (carga, TTFT, tok/s): [`docs/rendimiento.md`](docs/rendimiento.md).
- **Arquitectura:** [`docs/arquitectura.md`](docs/arquitectura.md) · **Hardware/LoRa:** [`docs/hardware.md`](docs/hardware.md) · **Idioma maya:** [`docs/idiomas-maya.md`](docs/idiomas-maya.md).

### Soberanía — el eje del proyecto

*"IA que funcione donde la nube no llega, no debería llegar o cuesta demasiado."* Tinimit
es exactamente eso, en varias capas:

| Capa | Cómo |
|---|---|
| **Datos** | El historial médico **nunca sale de la aldea**. Identidad por MAC del teléfono, sin login, sin terceros. `device.db` (nodo de la aldea) → `hub.db` (puesto de salud); ninguna base sale a internet. |
| **Infraestructura** | La aldea corre **su propio nodo** (ESP32 + radio) y su propia WiFi. No depende de cobertura de telecom ni de un proveedor cloud que pueda caerse, cortar el servicio, cobrar o censurar. Funciona con el enlace intermitente (cola offline) y sin él (texto curado local). |
| **Inteligencia (edge)** | **MedPsy-4B corre 100 % local** sobre hardware barato que la comunidad posee: ~62 tok/s y TTFT ~150 ms en una GPU de 6 GB; el objetivo real es una SBC ARM (`linux-arm64`, CPU-only). Un modelo pequeño no es una limitación aquí — es lo que hace posible que la aldea sea dueña de su IA. |
| **Clínica** | El contenido que importa (`hub/guias.py`) lo revisan **humanos de la comunidad** (ALMG / MSPAS); el modelo adapta el tono, no inventa el consejo. Red de seguridad: señales de alarma → emergencia, guardia anti-inyección, respaldo curado, disclaimer permanente. |
| **Lengua y cultura** | K'iche' **curado y validado por la comunidad**, nunca generado por máquina (`hub/plantillas/`). El nombre del proyecto es K'iche'. |
| **Control local** | El puesto de salud es dueño del registro y del inventario de medicina **por localidad**: ve quién consulta, desde dónde y sobre qué, y decide. |

Esto es también lo que la **categoría Psy** premia: calidad de dominio medible en hardware
edge realista, riesgos del dominio gestionados con responsabilidad, un modelo pequeño
resolviendo un problema concreto que se beneficia de ese tamaño.

### Categoría Psy de QVAC — cumplimiento

| Requisito | Cómo se cumple |
|---|---|
| **Un modelo Psy en función central del flujo principal** | **MedPsy-4B** (`HEALTHCARE_4B_MEDICAL_Q4_K_M`) escribe la orientación que recibe el vecino en cada consulta libre y la frase cálida + adaptación en la guiada, y la nota de la emergencia. Sin el modelo el flujo sigue vivo con texto curado, pero la respuesta "de la IA" es del modelo. |
| **`@qvac/sdk` para toda la inferencia y el transporte de pesos** | `hub/qvac_engine.py` usa `tetherto.qvac_sdk` (`Client`, `load_model`, `completion`). Los pesos GGUF se descargan del registro de QVAC por hyperswarm. No hay otra vía de inferencia. |
| **Experiencia principal local en hardware de consumo declarado** | Todo corre en una laptop con RTX 2060 (6 GB) — specs abajo. El objetivo real es una SBC ARM en la aldea (QVAC soporta `linux-arm64` CPU-only). Los servicios remotos solo servirían para sync opcional (Pears, ver abajo); la app es útil sin ellos. |
| **Sin inferencia en la nube en lo evaluado** | Verificado: `grep -riE "openai\|anthropic\|groq\|https?://" hub/*.py` no encuentra ninguna llamada de red saliente. |
| **Divulgar APIs remotas y componentes de terceros** | Sección "Base preexistente / terceros" abajo. **Ninguna API remota** en el camino principal. |
| **Código abierto, licencia permisiva** | MIT (`LICENSE`). |
| **Instrucciones de configuración + specs de hardware, reproducible** | Sección "Cómo correr" + "Hardware probado" abajo. |
| **Nombres de modelo, cuantización y hardware honestos** | Sección "Modelo" abajo: `HEALTHCARE_4B_MEDICAL_Q4_K_M`, Q4_K_M, Qwen3-4B-Thinking, RTX 2060 Vulkan. |
| **Registro de rendimiento estructurado** | `python hub/tools/perf_log.py` → [`docs/rendimiento.md`](docs/rendimiento.md) + `.json` (carga, prompts, tokens, TTFT, throughput). |
| **Riesgos del dominio, casos de fallo, incertidumbre** | "Red de seguridad" abajo: señales de alarma → emergencia, guardia anti-inyección, respaldo curado, disclaimer permanente, sin diagnóstico, contenido clínico revisado a mano (`guias.py`). |
| **Flujo de usuario completo (no solo una llamada al SDK)** | Kiosko → consulta guiada/libre/emergencia → registro por MAC → panel de conversaciones → mapa de insumos. |
| **Video de demostración** | A cargo del equipo; guion en `CONTINUAR.md`. |

### Pears (bonus, no implementado aún)

**Pear / Holepunch** es la pila P2P (hyperswarm para descubrir y conectar peers con
cifrado extremo a extremo y hole-punching; hypercore = log firmado y replicado;
hyperbee = base clave-valor sobre hypercore). Ya viene bundleada en el worker Bare de
QVAC (`~/.cache/qvac/worker/0.19.0/node_modules/`).

El hackathon la valora como **extra opcional**. Encaja de dos formas y está documentada
como stretch en `CONTINUAR.md`:

1. **Replicar las alertas de emergencia a un hub par.** El `hub.db` de alertas también
   se escribe en un hyperbee que un "hub regional" con mejor señal replica por
   hyperswarm. Si la aldea queda aislada, la alerta llega igual en cuanto haya cualquier
   ruta, aunque sea intermitente.
2. **Delegación de inferencia entre pares.** Un nodo sin modelo (una SBC en otra aldea)
   pide un `completion` a un peer que sí tiene MedPsy cargado y recibe los tokens de
   vuelta — exactamente la "delegación de inferencia entre pares" del enunciado.

Hoy Tinimit corre **entero en el dispositivo / la LAN** y compite en igualdad de
condiciones sin esto.

---

## Qué está hecho y funcionando

### 1. Kiosko — `prototipo/kiosk.html`

Interfaz de un solo archivo (mobile-first, ~360–420 px, JS vanilla, sin framework),
**cableada al hub**: cada consulta y emergencia va a `POST /api/*` y la orientación la
escribe el modelo local. Se sirve desde `GET /` (mismo origen); en hardware real lo
sirve el SoftAP del ESP32.

- Pantalla única: header (aldea · estado de enlace · idioma · ⚙) → botón **EMERGENCIA**
  → grilla de 9 **motivos** → **consultas anteriores** → **chat** → input fijo → disclaimer.
- **Conversaciones guardadas en el dispositivo** (`localStorage["aldea.convs"]`): cada
  consulta es una conversación con un `conversacion_id`. La lista "Consultas anteriores"
  muestra el **título** (síntoma / tema central) y la **fecha en pequeño**; tocar una la
  **reabre** (replica la transcripción y sigue con el mismo hilo, así el modelo tiene el
  contexto). **✚ Nueva consulta** arranca otra. Elegir un motivo también abre una nueva.
- **Alta mínima** la primera vez (nombre, edad, sector, alergias) ligada a la MAC
  (`AA:BB:CC:xx:xx:xx` en `localStorage`, simulada en web); al guardar hace
  `PUT /api/perfil/{mac}` para que el hub tenga el contexto.
- **Motivo → chat guiado server-driven**: el hub devuelve las repreguntas curadas una a
  una (`estado:"seguimiento"`) y al terminar la orientación del modelo
  (`estado:"final"`) con **pill de prioridad**. Sin enlace, las repreguntas salen de
  `GUIAS_OFFLINE` (espejo de `guias.py`) y el envío queda en cola.
- **EMERGENCIA → sub-pantalla**: 7 tipos + "otra/describir" → `POST /api/emergencia` →
  animación de relevo Aldea → Repetidor → Hub (espera a la respuesta real) → primeros
  auxilios del hub (o de `FIRST_AID` local si no hay enlace) + nota del modelo.
- **Chip por respuesta** con los bytes/tramas/airtime **reales** que devuelve el hub
  (`codec.py` + `link.py`): `📡 574→194 B · 3.0× · 4 tramas · 2 saltos · ~2.6 s`.
- **Cola offline real** (`localStorage["aldea.outbox"]`): al caer el enlace o fallar el
  `fetch`, el envío se guarda y se reintenta al reconectar o al recargar la página.
- **Idioma maya (K'iche', `quc`) — mecanismo completo.** El selector ofrece `ES · K'ICHE'`.
  El modelo **razona en español** y elige qué responder; el texto K'iche' sale de
  **plantillas curadas y validadas** (`hub/plantillas/quc.py`), nunca del modelo (no hay
  traducción automática local es→maya en QVAC). Lo no traducido se muestra en español
  **marcado** (subrayado punteado) y `idioma_respuesta` dice `"es"`. Ver `docs/idiomas-maya.md`
  para la lista de cadenas a traducir y las fuentes (ALMG, MSPAS, OPS).

Versión publicada del prototipo (Fase 1, respuestas simuladas):
<https://claude.ai/code/artifact/de18b566-061c-4791-8e4f-56bf3ffe86dd>

### 2. Hub central — `hub/`

Backend FastAPI + panel de administración. **Toda la inferencia es local** (runtime
QVAC = Bare worker + llama.cpp); el proceso no hace ninguna llamada de red a un
proveedor de modelos.

| Archivo | Rol |
|---|---|
| `hub/server.py` | FastAPI: endpoints `/api/*`, CORS, sirve el kiosko, calcula el coste real del enlace. |
| `hub/qvac_engine.py` | Clase `Engine`: conecta el `Client` de QVAC, **carga perezosa** del modelo en la 1ª consulta, `completion` serializado con lock, `unload` al apagar. |
| `hub/medical.py` | Lógica clínica de 3 modos + red de seguridad (ver abajo). |
| `hub/guias.py` | Datos clínicos **curados** en español (motivos, repreguntas, orientación de respaldo, primeros auxilios). Nada de esto lo genera el modelo. |
| `hub/plantillas/` | Capa de idiomas: `base.py` (esquema, deriva el español de `guias.py`), `quc.py` / `cak.py` (traducciones validadas), `resolver()`. `tools/listar_claves.py` lista lo que falta. |
| `hub/codec.py` | Envelope binario + DEFLATE crudo con diccionario preestablecido (`hub/dictionary.txt`). Mismo esquema que iría al firmware. |
| `hub/link.py` | Simulador del enlace LoRa: fragmentación ≤66 B, airtime real (ecuación de Semtech, SF9/BW125), límite de dwell, salto de repetidor. |
| `hub/store.py` | Registro SQLite en dos niveles: `device.db` (nodo de la aldea) + `hub.db` (central) + `sync_device_to_hub()`. Reemplaza el dict en memoria. También guarda el inventario del botiquín. |
| `hub/recursos.py` | Catálogo curado de **dónde conseguir medicina en la aldea** — varios puntos (puesto de salud lejano, minifarmacia, botiquín comunitario, promotora de salud, tienda), cada uno con su inventario y su sector — más las **hierbas de la zona** (uso tradicional seguro) y lo que NO se debe recomendar. |
| `hub/panel.html` | Panel del puesto de salud (`GET /panel`): alertas, mapa de la aldea, **conversaciones** en vivo (título + fecha, se abren completas), y buscador por persona. |
| `hub/insumos.html` | Mapa de insumos (`GET /insumos`): **la aldea al centro y los 5 lugares con medicina alrededor** — clic en un lugar muestra y edita su inventario; panel de qué se surte cada localidad; cómo se administra (device.db → hub.db). |
| `hub/tools/build_dict.py` · `hub/tools/seed_demo.py` | Genera `dictionary.txt` · siembra datos de demo para el panel. |
| `hub/run.sh` · `test_enlace.py` · `test_store.py` · `test_plantillas.py` | Arranque · pruebas del codec/link · del registro · de la capa de idiomas (sin modelo). |

**Los 3 modos** (`medical.py`):

1. **Consulta guiada** — el motivo de la grilla es el marco. Se hacen las repreguntas
   curadas de `GUIAS[motivo]` una a una; al terminarlas, la respuesta es el **texto
   clínico curado verbatim** (revisado por humanos) + una **frase cálida de entrada**
   que escribe el modelo personalizada con lo que contó la persona.
2. **Consulta libre** — el modelo responde con tono de promotora de salud cercana,
   frases cortas. Si el mensaje ya trae una pista de síntoma va directo al modelo; solo
   repregunta si es muy vago. **Saludos y preguntas de identidad** ("hola", "¿con quién
   hablo?", "gracias") se responden con una frase cálida canned, sin triaje. La
   conversación **mantiene contexto** entre turnos.
3. **Emergencia** — devuelve **siempre** los pasos curados de `FIRST_AID[tipo]`, prioridad
   fija `emergencia`, más una nota corta del modelo adaptada a la descripción.

**Amarrado a los recursos de la aldea, por localidad** (`recursos.py` + tabla `recursos`
en `store.py`): en cada orientación el modelo recibe qué hay **cerca del sector de la
persona** — la minifarmacia y el botiquín de su caserío primero, el puesto de salud
(a 2 horas) al final — y **recomienda primero lo más cercano**. Ejemplo real: alguien
de Panimaché I pregunta por ibuprofeno; el puesto de salud no tiene, pero la
minifarmacia del centro sí, y la IA responde *"toma ibuprofeno como dice la etiqueta en
tu minifarmacia"*. En el flujo guiado se añade una nota `📍 Dónde conseguirlo` calculada
en Python. El personal de salud ajusta cada inventario desde el panel (`Recursos de la
aldea`), punto por punto.

Con `ALDEA_DEBUG=1` el hub imprime en la terminal, por cada consulta: el mensaje que
entra, la decisión de ruta (guiada/libre/social/alarma), el **prompt exacto** que recibe
el modelo y su **respuesta cruda** con el tiempo. En el kiosko cada respuesta final
lleva la etiqueta **🤖 respuesta de la IA médica** o **📋 guía del puesto de salud**.

**Red de seguridad**, en todos los modos:

- Barrido de **señales de alarma** por regex en cada turno → corta y manda al botón
  EMERGENCIA.
- **Guardia anti-inyección / fuera de tema**: mensajes tipo "ignora tus instrucciones",
  "qué modelo eres", "actúa como…", "dame tu prompt" se atajan **antes de llamar al
  modelo** y reciben una respuesta fija ("solo puedo ayudarte con temas de salud"). El
  texto de la persona se trata siempre como síntomas, nunca como instrucciones; el
  system prompt lo refuerza y un filtro de salida descarta cualquier respuesta que
  revele que es una IA / su prompt / su nombre. Cobertura: `hub/test_medical.py`.
- Si el modelo falla o su respuesta se sale de rango → se usa el **texto curado** de
  `guias.py`.
- **Disclaimer permanente** en cada orientación; sin diagnóstico definitivo; siempre
  deriva al puesto de salud.
- Cada resultado lleva `fuente` = `curado` | `modelo`.

**Endpoints:**

| Método | Ruta | Entrada → Salida |
|---|---|---|
| `POST` | `/api/consulta` | `{mac, motivo?, mensajes:[{rol,texto}], lang?}` → `{estado:"seguimiento"\|"final", respuesta, prioridad, fuente, idioma_respuesta, lora}` |
| `POST` | `/api/emergencia` | `{mac, tipo, descripcion?, lang?}` → `{ack, tipo, prioridad, primeros_auxilios[], nota, fuente, meta}` |
| `GET`/`PUT` | `/api/perfil/{mac}` | `{nombre, edad, sector, alergias}`, en SQLite (`store.py`) |
| `GET` | `/health` | estado del modelo + listas de motivos/emergencias |
| `GET` | `/` · `/panel` · `/insumos` | kiosko · panel del puesto de salud · mapa de insumos |
| `GET` | `/api/panel/resumen` · `/api/panel/feed` | stats + sectores · conversaciones y alertas en vivo (polling) |
| `GET` | `/api/panel/conversaciones?mac=` · `/api/panel/conversacion/{id}` | lista de conversaciones · transcripción completa de una |
| `GET` | `/api/panel/buscar?q=` · `/api/panel/paciente/{mac}` | buscar personas · perfil + sus conversaciones |
| `GET` | `/api/panel/recursos` | puntos + inventario + `sectores` + `cobertura` por sector + hierbas + qué evitar |
| `POST` | `/api/panel/alerta/{id}/atender` · `/api/panel/recursos/{punto_id}/{item}?cantidad=` · `/api/panel/enlace?activo=` | atender alerta · ajustar inventario de un punto · simular caída del enlace |

**Conversaciones.** El kiosko agrupa los turnos en conversaciones: un `conversacion_id`
(uuid del cliente) viaja en cada `/api/consulta` y `/api/emergencia`. El hub guarda una
fila `conversaciones` (título = síntoma / tema central, transcripción, prioridad máxima)
que se actualiza turno a turno, más una fila `consultas` por intercambio (con sus bytes
del enlace). Elegir un motivo nuevo o tocar **✚ Nueva consulta** en el kiosko arranca
otra conversación. En la siguiente consulta de la misma MAC el hub le pasa al modelo los
títulos de las conversaciones previas (no el texto completo — eso sería demasiado); si
la persona **retoma** una conversación vieja desde el kiosko, su transcripción entera
viaja como `mensajes` y el modelo recupera el detalle. Todo se replica `device.db → hub.db`.

`mensajes` es la transcripción completa de esa consulta; el server cuenta los turnos
`assistant`/`bot` para saber cuántas repreguntas van. `lang` (`es`|`cak`, opcional) solo
alimenta el envelope del códec.

El objeto **`lora`** (y `meta.lora` en emergencia) trae el coste real del enlace:
`{bytes_in, bytes_comprimido, tramas, airtime_ms, saltos}` describen el **downlink** (la
respuesta que el vecino espera), más `ratio`, `uplink`/`downlink` detallados,
`airtime_total_ms`, `ratio_total` y `hops[]`. `provisional` es `false`.

### Compresión y enlace

`codec.py` usa DEFLATE crudo (`zlib`, `wbits=-15`) con un diccionario preestablecido de
~7.8 KB construido desde los textos curados de `guias.py` (`dictionary.txt`, idéntico al
que iría al firmware). Ratios medios sobre un corpus de ejemplo:

| Tipo de mensaje | n | ratio medio |
|---|---|---|
| Orientación **curada** (respaldo, casi verbatim en el diccionario) | 10 | **26×** |
| Primeros auxilios de emergencia | 7 | **10×** |
| Orientación **del modelo** (texto nuevo) | 5 | **4.3×** |
| Mensaje del usuario (frases cortas) | 7 | **~1×** (no comprimen) |
| **Global** | 29 | **12.5×** |

`link.py` fragmenta a tramas ≤ 66 B (límite de dwell de 400 ms de US915 → una trama de
66 B ≈ 390 ms de airtime por la ecuación de Semtech, SF9/BW125), reensambla, y modela el
salto de repetidor como store-and-forward (`2 · airtime + 50 ms`). Ejemplo real: una
orientación del modelo de ~240 B de texto → ~70 B al aire → 2 tramas → ~1.1 s en los dos
saltos. Ver `docs/hardware.md` para el detalle del envelope y el camino en LoRa real.

### 3. Panel del puesto de salud — `hub/panel.html` (`GET /panel`)

Pantalla del personal de salud, en vivo (polling cada 3.5 s):

- **Alertas de emergencia** fijadas arriba, con sonido al llegar una nueva y botón
  "marcar atendida".
- **Mapa de la aldea** — diagrama de los sectores/caseríos como nodos alrededor del
  puesto de salud; el tamaño refleja cuántas consultas y el color la prioridad máxima
  (rojo con pulso = emergencia abierta). Click en un sector filtra el feed. Es la base
  del grafo más completo que viene después.
- **Conversaciones** — cada tarjeta es una conversación: **título** (el síntoma / tema
  central), **fecha pequeña**, prioridad, persona · sector y el número de mensajes.
  Tocarla abre la **transcripción completa** (los turnos de ida y vuelta). Consultar sobre
  X y, dos horas después, sobre otra cosa aparece como dos conversaciones separadas.
- **Buscador de personas** por nombre / MAC / sector → sus conversaciones, cada una con
  botón para leerla completa.
- **Estado del enlace device→hub** con un botón para simular la caída: las consultas se
  acumulan en `device.db` y el panel no las ve hasta reconectar.
El inventario de la aldea se administra en la página aparte `/insumos` (enlace en la
barra superior).

`python tools/seed_demo.py --reset` llena el panel con datos de ejemplo para la demo.

### 3b. Mapa de insumos — `hub/insumos.html` (`GET /insumos`)

Página aparte para ver y administrar de dónde sale la medicina. Diagrama simple: **la
aldea al centro y los 5 lugares con medicina alrededor** (minifarmacia, botiquín,
promotora, tienda, puesto de salud). El aro de cada lugar es verde/ámbar según
faltantes y el puesto de salud va marcado como lejano, fuera del círculo.

- **Tocar un lugar** abre su inventario editable (`−`/`+`, sincroniza a `hub.db`) y
  muestra cuántos renglones tiene con stock.
- **"De dónde se surte cada localidad"**: para cada sector, la cadena de lugares del
  más cercano al más lejano; tocando un sector se ve además qué se consigue cerca.
- Recuadro **"cómo se administran"**: inventario por lugar (no una sola bodega),
  `kiosko → device.db → sync → hub.db`, y que lo agotado el modelo lo trata como no
  disponible.

El panel del puesto de salud (`/panel`) se quedó con lo esencial (alertas, mapa de
consultas, feed, buscador); el inventario se administra aquí.

### Modelo

| | |
|---|---|
| **Nombre (registro QVAC)** | `HEALTHCARE_4B_MEDICAL_Q4_K_M` |
| **Familia** | **MedPsy-4B** de QVAC (modelo Psy oficial), base **Qwen3-4B-Thinking** afinado en salud |
| **Cuantización** | Q4_K_M (GGUF, ≈ 2.7 GB) |
| **Runtime** | `@qvac/sdk` → worker Bare + llama.cpp, **100 % local**; los pesos se bajan del registro de QVAC por hyperswarm |
| **Ejecución** | GPU (Vulkan) o CPU, según `ALDEA_DEVICE` |
| **Rendimiento medido** | carga 16 s · TTFT ~85–220 ms · **~60 tok/s** en la RTX 2060 — ver [`docs/rendimiento.md`](docs/rendimiento.md) |

Es un modelo de **razonamiento**: piensa en un bloque `<think>` que el hub **descarta**
vía el evento `thinkingDelta`, y responde en español. En HealthBench (74.0) y
HealthBench-Hard (58.0) supera a MedGemma-27B.

**Alternativas** por `ALDEA_MODEL`, honestamente identificadas:
`HEALTHCARE_1_7B_MEDICAL_Q4_K_M` (MedPsy-1.7B, ~2× más rápido, para SBC modestas),
`MEDGEMMA_4B_IT_Q4_1` (MedGemma-4B, Q4_1, sin `<think>`). El hub filtra respuestas con
mezcla de idiomas (Qwen a veces cuela caracteres CJK) y cae al texto curado.

**Por qué un modelo pequeño es lo correcto aquí:** el nodo real de la aldea es una SBC
ARM o un teléfono; un modelo de 4B Q4 entra en 6 GB, responde en segundos sin red, y la
calidad clínica la ancla el contenido curado + la red de seguridad, no el tamaño del
modelo.

### Hardware probado

| | |
|---|---|
| CPU | Intel Core i7-9750H @ 2.6 GHz (6c/12t) |
| GPU | NVIDIA GeForce RTX 2060 Mobile, 6 GB, driver 595.84 (backend **Vulkan**) |
| RAM | 24 GB |
| SO | Pop!_OS / Linux 7.0 · Python 3.12 |

Objetivo de despliegue: SBC `linux-arm64` en la aldea (QVAC corre CPU-only ahí) + ESP32
como nodo de radio. Ver [`docs/hardware.md`](docs/hardware.md).

### Verificado

Sobre la RTX 2060 con MedPsy-4B (tiempos = TTFT + generación del modelo; las repreguntas
y primeros auxilios son texto curado, respuesta inmediata):

| Ruta | Tiempo | Resultado |
|---|---|---|
| Orientación completa del modelo (predict 800) | ~8 s | adapta el texto curado al caso, formato `PRIORIDAD/ORIENTACION` |
| Libre "puedo tomar ibuprofeno?" (persona de Panimaché I) | ~7 s | *"toma ibuprofeno … en tu minifarmacia"* — usa el punto cercano, no el puesto lejano |
| Guiada (fiebre) | repreguntas 0 s + orientación ~8 s | frase cálida del modelo + orientación curada + `📍 Dónde conseguirlo` |
| Nota de emergencia (mordedura) | ~8 s | pasos curados intactos + nota contextual del modelo |
| Social / "¿quién eres?" / intento de hackeo | 0 s | respuesta canned, **sin llamar al modelo** |

También: arranque de la app, `/health`, alta/lectura de perfil, repreguntas curadas,
red-flag → emergencia, guardia anti-inyección, y respaldo curado cuando el modelo
devuelve basura. Registro de rendimiento reproducible: `python hub/tools/perf_log.py`.

**Prueba de punta a punta en el navegador** (Chromium headless contra el hub real):
alta → `PUT` perfil OK · tocar "Fiebre" → 3 repreguntas → orientación del modelo con pill
`Rutina` y chip real `📡 574→194 B · 3.0× · 4 tramas · 2 saltos · ~2.6 s` · caída del
enlace → burbuja pendiente + cola · reconectar → la cola se vacía sola · EMERGENCIA
(mordedura) → 4 pasos + metadatos reales del relevo. **0 errores de consola.**

**Panel** (Chromium headless): con datos sembrados, el mapa dibuja los 7 sectores con
tamaño/color por actividad, las 2 alertas abiertas quedan fijadas arriba, click en un
sector filtra el feed a esas consultas, el buscador abre el historial de la persona, y
simular la caída del enlace deja las filas "sin sincronizar" hasta reconectar. Una
consulta guiada real termina y aparece en el feed en <2 s con su chip de enlace.
**0 errores de consola.**

`hub/test_enlace.py`, `test_store.py`, `test_plantillas.py` y `test_medical.py` cubren el
códec (round-trip, envelope, corrupción, airtime, dwell), el registro (perfiles,
conversaciones, feed, alertas, resumen por sector, sync en dos niveles), la capa de
idiomas y la red de seguridad (señales de alarma, detección de inyección, respaldo
curado). Todos corren **sin el modelo**.

**Cumplimiento (regla técnica, art. 10):**
`grep -riE "openai|anthropic|groq|api[_-]?key|https?://(api|generativelanguage)" hub/*.py`
no encuentra ninguna llamada de inferencia a la nube (`codec.py`, `link.py` y
`build_dict.py` son stdlib pura). La única dependencia de inferencia es
`tetherto.qvac_sdk`, que corre local.

---

## Cómo correr

Requiere el SDK de QVAC instalado en un venv (probado con `tetherto.qvac_sdk` v0.19.0
+ `fastapi` + `uvicorn`).

```bash
cd hub
ALDEA_VENV=/home/yeffrimic/Documents/qvac/.venv ./run.sh
# kiosko en http://127.0.0.1:8000 · API en /api/*
```

Variables de entorno:

| Var | Default | Notas |
|---|---|---|
| `ALDEA_MODEL` | `HEALTHCARE_4B_MEDICAL_Q4_K_M` (MedPsy-4B) | `HEALTHCARE_1_7B_MEDICAL_Q4_K_M` · `MEDGEMMA_4B_IT_Q4_1` |
| `ALDEA_DEVICE` | `gpu` | `gpu` \| `cpu` |
| `ALDEA_PORT` | `8000` | |
| `ALDEA_DEBUG` | — | `=1` imprime prompt + respuesta del modelo en la terminal |
| `ALDEA_VENV` | `~/Documents/qvac/.venv` | (solo `run.sh`) |
| `ALDEA_DATA_DIR` | `hub/data` | dónde viven `device.db` + `hub.db` |

La primera consulta descarga los pesos del modelo desde el registro de QVAC
(MedPsy-4B ≈ 2.7 GB por hyperswarm) y los carga; los arranques siguientes solo cargan.

> Si al cargar el modelo aparece `File descriptor could not be locked`, hay otro proceso
> con el store del registro abierto: `pkill -f bare-runtime` y reintenta.

Pruebas sin modelo:

```bash
cd hub
python test_enlace.py            # codec + link (round-trip, envelope, airtime, dwell)
python test_store.py             # registro SQLite, conversaciones, sync dos niveles
python test_plantillas.py        # capa de idiomas
python test_medical.py           # red de seguridad + guardia anti-inyección
```

Utilidades:

```bash
python tools/perf_log.py                # registro de rendimiento → docs/rendimiento.{md,json}
python tools/seed_demo.py --reset       # datos de ejemplo para el panel
python tools/listar_claves.py quc --solo-clinico   # qué falta traducir a K'iche'
python tools/build_dict.py              # regenera dictionary.txt tras cambios en guias.py
```

El registro vive en `hub/data/{device,hub}.db` (se crea solo; `ALDEA_DATA_DIR` lo mueve).

---

## Base preexistente y terceros (declarado — art. 11 del reglamento)

**Ninguna API remota en el camino principal.** La única dependencia de inferencia es
`tetherto.qvac_sdk`, que corre local.

**Trabajo previo del propio autor** (reutilizado como patrón, no como producto):

- **`~/Documents/qvac/`** — demos propias con el SDK de QVAC, ya funcionando antes del
  hackathon (`qvac.py` chat LLM, `app.py` visión→cuento con FastAPI+HTML, `benchmark.py`
  GPU vs CPU, `live_vision.py`, `segmentation.py`). Tinimit **reutiliza el patrón de
  arquitectura** (lifespan de FastAPI, carga perezosa del modelo, `completion`
  streaming); el producto —kiosko, hub médico, códec, panel, plantillas de idioma— se
  construyó dentro de la ventana.

**Componentes de terceros:**

| Componente | Uso | Origen / licencia |
|---|---|---|
| `tetherto.qvac_sdk` v0.19.0 + worker Bare (`~/.cache/qvac/worker/0.19.0/`) | **toda** la inferencia; transporte de pesos | oficial de QVAC/Tether |
| Modelos: `HEALTHCARE_4B_MEDICAL_Q4_K_M` (MedPsy-4B), `HEALTHCARE_1_7B_MEDICAL_Q4_K_M`, `MEDGEMMA_4B_IT_Q4_1` | modelo médico | registro de QVAC · MedPsy Apache-2.0 (Tether Data) |
| FastAPI + Uvicorn + Pydantic | servidor del hub | MIT / BSD |
| `zlib` (stdlib de Python) | DEFLATE del códec de compresión | — |
| Google Fonts (Fraunces, Public Sans, IBM Plex Mono) | tipografía de kiosko y paneles; **CDN, solo estética**; offline cae a fuentes del sistema | OFL/Apache |
| Cadenas de UI en K'iche'/Kaqchikel de la localización de Firefox de Mozilla | ~10 palabras de interfaz, citadas en el código | MPL-2.0 · `docs/idiomas-maya.md` |
| Corpus para el diccionario del códec | derivado de `hub/guias.py` (contenido propio, curado a mano) | — |

**Servicios en la nube:** ninguno para la inferencia. La interfaz se sirve desde el
propio hub (mismo origen). El único uso de red previsto es la **sincronización P2P
opcional** con Pears (no implementada), que tampoco es "nube".

**No relacionados / no usados en este proyecto:** `~/groq.py`, `~/mirror.py`.

---

## Documentación

- [`docs/arquitectura.md`](docs/arquitectura.md) — componentes, flujo de una consulta, datos y privacidad, red de seguridad.
- [`docs/rendimiento.md`](docs/rendimiento.md) — registro de rendimiento del modelo (carga, TTFT, tokens, tok/s). Regenerar: `python hub/tools/perf_log.py`.
- [`docs/hardware.md`](docs/hardware.md) — ESP32 + LoRa: envelope, MTU, dwell, códec en C, fit en el chip.
- [`docs/idiomas-maya.md`](docs/idiomas-maya.md) — cómo funciona el K'iche', por qué no lo genera el modelo, fuentes.
- `CONTINUAR.md` — checklist de entrega y lo opcional pendiente.

## Estado

Kiosko de dos modos, hub médico sobre MedPsy-4B, enlace comprimido real, registro SQLite
en dos niveles, panel de conversaciones, mapa de insumos por localidad, idioma K'iche'
(mecanismo), agrupación por conversación, guardia anti-inyección y registro de
rendimiento: **hechos y probados** (`hub/test_*.py` en verde). Falta grabar el **video**
(guion en `CONTINUAR.md`) y, opcionales, las 68 frases clínicas en K'iche' validadas y
el stretch de Pears.
