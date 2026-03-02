import discord
from discord.ext import commands, tasks
import yfinance as yf
import datetime
import asyncio
import requests
from email.utils import parsedate_to_datetime
import logging
import os
from dotenv import load_dotenv

# 載入 .env 檔案 (在 Railway 上執行時，這行不會報錯，會自動去抓 Railway 後台的變數)
load_dotenv()

# 關閉 yfinance 煩人的警告訊息
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# ================= 設定區 =================

# 1. 透過環境變數安全讀取 Token
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    raise ValueError("❌ 找不到 DISCORD_TOKEN！請確認 .env 檔案或 Railway 環境變數是否已設定。")

# 2. PCB 專屬的發送頻道 ID
TARGET_CHANNEL_ID = 1478008186916307019

# 3. 自動播報時間設定 (24小時制，台灣時間)
REPORT_TIME = "20:00"
# =========================================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# 🇹🇼 PCB 百科全書
PCB_SUPPLY_CHAIN = {
    "🧵 上游：玻纖/樹脂/銅箔": [
        ("1802", "台玻"), ("1303", "南亞"), ("1815", "富喬"), ("5340", "建榮"), ("5475", "德宏"),
        ("3645", "達邁"), ("1717", "長興"), ("4764", "雙鍵"), ("7419", "達勝"), ("3093", "港建"),
        ("8358", "金居"), ("4989", "榮科"), ("3388", "崇越電"), ("8240", "華宏")
    ],
    "⚙️ 上游：設備與耗材 (一)": [
        ("1528", "恩德"), ("1595", "川寶"), ("1785", "光洋科"), ("2467", "志聖"), ("2493", "揚博"),
        ("3010", "華立"), ("3030", "德律"), ("3455", "由田"), ("3485", "敘豐"), ("3498", "陽程"),
        ("3535", "晶彩科"), ("3563", "牧德"), ("4542", "科嶠"), ("5536", "聖暉")
    ],
    "⚙️ 上游：設備與耗材 (二)": [
        ("6438", "迅得"), ("8438", "昶昕"), ("6664", "群翊"), ("6706", "惠特"), ("6727", "亞泰金屬"),
        ("4577", "達航"), ("6658", "聯策"), ("6877", "鏵友益"), ("7730", "暉盛"), ("7795", "長廣"),
        ("7825", "和亞"), ("3167", "大量"), ("8021", "尖點"), ("8074", "鉅橡") 
    ],
    "🎛️ 中游：CCL 銅箔基板": [
        ("2383", "台光電"), ("6213", "聯茂"), ("6274", "台燿"), ("6672", "騰輝電子"), ("8039", "台虹"),
        ("4939", "亞電"), ("3354", "律勝"), ("3585", "聯致"), ("5381", "合正"), ("6509", "聚和"),
        ("8291", "尚茂"), ("5498", "凱崴"), ("6224", "聚鼎"), ("3144", "新揚科")
    ],
    "🖥️ 中游：PCB板廠 (一)": [
        ("3037", "欣興"), ("8046", "南電"), ("3189", "景碩"), ("4958", "臻鼎-KY"), ("2368", "金像電"),
        ("3044", "健鼎"), ("2313", "華通"), ("5469", "瀚宇博"), ("2316", "楠梓電"), ("6153", "嘉聯益"),
        ("6269", "台郡"), ("2355", "敬鵬"), ("2367", "燿華"), ("2402", "毅嘉"), ("4909", "新復興")
    ],
    "🖥️ 中游：PCB板廠 (二)": [
        ("3715", "定穎投控"), ("4927", "泰鼎-KY"), ("5439", "高技"), ("6191", "精成科"), ("8155", "博智"),
        ("8213", "志超"), ("2328", "廣宇"), ("3114", "好德"), ("3229", "晟鈦"), ("3276", "宇環"),
        ("3321", "同泰"), ("3390", "旭軟"), ("5291", "邑昇"), ("5321", "美而快"), ("5349", "先豐")
    ],
    "🖥️ 中游：PCB板廠 (三)": [
        ("5355", "佳總"), ("5464", "霖宏"), ("6108", "競國"), ("6141", "柏承"), ("6156", "松上"),
        ("6194", "育富"), ("6207", "雷科"), ("6210", "慶生"), ("6271", "同欣電"), ("6407", "相互"),
        ("6597", "立誠"), ("6835", "圓裕"), ("3115", "富榮網")
    ],
    "🧩 中游：基板組裝與加工": [
        ("3520", "華盈"), ("3665", "貿聯-KY"), ("6266", "泰詠"), ("8183", "精星")
    ]
}

def get_real_date():
    try:
        res = requests.head("https://www.google.com", timeout=5)
        if 'Date' in res.headers:
            gmt_time = parsedate_to_datetime(res.headers['Date'])
            tw_time = gmt_time + datetime.timedelta(hours=8)
            return tw_time.date()
    except Exception as e:
        print(f"校時失敗: {e}")
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date()

