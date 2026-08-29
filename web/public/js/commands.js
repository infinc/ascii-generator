// chat_functions.py: send_messages のコマンド分岐の移植。
// Web ではファイルパスが無いので、/generate と /file はピッカー/D&D でファイルを受け取る。

import * as ui from "./ui.js";
import { sendPayload } from "./protocol.js";
import { imageToAscii, isImageFile } from "./image.js";
import { isHeic } from "./heic.js";
import { ASCII_CHARS_NORMAL, asciiToImage, stripAnsi } from "./ascii.js";

// Achex は1回の送信が 500KB を超えると接続を切る (README 参照)
const MAX_FRAME_BYTES = 500 * 1024;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function frameBytes(ctx, message) {
    return new TextEncoder().encode(JSON.stringify({ to: ctx.roomId, id: ctx.fullId, message })).length;
}

// /cmd の出力と、ホーム画面のコマンド表 (landing.js) の両方がここを参照する。
export const COMMANDS = [
    { cmd: "/cmd", desc: "全てのコマンドを表示します" },
    { cmd: "/help", desc: "ヘルプを表示します" },
    { cmd: "/file", desc: "ファイルを送信します(テキストベースのファイルのみ)" },
    { cmd: "/show", desc: "最新のファイルの中身を表示します" },
    { cmd: "/download <[raw/png]>", desc: "最新のファイルを .txt(そのまま) もしくは .png(写真に変換)して保存します" },
    { cmd: "/generate <[gray/color]> <width> [factor]", desc: "すぐにASCII ARTを生成します(factor省略時=0.55)" },
    { cmd: "/user <user_nameid>", desc: "相手がオンラインか確認します" },
    { cmd: "/clear", desc: "チャットの表示を消して画面を綺麗にします" },
    { cmd: "/exit", desc: "退出します" },
];

function showCommandList() {
    ui.logHelper("コマンドリスト");
    for (const { cmd, desc } of COMMANDS) {
        ui.logLine(`${cmd} ... ${desc}`, "helper");
    }
}

function showHelp() {
    ui.logHelper("退出するには/exitと入力してください");
    ui.logHelper("全てのコマンドを出力するには、/cmdと入力してください");
    ui.logHelper("デフォルトの補正係数は0.55です。");
    ui.logHelper("ファイルは下の欄にドラッグ&ドロップするか、コマンド実行時に選択できます。");
}

/** D&D 済みのファイルがあればそれを使い、無ければピッカーを開く */
async function resolveFile(wantImage) {
    const staged = ui.getStagedFile();
    if (staged) {
        if (isImageFile(staged) === wantImage) return staged;
    }
    // HEIC は MIME が空になる環境があるので、拡張子でも選べるようにする
    return await ui.openFilePicker(wantImage ? "image/*,.heic,.heif" : ".txt,.md,.json,.csv,.log,text/*");
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
    // factor は省略可 (省略時は 0.55) — Python 版と揃える
    if (parts.length !== 3 && parts.length !== 4) {
        ui.logSystem("コマンド: /generate <[gray/color]> <width> [factor]");
        return;
    }
    const mode = parts[1];
    const size = Number(parts[2]);
    const correctionFactor = parts.length === 4 ? Number(parts[3]) : 0.55;

    if (mode !== "gray" && mode !== "color") {
        ui.logError("gray又はcolorを選択してください。");
        return;
    }
    if (!Number.isInteger(size) || size <= 0) {
        ui.logError("横幅は1以上の整数で指定してください。");
        return;
    }
    if (!Number.isFinite(correctionFactor) || correctionFactor <= 0) {
        ui.logError("補正係数は0より大きい数値で指定してください。");
        return;
    }

    const file = await resolveFile(true);
    if (!file) {
        ui.logSystem("画像が選択されませんでした。");
        return;
    }
    if (!isImageFile(file)) {
        ui.logError("指定された物は画像ではありません。");
        return;
    }

    let result;
    try {
        // HEIC は初回だけ 1.4MB のデコーダ (libheif) を読み込むので、その旨を出す
        ui.setBusy(isHeic(file) ? "HEICを復号しています… (初回はデコーダの読み込みに少し時間がかかります)" : "生成中…");
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

    ui.logSystem("コマンド: /download <[raw/png]>");
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

    // 引数を取らないコマンドは完全一致で判定する (/clear123 のような入力を誤認しないため)。
    // 一致しなければ下の通常メッセージ送信に落ちる。
    const bare = msg.trim();

    if (bare === "/exit") {
        ui.logSystem("退出しました");
        sendPayload(ctx, `[System]${ctx.fullId} が退出しました`);
        ctx.leave();
        return;
    }
    if (bare === "/help") return showHelp();
    if (bare === "/cmd") return showCommandList();
    if (bare === "/clear") {
        ui.clearLog();
        ui.logSystem("画面をクリアしました");
        return;
    }
    if (bare === "/file") return await cmdFile(ctx, msg);
    if (bare === "/show") return cmdShow(ctx);

    // 引数を取るコマンドは前方一致のまま (引数なしで打つと使い方を表示する)
    if (msg.startsWith("/generate")) return await cmdGenerate(ctx, msg);
    if (msg.startsWith("/download")) return cmdDownload(ctx, msg);
    if (msg.startsWith("/user")) return cmdUser(ctx, msg);

    const size = frameBytes(ctx, msg);
    if (size > MAX_FRAME_BYTES) {
        ui.logError(`メッセージが大きすぎます (${ui.formatBytes(size)})。500KBを超えると接続が切れます。`);
        return;
    }
    if (sendPayload(ctx, msg)) ui.logMessage(ctx.fullId, msg, true);
}
