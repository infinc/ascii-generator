// functions.py の変換ロジックの移植。
// Python 版と同じ出力になることが最優先なので、演算はそのまま写している。

export const ASCII_CHARS_BLOCK = " ░▒▓█";
export const ASCII_CHARS_NORMAL = " .:-=+*#%@";
export const ASCII_CHARS_IMPACT = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

const ANSI_RE = /\x1b\[[0-9;]*m/g;

/** ANSI エスケープを取り除く (chat_functions.py の /download raw と同じ) */
export function stripAnsi(text) {
    return text.replace(ANSI_RE, "");
}

/** functions.py: gray_generator */
export function grayGenerator(chars, pixels, width) {
    const numChars = chars.length;
    let out = "";
    for (let i = 0; i < pixels.length; i++) {
        // Python: chars[pixel * num_chars // 256]
        out += chars[Math.floor((pixels[i] * numChars) / 256)];
    }
    const lines = [];
    for (let i = 0; i < out.length; i += width) {
        lines.push(out.slice(i, i + width));
    }
    return lines.join("\n");
}

/** functions.py: rgb_to_256
 *  Python の round() は偶数丸めだが、r が 0..255 の整数のとき r/255*5 は
 *  厳密に .5 にならないため Math.round と一致する。 */
export function rgbTo256(r, g, b) {
    return 16 + 36 * Math.round((r / 255) * 5) + 6 * Math.round((g / 255) * 5) + Math.round((b / 255) * 5);
}

/** functions.py: rgb_generator
 *  pixelsRgb は [r,g,b,r,g,b,...] のフラット配列。 */
export function rgbGenerator(chars, pixelsRgb, pixelsGray, width) {
    const numChars = chars.length;
    const gen = [];
    for (let i = 0; i < pixelsGray.length; i++) {
        const char = chars[Math.floor((pixelsGray[i] * numChars) / 256)];
        const o = i * 3;
        const colorCode = rgbTo256(pixelsRgb[o], pixelsRgb[o + 1], pixelsRgb[o + 2]);
        gen.push(`\x1b[38;5;${colorCode}m${char}`);
        if ((i + 1) % width === 0) {
            gen.push("\x1b[0m\n");
        }
    }
    return gen.join("");
}

/**
 * functions.py: ascii_to_image の移植。
 * ASCII ART のテキストを PNG の Blob に戻す。
 * 戻り値: { blob, width, height } / 中身が空なら null
 */
export async function asciiToImage(text, chars) {
    // Python の readlines() は末尾の改行で空行を生まないので、末尾の "" を1つだけ落とす
    const lines = text.split("\n");
    if (lines.length > 0 && lines[lines.length - 1] === "") {
        lines.pop();
    }
    if (lines.length === 0) return null;

    const newHeight = lines.length;
    let newWidth = 0;
    for (const line of lines) {
        newWidth = Math.max(newWidth, stripAnsi(line).length);
    }
    if (newWidth === 0) return null;

    const numChars = chars.length;
    const charToGray = new Map();
    for (let i = 0; i < numChars; i++) {
        charToGray.set(chars[i], Math.trunc((i / (numChars - 1)) * 255));
    }

    const img = new ImageData(newWidth, newHeight);
    const data = img.data;
    for (let i = 3; i < data.length; i += 4) data[i] = 255; // alpha

    for (let y = 0; y < lines.length; y++) {
        // Python: re.split(r'(\x1b\[[0-9;]*m)', line) — キャプチャ付き split で区切りも残る
        const parts = lines[y].split(/(\x1b\[[0-9;]*m)/);
        let currentColor = null;
        let x = 0;

        for (const part of parts) {
            if (!part) continue;

            if (part.startsWith("\x1b[")) {
                const m = /^\x1b\[([0-9;]+)m/.exec(part);
                if (!m) continue;
                const codes = m[1].split(";");
                if (codes.length >= 3 && codes[0] === "38") {
                    if (codes[1] === "5" && codes.length === 3) {
                        let code = parseInt(codes[2], 10);
                        if (code >= 16) {
                            code -= 16;
                            // Python 版と同じ復元式 (xterm の実パレットとは僅かに異なるが原典に合わせる)
                            const r = Math.trunc((Math.floor(code / 36) / 5) * 255);
                            const g = Math.trunc((Math.floor((code % 36) / 6) / 5) * 255);
                            const b = Math.trunc(((code % 6) / 5) * 255);
                            currentColor = [r, g, b];
                        }
                    } else if (codes[1] === "2" && codes.length === 5) {
                        currentColor = [parseInt(codes[2], 10), parseInt(codes[3], 10), parseInt(codes[4], 10)];
                    }
                } else if (codes[0] === "0") {
                    currentColor = null;
                }
            } else {
                for (const char of part) {
                    if (x >= newWidth) break;
                    const grayVal = charToGray.has(char) ? charToGray.get(char) : 0;
                    const p = (y * newWidth + x) * 4;
                    if (currentColor === null) {
                        data[p] = grayVal; data[p + 1] = grayVal; data[p + 2] = grayVal;
                    } else if (char === " " || grayVal === 0) {
                        data[p] = 0; data[p + 1] = 0; data[p + 2] = 0;
                    } else {
                        data[p] = currentColor[0]; data[p + 1] = currentColor[1]; data[p + 2] = currentColor[2];
                    }
                    x += 1;
                }
            }
        }
    }

    // 生成時に 0.55 倍に潰した縦を戻す (cv2.INTER_LINEAR 相当)
    const restoredHeight = Math.max(1, Math.trunc(newHeight / 0.55));

    const src = document.createElement("canvas");
    src.width = newWidth;
    src.height = newHeight;
    src.getContext("2d").putImageData(img, 0, 0);

    const dst = document.createElement("canvas");
    dst.width = newWidth;
    dst.height = restoredHeight;
    const dctx = dst.getContext("2d");
    dctx.imageSmoothingEnabled = true;
    dctx.imageSmoothingQuality = "high";
    dctx.drawImage(src, 0, 0, newWidth, restoredHeight);

    const blob = await new Promise((resolve) => dst.toBlob(resolve, "image/png"));
    return { blob, width: newWidth, height: restoredHeight };
}