def fetch_data():
    ANSI_RED = "\u001b[0;31m"    
    ANSI_GREEN = "\u001b[0;32m"  
    ANSI_YELLOW = "\u001b[0;33m" 
    ANSI_WHITE = "\u001b[0;37m"  
    ANSI_RESET = "\u001b[0m"

    end_date = get_real_date()
    start_date = end_date - datetime.timedelta(days=10) 

    total_change = 0
    valid_count = 0
    cat_results = {}

    for cat, stocks in PCB_SUPPLY_CHAIN.items():
        block_content = f"```ansi\n" 
        stock_data_list = []
        
        for code, name in stocks:
            try:
                ticker = f"{code}.TW"
                df = yf.Ticker(ticker).history(start=start_date, end=end_date + datetime.timedelta(days=1))
                if df.empty:
                    ticker = f"{code}.TWO"
                    df = yf.Ticker(ticker).history(start=start_date, end=end_date + datetime.timedelta(days=1))
                
                if len(df) >= 2:
                    close = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2]
                    change = ((close - prev_close) / prev_close) * 100
                    
                    vol_today = df['Volume'].iloc[-1]
                    vol_yest = df['Volume'].iloc[-2]
                    vol_lots = int(vol_today / 1000) if not df['Volume'].isna().iloc[-1] else 0
                    
                    is_burst = vol_today > (vol_yest * 1.5) and vol_lots > 500

                    stock_data_list.append({
                        'code': code, 'name': name, 'price': close, 'change': change,
                        'vol': vol_lots, 'is_burst': is_burst
                    })
                    total_change += change
                    valid_count += 1
            except Exception as e: 
                print(f"台股抓取錯誤 {code}: {e}")
        
        stock_data_list.sort(key=lambda x: x['change'], reverse=True)

        for s in stock_data_list:
            if s['change'] > 0: color = ANSI_RED
            elif s['change'] < 0: color = ANSI_GREEN
            else: color = ANSI_WHITE
            
            if s['is_burst']:
                vol_color = ANSI_YELLOW
                burst_mark = " 🔥"
            else:
                vol_color = ANSI_WHITE
                burst_mark = ""

            display_name = s['name'][:4] 
            id_name = f"{s['code']} {display_name}".ljust(9)
            price_str = f"{s['price']:.1f}".rjust(6)
            pct_str = f"{s['change']:+.1f}%".rjust(7)
            vol_str = f"{s['vol']:,}張".rjust(9) 
            
            block_content += f"{id_name} {price_str} {color}{pct_str}{ANSI_RESET} {vol_color}{vol_str}{burst_mark}{ANSI_RESET}\n"
            
        block_content += "```"
        cat_results[cat] = block_content

    avg_change = total_change / valid_count if valid_count > 0 else 0
    return cat_results, avg_change, end_date

async def send_report(channel):
    msg = await channel.send("🏗️ **正在雲端安全掃描近 90 檔 PCB 全產業鏈，請稍候約 45 秒...**")
    
    try:
        cat_res, avg_chg, data_date = await asyncio.to_thread(fetch_data)
        
        embed_color = 0xff4757 if avg_chg > 0 else 0x2ecc71
        therm = "🔥 資金湧入" if avg_chg > 0.5 else "🧊 資金撤退" if avg_chg < -0.5 else "⚖️ 多空平衡"

        embeds_to_send = []
        
        # 建立第一個主要的 Embed (只有第一頁有標題和說明)
        current_embed = discord.Embed(
            title=f"🎯 台股 PCB 全百科戰略地圖 | {data_date}",
            description="嚴格追蹤從「玻纖銅箔」、「耗材設備」到「各式板廠」的最完整資金輪動",
            color=embed_color
        )
        current_embed.add_field(name=f"🇹🇼 產業鏈綜合熱度：{therm}", value=f"平均漲跌幅：**{avg_chg:+.2f}%**", inline=False)

        for cat, content in cat_res.items():
            if "```ansi\n```" in content or len(content.strip()) <= 15:
                continue 

            # 如果加上下一個板塊會超過安全限制，就先存起來並開新的
            if len(current_embed) + len(cat) + len(content) > 5000:
                embeds_to_send.append(current_embed)
                
                # 開啟新的 Embed (不加標題、不加敘述，只保留左側顏色條，營造無縫接軌視覺感)
                current_embed = discord.Embed(color=embed_color)

            current_embed.add_field(name=f"**{cat}**", value=content, inline=False)

        if len(current_embed.fields) > 0:
            embeds_to_send.append(current_embed)

        # 加上版權/備註資訊 (只加在最後一頁的底部)
        if embeds_to_send:
            embeds_to_send[-1].set_footer(text="數據來源：Yahoo Finance ｜ 紅色=漲 ｜ 綠色=跌 ｜ 黃色數字+🔥=爆量")

        for i, emb in enumerate(embeds_to_send):
            if i == 0:
                await msg.edit(content=None, embed=emb)
            else:
                await channel.send(embed=emb)

    except Exception as e:
        await msg.edit(content=f"❌ 抓取資料時發生錯誤：`{e}`")

@tasks.loop(minutes=1)
async def schedule_task():
    tw_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    now = tw_time.strftime("%H:%M")
    
    if now == REPORT_TIME and TARGET_CHANNEL_ID:
        ch = bot.get_channel(TARGET_CHANNEL_ID)
        if ch: 
            await send_report(ch)
        await asyncio.sleep(61)

@bot.command()
async def pcb(ctx):
    await send_report(ctx.channel)

@bot.event
async def on_ready():
    print(f'🎯 雲端防擋版 PCB 百科戰情室 {bot.user} 已上線！')
    
    if not schedule_task.is_running():
        schedule_task.start()
        print(f"⏰ 定時播報任務已啟動！(設定時間: {REPORT_TIME} 台灣時間)")

bot.run(TOKEN)

