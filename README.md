# 🔍 WallaDeal

**Scraper de Wallapop** que te avisa al instante de nuevos chollos por **ntfy** y/o **Telegram**. Gratis, sin servidor, corre en GitHub Actions.

> Pensado por y para estudiantes que quieren pillar chollos rápido sin estar pegados a Wallapop.

## ✨ Features

- 🔎 **Múltiples búsquedas** — configura varias con keywords y rangos de precio
- 🏷️ **Filtrado inteligente** — por keywords en el título, rango de precios, y exclusión de palabras
- 🆕 **Solo artículos nuevos** — recuerda lo que ya has visto, no repite avisos
- 📱 **ntfy** — notificaciones push gratis, sin registro, con imagen del artículo
- 💬 **Telegram** — alertas con formato rico y link directo
- ⚡ **GitHub Actions** — corre cada 10 min gratis, sin servidor propio
- 🧹 **Auto-limpieza** — borra IDs antiguos (7 días) para no crecer infinitamente

## 🚀 Setup rápido

### 1. Clonar y configurar

```bash
git clone https://github.com/TU_USER/walladeal.git
cd walladeal
cp config.example.yaml config.yaml
```

Edita `config.yaml` con tus búsquedas:

```yaml
searches:
  - name: "Switch barata"
    keywords: ["nintendo", "switch"]
    excluded_keywords: ["funda", "carcasa"]
    min_price: 50
    max_price: 180
    latitude: 40.4168    # Tu ciudad
    longitude: -3.7038
    distance: 50000      # Radio en metros
```

### 2. Notificaciones

#### 📱 ntfy (recomendado, 0 setup)

1. Instala la app **ntfy** ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/app/ntfy/id1625396347))
2. Suscríbete a un topic secreto (ej: `walladeal-miuser-xyz`)
3. Configura el mismo topic en `config.yaml`:

```yaml
notifications:
  ntfy:
    enabled: true
    topic: "walladeal-miuser-xyz"
```

#### 💬 Telegram

1. Habla con [@BotFather](https://t.me/BotFather) y crea un bot → copia el **token**
2. Envía `/start` a tu bot y obtén tu **chat_id** (usa [@userinfobot](https://t.me/userinfobot))
3. Configura en `config.yaml`:

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "123456:ABC-DEF..."
    chat_id: "123456789"
```

### 3. Probar en local

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

La primera ejecución guarda los artículos actuales sin notificar (para no spamear). A partir de la segunda, solo avisa de los nuevos.

## ☁️ Despliegue en GitHub Actions (gratis)

### 1. Crear los secrets

Ve a tu repo → **Settings** → **Secrets and variables** → **Actions** y añade:

| Secret | Descripción |
|---|---|
| `NTFY_TOPIC` | Tu topic secreto de ntfy |
| `TELEGRAM_BOT_TOKEN` | Token del bot (opcional) |
| `TELEGRAM_CHAT_ID` | Tu chat ID (opcional) |
| `WALLADEAL_SEARCHES` | Tu config de búsquedas en YAML (ver abajo) |

#### `WALLADEAL_SEARCHES` ejemplo:

```yaml
- name: "Switch"
  keywords: ["nintendo", "switch"]
  excluded_keywords: ["funda"]
  min_price: 50
  max_price: 180
  latitude: 40.4168
  longitude: -3.7038
  distance: 50000
```

### 2. Activar el workflow

El workflow ya está configurado en `.github/workflows/scrape.yml`. Se ejecuta:
- ⏰ Automáticamente cada 10 minutos
- 🖱️ Manualmente desde la pestaña **Actions** → **WallaDeal Scraper** → **Run workflow**

El estado (`seen_items.json`) se guarda automáticamente en un branch `data-store`.

## 🏗️ Arquitectura

```
walladeal/
├── main.py                 # Punto de entrada
├── src/
│   ├── scraper.py          # Scraping con Playwright (headless browser)
│   ├── filters.py          # Filtrado por keywords + precio
│   ├── tracker.py          # Detección de artículos nuevos
│   └── notifier.py         # Notificaciones (ntfy + Telegram)
├── config.example.yaml     # Ejemplo de configuración
├── .github/workflows/
│   └── scrape.yml          # GitHub Actions (cron)
└── requirements.txt        # Dependencias
```

## ⚠️ Disclaimer

Este proyecto hace scraping de la web de Wallapop usando un navegador headless (Playwright). Puede dejar de funcionar si Wallapop cambia su estructura web. Uso bajo tu responsabilidad y de forma razonable.

## 📄 License

MIT — haz lo que quieras con esto 🤙
