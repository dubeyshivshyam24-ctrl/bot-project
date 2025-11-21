import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- CONFIGURATION (Yahan sirf TOKEN bharna baki hai) ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"  # <--- ⚠️ YAHAN APNA BOT TOKEN PASTE KAREIN

MAIN_CHANNEL = "@PersonalFinanceWithShiv"   # Aapka Main Channel
ADMIN_USERNAME = "Mr_MorningStar524"        # Aapka Admin ID (Bina @ ke)

# Task Wale Saare Channels
TASK_CHANNELS = [
    "@IAS_PrepQuiz_Zone",
    "@UPSC_Quiz_Vault",
    "@English_Speaking_Grammar_Shots",
    "@The_EnglishRoom5",
    "@SarkariJobsUpdateHub",
    "@GovernmentSchemesIndia",
    "@MinistryOfTourism"
]

# --- MONEY SETTINGS ---
REFER_REWARD = 0.5   # Per Refer
TASK_REWARD = 5  # Task Complete karne par
MIN_WITHDRAW = 500   # Min Withdrawal
CURRENCY = "₹"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Helper Functions ---
async def check_subscription(user_id, channel_username, bot):
    try:
        # Check karein user member hai ya nahi
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        return False

# --- Main Menu Design ---
def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(f"📋 Complete Tasks ({CURRENCY}{TASK_REWARD})", callback_data="tasks")
        ],
        [
            InlineKeyboardButton("💰 Wallet", callback_data="balance"),
            InlineKeyboardButton("👥 Invite", callback_data="invite")
        ],
        [
            InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # 1. Force Subscribe Check (Main Channel)
    if not await check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"⚠️ **Access Denied!** ⚠️\n\n"
            f"Bot use karne ke liye pehle hamara Main Channel join karein:\n"
            f"👉 {MAIN_CHANNEL}\n\n"
            f"Join karne ke baad **'✅ Check Joined'** button dabayein."
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Join Main Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("✅ Check Joined", callback_data="check_join_main")]
        ]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    # 2. Referral System
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id == user_id: referrer_id = None

    is_new = await add_user(user_id, referrer_id, REFER_REWARD)
    
    # Referrer ko bonus dena
    if is_new and referrer_id:
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 **Naya Referral!** 🎉\nUser {user.first_name} ne join kiya.\n**+{CURRENCY}{REFER_REWARD}** added to wallet.",
                parse_mode=ParseMode.MARKDOWN
            )
        except: pass

    # Welcome Message
    welcome_text = (
        f"👋 **Hello, {user.first_name}!**\n\n"
        f"**Reward Vault Bot** mein swagat hai. 🤖\n"
        f"Yahan tasks complete karein aur refer karke paise kamayein.\n\n"
        f"👇 **Menu:**"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

# --- Admin Payment Command ---
async def admin_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME: return

    try:
        if len(context.args) != 2: raise ValueError()
        target_user_id = int(context.args[0])
        amount = float(context.args[1])

        new_bal = await reduce_balance(target_user_id, amount)

        if new_bal is not None:
            await update.message.reply_text(f"✅ **Paid!**\nUser: `{target_user_id}`\nAmount: {CURRENCY}{amount}\nRem Balance: {CURRENCY}{new_bal}", parse_mode=ParseMode.MARKDOWN)
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🥳 **Withdrawal Successful!**\n\nAapka **{CURRENCY}{amount}** ka payment bhej diya gaya hai. ✅",
                    parse_mode=ParseMode.MARKDOWN
                )
            except: pass
        else:
            await update.message.reply_text("❌ Error: User not found or Low Balance.")
    except:
        await update.message.reply_text("Use: `/paid UserID Amount`")

# --- Buttons Logic ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "check_join_main":
        if await check_subscription(user_id, MAIN_CHANNEL, context.bot):
            await add_user(user_id)
            welcome_text = (
                f"👋 **Hello, {query.from_user.first_name}!**\n\n"
                f"**Reward Vault Bot** mein swagat hai. 🤖\n"
                f"Yahan tasks complete karein aur refer karke paise kamayein.\n\n"
                f"👇 **Menu:**"
            )
            await query.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("❌ Not Joined! Pehle channel join karein.", show_alert=True)

    elif data == "tasks":
        user_data = await get_user_data(user_id)
        if user_data and user_data[2] == 1:
            await query.message.reply_text("✅ **Task Completed!**\nAap ye task pehle hi kar chuke hain.", parse_mode=ParseMode.MARKDOWN)
            return
        
        task_text = (
            f"📋 **Task List:**\n"
            f"Niche diye gaye sabhi channels join karein aur **{CURRENCY}{TASK_REWARD}** paayein! 👇"
        )
        btns = []
        for ch in TASK_CHANNELS:
            # Button text clean karne ke liye
            display_name = ch.replace("@", "").replace("_", " ")
            btns.append([InlineKeyboardButton(f"Join {display_name} ↗️", url=f"https://t.me/{ch.replace('@', '')}")])
        
        btns.append([InlineKeyboardButton("💰 Claim Reward 💰", callback_data="claim_task")])
        
        await query.message.reply_text(task_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif data == "claim_task":
        not_joined = []
        for ch in TASK_CHANNELS:
            if not await check_subscription(user_id, ch, context.bot):
                not_joined.append(ch)
        
        if not not_joined:
            if await complete_task_reward(user_id, TASK_REWARD):
                await query.message.reply_text(f"🎉 **Success!**\nTask complete hua. **{CURRENCY}{TASK_REWARD}** added!", parse_mode=ParseMode.MARKDOWN)
            else:
                await query.message.reply_text("⚠️ Reward already claimed.", parse_mode=ParseMode.MARKDOWN)
        else:
            failed_text = "❌ **Task Pending!**\n\nAapne ye channels join nahi kiye:\n" + "\n".join(not_joined)
            await query.message.reply_text(failed_text)

    elif data == "balance":
        d = await get_user_data(user_id)
        bal_text = (
            f"🏦 **Wallet Status**\n\n"
            f"💰 Balance: `{CURRENCY}{d[0]:.2f}`\n"
            f"👥 Referrals: `{d[1]}`"
        )
        await query.message.reply_text(bal_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "invite":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        invite_text = (
            f"📣 **Refer & Earn**\n\n"
            f"Share karein aur kamayein **{CURRENCY}{REFER_REWARD}** per friend!\n\n"
            f"👇 **Aapka Link:**\n`{link}`"
        )
        await query.message.reply_text(invite_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "withdraw":
        d = await get_user_data(user_id)
        if d[0] >= MIN_WITHDRAW:
            msg = (
                f"✅ **Withdrawal Open**\n\n"
                f"Payment ke liye Admin ko message karein:\n"
                f"👤 @{ADMIN_USERNAME}\n\n"
                f"Balance: {CURRENCY}{d[0]:.2f}"
            )
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer(f"❌ Balance kam hai! Min: {CURRENCY}{MIN_WITHDRAW}", show_alert=True)

if __name__ == '__main__':
    keep_alive()
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("paid", admin_paid))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
