import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- ⚠️ YOUR CONFIGURATION ⚠️ ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"  # <--- YAHAN APNA BOT TOKEN PASTE KAREIN

MAIN_CHANNEL = "@PersonalFinanceWithShiv"
ADMIN_USERNAME = "Mr_MorningStar524"

# List of Task Channels
TASK_CHANNELS = [
    "@IAS_PrepQuiz_Zone",
    "@UPSC_Quiz_Vault",
    "@English_Speaking_Grammar_Shots",
    "@The_EnglishRoom5",
    "@SarkariJobsUpdateHub",
    "@GovernmentSchemesIndia",
    "@MinistryOfTourism"
]

# --- SETTINGS ---
REWARD_PER_CHANNEL = 5.00   # ₹5 per channel
REFER_REWARD = 0.05        # ₹5 per Invite
MIN_WITHDRAW = 500        # Min Withdraw
CURRENCY = "₹"

# Auto-Calculate Total Task Reward
TOTAL_TASK_REWARD = REWARD_PER_CHANNEL * len(TASK_CHANNELS)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Helper Functions ---
async def check_subscription(user_id, channel_username, bot):
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        return False

# --- Main Menu (English & Professional) ---
def get_main_menu_keyboard():
    keyboard = [
        [
            # Dynamic Reward Display
            InlineKeyboardButton(f"📋 Start Tasks (Earn {CURRENCY}{TOTAL_TASK_REWARD})", callback_data="tasks")
        ],
        [
            InlineKeyboardButton("💼 Wallet", callback_data="balance"),
            InlineKeyboardButton("👫 Refer & Earn", callback_data="invite")
        ],
        [
            InlineKeyboardButton("🏦 Withdraw Funds", callback_data="withdraw")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # 1. Force Subscribe Check
    if not await check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"🔒 **Access Locked!**\n\n"
            f"To access the Reward Vault, you must join our official channel first.\n\n"
            f"👉 **Step 1:** Join {MAIN_CHANNEL}\n"
            f"👉 **Step 2:** Click 'Verify Joined'"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Join Official Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify Joined", callback_data="check_join_main")]
        ]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    # 2. Referral Logic
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id == user_id: referrer_id = None

    is_new = await add_user(user_id, referrer_id, REFER_REWARD)
    
    if is_new and referrer_id:
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 **New Referral!**\n\nUser **{user.first_name}** joined via your link.\n**+{CURRENCY}{REFER_REWARD}** added to your wallet.",
                parse_mode=ParseMode.MARKDOWN
            )
        except: pass

    # Welcome Message
    welcome_text = (
        f"💎 **Welcome to Reward Vault, {user.first_name}!**\n\n"
        f"We pay you for completing simple tasks and inviting friends.\n\n"
        f"💰 **Current Rates:**\n"
        f"• Per Channel Join: **{CURRENCY}{REWARD_PER_CHANNEL}**\n"
        f"• Per Referral: **{CURRENCY}{REFER_REWARD}**\n\n"
        f"👇 **Select an option to start earning:**"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def admin_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME: return

    try:
        if len(context.args) != 2: raise ValueError()
        target_user_id = int(context.args[0])
        amount = float(context.args[1])

        new_bal = await reduce_balance(target_user_id, amount)

        if new_bal is not None:
            await update.message.reply_text(f"✅ **Transfer Confirmed!**\nUser: `{target_user_id}`\nSent: {CURRENCY}{amount}\nRemaining: {CURRENCY}{new_bal}", parse_mode=ParseMode.MARKDOWN)
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💳 **Withdrawal Processed!**\n\nYour payment of **{CURRENCY}{amount}** has been sent successfully. Check your bank/UPI.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except: pass
        else:
            await update.message.reply_text("❌ Error: User not found or Insufficient Balance.")
    except:
        await update.message.reply_text("Usage: `/paid UserID Amount`")

# --- Button Logic ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "check_join_main":
        if await check_subscription(user_id, MAIN_CHANNEL, context.bot):
            await add_user(user_id)
            welcome_text = (
                f"✅ **Verified Successfully!**\n\n"
                f"Welcome back, **{query.from_user.first_name}**.\n"
                f"Start earning by selecting a task below."
            )
            await query.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("❌ Verification Failed! Please join the channel first.", show_alert=True)

    elif data == "tasks":
        user_data = await get_user_data(user_id)
        if user_data and user_data[2] == 1:
            await query.message.reply_text("✅ **Task Completed!**\nYou have already claimed the reward for these tasks.", parse_mode=ParseMode.MARKDOWN)
            return
        
        # Dynamic Task List
        task_text = (
            f"📋 **Active Task Bundle**\n\n"
            f"Join the channels below to earn **{CURRENCY}{REWARD_PER_CHANNEL}** per channel.\n"
            f"💵 **Total Reward:** {CURRENCY}{TOTAL_TASK_REWARD}\n\n"
            f"👇 **Click links to join:**"
        )
        btns = []
        for ch in TASK_CHANNELS:
            # Format name for display
            clean_name = ch.replace("@", "").replace("_", " ")
            btns.append([InlineKeyboardButton(f"🔹 Join {clean_name}", url=f"https://t.me/{ch.replace('@', '')}")])
        
        btns.append([InlineKeyboardButton(f"💰 Claim {CURRENCY}{TOTAL_TASK_REWARD} Reward 💰", callback_data="claim_task")])
        
        await query.message.reply_text(task_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif data == "claim_task":
        not_joined = []
        for ch in TASK_CHANNELS:
            if not await check_subscription(user_id, ch, context.bot):
                not_joined.append(ch)
        
        if not not_joined:
            # Success - Join kiya hai
            if await complete_task_reward(user_id, TOTAL_TASK_REWARD):
                success_text = (
                    f"🎉 **Task Completed Successfully!**\n\n"
                    f"You joined all channels.\n"
                    f"💵 **{CURRENCY}{TOTAL_TASK_REWARD}** has been added to your wallet!\n\n"
                    f"Check your balance."
                )
                await query.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.message.reply_text("⚠️ **Error:** Reward already claimed.", parse_mode=ParseMode.MARKDOWN)
        else:
            # Failure - Kuch channel reh gaye
            failed_text = (
                f"❌ **Task Incomplete!**\n\n"
                f"You missed some channels. Join them to claim **{CURRENCY}{TOTAL_TASK_REWARD}**:\n\n"
            ) + "\n".join([f"🔸 {ch}" for ch in not_joined])
            await query.message.reply_text(failed_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "balance":
        d = await get_user_data(user_id)
        bal_text = (
            f"💼 **My Wallet**\n\n"
            f"💵 **Balance:** `{CURRENCY}{d[0]:.2f}`\n"
            f"👥 **Total Referrals:** `{d[1]}`\n\n"
            f"Min Withdrawal: {CURRENCY}{MIN_WITHDRAW}"
        )
        await query.message.reply_text(bal_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "invite":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        invite_text = (
            f"🤝 **Refer & Earn**\n\n"
            f"Invite your friends and earn **{CURRENCY}{REFER_REWARD}** for every successful join!\n\n"
            f"🔗 **Your Referral Link:**\n"
            f"`{link}`\n\n"
            f"_Tap link to copy_"
        )
        await query.message.reply_text(invite_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "withdraw":
        d = await get_user_data(user_id)
        if d[0] >= MIN_WITHDRAW:
            msg = (
                f"🏦 **Withdrawal Request**\n\n"
                f"You are eligible for withdrawal!\n"
                f"Available Balance: **{CURRENCY}{d[0]:.2f}**\n\n"
                f"📩 **Send your UPI/Bank details to:**\n"
                f"👤 @{ADMIN_USERNAME}"
            )
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer(f"❌ Insufficient Funds! Min: {CURRENCY}{MIN_WITHDRAW}", show_alert=True)

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
    app.run_polling()    if user.username != ADMIN_USERNAME: return

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
