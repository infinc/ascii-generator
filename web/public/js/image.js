// cv2 の代替。Canvas で画像を読み込み、cv2 と同じ手順でグレースケール化・リサイズする。
//
// 注意: Canvas の drawImage による縮小は面積平均に近い高品質縮小で、
// cv2.resize(INTER_LINEAR) の疎なバイリニア標本化とは結果が大きく変わる
// (実測で ASCII の 17.8% の文字が変わった)。そのためリサイズは自前で実装している。
//
// この実装は cv2 の INTER_LINEAR_EXACT とビット単位で一致することを確認済み。
// Python 版が使う既定の INTER_LINEAR は OpenCV の旧固定小数点パスで、
// EXACT と最大1階調ずれる (colorConvert.png では 2700画素中172画素)。
// その結果 ASCII の 0.3〜0.8% の文字が1段階だけ変わるが、見た目には分からない。
// 旧パスは精度が低いために EXACT が追加された経緯があり、ここでは EXACT に合わせている。

import { grayGenerator, rgbGenerator } from "./ascii.js";
import { isHeic, decodeHeic } from "./heic.js";

/** HEIC は環境によって file.type が空になるので、拡張子も見て画像として扱う */
export function isImageFile(file) {
    return Boolean(file) && ((file.type || "").startsWith("image/") || isHeic(file));
}

/** cv2 の COLOR_BGR2GRAY と同じ固定小数点演算 */
function toGray(r, g, b) {
    return (r * 4899 + g * 9617 + b * 1868 + 8192) >> 14;
}

// OpenCV の INTER_LINEAR_EXACT は ufixedpoint16 (小数8bit) で重みを持ち、
// 縦方向の積 (小数16bit) を丸めて uint8 に落とす。
const FIXED_SHIFT = 8;
const FIXED_ONE = 1 << FIXED_SHIFT; // 256
const VERT_DIV = 1 << (FIXED_SHIFT * 2); // 65536
const VERT_HALF = VERT_DIV / 2;

/** OpenCV の cvRound (偶数丸め) */
function cvRound(x) {
    const floor = Math.floor(x);
    if (x - floor === 0.5) return floor % 2 === 0 ? floor : floor + 1;
    return Math.round(x);
}

/** OpenCV の computeResizeLinearTab 相当。重みは倍精度で求めて小数8bitに丸める。 */
function buildMap(srcLen, dstLen) {
    const idx = new Int32Array(dstLen);
    const a0 = new Int32Array(dstLen);
    const a1 = new Int32Array(dstLen);
    const scale = srcLen / dstLen;
    for (let d = 0; d < dstLen; d++) {
        let f = scale * (d + 0.5) - 0.5;
        let s = Math.floor(f);
        f -= s;
        if (s < 0) {
            s = 0;
            f = 0;
        }
        if (s >= srcLen - 1) {
            s = srcLen - 1;
            f = 0;
        }
        idx[d] = s;
        a0[d] = cvRound((1 - f) * FIXED_ONE);
        a1[d] = cvRound(f * FIXED_ONE);
    }
    return { idx, a0, a1 };
}

/**
 * cv2.resize(..., interpolation=INTER_LINEAR_EXACT) 相当。
 * OpenCV と同じ小数8bitの固定小数点で計算するので、丸めまで一致する。
 * src は channels 個ずつインターリーブされた Uint8Array。
 */
export function resizeBilinear(src, srcW, srcH, dstW, dstH, channels) {
    const dst = new Uint8Array(dstW * dstH * channels);
    const mx = buildMap(srcW, dstW);
    const my = buildMap(srcH, dstH);
    const rowStride = srcW * channels;

    for (let dy = 0; dy < dstH; dy++) {
        const sy = my.idx[dy];
        const by0 = my.a0[dy];
        const by1 = my.a1[dy];
        const row0 = sy * rowStride;
        const row1 = Math.min(sy + 1, srcH - 1) * rowStride;

        for (let dx = 0; dx < dstW; dx++) {
            const sx = mx.idx[dx];
            const bx0 = mx.a0[dx];
            const bx1 = mx.a1[dx];
            const c0 = sx * channels;
            const c1 = Math.min(sx + 1, srcW - 1) * channels;
            const out = (dy * dstW + dx) * channels;

            for (let c = 0; c < channels; c++) {
                // hlineResize: 小数8bitのまま保持 (ここでは丸めない)
                const h0 = src[row0 + c0 + c] * bx0 + src[row0 + c1 + c] * bx1;
                const h1 = src[row1 + c0 + c] * bx0 + src[row1 + c1 + c] * bx1;
                // vlineResize: 小数16bitの積を丸めて uint8 へ
                const v = Math.floor((h0 * by0 + h1 * by1 + VERT_HALF) / VERT_DIV);
                dst[out + c] = v < 0 ? 0 : v > 255 ? 255 : v;
            }
        }
    }
    return dst;
}

/**
 * chat_functions.py: instant_generate の変換部分。
 * mode は "gray" | "color"。戻り値は ASCII ART の文字列 (color は ANSI 256色エスケープ入り)。
 */
export async function imageToAscii(file, mode, width, factor, chars) {
    if (mode !== "gray" && mode !== "color") {
        throw new Error("gray又はcolorを選択してください。");
    }
    if (!Number.isInteger(width) || width <= 0) {
        throw new Error("横幅は1以上の整数で指定してください。");
    }
    if (!Number.isFinite(factor) || factor <= 0) {
        throw new Error("補正係数は0より大きい数値で指定してください。");
    }

    let bitmap;
    try {
        bitmap = await createImageBitmap(file);
    } catch (_) {
        // Chrome や Firefox は HEIC を復号できないので、同梱の libheif で読み直す
        if (!isHeic(file)) {
            throw new Error("指定された物は画像ではありません。");
        }
        bitmap = await decodeHeic(file);
    }

    try {
        const srcW = bitmap.width;
        const srcH = bitmap.height;

        // Python 版と同じ制限: 元画像より大きい横幅は指定できない
        if (srcW < width) {
            throw new Error("画像のサイズよりも大きい値を入力することはできません。");
        }

        const height = Math.ceil(srcH * (width / srcW) * factor);
        if (height < 1) {
            throw new Error("補正係数が小さすぎます。高さが0になりました。");
        }

        // 等倍で読み出す (ここでブラウザにリサイズさせない)
        const canvas = document.createElement("canvas");
        canvas.width = srcW;
        canvas.height = srcH;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(bitmap, 0, 0);
        const { data } = ctx.getImageData(0, 0, srcW, srcH);

        const srcCount = srcW * srcH;

        // Python 版はグレースケール化 → リサイズ の順なので、それに合わせる
        const srcGray = new Uint8Array(srcCount);
        for (let i = 0; i < srcCount; i++) {
            const p = i * 4;
            srcGray[i] = toGray(data[p], data[p + 1], data[p + 2]);
        }
        const pixelsGray = resizeBilinear(srcGray, srcW, srcH, width, height, 1);

        if (mode === "gray") {
            return grayGenerator(chars, pixelsGray, width);
        }

        const srcRgb = new Uint8Array(srcCount * 3);
        for (let i = 0; i < srcCount; i++) {
            const p = i * 4;
            const o = i * 3;
            srcRgb[o] = data[p];
            srcRgb[o + 1] = data[p + 1];
            srcRgb[o + 2] = data[p + 2];
        }
        const pixelsRgb = resizeBilinear(srcRgb, srcW, srcH, width, height, 3);
        return rgbGenerator(chars, pixelsRgb, pixelsGray, width);
    } finally {
        bitmap.close();
    }
}
