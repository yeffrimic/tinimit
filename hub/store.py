"""Registro de Tinimit — SQLite en dos niveles.

`device.db`  — lo que guardaría el nodo de la aldea (ESP32/SBC local). Cada consulta y
               alerta se escribe aquí primero, con `sincronizado = 0`.
`hub.db`     — el hub central / puesto de salud. El panel lee SOLO de aquí.

`sync_device_to_hub()` empuja las filas nuevas de device -> hub y las marca
`sincronizado = 1`. En la demo se llama automáticamente después de cada escritura, así
que el panel va en vivo; se puede apagar (`store.enlace_hub = False`) para mostrar el
caso "sin enlace al hub": las filas se acumulan en device.db y el panel no las ve hasta
reconectar. Ningún dato sale nunca a internet.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from recursos import INVENTARIO_BASE, PUNTOS_BASE

_DATA_DIR = Path(os.environ.get("ALDEA_DATA_DIR", Path(__file__).with_name("data")))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pacientes (
  mac            TEXT PRIMARY KEY,
  nombre         TEXT DEFAULT '',
  edad           TEXT DEFAULT '',
  sector         TEXT DEFAULT '',
  alergias       TEXT DEFAULT '',
  creado_ts      REAL,
  actualizado_ts REAL
);
CREATE TABLE IF NOT EXISTS consultas (
  id             INTEGER PRIMARY KEY,
  conversacion_id TEXT DEFAULT '',
  mac            TEXT,
  nombre         TEXT DEFAULT '',
  sector         TEXT DEFAULT '',
  motivo         TEXT DEFAULT '',
  texto          TEXT DEFAULT '',
  respuesta      TEXT DEFAULT '',
  prioridad      TEXT DEFAULT 'rutina',
  es_emergencia  INTEGER DEFAULT 0,
  fuente         TEXT DEFAULT 'curado',
  ts             REAL,
  bytes_texto    INTEGER DEFAULT 0,
  bytes_aire     INTEGER DEFAULT 0,
  tramas         INTEGER DEFAULT 0,
  ratio          REAL DEFAULT 0,
  airtime_ms     REAL DEFAULT 0,
  sincronizado   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS conversaciones (
  id             TEXT PRIMARY KEY,
  mac            TEXT,
  nombre         TEXT DEFAULT '',
  sector         TEXT DEFAULT '',
  titulo         TEXT DEFAULT '',
  motivo         TEXT DEFAULT '',
  transcripcion  TEXT DEFAULT '[]',
  prioridad      TEXT DEFAULT 'rutina',
  es_emergencia  INTEGER DEFAULT 0,
  n_turnos       INTEGER DEFAULT 0,
  iniciada_ts    REAL,
  actualizada_ts REAL,
  sincronizado   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alertas (
  id           INTEGER PRIMARY KEY,
  consulta_id  INTEGER,
  mac          TEXT,
  nombre       TEXT DEFAULT '',
  sector       TEXT DEFAULT '',
  tipo         TEXT DEFAULT '',
  estado       TEXT DEFAULT 'nueva',
  ts           REAL,
  atendida_ts  REAL,
  sincronizado INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS recursos (
  punto_id  TEXT DEFAULT '',
  item      TEXT DEFAULT '',
  categoria TEXT DEFAULT '',
  cantidad  INTEGER DEFAULT 0,
  unidad    TEXT DEFAULT '',
  para      TEXT DEFAULT '',
  PRIMARY KEY (punto_id, item)
);
CREATE INDEX IF NOT EXISTS ix_consultas_ts ON consultas(ts);
CREATE INDEX IF NOT EXISTS ix_consultas_mac ON consultas(mac);
CREATE INDEX IF NOT EXISTS ix_consultas_conv ON consultas(conversacion_id);
CREATE INDEX IF NOT EXISTS ix_alertas_estado ON alertas(estado);
CREATE INDEX IF NOT EXISTS ix_conv_mac ON conversaciones(mac);
CREATE INDEX IF NOT EXISTS ix_conv_ts ON conversaciones(actualizada_ts);
"""

