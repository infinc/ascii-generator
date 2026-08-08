import asyncio
import json
import ssl
import sys
import traceback
import websockets
import functions
import secrets
import string
import re
import hashlib
from functions import os
from functions import mimetypes
from functions import cv2
from functions import math

save = None


async def receive_messages(websocket, my_name, full_id, room_name, absolute_id):
    global save
    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get("auth") == "OK":
                print("\r[System]認証が成功しました")
                continue
            msg = data.get("message")
            if msg:
                sender = data.get("id", "unknown")
                if sender == full_id:
                    continue

                if msg.startswith("/user "):
                    target_user = msg.split(" ", 1)[1].strip()
                    if target_user in (my_name, absolute_id, full_id):
                        payload = {
                            "to": room_name,
                            "id": full_id,
                            "message": f"/opfounduser {sender}"
                        }
                        await websocket.send(json.dumps(payload))
                    continue
                elif msg.startswith("/opfounduser "):
                    requester = msg.split(" ", 1)[1].strip()
                    if full_id == requester:
                        print(f"\r[System]{sender} は現在オンラインです")
                        print(f"{full_id}: ", end="", flush=True)
                    continue
                elif msg.startswith("/opsyncsave\n"):
                    save = msg.split("\n", 1)[1]
                    continue
                elif msg.startswith("/opfiledm "):
                    parts = msg.split("\n", 1)
                    target_user = parts[0].replace("/opfiledm ", "").strip()
                    if target_user in (my_name, absolute_id, full_id):
                        content = parts[1] if len(parts) > 1 else ""
                        save = content
                        print(f"\r[{sender} (最新のファイル)]:\n{content}")
                        print(f"{full_id}: ", end="", flush=True)

                    continue
                print(f"\r{sender}: {msg}")
                print(f"{full_id}: ", end="", flush=True)

                if msg.strip() == "/show" and sender != full_id and save is not None:
                    payload = {
                        "to": room_name,
                        "id": full_id,
                        "message": f"/opfiledm {sender}\n{save}"
                    }
                    await websocket.send(json.dumps(payload))
    except websockets.exceptions.ConnectionClosed:
        print("\r[System]接続が切れました")
        print("\r[System]続けるには再接続してください")
        sys.exit()


