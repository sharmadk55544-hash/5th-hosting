#CREDIT - @CXXWIO
#MAIN CHANNEL - DK HOSTING BOT #

import os
import re
import sys
import time
import json
import zipfile
import subprocess
import shutil
import threading
import html
import functools
import psutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ============================================================
# BOT CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

STORAGE_DIR = os.getenv("STORAGE_DIR", "user_files")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uplo556ads")
DATA_FILE = os.path.join(STORAGE_DIR, "users.json")

os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

# ============================================================
# GLOBALS
# ============================================================

users = {}

active_scripts = {}
logs_store = {}

# Global re-entrant lock protecting users / active_scripts / logs_store
STATE_LOCK = threading.RLock()

# One lock per (user, script) so two starts never race each other
SCRIPT_LOCKS = {}


def locked(fn):
    """Run the wrapped function while holding STATE_LOCK."""

    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):

        with STATE_LOCK:
            return fn(*args, **kwargs)

    return wrapper


install_waiting_users = {}
env_waiting_users = {}

bot_start_time = time.time()
START_TIME = datetime.now()

RECOMMENDED_PACKAGES = [
    "pip",
    "setuptools",
    "wheel",
    "requests",
    "numpy",
    "pandas",
    "flask",
    "aiohttp",
    "pyrogram",
    "python-dotenv",
    "beautifulsoup4",
    "lxml",
    "pillow",
    "matplotlib",
    "scipy",
    "scikit-learn",
    "pytest"
]

PYTG_CALLS_PACKAGE = "git+https://github.com/pytgcalls/pytgcalls.git"

# ============================================================
# PREMIUM EMOJI
# ============================================================

PREMIUM_EMOJI_IDS = [

    # Existing Premium Emojis
    "5289722755871162900",
    "5372849966689566579",
    "5359664288241829619",
    "5445033158456145975",
    "5445092669522996408",
    "5445358884480916784",
    "5445307250384075361",
    "5447602197439218445",
    "6147460667281511517",
    "6235459831302460476",
    "6244492465353529537",
    "6318817991102305543",

    # New Premium Emojis
    "5231200819986047254",
    "5944970130554359187",
    "6120548140211770562",
    "4987977590812705943",
    "5416081784641168838",
    "6321171873698681876",
    "5915556996215476302",
    "5877443460725739250",
    "4990298741463319592",
    "5462956611033117422",
    "6231214251835397322",
    "6282846669335702032",
    "5210952531676504517",
    "6129639980387015660",
]

PE_FIRE = PREMIUM_EMOJI_IDS[0]
PE_STAR = PREMIUM_EMOJI_IDS[1]
PE_ROCKET = PREMIUM_EMOJI_IDS[2]
PE_CROWN = PREMIUM_EMOJI_IDS[3]
PE_SHIELD = PREMIUM_EMOJI_IDS[4]
PE_MONEY = PREMIUM_EMOJI_IDS[5]
PE_PHONE = PREMIUM_EMOJI_IDS[6]
PE_CHECK = PREMIUM_EMOJI_IDS[7]
PE_CROSS = PREMIUM_EMOJI_IDS[8]
PE_WARNING = PREMIUM_EMOJI_IDS[9]
PE_LOCK = PREMIUM_EMOJI_IDS[10]
PE_GIFT = PREMIUM_EMOJI_IDS[11]

PE_APPROVE = PREMIUM_EMOJI_IDS[12]
PE_USER = PREMIUM_EMOJI_IDS[13]
PE_ADMIN = PREMIUM_EMOJI_IDS[14]
PE_UPLOAD = PREMIUM_EMOJI_IDS[15]
PE_FOLDER = PREMIUM_EMOJI_IDS[16]
PE_SETTINGS = PREMIUM_EMOJI_IDS[17]
PE_SERVER = PREMIUM_EMOJI_IDS[18]
PE_DIAMOND = PREMIUM_EMOJI_IDS[19]
PE_BOT = PREMIUM_EMOJI_IDS[20]


EMOJI_RUNTIME_DISABLED = {'v': False}   # set automatically if Telegram keeps rejecting custom emoji


def custom_emoji_enabled():
    """Premium emojis are ON by default. Only an explicit 0/false/no/off disables them."""
    if EMOJI_RUNTIME_DISABLED['v']:
        return False
    return os.getenv('ENABLE_CUSTOM_EMOJI', '1').strip().lower() not in ('0', 'false', 'no', 'off')


