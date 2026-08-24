import asyncio
import json
import ssl
import sys
import certifi
import websockets
import functions
import secrets
import string
import re
import hashlib
import os
import mimetypes
import cv2
import math

save = None
disconnected = False


def notify_disconnected():
    """切断を1回だけ通知する。再接続の入力は send_messages の input が受け取る。"""
    global disconnected
    if disconnected:
        return
    disconnected = True
    print("\r[System]接続が切れました")
    print("\r[System]続けるにはconnect と入力して再接続してください")


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
        pass

    # サーバー側から正常に閉じられた場合は async for が終わるだけで例外が出ないため、
    # ここで切断をまとめて通知する
    notify_disconnected()


async def send_messages(websocket, my_name, full_id, room_name, absolute_id):
    global save
    loop = asyncio.get_running_loop()

    while True:
        msg = await loop.run_in_executor(None, input, f"{full_id}: ")

        if disconnected:
            if msg.strip() == "connect":
                return "reconnect"
            if msg.strip() == "/exit":
                return None
            print(f"\r[System]接続が切れています。connect と入力すると再接続します")
            continue

        if not msg.strip():
            continue

        try:
            if msg.strip() == "/exit":
                print(f"\r[System]退出しました")
                payload = {
                    "to": room_name,
                    "id": full_id,
                    "message": f"[System]{full_id} が退出しました"
                }
                await websocket.send(json.dumps(payload))
                break

            elif msg.strip() == "/help":
                functions.help_list()

            elif msg.strip() == "/cmd":
                functions.command_list()

            elif msg.strip() == "/clear":
                functions.clear_screen()

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
                                    print(f"\r[Helper]エラー: 画像の生成に失敗しました")

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

            elif msg.strip() == "/show":
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
        except websockets.exceptions.ConnectionClosed:
            notify_disconnected()
            continue


async def wait_for_connect():
    """再接続の入力を待つ。connect なら True、/exit なら False を返す。"""
    loop = asyncio.get_running_loop()

    while True:
        msg = await loop.run_in_executor(None, input, "")
        if msg.strip() == "connect":
            return True
        if msg.strip() == "/exit":
            return False
        print(f"\r[System]接続が切れています。connect と入力すると再接続します")


async def connect_and_run(my_name, room_name, room_password, absolute_id, rejoin):
    """1回分の接続。切断されて再接続を求められたら "reconnect" を返す。"""
    global disconnected
    disconnected = False

    uri = f"wss://cloud.achex.ca/chat"

    # Achex のサーバは ECDHE/DHE (前方秘匿性のある鍵交換) に対応しておらず、
    # RSA 鍵交換の AES256-GCM-SHA384 しか受け付けない。Python 3.10 以降の既定の
    # 暗号リストは前方秘匿性のあるスイートだけなので、そのままでは共通の暗号が
    # 無く、サーバに切断されて SSLEOFError になる。そのため RSA 鍵交換の GCM
    # スイートを明示的に足している。証明書の検証(チェーン・ホスト名)は有効なまま。
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.set_ciphers("ECDHE+AESGCM:DHE+AESGCM:AES256-GCM-SHA384:AES128-GCM-SHA256")

    print(f"\r[System]Connecting to {uri}...")

    headers = {
        # Achex は Origin ヘッダの無い WebSocket ハンドシェイクを拒否する
        # (付けないと HTTP の応答すら返ってこない)。値の内容は問われないが、
        # 接続先を明示する意味でサービス自身の URL を入れている。
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

        full_id = f"[{absolute_id}]{my_name}"
        joined = "が再接続しました" if rejoin else "が参加しました"
        await websocket.send(json.dumps({"to": real_room_id, "id": "[System]", "message": f"{full_id} {joined}"}))
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

        result = await send_task
        receive_task.cancel()
        return result


async def main():
    print("匿名性は低いです。パスワードや個人情報を送らないでください。")
    print("通信はTLSで暗号化され証明書も検証しますが、Achex側の制約で前方秘匿性はありません。")
    my_name = input("使用するユーザーネームを入力: ")
    room_name = input("参加する部屋のIDを入力: ")
    print("パスワードは入力しなくてもデフォルトでpasswordになります。")
    room_password = input("参加する部屋のパスワードを入力: ")
    if not room_password:
        room_password = "password"

    # 再接続しても同じ人物として戻れるよう、IDは最初に1回だけ作る
    absolute_id = generate_absolute_id()
    connected_before = False
    rejoin = False

    while True:
        try:
            result = await connect_and_run(my_name, room_name, room_password, absolute_id, rejoin)
        except Exception as e:
            if not connected_before:
                print(f"\r[System]エラー: {e}")
                print(f"\r中止")
                sys.exit()

            print(f"\r[System]再接続に失敗しました: {e}")
            print(f"\r[System]続けるにはconnect と入力して再接続してください")
            if not await wait_for_connect():
                print(f"\r[System]退出しました")
                break
            rejoin = True
            continue

        connected_before = True
        if result != "reconnect":
            break

        rejoin = True
        print(f"\r[System]再接続します...")


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

            img = functions.read_image(path)
            if img is None:
                print(f"\r[Helper]エラー: 指定された物は画像ではありません。")
                return
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
                else:
                    print(f"\r[Helper]エラー: 指定された物は画像ではありません。")

            elif color == "color":
                if mime_type and mime_type.startswith('image'):
                    resized_rgb = cv2.resize(rgb, (size, height))
                    resized_gray = cv2.resize(gray, (size, height))
                    pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
                    pixels_gray = resized_gray.flatten().astype(int)
                    result = functions.rgb_generator(functions.ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, size)
                    print(f"\r{result}")
                    await uploaded(result, f"{path}のカラーASCII ART", room_name, full_id, websocket, msg)
                else:
                    print(f"\r[Helper]エラー: 指定された物は画像ではありません。")
            else:
                print(f"\r[Helper]エラー: gray又はcolorを選択してください。")

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