async def send_messages(websocket, my_name, full_id, room_name, absolute_id):
    global save
    loop = asyncio.get_running_loop()

    while True:
        msg = await loop.run_in_executor(None, input, f"{full_id}: ")
        if not msg.strip():
            continue

        if msg.startswith("/exit"):
            print(f"\r[System]退出しました")
            payload = {
                "to": room_name,
                "id": full_id,
                "message": f"[System]{full_id} が退出しました"
            }
            await websocket.send(json.dumps(payload))
            break

        elif msg.startswith("/help"):
            functions.help_list()

        elif msg.startswith("/cmd"):
            functions.command_list()

        elif msg.startswith("/generate "):
            await instant_generate(msg, my_name, full_id, room_name, websocket)

        elif msg.startswith("/download "):
            if save is not None:
                cmd_parts = msg.strip().split()
                if len(cmd_parts) >= 2:
                    mode = cmd_parts[1].lower()

                    if mode == "raw":
                        filename = cmd_parts[2] if len(cmd_parts) > 2 else "downloaded_raw.txt"
                        if not filename.endswith(".txt"):
                            filename += ".txt"

                        try:
                            with open(filename, "w", encoding="utf-8") as f:
                                clean_save = re.sub(r'\x1b\[[0-9;]*m', '', save)
                                f.write(clean_save)
                            print(f"\r[Helper]{filename} として保存しました")
                        except Exception as e:
                            print(f"\r[Helper]エラー: {e}")

                    elif mode == "png":
                        filename = cmd_parts[2] if len(cmd_parts) > 2 else "downloaded.png"
                        if filename.endswith(".txt"):
                            filename = filename[:-4] + ".png"
                        elif not filename.endswith(".png"):
                            filename += ".png"

                        try:
                            temp_txt = "temp_download_ascii.txt"
                            with open(temp_txt, "w", encoding="utf-8") as f:
                                f.write(save)

                            functions.ascii_to_image(temp_txt, functions.ASCII_CHARS_NORMAL)

                            if os.path.exists("Generated-photos.png"):
                                if os.path.exists(filename):
                                    os.remove(filename)
                                os.rename("Generated-photos.png", filename)
                                print(f"\r[Helper]{filename} として保存しました")
                            else:
                                print(f"\r[Helper]エラー: test")

                            if os.path.exists(temp_txt):
                                os.remove(temp_txt)

                        except Exception as e:
                            print(f"\r[Helper]エラー: {e}")
                    else:
                        print(f"\r[System]コマンド: /download <[raw/png]> <filename>")
                else:
                    print(f"\r[System]コマンド: /download <[raw/png]> <filename>")
            else:
                print(f"\r[Helper]エラー: ダウンロードするファイルが存在しません")
            continue

        elif msg.startswith("/file "):
            file = msg[6:].strip()

            if os.path.exists(file):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    await uploaded(file_content, file, room_name, full_id, websocket, msg)

                except Exception as e:
                    print(f"\r[Helper]エラー: {e}")
                    continue
            else:
                print(f"\r[Helper]エラー: {file} が存在しません。")

        elif msg.startswith("/user "):
            target_user = msg[6:].strip()
            if not target_user:
                print(f"\r[System]コマンド: /user <user_nameid>")
                print(f"{full_id}: ", end="", flush=True)
                continue

            if target_user in (my_name, absolute_id, full_id):
                print(f"\r[System]指定した人は自分自身です。")
                print(f"{full_id}: ", end="", flush=True)
                continue

            print(f"\r[System]{target_user} を検索しています...")

            payload = {
                "to": room_name,
                "id": full_id,
                "message": f"/user {target_user}"
            }
            await websocket.send(json.dumps(payload))

            print(f"{full_id}: ", end="", flush=True)
            continue

        elif msg.startswith("/show"):
            if save is not None:
                print(f"\r{save}")
            else:
                try:
                    payload = {
                        "to": room_name,
                        "id": full_id,
                        "message": msg
                    }
                    await websocket.send(json.dumps(payload))

                except Exception:
                    print(f"\r[Helper]エラー: ダウンロードするファイルが存在しません")
        else:
            payload = {
                "to": room_name,
                "id": full_id,
                "message": msg
            }
            await websocket.send(json.dumps(payload))


async def main():
    print("匿名性は低いです。パスワードや個人情報を送らないでください。")
    my_name = input("使用するユーザーネームを入力: ")
    room_name = input("参加する部屋のIDを入力: ")
    print("パスワードは入力しなくてもデフォルトでpasswordになります。")
    room_password = input("参加する部屋のパスワードを入力: ")
    if not room_password:
        room_password = "password"

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
            secret_key = f"{room_name}::{room_password}"
            real_room_id = hashlib.sha256(secret_key.encode()).hexdigest()

            auth_data = {
                "auth": real_room_id
            }

            await websocket.send(json.dumps(auth_data))

            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    res_data = json.loads(response)

                    if "auth" in res_data:
                        if res_data["auth"] == "OK":
                            print("\r[System]認証が成功しました")
                            break
                        else:
                            print(f"\r[System]エラー: 認証に失敗しました。")
                            print(f"\r中止")
                            sys.exit()
                    elif "ERR" in res_data or "error" in res_data:
                        err_msg = res_data.get("ERR", res_data.get("error", "Unknown error"))
                        print(f"\r[System]エラー: 認証に失敗しました。{err_msg}")
                        print(f"\r中止")
            except asyncio.TimeoutError:
                pass

            absolute_id = generate_absolute_id()
            full_id = f"[{absolute_id}]{my_name}"
            await websocket.send(json.dumps({"to": real_room_id, "id": "[System]", "message": f"{full_id} が参加しました"}))
            print(f"\r-----------------------------")
            print(f"\rあなたのユーザーネーム: {my_name}")
            print(f"\rあなたのID: {absolute_id}")
            print(f"\r部屋のID: {room_name}")
            print(f"\r部屋のパスワード: {room_password}")
            print(f"\r-----------------------------")
            print(f"\r[System]接続しました。退出するには/exitと入力してください")
            print(f"\r[System]全てのコマンドを出力するには、/cmdと入力してください")

            receive_task = asyncio.create_task(receive_messages(websocket, my_name, full_id, real_room_id, absolute_id))
            send_task = asyncio.create_task(send_messages(websocket, my_name, full_id, real_room_id, absolute_id))

            await send_task
            receive_task.cancel()

    except Exception as e:
        print(f"\r[System]エラー: {e}")
        print(f"\r中止")
        sys.exit()


