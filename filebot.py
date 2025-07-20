import os
import json
from PIL import Image
from telegram import (
    Update, ReplyKeyboardMarkup, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
)
import time
from telegram.ext import ApplicationBuilder

TOKEN = '7769304731:AAG3cvrr15zsRmrggsbhMTlYTV9-08QSs_M'
MAIN_ADMIN_ID = 6810448582
ADMINS_FILE = 'admins.txt'
FILES_DB = 'files_db.json'
SETTINGS_FILE = 'settings.json'

if not os.path.exists("downloads"):
    os.makedirs("downloads")

def load_admins():
    if not os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'w') as f:
            f.write(str(MAIN_ADMIN_ID) + '\n')
    with open(ADMINS_FILE, 'r') as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())

def save_admins(admins):
    with open(ADMINS_FILE, 'w') as f:
        for admin_id in admins:
            f.write(str(admin_id) + '\n')

def load_files_db():
    if not os.path.exists(FILES_DB):
        with open(FILES_DB, 'w', encoding='utf-8') as f:
            json.dump([], f)
    with open(FILES_DB, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_files_db(files):
    with open(FILES_DB, 'w', encoding='utf-8') as f:
        json.dump(files, f, ensure_ascii=False)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"accept_files": True, "welcome_message": "به ربات فایل‌یاب خوش آمدید!", "force_channels": []}
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False)

