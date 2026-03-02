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
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import warnings

warnings.filterwarnings('ignore')
load_dotenv()
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# ================= 終極雲端字型處理 =================
FONT_PATH = "TaipeiSansTC.ttf"
if not os.path.exists(FONT_PATH):
    try:
        print("📥 偵測到雲端環境，正在下載中文字型 (台北黑體)...")
        url = "https://raw.githubusercontent.com/halfrost/Halfrost-Field/master/contents/Machine_Learning/TaipeiSansTCBeta-Regular.ttf"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        with open(FONT_PATH, "wb") as f:
            f.write(response.content)
        print("✅ 字型下載完成！")
    except Exception as e:
        print(f"❌ 字型下載失敗: {e}")

if os.path.exists(FONT_PATH):
    my_font = fm.FontProperties(fname=FONT_PATH)
else:
    my_font = fm.FontProperties(family='Microsoft JhengHei')
    
plt.rcParams['axes.unicode_minus'] = False 

# ================= 設定區 =================
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("❌ 找不到 DISCORD_TOKEN！請確認 .env 檔案或 Railway 環境變數。")

TARGET_CHANNEL_ID = 1477660722786996294
REPORT_TIME = "20:00"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

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

# ================= 繪圖風格設定 =================
BG_COLOR = "#131722"
GRID_COLOR = "#2a2e39"
TEXT_COLOR = "#d1d4dc"
UP_COLOR = "#ef5350"
DOWN_COLOR = "#26a69a"

plt.rcParams['text.color'] = TEXT_COLOR
plt.rcParams['axes.labelcolor'] = TEXT_COLOR
plt.rcParams['xtick.color'] = TEXT_COLOR
plt.rcParams['ytick.color'] = TEXT_COLOR

def setup_premium_axes(ax, title, ylabel=None, xlabel=None):
    ax.set_facecolor(BG_COLOR)
    ax.set_title(title, fontproperties=my_font, fontsize=16, pad=20, fontweight='bold', color='white')
    if ylabel: ax.set_ylabel(ylabel, fontproperties=my_font, fontsize=12, labelpad=10)
    if xlabel: ax.set_xlabel(xlabel, fontproperties=my_font, fontsize=12, labelpad=10)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRID_COLOR)
    ax.spines['bottom'].set_color(GRID_COLOR)
    ax.grid(axis='x' if ylabel else 'y', color=GRID_COLOR, linestyle='--', alpha=0.7)

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