def pe(emoji_id, fallback="💎"):
    """
    Telegram custom premium emoji HTML (<tg-emoji>) with a normal-emoji fallback.
    """
    emoji_id = str(emoji_id).strip()
    if not emoji_id.isdigit() or not custom_emoji_enabled():
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# ---- Custom emoji IDs generated from emoji.json (12 packs, 612 unique emojis) ----
EMOJI_JSON_MAP = {
    "⭐": "5427086749278943412",
    "▶": "5341270334882463507",
    "💜": "5343584905643180151",
    "👣": "5368593404991127537",
    "📄": "5343597635926245720",
    "💨": "5343766389486272458",
    "🎙": "5343850098398871461",
    "🔇": "5343930942568283286",
    "😄": "5343635672156623047",
    "🏷": "5343863498696833806",
    "🎨": "5341665785406308254",
    "🖼": "5341285075210224047",
    "🙂": "5429437075642398048",
    "💬": "5368408034202632731",
    "📹": "5426894489362907268",
    "🔘": "5429555393401469575",
    "💤": "5429584229811896096",
    "🔄": "5429166458343011591",
    "🏪": "5431646131941556182",
    "🤖": "5431490770089560625",
    "⏳": "5431672893882778047",
    "📍": "5431626942027677918",
    "💼": "5431745143822632981",
    "🎥": "5431443461024791843",
    "⚡": "5427113717378595836",
    "🎁": "5426999892155318407",
    "🆕": "5400038655861466061",
    "🔑": "5229153645299245972",
    "🛡": "5229142972305515214",
    "🔒": "5231450353290976069",
    "🌃": "5429170023165867734",
    "☠": "5402479073458921106",
    "🎃": "5402405242971103041",
    "👻": "5402069969234043254",
    "🧟‍♂": "5400278770303114814",
    "🍪": "5231337984061612745",
    "❄": "5233528344368129429",
    "🎅": "5233588396600861264",
    "💰": "5431416651838932108",
    "🧭": "5818967150278218011",
    "✈": "5821043371828841290",
    "🧳": "5819087259038649860",
    "📸": "5818849313555483639",
    "🗺": "5818690584449126294",
    "🚃": "5819122456295641130",
    "🚌": "5821101929412955791",
    "⛰": "5818764548080930127",
    "🌐": "5819203420724137401",
    "🔔": "5818953372023131792",
    "🕹": "5821072212534233982",
    "⌨": "5818802717455290572",
    "📶": "5821276292200271408",
    "🔎": "5818687127000452892",
    "👮": "5818788359379620468",
    "👮‍♀": "5818678700274617758",
    "👩‍💻": "5818995853544656277",
    "🧑‍💻": "5819154994967874788",
    "👨‍💻": "5818813162815753343",
    "🚓": "5818727130325847330",
    "🚕": "5819098039406562961",
    "🆔": "5818885490065017876",
    "😊": "5819052779041197669",
    "⚙": "5818705028424141605",
    "🔐": "5821453562680448557",
    "📱": "5819099456745770209",
    "❕": "5818865088970362886",
    "🛂": "5818955300463447293",
    "❔": "5818947586702184246",
    "💻": "5818774589714468177",
    "🖌": "5819016409258135133",
    "🛄": "5818740513443942870",
    "⚫": "5818899491658403448",
    "⚪": "5819167635056627108",
    "🔵": "5821058666207382432",
    "🔴": "5818717642743090785",
    "🟢": "5818812952362356039",
    "🟡": "5819199598203244104",
    "👀": "5818845400840277279",
    "⏺": "5820914686018718964",
    "🗣": "5818751353941398485",
    "➕": "5818651538901437748",
    "✖": "5818804920773512716",
    "💫": "5819060814925008220",
    "☯": "5819005890883227245",
    "🎖": "5819146121565441618",
    "🟦": "5821238376228981917",
    "👤": "5818715087237549366",
    "📷": "5821087262099639879",
    "➗": "5821267302833720574",
    "🉐": "5821446132387023959",
    "☎": "5821410007417097865",
    "🕊": "5821081816081108141",
    "⏸": "5947029782121155470",
    "👮‍♂": "5854973145315806460",
    "⬆": "5866391659469606245",
    "🚀": "5868484743061834951",
    "🎬": "5866430606233046609",
    "🐤": "5866424082177723899",
    "🎰": "5866084676682125789",
    "🎼": "5866342164266486901",
    "🍏": "5866011417424957198",
    "🐥": "5866169914603081371",
    "🐩": "5866055402185035499",
    "👁": "5886667040432853038",
    "⚛": "5888605518087326713",
    "☔": "5888518794107687110",
    "✅": "5886355367541083626",
    "🌏": "5888675895421440226",
    "👎": "5888789252493283486",
    "♨": "5886324117359038886",
    "🌈": "5891237108974095799",
    "🏳‍🌈": "5890784857507761927",
    "❤": "5890765160787742493",
    "🔺": "5890942929484123460",
    "🟥": "5890710155141582641",
    "🎇": "5888999340818566791",
    "↗": "5891147709229830419",
    "✏": "5956143844457189176",
    "⏱": "5981043230160981261",
    "❣": "5980792215092333916",
    "🔓": "5981075141767990672",
    "⬇": "5979076319823007456",
    "🗑": "5979070714890686650",
    "🤝": "5978856151209480380",
    "🔈": "5981056518789794953",
    "👍": "5978637417115029380",
    "☝": "5978555237210787432",
    "🔊": "5980884380795539169",
    "❌": "5980953710157632545",
    "🚫": "5978714271259823413",
    "🇷🇺": "5981261427384520401",
    "🌟": "5981137088081301019",
    "💎": "5800688138833629633",
    "🤬": "5801003385138188414",
    "🧠": "5801027411185242471",
    "😮": "5798523741604419569",
    "📅": "5800810214689084012",
    "🎾": "5798459514663473705",
    "🔮": "5800735009811730616",
    "✨": "5800833282958430823",
    "👛": "5798937402789597866",
    "💵": "5800720664620961831",
    "🥂": "5803393311100113792",
    "👑": "5803032306213982905",
    "🔖": "5803151379887297481",
    "📣": "5803175856905917502",
    "📌": "5801018335919347111",
    "🐱": "5803403881014629353",
    "💯": "5803420575552508108",
    "🩷": "5800834464074438266",
    "🖕": "5803375925072499189",
    "🌚": "5802946896494334636",
    "🎄": "5802903921051571261",
    "🏅": "5803357151770449172",
    "💲": "5866146206383608554",
    "❓": "5886448503906899325",
    "✉": "5891268505185030578",
    "😯": "5888935788187490785",
    "📎": "5888584382553265934",
    "💥": "5888974760720732797",
    "🌿": "5891031465939964877",
    "🫊": "5891198677606732755",
    "🏿": "5891063600885273198",
    "🤮": "5890958576049984200",
    "🧛‍♂": "5890944411247841790",
    "💔": "5890772268958617745",
    "💕": "5888555619157285122",
    "🌀": "5913534466051021148",
    "♻": "5911100572508885928",
    "🕵": "5911522793563886333",
    "🔋": "5913513644049570217",
    "🪫": "5913614837774029701",
    "🍽": "5913264639025615311",
    "🇹🇷": "5913265296155611115",
    "💶": "5913391091452743449",
    "👜": "5926860096008098405",
    "☀": "5924629264224753123",
    "🛜": "5927284851093803771",
    "🍎": "5927042730902426764",
    "🟣": "5927197323955278457",
    "🌙": "5924764134787782252",
    "📋": "5926764846518376076",
    "⬛": "5924517114038719190",
    "✔": "5931760627923030124",
    "☑": "5931408616698416937",
    "🔥": "5931344368282636710",
    "💦": "5967560851077469602",
    "🚨": "5967317893367468926",
    "🎤": "5969607557612835024",
    "⌚": "5969545478155539601",
    "♾": "5967617883948192905",
    "🎮": "6008006717017690954",
    "⚠": "6008233706039284019",
    "💙": "5780496071645991525",
    "🪤": "5780922965625410989",
    "➖": "5789644639749281149",
    "5⃣": "5791772473921901213",
    "6⃣": "5789851558388700130",
    "🥰": "5789793808258437906",
    "🕶": "5789607097440147328",
    "💧": "5789876430544311548",
    "1⃣": "5800923472976679740",
    "2⃣": "5802912291942830882",
    "3⃣": "5801094885121463194",
    "4⃣": "5800901723262293755",
    "7⃣": "5801177052140803279",
    "8⃣": "5801170261797507837",
    "9⃣": "5800648479105618763",
    "🔍": "5803403369913520877",
    "🛸": "5800824143268025850",
    "🦁": "5803360604924154219",
    "🛒": "5803157955482227929",
    "🤩": "6084695058894819673",
    "❤‍🔥": "6089028758205897441",
    "🔝": "6086784182527202100",
    "💀": "6087162775304409688",
    "👹": "6086817820711064076",
    "😉": "6089024570612781324",
    "🚩": "6087060924449953862",
    "💭": "6086708148721160702",
    "☄": "6093377734715642495",
    "💠": "6093865234978574850",
    "🟿": "6093513636070822132",
    "➡": "6093852921307337895",
    "☃": "6093818260921258328",
    "📊": "6093382540784046658",
    "🏭": "6093596992796102377",
    "🖥": "6093875388281263010",
    "😀": "6093864814071780526",
    "😁": "6093425709500339144",
    "🥹": "6093835694193512831",
    "😢": "6093376514944929700",
    "😃": "6095627640448750533",
    "🧐": "6093710452947161299",
    "🥲": "6093467039970629408",
    "👏": "6093744967304352336",
    "😎": "6093639774965338848",
    "🏵": "6093584842333622858",
    "🤔": "6093666528316625608",
    "😒": "6093576514392037256",
    "🤣": "6093661404420641058",
    "🥺": "6093779241143374561",
    "🤗": "6095742874421301875",
    "🏝": "6093464720688288321",
    "🍴": "6093451264555750089",
    "⛔": "6093778090092139204",
    "👋": "6095851644468072524",
    "🕓": "6093456762113888541",
    "😂": "6093522689861882360",
    "🤨": "6093493892106162082",
    "😧": "6095888417978061469",
    "🤪": "6096026428162183499",
    "😍": "6093725459562893833",
    "😭": "6093930033150170743",
    "😏": "6093748819890018226",
    "🧧": "6246774261218810895",
    "🤙": "5780840497958360623",
    "😆": "5780413823022273797",
    "😱": "5783091623462180025",
    "😟": "5783151611270403662",
    "😾": "5783124312458270318",
    "😨": "5782753386197685582",
    "😼": "5783023329187206172",
    "🎈": "5782734256413349701",
    "😑": "5782876166427775766",
    "😝": "5782993191401689635",
    "😺": "5783154622042477033",
    "😸": "5782681033178617588",
    "🌸": "5782789524052513567",
    "🐶": "5780764734735259441",
    "💃": "5780636053220103355",
    "😔": "5782882973950940285",
    "🦶": "5782867877140895194",
    "🤞": "5782827367009359233",
    "🐈": "5783166815454630601",
    "🔨": "5783010354091005955",
    "🥡": "5783000136363807783",
    "😡": "5782833521697494295",
    "🌹": "5783036501851902672",
    "🫂": "5783182062588531009",
    "🟪": "5783019966227813296",
    "🤫": "5782961266909779599",
    "🙄": "5783066953170032069",
    "🐣": "5785100057543972225",
    "🤓": "5782848150356104237",
    "☺": "5785056124323500928",
    "◼": "5785181606088020813",
    "📨": "6010453886303737503",
    "📝": "6010292709066019210",
    "🕖": "6010415291727615186",
    "🔶": "6010071909092298592",
    "🔹": "6010352555140321877",
    "🔸": "6010479565913198652",
    "‼": "6010089965134811556",
    "❗": "6010323791744341519",
    "🛩": "6010061175969027500",
    "🆏": "6010080507616826629",
    "❤‍🩹": "6010209683053220363",
    "🕦": "6010153921492816021",
    "🧑": "6010482465016123577",
    "😇": "6010068610557417146",
    "😚": "6298544959486167081",
    "😥": "6298480869984175913",
    "👽": "6298566954013689358",
    "🐺": "6220014823963363136",
    "🐹": "6219810752887262728",
    "🐋": "6219882697884436514",
    "☜": "6219727185708582935",
    "😴": "6298513503145691368",
    "🔻": "6255512604110751681",
    "🆒": "6170120369274358018",
    "🥠": "6298540449770506365",
    "👩‍🚒": "6298452746538321740",
    "🇮🇳": "6138853050309150669",
    "🕺": "6105135237753210602",
    "0⃣": "6219488394116859803",
    "🫶": "6298454498884978957",
    "😘": "6298412927896520857",
    "🍄": "6102848541330249485",
    "💍": "6102796683895117675",
    "😤": "6034865170449175739",
    "🙁": "6035210301136182368",
    "😈": "6035136809950778133",
    "👿": "6032985916098750553",
    "👅": "6035374291577475270",
    "😠": "6035355642829475999",
    "😕": "6035072209347678547",
    "👒": "6033077437556855182",
    "💣": "6032673796530377389",
    "♋": "6032916496542339992",
    "☁": "6034832094906028632",
    "🩸": "6035343380697846690",
    "🪽": "6035194237958493530",
    "🫌": "6035317340311129897",
    "🗡": "6033067975743902590",
    "🆗": "4956649845952611245",
    "🚷": "4958472535583753086",
    "🪩": "4956247175588742152",
    "🧝": "4956582878822531899",
    "🔗": "4958689671950369798",
    "ℹ": "4958529074533238201",
    "🐦‍⬛": "4958830950604604428",
    "🪅": "4956614279328433146",
    "🤭": "4956252273714922652",
    "🌕": "4956273117191213833",
    "🚗": "4958801766301828295",
    "🦌": "4956761150030087025",
    "🍭": "4956555872068174842",
    "☕": "4956252540002894879",
    "🌲": "4956557431141303451",
    "🍨": "4956420821116519533",
    "🕷": "4958923223681991654",
    "🔽": "4956720180337050608",
    "🧤": "4956379112689107750",
    "🎀": "4956722293460960020",
    "©": "4956313992394966051",
    "🫐": "4958990289596318519",
    "🦄": "4956529835976426308",
    "🎩": "4956564307383944011",
    "⚰": "4958724224962265918",
    "🧦": "4958668411862254755",
    "🧹": "4956591954088428445",
    "🍲": "4958644823901864780",
    "🎉": "4956308456182121758",
    "🌛": "4958828150285927471",
    "🍃": "4956468890390496140",
    "🍑": "4956214684161147887",
    "🫦": "4956516272469705982",
    "⛸": "4958738711886955477",
    "💌": "4958503072801228000",
    "🪦": "4956214142995268150",
    "🔼": "4958790109760587106",
    "💋": "4956680567853679460",
    "🩶": "4956750494216225777",
    "🗳": "4956214413578207998",
    "📉": "4956552088201986883",
    "💐": "4956353063712457393",
    "🌺": "4956283708580563433",
    "🌩": "4956233646441760046",
    "🦋": "4958719848390591540",
    "😶‍💫": "4956500084737966923",
    "💡": "4958665796227171144",
    "💝": "4958839553424098323",
    "🎏": "4956499169909932961",
    "🧶": "4958558095627256768",
    "🎆": "4958488079070397388",
    "🪟": "4956494239287477123",
    "💩": "4956505651015582631",
    "🧩": "4958903389523018769",
    "🏡": "4958485609464202497",
    "📈": "4956599758044005301",
    "💖": "4958577444454925201",
    "🍰": "4958931508673905639",
    "🧸": "4956708038464504901",
    "👈": "4956304191279596468",
    "🦴": "4956357289960276851",
    "🧪": "4956561910792192697",
    "👼": "4958963647914181913",
    "🥳": "4956425077429109847",
    "🐸": "4956488741729338655",
    "🐈⬛": "4956598503913554822",
    "🍬": "4958563494401147639",
    "🔜": "4956507210088711059",
    "🎶": "4958562566688211974",
    "🏳": "5433754814855001814",
    "🇨🇳": "5433827537241258614",
    "🇿🇦": "5431855966863766753",
    "🇧🇷": "5431769908604056769",
    "🇳🇴": "5434147542369579483",
    "🇬🇧": "5435996255207567113",
    "🇦🇨": "5433636707549331311",
    "🇦🇫": "5433845881046578644",
    "🇦🇮": "5433627189901801019",
    "🇦🇱": "5433946537900128161",
    "🇦🇴": "5433750193470191473",
    "🇦🇷": "5433754239329383923",
    "🇦🇪": "5433804400252434985",
    "🇦🇺": "5431556723607352698",
    "🇦🇹": "5431640943621060829",
    "🇧🇾": "5431375858239550223",
    "🇧🇯": "5433682092468746953",
    "🇧🇩": "5433854239052935880",
    "🇧🇧": "5434027579638035690",
    "🇧🇪": "5431739800883312139",
    "🇧🇦": "5433598052843665552",
    "🇧🇼": "5431431529605642522",
    "🇧🇿": "5433838931789492934",
    "🇧🇲": "5433609855413794108",
    "🇧🇳": "5433991338703991663",
    "🇧🇱": "5433895109961725692",
    "🇧🇫": "5433789964867352475",
    "🇧🇹": "5431663303220804322",
    "🇨🇦": "5433666360003540231",
    "🇨🇩": "5433696429069580735",
    "🇨🇫": "5433774971136521802",
    "🇨🇬": "5433960238845802718",
    "🇨🇭": "5431865097964237519",
    "🇨🇮": "5431374711483282830",
    "🇨🇰": "5433825269498525925",
    "🇨🇱": "5431561302042488884",
    "🇨🇲": "5433630999537792332",
    "🇨🇴": "5431703839122141424",
    "🇨🇵": "5433861570562111275",
    "🇨🇷": "5431489619038320862",
    "🇨🇻": "5434096943359866241",
    "🇨🇼": "5433958877341169005",
    "🇨🇽": "5433708502222649633",
    "🇨🇾": "5433614889115464671",
    "🇨🇿": "5434140679011842196",
    "🇩🇪": "5431462560744353934",
    "🇩🇬": "5431619494554383246",
    "🇸🇻": "5434134189316257066",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿": "5431508997930758727",
    "🇪🇨": "5433723401464198287",
    "🇪🇪": "5433727662071755290",
    "🇪🇬": "5433804408842368654",
    "🇪🇷": "5434011361841525609",
    "🇪🇸": "5433640560134994324",
    "🇪🇹": "5431380440969654931",
    "🇪🇺": "5434067424049639550",
    "🇫🇮": "5433979415874779870",
    "🇫🇯": "5433982207603520017",
    "🇫🇰": "5433596974806873997",
    "🇫🇲": "5433814347396692144",
    "🇫🇴": "5431695798943363996",
    "🇫🇷": "5434041611296192616",
    "🇬🇦": "5433935894971168754",
    "🇬🇩": "5431676201007592926",
    "🇬🇪": "5434115081006756195",
    "🇬🇫": "5434072118448894385",
    "🇬🇬": "5434036689263670086",
    "🇬🇭": "5433628435442316429",
    "🇬🇮": "5433884376838454074",
    "🇬🇱": "5433882955204279044",
    "🇬🇲": "5433749102548496991",
    "🇬🇳": "5434155397864764491",
    "🇬🇵": "5433810168393511493",
    "🇬🇶": "5434067655977874913",
    "🇬🇷": "5433860784583096428",
    "🇬🇸": "5431626087329182684",
    "🇬🇹": "5433643519367461444",
    "🇬🇺": "5433755347430946164",
    "🇬🇼": "5433792670696748414",
    "🇬🇾": "5434004021742417775",
    "🇭🇳": "5433884162090088194",
    "🇭🇷": "5433820583689205435",
    "🇭🇹": "5433652375590025431",
    "🇭🇺": "5431785473565537213",
    "🇭🇰": "5433727778035872782",
    "🇮🇩": "5433872853441196535",
    "🇮🇪": "5431620340662940910",
    "🇮🇱": "5431414444225738871",
    "🇮🇲": "5433876972314836083",
    "🇮🇶": "5434119663736862995",
    "🇮🇷": "5431669247455540884",
    "🇮🇸": "5433626051735467592",
    "🇮🇹": "5433833485770964033",
    "🇯🇪": "5433773682646332733",
    "🇯🇲": "5433968339154122439",
    "🇯🇴": "5434150334098327966",
    "🇯🇵": "5434010919459894038",
    "🇰🇪": "5433943093336356065",
    "🇰🇬": "5433598722858562967",
    "🇰🇭": "5434130474169544969",
    "🇰🇮": "5433859405898594234",
    "🇰🇲": "5431519649449653173",
    "🇰🇳": "5434064563601421981",
    "🇰🇵": "5431428076451934112",
    "🇰🇷": "5433798752370439037",
    "🇰🇼": "5433674924168328689",
    "🇰🇾": "5434012796360604182",
    "🇰🇿": "5431656358258685474",
    "🇱🇦": "5434131139889478358",
    "🇱🇧": "5433895144321462723",
    "🇱🇨": "5434026158003862063",
    "🇱🇮": "5431350891594658893",
    "🇱🇰": "5433737613510981562",
    "🇱🇷": "5433836092816108548",
    "🇱🇸": "5434142701941437163",
    "🇱🇹": "5434057098948261250",
    "🇱🇺": "5433714227414054291",
    "🇱🇻": "5431434686406604479",
    "🇱🇾": "5433852121634060293",
    "🇲🇦": "5433776225266972326",
    "🇲🇨": "5433851438734259274",
    "🇲🇩": "5433972762970437003",
    "🇲🇪": "5433748668756802256",
    "🇲🇫": "5434098446598419585",
    "🇲🇬": "5433855712226718930",
    "🇲🇭": "5433920471743607048",
    "🇲🇰": "5431353614603926322",
    "🇲🇱": "5431394721735914525",
    "🇲🇲": "5433738201921500487",
    "🇲🇳": "5431484894574295376",
    "🇲🇴": "5433613703704490463",
    "🇲🇷": "5431830051031103147",
    "🇲🇸": "5434125517777286321",
    "🇲🇹": "5434001565021123877",
    "🇲🇺": "5431894290856949874",
    "🇲🇻": "5433721073591926542",
    "🇲🇼": "5433691077540330355",
    "🇲🇽": "5431588626624427422",
    "🇲🇾": "5433902785068283672",
    "🇲🇿": "5434129692485498098",
    "🇳🇦": "5433867115364889538",
    "🇳🇨": "5433785261878162812",
    "🇳🇪": "5431696408828720537",
    "🇳🇫": "5433711929606551683",
    "🇳🇬": "5434045605615777483",
    "🇳🇮": "5431755073787016798",
    "🇳🇱": "5431520783321019240",
    "🇳🇵": "5434132406904830055",
    "🇳🇷": "5434009493530752727",
    "🇳🇺": "5433910876786670092",
    "🇳🇿": "5434058864179822603",
    "🇴🇲": "5433834847275594263",
    "🇵🇦": "5434131504961696728",
    "🇵🇪": "5434029851675734900",
    "🇵🇫": "5434040911216522968",
    "🇵🇬": "5433629779767081651",
    "🇵🇭": "5433772127868172193",
    "🇵🇰": "5433640100573491806",
    "🇵🇱": "5433678179753538895",
    "🇵🇲": "5434152992683079729",
    "🇵🇳": "5431529734032865031",
    "🇵🇷": "5433684690923961019",
    "🇵🇸": "5433895436379240198",
    "🇵🇹": "5431788596006762529",
    "🇵🇼": "5434076031164103400",
    "🇵🇾": "5433852276252883640",
    "🇶🇦": "5433992296481700344",
    "🇷🇪": "5434153928985949656",
    "🇷🇴": "5434094173105960379",
    "🇷🇸": "5434009132753499322",
    "🇷🇼": "5434078960331796980",
    "🇼🇸": "5433735143904786332",
    "🇸🇦": "5433811229250434478",
    "🎟": "5458871830846656370",
    "📦": "5458790973792340888",
    "💳": "5460959824902638811",
    "🔪": "5458848109742280160",
    "🔫": "5458685884532545296",
    "💊": "5460985873879288634",
    "🦈": "5460680720747877706",
    "🦉": "5461152772013444213",
    "🐒": "5460791419234963381",
    "🦊": "5460660203689105734",
    "🐰": "5461154601669510918",
    "🦦": "5460903002485314455",
    "🐼": "5460880372302629461",
    "🦝": "5460640760372154944",
    "🐧": "5458676946705602852",
    "🦆": "5458484867178188906",
    "👾": "5460913374831332135",
    "🐕": "5458404181922566812",
    "🦅": "5461099497239105126",
    "🐉": "5458692095055255320",
    "🐢": "5458626906041636543",
    "🏆": "5460948786836687726",
    "🎲": "5463376160618468145",
    "🥇": "5462947101975530592",
    "🐔": "5350310639745130183",
    "🫥": "5350783674558211235",
    "😷": "5350450260541990949",
    "🤤": "5350534493440595973",
    "🩴": "5348281761619011725",
    "🩱": "5348586579742976907",
    "❇": "5370796766163657234",
    "🪧": "5371000046965780387",
    "🎗": "5370885517367858328",
    "🎯": "5228855127892327218",
    "🥈": "5231431133312348035",
}

# Older IDs are kept only for emojis that emoji.json does not contain (for example 📁 and 📤).
_LEGACY_EMOJI_MAP = {
    "🔥": PE_FIRE, "⭐": PE_STAR, "🚀": PE_ROCKET, "👑": PE_CROWN, "🛡": PE_SHIELD,
    "💰": PE_MONEY, "📱": PE_PHONE, "✅": PE_CHECK, "❌": PE_CROSS, "⚠": PE_WARNING,
    "🔒": PE_LOCK, "🎁": PE_GIFT, "👤": PE_USER, "📤": PE_UPLOAD, "📁": PE_FOLDER,
    "⚙": PE_SETTINGS, "🖥": PE_SERVER, "💎": PE_DIAMOND, "🤖": PE_BOT,
}
CUSTOM_EMOJI_MAP = {**_LEGACY_EMOJI_MAP, **EMOJI_JSON_MAP}


def _norm_emoji(value):
    return value.replace('\ufe0f', '')


def emoji_id_for(char, default=None):
    return CUSTOM_EMOJI_MAP.get(_norm_emoji(char), default)


# every named constant now points at the emoji.json ID where one exists
PE_FIRE, PE_STAR, PE_ROCKET, PE_CROWN = (emoji_id_for(c, d) for c, d in (("🔥", PE_FIRE), ("⭐", PE_STAR), ("🚀", PE_ROCKET), ("👑", PE_CROWN)))
PE_SHIELD, PE_MONEY, PE_PHONE, PE_CHECK = (emoji_id_for(c, d) for c, d in (("🛡", PE_SHIELD), ("💰", PE_MONEY), ("📱", PE_PHONE), ("✅", PE_CHECK)))
PE_CROSS, PE_WARNING, PE_LOCK, PE_GIFT = (emoji_id_for(c, d) for c, d in (("❌", PE_CROSS), ("⚠", PE_WARNING), ("🔒", PE_LOCK), ("🎁", PE_GIFT)))
PE_APPROVE, PE_USER, PE_ADMIN = emoji_id_for("✅", PE_APPROVE), emoji_id_for("👤", PE_USER), emoji_id_for("🛡", PE_ADMIN)
PE_UPLOAD, PE_FOLDER = emoji_id_for("📤", PE_UPLOAD), emoji_id_for("📁", PE_FOLDER)
PE_SETTINGS, PE_SERVER, PE_DIAMOND, PE_BOT = (emoji_id_for(c, d) for c, d in (("⚙", PE_SETTINGS), ("🖥", PE_SERVER), ("💎", PE_DIAMOND), ("🤖", PE_BOT)))

