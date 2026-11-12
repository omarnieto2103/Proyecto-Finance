"""
main.py - Punto de entrada de la terminal financiera.
"""
import logging
import sys

from ui.ventana_principal import AppFinanciera


def configurar_logging():
    """Configura logging a consola y archivo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("portafolio.log", encoding="utf-8"),
        ],
    )


def main():
    """Arranca la aplicación capturando errores fatales."""
    configurar_logging()
    logger = logging.getLogger(__name__)
    try:
        app = AppFinanciera()
        app.mainloop()
    except Exception:
        logger.exception("Error fatal al iniciar la aplicación")
        sys.exit(1)


if __name__ == "__main__":
    main()