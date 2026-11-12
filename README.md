# Terminal Financiera Profesional de Portafolio

Aplicación de escritorio en Python para el seguimiento, monitorización y auditoría de portafolios de inversión multiactivos con conversión automática a pesos colombianos (COP).

![Terminal Financiera Pro](docs/capturas/resumen.png)

## Descripción

Sistema académico que permite registrar y evaluar el desempeño de un portafolio compuesto por renta fija y renta variable:

- **Renta variable:** acciones internacionales y colombianas listadas en NYSE y NASDAQ (Coca-Cola, Nike, Apple, Microsoft, Ecopetrol, Bancolombia, entre otras), con conversión a COP usando TRM histórica.
- **Renta fija:** Certificados de Depósito a Término (CDT), bonos corporativos y Títulos de Deuda Pública (TES).
- **Ingresos:** dividendos con retención en la fuente del 4% para acciones, intereses de CDT con retención del 7% para rendimientos financieros.
- **Costos:** comisiones del bróker descontadas del resultado financiero.
- **Valoración:** precios de mercado en tiempo real con `yfinance` y tasas de cambio con `open.er-api`.
- **Auditoría:** cálculo de rentabilidad acumulada y rentabilidad efectiva anual (E.A.) por activo y consolidada.

## Funcionalidades

| Módulo | Descripción |
|--------|-------------|
| Resumen | Tarjetas con el patrimonio total y gráfica de composición del portafolio. |
| Cuenta | Depósitos y retiros de efectivo en COP. |
| CDT | Apertura con tasa E.A., plazo y liquidación con interés compuesto base 360. |
| Bonos | Compra y redención con cupón anual. |
| TES | Adquisición y redención con cupón anual. |
| Acciones | Consulta de precios en vivo, compra y venta con comisión de bróker, gráfico histórico en COP. |
| Dividendos | Registro con retención del 4%. |
| Divisas | Conversión multidivisa con tasas en tiempo real. |
| Rendimiento | Rentabilidad acumulada, rentabilidad E.A. por activo y consolidada. |
| Simulación | Simulador histórico de inversión en acciones. |
| Movimientos | Historial completo de operaciones. |

## Arquitectura
