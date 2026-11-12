"""
cliente_api.py - Consultas a yfinance y open.er-api con soporte multidivisa,
TRM histórica aproximada, dividendos y metadatos de bolsa.
"""
from __future__ import annotations

import logging
import time
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
import yfinance as yf

logger = logging.getLogger(__name__)


# Estructuras de datos

@dataclass
class Cotizacion:
    """Resultado unificado de una acción/ETF consultada."""
    simbolo: str
    precio_original: float
    moneda_original: str
    precio_cop: float
    bolsa: str
    serie_cop: list[tuple[datetime, float]] = field(default_factory=list)
    dividendos: list[tuple[datetime, float]] = field(default_factory=list)
    # True cuando la serie en COP se armó con una sola tasa spot (no histórica).
    es_aproximado: bool = False


# Cliente de mercado

class ClienteAPI:
    """Cliente para tasas de cambio, cotizaciones, dividendos y bolsas."""

    # TTL de cada cache: evita pegarle a las APIs en cada consulta.
    _TTL_SPOT = 60 * 15
    _TTL_HIST = 60 * 60 * 6
    _TTL_COT = 60 * 5
    # (connect, read): falla rápido si el host no responde.
    _TIMEOUT = (3, 10)
    _URL_ER = "https://open.er-api.com/v6/latest/USD"

    def __init__(self) -> None:
        self._cache_tasas_usd: Optional[dict[str, float]] = None
        self._cache_tasas_ts: float = 0.0
        self._cache_fx_hist: dict[str, tuple[list[datetime], list[float], float]] = {}
        self._cache_cotizaciones: dict[str, tuple[Cotizacion, float]] = {}


