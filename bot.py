import os
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = "7978339304:AAESYFoIzMymbwoc4Vfsg3TyAmcR0MQOp_c"
ADMIN_ID = 7112285392
CHANNEL_USERNAME = "@V2File_Mamad"
BASE_DIR = "configs"
PRICE_FILE = "prices.json"

CATEGORIES = ["free", "paid", "vip"]
DEFAULT_PRICES = {"paid": 50000, "vip": 100000}

# ساخت پوشه‌ها و فایل قیمت با پیغام چاپی
for cat in CATEGORIES:
    folder = os.path.join(BASE_DIR, cat)
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"پوشه {folder} ساخته شد.")
    else:
        print(f"پوشه {folder} قبلاً وجود داشت.")

if not os.path.exists(PRICE_FILE):
    with open(PRICE_FILE, "w") as f:
        json.dump(DEFAULT_PRICES, f)

with open(PRICE_FILE) as f:
    prices = json.load(f)

admin_pending_files = {}
admin_waiting_for_price = False
pending_payments = {}  # user_id -> {'category': ..., 'filename': ...}

# منوی اصلی
def get_main_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("📥 فایل رایگان", callback_data="get_free")],
        [InlineKeyboardButton("💰 فایل پولی", callback_data="list_paid")],
        [InlineKeyboardButton("🌟 فایل VIP", callback_data="list_vip")],
        [InlineKeyboardButton("ℹ️ درباره ما", callback_data="about")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("💵 تنظیم قیمت", callback_data="set_price")])
    return InlineKeyboardMarkup(keyboard)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = (user_id == ADMIN_ID)
    await update.message.reply_text(
        "🎉 خوش اومدی! یکی از گزینه‌های زیر رو انتخاب کن 👇",
        reply_markup=get_main_menu(is_admin)
    )

# وقتی ادمین فایل میفرسته
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ فقط ادمین می‌تونه فایل بفرسته.")
        return

    doc: Document = update.message.document
    admin_pending_files[user_id] = {
        "file_id": doc.file_id,
        "file_name": doc.file_name
    }

    keyboard = [
        [InlineKeyboardButton("🔓 رایگان", callback_data="save_free")],
        [InlineKeyboardButton("💰 پولی", callback_data="save_paid")],
        [InlineKeyboardButton("🌟 VIP", callback_data="save_vip")]
    ]
    await update.message.reply_text("📁 فایل رو تو کدوم دسته ذخیره کنم؟", reply_markup=InlineKeyboardMarkup(keyboard))

# ذخیره فایل در دسته
async def save_file_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in admin_pending_files:
        await query.edit_message_text("❗️فایلی در صف ذخیره نیست.")
        return

    data = admin_pending_files.pop(user_id)
    category = query.data.replace("save_", "")
    folder_path = os.path.join(BASE_DIR, category)
    file_path = os.path.join(folder_path, data["file_name"])

    file = await context.bot.get_file(data["file_id"])
    await file.download_to_drive(file_path)

    await query.edit_message_text(f"✅ فایل در دسته {category.upper()} ذخیره شد.")

# نمایش لیست فایل‌ها برای پولی و vip
async def show_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    files = os.listdir(os.path.join(BASE_DIR, category))
    if not files:
        await update.callback_query.message.reply_text("❌ هیچ فایلی در این دسته نیست.")
        return

    buttons = [
        [InlineKeyboardButton(f, callback_data=f"buy_{category}_{f}")]
        for f in files
    ]
    await update.callback_query.message.reply_text(f"📂 فایل‌های دسته {category.upper()}:", reply_markup=InlineKeyboardMarkup(buttons))

# نمایش اطلاعات پرداخت و درخواست رسید
async def show_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, filename: str):
    price = prices.get(category, 0)
    message = f"""💳 برای دریافت فایل `{filename}` از دسته {category.upper()}:
🏷 قیمت: {price:,} تومان
💳 شماره کارت: 6037-9918-1234-5678
👤 به نام: علی رضایی

📩 لطفاً رسید پرداخت رو همینجا بفرست."""
    user_id = update.callback_query.from_user.id
    pending_payments[user_id] = {"category": category, "filename": filename}
    await update.callback_query.message.reply_text(message, parse_mode="Markdown")

