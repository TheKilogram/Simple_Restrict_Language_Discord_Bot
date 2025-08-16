import discord
import os
import csv
import re
from dotenv import load_dotenv
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
# Read the Discord bot token from an environment variable
load_dotenv()  # Ensure you have python-dotenv installed and .env file set up
TOKEN_ENV_VAR = "DISCORD_BOT_TOKEN"
discord_token = os.getenv(TOKEN_ENV_VAR)
if not discord_token:
    raise RuntimeError(f"Environment variable {TOKEN_ENV_VAR} is not set. Export your bot token before running.")

# Load restricted user IDs from a CSV file (one ID per line or first column). No header required.
def load_restricted_user_ids(path: str):
    """
    Load identifiers (user IDs, usernames, or any stable tokens) from a CSV file.
    Accepts any non-empty, non-comment first-column value (no numeric restriction).
    Lines starting with '#', blank lines are ignored.
    """
    ids = set()
    if not os.path.isfile(path):
        print(f"[WARN] Restricted user identifier CSV not found at '{path}'. No users restricted.")
        return ids
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                cell = row[0].strip()
                if not cell or cell.startswith('#'):
                    continue
                ids.add(cell)
    except Exception as e:
        print(f"[ERROR] Failed to read restricted identifiers CSV '{path}': {e}")
    return ids

# CSV path configurable via env var; defaults to file in same directory.
RESTRICTED_IDS_CSV = os.getenv("RESTRICTED_USER_IDS_CSV", "UserIDs-List.csv")
RESTRICTED_USER_IDS = load_restricted_user_ids(RESTRICTED_IDS_CSV)
print(f"Loaded {len(RESTRICTED_USER_IDS)} restricted user ID(s) from {RESTRICTED_IDS_CSV}")
if RESTRICTED_USER_IDS:
    print("Restricted identifiers (exact match against ID, username, or global_name):")
    for ident in sorted(RESTRICTED_USER_IDS):
        print(f"  - {ident}")
else:
    print("(No restricted identifiers loaded)")

bot = commands.Bot(command_prefix="!", intents=intents)

# Allowed ASCII punctuation/letters/digits plus space
ALLOWED_ASCII = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?;:'\"-@#$%&()[]{}<>_/\\|`~^+=")

# URL regex (simple): matches http/https URLs; we'll strip them before character scanning
URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)
# Discord custom emoji: <a:name:id> or <:name:id>
CUSTOM_EMOJI_REGEX = re.compile(r"<a?:[A-Za-z0-9_~]{2,}:[0-9]+>")
# Mentions: users, roles, channels (e.g., <@123>, <@!123>, <#123>, <@&123>)
MENTION_REGEX = re.compile(r"<[@#!&][0-9]+>")
# Inline code blocks / spoilers etc could be stripped if desired later.

def is_emoji(cp: int) -> bool:
    """Rudimentary emoji range detection by codepoint."""
    return (
        0x1F300 <= cp <= 0x1F5FF or
        0x1F600 <= cp <= 0x1F64F or
        0x1F680 <= cp <= 0x1F6FF or
        0x1F700 <= cp <= 0x1FAFF or  # includes many supplemental emoji blocks
        0x2600 <= cp <= 0x26FF or
        0x2700 <= cp <= 0x27BF or
        0x1F1E6 <= cp <= 0x1F1FF or  # regional indicator (flags)
        0x1F900 <= cp <= 0x1F9FF or
        0x1F3FB <= cp <= 0x1F3FF or  # skin tone modifiers
        cp in (0x200D, 0xFE0E, 0xFE0F)  # joiner / variation selectors
    )

def is_allowed_text(text: str) -> bool:
    """
    Allow: ASCII letters/digits/punctuation, whitespace, emojis, and URLs.
    Reject: Other script characters (e.g., CJK, Cyrillic, etc.) outside emoji/URL parts.
    """
    # Remove safe constructs we always allow before scanning
    scrubbed = URL_REGEX.sub('', text)
    scrubbed = CUSTOM_EMOJI_REGEX.sub('', scrubbed)
    scrubbed = MENTION_REGEX.sub('', scrubbed)
    for ch in scrubbed:
        if ch in ALLOWED_ASCII or ch.isspace():
            continue
        cp = ord(ch)
        if is_emoji(cp):
            continue
        # Anything else (foreign script) => reject
        return False
    return True

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_message(message):
    print(f"Received message from {message.author.name} (ID {message.author.id}): {message.content}")
    author_id_str = str(message.author.id)
    # Some Discord libraries expose 'global_name'; fall back gracefully.
    author_global = getattr(message.author, 'global_name', None)
    if (
        author_id_str in RESTRICTED_USER_IDS
        or message.author.name in RESTRICTED_USER_IDS
        or (author_global and author_global in RESTRICTED_USER_IDS)
    ):
        print(f"Message from restricted user {message.author.name} (ID {author_id_str}) detected.")
        if not is_allowed_text(message.content):
            await message.delete()
            try:
                await message.channel.send(
                    f"{message.author.mention}, ONLY ENGLISH!!!!!!!.",
                    delete_after=5
                )
            except discord.Forbidden:
                pass
            return
    await bot.process_commands(message)

bot.run(discord_token)
