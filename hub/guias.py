"""Datos clínicos curados — única fuente de verdad compartida por el kiosko y el hub.

NADA de esto se genera con el modelo. Son textos revisados a mano (orientación de
puesto de salud rural). El modelo solo los usa como marco y como red de seguridad:
- las repreguntas guiadas salen de aquí tal cual,
- la orientación final del modelo cae a estos textos si falla o se sale de rango,
- los primeros auxilios de emergencia se muestran SIEMPRE desde aquí.

Mantener sincronizado con `prototipo/kiosk.html`: `MOTIVOS`, `EMERGENCIAS` y
`GUIAS_OFFLINE` (solo las `preguntas`) tienen una copia en el kiosko para el modo sin
enlace. Tras cualquier cambio aquí, regenerar el diccionario del códec:
`python tools/build_dict.py`.
"""

from __future__ import annotations

# Prioridades válidas, de menor a mayor.
PRIORIDADES = ("rutina", "urgente", "emergencia")

# Motivos de la grilla del kiosko. `label` para prompts del modelo.
MOTIVOS: dict[str, str] = {
    "fiebre": "fiebre",
    "dolor": "dolor",
    "diarrea": "diarrea",
    "tos": "tos o gripe",
    "herida": "herida",
    "embarazo": "embarazo",
    "nino": "niño enfermo",
    "medicamento": "duda sobre un medicamento",
    "otro": "otra molestia",
}

