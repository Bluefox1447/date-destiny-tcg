# Date Destiny TCG — เว็บเกมการ์ด

Flask + SQLite + Socket.IO (Python) / HTML + CSS + JavaScript (หน้าเว็บ)

## เริ่มใช้งาน
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # แล้วแก้ค่าในไฟล์
python app.py                                         # เปิด http://localhost:5000
flask --app app seed-demo                             # (ไม่บังคับ) เพิ่มการ์ดตัวอย่าง 12 ใบ
```
ฐานข้อมูล `instance/dds.db` ถูกสร้างอัตโนมัติ

## ตั้งค่าที่ต้องทำ
| เรื่อง | วิธี |
|---|---|
| Admin คนแรก | ใส่อีเมลใน `ADMIN_EMAILS` ใน .env แล้วสมัคร หรือสมัครก่อนแล้วรัน `flask --app app make-admin` |
| ส่งรหัสยืนยันอีเมล | ตั้ง `MAIL_*` (Gmail ใช้ App Password) ถ้าไม่ตั้ง รหัสจะพิมพ์ใน console เพื่อทดสอบ |
| Google login | สร้าง OAuth Client ที่ console.cloud.google.com ใส่ Redirect URI `http://localhost:5000/auth/google/callback` |
| Discord login | สร้างแอปที่ discord.com/developers ใส่ Redirect `http://localhost:5000/auth/discord/callback` |

ขึ้นเซิร์ฟเวอร์จริง: เปลี่ยน `SECRET_KEY`, ใช้ HTTPS, เปลี่ยน Redirect URI เป็นโดเมนจริง และรันด้วย
`gunicorn -k gthread --threads 100 -w 1 app:app` (ใช้ 1 worker เพราะสถานะห้องเก็บในหน่วยความจำ)

## โครงสร้าง
```
app.py        เส้นทางเว็บ, ล็อคอิน, Admin, เด็ค, ห้อง, Socket.IO
game.py       เอนจินห้องเล่น (setup, เฟส, ย้ายการ์ด, ซ่อนข้อมูลฝั่งตรงข้าม)
models.py     User / Card / Deck / News
templates/    หน้าเว็บ (admin/ = หน้าจัดการ)
static/js/    app.js (วาดการ์ด), deckbuilder.js, play.js (สนาม)
```

## ข้อสันนิษฐานที่ผมตั้งไว้ (ปรับได้)
- Firewall Zone = โซน HP (วางการ์ด 8 ใบคว่ำ), แถบเลข 1–10 = ตัวนับ Code ของแต่ละฝั่ง (Code สูงสุด 10)
- ไม่มี Operator แล้ว: Partners 4 ใบวางบน Partners Zone ตอน Setup
- เด็คหลัก 50 ใบ ซ้ำได้ 4 ใบ (นับรวม Partners) (`DECK_SIZE`, `MAX_COPIES` ใน .env)
- HP −1 ย้ายการ์ดบนสุดของ HP ไป Delect Zone และถ้า HP หมดแล้วโดนอีก = แพ้
- ไม่มีระบบ CSRF token และห้องเล่นหายเมื่อรีสตาร์ทเซิร์ฟเวอร์ (ควรเพิ่มก่อนเปิดใช้งานจริง)

---

# เปิดให้เพื่อนเล่นออนไลน์ผ่านลิงก์

ในห้องเล่นกดปุ่ม **คัดลอกลิงก์ห้อง** แล้วส่งให้เพื่อน เพื่อนเปิดลิงก์ → ล็อคอิน/สมัคร → เลือกเด็ค → เข้าห้องทันที
(ถ้าเพื่อนยังไม่ล็อคอิน ระบบจะพากลับมาที่ห้องเดิมให้หลังล็อคอินหรือสมัครเสร็จ)
เกมคุยกันผ่าน WebSocket จึงเห็นการเคลื่อนไหวของอีกฝ่ายแบบเรียลไทม์

## วิธีที่ 1: เพื่อนอยู่ Wi-Fi/วงแลนเดียวกัน (ง่ายสุด)
รัน `python app.py` แล้วส่งลิงก์แบบ `http://192.168.x.x:5000/rooms/ABCDE` ให้เพื่อน
(Windows จะถามให้อนุญาต Firewall ครั้งแรก ให้กดอนุญาต)

## วิธีที่ 2: เพื่อนอยู่คนละที่ โดยใช้เครื่องตัวเองเป็นเซิร์ฟเวอร์ (ฟรี ไม่ต้องเช่าเซิร์ฟเวอร์)
ใช้ Cloudflare Quick Tunnel ซึ่งรองรับ WebSocket
1. ติดตั้ง: `winget install Cloudflare.cloudflared` (Windows) หรือดูที่ developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads
2. แก้ `.env` ให้มีบรรทัดเหล่านี้
   ```
   BEHIND_PROXY=1
   COOKIE_SECURE=1
   FLASK_DEBUG=0
   SKIP_EMAIL_VERIFY=1     # ถ้าไม่ได้ตั้งค่าส่งอีเมล เพื่อนจะได้สมัครแล้วใช้ได้ทันที (เหมาะกับกลุ่มเพื่อนเท่านั้น)
   ```
3. เปิดเซิร์ฟเวอร์ `python app.py` แล้วเปิดอีกหน้าต่าง รัน
   `cloudflared tunnel --url http://localhost:5000`
4. จะได้ลิงก์ `https://xxxx.trycloudflare.com` ใช้ลิงก์นี้เข้าเว็บและสร้างห้อง แล้วคัดลอกลิงก์ห้องส่งให้เพื่อน