# Tasas spot

    def _refrescar_tasas_usd(self) -> None:
        """Refresca tasas base USD con TTL. No lanza si falla: conserva cache."""
        if self._cache_tasas_usd and (time.time() - self._cache_tasas_ts) < self._TTL_SPOT:
            return
        try:
            r = requests.get(self._URL_ER, timeout=self._TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("result") != "success":
                raise ValueError(f"ER-API: {data.get('error-type')}")
            self._cache_tasas_usd = {k: float(v) for k, v in data["rates"].items() if v}
            self._cache_tasas_ts = time.time()
            logger.info("Tasas spot refrescadas (%d pares)", len(self._cache_tasas_usd))
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error("Fallo al refrescar tasas USD: %s", e)
            # Si ya había cache previo, se sigue usando; si no, no hay de dónde.
            if not self._cache_tasas_usd:
                raise RuntimeError(f"Sin tasas disponibles: {e}") from e

    def obtener_tasas_usd(self) -> dict[str, float]:
        """Retorna dict {MONEDA: unidades por 1 USD} (ej: {'COP': 4000})."""
        self._refrescar_tasas_usd()
        return dict(self._cache_tasas_usd or {})

    def obtener_tasas_cop(self) -> dict[str, float]:
        """Retorna dict {MONEDA: COP por 1 unidad de MONEDA} (ej: {'EUR': 4348})."""
        tasas = self.obtener_tasas_usd()
        cop = tasas.get("COP")
        if not cop:
            raise RuntimeError("ER-API no devolvió COP")
        return {m: cop / v for m, v in tasas.items() if v and m != "COP"}


# TRM y FX histórico

    def _serie_fx(self, par: str = "COP=X", rango: str = "1y") -> tuple[list[datetime], list[float]]:
        """
        Serie FX ascendente (fechas, valores).
        OJO: 'COP=X' de Yahoo ≈ USD/COP interbancario, NO es TRM oficial Superfinanciera.
        Para auditoría estricta usar BanRep. Documentar en README.
        """
        clave = f"{par}|{rango}"
        cache = self._cache_fx_hist.get(clave)
        if cache and (time.time() - cache[2]) < self._TTL_HIST:
            return cache[0], cache[1]

        try:
            hist = yf.Ticker(par).history(period=rango, interval="1d")
            if hist is None or hist.empty:
                raise ValueError(f"Sin datos FX para {par}")
            pares = []
            for fecha, cierre in hist["Close"].dropna().items():
                if getattr(fecha, "tzinfo", None) is not None:
                    fecha = fecha.tz_localize(None)
                pares.append((fecha.to_pydatetime(), float(cierre)))
            pares.sort(key=lambda x: x[0])
            fechas = [p[0] for p in pares]
            valores = [p[1] for p in pares]
            self._cache_fx_hist[clave] = (fechas, valores, time.time())
            return fechas, valores
        except (ValueError, KeyError) as e:
            logger.warning("FX histórico %s falló: %s", par, e)
            return [], []

    def obtener_trm(self, fecha: Optional[datetime] = None) -> float:
        """
        TRM aproximada. Si `fecha` es None → última disponible.
        Si no hay serie → fallback a spot ER-API.
        """
        fechas, valores = self._serie_fx(rango="5d")
        if fecha is not None and fechas:
            # Se busca la tasa vigente en la fecha pedida.
            fechas_ord, valores_ord = self._serie_fx(rango="1y")
            i = bisect_right(fechas_ord, fecha) - 1
            if i >= 0:
                return valores_ord[i]
        if valores:
            return valores[-1]
        # Sin serie de Yahoo, se recurre a la spot de ER-API.
        return float(self.obtener_tasas_usd().get("COP", 4000.0))

    def _fx_historico_alineado(
        self, fechas: list[datetime], par: str
    ) -> Optional[list[float]]:
        """Para cada fecha, devuelve la tasa FX vigente (último cierre ≤ fecha)."""
        fx_fechas, fx_vals = self._serie_fx(par)
        if not fx_fechas:
            return None
        out = []
        for f in fechas:
            # Feriados: se usa el último cierre hábil anterior.
            i = bisect_right(fx_fechas, f) - 1
            out.append(fx_vals[i] if i >= 0 else fx_vals[0])
        return out


# Cotizaciones de acciones

    def consultar_accion(self, simbolo: str, rango: str = "1y") -> Cotizacion:
        """
        Devuelve Cotizacion con precio en COP, serie histórica en COP,
        dividendos (en moneda original) y bolsa de listado.
        """
        simbolo = simbolo.upper().strip()
        clave = f"{simbolo}|{rango}"
        cache = self._cache_cotizaciones.get(clave)
        if cache and (time.time() - cache[1]) < self._TTL_COT:
            return cache[0]

        ticker = yf.Ticker(simbolo)
        hist = ticker.history(period=rango, interval="1d")
        if hist is None or hist.empty:
            raise ValueError(f"Símbolo sin datos: {simbolo}")

        serie = []
        for fecha, cierre in hist["Close"].dropna().items():
            if getattr(fecha, "tzinfo", None) is not None:
                fecha = fecha.tz_localize(None)
            serie.append((fecha.to_pydatetime(), float(cierre)))
        serie.sort(key=lambda x: x[0])
        if not serie:
            raise ValueError(f"Sin precios válidos para {simbolo}")

        # fast_info puede no traer todos los campos; se cae a defaults seguros.
        moneda = "USD"
        bolsa = "DESCONOCIDA"
        try:
            info = ticker.fast_info
            moneda = str(info.get("currency") or "USD").upper()
            bolsa = str(info.get("exchange") or "DESCONOCIDA").upper()
        except (AttributeError, KeyError, TypeError):
            pass

        precio_actual = serie[-1][1]
        try:
            ultimo = float(ticker.fast_info.get("last_price") or 0)
            if ultimo > 0:
                precio_actual = ultimo
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

        dividendos: list[tuple[datetime, float]] = []
        try:
            divs = ticker.dividends
            if divs is not None and not divs.empty:
                for fecha, val in divs.items():
                    if getattr(fecha, "tzinfo", None) is not None:
                        fecha = fecha.tz_localize(None)
                    dividendos.append((fecha.to_pydatetime(), float(val)))
                dividendos.sort(key=lambda x: x[0])
        except (AttributeError, KeyError, TypeError):
            pass

        # Conversión a COP según la moneda de origen del activo.
        es_aproximado = False
        fechas = [f for f, _ in serie]
        precios = [c for _, c in serie]

        if moneda == "COP":
            serie_cop = list(serie)
            precio_cop = precio_actual

        elif moneda == "USD":
            fx = self._fx_historico_alineado(fechas, "COP=X")
            if fx:
                # Serie punto a punto con la tasa vigente de cada día.
                serie_cop = [(f, p * t) for f, p, t in zip(fechas, precios, fx)]
                precio_cop = precio_actual * self.obtener_trm()
            else:
                # Sin serie FX: se usa una sola tasa y se marca la cotización.
                trm = self.obtener_trm()
                serie_cop = [(f, p * trm) for f, p in serie]
                precio_cop = precio_actual * trm
                es_aproximado = True

        else:
            # Otras monedas: conversión cruzada vía USD con tasa spot única.
            tasas = self.obtener_tasas_usd()
            cop_por_usd = tasas.get("COP")
            usd_por_moneda = tasas.get(moneda)
            if not cop_por_usd or not usd_por_moneda:
                raise ValueError(f"Moneda no soportada por ER-API: {moneda}")
            factor = cop_por_usd / usd_por_moneda
            serie_cop = [(f, p * factor) for f, p in serie]
            precio_cop = precio_actual * factor
            es_aproximado = True
            logger.warning(
                "Serie %s convertida con tasa spot única (moneda %s); "
                "no refleja variación cambiaria histórica.", simbolo, moneda
            )

        resultado = Cotizacion(
            simbolo=simbolo,
            precio_original=precio_actual,
            moneda_original=moneda,
            precio_cop=precio_cop,
            bolsa=bolsa,
            serie_cop=serie_cop,
            dividendos=dividendos,
            es_aproximado=es_aproximado,
        )
        self._cache_cotizaciones[clave] = (resultado, time.time())
        return resultado


# Conversión entre divisas

    def convertir(
        self,
        monto: float,
        desde: str,
        hacia: str,
        fecha: Optional[datetime] = None,
        spread_bps: float = 0.0,
    ) -> float:
        """
        Convierte monto entre divisas usando USD como pivote.
        `spread_bps` = costo operativo en puntos base (25 = 0.25%).
        """
        desde, hacia = desde.upper(), hacia.upper()
        if desde == hacia:
            return monto

        if fecha is None:
            tasas = self.obtener_tasas_usd()
            t_desde = tasas.get(desde)
            t_hacia = tasas.get(hacia)
            if not t_desde or not t_hacia:
                raise ValueError(f"Par no soportado: {desde}/{hacia}")
        else:
            # Conversión histórica solo soportada cuando un lado es COP.
            t_desde = self.obtener_trm(fecha) if desde == "COP" else None
            t_hacia = self.obtener_trm(fecha) if hacia == "COP" else None
            if t_desde is None or t_hacia is None:
                raise NotImplementedError(
                    "Conversión histórica fuera de COP aún no soportada."
                )

        usd = monto / t_desde
        resultado = usd * t_hacia
        if spread_bps:
            # Se descuenta el costo de la operación sobre el resultado final.
            resultado *= 1 - (spread_bps / 10_000)
        return resultado


# Prueba rápida de humo

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    api = ClienteAPI()

    print(f"TRM aprox: {api.obtener_trm():,.2f} COP/USD")
    for sym in ("NKE", "KO", "AAPL"):
        c = api.consultar_accion(sym, rango="6mo")
        print(
            f"{sym} [{c.bolsa}] {c.precio_original:.2f} {c.moneda_original} "
            f"→ {c.precio_cop:,.0f} COP | divs: {len(c.dividendos)} | aprox: {c.es_aproximado}"
        )