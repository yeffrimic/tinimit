"""Recursos de la aldea — dónde conseguir medicina y las hierbas de la zona.

Los recursos son **por localidad** y **por aldea completa**: de nada sirve que el
puesto de salud tenga ibuprofeno si está a 2 horas a pie. Por eso hay varios PUNTOS
(minifarmacia, botiquín comunitario, promotora de salud, tienda) y cada uno tiene su
propio inventario. Cuando alguien consulta, la IA recibe qué hay **cerca de su sector**
y recomienda primero lo más cercano.

- `PUNTOS_BASE` + `INVENTARIO_BASE`: catálogo por defecto. Las CANTIDADES viven en
  `store.py` (tabla `recursos`, editable desde el panel).
- `HIERBAS`: plantas de uso tradicional seguro y documentado en el altiplano de
  Guatemala. Curado a mano, NO generado.

Nada de esto se inventa con el modelo.
"""

from __future__ import annotations

import re

# localidades de la aldea (donde vive la gente). El puesto de salud está en el
# "Sector Centro" pero a 2 h a pie de la mayoría.
SECTORES: list[str] = [
    "Sector Centro", "Caserío El Tablón", "Chuwa Nima Ab'aj",
    "Panimaché I", "Panimaché II", "Xepiacul", "La Estancia",
]

# --- puntos donde conseguir medicina / atención ------------------------------
# tipo: puesto_salud | minifarmacia | botiquin | promotor | tienda
PUNTOS_BASE: list[dict] = [
    {"id": "puesto_salud", "nombre": "Puesto de salud San Miguel", "tipo": "puesto_salud",
     "sector": "Sector Centro", "distancia": "a ~2 horas a pie (10 km)",
     "cerca_de": [], "lejos": True},
    {"id": "minifarmacia", "nombre": "Minifarmacia La Bendición", "tipo": "minifarmacia",
     "sector": "Sector Centro", "distancia": "en el centro de la aldea",
     "cerca_de": ["*"], "lejos": False},
    {"id": "botiquin_panimache", "nombre": "Botiquín comunitario de Panimaché",
     "tipo": "botiquin", "sector": "Panimaché I", "distancia": "en Panimaché",
     "cerca_de": ["Panimaché I", "Panimaché II"], "lejos": False},
    {"id": "promotora_xepiacul", "nombre": "Doña Marta, promotora de salud",
     "tipo": "promotor", "sector": "Xepiacul", "distancia": "en Xepiacul",
     "cerca_de": ["Xepiacul", "La Estancia"], "lejos": False},
    {"id": "tienda_tablon", "nombre": "Tienda de don Julián", "tipo": "tienda",
     "sector": "Caserío El Tablón", "distancia": "en el Caserío El Tablón",
     "cerca_de": ["Caserío El Tablón", "Chuwa Nima Ab'aj"], "lejos": False},
]