_EMOJI_ALT = '|'.join(''.join(re.escape(c) + '\ufe0f?' for c in k)
                      for k in sorted(CUSTOM_EMOJI_MAP, key=len, reverse=True))
_EMOJI_RE = re.compile(r'(<tg-emoji\b.*?</tg-emoji>|<pre>.*?</pre>|<code>.*?</code>)|(' + _EMOJI_ALT + ')', re.S)
_LEAD_EMOJI_RE = re.compile('^(' + _EMOJI_ALT + r')\s*')


def decorate_emojis(text):
    """Turn known Unicode emojis in an HTML message into custom emoji entities."""
    if not isinstance(text, str) or not custom_emoji_enabled():
        return text
    if len(_EMOJI_RE.findall(text)) > 90:      # Telegram allows 100 entities per message
        return text

    def swap(m):
        if m.group(1):
            return m.group(1)
        return pe(CUSTOM_EMOJI_MAP[_norm_emoji(m.group(2))], m.group(2))
    return _EMOJI_RE.sub(swap, text)


BUTTON_ICON_STATE = {'disabled': os.getenv('BUTTON_EMOJI', '1').strip().lower() in ('0', 'false', 'no', 'off')}
_PlainInlineButton = InlineKeyboardButton


class InlineKeyboardButton(_PlainInlineButton):
    """Moves a leading emoji of the label into icon_custom_emoji_id (premium icon on the button)."""

    def __init__(self, text, *args, **kwargs):
        self._plain_text = text
        self._icon = None
        label = icon = None
        if custom_emoji_enabled() and not BUTTON_ICON_STATE['disabled'] and 'icon_custom_emoji_id' not in kwargs:
            m = _LEAD_EMOJI_RE.match(text)
            if m and text[m.end():].strip():
                icon = CUSTOM_EMOJI_MAP.get(_norm_emoji(m.group(1)))
                label = text[m.end():]
        if icon:
            try:
                super().__init__(label, *args, icon_custom_emoji_id=icon, **kwargs)
                self._icon = icon
                return
            except TypeError:
                BUTTON_ICON_STATE['disabled'] = True   # installed library predates Bot API 9.4
        super().__init__(text, *args, **kwargs)


def safe_html(value):
    return html.escape(str(value), quote=False)


def premium_header(title, emoji_id=PE_CROWN, fallback="👑"):
    return (
        f"{pe(emoji_id, fallback)} "
        f"<b>{safe_html(title)}</b>"
    )



# ============================================================
# TELEGRAM BOT INIT
# ============================================================

if not BOT_TOKEN or OWNER_ID <= 0:
    raise SystemExit("Set BOT_TOKEN and OWNER_ID in the environment variables first.")

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode=None
)


# ---- Premium emoji send layer -------------------------------------------------
# Wraps the send/edit methods ONCE so every HTML message and caption in the bot
# (legacy handlers included) gets custom emoji entities and button icons. If Telegram
# rejects them, the message is resent in steps: without button icons, then without
# custom emoji, so a message is never lost.
EMOJI_STATS = {'sent':0,'rejected':0,'button_fallbacks':0,'last_error':''}
_TG_EMOJI_TAG = re.compile(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', re.S)
RAW_SEND_MESSAGE = bot.send_message

def strip_custom_emoji(value):
    return _TG_EMOJI_TAG.sub(r'\1', value) if isinstance(value,str) else value

def _markup_has_icons(markup):
    return any(getattr(b,'_icon',None) for row in (getattr(markup,'keyboard',None) or []) for b in row)

def strip_button_icons(markup):
    import copy
    clone = copy.deepcopy(markup)
    for row in clone.keyboard:
        for b in row:
            if getattr(b,'_icon',None):
                b.icon_custom_emoji_id = None
                b.text = b._plain_text
                b._icon = None
    return clone

def _install_emoji_layer():
    def make(original, pos, field):
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            args = list(args)
            if kwargs.get('parse_mode') == 'HTML':
                if field in kwargs:
                    kwargs[field] = decorate_emojis(kwargs[field])
                elif pos is not None and len(args) > pos:
                    args[pos] = decorate_emojis(args[pos])
            markup = kwargs.get('reply_markup')
            used_text = any('<tg-emoji' in v for v in list(args)+list(kwargs.values()) if isinstance(v,str))
            used_icon = _markup_has_icons(markup)
            try:
                result = original(*args, **kwargs)
                if used_text:
                    EMOJI_STATS['sent'] += 1
                return result
            except Exception as exc:
                if not (getattr(exc,'error_code',0) == 400 and 'not modified' not in str(exc).lower()
                        and (used_text or used_icon)):
                    raise
                EMOJI_STATS['last_error'] = str(exc)[:300]
                if used_icon:
                    kw2 = dict(kwargs)
                    kw2['reply_markup'] = strip_button_icons(markup)
                    try:
                        result = original(*args, **kw2)
                        BUTTON_ICON_STATE['disabled'] = True
                        EMOJI_STATS['button_fallbacks'] += 1
                        print(f'Telegram rejected button icons; disabled: {exc}')
                        return result
                    except Exception as exc2:
                        if getattr(exc2,'error_code',0) != 400:
                            raise
                        exc, kwargs = exc2, kw2
                if not used_text:
                    raise exc
                EMOJI_STATS['rejected'] += 1
                if EMOJI_STATS['rejected'] >= 3 and EMOJI_STATS['sent'] == 0:
                    EMOJI_RUNTIME_DISABLED['v'] = True
                    print('Telegram keeps rejecting custom emoji; switched off until restart.')
                print(f'Custom emoji rejected, resending plain: {exc}')
                return original(*[strip_custom_emoji(a) for a in args],
                                **{k:strip_custom_emoji(v) for k,v in kwargs.items()})
        wrapper._emoji_layer = True
        return wrapper
    for name, pos, field in (('send_message',1,'text'),('edit_message_text',0,'text'),('send_photo',None,'caption'),
                             ('send_document',None,'caption'),('edit_message_caption',None,'caption')):
        current = getattr(bot, name)
        if not getattr(current, '_emoji_layer', False):
            setattr(bot, name, make(current, pos, field))

_install_emoji_layer()

def emoji_self_test(uid):
    """Owner command /emojitest: sends sample custom emojis plus a button icon and reports Telegram's answer."""
    sample = ' '.join(pe(i,'•') for i in list(EMOJI_JSON_MAP.values())[:40])
    probe = InlineKeyboardMarkup([[InlineKeyboardButton('👑 Button icon test','s:home')]])
    report = []
    try:
        RAW_SEND_MESSAGE(uid, '🧪 <b>Custom emoji test</b>\n'+sample, parse_mode='HTML')
        report.append('✅ Text: Telegram accepted custom emoji entities.')
    except Exception as exc:
        report.append('⚠️ Text rejected: <code>'+safe_html(str(exc)[:300])+'</code>')
    try:
        RAW_SEND_MESSAGE(uid, 'Button icon probe 👇', reply_markup=probe)
        report.append('✅ Button: accepted' + (' (icon sent)' if _markup_has_icons(probe) else ' (library has no icon support, plain label sent)'))
    except Exception as exc:
        report.append('⚠️ Button rejected: <code>'+safe_html(str(exc)[:300])+'</code>')
    report.append(f'Sent: {EMOJI_STATS["sent"]} • Rejected: {EMOJI_STATS["rejected"]} • Button fallbacks: {EMOJI_STATS["button_fallbacks"]}\n'
                  f'Enabled: {custom_emoji_enabled()} • Button icons: {not BUTTON_ICON_STATE["disabled"]}\n'
                  'If the emojis above look plain, Telegram is accepting but not showing them for this bot.')
    bot.send_message(uid, '\n'.join(report), parse_mode='HTML')



# ============================================================
# DATA PERSISTENCE
# ============================================================

@locked
def save_data():
    try:
        temp_file = DATA_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            payload = None

            for _attempt in range(5):

                try:

                    payload = json.dumps(
                        users,
                        indent=4,
                        ensure_ascii=False
                    )

                    break

                except RuntimeError:

                    # dict changed size while serialising - retry
                    time.sleep(0.05)

            if payload is None:
                raise RuntimeError("users changed during save")

            f.write(payload)

        os.replace(temp_file, DATA_FILE)

    except Exception as e:
        print(f"Save Error: {e}")


@locked
def load_data():

    global users

    if not os.path.exists(DATA_FILE):
        users = {}
        return

    try:

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        users.clear()

        for key, value in raw_data.items():

            try:
                uid = int(key)
            except:
                continue

            if not isinstance(value, dict):
                value = {}

            value.setdefault("files", [])
            value.setdefault("env_vars", {})

            value.setdefault(
                "approved",
                uid == OWNER_ID
            )

            value.setdefault(
                "rejected",
                False
            )

            users[uid] = value

    except Exception as e:

        print(f"Load Error: {e}")

        users = {}


load_data()


# ============================================================
# USER / APPROVAL SYSTEM
# ============================================================

@locked
def ensure_user(uid):

    if uid not in users:

        users[uid] = {
            "files": [],
            "env_vars": {},
            "approved": uid == OWNER_ID,
            "rejected": False
        }

        save_data()

    else:

        users[uid].setdefault("files", [])
        users[uid].setdefault("env_vars", {})
        users[uid].setdefault(
            "approved",
            uid == OWNER_ID
        )
        users[uid].setdefault(
            "rejected",
            False
        )


def is_owner(uid):

    return uid == OWNER_ID


def is_approved(uid):

    if uid == OWNER_ID:
        return True

    ensure_user(uid)

    return users[uid].get("approved", False)


def approval_buttons(uid):

    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "✅ APPROVE",
            callback_data=f"approve_{uid}"
        ),
        InlineKeyboardButton(
            "❌ REJECT",
            callback_data=f"reject_{uid}"
        )
    )

    return markup


def send_approval_request(message):

    uid = message.from_user.id

    first_name = (
        message.from_user.first_name
        or "Unknown"
    )

    username = message.from_user.username

    if username:
        username_text = f"@{username}"
    else:
        username_text = "No username"

    text = (
        f"{pe(PE_ADMIN, '👑')} "
        f"<b>NEW USER APPROVAL</b>\n\n"

        f"{pe(PE_USER, '👤')} "
        f"<b>Name:</b> "
        f"{safe_html(first_name)}\n"

        f"{pe(PE_PHONE, '🆔')} "
        f"<b>User ID:</b> "
        f"<code>{uid}</code>\n"

        f"{pe(PE_BOT, '🤖')} "
        f"<b>Username:</b> "
        f"{safe_html(username_text)}\n\n"

        f"{pe(PE_WARNING, '⚠️')} "
        f"<b>Status:</b> Pending Approval"
    )

    try:

        bot.send_message(
            OWNER_ID,
            text,
            reply_markup=approval_buttons(uid),
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            f"Approval notification error: {e}"
        )


def approval_required(message):

    uid = message.from_user.id

    if is_owner(uid):
        return False

    if is_approved(uid):
        return False

    ensure_user(uid)

    bot.reply_to(
        message,
        (
            f"{pe(PE_LOCK, '🔐')} "
            f"<b>ACCESS PENDING</b>\n\n"

            f"{pe(PE_ADMIN, '👑')} "
            f"Your account is waiting for "
            f"<b>Owner Approval</b>.\n\n"

            f"{pe(PE_STAR, '⭐')} "
            f"Please wait until the owner approves "
            f"your account."
        ),
        parse_mode="HTML"
    )

    return True


# ============================================================
# OWNER NOTIFICATION
# ============================================================

def notify_owner(text, index=0):

    try:

        bot.send_message(
            OWNER_ID,
            f"{pe(emoji_id_for('🔔', PE_STAR), '🔔')} {text}",
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            f"Owner notification error: {e}"
        )


# ============================================================
# UTILITIES
# ============================================================

def uptime():

    seconds = int(
        time.time() - bot_start_time
    )

    return (
        f"{seconds // 3600}h "
        f"{(seconds % 3600) // 60}m "
        f"{seconds % 60}s"
    )


def user_folder(uid):

    path = os.path.join(
        UPLOAD_DIR,
        str(uid)
    )

    os.makedirs(
        path,
        exist_ok=True
    )

    return path


def get_system_info():

    cpu_freq = psutil.cpu_freq()

    if cpu_freq:
        cpu_ghz = cpu_freq.current / 1000
    else:
        cpu_ghz = 0

    ram = psutil.virtual_memory()

    total_ram_gb = (
        ram.total /
        (1024 ** 3)
    )

    free_ram_gb = (
        ram.available /
        (1024 ** 3)
    )

    return (
        cpu_ghz,
        total_ram_gb,
        free_ram_gb
    )


def install_requirements(folder):

    req_file = os.path.join(
        folder,
        "requirements.txt"
    )

    if os.path.exists(req_file):

        try:

            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    req_file
                ]
            )

        except Exception as e:

            print(
                f"Requirements install error: {e}"
            )


# ============================================================
# .ENV HELPERS
# ============================================================

ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_env_text(text):
    """Parse KEY=VALUE lines. Returns dict."""

    result = {}

    for raw in (text or "").splitlines():

        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]

        if ENV_KEY_RE.match(key):
            result[key] = value

    return result


def read_env_file(uid):

    path = os.path.join(user_folder(uid), ".env")

    if not os.path.exists(path):
        return {}

    try:

        with open(path, "r", encoding="utf-8") as f:
            return parse_env_text(f.read())

    except Exception as e:

        print(f".env read error: {e}")

        return {}


def get_file_env(uid, filename):

    ensure_user(uid)

    return users[uid].setdefault(
        "env_vars",
        {}
    ).get(filename, {})


