"""BLE チャットの下位層。

BLE は1回に送れるバイト数が非常に小さい (ATT MTU の既定は23バイト、
実データは20バイト。macOS でも185バイト程度) ため、チャットのメッセージ1件でも
そのままでは送れない。ここではメッセージを

    1. JSON にする
    2. HMAC を前置してシールする       (部屋のパスワードを知らない相手を弾く)
    3. 固定8バイトのヘッダを付けて分割する
    4. 受信側で番号順に組み直し、CRC で壊れていないか確かめる

という流れで運ぶための道具を提供する。BLE そのものには依存しないので、
bleak / bless が無い環境でも import でき、単体で試せる。
"""

import hashlib
import hmac
import struct
import time
import uuid
import zlib

# --- GATT の識別子 -----------------------------------------------------------

# Central -> Peripheral。ゲストからホストへの送信に使う。
RX_CHAR_UUID = "6e5f0001-8a2b-4c3d-9e1f-a5b6c7d8e9f0"
# Peripheral -> Central。ホストから全ゲストへの通知に使う。
TX_CHAR_UUID = "6e5f0002-8a2b-4c3d-9e1f-a5b6c7d8e9f0"

HOST_SRC = 0x0000  # ホストの送信者タグは固定


def room_secret(room_name, room_password):
    """部屋ID とパスワードから共有秘密を作る。"""
    return hashlib.sha256(f"{room_name}::{room_password}".encode()).digest()


def room_id_hex(room_name, room_password):
    """Achex 版の real_room_id と同じ値。メッセージの "to" に入れる。"""
    return room_secret(room_name, room_password).hex()


def service_uuid(room_name, room_password):
    """部屋ごとの Service UUID。

    部屋IDとパスワードの両方が一致したときだけ同じ UUID になるので、
    違う部屋のホストはスキャンの段階で候補に上がらない。
    """
    return str(uuid.UUID(bytes=room_secret(room_name, room_password)[:16]))


def advert_name(room_name, room_password):
    """アドバタイズに載せる名前 (6文字)。

    アドバタイズは31バイトしかなく、Flags(3) + 128bit Service UUID(18) で
    既に21バイト使う。名前を8文字にすると合計31バイトちょうどになり、
    OS によっては Service UUID か名前の末尾が黙って削られて検出できなくなる。
    6文字にして2バイトの余白を残している。
    """
    return "A" + room_id_hex(room_name, room_password)[:5]


# --- HMAC によるシール -------------------------------------------------------

MAC_LEN = 8


def seal(json_bytes, secret):
    """本文に HMAC を前置する。"""
    mac = hmac.new(secret, json_bytes, hashlib.sha256).digest()[:MAC_LEN]
    return mac + json_bytes


def unseal(body, secret):
    """HMAC を検証して本文を返す。不正なら None。

    ホストは受け取った本文をそのまま中継するので、HMAC はヘッダを含めず
    本文だけを対象にしている (中継時にヘッダの msg_id が振り直されるため)。
    """
    if len(body) < MAC_LEN:
        return None
    mac, json_bytes = body[:MAC_LEN], body[MAC_LEN:]
    expected = hmac.new(secret, json_bytes, hashlib.sha256).digest()[:MAC_LEN]
    if not hmac.compare_digest(mac, expected):
        return None
    return json_bytes


# --- フレーム ---------------------------------------------------------------

#  verflags uint8   上位4bit = バージョン、bit0 = zlib 圧縮
#  src      uint16  送信者タグ
#  msg_id   uint8   送信者ごとの連番 (256 で一周)
#  idx      uint8   チャンク番号
#  total    uint8   総チャンク数
#  crc      uint16  本文全体の CRC32 の下位16bit
HDR = struct.Struct("<BHBBBH")
HDR_LEN = HDR.size  # 8

VERSION = 1
FLAG_COMPRESSED = 0x01

MAX_CHUNKS = 255
MIN_CHUNK_PAYLOAD = 12  # MTU が既定の20バイトのときの実データ量


