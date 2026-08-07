import asyncio
import json
import ssl
import sys
import traceback
import websockets
import properties
from properties import os
from properties import mimetypes
from properties import cv2
from properties import math

save = None


async def receive_messages(websocket, my_name, room_name):
    global save
    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get("auth") == "OK":
                print("\r[System]Server authentication successful")
                continue
            msg = data.get("message")
            if msg:
                sender = data.get("id", "unknown")
                if sender == my_name:
                    continue

                if msg.startswith("/user"):
                    target_user = msg.split(" ", 1)[1].strip()
                    if my_name == target_user:
                        payload = {
                            "to": room_name,
                            "id": my_name,
                            "message": f"/opfounduser {sender}"
                        }
                        await websocket.send(json.dumps(payload))
                    continue
                elif msg.startswith("/opfounduser"):
                    requester = msg.split(" ", 1)[1].strip()
                    if my_name == requester:
                        print(f"\r[System]{sender} is currently online.")
                        print(f"{my_name}: ", end="", flush=True)
                    continue
                elif msg.startswith("/opsyncsave\n"):
                    save = msg.split("\n", 1)[1]
                    continue
                elif msg.startswith("/opfiledm "):
                    parts = msg.split("\n", 1)
                    target_user = parts[0].replace("/opfiledm ", "").strip()
                    if my_name == target_user:
                        content = parts[1] if len(parts) > 1 else ""
                        save = content
                        print(f"\r[{sender} (latest file)]:\n{content}")
                        print(f"{my_name}: ", end="", flush=True)

                    continue
                print(f"\r{sender}: {msg}")
                print(f"{my_name}: ", end="", flush=True)

                if msg.strip() == "/show" and sender != my_name and save is not None:
                    payload = {
                        "to": room_name,
                        "id": my_name,
                        "message": f"/opfiledm {sender}\n{save}"
                    }
                    await websocket.send(json.dumps(payload))
    except websockets.exceptions.ConnectionClosed:
        print("\r[System]Connection defused")


async def send_messages(websocket, my_name, room_name):
    global save
    loop = asyncio.get_running_loop()

    while True:
        msg = await loop.run_in_executor(None, input, f"{my_name}: ")
        if msg.lower() in ['exit', 'quit']:
            print(f"\r[System]Disconnected")
            break

        elif msg.startswith("/help"):
            properties.help()

        elif msg.startswith("/cmd"):
            properties.command_list()

        elif msg.startswith("/generate "):
            await instant_generate(msg, my_name, room_name, websocket)

        elif msg.startswith("/download"):
            if save is not None:
                cmd_parts = msg.strip().split(maxsplit=1)
                filename = cmd_parts[1] if len(cmd_parts) > 1 else "downloaded.txt"
                if not filename.endswith(".txt"):
                    filename += ".txt"

                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(save)
                    print(f"\r[Helper]Successfully saved as '{filename}'.")
                except Exception as e:
                    print(f"\r[Helper]Failed to save the file: {e}")
            else:
                print(f"\r[Helper]No history found to download.")
            continue

        elif msg.startswith("/file "):
            file = msg[6:].strip()

            if os.path.exists(file):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    await uploaded(file_content, file, room_name, my_name, websocket, msg)

                except Exception:
                    print(f"\r[Helper]Failed to load {file}.")
                    continue
            else:
                print(f"\r[Helper]{file} doesn't exist.")

        elif msg.startswith("/show"):
            if save is not None:
                print(f"\r{save}")
            else:
                try:
                    payload = {
                        "to": room_name,
                        "id": my_name,
                        "message": msg
                    }
                    await websocket.send(json.dumps(payload))

                except Exception:
                    print(f"\r[Helper]No history found.")
        else:
            payload = {
                "to": room_name,
                "id": my_name,
                "message": msg
            }
            await websocket.send(json.dumps(payload))


async def main():
    print("30000")
    room_name = input("Enter the ID of the room you want to join: ")
    my_name = input("Enter your name: ")

    uri = f"wss://cloud.achex.ca/chat"

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1
    try:
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=0')
    except Exception:
        pass

    try:
        print(f"\r[System]Connecting to {uri}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Origin": "https://cloud.achex.ca"
        }

        async with websockets.connect(uri, ssl=ssl_context, additional_headers=headers) as websocket:
            auth_data = {
                "auth": room_name,
                "password": "password110"
            }
            await websocket.send(json.dumps(auth_data))
            await websocket.send(json.dumps({"to": room_name, "id": "[System]", "message": f"{my_name} joined"}))
            print(f"\r[System]Connected. To leave the chat, type exit")
            print(f"\r[System]To show all commands. type /cmd")
            receive_task = asyncio.create_task(receive_messages(websocket, my_name, room_name))
            send_task = asyncio.create_task(send_messages(websocket, my_name, room_name))

            await send_task
            receive_task.cancel()

    except Exception as e:
        print(f"\r[System]Error was occurred: {e}")
        traceback.print_exc()


def start():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\r[System]Error was occurred")


async def instant_generate(msg, my_name, room_name, websocket):
    parts = msg.split()
    if len(parts) == 5:
        path = parts[1]
        color = parts[2]
        size = int(parts[3])
        correction_factor = float(parts[4])
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width = gray.shape
        # setsumei
        mime_type, _ = mimetypes.guess_type(path)
        if width >= size:
            height = math.ceil(height * (size / width) * correction_factor)
        else:
            print(f"\r[System]error")

        if color == "gray":
            if mime_type and mime_type.startswith('image'):
                resized_gray = cv2.resize(gray, (size, height))
                pixels = resized_gray.flatten().astype(int)
                result = properties.gray_generator(properties.ASCII_CHARS_NORMAL, pixels, size)
                print(f"\r{result}")
                await uploaded(result, f"ASCII art of {path}", room_name, my_name, websocket, msg)

                # ws send message
        elif color == "color":
            if mime_type and mime_type.startswith('image'):
                resized_rgb = cv2.resize(rgb, (size, height))
                resized_gray = cv2.resize(gray, (size, height))
                pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
                pixels_gray = resized_gray.flatten().astype(int)
                result = properties.rgb_generator(properties.ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, "r", size)
                print(f"\r{result}")
                await uploaded(result, f"Color ASCII art of {path}", room_name, my_name, websocket, msg)
                # ws send message
    else:
        print(f"\r[System]Error was occurred")


async def uploaded(content, display_name, room_name, my_name, websocket, msg):
    global save
    list_msg = [msg,
                "-----------------------------",
                f"{my_name} uploaded {display_name}.",
                f"To show it, type /show",
                f"To download it, type /download",
                "-----------------------------"]
    for i in range(len(list_msg)):
        payload = {
            "to": room_name,
            "id": my_name,
            "message": list_msg[i]
        }
        if i != 0:
            print(f"\r{my_name}: {list_msg[i]}")
        await websocket.send(json.dumps(payload))
        await asyncio.sleep(0.1)

    sync_payload = {
        "to": room_name,
        "id": my_name,
        "message": f"/opsyncsave\n{content}"
    }
    await websocket.send(json.dumps(sync_payload))
    save = content
