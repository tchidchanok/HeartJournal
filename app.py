"""
บันทึกใจ — เว็บจดบันทึกอารมณ์ประจำวัน การเดินจงกรม
และการปฏิบัติตามหลักธรรมนาวา "วัง" 7 ขั้นตอน

Single-file Flask app (Tailwind CDN + SQLite)

วิธีรัน:
    pip install flask
    python app.py
แล้วเปิด http://127.0.0.1:5000
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, flash, g, redirect, render_template, request, url_for
from jinja2 import DictLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("MINDFUL_DB", os.path.join(BASE_DIR, "mindful.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")

# ---------------------------------------------------------------------------
# ข้อมูลคงที่
# ---------------------------------------------------------------------------

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
TH_WEEKDAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

MOOD_LEVELS = {
    1: {"emoji": "😢", "label": "แย่มาก"},
    2: {"emoji": "😟", "label": "ไม่ค่อยดี"},
    3: {"emoji": "😐", "label": "เฉยๆ"},
    4: {"emoji": "🙂", "label": "ดี"},
    5: {"emoji": "😄", "label": "ดีมาก"},
}

MOOD_TYPES = ["สุข", "สงบ", "ขอบคุณ", "ตื่นเต้น", "เบื่อ", "เหนื่อย",
              "เศร้า", "กังวล", "กลัว", "เหงา", "หงุดหงิด", "โกรธ", "อื่นๆ"]

KHANDHAS = ["รูป", "เวทนา", "สัญญา", "สังขาร", "วิญญาณ"]

# หลักธรรมนาวา "วัง" 7 ขั้นตอน
# blocks: p = ย่อหน้า, chant = บทสวด (บาลี, คำแปล), recite = บทท่อง (memorize = มีปุ่มซ่อนเพื่อฝึกท่อง),
#         stages = ลำดับขั้น (หัวข้อ, คำอธิบาย), terms = นิยาม (คำ, ความหมาย),
#         map = การจัดลง (ข้อความ, จัดเป็น), bullets = รายการ, quote = ข้อความเน้น
STEPS = [
    {
        "no": 1, "icon": "🪷",
        "title": "ระลึกพระรัตนตรัย",
        "summary": "จุดประสงค์ของการระลึกพระรัตนตรัย ก็เพื่อเป็นพลังทางใจ และพลังทางสติปัญญา "
                   "ในการเจริญจริยธรรมเพื่อไปสู่ความสิ้นทุกข์",
        "blocks": [
            {"type": "p", "text": "ระลึกถึงพระรัตนตรัย ย้ำ ๆ ซ้ำ ๆ โดยระลึกอยู่เสมอว่า"},
            {"type": "chant", "lines": [
                ("พุทโธ เม นาโถ", "พระพุทธเป็นที่พึ่งอันประเสริฐของข้าพเจ้า"),
                ("ธัมโม เม นาโถ", "พระธรรมเป็นที่พึ่งอันประเสริฐของข้าพเจ้า"),
                ("สังโฆ เม นาโถ", "พระสงฆ์เป็นที่พึ่งอันประเสริฐของข้าพเจ้า"),
            ]},
        ],
    },
    {
        "no": 2, "icon": "👋",
        "title": "ทักอารมณ์",
        "summary": "ในชีวิตที่ผ่านมาจิตไม่เคยได้เรียนรู้ จึงได้แต่รับอารมณ์ ฉะนั้น การทักอารมณ์ "
                   "จึงเป็นวิธีการหนึ่งที่จะสร้างสติ ซึ่งจะทำให้จิตรู้สึกตัว เมื่อใดก็ตามที่มีอารมณ์กระทบจิต "
                   "โดยอารมณ์นั้นถูกรู้ด้วยการทัก จะทำให้จิตรู้จักอารมณ์ที่เกิดขึ้น และไม่เป็นไปตามอารมณ์นั้น",
        "blocks": [
            {"type": "p", "text": "ตัวอย่างการทักอารมณ์เมื่อมี “ความโกรธ” เกิดขึ้น ให้ทักว่า"},
            {"type": "recite", "title": "ทักอารมณ์", "lines": [
                "นี่คือ “ความโกรธ”",
                "“ความโกรธ” กำลังเกิดขึ้นกับจิต",
                "จิตกำลังมี “ความโกรธ”",
                "“ความโกรธ” กำลังปรุงแต่งจิต",
                "จิตกำลังถูก “ความโกรธ” ปรุงแต่ง",
            ]},
        ],
        "link": ("mood", "ไปทักอารมณ์ในบันทึกอารมณ์"),
    },
    {
        "no": 3, "icon": "🌍",
        "title": "ท่องธาตุกัมมัฏฐาน 4",
        "summary": "กำหนดพิจารณากายนี้ให้เห็นว่า เป็นแต่เพียงธาตุ ๔ คือ ดิน น้ำ ไฟ ลม ประกอบรวมกันอยู่ "
                   "ไม่ใช่เรา ไม่ใช่ของเรา",
        "memorize": True,
        "blocks": [
            {"type": "recite", "title": "บทท่องธาตุกัมมัฏฐาน ๔ (ท่องให้ได้แบบทุกตัวอักษร)", "memorize": True, "lines": [
                "ธาตุกัมมัฏฐาน ๔ ธาตุ ๔ คือ ธาตุดิน เรียก ปฐวีธาตุ ธาตุน้ำ เรียก อาโปธาตุ "
                "ธาตุไฟ เรียก เตโชธาตุ ธาตุลม เรียก วาโยธาตุ",
                "ธาตุอันใดมีลักษณะแข้นแข็ง ธาตุนั้นเป็นธาตุดิน ธาตุดินที่มีในกายนี้ คือ ผม ขน เล็บ ฟัน หนัง "
                "เนื้อ เอ็น กระดูก เยื่อในกระดูก ม้าม หัวใจ ตับ พังผืด ไต ปอด ไส้ใหญ่ ไส้น้อย อาหารใหม่ อาหารเก่า",
                "ธาตุอันใดมีลักษณะเหลวเอิบอาบ ธาตุนั้นเป็นธาตุน้ำ ธาตุน้ำที่มีในกายนี้ คือ น้ำดี น้ำเสลด "
                "น้ำหนอง น้ำเลือด น้ำมันเหงื่อ น้ำมันข้น น้ำตา น้ำมันเปลว น้ำลาย น้ำมูก น้ำไขข้อ น้ำปัสสาวะ",
                "ธาตุอันใดมีลักษณะร้อน ธาตุนั้นเป็นธาตุไฟ ธาตุไฟที่มีในกายนี้ คือ ไฟที่ทำกายให้อบอุ่น "
                "ไฟที่ทำกายให้ทรุดโทรม ไฟที่ทำกายให้กระวนกระวาย ไฟที่ทำอาหารให้ย่อย",
                "ธาตุอันใดมีลักษณะพัดไปมา ธาตุนั้นเป็นธาตุลม ธาตุลมที่มีในกายนี้ คือ ลมพัดขึ้นเบื้องบน "
                "ลมพัดลงเบื้องต่ำ ลมในท้อง ลมในไส้ ลมพัดไปตามตัว ลมหายใจ",
                "ความกำหนดพิจารณากายนี้ให้เห็นว่า เป็นแต่เพียงธาตุ ๔ คือ ดิน น้ำ ไฟ ลม ประกอบรวมกันอยู่ "
                "ไม่ใช่เรา ไม่ใช่ของเรา เรียกว่า ธาตุกัมมัฏฐาน",
            ]},
            {"type": "p", "text":
                "เมื่อพิจารณาเห็นร่างกายแยกออกเป็นธาตุ ๔ ดิน น้ำ ไฟ ลม ย้ำๆ ซ้ำๆ อยู่เสมอ "
                "ก็จะไม่เห็นร่างกายประกอบรวมกันอยู่ เราก็จะเกิดความรู้ (วิชชา) อันเป็นความเห็นที่ถูกต้องขึ้นมา "
                "ความรู้ที่ถูกต้องนี้จะไปทำลายความไม่รู้ (อวิชชา) ในจิต และจะค่อยๆ ถอนสักกายทิฏฐิ "
                "อันเป็นไปเพื่อความยึดมั่นถือมั่นได้ในระดับหนึ่ง แต่หากจะถอนสักกายทิฏฐิให้ได้เด็ดขาด "
                "ก็ต้องฝึกมอง “เห็นอารมณ์เกิด-ดับ” ประกอบพร้อมไปด้วย เรียกว่า “เจริญสมถะและวิปัสสนา” "
                "ควบคู่กันไป จนกว่าจะเกิดกำลังในการละความเห็นผิดได้อย่างเด็ดขาด"},
        ],
    },
    {
        "no": 4, "icon": "🍂",
        "title": "พิจารณาร่างกาย 6 ขั้นตอน",
        "summary": "หมดลมหายใจ → น้ำดันดิน → ธาตุดินแตก → น้ำละลายดิน → "
                   "ร่างกายเหลือแต่โครงกระดูก → กระดูกสลายลงสู่ดิน",
        "blocks": [
            {"type": "stages", "rows": [
                ("หมดลมหายใจ",
                 "ให้พิจารณาว่า เมื่อร่างกายหมดลมหายใจแล้ว ธาตุลมกับธาตุไฟก็สลายออกจากกัน "
                 "เราก็ขาดการรับรู้ทุกส่วนทางร่างกาย ไม่สามารถควบคุมร่างกายได้อีก ร่างกายก็จะล้มนอนราบไปกับแผ่นดิน "
                 "(กำหนดความคิด ยกเรื่องของร่างกายที่นอนราบไปกับแผ่นดินขึ้นมาสู่การพิจารณา)"),
                ("น้ำดันดิน",
                 "เมื่อธาตุลมกับธาตุไฟแยกออกจากร่างกายแล้ว ก็เหลือแต่ธาตุดินกับธาตุน้ำที่ยังคงประกอบรวมกันอยู่ "
                 "ให้พิจารณาว่า หากทิ้งให้ร่างกายนอนราบไปกับแผ่นดินนานหลายๆ วัน น้ำจะเริ่มดันดินออกมา "
                 "ร่างกายก็จะบวม พอง ขึ้นอืด เขียวช้ำ ตาถลน ลิ้นจุกปาก แขนขาบวม พอง ชี้ชูชันขึ้น"),
                ("ธาตุดินแตก",
                 "ธาตุน้ำที่ดันดินออกมา เมื่อผ่านไปหลายวันเข้า ผิวหนังก็จะปริแตกไปทั่วทั้งร่างกาย "
                 "น้ำเหลือง น้ำหนอง น้ำเลือด ก็จะไหลเยิ้มออกมาตามรอยที่ปริแตกทั่วทั้งร่างกายนั้น"),
                ("น้ำละลายดิน",
                 "เมื่อน้ำเหลือง น้ำหนอง น้ำเลือด ไหลออกมาตามรอยปริแตกทั่วทั้งร่างกาย เนื้อหนังก็เริ่มเปื่อยเน่า "
                 "และอวัยวะส่วนอื่นๆ ก็เข้าสู่สภาพย่อยสลายลงสู่ดิน"),
                ("ร่างกายเหลือแต่โครงกระดูก",
                 "เมื่อเนื้อหนังย่อยสลายลงดินหมดแล้ว ก็เหลือแต่โครงกระดูกขาวโพลนนอนอยู่ พิจารณากะโหลกศีรษะ "
                 "กระดูกซี่โครง กระดูกแขน กระดูกขา กระดูกทั้งโครงที่ไม่มีเนื้อเหลือติดอยู่ หลุดแยกออกจากกันทุกส่วน"),
                ("กระดูกสลายลงสู่ดิน",
                 "พิจารณาเห็นโครงกระดูกเป็นสภาพ “ผุ” “กร่อน” ทั่วทั้งโครง แล้วพิจารณาเห็นกระดูกที่ผุกร่อนนั้น"
                 "ค่อยๆ สลายไปเป็นดิน โดยพิจารณาเทียบเคียงให้จิตเห็นว่า"),
            ]},
            {"type": "quote", "lines": ["“ดินกับร่างกายของเราเป็นอันเดียวกัน", "ร่างกายของเรากับดินก็เป็นอันเดียวกัน”"]},
        ],
    },
    {
        "no": 5, "icon": "🖐️",
        "title": "ท่องขันธ์ 5 / แยกขันธ์ 5",
        "summary": "กายกับใจ แบ่งออกเป็น ๕ ส่วน เรียกว่า ขันธ์ ๕ ได้แก่ ๑. รูปขันธ์ ๒. เวทนาขันธ์ "
                   "๓. สัญญาขันธ์ ๔. สังขารขันธ์ ๕. วิญญาณขันธ์",
        "blocks": [
            {"type": "terms", "rows": [
                ("รูป", "ธาตุ ๔ คือ ดิน น้ำ ไฟ ลม ประกอบรวมกันเป็นกายนี้ เรียกว่า รูป"),
                ("เวทนา", "สภาพของอารมณ์ที่เป็นสุข คือ สบายกาย สบายใจ หรืออารมณ์ที่เป็นทุกข์ คือ ไม่สบายกาย "
                          "ไม่สบายใจ หรืออารมณ์เฉยๆ คือ ไม่ทุกข์ไม่สุข เรียกว่า เวทนา"),
                ("สัญญา", "ความจำได้ การหมายรู้ คือ จำรูป จำเสียง จำกลิ่น จำรส จำการสัมผัส "
                          "จำอารมณ์ที่เกิดขึ้นกับใจได้ เรียกว่า สัญญา"),
                ("สังขาร", "เจตสิกธรรม คือ สิ่งที่ปรุงแต่งใจ เป็นส่วนดีเรียกกุศล เป็นส่วนชั่วเรียกอกุศล "
                           "เป็นส่วนกลางๆ ไม่ดีไม่ชั่วเรียกอัพยากต (อ่านว่า อับ-พะ-ยา-กะ-ตะ) เรียกว่า สังขาร"),
                ("วิญญาณ", "การรับรู้ ทางตา ทางหู ทางจมูก ทางลิ้น ทางกาย ทางใจ เรียกว่า วิญญาณ"),
            ]},
            {"type": "p", "text": "ขันธ์ ๕ นี้ กล่าวโดยย่อ แบ่งเป็น “รูป” กับ “นาม”"},
            {"type": "map", "rows": [
                ("ธาตุ ๔", "“รูป”"),
                ("เวทนา สัญญา สังขาร วิญญาณ", "“นาม”"),
            ]},
        ],
    },
    {
        "no": 6, "icon": "🌊",
        "title": "ดูขันธ์ 5 เกิดดับ / จับอารมณ์ลงขันธ์",
        "summary": "การดูขันธ์ ๕ เกิด-ดับ จะต้องยกเอาอารมณ์ (สิ่งที่ผ่านเข้ามาให้รับรู้) เป็นที่ตั้งแห่งการกำหนด "
                   "เพราะขันธ์ ๕ จะเกิด-ดับ พร้อมกับอารมณ์",
        "blocks": [
            {"type": "p", "text": "ตัวอย่างเช่น เมื่อเกิดอารมณ์โกรธขึ้นมาในจิต"},
            {"type": "map", "rows": [
                ("กาย ได้รับความเร่าร้อนขณะโกรธ", "รูปขันธ์"),
                ("ความรู้สึก ในขณะที่โกรธ", "เวทนาขันธ์"),
                ("การจำ อารมณ์ที่โกรธไว้", "สัญญาขันธ์"),
                ("การปรุงแต่ง อารมณ์โกรธ", "สังขารขันธ์"),
                ("การรับรู้ ในการปรุงแต่งอารมณ์โกรธ ในการจำอารมณ์โกรธ ในความรู้สึกที่โกรธ "
                 "ในกายที่เร่าร้อนขณะโกรธ", "วิญญาณขันธ์"),
            ]},
            {"type": "p", "text":
                "เพราะฉะนั้น การเกิดขึ้นขันธ์ ๕ จึงเกิดขึ้นพร้อมกับอารมณ์ ดับพร้อมกับอารมณ์ "
                "หากมีสติเฝ้าดูอารมณ์โกรธที่เกิดขึ้นโดยไม่ต้องทำอะไรกับอารมณ์โกรธ จนเห็นอารมณ์โกรธนั้นดับลงไปเอง "
                "ก็ชื่อว่า ได้เห็นการดับไปของขันธ์ ๕"},
        ],
        "link": ("mood", "ไปจับอารมณ์ลงขันธ์ในบันทึกอารมณ์"),
    },
    {
        "no": 7, "icon": "💡",
        "title": "พิจารณาขันธ์ 5 ลงอริยสัจ 4",
        "summary": "การกำหนดพิจารณาขันธ์ ๕ ลงอริยสัจ ๔ ให้เห็นความเกิด-ดับอยู่เสมอ "
                   "จะเป็นไปเพื่อความสิ้นอาสวะได้",
        "blocks": [
            {"type": "bullets", "lines": [
                "อารมณ์ทุกอารมณ์ให้จัดลงในส่วนของทุกข์เสมอ",
                "ตัณหาที่เกิดร่วมกับอารมณ์ทุกอารมณ์ให้จัดลงสมุทัย",
                "ความดับของตัณหาพร้อมกับความดับของอารมณ์ให้จัดลงนิโรธ",
                "กำหนดรู้อารมณ์เกิด-ดับ พร้อมกับตัณหาให้จัดลง มรรค",
            ]},
            {"type": "p", "text": "ตัวอย่างเช่น"},
            {"type": "map", "rows": [
                ("อารมณ์โกรธที่อาศัยขันธ์ ๕ เกิด", "ทุกขสัจจะ"),
                ("ตัณหาที่เกิดร่วมกับอารมณ์โกรธ", "สมุทัยสัจจะ"),
                ("ความดับไปของตัณหาพร้อมกับอารมณ์โกรธ", "นิโรธสัจจะ"),
                ("การกำหนดรู้ความเกิดความดับของอารมณ์พร้อมกับตัณหา", "มรรคสัจจะ"),
            ]},
        ],
        "link": ("mood", "ไปพิจารณาลงอริยสัจ 4 ในบันทึกอารมณ์"),
    },
]

# ---------------------------------------------------------------------------
# ฐานข้อมูล
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS moods (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date  TEXT NOT NULL,
    entry_time  TEXT NOT NULL,
    level       INTEGER NOT NULL,
    mood_type   TEXT NOT NULL,
    cause       TEXT DEFAULT '',
    observe     TEXT DEFAULT '',
    khandha     TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS walks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date  TEXT NOT NULL,
    minutes     INTEGER NOT NULL,
    phase       INTEGER DEFAULT 0,
    step        INTEGER DEFAULT 0,
    topic       TEXT DEFAULT '',
    rounds      INTEGER DEFAULT 0,
    note        TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS practice (
    entry_date  TEXT PRIMARY KEY,
    steps       TEXT DEFAULT '',
    reflection  TEXT DEFAULT '',
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_moods_date ON moods(entry_date);
CREATE INDEX IF NOT EXISTS idx_walks_date ON walks(entry_date);
"""

