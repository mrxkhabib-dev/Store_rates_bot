import asyncio
import re
import ast
import operator
import os
from datetime import datetime

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
# ADMIN SETTINGS
# ============================================================

ADMIN_ID = 5384520293  # your Telegram ID (@mrx_khabib)


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
