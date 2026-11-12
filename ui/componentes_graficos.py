"""
componentes_graficos.py - Paletas de color y estilos visuales de la interfaz.
"""

# Paleta oscura (por defecto)
PALETA_OSCURA = {
    "BG_APP": "#0F172A",
    "BG_CARD": "#1E293B",
    "BG_HEADER": "#090D16",
    "BORDE_SUTIL": "#334155",
    "TEXTO_PRINCIPAL": "#F8FAFC",
    "TEXTO_MUTED": "#94A3B8",
    "ACCESO_AZUL": "#38BDF8",
    "VERDE_EXITO": "#10B981",
    "ROJO_ALERTA": "#F43F5E",
    "NARANJA_WARN": "#F59E0B",
    "MORADO_CDT": "#A855F7",
    "TEAL_TES": "#2DD4BF",
    "FILA_PAR": "#1E293B",
    "FILA_IMPAR": "#172033",
    "GANANCIA_FONDO": "#064E3B",
    "GANANCIA_TEXTO": "#34D399",
    "PERDIDA_FONDO": "#7F1D1D",
    "PERDIDA_TEXTO": "#FCA5A5",
    "BTN_TEXTO": "#0F172A",
    "COLORES_DIVISAS": [
        "#38BDF8", "#A855F7", "#F59E0B", "#F43F5E",
        "#2DD4BF", "#10B981", "#38BDF8", "#F43F5E", "#94A3B8",
    ],
}

# Paleta clara
PALETA_CLARA = {
    "BG_APP": "#F4F7F6",
    "BG_CARD": "#FFFFFF",
    "BG_HEADER": "#0A2540",
    "BORDE_SUTIL": "#D1D5DB",
    "TEXTO_PRINCIPAL": "#1E293B",
    "TEXTO_MUTED": "#64748B",
    "ACCESO_AZUL": "#0284C7",
    "VERDE_EXITO": "#059669",
    "ROJO_ALERTA": "#DC2626",
    "NARANJA_WARN": "#D97706",
    "MORADO_CDT": "#7C3AED",
    "TEAL_TES": "#0891B2",
    "FILA_PAR": "#FFFFFF",
    "FILA_IMPAR": "#F1F5F9",
    "GANANCIA_FONDO": "#D1FAE5",
    "GANANCIA_TEXTO": "#065F46",
    "PERDIDA_FONDO": "#FEE2E2",
    "PERDIDA_TEXTO": "#991B1B",
    "BTN_TEXTO": "#FFFFFF",
    "COLORES_DIVISAS": [
        "#0284C7", "#7C3AED", "#D97706", "#DC2626",
        "#0891B2", "#059669", "#0284C7", "#DC2626", "#64748B",
    ],
}


def obtener_paleta(nombre: str = "oscura") -> dict:
    """Retorna la paleta según el modo activo."""
    return PALETA_CLARA if nombre == "clara" else PALETA_OSCURA


# Compatibilidad: constantes de la paleta oscura expuestas para imports existentes
_p = PALETA_OSCURA
BG_APP = _p["BG_APP"]
BG_CARD = _p["BG_CARD"]
BG_HEADER = _p["BG_HEADER"]
BORDE_SUTIL = _p["BORDE_SUTIL"]
TEXTO_PRINCIPAL = _p["TEXTO_PRINCIPAL"]
TEXTO_MUTED = _p["TEXTO_MUTED"]
ACCESO_AZUL = _p["ACCESO_AZUL"]
VERDE_EXITO = _p["VERDE_EXITO"]
ROJO_ALERTA = _p["ROJO_ALERTA"]
NARANJA_WARN = _p["NARANJA_WARN"]
MORADO_CDT = _p["MORADO_CDT"]
TEAL_TES = _p["TEAL_TES"]
COLORES_DIVISAS = _p["COLORES_DIVISAS"]
COLOR_GANANCIA_FONDO = _p["GANANCIA_FONDO"]
COLOR_GANANCIA_TEXTO = _p["GANANCIA_TEXTO"]
COLOR_PERDIDA_FONDO = _p["PERDIDA_FONDO"]
COLOR_PERDIDA_TEXTO = _p["PERDIDA_TEXTO"]