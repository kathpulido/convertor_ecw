# -*- coding: utf-8 -*-
"""Conversor de planos ECW / ERS (y .ecw.aux.xml) a PDF o JPG.
Permite rotar el plano interactivamente (vista previa en vivo) antes de
exportar, y agrega una marca pequeña "DADEP" en una esquina."""
import os, sys, threading, tkinter as tk
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
LADO_PREVIEW = 1200  # resolución de la vista previa (rápida); la exportación usa "Lado máx."


def resolver_entrada(ruta):
    """Si el usuario elige un .ecw.aux.xml, usa el .ecw hermano."""
    low = ruta.lower()
    if low.endswith(".ecw.aux.xml"):
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


def marcar_dadep(img, esquina, texto="DADEP"):
    """Dibuja el nombre 'DADEP' pequeño en una esquina, legible sobre cualquier fondo."""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    lado_menor = min(img.size)
    tam = max(10, int(lado_menor * 0.02))
    try:
        font = ImageFont.load_default(size=tam)
    except TypeError:
        font = ImageFont.load_default()
    grosor = max(1, tam // 8)
    bbox = draw.textbbox((0, 0), texto, font=font, stroke_width=grosor)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margen = max(6, int(lado_menor * 0.012))
    W, H = img.size
    if esquina == "Inferior derecha":
        xy = (W - margen - tw - bbox[0], H - margen - th - bbox[1])
    elif esquina == "Inferior izquierda":
        xy = (margen - bbox[0], H - margen - th - bbox[1])
    elif esquina == "Superior derecha":
        xy = (W - margen - tw - bbox[0], margen - bbox[1])
    else:
        xy = (margen - bbox[0], margen - bbox[1])
    draw.text(xy, texto, font=font, fill="white", stroke_width=grosor, stroke_fill="black")
    return img


def convertir(ruta, carpeta, formato, angulo, calidad, dpi, max_lado, marca, esquina):
    img = leer_imagen(ruta, max_lado)
    img = rotar(img, angulo)
    if marca:
        img = marcar_dadep(img, esquina)
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

        ttk.Label(izq, text="Archivos (.ecw, .ers, .ecw.aux.xml):").pack(anchor="w")
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
        ttk.Checkbutton(o, text="Agregar marca 'DADEP'", variable=self.marca,
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
            filetypes=[("Planos ECW/ERS", "*.ecw *.ers *.xml"), ("Todos", "*.*")]))

    def agregar_carpeta(self):
        d = filedialog.askdirectory()
        if d:
            self._add(os.path.join(d, n) for n in sorted(os.listdir(d))
                      if n.lower().endswith((".ecw", ".ers")))

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
