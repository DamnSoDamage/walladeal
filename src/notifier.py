"""
Módulo de notificaciones — envía alertas a ntfy y/o Telegram.
"""

import requests
import logging

logger = logging.getLogger(__name__)


def send_ntfy(
    item: dict,
    topic: str,
    server: str = "https://ntfy.sh",
    search_name: str = "",
) -> bool:
    """
    Envía una notificación a ntfy.sh con los datos del artículo.
    
    Args:
        item: Dict del artículo {title, price, url, ...}
        topic: Nombre del topic de ntfy (tu canal secreto)
        server: URL del servidor ntfy (por defecto el público)
        search_name: Nombre de la búsqueda para contexto
    
    Returns:
        True si se envió correctamente
    """
    title = item.get("title", "Artículo")
    price = item.get("price", "?")
    currency = item.get("currency", "€")
    url = item.get("url", "")

    # Emoji según rango de precio
    price_emoji = "🔥" if price and float(price) < 50 else "💰"
    
    tag_label = f"[{search_name}] " if search_name else ""
    
    message = f"{tag_label}{price_emoji} {price}{currency}\n{title}"
    
    headers = {
        "Title": f"WallaDeal: {title[:60]}",
        "Priority": "default",
        "Tags": "shopping,wallapop",
    }
    
    if url:
        headers["Click"] = url
        headers["Actions"] = f"view, Ver en Wallapop, {url}"

    # Añadir imagen si disponible
    images = item.get("images", [])
    if images:
        headers["Attach"] = images[0]

    try:
        ntfy_url = f"{server.rstrip('/')}/{topic}"
        response = requests.post(
            ntfy_url,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        logger.debug(f"📨 ntfy OK: {title[:40]}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error enviando ntfy: {e}")
        return False


def send_telegram(
    item: dict,
    bot_token: str,
    chat_id: str,
    search_name: str = "",
) -> bool:
    """
    Envía un mensaje a Telegram con los datos del artículo.
    
    Args:
        item: Dict del artículo
        bot_token: Token del bot de Telegram
        chat_id: ID del chat/grupo
        search_name: Nombre de la búsqueda
    
    Returns:
        True si se envió correctamente
    """
    title = item.get("title", "Artículo")
    price = item.get("price", "?")
    currency = item.get("currency", "€")
    url = item.get("url", "")
    description = item.get("description", "")

    price_emoji = "🔥" if price and float(price) < 50 else "💰"
    tag_label = f"*[{search_name}]*\n" if search_name else ""

    # Escapar caracteres especiales de Markdown v2
    def escape_md(text: str) -> str:
        special_chars = r"_*[]()~`>#+-=|{}.!"
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    desc_preview = description[:150] + "..." if len(description) > 150 else description

    text = (
        f"{tag_label}"
        f"{price_emoji} *{escape_md(str(price))}{escape_md(currency)}*\n\n"
        f"📦 {escape_md(title)}\n\n"
    )
    
    if desc_preview:
        text += f"_{escape_md(desc_preview)}_\n\n"
    
    if url:
        text += f"[🔗 Ver en Wallapop]({url})"

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.debug(f"📨 Telegram OK: {title[:40]}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error enviando Telegram: {e}")
        return False


def notify_all(
    items: list[dict],
    config: dict,
    search_name: str = "",
) -> dict:
    """
    Envía notificaciones por todos los canales habilitados.
    
    Args:
        items: Lista de artículos nuevos
        config: Configuración de notificaciones
        search_name: Nombre de la búsqueda
    
    Returns:
        Dict con contadores {ntfy_sent, ntfy_failed, telegram_sent, telegram_failed}
    """
    stats = {
        "ntfy_sent": 0,
        "ntfy_failed": 0,
        "telegram_sent": 0,
        "telegram_failed": 0,
    }

    ntfy_config = config.get("ntfy", {})
    telegram_config = config.get("telegram", {})

    ntfy_enabled = ntfy_config.get("enabled", False)
    telegram_enabled = telegram_config.get("enabled", False)

    if not ntfy_enabled and not telegram_enabled:
        logger.warning("⚠️ No hay canales de notificación habilitados")
        return stats

    for item in items:
        # ntfy
        if ntfy_enabled:
            topic = ntfy_config.get("topic", "")
            server = ntfy_config.get("server", "https://ntfy.sh")
            if topic:
                ok = send_ntfy(item, topic, server, search_name)
                stats["ntfy_sent" if ok else "ntfy_failed"] += 1

        # Telegram
        if telegram_enabled:
            bot_token = telegram_config.get("bot_token", "")
            chat_id = str(telegram_config.get("chat_id", ""))
            if bot_token and chat_id:
                ok = send_telegram(item, bot_token, chat_id, search_name)
                stats["telegram_sent" if ok else "telegram_failed"] += 1

    logger.info(
        f"📊 Notificaciones: "
        f"ntfy={stats['ntfy_sent']}/{stats['ntfy_sent']+stats['ntfy_failed']} "
        f"telegram={stats['telegram_sent']}/{stats['telegram_sent']+stats['telegram_failed']}"
    )
    return stats