# inventario por punto. categoria: analgesico | rehidratacion | suplemento |
#   antiparasitario | antibiotico | alergia | curacion | insumo | casero
INVENTARIO_BASE: dict[str, list[dict]] = {
    "puesto_salud": [
        {"item": "paracetamol tabletas 500 mg", "categoria": "analgesico", "cantidad": 40, "unidad": "tabletas", "para": "fiebre y dolor"},
        {"item": "paracetamol jarabe (niños)", "categoria": "analgesico", "cantidad": 3, "unidad": "frascos", "para": "fiebre y dolor en niños"},
        {"item": "ibuprofeno tabletas 400 mg", "categoria": "analgesico", "cantidad": 0, "unidad": "tabletas", "para": "dolor e inflamación"},
        {"item": "sales de rehidratación oral (SRO)", "categoria": "rehidratacion", "cantidad": 25, "unidad": "sobres", "para": "diarrea, vómito, deshidratación"},
        {"item": "sulfato ferroso + ácido fólico", "categoria": "suplemento", "cantidad": 30, "unidad": "tabletas", "para": "embarazo y anemia"},
        {"item": "albendazol 400 mg", "categoria": "antiparasitario", "cantidad": 12, "unidad": "tabletas", "para": "desparasitación (con indicación)"},
        {"item": "amoxicilina 500 mg", "categoria": "antibiotico", "cantidad": 0, "unidad": "cápsulas", "para": "infecciones (solo con receta del personal de salud)"},
        {"item": "loratadina 10 mg", "categoria": "alergia", "cantidad": 10, "unidad": "tabletas", "para": "ronchas y alergia leve"},
        {"item": "gasas estériles", "categoria": "curacion", "cantidad": 20, "unidad": "sobres", "para": "cubrir heridas"},
        {"item": "yodopovidona (antiséptico)", "categoria": "curacion", "cantidad": 1, "unidad": "frasco", "para": "limpiar heridas"},
        {"item": "guantes", "categoria": "insumo", "cantidad": 2, "unidad": "cajas", "para": "atención de heridas y partos"},
        {"item": "termómetro", "categoria": "insumo", "cantidad": 1, "unidad": "unidad", "para": "medir la fiebre"},
    ],
    "minifarmacia": [
        {"item": "paracetamol tabletas 500 mg", "categoria": "analgesico", "cantidad": 60, "unidad": "tabletas", "para": "fiebre y dolor"},
        {"item": "paracetamol jarabe (niños)", "categoria": "analgesico", "cantidad": 4, "unidad": "frascos", "para": "fiebre y dolor en niños"},
        {"item": "ibuprofeno tabletas 400 mg", "categoria": "analgesico", "cantidad": 30, "unidad": "tabletas", "para": "dolor e inflamación"},
        {"item": "sales de rehidratación oral (SRO)", "categoria": "rehidratacion", "cantidad": 20, "unidad": "sobres", "para": "diarrea, vómito"},
        {"item": "antiácido (sal de frutas)", "categoria": "casero", "cantidad": 15, "unidad": "sobres", "para": "acidez, indigestión"},
        {"item": "loratadina 10 mg", "categoria": "alergia", "cantidad": 12, "unidad": "tabletas", "para": "ronchas y alergia leve"},
        {"item": "curitas y tela adhesiva", "categoria": "curacion", "cantidad": 8, "unidad": "cajas", "para": "heridas pequeñas"},
        {"item": "gasas y algodón", "categoria": "curacion", "cantidad": 10, "unidad": "paquetes", "para": "curaciones"},
        {"item": "alcohol / agua oxigenada", "categoria": "curacion", "cantidad": 3, "unidad": "frascos", "para": "limpiar heridas"},
        {"item": "suero fisiológico", "categoria": "curacion", "cantidad": 5, "unidad": "frascos", "para": "lavar ojos y heridas"},
    ],
    "botiquin_panimache": [
        {"item": "paracetamol tabletas 500 mg", "categoria": "analgesico", "cantidad": 20, "unidad": "tabletas", "para": "fiebre y dolor"},
        {"item": "sales de rehidratación oral (SRO)", "categoria": "rehidratacion", "cantidad": 10, "unidad": "sobres", "para": "diarrea, vómito"},
        {"item": "gasas y curitas", "categoria": "curacion", "cantidad": 6, "unidad": "paquetes", "para": "heridas"},
        {"item": "jabón", "categoria": "insumo", "cantidad": 4, "unidad": "barras", "para": "lavado de heridas y manos"},
    ],
    "promotora_xepiacul": [
        {"item": "paracetamol tabletas 500 mg", "categoria": "analgesico", "cantidad": 15, "unidad": "tabletas", "para": "fiebre y dolor"},
        {"item": "sales de rehidratación oral (SRO)", "categoria": "rehidratacion", "cantidad": 12, "unidad": "sobres", "para": "diarrea, vómito"},
        {"item": "botiquín de primeros auxilios (gasas, vendas, jabón)", "categoria": "curacion", "cantidad": 1, "unidad": "botiquín", "para": "heridas y golpes"},
        {"item": "termómetro", "categoria": "insumo", "cantidad": 1, "unidad": "unidad", "para": "medir la fiebre"},
    ],
    "tienda_tablon": [
        {"item": "sal y azúcar", "categoria": "casero", "cantidad": 99, "unidad": "libras", "para": "suero casero (1 L agua + 8 cdtas azúcar + 1 cdta sal)"},
        {"item": "agua pura embotellada", "categoria": "casero", "cantidad": 20, "unidad": "botellas", "para": "beber cuando el agua no es segura"},
        {"item": "miel", "categoria": "casero", "cantidad": 6, "unidad": "frascos", "para": "tos y garganta (mayores de 1 año)"},
        {"item": "jabón", "categoria": "insumo", "cantidad": 12, "unidad": "barras", "para": "lavado de manos y heridas"},
    ],
}