@locked
def write_env_file(uid, filename):
    """Write the saved variables of a file into user_folder/.env"""

    env_vars = get_file_env(uid, filename)

    path = os.path.join(user_folder(uid), ".env")

    try:

        lines = []

        for k, v in env_vars.items():

            v = str(v)

            if re.search(r"[\s#'\"\\]", v):
                v = (
                    '"'
                    + v.replace("\\", "\\\\").replace('"', '\\"')
                    + '"'
                )

            lines.append(f"{k}={v}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

    except Exception as e:

        print(f".env write error: {e}")


@locked
def set_env_vars(uid, filename, new_vars):

    ensure_user(uid)

    store = users[uid].setdefault("env_vars", {})
    store.setdefault(filename, {}).update(new_vars)

    save_data()
    write_env_file(uid, filename)


@locked
def clear_env_vars(uid, filename):

    ensure_user(uid)

    users[uid].setdefault("env_vars", {}).pop(filename, None)

    save_data()
    write_env_file(uid, filename)


def mask_value(key, value):

    value = str(value)

    if key in ("ADMIN_ID", "OWNER_ID", "API_ID"):
        return value

    if len(value) <= 6:
        return "*" * len(value)

    return value[:4] + "*" * 6 + value[-2:]


# ============================================================
# SCRIPT RUNNING
# ============================================================

def kill_process_tree(proc):
    """Kill a process and every child it spawned (no zombies left behind)."""

    if proc is None:
        return

    try:
        pid = proc.pid
    except Exception:
        return

    parent = None

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        parent = None
    except Exception:
        parent = None

    if parent is not None:

        try:
            children = parent.children(recursive=True)
        except Exception:
            children = []

        for child in children:

            try:
                child.terminate()
            except Exception:
                pass

        try:
            _, alive = psutil.wait_procs(children, timeout=2)
        except Exception:
            alive = []

        for child in alive:

            try:
                child.kill()
            except Exception:
                pass

        try:
            parent.terminate()
        except Exception:
            pass

        try:
            parent.wait(timeout=3)
        except Exception:

            try:
                parent.kill()
            except Exception:
                pass

    try:
        proc.kill()
    except Exception:
        pass

    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def get_script_lock(user_id, file_path):

    with STATE_LOCK:

        return SCRIPT_LOCKS.setdefault(
            (user_id, file_path),
            threading.Lock()
        )


def stop_script(user_id, file_path):

    with STATE_LOCK:

        proc = active_scripts.get(user_id, {}).pop(file_path, None)

    if not proc:
        return False

    kill_process_tree(proc)

    return True


def append_log(user_id, file_path, line, proc=None):

    with STATE_LOCK:

        # Ignore output of an old instance that was replaced / stopped
        if (
            proc is not None
            and active_scripts.get(user_id, {}).get(file_path) is not proc
        ):
            return

        buf = logs_store.setdefault(
            user_id,
            {}
        ).setdefault(file_path, [])

        buf.append(line)

        if len(buf) > 100:
            del buf[:-100]


def run_script_thread(
    user_id,
    file_path
):

    proc = None

    try:

        abs_path = os.path.abspath(file_path)
        script_dir = os.path.dirname(abs_path)

        # Isolated environment: never leak the hosting bot's credentials
        child_env = os.environ.copy()
        child_env.pop("BOT_TOKEN", None)
        child_env.pop("OWNER_ID", None)
        child_env.pop("PORT", None)

        # Universal Python execution environment
        child_env["PYTHONUNBUFFERED"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"

        root_dir = os.path.abspath(user_folder(user_id))

        py_paths = [script_dir]

        if root_dir != script_dir:
            py_paths.append(root_dir)

        child_env["PYTHONPATH"] = os.pathsep.join(py_paths)

        # .env file inside the user's folder
        child_env.update(read_env_file(user_id))

        # Per-file saved variables (take priority)
        filename = os.path.relpath(
            abs_path,
            root_dir
        ).replace(os.sep, "/")

        with STATE_LOCK:

            env_store = users.get(user_id, {}).get("env_vars", {})

            saved = env_store.get(filename)

            if saved is None:
                saved = env_store.get(os.path.basename(abs_path), {})

            saved = dict(saved)

        child_env.update(
            {str(k): str(v) for k, v in saved.items()}
        )

        with get_script_lock(user_id, file_path):

            # Never keep two instances alive (prevents Telegram 409 Conflict)
            with STATE_LOCK:

                old = active_scripts.get(user_id, {}).pop(
                    file_path,
                    None
                )

            if old is not None:
                kill_process_tree(old)

            with STATE_LOCK:

                logs_store.setdefault(
                    user_id,
                    {}
                )[file_path] = []

            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    abs_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=script_dir,
                env=child_env
            )

            with STATE_LOCK:

                active_scripts.setdefault(
                    user_id,
                    {}
                )[file_path] = proc

        # stdout + stderr (merged) -> logs
        for line in iter(proc.stdout.readline, ""):

            append_log(
                user_id,
                file_path,
                line.rstrip("\r\n"),
                proc
            )

        return_code = proc.wait()

        with STATE_LOCK:

            own = (
                active_scripts.get(user_id, {}).get(file_path)
                is proc
            )

        if own:

            append_log(
                user_id,
                file_path,
                f"[Process exited with code {return_code}]",
                proc
            )

            if return_code != 0:

                with STATE_LOCK:

                    tail = "\n".join(
                        logs_store.get(user_id, {}).get(file_path, [])
                    )

                if "ModuleNotFoundError" in tail or "No module named" in tail:

                    append_log(
                        user_id,
                        file_path,
                        "[Hint: install the missing package from "
                        "the Package Installer, then run again]",
                        proc
                    )

    except Exception as e:

        print(
            f"Error in script {file_path}: {e}"
        )

        append_log(
            user_id,
            file_path,
            f"Launcher error: {e}"
        )

    finally:

        # Only remove our own entry (a newer instance may have replaced it)
        with STATE_LOCK:

            if (
                proc is not None
                and active_scripts.get(user_id, {}).get(file_path) is proc
            ):

                active_scripts[user_id].pop(
                    file_path,
                    None
                )

        try:

            if proc is not None and proc.stdout:
                proc.stdout.close()

        except Exception:
            pass


def start_script(
    user_id,
    file_path
):

    # Never run duplicate instances of the same file
    with STATE_LOCK:

        old = active_scripts.get(user_id, {}).pop(file_path, None)

    if old is not None:
        kill_process_tree(old)

    thread = threading.Thread(
        target=run_script_thread,
        args=(
            user_id,
            file_path
        ),
        daemon=True
    )

    thread.start()


# ============================================================
# INSTALLATION
# ============================================================

def live_install(
    cmd_list,
    chat_id,
    message_id,
    description
):

    try:

        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output_lines = []

        while True:

            line = proc.stdout.readline()

            if line:

                output_lines.append(
                    line.rstrip()
                )

                if len(output_lines) > 8:
                    output_lines = (
                        output_lines[-8:]
                    )

                live_text = "\n".join(
                    output_lines
                )

                try:

                    bot.edit_message_text(
                        (
                            f"{pe(PE_UPLOAD, '📥')} "
                            f"<b>{safe_html(description)}...</b>\n"
                            f"<pre>{safe_html(live_text)}</pre>"
                        ),
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML"
                    )

                except:
                    pass

            if (
                not line
                and proc.poll() is not None
            ):
                break

        full_output = "\n".join(
            output_lines[-100:]
        )

        if proc.returncode == 0:

            bot.edit_message_text(
                (
                    f"{pe(PE_CHECK, '✅')} "
                    f"<b>{safe_html(description)} "
                    f"installed!</b>\n\n"
                    f"<pre>{safe_html(full_output)}</pre>"
                ),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )

        else:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>Installation Failed</b>\n\n"
                    f"<pre>{safe_html(full_output)}</pre>"
                ),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )

    except Exception as e:

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>Exception</b>\n\n"
                    f"<code>{safe_html(e)}</code>"
                ),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )

        except:
            pass


def install_recommended_packages(
    chat_id,
    message_id
):

    total = len(RECOMMENDED_PACKAGES)

    for idx, pkg in enumerate(
        RECOMMENDED_PACKAGES,
        start=1
    ):

        live_install(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                pkg
            ],
            chat_id,
            message_id,
            f"{pkg} ({idx}/{total})"
        )

    live_install(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            PYTG_CALLS_PACKAGE
        ],
        chat_id,
        message_id,
        "pytgcalls (GitHub)"
    )


# ============================================================
# MAIN KEYBOARD
# ============================================================

def control_buttons(uid=None):

    # IMPORTANT:
    # Do NOT pass a list as the first argument.
    # This fixes:
    # ReplyKeyboardMarkup.__init__()
    # got multiple values for resize_keyboard

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        KeyboardButton("🌏 Upload"),
        KeyboardButton("📁 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬")
    )

    markup.row(
        KeyboardButton("🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭"),
        KeyboardButton("⏹ 𝐒𝐭𝐨𝐩")
    )

    markup.row(
        KeyboardButton("⚡ 𝐒𝐩𝐞𝐞𝐝"),
        KeyboardButton("🚀 𝐒𝐭𝐚𝐭ᴜѕ")
    )

    markup.row(
        KeyboardButton(
            "⚙️ Recommended Install"
        )
    )

    if uid is not None and uid == OWNER_ID:
        markup.row(
            KeyboardButton("👑 Owner Panel")
        )

    return markup


# ============================================================
# .ENV MENUS
# ============================================================

def env_menu_text(uid, filename, prefix=""):

    env_vars = get_file_env(uid, filename)

    if env_vars:

        lines = "\n".join(
            f"• <code>{safe_html(k)}</code> = "
            f"<code>{safe_html(mask_value(k, v))}</code>"
            for k, v in env_vars.items()
        )

    else:

        lines = "<i>No variables saved yet.</i>"

    return (
        f"{prefix}"
        f"{pe(PE_SETTINGS, '⚙️')} "
        f"<b>.ENV CONFIGURATION</b>\n"
        f"<code>{safe_html(filename)}</code>\n\n"

        f"{pe(PE_LOCK, '🔐')} "
        f"<b>Saved Variables:</b>\n"
        f"{lines}\n\n"

        f"{pe(PE_STAR, '⚡')} "
        f"Choose an option below, then press "
        f"<b>Save &amp; Run Bot</b>."
    )


def env_menu_markup(filename):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤖 Set BOT_TOKEN",
                callback_data=f"setenv_BOT_TOKEN_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "👑 Set ADMIN_ID / OWNER_ID",
                callback_data=f"setenv_ADMIN_ID_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔑 Set API_ID & API_HASH",
                callback_data=f"setenv_API_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Add Custom Variable (KEY=VALUE)",
                callback_data=f"setenv_CUSTOM_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Clear .env Variables",
                callback_data=f"clearenv_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 Save & Run Bot",
                callback_data=f"skiprun_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data=f"file_{filename}"
            )
        ]
    ])


def env_prompt_markup(filename):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data=f"cancelenv_{filename}"
            )
        ]
    ])


def send_env_menu(chat_id, uid, filename, prefix="", message_id=None):

    text = env_menu_text(uid, filename, prefix)
    markup = env_menu_markup(filename)

    if message_id:

        try:

            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )

            return

        except Exception:
            pass

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )


def env_ask_markup_text(mode, filename):

    if mode == "BOT_TOKEN":

        return (
            f"{pe(PE_BOT, '🤖')} "
            f"<b>SET BOT_TOKEN</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"
            f"Send your bot token now "
            f"(from @BotFather)."
        )

    if mode == "ADMIN_ID":

        return (
            f"{pe(PE_ADMIN, '👑')} "
            f"<b>SET ADMIN_ID / OWNER_ID</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"
            f"Send your numeric Telegram user ID.\n"
            f"It will be saved as both "
            f"<code>ADMIN_ID</code> and <code>OWNER_ID</code>."
        )

    if mode == "API":

        return (
            f"{pe(PE_LOCK, '🔑')} "
            f"<b>SET API_ID &amp; API_HASH</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"
            f"Send <b>API_ID</b> first (numbers only),\n"
            f"or send both at once:\n"
            f"<pre>API_ID=123456\nAPI_HASH=abcdef...</pre>"
        )

    return (
        f"{pe(PE_SETTINGS, '➕')} "
        f"<b>ADD CUSTOM VARIABLES</b>\n"
        f"<code>{safe_html(filename)}</code>\n\n"
        f"Send one or more lines in "
        f"<code>KEY=VALUE</code> format:\n"
        f"<pre>MONGO_URL=mongodb://...\nLOG_CHANNEL=-100123</pre>"
    )


def handle_env_input(message, state):
    """Process a text reply for a pending setenv_* request."""

    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()

    mode = state["mode"]
    filename = state["filename"]

    # Remove the user's message (may contain secrets)
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    def fail(reason):

        bot.send_message(
            chat_id,
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>{safe_html(reason)}</b>\n\n"
                f"Please try again or press Cancel."
            ),
            reply_markup=env_prompt_markup(filename),
            parse_mode="HTML"
        )

    if mode == "BOT_TOKEN":

        if not re.match(r"^\d+:[A-Za-z0-9_-]{20,}$", text):
            return fail("Invalid BOT_TOKEN format")

        new_vars = {"BOT_TOKEN": text}

    elif mode == "ADMIN_ID":

        if not re.match(r"^-?\d+$", text):
            return fail("ID must be numeric")

        new_vars = {"ADMIN_ID": text, "OWNER_ID": text}

    elif mode == "API":

        step = state.get("step", "API_ID")

        if "=" in text:

            parsed = parse_env_text(text)

            new_vars = {
                k: v for k, v in parsed.items()
                if k in ("API_ID", "API_HASH")
            }

            if not new_vars:
                return fail("Send API_ID=... and/or API_HASH=...")

        elif step == "API_ID":

            if not re.match(r"^\d+$", text):
                return fail("API_ID must be numeric")

            state["api_id"] = text
            state["step"] = "API_HASH"

            bot.send_message(
                chat_id,
                (
                    f"{pe(PE_CHECK, '✅')} "
                    f"<b>API_ID received.</b>\n\n"
                    f"Now send your <b>API_HASH</b>."
                ),
                reply_markup=env_prompt_markup(filename),
                parse_mode="HTML"
            )

            return

        else:

            if not re.match(r"^[A-Za-z0-9]{16,64}$", text):
                return fail("Invalid API_HASH format")

            new_vars = {
                "API_ID": state.get("api_id", ""),
                "API_HASH": text
            }

    else:

        new_vars = parse_env_text(text)

        if not new_vars:
            return fail("No valid KEY=VALUE lines found")

    env_waiting_users.pop(uid, None)

    set_env_vars(uid, filename, new_vars)

    saved_keys = ", ".join(new_vars.keys())

    send_env_menu(
        chat_id,
        uid,
        filename,
        prefix=(
            f"{pe(PE_CHECK, '✅')} "
            f"<b>Saved:</b> "
            f"<code>{safe_html(saved_keys)}</code>\n\n"
        )
    )


# ============================================================
# EXTRA STATE
# ============================================================

owner_waiting = {}
owner_run_cache = []
req_select_store = {}

MENU_PREFIXES = (
    "🌏", "📁", "🔄", "⏹", "⚡", "🚀", "⚙", "👑"
)


def is_menu_button(text):
    return any(text.startswith(p) for p in MENU_PREFIXES)


def edit_call(call, text, markup=None):

    try:

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception:
        pass


def get_file_limit(uid):
    """None = unlimited, otherwise the max number of files."""

    if uid == OWNER_ID:
        return None

    ensure_user(uid)

    lim = users[uid].get("max_files", users[uid].get("file_limit", 2))

    try:
        lim = int(lim)
    except Exception:
        lim = 2

    if lim < 0:
        return None

    return lim


def limit_label(uid):

    if uid == OWNER_ID:
        return "Unlimited"

    lim = get_file_limit(uid)

    return "Unlimited" if lim is None else str(lim)


# ============================================================
# MANUAL PACKAGE INSTALLER
# ============================================================

PKG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\],=<>!~@:/+]*$")


def pip_cmd(spec):

    return [
        sys.executable,
        "-m",
        "pip",
        "install",
        spec
    ]


def install_in_thread(chat_id, items):
    """items = [(cmd_list, description), ...] installed one by one."""

    def worker():

        for cmd, desc in items:

            try:

                m = bot.send_message(
                    chat_id,
                    (
                        f"{pe(PE_UPLOAD, '📥')} "
                        f"<b>Preparing {safe_html(desc)}...</b>"
                    ),
                    parse_mode="HTML"
                )

                live_install(
                    cmd,
                    chat_id,
                    m.message_id,
                    desc
                )

            except Exception as e:

                print(f"Install error: {e}")

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


def pkg_menu_text(prefix=""):

    return (
        f"{prefix}"
        f"{pe(PE_SETTINGS, '⚙️')} "
        f"<b>PACKAGE INSTALLER</b>\n\n"

        f"{pe(PE_SERVER, '📦')} "
        f"Nothing is installed automatically.\n"
        f"Choose how you want to install:\n\n"

        f"• {pe(PE_STAR, '✍️')} "
        f"<b>Manual</b> - type package name(s)\n"

        f"• {pe(PE_DIAMOND, '📋')} "
        f"<b>Recommended</b> - install one package "
        f"from the list"
    )


def pkg_menu_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✍️ Manual Package Install (Type Name)",
                callback_data="manual_pkg_input"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Choose from Recommended List",
                callback_data="rec_pkg_list"
            )
        ]
    ])


def pkg_cancel_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="pkg_cancel"
            )
        ]
    ])


def rec_list_markup():

    rows = []
    row = []

    for p in RECOMMENDED_PACKAGES:

        row.append(
            InlineKeyboardButton(
                f"📦 {p}",
                callback_data=f"recpkg_{p}"
            )
        )

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton(
            "📦 pytgcalls (GitHub)",
            callback_data="recpkg_pytgcalls"
        )
    ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="pkg_menu"
        )
    ])

    return InlineKeyboardMarkup(rows)


def handle_manual_install_input(message):

    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()

    names = text.split()

    valid = bool(names) and all(
        PKG_NAME_RE.match(n) and len(n) <= 120
        for n in names
    )

    if not valid:

        bot.send_message(
            chat_id,
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Invalid package name.</b>\n\n"
                f"Send names like "
                f"<code>pyrogram</code> or "
                f"<code>requests aiohttp</code>."
            ),
            reply_markup=pkg_cancel_markup(),
            parse_mode="HTML"
        )

        return

    install_waiting_users.pop(uid, None)

    install_in_thread(
        chat_id,
        [(pip_cmd(n), n) for n in names[:10]]
    )


