"""BLEのみで動くチャット (メニュー6番)。

インターネットを使わず、近くの端末と Bluetooth Low Energy だけで会話する。
Achex 版 (5番) と同じコマンドループ (chat_functions.send_messages /
receive_messages) をそのまま使い、通信路だけ差し替えている。

構成は Achex のときと同じ形にしてある。
  make した端末が Peripheral になり、Achex サーバの役割 (受け取った発言を
  全員に配り直す) を肩代わりする。join した端末は Central として接続する。

BLE の制約から来る作りは ble_link.py 側にまとめてある。
"""

import asyncio
import json
import secrets
import sys
import time

import ble_link
import chat_functions
import chat_transport

# BLE のコントローラが Peripheral として同時に受けられる Central は、macOS や
# 一般的なアダプタで4〜7台程度。超えると黙って不安定になるので、明示的に断る。
MAX_GUESTS = 4

SCAN_TIMEOUT = 15.0       # 部屋を探す時間
HELLO_TIMEOUT = 3.0       # authok を待つ時間
HELLO_RETRY = 3           # hello を送り直す回数
ACK_TIMEOUT = 2.0         # 通知の到達確認を待つ時間
CHUNK_GAP = 0.015         # 通知を連投するときの間隔
PING_INTERVAL = 10.0      # ゲストが生存を知らせる間隔
SESSION_TIMEOUT = 30.0    # これだけ無音ならゲストが落ちたとみなす


class RoomNotFound(Exception):
    """指定した部屋のホストが電波の届く範囲に見つからなかった。"""


class RoomFull(Exception):
    """部屋が満員で断られた。"""


class _Ble:
    """bleak / bless から必要なものだけ集めた入れ物。"""

    def __init__(self):
        from bleak import BleakClient, BleakScanner
        from bless import (BlessServer, GATTAttributePermissions,
                           GATTCharacteristicProperties)
        self.BleakClient = BleakClient
        self.BleakScanner = BleakScanner
        self.BlessServer = BlessServer
        self.props = GATTCharacteristicProperties
        self.perms = GATTAttributePermissions


def _load_ble():
    """bleak / bless は重いので、6番を選んだときだけ読み込む。

    functions.py が pillow_heif をこうしているのと同じ方針。BLE の依存が
    入っていない環境でも1〜5番は動かせる。
    """
    try:
        return _Ble()
    except ImportError:
        print("エラー: BLEチャットには bleak と bless が必要です。")
        print("pip install -r requirements.txt を実行してください。")
        return None


class _BleTransportBase(chat_transport.ChatTransport):
    """ホストとゲストで共通の部分。"""

    display_name = "BLE"
    supports_files = False        # 帯域が狭いのでファイル転送は載せていない
    supports_generate = False
    supports_user_lookup = True   # 短いテキストの往復だけなのでBLEでも使える

    def __init__(self, secret, room_id, full_id):
        self._secret = secret
        self._room_id = room_id
        self._full_id = full_id
        self._loop = asyncio.get_running_loop()
        self._inbox = asyncio.Queue()
        self._msg_id = 0
        self._closed = False
        self._tasks = []

    # --- ChatTransport の実装 ---

    async def recv(self, timeout=None):
        if timeout is None:
            item = await self._inbox.get()
        else:
            item = await asyncio.wait_for(self._inbox.get(), timeout)
        if item is None:
            raise chat_transport.TransportClosed
        return item

    async def __anext__(self):
        item = await self._inbox.get()
        if item is None:
            raise chat_transport.TransportClosed
        return item

    # --- 共通の道具 ---

    def _next_msg_id(self):
        self._msg_id = (self._msg_id + 1) % 256
        return self._msg_id

    def _seal(self, frame):
        raw = json.dumps(frame, ensure_ascii=False).encode("utf-8")
        return ble_link.seal(raw, self._secret)

    def _open(self, body):
        """HMAC を確かめて JSON に戻す。不正なら None。"""
        raw = ble_link.unseal(body, self._secret)
        if raw is None:
            return None
        try:
            frame = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return frame if isinstance(frame, dict) else None

    def _deliver(self, frame):
        """チャット本体 (receive_messages) に Achex と同じ形で渡す。"""
        self._inbox.put_nowait(json.dumps({
            "to": frame.get("to", self._room_id),
            "id": frame.get("id", "unknown"),
            "message": frame.get("message", ""),
        }))

    def _system(self, text):
        """[System] からの発言として自分の画面に出す。"""
        self._inbox.put_nowait(json.dumps({
            "to": self._room_id, "id": "[System]", "message": text,
        }))

    def _on_drop(self, src, why):
        print(f"\r[System]メッセージを受け取れませんでした: {why}")
        print(f"{self._full_id}: ", end="", flush=True)

    async def _cancel_tasks(self):
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks = []


class BleHostTransport(_BleTransportBase):
    """make した側。Peripheral として広告し、全員の発言を配り直す。"""

    def __init__(self, secret, room_id, full_id):
        super().__init__(secret, room_id, full_id)
        self._ble = None
        self._server = None
        self._svc_uuid = None
        self._sessions = {}   # src -> {"id", "last", "mtu"}
        self._blocked = set()
        self._acks = {}       # msg_id -> ack を返した src の集合
        self._reasm = ble_link.Reassembler(on_drop=self._on_drop)
        self._rx_queue = asyncio.Queue()
        # 送信は必ずこのキューを通す。受信ポンプが送信の完了 (= ack の到着) を
        # 待ってしまうと、その ack を処理する者が居なくなって自分で詰まるため、
        # 受信と送信を別のタスクに分けている。
        self._tx_queue = asyncio.Queue()

    async def start(self, ble, room_name, room_password):
        self._ble = ble
        self._svc_uuid = ble_link.service_uuid(room_name, room_password)
        name = ble_link.advert_name(room_name, room_password)

        print(f"\r[System]部屋を作っています...")

        # BlessServer の生成は Bluetooth の電源が入るまでブロックする。
        # 電源が切れていると戻ってこないので、別スレッドに逃がして時間を区切る。
        loop = self._loop
        try:
            self._server = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ble.BlessServer(name=name, loop=loop)),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            raise chat_transport.TransportClosed(
                "Bluetoothが使える状態か確認してください") from None

        self._server.read_request_func = self._on_read
        self._server.write_request_func = self._on_write

        await self._server.add_new_service(self._svc_uuid)
        props, perms = ble.props, ble.perms
        await self._server.add_new_characteristic(
            self._svc_uuid, ble_link.RX_CHAR_UUID,
            props.write | props.write_without_response,
            None, perms.writeable,
        )
        # 値は None にしておく。CoreBluetooth は初期値を持つ characteristic を
        # read-only としか認めず、値を入れたまま notify を付けると
        # "Characteristics with cached values must be read-only" で弾かれる。
        await self._server.add_new_characteristic(
            self._svc_uuid, ble_link.TX_CHAR_UUID,
            props.notify | props.read,
            None, perms.readable,
        )
        # 名前は6文字なので UUID が広告から落とされることはないが、意図を明示する。
        await self._server.start(prioritize_local_name=False)

        # ホストは自分が認証する側。Achex と同じ経路を通すため自分に OK を流す。
        self._inbox.put_nowait('{"auth": "OK"}')
        self._tasks = [
            asyncio.create_task(self._rx_pump()),
            asyncio.create_task(self._tx_pump()),
            asyncio.create_task(self._watch()),
        ]

    # --- BLE からの入り口 ---

    def _on_read(self, characteristic, **kwargs):
        return characteristic.value or bytearray(b"\x00")

    def _on_write(self, characteristic, value, **kwargs):
        # CoreBluetooth のスレッドから呼ばれる。ここで待つと BLE 全体が
        # 止まるので、受け渡しだけしてすぐ戻る。
        if self._closed or characteristic is None:
            return
        if str(characteristic.uuid).lower() != ble_link.RX_CHAR_UUID.lower():
            return
        self._loop.call_soon_threadsafe(self._rx_queue.put_nowait, bytes(value))

    async def _rx_pump(self):
        while not self._closed:
            chunk = await self._rx_queue.get()
            ids = ble_link.peek(chunk)
            if ids is None or ids[0] in self._blocked:
                continue
            body = self._reasm.feed(chunk)
            if body is None:
                continue
            frame = self._open(body)
            if frame is None:
                # 部屋のパスワードを知らない相手。部屋の存在を教えないため、
                # 何も返さずに捨てる。守っているのは接続ではなく HMAC。
                continue
            try:
                await self._handle(frame, body)
            except chat_transport.TransportClosed:
                break
            except Exception as e:
                print(f"\r[System]エラー: {e}")

    async def _handle(self, frame, body):
        kind = frame.get("t")
        src = frame.get("src")
        if not isinstance(src, int):
            return

        if kind == "hello":
            await self._on_hello(frame, src)
            return

        session = self._sessions.get(src)
        if session is None:
            return  # 認証を通っていない相手は相手にしない
        session["last"] = time.monotonic()

        if kind == "msg":
            self._deliver(frame)
            # 本文はそのまま配り直す。HMAC は本文だけを対象にしているので、
            # ここで番号を振り直しても検証は通る。
            # 発言者本人にも返るが、receive_messages が自分の発言を捨てるので
            # Achex のときとまったく同じ見え方になる。
            self._enqueue(body)
        elif kind == "ack":
            ref = frame.get("ref_msg")
            # 送信待ちが残っているものだけ拾う。こうしないと、待つのをやめた
            # 後から届いた ack で _acks が増え続ける。
            if isinstance(ref, int) and ref in self._acks:
                self._acks[ref].add(src)
        elif kind == "bye":
            del self._sessions[src]
            await self._announce(f"{session['id']} が退出しました")
        elif kind == "ping":
            pass

    async def _on_hello(self, frame, src):
        gid = str(frame.get("id", "unknown"))
        if src in self._sessions:
            # authok が届かず送り直してきた場合。登録済みなので返事だけする。
            await self._send_frame({"t": "authok", "src": src}, expect_ack=False)
            return
        if len(self._sessions) >= MAX_GUESTS:
            await self._send_frame(
                {"t": "authng", "src": src, "reason": "full"}, expect_ack=False)
            return

        mtu = frame.get("mtu")
        self._sessions[src] = {
            "id": gid,
            "last": time.monotonic(),
            "mtu": mtu if isinstance(mtu, int) and mtu >= 23 else 23,
        }
        await self._send_frame({"t": "authok", "src": src}, expect_ack=False)
        joined = "が再接続しました" if frame.get("rejoin") else "が参加しました"
        await self._announce(f"{gid} {joined}")

    async def _announce(self, text):
        """[System] の発言として自分にも全ゲストにも見せる。"""
        self._system(text)
        await self._send_frame(
            {"t": "msg", "to": self._room_id, "id": "[System]", "message": text},
            expect_ack=False)

    # --- 送信 ---

    async def send(self, payload):
        frame = {"t": "msg"}
        frame.update(payload)
        done = asyncio.Event()
        self._enqueue(self._seal(frame), True, done)
        await done.wait()

    async def _send_frame(self, frame, expect_ack=True):
        self._enqueue(self._seal(frame), expect_ack)

    def _enqueue(self, body, expect_ack=True, done=None):
        if self._closed:
            if done is not None:
                done.set()
            raise chat_transport.TransportClosed
        self._tx_queue.put_nowait((body, expect_ack, done))

    async def _tx_pump(self):
        """送信はこのタスクだけが行う。順序が保たれ、通知も混ざらない。"""
        while not self._closed:
            body, expect_ack, done = await self._tx_queue.get()
            try:
                await self._broadcast(body, expect_ack)
            except chat_transport.TransportClosed:
                break
            except Exception as e:
                print(f"\r[System]エラー: {e}")
            finally:
                if done is not None:
                    done.set()

    async def _broadcast(self, body, expect_ack=True):
        if self._closed:
            raise chat_transport.TransportClosed
        payload = self._chunk_payload()

        # notify は ATT の確認応答が無いので、届いたかどうかは
        # アプリ側の ack で確かめ、駄目なら1度だけ送り直す。
        for _attempt in range(2):
            msg_id = self._next_msg_id()
            waiting = set(self._sessions) if expect_ack else set()
            self._acks[msg_id] = set()
            try:
                chunks = ble_link.pack(body, ble_link.HOST_SRC, msg_id, payload)
            except ValueError as e:
                self._acks.pop(msg_id, None)
                print(f"\r[System]エラー: {e}")
                return
            try:
                for chunk in chunks:
                    await self._notify(chunk)
                    await asyncio.sleep(CHUNK_GAP)
                if not waiting or await self._wait_acks(msg_id, waiting):
                    return
            finally:
                self._acks.pop(msg_id, None)
        print(f"\r[System]送信できませんでした")
        print(f"{self._full_id}: ", end="", flush=True)

    async def _wait_acks(self, msg_id, waiting):
        deadline = time.monotonic() + ACK_TIMEOUT
        while time.monotonic() < deadline:
            if waiting <= self._acks.get(msg_id, set()):
                return True
            await asyncio.sleep(0.05)
            waiting &= set(self._sessions)  # 途中で抜けた人は待たない
            if not waiting:
                return True
        return waiting <= self._acks.get(msg_id, set())

    async def _notify(self, chunk):
        char = self._server.get_characteristic(ble_link.TX_CHAR_UUID)
        if char is None:
            raise chat_transport.TransportClosed
        # bless 0.3.0 は「送信できるようになった」通知を公開していないので、
        # 送信キューが空くまで短い間隔で試し続ける。
        for _ in range(50):
            char.value = bytearray(chunk)
            if self._server.update_value(self._svc_uuid, ble_link.TX_CHAR_UUID):
                return
            await asyncio.sleep(0.02)
        raise chat_transport.TransportClosed("通知を送信できませんでした")

    def _chunk_payload(self):
        # ホストからは相手の MTU を直接見られない (bless 0.3.0 は CBCentral を
        # 渡してくれない) ので、hello で申告された値の最小を使う。
        mtus = [s["mtu"] for s in self._sessions.values()]
        mtu = min(mtus) if mtus else 23
        return max(ble_link.MIN_CHUNK_PAYLOAD, min(mtu, 247) - 3 - ble_link.HDR_LEN)

    # --- 見張り ---

    async def _watch(self):
        while not self._closed:
            await asyncio.sleep(5.0)
            self._reasm.sweep()

            now = time.monotonic()
            for src, s in list(self._sessions.items()):
                if now - s["last"] > SESSION_TIMEOUT:
                    del self._sessions[src]
                    try:
                        await self._announce(f"{s['id']} が切断されました")
                    except chat_transport.TransportClosed:
                        pass

            try:
                advertising = await self._server.is_advertising()
            except Exception:
                advertising = True
            if not advertising and not self._closed:
                chat_functions.notify_disconnected()

    async def close(self):
        self._closed = True
        self._inbox.put_nowait(None)
        await self._cancel_tasks()
        try:
            await self._server.stop()
        except Exception:
            pass


