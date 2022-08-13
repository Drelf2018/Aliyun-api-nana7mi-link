import asyncio
import os
import random
import time
from functools import partial
from io import BytesIO
from PIL import Image

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pywebio import config
from pywebio.input import *
from pywebio.output import *
from pywebio.platform.fastapi import webio_routes
from pywebio.session import eval_js
from pywebio.session import run_asyncio_coroutine as rac
from pywebio.session import run_js

app = FastAPI()
config(js_code='''$("body").prepend('<nav class="navbar navbar-dark bg-dark"><div class="container"><a href="/" class="router-link-active router-link-exact-active navbar-brand">🏠</a><a href="https://t.bilibili.com/682043379459031137"><img src="https://api.nana7mi.link/eyes" height="40px" style="border-radius:7px"></a><a href="/?app=about" class="router-link-active router-link-exact-active navbar-brand">❔</a></div></nav>')''')

def code():
    '打印 python 源码'
    with open(__file__, 'r', encoding='utf-8') as fp:
        code = fp.read()
    return [
        put_markdown('## 😰你知道我长什么样 来找我吧').onclick(
            lambda: run_js(code_='tw=window.open();tw.location="https://github.com/Drelf2018/api.nana7mi.link";')
        ),
        put_code(code, 'python')
    ]

def t2s(timenum: int, format: str = '%H:%M:%S') -> str:
    '时间戳转指定格式'
    if timenum is None:
        return '直播中'
    elif timenum == 0:
        return 0
    if len(str(timenum)) > 10:
        timenum //= 1000
    return time.strftime(format, time.localtime(timenum))

# 打印直播场次信息
async def put_live(room_info: dict, pos: int):
    room_info["rst"] = t2s(room_info["st"], "%Y/%m/%d %H:%M:%S")
    room_info["rsp"] = t2s(room_info["sp"], "%Y/%m/%d %H:%M:%S")
    room_info['cover'] = room_info['cover'].replace('https://i0.hdslb.com/bfs/live/new_room_cover/', '')
    put_html(
'''<div style="display: grid; grid-auto-flow: column; grid-template-columns: 10fr 1fr 30fr;" class="pywebio-clickable">
    <a href="/cover/raw_{cover}"><img src="/cover/{cover}" width="196px" style="border-radius:10px"></a>
    <div></div>
    <div style="display: grid; grid-auto-flow: row; grid-template-rows: 1fr 1fr;">
        <h3 id="{username}-{title}">{username} {title}</h3>
        <p><font color="grey">开始</font> <strong>{rst}</strong> 
        <font color="grey">结束</font> <strong>{rsp}</strong></p>
    </div>
</div>'''.format_map(room_info), scope='query_scope').onclick(
        partial(
            reload_live,
            room_info=room_info,
            url=f'http://api.nana7mi.link:5762/live/{room_info["room"]}/{pos}',
            pos=pos
        )
    )

async def reload_live(room_info, url: str, pos: int):
    clear('query_scope')
    put_markdown('弹幕加载中', scope='query_scope')
    session = httpx.AsyncClient()
    with put_loading('border', 'primary'):
        resp = await rac(session.get(url, timeout=30.0))
        js = resp.json()
        if js['status'] != 0:
            toast('运行时错误：'+js['status'], 3, color='error')
            return
        danmaku = js['live']['danmaku']
        clear('query_scope')
    await put_live(room_info, pos)
    temp = '%s <a href="https://space.bilibili.com/%d">%s</a> %s\n\n'
    danma_str = ''.join([temp % (t2s(dm["time"]), dm["uid"], dm["username"], dm["msg"]) for dm in danmaku])
    put_markdown(danma_str, scope='query_scope')

# 打印弹幕列表
async def put_danmaku(room_info: dict, danmaku: list, flag: bool = False):
    await put_live(room_info, danmaku)  # 先打印直播信息
    if flag:
        danma_str = '\n\n'.join([f'{t2s(dm["time"])} <a href="https://space.bilibili.com/{dm["uid"]}">{dm["username"]}</a> {dm["msg"]}'
                                    for dm in danmaku])
        put_markdown(danma_str, scope='query_scope')
        put_markdown('---', scope='query_scope')