# คอลัมน์ที่เพิ่มภายหลัง — อัปเกรดฐานข้อมูลเวอร์ชันเก่าให้อัตโนมัติ
MIGRATIONS = {
    "moods": {"khandha": "TEXT DEFAULT ''"},
    "walks": {"step": "INTEGER DEFAULT 0", "topic": "TEXT DEFAULT ''"},
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        for table, columns in MIGRATIONS.items():
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, decl in columns.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_str():
    return datetime.now().isoformat(timespec="seconds")


def parse_date(value, default=None):
    try:
        return date.fromisoformat((value or "").strip()).isoformat()
    except ValueError:
        return default if default is not None else date.today().isoformat()


def parse_time(value):
    try:
        return datetime.strptime((value or "").strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return datetime.now().strftime("%H:%M")


def to_int(value, default, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def parse_steps(text):
    return {int(s) for s in (text or "").split(",") if s.isdigit() and 1 <= int(s) <= 7}


def calc_streak(db, today):
    rows = db.execute(
        "SELECT entry_date FROM moods UNION SELECT entry_date FROM walks "
        "UNION SELECT entry_date FROM practice WHERE steps != ''"
    ).fetchall()
    active = {r[0] for r in rows}
    d = today if today.isoformat() in active else today - timedelta(days=1)
    streak = 0
    while d.isoformat() in active:
        streak += 1
        d -= timedelta(days=1)
    return streak


@app.template_filter("thai_date")
def thai_date(value):
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{d.day} {TH_MONTHS[d.month - 1]} {d.year + 543}"


@app.template_filter("thai_weekday")
def thai_weekday(value):
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return TH_WEEKDAYS[d.weekday()]


@app.context_processor
def inject_globals():
    return {
        "today": date.today().isoformat(),
        "mood_levels": MOOD_LEVELS,
        "mood_types": MOOD_TYPES,
        "khandhas": KHANDHAS,
        "steps": STEPS,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    db = get_db()
    today = date.today()
    start = today - timedelta(days=6)
    rng = (start.isoformat(), today.isoformat())

    moods = {r["entry_date"]: r for r in db.execute(
        "SELECT entry_date, AVG(level) AS avg_level, COUNT(*) AS n FROM moods "
        "WHERE entry_date BETWEEN ? AND ? GROUP BY entry_date", rng)}
    walks = {r["entry_date"]: r["total"] for r in db.execute(
        "SELECT entry_date, SUM(minutes) AS total FROM walks "
        "WHERE entry_date BETWEEN ? AND ? GROUP BY entry_date", rng)}
    practices = {r["entry_date"]: parse_steps(r["steps"]) for r in db.execute(
        "SELECT entry_date, steps FROM practice WHERE entry_date BETWEEN ? AND ?", rng)}

    week = []
    for i in range(7):
        k = (start + timedelta(days=i)).isoformat()
        m = moods.get(k)
        week.append({
            "date": k,
            "mood": round(m["avg_level"]) if m else None,
            "mood_n": m["n"] if m else 0,
            "walk": walks.get(k, 0),
            "steps": practices.get(k, set()),
        })

    hour = datetime.now().hour
    greeting = ("สวัสดีตอนเช้า" if hour < 12 else
                "สวัสดีตอนบ่าย" if hour < 17 else
                "สวัสดีตอนเย็น" if hour < 21 else "ราตรีสวัสดิ์")

    return render_template(
        "dashboard.html",
        week=week,
        today_row=week[-1],
        max_walk=max([w["walk"] for w in week] + [1]),
        streak=calc_streak(db, today),
        total_walk=db.execute("SELECT COALESCE(SUM(minutes), 0) FROM walks").fetchone()[0],
        recent_moods=db.execute(
            "SELECT * FROM moods ORDER BY entry_date DESC, entry_time DESC, id DESC LIMIT 4").fetchall(),
        greeting=greeting,
    )


@app.route("/mood", methods=["GET", "POST"])
def mood():
    db = get_db()
    if request.method == "POST":
        level = to_int(request.form.get("level"), 0, 0, 5)
        if level < 1:
            flash("กรุณาเลือกระดับอารมณ์", "error")
            return redirect(url_for("mood"))
        mood_type = request.form.get("mood_type", "")
        if mood_type not in MOOD_TYPES:
            mood_type = "อื่นๆ"
        db.execute(
            "INSERT INTO moods (entry_date, entry_time, level, mood_type, cause, observe, khandha, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (parse_date(request.form.get("entry_date")), parse_time(request.form.get("entry_time")),
             level, mood_type,
             request.form.get("cause", "").strip()[:2000],
             request.form.get("observe", "").strip()[:2000],
             ",".join(k for k in KHANDHAS if k in request.form.getlist("khandha")),
             request.form.get("note", "").strip()[:4000],
             now_str()),
        )
        db.commit()
        flash("บันทึกอารมณ์เรียบร้อยแล้ว 🙏", "success")
        return redirect(url_for("mood"))

    filter_date = parse_date(request.args.get("date"), default="")
    if filter_date:
        entries = db.execute(
            "SELECT * FROM moods WHERE entry_date = ? ORDER BY entry_time DESC, id DESC",
            (filter_date,)).fetchall()
    else:
        entries = db.execute(
            "SELECT * FROM moods ORDER BY entry_date DESC, entry_time DESC, id DESC LIMIT 50").fetchall()

    since = (date.today() - timedelta(days=29)).isoformat()
    dist = db.execute(
        "SELECT mood_type, COUNT(*) AS n FROM moods WHERE entry_date >= ? "
        "GROUP BY mood_type ORDER BY n DESC", (since,)).fetchall()

    return render_template(
        "mood.html", entries=entries, filter_date=filter_date, dist=dist,
        dist_max=max([r["n"] for r in dist] + [1]),
        now_time=datetime.now().strftime("%H:%M"),
    )


@app.post("/mood/<int:entry_id>/delete")
def mood_delete(entry_id):
    db = get_db()
    db.execute("DELETE FROM moods WHERE id = ?", (entry_id,))
    db.commit()
    flash("ลบบันทึกแล้ว", "success")
    return redirect(request.referrer or url_for("mood"))


@app.route("/walk", methods=["GET", "POST"])
def walk():
    db = get_db()
    if request.method == "POST":
        minutes = to_int(request.form.get("minutes"), 0, 0, 600)
        if minutes < 1:
            flash("กรุณาระบุเวลาเดินจงกรมอย่างน้อย 1 นาที", "error")
            return redirect(url_for("walk"))
        db.execute(
            "INSERT INTO walks (entry_date, minutes, phase, step, topic, rounds, note, created_at) "
            "VALUES (?, ?, 0, ?, ?, ?, ?, ?)",
            (parse_date(request.form.get("entry_date")), minutes,
             to_int(request.form.get("step"), 0, 0, 7),
             request.form.get("topic", "").strip()[:1000],
             to_int(request.form.get("rounds"), 0, 0, 10000),
             request.form.get("note", "").strip()[:4000], now_str()),
        )
        db.commit()
        flash(f"บันทึกการเดินจงกรม {minutes} นาทีแล้ว สาธุ 🙏", "success")
        return redirect(url_for("walk"))

    today = date.today()
    week_start = (today - timedelta(days=6)).isoformat()
    stats = {
        "today": db.execute("SELECT COALESCE(SUM(minutes),0) FROM walks WHERE entry_date = ?",
                            (today.isoformat(),)).fetchone()[0],
        "week": db.execute("SELECT COALESCE(SUM(minutes),0) FROM walks WHERE entry_date >= ?",
                           (week_start,)).fetchone()[0],
        "total": db.execute("SELECT COALESCE(SUM(minutes),0) FROM walks").fetchone()[0],
        "sessions": db.execute("SELECT COUNT(*) FROM walks").fetchone()[0],
    }
    step_stats = {r["step"]: r for r in db.execute(
        "SELECT step, COUNT(*) AS n, SUM(minutes) AS total FROM walks WHERE step > 0 GROUP BY step")}
    sessions = db.execute(
        "SELECT * FROM walks ORDER BY entry_date DESC, id DESC LIMIT 50").fetchall()
    return render_template("walk.html", sessions=sessions, stats=stats, step_stats=step_stats,
                           step_brief=[{"no": s["no"], "title": s["title"], "summary": s["summary"]}
                                       for s in STEPS])


@app.post("/walk/<int:entry_id>/delete")
def walk_delete(entry_id):
    db = get_db()
    db.execute("DELETE FROM walks WHERE id = ?", (entry_id,))
    db.commit()
    flash("ลบบันทึกแล้ว", "success")
    return redirect(url_for("walk"))


@app.route("/practice", methods=["GET", "POST"])
def practice():
    db = get_db()
    if request.method == "POST":
        d = parse_date(request.form.get("entry_date"))
        steps = sorted({int(s) for s in request.form.getlist("steps") if s.isdigit() and 1 <= int(s) <= 7})
        db.execute(
            "INSERT INTO practice (entry_date, steps, reflection, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(entry_date) DO UPDATE SET steps = excluded.steps, "
            "reflection = excluded.reflection, updated_at = excluded.updated_at",
            (d, ",".join(map(str, steps)), request.form.get("reflection", "").strip()[:4000], now_str()),
        )
        db.commit()
        msg = "ปฏิบัติครบ 7 ขั้นตอนแล้ว อนุโมทนาสาธุ 🙏" if len(steps) == 7 else f"บันทึกแล้ว ({len(steps)}/7 ขั้นตอน)"
        flash(msg, "success")
        return redirect(url_for("practice", date=d))

    d = parse_date(request.args.get("date"))
    cur = date.fromisoformat(d)
    row = db.execute("SELECT * FROM practice WHERE entry_date = ?", (d,)).fetchone()

    hist_start = date.today() - timedelta(days=13)
    hist_rows = {r["entry_date"]: len(parse_steps(r["steps"])) for r in db.execute(
        "SELECT entry_date, steps FROM practice WHERE entry_date >= ?", (hist_start.isoformat(),))}
    history = [((hist_start + timedelta(days=i)).isoformat(),
                hist_rows.get((hist_start + timedelta(days=i)).isoformat(), 0)) for i in range(14)]

    return render_template(
        "practice.html",
        cur_date=d,
        prev_date=(cur - timedelta(days=1)).isoformat(),
        next_date=(cur + timedelta(days=1)).isoformat(),
        done=parse_steps(row["steps"]) if row else set(),
        reflection=row["reflection"] if row else "",
        mood_count=db.execute("SELECT COUNT(*) FROM moods WHERE entry_date = ?", (d,)).fetchone()[0],
        walk_minutes=db.execute("SELECT COALESCE(SUM(minutes),0) FROM walks WHERE entry_date = ?",
                                (d,)).fetchone()[0],
        history=history,
    )


# ---------------------------------------------------------------------------
# Templates (Jinja2 ในไฟล์เดียว)
# ---------------------------------------------------------------------------

BASE_HTML = """<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{% endblock %} · บันทึกใจ</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: { extend: { fontFamily: { sans: ['Sarabun', 'ui-sans-serif', 'system-ui', 'sans-serif'] } } }
    };
  </script>
  <style type="text/tailwindcss">
    @layer components {
      .card  { @apply rounded-3xl border border-stone-200/80 bg-white/90 p-5 shadow-sm sm:p-6; }
      .label { @apply mb-1.5 block text-sm font-medium text-stone-700; }
      .input { @apply w-full rounded-xl border border-stone-300 bg-white px-3.5 py-2.5 text-stone-800 shadow-sm outline-none transition placeholder:text-stone-400 focus:border-amber-400 focus:ring-4 focus:ring-amber-100; }
      .btn   { @apply inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 font-semibold transition active:scale-[.98] disabled:opacity-50; }
      .btn-primary { @apply btn bg-amber-600 text-white shadow-sm hover:bg-amber-700; }
      .btn-green   { @apply btn bg-emerald-600 text-white shadow-sm hover:bg-emerald-700; }
      .btn-ghost   { @apply btn border border-stone-300 bg-white text-stone-700 hover:bg-stone-50; }
      .nav-link    { @apply whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium text-stone-600 transition hover:bg-amber-50 hover:text-amber-800; }
      .nav-active  { @apply bg-amber-100 text-amber-900; }
    }
  </style>
</head>
<body class="min-h-screen bg-gradient-to-b from-amber-50/70 via-stone-50 to-emerald-50/40 font-sans text-stone-800 antialiased">
  <header class="sticky top-0 z-30 border-b border-stone-200/70 bg-white/80 backdrop-blur">
    <div class="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <a href="{{ url_for('dashboard') }}" class="flex items-center gap-2">
        <span class="grid h-9 w-9 place-items-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-lg shadow">🪷</span>
        <span class="leading-tight">
          <span class="block text-lg font-bold text-stone-800">บันทึกใจ</span>
          <span class="block text-xs text-stone-500">อารมณ์ · จงกรม · ธรรมนาวา วัง</span>
        </span>
      </a>
      <nav class="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 sm:pb-0">
        {% set ep = request.endpoint %}
        <a href="{{ url_for('dashboard') }}" class="nav-link {% if ep == 'dashboard' %}nav-active{% endif %}">🏠 หน้าหลัก</a>
        <a href="{{ url_for('mood') }}" class="nav-link {% if ep == 'mood' %}nav-active{% endif %}">📝 บันทึกอารมณ์</a>
        <a href="{{ url_for('walk') }}" class="nav-link {% if ep == 'walk' %}nav-active{% endif %}">👣 เดินจงกรม</a>
        <a href="{{ url_for('practice') }}" class="nav-link {% if ep == 'practice' %}nav-active{% endif %}">📿 ธรรมนาวา 7 ขั้น</a>
      </nav>
    </div>
  </header>

  <main class="mx-auto max-w-6xl px-4 py-6 sm:py-8">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for cat, msg in messages %}
        <div class="mb-4 flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm
                    {% if cat == 'error' %}border-rose-200 bg-rose-50 text-rose-800{% else %}border-emerald-200 bg-emerald-50 text-emerald-800{% endif %}">
          <span>{{ msg }}</span>
          <button type="button" onclick="this.parentElement.remove()" class="text-lg leading-none opacity-60 hover:opacity-100">&times;</button>
        </div>
      {% endfor %}
    {% endwith %}
    {% block content %}{% endblock %}
  </main>

  <footer class="mx-auto max-w-6xl px-4 pb-10 pt-4 text-center text-xs leading-relaxed text-stone-500">
    บันทึกใจ · ฝึกปฏิบัติตามหลักธรรมนาวา “วัง” 7 ขั้นตอน เพื่อความพ้นทุกข์
  </footer>
  {% block scripts %}{% endblock %}
</body>
</html>
"""

DASHBOARD_HTML = """{% extends "base.html" %}
{% block title %}หน้าหลัก{% endblock %}
{% block content %}
<section class="relative overflow-hidden rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-100 via-orange-50 to-emerald-100/60 p-6 sm:p-8">
  <div class="pointer-events-none absolute -right-6 -top-6 select-none text-[9rem] leading-none opacity-10">🪷</div>
  <p class="text-sm font-medium text-amber-800/80">วัน{{ today|thai_weekday }}ที่ {{ today|thai_date }}</p>
  <h1 class="mt-1 text-2xl font-bold text-stone-800 sm:text-3xl">{{ greeting }} 🙏</h1>
  <p class="mt-2 max-w-2xl text-stone-600">พุทโธ เม นาโถ · ธัมโม เม นาโถ · สังโฆ เม นาโถ — ทักอารมณ์ เดินจงกรม และปฏิบัติตามหลักธรรมนาวา “วัง” 7 ขั้นตอน ย้ำๆ ซ้ำๆ ทุกวัน</p>
  <div class="mt-5 flex flex-wrap gap-2">
    <a href="{{ url_for('mood') }}" class="btn-primary">📝 บันทึกอารมณ์</a>
    <a href="{{ url_for('walk') }}" class="btn-green">👣 เริ่มเดินจงกรม</a>
    <a href="{{ url_for('practice') }}" class="btn-ghost">📿 ปฏิบัติ 7 ขั้นตอน</a>
  </div>
</section>

<section class="mt-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
  <div class="card">
    <p class="text-sm text-stone-500">อารมณ์วันนี้</p>
    <p class="mt-2 text-4xl">{% if today_row.mood %}{{ mood_levels[today_row.mood].emoji }}{% else %}<span class="text-stone-300">—</span>{% endif %}</p>
    <p class="mt-1 text-xs text-stone-500">{% if today_row.mood_n %}บันทึก {{ today_row.mood_n }} ครั้ง{% else %}ยังไม่ได้บันทึก{% endif %}</p>
  </div>
  <div class="card">
    <p class="text-sm text-stone-500">เดินจงกรมวันนี้</p>
    <p class="mt-2 text-3xl font-bold text-emerald-700">{{ today_row.walk }} <span class="text-base font-medium">นาที</span></p>
    <p class="mt-1 text-xs text-stone-500">สะสมทั้งหมด {{ total_walk }} นาที</p>
  </div>
  <div class="card">
    <p class="text-sm text-stone-500">ธรรมนาวาวันนี้</p>
    <p class="mt-2 text-3xl font-bold text-amber-700">{{ today_row.steps|length }}<span class="text-base font-medium text-stone-500">/7</span></p>
    <div class="mt-2 h-2 overflow-hidden rounded-full bg-stone-100">
      <div class="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500" style="width: {{ (today_row.steps|length / 7 * 100)|round|int }}%"></div>
    </div>
  </div>
  <div class="card">
    <p class="text-sm text-stone-500">ปฏิบัติต่อเนื่อง</p>
    <p class="mt-2 text-3xl font-bold text-orange-600">{{ streak }} <span class="text-base font-medium">วัน</span></p>
    <p class="mt-1 text-xs text-stone-500">{% if streak %}ทำต่อไปนะ 🔥{% else %}เริ่มวันนี้ได้เลย{% endif %}</p>
  </div>
</section>

<section class="mt-6 grid gap-6 lg:grid-cols-5">
  <div class="card lg:col-span-3">
    <h2 class="text-lg font-bold">ภาพรวม 7 วันล่าสุด</h2>
    <div class="mt-4 space-y-3">
      {% for d in week|reverse %}
      <div class="grid grid-cols-[4.5rem_2.5rem_1fr_auto] items-center gap-3">
        <div class="leading-tight">
          <p class="text-sm font-semibold {% if d.date == today %}text-amber-700{% endif %}">{{ d.date|thai_weekday }}</p>
          <p class="text-xs text-stone-500">{{ d.date|thai_date }}</p>
        </div>
        <div class="text-center text-2xl" title="อารมณ์เฉลี่ย">{% if d.mood %}{{ mood_levels[d.mood].emoji }}{% else %}<span class="text-base text-stone-300">·</span>{% endif %}</div>
        <div class="flex items-center gap-2" title="เดินจงกรม">
          <div class="h-2.5 flex-1 overflow-hidden rounded-full bg-stone-100">
            <div class="h-full rounded-full bg-emerald-500" style="width: {{ (d.walk / max_walk * 100)|round|int }}%"></div>
          </div>
          <span class="w-12 text-right text-xs text-stone-500">{{ d.walk }} น.</span>
        </div>
        <a href="{{ url_for('practice', date=d.date) }}" class="flex gap-1" title="ธรรมนาวา {{ d.steps|length }}/7">
          {% for n in range(1, 8) %}
            <span class="h-2.5 w-2.5 rounded-full {% if n in d.steps %}bg-amber-500{% else %}bg-stone-200{% endif %}"></span>
          {% endfor %}
        </a>
      </div>
      {% endfor %}
    </div>
    <div class="mt-5 flex flex-wrap gap-4 border-t border-stone-100 pt-4 text-xs text-stone-500">
      <span>😊 อารมณ์เฉลี่ย</span>
      <span class="flex items-center gap-1"><span class="h-2 w-4 rounded-full bg-emerald-500"></span> นาทีเดินจงกรม</span>
      <span class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-full bg-amber-500"></span> ขั้นตอนธรรมนาวา</span>
    </div>
  </div>

  <div class="card lg:col-span-2">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-bold">บันทึกอารมณ์ล่าสุด</h2>
      <a href="{{ url_for('mood') }}" class="text-sm font-medium text-amber-700 hover:underline">ดูทั้งหมด →</a>
    </div>
    <div class="mt-4 space-y-3">
      {% for m in recent_moods %}
      <div class="flex gap-3 rounded-2xl bg-stone-50 p-3">
        <span class="text-3xl">{{ mood_levels[m.level].emoji }}</span>
        <div class="min-w-0">
          <p class="text-sm"><span class="font-semibold">{{ m.mood_type }}</span>
            <span class="text-stone-500">· {{ m.entry_date|thai_date }} {{ m.entry_time }}</span></p>
          <p class="truncate text-sm text-stone-600">{{ m.note or m.cause or m.observe or '—' }}</p>
        </div>
      </div>
      {% else %}
      <p class="rounded-2xl bg-stone-50 p-6 text-center text-sm text-stone-500">ยังไม่มีบันทึก ลองเริ่มทักอารมณ์แรกของวันนี้ดูนะ</p>
      {% endfor %}
    </div>
  </div>
</section>
{% endblock %}
"""

MOOD_HTML = """{% extends "base.html" %}
{% block title %}บันทึกอารมณ์{% endblock %}
{% block content %}
<div class="mb-6">
  <h1 class="text-2xl font-bold sm:text-3xl">📝 บันทึกอารมณ์ประจำวัน</h1>
  <p class="mt-1 text-stone-600">ทักอารมณ์ (ขั้นที่ 2) · จับอารมณ์ลงขันธ์ (ขั้นที่ 6) · พิจารณาขันธ์ 5 ลงอริยสัจ 4 (ขั้นที่ 7)</p>
</div>

<div class="grid gap-6 lg:grid-cols-5">
  <form method="post" class="card h-fit space-y-5 lg:col-span-2">
    <div class="grid grid-cols-2 gap-3">
      <div><label class="label" for="entry_date">วันที่</label>
        <input class="input" type="date" id="entry_date" name="entry_date" value="{{ today }}" max="{{ today }}" required></div>
      <div><label class="label" for="entry_time">เวลา</label>
        <input class="input" type="time" id="entry_time" name="entry_time" value="{{ now_time }}" required></div>
    </div>

    <div>
      <span class="label">ตอนนี้รู้สึกอย่างไร?</span>
      <div class="grid grid-cols-5 gap-2">
        {% for lv, info in mood_levels.items() %}
        <label class="cursor-pointer">
          <input type="radio" name="level" value="{{ lv }}" class="peer sr-only" {% if lv == 3 %}checked{% endif %} required>
          <div class="flex flex-col items-center rounded-2xl border border-stone-200 bg-white py-2.5 transition hover:bg-stone-50 peer-checked:border-amber-400 peer-checked:bg-amber-50 peer-checked:ring-2 peer-checked:ring-amber-200">
            <span class="text-3xl">{{ info.emoji }}</span>
            <span class="mt-1 text-[11px] text-stone-600">{{ info.label }}</span>
          </div>
        </label>
        {% endfor %}
      </div>
    </div>

    <div>
      <span class="label">อารมณ์ที่เกิดขึ้น</span>
      <div class="flex flex-wrap gap-2">
        {% for t in mood_types %}
        <label class="cursor-pointer">
          <input type="radio" name="mood_type" value="{{ t }}" class="mood-type peer sr-only" {% if loop.first %}checked{% endif %}>
          <span class="inline-block rounded-full border border-stone-300 bg-white px-3 py-1 text-sm text-stone-700 transition hover:bg-stone-50 peer-checked:border-amber-500 peer-checked:bg-amber-500 peer-checked:text-white">{{ t }}</span>
        </label>
        {% endfor %}
      </div>
      <div class="mt-3 rounded-2xl bg-amber-50 p-3 ring-1 ring-amber-100">
        <p class="text-xs font-semibold text-amber-800">👋 ทักอารมณ์ว่า…</p>
        <ul id="tak-lines" class="mt-1 space-y-0.5 text-sm text-stone-700"></ul>
      </div>
    </div>

    <div><label class="label" for="cause">เหตุที่ทำให้อารมณ์เกิด</label>
      <textarea class="input" id="cause" name="cause" rows="2" placeholder="เช่น ได้ยินคำพูดที่ไม่ถูกใจ, ได้ทำสิ่งที่ชอบ"></textarea></div>

    <div>
      <span class="label">จับอารมณ์ลงขันธ์ <span class="font-normal text-stone-400">(เลือกได้หลายข้อ)</span></span>
      <div class="flex flex-wrap gap-2">
        {% for k in khandhas %}
        <label class="cursor-pointer">
          <input type="checkbox" name="khandha" value="{{ k }}" class="peer sr-only">
          <span class="inline-block rounded-full border border-stone-300 bg-white px-3 py-1 text-sm text-stone-700 transition hover:bg-stone-50 peer-checked:border-sky-600 peer-checked:bg-sky-600 peer-checked:text-white">{{ k }}ขันธ์</span>
        </label>
        {% endfor %}
      </div>
    </div>
    <div><label class="label" for="observe">ดูขันธ์ 5 เกิด–ดับ</label>
      <textarea class="input" id="observe" name="observe" rows="2" placeholder="เฝ้าดูอารมณ์โดยไม่ต้องทำอะไรกับอารมณ์ จนเห็นอารมณ์นั้นดับลงไปเอง"></textarea></div>

    <div>
      <label class="label" for="note">พิจารณาขันธ์ 5 ลงอริยสัจ 4</label>
      <ul id="ariya-lines" class="mb-2 space-y-1 rounded-2xl bg-emerald-50 p-3 text-sm text-stone-700 ring-1 ring-emerald-100"></ul>
      <textarea class="input" id="note" name="note" rows="3" placeholder="บันทึกสิ่งที่พิจารณาเห็น"></textarea>
    </div>

    <button class="btn-primary w-full" type="submit">บันทึกอารมณ์</button>
  </form>

  <div class="space-y-6 lg:col-span-3">
    {% if dist %}
    <div class="card">
      <h2 class="font-bold">อารมณ์ที่พบบ่อยใน 30 วัน</h2>
      <div class="mt-3 space-y-2">
        {% for r in dist %}
        <div class="grid grid-cols-[5rem_1fr_2rem] items-center gap-3 text-sm">
          <span class="text-stone-600">{{ r.mood_type }}</span>
          <div class="h-2.5 overflow-hidden rounded-full bg-stone-100">
            <div class="h-full rounded-full bg-amber-400" style="width: {{ (r.n / dist_max * 100)|round|int }}%"></div>
          </div>
          <span class="text-right text-stone-500">{{ r.n }}</span>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    <div class="card">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <h2 class="font-bold">{% if filter_date %}บันทึกวันที่ {{ filter_date|thai_date }}{% else %}บันทึกล่าสุด{% endif %}</h2>
        <form method="get" class="flex items-center gap-2">
          <input class="input py-1.5 text-sm" type="date" name="date" value="{{ filter_date }}" onchange="this.form.submit()">
          {% if filter_date %}<a href="{{ url_for('mood') }}" class="btn-ghost py-1.5 text-sm">ทั้งหมด</a>{% endif %}
        </form>
      </div>

      <div class="mt-4 space-y-3">
        {% for e in entries %}
        <article class="rounded-2xl border border-stone-200 bg-white p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <span class="text-4xl">{{ mood_levels[e.level].emoji }}</span>
              <div>
                <p class="font-semibold">{{ e.mood_type }}
                  <span class="ml-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs font-normal text-stone-600">{{ mood_levels[e.level].label }}</span></p>
                <p class="text-sm text-stone-500">วัน{{ e.entry_date|thai_weekday }} {{ e.entry_date|thai_date }} · {{ e.entry_time }} น.</p>
              </div>
            </div>
            <form method="post" action="{{ url_for('mood_delete', entry_id=e.id) }}" onsubmit="return confirm('ต้องการลบบันทึกนี้ใช่ไหม?')">
              <button class="rounded-lg px-2 py-1 text-sm text-stone-400 hover:bg-rose-50 hover:text-rose-600" title="ลบ">🗑️</button>
            </form>
          </div>
          {% if e.khandha %}
          <div class="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
            <span class="font-semibold text-sky-700">ขันธ์:</span>
            {% for k in e.khandha.split(',') %}<span class="rounded-full bg-sky-100 px-2 py-0.5 text-sky-800">{{ k }}ขันธ์</span>{% endfor %}
          </div>
          {% endif %}
          {% if e.cause or e.observe or e.note %}
          <dl class="mt-3 space-y-2 text-sm">
            {% if e.cause %}<div><dt class="text-xs font-semibold text-amber-700">เหตุที่เกิด</dt><dd class="whitespace-pre-line text-stone-700">{{ e.cause }}</dd></div>{% endif %}
            {% if e.observe %}<div><dt class="text-xs font-semibold text-sky-700">ขันธ์ 5 เกิด–ดับ</dt><dd class="whitespace-pre-line text-stone-700">{{ e.observe }}</dd></div>{% endif %}
            {% if e.note %}<div><dt class="text-xs font-semibold text-emerald-700">อริยสัจ 4</dt><dd class="whitespace-pre-line text-stone-700">{{ e.note }}</dd></div>{% endif %}
          </dl>
          {% endif %}
        </article>
        {% else %}
        <p class="rounded-2xl bg-stone-50 p-8 text-center text-stone-500">ยังไม่มีบันทึก{% if filter_date %}ในวันนี้{% endif %}</p>
        {% endfor %}
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
(() => {
  const radios = document.querySelectorAll('.mood-type');
  const tak = document.getElementById('tak-lines');
  const ariya = document.getElementById('ariya-lines');

  function fill(el, lines) {
    el.replaceChildren(...lines.map((text) => {
      const li = document.createElement('li');
      li.textContent = text;
      return li;
    }));
  }

  function update() {
    const checked = document.querySelector('.mood-type:checked');
    const t = checked ? checked.value : 'อื่นๆ';
    const n = t === 'อื่นๆ' ? 'อารมณ์นี้' : 'ความ' + t;
    fill(tak, [
      `นี่คือ “${n}”`,
      `“${n}” กำลังเกิดขึ้นกับจิต`,
      `จิตกำลังมี “${n}”`,
      `“${n}” กำลังปรุงแต่งจิต`,
      `จิตกำลังถูก “${n}” ปรุงแต่ง`,
    ]);
    fill(ariya, [
      `ทุกข์ — ${n}ที่อาศัยขันธ์ ๕ เกิด`,
      `สมุทัย — ตัณหาที่เกิดร่วมกับ${n}`,
      `นิโรธ — ความดับไปของตัณหาพร้อมกับ${n}`,
      `มรรค — การกำหนดรู้ความเกิดความดับของ${n}พร้อมกับตัณหา`,
    ]);
  }

  radios.forEach((r) => r.addEventListener('change', update));
  update();
})();
</script>
{% endblock %}
"""

WALK_HTML = """{% extends "base.html" %}
{% block title %}เดินจงกรม{% endblock %}
{% block content %}
<div class="mb-6">
  <h1 class="text-2xl font-bold sm:text-3xl">👣 เดินจงกรม</h1>
  <p class="mt-1 text-stone-600">ตั้งเวลา เลือกสิ่งที่จะพิจารณา แล้วเดินอย่างมีสติ</p>
</div>

<section class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
  <div class="card"><p class="text-sm text-stone-500">วันนี้</p><p class="mt-1 text-2xl font-bold text-emerald-700">{{ stats.today }} <span class="text-sm font-medium">นาที</span></p></div>
  <div class="card"><p class="text-sm text-stone-500">7 วันล่าสุด</p><p class="mt-1 text-2xl font-bold text-emerald-700">{{ stats.week }} <span class="text-sm font-medium">นาที</span></p></div>
  <div class="card"><p class="text-sm text-stone-500">สะสมทั้งหมด</p><p class="mt-1 text-2xl font-bold text-emerald-700">{{ stats.total }} <span class="text-sm font-medium">นาที</span></p></div>
  <div class="card"><p class="text-sm text-stone-500">จำนวนครั้ง</p><p class="mt-1 text-2xl font-bold text-emerald-700">{{ stats.sessions }} <span class="text-sm font-medium">ครั้ง</span></p></div>
</section>

<div class="mt-6 grid gap-6 lg:grid-cols-5">
  <div class="space-y-6 lg:col-span-2">
    <!-- Timer -->
    <div class="card bg-gradient-to-br from-emerald-50 to-white">
      <h2 class="font-bold">⏱️ ตัวจับเวลา</h2>
      <div class="mt-4 flex flex-wrap gap-2">
        {% for m in [10, 15, 20, 30, 45, 60] %}
        <button type="button" data-min="{{ m }}" class="preset rounded-full border border-emerald-200 bg-white px-3 py-1 text-sm text-emerald-800 hover:bg-emerald-50">{{ m }} นาที</button>
        {% endfor %}
      </div>
      <div class="relative mx-auto mt-5 grid h-56 w-56 place-items-center">
        <svg class="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="45" fill="none" stroke="#e7e5e4" stroke-width="5"></circle>
          <circle id="ring" cx="50" cy="50" r="45" fill="none" stroke="#059669" stroke-width="5" stroke-linecap="round"
                  stroke-dasharray="282.74" stroke-dashoffset="0" style="transition: stroke-dashoffset .5s linear"></circle>
        </svg>
        <div class="text-center">
          <div id="display" class="font-mono text-5xl font-bold tabular-nums text-stone-800">15:00</div>
          <div id="status" class="mt-1 text-sm text-stone-500">พร้อมเริ่ม</div>
        </div>
      </div>
      <div class="mt-4">
        <label class="label" for="timer-step">พิจารณาขั้นตอนใดขณะเดิน</label>
        <select id="timer-step" class="input">
          <option value="0">— ไม่ระบุ —</option>
          {% for s in steps %}<option value="{{ s.no }}">{{ s.no }}. {{ s.title }}</option>{% endfor %}
        </select>
        <p id="step-summary" class="mt-2 hidden rounded-xl bg-white px-3 py-2 text-sm text-emerald-900 ring-1 ring-emerald-100"></p>
      </div>
      <div class="mt-4 grid grid-cols-3 gap-2">
        <button type="button" id="btn-start" class="btn-green">▶ เริ่ม</button>
        <button type="button" id="btn-pause" class="btn-ghost" disabled>⏸ พัก</button>
        <button type="button" id="btn-reset" class="btn-ghost">↺ รีเซ็ต</button>
      </div>
      <button type="button" id="btn-use" class="mt-2 w-full text-sm text-emerald-700 hover:underline">ใช้เวลาที่เดินไปแล้วกรอกลงฟอร์ม ↓</button>
    </div>

    <!-- Form -->
    <form method="post" class="card space-y-4" id="walk-form">
      <h2 class="font-bold">บันทึกการเดินจงกรม</h2>
      <div class="grid grid-cols-2 gap-3">
        <div><label class="label" for="w-date">วันที่</label>
          <input class="input" type="date" id="w-date" name="entry_date" value="{{ today }}" max="{{ today }}" required></div>
        <div><label class="label" for="w-min">เวลา (นาที)</label>
          <input class="input" type="number" id="w-min" name="minutes" min="1" max="600" value="15" required></div>
      </div>
      <div class="grid grid-cols-3 gap-3">
        <div class="col-span-2"><label class="label" for="w-step">พิจารณาขั้นตอน</label>
          <select class="input" id="w-step" name="step">
            <option value="0">— ไม่ระบุ —</option>
            {% for s in steps %}<option value="{{ s.no }}">{{ s.no }}. {{ s.title }}</option>{% endfor %}
          </select></div>
        <div><label class="label" for="w-rounds">รอบ</label>
          <input class="input" type="number" id="w-rounds" name="rounds" min="0" value="0"></div>
      </div>
      <div><label class="label" for="w-topic">พิจารณาเรื่องใดขณะเดิน</label>
        <textarea class="input" id="w-topic" name="topic" rows="2" placeholder="เช่น พิจารณาความโกรธเมื่อเช้าลงขันธ์ 5, ท่องธาตุ 4 ทุกย่างก้าว"></textarea></div>
      <div><label class="label" for="w-note">สภาวะที่พบ</label>
        <textarea class="input" id="w-note" name="note" rows="2" placeholder="เช่น ใจฟุ้งซ่านช่วงแรก แล้วค่อยๆ สงบลง"></textarea></div>
      <button class="btn-green w-full" type="submit">บันทึก</button>
    </form>
  </div>

  <div class="space-y-6 lg:col-span-3">
    <div class="card">
      <h2 class="font-bold">การพิจารณาขณะเดิน ตาม 7 ขั้นตอน</h2>
      <ol class="mt-3 divide-y divide-stone-100">
        {% for s in steps %}
        {% set st = step_stats.get(s.no) %}
        <li class="flex items-center gap-3 py-2.5">
          <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-800">{{ s.no }}</span>
          <a href="{{ url_for('practice') }}#step-{{ s.no }}" class="flex-1 text-stone-700 hover:text-emerald-700">{{ s.icon }} {{ s.title }}</a>
          <span class="shrink-0 text-xs {% if st %}text-emerald-700{% else %}text-stone-400{% endif %}">
            {% if st %}{{ st.n }} ครั้ง · {{ st.total }} นาที{% else %}ยังไม่ได้พิจารณา{% endif %}
          </span>
        </li>
        {% endfor %}
      </ol>
    </div>

    <div class="card">
      <h2 class="font-bold">ประวัติการเดินจงกรม</h2>
      <div class="mt-3 space-y-2">
        {% for s in sessions %}
        <div class="flex items-start justify-between gap-3 rounded-2xl border border-stone-200 p-3">
          <div class="flex min-w-0 gap-3">
            <div class="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-emerald-600 text-white">
              <span class="text-center text-sm font-bold leading-none">{{ s.minutes }}<br><span class="text-[10px] font-normal">นาที</span></span>
            </div>
            <div class="min-w-0">
              <p class="font-semibold">
                {% if s.step %}ขั้นที่ {{ s.step }} · {{ steps[s.step - 1].title }}{% else %}เดินจงกรม{% endif %}
                {% if s.rounds %}<span class="font-normal text-stone-500">· {{ s.rounds }} รอบ</span>{% endif %}
              </p>
              <p class="text-sm text-stone-500">วัน{{ s.entry_date|thai_weekday }} {{ s.entry_date|thai_date }}</p>
              {% if s.topic %}<p class="mt-1 whitespace-pre-line text-sm text-stone-700"><span class="font-medium text-emerald-700">พิจารณา:</span> {{ s.topic }}</p>{% endif %}
              {% if s.note %}<p class="mt-1 whitespace-pre-line text-sm text-stone-600"><span class="font-medium text-stone-500">สภาวะ:</span> {{ s.note }}</p>{% endif %}
            </div>
          </div>
          <form method="post" action="{{ url_for('walk_delete', entry_id=s.id) }}" onsubmit="return confirm('ต้องการลบบันทึกนี้ใช่ไหม?')">
            <button class="rounded-lg px-2 py-1 text-sm text-stone-400 hover:bg-rose-50 hover:text-rose-600" title="ลบ">🗑️</button>
          </form>
        </div>
        {% else %}
        <p class="rounded-2xl bg-stone-50 p-8 text-center text-stone-500">ยังไม่มีประวัติ เริ่มเดินจงกรมครั้งแรกกันเลย</p>
        {% endfor %}
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
(() => {
  const STEPS = {{ step_brief|tojson }};
  const CIRC = 282.74;
  const $ = (id) => document.getElementById(id);
  const display = $('display'), status = $('status'), ring = $('ring');
  const btnStart = $('btn-start'), btnPause = $('btn-pause'), btnReset = $('btn-reset');
  const stepSel = $('timer-step'), stepSummary = $('step-summary');

  let total = 15 * 60, remaining = total, endAt = null, tick = null;

  const fmt = (s) => String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
  function render() {
    display.textContent = fmt(Math.max(0, Math.ceil(remaining)));
    ring.style.strokeDashoffset = CIRC * (1 - remaining / total);
  }
  function showStep() {
    const s = STEPS.find((x) => String(x.no) === stepSel.value);
    stepSummary.textContent = s ? s.summary : '';
    stepSummary.classList.toggle('hidden', !s);
  }

  function bell() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [0, 1.6, 3.2].forEach((t) => {
        const o = ctx.createOscillator(), gain = ctx.createGain();
        o.type = 'sine'; o.frequency.value = 528;
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + t);
        gain.gain.exponentialRampToValueAtTime(0.4, ctx.currentTime + t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 1.5);
        o.connect(gain).connect(ctx.destination);
        o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 1.6);
      });
    } catch (e) {}
  }

  function fillForm(minutes) {
    $('w-min').value = Math.max(1, minutes);
    $('w-step').value = stepSel.value;
    $('walk-form').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function stop() { clearInterval(tick); tick = null; endAt = null; }

  function start() {
    if (remaining <= 0) remaining = total;
    endAt = Date.now() + remaining * 1000;
    tick = setInterval(() => {
      remaining = (endAt - Date.now()) / 1000;
      if (remaining <= 0) {
        remaining = 0; stop(); render();
        status.textContent = 'ครบเวลาแล้ว สาธุ 🙏';
        btnStart.disabled = false; btnPause.disabled = true;
        bell(); fillForm(Math.round(total / 60));
        return;
      }
      render();
    }, 250);
    status.textContent = 'กำลังเดินจงกรม…';
    btnStart.disabled = true; btnPause.disabled = false;
  }

  function pause() {
    stop();
    status.textContent = 'พักอยู่';
    btnStart.disabled = false; btnPause.disabled = true;
    btnStart.textContent = '▶ ต่อ';
  }

  function reset() {
    stop(); remaining = total; render();
    status.textContent = 'พร้อมเริ่ม';
    btnStart.disabled = false; btnPause.disabled = true;
    btnStart.textContent = '▶ เริ่ม';
  }

  document.querySelectorAll('.preset').forEach((b) => b.addEventListener('click', () => {
    total = parseInt(b.dataset.min, 10) * 60; reset();
    document.querySelectorAll('.preset').forEach((x) => x.classList.remove('bg-emerald-600', 'text-white'));
    b.classList.add('bg-emerald-600', 'text-white');
  }));

  btnStart.addEventListener('click', start);
  btnPause.addEventListener('click', pause);
  btnReset.addEventListener('click', reset);
  $('btn-use').addEventListener('click', () => fillForm(Math.round((total - remaining) / 60)));
  stepSel.addEventListener('change', showStep);

  showStep(); render();
})();
</script>
{% endblock %}
"""

PRACTICE_HTML = """{% extends "base.html" %}
{% block title %}ธรรมนาวา 7 ขั้นตอน{% endblock %}
{% block content %}
<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold sm:text-3xl">📿 หลักธรรมนาวา “วัง” 7 ขั้นตอน</h1>
    <p class="mt-1 text-stone-600">ติ๊กขั้นตอนที่ปฏิบัติแล้วในแต่ละวัน · กด “อ่านรายละเอียด” เพื่อดูวิธีปฏิบัติ</p>
  </div>
  <div class="flex items-center gap-2">
    <a href="{{ url_for('practice', date=prev_date) }}" class="btn-ghost px-3" title="วันก่อนหน้า">‹</a>
    <form method="get"><input class="input" type="date" name="date" value="{{ cur_date }}" onchange="this.form.submit()"></form>
    {% if cur_date < today %}<a href="{{ url_for('practice', date=next_date) }}" class="btn-ghost px-3" title="วันถัดไป">›</a>{% endif %}
  </div>
</div>

<div class="mt-6 grid gap-6 lg:grid-cols-3">
  <form method="post" class="space-y-4 lg:col-span-2">
    <input type="hidden" name="entry_date" value="{{ cur_date }}">

    <div class="card sticky top-[4.5rem] z-20 sm:top-20">
      <div class="flex items-center justify-between gap-3 text-sm">
        <span class="font-semibold">วัน{{ cur_date|thai_weekday }}ที่ {{ cur_date|thai_date }}</span>
        <span class="flex items-center gap-3">
          <button type="button" id="toggle-all" class="text-xs font-medium text-amber-700 hover:underline">เปิดรายละเอียดทั้งหมด</button>
          <span><span id="done-count" class="text-lg font-bold text-amber-700">{{ done|length }}</span> / 7</span>
        </span>
      </div>
      <div class="mt-2 h-3 overflow-hidden rounded-full bg-stone-100">
        <div id="progress" class="h-full rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-emerald-500 transition-all duration-500" style="width: {{ (done|length / 7 * 100)|round|int }}%"></div>
      </div>
    </div>

    {% for s in steps %}
    <div id="step-{{ s.no }}" class="card step-card scroll-mt-40 transition {% if s.no in done %}ring-2 ring-emerald-300{% endif %}">
      <label class="flex cursor-pointer items-start gap-4">
        <input type="checkbox" name="steps" value="{{ s.no }}" class="step-cb mt-1.5 h-5 w-5 shrink-0 cursor-pointer accent-emerald-600" {% if s.no in done %}checked{% endif %}>
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-amber-100 text-sm font-bold text-amber-800">{{ s.no }}</span>
            <h2 class="text-lg font-bold">{{ s.icon }} {{ s.title }}</h2>
          </div>
          <p class="mt-2 leading-relaxed text-stone-600">{{ s.summary }}</p>
        </div>
      </label>

      {% if s.no in (2, 6, 7) %}
        <p class="ml-9 mt-3 text-sm text-sky-800">📝 วันนี้บันทึกอารมณ์แล้ว <b>{{ mood_count }}</b> ครั้ง</p>
      {% endif %}

      <details class="step-details ml-9 mt-3">
        <summary class="cursor-pointer select-none text-sm font-medium text-amber-700 hover:underline">อ่านรายละเอียด{% if s.memorize %} / ฝึกท่อง{% endif %}</summary>
        <div class="mt-3 space-y-4 text-[15px] leading-relaxed text-stone-700">
          {% for b in s.blocks %}
            {% if b.type == 'p' %}
              <p>{{ b.text }}</p>

            {% elif b.type == 'chant' %}
              <div class="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/60 p-4 text-center">
                {% for pali, meaning in b.lines %}
                <div>
                  <p class="text-xl font-semibold text-stone-800">{{ pali }}</p>
                  <p class="text-sm text-stone-600">({{ meaning }})</p>
                </div>
                {% endfor %}
              </div>

            {% elif b.type == 'recite' %}
              <div class="recite rounded-2xl border border-sky-200 bg-sky-50/60 p-4">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-sm font-semibold text-sky-800">{{ b.title }}</p>
                  {% if b.memorize %}
                  <button type="button" class="memo-toggle rounded-full bg-white px-3 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200 hover:bg-sky-100">🙈 ซ่อนข้อความเพื่อฝึกท่อง</button>
                  {% endif %}
                </div>
                <div class="mt-2 space-y-2">
                  {% for line in b.lines %}<p class="memo-line rounded-lg transition">{{ line }}</p>{% endfor %}
                </div>
              </div>

            {% elif b.type == 'stages' %}
              <ol class="space-y-3">
                {% for title, text in b.rows %}
                <li class="flex gap-3">
                  <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-stone-700 text-sm font-bold text-white">{{ loop.index }}</span>
                  <div><p class="font-semibold text-stone-800">{{ title }}</p><p>{{ text }}</p></div>
                </li>
                {% endfor %}
              </ol>

            {% elif b.type == 'terms' %}
              <dl class="divide-y divide-stone-100 rounded-2xl border border-stone-200 bg-white">
                {% for term, text in b.rows %}
                <div class="grid gap-1 p-3 sm:grid-cols-[5.5rem_1fr]">
                  <dt class="font-semibold text-amber-800">{{ term }}</dt><dd>{{ text }}</dd>
                </div>
                {% endfor %}
              </dl>

            {% elif b.type == 'map' %}
              <div class="space-y-2">
                {% for left, right in b.rows %}
                <div class="flex flex-col gap-1 rounded-xl bg-stone-50 p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                  <span>{{ left }}</span>
                  <span class="shrink-0 text-sm"><span class="text-stone-400">จัดเป็น</span>
                    <span class="ml-1 rounded-full bg-emerald-100 px-2.5 py-0.5 font-semibold text-emerald-800">{{ right }}</span></span>
                </div>
                {% endfor %}
              </div>

            {% elif b.type == 'bullets' %}
              <ul class="space-y-1.5">
                {% for line in b.lines %}<li class="flex gap-2"><span class="text-amber-500">•</span><span>{{ line }}</span></li>{% endfor %}
              </ul>

            {% elif b.type == 'quote' %}
              <blockquote class="rounded-2xl border-l-4 border-amber-400 bg-amber-50 p-4 text-center text-lg font-medium text-stone-800">
                {% for line in b.lines %}<p>{{ line }}</p>{% endfor %}
              </blockquote>
            {% endif %}
          {% endfor %}

          {% if s.link %}
          <a href="{{ url_for(s.link[0]) }}" class="inline-block text-sm font-medium text-emerald-700 hover:underline">{{ s.link[1] }} →</a>
          {% endif %}
        </div>
      </details>
    </div>
    {% endfor %}

    <div class="card">
      <label class="label" for="reflection">สิ่งที่ได้พิจารณา / ความเข้าใจที่เกิดขึ้นวันนี้</label>
      <textarea class="input" id="reflection" name="reflection" rows="4" placeholder="เช่น เห็นความโกรธเกิดขึ้นแล้วดับไป เห็นขันธ์ ๕ ดับพร้อมกับอารมณ์">{{ reflection }}</textarea>
      <button class="btn-primary mt-4 w-full" type="submit">💾 บันทึกการปฏิบัติ</button>
    </div>
  </form>

  <aside class="space-y-6">
    <div class="card lg:sticky lg:top-24">
      <div class="mb-5 grid grid-cols-2 gap-2 text-center">
        <a href="{{ url_for('mood') }}" class="rounded-2xl bg-sky-50 p-3 hover:bg-sky-100">
          <p class="text-2xl font-bold text-sky-700">{{ mood_count }}</p><p class="text-xs text-stone-600">📝 บันทึกอารมณ์</p></a>
        <a href="{{ url_for('walk') }}" class="rounded-2xl bg-emerald-50 p-3 hover:bg-emerald-100">
          <p class="text-2xl font-bold text-emerald-700">{{ walk_minutes }}</p><p class="text-xs text-stone-600">👣 นาทีเดินจงกรม</p></a>
      </div>
      <h2 class="font-bold">14 วันล่าสุด</h2>
      <div class="mt-3 grid grid-cols-7 gap-2">
        {% for d, n in history %}
        {% set shade = 'bg-stone-100 text-stone-400' if n == 0 else ('bg-amber-200 text-amber-900' if n < 4 else ('bg-amber-400 text-white' if n < 7 else 'bg-emerald-500 text-white')) %}
        <a href="{{ url_for('practice', date=d) }}" title="{{ d|thai_date }} · {{ n }}/7"
           class="grid aspect-square place-items-center rounded-xl text-xs font-semibold {{ shade }} {% if d == cur_date %}ring-2 ring-stone-800 ring-offset-1{% endif %}">
          {{ d[8:]|int }}
        </a>
        {% endfor %}
      </div>
      <div class="mt-3 flex flex-wrap gap-3 text-xs text-stone-500">
        <span class="flex items-center gap-1"><span class="h-3 w-3 rounded bg-stone-100"></span>0</span>
        <span class="flex items-center gap-1"><span class="h-3 w-3 rounded bg-amber-200"></span>1–3</span>
        <span class="flex items-center gap-1"><span class="h-3 w-3 rounded bg-amber-400"></span>4–6</span>
        <span class="flex items-center gap-1"><span class="h-3 w-3 rounded bg-emerald-500"></span>ครบ 7</span>
      </div>

      <div class="mt-5 rounded-2xl bg-gradient-to-br from-amber-50 to-emerald-50 p-4 text-sm leading-relaxed text-stone-700">
        <p class="font-semibold">ลำดับการปฏิบัติ</p>
        <ol class="mt-1 space-y-0.5">
          {% for s in steps %}<li><a href="#step-{{ s.no }}" class="hover:text-amber-700">{{ s.no }}. {{ s.title }}</a></li>{% endfor %}
        </ol>
      </div>
    </div>
  </aside>
</div>
{% endblock %}

{% block scripts %}
<script>
(() => {
  const boxes = document.querySelectorAll('.step-cb');
  function update() {
    const n = [...boxes].filter((b) => b.checked).length;
    document.getElementById('done-count').textContent = n;
    document.getElementById('progress').style.width = (n / 7 * 100) + '%';
    boxes.forEach((b) => {
      const card = b.closest('.step-card');
      card.classList.toggle('ring-2', b.checked);
      card.classList.toggle('ring-emerald-300', b.checked);
    });
  }
  boxes.forEach((b) => b.addEventListener('change', update));

  // เปิด/ปิดรายละเอียดทั้งหมด
  const toggleAll = document.getElementById('toggle-all');
  toggleAll.addEventListener('click', () => {
    const details = document.querySelectorAll('.step-details');
    const open = ![...details].every((d) => d.open);
    details.forEach((d) => { d.open = open; });
    toggleAll.textContent = open ? 'ปิดรายละเอียดทั้งหมด' : 'เปิดรายละเอียดทั้งหมด';
  });

  // เปิดรายละเอียดของขั้นตอนที่ลิงก์มา (#step-N)
  const target = location.hash && document.querySelector(location.hash + ' .step-details');
  if (target) target.open = true;

  // โหมดฝึกท่อง: ซ่อนข้อความ แล้วแตะทีละย่อหน้าเพื่อเฉลย
  const HIDDEN = ['blur-sm', 'select-none', 'cursor-pointer', 'bg-sky-100'];
  document.querySelectorAll('.memo-toggle').forEach((btn) => {
    const lines = btn.closest('.recite').querySelectorAll('.memo-line');
    btn.addEventListener('click', () => {
      const hide = btn.dataset.hidden !== '1';
      btn.dataset.hidden = hide ? '1' : '0';
      lines.forEach((l) => HIDDEN.forEach((c) => l.classList.toggle(c, hide)));
      btn.textContent = hide ? '👀 แสดงข้อความทั้งหมด' : '🙈 ซ่อนข้อความเพื่อฝึกท่อง';
    });
    lines.forEach((l) => l.addEventListener('click', () => HIDDEN.forEach((c) => l.classList.remove(c))));
  });
})();
</script>
{% endblock %}
"""

app.jinja_loader = DictLoader({
    "base.html": BASE_HTML,
    "dashboard.html": DASHBOARD_HTML,
    "mood.html": MOOD_HTML,
    "walk.html": WALK_HTML,
    "practice.html": PRACTICE_HTML,
})

init_db()

if __name__ == "__main__":
    app.run(debug=True)
