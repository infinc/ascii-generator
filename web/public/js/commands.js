// chat_functions.py: send_messages のコマンド分岐の移植。
// Web ではファイルパスが無いので、/generate と /file はピッカー/D&D でファイルを受け取る。

import * as ui from "./ui.js";
import { sendPayload } from "./protocol.js";
import { imageToAscii } from "./image.js";
import { ASCII_CHARS_NORMAL, asciiToImage, stripAnsi } from "./ascii.js";

// Achex は1回の送信が 500KB を超えると接続を切る (README 参照)
const MAX_FRAME_BYTES = 500 * 1024;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function frameBytes(ctx, message) {
    return new TextEncoder().encode(JSON.stringify({ to: ctx.roomId, id: ctx.fullId, message })).length;
}

function showCommandList() {
    ui.logHelper("コマンドリスト");
    for (const line of [
        "/cmd ... 全てのコマンドを表示します",
        "/help ... ヘルプを表示します",
        "/file ... ファイルを送信します(テキストベースのファイルのみ)",
        "/show ... 最新のファイルの中身を表示します",
        "/download <[raw/png]> <filename> ... 最新のファイルを .txt(そのまま) もしくは .png(写真に変換)して保存します",
        "/generate <[gray/color]> <width> <factor(default=0.55)> ... すぐにASCII ARTを生成します",
        "/user <user_nameid> ... 相手がオンラインか確認します",
        "/exit ... 退出します",
    ]) {
        ui.logLine(line, "helper");
    }
}

function showHelp() {
    ui.logHelper("退出するには/exitと入力してください");
    ui.logHelper("全てのコマンドを出力するには、/cmdと入力してください");
    ui.logHelper("デフォルトの補正関数は0.55です。");
    ui.logHelper("ファイルは下の欄にドラッグ&ドロップするか、コマンド実行時に選択できます。");
}

/** D&D 済みのファイルがあればそれを使い、無ければピッカーを開く */
async function resolveFile(wantImage) {
    const staged = ui.getStagedFile();
    if (staged) {
        const isImage = staged.type.startsWith("image/");
        if (isImage === wantImage) return staged;
    }
    return await ui.openFilePicker(wantImage ? "image/*" : ".txt,.md,.json,.csv,.log,text/*");
}

/** ファイル名に危険な文字が混ざらないようにする (Python 版は無検証) */
function safeFilename(name, fallback) {
    const cleaned = name.replace(/[\\/]/g, "_").replace(/^\.+/, "").trim();
    return cleaned || fallback;
}

/**
 * chat_functions.py: uploaded()
 * 6フレームを 0.1 秒間隔で送ってから /opsyncsave を送る。
 * 直列の await で送るので、タブが非アクティブでも順序と内容は保たれる (間隔が伸びるだけ)。
 */
async function uploaded(ctx, content, displayName, originalMsg) {
    const syncMsg = `/opsyncsave\n${content}`;
    const size = frameBytes(ctx, syncMsg);
    if (size > MAX_FRAME_BYTES) {
        ui.logError(
            `データが大きすぎます (${ui.formatBytes(size)})。` +
            `Achexは1回に500KBを超える送信を受け付けず、接続が切れるため送信を中止しました。`
        );
        return;
    }

    const frames = [
        originalMsg,
        "-----------------------------",
        `${ctx.fullId} が${displayName} をアップロードしました。`,
        "表示するには/showと入力してください。",
        "ダウンロードするには、/download <[raw/png]>と入力してください。",
        "-----------------------------",
    ];
    const total = frames.length + 1;

    try {
        for (let i = 0; i < frames.length; i++) {
            ui.setBusy(`送信中… (${i + 1}/${total}) このタブを開いたままにしてください`);
            if (!sendPayload(ctx, frames[i])) throw new Error("送信中に接続が切れました。");
            if (i !== 0) ui.logMessage(ctx.fullId, frames[i], true);
            await sleep(100);
        }
        ui.setBusy(`送信中… (${total}/${total}) このタブを開いたままにしてください`);
        if (!sendPayload(ctx, syncMsg)) throw new Error("送信中に接続が切れました。");
        ctx.save = content;
        ui.logHelper(`${displayName} を共有しました (${ui.formatBytes(size)})`);
    } catch (e) {
        // /opsyncsave まで届いていなければ、受信側の save は更新されない
        ui.logError(`${e.message} 共有は完了していません。`);
    } finally {
        ui.setBusy(null);
    }
}

