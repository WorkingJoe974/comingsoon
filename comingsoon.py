from datetime import datetime, timedelta
from types import NoneType
import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import tasks, commands
import logging
import os
import platform
import asyncio

# Set up logging
logging.basicConfig(
    filename='stock_check.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set up console output
now = datetime.now()
formatted_now = now.strftime("%Y-%m-%d %H:%M:%S ----->")


# Function to prompt the user for input and set environment variables persistently if running on Windows
def prompt_user_for_env_variable(var_name, prompt_text):
    value = os.getenv(var_name)
    if value is None and platform.system() == 'Windows':
        value = input(prompt_text)
        os.system(f'setx {var_name} "{value}"')
    return value


# Check if the required environment variables are set, and prompt the user if running on Windows
TOKEN = prompt_user_for_env_variable('DISCORD_BOT_TOKEN', 'Please enter your Discord Bot Token: ')
CHANNEL_ID = prompt_user_for_env_variable('DISCORD_CHANNEL_ID', 'Please enter your Discord Channel ID: ')

if TOKEN is None or CHANNEL_ID is None:
    logging.error("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID environment variables must be set.")
    print(f"{formatted_now} Error: DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID environment variables must be set.")
    exit(1)

# Explicitly convert the environment variables to strings and remove whitespace
TOKEN = TOKEN.strip()
CHANNEL_ID = int(CHANNEL_ID.strip())

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix='!', intents=intents)

check_interval = 30  # Default interval in minutes
selected_products = ["RTX 5080"] # Default selected product

products = {
    "RTX 5080": "https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153",
    "RTX 5090": "https://www.bestbuy.com/site/nvidia-geforce-rtx-5090-32gb-gddr7-graphics-card-dark-gun-metal/6614151.p?skuId=6614151"
}


@tasks.loop(hours=24)
async def restart_task():
    # Calculate the time difference to the next Monday at midnight
    now = datetime.now()
    days_until_monday = (7 - now.weekday()) % 7  # Days left until Monday
    next_monday = now + timedelta(days=days_until_monday)
    midnight_next_monday = datetime.combine(next_monday.date(), datetime.min.time())

    # Calculate the delay in seconds
    delay_seconds = (midnight_next_monday - now).total_seconds()

    if delay_seconds > 0:
        print(f"{formatted_now} Waiting for {delay_seconds} seconds until midnight on Monday.")
        logging.info(f"Waiting for {delay_seconds} seconds until midnight on Monday.")
        await asyncio.sleep(delay_seconds)

    # Restart the stock check task
    if not check_stock.is_running():
        print(f"{formatted_now} It's midnight on Monday. Restarting the stock check task.")
        logging.info("It's midnight on Monday. Restarting the stock check task.")
        check_stock.start()

@bot.event
async def on_ready():
    print(f"{formatted_now} Logged in as {bot.user}")
    logging.info('Logged in as %s', bot.user)
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            raise ValueError("Invalid CHANNEL_ID")
        check_stock.change_interval(minutes=check_interval)
        restart_task.start()  # Start the task to monitor and restart at midnight Monday
        if datetime.now().weekday() not in [5, 6]:
            check_stock.start()  # Start stock check if it's a weekday
    except Exception as e:
        logging.error(f"Error with TOKEN or CHANNEL_ID: {e}")
        print(f"{formatted_now} Error with TOKEN or CHANNEL_ID: {e}")
        await bot.close()