# ============================================================
# REQUIREMENTS.TXT HELPERS
# ============================================================

def find_requirements(folder):
    """Relative path of a requirements.txt inside folder, or None."""

    if os.path.isfile(os.path.join(folder, "requirements.txt")):
        return "requirements.txt"

    for root, dirs, files in os.walk(folder):

        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d not in ("venv", "env", "__pycache__", "node_modules")
        ]

        for f in files:

            if f.lower() == "requirements.txt":

                return os.path.relpath(
                    os.path.join(root, f),
                    folder
                ).replace(os.sep, "/")

    return None


def safe_user_path(uid, rel):

    base = os.path.abspath(user_folder(uid))

    target = os.path.abspath(os.path.join(base, rel))

    if target == base or not target.startswith(base + os.sep):
        return None

    return target


def parse_requirements_file(path):

    pkgs = []

    try:

        with open(path, "r", encoding="utf-8", errors="ignore") as f:

            for raw in f:

                line = raw.split(" #")[0].strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("-")
                ):
                    continue

                if line not in pkgs:
                    pkgs.append(line)

    except Exception as e:

        print(f"Requirements parse error: {e}")

    return pkgs[:80]


def req_buttons(rel):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📦 Install requirements.txt",
                callback_data=f"reqinstall_{rel}"
            )
        ],
        [
            InlineKeyboardButton(
                "☑️ Select Packages from File",
                callback_data=f"reqselect_{rel}"
            )
        ],
        [
            InlineKeyboardButton(
                "⏭ Skip Installation",
                callback_data="myfiles"
            )
        ]
    ])


def req_prompt_text(rel):

    return (
        f"{pe(PE_CHECK, '✅')} "
        f"<b>File saved:</b> "
        f"<code>{safe_html(rel)}</code>\n\n"

        f"{pe(PE_SERVER, '📦')} "
        f"<b>Install the dependencies?</b>\n\n"

        f"{pe(PE_LOCK, '🔐')} "
        f"Nothing is installed automatically. "
        f"Choose an option below."
    )


def req_note(folder):

    if find_requirements(folder):

        return (
            f"{pe(PE_SERVER, '📦')} "
            f"<b>requirements.txt</b> found - "
            f"it is NOT installed automatically. "
            f"Choose below.\n\n"
        )

    return ""


def scan_py_files(folder, limit=300):
    """Find every .py file in the user's folder, including subfolders."""

    skip = {
        "venv", "env", ".venv", "__pycache__",
        "node_modules", "site-packages", ".git"
    }

    found = []

    for root, dirs, files in os.walk(folder):

        dirs[:] = [
            d for d in dirs
            if d not in skip and not d.startswith(".")
        ]

        for f in sorted(files):

            if f.lower().endswith(".py"):

                found.append(
                    os.path.relpath(
                        os.path.join(root, f),
                        folder
                    ).replace(os.sep, "/")
                )

                if len(found) >= limit:
                    return found

    return found


def zip_markup(folder, main_file):

    rows = []

    rel = find_requirements(folder)

    if rel:
        rows += req_buttons(rel).keyboard

    rows += env_choice_markup(main_file).keyboard

    return InlineKeyboardMarkup(rows)


# ============================================================
# OWNER PANEL
# ============================================================

def user_status_icon(u_id):

    u = users.get(u_id, {})

    if u_id == OWNER_ID:
        return "👑"

    if u.get("approved"):
        return "✅"

    if u.get("rejected"):
        return "🚫"

    return "⏳"


def owner_text():

    total_users = len(users)

    approved_users = sum(
        1 for u in users.values()
        if u.get("approved", False)
    )

    pending_users = sum(
        1 for u in users.values()
        if not u.get("approved", False)
        and not u.get("rejected", False)
    )

    banned_users = sum(
        1 for u in users.values()
        if u.get("rejected", False)
        and not u.get("approved", False)
    )

    total_files = sum(
        len(u.get("files", []))
        for u in users.values()
    )

    running = sum(
        len(v) for v in active_scripts.values()
    )

    return (
        f"{pe(PE_ADMIN, '👑')} "
        f"<b>OWNER PANEL</b>\n\n"

        f"{pe(PE_USER, '👥')} "
        f"<b>Total Users:</b> {total_users}\n"

        f"{pe(PE_CHECK, '✅')} "
        f"<b>Approved:</b> {approved_users}\n"

        f"{pe(PE_WARNING, '⏳')} "
        f"<b>Pending:</b> {pending_users}\n"

        f"{pe(PE_CROSS, '🚫')} "
        f"<b>Banned:</b> {banned_users}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Total Files:</b> {total_files}\n"

        f"{pe(PE_SERVER, '🟢')} "
        f"<b>Running Scripts:</b> {running}\n"

        f"⏱️ <b>Uptime:</b> {uptime()}"
    )


def owner_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👥 Manage Users",
                callback_data="owner_users"
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 All Running Scripts",
                callback_data="owner_running"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Broadcast Message",
                callback_data="owner_broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "🖥 Server & Storage Cleanup",
                callback_data="owner_cleanup"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="owner_home"
            )
        ]
    ])


def owner_back_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="owner_home"
            )
        ]
    ])


def send_owner_panel(chat_id):

    bot.send_message(
        chat_id,
        owner_text(),
        reply_markup=owner_markup(),
        parse_mode="HTML"
    )


def owner_users_view():

    approved = sum(
        1 for u in users.values()
        if u.get("approved", False)
    )

    pending = sum(
        1 for u in users.values()
        if not u.get("approved", False)
        and not u.get("rejected", False)
    )

    text = (
        f"{pe(PE_USER, '👥')} "
        f"<b>MANAGE USERS</b>\n\n"
        f"{pe(PE_CHECK, '✅')} "
        f"<b>Approved:</b> {approved}\n"
        f"{pe(PE_WARNING, '⏳')} "
        f"<b>Pending:</b> {pending}\n\n"
        f"✅ approved  ⏳ pending  🚫 banned  👑 owner\n"
        f"Tap a user to manage."
    )

    # Pending users first
    ordered = sorted(
        users.items(),
        key=lambda kv: (
            0 if (
                not kv[1].get("approved", False)
                and not kv[1].get("rejected", False)
            ) else 1
        )
    )

    rows = []

    for u_id, u in ordered[:90]:

        name = str(u.get("name") or "")[:18]

        label = (
            f"{user_status_icon(u_id)} {u_id} "
            f"• 📁{len(u.get('files', []))}"
        )

        if name:
            label += f" • {name}"

        rows.append([
            InlineKeyboardButton(
                label,
                callback_data=f"owner_user_{u_id}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="owner_home"
        )
    ])

    return text, InlineKeyboardMarkup(rows)


def owner_user_view(target):

    u = users.get(target)

    if u is None:
        return None, None

    icon = user_status_icon(target)

    status = {
        "👑": "Owner",
        "✅": "Approved",
        "🚫": "Banned",
        "⏳": "Pending"
    }.get(icon, "Unknown")

    running = len(active_scripts.get(target, {}))

    text = (
        f"{pe(PE_USER, '👤')} "
        f"<b>USER DETAILS</b>\n\n"

        f"{pe(PE_PHONE, '🆔')} "
        f"<b>ID:</b> <code>{target}</code>\n"

        f"{pe(PE_BOT, '📛')} "
        f"<b>Name:</b> "
        f"{safe_html(u.get('name') or 'Unknown')}\n"

        f"{pe(PE_SHIELD, '📌')} "
        f"<b>Status:</b> {icon} {status}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Files:</b> {len(u.get('files', []))}\n"

        f"{pe(PE_SERVER, '🟢')} "
        f"<b>Running:</b> {running}\n"

        f"{pe(PE_GIFT, '📦')} "
        f"<b>File Limit:</b> {limit_label(target)}"
    )

    rows = []

    if target != OWNER_ID:

        if u.get("approved"):

            rows.append([
                InlineKeyboardButton(
                    "❌ Ban (Unapprove)",
                    callback_data=f"owner_ban_{target}"
                )
            ])

        else:

            rows.append([
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"owner_appr_{target}"
                )
            ])

        rows.append([
            InlineKeyboardButton(
                "📈 Change File Limit",
                callback_data=f"owner_setlim_{target}"
            )
        ])

        rows.append([
            InlineKeyboardButton(
                "➖ Limit",
                callback_data=f"owner_lim_{target}_dec"
            ),
            InlineKeyboardButton(
                "➕ Limit",
                callback_data=f"owner_lim_{target}_inc"
            )
        ])

        rows.append([
            InlineKeyboardButton(
                "♾ Unlimited",
                callback_data=f"owner_lim_{target}_unl"
            ),
            InlineKeyboardButton(
                "🔁 Reset (2)",
                callback_data=f"owner_lim_{target}_reset"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "📁 View User Files",
            callback_data=f"owner_files_{target}"
        )
    ])

    rows.append([
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="owner_users"
        )
    ])

    return text, InlineKeyboardMarkup(rows)


def owner_files_view(target):

    files = users.get(target, {}).get("files", [])

    folder = user_folder(target)

    lines = []

    for f in files[:60]:

        p = os.path.join(folder, f)

        run = p in active_scripts.get(target, {})

        lines.append(
            f"{'🟢' if run else '⚪'} "
            f"<code>{safe_html(f)}</code>"
        )

    body = "\n".join(lines) or "No files."

    text = (
        f"{pe(PE_FOLDER, '📂')} "
        f"<b>FILES OF</b> <code>{target}</code>\n\n"
        f"{body}\n\n"
        f"🟢 running  ⚪ stopped"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data=f"owner_user_{target}"
            )
        ]
    ])

    return text, markup


def owner_running_view():

    owner_run_cache.clear()

    for u_id, procs in list(active_scripts.items()):

        for p in list(procs.keys()):

            owner_run_cache.append((u_id, p))

    lines = []
    rows = []

    for i, (u_id, p) in enumerate(owner_run_cache[:40]):

        base = os.path.basename(p)

        lines.append(
            f"🟢 <code>{u_id}</code> - "
            f"<code>{safe_html(base)}</code>"
        )

        rows.append([
            InlineKeyboardButton(
                f"⏹ Force Stop • {u_id} • {base[:20]}",
                callback_data=f"owner_fstop_{i}"
            )
        ])

    body = "\n".join(lines) or "No scripts running."

    if owner_run_cache:

        rows.append([
            InlineKeyboardButton(
                "⏹ Stop All Scripts",
                callback_data="owner_stopall"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "🔄 Refresh",
            callback_data="owner_running"
        ),
        InlineKeyboardButton(
            "⬅ Back",
            callback_data="owner_home"
        )
    ])

    text = (
        f"{pe(PE_SERVER, '🟢')} "
        f"<b>ALL RUNNING SCRIPTS</b> "
        f"({len(owner_run_cache)})\n\n{body}"
    )

    return text, InlineKeyboardMarkup(rows)


def dir_size(path):

    total = 0

    for root, _, files in os.walk(path):

        for f in files:

            try:
                total += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass

    return total


def owner_cleanup_view(prefix=""):

    cpu = psutil.cpu_percent(interval=0.3)

    ram = psutil.virtual_memory()

    try:

        disk = psutil.disk_usage(os.path.abspath(STORAGE_DIR))

        disk_line = (
            f"{round(disk.used / 1024 ** 3, 2)} / "
            f"{round(disk.total / 1024 ** 3, 2)} GB "
            f"({disk.percent}%)"
        )

    except Exception:

        disk_line = "N/A"

    storage_mb = round(
        dir_size(UPLOAD_DIR) / 1024 ** 2,
        2
    )

    log_files = sum(len(v) for v in logs_store.values())

    log_lines = sum(
        len(lines)
        for d in logs_store.values()
        for lines in d.values()
    )

    dead = sum(
        1
        for procs in active_scripts.values()
        for proc in procs.values()
        if proc.poll() is not None
    )

    running = sum(
        len(v) for v in active_scripts.values()
    )

    text = (
        f"{prefix}"
        f"{pe(PE_SERVER, '🖥')} "
        f"<b>SERVER &amp; STORAGE</b>\n\n"

        f"{pe(PE_FIRE, '⚙️')} "
        f"<b>CPU:</b> {cpu}%\n"

        f"{pe(PE_DIAMOND, '💾')} "
        f"<b>RAM:</b> "
        f"{round(ram.used / 1024 ** 3, 2)} / "
        f"{round(ram.total / 1024 ** 3, 2)} GB "
        f"({ram.percent}%)\n"

        f"{pe(PE_SHIELD, '💽')} "
        f"<b>Disk:</b> {disk_line}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>User Files:</b> {storage_mb} MB\n\n"

        f"{pe(PE_CHECK, '🟢')} "
        f"<b>Running Scripts:</b> {running}\n"

        f"{pe(PE_WARNING, '💀')} "
        f"<b>Dead Processes:</b> {dead}\n"

        f"{pe(PE_SETTINGS, '🔧')} "
        f"<b>Active Processes:</b> "
        f"{len(psutil.Process(os.getpid()).children(recursive=True))}\n"

        f"{pe(PE_UPLOAD, '📜')} "
        f"<b>Logs:</b> {log_files} files, "
        f"{log_lines} lines"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🧽 Clear Stale Logs",
                callback_data="owner_clr_stale"
            )
        ],
        [
            InlineKeyboardButton(
                "🧹 Clear All Logs",
                callback_data="owner_clr_all"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Kill Dead/Zombie Processes",
                callback_data="owner_clr_dead"
            )
        ],
        [
            InlineKeyboardButton(
                "🧼 Remove __pycache__",
                callback_data="owner_clr_cache"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="owner_cleanup"
            ),
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="owner_home"
            )
        ]
    ])

    return text, markup


@locked
def do_cleanup(kind):

    if kind == "stale":

        removed = 0

        for u_id in list(logs_store.keys()):

            for p in list(logs_store[u_id].keys()):

                if p not in active_scripts.get(u_id, {}):

                    logs_store[u_id].pop(p, None)
                    removed += 1

        return (
            f"{pe(PE_CHECK, '🧹')} "
            f"<b>Stale logs removed:</b> {removed}\n\n"
        )

    if kind == "all":

        count = sum(len(v) for v in logs_store.values())

        logs_store.clear()

        return (
            f"{pe(PE_CHECK, '🧹')} "
            f"<b>All logs cleared:</b> {count}\n\n"
        )

    if kind == "dead":

        removed = 0

        for u_id in list(active_scripts.keys()):

            for p, proc in list(active_scripts[u_id].items()):

                if proc.poll() is not None:

                    kill_process_tree(proc)

                    active_scripts[u_id].pop(p, None)

                    removed += 1

        reaped = 0

        try:

            me = psutil.Process(os.getpid())

            for child in me.children(recursive=True):

                try:

                    if child.status() == psutil.STATUS_ZOMBIE:

                        try:
                            os.waitpid(child.pid, os.WNOHANG)
                        except Exception:
                            pass

                        reaped += 1

                except Exception:
                    pass

        except Exception:
            pass

        return (
            f"{pe(PE_CHECK, '🔄')} "
            f"<b>Dead processes removed:</b> {removed}\n"
            f"{pe(PE_CHECK, '🧟')} "
            f"<b>Zombies reaped:</b> {reaped}\n\n"
        )

    if kind == "cache":

        removed = 0

        for root, dirs, _ in os.walk(UPLOAD_DIR):

            for d in list(dirs):

                if d == "__pycache__":

                    shutil.rmtree(
                        os.path.join(root, d),
                        ignore_errors=True
                    )

                    dirs.remove(d)
                    removed += 1

        return (
            f"{pe(PE_CHECK, '🧼')} "
            f"<b>__pycache__ folders removed:</b> {removed}\n\n"
        )

    return ""