def pack(body, src, msg_id, chunk_payload):
    """本文をチャンクの列にする。

    chunk_payload はヘッダを除いた1チャンクあたりのバイト数。
    """
    if chunk_payload < 1:
        raise ValueError("chunk_payload が小さすぎます")

    crc = zlib.crc32(body) & 0xFFFF
    total = max(1, -(-len(body) // chunk_payload))
    if total > MAX_CHUNKS:
        raise ValueError("メッセージが長すぎます")

    verflags = VERSION << 4
    out = []
    for idx in range(total):
        piece = body[idx * chunk_payload:(idx + 1) * chunk_payload]
        out.append(HDR.pack(verflags, src, msg_id, idx, total, crc) + piece)
    return out


def peek(chunk):
    """チャンクから (送信者タグ, メッセージ番号) を取り出す。壊れていれば None。"""
    if len(chunk) < HDR_LEN:
        return None
    verflags, src, msg_id, _idx, _total, _crc = HDR.unpack_from(chunk)
    if verflags >> 4 != VERSION:
        return None
    return src, msg_id


def peek_src(chunk):
    """チャンクから送信者タグだけ取り出す。壊れていれば None。"""
    got = peek(chunk)
    return None if got is None else got[0]


INCOMPLETE_TIMEOUT = 15.0
MAX_PENDING = 64


class Reassembler:
    """チャンクを組み直す。

    送信元の識別は BLE の接続ではなくヘッダの src で行う。bless 0.3.0 の
    書き込みコールバックには「どの Central が書いたか」が渡ってこないので、
    ホスト側では src で分けるしかない。
    """

    def __init__(self, on_drop=None):
        # (src, msg_id) -> {"total", "crc", "parts", "t"}
        self._buf = {}
        # 未完成のまま捨てるときに呼ぶ。届かなかったことをユーザーに見せるため。
        self._on_drop = on_drop

    def feed(self, chunk):
        """チャンクを1つ食べる。メッセージが揃えば本文を返す。"""
        self.sweep()

        if len(chunk) < HDR_LEN:
            return None
        verflags, src, msg_id, idx, total, crc = HDR.unpack_from(chunk)
        if verflags >> 4 != VERSION:
            return None
        if total == 0 or idx >= total:
            return None

        key = (src, msg_id)
        entry = self._buf.get(key)
        # msg_id は256で一周するので、同じ鍵で別のメッセージが来ることがある。
        # 総数か CRC が食い違ったら古い方は諦めて作り直す。
        if entry is not None and (entry["total"] != total or entry["crc"] != crc):
            self._drop(key, entry)
            entry = None
        if entry is None:
            entry = {"total": total, "crc": crc, "parts": {}, "t": time.monotonic()}
            self._buf[key] = entry

        entry["parts"][idx] = chunk[HDR_LEN:]
        entry["t"] = time.monotonic()

        if len(entry["parts"]) < total:
            self._evict()
            return None

        del self._buf[key]
        body = b"".join(entry["parts"][i] for i in range(total))
        if (zlib.crc32(body) & 0xFFFF) != crc:
            if self._on_drop:
                self._on_drop(src, "内容が壊れていました")
            return None
        if verflags & FLAG_COMPRESSED:
            # 現状の送信側は圧縮しないが、将来ファイル転送で有効にしたときに
            # 今のクライアントが読めるよう、展開だけ先に用意しておく。
            try:
                body = zlib.decompress(body)
            except zlib.error:
                if self._on_drop:
                    self._on_drop(src, "展開に失敗しました")
                return None
        return body

    def sweep(self):
        """届き切らなかったメッセージを時間で片付ける。"""
        now = time.monotonic()
        for key, entry in list(self._buf.items()):
            if now - entry["t"] > INCOMPLETE_TIMEOUT:
                self._drop(key, entry)

    def _drop(self, key, entry):
        self._buf.pop(key, None)
        if self._on_drop:
            self._on_drop(key[0], f"一部が届きませんでした ({len(entry['parts'])}/{entry['total']})")

    def _evict(self):
        while len(self._buf) > MAX_PENDING:
            key = min(self._buf, key=lambda k: self._buf[k]["t"])
            self._drop(key, self._buf[key])
