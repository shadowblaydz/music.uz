# 24/7 va bepul ishga tushirish

Eng real bepul variant: Oracle Cloud Always Free VM. Telegram bot long polling rejimida ishlaydi, shuning uchun unga doimiy ishlaydigan kichik server kerak bo'ladi.

Oracle hujjatlariga ko'ra Always Free resurslar muddatsiz beriladi, lekin hisob yaratishda telefon raqami va karta kerak bo'lishi mumkin. Ba'zi regionlarda bepul VM uchun "out of host capacity" xatosi chiqishi mumkin.

Rasmiy havolalar:

- Oracle Always Free: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Oracle Free Tier FAQ: https://www.oracle.com/cloud/free/faq/
- Telegram Bot API updates: https://core.telegram.org/bots/api#getting-updates

## Oracle Cloud VM ustida deploy

1. Oracle Cloud Free Tier hisob oching.
2. Always Free Ubuntu VM yarating.
3. SSH orqali serverga kiring.
4. Paketlarni o'rnating:

```bash
sudo apt update
sudo apt install -y python3 git
```

5. Loyihani serverga yuklang yoki `git clone` qiling.
6. Loyiha papkasida tekshirib ko'ring:

```bash
python3 main.py
```

Bot birinchi ishga tushganda token so'raydi va `.env` faylga saqlaydi.

7. Systemd service yarating:

```bash
sudo nano /etc/systemd/system/musiqa-bot.service
```

Ichiga quyidagini moslab yozing:

```ini
[Unit]
Description=Musiqa Topuvchi Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/Musiqa-topuvchi-telegram-bot
ExecStart=/usr/bin/python3 /home/ubuntu/Musiqa-topuvchi-telegram-bot/main.py
Restart=always
RestartSec=5
User=ubuntu
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

8. Service ni yoqing:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now musiqa-bot
sudo systemctl status musiqa-bot
```

Log ko'rish:

```bash
journalctl -u musiqa-bot -f
```

## Cloud Run varianti

Google Cloud Run free tier bor, lekin webhook arxitekturasi va tashqi SQL kerak bo'ladi. Bu loyiha hozir long polling + SQLite uchun tayyorlangan. Kichik bot uchun Oracle Always Free VM sodda va mosroq.