ข้อจำกัด: ลิงก์เปลี่ยนทุกครั้งที่เปิดใหม่, เครื่องคุณต้องเปิดและรันเซิร์ฟเวอร์ไว้ระหว่างเล่น,
และถ้าใช้ Google/Discord login ต้องเพิ่ม Redirect URI ของลิงก์ใหม่ทุกครั้ง (แนะนำให้ใช้สมัครด้วยอีเมลแทน)

## วิธีที่ 3: ขึ้นเว็บถาวร (Render / Railway / VPS)
1. อัปโหลดโปรเจกต์ขึ้น GitHub แล้วสร้าง Web Service (Python)
2. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn -k gthread --threads 100 -w 1 -b 0.0.0.0:$PORT app:app` (มีในไฟล์ `Procfile` แล้ว)
   **ต้องใช้ `-w 1` (worker เดียว)** เพราะสถานะห้องเล่นเก็บอยู่ในหน่วยความจำ
3. ตั้ง Environment Variables: `SECRET_KEY` (สุ่มยาว ๆ), `BEHIND_PROXY=1`, `COOKIE_SECURE=1`, `ADMIN_EMAILS`, `MAIL_*` (หรือ `SKIP_EMAIL_VERIFY=1`)
4. **ฐานข้อมูล:** เครื่องฟรีส่วนใหญ่ลบไฟล์ SQLite ทุกครั้งที่รีสตาร์ท ให้สร้าง PostgreSQL แล้วใส่ `DATABASE_URL`
5. **รูปการ์ด/Sleeve:** ถูกเก็บเป็นไฟล์ ต้องต่อดิสก์ถาวรแล้วตั้ง `UPLOAD_DIR=/path/ของดิสก์` (ถ้าไม่มี รูปจะหายตอนรีสตาร์ท)
6. ตรวจว่าเว็บทำงาน: เปิด `/healthz` ต้องขึ้น `ok`

## ก่อนเปิดให้คนอื่นเข้า
- ปิด debug (`FLASK_DEBUG=0` เป็นค่าเริ่มต้นแล้ว) และอย่าใช้รหัสผ่านแอดมินที่เดาง่าย
- ตั้ง `SECRET_KEY` เอง (ถ้าไม่ตั้ง ระบบจะสร้างให้และเก็บไว้ใน `instance/secret_key`)
- ห้องเล่นหายเมื่อรีสตาร์ทเซิร์ฟเวอร์ และยังไม่มีระบบกันสแปม/จำกัดจำนวนครั้งล็อคอิน ถ้าเปิดสาธารณะจริงควรเพิ่ม

---

# ขึ้น Render ให้เพื่อนเล่นผ่านลิงก์ (ทีละขั้น)

โปรเจกต์มีไฟล์ `render.yaml` (Blueprint) พร้อมแล้ว จะสร้างเว็บ + ฐานข้อมูล PostgreSQL ให้ในครั้งเดียว

1. สร้างรีโพบน GitHub แล้วอัปโหลดโฟลเดอร์โปรเจกต์ทั้งหมดขึ้นไป (มี `.gitignore` กันไฟล์ลับให้แล้ว)
2. เข้า render.com → **New +** → **Blueprint** → เลือกรีโพ → Render จะอ่าน `render.yaml` แล้วสร้าง
   - เว็บ `date-destiny-tcg` (แผนฟรี)
   - ฐานข้อมูล `dds-db` (แผนฟรี) และต่อ `DATABASE_URL` ให้อัตโนมัติ
   - `SECRET_KEY` และ `ADMIN_CLAIM_TOKEN` ถูกสุ่มให้เอง
3. รอ build ประมาณ 3–5 นาที จะได้ลิงก์ `https://ชื่อบริการ.onrender.com`
4. เปิดเว็บ → สมัครสมาชิก → ไปที่ `/claim-admin` → ใส่รหัสจาก Render → Environment → `ADMIN_CLAIM_TOKEN` → จะได้เป็น Admin
   แล้วเพิ่มการ์ดและ Sleeve ในหน้าจัดการระบบ (รูปถูกเก็บในฐานข้อมูล ไม่หายตอนรีสตาร์ท)
5. สร้างห้อง → กด "คัดลอกลิงก์ห้อง" → ส่งให้เพื่อน → เพื่อนสมัคร (ไม่ต้องใช้อีเมลยืนยัน) แล้วเข้าห้องได้ทันที

## ข้อควรรู้ของแผนฟรี
- เว็บฟรีจะหลับเมื่อไม่มีใครใช้ ~15 นาที เปิดครั้งแรกหลังหลับใช้เวลาประมาณ 1 นาที
- ห้องเล่นเก็บในหน่วยความจำ ถ้าเว็บหลับหรือถูกรีสตาร์ท ห้องที่เปิดอยู่จะหาย (บัญชี เด็ค การ์ดไม่หาย)
- ฐานข้อมูลฟรีของ Render หมดอายุหลังสร้าง 30 วัน ความจุ 1 GB ถ้าจะใช้ต่อยาว ให้อัปเกรด หรือสร้างฐานข้อมูลฟรีที่อื่น (เช่น Neon) แล้วใส่ลิงก์ใน `DATABASE_URL`
- `SKIP_EMAIL_VERIFY=1` ทำให้ใครก็สมัครได้โดยไม่ยืนยันอีเมล เหมาะกับกลุ่มเพื่อน ถ้ามี `MAIL_*` แล้วให้ตั้งเป็น 0
#   d a t e - d e s t i n y - t c g  
 #   d a t e - d e s t i n y - t c g  
 