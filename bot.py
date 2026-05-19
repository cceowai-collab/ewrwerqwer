import html
import asyncio
import aiohttp
import re
import io  # Добавили для работы с виртуальной памятью
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.client.default import DefaultBotProperties

# ПРЯМАЯ ВСТАВКА (только для теста!)
BOT_TOKEN = "8907673192:AAEvE0vkCsIi3VN7TgN2_ecWDZEDeMUmGss"
CRYVEN_API_KEY = "@ouehy:jdSHUxRX"  # Замените на реальный ключ
CRYVEN_BASE_URL = "http://cryven.info"

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


class CrystalAPI:
    def __init__(self, api_key: str, base_url: str = CRYVEN_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.proxy = None  # Сюда можно передать прокси "http://ip:port", если запросы блокируются

    async def get(self, path: str, **params) -> dict:
        query = {"key": self.api_key}
        query.update({key: value for key, value in params.items() if value})
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{self.base_url}{path}", params=query, proxy=self.proxy) as response:
                response_text = await response.text()
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    error_preview = response_text[:150] if response_text else "Пустой ответ"
                    raise RuntimeError(f"Сервер вернул не JSON (HTTP {response.status}). Ответ: {error_preview}")

                if response.status >= 400:
                    raise RuntimeError(data.get("error", f"HTTP {response.status}"))
                return data

    async def post(self, path: str, **payload) -> dict:
        body = {"key": self.api_key}
        body.update({key: value for key, value in payload.items() if value})
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.base_url}{path}", json=body, proxy=self.proxy) as response:
                response_text = await response.text()
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    error_preview = response_text[:150] if response_text else "Пустой ответ"
                    raise RuntimeError(f"Сервер вернул не JSON (HTTP {response.status}). Ответ: {error_preview}")

                if response.status >= 400:
                    raise RuntimeError(data.get("error", f"HTTP {response.status}"))
                return data

    async def search(self, query: str) -> dict:
        return await self.get("/api/search", search=query)

    async def sherlock(self, username: str) -> dict:
        return await self.get("/api/telegram/search", search=username)

    async def photo_by_url(self, image_url: str) -> dict:
        return await self.get("/api/photo/search", image_url=image_url)


def safe(value) -> str:
    return html.escape(str(value if value is not None else ""))


# --- УМНАЯ ФУНКЦИЯ ГЛУБОКОЙ ОЧИСТКИ ---
def clean_output(value) -> str:
    if not value:
        return ""

    raw_str = str(value)
    found_tokens = re.findall(r"['\"]([^'\"]+)['\"]", raw_str)

    if not found_tokens:
        cleaned = raw_str.replace("[", "").replace("]", "").replace("'", "").replace('"', "").strip()
        return "" if cleaned in ("-", "None", "null", "") else cleaned

    ignored_markers = {
        "fullname", "fio", "name", "фио", "имя", "полное имя",
        "phone", "number", "телефон", "номер", "телефонный_номер",
        "email", "mail", "почта", "region", "регион", "address", "адрес",
        "card", "карта", "birthday", "дата_рождения", "snils", "снилс",
        "passport", "паспорт", "sex", "пол", "town", "город", "None", "null", "-"
    }

    result_items = []
    for token in found_tokens:
        token_clean = token.strip()
        if token_clean and token_clean.lower() not in ignored_markers:
            result_items.append(token_clean)

    return ", ".join(dict.fromkeys(result_items))


# --- ГЕНЕРАТОР ВЕБ-ОТЧЕТА ---

