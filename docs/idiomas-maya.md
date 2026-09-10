# Tinimit en idiomas maya (K'iche', y otros)

## Cómo funciona

`lang` (`es`, `quc`=K'iche', `cak`=Kaqchikel, `kek`=Q'eqchi', `mam`=Mam) viaja del
kiosko al hub. En el hub:

- **El modelo (MedPsy) razona SIEMPRE en español** — entiende el problema, hace el
  triaje, detecta señales de alarma, y decide **qué** responder.
- **El texto en idioma maya sale de plantillas curadas y validadas**
  (`hub/plantillas/<código>.py`), nunca del modelo.
- Si una cadena no está traducida y validada, se muestra el **español marcado**
  (subrayado punteado en el kiosko) y `idioma_respuesta` en la respuesta dice `"es"`.

### Por qué NO lo genera el modelo

- K'iche' / Kaqchikel / etc. son lenguas de muy bajos recursos: MedPsy/Qwen produce
  texto roto o mezclado con español, imposible de verificar.
- **No hay traducción automática local es→maya en QVAC**: Bergamot solo cubre lenguas
  europeas; no hay NLLB/MADLAD en el registro.
- Un error en una instrucción médica traducida puede hacer daño.

### Rutas por idioma (no español)

| Flujo | Qué pasa |
|---|---|
| Botón de motivo → repreguntas | repregunta de la plantilla si está validada, si no español marcado |
| Botón de motivo → orientación final | orientación K'iche' de plantilla si validada, si no la española marcada. **Sin** la frase cálida del modelo (el modelo no hace K'iche'). |
| Texto libre | el modelo **clasifica** el mensaje en uno de los 9 motivos (razona en español) → sirve la orientación de ese motivo en K'iche'. Si no encaja → genérico español + nota. |
| Emergencia | pasos de `FIRST_AID` en K'iche' si validados, si no español; la nota del modelo se omite. |
| Saludo / gracias / identidad | de `plantillas` (`social.*`). |

## Qué falta traducir a K'iche' (`quc`)

La lista viva sale del código:

```bash
cd hub
python tools/listar_claves.py quc --solo-clinico   # las 68 cadenas clínicas
python tools/listar_claves.py quc                   # todo (94), incluida la UI
python tools/listar_claves.py quc --hechas          # lo ya traducido
```

Bloques (🩺 = clínico, requiere validación estricta):

| Bloque | Nº | Qué es |
|---|---|---|
| `guia.<motivo>.pregunta.0..2` 🩺 | 27 | las 3 repreguntas de cada uno de los 9 motivos |
| `guia.<motivo>.orientacion` 🩺 | 9 | la orientación final de cada motivo (2 párrafos: qué hacer en casa + cuándo acudir) |
| `primeros_auxilios.<tipo>.0..3` 🩺 | 28 | los 4 pasos de cada uno de los 7 tipos de emergencia |
| `generico.pregunta` / `generico.orientacion` 🩺 | 2 | texto libre sin motivo claro |
| `aviso.emergencia` 🩺 | 1 | "esto puede ser grave, usa el botón rojo" |
| `disclaimer` 🩺 | 1 | descargo permanente |
| `social.*` | 5 | saludo, identidad, gracias, despedida, confirmar |
| `motivo.*` / `emergencia.*` | 16 | etiquetas de los botones |
| `ui.*`, `nota.*`, `saludo`, `langName` | 5 | interfaz |

## Fuentes ya incorporadas

**Interfaz (no clínica) — de la localización de Firefox de Mozilla** (MPL-2.0,
revisada por la comunidad de cada idioma):

