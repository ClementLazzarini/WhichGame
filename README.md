# 🎮 WhichGame

![Project
Status](https://img.shields.io/badge/Status-Production-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.0-092E20?style=for-the-badge&logo=django&logoColor=white)
![Tailwind
CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Alpine.js](https://img.shields.io/badge/Alpine.js-8BC0D0?style=for-the-badge&logo=alpine.js&logoColor=white)

> **Find your next gaming gem based on your budget and available time.**

**WhichGame** is a smart video game comparator. Unlike classic
aggregators, it cross-references three essential data points for the
modern gamer: Quality (Ratings), Real Cost (Current prices), and Time
Investment (Playtime).

🌐 **Live Demo:** https://www.whichgame.app

------------------------------------------------------------------------

## ⚡ Key Features

-   **Data-Driven Architecture (SSOT):** Proprietary local database
    (SQLite) for instant performance, populated via asynchronous
    background tasks.
-   **Smart Filtering:** Real-time combined filtering (Price +
    Duration + Platform + Genre + Year).
-   **Smart Linking:** Automatic detection and linking between original
    games and their modern Remakes/Remasters.
-   **Modern UI/UX:** Fully responsive interface, native Dark Mode,
    "Accordion" menus on mobile.
-   **DevOps Automation:** Autonomous updates for prices and new game
    releases via Cron Jobs.

------------------------------------------------------------------------

## 🛠️ Tech Stack

### Backend

-   **Python / Django**
-   **Management Commands** for ETL tasks
-   **SQLite** optimized for read-heavy workloads

### Frontend

-   **Django Templates**
-   **Tailwind CSS** via `django-tailwind`
-   **Alpine.js** for lightweight interactivity

### External APIs

-   **IGDB (Twitch):** Metadata, covers, release dates
-   **CheapShark:** Real-time pricing
-   **HowLongToBeat:** Playtime estimation

------------------------------------------------------------------------

## 🏗️ Data Architecture (ETL)

  -----------------------------------------------------------------------
  Layer             Script               Description
  ----------------- -------------------- --------------------------------
  **1. Ingestion**  `import_games.py`    Import from IGDB with filtering
                                         and offset persistence

  **2. Pricing**    `update_prices.py`   Enrich game prices with
                                         rate‑limit protection

  **3. Times**      `update_hltb.py`     Fetch playtimes

  **4. Linking**    `link_remakes.py`    Link originals to
                                         remakes/remasters
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 🚀 Local Installation

### 1. Clone the repository

``` bash
git clone https://github.com/ClementLazzarini/WhichGame.git
cd WhichGame
```

### 2. Virtual Environment

``` bash
python3 -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

``` bash
pip install -r requirements.txt
```

### 4. Configuration

Create a `.env` file:

    DEBUG=True
    SECRET_KEY=your_secret_key
    IGDB_CLIENT_ID=your_id
    IGDB_CLIENT_SECRET=your_secret

### 5. Database & Tailwind

``` bash
python manage.py migrate
python manage.py tailwind install
python manage.py tailwind start
```

### 6. Run Server

``` bash
python manage.py runserver
```

------------------------------------------------------------------------

## 🤖 Management Commands

### Import Games

``` bash
python manage.py import_games --limit 50
```

### Link Remakes

``` bash
python manage.py link_remakes
```

------------------------------------------------------------------------

## 👤 Author

**Clément Lazzarini**

GitHub: https://github.com/ClementLazzarini

------------------------------------------------------------------------

## 📄 License

MIT License --- see `LICENSE` for details.
