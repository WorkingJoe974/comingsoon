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
    print("Missing required environment variables.")
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


async def restart_task():
    while True:
        now = datetime.now()

        if now.weekday() not in [5, 6]:  # Only run if it's the weekend
            message = "It's not the weekend. Restart task is not needed yet."
            logging.info(message)
            print(message)
            await asyncio.sleep(24 * 3600)
            continue

        next_monday_midnight = datetime.combine(
            now + timedelta(days=(7 - now.weekday()) % 7), datetime.min.time()
        )

        if now >= next_monday_midnight:
            next_monday_midnight += timedelta(weeks=1)

        delay_seconds = (next_monday_midnight - now).total_seconds()

        message = (f"Restart task scheduled: Stock check will restart at midnight on Monday in "
                   f"{int(delay_seconds // 3600)} hours and {int((delay_seconds % 3600) // 60)} minutes.")
        logging.info(message)
        print(message)

        await asyncio.sleep(delay_seconds)

        message = "Midnight on Monday reached. Restarting stock check task."
        logging.info(message)
        print(message)

        if not check_stock.is_running():
            message = "Stock check task was stopped. Restarting now."
            logging.info(message)
            print(message)
            check_stock.start()
        else:
            message = "Stock check task is already running. No action needed."
            logging.info(message)
            print(message)

        await asyncio.sleep(24 * 3600)


@tasks.loop(minutes=30)
async def check_stock():
    if datetime.now().weekday() in [5, 6]:
        message = "It's the weekend. Skipping stock check."
        logging.info(message)
        print(message)
        check_stock.stop()
        return

    headers = {"User-Agent": "Mozilla/5.0", "cache-control": "max-age=0"}
    channel = bot.get_channel(CHANNEL_ID)

    for product_name in selected_products:
        product_url = PRODUCTS.get(product_name)
        if not product_url:
            message = f"Product {product_name} not found."
            logging.error(message)
            print(message)
            continue

        response = requests.get(product_url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

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

        message = f"{product_name} - {stock_status}"
        logging.info(message)
        print(message)


@bot.command(name='status')
async def status(ctx):
    now = datetime.now()
    day_of_week = now.weekday()
    status_message = f"I am running and checking {', '.join(selected_products)} stock every {check_interval} minute(s)."

    if day_of_week in [5, 6]:
        time_until_restart = time_until_next_monday()
        hours, remainder = divmod(time_until_restart.total_seconds(), 3600)
        minutes = remainder // 60
        status_message = (f"The stock check is currently disabled for the weekend.\n"
                          f"The task will restart at midnight on Monday in approximately {int(hours)} hours and {int(minutes)} minutes.")
    elif not check_stock.is_running():
        status_message += "\n(Note: The stock check task is currently stopped but can be manually restarted or will restart automatically.)"

    await ctx.send(status_message)
    print(status_message)


@bot.event
async def on_ready():
    message = f"Logged in as {bot.user}"
    logging.info(message)
    print(message)

    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            raise ValueError("Invalid CHANNEL_ID")

        check_stock.change_interval(minutes=check_interval)

        logging.info("Starting restart task loop.")
        print("Starting restart task loop.")
        asyncio.create_task(restart_task())

        if datetime.now().weekday() not in [5, 6]:
            message = "Starting stock check task since it's not the weekend."
            logging.info(message)
            print(message)
            check_stock.start()
        else:
            message = "Stock check task will remain stopped until Monday."
            logging.info(message)
            print(message)

    except Exception as e:
        message = f"Error in on_ready: {e}"
        logging.error(message)
        print(message)
        await bot.close()


@bot.command(name='clear')
async def clear(ctx):
    if ctx.author.guild_permissions.manage_messages:
        await ctx.channel.purge()
        confirmation_message = "All messages in this channel have been cleared."
        logging.info(confirmation_message)
        print(confirmation_message)
    else:
        error_message = "You do not have permission to manage messages."
        logging.warning(error_message)
        print(error_message)


@bot.command(name='log')
async def log(ctx, lines: int = 10):
    try:
        with open('stock_check.log', 'r') as log_file:
            log_lines = log_file.readlines()
            last_lines = log_lines[-lines:]  # Get the last N lines
            log_message = "```\n" + "".join(last_lines) + "\n```"

            if len(log_message) > 2000:  # Discord's message limit
                await ctx.send("Log output is too long. Try requesting fewer lines.")
            else:
                await ctx.send(log_message)

        logging.info(f"Sent last {lines} lines of the log to the channel.")
        print(f"Sent last {lines} lines of the log to the channel.")

    except Exception as e:
        error_message = f"Error reading log file: {e}"
        logging.error(error_message)
        print(error_message)
        await ctx.send(error_message)


@check_stock.before_loop
async def before_check_stock():
    await bot.wait_until_ready()

def main():
    try:
        bot.run(TOKEN)
    except Exception as e:
        message = f"Failed to run bot: {e}"
        logging.error(message)
        print(message)

if __name__ == '__main__':
    main()


