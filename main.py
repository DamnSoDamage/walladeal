"""
WallaDeal — Scraper de Wallapop con alertas de chollos.

Punto de entrada principal. Carga la configuración, ejecuta las búsquedas,
filtra resultados, detecta artículos nuevos y envía notificaciones.
"""

import os
import sys
import yaml
import logging
from src.scraper import search_items
from src.filters import apply_filters
from src.tracker import ItemTracker
from src.notifier import notify_all


def setup_logging(level: str = "INFO"):
    """Configura el logging con formato bonito."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_config() -> dict:
    """
    Carga la configuración desde config.yaml + variables de entorno.
    Las variables de entorno tienen prioridad sobre el YAML.
    """
    config_path = os.environ.get("WALLADEAL_CONFIG", "config.yaml")

    # Cargar YAML
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Sobreescribir con variables de entorno
    notifications = config.setdefault("notifications", {})
    
    # ntfy
    ntfy = notifications.setdefault("ntfy", {})
    if os.environ.get("NTFY_TOPIC"):
        ntfy["topic"] = os.environ["NTFY_TOPIC"]
        ntfy["enabled"] = True
    if os.environ.get("NTFY_SERVER"):
        ntfy["server"] = os.environ["NTFY_SERVER"]

    # Telegram
    telegram = notifications.setdefault("telegram", {})
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        telegram["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
        telegram["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
        telegram["enabled"] = True

    # Búsquedas desde env (para uso simple con GitHub Actions)
    if os.environ.get("WALLADEAL_SEARCHES"):
        searches_yaml = os.environ["WALLADEAL_SEARCHES"]
        config["searches"] = yaml.safe_load(searches_yaml)

    # Settings
    settings = config.setdefault("settings", {})
    if os.environ.get("LOG_LEVEL"):
        settings["log_level"] = os.environ["LOG_LEVEL"]

    return config


def run():
    """Ejecuta el ciclo completo de scraping + notificaciones."""
    config = load_config()
    settings = config.get("settings", {})
    
    setup_logging(settings.get("log_level", "INFO"))
    logger = logging.getLogger(__name__)

    searches = config.get("searches", [])
    if not searches:
        logger.error("❌ No hay búsquedas configuradas. Revisa config.yaml")
        sys.exit(1)

    notifications_config = config.get("notifications", {})
    seen_file = settings.get("seen_file", "seen_items.json")
    notify_first = settings.get("notify_on_first_run", False)

    # Cargar tracker
    tracker = ItemTracker(filepath=seen_file)
    is_first_run = tracker.is_first_run

    total_new = 0
    total_notified = 0

    logger.info("=" * 50)
    logger.info("🚀 WallaDeal — Iniciando scraping")
    logger.info("=" * 50)

    for search in searches:
        name = search.get("name", "Sin nombre")
        logger.info(f"\n{'─' * 40}")
        logger.info(f"🔎 Búsqueda: {name}")
        logger.info(f"{'─' * 40}")

        # 1. Scraping
        raw_items = search_items(
            keywords=" ".join(search.get("keywords", [])),
            latitude=search.get("latitude", 40.4168),
            longitude=search.get("longitude", -3.7038),
            distance=search.get("distance", 50000),
            min_price=search.get("min_price"),
            max_price=search.get("max_price"),
            category_ids=search.get("category_ids"),
        )

        if not raw_items:
            logger.info("📭 Sin resultados del API")
            continue

        # 2. Filtrar
        filtered_items = apply_filters(raw_items, search)

        if not filtered_items:
            logger.info("📭 Sin artículos tras filtros")
            continue

        # 3. Detectar nuevos
        new_items = tracker.get_new_items(filtered_items)

        # Marcar como vistos (incluyendo los que ya se conocían)
        tracker.mark_as_seen(filtered_items)

        if not new_items:
            logger.info("📭 Todos los artículos ya eran conocidos")
            continue

        total_new += len(new_items)

        # 4. Notificar
        if is_first_run and not notify_first:
            logger.info(
                f"🔇 Primera ejecución — guardando {len(new_items)} artículos sin notificar"
            )
        else:
            # Log de artículos nuevos
            for item in new_items:
                logger.info(
                    f"  🆕 {item['price']}€ — {item['title'][:60]}"
                )

            stats = notify_all(new_items, notifications_config, search_name=name)
            total_notified += stats.get("ntfy_sent", 0) + stats.get("telegram_sent", 0)

    # Guardar estado
    tracker.save()

    logger.info(f"\n{'=' * 50}")
    logger.info(
        f"✅ Completado: {total_new} nuevos, {total_notified} notificaciones enviadas"
    )
    logger.info(f"{'=' * 50}")


if __name__ == "__main__":
    run()
