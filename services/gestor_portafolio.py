"""
gestor_portafolio.py - Persistencia atómica, catálogo y registro de operaciones.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Ruta absoluta junto al módulo, para que no dependa del cwd del proceso.
ARCHIVO_DATOS = str(Path(__file__).resolve().parent / "datos_portafolio.json")

# Catálogo fijo de acciones: (símbolo, nombre, sector, bolsa).
CATALOGO_ACCIONES = [
    ("KO", "Coca-Cola", "Consumo", "NYSE"),
    ("PEP", "PepsiCo", "Consumo", "NASDAQ"),
    ("NKE", "Nike", "Consumo", "NYSE"),
    ("MCD", "McDonald's", "Consumo", "NYSE"),
    ("AAPL", "Apple", "Tecnología", "NASDAQ"),
    ("MSFT", "Microsoft", "Tecnología", "NASDAQ"),
    ("GOOGL", "Alphabet (Google)", "Tecnología", "NASDAQ"),
    ("AMZN", "Amazon", "Tecnología", "NASDAQ"),
    ("NVDA", "NVIDIA", "Tecnología", "NASDAQ"),
    ("TSLA", "Tesla", "Tecnología", "NASDAQ"),
    ("JPM", "JPMorgan Chase", "Finanzas", "NYSE"),
    ("V", "Visa", "Finanzas", "NYSE"),
    ("XOM", "ExxonMobil", "Energía", "NYSE"),
    ("JNJ", "Johnson & Johnson", "Salud", "NYSE"),
    ("T", "AT&T", "Telecom", "NYSE"),
    ("EC", "Ecopetrol (Colombia)", "Colombia", "NYSE"),
    ("CIB", "Bancolombia (Colombia)", "Colombia", "NYSE"),
    ("SPY", "ETF S&P 500", "ETF", "NYSE"),
    ("QQQ", "ETF Nasdaq 100", "ETF", "NASDAQ"),
]

OPCIONES_ACCIONES = sorted(f"{nombre} ({simbolo})" for simbolo, nombre, _, _ in CATALOGO_ACCIONES)
NOMBRES_ACCIONES = {simbolo: nombre for simbolo, nombre, _, _ in CATALOGO_ACCIONES}
BOLSAS_ACCIONES = {simbolo: bolsa for simbolo, _, _, bolsa in CATALOGO_ACCIONES}

# Versión del esquema persistido, para migraciones futuras.
ESQUEMA_VERSION = 1


def extraer_simbolo(texto: str) -> str:
    """Extrae el símbolo entre paréntesis finales o usa el texto tal cual."""
    texto = str(texto).strip()
    m = re.search(r"\(([^()]+)\)\s*$", texto)
    return (m.group(1) if m else texto).strip().upper()


def nombre_accion(simbolo: str) -> str:
    """Devuelve 'Nombre (SÍMBOLO)' o el símbolo si no está en el catálogo."""
    nombre = NOMBRES_ACCIONES.get(simbolo)
    return f"{nombre} ({simbolo})" if nombre else simbolo


# Esquema

class GestorPortafolio:
    """Carga, guarda y registra operaciones del portafolio con validación."""

    def __init__(self, archivo: str = ARCHIVO_DATOS) -> None:
        self.archivo = archivo
        self.datos = self.cargar()

    def datos_vacios(self) -> dict:
        """Estructura base del portafolio."""
        return {
            "esquema": ESQUEMA_VERSION,
            "saldo": 0.0,
            "cdts": [],
            "bonos": [],
            "tes": [],
            "acciones": {},
            "dividendos": [],
            "movimientos": [],
        }

    def _migrar(self, datos: dict) -> dict:
        """Aplica defaults sobre datos viejos sin romperlos."""
        base = self.datos_vacios()
        base.update(datos)
        base["esquema"] = ESQUEMA_VERSION
        # Si el JSON trae tipos inconsistentes, se reinicia esa sección.
        if not isinstance(base.get("acciones"), dict):
            logger.warning("Esquema inválido en 'acciones'; se reinicia a {}")
            base["acciones"] = {}
        if not isinstance(base.get("movimientos"), list):
            base["movimientos"] = []
        return base


# Carga y guardado

    def cargar(self) -> dict:
        """Carga JSON con validación de esquema; retorna esqueleto si falla."""
        if not os.path.exists(self.archivo):
            return self.datos_vacios()
        try:
            with open(self.archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos, dict):
                raise ValueError("El JSON raíz no es un objeto")
            return self._migrar(datos)
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.error("No se pudo cargar %s: %s", self.archivo, e)
            return self.datos_vacios()

    def guardar(self) -> None:
        """Escritura atómica vía archivo temporal + os.replace."""
        directorio = os.path.dirname(self.archivo) or "."
        os.makedirs(directorio, exist_ok=True)
        # Se escribe a un temporal en el mismo directorio para que os.replace
        # sea atómico (mismo sistema de archivos). Si el proceso muere a mitad,
        # el archivo original queda intacto.
        fd, tmp = tempfile.mkstemp(dir=directorio, prefix=".portafolio_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.archivo)
        except OSError as e:
            logger.error("Error al guardar %s: %s", self.archivo, e)
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


# Validaciones

    @staticmethod
    def _validar_positivo(valor: float, campo: str) -> float:
        """Verifica que `valor` sea numérico y > 0."""
        try:
            v = float(valor)
        except (TypeError, ValueError):
            raise ValueError(f"{campo} debe ser numérico: {valor!r}")
        if v <= 0:
            raise ValueError(f"{campo} debe ser > 0: {v}")
        return v

    @staticmethod
    def _validar_no_negativo(valor: float, campo: str) -> float:
        """Verifica que `valor` sea numérico y >= 0."""
        try:
            v = float(valor)
        except (TypeError, ValueError):
            raise ValueError(f"{campo} debe ser numérico: {valor!r}")
        if v < 0:
            raise ValueError(f"{campo} no puede ser negativo: {v}")
        return v

    @staticmethod
    def _validar_fecha(fecha: str) -> str:
        """Valida formato ISO YYYY-MM-DD."""
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
            return fecha
        except ValueError:
            raise ValueError(f"Fecha inválida (YYYY-MM-DD): {fecha!r}")


# Registro de operaciones

    def registrar_compra_accion(
        self,
        simbolo: str,
        cantidad: float,
        precio_unitario: float,
        comision: float,
        fecha: Optional[str] = None,
        moneda: str = "COP",
        trm: float = 1.0,
    ) -> dict:
        """Registra una compra de acción; valida y actualiza posición."""
        simbolo = simbolo.upper().strip()
        cantidad = self._validar_positivo(cantidad, "cantidad")
        precio_unitario = self._validar_positivo(precio_unitario, "precio_unitario")
        comision = self._validar_no_negativo(comision, "comision")
        trm = self._validar_positivo(trm, "trm")
        fecha = self._validar_fecha(fecha or datetime.now().strftime("%Y-%m-%d"))

        # El costo total incluye comisión y conversión a COP.
        costo_total = cantidad * precio_unitario * trm + comision
        if costo_total > self.datos["saldo"]:
            raise ValueError(
                f"Saldo insuficiente: requiere {costo_total:.2f}, disponible {self.datos['saldo']:.2f}"
            )

        pos = self.datos["acciones"].setdefault(
            simbolo,
            {
                "simbolo": simbolo,
                "nombre": NOMBRES_ACCIONES.get(simbolo, simbolo),
                "bolsa": BOLSAS_ACCIONES.get(simbolo, "DESCONOCIDA"),
                "cantidad": 0.0,
                "costo_total_cop": 0.0,
                "precio_promedio_cop": 0.0,
                "moneda_original": moneda.upper(),
            },
        )

        # Costo promedio ponderado para soportar compras sucesivas.
        nueva_cant = pos["cantidad"] + cantidad
        nuevo_costo = pos["costo_total_cop"] + costo_total
        pos["cantidad"] = nueva_cant
        pos["costo_total_cop"] = nuevo_costo
        pos["precio_promedio_cop"] = nuevo_costo / nueva_cant if nueva_cant else 0.0

        self.datos["saldo"] -= costo_total
        self.datos["movimientos"].append(
            {
                "tipo": "COMPRA_ACCION",
                "detalle": f"Compra {cantidad:g} x {simbolo}",
                "fecha": fecha,
                "simbolo": simbolo,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "moneda": moneda.upper(),
                "trm": trm,
                "comision": comision,
                "total_cop": costo_total,
                "monto": -costo_total,
            }
        )
        return pos

    def registrar_venta_accion(
        self,
        simbolo: str,
        cantidad: float,
        precio_unitario: float,
        comision: float,
        fecha: Optional[str] = None,
        moneda: str = "COP",
        trm: float = 1.0,
    ) -> dict:
        """Registra venta; valida que exista posición suficiente."""
        simbolo = simbolo.upper().strip()
        cantidad = self._validar_positivo(cantidad, "cantidad")
        precio_unitario = self._validar_positivo(precio_unitario, "precio_unitario")
        comision = self._validar_no_negativo(comision, "comision")
        trm = self._validar_positivo(trm, "trm")
        fecha = self._validar_fecha(fecha or datetime.now().strftime("%Y-%m-%d"))

        pos = self.datos["acciones"].get(simbolo)
        if not pos:
            raise ValueError(f"No hay posición abierta en {simbolo}")
        if cantidad > pos["cantidad"]:
            raise ValueError(
                f"Cantidad a vender ({cantidad}) excede posición ({pos['cantidad']})"
            )

        ingreso_bruto = cantidad * precio_unitario * trm
        ingreso_neto = ingreso_bruto - comision
        if ingreso_neto < 0:
            raise ValueError("La comisión supera el ingreso de la venta")

        # La posición se reduce al costo promedio, no al precio de venta.
        costo_promedio = pos["precio_promedio_cop"]
        pos["cantidad"] -= cantidad
        pos["costo_total_cop"] -= cantidad * costo_promedio
        if pos["cantidad"] <= 0:
            self.datos["acciones"].pop(simbolo)

        self.datos["saldo"] += ingreso_neto
        self.datos["movimientos"].append(
            {
                "tipo": "VENTA_ACCION",
                "detalle": f"Venta {cantidad:g} x {simbolo}",
                "fecha": fecha,
                "simbolo": simbolo,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "moneda": moneda.upper(),
                "trm": trm,
                "comision": comision,
                "total_cop": ingreso_neto,
                "monto": ingreso_neto,
                "costo_promedio_cop": costo_promedio,
                "utilidad_cop": (precio_unitario * trm - costo_promedio) * cantidad - comision,
            }
        )
        return pos

    def registrar_cdt(
        self,
        monto: float,
        tasa_ea: float,
        plazo_dias: int,
        fecha_inicio: Optional[str] = None,
        entidad: str = "",
    ) -> dict:
        """Registra un CDT con interés compuesto base 360."""
        monto = self._validar_positivo(monto, "monto")
        tasa_ea = self._validar_positivo(tasa_ea, "tasa_ea")
        if not isinstance(plazo_dias, int) or plazo_dias <= 0:
            raise ValueError("plazo_dias debe ser entero > 0")
        if monto > self.datos["saldo"]:
            raise ValueError(f"Saldo insuficiente para CDT: {monto}")

        fecha_inicio = self._validar_fecha(
            fecha_inicio or datetime.now().strftime("%Y-%m-%d")
        )
        cdt = {
            "id": f"CDT-{len(self.datos['cdts']) + 1:04d}",
            "entidad": entidad,
            "monto": monto,
            "tasa_ea": tasa_ea,
            "plazo_dias": plazo_dias,
            "fecha_inicio": fecha_inicio,
            "vence": (datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
                      + timedelta(days=plazo_dias)).isoformat(),
            "final": round(monto * (1 + tasa_ea / 100) ** (plazo_dias / 360), 2),
            "estado": "ACTIVO",
        }
        self.datos["cdts"].append(cdt)
        self.datos["saldo"] -= monto
        self.datos["movimientos"].append(
            {
                "tipo": "APERTURA_CDT",
                "detalle": f"Apertura CDT {plazo_dias} días al {tasa_ea:g}% EA",
                "fecha": fecha_inicio,
                "id_cdt": cdt["id"],
                "monto": -monto,
                "tasa_ea": tasa_ea,
                "plazo_dias": plazo_dias,
            }
        )
        return cdt

    def registrar_dividendo(
        self,
        simbolo: str,
        monto_por_accion: float,
        fecha: Optional[str] = None,
        retencion_pct: float = 0.0,
    ) -> dict:
        """Registra dividendo sobre la posición actual; aplica retención."""
        simbolo = simbolo.upper().strip()
        monto_por_accion = self._validar_positivo(monto_por_accion, "monto_por_accion")
        retencion_pct = self._validar_no_negativo(retencion_pct, "retencion_pct")
        if retencion_pct > 100:
            raise ValueError("retencion_pct no puede superar 100")
        fecha = self._validar_fecha(fecha or datetime.now().strftime("%Y-%m-%d"))

        pos = self.datos["acciones"].get(simbolo)
        if not pos or pos["cantidad"] <= 0:
            raise ValueError(f"Sin posición en {simbolo} para recibir dividendo")

        # El dividendo se calcula sobre la cantidad actual y se retiene en fuente.
        bruto = pos["cantidad"] * monto_por_accion
        retencion = bruto * (retencion_pct / 100.0)
        neto = bruto - retencion

        self.datos["saldo"] += neto
        div = {
            "fecha": fecha,
            "simbolo": simbolo,
            "cantidad": pos["cantidad"],
            "monto_bruto": bruto,
            "retencion": retencion,
            "monto_neto": neto,
        }
        self.datos["dividendos"].append(div)
        self.datos["movimientos"].append(
            {
                "tipo": "DIVIDENDO",
                "detalle": f"Dividendo {simbolo}",
                "fecha": fecha,
                "simbolo": simbolo,
                "cantidad": pos["cantidad"],
                "monto": neto,
                "monto_bruto": bruto,
                "retencion": retencion,
                "monto_neto": neto,
            }
        )
        return div

    def registrar_bono(
        self,
        nombre: str,
        monto: float,
        tasa_anual: float,
        plazo_meses: int,
        fecha_inicio: Optional[str] = None,
    ) -> dict:
        """Registra un bono corporativo con cupón anual."""
        monto = self._validar_positivo(monto, "monto")
        tasa_anual = self._validar_positivo(tasa_anual, "tasa_anual")
        if not isinstance(plazo_meses, int) or plazo_meses <= 0:
            raise ValueError("plazo_meses debe ser entero > 0")
        if monto > self.datos["saldo"]:
            raise ValueError(f"Saldo insuficiente para bono: {monto}")

        fecha_inicio = self._validar_fecha(
            fecha_inicio or datetime.now().strftime("%Y-%m-%d")
        )
        bono = {
            "id": f"BONO-{len(self.datos['bonos']) + 1:04d}",
            "nombre": nombre or "Bono Corp",
            "monto": monto,
            "tasa": tasa_anual,
            "plazo": plazo_meses,
            "fecha_inicio": fecha_inicio,
            "vence": (datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
                      + timedelta(days=30 * plazo_meses)).isoformat(),
            "final": round(monto * (1 + tasa_anual / 100 * plazo_meses / 12), 2),
        }
        self.datos["bonos"].append(bono)
        self.datos["saldo"] -= monto
        self.datos["movimientos"].append(
            {
                "tipo": "COMPRA_BONO",
                "detalle": f"Compra {bono['nombre']}",
                "fecha": fecha_inicio,
                "id_bono": bono["id"],
                "monto": -monto,
                "tasa": tasa_anual,
                "plazo": plazo_meses,
            }
        )
        return bono

    def registrar_tes(
        self,
        tipo: str,
        monto: float,
        cupon_anual: float,
        plazo_anios: int,
        fecha_inicio: Optional[str] = None,
    ) -> dict:
        """Registra un TES con cupón anual."""
        monto = self._validar_positivo(monto, "monto")
        cupon_anual = self._validar_positivo(cupon_anual, "cupon_anual")
        if not isinstance(plazo_anios, int) or plazo_anios <= 0:
            raise ValueError("plazo_anios debe ser entero > 0")
        if monto > self.datos["saldo"]:
            raise ValueError(f"Saldo insuficiente para TES: {monto}")

        fecha_inicio = self._validar_fecha(
            fecha_inicio or datetime.now().strftime("%Y-%m-%d")
        )
        tes = {
            "id": f"TES-{len(self.datos['tes']) + 1:04d}",
            "tipo": tipo or "TES Tasa Fija",
            "monto": monto,
            "tasa": cupon_anual,
            "plazo_anios": plazo_anios,
            "emision": fecha_inicio,
            "vence": (datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
                      + timedelta(days=int(plazo_anios * 365))).isoformat(),
        }
        self.datos["tes"].append(tes)
        self.datos["saldo"] -= monto
        self.datos["movimientos"].append(
            {
                "tipo": "COMPRA_TES",
                "detalle": f"Compra {tes['tipo']} al {cupon_anual:g}%",
                "fecha": fecha_inicio,
                "id_tes": tes["id"],
                "monto": -monto,
                "tasa": cupon_anual,
                "plazo_anios": plazo_anios,
            }
        )
        return tes


# Consultas

    def listar_posiciones(self) -> list[dict]:
        """Retorna lista de posiciones abiertas en acciones."""
        return list(self.datos["acciones"].values())

    def total_invertido_cop(self) -> float:
        """Suma de costo total de posiciones + CDT + bonos + TES."""
        total = sum(p["costo_total_cop"] for p in self.datos["acciones"].values())
        total += sum(c["monto"] for c in self.datos["cdts"] if c.get("estado") == "ACTIVO")
        total += sum(b.get("monto", 0) for b in self.datos["bonos"])
        total += sum(t.get("monto", 0) for t in self.datos["tes"])
        return total