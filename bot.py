import os
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==============================
# CONFIGURATION
# ==============================

TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "visitation.db"

NAME, CATEGORY, DATE, PUROK, NOTES = range(5)

CATEGORIES = [
    "Tatay",
    "Nanay",
    "Anak",
    "IND"
]

PUROK_GROUPS = [
    "2-1",
    "2-2",
    "2-3"
]


# ==============================
# RENDER HEALTH SERVER
# ==============================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Visitation Bot is running!")

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    server.serve_forever()


# ==============================
# DATABASE
# ==============================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            date_visited TEXT NOT NULL,
            purok_grupo TEXT NOT NULL,
            notes TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_visit(name, category, date_visited, purok, notes):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO visits
        (name, category, date_visited, purok_grupo, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        category,
        date_visited,
        purok,
        notes
    ))

    conn.commit()
    conn.close()


def get_all_visits():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            category,
            date_visited,
            purok_grupo,
            notes
        FROM visits
        ORDER BY date_visited DESC, id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_week_visits():
    today = datetime.now().date()

    start = today - timedelta(
        days=today.weekday()
    )

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            category,
            date_visited,
            purok_grupo,
            notes
        FROM visits
        WHERE date_visited BETWEEN ? AND ?
        ORDER BY date_visited ASC, id ASC
    """, (
        start.isoformat(),
        today.isoformat()
    ))

    rows = cursor.fetchall()
    conn.close()

    return rows


# ==============================
# START
# ==============================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        ["/add", "/records"],
        ["/week"]
    ]

    await update.message.reply_text(
        "👋 Welcome sa Visitation Record Bot!\n\n"
        "Gamitin ang mga commands:\n\n"
        "/add — Magdagdag ng visitation record\n"
        "/records — Tingnan lahat ng records\n"
        "/week — Tingnan ang Visited of the Week\n"
        "/cancel — Kanselahin ang kasalukuyang entry",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# ==============================
# ADD RECORD
# ==============================

async def add_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📝 Magdagdag tayo ng visitation record.\n\n"
        "Ilagay ang **Name**:",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove()
    )

    return NAME


async def get_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    name = update.message.text.strip()

    if not name:
        await update.message.reply_text(
            "❌ Pakilagay ang pangalan."
        )

        return NAME

    context.user_data["name"] = name

    keyboard = [
        [category]
        for category in CATEGORIES
    ]

    await update.message.reply_text(
        "Piliin ang **Category**:",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    return CATEGORY


async def get_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    category = update.message.text.strip()

    if category not in CATEGORIES:

        await update.message.reply_text(
            "❌ Piliin lamang ang:\n"
            "Tatay\n"
            "Nanay\n"
            "Anak\n"
            "IND"
        )

        return CATEGORY

    context.user_data["category"] = category

    await update.message.reply_text(
        "📅 Ilagay ang **Date Visited**.\n\n"
        "Format: YYYY-MM-DD\n"
        "Halimbawa: 2026-08-17",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove()
    )

    return DATE


async def get_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    date_text = update.message.text.strip()

    try:
        datetime.strptime(
            date_text,
            "%Y-%m-%d"
        )

    except ValueError:
