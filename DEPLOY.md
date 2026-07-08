# Kiosko POS — Guía de instalación y actualización

Guía práctica para (1) instalar el sistema en la PC del local y (2) publicar
actualizaciones desde casa.

---

## 1. Qué es y cómo está armado

- **App de escritorio liviana** (Python + CustomTkinter), empaquetada en un único
  `Kiosko.exe` (~30 MB, ~68 MB de RAM en uso).
- **Base local SQLite** (`data/kiosko.db`): la caja lee y escribe siempre acá,
  así funciona **sin internet** (offline-first).
- **Base central Neon (PostgreSQL)**: respaldo en la nube. Un hilo en segundo
  plano sube ventas/compras/gastos/cuentas y baja precios, cada ~60 segundos,
  cuando hay conexión.

---

## 2. Instalación en la PC del local (primera vez)

> No requiere instalar Python ni nada: es un solo `.exe`.

1. **Crear una carpeta** para la app, por ejemplo `C:\Kiosko\`.
2. **Copiar `Kiosko.exe`** ahí dentro.
3. **Crear el archivo `.env`** en la misma carpeta (`C:\Kiosko\.env`) con una
   línea con la conexión a Neon:
   ```
   NEON_DATABASE_URL=postgresql://usuario:password@ep-xxxx.neon.tech/kiosko?sslmode=require
   ```
   > El `.env` es lo único que hay que configurar. Sin él, la app igual funciona
   > offline pero no sincroniza con la nube.
4. **Doble clic en `Kiosko.exe`.** La primera vez crea sola `C:\Kiosko\data\kiosko.db`.

La carpeta queda así:
```
C:\Kiosko\
├── Kiosko.exe          (el programa — se reemplaza al actualizar)
├── .env                (configuración — NO se toca al actualizar)
└── data\
    └── kiosko.db       (los datos — NO se tocan al actualizar)
```

### Opcionales útiles
- **Acceso directo en el escritorio**: clic derecho sobre `Kiosko.exe` →
  *Enviar a* → *Escritorio*.
- **Que arranque solo con Windows**: copiar un acceso directo del `.exe` en la
  carpeta que se abre con `Win+R` → `shell:startup`.

### Si Windows muestra una advertencia al abrir
Como el `.exe` no está firmado digitalmente, Windows SmartScreen puede mostrar
*"Windows protegió su PC"*. Es normal: clic en **Más información → Ejecutar de
todas formas**. (Algún antivirus también puede marcar falsos positivos con
ejecutables de PyInstaller; agregar la carpeta como excepción si pasa.)

---

## 3. Primer uso (orden recomendado)

1. **Proveedores** → *Nuevo proveedor*: cargá tus proveedores.
2. **Stock** → *Nuevo producto*, o directamente *Recibir remito* (da de alta el
   stock y el costo de una sola vez al escanear).
3. **Caja**: pasá productos con la pistolita y cobrá.

---

## 4. Publicar una actualización (desde tu casa)

El sistema se actualiza desde **GitHub Releases** del repo
`Alan934/sistema-comercio` (público).

### Requisitos en tu PC de desarrollo (una sola vez)
```powershell
pip install -r requirements.txt          # dependencias de la app
pip install -r requirements-build.txt    # PyInstaller (para compilar)
```

### Pasos para sacar una versión nueva
1. Hacé tus cambios en el código.
2. **Subí el número de versión** en `config/settings.py`:
   ```python
   APP_VERSION = "0.2.0"   # antes estaba en "0.1.0"
   ```
3. **Compilá**:
   ```powershell
   python build.py
   ```
   Genera `dist/Kiosko.exe`.
4. **Publicá en GitHub**: repo → *Releases* → *Draft a new release*:
   - **Tag**: `v0.2.0` (igual que `APP_VERSION`, con la `v` adelante).
   - Adjuntá el archivo **`Kiosko.exe`** generado.
   - *Publish release*.

> **Regla de oro del versionado**: el `.exe` que corre en el local detecta la
> actualización solo si el tag publicado es un número **mayor** al que tiene
> embebido. Por eso siempre hay que subir `APP_VERSION` antes de compilar y usar
> ese mismo número como tag.

### Cómo actualiza la chica del local
1. Hace clic en **"Buscar actualización"** (abajo a la izquierda).
2. Si hay versión nueva, confirma. La app se descarga la versión, **se cierra,
   se reemplaza sola y se vuelve a abrir** ya actualizada.
3. Los datos y la configuración **no se pierden** (viven fuera del `.exe`).

> Solo necesita internet en el momento de actualizar. El resto del tiempo puede
> trabajar offline.

---

## 5. Actualizar precios (sin tocar el programa)

Cambiar precios **no requiere** una versión nueva del `.exe`. Editás los precios
en la base Neon y el local los baja solo en la próxima sincronización. El stock
se maneja en el local (las ventas lo descuentan); la sincronización de precios
nunca lo pisa.

---

## 6. Datos y respaldo

- Los datos viven en `data\kiosko.db` (al lado del `.exe`).
- **Backup manual**: copiar ese archivo `kiosko.db` (idealmente con la app
  cerrada) a un pendrive o carpeta.
- Además, todo lo operativo se respalda en **Neon** automáticamente cuando hay
  internet, así que ante una falla del disco no se pierde la información subida.

---

## 7. Problemas comunes

| Síntoma | Causa / solución |
|---|---|
| "Windows protegió su PC" al abrir | Normal (exe sin firmar): *Más información → Ejecutar de todas formas*. |
| No sincroniza | Revisar internet y que el `.env` tenga bien `NEON_DATABASE_URL`. Igual sigue vendiendo offline. |
| "Buscar actualización" dice límite alcanzado | GitHub limita consultas anónimas (60/hora por IP). Esperar un rato. |
| Quiero empezar de cero | Cerrar la app y borrar `data\kiosko.db`. Al reabrir se crea vacía. |
| Mover la app a otra PC | Copiar toda la carpeta `C:\Kiosko\` (exe + .env + data). |

---

## 8. Comandos útiles (desarrollo)

```powershell
python main.py                       # correr la app desde el código
python build.py                      # compilar el .exe
python release.py                    # publicar una versión nueva en GitHub
python demo_pos.py                   # probar el motor de ventas (consola)
python demo_stock.py                 # probar stock/compras/proveedores
python demo_reportes.py              # probar reportes + gastos
python demo_sync.py                  # probar sincronización con Neon
```
