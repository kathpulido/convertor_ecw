# -*- coding: utf-8 -*-
"""Conversor de planos ECW / ERS / TIFF (y .ecw.aux.xml) a PDF o JPG.
Permite rotar el plano interactivamente (vista previa en vivo) antes de
exportar, y agrega el logo del DADEP en una esquina."""
import base64, io, os, sys, threading, tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- Rutas internas para funcionar sin GDAL instalado (ejecutable portable) ---
_base = getattr(sys, "_MEIPASS", None)
if _base:
    _osgeo = os.path.join(_base, "osgeo")
    os.environ["GDAL_DRIVER_PATH"] = os.path.join(_osgeo, "gdalplugins")
    os.environ["GDAL_DATA"] = os.path.join(_osgeo, "data", "gdal")
    os.environ["PROJ_DATA"] = os.path.join(_osgeo, "data", "proj")
    os.environ["PROJ_LIB"] = os.environ["PROJ_DATA"]
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(_osgeo)
    os.environ["PATH"] = _osgeo + os.pathsep + os.environ.get("PATH", "")

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk
from osgeo import gdal

gdal.UseExceptions()
Image.MAX_IMAGE_PIXELS = None

ESQUINAS = ["Inferior derecha", "Inferior izquierda", "Superior derecha", "Superior izquierda"]
_ESQUINA_OPUESTA = {
    "Inferior derecha": "Superior izquierda",
    "Inferior izquierda": "Superior derecha",
    "Superior derecha": "Inferior izquierda",
    "Superior izquierda": "Inferior derecha",
}
GITHUB_AUTOR = "github.com/kathpulido"
LADO_PREVIEW = 1200  # resolución de la vista previa (rápida); la exportación usa "Lado máx."
EXTENSIONES = (".ecw", ".ers", ".tif", ".tiff")

# Logo del DADEP, incrustado en el programa (PNG en base64) para no depender
# de ningún archivo externo: el .exe queda funcionando solo, en cualquier PC.
_LOGO_DADEP_B64 = (
    "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"
)


def _cargar_logo_dadep():
    return Image.open(io.BytesIO(base64.b64decode(_LOGO_DADEP_B64))).convert("RGBA")


_logo_cache = None


def resolver_entrada(ruta):
    """Si el usuario elige un .ecw.aux.xml (o .tif.aux.xml), usa el archivo hermano."""
    if ruta.lower().endswith(".aux.xml"):
        return ruta[:-len(".aux.xml")]
    return ruta


def leer_imagen(ruta, max_lado):
    ds = gdal.Open(resolver_entrada(ruta))
    w, h, nb = ds.RasterXSize, ds.RasterYSize, ds.RasterCount
    if max_lado and max(w, h) > max_lado:
        k = max_lado / max(w, h)
        ow, oh = max(1, int(w * k)), max(1, int(h * k))
    else:
        ow, oh = w, h
    bandas = [1] if nb < 3 else [1, 2, 3]
    tipo = ds.GetRasterBand(1).DataType
    kw = dict(format="MEM", width=ow, height=oh, bandList=bandas,
              outputType=gdal.GDT_Byte, resampleAlg="average")
    if tipo != gdal.GDT_Byte:
        kw["scaleParams"] = [[]]  # estiramiento automático min-max a 8 bits
    out = gdal.Translate("", ds, **kw)
    arr = out.ReadAsArray()
    if len(bandas) == 1:
        return Image.fromarray(arr, "L").convert("RGB")
    return Image.fromarray(np.transpose(arr, (1, 2, 0)), "RGB")


