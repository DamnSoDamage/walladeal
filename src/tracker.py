"""
Módulo tracker — detecta artículos nuevos y persiste los ya vistos.
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DEFAULT_SEEN_FILE = "seen_items.json"
MAX_AGE_DAYS = 7  # Limpia IDs más antiguos de 7 días


class ItemTracker:
    """Rastrea artículos ya vistos para detectar novedades."""

    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or DEFAULT_SEEN_FILE
        self.seen: dict[str, str] = {}  # {item_id: timestamp_iso}
        self._load()

    def _load(self):
        """Carga el estado desde disco."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.seen = json.load(f)
                logger.info(f"📂 Cargados {len(self.seen)} artículos vistos")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"⚠️ Error cargando {self.filepath}: {e}")
                self.seen = {}
        else:
            logger.info("📂 Primera ejecución — sin artículos previos")

    def save(self):
        """Guarda el estado a disco."""
        self._cleanup_old()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.seen, f, indent=2, ensure_ascii=False)
            logger.debug(f"💾 Guardados {len(self.seen)} artículos vistos")
        except IOError as e:
            logger.error(f"❌ Error guardando {self.filepath}: {e}")

    def get_new_items(self, items: list[dict]) -> list[dict]:
        """
        Filtra y retorna solo los artículos que NO han sido vistos antes.
        
        Args:
            items: Lista de artículos del scraper
        
        Returns:
            Lista de artículos nuevos (no vistos antes)
        """
        new_items = []
        for item in items:
            item_id = str(item.get("id", ""))
            if item_id and item_id not in self.seen:
                new_items.append(item)

        logger.info(
            f"🆕 {len(new_items)} artículos nuevos de {len(items)} encontrados"
        )
        return new_items

    def mark_as_seen(self, items: list[dict]):
        """
        Marca una lista de artículos como vistos.
        
        Args:
            items: Lista de artículos a marcar
        """
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            item_id = str(item.get("id", ""))
            if item_id:
                self.seen[item_id] = now

    def _cleanup_old(self):
        """Elimina IDs más antiguos que MAX_AGE_DAYS para no crecer infinitamente."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
        before = len(self.seen)
        
        to_remove = []
        for item_id, ts in self.seen.items():
            try:
                seen_time = datetime.fromisoformat(ts)
                if seen_time < cutoff:
                    to_remove.append(item_id)
            except (ValueError, TypeError):
                # Si el timestamp está corrupto, lo mantenemos
                continue

        for item_id in to_remove:
            del self.seen[item_id]

        if to_remove:
            logger.info(
                f"🧹 Limpieza: eliminados {before - len(self.seen)} IDs antiguos"
            )

    @property
    def is_first_run(self) -> bool:
        """Indica si es la primera ejecución (no hay artículos previos)."""
        return len(self.seen) == 0
