"""
Módulo scraper — scraping de Wallapop con Playwright.

Usa Playwright (sync API) para abrir la web de Wallapop en un navegador
headless, navegar a la página de búsqueda y extraer los artículos del DOM.
"""

import re
import json
import logging
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
from playwright_stealth import stealth_sync

logger = logging.getLogger(__name__)

WALLAPOP_BASE = "https://es.wallapop.com"
SEARCH_URL = f"{WALLAPOP_BASE}/search"

# Selectores CSS (usan *= para evitar depender de hashes de CSS modules)
CARD_SELECTOR = 'a[class*="ItemCard"]'
COOKIE_ACCEPT_SELECTOR = "#onetrust-accept-btn-handler"


def _build_search_url(
    keywords: str,
    latitude: float,
    longitude: float,
    distance_km: int,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    order_by: str = "newest",
) -> str:
    """Construye la URL de búsqueda de Wallapop."""
    params = {
        "keywords": keywords,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "distance_in_km": str(distance_km),
        "order_by": order_by,
    }
    if min_price is not None:
        params["min_sale_price"] = str(min_price)
    if max_price is not None:
        params["max_sale_price"] = str(max_price)

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{SEARCH_URL}?{query}"


def _parse_price(price_text: str) -> tuple[float, str]:
    """
    Extrae precio numérico y moneda de un texto como '190 €' o '50,50€'.
    """
    cleaned = price_text.strip().replace("\xa0", " ")
    match = re.search(r"([\d.,]+)", cleaned)
    if match:
        num_str = match.group(1).replace(".", "").replace(",", ".")
        price = float(num_str)
    else:
        price = 0.0

    currency = "EUR"
    if "€" in cleaned:
        currency = "EUR"
    elif "$" in cleaned:
        currency = "USD"
    elif "£" in cleaned:
        currency = "GBP"

    return price, currency


def _extract_id_from_href(href: str) -> str:
    """
    Extrae un ID del href del artículo.
    Los hrefs tienen formato: /item/slug-texto-123456789
    El número al final es el ID.
    """
    match = re.search(r"-(\d{5,})$", href)
    if match:
        return match.group(1)
    # Fallback: usar todo el slug como ID
    slug = href.rstrip("/").split("/")[-1]
    return slug


def _scrape_from_dom(page) -> list[dict]:
    """Extrae artículos directamente de las tarjetas del DOM."""
    items = []

    cards = page.query_selector_all(CARD_SELECTOR)
    logger.debug(f"🃏 {len(cards)} tarjetas encontradas en el DOM")

    for card in cards:
        try:
            # Título
            h3 = card.query_selector("h3")
            title = h3.inner_text().strip() if h3 else "Sin título"

            # Precio
            strong = card.query_selector("strong")
            price_text = strong.inner_text().strip() if strong else "0"
            price, currency = _parse_price(price_text)

            # URL
            href = card.get_attribute("href") or ""
            if href.startswith("/"):
                url = f"{WALLAPOP_BASE}{href}"
            elif href.startswith("http"):
                url = href
            else:
                url = ""

            # ID
            item_id = _extract_id_from_href(href) if href else ""

            # Imagen
            images = []
            img = card.query_selector("img")
            if img:
                src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                if src and not src.startswith("data:"):
                    images.append(src)

            if not item_id:
                continue

            items.append({
                "id": item_id,
                "title": title,
                "price": price,
                "currency": currency,
                "url": url,
                "description": "",  # No disponible en la lista de búsqueda
                "images": images,
                "timestamp": "",
            })
        except Exception as e:
            logger.warning(f"⚠️ Error parseando tarjeta: {e}")
            continue

    return items


def _scrape_from_next_data(page) -> list[dict]:
    """
    Fallback: intenta extraer datos del JSON embebido en __NEXT_DATA__.
    Wallapop usa Next.js y a veces incluye los resultados en el HTML inicial.
    """
    try:
        script = page.query_selector('script#__NEXT_DATA__')
        if not script:
            return []

        raw = script.inner_text()
        data = json.loads(raw)

        # Navegar la estructura de Next.js
        page_props = data.get("props", {}).get("pageProps", {})

        # Buscar los items en varias rutas posibles
        search_items_data = None
        for key in ("searchItems", "items", "results"):
            if key in page_props:
                search_items_data = page_props[key]
                break

        # Intentar ruta más profunda
        if not search_items_data:
            initial_data = page_props.get("initialData", {})
            for key in ("searchItems", "items", "results"):
                if key in initial_data:
                    search_items_data = initial_data[key]
                    break

        if not search_items_data:
            return []

        # Si es un dict con una clave 'items' anidada
        if isinstance(search_items_data, dict) and "items" in search_items_data:
            search_items_data = search_items_data["items"]

        items = []
        for obj in search_items_data:
            if not isinstance(obj, dict):
                continue
            item = _parse_next_data_item(obj)
            if item:
                items.append(item)

        logger.info(f"📦 {len(items)} artículos extraídos de __NEXT_DATA__")
        return items

    except Exception as e:
        logger.debug(f"⚠️ Error extrayendo __NEXT_DATA__: {e}")
        return []


