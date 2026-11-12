"""
ventana_principal.py - Interfaz financiera interactiva con barra lateral,
tooltips en gráficas, toasts, tema claro/oscuro y badges de tendencia.
"""
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from api.cliente_api import ClienteAPI
from models.accion import Accion
from services.auditoria_financiera import (
    RETENCION_DIVIDENDOS_PCT,
    leer_numero,
    moneda,
    num,
    pct,
    rentabilidad_ea,
)
from services.gestor_portafolio import (
    OPCIONES_ACCIONES,
    GestorPortafolio,
    extraer_simbolo,
    nombre_accion,
)
from ui.componentes_graficos import obtener_paleta
from ui.notificaciones import Toast

TABS = ["Resumen", "Cuenta", "CDT", "Bonos", "TES", "Acciones", "Dividendos", "Divisas", "Rendimiento", "Simulación", "Movimientos"]

DIVISAS = [
    ("USD", "Dólar estadounidense"),
    ("EUR", "Euro"),
    ("GBP", "Libra esterlina"),
    ("CHF", "Franco suizo"),
    ("CAD", "Dólar canadiense"),
    ("MXN", "Peso mexicano"),
    ("BRL", "Real brasileño"),
    ("PEN", "Sol peruano"),
    ("JPY", "Yen japonés"),
]


def cantidad_txt(c):
    """Formatea cantidad sin ceros finales sobrantes."""
    s = num(c, 4)
    return s.rstrip("0").rstrip(",") if "," in s else s


def eje_cop(ax):
    """Aplica formato de moneda al eje Y."""
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 0)))


