import asyncio
import re
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message


# ============================================================
# SETTINGS
# ============================================================

SELL_MARGIN = 3.0

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=the-open-network&vs_currencies=usd"
)

CBU_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"


# ============================================================
# TELEGRAM TOKEN
# ============================================================

# TELEGRAM TOKEN

import os

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable was not found")

bot = Bot(token=TOKEN)
dp = Dispatcher()



# ============================================================
# GET LIVE TON PRICE
# ============================================================

async def get_ton_price():
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(COINGECKO_URL) as response:

            if response.status != 200:
                raise Exception(
                    f"CoinGecko returned HTTP {response.status}"
                )

            data = await response.json()

            return float(data["the-open-network"]["usd"])


# ============================================================
# GET CBU USD + RUB RATES
# ============================================================

async def get_cbu_rates():
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(CBU_URL) as response:

            if response.status != 200:
                raise Exception(
                    f"CBU returned HTTP {response.status}"
                )

            data = await response.json()

    usd_rate = None
    rub_rate = None

    for currency in data:
        code = currency.get("Ccy")

        if code == "USD":
            usd_rate = float(currency["Rate"])

        elif code == "RUB":
            rub_rate = float(currency["Rate"])

    if usd_rate is None:
        raise Exception("USD rate not found")

    if rub_rate is None:
        raise Exception("RUB rate not found")

    return usd_rate, rub_rate


# ============================================================
# FORMAT UZS
# ============================================================

def format_uzs(value):
    return f"{value:,.0f}".replace(",", " ")


# ============================================================
# FORMAT USD / RUB
# ============================================================

def format_money(value):
    return f"{value:,.2f}"


# ============================================================
# CALCULATE
# ============================================================

async def calculate(amount):

    ton_usd = await get_ton_price()

    usd_uzs, rub_uzs = await get_cbu_rates()

    # TON → USD
    total_usd = amount * ton_usd

    # USD → UZS
    total_uzs = total_usd * usd_uzs

    # UZS → RUB
    total_rub = total_uzs / rub_uzs

    # +3% recommended selling price
    selling_price = total_uzs * (1 + SELL_MARGIN / 100)

    return {
        "amount": amount,
        "total_usd": total_usd,
        "total_uzs": total_uzs,
        "total_rub": total_rub,
        "usd_uzs": usd_uzs,
        "selling_price": selling_price,
    }


# ============================================================
# FORMAT RESULT
# ============================================================

def format_result(data):

    amount = f"{data['amount']:g}"

    return (
    f"💠 **{amount} TON joriy kursi:**\n\n"
    f"💰 **{format_uzs(data['total_uzs'])} UZS**\n"
    f"💲 **{format_money(data['total_usd'])} USD**\n"
    f" ₽ **{format_money(data['total_rub'])} RUB**\n\n"
    f"🏛️ **CBU USD kursi:** "
    f"{format_uzs(data['usd_uzs'])} UZS\n"
    f"📊 **Sotish uchun:** "
    f"{format_uzs(data['selling_price'])} UZS "
    f"(+{SELL_MARGIN:g}%)"
    )


# ============================================================
# /START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    await message.answer(
        "💎 **TON Calculator Bot**\n\n"
        "TON miqdorini yuboring.\n\n"
        "Masalan:\n"
        "`2 TON`\n"
        "`12.5 TON`\n"
        "`45 TON`\n"
        "`100 TON`",
        parse_mode="Markdown"
    )


# ============================================================
# PROCESS TON
# ============================================================

async def process_ton(message: Message, amount: float):

    loading = await message.answer("⏳ Kurslar olinmoqda...")

    try:

        result = await calculate(amount)

        await loading.edit_text(
            format_result(result),
            parse_mode="Markdown"
        )

    except Exception as error:

        print(f"ERROR: {error}")

        await loading.edit_text(
            "❌ Kurslarni olishda xatolik yuz berdi.\n"
            "Birozdan keyin qayta urinib ko'ring."
        )


# ============================================================
# /TON COMMAND
# ============================================================

@dp.message()
async def message_handler(message: Message):

    if not message.text:
        return

    text = message.text.strip()

    # /ton 45
    command_match = re.fullmatch(
        r"/ton(?:@\w+)?\s+([0-9]+(?:[.,][0-9]+)?)",
        text,
        re.IGNORECASE
    )

    # 45 TON / 45 ton / 45
    amount_match = re.fullmatch(
        r"([0-9]+(?:[.,][0-9]+)?)\s*(?:ton)?",
        text,
        re.IGNORECASE
    )

    match = command_match or amount_match

    if not match:
        return

    try:

        amount = float(match.group(1).replace(",", "."))

        if amount <= 0:
            return

    except ValueError:
        return

    await process_ton(message, amount)


# ============================================================
# MAIN
# ============================================================

async def main():

    print("🤖 TON Calculator Bot is starting...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
