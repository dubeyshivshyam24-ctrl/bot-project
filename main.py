import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- ⚠️ CONFIGURATION ⚠️ ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"  # <--- Token Yahan Dalein

MAIN_CHANNEL = "@PersonalFinanceWithShiv"   # Main Entry Gate
ADMIN_USERNAME = "Mr_MorningStar524"

# Task Channels (Sequence mein)
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
REWARD_PER_CHANNEL = 5.00   
REFER_REWARD = 0.05         
MIN_WITHDRAW = 500
CURRENCY = "₹"

# Total Reward
TOTAL_TASK_REWARD = REWARD_PER_CHANNEL * len(TASK_CHANNELS)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Helper: Check Subscription ---
async def check_subscription(user_id, channel_username, bot):
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        return False

# --- Helper: Check All Channels (For Strict Lock) ---
async def get_missing_channels(user_id, bot):
    missing = []
    # Pehle Main Channel Check
    if not await check_subscription(user_id, MAIN_CHANNEL, bot):
        missing.append(MAIN_CHANNEL)
    # Phir Task Channels Check
    for ch in TASK_CHANNELS:
        if not await check_subscription(user_id, ch, bot):
            missing.append(ch)
    return missing

# --- Helper: Get Next Pending Task (Step-by-Step Logic) ---
async def get_next_pending_channel_index(user_id, bot):
    for index, ch in enumerate(TASK_CHANNELS):
        if not await check_subscription(user_id, ch, bot):
            return index # Ye wala channel bacha hai
    return -1 # Sab complete hai

# --- Menus ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"🚀 Start Tasks | Earn {CURRENCY}{TOTAL_TASK_REWARD}", callback_data="start_task_flow")],
        [InlineKeyboardButton("💼 Wallet", callback_data="balance"), InlineKeyboardButton("🔥 Refer & Earn", callback_data="invite")],
        [InlineKeyboardButton("🏦 Withdraw Money", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Sirf Entry ke liye Main Channel Check (Baaki andar check honge)
    if not await check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"🔒 **Access Restricted**\n\n"
            f"To unlock the **Reward Vault**, please join our official channel.\n\n"
            f"👉 **Required:** {MAIN_CHANNEL}\n"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Join Official Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify Access", callback_data="check_join_main")]
        ]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    # Database Entry
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id == user_id: referrer_id = None

    is_new = await add_user(user_id, referrer_id, REFER_REWARD)
    if is_new and referrer_id:
        try:
            await context.bot.send_message(chat_id=referrer_id, text=f"🎉 **New Referral!**\nReward: +{CURRENCY}{REFER_REWARD}", parse_mode=ParseMode.MARKDOWN)
        except: pass

    welcome_text = (
        f"👋 **Welcome, {user.first_name}!**\n\n"
        f"Complete tasks step-by-step to earn rewards.\n\n"
        f"📊 **Rates:**\n"
        f"├ Task Bundle: `{CURRENCY}{TOTAL_TASK_REWARD:.2f}`\n"
        f"└ Per Refer: `{CURRENCY}{REFER_REWARD:.2f}`\n\n"
        f"👇 *Select an option:*"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    bot = context.bot
    await query.answer()

    # --- ENTRY VERIFICATION ---
    if data == "check_join_main":
        if await check_subscription(user_id, MAIN_CHANNEL, bot):
            await add_user(user_id)
            await query.message.edit_text(f"✅ **Verified!**\nWelcome {query.from_user.first_name}.", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("❌ Not Joined Yet!", show_alert=True)

    # --- STEP-BY-STEP TASK FLOW ---
    elif data == "start_task_flow" or data == "verify_step":
        # Check karein user ne pehle hi reward le liya hai kya?
        user_data = await get_user_data(user_id)
        if user_data and user_data[2] == 1:
             await query.message.edit_text("✅ **All Tasks Completed!**\n\nYou have already claimed the full reward.", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
             return

        # Pata karo kaunsa channel bacha hai
        next_index = await get_next_pending_channel_index(user_id, bot)

        # Agar -1 aaya, matlab sab join kar liye -> Reward Do
        if next_index == -1:
            if await complete_task_reward(user_id, TOTAL_TASK_REWARD):
                success_text = (
                    f"🎉 **Congratulations!** 🎉\n\n"
                    f"You have successfully completed all steps.\n"
                    f"💵 **{CURRENCY}{TOTAL_TASK_REWARD}** has been added to your wallet!\n\n"
                    f"Keep earning by inviting friends."
                )
                await query.message.edit_text(success_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
            else:
                await query.message.edit_text("⚠️ **Reward Already Claimed.**", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
            return

        # Agar koi channel bacha hai, to sirf wahi dikhao
        current_channel = TASK_CHANNELS[next_index]
        clean_name = current_channel.replace("@", "").replace("_", " ")
        
        step_text = (
            f"📋 **Task Progress: Step {next_index + 1} of {len(TASK_CHANNELS)}**\n\n"
            f"To proceed to the next step, you must join this channel:\n\n"
            f"👉 **Target:** {current_channel}\n\n"
            f"⚠️ *Click 'Verify & Next' after joining.*"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"🔹 Join {clean_name} ↗️", url=f"https://t.me/{current_channel.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify & Next Step ➡️", callback_data="verify_step")]
        ]
        
        # Message Update karo (Naya message nahi bhejega, usi ko badlega - Professional lagta hai)
        try:
            await query.message.edit_text(step_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        except:
            # Agar message same hai to error na aaye
            pass

    # --- STRICT LOCK ON WITHDRAW/INVITE ---
    elif data in ["withdraw", "invite", "balance"]:
        # User click kare to pehle check karo ki saare channels joined hain ya nahi
        missing = await get_missing_channels(user_id, bot)
        
        if missing:
            # Agar ek bhi channel missing hai to Block karo
            error_text = (
                f"🚫 **Action Blocked!**\n\n"
                f"We noticed you unsubscribed from some channels.\n"
                f"To use this feature, you must maintain active membership.\n\n"
                f"👇 **Please Re-Join:**\n"
            ) + "\n".join([f"🔸 {ch}" for ch in missing])
            
            # Re-join buttons
            btns = [[InlineKeyboardButton(f"Join {ch.replace('@','')}", url=f"https://t.me/{ch.replace('@','')}") for ch in missing]]
            btns.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="check_join_main")])
            
            await query.message.edit_text(error_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
            return

        # Agar sab sahi hai to normal kaam karo
        if data == "balance":
            d = await get_user_data(user_id)
            await query.message.edit_text(f"💼 **Wallet**\n💰 Balance: `{CURRENCY}{d[0]:.2f}`\n👥 Refers: `{d[1]}`", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

        elif data == "invite":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            await query.message.edit_text(f"🔗 **Referral Link:**\n`{link}`\n\nReward: {CURRENCY}{REFER_REWARD} per user.", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

        elif data == "withdraw":
            d = await get_user_data(user_id)
            if d[0] >= MIN_WITHDRAW:
                await query.message.edit_text(f"✅ **Withdrawal Open**\nMsg Admin: @{ADMIN_USERNAME}", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
            else:
                await query.answer(f"❌ Min Withdraw: {CURRENCY}{MIN_WITHDRAW}", show_alert=True)

# --- ADMIN PAID (Same as before) ---
async def admin_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME: return
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        new_bal = await reduce_balance(uid, amt)
        if new_bal is not None:
            await update.message.reply_text(f"✅ Paid {CURRENCY}{amt}")
            try: await context.bot.send_message(uid, f"🏧 Withdrawal of {CURRENCY}{amt} received!")
            except: pass
    except: pass

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