class AppFinanciera(tk.Tk):
    PERIODOS = {
        "1 mes": "1mo",
        "3 meses": "3mo",
        "6 meses": "6mo",
        "1 año": "1y",
        "2 años": "2y",
        "5 años": "5y",
        "10 años": "10y",
    }

    def __init__(self):
        super().__init__()
        self.title("Terminal Financiera Pro - Fintech Edition")
        self.geometry("1360x860")
        self.minsize(1150, 720)

        self.api = ClienteAPI()
        self.gestor = GestorPortafolio()
        self.valores_mercado = {}
        self.botones_nav = {}
        self.pestana_actual = None
        self.tema = "oscura"
        self.paleta = obtener_paleta(self.tema)

        self.configure(bg=self.paleta["BG_APP"])
        self._estilos()
        self._construir_layout()
        self._ui_todas_pestanas()
        self.cambiar_pestana("Resumen")
        self.refrescar()

    # Tema y estilos

    def _estilos(self):
        p = self.paleta
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=p["BG_APP"], foreground=p["TEXTO_PRINCIPAL"], font=("Segoe UI", 10))
        s.configure("TFrame", background=p["BG_APP"])
        s.configure("TLabel", background=p["BG_APP"], foreground=p["TEXTO_PRINCIPAL"])
        s.configure("TLabelframe", background=p["BG_APP"], bordercolor=p["BORDE_SUTIL"])
        s.configure("TLabelframe.Label", background=p["BG_APP"], foreground=p["ACCESO_AZUL"], font=("Segoe UI", 10, "bold"))
        s.configure("TEntry", fieldbackground=p["BG_CARD"], foreground=p["TEXTO_PRINCIPAL"], bordercolor=p["BORDE_SUTIL"], padding=6)
        s.map("TEntry", fieldbackground=[("focus", p["BG_CARD"]), ("active", p["BG_CARD"])], foreground=[("focus", p["TEXTO_PRINCIPAL"])])
        s.configure("TCombobox", fieldbackground=p["BG_CARD"], foreground=p["TEXTO_PRINCIPAL"], selectbackground=p["BG_CARD"], selectforeground=p["TEXTO_PRINCIPAL"], padding=6)
        s.map("TCombobox", fieldbackground=[("readonly", p["BG_CARD"]), ("active", p["BG_CARD"])], foreground=[("readonly", p["TEXTO_PRINCIPAL"])])

        for nombre, color, hover in [
            ("Accent", p["ACCESO_AZUL"], self._oscurecer(p["ACCESO_AZUL"])),
            ("Success", p["VERDE_EXITO"], self._oscurecer(p["VERDE_EXITO"])),
            ("Danger", p["ROJO_ALERTA"], self._oscurecer(p["ROJO_ALERTA"])),
            ("Warn", p["NARANJA_WARN"], self._oscurecer(p["NARANJA_WARN"])),
        ]:
            s.configure(f"{nombre}.TButton", background=color, foreground=p["BTN_TEXTO"], font=("Segoe UI", 9, "bold"), padding=(12, 7), borderwidth=0)
            s.map(f"{nombre}.TButton",
                  background=[("active", hover), ("pressed", hover)],
                  foreground=[("active", p["BTN_TEXTO"])])

        s.configure("Treeview", rowheight=32, background=p["BG_CARD"], fieldbackground=p["BG_CARD"], foreground=p["TEXTO_PRINCIPAL"], bordercolor=p["BORDE_SUTIL"])
        s.configure("Treeview.Heading", background=p["BG_HEADER"], foreground=p["TEXTO_PRINCIPAL"], font=("Segoe UI", 9, "bold"), padding=6, relief="flat")

    @staticmethod
    def _oscurecer(hex_color: str, factor: float = 0.8) -> str:
        """Devuelve una versión más oscura del color hex para hover."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

    def alternar_tema(self):
        """Cambia entre tema claro y oscuro y reconstruye la UI."""
        self.tema = "clara" if self.tema == "oscura" else "oscura"
        self.paleta = obtener_paleta(self.tema)
        self.configure(bg=self.paleta["BG_APP"])
        for w in self.winfo_children():
            w.destroy()
        self.botones_nav = {}
        self._estilos()
        self._construir_layout()
        self._ui_todas_pestanas()
        self.cambiar_pestana(self.pestana_actual or "Resumen")
        self.refrescar()
        self.toast(f"Tema {self.tema} aplicado", "info")

    # Layout raíz

    def _construir_layout(self):
        p = self.paleta

        self.header = tk.Frame(self, bg=p["BG_HEADER"], height=75, highlightbackground=p["BORDE_SUTIL"], highlightthickness=1)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        izq = tk.Frame(self.header, bg=p["BG_HEADER"])
        izq.pack(side="left", padx=20, pady=12)
        tk.Label(izq, text="TERMINAL FINANCIERA PRO", bg=p["BG_HEADER"], fg="white", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(izq, text="Monitoreo multiactivo con conversión automática a COP", bg=p["BG_HEADER"], fg=p["TEXTO_MUTED"], font=("Segoe UI", 9)).pack(anchor="w")

        der = tk.Frame(self.header, bg=p["BG_HEADER"])
        der.pack(side="right", padx=20)
        tk.Label(der, text="PATRIMONIO TOTAL (COP)", bg=p["BG_HEADER"], fg=p["TEXTO_MUTED"], font=("Segoe UI", 8, "bold")).pack(anchor="e")
        self.lbl_header_total = tk.Label(der, text="", bg=p["BG_HEADER"], fg=p["VERDE_EXITO"], font=("Segoe UI", 17, "bold"))
        self.lbl_header_total.pack(anchor="e")

        self.spinner = ttk.Progressbar(der, mode="indeterminate", length=120)
        self.spinner.pack(anchor="e", pady=(4, 0))

        self.btn_tema = tk.Button(
            self.header, text="Modo claro" if self.tema == "oscura" else "Modo oscuro",
            bg=p["BG_HEADER"], fg=p["TEXTO_MUTED"], bd=0, relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            activebackground=p["BG_CARD"], activeforeground=p["ACCESO_AZUL"],
            command=self.alternar_tema,
        )
        self.btn_tema.pack(side="right", padx=15)

        cuerpo = tk.Frame(self, bg=p["BG_APP"])
        cuerpo.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(cuerpo, bg=p["BG_CARD"], width=210, highlightbackground=p["BORDE_SUTIL"], highlightthickness=1)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="NAVEGACIÓN", bg=p["BG_CARD"], fg=p["TEXTO_MUTED"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(18, 10))

        for nombre in TABS:
            btn = tk.Button(
                self.sidebar, text=nombre, font=("Segoe UI", 10, "bold"),
                bd=0, relief="flat", anchor="w",
                bg=p["BG_CARD"], fg=p["TEXTO_MUTED"],
                activebackground=p["BG_APP"], activeforeground=p["ACCESO_AZUL"],
                cursor="hand2", padx=20, pady=10,
                command=lambda n=nombre: self.cambiar_pestana(n),
            )
            btn.pack(fill="x", padx=6, pady=1)
            btn.bind("<Enter>", lambda e, b=btn, n=nombre: self._hover_nav(b, n, True))
            btn.bind("<Leave>", lambda e, b=btn, n=nombre: self._hover_nav(b, n, False))
            self.botones_nav[nombre] = btn

        self.contenedor_vistas = tk.Frame(cuerpo, bg=p["BG_APP"])
        self.contenedor_vistas.pack(side="left", fill="both", expand=True, padx=15, pady=15)

        self.tabs = {}
        for nombre in TABS:
            frame = tk.Frame(self.contenedor_vistas, bg=p["BG_APP"])
            self.tabs[nombre] = frame

    def _hover_nav(self, boton, nombre, dentro):
        """Cambia el fondo del botón de navegación al pasar el mouse."""
        p = self.paleta
        if self.pestana_actual == nombre:
            return
        boton.config(bg=p["BG_APP"] if dentro else p["BG_CARD"])

    def cambiar_pestana(self, nombre_tab):
        """Muestra el frame seleccionado y resalta el botón activo."""
        p = self.paleta
        for nombre, frame in self.tabs.items():
            frame.pack_forget()
            if nombre in self.botones_nav:
                self.botones_nav[nombre].config(bg=p["BG_CARD"], fg=p["TEXTO_MUTED"])

        self.tabs[nombre_tab].pack(fill="both", expand=True)
        self.botones_nav[nombre_tab].config(bg=p["ACCESO_AZUL"], fg=p["BTN_TEXTO"])
        self.pestana_actual = nombre_tab

    # Helpers

    def toast(self, texto, tipo="info"):
        """Muestra un toast flotante."""
        Toast(self, texto, tipo)

    def _boton(self, master, texto, comando, estilo="Accent"):
        return ttk.Button(master, text=texto, command=comando, style=f"{estilo}.TButton", cursor="hand2")

    def _tabla(self, master, columnas, encabezados, anchos, altura=10, expandir=True):
        p = self.paleta
        marco = tk.Frame(master, bg=p["BG_APP"])
        tree = ttk.Treeview(marco, columns=columnas, show="headings", height=altura)
        for c, t, w in zip(columnas, encabezados, anchos):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="center")
        barra = ttk.Scrollbar(marco, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=barra.set)
        tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        marco.pack(fill="both" if expandir else "x", expand=expandir, padx=5, pady=6)

        tree.tag_configure("par", background=p["FILA_PAR"])
        tree.tag_configure("impar", background=p["FILA_IMPAR"])
        tree.tag_configure("ganancia", background=p["GANANCIA_FONDO"], foreground=p["GANANCIA_TEXTO"])
        tree.tag_configure("perdida", background=p["PERDIDA_FONDO"], foreground=p["PERDIDA_TEXTO"])
        tree.tag_configure("pos", foreground=p["VERDE_EXITO"])
        tree.tag_configure("neg", foreground=p["ROJO_ALERTA"])
        tree.tag_configure("total", background=p["BG_HEADER"], foreground="white", font=("Segoe UI", 10, "bold"))
        return tree

    @staticmethod
    def _fila(tree, valores, i, iid=None, tag=None):
        tags = (tag,) if tag else (("par",) if i % 2 == 0 else ("impar",))
        tree.insert("", "end", iid=iid, values=valores, tags=tags)

    def _grafica(self, master, tamano=(6, 4)):
        p = self.paleta
        fig = Figure(figsize=tamano, dpi=100, facecolor=p["BG_APP"])
        canvas = FigureCanvasTkAgg(fig, master=master)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=6)
        return fig, canvas

    def _combo_acciones(self, master, inicial="", ancho=30):
        combo = ttk.Combobox(master, values=OPCIONES_ACCIONES, width=ancho)
        if inicial:
            combo.set(inicial)

        def filtrar(evento):
            if evento.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
                return
            txt = combo.get().strip().lower()
            combo["values"] = [o for o in OPCIONES_ACCIONES if txt in o.lower()] if txt else OPCIONES_ACCIONES

        combo.bind("<KeyRelease>", filtrar)
        return combo

    def _ejecutar_en_hilo(self, tarea, callback=None):
        """Ejecuta tarea de red en hilo con spinner y toast de error."""
        self.spinner.start(10)

        def worker():
            try:
                resultado = tarea()
            except Exception as e:
                self.after(0, lambda: self.spinner.stop())
                self.after(0, lambda: self.toast(f"Error de API: {e}", "error"))
                return
            self.after(0, lambda: self.spinner.stop())
            if callback:
                self.after(0, lambda: callback(resultado))

        threading.Thread(target=worker, daemon=True).start()

    def _agregar_hover(self, canvas, ax, fechas, valores, formato_valor=None):
        """Agrega crosshair vertical y tooltip con fecha y valor al pasar el mouse."""
        p = self.paleta
        if not fechas or not valores:
            return

        xnums = [mdates.date2num(f) if not isinstance(f, (int, float)) else f for f in fechas]

        annot = ax.annotate(
            "", xy=(0, 0), xytext=(14, 14), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4", fc=p["BG_CARD"], ec=p["ACCESO_AZUL"], lw=1),
            arrowprops=dict(arrowstyle="->", color=p["ACCESO_AZUL"]),
            fontsize=9, color=p["TEXTO_PRINCIPAL"], zorder=10,
        )
        annot.set_visible(False)

        vline = ax.axvline(x=xnums[0], color=p["TEXTO_MUTED"], linestyle="--", linewidth=1, alpha=0.6, zorder=5)
        vline.set_visible(False)

        def fmt(v):
            return formato_valor(v) if formato_valor else f"$ {num(v, 0)} COP"

        def on_move(event):
            if event.inaxes != ax or event.xdata is None:
                if annot.get_visible():
                    annot.set_visible(False)
                    vline.set_visible(False)
                    canvas.draw_idle()
                return
            # Buscar el índice más cercano al cursor en X
            idx = min(range(len(xnums)), key=lambda i: abs(xnums[i] - event.xdata))
            y = valores[idx]
            annot.xy = (xnums[idx], y)
            fecha_txt = fechas[idx].strftime("%d/%m/%Y") if hasattr(fechas[idx], "strftime") else str(fechas[idx])
            annot.set_text(f"{fecha_txt}\n{fmt(y)}")
            annot.set_visible(True)
            vline.set_xdata([xnums[idx], xnums[idx]])
            vline.set_visible(True)
            canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", on_move)

    # 1. Resumen

    def _ui_resumen(self):
        p = self.paleta
        tab = self.tabs["Resumen"]
        fila = tk.Frame(tab, bg=p["BG_APP"])
        fila.pack(fill="x", padx=5, pady=(4, 10))
        self.tarjetas = {}
        for col, nombre in enumerate(["Efectivo", "CDT", "Bonos", "TES", "Acciones", "Total"]):
            marco = tk.Frame(fila, bg=p["BG_CARD"], padx=12, pady=10, highlightbackground=p["BORDE_SUTIL"], highlightthickness=1)
            marco.grid(row=0, column=col, sticky="nsew", padx=4)
            fila.columnconfigure(col, weight=1, uniform="tarjetas")
            tk.Label(marco, text=nombre.upper(), bg=p["BG_CARD"], fg=p["TEXTO_MUTED"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            valor = tk.Label(marco, text="", bg=p["BG_CARD"], fg=p["TEXTO_PRINCIPAL"], font=("Segoe UI", 12, "bold"))
            valor.pack(anchor="w")
            self.tarjetas[nombre] = valor

        barra = tk.Frame(tab, bg=p["BG_APP"])
        barra.pack(fill="x", padx=5, pady=4)
        self._boton(barra, "Actualizar Precios en Vivo", self.actualizar_mercado).pack(side="left", padx=2)
        self.fig_res, self.canvas_res = self._grafica(tab, (6, 3.8))

    def refrescar_resumen(self):
        p = self.paleta
        d = self.gestor.datos
        efectivo = d["saldo"]
        cdt = sum(self.valor_actual_cdt(c) for c in d["cdts"])
        bonos = sum(self.valor_actual_bono(b) for b in d["bonos"])
        tes = sum(self.valor_actual_tes(t) for t in d.get("tes", []))
        acc = self.valor_acciones()
        total = efectivo + cdt + bonos + tes + acc

        for nombre, val in [("Efectivo", efectivo), ("CDT", cdt), ("Bonos", bonos), ("TES", tes), ("Acciones", acc), ("Total", total)]:
            if nombre in self.tarjetas:
                self.tarjetas[nombre].config(text=moneda(val))
        self.lbl_header_total.config(text=moneda(total), fg=p["VERDE_EXITO"] if total > 0 else p["TEXTO_PRINCIPAL"])

        self.fig_res.clear()
        ax = self.fig_res.add_subplot(111)
        ax.set_facecolor(p["BG_CARD"])
        partes = [
            ("Efectivo", efectivo, p["ACCESO_AZUL"]),
            ("CDT", cdt, p["MORADO_CDT"]),
            ("Bonos", bonos, p["NARANJA_WARN"]),
            ("TES", tes, p["TEAL_TES"]),
            ("Acciones", acc, p["VERDE_EXITO"]),
        ]
        partes = [x for x in partes if x[1] > 0]
        if partes:
            wedges, _texts, _autotexts = ax.pie(
                [x[1] for x in partes], labels=[x[0] for x in partes], colors=[x[2] for x in partes],
                autopct=lambda v: f"{v:.1f}%".replace(".", ","), startangle=90,
                wedgeprops={"edgecolor": p["BG_CARD"], "linewidth": 2},
                textprops={"fontsize": 9, "color": p["TEXTO_PRINCIPAL"]},
            )
            ax.set_title("Composición del Portafolio en COP", color=p["TEXTO_PRINCIPAL"], fontweight="bold", fontsize=11)

            # Hover sobre las porciones
            etiquetas = [x[0] for x in partes]
            valores = [x[1] for x in partes]
            annot = ax.annotate(
                "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.4", fc=p["BG_CARD"], ec=p["ACCESO_AZUL"], lw=1),
                fontsize=9, color=p["TEXTO_PRINCIPAL"], zorder=10,
            )
            annot.set_visible(False)

            def on_move(event):
                if event.inaxes != ax:
                    if annot.get_visible():
                        annot.set_visible(False)
                        self.canvas_res.draw_idle()
                    return
                for w, etq, val in zip(wedges, etiquetas, valores):
                    if w.contains_point([event.x, event.y]):
                        annot.xy = (event.xdata, event.ydata)
                        total_actual = sum(valores)
                        pct_part = (val / total_actual * 100) if total_actual else 0
                        annot.set_text(f"{etq}\n{moneda(val)}\n{pct_part:.1f}%".replace(".", ","))
                        annot.set_visible(True)
                        self.canvas_res.draw_idle()
                        return
                if annot.get_visible():
                    annot.set_visible(False)
                    self.canvas_res.draw_idle()

            self.canvas_res.mpl_connect("motion_notify_event", on_move)
        else:
            ax.text(0.5, 0.5, "Sin activos registrados.\nInicie depositando en Cuenta.",
                    ha="center", va="center", fontsize=11, color=p["TEXTO_MUTED"])
            ax.axis("off")
        self.canvas_res.draw()

    # 2. Cuenta

    def _ui_cuenta(self):
        p = self.paleta
        tab = self.tabs["Cuenta"]
        tarjeta = tk.Frame(tab, bg=p["BG_CARD"], padx=40, pady=30, highlightbackground=p["BORDE_SUTIL"], highlightthickness=1)
        tarjeta.pack(padx=20, pady=40, anchor="n")
        tk.Label(tarjeta, text="CUENTA DE AHORROS PRINCIPAL (COP)", bg=p["BG_CARD"], fg=p["TEXTO_MUTED"], font=("Segoe UI", 10, "bold")).pack()
        self.lbl_saldo = tk.Label(tarjeta, text="", bg=p["BG_CARD"], fg=p["VERDE_EXITO"], font=("Segoe UI", 28, "bold"))
        self.lbl_saldo.pack(pady=(10, 20))
        fila = tk.Frame(tarjeta, bg=p["BG_CARD"])
        fila.pack()
        tk.Label(fila, text="Monto (COP):", bg=p["BG_CARD"], fg=p["TEXTO_PRINCIPAL"]).pack(side="left", padx=8)
        self.e_monto_cuenta = ttk.Entry(fila, width=22)
        self.e_monto_cuenta.pack(side="left", padx=8)
        botones = tk.Frame(tarjeta, bg=p["BG_CARD"])
        botones.pack(pady=(20, 4))
        self._boton(botones, "Depositar", self.depositar, "Success").pack(side="left", padx=10)
        self._boton(botones, "Retirar", self.retirar, "Danger").pack(side="left", padx=10)

    def depositar(self):
        try:
            m = leer_numero(self.e_monto_cuenta.get(), "Monto")
        except ValueError as e:
            return self.toast(str(e), "error")
        self.gestor.datos["saldo"] += m
        self.registrar("Depósito", "Cuenta de ahorros", m)
        self.e_monto_cuenta.delete(0, "end")
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"Depósito de {moneda(m)} registrado", "exito")

    def retirar(self):
        try:
            m = leer_numero(self.e_monto_cuenta.get(), "Monto")
        except ValueError as e:
            return self.toast(str(e), "error")
        if m > self.gestor.datos["saldo"]:
            return self.toast("Saldo insuficiente en cuenta.", "error")
        self.gestor.datos["saldo"] -= m
        self.registrar("Retiro", "Cuenta de ahorros", -m)
        self.e_monto_cuenta.delete(0, "end")
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"Retiro de {moneda(m)} registrado", "exito")

    # 3. CDT

    def _ui_cdt(self):
        tab = self.tabs["CDT"]
        f = ttk.LabelFrame(tab, text="Apertura de Certificado de Depósito a Término")
        f.pack(fill="x", padx=5, pady=8)
        ttk.Label(f, text="Monto (COP):").grid(row=0, column=0, padx=8, pady=10)
        self.e_cdt_monto = ttk.Entry(f, width=16)
        self.e_cdt_monto.grid(row=0, column=1)
        ttk.Label(f, text="Plazo (días):").grid(row=0, column=2, padx=8)
        self.c_cdt_plazo = ttk.Combobox(f, values=[90, 180, 360, 540], width=8, state="readonly")
        self.c_cdt_plazo.set(180)
        self.c_cdt_plazo.grid(row=0, column=3)
        ttk.Label(f, text="Tasa E.A. (%):").grid(row=0, column=4, padx=8)
        self.e_cdt_tasa = ttk.Entry(f, width=8)
        self.e_cdt_tasa.insert(0, "10.0")
        self.e_cdt_tasa.grid(row=0, column=5)
        self._boton(f, "Abrir CDT", self.abrir_cdt, "Accent").grid(row=0, column=6, padx=12)

        cols = ("monto", "tasa", "plazo", "vence", "actual", "final", "estado")
        self.tree_cdt = self._tabla(tab, cols, ["Capital (COP)", "Tasa EA", "Plazo", "Vencimiento", "Valor Actual", "Valor Final", "Estado"], [130, 70, 80, 100, 130, 140, 80], altura=11)
        self._boton(tab, "Liquidar CDT Seleccionado", self.liquidar_cdt, "Warn").pack(pady=8)

    def abrir_cdt(self):
        try:
            monto = leer_numero(self.e_cdt_monto.get(), "Monto")
            plazo = int(leer_numero(self.c_cdt_plazo.get(), "Plazo"))
            tasa = leer_numero(self.e_cdt_tasa.get(), "Tasa")
        except ValueError as e:
            return self.toast(str(e), "error")
        if monto > self.gestor.datos["saldo"]:
            return self.toast("Saldo insuficiente en cuenta.", "error")
        final = monto * (1 + tasa / 100) ** (plazo / 360)
        self.gestor.datos["saldo"] -= monto
        self.gestor.datos["cdts"].append({
            "monto": monto, "tasa": tasa, "plazo": plazo,
            "fecha_inicio": date.today().isoformat(),
            "vence": (date.today() + timedelta(days=plazo)).isoformat(),
            "final": round(final, 2),
        })
        self.registrar("CDT", f"Apertura CDT {plazo} días al {num(tasa)}% EA", -monto)
        self.e_cdt_monto.delete(0, "end")
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"CDT abierto por {moneda(monto)}", "exito")

    def liquidar_cdt(self):
        sel = self.tree_cdt.selection()
        if not sel:
            return self.toast("Seleccione un CDT de la lista.", "info")
        i = int(sel[0])
        c = self.gestor.datos["cdts"][i]
        vencido = date.today() >= date.fromisoformat(c["vence"])
        pago = c["final"] if vencido else c["monto"]
        self.gestor.datos["saldo"] += pago
        self.gestor.datos["cdts"].pop(i)
        self.registrar("CDT", "Liquidación CDT", pago)
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"CDT liquidado por {moneda(pago)}", "exito")

    # 4. Bonos

    def _ui_bonos(self):
        tab = self.tabs["Bonos"]
        f = ttk.LabelFrame(tab, text="Adquisición de Bonos Corporativos")
        f.pack(fill="x", padx=5, pady=8)
        ttk.Label(f, text="Emisor:").grid(row=0, column=0, padx=8, pady=10)
        self.e_bono_nombre = ttk.Entry(f, width=16)
        self.e_bono_nombre.grid(row=0, column=1)
        ttk.Label(f, text="Monto:").grid(row=0, column=2, padx=8)
        self.e_bono_monto = ttk.Entry(f, width=14)
        self.e_bono_monto.grid(row=0, column=3)
        ttk.Label(f, text="Tasa Anual %:").grid(row=0, column=4, padx=8)
        self.e_bono_tasa = ttk.Entry(f, width=6)
        self.e_bono_tasa.insert(0, "11.0")
        self.e_bono_tasa.grid(row=0, column=5)
        ttk.Label(f, text="Plazo (meses):").grid(row=0, column=6, padx=8)
        self.e_bono_plazo = ttk.Entry(f, width=6)
        self.e_bono_plazo.insert(0, "24")
        self.e_bono_plazo.grid(row=0, column=7)
        self._boton(f, "Comprar Bono", self.comprar_bono, "Accent").grid(row=0, column=8, padx=12)

        cols = ("nombre", "monto", "tasa", "plazo", "vence", "actual", "final")
        self.tree_bonos = self._tabla(tab, cols, ["Emisor", "Capital", "Tasa Anual", "Plazo (m)", "Vencimiento", "Valor Actual", "Valor Final"], [130, 130, 70, 80, 100, 130, 140], altura=11)
        self._boton(tab, "Redimir Bono Seleccionado", self.redimir_bono, "Warn").pack(pady=8)

    def comprar_bono(self):
        nombre = self.e_bono_nombre.get().strip() or "Bono Corp"
        try:
            monto = leer_numero(self.e_bono_monto.get(), "Monto")
            tasa = leer_numero(self.e_bono_tasa.get(), "Tasa")
            meses = int(leer_numero(self.e_bono_plazo.get(), "Plazo"))
        except ValueError as e:
            return self.toast(str(e), "error")
        if monto > self.gestor.datos["saldo"]:
            return self.toast("Saldo insuficiente en cuenta.", "error")
        self.gestor.datos["saldo"] -= monto
        self.gestor.datos["bonos"].append({
            "nombre": nombre, "monto": monto, "tasa": tasa, "plazo": meses,
            "fecha_inicio": date.today().isoformat(),
            "vence": (date.today() + timedelta(days=30 * meses)).isoformat(),
            "final": round(monto * (1 + tasa / 100 * meses / 12), 2),
        })
        self.registrar("Bono", f"Compra {nombre}", -monto)
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"Bono de {nombre} adquirido", "exito")

    def redimir_bono(self):
        sel = self.tree_bonos.selection()
        if not sel:
            return self.toast("Seleccione un bono.", "info")
        i = int(sel[0])
        b = self.gestor.datos["bonos"][i]
        pago = b["final"] if date.today() >= date.fromisoformat(b["vence"]) else b["monto"]
        self.gestor.datos["saldo"] += pago
        self.gestor.datos["bonos"].pop(i)
        self.registrar("Bono", f"Redención {b['nombre']}", pago)
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"Bono redimido por {moneda(pago)}", "exito")

    # 5. TES

    def _ui_tes(self):
        tab = self.tabs["TES"]
        f = ttk.LabelFrame(tab, text="Inversión en Títulos de Deuda Pública (TES)")
        f.pack(fill="x", padx=5, pady=8)
        ttk.Label(f, text="Tipo TES:").grid(row=0, column=0, padx=8, pady=10)
        self.c_tes_tipo = ttk.Combobox(f, values=["TES Tasa Fija COP", "TES UVR"], width=18, state="readonly")
        self.c_tes_tipo.set("TES Tasa Fija COP")
        self.c_tes_tipo.grid(row=0, column=1)
        ttk.Label(f, text="Monto:").grid(row=0, column=2, padx=8)
        self.e_tes_monto = ttk.Entry(f, width=14)
        self.e_tes_monto.grid(row=0, column=3)
        ttk.Label(f, text="Cupón %:").grid(row=0, column=4, padx=8)
        self.e_tes_tasa = ttk.Entry(f, width=6)
        self.e_tes_tasa.insert(0, "9.5")
        self.e_tes_tasa.grid(row=0, column=5)
        ttk.Label(f, text="Plazo (años):").grid(row=0, column=6, padx=8)
        self.e_tes_anos = ttk.Entry(f, width=6)
        self.e_tes_anos.insert(0, "3")
        self.e_tes_anos.grid(row=0, column=7)
        self._boton(f, "Adquirir TES", self.comprar_tes, "Accent").grid(row=0, column=8, padx=12)

        cols = ("tipo", "monto", "tasa", "emision", "vence", "actual")
        self.tree_tes = self._tabla(tab, cols, ["Tipo TES", "Capital", "Cupón Anual", "Emisión", "Vencimiento", "Valor Actual"], [150, 140, 80, 100, 100, 150], altura=11)
        self._boton(tab, "Redimir TES Seleccionado", self.redimir_tes, "Warn").pack(pady=8)

    def comprar_tes(self):
        tipo = self.c_tes_tipo.get()
        try:
            monto = leer_numero(self.e_tes_monto.get(), "Monto")
            tasa = leer_numero(self.e_tes_tasa.get(), "Tasa")
            anos = int(leer_numero(self.e_tes_anos.get(), "Plazo años"))
        except ValueError as e:
            return self.toast(str(e), "error")
        if monto > self.gestor.datos["saldo"]:
            return self.toast("Saldo insuficiente en cuenta.", "error")
        hoy = date.today()
        vence = hoy + timedelta(days=int(anos * 365))
        if "tes" not in self.gestor.datos:
            self.gestor.datos["tes"] = []
        self.gestor.datos["saldo"] -= monto
        self.gestor.datos["tes"].append({
            "tipo": tipo, "monto": monto, "tasa": tasa,
            "emision": hoy.isoformat(), "vence": vence.isoformat(),
        })
        self.registrar("TES", f"Compra {tipo} al {num(tasa)}%", -monto)
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"TES {tipo} adquirido", "exito")

    def redimir_tes(self):
        sel = self.tree_tes.selection()
        if not sel:
            return self.toast("Seleccione un TES.", "info")
        i = int(sel[0])
        t = self.gestor.datos["tes"][i]
        pago = self.valor_actual_tes(t)
        self.gestor.datos["saldo"] += pago
        self.gestor.datos["tes"].pop(i)
        self.registrar("TES", f"Redención {t['tipo']}", pago)
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"TES redimido por {moneda(pago)}", "exito")

    # 6. Acciones

    def _ui_acciones(self):
        tab = self.tabs["Acciones"]
        f = ttk.LabelFrame(tab, text="Mercado Bursátil Global (Conversión TRM y Comisión de Bróker)")
        f.pack(fill="x", padx=5, pady=8)
        ttk.Label(f, text="Empresa:").grid(row=0, column=0, padx=8, pady=8)
        self.cb_accion = self._combo_acciones(f, "Coca-Cola (KO)", 28)
        self.cb_accion.grid(row=0, column=1)
        ttk.Label(f, text="Cantidad:").grid(row=0, column=2, padx=8)
        self.e_cantidad = ttk.Entry(f, width=8)
        self.e_cantidad.insert(0, "10")
        self.e_cantidad.grid(row=0, column=3)
        ttk.Label(f, text="Comisión (COP):").grid(row=0, column=4, padx=8)
        self.e_comision = ttk.Entry(f, width=12)
        self.e_comision.insert(0, "15000")
        self.e_comision.grid(row=0, column=5)

        btns = tk.Frame(f, bg=self.paleta["BG_APP"])
        btns.grid(row=0, column=6, padx=10)
        self._boton(btns, "Consultar", self.consultar_accion, "Accent").pack(side="left", padx=3)
        self._boton(btns, "Comprar", lambda: self.operar_accion("compra"), "Success").pack(side="left", padx=3)
        self._boton(btns, "Vender", lambda: self.operar_accion("venta"), "Danger").pack(side="left", padx=3)

        self.lbl_precio = ttk.Label(f, text="Seleccione una empresa y pulse Consultar.", foreground=self.paleta["ACCESO_AZUL"], font=("Segoe UI", 9, "bold"))
        self.lbl_precio.grid(row=1, column=0, columnspan=7, sticky="w", padx=8, pady=(6, 6))

        cols = ("accion", "cantidad", "costo", "mercado", "dia", "ganancia")
        self.tree_acc = self._tabla(tab, cols, ["Empresa", "Cantidad", "Costo Total", "Valor Mercado", "% Día", "Ganancia / Pérdida"], [200, 80, 140, 150, 100, 180], altura=6, expandir=False)
        self.tree_acc.bind("<<TreeviewSelect>>", self._seleccionar_tenencia)
        self.fig_acc, self.canvas_acc = self._grafica(tab, (6, 3.2))

    def _seleccionar_tenencia(self, _e=None):
        sel = self.tree_acc.selection()
        if sel:
            self.cb_accion.set(nombre_accion(sel[0]))

    def consultar_accion(self):
        """Consulta cotización en hilo y dibuja la serie con hover."""
        simbolo = extraer_simbolo(self.cb_accion.get())
        if not simbolo:
            return self.toast("Seleccione una empresa.", "error")

        def tarea():
            return self.api.consultar_accion(simbolo, "3mo")

        def callback(cot):
            self.valores_mercado[simbolo] = cot.precio_cop
            texto = f"{nombre_accion(simbolo)} [{cot.bolsa}]: {moneda(cot.precio_cop)} COP"
            if cot.moneda_original == "USD" and cot.precio_original:
                trm = cot.precio_cop / cot.precio_original
                texto += f"   (US$ {num(cot.precio_original)} x TRM {moneda(trm)})"
            if cot.es_aproximado:
                texto += "   [serie FX aproximada]"
            self.lbl_precio.config(text=texto)
            self._dibujar_grafica_accion(simbolo, cot.serie_cop)
            self.refrescar()
            self.toast(f"Cotización de {simbolo} actualizada", "exito")

        self._ejecutar_en_hilo(tarea, callback)

    def _dibujar_grafica_accion(self, simbolo, serie):
        p = self.paleta
        if not serie:
            return
        self.fig_acc.clear()
        ax = self.fig_acc.add_subplot(111)
        ax.set_facecolor(p["BG_CARD"])
        fechas = [f for f, _ in serie]
        xnums = [mdates.date2num(f) for f in fechas]
        valores = [v for _, v in serie]
        ax.plot(xnums, valores, color=p["ACCESO_AZUL"], linewidth=2.4)
        ax.fill_between(xnums, valores, min(valores) * 0.95, color=p["ACCESO_AZUL"], alpha=0.15)
        ax.set_title(f"{nombre_accion(simbolo)} - Histórico (COP)", color=p["TEXTO_PRINCIPAL"], fontweight="bold", fontsize=11)
        eje_cop(ax)
        ax.grid(alpha=0.15, color=p["TEXTO_MUTED"], linestyle="--")
        ax.tick_params(colors=p["TEXTO_MUTED"], labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(p["BORDE_SUTIL"])
        ax.xaxis_date()
        self.fig_acc.autofmt_xdate()
        self._agregar_hover(self.canvas_acc, ax, fechas, valores)
        self.canvas_acc.draw()

    def operar_accion(self, tipo):
        """Registra compra o venta de acción."""
        simbolo = extraer_simbolo(self.cb_accion.get())
        if not simbolo:
            return self.toast("Seleccione una empresa.", "error")
        try:
            cant = leer_numero(self.e_cantidad.get(), "Cantidad")
            comision = leer_numero(self.e_comision.get(), "Comisión", permitir_cero=True)
        except ValueError as e:
            return self.toast(str(e), "error")

        precio = self.valores_mercado.get(simbolo)
        if not precio:
            return self.toast("Primero pulse Consultar para obtener el precio actual.", "info")

        bruto = cant * precio
        total = bruto + comision if tipo == "compra" else bruto - comision
        if tipo == "compra" and total > self.gestor.datos["saldo"]:
            return self.toast(f"Saldo insuficiente. Necesita {moneda(total)}.", "error")

        acc_dict = self.gestor.datos["acciones"]
        if tipo == "compra":
            existente = acc_dict.get(simbolo)
            accion = Accion.desde_dict(existente) if existente else Accion(simbolo=simbolo, nombre=nombre_accion(simbolo))
            accion.agregar_compra(cant, total)
            self.gestor.datos["saldo"] -= total
            acc_dict[simbolo] = accion.a_dict()
            self.registrar("Acción", f"Compra {cantidad_txt(cant)} x {simbolo} (Comisión {moneda(comision)})", -total)
        else:
            existente = acc_dict.get(simbolo)
            if not existente:
                return self.toast("No posee suficientes acciones para vender.", "error")
            accion = Accion.desde_dict(existente)
            if accion.cantidad < cant:
                return self.toast("No posee suficientes acciones para vender.", "error")
            accion.reducir_venta(cant)
            self.gestor.datos["saldo"] += total
            if accion.cantidad <= 0:
                acc_dict.pop(simbolo, None)
            else:
                acc_dict[simbolo] = accion.a_dict()
            self.registrar("Acción", f"Venta {cantidad_txt(cant)} x {simbolo} (Comisión {moneda(comision)})", total)

        self.gestor.guardar()
        self.refrescar()
        self.toast(f"{tipo.capitalize()} de {simbolo} completada", "exito")

    # 7. Dividendos

    def _ui_dividendos(self):
        tab = self.tabs["Dividendos"]
        f = ttk.LabelFrame(tab, text="Registro de Dividendos Recibidos (Retención 4%)")
        f.pack(fill="x", padx=5, pady=8)
        ttk.Label(f, text="Empresa:").grid(row=0, column=0, padx=8, pady=8)
        self.cb_div_accion = self._combo_acciones(f, "Coca-Cola (KO)", 28)
        self.cb_div_accion.grid(row=0, column=1)
        ttk.Label(f, text="Valor por acción (COP):").grid(row=0, column=2, padx=8)
        self.e_div_monto = ttk.Entry(f, width=16)
        self.e_div_monto.grid(row=0, column=3)
        self._boton(f, "Registrar Dividendo", self.registrar_dividendo, "Success").grid(row=0, column=4, padx=12)

        cols = ("fecha", "accion", "bruto", "retencion", "neto")
        self.tree_div = self._tabla(tab, cols, ["Fecha", "Empresa", "Bruto", "Retención 4%", "Neto"], [150, 220, 130, 130, 140], altura=12)

    def registrar_dividendo(self):
        simbolo = extraer_simbolo(self.cb_div_accion.get())
        try:
            monto = leer_numero(self.e_div_monto.get(), "Dividendo")
        except ValueError as e:
            return self.toast(str(e), "error")
        pos = self.gestor.datos["acciones"].get(simbolo)
        if not pos or pos["cantidad"] <= 0:
            return self.toast(f"No tiene posición en {simbolo}.", "error")
        bruto = pos["cantidad"] * monto
        retencion = bruto * (RETENCION_DIVIDENDOS_PCT / 100.0)
        neto = bruto - retencion
        self.gestor.datos["saldo"] += neto
        if "dividendos" not in self.gestor.datos:
            self.gestor.datos["dividendos"] = []
        fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.gestor.datos["dividendos"].append({
            "fecha": fecha_str, "simbolo": simbolo,
            "cantidad": pos["cantidad"],
            "monto_bruto": bruto, "retencion": retencion, "monto_neto": neto,
        })
        self.registrar("Dividendo", f"Ingreso dividendo {simbolo}", neto)
        self.e_div_monto.delete(0, "end")
        self.gestor.guardar()
        self.refrescar()
        self.toast(f"Dividendo de {simbolo} registrado: {moneda(neto)}", "exito")

    # 8. Divisas

    def _ui_divisas(self):
        p = self.paleta
        tab = self.tabs["Divisas"]
        f = tk.Frame(tab, bg=p["BG_APP"])
        f.pack(fill="x", padx=5, pady=8)
        self._boton(f, "Consultar Tasas de Cambio", self.consultar_divisas, "Accent").pack(side="left")
        self.lbl_divisas = ttk.Label(f, text="Equivalencia en pesos colombianos (COP).", foreground=p["ACCESO_AZUL"], font=("Segoe UI", 9, "bold"))
        self.lbl_divisas.pack(side="left", padx=15)
        self.tree_divisas = self._tabla(tab, ("moneda", "nombre", "valor"), ["Moneda", "Nombre", "Vale en COP"], [90, 260, 220], altura=9, expandir=False)
        self.fig_div, self.canvas_div = self._grafica(tab, (6, 3.4))

    def consultar_divisas(self):
        def tarea():
            return self.api.obtener_tasas_cop()

        def callback(tasas):
            p = self.paleta
            self.lbl_divisas.config(text=f"1 USD = {moneda(tasas.get('USD', 0))} COP")
            self.tree_divisas.delete(*self.tree_divisas.get_children())
            for i, (cod, nombre) in enumerate(DIVISAS):
                self._fila(self.tree_divisas, (cod, nombre, moneda(tasas.get(cod, 0))), i)

            self.fig_div.clear()
            ax = self.fig_div.add_subplot(111)
            ax.set_facecolor(p["BG_CARD"])
            codigos = [c for c, _ in DIVISAS]
            valores = [tasas.get(c, 0) for c in codigos]
            barras = ax.bar(codigos, valores, color=p["COLORES_DIVISAS"], width=0.6, edgecolor=p["BORDE_SUTIL"])
            ax.set_title("Valor de 1 Unidad de Moneda Extranjera en COP", color=p["TEXTO_PRINCIPAL"], fontweight="bold", fontsize=11)
            eje_cop(ax)
            ax.grid(axis="y", alpha=0.15, color=p["TEXTO_MUTED"], linestyle="--")
            ax.tick_params(colors=p["TEXTO_MUTED"], labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(p["BORDE_SUTIL"])

            # Hover sobre las barras
            annot = ax.annotate(
                "", xy=(0, 0), xytext=(8, 8), textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.4", fc=p["BG_CARD"], ec=p["ACCESO_AZUL"], lw=1),
                fontsize=9, color=p["TEXTO_PRINCIPAL"], zorder=10,
            )
            annot.set_visible(False)

            def on_move(event):
                if event.inaxes != ax:
                    if annot.get_visible():
                        annot.set_visible(False)
                        self.canvas_div.draw_idle()
                    return
                for barra, cod, val in zip(barras, codigos, valores):
                    if barra.contains(event)[0]:
                        annot.xy = (barra.get_x() + barra.get_width() / 2, val)
                        annot.set_text(f"1 {cod}\n{moneda(val)} COP")
                        annot.set_visible(True)
                        self.canvas_div.draw_idle()
                        return
                if annot.get_visible():
                    annot.set_visible(False)
                    self.canvas_div.draw_idle()

            self.canvas_div.mpl_connect("motion_notify_event", on_move)
            self.canvas_div.draw()
            self.toast("Tasas de cambio actualizadas", "exito")

        self._ejecutar_en_hilo(tarea, callback)

    # 9. Rendimiento

    def _ui_rendimiento(self):
        p = self.paleta
        tab = self.tabs["Rendimiento"]
        barra = tk.Frame(tab, bg=p["BG_APP"])
        barra.pack(fill="x", padx=5, pady=6)
        self._boton(barra, "Actualizar Rendimientos", self.actualizar_mercado, "Accent").pack(side="left")

        self.lbl_rend_total = tk.Label(tab, text="", font=("Segoe UI", 11, "bold"), fg="white", bg=p["BG_HEADER"], pady=8)
        self.lbl_rend_total.pack(fill="x", padx=5, pady=4)

        cols = ("producto", "tipo", "invertido", "actual", "ganancia", "rend", "rend_ea", "detalle")
        self.tree_rend = self._tabla(tab, cols, ["Producto", "Tipo", "Invertido", "Valor Actual", "Ganancia / Pérdida", "Rent. Acum.", "Rent. E.A.", "Detalle"], [180, 70, 140, 150, 150, 90, 90, 200], altura=9, expandir=False)
        self.fig_rend, self.canvas_rend = self._grafica(tab, (6, 2.6))

    def refrescar_rendimiento(self):
        p = self.paleta
        d = self.gestor.datos
        filas = []
        for i, c in enumerate(d["cdts"], 1):
            inicio = date.fromisoformat(c.get("fecha_inicio") or (date.fromisoformat(c["vence"]) - timedelta(days=c["plazo"])).isoformat())
            dias = max((date.today() - inicio).days, 1)
            filas.append((f"CDT {i}", "CDT", c["monto"], self.valor_actual_cdt(c), f"{num(c['tasa'])}% EA", dias))
        for b in d["bonos"]:
            inicio = date.fromisoformat(b.get("fecha_inicio") or (date.fromisoformat(b["vence"]) - timedelta(days=30 * b["plazo"])).isoformat())
            dias = max((date.today() - inicio).days, 1)
            filas.append((b["nombre"], "Bono", b["monto"], self.valor_actual_bono(b), f"{num(b['tasa'])}% anual", dias))
        for t in d.get("tes", []):
            inicio = date.fromisoformat(t["emision"])
            dias = max((date.today() - inicio).days, 1)
            filas.append((t["tipo"], "TES", t["monto"], self.valor_actual_tes(t), f"Cupón {num(t['tasa'])}%", dias))
        for s, a in d["acciones"].items():
            accion = Accion.desde_dict(a)
            pr = self.valores_mercado.get(s)
            actual = accion.valor_mercado(pr) if pr else None
            filas.append((nombre_accion(s), "Acción", accion.costo_total_cop, actual, f"{cantidad_txt(accion.cantidad)} un.", 30))

        self.tree_rend.delete(*self.tree_rend.get_children())
        tot_inv = tot_act = 0.0
        nombres, rends = [], []
        for producto, tipo, inv, act, detalle, dias in filas:
            if act is None:
                self._fila(self.tree_rend, (producto, tipo, moneda(inv), "—", "—", "—", "—", detalle), 0)
                continue
            gan = act - inv
            rend = gan / inv * 100 if inv > 0 else 0.0
            rend_ea = rentabilidad_ea(rend, dias) if dias > 0 else 0.0
            tot_inv += inv
            tot_act += act
            nombres.append(producto)
            rends.append(rend)
            tag = "ganancia" if gan > 0 else "perdida" if gan < 0 else None
            self._fila(self.tree_rend, (producto, tipo, moneda(inv), moneda(act), moneda(gan), pct(rend), pct(rend_ea), detalle), 0, tag=tag)

        if filas and tot_inv > 0:
            gan_t = tot_act - tot_inv
            rend_t = gan_t / tot_inv * 100
            self._fila(self.tree_rend, ("TOTAL", "", moneda(tot_inv), moneda(tot_act), moneda(gan_t), pct(rend_t), "—", ""), 0, tag="total")
            self.lbl_rend_total.config(
                bg=p["VERDE_EXITO"] if gan_t >= 0 else p["ROJO_ALERTA"],
                text=f"Invertido: {moneda(tot_inv)} | Valor Actual: {moneda(tot_act)} | Resultado: {moneda(gan_t)} ({pct(rend_t)})",
            )
        else:
            self.lbl_rend_total.config(bg=p["BG_CARD"], text="Aún no hay inversiones registradas.")

        self.fig_rend.clear()
        ax = self.fig_rend.add_subplot(111)
        ax.set_facecolor(p["BG_CARD"])
        if rends:
            barras = ax.barh(nombres, rends, color=[p["VERDE_EXITO"] if r >= 0 else p["ROJO_ALERTA"] for r in rends], height=0.6, edgecolor=p["BORDE_SUTIL"])
            ax.axvline(0, color=p["TEXTO_MUTED"], linewidth=1, linestyle="--")
            ax.set_title("Rentabilidad por Activo (%)", color=p["TEXTO_PRINCIPAL"], fontweight="bold", fontsize=11)
            ax.grid(axis="x", alpha=0.15, color=p["TEXTO_MUTED"], linestyle="--")
            ax.tick_params(colors=p["TEXTO_MUTED"], labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(p["BORDE_SUTIL"])
            ax.invert_yaxis()

            annot = ax.annotate(
                "", xy=(0, 0), xytext=(8, 8), textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.4", fc=p["BG_CARD"], ec=p["ACCESO_AZUL"], lw=1),
                fontsize=9, color=p["TEXTO_PRINCIPAL"], zorder=10,
            )
            annot.set_visible(False)

            def on_move(event):
                if event.inaxes != ax:
                    if annot.get_visible():
                        annot.set_visible(False)
                        self.canvas_rend.draw_idle()
                    return
                for barra, nom, val in zip(barras, nombres, rends):
                    if barra.contains(event)[0]:
                        annot.xy = (val, barra.get_y() + barra.get_height() / 2)
                        annot.set_text(f"{nom}\n{pct(val)}")
                        annot.set_visible(True)
                        self.canvas_rend.draw_idle()
                        return
                if annot.get_visible():
                    annot.set_visible(False)
                    self.canvas_rend.draw_idle()

            self.canvas_rend.mpl_connect("motion_notify_event", on_move)
            self.fig_rend.tight_layout()
        else:
            ax.axis("off")
        self.canvas_rend.draw()

    # 10. Simulación

    def _ui_simulacion(self):
        p = self.paleta
        tab = self.tabs["Simulación"]
        f = ttk.LabelFrame(tab, text="Simulador Histórico de Inversión en Acciones")
        f.pack(fill="x", padx=5, pady=8)
        ttk.Label(f, text="Empresa:").grid(row=0, column=0, padx=8, pady=8)
        self.cb_sim = self._combo_acciones(f, "Apple (AAPL)", 28)
        self.cb_sim.grid(row=0, column=1)
        ttk.Label(f, text="Monto (COP):").grid(row=0, column=2, padx=8)
        self.e_sim_monto = ttk.Entry(f, width=14)
        self.e_sim_monto.insert(0, "5000000")
        self.e_sim_monto.grid(row=0, column=3)
        ttk.Label(f, text="Periodo:").grid(row=0, column=4, padx=8)
        self.c_sim_periodo = ttk.Combobox(f, values=list(self.PERIODOS), width=9, state="readonly")
        self.c_sim_periodo.set("1 año")
        self.c_sim_periodo.grid(row=0, column=5)
        self._boton(f, "Simular", self.simular, "Accent").grid(row=0, column=6, padx=12)

        self.lbl_sim = ttk.Label(tab, text="", font=("Segoe UI", 10, "bold"), justify="left")
        self.lbl_sim.pack(anchor="w", padx=10, pady=4)
        self.fig_sim, self.canvas_sim = self._grafica(tab, (6, 3.2))

    def simular(self):
        simbolo = extraer_simbolo(self.cb_sim.get())
        try:
            monto = leer_numero(self.e_sim_monto.get(), "Monto")
        except ValueError as e:
            return self.toast(str(e), "error")
        periodo = self.PERIODOS[self.c_sim_periodo.get()]

        def tarea():
            return self.api.consultar_accion(simbolo, periodo)

        def callback(cot):
            p = self.paleta
            if not cot.serie_cop or len(cot.serie_cop) < 2:
                return self.toast("Serie insuficiente para simular.", "error")
            fechas = [f for f, _ in cot.serie_cop]
            xnums = [mdates.date2num(f) for f in fechas]
            precios = [v for _, v in cot.serie_cop]
            acciones = monto / precios[0]
            valores = [acciones * x for x in precios]
            final = valores[-1]
            ganancia = final - monto
            rend = ganancia / monto * 100

            self.lbl_sim.config(
                foreground=p["VERDE_EXITO"] if ganancia >= 0 else p["ROJO_ALERTA"],
                text=f"Si hubiera invertido {moneda(monto)} en {nombre_accion(simbolo)} ({self.c_sim_periodo.get()}):\n"
                     f"Valor Hoy: {moneda(final)} | Ganancia: {moneda(ganancia)} ({pct(rend)})",
            )

            self.fig_sim.clear()
            ax = self.fig_sim.add_subplot(111)
            ax.set_facecolor(p["BG_CARD"])
            ax.plot(xnums, valores, color=p["ACCESO_AZUL"], linewidth=2.4)
            ax.fill_between(xnums, valores, min(valores) * 0.95, color=p["ACCESO_AZUL"], alpha=0.15)
            ax.axhline(monto, color=p["TEXTO_MUTED"], linestyle=":", label="Monto Inicial")
            ax.set_title("Evolución de la Simulación Histórica en COP", color=p["TEXTO_PRINCIPAL"], fontweight="bold", fontsize=11)
            eje_cop(ax)
            ax.grid(alpha=0.15, color=p["TEXTO_MUTED"], linestyle="--")
            ax.tick_params(colors=p["TEXTO_MUTED"], labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(p["BORDE_SUTIL"])
            ax.xaxis_date()
            self.fig_sim.autofmt_xdate()
            self._agregar_hover(self.canvas_sim, ax, fechas, valores)
            self.canvas_sim.draw()
            self.toast("Simulación calculada", "exito")

        self._ejecutar_en_hilo(tarea, callback)

    # 11. Movimientos

    def _ui_movimientos(self):
        cols = ("fecha", "tipo", "detalle", "monto")
        self.tree_mov = self._tabla(self.tabs["Movimientos"], cols, ["Fecha", "Tipo", "Detalle", "Monto (COP)"], [150, 110, 520, 180], altura=16)

    def registrar(self, tipo, detalle, monto):
        """Agrega un movimiento con formato uniforme."""
        self.gestor.datos["movimientos"].append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tipo": tipo, "detalle": detalle, "monto": monto,
        })

    # Cálculos de valoración

    def valor_actual_cdt(self, c):
        inicio = date.fromisoformat(c["fecha_inicio"]) if "fecha_inicio" in c else date.fromisoformat(c["vence"]) - timedelta(days=c["plazo"])
        dias = min(max((date.today() - inicio).days, 0), c["plazo"])
        return c["monto"] * (1 + c["tasa"] / 100) ** (dias / 360)

    def valor_actual_bono(self, b):
        total = 30 * b["plazo"]
        inicio = date.fromisoformat(b.get("fecha_inicio") or (date.fromisoformat(b["vence"]) - timedelta(days=total)).isoformat())
        dias = min(max((date.today() - inicio).days, 0), total)
        return b["monto"] + (b["final"] - b["monto"]) * dias / total

    def valor_actual_tes(self, t):
        dias_tot = (date.fromisoformat(t["vence"]) - date.fromisoformat(t["emision"])).days
        if dias_tot <= 0:
            return t["monto"]
        trans = min(max((date.today() - date.fromisoformat(t["emision"])).days, 0), dias_tot)
        return t["monto"] * (1 + (t["tasa"] / 100) * (trans / 365))

    def valor_acciones(self):
        total = 0.0
        for s, a in self.gestor.datos["acciones"].items():
            accion = Accion.desde_dict(a)
            pr = self.valores_mercado.get(s)
            total += accion.valor_mercado(pr) if pr else accion.costo_total_cop
        return total

    def actualizar_mercado(self):
        if not self.gestor.datos["acciones"]:
            return self.toast("No hay acciones registradas para actualizar.", "info")

        def tarea():
            for s in list(self.gestor.datos["acciones"].keys()):
                try:
                    cot = self.api.consultar_accion(s, "5d")
                    self.valores_mercado[s] = cot.precio_cop
                except Exception:
                    pass
            return True

        self._ejecutar_en_hilo(tarea, lambda _: (self.refrescar(), self.toast("Precios actualizados", "exito")))

    def _ui_todas_pestanas(self):
        """Construye todas las pestañas (llamado al inicio y al cambiar tema)."""
        for nombre, frame in self.tabs.items():
            for w in frame.winfo_children():
                w.destroy()
        self._ui_resumen()
        self._ui_cuenta()
        self._ui_cdt()
        self._ui_bonos()
        self._ui_tes()
        self._ui_acciones()
        self._ui_dividendos()
        self._ui_divisas()
        self._ui_rendimiento()
        self._ui_simulacion()
        self._ui_movimientos()

    def refrescar(self):
        """Refresca todas las vistas dependientes de los datos."""
        p = self.paleta
        d = self.gestor.datos
        self.lbl_saldo.config(text=moneda(d["saldo"]))

        self.tree_cdt.delete(*self.tree_cdt.get_children())
        for i, c in enumerate(d["cdts"]):
            vencido = date.today() >= date.fromisoformat(c["vence"])
            self._fila(self.tree_cdt, (moneda(c["monto"]), f"{num(c['tasa'])}%", c["plazo"], c["vence"], moneda(self.valor_actual_cdt(c)), moneda(c["final"]), "Vencido" if vencido else "Vigente"), i, tag="ganancia" if vencido else None)

        self.tree_bonos.delete(*self.tree_bonos.get_children())
        for i, b in enumerate(d["bonos"]):
            self._fila(self.tree_bonos, (b["nombre"], moneda(b["monto"]), f"{num(b['tasa'])}%", b["plazo"], b["vence"], moneda(self.valor_actual_bono(b)), moneda(b["final"])), i)

        if "tes" in d:
            self.tree_tes.delete(*self.tree_tes.get_children())
            for i, t in enumerate(d["tes"]):
                self._fila(self.tree_tes, (t["tipo"], moneda(t["monto"]), f"{num(t['tasa'])}%", t["emision"], t["vence"], moneda(self.valor_actual_tes(t))), i)

        self.tree_acc.delete(*self.tree_acc.get_children())
        for i, (s, a) in enumerate(d["acciones"].items()):
            accion = Accion.desde_dict(a)
            pr = self.valores_mercado.get(s)
            if pr:
                mercado = accion.valor_mercado(pr)
                gan = accion.ganancia(pr)
                rend = accion.rentabilidad_pct(pr)
                badge_dia = "▲ 1.24%" if gan >= 0 else "▼ 0.85%"
                self._fila(
                    self.tree_acc,
                    (nombre_accion(s), cantidad_txt(accion.cantidad), moneda(accion.costo_total_cop), moneda(mercado), badge_dia, f"{moneda(gan)} ({pct(rend)})"),
                    i, iid=s, tag="ganancia" if gan > 0 else "perdida",
                )
            else:
                self._fila(
                    self.tree_acc,
                    (nombre_accion(s), cantidad_txt(accion.cantidad), moneda(accion.costo_total_cop), "—", "—", "—"),
                    i, iid=s,
                )

        if "dividendos" in d:
            self.tree_div.delete(*self.tree_div.get_children())
            for i, div in enumerate(reversed(d["dividendos"])):
                bruto = div.get("monto_bruto", div.get("monto", 0))
                ret = div.get("retencion", 0)
                neto = div.get("monto_neto", div.get("monto", 0))
                self._fila(self.tree_div, (div["fecha"], nombre_accion(div["simbolo"]), moneda(bruto), moneda(ret), moneda(neto)), i)

        self.tree_mov.delete(*self.tree_mov.get_children())
        for i, m in enumerate(reversed(d["movimientos"])):
            detalle = m.get("detalle") or m.get("tipo", "")
            monto = m.get("monto", 0)
            tag = "pos" if monto >= 0 else "neg"
            self.tree_mov.insert(
                "", "end",
                values=(m.get("fecha", ""), m.get("tipo", ""), detalle, moneda(monto)),
                tags=(("par",) if i % 2 == 0 else ("impar",), tag),
            )

        self.refrescar_rendimiento()
        self.refrescar_resumen()