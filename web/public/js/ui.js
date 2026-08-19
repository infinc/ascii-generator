// 画面まわり。受信文字列は必ず textContent / DOM API で組み立てる (innerHTML は使わない)。

import { ansiToFragment } from "./ansi.js";

const el = {};
let stagedFile = null;
let scrollPinned = true;

export function initUi() {
    for (const id of [
        "join-screen", "chat-screen", "join-form", "join-name", "join-room", "join-pass",
        "join-error", "join-button", "log", "input-row", "msg-input", "send-button",
        "status-route", "status-room", "status-id", "staged", "staged-name", "staged-clear",
        "file-picker", "busy", "drop-overlay", "reconnect-button",
    ]) {
        el[id] = document.getElementById(id);
    }

    el.log.addEventListener("scroll", () => {
        const gap = el.log.scrollHeight - el.log.scrollTop - el.log.clientHeight;
        scrollPinned = gap < 40;
    });
    el["staged-clear"].addEventListener("click", () => setStagedFile(null));
    return el;
}

function scrollToBottom() {
    if (scrollPinned) el.log.scrollTop = el.log.scrollHeight;
}

function append(node) {
    el.log.appendChild(node);
    scrollToBottom();
}

function lineEl(kind) {
    const div = document.createElement("div");
    div.className = `line ${kind}`;
    return div;
}

/** 1行のプレーンなログ */
export function logLine(text, kind = "plain") {
    const div = lineEl(kind);
    div.textContent = text;
    append(div);
}

export function logSystem(text) {
    logLine(`[System]${text}`, "system");
}

export function logHelper(text) {
    logLine(`[Helper]${text}`, "helper");
}

export function logError(text) {
    logLine(`[Helper]エラー: ${text}`, "error");
}

/**
 * 他者/自分のメッセージ。ANSI が含まれていれば ASCII ART として <pre> で描く。
 */
export function logMessage(sender, msg, self = false) {
    const div = lineEl(self ? "msg self" : "msg");
    const who = document.createElement("span");
    who.className = "sender";
    who.textContent = `${sender}: `;
    div.appendChild(who);

    if (msg.includes("\n") || msg.includes("\x1b[")) {
        div.appendChild(document.createElement("br"));
        div.appendChild(artBlock(msg));
    } else {
        const body = document.createElement("span");
        body.textContent = msg;
        div.appendChild(body);
    }
    append(div);
}

/** ASCII ART を等幅・行間なしで描く <pre> */
export function artBlock(text) {
    const pre = document.createElement("pre");
    pre.className = "art";
    pre.appendChild(ansiToFragment(text));
    return pre;
}

export function logArt(text) {
    append(artBlock(text));
}

export function setRoute(text) {
    el["status-route"].textContent = text;
}

export function setRoomInfo(roomName, absoluteId, userName) {
    el["status-room"].textContent = `部屋: ${roomName}`;
    el["status-id"].textContent = `${userName} / ID: ${absoluteId}`;
}

export function showChatScreen() {
    el["join-screen"].hidden = true;
    el["chat-screen"].hidden = false;
    el["msg-input"].focus();
}

export function showJoinScreen() {
    el["chat-screen"].hidden = true;
    el["join-screen"].hidden = false;
    el["join-button"].disabled = false;
}

export function setJoinError(text) {
    el["join-error"].textContent = text || "";
    el["join-error"].hidden = !text;
}

/** 送信中は入力を止め、進捗を出す */
export function setBusy(text) {
    if (text) {
        el.busy.textContent = text;
        el.busy.hidden = false;
        el["msg-input"].disabled = true;
        el["send-button"].disabled = true;
    } else {
        el.busy.hidden = true;
        el["msg-input"].disabled = false;
        el["send-button"].disabled = false;
        el["msg-input"].focus();
    }
}

export function setDisconnected(on) {
    el["reconnect-button"].hidden = !on;
    el["msg-input"].disabled = on;
    el["send-button"].disabled = on;
}

export function setStagedFile(file) {
    stagedFile = file;
    if (file) {
        el.staged.hidden = false;
        el["staged-name"].textContent = `${file.name} (${formatBytes(file.size)})`;
    } else {
        el.staged.hidden = true;
        el["staged-name"].textContent = "";
    }
}

export function getStagedFile() {
    return stagedFile;
}

export function formatBytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

/** ファイル選択ダイアログを開く。キャンセルされたら null。 */
export function openFilePicker(accept) {
    return new Promise((resolve) => {
        const input = el["file-picker"];
        input.value = "";
        input.accept = accept || "";
        let settled = false;
        const done = (f) => {
            if (settled) return;
            settled = true;
            input.onchange = null;
            resolve(f);
        };
        input.onchange = () => done(input.files[0] || null);
        // キャンセル時に change が飛ばないブラウザ向けの保険
        window.addEventListener("focus", () => setTimeout(() => done(input.files[0] || null), 300), { once: true });
        input.click();
    });
}

/** Blob をダウンロードさせる */
export function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export const dom = el;
