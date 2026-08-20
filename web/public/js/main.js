// 画面の起動と接続の管理。

import * as ui from "./ui.js";
import { connectAndAuth, sha256Hex, generateAbsoluteId } from "./achex.js";
import { handleIncoming } from "./protocol.js";
import { dispatch } from "./commands.js";

// Achex は {"ping":1} を無視するだけで応答も転送もしない。
// 他クライアントに見えないアイドル対策として使える。
const KEEPALIVE_MS = 30000;
const MAX_RECONNECT = 5;

const ctx = {
    ws: null,
    myName: "",
    absoluteId: "",
    fullId: "",
    roomId: "",
    roomName: "",
    roomPassword: "",
    save: null,
    transport: "",
    leaving: false,
    leave: () => leaveRoom(),
};

let keepaliveTimer = null;
let reconnectAttempt = 0;
let connecting = false;
// 入室のたびに増える。退出/再入室をまたいだ古い接続処理を捨てるために使う。
let sessionId = 0;
const history = [];
let historyIndex = -1;

function startKeepalive() {
    stopKeepalive();
    keepaliveTimer = setInterval(() => {
        if (ctx.ws && ctx.ws.readyState === WebSocket.OPEN) {
            ctx.ws.send(JSON.stringify({ ping: 1 }));
        }
    }, KEEPALIVE_MS);
}

function stopKeepalive() {
    if (keepaliveTimer) clearInterval(keepaliveTimer);
    keepaliveTimer = null;
}

function detachSocket(ws) {
    if (!ws) return;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    try { ws.close(); } catch (_) {}
}

function attachSocket(ws, transport) {
    // 再接続が競合したときに古いソケットが受信し続けないようにする
    if (ctx.ws && ctx.ws !== ws) detachSocket(ctx.ws);
    ctx.ws = ws;
    ctx.transport = transport;
    ui.setRoute(transport === "direct" ? "接続: Achex直結" : "接続: Workerリレー");
    ui.setDisconnected(false);
    startKeepalive();

    ws.onmessage = (event) => handleIncoming(ctx, event.data);
    ws.onerror = () => {};
    ws.onclose = () => {
        stopKeepalive();
        ctx.ws = null;
        if (ctx.leaving) return;
        ui.logSystem("接続が切れました");
        ui.setRoute("接続: 切断");
        ui.setDisconnected(true);
        scheduleReconnect();
    };
}

function scheduleReconnect() {
    if (reconnectAttempt >= MAX_RECONNECT) {
        ui.logSystem("自動再接続を諦めました。再接続ボタンを押してください");
        return;
    }
    const delay = Math.min(30000, 1000 * 2 ** reconnectAttempt);
    reconnectAttempt += 1;
    ui.logSystem(`${Math.round(delay / 1000)}秒後に再接続します (${reconnectAttempt}/${MAX_RECONNECT})`);
    setTimeout(() => {
        if (!ctx.leaving && !ctx.ws) reconnect();
    }, delay);
}

async function reconnect() {
    if (connecting) return; // 手動ボタンと自動再接続が重ならないようにする
    connecting = true;
    const mySession = sessionId;
    try {
        const { ws, transport } = await connectAndAuth(ctx.roomId, { onLog: (m) => ui.logSystem(m) });
        if (ctx.leaving || mySession !== sessionId) {
            // 待っている間に退出/別の部屋へ入室していたら、この接続は捨てる
            detachSocket(ws);
            return;
        }
        attachSocket(ws, transport);
        reconnectAttempt = 0;
        ui.logSystem("再接続しました");
    } catch (e) {
        ui.logSystem(`再接続に失敗しました: ${e.message}`);
        scheduleReconnect();
    } finally {
        connecting = false;
    }
}

async function joinRoom(myName, roomName, roomPassword) {
    ctx.myName = myName;
    ctx.roomName = roomName;
    ctx.roomPassword = roomPassword || "password";
    ctx.roomId = await sha256Hex(`${roomName}::${ctx.roomPassword}`);
    ctx.absoluteId = generateAbsoluteId();
    ctx.fullId = `[${ctx.absoluteId}]${myName}`;
    ctx.save = null;
    ctx.leaving = false;
    reconnectAttempt = 0;
    sessionId += 1;

    ui.dom.log.replaceChildren();
    ui.showChatScreen();
    ui.setRoomInfo(roomName, ctx.absoluteId, myName);

    const { ws, transport } = await connectAndAuth(ctx.roomId, { onLog: (m) => ui.logSystem(m) });
    attachSocket(ws, transport);

    // Python 版と同じく、入室通知だけ id は "[System]"
    ws.send(JSON.stringify({ to: ctx.roomId, id: "[System]", message: `${ctx.fullId} が参加しました` }));

    ui.logLine("-----------------------------", "system");
    ui.logLine(`あなたのユーザーネーム: ${myName}`, "system");
    ui.logLine(`あなたのID: ${ctx.absoluteId}`, "system");
    ui.logLine(`部屋のID: ${roomName}`, "system");
    ui.logLine(`部屋のパスワード: ${ctx.roomPassword}`, "system");
    ui.logLine("-----------------------------", "system");
    ui.logSystem("接続しました。退出するには/exitと入力してください");
    ui.logSystem("全てのコマンドを出力するには、/cmdと入力してください");
}

