from datetime import datetime
import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import tasks, commands

TOKEN = 'MTMzOTk5NjMxNzMxMjc0OTYxMA.GpHg2v.KHEPSYfqKxaLjLXDZEk9FjE_F8-c5G04tZxnzU'  # Replace with your Discord bot token
CHANNEL_ID = 1339996037372317737  # Replace with your Discord channel ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_stock.start()

@tasks.loop(minutes=30)
async def check_stock():
    url = "https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153"
    headers = {"User-Agent":"Mozilla/5.0","cache-control":"max-age=0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    channel = bot.get_channel(CHANNEL_ID)

    stock_status_div = soup.find("div", {"style": "color:#BB0628;margin-bottom:8px"})
    stock_status = stock_status_div.find("strong").text.strip() if stock_status_div else "Not Found"

    now = datetime.now()
    formatted_now = now.strftime("%Y-%m-%d %H:%M:%S")

    print(formatted_now + " ----->", stock_status)


    if "Not Found" in stock_status:
        await channel.send("HTML code was changed. An update to the python script is required")
    elif "Coming Soon" in stock_status:
        await channel.send("The RTX 5080 is coming soon!!!!! Get ready!!!!" + " https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153")


@check_stock.before_loop
async def before_check_stock():
    await bot.wait_until_ready()


bot.run(TOKEN)
