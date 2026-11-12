"""
accion.py - Modelo de entidad para acciones con trazabilidad de divisa y bolsa.
"""
from dataclasses import dataclass


@dataclass
class Accion:
    """Representa una tenencia de acciones con costo promedio y bolsa de listado."""
    simbolo: str
    nombre: str
    cantidad: float = 0.0
    costo_total_cop: float = 0.0
    precio_promedio_cop: float = 0.0
    moneda_original: str = "USD"
    bolsa: str = "DESCONOCIDA"

    def costo_unitario(self) -> float:
        """Costo promedio por acción en COP."""
        if self.cantidad <= 0:
            return 0.0
        return self.costo_total_cop / self.cantidad

    def valor_mercado(self, precio_cop: float) -> float:
        """Valor de la posición al precio dado."""
        return self.cantidad * precio_cop

    def ganancia(self, precio_cop: float) -> float:
        """Ganancia o pérdida no realizada en COP."""
        return self.valor_mercado(precio_cop) - self.costo_total_cop

    def rentabilidad_pct(self, precio_cop: float) -> float:
        """Rentabilidad sobre costo en porcentaje."""
        if self.costo_total_cop <= 0:
            return 0.0
        return (self.ganancia(precio_cop) / self.costo_total_cop) * 100.0

    def agregar_compra(self, cantidad: float, costo_total_cop: float) -> None:
        """Suma una compra recalculando costo promedio ponderado."""
        if cantidad <= 0:
            raise ValueError("cantidad debe ser > 0")
        nueva_cantidad = self.cantidad + cantidad
        nuevo_costo = self.costo_total_cop + costo_total_cop
        self.cantidad = nueva_cantidad
        self.costo_total_cop = nuevo_costo
        self.precio_promedio_cop = nuevo_costo / nueva_cantidad if nueva_cantidad else 0.0

    def reducir_venta(self, cantidad: float) -> float:
        """Reduce la posición y retorna el costo retirado."""
        if cantidad <= 0 or cantidad > self.cantidad:
            raise ValueError(f"cantidad inválida para venta: {cantidad}")
        costo_retirado = cantidad * self.precio_promedio_cop
        self.cantidad -= cantidad
        self.costo_total_cop -= costo_retirado
        if self.cantidad <= 1e-9:
            self.cantidad = 0.0
            self.costo_total_cop = 0.0
            self.precio_promedio_cop = 0.0
        return costo_retirado

    def a_dict(self) -> dict:
        """Serializa al esquema que persiste el gestor."""
        return {
            "simbolo": self.simbolo,
            "nombre": self.nombre,
            "cantidad": self.cantidad,
            "costo_total_cop": self.costo_total_cop,
            "precio_promedio_cop": self.precio_promedio_cop,
            "moneda_original": self.moneda_original,
            "bolsa": self.bolsa,
        }

    @classmethod
    def desde_dict(cls, datos: dict) -> "Accion":
        """Reconstruye desde un dict guardado por el gestor."""
        return cls(
            simbolo=datos.get("simbolo", ""),
            nombre=datos.get("nombre", datos.get("simbolo", "")),
            cantidad=float(datos.get("cantidad", 0.0)),
            costo_total_cop=float(datos.get("costo_total_cop", datos.get("costo_total", 0.0))),
            precio_promedio_cop=float(datos.get("precio_promedio_cop", 0.0)),
            moneda_original=datos.get("moneda_original", "USD"),
            bolsa=datos.get("bolsa", "DESCONOCIDA"),
        )