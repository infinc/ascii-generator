// Achex への接続層。
// chat_functions.py: main() の接続・認証部分に対応する。

export const ACHEX_DIRECT_URL = "wss://cloud.achex.ca/chat";

/** Python: hashlib.sha256(f"{room}::{pass}").hexdigest() */
export async function sha256Hex(text) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
}

// Python: string.ascii_letters + string.digits
const ID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

/** Python: generate_absolute_id() — secrets.choice 相当 (偏りを避けるため棄却サンプリング) */
export function generateAbsoluteId() {
    const limit = 256 - (256 % ID_CHARS.length); // 248
    const buf = new Uint8Array(1);
    const pick = () => {
        for (;;) {
            crypto.getRandomValues(buf);
            if (buf[0] < limit) return ID_CHARS[buf[0] % ID_CHARS.length];
        }
    };
    const part = () => Array.from({ length: 5 }, pick).join("");
    return `${part()}-${part()}`;
}

/** 同一オリジンの Worker リレー (直結が失敗したときのフォールバック) */
function relayUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/ws`;
}

function openSocket(url, timeoutMs) {
    return new Promise((resolve, reject) => {
        let ws;
        try {
            ws = new WebSocket(url);
        } catch (e) {
            reject(e);
            return;
        }
        const timer = setTimeout(() => {
            cleanup();
            try { ws.close(); } catch (_) {}
            reject(new Error(`接続がタイムアウトしました (${url})`));
        }, timeoutMs);

        const cleanup = () => {
            clearTimeout(timer);
            ws.onopen = null;
            ws.onerror = null;
            ws.onclose = null;
        };
        ws.onopen = () => { cleanup(); resolve(ws); };
        ws.onerror = () => { /* onclose でまとめて扱う */ };
        ws.onclose = (e) => { cleanup(); reject(new Error(`接続できませんでした (code=${e.code})`)); };
    });
}

/**
 * 接続して認証まで済ませる。
 * 直結を試し、ダメなら Worker リレーへフォールバックする。
 * 戻り値: { ws, transport: "direct"|"relay" }
 */
export async function connectAndAuth(roomId, { onLog } = {}) {
    const log = onLog || (() => {});
    const attempts = [
        { url: ACHEX_DIRECT_URL, transport: "direct", label: "直結" },
        { url: relayUrl(), transport: "relay", label: "Workerリレー" },
    ];

    let lastError = null;
    for (const attempt of attempts) {
        try {
            log(`${attempt.label}で接続しています... (${attempt.url})`);
            const ws = await openSocket(attempt.url, 8000);
            await authenticate(ws, roomId, log);
            return { ws, transport: attempt.transport };
        } catch (e) {
            lastError = e;
            log(`${attempt.label}に失敗しました: ${e.message}`);
        }
    }
    throw lastError || new Error("接続できませんでした");
}

/**
 * {"auth": roomId} を送って {"auth":"OK"} を待つ。
 * Python 版と同じく、5秒無応答でも成功扱いにする (chat_functions.py:279-280)。
 */
function authenticate(ws, roomId, log) {
    return new Promise((resolve, reject) => {
        const finish = (fn, arg) => {
            clearTimeout(timer);
            ws.onmessage = null;
            ws.onclose = null;
            fn(arg);
        };
        const timer = setTimeout(() => {
            log("認証の応答がありませんでしたが、続行します");
            finish(resolve);
        }, 5000);

        ws.onmessage = (event) => {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch (_) {
                return;
            }
            if ("auth" in data) {
                if (data.auth === "OK") {
                    finish(resolve);
                } else {
                    finish(reject, new Error("認証に失敗しました。"));
                }
            } else if ("ERR" in data || "error" in data) {
                const errMsg = data.ERR || data.error || "Unknown error";
                finish(reject, new Error(`認証に失敗しました。${errMsg}`));
            }
        };
        ws.onclose = () => finish(reject, new Error("認証中に接続が切れました。"));

        ws.send(JSON.stringify({ auth: roomId }));
    });
}