def rotar(img, angulo):
    """Rotación en sentido horario (como es habitual en planos), fondo blanco."""
    angulo = angulo % 360
    if angulo:
        return img.rotate(-angulo, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    return img


def marcar_dadep(img, esquina):
    """Pega el logo del DADEP, pequeño, en una esquina del plano."""
    global _logo_cache
    if _logo_cache is None:
        _logo_cache = _cargar_logo_dadep()
    logo = _logo_cache

    lado_menor = min(img.size)
    ancho_logo = max(70, int(lado_menor * 0.16))
    k = ancho_logo / logo.width
    alto_logo = max(1, int(logo.height * k))
    logo_r = logo.resize((ancho_logo, alto_logo), Image.LANCZOS)

    margen = max(6, int(lado_menor * 0.012))
    W, H = img.size
    if esquina == "Inferior derecha":
        xy = (W - margen - ancho_logo, H - margen - alto_logo)
    elif esquina == "Inferior izquierda":
        xy = (margen, H - margen - alto_logo)
    elif esquina == "Superior derecha":
        xy = (W - margen - ancho_logo, margen)
    else:
        xy = (margen, margen)

    out = img.convert("RGBA")
    out.alpha_composite(logo_r, dest=xy)
    return out.convert("RGB")


def marcar_autor(img, esquina):
    """Escribe el crédito de GitHub, en letra muy pequeña, en una esquina."""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    lado_menor = min(img.size)
    # Tamaño casi fijo en píxeles (no un % de la imagen): así se ve igual de
    # chiquito tanto en la vista previa como en un plano exportado enorme.
    tam = min(11, max(6, int(lado_menor * 0.0018)))
    try:
        font = ImageFont.load_default(size=tam)
    except TypeError:
        font = ImageFont.load_default()
    grosor = 1
    bbox = draw.textbbox((0, 0), GITHUB_AUTOR, font=font, stroke_width=grosor)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margen = min(14, max(3, int(lado_menor * 0.002)))
    W, H = img.size
    if esquina == "Inferior derecha":
        xy = (W - margen - tw - bbox[0], H - margen - th - bbox[1])
    elif esquina == "Inferior izquierda":
        xy = (margen - bbox[0], H - margen - th - bbox[1])
    elif esquina == "Superior derecha":
        xy = (W - margen - tw - bbox[0], margen - bbox[1])
    else:
        xy = (margen - bbox[0], margen - bbox[1])
    draw.text(xy, GITHUB_AUTOR, font=font, fill="white", stroke_width=grosor, stroke_fill="black")
    return img


def convertir(ruta, carpeta, formato, angulo, calidad, dpi, max_lado, marca, esquina):
    img = leer_imagen(ruta, max_lado)
    img = rotar(img, angulo)
    if marca:
        img = marcar_dadep(img, esquina)
    img = marcar_autor(img, _ESQUINA_OPUESTA[esquina])
    base = os.path.splitext(os.path.basename(resolver_entrada(ruta)))[0]
    if formato == "PDF":
        dest = os.path.join(carpeta, base + ".pdf")
        img.save(dest, "PDF", resolution=dpi)
    else:
        if max(img.size) > 65500:
            raise ValueError("Imagen > 65500 px: JPG no lo permite. Reduce 'Lado máx.'.")
        dest = os.path.join(carpeta, base + ".jpg")
        img.save(dest, "JPEG", quality=calidad, dpi=(dpi, dpi))
    return dest


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Conversor de planos ECW / ERS - DADEP")
        self.geometry("1040x620")
        self.minsize(920, 560)

        self.archivos = []
        self.angulos = {}      # ruta -> ángulo actual elegido por el usuario (° horario)
        self.cache_base = {}   # ruta -> imagen de vista previa (sin rotar, ya descargada)
        self.ruta_actual = None
        self._preview_photo = None
        p = dict(padx=8, pady=4)

        principal = ttk.Frame(self); principal.pack(fill="both", expand=True)

        # ---------- Panel izquierdo: archivos y opciones de exportación ----------
        izq = ttk.Frame(principal); izq.pack(side="left", fill="both", expand=True, **p)

        ttk.Label(izq, text="Archivos (.ecw, .ers, .tif/.tiff, .ecw.aux.xml):").pack(anchor="w")
        self.lista = tk.Listbox(izq, height=8, selectmode="extended", exportselection=False)
        self.lista.pack(fill="both", expand=True)
        self.lista.bind("<<ListboxSelect>>", self.al_seleccionar)
        b = ttk.Frame(izq); b.pack(fill="x", pady=4)
        ttk.Button(b, text="Agregar archivos", command=self.agregar).pack(side="left")
        ttk.Button(b, text="Agregar carpeta", command=self.agregar_carpeta).pack(side="left", padx=4)
        ttk.Button(b, text="Quitar", command=self.quitar).pack(side="left")

        o = ttk.LabelFrame(izq, text="Exportar"); o.pack(fill="x", **p)
        self.fmt = tk.StringVar(value="PDF")
        ttk.Label(o, text="Formato:").grid(row=0, column=0, sticky="w", **p)
        ttk.Radiobutton(o, text="PDF", variable=self.fmt, value="PDF").grid(row=0, column=1)
        ttk.Radiobutton(o, text="JPG", variable=self.fmt, value="JPG").grid(row=0, column=2)

        ttk.Label(o, text="Calidad JPG:").grid(row=1, column=0, sticky="w", **p)
        self.cal = tk.IntVar(value=90)
        ttk.Spinbox(o, from_=10, to=100, textvariable=self.cal, width=6).grid(row=1, column=1, sticky="w")
        ttk.Label(o, text="DPI:").grid(row=1, column=2, sticky="e")
        self.dpi = tk.IntVar(value=150)
        ttk.Spinbox(o, from_=50, to=1200, textvariable=self.dpi, width=6).grid(row=1, column=3, sticky="w")

        ttk.Label(o, text="Lado máx. (px, 0=completo):").grid(row=2, column=0, columnspan=2, sticky="w", **p)
        self.lado = tk.IntVar(value=12000)
        ttk.Spinbox(o, from_=0, to=60000, increment=1000, textvariable=self.lado, width=8)\
            .grid(row=2, column=2, sticky="w")

        self.marca = tk.BooleanVar(value=True)
        ttk.Checkbutton(o, text="Agregar logo del DADEP", variable=self.marca,
                        command=self.refrescar_preview).grid(row=3, column=0, columnspan=2, sticky="w", **p)
        self.esquina = tk.StringVar(value=ESQUINAS[0])
        combo_esq = ttk.Combobox(o, textvariable=self.esquina, values=ESQUINAS, state="readonly", width=17)
        combo_esq.grid(row=3, column=2, columnspan=2, sticky="w")
        combo_esq.bind("<<ComboboxSelected>>", lambda e: self.refrescar_preview())

        s = ttk.Frame(izq); s.pack(fill="x", **p)
        self.salida = tk.StringVar()
        ttk.Label(s, text="Carpeta de salida:").pack(side="left")
        ttk.Entry(s, textvariable=self.salida).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(s, text="...", width=3, command=self.elegir_salida).pack(side="left")

        self.barra = ttk.Progressbar(izq); self.barra.pack(fill="x", **p)
        self.estado = ttk.Label(izq, text="Selecciona un archivo para ver la vista previa")
        self.estado.pack(anchor="w", padx=8)
        self.btn = ttk.Button(izq, text="Convertir", command=self.iniciar); self.btn.pack(pady=6)

        # ---------- Panel derecho: vista previa y rotación ----------
        der = ttk.LabelFrame(principal, text="Vista previa y rotación")
        der.pack(side="left", fill="both", expand=True, **p)

        self.canvas = tk.Canvas(der, background="#B0B0B0", width=420, height=380, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda e: self.refrescar_preview())

        rot = ttk.Frame(der); rot.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(rot, text="⟲ -90°", command=lambda: self.girar(-90)).pack(side="left")
        ttk.Button(rot, text="⟳ +90°", command=lambda: self.girar(90)).pack(side="left", padx=4)
        ttk.Button(rot, text="180°", command=lambda: self.girar(180)).pack(side="left")
        ttk.Button(rot, text="Restablecer", command=self.restablecer_angulo).pack(side="left", padx=8)

        ajuste = ttk.Frame(der); ajuste.pack(fill="x", padx=6, pady=(0, 8))
        ttk.Label(ajuste, text="Ángulo:").pack(side="left")
        self.angulo_var = tk.DoubleVar(value=0.0)
        self.slider = ttk.Scale(ajuste, from_=-180, to=180, orient="horizontal",
                                variable=self.angulo_var, command=self._al_mover_slider)
        self.slider.pack(side="left", fill="x", expand=True, padx=6)
        self.spin_angulo = ttk.Spinbox(ajuste, from_=-360, to=360, increment=0.5, width=7,
                                       textvariable=self.angulo_var, command=self._al_escribir_angulo)
        self.spin_angulo.pack(side="left")
        self.spin_angulo.bind("<Return>", lambda e: self._al_escribir_angulo())
        self.spin_angulo.bind("<FocusOut>", lambda e: self._al_escribir_angulo())
        ttk.Label(der, text="Gira el plano con los botones o la regla; así se exportará.")\
            .pack(anchor="w", padx=6, pady=(0, 6))

    # ---------- Lista de archivos ----------
    def _add(self, rutas):
        primero_nuevo = None
        for r in rutas:
            r = os.path.normpath(r)
            if r not in self.archivos:
                self.archivos.append(r)
                self.lista.insert("end", os.path.basename(r))
                if primero_nuevo is None:
                    primero_nuevo = len(self.archivos) - 1
        if primero_nuevo is not None and self.ruta_actual is None:
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(primero_nuevo)
            self.al_seleccionar()

    def agregar(self):
        self._add(filedialog.askopenfilenames(
            filetypes=[("Planos ECW/ERS/TIFF", "*.ecw *.ers *.tif *.tiff *.xml"), ("Todos", "*.*")]))

    def agregar_carpeta(self):
        d = filedialog.askdirectory()
        if d:
            self._add(os.path.join(d, n) for n in sorted(os.listdir(d))
                      if n.lower().endswith(EXTENSIONES))

    def quitar(self):
        for i in reversed(self.lista.curselection()):
            ruta = self.archivos[i]
            self.lista.delete(i)
            del self.archivos[i]
            self.angulos.pop(ruta, None)
            self.cache_base.pop(ruta, None)
            if self.ruta_actual == ruta:
                self.ruta_actual = None
                self.canvas.delete("all")

    def elegir_salida(self):
        d = filedialog.askdirectory()
        if d:
            self.salida.set(d)

    # ---------- Vista previa ----------
    def al_seleccionar(self, event=None):
        sel = self.lista.curselection()
        if not sel:
            return
        ruta = self.archivos[sel[-1]]
        self.ruta_actual = ruta
        self.angulo_var.set(self.angulos.get(ruta, 0.0))
        if ruta in self.cache_base:
            self.refrescar_preview()
        else:
            self.estado.config(text=f"Cargando vista previa: {os.path.basename(ruta)}...")
            threading.Thread(target=self._cargar_preview_bg, args=(ruta,), daemon=True).start()

    def _cargar_preview_bg(self, ruta):
        try:
            img = leer_imagen(ruta, LADO_PREVIEW)
        except Exception as e:
            msg = f"No se pudo leer {os.path.basename(ruta)}: {e}"
            self.after(0, lambda: self.estado.config(text=msg))
            return
        self.cache_base[ruta] = img
        if ruta == self.ruta_actual:
            self.after(0, self.refrescar_preview)
            self.after(0, lambda: self.estado.config(text="Listo"))

    def girar(self, delta):
        if self.ruta_actual is None:
            return
        actual = self.angulos.get(self.ruta_actual, 0.0)
        nuevo = (actual + delta + 180) % 360 - 180
        self.angulo_var.set(round(nuevo, 1))
        self._aplicar_angulo(nuevo)

    def restablecer_angulo(self):
        self.angulo_var.set(0.0)
        self._aplicar_angulo(0.0)

    def _al_mover_slider(self, valor):
        self._aplicar_angulo(round(float(valor), 1))

    def _al_escribir_angulo(self):
        try:
            v = float(str(self.angulo_var.get()).replace(",", "."))
        except (ValueError, tk.TclError):
            return
        self._aplicar_angulo(v)

    def _aplicar_angulo(self, valor):
        if self.ruta_actual is None:
            return
        self.angulos[self.ruta_actual] = valor
        self.refrescar_preview()

    def refrescar_preview(self):
        self.canvas.delete("all")
        ruta = self.ruta_actual
        if ruta is None or ruta not in self.cache_base:
            return
        base = self.cache_base[ruta]
        angulo = self.angulos.get(ruta, 0.0)
        img = rotar(base, angulo)
        if self.marca.get():
            img = marcar_dadep(img, self.esquina.get())
        img = marcar_autor(img, _ESQUINA_OPUESTA[self.esquina.get()])
        cw = max(self.canvas.winfo_width(), 50)
        ch = max(self.canvas.winfo_height(), 50)
        iw, ih = img.size
        k = min(cw / iw, ch / ih)
        mostrar = img.resize((max(1, int(iw * k)), max(1, int(ih * k))), Image.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(mostrar)
        self.canvas.create_image(cw // 2, ch // 2, image=self._preview_photo, anchor="center")

    # ---------- Conversión ----------
    def iniciar(self):
        if not self.archivos:
            return messagebox.showwarning("Aviso", "Agrega al menos un archivo.")
        if not self.salida.get():
            self.salida.set(os.path.dirname(self.archivos[0]))
        os.makedirs(self.salida.get(), exist_ok=True)
        self.btn.config(state="disabled")
        self.barra.config(maximum=len(self.archivos), value=0)
        args = (self.salida.get(), self.fmt.get(), self.cal.get(), self.dpi.get(),
                self.lado.get(), self.marca.get(), self.esquina.get())
        threading.Thread(target=self.trabajo, args=args, daemon=True).start()

    def trabajo(self, carpeta, formato, calidad, dpi, max_lado, marca, esquina):
        errores = []
        for i, r in enumerate(list(self.archivos), 1):
            self.after(0, self.estado.config,
                       {"text": f"Convirtiendo {i}/{len(self.archivos)}: {os.path.basename(r)}"})
            try:
                angulo = self.angulos.get(r, 0.0)
                convertir(r, carpeta, formato, angulo, calidad, dpi, max_lado, marca, esquina)
            except Exception as e:
                errores.append(f"{os.path.basename(r)}: {e}")
            self.after(0, self.barra.config, {"value": i})
        self.after(0, self.fin, errores)

    def fin(self, errores):
        self.btn.config(state="normal")
        self.estado.config(text="Terminado")
        if errores:
            messagebox.showwarning("Terminado con errores", "\n".join(errores[:10]))
        else:
            messagebox.showinfo("Listo", "Conversión completada.")


if __name__ == "__main__":
    app = App()
    if gdal.GetDriverByName("ECW") is None:
        messagebox.showwarning(
            "Aviso", "Este equipo no cargó el driver ECW: solo se podrán "
            "convertir archivos .ers con datos sin comprimir.")
    app.mainloop()