def run_broadcast(owner_chat, text):

    sent = 0
    failed = 0

    body = (
        f"{pe(PE_ADMIN, '📢')} "
        f"<b>ANNOUNCEMENT</b>\n\n"
        f"{safe_html(text)}"
    )

    for target in list(users.keys()):

        try:

            bot.send_message(
                target,
                body,
                parse_mode="HTML"
            )

            sent += 1

        except Exception:

            failed += 1

        time.sleep(0.05)

    try:

        bot.send_message(
            owner_chat,
            (
                f"{pe(PE_CHECK, '✅')} "
                f"<b>BROADCAST FINISHED</b>\n\n"
                f"{pe(PE_USER, '📨')} "
                f"<b>Sent:</b> {sent}\n"
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Failed:</b> {failed}"
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass


def handle_owner_input(message, state):

    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()

    if state.get("mode") == "setlimit":

        target = state.get("target")

        low = text.lower()

        if low in ("unlimited", "inf", "-1"):

            new_limit = -1

        elif text.isdigit():

            new_limit = min(int(text), 100000)

        else:

            bot.send_message(
                chat_id,
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>Send a number</b> (for example "
                    f"<code>5</code>) or <code>unlimited</code>."
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data=f"owner_user_{target}"
                        )
                    ]
                ]),
                parse_mode="HTML"
            )

            return

        if target not in users or target == OWNER_ID:

            owner_waiting.pop(uid, None)

            return

        owner_waiting.pop(uid, None)

        users[target]["max_files"] = new_limit

        save_data()

        t, m = owner_user_view(target)

        bot.send_message(
            chat_id,
            (
                f"{pe(PE_CHECK, '✅')} "
                f"<b>File limit updated:</b> "
                f"{limit_label(target)}\n\n"
                f"{t}"
            ),
            reply_markup=m,
            parse_mode="HTML"
        )

        return

    if state.get("mode") not in ("broadcast", "bc_confirm") or not text:
        return

    text = text[:3500]

    owner_waiting[uid] = {
        "mode": "bc_confirm",
        "text": text
    }

    bot.send_message(
        chat_id,
        (
            f"{pe(PE_ADMIN, '📢')} "
            f"<b>BROADCAST PREVIEW</b>\n\n"
            f"{safe_html(text)}\n\n"
            f"{pe(PE_WARNING, '⚠️')} "
            f"Send to <b>{len(users)}</b> users?"
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Send Now",
                    callback_data="owner_bcsend"
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="owner_cancel"
                )
            ]
        ]),
        parse_mode="HTML"
    )


# ============================================================
# START COMMAND
# ============================================================

# ============================================================
# ADMIN PANEL (OWNER ONLY)
# ============================================================

def admin_text():

    total_users = len(users)

    approved_users = sum(
        1 for u in users.values()
        if u.get("approved", False)
    )

    pending_users = sum(
        1 for u in users.values()
        if not u.get("approved", False)
        and not u.get("rejected", False)
    )

    total_files = sum(
        len(u.get("files", []))
        for u in users.values()
    )

    running = sum(
        len(active_scripts.get(user_id, {}))
        for user_id in users
    )

    return (
        f"{pe(PE_ADMIN, '👑')} "
        f"<b>ADMIN PANEL</b>\n\n"

        f"{pe(PE_USER, '👥')} "
        f"<b>Total Users:</b> {total_users}\n"

        f"{pe(PE_CHECK, '✅')} "
        f"<b>Approved:</b> {approved_users}\n"

        f"{pe(PE_WARNING, '⏳')} "
        f"<b>Pending:</b> {pending_users}\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Total Files:</b> {total_files}\n"

        f"{pe(PE_SERVER, '🟢')} "
        f"<b>Running Scripts:</b> {running}\n"

        f"⏱️ <b>Uptime:</b> {uptime()}"
    )


def admin_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👥 All Users",
                callback_data="adm_users"
            ),
            InlineKeyboardButton(
                "⏳ Pending Users",
                callback_data="adm_pending"
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 Running Scripts",
                callback_data="adm_running"
            )
        ],
        [
            InlineKeyboardButton(
                "⏹ Stop All Scripts",
                callback_data="adm_stopall"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="adm_home"
            )
        ]
    ])


def admin_back_markup():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="adm_home"
            )
        ]
    ])


def send_admin_panel(chat_id):

    bot.send_message(
        chat_id,
        admin_text(),
        reply_markup=admin_markup(),
        parse_mode="HTML"
    )


# ============================================================
# KEEP-ALIVE HTTP SERVER (needed for Render Web Services)
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"DK HOSTING BOT IS RUNNING")

    def do_HEAD(self):

        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def start_keepalive_server():

    port = int(os.environ.get("PORT", "10000"))

    try:

        server = HTTPServer(
            ("0.0.0.0", port),
            KeepAliveHandler
        )

        threading.Thread(
            target=server.serve_forever,
            daemon=True
        ).start()

        print(f"Keep-alive server on port {port}")

    except Exception as e:

        print(f"Keep-alive server error: {e}")


@bot.message_handler(commands=["emojitest"])
def emojitest_command(message):

    if message.from_user.id == OWNER_ID:
        emoji_self_test(message.from_user.id)


@bot.message_handler(
    commands=["start"]
)
def start_command(message):

    uid = message.from_user.id

    first_name = (
        message.from_user.first_name
        or "User"
    )

    is_new = uid not in users

    ensure_user(uid)

    users[uid]["name"] = first_name
    save_data()

    env_waiting_users.pop(uid, None)

    # Owner always has access
    if uid == OWNER_ID:

        users[uid]["approved"] = True
        users[uid]["rejected"] = False

        save_data()

    # New users need owner approval
    if is_new and uid != OWNER_ID:

        send_approval_request(message)

        bot.send_message(
            uid,
            (
                f"{pe(PE_LOCK, '🔐')} "
                f"<b>ACCESS REQUESTED</b>\n\n"

                f"{pe(PE_USER, '👤')} "
                f"Welcome, "
                f"<b>{safe_html(first_name)}</b>!\n\n"

                f"{pe(PE_ADMIN, '👑')} "
                f"Your access request has been "
                f"sent to the owner.\n\n"

                f"{pe(PE_STAR, '⭐')} "
                f"<b>Please wait for approval.</b>"
            ),
            parse_mode="HTML"
        )

        return

    if not is_approved(uid):

        bot.send_message(
            uid,
            (
                f"{pe(PE_LOCK, '🔐')} "
                f"<b>ACCESS PENDING</b>\n\n"

                f"Your account is waiting for "
                f"<b>Owner Approval</b>.\n\n"

                f"{pe(PE_STAR, '⭐')} "
                f"Please wait."
            ),
            parse_mode="HTML"
        )

        return

    welcome = (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ {pe(PE_ROCKET, '🚀')} "
        f"<b>DK HOSTING BOT</b> ┃\n"
        f"┃ <b>VERSION 0.3</b> ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"

        f"{pe(PE_GIFT, '👤')} "
        f"<b>Wᴇʟᴄᴏᴍᴇ</b> "
        f"{safe_html(first_name)}!\n\n"

        f"{pe(PE_PHONE, '🆔')} "
        f"<b>Uꜱᴇʀ ID:</b> "
        f"<code>{uid}</code>\n\n"

        f"{pe(PE_FOLDER, '📁')} "
        f"<b>Fɪʟᴇꜱ:</b> "
        f"{len(users[uid]['files'])}\n\n"

        f"{pe(PE_STAR, '⚡')} "
        f"<b>Fᴇᴀᴛᴜʀᴇꜱ:</b>\n"

        f"• {pe(PE_CHECK, '✅')} "
        f"Aᴜᴛᴏ-Rᴇᴄᴏᴠᴇʀʏ Sʏꜱᴛᴇᴍ\n"

        f"• {pe(PE_BOT, '🤖')} "
        f"Pʏᴛʜᴏɴ / Jꜱ / Zɪᴘ Sᴜᴘᴘᴏʀᴛ\n"

        f"• {pe(PE_DIAMOND, '💎')} "
        f"Pʀᴇᴍɪᴜᴍ Eᴍᴏᴊɪ Sʏꜱᴛᴇᴍ\n\n"

        f"Uꜱᴇ ᴛʜᴇ Bᴜᴛᴛᴏɴs Bᴇʟᴏᴡ."
    )

    bot.send_message(
        uid,
        welcome,
        reply_markup=control_buttons(uid),
        parse_mode="HTML"
    )

    notify_owner(
        f"<b>User Started Bot</b>\n"
        f"👤 <code>{uid}</code>\n"
        f"Name: {safe_html(first_name)}",
        0
    )


# ============================================================
# TEXT / CONTROL BUTTON HANDLER
# ============================================================

