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
    async with aiohttp.ClientSession() as session:
        async with session.get(COINGECKO_URL) as response:
            data = await response.json()
            return float(data["the-open-network"]["usd"])


# ============================================================
# GET CBU USD + RUB RATES
# ============================================================

async def get_cbu_rates():
    async with aiohttp.ClientSession() as session:
        async with session.get(CBU_URL) as response:
            data = await response.json()
    usd_rate = None
    rub_rate = None
    for currency in data:
        code = currency.get("Ccy")
        if code == "USD":
            usd_rate = float(currency["Rate"])
        elif code == "RUB":
            rub_rate = float(currency["Rate"])
    return usd_rate, rub_rate


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
# SAFE CALCULATOR
# ============================================================

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

def safe_calculate(expression):
    expression = expression.replace(",", ".").strip()
    tree = ast.parse(expression, mode="eval")
    def calculate_node(node):
        if isinstance(node, ast.Expression):
            return calculate_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            if type(node.op) not in ALLOWED_OPERATORS:
                raise ValueError("Operator not allowed")
            left = calculate_node(node.left)
            right = calculate_node(node.right)
            return ALLOWED_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = calculate_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            return value
        raise ValueError("Invalid expression")
    return calculate_node(tree)


def format_calculator_result(result):
    if isinstance(result, float) and result.is_integer():
        return f"{int(result):,}".replace(",", " ")
    if isinstance(result, float):
        return (f"{result:,.10f}".rstrip("0").rstrip(".").replace(",", " "))
    return f"{result:,}".replace(",", " ")


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
# MAIN MESSAGE HANDLER
# ============================================================

@dp.message()
async def message_handler(message: Message):
    if not message.text:
        return
    text = message.text.strip()

    # TON amount
    amount_match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)\s*ton", text, re.IGNORECASE)
    if amount_match:
        amount = float(amount_match.group(1).replace(",", "."))
        if amount > 0:
            result = await calculate(amount)
            await send_reply(message, format_result(result), parse_mode="Markdown")
        return

    # Calculator
    if re.fullmatch(r"[-+*/().%\d\s,]+", text) and re.search(r"[+\-*/%]", text):
        try:
            result = safe_calculate(text)
            await send_reply(message, format_calculator_result(result))
        except Exception:
            await send_reply(message, "❌ Invalid calculation.")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

async def main():
    print("🤖 TON Calculator Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

