"""
Currency Converter Telegram Bot
@currencyconverter2003Bot
Deployed on Railway.app
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ============ Configuration & Setup ============

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Get environment variables from Railway
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set!")
    raise ValueError("TELEGRAM_TOKEN is required")

# API Configuration
EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/"

# Supported Currencies with emojis
CURRENCIES = {
    "USD": {"name": "US Dollar", "emoji": "🇺🇸"},
    "EUR": {"name": "Euro", "emoji": "🇪🇺"},
    "GBP": {"name": "British Pound", "emoji": "🇬🇧"},
    "JPY": {"name": "Japanese Yen", "emoji": "🇯🇵"},
    "AUD": {"name": "Australian Dollar", "emoji": "🇦🇺"},
    "CAD": {"name": "Canadian Dollar", "emoji": "🇨🇦"},
    "CHF": {"name": "Swiss Franc", "emoji": "🇨🇭"},
    "CNY": {"name": "Chinese Yuan", "emoji": "🇨🇳"},
    "INR": {"name": "Indian Rupee", "emoji": "🇮🇳"},
    "BRL": {"name": "Brazilian Real", "emoji": "🇧🇷"},
    "ZAR": {"name": "South African Rand", "emoji": "🇿🇦"},
    "NGN": {"name": "Nigerian Naira", "emoji": "🇳🇬"},
    "KES": {"name": "Kenyan Shilling", "emoji": "🇰🇪"},
    "GHS": {"name": "Ghanaian Cedi", "emoji": "🇬🇭"},
    "EGP": {"name": "Egyptian Pound", "emoji": "🇪🇬"},
    "MXN": {"name": "Mexican Peso", "emoji": "🇲🇽"},
    "SGD": {"name": "Singapore Dollar", "emoji": "🇸🇬"},
    "NZD": {"name": "New Zealand Dollar", "emoji": "🇳🇿"},
    "KRW": {"name": "South Korean Won", "emoji": "🇰🇷"},
    "RUB": {"name": "Russian Ruble", "emoji": "🇷🇺"},
}

# Store user session data
user_sessions: Dict[int, Dict] = {}

# Exchange rate cache
rate_cache = {
    "data": None,
    "timestamp": None,
    "base": None,
}


# ============ Helper Functions ============

def get_exchange_rates(base_currency: str = "USD") -> Optional[Dict]:
    """
    Fetch exchange rates from API with caching
    """
    global rate_cache
    
    # Check cache (valid for 5 minutes)
    if (
        rate_cache["data"] 
        and rate_cache["base"] == base_currency
        and rate_cache["timestamp"]
        and (datetime.now() - rate_cache["timestamp"]).seconds < 300
    ):
        return rate_cache["data"]
    
    try:
        url = f"{EXCHANGE_API_URL}{base_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Update cache
        rate_cache["data"] = data.get("rates", {})
        rate_cache["base"] = base_currency
        rate_cache["timestamp"] = datetime.now()
        
        return rate_cache["data"]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse API response: {e}")
        return None


def convert_currency(
    amount: float, from_currency: str, to_currency: str
) -> Optional[Tuple[float, float]]:
    """
    Convert amount between currencies
    Returns: (converted_amount, exchange_rate) or None on error
    """
    rates = get_exchange_rates(from_currency)
    if not rates:
        return None
    
    rate = rates.get(to_currency)
    if not rate:
        return None
    
    converted = amount * rate
    return (round(converted, 2), round(rate, 4))


def get_currency_display(code: str) -> str:
    """Get formatted currency display with emoji"""
    currency = CURRENCIES.get(code.upper())
    if currency:
        return f"{currency['emoji']} {code.upper()}"
    return f"🌐 {code.upper()}"


def format_currency_list() -> str:
    """Format currency list for display"""
    lines = ["📊 *Supported Currencies*\n"]
    lines.append("I can convert between these currencies:\n")
    
    for code, info in CURRENCIES.items():
        lines.append(f"{info['emoji']} `{code}` - {info['name']}")
    
    lines.append("\n_Type /convert to start converting!_")
    return "\n".join(lines)


def create_currency_keyboard(
    prefix: str, exclude: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard with currency buttons
    """
    keyboard = []
    row = []
    
    for code in CURRENCIES.keys():
        if exclude and code == exclude:
            continue
        button = InlineKeyboardButton(
            get_currency_display(code), callback_data=f"{prefix}_{code}"
        )
        row.append(button)
        if len(row) == 3:  # 3 buttons per row
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Add control buttons
    keyboard.append([
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


def create_main_menu() -> InlineKeyboardMarkup:
    """Create the main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Convert Currency", callback_data="convert"),
            InlineKeyboardButton("📊 View Currencies", callback_data="list"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ============ Command Handlers ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    # Clear any existing session
    user_sessions.pop(user_id, None)
    
    welcome_text = (
        f"👋 *Welcome {user.first_name}!*\n\n"
        "💱 I'm your **Currency Converter Bot**!\n"
        "I can help you convert between 20+ currencies in real-time.\n\n"
        "✨ *What I can do:*\n"
        "• Interactive currency conversion\n"
        "• Quick conversion like `10 USD to EUR`\n"
        "• Real-time exchange rates\n"
        "• 20+ supported currencies\n\n"
        "📱 *Choose an option below or type /help*"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=create_main_menu(),
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_text = (
        "📚 *Help & Usage Guide*\n\n"
        "🔹 *Interactive Conversion*\n"
        "Type `/convert` and follow the steps\n\n"
        "🔹 *Quick Conversion*\n"
        "Type `10 USD to EUR` directly\n"
        "Example: `100 NGN to USD`\n\n"
        "🔹 *Commands*\n"
        "`/start` - Welcome message\n"
        "`/help` - This guide\n"
        "`/convert` - Start conversion\n"
        "`/list` - Show all currencies\n"
        "`/about` - Bot information\n\n"
        "💡 *Tips*\n"
        "• Use 3-letter currency codes\n"
        "• Amounts can be decimals: `10.50`\n"
        "• Rates update every 5 minutes"
    )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /about command"""
    about_text = (
        "ℹ️ *About This Bot*\n\n"
        "🤖 **Currency Converter Bot**\n"
        f"📱 Username: @{context.bot.username}\n"
        "🔧 Version: 1.0.0\n\n"
        "⚡ *Features*\n"
        "• Real-time exchange rates\n"
        "• 20+ currencies supported\n"
        "• Interactive conversion\n"
        "• Quick text conversion\n\n"
        "📦 *Powered by*\n"
        "• Python 3.11\n"
        "• python-telegram-bot v20.7\n"
        "• Exchange Rate API\n"
        "• Deployed on Railway\n\n"
        "💻 *Source Code*\n"
        "Available on GitHub"
    )
    
    await update.message.reply_text(about_text, parse_mode="Markdown")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command"""
    await update.message.reply_text(
        format_currency_list(),
        parse_mode="Markdown",
    )


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /convert command - Start conversion flow"""
    user_id = update.effective_user.id
    
    # Initialize session
    user_sessions[user_id] = {"step": "select_from"}
    
    await update.message.reply_text(
        "🌍 *Step 1: Select Base Currency*\n\n"
        "Choose the currency you want to convert **FROM**:\n"
        "_(Use the buttons below)_",
        reply_markup=create_currency_keyboard("from"),
        parse_mode="Markdown",
    )


# ============ Callback Handlers ============

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all callback queries from inline buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Handle main menu actions
    if data in ["convert", "list", "help", "about"]:
        if data == "convert":
            await convert_command(update, context)
        elif data == "list":
            await query.edit_message_text(
                format_currency_list(),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back")]
                ])
            )
        elif data == "help":
            await query.edit_message_text(
                "📚 *Help & Usage Guide*\n\n"
                "🔹 Type `/convert` for interactive conversion\n"
                "🔹 Type `10 USD to EUR` for quick conversion\n"
                "🔹 Type `/list` to see all currencies",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back")]
                ])
            )
        elif data == "about":
            await query.edit_message_text(
                "ℹ️ *Currency Converter Bot*\n"
                f"📱 @{context.bot.username}\n"
                "⚡ Real-time exchange rates\n"
                "🌍 20+ currencies supported",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back")]
                ])
            )
        return
    
    # Handle back button
    if data == "back":
        await query.edit_message_text(
            "👋 Welcome back! What would you like to do?",
            reply_markup=create_main_menu(),
            parse_mode="Markdown",
        )
        return
    
    # Handle cancel
    if data == "cancel":
        user_sessions.pop(user_id, None)
        await query.edit_message_text(
            "❌ *Conversion Cancelled*\n\n"
            "Type `/convert` to start again, or `/help` for assistance.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Start New", callback_data="convert")]
            ])
        )
        return
    
    # Handle currency selection
    if data.startswith("from_"):
        from_currency = data.replace("from_", "")
        user_sessions[user_id]["from_currency"] = from_currency
        user_sessions[user_id]["step"] = "select_to"
        
        await query.edit_message_text(
            f"✅ *Base Currency Selected:* {get_currency_display(from_currency)}\n\n"
            "🌍 *Step 2: Select Target Currency*\n"
            "Choose the currency you want to convert **TO**:",
            reply_markup=create_currency_keyboard("to", exclude=from_currency),
            parse_mode="Markdown",
        )
        
    elif data.startswith("to_"):
        to_currency = data.replace("to_", "")
        from_currency = user_sessions[user_id].get("from_currency")
        
        if not from_currency:
            await query.edit_message_text(
                "❌ *Session Error*\n\n"
                "Please start again with /convert",
                parse_mode="Markdown"
            )
            user_sessions.pop(user_id, None)
            return
        
        user_sessions[user_id]["to_currency"] = to_currency
        user_sessions[user_id]["step"] = "enter_amount"
        
        await query.edit_message_text(
            f"✅ *Conversion Setup Complete*\n\n"
            f"🔄 {get_currency_display(from_currency)} → {get_currency_display(to_currency)}\n\n"
            "💰 *Step 3: Enter Amount*\n"
            "Type the amount you want to convert\n"
            "(e.g., `100` or `100.50`)",
            parse_mode="Markdown",
        )