# 按钮点击事件
async def onclick(btn):
    clear('query_scope')
    session = httpx.AsyncClient()
    try:
        if btn == '😋查发言':
            uid = await input('输入查询用户 uid')
            if uid and uid.isdigit:
                try:
                    resp = await rac(session.get(f'http://api.nana7mi.link:5762/uid/{uid}', timeout=20.0))
                except Exception as e:
                    toast(f'运行时错误：{e}', 3, color='error')
                    return
                js = resp.json()
            else:
                toast('输入不正确', 3, color='error')
                return
            first = True  # 标识符 用来判断是否打印分割线
            danmaku = js['danmaku']
            for dm in danmaku:
                if not dm['room_info']:  # 没有 room_info 表示下播时发送的弹幕 直接打印
                    first = False
                    put_markdown(f'{t2s(dm["time"], "%Y/%m/%d %H:%M:%S")} <a href="https://live.bilibili.com/{dm["room"]}">[{dm["room"]}]</a> <a href="https://space.bilibili.com/{uid}">{dm["username"]}</a> {dm["msg"]}', scope='query_scope')
                else:
                    if not first:
                        put_markdown('---', scope='query_scope')
                    first = True
                    await put_danmaku(dm['room_info'], dm['danmaku'], True)

        elif btn == '🍜查直播':
            roomid = await input('输入查询直播间号')
            if roomid and roomid.isdigit:
                resp = await rac(session.get(f'http://api.nana7mi.link:5762/live/{roomid}', timeout=20.0))
                js = resp.json()
                if js['status'] == 0:
                    n = len(js['lives']) - 1
                    for pos, live in enumerate(js['lives']):
                        await put_danmaku(live, danmaku=n-pos)
            else:
                toast('输入不正确', 3, color='error')
    except Exception as e:
        toast(f'运行时错误：{e}', 3, color='error')
        return

async def cha():
    '狠狠查他弹幕'

    quotations = [
        '你们会无缘无故的说好用，就代表哪天无缘无故的就要骂难用',
        '哈咯哈咯，听得到吗',
        '还什么都没有更新，不要急好嘛',
        '直播只是工作吗直播只是工作吗直播只是工作吗？'
    ]
    put_markdown(f'# 😎 api.nana7mi.link <font color="grey" size=4>*{random.choice(quotations)}*</font>')
    put_buttons(['😋查发言', '🍜查直播'], onclick=onclick),
    put_scope('query_scope')
    try:
        session = httpx.AsyncClient()
        resp = await rac(session.get('http://api.nana7mi.link:5762/rooms', timeout=20.0))
        js = resp.json()
        if isinstance(js['rooms'], list):
            pending = [asyncio.create_task(put_live(room, -1)) for room in js['rooms']][::-1]
            await asyncio.wait(pending)
        else:
            toast(f'运行时错误：{js["rooms"]}', 3, color='error')
    except Exception as e:
        print(e, e.__traceback__.tb_lineno, resp.content)
        toast(f'运行时错误：{e.__traceback__.tb_lineno} {e}', 3, color='error')

async def about():
    '关于'
    put_tabs([
        {'title': '源码', 'content': code()},
        {'title': '私货', 'content': 
            put_html('''
                <iframe src="//player.bilibili.com/player.html?aid=78090377&bvid=BV1vJ411B7ng&cid=133606284&page=1"
                    width="100%" height="550" scrolling="true" border="0" frameborder="no" framespacing="0" allowfullscreen="true">
                </iframe>''')
        }
    ]).style('border:none;')  # 取消 put_tabs 的边框


@app.get("/cover/{filename}")
async def new_room_cover(filename: str):
    path =  'cover\\' + filename
    if not os.path.exists(path):
        async with httpx.AsyncClient() as session:
            resp = await session.get('https://i0.hdslb.com/bfs/live/new_room_cover/'+filename)
        content = BytesIO(resp.content)
        img = Image.open(content)
        img.save('cover\\raw_'+filename)
        img = img.resize((196, int(img.height*196/img.width)))
        img.save(path)
    if os.path.exists(path):
        return StreamingResponse(open(path, mode="rb"), media_type="image/jpg")

app.mount('/', FastAPI(routes=webio_routes({'index': cha, 'about': about})))
# const Http = new XMLHttpRequest();
# const url='http:api.nana7mi.link:5762/rooms';
# Http.open("GET", url);
# Http.send();

# Http.onreadystatechange = (e) => {
#   console.log(Http.responseText)
# }

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=9000)
