"""チャットの通信路を抽象化する。

chat_functions.py のコマンドループ (send_messages / receive_messages) は、
通信路に対して次の3種類の操作しかしない。

  * send(payload)        メッセージを1件送る
  * recv(timeout=...)    メッセージを1件待つ (認証ハンドシェイクでのみ使う)
  * async for            受信ループ

この3つだけを ChatTransport として切り出すことで、同じコマンドループを
Achex (WebSocket) と BLE の両方で使い回せる。
"""

import asyncio
import json

import websockets


class TransportClosed(Exception):
    """通信路が切れたことを示す。通信方式に依存しない例外。"""


class ChatTransport:
    """通信路の共通インターフェース。

    supports_* は、その通信路で使えるコマンドを示す。send_messages が
    これを見て未対応コマンドを弾くので、通信方式ごとの分岐 (isinstance など) を
    コマンドループ側に書かずに済む。
    """

    display_name = "?"
    supports_files = False        # /file /show /download
    supports_generate = False     # /generate
    supports_user_lookup = False  # /user

    async def send(self, payload: dict) -> None:
        raise NotImplementedError

    async def recv(self, timeout: float | None = None) -> str:
        """受信したメッセージを JSON 文字列のまま返す。"""
        raise NotImplementedError

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        pass


class WebSocketTransport(ChatTransport):
    """Achex (wss://cloud.achex.ca/chat) 用。

    json.dumps と ConnectionClosed の変換をするだけで、送るバイト列は
    リファクタ前と同一。
    """

    display_name = "Achex"
    supports_files = True
    supports_generate = True
    supports_user_lookup = True

    def __init__(self, websocket):
        self._ws = websocket
        self._it = websocket.__aiter__()

    async def send(self, payload: dict) -> None:
        try:
            await self._ws.send(json.dumps(payload))
        except websockets.exceptions.ConnectionClosed:
            raise TransportClosed from None

    async def recv(self, timeout: float | None = None) -> str:
        coro = self._ws.recv()
        if timeout is None:
            return await coro
        return await asyncio.wait_for(coro, timeout)

    async def __anext__(self) -> str:
        # 正常終了は StopAsyncIteration がそのまま伝わり、異常終了は
        # TransportClosed になる。どちらも呼び出し側で notify_disconnected() に
        # 合流するので、リファクタ前と経路が変わらない。
        try:
            return await self._it.__anext__()
        except websockets.exceptions.ConnectionClosed:
            raise TransportClosed from None

    async def close(self) -> None:
        try:
            await self._ws.close()
        except Exception:
            pass
