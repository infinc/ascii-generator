import asyncio
import json
import ssl
import sys
import certifi
import websockets
import chat_transport
import functions
import secrets
import string
import re
import hashlib
import os
import cv2
import math
import codecs
import select
import shutil
import threading
import unicodedata

# input() は readline を読み込んでおくと行編集 (矢印キーなど) に対応する。
# チャット中の入力欄だけは下の LineEditor を使う。
try:
    import readline  # noqa: F401
except ImportError:
    readline = None

# 端末を1文字ずつ読むのに使う。Windows には無い。
try:
    import termios
except ImportError:
    termios = None

save = None
disconnected = False


# 入出力が端末 (tty) のときだけ、入力欄を描き直しながら受信を表示できる。
# PyCharm の通常の実行コンソールは端末ではないので \r や \x1b[K が効かない。
# その場合は描き直しをせずに出すだけにする。
INTERACTIVE = termios is not None and sys.stdin.isatty() and sys.stdout.isatty()


def _display_width(s):
    """端末上での幅。全角は2、結合文字は0として数える。"""
    w = 0
    for c in s:
        if unicodedata.combining(c):
            continue
        w += 2 if unicodedata.east_asian_width(c) in "WF" else 1
    return w


class LineEditor:
    """チャットの入力欄。input() の代わりに1文字ずつ読んで自分で描く。

    input() (readline) は別スレッドで待たせているので、受信を表示するときに
    入力欄を描き直す手段が無い。macOS の libedit は get_line_buffer() が
    Enter の後も前の行を返し続け、redisplay() も次のキー入力まで何も描かない。
    そのため入力欄が消えたり、プロンプトが2つ出たりしていた。入力中の文字と
    画面の状態をここで持っておけば、いつでも正しく描き直せる。

    できる編集は文字の追加、Backspace、Ctrl-U (全消去)、Ctrl-W (1語消去) だけ。
    矢印キーなどのエスケープシーケンスは読み捨てる。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._prompt = None   # 入力待ちでないときは None
        self._buf = []
        self._rows = 0        # 入力欄の描画で使っている行数 - 1 (カーソルの行)
        self._cancel = threading.Event()

    # --- 描画 (必ず _lock を取ってから呼ぶ) ---

    def _erase(self):
        """入力欄を消して、カーソルを入力欄の先頭に戻す。"""
        if self._rows:
            sys.stdout.write(f"\x1b[{self._rows}A")
        sys.stdout.write("\r\x1b[J")
        self._rows = 0

    def _draw(self):
        line = self._prompt + "".join(self._buf)
        sys.stdout.write(line)
        cols = shutil.get_terminal_size().columns or 80
        w = _display_width(line)
        # 行末ちょうどで止まったときは、多くの端末で次の文字まで折り返さない
        self._rows = max(0, (w - 1) // cols) if w else 0

    def print_above(self, text):
        """入力欄の上に text を出し、入力欄を描き直す。"""
        with self._lock:
            if self._prompt is None:
                sys.stdout.write(f"\r\x1b[K{text}\n")
            else:
                self._erase()
                sys.stdout.write(f"{text}\n")
                self._draw()
            sys.stdout.flush()

    # --- 入力 ---

    def cancel(self):
        """読み込み中のスレッドを終わらせる。Ctrl-C で抜けるときに使う。"""
        self._cancel.set()

    def read_line(self, prompt):
        """1行読む。別スレッドで呼ぶ。input() と同じく EOF で EOFError。"""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        # 行単位のバッファとエコーを切る。ISIG は残すので Ctrl-C は効く。
        new[3] &= ~(termios.ICANON | termios.ECHO)
        new[6][termios.VMIN] = 1
        new[6][termios.VTIME] = 0
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        esc = None  # エスケープシーケンスを読み捨て中なら、そこまでの文字列

        self._cancel.clear()
        with self._lock:
            self._prompt = prompt
            self._buf = []
            self._draw()
            sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        try:
            while True:
                # 定期的に起きて、cancel() されていないか確かめる
                r, _, _ = select.select([fd], [], [], 0.1)
                if self._cancel.is_set():
                    raise EOFError
                if not r:
                    continue
                data = os.read(fd, 1024)
                if not data:
                    raise EOFError
                for c in decoder.decode(data):
                    if esc is not None:
                        esc += c
                        # ESC [ ... 終端文字 / ESC O x / ESC x のどれかで終わる
                        if len(esc) == 2 and c not in "[O":
                            esc = None
                        elif len(esc) >= 3 and (esc[1] == "O" or "@" <= c <= "~"):
                            esc = None
                        continue
                    with self._lock:
                        if c in "\r\n":
                            line = "".join(self._buf)
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                            self._prompt = None
                            self._rows = 0
                            return line
                        if c == "\x1b":
                            esc = c
                            continue
                        if c == "\x04":           # Ctrl-D
                            if not self._buf:
                                raise EOFError
                            continue
                        if c in "\x7f\x08":        # Backspace
                            if not self._buf:
                                continue
                            self._buf.pop()
                        elif c == "\x15":          # Ctrl-U
                            self._buf = []
                        elif c == "\x17":          # Ctrl-W
                            while self._buf and self._buf[-1] == " ":
                                self._buf.pop()
                            while self._buf and self._buf[-1] != " ":
                                self._buf.pop()
                        elif c == "\t":
                            self._buf.append(" ")
                        elif c < " ":
                            continue               # その他の制御文字は無視
                        else:
                            self._buf.append(c)
                        self._erase()
                        self._draw()
                        sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            with self._lock:
                self._prompt = None
                self._rows = 0


_editor = LineEditor() if INTERACTIVE else None


async def read_chat_line(prompt):
    """チャットの入力欄から1行読む。端末でなければ input() を使う。"""
    loop = asyncio.get_running_loop()
    if _editor is None:
        return await loop.run_in_executor(None, input, prompt)
    try:
        return await loop.run_in_executor(None, _editor.read_line, prompt)
    except asyncio.CancelledError:
        # スレッドは待たせたままだと終了時に join で止まり、端末の設定も
        # 戻らないので、ここで抜けさせる。
        _editor.cancel()
        raise


def show_incoming(text, full_id=None):
    """入力待ちの途中で届いた表示を、打ちかけの文字を残したまま出す。

    受信は入力を待っている最中に起きる。そのまま print すると、プロンプトと
    入力途中の文字が上書きされて見えなくなるため、入力欄を消して本文を出したあと、
    入力欄を描き直す。full_id は以前の呼び出し方との互換のために残している。
    """
    if _editor is None:
        # 打ちかけの文字は消せないので、それとは別の行に出す。
        # プロンプトを出し直すと、打ちかけの文字が消えたように見えるので出さない。
        print(f"\n{text}", flush=True)
        return
    _editor.print_above(text)


def warn_if_not_terminal():
    """端末でないと受信時の表示が崩れるので、直し方を案内する。"""
    if INTERACTIVE:
        return
    print("[System]注意: 端末ではない画面で実行されているため、入力中にメッセージが届くと表示が乱れます。")
    print("[System]PyCharm では、実行構成の「Modify options」→「Emulate terminal in output console」を有効にしてください。")

# コマンドと、それを使うために通信路が備えている必要がある機能の対応。
_CAP_FOR_CMD = {
    "/file": "supports_files",
    "/show": "supports_files",
    "/download": "supports_files",
    "/generate": "supports_generate",
    "/user": "supports_user_lookup",
}


def reset_disconnected():
    """新しい接続を張る前に切断フラグを戻す。ble_chat からも使う。"""
    global disconnected
    disconnected = False


def notify_disconnected():
    """切断を1回だけ通知する。再接続の入力は send_messages の input が受け取る。"""
    global disconnected
    if disconnected:
        return
    disconnected = True
    show_incoming("[System]接続が切れました")
    show_incoming("[System]続けるにはconnect と入力して再接続してください")


async def receive_messages(transport, my_name, full_id, room_name, absolute_id):
    global save
    try:
        async for message in transport:
            data = json.loads(message)

            if data.get("auth") == "OK":
                print("\r[System]認証が成功しました")
                continue
            msg = data.get("message")
            if msg:
                sender = data.get("id", "unknown")
                if sender == full_id:
                    continue

                if msg.startswith("/user ") and transport.supports_user_lookup:
                    target_user = msg.split(" ", 1)[1].strip()
                    if target_user in (my_name, absolute_id, full_id):
                        payload = {
                            "to": room_name,
                            "id": full_id,
                            "message": f"/opfounduser {sender}"
                        }
                        await transport.send(payload)
                    continue
                elif msg.startswith("/opfounduser "):
                    requester = msg.split(" ", 1)[1].strip()
                    if full_id == requester:
                        show_incoming(f"[System]{sender} は現在オンラインです", full_id)
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
                        show_incoming(f"[{sender} (最新のファイル)]:\n{content}", full_id)

                    continue
                show_incoming(f"{sender}: {msg}", full_id)

                if (msg.strip() == "/show" and sender != full_id
                        and save is not None and transport.supports_files):
                    payload = {
                        "to": room_name,
                        "id": full_id,
                        "message": f"/opfiledm {sender}\n{save}"
                    }
                    await transport.send(payload)
    except chat_transport.TransportClosed:
        pass

    # サーバー側から正常に閉じられた場合は async for が終わるだけで例外が出ないため、
    # ここで切断をまとめて通知する
    notify_disconnected()


async def send_messages(transport, my_name, full_id, room_name, absolute_id):
    global save

    while True:
        msg = await read_chat_line(f"{full_id}: ")

        if disconnected:
            if msg.strip() == "connect":
                return "reconnect"
            if msg.strip() == "/exit":
                return None
            print(f"\r[System]接続が切れています。connect と入力すると再接続します")
            continue

        if not msg.strip():
            continue

        # 通信方式によって使えないコマンドをここで弾く。
        # 黙って失敗させずに理由を出す。
        cmd = msg.strip().split(" ", 1)[0] if msg.strip().startswith("/") else ""
        cap = _CAP_FOR_CMD.get(cmd)
        if cap and not getattr(transport, cap):
            print(f"\r[System]{cmd} は{transport.display_name}では未対応です")
            continue

        try:
            if msg.strip() == "/exit":
                print(f"\r[System]退出しました")
                payload = {
                    "to": room_name,
                    "id": full_id,
                    "message": f"[System]{full_id} が退出しました"
                }
                await transport.send(payload)
                break

            elif msg.strip() == "/help":
                functions.help_list()

            elif msg.strip() == "/cmd":
                functions.command_list(transport)

            elif msg.strip() == "/clear":
                functions.clear_screen()

            elif msg.startswith("/generate "):
                await instant_generate(msg, my_name, full_id, room_name, transport)

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
                        await uploaded(file_content, file, room_name, full_id, transport, msg)

                    except Exception as e:
                        print(f"\r[Helper]エラー: {e}")
                        continue
                else:
                    print(f"\r[Helper]エラー: {file} が存在しません。")

            elif msg.startswith("/user "):
                target_user = msg[6:].strip()
                if not target_user:
                    print(f"\r[System]コマンド: /user <user_nameid>")
                    continue

                if target_user in (my_name, absolute_id, full_id):
                    print(f"\r[System]指定した人は自分自身です。")
                    continue

                print(f"\r[System]{target_user} を検索しています...")

                payload = {
                    "to": room_name,
                    "id": full_id,
                    "message": f"/user {target_user}"
                }
                await transport.send(payload)

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
                        await transport.send(payload)

                    except Exception:
                        print(f"\r[Helper]エラー: ダウンロードするファイルが存在しません")
            else:
                payload = {
                    "to": room_name,
                    "id": full_id,
                    "message": msg
                }
                await transport.send(payload)
        except chat_transport.TransportClosed:
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
    reset_disconnected()

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
        transport = chat_transport.WebSocketTransport(websocket)
        secret_key = f"{room_name}::{room_password}"
        real_room_id = hashlib.sha256(secret_key.encode()).hexdigest()

        auth_data = {
            "auth": real_room_id
        }

        await transport.send(auth_data)

        try:
            while True:
                response = await transport.recv(timeout=5.0)
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
        await transport.send({"to": real_room_id, "id": "[System]", "message": f"{full_id} {joined}"})
        print(f"\r-----------------------------")
        print(f"\rあなたのユーザーネーム: {my_name}")
        print(f"\rあなたのID: {absolute_id}")
        print(f"\r部屋のID: {room_name}")
        print(f"\r部屋のパスワード: {room_password}")
        print(f"\r-----------------------------")
        print(f"\r[System]接続しました。退出するには/exitと入力してください")
        print(f"\r[System]全てのコマンドを出力するには、/cmdと入力してください")

        receive_task = asyncio.create_task(receive_messages(transport, my_name, full_id, real_room_id, absolute_id))
        send_task = asyncio.create_task(send_messages(transport, my_name, full_id, real_room_id, absolute_id))

        result = await send_task
        receive_task.cancel()
        return result


def prompt_room_info():
    """ユーザー名・部屋ID・パスワードを聞く。Achex と BLE で共通。"""
    warn_if_not_terminal()
    my_name = input("使用するユーザーネームを入力: ")
    room_name = input("参加する部屋のIDを入力: ")
    print("パスワードは入力しなくてもデフォルトでpasswordになります。")
    room_password = input("参加する部屋のパスワードを入力: ")
    if not room_password:
        room_password = "password"
    return my_name, room_name, room_password


async def main():
    print("匿名性は低いです。パスワードや個人情報を送らないでください。")
    print("通信はTLSで暗号化され証明書も検証しますが、Achex側の制約で前方秘匿性はありません。")
    my_name, room_name, room_password = prompt_room_info()

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


async def instant_generate(msg, my_name, full_id, room_name, transport):
    try:
        parts = msg.split()
        # factor は省略可 (省略時は 0.55)
        if len(parts) not in (4, 5):
            print(f"\r[System]コマンド: /generate <path> <[gray/color]> <width> [factor]")
            return

        path = parts[1]
        color = parts[2]
        size = int(parts[3])
        correction_factor = float(parts[4]) if len(parts) == 5 else 0.55

        if not os.path.exists(path):
            print(f"\r[System]エラー: {path} は存在しません。")
            return

        if not functions.is_image_path(path):
            print(f"\r[Helper]エラー: 指定された物は画像ではありません。")
            return

        img = functions.read_image(path)
        if img is None:
            print(f"\r[Helper]エラー: 指定された物は画像ではありません。")
            return
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width = gray.shape

        if width >= size:
            height = math.ceil(height * (size / width) * correction_factor)
        else:
            print(f"\r[System]エラー: 画像のサイズよりも大きい値を入力することはできません。")
            return

        if color == "gray":
            resized_gray = cv2.resize(gray, (size, height))
            pixels = resized_gray.flatten().astype(int)
            result = functions.gray_generator(functions.ASCII_CHARS_NORMAL, pixels, size)
            print(f"\r{result}")
            await uploaded(result, f"{path} の白黒ASCII ART", room_name, full_id, transport, msg)

        elif color == "color":
            resized_rgb = cv2.resize(rgb, (size, height))
            resized_gray = cv2.resize(gray, (size, height))
            pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
            pixels_gray = resized_gray.flatten().astype(int)
            result = functions.rgb_generator(functions.ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, size)
            print(f"\r{result}")
            await uploaded(result, f"{path}のカラーASCII ART", room_name, full_id, transport, msg)
        else:
            print(f"\r[Helper]エラー: gray又はcolorを選択してください。")
    except Exception as e:
        print(f"\r[System]エラー: {e}")


async def uploaded(content, display_name, room_name, full_id, transport, msg):
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
        await transport.send(payload)
        await asyncio.sleep(0.1)

    sync_payload = {
        "to": room_name,
        "id": full_id,
        "message": f"/opsyncsave\n{content}"
    }
    await transport.send(sync_payload)
    save = content


def generate_absolute_id():
    chars = string.ascii_letters + string.digits
    absolute_id = ''.join(secrets.choice(chars) for _ in range(5)) + "-" + ''.join(
        secrets.choice(chars) for _ in range(5))
    return absolute_id