_PRIO_ORDEN = {"rutina": 0, "urgente": 1, "emergencia": 2}
_PUNT_FIN = re.compile(r"[\s.,;:!?¿¡…]+$")
_PREFIJO_CONSULTA = re.compile(r"^consult[oaéí?]?\w*\s+(por|sobre|de)\s+", re.IGNORECASE)


def _load_turnos(raw: str | None) -> list[dict]:
    try:
        v = json.loads(raw or "[]")
        return [t for t in v if isinstance(t, dict)] if isinstance(v, list) else []
    except Exception:  # noqa: BLE001
        return []


def _titulo_desde_texto(txt: str, n: int = 52) -> str:
    """Título corto a partir del primer mensaje: el síntoma / tema central."""
    txt = re.sub(r"\s+", " ", (txt or "").strip())
    txt = _PREFIJO_CONSULTA.sub("", txt)
    if len(txt) > n:
        txt = txt[:n].rsplit(" ", 1)[0] + "…"
    return _PUNT_FIN.sub("", txt) or "Consulta"


def _conn(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def _inicio_de_hoy() -> float:
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


class Store:
    def __init__(self, data_dir: Path = _DATA_DIR) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.device = _conn(data_dir / "device.db")
        self.hub = _conn(data_dir / "hub.db")
        self.enlace_hub = True  # False = simular "sin enlace al hub central"
        self._sembrar_recursos()

    def _sembrar_recursos(self) -> None:
        """Carga el catálogo la primera vez (no pisa cantidades editadas)."""
        filas = [
            {"punto_id": pid, **it}
            for pid, items in INVENTARIO_BASE.items()
            for it in items
        ]
        for db in (self.device, self.hub):
            if db.execute("SELECT COUNT(*) c FROM recursos").fetchone()["c"]:
                continue
            db.executemany(
                "INSERT INTO recursos(punto_id,item,categoria,cantidad,unidad,para) "
                "VALUES(:punto_id,:item,:categoria,:cantidad,:unidad,:para)",
                filas,
            )
            db.commit()

    def _puntos_con_inv(self, db: sqlite3.Connection) -> list[dict]:
        inv: dict[str, list[dict]] = {}
        for r in db.execute("SELECT * FROM recursos").fetchall():
            inv.setdefault(r["punto_id"], []).append(dict(r))
        return [{**p, "inventario": inv.get(p["id"], [])} for p in PUNTOS_BASE]

    def puntos(self) -> list[dict]:
        """Para el panel: puntos con su inventario (desde hub.db)."""
        out = self._puntos_con_inv(self.hub)
        for p in out:
            p["inventario"].sort(key=lambda x: (x["cantidad"] <= 0, x["categoria"], x["item"]))
        return out

    def recursos_inventario(self) -> list[dict]:
        """Para el modelo: puntos con inventario, desde device.db (el nodo de la aldea)."""
        return self._puntos_con_inv(self.device)

    def ajustar_recurso(self, punto_id: str, item: str, cantidad: int) -> dict | None:
        cantidad = max(0, int(cantidad))
        for db in (self.device, self.hub):
            db.execute(
                "UPDATE recursos SET cantidad=? WHERE punto_id=? AND item=?",
                (cantidad, punto_id, item),
            )
            db.commit()
        row = self.hub.execute(
            "SELECT * FROM recursos WHERE punto_id=? AND item=?", (punto_id, item)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ perfiles
    def get_perfil(self, mac: str) -> dict | None:
        for db in (self.hub, self.device):
            row = db.execute("SELECT * FROM pacientes WHERE mac = ?", (mac,)).fetchone()
            if row:
                return dict(row)
        return None

    def put_perfil(self, mac: str, **campos) -> dict:
        ahora = time.time()
        existe = self.device.execute(
            "SELECT creado_ts FROM pacientes WHERE mac = ?", (mac,)
        ).fetchone()
        creado = existe["creado_ts"] if existe else ahora
        fila = {
            "mac": mac,
            "nombre": campos.get("nombre", ""),
            "edad": str(campos.get("edad", "")),
            "sector": campos.get("sector", ""),
            "alergias": campos.get("alergias", ""),
            "creado_ts": creado,
            "actualizado_ts": ahora,
        }
        self.device.execute(
            """INSERT INTO pacientes(mac,nombre,edad,sector,alergias,creado_ts,actualizado_ts)
               VALUES(:mac,:nombre,:edad,:sector,:alergias,:creado_ts,:actualizado_ts)
               ON CONFLICT(mac) DO UPDATE SET
                 nombre=excluded.nombre, edad=excluded.edad, sector=excluded.sector,
                 alergias=excluded.alergias, actualizado_ts=excluded.actualizado_ts""",
            fila,
        )
        self.device.commit()
        self._sync()
        return fila

    # ------------------------------------------------------------------ consultas
    def log_consulta(
        self,
        *,
        mac: str,
        motivo: str,
        texto: str,
        respuesta: str,
        prioridad: str,
        fuente: str,
        lora: dict,
        es_emergencia: bool = False,
        tipo_emergencia: str = "",
        conversacion_id: str = "",
    ) -> int:
        perfil = self.get_perfil(mac) or {}
        ahora = time.time()
        cur = self.device.execute(
            """INSERT INTO consultas
               (conversacion_id,mac,nombre,sector,motivo,texto,respuesta,prioridad,
                es_emergencia,fuente,ts,bytes_texto,bytes_aire,tramas,ratio,airtime_ms,
                sincronizado)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                conversacion_id, mac, perfil.get("nombre", ""), perfil.get("sector", ""),
                motivo, texto, respuesta, prioridad, int(es_emergencia), fuente, ahora,
                lora.get("bytes_in", 0), lora.get("bytes_comprimido", 0),
                lora.get("tramas", 0), lora.get("ratio", 0.0), lora.get("airtime_ms", 0.0),
            ),
        )
        cid = cur.lastrowid
        if es_emergencia:
            self.device.execute(
                """INSERT INTO alertas(consulta_id,mac,nombre,sector,tipo,estado,ts,sincronizado)
                   VALUES(?,?,?,?,?, 'nueva', ?, 0)""",
                (cid, mac, perfil.get("nombre", ""), perfil.get("sector", ""),
                 tipo_emergencia or motivo, ahora),
            )
        self.device.commit()
        self._sync()
        return cid

    def atender_alerta(self, alerta_id: int) -> bool:
        ahora = time.time()
        for db in (self.device, self.hub):
            db.execute(
                "UPDATE alertas SET estado='atendida', atendida_ts=? WHERE id=?",
                (ahora, alerta_id),
            )
            db.commit()
        return True

    # -------------------------------------------------------------- conversaciones
    def registrar_conversacion(
        self,
        *,
        conv_id: str,
        mac: str,
        mensajes: list[dict],
        motivo: str = "",
        titulo: str = "",
        prioridad: str = "rutina",
        es_emergencia: bool = False,
    ) -> str:
        """Crea o actualiza una conversación (un tema, varios turnos).

        `mensajes` es la transcripción completa `[{rol, texto}]` (el cliente la manda
        entera en cada turno). El título se fija la primera vez y ya no cambia: es el
        síntoma / tema central para distinguir conversaciones en el panel.
        """
        conv_id = conv_id or f"srv-{time.time():.3f}".replace(".", "")
        perfil = self.get_perfil(mac) or {}
        ahora = time.time()
        turnos = [
            {"rol": ("bot" if str(m.get("rol")) in ("bot", "assistant", "sys")
                     else "user"),
             "texto": (m.get("texto") or "").strip()}
            for m in (mensajes or [])
            if (m.get("texto") or "").strip()
        ][-40:]

        prev = self.device.execute(
            "SELECT titulo, iniciada_ts, prioridad FROM conversaciones WHERE id = ?",
            (conv_id,),
        ).fetchone()
        iniciada = prev["iniciada_ts"] if prev else ahora
        tit = (prev["titulo"] if prev and prev["titulo"] else "") or titulo
        if not tit:
            primer = next((t["texto"] for t in turnos if t["rol"] == "user"), "")
            tit = _titulo_desde_texto(primer)
        pri_prev = prev["prioridad"] if prev else "rutina"
        prioridad = max([prioridad, pri_prev], key=lambda p: _PRIO_ORDEN.get(p, 0))

        self.device.execute(
            """INSERT INTO conversaciones
               (id,mac,nombre,sector,titulo,motivo,transcripcion,prioridad,es_emergencia,
                n_turnos,iniciada_ts,actualizada_ts,sincronizado)
               VALUES(:id,:mac,:nombre,:sector,:titulo,:motivo,:transcripcion,:prioridad,
                      :es_emergencia,:n_turnos,:iniciada_ts,:actualizada_ts,0)
               ON CONFLICT(id) DO UPDATE SET
                 nombre=excluded.nombre, sector=excluded.sector, titulo=excluded.titulo,
                 motivo=CASE WHEN excluded.motivo != '' THEN excluded.motivo
                             ELSE conversaciones.motivo END,
                 transcripcion=excluded.transcripcion, prioridad=excluded.prioridad,
                 es_emergencia=MAX(conversaciones.es_emergencia, excluded.es_emergencia),
                 n_turnos=excluded.n_turnos, actualizada_ts=excluded.actualizada_ts,
                 sincronizado=0""",
            {
                "id": conv_id, "mac": mac,
                "nombre": perfil.get("nombre", ""), "sector": perfil.get("sector", ""),
                "titulo": tit[:80], "motivo": motivo,
                "transcripcion": json.dumps(turnos, ensure_ascii=False),
                "prioridad": prioridad, "es_emergencia": int(es_emergencia),
                "n_turnos": len(turnos),
                "iniciada_ts": iniciada, "actualizada_ts": ahora,
            },
        )
        self.device.commit()
        self._sync()
        return conv_id

    def conversaciones(self, mac: str | None = None, limit: int = 60) -> list[dict]:
        where = "WHERE mac = ?" if mac else ""
        args: list = [mac] if mac else []
        args.append(limit)
        rows = self.hub.execute(
            f"""SELECT id,mac,nombre,sector,titulo,motivo,prioridad,es_emergencia,
                       n_turnos,iniciada_ts,actualizada_ts,transcripcion
                FROM conversaciones {where}
                ORDER BY actualizada_ts DESC LIMIT ?""",
            args,
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            turnos = _load_turnos(d.pop("transcripcion"))
            d["ultima_respuesta"] = next(
                (t["texto"] for t in reversed(turnos) if t["rol"] == "bot"), "")
            d["ultima_pregunta"] = next(
                (t["texto"] for t in reversed(turnos) if t["rol"] == "user"), "")
            d["preview"] = (d["ultima_respuesta"] or d["ultima_pregunta"])[:150]
            out.append(d)
        return out

    def conversacion(self, conv_id: str) -> dict | None:
        r = self.hub.execute(
            "SELECT * FROM conversaciones WHERE id = ?", (conv_id,)
        ).fetchone()
        if not r:
            return None
        d = dict(r)
        d["transcripcion"] = _load_turnos(d["transcripcion"])
        d["intercambios"] = [
            dict(x) for x in self.hub.execute(
                """SELECT id, texto, respuesta, prioridad, fuente, ts,
                          bytes_texto, bytes_aire, tramas, ratio
                   FROM consultas WHERE conversacion_id = ? ORDER BY ts""",
                (conv_id,),
            ).fetchall()
        ]
        return d

    # ------------------------------------------------------------------ sync
    def sync_device_to_hub(self) -> dict:
        """Empuja filas nuevas device -> hub. Devuelve cuántas de cada tipo."""
        movidas = {"pacientes": 0, "conversaciones": 0, "consultas": 0, "alertas": 0}

        for row in self.device.execute("SELECT * FROM pacientes").fetchall():
            self.hub.execute(
                """INSERT INTO pacientes(mac,nombre,edad,sector,alergias,creado_ts,actualizado_ts)
                   VALUES(:mac,:nombre,:edad,:sector,:alergias,:creado_ts,:actualizado_ts)
                   ON CONFLICT(mac) DO UPDATE SET
                     nombre=excluded.nombre, edad=excluded.edad, sector=excluded.sector,
                     alergias=excluded.alergias, actualizado_ts=excluded.actualizado_ts""",
                dict(row),
            )
            movidas["pacientes"] += 1

        for tabla in ("conversaciones", "consultas", "alertas"):
            filas = self.device.execute(
                f"SELECT * FROM {tabla} WHERE sincronizado = 0"
            ).fetchall()
            for row in filas:
                d = dict(row)
                d["sincronizado"] = 1
                cols = ",".join(d)
                ph = ",".join(f":{k}" for k in d)
                self.hub.execute(
                    f"INSERT OR REPLACE INTO {tabla}({cols}) VALUES({ph})", d
                )
                self.device.execute(
                    f"UPDATE {tabla} SET sincronizado = 1 WHERE id = ?", (row["id"],)
                )
                movidas[tabla] += 1

        self.hub.commit()
        self.device.commit()
        return movidas

    def _sync(self) -> None:
        if self.enlace_hub:
            self.sync_device_to_hub()

    def pendientes_de_sync(self) -> int:
        n = 0
        for tabla in ("conversaciones", "consultas", "alertas"):
            n += self.device.execute(
                f"SELECT COUNT(*) c FROM {tabla} WHERE sincronizado = 0"
            ).fetchone()["c"]
        return n

    # ------------------------------------------------------------------ lecturas (panel)
    def contexto_historial(self, mac: str, excluir_conv: str = "") -> str:
        """Para el modelo: de qué habló antes esta persona, por conversación.

        Sólo títulos + cuándo (no el texto completo — eso sería demasiado y lento). Si
        la persona retoma una conversación vieja, el kiosko manda su transcripción
        entera como `mensajes`, así que el modelo igual tiene el detalle.
        """
        filas = self.hub.execute(
            """SELECT titulo, motivo, prioridad, actualizada_ts FROM conversaciones
               WHERE mac = ? AND id != ? ORDER BY actualizada_ts DESC LIMIT 4""",
            (mac, excluir_conv or "\x00"),
        ).fetchall()
        if not filas:
            return ""
        ahora = time.time()
        partes = []
        for f in filas:
            dias = int((ahora - (f["actualizada_ts"] or ahora)) / 86400)
            cuando = "hoy" if dias == 0 else "ayer" if dias == 1 else f"hace {dias} días"
            tit = f["titulo"] or f["motivo"] or "consulta"
            marca = ", fue emergencia" if f["prioridad"] == "emergencia" else ""
            partes.append(f"«{tit}» ({cuando}{marca})")
        return "Conversaciones previas de esta persona: " + "; ".join(partes) + "."

    def resumen(self) -> dict:
        h = self.hub
        hoy = _inicio_de_hoy()
        total = h.execute("SELECT COUNT(*) c FROM consultas").fetchone()["c"]
        hoy_n = h.execute(
            "SELECT COUNT(*) c FROM consultas WHERE ts >= ?", (hoy,)
        ).fetchone()["c"]
        conv_total = h.execute("SELECT COUNT(*) c FROM conversaciones").fetchone()["c"]
        conv_hoy = h.execute(
            "SELECT COUNT(*) c FROM conversaciones WHERE actualizada_ts >= ?", (hoy,)
        ).fetchone()["c"]
        abiertas = h.execute(
            "SELECT COUNT(*) c FROM alertas WHERE estado = 'nueva'"
        ).fetchone()["c"]
        pac = h.execute("SELECT COUNT(*) c FROM pacientes").fetchone()["c"]

        sectores = []
        rows = h.execute(
            """SELECT COALESCE(NULLIF(sector,''),'Sin sector') sector,
                      COUNT(*) consultas,
                      SUM(es_emergencia) emergencias,
                      MAX(ts) ultima_ts,
                      GROUP_CONCAT(prioridad) prios
               FROM consultas GROUP BY 1 ORDER BY consultas DESC"""
        ).fetchall()
        for r in rows:
            prios = (r["prios"] or "").split(",")
            pmax = max(prios, key=lambda p: _PRIO_ORDEN.get(p, 0)) if prios else "rutina"
            abiertas_sec = h.execute(
                """SELECT COUNT(*) c FROM alertas
                   WHERE estado='nueva' AND COALESCE(NULLIF(sector,''),'Sin sector')=?""",
                (r["sector"],),
            ).fetchone()["c"]
            sectores.append({
                "sector": r["sector"],
                "consultas": r["consultas"],
                "emergencias": r["emergencias"] or 0,
                "alertas_abiertas": abiertas_sec,
                "ultima_ts": r["ultima_ts"],
                "prioridad_max": pmax,
            })

        return {
            "consultas_total": total,
            "consultas_hoy": hoy_n,
            "conversaciones_total": conv_total,
            "conversaciones_hoy": conv_hoy,
            "emergencias_abiertas": abiertas,
            "pacientes": pac,
            "sin_sincronizar": self.pendientes_de_sync(),
            "enlace_hub": self.enlace_hub,
            "sectores": sectores,
        }

    def feed(self, desde_id: int = 0, limit: int = 60) -> list[dict]:
        rows = self.hub.execute(
            """SELECT id, mac, nombre, sector, motivo, respuesta, prioridad,
                      es_emergencia, fuente, ts, bytes_texto, bytes_aire, tramas, ratio
               FROM consultas WHERE id > ? ORDER BY id DESC LIMIT ?""",
            (desde_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["resumen"] = (d.pop("respuesta") or "")[:160]
            out.append(d)
        return out

    def alertas_abiertas(self) -> list[dict]:
        rows = self.hub.execute(
            """SELECT a.*, c.respuesta FROM alertas a
               LEFT JOIN consultas c ON c.id = a.consulta_id
               WHERE a.estado = 'nueva' ORDER BY a.ts DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def buscar_pacientes(self, q: str) -> list[dict]:
        like = f"%{q}%"
        rows = self.hub.execute(
            """SELECT p.mac, p.nombre, p.sector, p.edad,
                      (SELECT COUNT(*) FROM conversaciones v WHERE v.mac = p.mac) conversaciones,
                      (SELECT COUNT(*) FROM consultas c WHERE c.mac = p.mac) consultas,
                      (SELECT MAX(actualizada_ts) FROM conversaciones v WHERE v.mac = p.mac) ultima_ts
               FROM pacientes p
               WHERE p.nombre LIKE ? OR p.mac LIKE ? OR p.sector LIKE ?
               ORDER BY ultima_ts DESC NULLS LAST LIMIT 25""",
            (like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]

    def paciente(self, mac: str) -> dict | None:
        perfil = self.hub.execute(
            "SELECT * FROM pacientes WHERE mac = ?", (mac,)
        ).fetchone()
        convs = self.conversaciones(mac=mac, limit=200)
        consultas = self.hub.execute(
            """SELECT id, motivo, texto, respuesta, prioridad, es_emergencia, fuente, ts,
                      bytes_texto, bytes_aire, tramas, ratio
               FROM consultas WHERE mac = ? ORDER BY ts DESC""",
            (mac,),
        ).fetchall()
        if not perfil and not convs and not consultas:
            return None
        return {
            "perfil": dict(perfil) if perfil else {"mac": mac},
            "conversaciones": convs,
            "consultas": [dict(c) for c in consultas],
        }


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