# ============ Message Handlers ============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Check if user is in conversion flow
    if user_id in user_sessions:
        session = user_sessions[user_id]
        step = session.get("step")
        
        if step == "enter_amount":
            try:
                amount = float(text)
                if amount <= 0:
                    await update.message.reply_text(
                        "❌ *Invalid Amount*\n\n"
                        "Please enter a positive number.\n"
                        "Type `/convert` to start over.",
                        parse_mode="Markdown"
                    )
                    return
                
                from_currency = session["from_currency"]
                to_currency = session["to_currency"]
                
                # Perform conversion
                result = convert_currency(amount, from_currency, to_currency)
                
                if result:
                    converted, rate = result
                    
                    response = (
                        f"✅ *Conversion Complete*\n\n"
                        f"{get_currency_display(from_currency)} *{amount:,.2f}*\n"
                        f"⬇️ *{rate:,.4f}* exchange rate\n"
                        f"{get_currency_display(to_currency)} *{converted:,.2f}*\n\n"
                        f"📊 Rate: 1 {from_currency} = {rate} {to_currency}"
                    )
                    
                    # Clear session after successful conversion
                    user_sessions.pop(user_id, None)
                    
                    await update.message.reply_text(
                        response,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 New Conversion", callback_data="convert")]
                        ])
                    )
                else:
                    await update.message.reply_text(
                        "❌ *Error*\n\n"
                        "Failed to get exchange rates.\n"
                        "Please try again later.\n"
                        "Type `/convert` to start over.",
                        parse_mode="Markdown"
                    )
                    
            except ValueError:
                await update.message.reply_text(
                    "❌ *Invalid Input*\n\n"
                    "Please enter a valid number.\n"
                    "Example: `100` or `100.50`\n"
                    "Type `/convert` to start over.",
                    parse_mode="Markdown"
                )
            return
    
    # Quick conversion: "10 USD to EUR"
    pattern = r"^(\d+\.?\d*)\s+([A-Za-z]{3})\s+to\s+([A-Za-z]{3})$"
    match = re.match(pattern, text, re.IGNORECASE)
    
    if match:
        amount = float(match.group(1))
        from_currency = match.group(2).upper()
        to_currency = match.group(3).upper()
        
        # Validate currencies
        if from_currency not in CURRENCIES:
            await update.message.reply_text(
                f"❌ *Unsupported Currency*\n\n"
                f"`{from_currency}` is not supported.\n"
                f"Type `/list` to see all supported currencies.",
                parse_mode="Markdown"
            )
            return
            
        if to_currency not in CURRENCIES:
            await update.message.reply_text(
                f"❌ *Unsupported Currency*\n\n"
                f"`{to_currency}` is not supported.\n"
                f"Type `/list` to see all supported currencies.",
                parse_mode="Markdown"
            )
            return
        
        # Perform conversion
        result = convert_currency(amount, from_currency, to_currency)
        
        if result:
            converted, rate = result
            
            response = (
                f"⚡ *Quick Conversion*\n\n"
                f"{get_currency_display(from_currency)} *{amount:,.2f}*\n"
                f"⬇️ Rate: *{rate:,.4f}*\n"
                f"{get_currency_display(to_currency)} *{converted:,.2f}*\n\n"
                f"🕐 Rates are real-time"
            )
            
            await update.message.reply_text(
                response,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Convert More", callback_data="convert")]
                ])
            )
        else:
            await update.message.reply_text(
                "❌ *Error*\n\n"
                "Failed to get exchange rates.\n"
                "Please try again later.",
                parse_mode="Markdown"
            )
        return
    
    # If not a command and not recognized
    await update.message.reply_text(
        "🤔 *I didn't understand that*\n\n"
        "You can:\n"
        "• Type `/convert` for interactive conversion\n"
        "• Type `10 USD to EUR` for quick conversion\n"
        "• Type `/help` for assistance",
        parse_mode="Markdown"
    )


# ============ Error Handler ============

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ *Oops! Something went wrong*\n\n"
                "Please try again later.\n"
                "If the problem persists, contact the bot admin.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")


# ============ Startup Handler ============

async def post_init(application: Application) -> None:
    """Actions to run after bot starts"""
    logger.info(f"Bot started: @{application.bot.username}")
    logger.info("Currency Converter Bot is ready!")


# ============ Main Function ============

def main() -> None:
    """Main entry point"""
    logger.info("Starting Currency Converter Bot...")
    
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("list", list_command))
        application.add_handler(CommandHandler("convert", convert_command))
        
        # Add callback query handler
        application.add_handler(CallbackQueryHandler(handle_callback))
        
        # Add message handler (must be after command handlers)
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Start bot with polling
        logger.info("Bot is polling for updates...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()