# medicina que necesita cadena de frío / hospital: no está en la aldea
NO_HAY_EN_LA_ALDEA = [
    "suero antiofídico (está en el centro de salud del municipio / hospital)",
    "oxígeno y sueros por la vena",
    "radiografías y laboratorio",
]

# --- hierbas de la zona (uso tradicional seguro y documentado) -----------------
HIERBAS: list[dict] = [
    {"nombre": "manzanilla", "para": "cólicos, malestar de estómago, gases; lavado de ojos irritados",
     "uso": "infusión: 1 cucharadita de flores en 1 taza de agua caliente, reposar 5 minutos",
     "precaucion": "no si hay alergia a las margaritas; no reemplaza el tratamiento"},
    {"nombre": "hierbabuena / menta", "para": "náuseas, gases, indigestión leve",
     "uso": "infusión de hojas frescas",
     "precaucion": "puede empeorar la acidez; no dar a bebés menores de 1 año"},
    {"nombre": "jengibre", "para": "náuseas, mareo, malestar por frío",
     "uso": "infusión de 2 o 3 rodajas en agua caliente",
     "precaucion": "con moderación si hay gastritis o úlcera"},
    {"nombre": "sábila (gel de la penca)", "para": "quemaduras leves, raspones, piel irritada",
     "uso": "aplicar el gel fresco SOBRE LA PIEL, 2 o 3 veces al día",
     "precaucion": "NO se toma (es laxante fuerte); no en heridas profundas ni infectadas"},
    {"nombre": "eucalipto", "para": "congestión de nariz y pecho por resfriado",
     "uso": "vapor: hojas en agua caliente, respirar el vapor con cuidado, tapando la cabeza",
     "precaucion": "NO en bebés ni personas con asma; nunca beber el aceite"},
    {"nombre": "flor de sauco", "para": "resfriado y malestar con fiebre leve",
     "uso": "infusión SOLO de las flores bien identificadas",
     "precaucion": "los tallos y las hojas son tóxicos; usar solo la flor"},
    {"nombre": "limón con miel", "para": "tos y garganta irritada",
     "uso": "agua tibia con jugo de limón y una cucharadita de miel",
     "precaucion": "la miel solo para mayores de 1 año"},
    {"nombre": "ajo", "para": "acompañar el cuidado del resfriado",
     "uso": "comer un diente crudo o machacado en la comida",
     "precaucion": "puede irritar el estómago; no en grandes cantidades"},
]

HIERBAS_EVITAR = [
    "ruda (puede provocar aborto y es tóxica)",
    "apazote/epazote en exceso (tóxico, sobre todo en niños)",
    "purgantes o 'lavados' fuertes, en especial en niños o con diarrea",
    "altamisa y poleo en el embarazo",
]

_MEDS_EN_TEXTO = re.compile(
    r"\b(paracetamol|acetaminof[eé]n|ibuprofeno|amoxicilina|antibi[oó]tico|"
    r"suero oral|sales de rehidrataci[oó]n|hierro|[aá]cido f[oó]lico|"
    r"loratadina|antihistam[íi]nico|albendazol|desparasit)\w*",
    re.IGNORECASE,
)
_ALIAS = {
    "paracetamol": "paracetamol", "acetaminofén": "paracetamol", "acetaminofen": "paracetamol",
    "ibuprofeno": "ibuprofeno", "amoxicilina": "amoxicilina", "antibiótico": "amoxicilina",
    "antibiotico": "amoxicilina", "suero oral": "sales de rehidratación",
    "sales de rehidratación": "sales de rehidratación", "hierro": "hierro",
    "ácido fólico": "hierro", "loratadina": "loratadina", "antihistamínico": "loratadina",
    "albendazol": "albendazol",
}

_TIPO_ETIQUETA = {
    "puesto_salud": "puesto de salud", "minifarmacia": "minifarmacia",
    "botiquin": "botiquín comunitario", "promotor": "promotora de salud", "tienda": "tienda",
}


def _corto(item: str) -> str:
    return item.split(" tableta")[0].split(" 5")[0].split(" 4")[0].split(" (")[0].strip()