async function cmdGenerate(ctx, msg) {
    const parts = msg.trim().split(/\s+/);
    if (parts.length !== 4) {
        ui.logSystem("コマンド: /generate <[gray/color]> <width> <factor>");
        return;
    }
    const mode = parts[1];
    const size = Number(parts[2]);
    const correctionFactor = Number(parts[3]);

    if (mode !== "gray" && mode !== "color") {
        ui.logError("gray又はcolorを選択してください。");
        return;
    }
    if (!Number.isInteger(size) || size <= 0) {
        ui.logError("横幅は1以上の整数で指定してください。");
        return;
    }
    if (!Number.isFinite(correctionFactor) || correctionFactor <= 0) {
        ui.logError("補正関数は0より大きい数値で指定してください。");
        return;
    }

    const file = await resolveFile(true);
    if (!file) {
        ui.logSystem("画像が選択されませんでした。");
        return;
    }
    if (!file.type.startsWith("image/")) {
        ui.logError("指定された物は画像ではありません。");
        return;
    }

    let result;
    try {
        ui.setBusy("生成中…");
        result = await imageToAscii(file, mode, size, correctionFactor, ASCII_CHARS_NORMAL);
    } catch (e) {
        ui.logError(e.message);
        return;
    } finally {
        ui.setBusy(null);
    }

    ui.logArt(result);
    // 表示名の空白の有無は Python 版の文言そのまま
    const displayName = mode === "gray" ? `${file.name} の白黒ASCII ART` : `${file.name}のカラーASCII ART`;
    await uploaded(ctx, result, displayName, msg);
}

async function cmdFile(ctx, msg) {
    const file = await resolveFile(false);
    if (!file) {
        ui.logSystem("ファイルが選択されませんでした。");
        return;
    }
    let content;
    try {
        // Python の open(..., encoding="utf-8") と同じくデコードできなければ失敗させる
        content = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
    } catch (_) {
        ui.logError(`${file.name} をUTF-8のテキストとして読み込めませんでした。テキストファイルのみ送信できます。`);
        return;
    }
    await uploaded(ctx, content, file.name, msg);
}

function cmdDownload(ctx, msg) {
    if (ctx.save == null) {
        ui.logError("ダウンロードするファイルが存在しません");
        return;
    }
    const cmdParts = msg.trim().split(/\s+/);
    if (cmdParts.length < 2) {
        ui.logSystem("コマンド: /download <[raw/png]> <filename>");
        return;
    }
    const mode = cmdParts[1].toLowerCase();

    if (mode === "raw") {
        let filename = cmdParts.length > 2 ? safeFilename(cmdParts[2], "downloaded_raw.txt") : "downloaded_raw.txt";
        if (!filename.endsWith(".txt")) filename += ".txt";
        const blob = new Blob([stripAnsi(ctx.save)], { type: "text/plain;charset=utf-8" });
        ui.downloadBlob(blob, filename);
        ui.logHelper(`${filename} として保存しました`);
        return;
    }

    if (mode === "png") {
        let filename = cmdParts.length > 2 ? safeFilename(cmdParts[2], "downloaded.png") : "downloaded.png";
        if (filename.endsWith(".txt")) filename = filename.slice(0, -4) + ".png";
        else if (!filename.endsWith(".png")) filename += ".png";

        asciiToImage(ctx.save, ASCII_CHARS_NORMAL)
            .then((out) => {
                if (!out) {
                    ui.logError("画像に変換できる内容がありませんでした。");
                    return;
                }
                ui.downloadBlob(out.blob, filename);
                ui.logHelper(`${filename} として保存しました`);
                ui.logHelper(`この画像の比率は(横:縦)${out.width}: ${out.height}`);
            })
            .catch((e) => ui.logError(e.message));
        return;
    }

    ui.logSystem("コマンド: /download <[raw/png]> <filename>");
}

function cmdUser(ctx, msg) {
    const targetUser = msg.slice("/user ".length).trim();
    if (!targetUser) {
        ui.logSystem("コマンド: /user <user_nameid>");
        return;
    }
    if (targetUser === ctx.myName || targetUser === ctx.absoluteId || targetUser === ctx.fullId) {
        ui.logSystem("指定した人は自分自身です。");
        return;
    }
    ui.logSystem(`${targetUser} を検索しています...`);
    sendPayload(ctx, `/user ${targetUser}`);
}

function cmdShow(ctx) {
    if (ctx.save != null) {
        ui.logArt(ctx.save);
    } else {
        sendPayload(ctx, "/show");
    }
}

/** 入力1行を処理する。Python 版と同じく、未知の入力はそのまま送信する。 */
export async function dispatch(ctx, msg) {
    if (!msg.trim()) return;

    if (msg.startsWith("/exit")) {
        ui.logSystem("退出しました");
        sendPayload(ctx, `[System]${ctx.fullId} が退出しました`);
        ctx.leave();
        return;
    }
    if (msg.startsWith("/help")) return showHelp();
    if (msg.startsWith("/cmd")) return showCommandList();
    if (msg.startsWith("/generate")) return await cmdGenerate(ctx, msg);
    if (msg.startsWith("/download")) return cmdDownload(ctx, msg);
    if (msg.startsWith("/file")) return await cmdFile(ctx, msg);
    if (msg.startsWith("/user")) return cmdUser(ctx, msg);
    if (msg.startsWith("/show")) return cmdShow(ctx);

    const size = frameBytes(ctx, msg);
    if (size > MAX_FRAME_BYTES) {
        ui.logError(`メッセージが大きすぎます (${ui.formatBytes(size)})。500KBを超えると接続が切れます。`);
        return;
    }
    if (sendPayload(ctx, msg)) ui.logMessage(ctx.fullId, msg, true);
}