def load_users_db():
    try:
        with open("users_db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users_db(users):
    with open("users_db.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def can_user_download(user_id):
    """بررسی اینکه آیا کاربر می‌تواند لینک دریافت کند"""
    users = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return True
    
    last_download = users[user_id_str].get("last_download", 0)
    current_time = time.time()
    
    # 12 ساعت = 43200 ثانیه
    if current_time - last_download >= 43200:
        return True
    
    return False

def update_user_download(user_id):
    """به‌روزرسانی زمان آخرین دانلود کاربر"""
    users = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = {}
    
    users[user_id_str]["last_download"] = time.time()
    users[user_id_str]["download_count"] = users[user_id_str].get("download_count", 0) + 1
    save_users_db(users)

def get_remaining_time(user_id):
    """محاسبه زمان باقی‌مانده تا دانلود بعدی"""
    users = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return 0
    
    last_download = users[user_id_str].get("last_download", 0)
    current_time = time.time()
    remaining = 43200 - (current_time - last_download)
    
    return max(0, remaining)

def main_keyboard(user_id=None, admins=None):
    # اگر ادمین است دکمه پنل مدیریت را نمایش بده، اگر نه فقط دکمه‌های دریافت فایل
    if user_id is not None and admins is not None and (user_id == MAIN_ADMIN_ID or user_id in admins):
        keyboard = [
            ["📤 ارسال فایل (فقط ادمین)", "📁 لیست فایل‌ها"],
            ["📥 دریافت آخرین فایل", "پنل مدیریت ⚙️"]
        ]
    else:
        keyboard = [
            ["📁 لیست فایل‌ها"],
            ["📥 دریافت آخرین فایل", "📊 وضعیت دانلود"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

MANAGE_PANEL = [
    ["🔄 فعال/غیرفعال کردن دریافت فایل", "✏️ تغییر پیام خوش‌آمد"],
    ["🗑 حذف فایل", "🔢 حذف فایل با شماره"],
    ["📝 تغییر نام فایل‌ها", "🔘 تغییر نام دکمه‌ها"],
    ["➕ افزودن ادمین", "➖ حذف ادمین"],
    ["👥 مدیریت عضویت اجباری کانال"],
    ["⬅️ بازگشت"]
]

def admin_panel_keyboard():
    return ReplyKeyboardMarkup([
        ["🔄 فعال/غیرفعال کردن دریافت فایل"],
        ["✏️ تغییر پیام خوش‌آمد"],
        ["🗑 حذف فایل", "🔢 حذف فایل با شماره"],
        ["🗑🗑 حذف دسته‌جمعی فایل‌ها"],
        ["🔘 تغییر نام دکمه‌ها", "📝 تغییر نام فایل‌ها"],
        ["➕ افزودن ادمین", "➖ حذف ادمین"],
        ["👥 مدیریت عضویت اجباری کانال"],
        ["⬅️ بازگشت"]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    force_channels = settings.get("force_channels", [])
    admins = load_admins()
    
    # بررسی عضویت در کانال‌های اجباری
    if force_channels and update.effective_user:
        is_member = await is_user_member_all(context.bot, update.effective_user.id, force_channels)
        if not is_member:
            join_buttons = []
            for ch in force_channels:
                # حذف @ از ابتدای نام کانال برای لینک
                channel_name = ch.lstrip('@')
                join_buttons.append([InlineKeyboardButton(f"عضویت در @{channel_name}", url=f"https://t.me/{channel_name}")])
            
            # اضافه کردن دکمه بررسی مجدد عضویت
            join_buttons.append([InlineKeyboardButton("✅ بررسی مجدد عضویت", callback_data="check_membership")])
            
            if update.message:
                await update.message.reply_text(
                    "🔒 برای استفاده از ربات ابتدا باید در کانال(های) زیر عضو شوید:\n\n" +
                    "\n".join([f"• @{ch.lstrip('@')}" for ch in force_channels]),
                    reply_markup=InlineKeyboardMarkup(join_buttons)
                )
            return
    
    if update.message and update.effective_user:
        await update.message.reply_text(
            settings.get("welcome_message", "به ربات فایل‌یاب خوش آمدید!"),
            reply_markup=main_keyboard(update.effective_user.id, admins)
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user or not update.message.document:
        return
    user_id = update.effective_user.id
    settings = load_settings()
    if user_id == MAIN_ADMIN_ID or user_id in load_admins():
        if not settings.get("accept_files", True):
            await update.message.reply_text("دریافت فایل غیرفعال است.")
            return
        file = update.message.document
        try:
            new_file = await context.bot.get_file(file.file_id)
            file_path = f"./downloads/{file.file_name}"
            await new_file.download_to_drive(file_path)
            files = load_files_db()
            file_id = f"doc_{file.file_id}"
            files.append({
                "id": file_id,
                "type": "document",
                "name": file.file_name,
                "path": file_path,
                "caption": update.message.caption or ""
            })
            save_files_db(files)
            await update.message.reply_text("✅ فایل با موفقیت آپلود و ذخیره شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ذخیره فایل: {e}")
    else:
        await update.message.reply_text("فقط ادمین می‌تواند فایل ارسال کند.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user or not update.message.photo:
        return
    user_id = update.effective_user.id
    settings = load_settings()
    if user_id == MAIN_ADMIN_ID or user_id in load_admins():
        if not settings.get("accept_files", True):
            await update.message.reply_text("دریافت فایل غیرفعال است.")
            return
        # بررسی اینکه آیا photo خالی نیست
        if not update.message.photo:
            await update.message.reply_text("❌ عکس دریافت نشد.")
            return
        photo = update.message.photo[-1]
        try:
            file = await context.bot.get_file(photo.file_id)
            # استفاده از نام کوتاه‌تر برای فایل
            import time
            timestamp = int(time.time())
            file_path = f"./downloads/photo_{timestamp}.jpg"
            
            # دانلود فایل
            await file.download_to_drive(file_path)
            
            # اطمینان از فرمت JPEG صحیح با استفاده از PIL
            try:
                with Image.open(file_path) as img:
                    # تبدیل به RGB اگر نیاز باشد
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    # ذخیره با کیفیت بالا
                    img.save(file_path, 'JPEG', quality=95)
            except Exception as img_error:
                # اگر PIL خطا داد، فایل را حذف کن
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise img_error
            
            files = load_files_db()
            file_id = f"photo_{timestamp}"
            files.append({
                "id": file_id,
                "type": "photo",
                "name": f"photo_{timestamp}.jpg",
                "path": file_path,
                "caption": update.message.caption or ""
            })
            save_files_db(files)
            await update.message.reply_text("✅ عکس با موفقیت آپلود و ذخیره شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ذخیره عکس: {e}")
    else:
        await update.message.reply_text("فقط ادمین می‌تواند عکس ارسال کند.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user_id = update.effective_user.id
    text = update.message.text
    user_state = context.user_data
    settings = load_settings()
    admins = load_admins()

    # اگر یکی از دکمه‌های اصلی زده شد، state را ریست کن
    main_menu_texts = [
        "📤 ارسال فایل (فقط ادمین)",
        "📁 لیست فایل‌ها",
        "پنل مدیریت ⚙️",
        "📥 دریافت آخرین فایل",
        "📊 وضعیت دانلود",
        "⬅️ بازگشت"
    ]
    if text in main_menu_texts and user_state.get("state"):
        user_state["state"] = None

    # مدیریت پنل
    if text == "پنل مدیریت ⚙️" and (user_id == MAIN_ADMIN_ID or user_id in admins):
        if update.message:
            await update.message.reply_text("پنل مدیریت فعال شد!", reply_markup=admin_panel_keyboard())
        user_state ["state"] = "admin_panel"
        return

    # منطق پنل مدیریت
    if user_state and user_state.get("state") == "admin_panel":
        if text == "🔄 فعال/غیرفعال کردن دریافت فایل":
            settings["accept_files"] = not settings.get("accept_files", True)
            save_settings(settings)
            status = "فعال" if settings["accept_files"] else "غیرفعال"
            await update.message.reply_text(f"دریافت فایل اکنون: {status}")
        elif text == "✏️ تغییر پیام خوش‌آمد":
            await update.message.reply_text("پیام خوش‌آمد جدید را ارسال کنید:")
            if user_state:
                user_state["state"] = "change_welcome"
            return
        elif text == "🗑 حذف فایل":
            files = load_files_db()
            if not files:
                await update.message.reply_text("هیچ فایلی برای حذف وجود ندارد.")
                return
            msg = "شماره فایلی که می‌خواهید حذف کنید را ارسال کنید:\n"
            for i, f in enumerate(files, 1):
                if f:
                    msg += f"{i}. {f.get('name', f.get('id'))}\n"
            await update.message.reply_text(msg)
            if user_state:
                user_state["state"] = "delete_file"
            return
        elif text == "🔢 حذف فایل با شماره":
            files = load_files_db()
            if not files:
                await update.message.reply_text("هیچ فایلی برای حذف وجود ندارد.")
                return
            msg = "شماره فایلی که می‌خواهید حذف کنید را ارسال کنید:\n"
            for i, f in enumerate(files, 1):
                if f:
                    msg += f"{i}. {f.get('name', f.get('id'))}\n"
            await update.message.reply_text(msg)
            if user_state:
                user_state["state"] = "delete_file_by_number"
            return
        elif text == "🗑🗑 حذف دسته‌جمعی فایل‌ها":
            files = load_files_db()
            if not files:
                await update.message.reply_text("هیچ فایلی برای حذف وجود ندارد.")
                return
            msg = "🔴 حذف دسته‌جمعی فایل‌ها\n\n"
            msg += "فایل‌های موجود:\n"
            for i, f in enumerate(files, 1):
                if f:
                    msg += f"{i}. {f.get('name', f.get('id'))}\n"
            msg += "\n📝 برای حذف دسته‌جمعی، شماره‌ها را با کاما جدا کنید.\n"
            msg += "مثال: 1,3,5 یا 1-5 برای حذف فایل‌های 1 تا 5\n"
            msg += "یا 'همه' برای حذف تمام فایل‌ها"
            await update.message.reply_text(msg)
            if user_state:
                user_state["state"] = "bulk_delete_files"
            return
        elif text == "🔘 تغییر نام دکمه‌ها":
            await update.message.reply_text("کدام دکمه را می‌خواهید تغییر دهید؟\n1. ارسال فایل\n2. لیست فایل‌ها\n3. دریافت آخرین فایل\nعدد گزینه را ارسال کنید.")
            if user_state:
                user_state["state"] = "choose_button_to_rename"
            return
        elif text == "📝 تغییر نام فایل‌ها":
            files = load_files_db()
            if not files:
                await update.message.reply_text("هیچ فایلی برای تغییر نام وجود ندارد.")
                return
            msg = "فایل‌های موجود:\n"
            for i, f in enumerate(files, 1):
                if f:
                    msg += f"{i}. {f.get('name', f.get('id'))}\n"
            msg += "\nشماره فایلی که می‌خواهید نام آن را تغییر دهید را ارسال کنید:"
            await update.message.reply_text(msg)
            if user_state:
                user_state["state"] = "choose_file_to_rename"
            return
        elif text == "➕ افزودن ادمین":
            await update.message.reply_text("آی‌دی ادمین جدید را ارسال کنید:")
            if user_state:
                user_state["state"] = "add_admin"
            return
        elif text == "➖ حذف ادمین":
            msg = "آی‌دی ادمینی که می‌خواهید حذف کنید را ارسال کنید:\n"
            for aid in admins:
                if aid != MAIN_ADMIN_ID:
                    msg += f"- {aid}\n"
            await update.message.reply_text(msg)
            if user_state:
                user_state["state"] = "remove_admin"
            return
        elif text == "👥 مدیریت عضویت اجباری کانال":
            force_channels = settings.get("force_channels", [])
            msg = "لیست کانال‌های فعلی:\n" + ("\n".join([f"@{ch}" for ch in force_channels]) if force_channels else "(هیچ کانالی ثبت نشده)")
            msg += "\n\nیوزرنیم کانال‌های جدید را با @ یا بدون @ و با کاما یا اینتر جداگانه وارد کنید:"
            await update.message.reply_text(msg)
            if user_state:
                user_state["state"] = "manage_force_channels"
            return
        elif text == "⬅️ بازگشت":
            await update.message.reply_text("بازگشت به منوی اصلی", reply_markup=admin_panel_keyboard())
            if user_state:
                user_state["state"] = None
            return
        else:
            await update.message.reply_text("از دکمه‌های پنل مدیریت استفاده کنید.")
        return

    # تغییر پیام خوش‌آمد
    if user_state and user_state.get("state") == "change_welcome":
        settings["welcome_message"] = text
        save_settings(settings)
        await update.message.reply_text("پیام خوش‌آمد جدید ذخیره شد.", reply_markup=admin_panel_keyboard())
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # حذف فایل
    if user_state and user_state.get("state") == "delete_file":
        try:
            file_index = int(text) - 1
            files = load_files_db()
            if 0 <= file_index < len(files) and files[file_index]:
                file_to_delete = files[file_index]
                file_name = file_to_delete.get('name', file_to_delete.get('id', f'فایل {file_index + 1}'))
                
                # حذف فایل از سیستم
                try:
                    if file_to_delete.get("path") and os.path.exists(file_to_delete["path"]):
                        os.remove(file_to_delete["path"])
                except Exception:
                    pass
                
                # حذف از دیتابیس
                files.pop(file_index)
                save_files_db(files)
                
                await update.message.reply_text(
                    f"✅ فایل '{file_name}' با شماره {file_index + 1} حذف شد.",
                    reply_markup=admin_panel_keyboard()
                )
            else:
                await update.message.reply_text("❌ شماره معتبر وارد کنید.", reply_markup=admin_panel_keyboard())
        except ValueError:
            await update.message.reply_text("❌ شماره معتبر وارد کنید.", reply_markup=admin_panel_keyboard())
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # حذف فایل با شماره
    if user_state and user_state.get("state") == "delete_file_by_number":
        try:
            file_index = int(text) - 1
            files = load_files_db()
            if 0 <= file_index < len(files) and files[file_index]:
                file_to_delete = files[file_index]
                if file_to_delete.get("path") and os.path.exists(file_to_delete["path"]):
                    os.remove(file_to_delete["path"])
                files.pop(file_index)
                save_files_db(files)
                await update.message.reply_text(f"فایل با شماره {file_index + 1} حذف شد.", reply_markup=admin_panel_keyboard())
            else:
                await update.message.reply_text("شماره معتبر وارد کنید.")
        except ValueError:
            await update.message.reply_text("شماره معتبر وارد کنید.")
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # حذف دسته‌جمعی فایل‌ها
    if user_state and user_state.get("state") == "bulk_delete_files":
        try:
            if text and text.lower() == "همه":
                files = load_files_db()
                for f in files:
                    if f and f.get("path") and os.path.exists(f["path"]):
                        os.remove(f["path"])
                files.clear()
                save_files_db(files)
                await update.message.reply_text("تمام فایل‌ها با موفقیت حذف شدند.", reply_markup=admin_panel_keyboard())
                if user_state:
                    user_state["state"] = "admin_panel"
                return
            
            # تقسیم شماره‌ها با کاما یا اینتر
            indices_to_delete = []
            if text:
                for item in text.split(','):
                    if '-' in item:
                        start, end = map(int, item.split('-'))
                        indices_to_delete.extend(range(start - 1, end))
                    else:
                        try:
                            indices_to_delete.append(int(item) - 1)
                        except ValueError:
                            await update.message.reply_text(f"شماره '{item}' معتبر نیست.")
                            return
            
            # حذف فایل‌های موجود با شماره‌های انتخاب شده
            files = load_files_db()
            deleted_count = 0
            for i in sorted(indices_to_delete, reverse=True): # از آخر به اول حذف کنیم
                if 0 <= i < len(files) and files[i]:
                    file_to_delete = files[i]
                    file_name = file_to_delete.get('name', file_to_delete.get('id', f'فایل {i + 1}'))
                    
                    # حذف فایل از سیستم
                    try:
                        if file_to_delete.get("path") and os.path.exists(file_to_delete["path"]):
                            os.remove(file_to_delete["path"])
                    except Exception:
                        pass
                    
                    # حذف از دیتابیس
                    files.pop(i)
                    deleted_count += 1
            
            save_files_db(files)
            await update.message.reply_text(f"✅ {deleted_count} فایل با موفقیت حذف شدند.", reply_markup=admin_panel_keyboard())
            if user_state:
                user_state["state"] = "admin_panel"
            return
        except Exception as e:
            await update.message.reply_text(f"خطا در حذف دسته‌جمعی فایل‌ها: {str(e)}", reply_markup=admin_panel_keyboard())
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # تغییر نام دکمه‌ها
    if user_state and user_state.get("state") == "choose_button_to_rename":
        if text and text in ["1", "2", "3"]:
            user_state["rename_button_index"] = int(text)
            await update.message.reply_text("نام جدید دکمه را ارسال کنید:")
            user_state["state"] = "rename_button"
        else:
            await update.message.reply_text("عدد معتبر وارد کنید (1 تا 3).")
        return
    if user_state and user_state.get("state") == "rename_button":
        idx = user_state.get("rename_button_index")
        await update.message.reply_text("نام دکمه تغییر کرد.", reply_markup=admin_panel_keyboard())
        user_state["state"] = "admin_panel"
        return

    # تغییر نام فایل‌ها
    if user_state and user_state.get("state") == "choose_file_to_rename":
        try:
            if text is not None:
                file_index = int(text) - 1
                files = load_files_db()
                if 0 <= file_index < len(files) and files[file_index]:
                    user_state["file_to_rename_index"] = file_index
                    await update.message.reply_text("نام جدید فایل را ارسال کنید:")
                    user_state["state"] = "rename_file"
                else:
                    await update.message.reply_text("شماره معتبر وارد کنید.")
            else:
                await update.message.reply_text("شماره معتبر وارد کنید.")
        except ValueError:
            await update.message.reply_text("شماره معتبر وارد کنید.")
        return
    
    if user_state and user_state.get("state") == "rename_file":
        file_index = user_state.get("file_to_rename_index")
        files = load_files_db()
        if file_index is not None and 0 <= file_index < len(files) and files[file_index]:
            old_file = files[file_index]
            old_name = old_file.get("name", old_file.get("id"))
            
            # تغییر نام فایل در دیتابیس
            files[file_index]["name"] = text
            save_files_db(files)
            
            await update.message.reply_text(f"✅ نام فایل از '{old_name}' به '{text}' تغییر کرد.", reply_markup=admin_panel_keyboard())
        else:
            await update.message.reply_text("خطا در تغییر نام فایل.", reply_markup=admin_panel_keyboard())
        user_state["state"] = "admin_panel"
        return

    # افزودن ادمین
    if user_state and user_state.get("state") == "add_admin":
        try:
            if text is not None:
                new_admin = int(text)
                admins.add(new_admin)
                save_admins(admins)
                await update.message.reply_text("ادمین جدید اضافه شد.", reply_markup=admin_panel_keyboard())
            else:
                await update.message.reply_text("آی‌دی معتبر وارد کنید.")
        except Exception:
            await update.message.reply_text("آی‌دی معتبر وارد کنید.")
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # حذف ادمین
    if user_state and user_state.get("state") == "remove_admin":
        try:
            if text is not None:
                rem_admin = int(text)
                if rem_admin != MAIN_ADMIN_ID and rem_admin in admins:
                    admins.remove(rem_admin)
                    save_admins(admins)
                    await update.message.reply_text("ادمین حذف شد.", reply_markup=admin_panel_keyboard())
                else:
                    await update.message.reply_text("آی‌دی معتبر وارد کنید.")
            else:
                await update.message.reply_text("آی‌دی معتبر وارد کنید.")
        except Exception:
            await update.message.reply_text("آی‌دی معتبر وارد کنید.")
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # مدیریت کانال‌های اجباری
    if user_state and user_state.get("state") == "manage_force_channels":
        try:
            if text is None:
                await update.message.reply_text("لطفاً کانال‌ها را وارد کنید.", reply_markup=admin_panel_keyboard())
                if user_state:
                    user_state["state"] = "admin_panel"
                return
            
            # تقسیم کانال‌ها با کاما یا اینتر
            channels = [ch.strip().lstrip('@') for ch in text.split(',') if ch.strip()]
            if not channels:
                await update.message.reply_text("لطفاً حداقل یک کانال وارد کنید.", reply_markup=admin_panel_keyboard())
                if user_state:
                    user_state["state"] = "admin_panel"
                return
            
            # بررسی معتبر بودن کانال‌ها
            valid_channels = []
            for channel in channels:
                try:
                    # بررسی وجود کانال
                    chat = await context.bot.get_chat(f"@{channel}")
                    if chat.type in ["channel", "supergroup"]:
                        valid_channels.append(channel)
                    else:
                        await update.message.reply_text(f"کانال @{channel} معتبر نیست.")
                except Exception:
                    await update.message.reply_text(f"کانال @{channel} پیدا نشد.")
            
            if valid_channels:
                settings["force_channels"] = valid_channels
                save_settings(settings)
                await update.message.reply_text(
                    f"✅ کانال‌های اجباری به‌روزرسانی شد:\n" + 
                    "\n".join([f"• @{ch}" for ch in valid_channels]),
                    reply_markup=admin_panel_keyboard()
                )
            else:
                await update.message.reply_text("هیچ کانال معتبری پیدا نشد.", reply_markup=admin_panel_keyboard())
        except Exception as e:
            await update.message.reply_text(f"خطا در تنظیم کانال‌ها: {str(e)}", reply_markup=admin_panel_keyboard())
        if user_state:
            user_state["state"] = "admin_panel"
        return

    # منوی اصلی
    if text == "📤 ارسال فایل (فقط ادمین)":
        if user_id == MAIN_ADMIN_ID or user_id in admins:
            await update.message.reply_text("لطفاً فایل یا عکس خود را ارسال کنید.")
        else:
            await update.message.reply_text("فقط ادمین می‌تواند فایل ارسال کند.")
        return
    if text == "📁 لیست فایل‌ها":
        files = load_files_db()
        if not files:
            await update.message.reply_text("هیچ فایلی وجود ندارد.")
            return
        keyboard = []
        for i, f in enumerate(files, 1):
            if f:
                # نمایش نام فایل از فیلد name
                file_name = f.get('name', f.get('id', f'فایل {i}'))
                
                # اضافه کردن نوع فایل به ابتدای نام
                file_type = f.get('type', '')
                if file_type == 'photo':
                    show_name = f"📷 {i}. {file_name}"
                elif file_type == 'document':
                    show_name = f"📄 {i}. {file_name}"
                elif file_type == 'text':
                    show_name = f"📝 {i}. {file_name}"
                else:
                    show_name = f"📁 {i}. {file_name}"
                
                # اضافه کردن caption اگر وجود داشته باشد
                caption = f.get('caption', '')
                if caption:
                    show_name += f" - {caption[:20]}"  # حداکثر 20 کاراکتر
                
                callback_id = f.get('id', '')[:30]  # حداکثر ۳۰ کاراکتر
                keyboard.append([InlineKeyboardButton(show_name, callback_data=f"download_{callback_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_main")])
        await update.message.reply_text(
            "برای دریافت هر فایل روی دکمه آن کلیک کنید:\n\n💡 برای حذف فایل، شماره آن را ارسال کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    # اگر دکمه «📥 دریافت آخرین فایل» زده شد، state را ریست کن و فقط منطق همین دکمه را اجرا کن
    if text == "📥 دریافت آخرین فایل":
        user_state["state"] = None
        files = load_files_db()
        if files:
            # بررسی محدودیت دانلود برای کاربران غیر ادمین
            if user_id != MAIN_ADMIN_ID and user_id not in admins:
                if not can_user_download(user_id):
                    remaining_time = get_remaining_time(user_id)
                    hours = int(remaining_time // 3600)
                    minutes = int((remaining_time % 3600) // 60)
                    await update.message.reply_text(
                        f"⏰ شما در 12 ساعت گذشته فایل دانلود کرده‌اید!\n"
                        f"⏳ زمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه"
                    )
                    return
            last_file = files[-1]
            try:
                if last_file and last_file.get("type") == "document":
                    await context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(last_file["path"]), caption=last_file.get("caption", ""))
                    if user_id != MAIN_ADMIN_ID and user_id not in admins:
                        update_user_download(user_id)
                elif last_file and last_file.get("type") == "photo":
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(last_file["path"]), caption=last_file.get("caption", ""))
                    if user_id != MAIN_ADMIN_ID and user_id not in admins:
                        update_user_download(user_id)
                elif last_file and last_file.get("type") == "text":
                    await update.message.reply_text(last_file["content"])
                    if user_id != MAIN_ADMIN_ID and user_id not in admins:
                        update_user_download(user_id)
                else:
                    await update.message.reply_text("نوع فایل پشتیبانی نمی‌شود.")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا در ارسال فایل: {str(e)}")
        else:
            await update.message.reply_text("هیچ فایلی وجود ندارد.")
        return
    elif text == "📊 وضعیت دانلود":
        users_db = load_users_db()
        user_id_str = str(user_id)
        user_data = users_db.get(user_id_str, {})
        
        if user_id_str not in users_db:
            message = "✅ شما هنوز هیچ فایلی دانلود نکرده‌اید.\n🆓 می‌توانید یک فایل دانلود کنید."
        else:
            last_download_time = user_data.get("last_download", 0)
            download_count = user_data.get("download_count", 0)
            remaining_time = get_remaining_time(user_id)
            
            if remaining_time > 0:
                hours = int(remaining_time // 3600)
                minutes = int((remaining_time % 3600) // 60)
                message = f"⏰ شما در 12 ساعت گذشته فایل دانلود کرده‌اید!\n"
                message += f"📊 تعداد دانلود: {download_count}\n"
                message += f"⏳ زمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه"
            else:
                message = f"✅ می‌توانید فایل دانلود کنید!\n"
                message += f"📊 تعداد دانلود: {download_count}"
        
        await update.message.reply_text(message)
    elif text == "⬅️ بازگشت":
        await update.message.reply_text("بازگشت به منوی اصلی", reply_markup=main_keyboard(user_id, admins))
    # حذف فایل با شماره (برای همه کاربران)
    elif text and text.isdigit():
        try:
            file_index = int(text) - 1
            files = load_files_db()
            if 0 <= file_index < len(files) and files[file_index]:
                file_to_delete = files[file_index]
                file_name = file_to_delete.get('name', file_to_delete.get('id', f'فایل {file_index + 1}'))
                
                # حذف فایل از سیستم
                try:
                    if file_to_delete.get("path") and os.path.exists(file_to_delete["path"]):
                        os.remove(file_to_delete["path"])
                except Exception:
                    pass
                
                # حذف از دیتابیس
                files.pop(file_index)
                save_files_db(files)
                
                await update.message.reply_text(
                    f"✅ فایل '{file_name}' با شماره {file_index + 1} حذف شد.",
                    reply_markup=main_keyboard(user_id, admins)
                )
            else:
                await update.message.reply_text("❌ شماره معتبر وارد کنید.")
        except ValueError:
            await update.message.reply_text("❌ شماره معتبر وارد کنید.")
    elif (user_id == MAIN_ADMIN_ID or user_id in admins) and text not in ["📤 ارسال فایل (فقط ادمین)", "📁 لیست فایل‌ها", "پنل مدیریت ⚙️", "📥 دریافت آخرین فایل", "📊 وضعیت دانلود"]:
        files = load_files_db()
        file_id = f"text_{len(files)+1}"
        files.append({
            "id": file_id,
            "type": "text",
            "name": f"متن {len(files)+1}",
            "content": text
        })
        save_files_db(files)
        await update.message.reply_text("✅ متن ذخیره شد.")

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id if query.from_user else None
    data = query.data if query.data else None
    admins = load_admins()
    
    # بررسی مجدد عضویت
    if data == "check_membership":
        settings = load_settings()
        force_channels = settings.get("force_channels", [])
        
        if force_channels:
            is_member = await is_user_member_all(context.bot, user_id, force_channels)
            if is_member:
                if query.message and query.message.chat:
                    await context.bot.send_message(
                        chat_id=query.message.chat.id,
                        text="✅ عضویت شما تأیید شد! به ربات خوش آمدید.",
                        reply_markup=main_keyboard(user_id, admins)
                    )
            else:
                await query.answer("❌ هنوز در کانال‌های اجباری عضو نیستید!", show_alert=True)
        else:
            if query.message and query.message.chat:
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text="✅ عضویت شما تأیید شد! به ربات خوش آمدید.",
                    reply_markup=main_keyboard(user_id, admins)
                )
        await query.answer()
        return
    
    if data == "back_to_main":
        reply_markup = main_keyboard(user_id, admins)
        if query.message and query.message.chat:
            await context.bot.send_message(chat_id=query.message.chat.id, text="بازگشت به منوی اصلی", reply_markup=reply_markup)
        await query.answer()
        return
    
    if data and data.startswith("download_"):
        file_id = data.replace("download_", "", 1)
        files = load_files_db()
        # جستجو در فایل‌ها با استفاده از 30 کاراکتر اول
        file_info = None
        for f in files:
            if f and f.get("id", "")[:30] == file_id:
                file_info = f
                break
        if not file_info:
            await query.answer("فایل پیدا نشد!", show_alert=True)
            return
        
        # بررسی محدودیت دانلود برای کاربران غیر ادمین
        if user_id != MAIN_ADMIN_ID and user_id not in admins:
            if not can_user_download(user_id):
                remaining_time = get_remaining_time(user_id)
                hours = int(remaining_time // 3600)
                minutes = int((remaining_time % 3600) // 60)
                
                await query.answer(
                    f"⏰ شما در 12 ساعت گذشته فایل دریافت کرده‌اید!\n"
                    f"⏳ زمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه",
                    show_alert=True
                )
                return
        
        chat_id = query.message.chat.id if query.message and query.message.chat else None
        # اگر نوع فایل عکس است، ابتدا preview با دکمه دانلود نمایش بده
        if file_info and file_info.get("type") == "photo" and chat_id:
            try:
                # اطمینان از وجود فایل
                if not os.path.exists(file_info["path"]):
                    await context.bot.send_message(chat_id=chat_id, text='❌ فایل پیدا نشد.')
                    return
                
                # تلاش برای ارسال به صورت عکس
                try:
                    await context.bot.send_photo(chat_id=chat_id, photo=InputFile(file_info["path"]), caption=file_info.get("caption", ""))
                    # به‌روزرسانی دانلود کاربر
                    if user_id != MAIN_ADMIN_ID and user_id not in admins:
                        update_user_download(user_id)
                    await context.bot.send_message(chat_id=chat_id, text="✅ عکس ارسال شد. از دکمه‌های زیر استفاده کنید:", reply_markup=main_keyboard(user_id, admins))
                except Exception as photo_error:
                    # اگر خطای Image_process_failed رخ داد، به صورت فایل ارسال کن
                    if "Image_process_failed" in str(photo_error):
                        try:
                            await context.bot.send_document(chat_id=chat_id, document=InputFile(file_info["path"]), caption=file_info.get("caption", ""))
                            # به‌روزرسانی دانلود کاربر
                            if user_id != MAIN_ADMIN_ID and user_id not in admins:
                                update_user_download(user_id)
                            await context.bot.send_message(chat_id=chat_id, text="✅ فایل ارسال شد (به صورت فایل). از دکمه‌های زیر استفاده کنید:", reply_markup=main_keyboard(user_id, admins))
                        except Exception as doc_error:
                            await context.bot.send_message(chat_id=chat_id, text=f'❌ خطا در ارسال فایل: {str(doc_error)}')
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=f'❌ خطا در ارسال عکس: {str(photo_error)}')
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=f'❌ خطا در ارسال عکس: {str(e)}')
            await query.answer()
            return
        # اگر نوع فایل داکیومنت است و پسوند jpg/png دارد، preview عکس بده
        elif file_info and file_info.get("type") == "document" and chat_id:
            file_path = file_info["path"]
            if file_path and file_path.lower().endswith((".jpg", ".jpeg", ".png")):
                try:
                    # اطمینان از وجود فایل
                    if not os.path.exists(file_path):
                        await context.bot.send_message(chat_id=chat_id, text='❌ فایل پیدا نشد.')
                        return
                    
                    # تلاش برای ارسال به صورت عکس
                    try:
                        await context.bot.send_photo(chat_id=chat_id, photo=InputFile(file_path), caption=file_info.get("caption", ""))
                        # به‌روزرسانی دانلود کاربر
                        if user_id != MAIN_ADMIN_ID and user_id not in admins:
                            update_user_download(user_id)
                        await context.bot.send_message(chat_id=chat_id, text="✅ عکس ارسال شد. از دکمه‌های زیر استفاده کنید:", reply_markup=main_keyboard(user_id, admins))
                    except Exception as photo_error:
                        # اگر خطای Image_process_failed رخ داد، به صورت فایل ارسال کن
                        if "Image_process_failed" in str(photo_error):
                            try:
                                await context.bot.send_document(chat_id=chat_id, document=InputFile(file_path), caption=file_info.get("caption", ""))
                                # به‌روزرسانی دانلود کاربر
                                if user_id != MAIN_ADMIN_ID and user_id not in admins:
                                    update_user_download(user_id)
                                await context.bot.send_message(chat_id=chat_id, text="✅ فایل ارسال شد (به صورت فایل). از دکمه‌های زیر استفاده کنید:", reply_markup=main_keyboard(user_id, admins))
                            except Exception as doc_error:
                                await context.bot.send_message(chat_id=chat_id, text=f'❌ خطا در ارسال فایل: {str(doc_error)}')
                        else:
                            await context.bot.send_message(chat_id=chat_id, text=f'❌ خطا در ارسال عکس: {str(photo_error)}')
                except Exception as e:
                    await context.bot.send_message(chat_id=chat_id, text=f'❌ خطا در ارسال عکس: {str(e)}')
                await query.answer()
                return
            # اگر فایل عکس نبود، همان رفتار قبلی
            try:
                # اطمینان از وجود فایل
                if not os.path.exists(file_path):
                    await context.bot.send_message(chat_id=chat_id, text='❌ فایل پیدا نشد.')
                    return
                await context.bot.send_document(chat_id=chat_id, document=InputFile(file_path), caption=file_info.get("caption", ""))
                # به‌روزرسانی دانلود کاربر
                if user_id != MAIN_ADMIN_ID and user_id not in admins:
                    update_user_download(user_id)
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text='❌ خطا در ارسال فایل.')
        elif file_info and file_info.get("type") == "text" and chat_id:
            await context.bot.send_message(chat_id=chat_id, text=file_info["content"])
            # به‌روزرسانی دانلود کاربر
            if user_id != MAIN_ADMIN_ID and user_id not in admins:
                update_user_download(user_id)
        reply_markup = main_keyboard(user_id, admins)
        if chat_id:
            await context.bot.send_message(chat_id=chat_id, text="✅ ارسال انجام شد. از دکمه‌های زیر استفاده کنید:", reply_markup=reply_markup)
        await query.answer()

async def is_user_member_all(bot, user_id, channels):
    for ch in channels:
        try:
            # اگر کانال با @ شروع نشده، اضافه کن
            if not ch.startswith('@'):
                ch = f"@{ch}"
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

if __name__ == '__main__':
    import asyncio
    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
    TOKEN = os.environ.get('BOT_TOKEN', TOKEN)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(CallbackQueryHandler(handle_download_callback))

    if WEBHOOK_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/webhook/{TOKEN}"
        )
    else:
        app.run_polling() 