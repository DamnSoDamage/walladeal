"""
Módulo de filtrado — filtra artículos por keywords y rango de precios.
"""

import logging

logger = logging.getLogger(__name__)


def filter_by_keywords(items: list[dict], keywords: list[str]) -> list[dict]:
    """
    Filtra artículos cuyo título contenga AL MENOS UNA de las keywords.
    Comparación case-insensitive.
    
    Args:
        items: Lista de artículos
        keywords: Lista de palabras clave a buscar en el título
    
    Returns:
        Lista de artículos que coinciden
    """
    if not keywords:
        return items

    keywords_lower = [kw.lower() for kw in keywords]
    filtered = []

    for item in items:
        title_lower = item.get("title", "").lower()
        if any(kw in title_lower for kw in keywords_lower):
            filtered.append(item)

    logger.debug(
        f"🏷️ Filtro keywords ({keywords}): {len(items)} → {len(filtered)} artículos"
    )
    return filtered


def filter_by_price(
    items: list[dict],
    min_price: float | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Filtra artículos dentro del rango de precio.
    Es una segunda capa de seguridad — la API ya filtra por precio,
    pero a veces no es 100% fiable.
    
    Args:
        items: Lista de artículos
        min_price: Precio mínimo (None = sin mínimo)
        max_price: Precio máximo (None = sin máximo)
    
    Returns:
        Lista de artículos dentro del rango
    """
    filtered = []

    for item in items:
        price = item.get("price", 0)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        filtered.append(item)

    logger.debug(
        f"💰 Filtro precio ({min_price}-{max_price}€): {len(items)} → {len(filtered)}"
    )
    return filtered


def filter_by_excluded_keywords(
    items: list[dict], excluded: list[str]
) -> list[dict]:
    """
    Excluye artículos cuyo título contenga alguna keyword de exclusión.
    Útil para descartar artículos que no son lo que buscas.
    
    Args:
        items: Lista de artículos
        excluded: Keywords de exclusión (ej: ["funda", "carcasa"])
    
    Returns:
        Lista de artículos que NO contienen ninguna keyword de exclusión
    """
    if not excluded:
        return items

    excluded_lower = [kw.lower() for kw in excluded]
    filtered = []

    for item in items:
        title_lower = item.get("title", "").lower()
        if not any(ex in title_lower for ex in excluded_lower):
            filtered.append(item)

    logger.debug(
        f"🚫 Filtro exclusión ({excluded}): {len(items)} → {len(filtered)}"
    )
    return filtered


def apply_filters(items: list[dict], search_config: dict) -> list[dict]:
    """
    Aplica todos los filtros configurados a la lista de artículos.
    
    Args:
        items: Lista de artículos del scraper
        search_config: Configuración de la búsqueda con keys:
            - keywords (list[str])
            - min_price (float|None)
            - max_price (float|None)
            - excluded_keywords (list[str])
    
    Returns:
        Lista de artículos filtrados
    """
    result = items

    # Filtro por keywords en título
    keywords = search_config.get("keywords", [])
    if keywords:
        result = filter_by_keywords(result, keywords)

    # Filtro por rango de precio (segunda capa)
    result = filter_by_price(
        result,
        min_price=search_config.get("min_price"),
        max_price=search_config.get("max_price"),
    )

    # Filtro de exclusión
    excluded = search_config.get("excluded_keywords", [])
    if excluded:
        result = filter_by_excluded_keywords(result, excluded)

    logger.info(
        f"✅ Filtros aplicados: {len(items)} → {len(result)} artículos"
    )
    return result
