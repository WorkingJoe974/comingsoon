from datetime import datetime
from types import NoneType
import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import tasks, commands
import logging
import os
import platform

# Set up logging
logging.basicConfig(
    filename='stock_check.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


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
    print("Error: DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID environment variables must be set.")
    exit(1)


# Explicitly convert the environment variables to strings and remove whitespace
TOKEN = TOKEN.strip()
CHANNEL_ID = int(CHANNEL_ID)


intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix='!', intents=intents)


check_interval = 30  # Default interval in minutes


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    logging.info('Logged in as %s', bot.user)
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            raise ValueError("Invalid CHANNEL_ID")
        check_stock.change_interval(minutes=check_interval)
        check_stock.start()
    except Exception as e:
        logging.error(f"Error with TOKEN or CHANNEL_ID: {e}")
        print(f"Error with TOKEN or CHANNEL_ID: {e}")
        await bot.close()


@tasks.loop(minutes=30)
async def check_stock():
    global stock_status
    url = "https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153"
    headers = {"User-Agent": "Mozilla/5.0", "cache-control": "max-age=0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    # Check for "Sold Out", "Coming Soon", and "Add to Cart"
    status_elements = soup.find_all(string=["Sold Out", "Coming Soon", "Add to Cart"])


    now = datetime.now()
    formatted_now = now.strftime("%Y-%m-%d %H:%M:%S")


    channel = bot.get_channel(CHANNEL_ID)

    for element in status_elements:
        parent_div = element.find_parent("div")
        if parent_div and "Sold Out" in element:
            stock_status = "Sold Out"
        elif parent_div and "Coming Soon" in element:
            stock_status = "Coming Soon"
            await channel.send(stock_status)
        elif parent_div and "Add to Cart" in element:
            stock_status = "Add to Cart"
            await channel.send(stock_status)


    print(formatted_now + " ----->", stock_status)
    logging.info(formatted_now + " -----> " + stock_status)


@bot.command(name='status')
async def status(ctx):
    status_message = f"I am running and checking stock every {check_interval} minute(s)"
    print(status_message)
    await ctx.send(status_message)


@bot.command(name='setinterval')
async def setinterval(ctx, minutes: int):
    global check_interval
    check_interval = minutes
    check_stock.change_interval(minutes=check_interval)
    confirmation_message = f"Stock check interval set to {check_interval} minute(s)."
    print(confirmation_message)
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
        print(error_message)
        await ctx.send(error_message)


@bot.command(name='clear')
async def clear(ctx):
    if ctx.author.guild_permissions.manage_messages:
        await ctx.channel.purge()
        confirmation_message = "All messages in this channel have been cleared."
        print(confirmation_message)
        logging.info(confirmation_message)
    else:
        await ctx.send("You do not have permission to manage messages.")


@check_stock.before_loop
async def before_check_stock():
    await bot.wait_until_ready()


try:
    bot.run(TOKEN)
except Exception as e:
    logging.error(f"Failed to run bot: {e}")
    print(f"Failed to run bot: {e}")
