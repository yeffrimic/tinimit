"""Kaqchikel (cak) — solo cadenas con fuente confiable. El resto hereda de `es`.

El contenido clínico kaqchikel debe validarse con hablantes / ALMG / MSPAS antes de
usarse. NO se genera con el modelo. Ver `docs/idiomas-maya.md`.

Kaqchikel SÍ tiene localización de Firefox de Mozilla (MPL-2.0, revisada por la
comunidad): github.com/mozilla-l10n/firefox-l10n, carpeta `cak/`. De ahí salen las
cadenas de interfaz (no clínicas). Las clínicas siguen pendientes.
"""

T: dict[str, str] = {
    "langName": "Kaqchikel",
    "saludo": "La utz awäch?",  # saludo verificado (ya estaba en el kiosko)
}

# Vocabulario de UI de Mozilla Firefox (cak/), por si se amplía la interfaz:
#   Aceptar=ÜTZ  Cancelar=Tiq'at  Sí=Je'  No=Manäq  Guardar=Tiyak
#   Revertir/Atrás=Titzolïx  Cerrar=Titz'apïx  Eliminar=Tiyuj
#   Alerta="Retal k'ayewal"  Confirmar=Tajikib'a'  Idioma(s)="Taq ch'ab'äl"
#   "Saber más"="Tetamäx ch'aqa'"  Ubicación no aplica
