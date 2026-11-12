"""
notificaciones.py - Toasts flotantes que se desvanecen.
"""
import tkinter as tk


class Toast:
    """Aviso flotante no modal, esquina superior derecha, autodesvanecido."""

    DURACION_MS = 3000
    PASO_FADE = 40

    def __init__(self, root: tk.Tk, texto: str, tipo: str = "info"):
        self.root = root
        paleta = root.paleta
        colores = {
            "info":    (paleta["ACCESO_AZUL"], paleta["BTN_TEXTO"]),
            "exito":   (paleta["VERDE_EXITO"], paleta["BTN_TEXTO"]),
            "error":   (paleta["ROJO_ALERTA"], "#FFFFFF"),
            "warning": (paleta["NARANJA_WARN"], paleta["BTN_TEXTO"]),
        }
        fondo, texto_color = colores.get(tipo, colores["info"])

        self.ventana = tk.Toplevel(root)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)

        ancho, alto = 340, 60
        x = root.winfo_rootx() + root.winfo_width() - ancho - 30
        y = root.winfo_rooty() + 100
        self.ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.ventana.configure(bg=fondo)

        marco = tk.Frame(self.ventana, bg=fondo, padx=14, pady=10)
        marco.pack(fill="both", expand=True)
        tk.Label(
            marco, text=texto, bg=fondo, fg=texto_color,
            font=("Segoe UI", 10, "bold"), wraplength=ancho - 40,
            justify="left", anchor="w",
        ).pack(fill="both", expand=True)

        self._alpha = 1.0
        self.ventana.attributes("-alpha", self._alpha)
        self.ventana.after(self.DURACION_MS, self._desvanecer)

    def _desvanecer(self):
        self._alpha -= 0.08
        if self._alpha <= 0:
            self.ventana.destroy()
            return
        try:
            self.ventana.attributes("-alpha", self._alpha)
            self.ventana.after(self.PASO_FADE, self._desvanecer)
        except tk.TclError:
            pass