# Guiones de repreguntas + orientación de respaldo, por motivo.
GUIAS: dict[str, dict] = {
    "fiebre": {
        "prioridad": "rutina",
        "preguntas": [
            "¿Hace cuántos días tiene fiebre?",
            "¿Pudiste medir la temperatura? ¿Cuánto marcó?",
            "¿Tiene además dolor de cabeza fuerte, vómitos, manchas en la piel, convulsiones o le cuesta respirar?",
        ],
        "orientacion": (
            "Dale líquidos en poca cantidad y seguido. Puedes usar paracetamol según el "
            "peso, cada 6 horas, sin pasar la dosis. Mantén a la persona fresca, sin "
            "abrigar de más.\n\nAcude hoy al puesto de salud si la fiebre pasa de 3 días, "
            "sube de 39°C y no baja, o aparece cualquier señal de alarma: no despierta "
            "bien, manchas moradas, vómito constante o dificultad para respirar."
        ),
    },
    "dolor": {
        "prioridad": "urgente",
        "preguntas": [
            "¿En qué parte del cuerpo es el dolor?",
            "¿Desde cuándo y qué tan fuerte es: leve, molesto o muy fuerte?",
            "¿Apareció después de un golpe o esfuerzo? ¿Se corre hacia otra parte del cuerpo?",
        ],
        "orientacion": (
            "Para dolor leve o moderado puedes usar paracetamol según el peso, cada 6 a 8 "
            "horas, y descansar la zona.\n\nBusca atención pronto si el dolor es en el "
            "pecho y baja al brazo o la mandíbula, es en la parte baja derecha de la "
            "barriga y va en aumento, viene con fiebre alta, o no cede en 2 o 3 días."
        ),
    },
    "diarrea": {
        "prioridad": "urgente",
        "preguntas": [
            "¿Cuántas veces al día y desde cuándo?",
            "¿Hay sangre o moco en el excremento? ¿Hay vómito?",
            "¿Orina poco, tiene la boca seca, los ojos hundidos o está muy decaída?",
        ],
        "orientacion": (
            "Lo más importante es reponer líquidos: da suero oral (un sobre en 1 litro de "
            "agua limpia) a sorbos después de cada evacuación. Sigue dando de comer; si es "
            "bebé, sigue con el pecho. Evita gaseosas y jugos muy dulces.\n\nAcude al "
            "puesto de salud si hay sangre, vómito que no para, señales de deshidratación, "
            "o si la diarrea dura más de 2 días (más de 1 día en un niño pequeño)."
        ),
    },
    "tos": {
        "prioridad": "rutina",
        "preguntas": [
            "¿Hace cuántos días? ¿Es seca o con flema?",
            "¿Hay fiebre, dolor de garganta o de oído?",
            "¿Le silba el pecho, respira rápido o se le hunden las costillas al respirar?",
        ],
        "orientacion": (
            "Toma líquidos tibios, miel si es mayor de 1 año, y descansa. La mayoría de "
            "las gripes mejoran en 5 a 7 días.\n\nAcude al puesto de salud si hay "
            "dificultad para respirar, respiración rápida, fiebre que no baja en 3 días, "
            "o la tos dura más de 2 semanas."
        ),
    },
    "herida": {
        "prioridad": "urgente",
        "preguntas": [
            "¿Cómo se hizo la herida y hace cuánto?",
            "¿Sangra mucho ahora o ya se detuvo?",
            "¿Es profunda, tiene tierra u objeto adentro, o fue por mordedura o algo oxidado?",
        ],
        "orientacion": (
            "Lava tus manos, limpia la herida con agua limpia a chorro y jabón, seca y "
            "cúbrela con tela o gasa limpia. Cambia el apósito a diario.\n\nBusca atención "
            "hoy si la herida es profunda o abierta (puede necesitar puntos), no deja de "
            "sangrar, fue con algo oxidado o por mordedura, o si no tienes la vacuna del "
            "tétanos al día. Vigila señales de infección: enrojecimiento que crece, calor, "
            "pus o fiebre."
        ),
    },
    "embarazo": {
        "prioridad": "urgente",
        "preguntas": [
            "¿De cuántos meses o semanas está?",
            "¿Qué está sintiendo: control de rutina, dolor, sangrado, dolor de cabeza, hinchazón?",
            "¿El bebé se mueve como siempre? ¿Ha tenido algún problema en este embarazo?",
        ],
        "orientacion": (
            "Lleva tu control con la comadrona o en el puesto de salud, toma el hierro y "
            "el ácido fólico, y come variado.\n\nAcude de inmediato si hay sangrado, "
            "pérdida de líquido, dolor fuerte y seguido de barriga, dolor de cabeza fuerte "
            "con visión borrosa, hinchazón repentina de cara y manos, fiebre, o si el bebé "
            "deja de moverse."
        ),
    },
    "nino": {
        "prioridad": "urgente",
        "preguntas": [
            "¿Qué edad tiene el niño o la niña?",
            "¿Qué le notas: fiebre, tos, diarrea, no quiere comer, decaído?",
            "¿Está tomando líquidos y orinando? ¿Respira bien? ¿Reacciona como siempre?",
        ],
        "orientacion": (
            "En niños pequeños vigila de cerca: ofrece líquidos y pecho seguido.\n\n"
            "Señales para acudir hoy mismo al puesto de salud: no quiere tomar nada, "
            "vomita todo, respira rápido o con dificultad, está muy decaído o no despierta "
            "bien, tiene convulsiones, o le sale sarpullido con la piel muy pálida o morada."
        ),
    },
    "medicamento": {
        "prioridad": "rutina",
        "preguntas": [
            "¿Qué medicamento es y para quién?",
            "¿Sabes la dosis indicada y cada cuánto tomarlo?",
            "¿La persona es alérgica a algún medicamento o toma otros?",
        ],
        "orientacion": (
            "Toma el medicamento tal como lo indicó el personal de salud: misma dosis, "
            "mismas horas y todos los días indicados, aunque ya te sientas bien (sobre "
            "todo los antibióticos). No compartas medicamentos ni uses sobras.\n\nSi "
            "aparece roncha, hinchazón de labios o dificultad para respirar, suspende y "
            "busca ayuda de inmediato."
        ),
    },
    "otro": {
        "prioridad": "rutina",
        "preguntas": [
            "Cuéntame con tus palabras qué está pasando.",
            "¿Desde cuándo lo notas y ha cambiado con el tiempo?",
            "¿Hay algo que lo mejora o lo empeora? ¿Alguna otra molestia?",
        ],
        "orientacion": (
            "Gracias. Anota cómo evoluciona (desde cuándo, qué lo cambia) y coméntalo en "
            "tu próxima visita al puesto de salud.\n\nSi aparece dolor fuerte, fiebre alta "
            "que no baja, sangrado, dificultad para respirar o te sientes cada vez peor, "
            "no esperes: acude a atención."
        ),
    },
}