def fetch_data_and_plot():
    end_date = get_real_date()
    start_date = end_date - datetime.timedelta(days=10) 

    total_change = 0
    valid_count = 0
    all_stocks_data = [] 
    
    # 用來存放 Discord 文字版面的精簡摘要
    summary_text = ""

    for cat, stocks in PCB_SUPPLY_CHAIN.items():
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
                    vol_lots = int(vol_today / 1000) if not pd.isna(df['Volume'].iloc[-1]) else 0
                    is_burst = vol_today > (vol_yest * 1.5) and vol_lots > 500

                    stock_data_list.append({'code': code, 'name': name, 'price': close, 'change': change, 'vol': vol_lots, 'is_burst': is_burst})
                    
                    clean_cat = cat.split(" ", 1)[-1] if " " in cat else cat
                    all_stocks_data.append({
                        'Category': clean_cat, 'Code': code, 'Name': name, 
                        'Change': change, 'Volume': vol_lots, 'Burst': is_burst
                    })

                    total_change += change
                    valid_count += 1
            except Exception as e: 
                pass
        
        # 排序並萃取該板塊精華 (只抓漲幅前 3 名作為領漲代表)
        stock_data_list.sort(key=lambda x: x['change'], reverse=True)
        cat_avg = sum(s['change'] for s in stock_data_list) / len(stock_data_list) if stock_data_list else 0
        
        # 整理文字：只顯示大於 0% 的前三名強勢股
        top_gainers = [f"{s['name']}({s['change']:+.1f}%)" for s in stock_data_list[:3] if s['change'] > 0]
        top_str = "、".join(top_gainers) if top_gainers else "無明顯漲勢"
        
        # 組合該板塊的精簡文字
        color_icon = "🔴" if cat_avg > 0 else "🟢" if cat_avg < 0 else "⚪"
        summary_text += f"**{cat}** ｜ {color_icon} 平均 `{cat_avg:+.2f}%`\n"
        summary_text += f"└ 🔥 領漲：*{top_str}*\n\n"

    avg_change = total_change / valid_count if valid_count > 0 else 0
    df_plot = pd.DataFrame(all_stocks_data)

    # =============== 繪製圖表 ===============
    if not df_plot.empty:
        # 【圖一】各板塊資金熱度
        fig1, ax1 = plt.subplots(figsize=(12, 7))
        fig1.patch.set_facecolor(BG_COLOR) 
        
        cat_avg_df = df_plot.groupby('Category')['Change'].mean().sort_values(ascending=True)
        colors1 = [DOWN_COLOR if x < 0 else UP_COLOR for x in cat_avg_df]
        bars1 = ax1.barh(cat_avg_df.index, cat_avg_df.values, color=colors1, height=0.6, alpha=0.9)
        ax1.axvline(x=0, color=TEXT_COLOR, linestyle='-', linewidth=1, alpha=0.5)
        setup_premium_axes(ax1, f'🎯 PCB 各次產業平均資金熱度 ({end_date})', xlabel='平均漲跌幅 (%)')

        for label in ax1.get_yticklabels():
            label.set_fontproperties(my_font)
            label.set_fontsize(11)

        for bar in bars1:
            width = bar.get_width()
            x_pos = width + 0.15 if width > 0 else width - 0.15
            ha = 'left' if width > 0 else 'right'
            ax1.text(x_pos, bar.get_y() + bar.get_height()/2, f'{width:+.2f}%', 
                     ha=ha, va='center', fontproperties=my_font, fontsize=11, fontweight='bold', color='white')

        plt.tight_layout()
        plt.savefig('heatmap.png', dpi=200, facecolor=fig1.get_facecolor(), edgecolor='none')
        plt.close(fig1)

        # 【圖二】漲幅前 15 名強勢股
        top_15 = df_plot.sort_values(by='Change', ascending=False).head(15)
        fig2, ax2 = plt.subplots(figsize=(14, 7))
        fig2.patch.set_facecolor(BG_COLOR)

        names = [f"{row.Code}\n{row.Name}" for row in top_15.itertuples()]
        bars2 = ax2.bar(names, top_15['Change'], color=UP_COLOR, width=0.55, alpha=0.9)
        ax2.axhline(y=0, color=TEXT_COLOR, linestyle='-', linewidth=1, alpha=0.5)
        setup_premium_axes(ax2, f'🚀 PCB 產業鏈 - 漲幅前 15 名強勢股 ({end_date})', ylabel='漲跌幅 (%)')

        for label in ax2.get_xticklabels():
            label.set_fontproperties(my_font)
            label.set_fontsize(11)

        for bar, is_burst in zip(bars2, top_15['Burst']):
            height = bar.get_height()
            burst_text = "[爆量]" if is_burst else ""
            ax2.text(bar.get_x() + bar.get_width()/2, height + 0.2, 
                     f'{height:+.1f}%\n{burst_text}', 
                     ha='center', va='bottom', fontproperties=my_font, fontsize=11, fontweight='bold', color='white')

        plt.tight_layout()
        plt.savefig('top15.png', dpi=200, facecolor=fig2.get_facecolor(), edgecolor='none')
        plt.close(fig2)

    return summary_text, avg_change, end_date

async def send_report(channel):
    msg = await channel.send("🏗️ **正在生成極簡版 PCB 戰情儀表板，請稍候約 45 秒...**")
    
    try:
        summary_text, avg_chg, data_date = await asyncio.to_thread(fetch_data_and_plot)
        
        embed_color = 0xff4757 if avg_chg > 0 else 0x2ecc71
        therm = "🔥 資金全面湧入" if avg_chg > 0.5 else "🧊 資金正在撤退" if avg_chg < -0.5 else "⚖️ 多空力道平衡"

        # 建立單一極簡版 Embed
        embed = discord.Embed(
            title=f"📊 台股 PCB 戰略儀表板 | {data_date}",
            description=f"**大盤產業鏈綜合熱度：** {therm} (平均 **{avg_chg:+.2f}%**)\n\n" + summary_text,
            color=embed_color
        )
        embed.set_footer(text="詳細個股排行請見下方圖表 ｜ 數據來源：Yahoo Finance")

        # 編輯覆蓋原本的等待訊息
        await msg.edit(content=None, embed=embed)

        # 接著發送圖表
        files = []
        if os.path.exists('heatmap.png'):
            files.append(discord.File('heatmap.png'))
        if os.path.exists('top15.png'):
            files.append(discord.File('top15.png'))
            
        if files:
            await channel.send(files=files)

    except Exception as e:
        await msg.edit(content=f"❌ 發生錯誤：`{e}`")

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
    print(f'🎯 雲端極簡版 PCB 戰情室 {bot.user} 已上線！')
    if not schedule_task.is_running():
        schedule_task.start()
        print(f"⏰ 定時播報任務已啟動！({REPORT_TIME})")

bot.run(TOKEN)