class BleGuestTransport(_BleTransportBase):
    """join した側。Central としてホストに接続する。"""

    def __init__(self, secret, room_id, full_id):
        super().__init__(secret, room_id, full_id)
        self._ble = None
        self._client = None
        self._src = secrets.randbits(16) or 1  # 0 はホストが使う
        self._write_size = 20
        # 1つのメッセージのチャンクが他のメッセージと混ざらないようにする。
        # ホスト側は送信タスクが1本だけなので、こちらにだけ必要。
        self._send_lock = asyncio.Lock()
        # _settled は「ホストが返事をした」、_authed は「通った」。分けておかないと
        # 満員で断られた場合と返事が無い場合を区別できない。
        self._settled = asyncio.Event()
        self._authed = False
        self._auth_error = None
        self._reasm = ble_link.Reassembler(on_drop=self._on_drop)

    async def connect(self, ble, room_name, room_password, rejoin):
        self._ble = ble
        svc_uuid = ble_link.service_uuid(room_name, room_password).lower()

        print(f"\r[System]部屋を探しています...")
        device = await ble.BleakScanner.find_device_by_filter(
            lambda d, adv: svc_uuid in [u.lower() for u in (adv.service_uuids or [])],
            timeout=SCAN_TIMEOUT,
        )
        if device is None:
            raise RoomNotFound

        print(f"\r[System]接続しています...")
        self._client = ble.BleakClient(
            device, disconnected_callback=self._on_disconnected, timeout=30.0)
        await self._client.connect()
        await self._client.start_notify(ble_link.TX_CHAR_UUID, self._on_notify)

        mtu = getattr(self._client, "mtu_size", 0) or 23
        chrc = self._client.services.get_characteristic(ble_link.RX_CHAR_UUID)
        self._write_size = max(
            20, min(getattr(chrc, "max_write_without_response_size", 20) or 20, 244))

        hello = {"t": "hello", "src": self._src, "id": self._full_id,
                 "mtu": int(mtu), "rejoin": bool(rejoin)}
        # authok が届かないことがあるので、返事が来るまで hello を送り直す。
        for _ in range(HELLO_RETRY):
            await self._send_frame(hello)
            try:
                await asyncio.wait_for(self._settled.wait(), HELLO_TIMEOUT)
                break
            except asyncio.TimeoutError:
                continue
        if self._auth_error == "full":
            raise RoomFull
        if not self._authed:
            raise chat_transport.TransportClosed("ホストから応答がありませんでした")

        self._tasks = [asyncio.create_task(self._ping_loop())]

    # --- BLE からの入り口 ---

    def _on_notify(self, _sender, data):
        # bleak の CoreBluetooth バックエンドはイベントループ上で呼ぶ。
        # 念のため、ループ外から来ても安全なように渡し方を揃えておく。
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self._loop.call_soon_threadsafe(self._handle_chunk, bytes(data))
            return
        self._handle_chunk(bytes(data))

    def _handle_chunk(self, chunk):
        ids = ble_link.peek(chunk)
        if ids is None:
            return
        body = self._reasm.feed(chunk)
        if body is None:
            return
        frame = self._open(body)
        if frame is None:
            return
        asyncio.ensure_future(self._handle(frame, ids[1]), loop=self._loop)

    async def _handle(self, frame, msg_id):
        kind = frame.get("t")
        if kind == "msg":
            self._deliver(frame)
            # 届いたことをホストに知らせる。ホストはこれが揃わないと送り直す。
            await self._send_frame(
                {"t": "ack", "src": self._src, "ref_msg": msg_id})
        elif kind == "authok":
            if frame.get("src") == self._src and not self._authed:
                self._authed = True
                self._inbox.put_nowait('{"auth": "OK"}')
                self._settled.set()
        elif kind == "authng":
            if frame.get("src") == self._src:
                self._auth_error = frame.get("reason") or "ng"
                self._settled.set()

    # --- 送信 ---

    async def send(self, payload):
        frame = {"t": "msg", "src": self._src}
        frame.update(payload)
        await self._send_frame(frame)

    async def _send_frame(self, frame):
        if self._closed:
            raise chat_transport.TransportClosed
        body = self._seal(frame)
        payload = max(ble_link.MIN_CHUNK_PAYLOAD, self._write_size - ble_link.HDR_LEN)
        async with self._send_lock:
            msg_id = self._next_msg_id()
            try:
                chunks = ble_link.pack(body, self._src, msg_id, payload)
            except ValueError as e:
                print(f"\r[System]エラー: {e}")
                return
            for chunk in chunks:
                try:
                    # response=True にすると ATT が1件ずつ応答を返すので、
                    # 送信キューが溢れてチャンクが黙って消えることがない。
                    await self._client.write_gatt_char(
                        ble_link.RX_CHAR_UUID, chunk, response=True)
                except Exception:
                    raise chat_transport.TransportClosed from None

    async def _ping_loop(self):
        while not self._closed:
            await asyncio.sleep(PING_INTERVAL)
            try:
                await self._send_frame({"t": "ping", "src": self._src})
            except chat_transport.TransportClosed:
                break
            except Exception:
                break

    def _on_disconnected(self, _client):
        if self._closed:
            return
        self._closed = True
        self._inbox.put_nowait(None)

    async def close(self):
        if not self._closed:
            try:
                await self._send_frame(
                    {"t": "bye", "src": self._src, "id": self._full_id})
            except Exception:
                pass
        self._closed = True
        self._inbox.put_nowait(None)
        await self._cancel_tasks()
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass


async def connect_and_run(ble, mode, my_name, room_name, room_password,
                          absolute_id, rejoin):
    """1回分の接続。切断されて再接続を求められたら "reconnect" を返す。"""
    chat_functions.reset_disconnected()

    secret = ble_link.room_secret(room_name, room_password)
    room_id = ble_link.room_id_hex(room_name, room_password)
    full_id = f"[{absolute_id}]{my_name}"

    if mode == "make":
        transport = BleHostTransport(secret, room_id, full_id)
        await transport.start(ble, room_name, room_password)
    else:
        transport = BleGuestTransport(secret, room_id, full_id)
        await transport.connect(ble, room_name, room_password, rejoin)

    # 認証の待ち方は Achex 版と同じ。通信路が {"auth": "OK"} を流してくる。
    try:
        while True:
            res_data = json.loads(await transport.recv(timeout=10.0))
            if "auth" in res_data:
                if res_data["auth"] == "OK":
                    print("\r[System]認証が成功しました")
                    break
                print(f"\r[System]エラー: 認証に失敗しました。")
                print(f"\r中止")
                sys.exit()
    except asyncio.TimeoutError:
        print(f"\r[System]エラー: 認証に失敗しました。")
        print(f"\r中止")
        sys.exit()

    print(f"\r-----------------------------")
    print(f"\rあなたのユーザーネーム: {my_name}")
    print(f"\rあなたのID: {absolute_id}")
    print(f"\r部屋のID: {room_name}")
    print(f"\r部屋のパスワード: {room_password}")
    print(f"\rあなたの役割: {'ホスト (make)' if mode == 'make' else 'ゲスト (join)'}")
    print(f"\r-----------------------------")
    if mode == "make":
        print(f"\r[System]部屋を作りました。参加者を待っています")
    print(f"\r[System]接続しました。退出するには/exitと入力してください")
    print(f"\r[System]全てのコマンドを出力するには、/cmdと入力してください")

    receive_task = asyncio.create_task(
        chat_functions.receive_messages(transport, my_name, full_id, room_id, absolute_id))
    send_task = asyncio.create_task(
        chat_functions.send_messages(transport, my_name, full_id, room_id, absolute_id))
    try:
        result = await send_task
    finally:
        receive_task.cancel()
        await transport.close()
    return result