GENERIC_PREGUNTA = (
    "Cuéntame con tus palabras qué te está molestando y desde cuándo. "
    "También puedes tocar uno de los botones de arriba."
)
GENERIC_ORIENTACION = (
    "Gracias por contarme. Descansa, toma agua y observa cómo sigues.\n\n"
    "Ve al puesto de salud si empeora, si no mejora en 2 o 3 días, o si aparece "
    "fiebre alta, dolor fuerte, sangrado o te cuesta respirar."
)

# Tipos de emergencia + primeros auxilios. Se muestran SIEMPRE tal cual.
EMERGENCIAS: dict[str, str] = {
    "sangrado": "sangrado abundante",
    "respira": "la persona no respira o respira mal",
    "parto": "parto en curso",
    "intox": "intoxicación o envenenamiento",
    "mordedura": "mordedura de serpiente o animal",
    "accidente": "accidente o golpe grave",
    "otra": "otra emergencia",
}

FIRST_AID: dict[str, list[str]] = {
    "sangrado": [
        "Presiona fuerte y sin soltar sobre la herida con una tela limpia.",
        "Si puedes, eleva la parte que sangra por encima del corazón.",
        "Si la tela se empapa, pon otra encima sin quitar la primera.",
        "Acuesta a la persona y abrígala; vigila que siga despierta.",
    ],
    "respira": [
        "Pide ayuda a gritos a las personas cercanas.",
        "Revisa la boca y saca solo lo que veas suelto.",
        "Si no respira y sabes RCP: 30 compresiones fuertes al centro del pecho y 2 respiraciones. Repite sin parar.",
        "No dejes sola a la persona hasta que llegue ayuda.",
    ],
    "parto": [
        "Lávate bien las manos. Si la comadrona está, deja que ella guíe.",
        "Cuando salga el bebé, recíbelo con una tela limpia y sécalo.",
        "Ponlo sobre el pecho de la madre, piel con piel, y abriga a los dos.",
        "No jales el cordón ni cortes nada; espera a la ayuda.",
    ],
    "intox": [
        "Aleja a la persona del producto y del lugar.",
        "NO le provoques el vómito.",
        "Guarda el envase del producto para mostrarlo.",
        "Si está en la piel o los ojos, lava con agua abundante varios minutos.",
    ],
    "mordedura": [
        "Mantén a la persona quieta y calmada; el movimiento reparte el veneno.",
        "Baja la zona mordida por debajo del corazón y quítale anillos o pulseras.",
        "NO cortes, NO succiones y NO pongas torniquete.",
        "Marca con lapicero el borde de la hinchazón y anota la hora.",
    ],
    "accidente": [
        "Si golpeó cabeza, cuello o espalda, no la muevas salvo que haya más peligro.",
        "Controla los sangrados con presión.",
        "Abrígala y háblale para mantenerla despierta.",
        "Vigila que siga respirando hasta que llegue ayuda.",
    ],
    "otra": [
        "Mantén la calma y quédate con la persona.",
        "No la muevas sin necesidad.",
        "Abrígala y aflójale la ropa apretada.",
        "Vigila su respiración y su estado hasta que llegue ayuda.",
    ],
}


def maxima(a: str, b: str) -> str:
    """Devuelve la prioridad más alta de las dos."""
    ia = PRIORIDADES.index(a) if a in PRIORIDADES else 0
    ib = PRIORIDADES.index(b) if b in PRIORIDADES else 0
    return PRIORIDADES[max(ia, ib)]