def _parse_next_data_item(obj: dict) -> Optional[dict]:
    """Parsea un artículo del JSON de __NEXT_DATA__."""
    try:
        item_id = str(obj.get("id", ""))
        title = obj.get("title", obj.get("name", "Sin título"))

        # Precio
        price_raw = obj.get("price", 0)
        if isinstance(price_raw, dict):
            price = float(price_raw.get("amount", 0))
            currency = price_raw.get("currency", "EUR")
        else:
            price = float(price_raw) if price_raw else 0
            currency = obj.get("currency", "EUR")

        description = obj.get("description", "")

        # URL
        web_slug = obj.get("web_slug", obj.get("slug", ""))
        url = f"{WALLAPOP_BASE}/item/{web_slug}" if web_slug else ""

        # Imágenes
        images = []
        for img in obj.get("images", []):
            if isinstance(img, str):
                images.append(img)
            elif isinstance(img, dict):
                img_url = (
                    img.get("original", "")
                    or img.get("urls", {}).get("big", "")
                    or img.get("medium", "")
                    or img.get("small", "")
                    or img.get("url", "")
                )
                if img_url:
                    images.append(img_url)

        # Timestamp
        timestamp = obj.get("created_at", obj.get("creation_date", ""))
        if isinstance(timestamp, (int, float)) and timestamp > 1000000000:
            from datetime import datetime, timezone
            timestamp = datetime.fromtimestamp(
                timestamp / 1000, tz=timezone.utc
            ).isoformat()

        if not item_id:
            return None

        return {
            "id": item_id,
            "title": title,
            "price": price,
            "currency": currency,
            "url": url,
            "description": description,
            "images": images,
            "timestamp": str(timestamp),
        }
    except Exception as e:
        logger.warning(f"⚠️ Error parseando item __NEXT_DATA__: {e}")
        return None


def search_items(
    keywords: str,
    latitude: float = 40.4168,
    longitude: float = -3.7038,
    distance: int = 50000,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    category_ids: Optional[str] = None,
    order_by: str = "newest",
) -> list[dict]:
    """
    Busca artículos en Wallapop usando Playwright.

    Args:
        keywords: Términos de búsqueda
        latitude/longitude: Centro de la búsqueda
        distance: Radio en metros (se convierte a km internamente)
        min_price/max_price: Rango de precios en euros
        category_ids: IDs de categorías (no usado actualmente)
        order_by: Orden de resultados

    Returns:
        Lista de dicts con {id, title, price, currency, url, description, images, timestamp}
    """
    distance_km = distance // 1000 if distance > 1000 else distance

    search_url = _build_search_url(
        keywords, latitude, longitude, distance_km, min_price, max_price, order_by
    )

    logger.info(f"🔍 Buscando: '{keywords}' (precio: {min_price}-{max_price}€)")
    logger.debug(f"🌐 URL: {search_url}")

    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
        )
        page = context.new_page()
        stealth_sync(page)

        try:
            # Navegar a la página de búsqueda
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            # Cerrar banner de cookies si aparece
            try:
                cookie_btn = page.wait_for_selector(
                    COOKIE_ACCEPT_SELECTOR, timeout=5000
                )
                if cookie_btn:
                    cookie_btn.click()
                    logger.debug("🍪 Banner de cookies cerrado")
            except PwTimeout:
                pass  # No hay banner de cookies

            # Esperar a que carguen las tarjetas de producto
            try:
                page.wait_for_selector(CARD_SELECTOR, timeout=15000)
            except PwTimeout:
                logger.warning("⚠️ Timeout esperando tarjetas de producto")

            # Scroll lento para cargar imágenes lazy-loaded
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(1000)

            # 1. Intentar extraer del DOM
            items = _scrape_from_dom(page)

            # 2. Fallback: __NEXT_DATA__
            if not items:
                logger.info("🔄 DOM sin resultados, intentando __NEXT_DATA__...")
                items = _scrape_from_next_data(page)

            logger.info(f"📦 {len(items)} artículos encontrados")

            if not items:
                # Tomar captura para depurar por qué no cargó nada
                page.screenshot(path="debug_wallapop.png")
                logger.info("📸 Captura de pantalla guardada en debug_wallapop.png")

        except Exception as e:
            logger.error(f"❌ Error durante el scraping: {e}")
            try:
                page.screenshot(path="debug_wallapop.png")
            except:
                pass
        finally:
            browser.close()

    return items
