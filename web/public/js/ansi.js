// ANSI 256色エスケープを DOM に変換する。
// 受信文字列は第三者由来なので、必ず textContent 経由で組み立てる (innerHTML は使わない)。

const BASE_16 = [
    "#000000", "#800000", "#008000", "#808000", "#000080", "#800080", "#008080", "#c0c0c0",
    "#808080", "#ff0000", "#00ff00", "#ffff00", "#0000ff", "#ff00ff", "#00ffff", "#ffffff",
];
const CUBE_LEVELS = [0, 95, 135, 175, 215, 255];

const hex2 = (n) => n.toString(16).padStart(2, "0");

/** xterm の 256色パレット。画面表示はターミナルの見た目に合わせる。 */
export function xterm256ToHex(code) {
    if (code < 0 || code > 255) return null;
    if (code < 16) return BASE_16[code];
    if (code < 232) {
        const c = code - 16;
        const r = CUBE_LEVELS[Math.floor(c / 36)];
        const g = CUBE_LEVELS[Math.floor((c % 36) / 6)];
        const b = CUBE_LEVELS[c % 6];
        return `#${hex2(r)}${hex2(g)}${hex2(b)}`;
    }
    const v = 8 + (code - 232) * 10;
    return `#${hex2(v)}${hex2(v)}${hex2(v)}`;
}

/**
 * ANSI 付きテキストを DocumentFragment に変換する。
 * 対応: \x1b[38;5;Nm (256色), \x1b[38;2;R;G;Bm (真の色), \x1b[0m / \x1b[m (リセット)。
 * それ以外のエスケープは色を変えずに読み飛ばす。
 */
export function ansiToFragment(text) {
    const frag = document.createDocumentFragment();
    const parts = text.split(/(\x1b\[[0-9;]*m)/);
    let color = null;

    for (const part of parts) {
        if (!part) continue;

        if (part.startsWith("\x1b[")) {
            const m = /^\x1b\[([0-9;]*)m$/.exec(part);
            if (!m) continue;
            const codes = m[1] === "" ? ["0"] : m[1].split(";");
            if (codes[0] === "38" && codes[1] === "5" && codes.length === 3) {
                color = xterm256ToHex(parseInt(codes[2], 10));
            } else if (codes[0] === "38" && codes[1] === "2" && codes.length === 5) {
                const [r, g, b] = codes.slice(2).map((c) => parseInt(c, 10) & 255);
                color = `#${hex2(r)}${hex2(g)}${hex2(b)}`;
            } else if (codes[0] === "0" || codes[0] === "39") {
                color = null;
            }
            continue;
        }

        if (color === null) {
            frag.appendChild(document.createTextNode(part));
        } else {
            const span = document.createElement("span");
            span.style.color = color;
            span.textContent = part;
            frag.appendChild(span);
        }
    }
    return frag;
}