def generate_html_report(query: str, data: dict) -> str:
    fast = data.get("fast-result") or {}
    full = data.get("full-result") or {}
    rows = full.get("Базы Данных") or []
    if not isinstance(rows, list):
        rows = []

    sidebar_items = ""
    for i, row in enumerate(rows, 1):
        source_name = row.get("source") or row.get("database") or row.get("name") or f"Источник #{i}"
        source_name = clean_output(source_name)
        fields_count = len([k for k in row.keys() if k not in ("source", "database", "name")])
        sidebar_items += f"""
        <div class="sidebar-item" onclick="scrollToElement('db-{i}')">
            <span class="db-icon">💎</span>
            <span class="db-name">{safe(source_name)}</span>
            <span class="db-badge">{fields_count}</span>
        </div>
        """

    db_cards = ""
    for i, row in enumerate(rows, 1):
        source_name = row.get("source") or row.get("database") or row.get("name") or f"Источник #{i}"
        source_name = clean_output(source_name)
        row_content = ""
        for key, val in row.items():
            if key in ("source", "database", "name"):
                continue
            clean_val = clean_output(val) or "—"
            row_content += f"""
            <div class="data-row">
                <div class="data-key">{safe(key).upper()}</div>
                <div class="data-val">{safe(clean_val)}</div>
            </div>
            """
        db_cards += f"""
        <div class="card" id="db-{i}">
            <div class="card-header">📂 {safe(source_name)} <span class="card-index">#{i}</span></div>
            <div class="card-body">{row_content if row_content else '<div class="data-val">Нет внутренних полей</div>'}</div>
        </div>
        """

    fast_blocks_html = ""
    if fast:
        for k, v in fast.items():
            clean_v = clean_output(v)
            if clean_v:
                fast_blocks_html += f"""
                <div class="info-block">
                    <div class="info-key">{safe(k).upper()}</div>
                    <div class="info-val">{safe(clean_v)}</div>
                </div>
                """

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Crystal Search Отчет — {safe(query)}</title>
        <style>
            :root {{
                --bg-main: #0b0f19; --bg-sidebar: #0f1423; --bg-card: #13192e;
                --border-color: #1e2642; --text-main: #f1f5f9; --text-muted: #64748b;
                --accent-crystal: #00d2ff;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; }}
            body {{ background-color: var(--bg-main); color: var(--text-main); display: flex; height: 100vh; overflow: hidden; }}
            .sidebar {{ width: 320px; background-color: var(--bg-sidebar); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; }}
            .sidebar-logo {{ padding: 24px; font-size: 20px; font-weight: bold; color: var(--accent-crystal); border-bottom: 1px solid var(--border-color); }}
            .sidebar-menu {{ flex: 1; overflow-y: auto; padding: 15px; }}
            .sidebar-title {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 1px; margin-bottom: 10px; }}
            .sidebar-item {{ display: flex; align-items: center; padding: 10px 12px; border-radius: 6px; cursor: pointer; margin-bottom: 5px; }}
            .sidebar-item:hover {{ background-color: rgba(0, 210, 255, 0.1); }}
            .db-name {{ flex: 1; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #cbd5e1; }}
            .db-badge {{ background: #1e293b; color: var(--accent-crystal); font-size: 11px; padding: 2px 6px; border-radius: 10px; }}
            .main-content {{ flex: 1; overflow-y: auto; padding: 30px; display: flex; flex-direction: column; gap: 25px; }}
            .search-header {{ background: linear-gradient(135deg, #0f172a, #1e293b); padding: 25px; border-radius: 10px; border: 1px solid var(--border-color); }}
            .search-query {{ font-size: 28px; font-weight: bold; color: #fff; margin-top: 5px; font-family: monospace; }}
            .stats-grid {{ display: flex; gap: 20px; margin-top: 20px; }}
            .stat-box {{ background: var(--bg-sidebar); border: 1px solid var(--border-color); padding: 15px 25px; border-radius: 8px; flex: 1; text-align: center; }}
            .stat-val {{ font-size: 22px; font-weight: bold; color: var(--accent-crystal); }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 15px; margin-top: 15px; }}
            .info-block {{ background: rgba(255,255,255,0.02); padding: 12px 15px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); }}
            .info-key {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: bold; }}
            .info-val {{ font-size: 14px; color: #e2e8f0; margin-top: 4px; word-break: break-word; line-height: 1.4; }}
            .card {{ background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 15px; scroll-margin-top: 20px; }}
            .card-header {{ background-color: rgba(255,255,255,0.03); padding: 14px 20px; font-size: 15px; font-weight: bold; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; }}
            .card-body {{ padding: 15px 20px; }}
            .data-row {{ display: flex; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 13.5px; }}
            .data-key {{ width: 200px; color: var(--text-muted); font-weight: 600; font-size: 11px; }}
            .data-val {{ flex: 1; color: #cbd5e1; word-break: break-word; }}
        </style>
        <script>
            function scrollToElement(id) {{
                const el = document.getElementById(id);
                if(el) el.scrollIntoView({{ behavior: 'smooth' }});
            }}
        </script>
    </head>
    <body>
        <div class="sidebar">
            <div class="sidebar-logo">💎 Crystal Search</div>
            <div class="sidebar-menu">
                <div class="sidebar-title">Источники данных</div>
                {sidebar_items if sidebar_items else '<div style="color:var(--text-muted);">Ничего не найдено</div>'}
            </div>
        </div>
        <div class="main-content">
            <div class="search-header">
                <div style="font-size:12px; color:var(--text-muted); text-transform:uppercase;">Поисковый запрос</div>
                <div class="search-query">{safe(query)}</div>
                <div class="stats-grid">
                    <div class="stat-box"><div class="stat-val">{len(rows)}</div><div style="font-size:12px; color:var(--text-muted);">Источников</div></div>
                    <div class="stat-box"><div class="stat-val">{data.get('results_count') or len(rows)}</div><div style="font-size:12px; color:var(--text-muted);">Полей всего</div></div>
                </div>
                <div style="margin-top: 25px;">
                    <div class="sidebar-title">🔹 Ключевая информация</div>
                    <div class="info-grid">
                        {fast_blocks_html if fast_blocks_html else '<div class="info-val">Сводка отсутствует</div>'}
                    </div>
                </div>
            </div>
            {db_cards}
        </div>
    </body>
    </html>
    """


# --- ХЕНДЛЕРЫ БОТА ---

session_storage = {}
api = CrystalAPI(CRYVEN_API_KEY)


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "💎 <b>Crystal Search Bot</b>\n\n"
        "Используй для поиска - \n\n"

"🕵️ Личность:\n"
"/search Навальный Алексей Анатольевич 04.06.1976 - ФИО\n\n"

"📲 Контакты:\n"
"/search 79999688666 – номер телефона\n"
"/search 79999688666@mail.ru – email\n\n"

"🚘 Транспорт:\n"
"/search В395ОК199 – номер автомобиля\n"
"/search XTA211440C5106924 – VIN автомобиля\n\n"

"📄 Документы:\n"
"/search 1234567890 – водительские права\n"
"/search 1234567890 – паспорт\n"
"/search 12345678901 – СНИЛС\n"
"/search 123456789012 – ИНН\n\n"

"🏢Юридическое лицо:\n"
"/search 2540214547 – ИНН\n"
"/search 1107449004464 – ОГРН или ОГРНИП"

    )


@dp.message(Command("search"))
async def search_command(message: Message):
    query = message.text.replace("/search", "", 1).strip()
    if not query:
        await message.answer("Пример: /search 79999999999")
        return

    wait = await message.answer("💎 <b>Crystal Search</b>\n\n⏳ <i>Выполняю поиск из баз данных...</i>")

    try:
        data = await api.search(query)
        fast = data.get("fast-result") or {}
        full = data.get("full-result") or {}
        rows = full.get("Базы Данных") or []

        session_storage[message.from_user.id] = {"query": query, "data": data}

        fast_clean = {str(k).lower(): v for k, v in fast.items()}

        def find_value(keys_list):
            for k in keys_list:
                if k in fast_clean and fast_clean[k]:
                    return fast_clean[k]
            return None

        fio = find_value(["fullname", "фио", "имя", "name", "fio", "full_name"])
        phone = find_value(["phone", "телефон", "номер", "number", "telephone"])
        email = find_value(["email", "почта", "mail", "e-mail"])

        if not fio and not phone and not email and rows:
            first_row = rows[0]
            first_row_clean = {str(k).lower(): v for k, v in first_row.items()}
            fio = first_row_clean.get("фио") or first_row_clean.get("имя") or first_row_clean.get(
                "name") or first_row_clean.get("fullname")
            phone = first_row_clean.get("телефон") or first_row_clean.get("номер") or first_row_clean.get("phone")
            email = first_row_clean.get("почта") or first_row_clean.get("email")

        fio_res = clean_output(fio)
        phone_res = clean_output(phone)
        email_res = clean_output(email)

        fio_str = safe(fio_res) if fio_res else "<i>Не найдено в сводке</i>"
        phone_str = safe(phone_res) if phone_res else "<i>Не найдено в сводке</i>"
        email_str = safe(email_res) if email_res else "<i>Не найдено в сводке</i>"

        text = (
            f"💎 <b>Crystal Search</b>\n\n"
            f"🔎 <b>Запрос:</b> <code>{safe(query)}</code>\n"
            f"📊 <b>Найдено:</b> {len(rows)} источников\n\n"
            f"📄 <b>Краткая сводка:</b>\n"
            f"├ <b>ФИО:</b> {fio_str}\n"
            f"├ <b>Телефон:</b> {phone_str}\n"
            f"└ <b>Почта:</b> {email_str}\n\n"
            f"📬 Полный отчет сгенерирован."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Получить файл отчета (HTML)", callback_data="open_report")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="go_back")]
        ])

        await wait.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        error_msg = str(e)
        if "504" in error_msg or "proxy" in error_msg.lower():
            await wait.edit_text(
                "💎 <b>Crystal Search</b>\n\n"
                "⚠️ <b>Сервер перегружен (HTTP 504)</b>\n"
                "В данный момент база данных отвечает слишком медленно из-за высокой нагрузки. "
                "Пожалуйста, повторите попытку через 1-2 минуты."
            )
        else:
            await wait.edit_text(f"❌ <b>Ошибка при поиске:</b>\n<code>{safe(e)}</code>")


# --- ОБНОВЛЕННАЯ ОТПРАВКА БЕЗ СОХРАНЕНИЯ НА ДИСК КОМПЬЮТЕРА ---
@dp.callback_query(lambda c: c.data == "open_report")
async def open_report_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in session_storage:
        await callback_query.answer("⚠️ Данные устарели. Повторите запрос.", show_alert=True)
        return

    user_data = session_storage[user_id]
    query = user_data["query"]
    data = user_data["data"]

    # 1. Генерируем HTML-строку текста отчета
    html_content = generate_html_report(query, data)
    file_name = f"crystal_{query}.html".replace("+", "").replace(" ", "_")

    try:
        # 2. Конвертируем строку в байты UTF-8 и пакуем в виртуальный буфер io.BytesIO
        file_bytes = html_content.encode("utf-8")
        file_buffer = io.BytesIO(file_bytes)

        # 3. Передаем виртуальный файл в Telegram с помощью BufferedInputFile
        document = BufferedInputFile(file_buffer.getvalue(), filename=file_name)

        await callback_query.message.reply_document(
            document=document,
            caption=f"📂 <b>Полный интерактивный отчет по запросу:</b> <code>{safe(query)}</code>\n\n"
                    f"<i>Нажмите на файл, чтобы открыть его на телефоне или ПК.</i>"
        )
        await callback_query.answer("🚀 Отчет отправлен в чат!")
    except Exception as e:
        await callback_query.answer("❌ Ошибка при формировании файла в памяти", show_alert=True)


@dp.callback_query(lambda c: c.data == "go_back")
async def go_back_callback(callback_query: CallbackQuery):
    await callback_query.message.edit_text("💎 Введите новый запрос для поиска.")
    await callback_query.answer()


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))