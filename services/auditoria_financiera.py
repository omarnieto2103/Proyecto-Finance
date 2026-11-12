"""
auditoria_financiera.py - Cálculos de rentabilidad, valoración y formato.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

logger = logging.getLogger(__name__)

# Retenciones vigentes en Colombia: 4% para dividendos de acciones,
# 7% para rendimientos financieros (CDT, bonos, TES).
RETENCION_DIVIDENDOS_PCT = 4.0
RETENCION_RENDIMIENTOS_PCT = 7.0

# Los CDT en Colombia liquidan interés con base 360 días.
BASE_CDT_DIAS = 360

# Precisión de centavos para redondeo monetario.
_CENT = Decimal("0.01")


# Parseo y formato

def leer_numero(texto, nombre: str = "Valor", permitir_cero: bool = False) -> float:
    """Parsea número en formato colombiano (1.234,56) o anglosajón (1,234.56)."""
    t = str(texto).strip().replace("$", "").replace(" ", "")
    if not t:
        raise ValueError(f"{nombre} no puede estar vacío.")
    # Si hay ambos separadores, el último en aparecer es el decimal.
    if "." in t and "," in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    # Solo coma: puede ser decimal (1,5) o miles (1,500,000).
    elif "," in t:
        t = t.replace(",", ".") if t.count(",") == 1 else t.replace(",", "")
    # Solo punto con patrón de miles colombiano: 1.234.567
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        n = float(t)
    except ValueError:
        raise ValueError(f"{nombre} debe ser un número válido.")
    if math.isnan(n) or math.isinf(n):
        raise ValueError(f"{nombre} no puede ser NaN ni infinito.")
    if n < 0 or (n == 0 and not permitir_cero):
        raise ValueError(f"{nombre} debe ser mayor que cero.")
    return n


def _dec(x: float) -> Decimal:
    """Cuantiza un float a centavos con redondeo bancario."""
    return Decimal(str(x)).quantize(_CENT, rounding=ROUND_HALF_UP)


def num(x, dec: int = 2) -> str:
    """Formatea número con separador de miles '.' y decimal ','."""
    if x is None:
        return "-"
    x = round(float(x), dec)
    if x == 0:
        x = 0.0
    s = f"{abs(x):,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{s}" if x < 0 else s


def moneda(x) -> str:
    """Formatea un valor como pesos colombianos."""
    if x is None:
        return "$ -"
    s = num(x)
    return f"-$ {s[1:]}" if s.startswith("-") else f"$ {s}"


def pct(x, signo: bool = True, dec: int = 2) -> str:
    """Formatea un porcentaje con signo opcional."""
    if x is None:
        return "-"
    s = num(x, dec)
    if signo and x > 0 and not s.startswith("-"):
        s = "+" + s
    return f"{s}%"


# Valoración de instrumentos

def valor_cdt(
    monto: float,
    tasa_ea: float,
    dias_transcurridos: int,
    base_dias: int = BASE_CDT_DIAS,
) -> dict:
    """Valor presente de un CDT con interés compuesto y retención."""
    if monto <= 0 or tasa_ea <= 0:
        raise ValueError("monto y tasa_ea deben ser positivos")
    if dias_transcurridos < 0:
        raise ValueError("dias_transcurridos no puede ser negativo")

    # TEA -> tasa periódica equivalente para la base de días.
    factor = (1 + tasa_ea / 100.0) ** (dias_transcurridos / base_dias) - 1
    interes_bruto = monto * factor
    retencion = interes_bruto * (RETENCION_RENDIMIENTOS_PCT / 100.0)
    interes_neto = interes_bruto - retencion

    return {
        "monto_inicial": monto,
        "dias_transcurridos": dias_transcurridos,
        "interes_bruto": interes_bruto,
        "retencion": retencion,
        "interes_neto": interes_neto,
        "valor_actual": monto + interes_neto,
    }


def valor_bono_cupon(
    valor_nominal: float,
    tasa_cupon_ea: float,
    dias_desde_ultimo_cupon: int,
    base_dias: int = BASE_CDT_DIAS,
) -> dict:
    """Interés causado de un bono entre cupones."""
    if valor_nominal <= 0 or tasa_cupon_ea <= 0:
        raise ValueError("valor_nominal y tasa_cupon_ea deben ser positivos")
    factor = (1 + tasa_cupon_ea / 100.0) ** (dias_desde_ultimo_cupon / base_dias) - 1
    bruto = valor_nominal * factor
    retencion = bruto * (RETENCION_RENDIMIENTOS_PCT / 100.0)
    return {
        "interes_bruto": bruto,
        "retencion": retencion,
        "interes_neto": bruto - retencion,
    }


# Rentabilidad

def _dias_entre(f1: date, f2: date) -> int:
    """Días calendario entre dos fechas."""
    if f2 < f1:
        raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
    return (f2 - f1).days


def rentabilidad_acumulada(
    valor_invertido: float,
    valor_actual: float,
    ingresos: float = 0.0,
    costos: float = 0.0,
) -> float:
    """Rentabilidad acumulada del período en porcentaje."""
    if valor_invertido <= 0:
        raise ValueError("valor_invertido debe ser > 0")
    # Fórmula: (valor_actual + ingresos - costos - invertido) / invertido * 100.
    return ((valor_actual + ingresos - costos - valor_invertido) / valor_invertido) * 100.0


def rentabilidad_ea(
    rentabilidad_acum_pct: float,
    dias: int,
    base_dias: int = 365,
) -> float:
    """Convierte rentabilidad acumulada a efectiva anual."""
    if dias <= 0:
        raise ValueError("días debe ser > 0")
    # Fórmula: ((1 + r)^(base/días) - 1) * 100.
    factor = (1 + rentabilidad_acum_pct / 100.0) ** (base_dias / dias) - 1
    return factor * 100.0


# Auditoría por posición

@dataclass
class FilaAuditoria:
    """Fila de la tabla de auditoría."""
    activo: str
    tipo: str
    invertido_cop: float
    valor_actual_cop: float
    ingresos_cop: float = 0.0
    costos_cop: float = 0.0
    rent_acum_pct: float = 0.0
    dias: int = 0
    rent_ea_pct: float = 0.0
    observacion: str = ""


def auditar_posicion_accion(
    simbolo: str,
    posicion: dict,
    precio_actual_cop: float,
    dividendos_cop: float,
    dias_tenencia: int,
    es_aproximado: bool = False,
) -> FilaAuditoria:
    """Calcula P&L y rentabilidades de una posición de acción."""
    invertido = posicion["costo_total_cop"]
    valor_actual = posicion["cantidad"] * precio_actual_cop
    rent_acum = rentabilidad_acumulada(invertido, valor_actual, ingresos=dividendos_cop)
    rent_ea = rentabilidad_ea(rent_acum, dias_tenencia) if dias_tenencia > 0 else 0.0

    obs = "Serie FX aproximada" if es_aproximado else ""
    return FilaAuditoria(
        activo=simbolo,
        tipo="Acción",
        invertido_cop=invertido,
        valor_actual_cop=valor_actual,
        ingresos_cop=dividendos_cop,
        costos_cop=0.0,
        rent_acum_pct=rent_acum,
        dias=dias_tenencia,
        rent_ea_pct=rent_ea,
        observacion=obs,
    )


def auditar_cdt(cdt: dict, fecha_corte: Optional[date] = None) -> FilaAuditoria:
    """Auditoría de un CDT a la fecha de corte."""
    fecha_corte = fecha_corte or date.today()
    fecha_inicio = datetime.strptime(cdt["fecha_inicio"], "%Y-%m-%d").date()
    dias = _dias_entre(fecha_inicio, fecha_corte)

    valor = valor_cdt(cdt["monto"], cdt["tasa_ea"], dias)
    rent_acum = rentabilidad_acumulada(cdt["monto"], valor["valor_actual"])
    rent_ea = rentabilidad_ea(rent_acum, dias) if dias > 0 else 0.0

    return FilaAuditoria(
        activo=cdt.get("id", "CDT"),
        tipo="CDT",
        invertido_cop=cdt["monto"],
        valor_actual_cop=valor["valor_actual"],
        ingresos_cop=valor["interes_neto"],
        costos_cop=valor["retencion"],
        rent_acum_pct=rent_acum,
        dias=dias,
        rent_ea_pct=rent_ea,
    )


# Consolidado

@dataclass
class ResumenPortafolio:
    """Resultado global del portafolio."""
    total_invertido: float = 0.0
    valor_actual: float = 0.0
    ingresos_totales: float = 0.0
    costos_totales: float = 0.0
    rent_acum_pct: float = 0.0
    rent_ea_pct: float = 0.0
    peso_renta_fija: float = 0.0
    peso_renta_variable: float = 0.0
    filas: list[FilaAuditoria] = field(default_factory=list)


def consolidar_portafolio(
    filas: list[FilaAuditoria],
    dias_portafolio: int,
) -> ResumenPortafolio:
    """Agrega filas y calcula rentabilidad global del portafolio."""
    if not filas:
        return ResumenPortafolio()

    inv = sum(f.invertido_cop for f in filas)
    act = sum(f.valor_actual_cop for f in filas)
    ing = sum(f.ingresos_cop for f in filas)
    cos = sum(f.costos_cop for f in filas)

    # Renta fija incluye CDT, bonos y TES; renta variable son acciones.
    rf = sum(f.invertido_cop for f in filas if f.tipo in ("CDT", "Bono", "TES"))
    rv = sum(f.invertido_cop for f in filas if f.tipo == "Acción")

    rent_acum = rentabilidad_acumulada(inv, act, ing, cos) if inv > 0 else 0.0
    rent_ea = rentabilidad_ea(rent_acum, dias_portafolio) if dias_portafolio > 0 else 0.0

    return ResumenPortafolio(
        total_invertido=inv,
        valor_actual=act,
        ingresos_totales=ing,
        costos_totales=cos,
        rent_acum_pct=rent_acum,
        rent_ea_pct=rent_ea,
        peso_renta_fija=(rf / inv * 100.0) if inv > 0 else 0.0,
        peso_renta_variable=(rv / inv * 100.0) if inv > 0 else 0.0,
        filas=filas,
    )


def tabla_auditoria(filas: list[FilaAuditoria]) -> list[list[str]]:
    """Genera tabla lista para mostrar en UI (lista de filas string)."""
    encabezado = [
        "Activo", "Tipo", "Invertido", "Valor actual",
        "Ingresos", "Rent. acum.", "Días", "Rent. E.A.", "Observación",
    ]
    cuerpo = [encabezado]
    for f in filas:
        cuerpo.append([
            f.activo,
            f.tipo,
            moneda(f.invertido_cop),
            moneda(f.valor_actual_cop),
            moneda(f.ingresos_cop),
            pct(f.rent_acum_pct),
            str(f.dias),
            pct(f.rent_ea_pct),
            f.observacion or "-",
        ])
    return cuerpo