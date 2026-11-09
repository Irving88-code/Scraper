# Web Scraper de Productos y Precios

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![License](https://img.shields.io/badge/Licencia-MIT-green)
![Version](https://img.shields.io/badge/Versión-1.2.0-orange)

Herramienta de línea de comandos que extrae **nombres de productos y precios** de cualquier tienda online y los exporta a un archivo **CSV** listo para analizar en Excel, Google Sheets o cualquier herramienta de datos.

---

## Características

- Detección automática de productos sin configuración previa
- **Paginación automática** — recorre múltiples páginas con un solo comando
- Soporte para **WooCommerce**, **Shopify** y sitios personalizados
- Tres estrategias de extracción: JSON-LD (schema.org), Open Graph y selectores CSS
- Delay configurable entre requests para no sobrecargar el servidor
- Salida CSV compatible con Excel (codificación UTF-8 con BOM)
- Scraping de múltiples URLs en un solo comando

---

## Tecnologías utilizadas

| Librería | Rol |
|---|---|
| `requests` | Descarga de páginas HTML |
| `BeautifulSoup4` | Parsing y extracción de datos |
| `lxml` | Parser HTML de alto rendimiento |
| `csv` (stdlib) | Escritura del archivo de salida |

---

## Instalación

```bash
# 1. Clona o descarga el proyecto
cd scraper

# 2. Instala las dependencias
pip install -r requirements.txt
```

**Requisitos:** Python 3.11 o superior.

---

## Uso

### Básico — detección automática

```bash
python scraper.py https://tienda.com/productos
```

### Con paginación

```bash
python scraper.py https://tienda.com/categoria --pages 10
```

### Con configuración personalizada

```bash
python scraper.py https://tienda.com --config configs/woocommerce.json
```

### Varias URLs a la vez

```bash
python scraper.py https://tienda.com/ropa https://tienda.com/zapatos --output catalogo.csv
```

### Todas las opciones

```
python scraper.py --help

opciones:
  --config   Archivo JSON con selectores CSS (ver carpeta configs/)
  --output   Nombre del CSV de salida (auto-generado si se omite)
  --pages    Páginas máximas a recorrer por URL  [default: 1]
  --delay    Segundos de espera entre requests   [default: 1.0]
  --version  Muestra la versión
```

---

## Configuración de selectores

Cuando la detección automática no funciona, crea tu propio `config.json` con los selectores CSS del sitio objetivo:

```json
{
  "container": ".product-card",
  "name":      ".product-title",
  "price":     ".product-price"
}
```

**¿Cómo encontrar los selectores?**
1. Abre el sitio en Chrome/Firefox
2. Clic derecho sobre un producto → **Inspeccionar**
3. Identifica la clase CSS del contenedor, nombre y precio
4. Escríbelos en el JSON

La carpeta `configs/` incluye plantillas listas para:

| Archivo | Plataforma |
|---|---|
| `woocommerce.json` | WordPress + WooCommerce |
| `shopify.json` | Shopify |
| `json_ld.json` | Cualquier sitio con schema.org |
| `personalizado.json` | Plantilla en blanco para editar |

---

## Formato de salida

El CSV generado contiene cuatro columnas:

| nombre | precio | moneda | url |
|---|---|---|---|
| A Light in the Attic | 51.77 | | https://... |
| Tipping the Velvet | 53.74 | | https://... |
| Sapiens | 54.23 | GBP | https://... |

- `moneda` se rellena cuando el sitio usa JSON-LD o meta tags de producto.
- `url` corresponde a la página donde se encontró el producto.

---

## Ejemplo de ejecución

```
$ python scraper.py https://books.toscrape.com/ --pages 3

  Web Scraper de Productos v1.2.0
  ────────────────────────────────────────
   Página 1/3: https://books.toscrape.com/
  ✓ Productos encontrados: 20
   Página 2/3: https://books.toscrape.com/catalogue/page-2.html
  ✓ Productos encontrados: 20
   Página 3/3: https://books.toscrape.com/catalogue/page-3.html
  ✓ Productos encontrados: 20
  ────────────────────────────────────────
  ✓ CSV guardado → productos_books_20241103_120000.csv  (60 filas)
```

El archivo `sample_output/libros_ejemplo.csv` incluye una muestra real de 60 registros generada con este comando.

---

## Estructura del proyecto

```
scraper/
├── scraper.py              # Script principal
├── requirements.txt        # Dependencias pip
├── configs/
│   ├── woocommerce.json    # Selectores WooCommerce
│   ├── shopify.json        # Selectores Shopify
│   ├── json_ld.json        # Extracción por schema.org
│   └── personalizado.json  # Plantilla editable
└── sample_output/
    └── libros_ejemplo.csv  # Salida de ejemplo (60 productos)
```

---

## Notas de uso responsable

- Respeta el archivo `robots.txt` del sitio objetivo.
- Usa `--delay` para no generar carga excesiva en el servidor.
- Este proyecto es para uso educativo y análisis de datos propios o públicamente accesibles.

---

## Licencia

MIT — libre de usar, modificar y distribuir.