def puntos_para_sector(sector: str, puntos: list[dict]) -> list[dict]:
    """Puntos relevantes para el sector, del más cercano al más lejano:

    1. el que sirve a ESA localidad por nombre (botiquín / promotora / tienda local),
    2. el que sirve a toda la aldea (minifarmacia del centro),
    3. el puesto de salud, que queda lejos.

    Se omiten los puntos propios de OTROS sectores.
    """
    sector = (sector or "").strip()
    rankeados: list[tuple[int, dict]] = []
    for p in puntos:
        cd = p.get("cerca_de") or []
        if p.get("lejos"):
            rankeados.append((2, p))
        elif sector and (sector in cd or p["sector"] == sector):
            rankeados.append((0, p))
        elif "*" in cd:
            rankeados.append((1, p))
        elif not sector:  # sin sector conocido: muéstralos todos
            rankeados.append((1, p))
    rankeados.sort(key=lambda t: t[0])
    return [p for _, p in rankeados]


def contexto_modelo(sector: str, puntos_con_inv: list[dict]) -> str:
    """Párrafo de recursos para el prompt: qué hay cerca del sector de la persona."""
    ordenados = puntos_para_sector(sector, puntos_con_inv)
    frases = ["Recomienda SOLO cosas que la familia consiga en la aldea, y PRIMERO lo más "
              "cercano al vecino."]
    for p in ordenados:
        meds = sorted({_corto(x["item"]) for x in p.get("inventario", []) if x["cantidad"] > 0})
        if not meds:
            continue
        etq = _TIPO_ETIQUETA.get(p["tipo"], p["tipo"])
        cercania = "LEJOS, " + p["distancia"] if p.get("lejos") else p["distancia"]
        frases.append(f"{p['nombre']} ({etq}, {cercania}): {', '.join(meds)}.")
    frases.append("Si algo que ayudaría no está en ningún lado cercano, dilo y di a dónde "
                  "ir. Nunca mandes a alguien 2 horas al puesto de salud por algo que hay "
                  "en la minifarmacia o el botiquín de su sector.")
    hierbas = ", ".join(h["nombre"].split(" (")[0] for h in HIERBAS[:6])
    frases.append(f"Hierbas seguras de la zona: {hierbas}. Sugiere una SOLO si de verdad "
                  "sirve para lo que tiene la persona. Nunca recomiendes ruda ni purgantes fuertes.")
    return " ".join(frases)


def donde_conseguir(item_corto: str, sector: str, puntos_con_inv: list[dict]) -> str:
    """El punto más cercano al sector que tiene ese medicamento (o '')."""
    for p in puntos_para_sector(sector, puntos_con_inv):
        for x in p.get("inventario", []):
            if _corto(x["item"]).lower() == item_corto.lower() and x["cantidad"] > 0:
                donde = "el puesto de salud (lejos)" if p.get("lejos") else p["nombre"]
                return donde
    return ""


def cobertura_por_sector(puntos: list[dict]) -> dict[str, list[str]]:
    """Para cada localidad, los ids de punto que la surten, del más cercano al más
    lejano (el puesto de salud, si aplica, siempre al final). Es la misma lógica que
    usa el modelo — sirve para explicar en el panel de dónde saca medicina cada
    localidad."""
    return {
        s: [p["id"] for p in puntos_para_sector(s, puntos)]
        for s in SECTORES
    }


def nota_disponibilidad(texto: str, sector: str, puntos_con_inv: list[dict]) -> str:
    """Si el texto curado nombra un medicamento, dice dónde conseguirlo cerca del
    sector, o que no hay en la aldea. Determinístico, sin modelo."""
    vistos: set[str] = set()
    lineas: list[str] = []
    for m in _MEDS_EN_TEXTO.findall(texto):
        corto = _ALIAS.get(m.lower())
        if not corto or corto in vistos:
            continue
        vistos.add(corto)
        donde = donde_conseguir(corto, sector, puntos_con_inv)
        if donde:
            lineas.append(f"{corto.capitalize()}: hay en {donde}.")
        else:
            lineas.append(f"{corto.capitalize()}: hoy no hay en la aldea; pregunta en el "
                          f"puesto de salud.")
    return ("📍 Dónde conseguirlo: " + " ".join(lineas)) if lineas else ""
