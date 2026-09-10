"""K'iche' (quc) — objetivo principal de traducción de Tinimit.

Por qué K'iche': lengua maya más hablada de Guatemala (~1.1 M), la que más material
de salud bilingüe validado tiene (MSPAS, OPS/PAHO, DIGEBI), y la de la zona de la
aldea (Panimaché / Chuwa Nima Ab'aj son cantones K'iche' de Santa Catarina
Ixtahuacán, Sololá — variante de Nahualá).

REGLA DURA: el contenido CLÍNICO (repreguntas, orientaciones, primeros auxilios,
avisos) solo va aquí si viene de ALMG / MSPAS / un hablante nativo. NADA se genera
con el modelo. El modelo solo razona en español y elige qué responder.

Para traducir: `docs/idiomas-maya.md` + `python tools/listar_claves.py quc`.
Al pegar una traducción validada, ponla en `T` y corre `python test_plantillas.py`.

`_CANDIDATOS` = borradores SIN VALIDAR; NO se usan (`PERMITIR_CANDIDATOS = False`).
Están aquí solo para que un revisor de ALMG los confirme o corrija.
"""

# --- traducciones VALIDADAS (se usan) ---------------------------------------
# Fuente UI: Mozilla Focus for Android, localización K'iche' (MPL-2.0, revisada por
# la comunidad) — github.com/mozilla-l10n/android-l10n, values-quc/strings.xml
T: dict[str, str] = {
    "langName": "K'iche'",
    "saludo": "Utz apetem.",  # "Bienvenido/a" (Mozilla: "Utz apetem pa %1$s")
}

# --- borradores SIN VALIDAR (NO se usan) ----------------------------------
PERMITIR_CANDIDATOS = False

# VOCABULARIO de referencia para quien traduzca (NO son frases, NO son consejos).
# Fuentes: Wiktionary "Mayan Swadesh lists" (columna K'iche') + diccionario ALMG
# "K'iche' Choltzij" + Christenson K'iche'-English (FAMSI). Confirmar con ALMG la
# variante de Nahualá / Santa Catarina Ixtahuacán.
GLOSARIO: dict[str, str] = {
    "fiebre / calor": "q'aq'",          # (lit. fuego)
    "enfermo / enfermedad": "yawa' / yab'il",
    "dolor / doler": "q'oxow / k'ax",
    "agua": "ja'",
    "sangre": "kik'",
    "cabeza": "jolom",
    "estómago / panza": "pam",
    "boca": "chi'",
    "niño / niña": "ak'al / al",
    "mujer": "ixoq",
    "hombre": "achi",
    "persona": "winaq",
    "casa": "ja / achoch",
    "día / sol": "q'ij",
    "hoy": "kamik / wakamik",
    "noche": "chaq'ab'",
    "comer": "wa'im",
    "beber / tomar": "qumunik",
    "dormir": "waram",
    "descansar": "uxlanik",
    "ver / mirar": "il / ka'yik",
    "caliente": "miq'in",
    "frío": "tew",
    "bueno": "utz",
    "no": "ma / man ... taj",
    "todos": "konojel",
    "medicina": "aq'omanik / aq'om",
    "curar / sanar": "kunaj",
}

_CANDIDATOS: dict[str, str] = {
    # aproximaciones de UI, a confirmar con ALMG:
    "social.despedida": "Chatux chi utz.",  # ~"que estés bien" — REVISAR
}

if PERMITIR_CANDIDATOS:
    T = {**_CANDIDATOS, **T}
