"""
Product & Price Web Scraper  |  github.com/irvintorres074
Extrae nombres de productos y precios de cualquier tienda online y los guarda en CSV.

Uso:
  python scraper.py <url> [opciones]

Opciones:
  --config  config.json   Selectores CSS personalizados
  --output  archivo.csv   Nombre del archivo de salida
  --pages   N             Número máximo de páginas a recorrer (paginación)
  --delay   segundos      Pausa entre requests (default: 1.0)
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------

VERSION = "1.2.0"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}

# Selectores de "siguiente página" comunes en tiendas online
NEXT_PAGE_SELECTORS = [
    "a[rel='next']",
    "li.next > a",
    ".pagination .next a",
    ".next-page a",
    "a.next",
    "[aria-label='Next page']",
    "[aria-label='Siguiente']",
]

# Estrategias de extracción intentadas en orden (la primera que devuelva datos gana)
FALLBACK_SELECTORS = [
    # schema.org JSON-LD (el más confiable y estructurado)
    {"type": "json_ld"},
    # Open Graph / meta tags (páginas de producto individual)
    {"type": "meta"},
    # Selectores CSS — de específico a genérico
    {"container": "li.product",           "name": ".woocommerce-loop-product__title", "price": ".price .woocommerce-Price-amount"},
    {"container": ".grid-product",        "name": ".grid-product__title",             "price": ".grid-product__price"},
    {"container": "article.product_pod",  "name": "h3 a",                             "price": ".price_color"},
    {"container": ".product-item",        "name": ".product-title,.product-name,.item-title", "price": ".price,.product-price,.item-price"},
    {"container": ".product",             "name": "h2,h3,.name",                      "price": ".price,.amount"},
    {"container": "[data-product-id]",    "name": ".title,.name",                     "price": ".price"},
    {"container": ".item",                "name": ".name,.title",                     "price": ".price"},
    {"container": "article",              "name": "h2 a,h3 a,h4 a",                  "price": ".price,.price_color,.amount"},
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def log(msg: str, level: str = "INFO"):
    prefix = {"INFO": "  ", "OK": "  ✓", "WARN": "  !", "ERR": "  ✗"}.get(level, "  ")
    print(f"{prefix} {msg}")


def clean_price(text: str) -> str:
    """Extrae el primer valor numérico con decimales del texto."""
    text = text.strip().replace(" ", "").replace(" ", "")
    match = re.search(r"[\d]+[.,]?\d*", text)
    if not match:
        return text
    return match.group(0).replace(",", ".")


def _get_text(el, attr: str | None = None) -> str:
    """Lee texto de un elemento, priorizando el atributo title sobre texto truncado."""
    if el is None:
        return ""
    if attr:
        return el.get(attr, "").strip()
    if el.get("title"):
        return el["title"].strip()
    inner = el.select_one("a[title]")
    if inner:
        return inner["title"].strip()
    return el.get_text(" ", strip=True)


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Descarga de páginas
# ---------------------------------------------------------------------------

def fetch_page(url: str, session: requests.Session) -> BeautifulSoup:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def find_next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    """Busca el enlace a la siguiente página con múltiples selectores."""
    for sel in NEXT_PAGE_SELECTORS:
        tag = soup.select_one(sel)
        if tag and tag.get("href"):
            return urljoin(current_url, tag["href"])
    return None


# ---------------------------------------------------------------------------
# Estrategias de extracción
# ---------------------------------------------------------------------------

def scrape_json_ld(soup: BeautifulSoup) -> list[dict]:
    products = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            tipo = item.get("@type", "")
            if tipo == "Product":
                _append_ld_product(item, products)
            elif tipo == "ItemList":
                for elem in item.get("itemListElement", []):
                    _append_ld_product(elem.get("item", elem), products)
    return products


def _append_ld_product(item: dict, out: list):
    name = item.get("name", "").strip()
    if not name:
        return
    offers = item.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    out.append({
        "nombre":  name,
        "precio":  str(offers.get("price", "")).strip(),
        "moneda":  offers.get("priceCurrency", ""),
        "url":     item.get("url", ""),
    })


def scrape_meta(soup: BeautifulSoup, page_url: str) -> list[dict]:
    name_tag     = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
    price_tag    = soup.find("meta", property="product:price:amount")
    currency_tag = soup.find("meta", property="product:price:currency")
    if name_tag and price_tag:
        return [{
            "nombre": name_tag.get("content", "").strip(),
            "precio": price_tag.get("content", "").strip(),
            "moneda": currency_tag.get("content", "") if currency_tag else "",
            "url":    page_url,
        }]
    return []


def scrape_css(soup: BeautifulSoup, selector: dict, page_url: str) -> list[dict]:
    container_sel = selector.get("container", "")
    name_sel      = selector.get("name", "")
    price_sel     = selector.get("price", "")
    name_attr     = selector.get("name_attr")
    price_attr    = selector.get("price_attr")

    containers = soup.select(container_sel) if container_sel else [soup]
    products = []
    for container in containers:
        name_el  = container.select_one(name_sel)  if name_sel  else None
        price_el = container.select_one(price_sel) if price_sel else None
        name  = _get_text(name_el,  name_attr)
        price = _get_text(price_el, price_attr)
        if name or price:
            products.append({
                "nombre": name,
                "precio": clean_price(price) if price else "",
                "moneda": "",
                "url":    page_url,
            })
    return products


def extract_products(soup: BeautifulSoup, url: str, config: dict | None) -> list[dict]:
    """Aplica la estrategia correcta según config o prueba todas en orden."""
    if config:
        sel_type = config.get("type")
        if sel_type == "json_ld":
            return scrape_json_ld(soup)
        if sel_type == "meta":
            return scrape_meta(soup, url)
        return scrape_css(soup, config, url)

    for sel in FALLBACK_SELECTORS:
        if sel.get("type") == "json_ld":
            products = scrape_json_ld(soup)
        elif sel.get("type") == "meta":
            products = scrape_meta(soup, url)
        else:
            products = scrape_css(soup, sel, url)
        if products:
            return products
    return []


# ---------------------------------------------------------------------------
# Motor de scraping con paginación
# ---------------------------------------------------------------------------

def scrape_site(
    start_url: str,
    config: dict | None,
    session: requests.Session,
    max_pages: int = 1,
    delay: float = 1.0,
) -> list[dict]:
    all_products: list[dict] = []
    url = start_url
    page_num = 0

    while url and page_num < max_pages:
        page_num += 1
        log(f"Página {page_num}/{max_pages}: {url}")

        try:
            soup = fetch_page(url, session)
        except requests.HTTPError as e:
            log(f"HTTP {e.response.status_code} — omitiendo esta página", "ERR")
            break
        except Exception as e:
            log(f"{e}", "ERR")
            break

        products = extract_products(soup, url, config)
        log(f"Productos encontrados: {len(products)}", "OK" if products else "WARN")
        all_products.extend(products)

        next_url = find_next_page(soup, url) if page_num < max_pages else None
        url = next_url

        if url:
            time.sleep(delay)

    return all_products


# ---------------------------------------------------------------------------
# Salida CSV
# ---------------------------------------------------------------------------

def save_csv(products: list[dict], output: str):
    fieldnames = ["nombre", "precio", "moneda", "url"]
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    log(f"CSV guardado → {output}  ({len(products)} filas)", "OK")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_output_name(url: str) -> str:
    domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
    stamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"productos_{domain}_{stamp}.csv"


def main():
    parser = argparse.ArgumentParser(
        prog="scraper",
        description=f"Web Scraper de Productos y Precios v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python scraper.py https://tienda.com/productos\n"
            "  python scraper.py https://tienda.com --pages 5 --delay 2\n"
            "  python scraper.py https://tienda.com --config configs/woocommerce.json\n"
        ),
    )
    parser.add_argument("urls",    nargs="+", help="URL(s) de inicio")
    parser.add_argument("--config",           help="Archivo JSON con selectores CSS personalizados")
    parser.add_argument("--output", default="", help="Nombre del CSV de salida (auto si se omite)")
    parser.add_argument("--pages",  type=int, default=1,   help="Páginas máximas por URL (default: 1)")
    parser.add_argument("--delay",  type=float, default=1.0, help="Segundos entre requests (default: 1)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else None
    output = args.output or build_output_name(args.urls[0])

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    print(f"\n  Web Scraper de Productos v{VERSION}")
    print(f"  {'─' * 40}")

    all_products: list[dict] = []
    for url in args.urls:
        products = scrape_site(url, config, session, args.pages, args.delay)
        all_products.extend(products)

    print(f"  {'─' * 40}")

    if all_products:
        save_csv(all_products, output)
    else:
        log("No se encontraron productos.", "WARN")
        log("Consejo: usa --config con selectores CSS del inspector de tu navegador.", "INFO")
        sys.exit(1)


if __name__ == "__main__":
    main()