function leaveRoom() {
    ctx.leaving = true;
    sessionId += 1;
    stopKeepalive();
    detachSocket(ctx.ws);
    ctx.ws = null;
    ui.setStagedFile(null);
    ui.showJoinScreen();
}

function setupDragAndDrop() {
    const overlay = ui.dom["drop-overlay"];
    let depth = 0;

    window.addEventListener("dragenter", (e) => {
        if (![...e.dataTransfer.types].includes("Files")) return;
        e.preventDefault();
        depth += 1;
        if (!ui.dom["chat-screen"].hidden) overlay.hidden = false;
    });
    window.addEventListener("dragover", (e) => {
        if ([...e.dataTransfer.types].includes("Files")) e.preventDefault();
    });
    window.addEventListener("dragleave", () => {
        depth = Math.max(0, depth - 1);
        if (depth === 0) overlay.hidden = true;
    });
    window.addEventListener("drop", (e) => {
        if (![...e.dataTransfer.types].includes("Files")) return;
        e.preventDefault();
        depth = 0;
        overlay.hidden = true;
        if (ui.dom["chat-screen"].hidden) return;
        const file = e.dataTransfer.files[0];
        if (!file) return;
        ui.setStagedFile(file);
        if (file.type.startsWith("image/")) {
            ui.logHelper(`${file.name} を選択しました。/generate <[gray/color]> <width> <factor> で送信できます`);
        } else {
            ui.logHelper(`${file.name} を選択しました。/file で送信できます`);
        }
    });
}

function setupInput() {
    const input = ui.dom["msg-input"];

    const submit = async () => {
        const value = input.value;
        if (!value.trim()) return;
        input.value = "";
        history.push(value);
        historyIndex = history.length;
        try {
            await dispatch(ctx, value);
        } catch (e) {
            ui.logError(e.message);
        }
    };

    ui.dom["send-button"].addEventListener("click", submit);

    // IME (日本語入力など) の変換中かどうか。変換確定の Enter を送信と誤認しないために使う
    let composing = false;
    input.addEventListener("compositionstart", () => {
        composing = true;
    });
    input.addEventListener("compositionend", () => {
        composing = false;
    });

    input.addEventListener("keydown", (e) => {
        // 変換確定の Enter はブラウザによって isComposing が false になることがあるため
        // compositionend 直後の keyCode 229 も含めて弾く
        if (composing || e.isComposing || e.keyCode === 229) return;
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
        } else if (e.key === "ArrowUp" && historyIndex > 0) {
            e.preventDefault();
            historyIndex -= 1;
            input.value = history[historyIndex];
        } else if (e.key === "ArrowDown") {
            e.preventDefault();
            if (historyIndex < history.length - 1) {
                historyIndex += 1;
                input.value = history[historyIndex];
            } else {
                historyIndex = history.length;
                input.value = "";
            }
        }
    });

    ui.dom["reconnect-button"].addEventListener("click", () => {
        reconnectAttempt = 0;
        ui.dom["reconnect-button"].hidden = true;
        reconnect();
    });
}

function setupJoinForm() {
    ui.dom["join-form"].addEventListener("submit", async (e) => {
        e.preventDefault();
        const myName = ui.dom["join-name"].value.trim();
        const roomName = ui.dom["join-room"].value.trim();
        const roomPassword = ui.dom["join-pass"].value;

        if (!myName) return ui.setJoinError("ユーザーネームを入力してください");
        if (!roomName) return ui.setJoinError("部屋のIDを入力してください");

        ui.setJoinError("");
        ui.dom["join-button"].disabled = true;
        try {
            await joinRoom(myName, roomName, roomPassword);
        } catch (err) {
            ui.showJoinScreen();
            ui.setJoinError(`接続できませんでした: ${err.message}`);
        }
    });
}

function main() {
    if (!window.isSecureContext) {
        document.body.textContent =
            "このページはHTTPS (または localhost) で開いてください。部屋IDの生成にWeb Cryptoが必要です。";
        return;
    }
    ui.initUi();
    setupJoinForm();
    setupInput();
    setupDragAndDrop();
}

main();