# دریافت عکس رسید پرداخت و ارسال به ادمین
async def handle_payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_payments:
        await update.message.reply_text("❌ عکسی ارسال شد اما در انتظار پرداختی نبودید.")
        return

    photo = update.message.photo[-1]
    data = pending_payments[user_id]
    caption = f"📥 درخواست پرداخت:\n👤 کاربر: {user_id}\n📁 فایل: {data['filename']} ({data['category']})"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و ارسال فایل", callback_data=f"approve_{user_id}")]
    ])
    await context.bot.send_photo(ADMIN_ID, photo.file_id, caption=caption, reply_markup=keyboard)
    await update.message.reply_text("✅ رسید ارسال شد. منتظر تایید ادمین باش.")

# تایید پرداخت توسط ادمین و ارسال فایل به کاربر
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) != 2:
        return

    user_id = int(parts[1])
    data = pending_payments.pop(user_id, None)
    if not data:
        await query.edit_message_text("❌ اطلاعاتی برای این کاربر یافت نشد.")
        return

    file_path = os.path.join(BASE_DIR, data['category'], data['filename'])
    await context.bot.send_document(user_id, InputFile(file_path))
    await query.edit_message_text("✅ فایل ارسال شد.")

# ارسال فایل رایگان با چک عضویت در کانال
async def send_random_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['left', 'kicked']:
            raise Exception()
    except:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
        ])
        await update.callback_query.message.reply_text("🔐 اول باید عضو کانال بشی:", reply_markup=keyboard)
        return

    files = os.listdir(os.path.join(BASE_DIR, "free"))
    if not files:
        await update.callback_query.message.reply_text("❌ فایل رایگان موجود نیست.")
        return

    selected = random.choice(files)
    file_path = os.path.join(BASE_DIR, "free", selected)
    await update.callback_query.message.reply_document(InputFile(file_path))

# هندلر دکمه‌ها
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global admin_waiting_for_price
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith("save_"):
        await save_file_category(update, context)
    elif data == "get_free":
        await send_random_free(update, context)
    elif data.startswith("list_"):
        category = data.replace("list_", "")
        await show_file_list(update, context, category)
    elif data.startswith("buy_"):
        _, category, filename = data.split("_", 2)
        await show_payment_info(update, context, category, filename)
    elif data.startswith("approve_"):
        await approve_payment(update, context)
    elif data == "check_join":
        await send_random_free(update, context)
    elif data == "about":
        await query.answer()
        await query.message.reply_text("🤖 ربات فروش کانفیگ ساخته شده توسط ممد\n📢 کانال: https://t.me/V2File_Mamad")
    elif data == "set_price" and user_id == ADMIN_ID:
        admin_waiting_for_price = True
        await query.message.reply_text("💬 قیمت رو وارد کن:\nمثال:\n`paid:45000`\nیا\n`vip:90000`", parse_mode='Markdown')

# هندلر متن (تنظیم قیمت)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global admin_waiting_for_price
    user_id = update.message.from_user.id
    if admin_waiting_for_price and user_id == ADMIN_ID:
        try:
            key, val = update.message.text.strip().split(":")
            key = key.strip()
            val = int(val.strip())
            if key in ["paid", "vip"]:
                prices[key] = val
                with open(PRICE_FILE, "w") as f:
                    json.dump(prices, f)
                await update.message.reply_text(f"✅ قیمت جدید برای {key.upper()} ثبت شد: {val:,} تومان")
            else:
                await update.message.reply_text("⛔️ دسته نامعتبره.")
        except:
            await update.message.reply_text("❌ فرمت اشتباهه. مثل این بنویس:\n`vip:75000`", parse_mode='Markdown')
        admin_waiting_for_price = False

# دستور ناشناخته
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⛔️ دستور ناشناخته!")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.PHOTO, handle_payment_photo))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    print("🤖 ربات آماده اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
