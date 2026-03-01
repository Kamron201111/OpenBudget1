# 🤖 OpenBudget Vote Bot — Python/aiogram 3

OpenBudget.uz sayti uchun Telegram ovoz yig'uvchi bot.

---

## 📋 Tarkib

```
openbudget_bot/
├── bot.py              ← Asosiy bot fayli
├── requirements.txt    ← Kutubxonalar
├── data/               ← Sozlamalar (avtomatik yaratiladi)
│   ├── owners.dat      ← Admin ID lar
│   ├── porjectid.dat   ← Loyiha ID
│   ├── description.dat ← Bot tavsifi
│   ├── vote_payment.dat← Ovoz uchun to'lov
│   ├── ref_payment.dat ← Referal uchun to'lov
│   └── status.dat      ← Bildirishnoma holati
├── users/              ← Foydalanuvchi ma'lumotlari
├── votes/              ← Ovozlar
├── requests/           ← Pul yechish so'rovlari
├── notifications/      ← Yuborilishi kerak xabarlar
├── referals/           ← Referal tarixi
└── tmp/                ← Vaqtinchalik fayllar (Excel)
```

---

## ⚙️ O'rnatish

### 1. Python o'rnatish
Python 3.10 yoki undan yuqori bo'lishi kerak.

### 2. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 3. Bot tokenini kiritish
`bot.py` faylini oching va 17-qatordagi:
```python
BOT_TOKEN = ""
```
ni o'zgartirib tokeningizni kiriting:
```python
BOT_TOKEN = "1234567890:AABBccDDeeFFggHHiiJJkkLLmmNNoo"
```

### 4. Birinchi adminni qo'shish
`data/owners.dat` faylini yarating va o'z Telegram ID ingizni kiriting:
```
123456789
```
Bir nechta admin bo'lsa `|` bilan ajrating:
```
123456789|987654321
```

### 5. Loyiha IDni sozlash
`data/porjectid.dat` faylini yarating va OpenBudget loyiha IDini kiriting.

### 6. Botni ishga tushirish
```bash
python bot.py
```

---

## 🚀 Server da ishga tushirish (systemd)

`/etc/systemd/system/openbudget_bot.service` fayl yarating:

```ini
[Unit]
Description=OpenBudget Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/openbudget_bot
ExecStart=/usr/bin/python3 /home/ubuntu/openbudget_bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Keyin:
```bash
sudo systemctl daemon-reload
sudo systemctl enable openbudget_bot
sudo systemctl start openbudget_bot
sudo systemctl status openbudget_bot
```

---

## ✅ PHP dan farqlari (yaxshilanishlar)

| PHP | Python |
|-----|--------|
| Webhook (cron kerak) | Polling (cron shart emas) |
| OTP vaqt tekshiruvi xato | Tuzatildi: `time() - token_time < 180` |
| `$http_status == 0` (= emas) | Tuzatildi |
| PHP crone.php alohida process | Async fon jarayoni (bitta process) |
| Race condition JSON yozishda | Yaxshilangan (lock yo'q lekin tez) |

---

## 📱 Buyruqlar

**Foydalanuvchi:**
- `/start` — Boshlash / Asosiy menyu
- Telefon yuborish → SMS → Tasdiqlash → Pul ishlash
- 💳 Hisobim — Balansni ko'rish
- 🔄 Pul yechib olish — So'rov yuborish
- 🔗 Referal — Referal havolasini olish

**Admin:**
- 🗣 Ovozlar — Barcha ovozlarni ko'rish
- 🏦 Murojaatlar — Pul yechish so'rovlari
- 📝 Matn — Bot tavsifini o'zgartirish
- 🗄 Loyiha — Loyiha IDni o'zgartirish
- 💴 Ovoz berish — Ovoz uchun to'lovni belgilash
- 💶 Referal — Referal to'lovini belgilash
- ✍️ Bildirishnoma — Barcha userlarga xabar yuborish
- 🟢 Holat — Bildirishnoma holatini boshqarish
- 📁 Excel — CSV eksport qilish
- 🗑 Tozalash — Ovozlarni tozalash
- 👨‍👩‍👧 Foydalanuvchilar — Ro'yxat ko'rish
- 👨‍💻 Adminlar — Admin qo'shish/o'chirish