| Idioma | Repo | Qué se sacó |
|---|---|---|
| K'iche' (`quc`) | [mozilla-l10n/android-l10n](https://github.com/mozilla-l10n/android-l10n) — `mozilla-mobile/focus-android/app/src/main/res/values-quc/strings.xml` (Firefox Focus, ~685 cadenas) | `saludo` = "Utz apetem" ("bienvenido"); `guardar` = "Uk'olik". También disponibles: cancelar=Uq'atexik, ayuda=Tob'anem, configuración="Taq wiqitajem", abrir=Ujaqik, cerrar="Chatz'apij", buscar=Chatzukuj, activado=Utzijik, apagado=Uchupik. |
| Kaqchikel (`cak`) | [mozilla-l10n/firefox-l10n](https://github.com/mozilla-l10n/firefox-l10n) — carpeta `cak/` (Firefox completo, 302 archivos) | `guardar` = "Tiyak", `volver` = "Titzolïx". También: Aceptar=ÜTZ, Cancelar=Tiq'at, Sí=Je', No=Manäq, Cerrar="Titz'apïx", Eliminar=Tiyuj, Alerta="Retal k'ayewal", Confirmar="Tajikib'a'", Idioma="Taq ch'ab'äl". |

> K'iche' en Pontoon: ~668/5612 cadenas (12 %), en curso. No está en el repo de
> Firefox de escritorio todavía; sí en Focus for Android (arriba).

**Vocabulario K'iche' de referencia** (en `hub/plantillas/quc.py` → `GLOSARIO`):
palabras sueltas de [Wiktionary — Mayan Swadesh lists](https://en.wiktionary.org/wiki/Appendix:Mayan_Swadesh_lists),
el diccionario ALMG "K'iche' Choltzij" y el
[Christenson K'iche'–English](https://www.famsi.org/mayawriting/dictionary/christenson/quidic_complete.pdf) (FAMSI).
Ej.: fiebre/calor = `q'aq'`, dolor = `q'oxow`/`k'ax`, agua = `ja'`, sangre = `kik'`,
niño = `ak'al`, medicina = `aq'om`, curar = `kunaj`.

### Por qué el vocabulario NO basta para el contenido clínico

Traducir palabra por palabra una instrucción médica produce frases **ambiguas o
peligrosas** (la gramática, el registro y el sentido cambian). "Toma paracetamol cada
6 horas sin pasar la dosis" o "acude si hay manchas moradas y no despierta bien"
necesitan **un hablante fluido con formación o experiencia en salud comunitaria**, no
un diccionario. El glosario es el andamiaje para esa persona, no un sustituto.

## De dónde sacar cada traducción clínica (validada)

- **ALMG — Academia de Lenguas Mayas de Guatemala** (almg.org.gt): comunidad
  lingüística K'iche', sede en Santa Cruz del Quiché. Es la autoridad. Tienen glosarios
  y pueden revisar.
- **MSPAS** — materiales bilingües de salud: "Señales de peligro" (AINM-C / estrategia
  AIEPI-IMCI), salud materno-neonatal, primeros auxilios comunitarios, publicados en
  K'iche', Q'eqchi', Mam y Kaqchikel para promotores y comadronas.
- **OPS/PAHO** — "Manual del promotor / promotora de salud" y rotafolios comunitarios
  en idiomas mayas.
- **DIGEBI** (MINEDUC) — vocabulario técnico estandarizado en idiomas mayas.
- **Un hablante nativo de la variante local** — Panimaché / Chuwa Nima Ab'aj usan la
  variante de **Nahualá / Santa Catarina Ixtahuacán** (Sololá), que tiene rasgos
  propios (p. ej. la vocal `ä`). La traducción debe revisarse con alguien de esa zona.

## Cómo agregar una traducción validada

1. Editar `hub/plantillas/quc.py`, en el dict `T`:
   ```python
   T = {
       "langName": "K'iche'",
       "saludo": "...",
       "guia.fiebre.pregunta.0": "<texto validado en K'iche'>",
       # ...
   }
   ```
2. `cd hub && python test_plantillas.py` — verifica que ninguna clave clínica quedó en
   español por error.
3. Se activa sola: el hub sirve esa cadena en K'iche' y `idioma_respuesta` pasa a `quc`
   para esa respuesta; el kiosko deja de marcarla.

`hub/plantillas/quc.py` tiene además `_CANDIDATOS` — borradores **sin validar** que no
se usan (`PERMITIR_CANDIDATOS = False`), solo para que un revisor de ALMG los confirme
o corrija.

## Espejo en el kiosko

El kiosko tiene una copia de `MOTIVOS`/`EMERGENCIAS` labels y `GUIAS_OFFLINE.preguntas`
(para el modo sin enlace) en `I18N` / constantes. Al validar traducciones, actualizar
**primero** `hub/plantillas/quc.py`; luego reflejar las etiquetas y las repreguntas en
`prototipo/kiosk.html` (`I18N.quc` y `GUIAS_OFFLINE` — hoy sin variante `quc`).

## Otros idiomas

El mecanismo es multi-idioma: crear `hub/plantillas/kek.py` (Q'eqchi'), `mam.py` (Mam),
etc. con el mismo dict `T`, añadir el código a `IDIOMAS` en `hub/plantillas/__init__.py`
y a `LANGS` en `hub/codec.py` (ya están reservados `quc`, `kek`, `mam`).
