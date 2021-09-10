import os
import asyncio
import subprocess
from pytgcalls import idle
from pytgcalls import PyTgCalls
from pytgcalls import StreamType
from pytgcalls.types.input_stream import AudioParameters
from pytgcalls.types.input_stream import InputAudioStream
from pytgcalls.types.input_stream import InputVideoStream
from pytgcalls.types.input_stream import VideoParameters
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH, SESSION_NAME
from youtube_dl import YoutubeDL
from youtube_dl.utils import ExtractorError
SIGINT: int = 2

app = Client(SESSION_NAME, API_ID, API_HASH)

call_py = PyTgCalls(app)
FFMPEG_PROCESSES = {}
def raw_converter(dl, song, video):
    return subprocess.Popen(
        ['ffmpeg', '-i', dl, '-f', 's16le', '-ac', '1', '-ar', '48000', song, '-y', '-f', 'rawvideo', '-r', '20', '-pix_fmt', 'yuv420p', '-vf', 'scale=1280:720', video, '-y'],
        stdin=None,
        stdout=None,
        stderr=None,
        cwd=None,
    )
    
def youtube(url: str):
    try:
        params = {"format": "best[height=?720]/best", "noplaylist": True}
        yt = YoutubeDL(params)
        info = yt.extract_info(url, download=False)
        return info['url']
    except ExtractorError: # do whatever
        return 
    except Exception:
        return
    



@Client.on_message(filters.command("stream"))
async def stream(client, m: Message):
    replied = m.reply_to_message
    if not replied:
        if len(m.command) < 2:
            await m.reply("`Reply to some Video or Give Some Live Stream Url!`")
        else:
            livelink = m.text.split(None, 1)[1]
            chat_id = m.chat.id
            try:
                livelink = await asyncio.wait_for(
                    app.loop.run_in_executor(
                        None,
                        lambda : youtube(livelink)
                    ),
                    timeout=None # Add timeout (recommended)
                )
            except asyncio.TimeoutError:
                await m.reply("TimeoutError: process is taking unexpected time")
                return
            if not livelink:
                await m.reply("Can't fetch source")
                return
            process = raw_converter(livelink, f'audio{chat_id}.raw', f'video{chat_id}.raw')
            FFMPEG_PROCESSES[chat_id] = process
            msg = await m.reply("`Starting Live Stream...`")
            await asyncio.sleep(10)
            try:
                audio_file = f'audio{chat_id}.raw'
                video_file = f'video{chat_id}.raw'
                while not os.path.exists(audio_file) or \
                        not os.path.exists(video_file):
                    await asyncio.sleep(2)
                await call_py.join_group_call(
                    chat_id,
                    InputAudioStream(
                        audio_file,
                        AudioParameters(
                            bitrate=48000,
                        ),
                    ),
                    InputVideoStream(
                        video_file,
                        VideoParameters(
                            width=1280,
                            height=720,
                            frame_rate=20,
                        ),
                    ),
                    stream_type=StreamType().local_stream,
                )
                await msg.edit("**Started Streaming!**")
                await idle()
            except Exception as e:
                await msg.edit(f"**Error** -- `{e}`")
   
    elif replied.video or replied.document:
        msg = await m.reply("`Downloading...`")
        video = await client.download_media(m.reply_to_message)
        chat_id = m.chat.id
        await msg.edit("`Processing...`")
        os.system(f"ffmpeg -i '{video}' -f s16le -ac 1 -ar 48000 'audio{chat_id}.raw' -y -f rawvideo -r 20 -pix_fmt yuv420p -vf scale=640:360 'video{chat_id}.raw' -y")
        try:
            audio_file = f'audio{chat_id}.raw'
            video_file = f'video{chat_id}.raw'
            while not os.path.exists(audio_file) or \
                    not os.path.exists(video_file):
                await asyncio.sleep(2)
            await call_py.join_group_call(
                chat_id,
                InputAudioStream(
                    audio_file,
                    AudioParameters(
                        bitrate=48000,
                    ),
                ),
                InputVideoStream(
                    video_file,
                    VideoParameters(
                        width=640,
                        height=360,
                        frame_rate=20,
                    ),
                ),
                stream_type=StreamType().local_stream,
            )
            await msg.edit("**Started Streaming!**")
        except Exception as e:
            await msg.edit(f"**Error** -- `{e}`")
            await idle()
    else:
        await m.reply("`Reply to some Video!`")

@Client.on_message(filters.command("stop"))
async def stopvideo(client, m: Message):
    chat_id = m.chat.id
    try:
        process = FFMPEG_PROCESSES.get(chat_id)
        if process:
            try:
                process.send_signal(SIGINT)
                await asyncio.sleep(3)
            except Exception as e:
                print(e)
        await call_py.leave_group_call(chat_id)
        await m.reply("**⏹️ Stopped Streaming!**")
    except Exception as e:
        await m.reply(f"**🚫 Error** - `{e}`")