def start():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\r[System]エラー: ユーザーの操作によって終了しました。")
        print(f"\r中止")
        sys.exit()


async def instant_generate(msg, my_name, full_id, room_name, websocket):
    try:
        parts = msg.split()
        if len(parts) == 5:
            path = parts[1]
            color = parts[2]
            size = int(parts[3])
            correction_factor = float(parts[4])

            if not os.path.exists(path):
                print(f"\r[System]エラー: {path} は存在しません。")
                return

            img = cv2.imread(path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width = gray.shape

            mime_type, _ = mimetypes.guess_type(path)
            if width >= size:
                height = math.ceil(height * (size / width) * correction_factor)
            else:
                print(f"\r[System]エラー: 画像のサイズよりも大きい値を入力することはできません。")
                return

            if color == "gray":
                if mime_type and mime_type.startswith('image'):
                    resized_gray = cv2.resize(gray, (size, height))
                    pixels = resized_gray.flatten().astype(int)
                    result = functions.gray_generator(functions.ASCII_CHARS_NORMAL, pixels, size)
                    print(f"\r{result}")
                    await uploaded(result, f"{path} の白黒ASCII ART", room_name, full_id, websocket, msg)

            elif color == "color":
                if mime_type and mime_type.startswith('image'):
                    resized_rgb = cv2.resize(rgb, (size, height))
                    resized_gray = cv2.resize(gray, (size, height))
                    pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
                    pixels_gray = resized_gray.flatten().astype(int)
                    result = functions.rgb_generator(functions.ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, "r", size)
                    print(f"\r{result}")
                    await uploaded(result, f"{path}のカラーASCII ART", room_name, full_id, websocket, msg)
        else:
            print(f"\r[System]コマンド: /generate <path> <[gray/color]> <width> <factor>")
    except Exception as e:
        print(f"\r[System]エラー: {e}")


async def uploaded(content, display_name, room_name, full_id, websocket, msg):
    global save
    list_msg = [msg,
                "-----------------------------",
                f"{full_id} が{display_name} をアップロードしました。",
                f"表示するには/showと入力してください。",
                f"ダウンロードするには、/download <[raw/png]>と入力してください。",
                "-----------------------------"]
    for i in range(len(list_msg)):
        payload = {
            "to": room_name,
            "id": full_id,
            "message": list_msg[i]
        }
        if i != 0:
            print(f"\r{full_id}: {list_msg[i]}")
        await websocket.send(json.dumps(payload))
        await asyncio.sleep(0.1)

    sync_payload = {
        "to": room_name,
        "id": full_id,
        "message": f"/opsyncsave\n{content}"
    }
    await websocket.send(json.dumps(sync_payload))
    save = content


def generate_absolute_id():
    chars = string.ascii_letters + string.digits
    absolute_id = ''.join(secrets.choice(chars) for _ in range(5)) + "-" + ''.join(
        secrets.choice(chars) for _ in range(5))
    return absolute_id