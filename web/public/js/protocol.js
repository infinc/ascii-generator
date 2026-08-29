// chat_functions.py: receive_messages の移植。
// ここでの分岐は Python 版とワイヤ互換を保つための仕様なので、勝手に変えないこと。

import * as ui from "./ui.js";

function splitOnce(text, sep) {
    const i = text.indexOf(sep);
    if (i === -1) return [text];
    return [text.slice(0, i), text.slice(i + sep.length)];
}

export function sendPayload(ctx, message) {
    if (!ctx.ws || ctx.ws.readyState !== WebSocket.OPEN) {
        ui.logError("接続されていません。");
        return false;
    }
    ctx.ws.send(JSON.stringify({ to: ctx.roomId, id: ctx.fullId, message }));
    return true;
}

export function handleIncoming(ctx, raw) {
    let data;
    try {
        data = JSON.parse(raw);
    } catch (_) {
        return;
    }

    if (data.auth === "OK") {
        ui.logSystem("認証が成功しました");
        return;
    }
    if (data.error || data.ERR) {
        ui.logError(String(data.error || data.ERR));
        return;
    }

    const msg = data.message;
    if (!msg) return;

    const sender = data.id != null ? data.id : "unknown";
    if (sender === ctx.fullId) return;

    if (msg.startsWith("/user ")) {
        const targetUser = msg.slice("/user ".length).trim();
        if (targetUser === ctx.myName || targetUser === ctx.absoluteId || targetUser === ctx.fullId) {
            sendPayload(ctx, `/opfounduser ${sender}`);
        }
        return;
    }

    if (msg.startsWith("/opfounduser ")) {
        const requester = msg.slice("/opfounduser ".length).trim();
        if (ctx.fullId === requester) {
            ui.logSystem(`${sender} は現在オンラインです`);
        }
        return;
    }

    if (msg.startsWith("/opsyncsave\n")) {
        ctx.save = splitOnce(msg, "\n")[1];
        // Python 版は無言で上書きするが、Web では何が起きたか分かるように出す
        ui.logSystem(`${sender} がファイルを共有しました (${ui.formatBytes(new Blob([ctx.save]).size)})。/show で表示できます`);
        return;
    }

    if (msg.startsWith("/opfiledm ")) {
        const parts = splitOnce(msg, "\n");
        const targetUser = parts[0].replaceAll("/opfiledm ", "").trim();
        if (targetUser === ctx.myName || targetUser === ctx.absoluteId || targetUser === ctx.fullId) {
            const content = parts.length > 1 ? parts[1] : "";
            ctx.save = content;
            ui.logLine(`[${sender} (最新のファイル)]:`, "system");
            ui.logArt(content);
        }
        return;
    }

    ui.logMessage(sender, msg);

    // 誰かが /show を投げてきて、自分がファイルを持っていれば送り返す
    if (msg.trim() === "/show" && ctx.save != null) {
        sendPayload(ctx, `/opfiledm ${sender}\n${ctx.save}`);
    }
}