@bot.message_handler(func=lambda message: True, content_types=["text"])
def control_handler(message):

    uid = message.from_user.id
    text = (message.text or "").strip()

    ensure_user(uid)

    if approval_required(message):
        return

    user_data = users[uid]

    # --------------------------------------------------------
    # PENDING .ENV INPUT
    # --------------------------------------------------------

    if is_menu_button(text):

        install_waiting_users.pop(uid, None)
        owner_waiting.pop(uid, None)
        env_waiting_users.pop(uid, None)

    if uid in install_waiting_users:

        handle_manual_install_input(message)

        return

    if uid in owner_waiting and is_owner(uid):

        handle_owner_input(
            message,
            owner_waiting[uid]
        )

        return

    if uid in env_waiting_users:

        handle_env_input(
            message,
            env_waiting_users[uid]
        )

        return

    # --------------------------------------------------------
    # UPLOAD
    # --------------------------------------------------------

    if text.startswith("👑") and is_owner(uid):

        send_owner_panel(message.chat.id)

    elif text.startswith("🌏"):

        bot.reply_to(
            message,
            (
                f"{pe(PE_UPLOAD, '⬆️')} "
                f"<b>UPLOAD YOUR FILE</b>\n\n"

                f"{pe(PE_FOLDER, '📁')} "
                f"Send your <b>.py</b>, <b>.zip</b> or "
                f"<b>requirements.txt</b> file "
                f"directly in this chat.\n\n"

                f"{pe(PE_STAR, '⭐')} "
                f"After uploading you can configure "
                f"<b>.env</b> variables or run it directly."
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # RECOMMENDED INSTALL
    # --------------------------------------------------------

    elif text.startswith("⚙"):

        bot.reply_to(
            message,
            pkg_menu_text(),
            reply_markup=pkg_menu_markup(),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # MY FILES
    # --------------------------------------------------------

    elif text.startswith("📁"):

        files = user_data["files"]

        if not files:

            bot.reply_to(
                message,
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>No files.</b>"
                ),
                parse_mode="HTML"
            )

            return

        buttons = [
            [
                InlineKeyboardButton(
                    f"📄 {f}",
                    callback_data=f"file_{f}"
                )
            ]
            for f in files
        ]

        bot.reply_to(
            message,
            (
                f"{pe(PE_FOLDER, '📁')} "
                f"<b>𝐘𝐨𝐮𝐫 𝐅𝐢𝐥𝐞𝐬:</b>"
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # SPEED
    # --------------------------------------------------------

    elif text.startswith("⚡"):

        start_time = time.time()

        time.sleep(0.1)

        processing_time = (
            time.time() - start_time
        )

        cpu_ghz, total_ram_gb, free_ram_gb = (
            get_system_info()
        )

        bot.reply_to(
            message,
            (
                f"{pe(PE_FIRE, '⚡')} "
                f"<b>BOT SPEED</b>\n\n"

                f"⏱️ <b>Response:</b> "
                f"{round(processing_time, 4)} sec\n\n"

                f"⚙️ <b>CPU:</b> "
                f"{round(cpu_ghz, 2)} GHz\n"

                f"💾 <b>RAM:</b> "
                f"{round(total_ram_gb, 2)} GB\n"

                f"🟢 <b>FREE:</b> "
                f"{round(free_ram_gb, 2)} GB"
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # RESTART
    # --------------------------------------------------------

    elif text.startswith("🔄"):

        if uid in active_scripts:

            for p in list(
                active_scripts[uid].values()
            ):

                kill_process_tree(p)

            active_scripts[uid] = {}

        folder = user_folder(uid)

        for fname in user_data["files"]:

            if fname.endswith(".py"):

                path = os.path.join(
                    folder,
                    fname
                )

                if os.path.exists(path):

                    start_script(
                        uid,
                        path
                    )

        bot.reply_to(
            message,
            (
                f"{pe(PE_ROCKET, '🔄')} "
                f"<b>All your scripts have "
                f"been restarted.</b>"
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    elif text.startswith("⏹"):

        if uid in active_scripts:

            for p in list(
                active_scripts[uid].values()
            ):

                kill_process_tree(p)

            active_scripts[uid] = {}

        bot.reply_to(
            message,
            (
                f"{pe(PE_SHIELD, '⏹')} "
                f"<b>Stopped all your scripts.</b>"
            ),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    elif text.startswith("🚀"):

        total_users = len(users)

        total_files = sum(
            len(u.get("files", []))
            for u in users.values()
            if u
        )

        running_scripts = sum(
            len(
                active_scripts.get(
                    user_id,
                    {}
                )
            )
            for user_id in users
        )

        approved_users = sum(
            1
            for u in users.values()
            if u.get("approved", False)
        )

        pending_users = sum(
            1
            for u in users.values()
            if (
                not u.get(
                    "approved",
                    False
                )
                and not u.get(
                    "rejected",
                    False
                )
            )
        )

        uptime_seconds = (
            datetime.now() - START_TIME
        ).total_seconds()

        hours, remainder = divmod(
            int(uptime_seconds),
            3600
        )

        minutes, seconds = divmod(
            remainder,
            60
        )

        bot.reply_to(
            message,
            (
                f"📊 <b>LIVE STATISTICS</b>\n\n"

                f"👥 <b>Total Users:</b> "
                f"{total_users}\n"

                f"✅ <b>Approved Users:</b> "
                f"{approved_users}\n"

                f"⏳ <b>Pending Users:</b> "
                f"{pending_users}\n"

                f"📁 <b>Total Files:</b> "
                f"{total_files}\n"

                f"🟢 <b>Running Scripts:</b> "
                f"{running_scripts}\n"

                f"🔒 <b>Bot Status:</b> "
                f"{pe(PE_CHECK, '🟢')} "
                f"<b>ONLINE</b>\n\n"

                f"⏱️ <b>Uptime:</b> "
                f"{hours}h "
                f"{minutes}m "
                f"{seconds}s"
            ),
            parse_mode="HTML"
        )


# ============================================================
# DOCUMENT / FILE HANDLER
# ============================================================

def env_choice_markup(filename):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚙️ Configure .env Variables",
                callback_data=f"envmenu_{filename}"
            )
        ],
        [
            InlineKeyboardButton(
                "▶️ Skip & Run Directly",
                callback_data=f"skiprun_{filename}"
            )
        ]
    ])


def env_choice_text(filename, extra=""):

    return (
        f"{extra}"
        f"{pe(PE_CHECK, '✅')} "
        f"<b>File ready:</b> "
        f"<code>{safe_html(filename)}</code>\n\n"

        f"{pe(PE_SETTINGS, '⚙️')} "
        f"<b>Do you want to configure "
        f".env variables before running?</b>\n\n"

        f"{pe(PE_LOCK, '🔐')} "
        f"Set <code>BOT_TOKEN</code>, "
        f"<code>ADMIN_ID</code>, "
        f"<code>API_ID</code> / <code>API_HASH</code> "
        f"or any custom variable.\n\n"

        f"{pe(PE_ROCKET, '🚀')} "
        f"Or skip and run it right away."
    )


@bot.message_handler(
    content_types=["document"]
)
def document_handler(message):

    uid = message.from_user.id

    ensure_user(uid)

    if approval_required(message):
        return

    user_data = users[uid]

    # File limit for normal users
    file_limit = get_file_limit(uid)

    if (
        file_limit is not None
        and len(user_data["files"]) >= file_limit
    ):

        bot.reply_to(
            message,
            (
                f"{pe(PE_WARNING, '⚠️')} "
                f"<b>You have reached the limit "
                f"of {file_limit} files.</b>\n\n"
                f"Contact the owner for more."
            ),
            parse_mode="HTML"
        )

        return

    doc = message.document

    filename = os.path.basename(doc.file_name or "")

    # Allowed file types
    if not filename.lower().endswith(
        (".py", ".zip", ".txt")
    ):

        bot.reply_to(
            message,
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Only .py, .zip and .txt "
                f"files are allowed.</b>"
            ),
            parse_mode="HTML"
        )

        return

    folder = user_folder(uid)

    save_path = os.path.join(
        folder,
        filename
    )

    msg = bot.reply_to(
        message,
        (
            f"{pe(PE_UPLOAD, '⬇️')} "
            f"<b>Downloading...</b>"
        ),
        parse_mode="HTML"
    )

    try:

        file_info = bot.get_file(
            doc.file_id
        )

        downloaded_file = bot.download_file(
            file_info.file_path
        )

        # Stop any running copy before overwriting
        stop_script(uid, save_path)

        with open(
            save_path,
            "wb"
        ) as f:

            f.write(
                downloaded_file
            )

    except Exception as e:

        bot.edit_message_text(
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>Download failed.</b>\n\n"
                f"<code>{safe_html(e)}</code>"
            ),
            chat_id=message.chat.id,
            message_id=msg.message_id,
            parse_mode="HTML"
        )

        return

    if filename not in user_data["files"]:

        user_data["files"].append(
            filename
        )

        save_data()

    # --------------------------------------------------------
    # ZIP FILE
    # --------------------------------------------------------

    if filename.lower().endswith(".zip"):

        try:

            py_files = []

            base = os.path.abspath(folder)

            with zipfile.ZipFile(
                save_path,
                "r"
            ) as zip_ref:

                for member in zip_ref.namelist():

                    target = os.path.abspath(
                        os.path.join(folder, member)
                    )

                    # Block path traversal
                    if not (
                        target == base
                        or target.startswith(base + os.sep)
                    ):
                        continue

                    zip_ref.extract(member, folder)

                    if (
                        not member.endswith("/")
                        and member.lower().endswith(".py")
                    ):
                        py_files.append(member)

            py_files = scan_py_files(folder) or py_files

            for pf in py_files:

                if pf not in user_data["files"]:
                    user_data["files"].append(pf)

            save_data()

            if py_files:

                preferred = [
                    "main.py", "bot.py", "app.py",
                    "run.py", "start.py", "__main__.py"
                ]

                main_file = None

                for cand in preferred:

                    for pf in py_files:

                        if pf.lower() == cand:
                            main_file = pf
                            break

                    if main_file:
                        break

                if not main_file:

                    for pf in py_files:

                        for cand in preferred:

                            if pf.lower().endswith("/" + cand):
                                main_file = pf
                                break

                        if main_file:
                            break

                if not main_file:
                    main_file = py_files[0]

                extra = (
                    f"{pe(PE_CHECK, '📦')} "
                    f"<b>ZIP extracted successfully.</b>\n"
                    f"{pe(PE_FOLDER, '📁')} "
                    f"<b>{len(py_files)}</b> Python file(s) "
                    f"added to 📁 My Files.\n\n"
                    + req_note(folder)
                )

                bot.edit_message_text(
                    env_choice_text(main_file, extra),
                    chat_id=message.chat.id,
                    message_id=msg.message_id,
                    reply_markup=zip_markup(folder, main_file),
                    parse_mode="HTML"
                )

            else:

                bot.edit_message_text(
                    (
                        f"{pe(PE_CHECK, '📦')} "
                        f"<b>ZIP extracted "
                        f"successfully.</b>"
                    ),
                    reply_markup=(
                        req_buttons(find_requirements(folder))
                        if find_requirements(folder)
                        else None
                    ),
                    chat_id=message.chat.id,
                    message_id=msg.message_id,
                    parse_mode="HTML"
                )

        except Exception as e:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>ZIP extraction failed.</b>\n\n"
                    f"<code>{safe_html(e)}</code>"
                ),
                chat_id=message.chat.id,
                message_id=msg.message_id,
                parse_mode="HTML"
            )

    # --------------------------------------------------------
    # TXT / REQUIREMENTS
    # --------------------------------------------------------

    elif filename.lower().endswith(".txt"):

        bot.edit_message_text(
            req_prompt_text(filename),
            chat_id=message.chat.id,
            message_id=msg.message_id,
            reply_markup=req_buttons(filename),
            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # PYTHON FILE
    # --------------------------------------------------------

    elif filename.lower().endswith(".py"):

        bot.edit_message_text(
            env_choice_text(filename),
            chat_id=message.chat.id,
            message_id=msg.message_id,
            reply_markup=env_choice_markup(filename),
            parse_mode="HTML"
        )

    notify_owner(
        (
            f"<b>File Uploaded</b>\n"
            f"{pe(PE_USER, '👤')} "
            f"User: <code>{uid}</code>\n"
            f"{pe(PE_FOLDER, '📁')} "
            f"File: <code>"
            f"{safe_html(filename)}"
            f"</code>"
        ),
        1
    )


# ============================================================
# CALLBACK QUERY
# ============================================================

def show_myfiles(call):

    uid = call.from_user.id

    files = users[uid]["files"]

    if not files:

        bot.edit_message_text(
            (
                f"{pe(PE_CROSS, '❌')} "
                f"<b>No files.</b>"
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )

        return

    buttons = [
        [
            InlineKeyboardButton(
                f"📄 {f}",
                callback_data=f"file_{f}"
            )
        ]
        for f in files
    ]

    bot.edit_message_text(
        (
            f"{pe(PE_FOLDER, '📁')} "
            f"<b>𝐘𝐨ᴜʀ 𝐅ɪ𝐥ᴇs:</b>"
        ),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
        parse_mode="HTML"
    )


@bot.callback_query_handler(
    func=lambda call: True
)
def callback_query(call):

    uid = call.from_user.id

    ensure_user(uid)

    data = call.data or ""

    # --------------------------------------------------------
    # APPROVE USER
    # --------------------------------------------------------

    if data.startswith("approve_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        try:

            target_id = int(
                data.split(
                    "_",
                    1
                )[1]
            )

        except:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid user ID."
            )

            return

        ensure_user(
            target_id
        )

        users[target_id]["approved"] = True
        users[target_id]["rejected"] = False

        save_data()

        bot.answer_callback_query(
            call.id,
            "✅ User Approved!"
        )

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_APPROVE, '✅')} "
                    f"<b>USER APPROVED</b>\n\n"

                    f"{pe(PE_USER, '👤')} "
                    f"<b>User ID:</b> "
                    f"<code>{target_id}</code>\n\n"

                    f"{pe(PE_ADMIN, '👑')} "
                    f"Approved by Owner."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )

        except:
            pass

        try:

            bot.send_message(
                target_id,
                (
                    f"{pe(PE_GIFT, '🎁')} "
                    f"<b>ACCESS APPROVED!</b>\n\n"

                    f"{pe(PE_CHECK, '✅')} "
                    f"Your account has been "
                    f"approved by the owner.\n\n"

                    f"{pe(PE_ROCKET, '🚀')} "
                    f"You can now use "
                    f"<b>DK HOSTING BOT</b>."
                ),
                reply_markup=control_buttons(),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                f"Approval notification error: {e}"
            )

        return

    # --------------------------------------------------------
    # REJECT USER
    # --------------------------------------------------------

    if data.startswith("reject_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        try:

            target_id = int(
                data.split(
                    "_",
                    1
                )[1]
            )

        except:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid user ID."
            )

            return

        ensure_user(
            target_id
        )

        users[target_id]["approved"] = False
        users[target_id]["rejected"] = True

        save_data()

        bot.answer_callback_query(
            call.id,
            "❌ User Rejected!"
        )

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>USER REJECTED</b>\n\n"

                    f"{pe(PE_USER, '👤')} "
                    f"<b>User ID:</b> "
                    f"<code>{target_id}</code>\n\n"

                    f"{pe(PE_ADMIN, '👑')} "
                    f"Rejected by Owner."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )

        except:
            pass

        try:

            bot.send_message(
                target_id,
                (
                    f"{pe(PE_CROSS, '❌')} "
                    f"<b>ACCESS REJECTED</b>\n\n"
                    f"Your request was rejected "
                    f"by the owner."
                ),
                parse_mode="HTML"
            )

        except:
            pass

        return

    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if data.startswith("adm_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        def adm_edit(text, markup):

            try:

                bot.edit_message_text(
                    text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )

            except Exception:
                pass

        if data == "adm_home":

            adm_edit(admin_text(), admin_markup())

        elif data == "adm_users":

            lines = []

            for u_id, u in users.items():

                status = (
                    "👑" if u_id == OWNER_ID
                    else "✅" if u.get("approved")
                    else "❌" if u.get("rejected")
                    else "⏳"
                )

                lines.append(
                    f"{status} <code>{u_id}</code> — "
                    f"{len(u.get('files', []))} files, "
                    f"{len(active_scripts.get(u_id, {}))} running"
                )

            body = "\n".join(lines[:60]) or "No users."

            adm_edit(
                f"{pe(PE_USER, '👥')} <b>ALL USERS</b>\n\n{body}",
                admin_back_markup()
            )

        elif data == "adm_pending":

            pending = [
                u_id for u_id, u in users.items()
                if not u.get("approved", False)
                and not u.get("rejected", False)
            ]

            if not pending:

                adm_edit(
                    f"{pe(PE_CHECK, '✅')} <b>No pending users.</b>",
                    admin_back_markup()
                )

            else:

                adm_edit(
                    f"{pe(PE_WARNING, '⏳')} "
                    f"<b>{len(pending)} pending user(s) below.</b>",
                    admin_back_markup()
                )

                for u_id in pending[:20]:

                    bot.send_message(
                        call.message.chat.id,
                        f"{pe(PE_USER, '👤')} "
                        f"<b>User ID:</b> <code>{u_id}</code>",
                        reply_markup=approval_buttons(u_id),
                        parse_mode="HTML"
                    )

        elif data == "adm_running":

            lines = []

            for u_id, procs in active_scripts.items():

                for p in procs:

                    lines.append(
                        f"🟢 <code>{u_id}</code> — "
                        f"<code>{safe_html(os.path.basename(p))}</code>"
                    )

            body = "\n".join(lines[:60]) or "No scripts running."

            adm_edit(
                f"{pe(PE_SERVER, '🟢')} <b>RUNNING SCRIPTS</b>\n\n{body}",
                admin_back_markup()
            )

        elif data == "adm_stopall":

            for u_id in list(active_scripts.keys()):

                for p in list(active_scripts[u_id].keys()):
                    stop_script(u_id, p)

            adm_edit(
                f"{pe(PE_SHIELD, '⏹')} <b>All scripts stopped.</b>",
                admin_back_markup()
            )

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # APPROVAL CHECK
    # --------------------------------------------------------

    if not is_approved(uid):

        bot.answer_callback_query(
            call.id,
            "🔐 Owner approval required."
        )

        return

    # --------------------------------------------------------
    # PACKAGE INSTALLER (MANUAL)
    # --------------------------------------------------------

    if data in ("pkg_menu", "pkg_cancel"):

        install_waiting_users.pop(uid, None)

        edit_call(call, pkg_menu_text(), pkg_menu_markup())

        bot.answer_callback_query(call.id)

        return

    if data == "manual_pkg_input":

        install_waiting_users[uid] = True

        edit_call(
            call,
            (
                f"{pe(PE_STAR, '✍️')} "
                f"<b>MANUAL PACKAGE INSTALL</b>\n\n"
                f"Send the package name(s) now.\n"
                f"Example:\n"
                f"<pre>pyrogram\nrequests aiohttp</pre>"
            ),
            pkg_cancel_markup()
        )

        bot.answer_callback_query(call.id)

        return

    if data == "rec_pkg_list":

        install_waiting_users.pop(uid, None)

        edit_call(
            call,
            (
                f"{pe(PE_DIAMOND, '📋')} "
                f"<b>RECOMMENDED PACKAGES</b>\n\n"
                f"Tap a package to install "
                f"<b>only that one</b>."
            ),
            rec_list_markup()
        )

        bot.answer_callback_query(call.id)

        return

    if data.startswith("recpkg_"):

        name = data[len("recpkg_"):]

        if name == "pytgcalls":

            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                PYTG_CALLS_PACKAGE
            ]

            desc = "pytgcalls (GitHub)"

        elif name in RECOMMENDED_PACKAGES:

            cmd = pip_cmd(name)
            desc = name

        else:

            bot.answer_callback_query(
                call.id,
                "❌ Unknown package."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(cmd, desc)]
        )

        bot.answer_callback_query(
            call.id,
            f"📦 Installing {name}"
        )

        return

    # --------------------------------------------------------
    # REQUIREMENTS.TXT INSTALL
    # --------------------------------------------------------

    if data.startswith("reqinstall_"):

        rel = data[len("reqinstall_"):]

        path = safe_user_path(uid, rel)

        if not path or not os.path.isfile(path):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    path
                ],
                rel
            )]
        )

        bot.answer_callback_query(
            call.id,
            "📦 Installing requirements..."
        )

        return

    if data.startswith("reqselect_"):

        rel = data[len("reqselect_"):]

        path = safe_user_path(uid, rel)

        if not path or not os.path.isfile(path):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        pkgs = parse_requirements_file(path)

        if not pkgs:

            bot.answer_callback_query(
                call.id,
                "❌ No packages found in file."
            )

            return

        req_select_store[uid] = {
            "rel": rel,
            "pkgs": pkgs
        }

        rows = [
            [
                InlineKeyboardButton(
                    f"📦 {p[:40]}",
                    callback_data=(
                        f"pkginst_{p}"
                        if len(f"pkginst_{p}".encode()) <= 64
                        else f"reqpkg_{i}"
                    )
                )
            ]
            for i, p in enumerate(pkgs)
        ]

        rows.append([
            InlineKeyboardButton(
                "⬅ Back",
                callback_data=f"reqback_{rel}"
            )
        ])

        edit_call(
            call,
            (
                f"{pe(PE_SERVER, '☑️')} "
                f"<b>SELECT PACKAGES</b>\n"
                f"<code>{safe_html(rel)}</code>\n\n"
                f"Tap a package to install "
                f"<b>only that one</b>."
            ),
            InlineKeyboardMarkup(rows)
        )

        bot.answer_callback_query(call.id)

        return

    if data.startswith("reqback_"):

        rel = data[len("reqback_"):]

        edit_call(call, req_prompt_text(rel), req_buttons(rel))

        bot.answer_callback_query(call.id)

        return

    if data.startswith("pkginst_"):

        spec = data[len("pkginst_"):]

        if not spec or not PKG_NAME_RE.match(spec):

            bot.answer_callback_query(
                call.id,
                "❌ Invalid package."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(pip_cmd(spec), spec)]
        )

        bot.answer_callback_query(
            call.id,
            f"📦 Installing {spec[:40]}"
        )

        return

    if data.startswith("reqpkg_"):

        try:
            idx = int(data[len("reqpkg_"):])
            pkg = req_select_store[uid]["pkgs"][idx]
        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ List expired. Select again."
            )

            return

        install_in_thread(
            call.message.chat.id,
            [(pip_cmd(pkg), pkg)]
        )

        bot.answer_callback_query(
            call.id,
            "📦 Installing..."
        )

        return

    # --------------------------------------------------------
    # OWNER PANEL
    # --------------------------------------------------------

    if data.startswith("owner_"):

        if uid != OWNER_ID:

            bot.answer_callback_query(
                call.id,
                "❌ Owner only!"
            )

            return

        if data != "owner_bcsend":
            pass

        if data == "owner_home":

            owner_waiting.pop(uid, None)

            edit_call(call, owner_text(), owner_markup())

        elif data == "owner_users":

            t, m = owner_users_view()

            edit_call(call, t, m)

        elif data.startswith("owner_user_"):

            try:
                target = int(data[len("owner_user_"):])
            except Exception:
                target = None

            t, m = owner_user_view(target)

            if t is None:

                bot.answer_callback_query(
                    call.id,
                    "❌ User not found."
                )

                return

            edit_call(call, t, m)

        elif data.startswith("owner_files_"):

            target = int(data[len("owner_files_"):])

            t, m = owner_files_view(target)

            edit_call(call, t, m)

        elif data.startswith("owner_ban_"):

            target = int(data[len("owner_ban_"):])

            if target == OWNER_ID or target not in users:

                bot.answer_callback_query(
                    call.id,
                    "❌ Not allowed."
                )

                return

            users[target]["approved"] = False
            users[target]["rejected"] = True

            for p in list(active_scripts.get(target, {}).keys()):
                stop_script(target, p)

            save_data()

            try:

                bot.send_message(
                    target,
                    (
                        f"{pe(PE_CROSS, '🚫')} "
                        f"<b>ACCESS REMOVED</b>\n\n"
                        f"The owner has removed your access."
                    ),
                    parse_mode="HTML"
                )

            except Exception:
                pass

            t, m = owner_user_view(target)

            edit_call(call, t, m)

            bot.answer_callback_query(call.id, "🚫 User banned")

            return

        elif data.startswith("owner_appr_"):

            target = int(data[len("owner_appr_"):])

            ensure_user(target)

            users[target]["approved"] = True
            users[target]["rejected"] = False

            save_data()

            try:

                bot.send_message(
                    target,
                    (
                        f"{pe(PE_GIFT, '🎁')} "
                        f"<b>ACCESS APPROVED!</b>\n\n"
                        f"You can use <b>DK HOSTING BOT</b> now."
                    ),
                    reply_markup=control_buttons(),
                    parse_mode="HTML"
                )

            except Exception:
                pass

            t, m = owner_user_view(target)

            edit_call(call, t, m)

            bot.answer_callback_query(call.id, "✅ User approved")

            return

        elif data.startswith("owner_setlim_"):

            try:
                target = int(data[len("owner_setlim_"):])
            except Exception:
                target = None

            if target not in users or target == OWNER_ID:

                bot.answer_callback_query(
                    call.id,
                    "❌ Not allowed."
                )

                return

            owner_waiting[uid] = {
                "mode": "setlimit",
                "target": target
            }

            edit_call(
                call,
                (
                    f"{pe(PE_GIFT, '📈')} "
                    f"<b>CHANGE FILE LIMIT</b>\n\n"
                    f"{pe(PE_PHONE, '🆔')} "
                    f"<b>User:</b> <code>{target}</code>\n"
                    f"{pe(PE_FOLDER, '📁')} "
                    f"<b>Current:</b> {limit_label(target)}\n\n"
                    f"Send the new maximum number of files, "
                    f"or <code>unlimited</code>."
                ),
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data=f"owner_user_{target}"
                        )
                    ]
                ])
            )

        elif data.startswith("owner_lim_"):

            rest = data[len("owner_lim_"):]

            target_s, op = rest.rsplit("_", 1)

            target = int(target_s)

            if target == OWNER_ID or target not in users:

                bot.answer_callback_query(
                    call.id,
                    "❌ Not allowed."
                )

                return

            cur = get_file_limit(target)

            if op == "inc":

                new = 1 if cur is None else cur + 1

                if cur is None:
                    new = -1

            elif op == "dec":

                new = -1 if cur is None else max(0, cur - 1)

            elif op == "unl":

                new = -1

            else:

                new = 2

            users[target]["max_files"] = new

            save_data()

            t, m = owner_user_view(target)

            edit_call(call, t, m)

            bot.answer_callback_query(
                call.id,
                f"📦 Limit: {limit_label(target)}"
            )

            return

        elif data == "owner_running":

            t, m = owner_running_view()

            edit_call(call, t, m)

        elif data.startswith("owner_fstop_"):

            try:

                idx = int(data[len("owner_fstop_"):])

                u_id, p = owner_run_cache[idx]

                stopped = stop_script(u_id, p)

            except Exception:

                stopped = False

            bot.answer_callback_query(
                call.id,
                "⏹ Stopped" if stopped else "❌ Not running"
            )

            t, m = owner_running_view()

            edit_call(call, t, m)

            return

        elif data == "owner_stopall":

            for u_id in list(active_scripts.keys()):

                for p in list(active_scripts[u_id].keys()):
                    stop_script(u_id, p)

            t, m = owner_running_view()

            edit_call(call, t, m)

            bot.answer_callback_query(call.id, "⏹ All stopped")

            return

        elif data == "owner_broadcast":

            owner_waiting[uid] = {"mode": "broadcast"}

            edit_call(
                call,
                (
                    f"{pe(PE_ADMIN, '📢')} "
                    f"<b>BROADCAST MESSAGE</b>\n\n"
                    f"Send the message you want to deliver to "
                    f"all <b>{len(users)}</b> users."
                ),
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data="owner_cancel"
                        )
                    ]
                ])
            )

        elif data == "owner_bcsend":

            state = owner_waiting.pop(uid, None)

            if not state or state.get("mode") != "bc_confirm":

                bot.answer_callback_query(
                    call.id,
                    "❌ Nothing to send."
                )

                return

            threading.Thread(
                target=run_broadcast,
                args=(call.message.chat.id, state["text"]),
                daemon=True
            ).start()

            edit_call(
                call,
                (
                    f"{pe(PE_ROCKET, '📢')} "
                    f"<b>Broadcast started...</b>"
                ),
                owner_back_markup()
            )

            bot.answer_callback_query(call.id, "📢 Sending")

            return

        elif data == "owner_cancel":

            owner_waiting.pop(uid, None)

            edit_call(call, owner_text(), owner_markup())

            bot.answer_callback_query(call.id, "Cancelled")

            return

        elif data == "owner_cleanup":

            t, m = owner_cleanup_view()

            edit_call(call, t, m)

        elif data.startswith("owner_clr_"):

            prefix = do_cleanup(data[len("owner_clr_"):])

            t, m = owner_cleanup_view(prefix)

            edit_call(call, t, m)

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # FILE DETAILS
    # --------------------------------------------------------

    if data.startswith("file_"):

        filename = data[5:]

        env_waiting_users.pop(uid, None)

        user_data = users.get(
            uid,
            {"files": []}
        )

        if filename not in user_data.get(
            "files",
            []
        ):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        user_name = (
            call.from_user.first_name
            or "User"
        )

        path = os.path.join(
            user_folder(uid),
            filename
        )

        running = (
            path in active_scripts.get(
                uid,
                {}
            )
        )

        msg = (
            f"{pe(PE_STAR, '⚡')} "
            f"<b>𝐀𝐜𝐭𝐢𝐨𝐧𝐬 𝐟𝐨𝐫</b>\n"
            f"<code>{safe_html(filename)}</code>\n\n"

            f"{pe(PE_PHONE, '🆔')} "
            f"<b>𝐔𝐬ᴇʀ ID:</b> "
            f"<code>{uid}</code>\n"

            f"{pe(PE_USER, '👤')} "
            f"<b>𝐍ᴀᴍᴇ:</b> "
            f"<code>{safe_html(user_name)}</code>\n"

            f"{pe(PE_CHECK, '🟢')} "
            f"<b>𝐑ᴜɴɴɪɴɢ:</b> "
            f"<code>{1 if running else 0}</code>"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    "▶ Run",
                    callback_data=f"run_{filename}"
                ),
                InlineKeyboardButton(
                    "⏹ Stop",
                    callback_data=f"stop_{filename}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Set / Edit .env",
                    callback_data=f"envmenu_{filename}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📜 Logs",
                    callback_data=f"logs_{filename}"
                ),
                InlineKeyboardButton(
                    "🗑 Delete",
                    callback_data=f"del_{filename}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back",
                    callback_data="myfiles"
                )
            ]
        ]

        try:

            bot.edit_message_text(
                msg,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=InlineKeyboardMarkup(
                    buttons
                ),
                parse_mode="HTML"
            )

        except Exception:
            pass

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # MY FILES BACK BUTTON
    # --------------------------------------------------------

    if data == "myfiles":

        env_waiting_users.pop(uid, None)

        show_myfiles(call)

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # LOGS
    # --------------------------------------------------------

    if data.startswith("logs_"):

        fname = data[5:]

        path = os.path.join(
            user_folder(uid),
            fname
        )

        lines = logs_store.get(uid, {}).get(path, [])[-30:]

        if lines:

            log_text = "\n".join(lines)

            if len(log_text) > 3300:
                log_text = "..." + log_text[-3300:]

        else:

            log_text = "No logs yet."

        running = path in active_scripts.get(uid, {})

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_SERVER, '📜')} "
                    f"<b>LOGS</b>\n"
                    f"<code>{safe_html(fname)}</code>\n"
                    f"{pe(PE_CHECK, '🟢')} "
                    f"<b>Running:</b> "
                    f"<code>{1 if running else 0}</code>\n\n"
                    f"<pre>{safe_html(log_text)}</pre>"
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔄 Refresh",
                            callback_data=f"logs_{fname}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅ Back",
                            callback_data=f"file_{fname}"
                        )
                    ]
                ]),
                parse_mode="HTML"
            )

        except Exception:
            pass

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # DELETE FILE
    # --------------------------------------------------------

    if data.startswith("del_"):

        fname = data[4:]

        if fname not in users[uid]["files"]:

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        path = safe_user_path(uid, fname)

        if not path:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid path."
            )

            return

        stop_script(uid, path)

        try:

            if os.path.isfile(path):
                os.remove(path)

        except Exception as e:

            print(f"Delete error: {e}")

        if fname in users[uid]["files"]:
            users[uid]["files"].remove(fname)

        users[uid].setdefault("env_vars", {}).pop(fname, None)

        logs_store.get(uid, {}).pop(path, None)

        save_data()

        bot.answer_callback_query(
            call.id,
            f"🗑 {fname} deleted"
        )

        notify_owner(
            (
                f"<b>File Deleted</b>\n"
                f"User: <code>{uid}</code>\n"
                f"File: <code>"
                f"{safe_html(fname)}"
                f"</code>"
            ),
            4
        )

        show_myfiles(call)

        return

    # --------------------------------------------------------
    # .ENV MENU
    # --------------------------------------------------------

    if data.startswith("envmenu_"):

        fname = data[len("envmenu_"):]

        env_waiting_users.pop(uid, None)

        if not os.path.exists(
            os.path.join(user_folder(uid), fname)
        ):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        send_env_menu(
            call.message.chat.id,
            uid,
            fname,
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # SET .ENV VARIABLE (ask for input)
    # --------------------------------------------------------

    if data.startswith("setenv_"):

        rest = data[len("setenv_"):]

        mode = None
        fname = None

        for m in ("BOT_TOKEN", "ADMIN_ID", "API", "CUSTOM"):

            if rest.startswith(m + "_"):

                mode = m
                fname = rest[len(m) + 1:]
                break

        if not mode:

            bot.answer_callback_query(
                call.id,
                "❌ Invalid option."
            )

            return

        env_waiting_users[uid] = {
            "mode": mode,
            "filename": fname,
            "step": "API_ID"
        }

        try:

            bot.edit_message_text(
                env_ask_markup_text(mode, fname),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=env_prompt_markup(fname),
                parse_mode="HTML"
            )

        except Exception:

            bot.send_message(
                call.message.chat.id,
                env_ask_markup_text(mode, fname),
                reply_markup=env_prompt_markup(fname),
                parse_mode="HTML"
            )

        bot.answer_callback_query(call.id)

        return

    # --------------------------------------------------------
    # CANCEL .ENV INPUT
    # --------------------------------------------------------

    if data.startswith("cancelenv_"):

        fname = data[len("cancelenv_"):]

        env_waiting_users.pop(uid, None)

        send_env_menu(
            call.message.chat.id,
            uid,
            fname,
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id, "Cancelled")

        return

    # --------------------------------------------------------
    # CLEAR .ENV
    # --------------------------------------------------------

    if data.startswith("clearenv_"):

        fname = data[len("clearenv_"):]

        env_waiting_users.pop(uid, None)

        clear_env_vars(uid, fname)

        send_env_menu(
            call.message.chat.id,
            uid,
            fname,
            prefix=(
                f"{pe(PE_CHECK, '✅')} "
                f"<b>All .env variables cleared.</b>\n\n"
            ),
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id, "🗑 Cleared")

        return

    # --------------------------------------------------------
    # SKIP & RUN / SAVE & RUN
    # --------------------------------------------------------

    if data.startswith("skiprun_"):

        fname = data[len("skiprun_"):]

        env_waiting_users.pop(uid, None)

        path = os.path.join(
            user_folder(uid),
            fname
        )

        if (
            fname not in users[uid]["files"]
            or not os.path.exists(path)
        ):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        if not fname.lower().endswith(".py"):

            bot.answer_callback_query(
                call.id,
                "❌ Only Python files can run."
            )

            return

        # Make python-dotenv pick up this file's variables
        if get_file_env(uid, fname):
            write_env_file(uid, fname)

        start_script(
            uid,
            path
        )

        try:

            bot.edit_message_text(
                (
                    f"{pe(PE_ROCKET, '⚡')} "
                    f"<b>Started "
                    f"{safe_html(fname)}!</b>\n\n"

                    f"{pe(PE_CHECK, '✅')} "
                    f"Your script is now running.\n"
                    f"{pe(PE_SERVER, '📜')} "
                    f"Check output in "
                    f"📁 My Files → Logs."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "📜 Logs",
                            callback_data=f"logs_{fname}"
                        ),
                        InlineKeyboardButton(
                            "⬅ Back",
                            callback_data=f"file_{fname}"
                        )
                    ]
                ]),
                parse_mode="HTML"
            )

        except Exception:
            pass

        bot.answer_callback_query(
            call.id,
            f"▶ {fname} started"
        )

        notify_owner(
            (
                f"<b>Script Started</b>\n"
                f"User: <code>{uid}</code>\n"
                f"File: <code>"
                f"{safe_html(fname)}"
                f"</code>"
            ),
            2
        )

        return

    # --------------------------------------------------------
    # RUN FILE
    # --------------------------------------------------------

    if data.startswith("run_"):

        fname = data[4:]

        if fname not in users[uid]["files"]:

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        path = os.path.join(
            user_folder(uid),
            fname
        )

        if not os.path.exists(path):

            bot.answer_callback_query(
                call.id,
                "❌ File not found."
            )

            return

        if not fname.lower().endswith(".py"):

            bot.answer_callback_query(
                call.id,
                "❌ Only Python files can run."
            )

            return

        if get_file_env(uid, fname):
            write_env_file(uid, fname)

        start_script(
            uid,
            path
        )

        bot.answer_callback_query(
            call.id,
            f"▶ {fname} started"
        )

        notify_owner(
            (
                f"<b>Script Started</b>\n"
                f"User: <code>{uid}</code>\n"
                f"File: <code>"
                f"{safe_html(fname)}"
                f"</code>"
            ),
            2
        )

        return

    # --------------------------------------------------------
    # STOP FILE
    # --------------------------------------------------------

    if data.startswith("stop_"):

        fname = data[5:]

        path = os.path.join(
            user_folder(uid),
            fname
        )

        if stop_script(uid, path):

            bot.answer_callback_query(
                call.id,
                f"⏹ {fname} stopped"
            )

            notify_owner(
                (
                    f"<b>Script Stopped</b>\n"
                    f"User: <code>{uid}</code>\n"
                    f"File: <code>"
                    f"{safe_html(fname)}"
                    f"</code>"
                ),
                3
            )

        else:

            bot.answer_callback_query(
                call.id,
                "❌ Script not running"
            )

        return


# ============================================================
# RESTORE ALL SCRIPTS
# ============================================================

def restore_all():

    load_data()

    print(
        "🔄 Restoring scripts..."
    )

    for uid, data in users.items():

        if (
            uid != OWNER_ID
            and not data.get(
                "approved",
                False
            )
        ):
            continue

        folder = user_folder(uid)

        for f in data.get(
            "files",
            []
        ):

            if f.endswith(".py"):

                path = os.path.join(
                    folder,
                    f
                )

                if os.path.exists(path):

                    start_script(
                        uid,
                        path
                    )

    print(
        "✅ System Ready"
    )


# ============================================================
# BOT START
# ============================================================

if __name__ == "__main__":

    print(
        "=================================================="
    )

    print(
        "🔧 DK HOSTING BOT"
    )

    print(
        "=================================================="
    )

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN is not configured!"
        )

        print(
            "Set BOT_TOKEN in Render Environment Variables."
        )

        sys.exit(1)

    start_keepalive_server()

    restore_all()

    print(
        "DK HOSTING BOT IS RUNNING 🏃"
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=60,
        long_polling_timeout=60
    )