async def main():
    print("BLEのみで通信します。インターネットには接続しません。")
    print("BLEの通信内容は暗号化されません。パスワードや個人情報を送らないでください。")
    print(f"同時に参加できるのは、ホストを除いて{MAX_GUESTS}人までです。")
    print("届く距離はおおよそ5〜15mです。壁を挟むと大きく短くなります。")
    if sys.platform == "darwin":
        print("macOSでは、Bluetoothの利用許可を持たないアプリから実行すると")
        print("macOSがプロセスを強制終了します。PyCharmから実行してください。")

    ble = _load_ble()
    if ble is None:
        return

    my_name, room_name, room_password = chat_functions.prompt_room_info()

    print("make  ... この端末が部屋のホストになります")
    print("join  ... 既にある部屋に参加します")
    print("leave ... 何もせずに終了します")
    while True:
        mode = input("make / join / leave を選択: ").strip().lower()
        if mode in ("make", "join", "leave"):
            break
        print("エラー: make、join、又はleaveを入力してください")

    if mode == "leave":
        print("\r[System]退出しました")
        return

    # 再接続しても同じ人物として戻れるよう、IDは最初に1回だけ作る
    absolute_id = chat_functions.generate_absolute_id()
    connected_before = False
    rejoin = False

    while True:
        try:
            result = await connect_and_run(
                ble, mode, my_name, room_name, room_password, absolute_id, rejoin)
        except RoomNotFound:
            print(f"\r[System]エラー: 部屋が見つかりませんでした")
            print(f"\r[System]部屋のIDとパスワードが合っているか、")
            print(f"\r[System]ホストが近く(5〜15m以内)にいるかを確認してください")
            print(f"\r中止")
            return
        except RoomFull:
            print(f"\r[System]エラー: 部屋が満員です (ゲストは{MAX_GUESTS}人まで)")
            print(f"\r中止")
            return
        except Exception as e:
            if not connected_before:
                print(f"\r[System]エラー: {e}")
                print(f"\r中止")
                return

            print(f"\r[System]再接続に失敗しました: {e}")
            print(f"\r[System]続けるにはconnect と入力して再接続してください")
            if not await chat_functions.wait_for_connect():
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