@tasks.loop(minutes=30)
async def check_stock():
    # Check if today is Saturday (5) or Sunday (6)
    if datetime.now().weekday() in [5, 6]:
        print(f"{formatted_now} It's the weekend. Skipping stock check.")
        logging.info("It's the weekend. Skipping stock check.")
        check_stock.stop()
        return

    headers = {"User-Agent": "Mozilla/5.0", "cache-control": "max-age=0"}

    for product_name in selected_products:
        product_url = products[product_name]
        response = requests.get(product_url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        # Check for "Sold Out", "Coming Soon", and "Add to Cart"
        status_elements = soup.find_all(string=["Sold Out", "Coming Soon", "Add to Cart"])
        stock_status = "Not Found"
        channel = bot.get_channel(CHANNEL_ID)

        for element in status_elements:
            parent_div = element.find_parent("div")
            if parent_div and "Sold Out" in element:
                stock_status = "Sold Out"
            elif parent_div and "Coming Soon" in element:
                stock_status = "Coming Soon"
                await channel.send(f"{product_name} - {stock_status}")
            elif parent_div and "Add to Cart" in element:
                stock_status = "Add to Cart"
                await channel.send(f"{product_name} - {stock_status}")

        print(f"{formatted_now} {product_name} - {stock_status}")
        logging.info(f"{formatted_now} {product_name} - {stock_status}")


@bot.command(name='setproducts')
async def setproducts(ctx, *args):
    global selected_products
    valid_products = ["RTX 5080", "RTX 5090", "both"]
    selected_products = []

    for arg in args:
        if arg.lower() == "both":
            selected_products = ["RTX 5080", "RTX 5090"]
            break
        elif arg.upper() in valid_products:
            selected_products.append(arg.upper())

    if not selected_products:
        logging.info("Invalid product selection. Please choose from 'RTX 5080', 'RTX 5090', or 'both'.")
        print(f"{formatted_now} Invalid product selection. Please choose from 'RTX 5080', 'RTX 5090', or 'both'.")
        await ctx.send("Invalid product selection. Please choose from 'RTX 5080', 'RTX 5090', or 'both'.")
    else:
        logging.info(f"Selected products for stock check: {', '.join(selected_products)}")
        print(f"{formatted_now} Selected products for stock check: {', '.join(selected_products)}")
        await ctx.send(f"Selected products for stock check: {', '.join(selected_products)}")


@bot.command(name='status')
async def status(ctx):
    now = datetime.now()
    day_of_week = now.weekday()
    status_message = f"I am running and checking {', '.join(selected_products)} stock every {check_interval} minute(s)."

    if day_of_week in [5, 6]:  # Saturday or Sunday
        # Calculate time until midnight on Monday
        days_until_monday = (7 - day_of_week) % 7
        next_monday = now + timedelta(days=days_until_monday)
        midnight_next_monday = datetime.combine(next_monday.date(), datetime.min.time())
        time_until_restart = midnight_next_monday - now
        hours, remainder = divmod(time_until_restart.total_seconds(), 3600)
        minutes = remainder // 60

        status_message = (
            f"The stock check is currently disabled for the weekend.\n"
            f"The task will restart at midnight on Monday in approximately {int(hours)} hours and {int(minutes)} minutes."
        )
    elif not check_stock.is_running():
        status_message += "\n(Note: The stock check task is currently stopped but can be manually restarted or will restart automatically.)"

    print(f"{formatted_now} {status_message}")
    await ctx.send(status_message)


@bot.command(name='setinterval')
async def setinterval(ctx, minutes: int):
    global check_interval
    check_interval = minutes
    check_stock.change_interval(minutes=check_interval)
    confirmation_message = f"Stock check interval set to {check_interval} minute(s)."
    print(f"{formatted_now} {confirmation_message}")
    logging.info(confirmation_message)
    await ctx.send(confirmation_message)


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
        print(f"{formatted_now} {error_message}")
        await ctx.send(error_message)


@bot.command(name='clear')
async def clear(ctx):
    if ctx.author.guild_permissions.manage_messages:
        await ctx.channel.purge()
        confirmation_message = "All messages in this channel have been cleared."
        print(f"{formatted_now} {confirmation_message}")
        logging.info(confirmation_message)
    else:
        await ctx.send("You do not have permission to manage messages.")


@check_stock.before_loop
async def before_check_stock():
    await bot.wait_until_ready()


def main():
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Failed to run bot: {e}")
        print(f"{formatted_now} Failed to run bot: {e}")


if __name__ == '__main__':
    main()
