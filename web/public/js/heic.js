// HEIC/HEIF の復号。
// Chrome や Firefox は HEIC を復号できない (createImageBitmap が InvalidStateError になる) ため、
// 同梱した libheif の wasm ビルドで自前に復号する。
// wasm 入りで 1.4MB あるので、HEIC を渡されたときにだけ動的 import する。

const VENDOR_URL = "../vendor/libheif/libheif-bundle.mjs";

let libheifPromise = null;

/** 拡張子か MIME で HEIC/HEIF らしさを判定する (環境によって file.type が空になる) */
export function isHeic(file) {
    if (!file) return false;
    const type = (file.type || "").toLowerCase();
    if (type.startsWith("image/heic") || type.startsWith("image/heif")) return true;
    return /\.(heic|heif)$/i.test(file.name || "");
}

function loadLibheif() {
    if (!libheifPromise) {
        libheifPromise = import(new URL(VENDOR_URL, import.meta.url).href)
            .then((mod) => (mod.default || mod)())
            .catch((e) => {
                libheifPromise = null; // 次回やり直せるようにする
                throw new Error(`HEICデコーダを読み込めませんでした: ${e.message}`);
            });
    }
    return libheifPromise;
}

/**
 * HEIC の File/Blob を ImageBitmap にする。
 * 呼び出し側は createImageBitmap の結果と同じように扱える。
 */
export async function decodeHeic(file) {
    const heif = await loadLibheif();
    const buffer = new Uint8Array(await file.arrayBuffer());

    let images;
    try {
        images = new heif.HeifDecoder().decode(buffer);
    } catch (e) {
        throw new Error(`HEICを復号できませんでした: ${e.message}`);
    }
    if (!images || images.length === 0) {
        throw new Error("HEICを復号できませんでした: 画像が入っていません。");
    }

    const image = images[0];
    try {
        const width = image.get_width();
        const height = image.get_height();
        if (!width || !height) {
            throw new Error("HEICを復号できませんでした: サイズを取得できません。");
        }

        // display() は libheif 側のコールバックで ImageData を埋める
        const imageData = new ImageData(width, height);
        await new Promise((resolve, reject) => {
            image.display(imageData, (filled) => {
                if (filled) resolve();
                else reject(new Error("HEICを復号できませんでした。"));
            });
        });
        return await createImageBitmap(imageData);
    } finally {
        // libheif が確保したメモリを解放する (実装によっては無いことがある)
        for (const img of images) {
            if (typeof img.free === "function") img.free();
        }
    }
}
