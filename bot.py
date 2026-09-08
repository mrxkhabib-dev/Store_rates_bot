import asyncio
import re
import ast
import operator
import os

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

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable was not found")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# GET LIVE TON PRICE
# ============================================================

async def get_ton_price():
    timeout = aiohttp.ClientTimeout(total=15)
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    COINGECKO_URL,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "TON-Calculator-Bot/1.0"
                    }
                ) as response:
                    if response.status == 429:
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise Exception("CoinGecko rate limit reached")
                    if response.status != 200:
                        raise Exception(f"CoinGecko returned HTTP {response.status}")
                    data = await response.json()
                    price = data["the-open-network"]["usd"]
                    return float(price)
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, TypeError, ValueError) as error:
            if attempt == 2:
                raise Exception(f"Unable to get TON price: {error}")
            await asyncio.sleep(2 ** attempt)
    raise Exception("Unable to get TON price")


# ============================================================
# GET CBU USD + RUB RATES
# ============================================================

async def get_cbu_rates():
    timeout = aiohttp.ClientTimeout(total=15)
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    CBU_URL,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "TON-Calculator-Bot/1.0"
                    }
                ) as response:
                    if response.status != 200:
                        raise Exception(f"CBU returned HTTP {response.status}")
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
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, TypeError, ValueError) as error:
            if attempt == 2:
                raise Exception(f"Unable to get CBU rates: {error}")
            await asyncio.sleep(2 ** attempt)
    raise Exception("Unable to get CBU rates")


# ============================================================
# FORMATTERS
# ============================================================

def format_uzs(value):
    return f"{value:,.0f}".replace(",", " ")

def format_money(value):
    return f"{value:,.2f}"


# ============================================================
# TON CALCULATE
# ============================================================

async def calculate(amount):
    ton_usd, rates = await asyncio.gather(get_ton_price(), get_cbu_rates())
    usd_uzs, rub_uzs = rates
    total_usd = amount * ton_usd
    total_uzs = total_usd * usd_uzs
    total_rub = total_uzs / rub_uzs
    selling_price = total_uzs * (1 + SELL_MARGIN / 100)
    return {
        "amount": amount,
        "ton_usd": ton_usd,
        "total_usd": total_usd,
        "total_uzs": total_uzs,
        "total_rub": total_rub,
        "usd_uzs": usd_uzs,
        "selling_price": selling_price,
    }


# ============================================================
# FORMAT TON RESULT
# ============================================================

def format_result(data):
    amount = f"{data['amount']:g}"
    return (
        f"💠 **{amount} TON joriy kursi:**\n\n"
        f"💰 **{format_uzs(data['total_uzs'])} UZS**\n"
        f"💲 **{format_money(data['total_usd'])} USD**\n"
        f"₽ **{format_money(data['total_rub'])} RUB**\n\n"
        f"🏛️ **CBU USD kursi:** {format_uzs(data['usd_uzs'])} UZS\n"
        f"📊 **Sotish uchun:** {format_uzs(data['selling_price'])} UZS (+{SELL_MARGIN:g}%)"
    )


# ============================================================
# REPLY HELPER
# ============================================================

async def send_reply(message: Message, text: str, parse_mode=None):
    await message.reply(text, parse_mode=parse_mode)


# ============================================================
# /START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    await send_reply(
        message,
        "💎 **TON Calculator Bot**\n\n"
        "TON miqdorini yuboring.\n\n"
        "Masalan:\n"
        "`2 TON`\n"
        "`12.5 TON`\n"
        "`45 TON`\n"
        "`100 TON`\n\n"
        "Faqat `TON` bilan yuboring.",
        parse_mode="Markdown"
    )


# ============================================================
# PROCESS TON
# ============================================================

async def process_ton(message: Message, amount: float):
    try:
        result = await calculate(amount)
        await send_reply(message, format_result(result), parse_mode="Markdown")
    except Exception as error:
        print(f"ERROR: {error}")
        await send_reply(
            message,
            "❌ Kurslarni olishda xatolik yuz berdi.\n\n"
            "Kurs serverlari vaqtincha javob bermayapti.\n"
            "Birozdan keyin qayta urinib ko'ring."
        )


# ============================================================
# MAIN MESSAGE HANDLER
# ============================================================

@dp.message()
async def message_handler(message: Message):
    if not message.text:
        return
    text = message.text.strip()

    # 1. /ton 45
    command_match = re.fullmatch(
        r"/ton(?:@\w+)?\s+([0-9]+(?:[.,][0-9]+)?)",
        text,
        re.IGNORECASE
    )
    if command_match:
        try:
            amount = float(command_match.group(1).replace(",", "."))
            if amount <= 0:
                return
        except ValueError:
            return
        await process_ton(message, amount)
        return

    # 2. TON AMOUNT (must include "ton")
    amount_match = re.fullmatch(
        r"([0-9]+(?:[.,][0-9]+)?)\s*ton",
        text,
        re.IGNORECASE
    )
    if amount_match:
        try:
            amount = float(amount_match.group(1).replace(",", "."))
            if amount <= 0:
                return
        except ValueError:
            return
        await process_ton(message, amount)
        return

    # 3. Calculator
    if re.fullmatch(r"[-+*/().%\d\s,]+", text) and re.search(r"[+\-*/%]", text):
        try:
            result = safe_calculate(text)
            await send_reply(
                message,
                f"🧮 **Calculator**\n\n`{text}` = **{format_calculator_result(result)}**",
                parse_mode="Markdown"
            )
            return
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError, OverflowError):
            pass


# ============================================================
# MAIN
# ============================================================

async def main():
    print("🤖 TON Calculator Bot is starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
