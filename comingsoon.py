from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import tasks, commands
import logging
import os
import platform
import asyncio
import json

# Set up logging
logging.basicConfig(
    filename='stock_check.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants for products
PRODUCTS = {
    "5080": "https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153",
    "5090": "https://www.bestbuy.com/site/nvidia-geforce-rtx-5090-32gb-gddr7-graphics-card-dark-gun-metal/6614151.p?skuId=6614151"
}

# Function to load environment variables or prompt for input
def get_env_variable(var_name, prompt_text):
    value = os.getenv(var_name)
    if value is None and platform.system() == 'Windows':
        value = input(prompt_text)
        os.system(f'setx {var_name} "{value}"')
    return value

# Loading environment variables
TOKEN = get_env_variable('DISCORD_BOT_TOKEN', 'Please enter your Discord Bot Token: ')
CHANNEL_ID = get_env_variable('DISCORD_CHANNEL_ID', 'Please enter your Discord Channel ID: ')

if not TOKEN or not CHANNEL_ID:
    logging.error("Missing required environment variables.")
    exit(1)

CHANNEL_ID = int(CHANNEL_ID.strip())

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration defaults
check_interval = 30  # Default check interval (minutes)
selected_products = ["5090"]  # Default selected product

# Helper function to calculate the time remaining until midnight on Monday
def time_until_next_monday():
    now = datetime.now()
    days_until_monday = (7 - now.weekday()) % 7
    next_monday = now + timedelta(days=days_until_monday)
    midnight_next_monday = datetime.combine(next_monday.date(), datetime.min.time())
    return midnight_next_monday - now

# Task to restart the stock check task at midnight on Monday
@tasks.loop(hours=24)
async def restart_task():
    if datetime.now().weekday() not in [5, 6]:
        return  # Do nothing if it's not the weekend

    time_until_restart = time_until_next_monday()
    delay_seconds = time_until_restart.total_seconds()

    print(f"Waiting for {delay_seconds} seconds until midnight on Monday.")
    logging.info(f"Waiting for {delay_seconds} seconds until midnight on Monday.")
    await asyncio.sleep(delay_seconds)

    # Restart stock check task at midnight
    if not check_stock.is_running():
        logging.info("Restarting stock check task at midnight.")
        check_stock.start()

# Task to check stock
@tasks.loop(minutes=30)
async def check_stock():
    if datetime.now().weekday() in [5, 6]:
        logging.info("It's the weekend. Skipping stock check.")
        check_stock.stop()
        return

    headers = {"User-Agent": "Mozilla/5.0", "cache-control": "max-age=0"}
    channel = bot.get_channel(CHANNEL_ID)

    for product_name in selected_products:
        product_url = PRODUCTS.get(product_name)
        if not product_url:
            logging.error(f"Product {product_name} not found.")
            continue

        response = requests.get(product_url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        # Look for stock status
        status_elements = soup.find_all(string=["Sold Out", "Coming Soon", "Add to Cart"])
        stock_status = "Not Found"

        for element in status_elements:
            parent_div = element.find_parent("div")
            if parent_div:
                if "Sold Out" in element:
                    stock_status = "Sold Out"
                elif "Coming Soon" in element:
                    stock_status = "Coming Soon"
                    await channel.send(f"{product_name} - {stock_status}")
                elif "Add to Cart" in element:
                    stock_status = "Add to Cart"
                    await channel.send(f"{product_name} - {stock_status}")

        logging.info(f"{product_name} - {stock_status}")

# Command to set product(s) for stock check
@bot.command(name='setproducts')
async def setproducts(ctx, *args):
    global selected_products
    valid_products = ["5080", "5090", "both"]
    if "both" in args:
        selected_products = ["5080", "5090"]
    elif any(product in args for product in valid_products):
        selected_products = args
    else:
        await ctx.send("Invalid product selection. Use '5080', '5090', or 'both'.")
        return

    logging.info(f"Selected products for stock check: {', '.join(selected_products)}")
    await ctx.send(f"Selected products for stock check: {', '.join(selected_products)}")

# Command to show current status
@bot.command(name='status')
async def status(ctx):
    now = datetime.now()
    day_of_week = now.weekday()
    status_message = f"I am running and checking {', '.join(selected_products)} stock every {check_interval} minute(s)."

    if day_of_week in [5, 6]:  # Saturday or Sunday
        time_until_restart = time_until_next_monday()
        hours, remainder = divmod(time_until_restart.total_seconds(), 3600)
        minutes = remainder // 60
        status_message = (f"The stock check is currently disabled for the weekend.\n"
                          f"The task will restart at midnight on Monday in approximately {int(hours)} hours and {int(minutes)} minutes.")
    elif not check_stock.is_running():
        status_message += "\n(Note: The stock check task is currently stopped but can be manually restarted or will restart automatically.)"

    await ctx.send(status_message)

# Command to set stock check interval
@bot.command(name='setinterval')
async def setinterval(ctx, minutes: int):
    global check_interval
    check_interval = minutes
    check_stock.change_interval(minutes=check_interval)
    confirmation_message = f"Stock check interval set to {check_interval} minute(s)."
    logging.info(confirmation_message)
    await ctx.send(confirmation_message)

# Command to retrieve logs
@bot.command(name='log')
async def log(ctx, lines: int = 10):
    try:
        with open('stock_check.log', 'r') as log_file:
            log_lines = log_file.readlines()
            last_lines = log_lines[-lines:]
            log_message = "```\n" + "".join(last_lines) + "\n```"
            await ctx.send(log_message)
    except Exception as e:
        error_message = f"Error reading log file: {e}"
        await ctx.send(error_message)

# Command to clear messages in a channel
@bot.command(name='clear')
async def clear(ctx):
    if ctx.author.guild_permissions.manage_messages:
        await ctx.channel.purge()
        confirmation_message = "All messages in this channel have been cleared."
        logging.info(confirmation_message)
        await ctx.send(confirmation_message)
    else:
        await ctx.send("You do not have permission to manage messages.")

# Event triggered when bot is ready
@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user}")
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            raise ValueError("Invalid CHANNEL_ID")
        check_stock.change_interval(minutes=check_interval)
        restart_task.start()
        check_stock.start()  # Start stock check if it's not the weekend
    except Exception as e:
        logging.error(f"Error with TOKEN or CHANNEL_ID: {e}")
        await bot.close()

@check_stock.before_loop
async def before_check_stock():
    await bot.wait_until_ready()

def main():
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Failed to run bot: {e}")

if __name__ == '__main__':
    main()

