# Railway deploy qilish

Bu bot Railway'da long polling worker sifatida ishlaydi. Web server kerak emas, shuning uchun `railway.json` ichida healthcheck o'chirilgan va bitta replica belgilangan.

## 1. GitHub'ga hamma fayllarni yuboring

Railway logida build faqat `README.md` faylini ko'rgan. Bu odatda kod fayllari GitHub'ga commit qilinmaganini bildiradi.

```bash
git add .
git commit -m "Prepare bot for Railway"
git push
```

`git status` ichida commit qilinmagan `main.py`, `app/`, `requirements.txt`, `railway.json` yoki `.python-version` qolmasin.

## 2. Railway Variables

Railway service ichida `Variables` bo'limiga quyidagilarni qo'shing:

```env
BOT_TOKEN=BotFather bergan token
ADMIN_IDS=Telegram ID raqamingiz
LOG_LEVEL=INFO
```

Majburiy qiymat faqat `BOT_TOKEN`. `ADMIN_IDS` bo'sh qolsa ham bot ishlaydi, lekin admin panel ochilmaydi.

Audio orqali qo'shiq tanish kerak bo'lsa, ixtiyoriy token:

```env
AUDD_API_TOKEN=AudD tokeningiz
```

## 3. Railway service sozlamalari

Repo root papkasi tanlangan bo'lishi kerak. Agar Railway root directory so'rasa, `/` qoldiring.

`railway.json` quyidagilarni avtomatik beradi:

```json
{
  "deploy": {
    "startCommand": "python main.py",
    "numReplicas": 1,
    "restartPolicyType": "ALWAYS",
    "healthcheckPath": null,
    "sleepApplication": false
  }
}
```

## 4. SQLite ma'lumotlarini saqlab qolish

Default holatda bot SQLite faylni `data/musiqa_bot.sqlite3` ichida yaratadi. Railway redeploy yoki container almashganda bu fayl yo'qolishi mumkin.

Tarix va favoritlar doimiy saqlansin desangiz:

1. Railway'da service uchun Volume qo'shing.
2. Mount path sifatida `/data` kiriting.
3. Variables ichiga qo'shing:

```env
DATABASE_PATH=/data/musiqa_bot.sqlite3
```

## 5. Tekshirish

Deploy tugagach logda shunga o'xshash yozuv chiqishi kerak:

```text
Bot ishga tushdi: @bot_username
```

Keyin Telegramda botga `/start` yuboring.
