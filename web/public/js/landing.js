// ホーム画面 (参加前) の中身。コマンド表の生成と、フッターで動く ASCII アニメーション。
// 表示テキストは textContent 経由でのみ組み立てる (innerHTML は使わない)。

import { COMMANDS } from "./commands.js";
import { ASCII_CHARS_NORMAL } from "./ascii.js";

const ROWS = 7;
const FRAME_MS = 1000 / 12; // 装飾なので 12fps で十分
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

let pre = null;
let cols = 0;
let running = false;
let rafId = 0;
let lastFrame = 0;
let phase = 0;

/** /cmd と同じ一覧からコマンド表を組み立てる */
function buildCommandTable() {
    const tbody = document.getElementById("command-rows");
    if (!tbody) return;

    const rows = COMMANDS.map(({ cmd, desc }) => {
        const tr = document.createElement("tr");
        const th = document.createElement("th");
        th.scope = "row";
        const code = document.createElement("code");
        code.textContent = cmd;
        th.appendChild(code);
        const td = document.createElement("td");
        td.textContent = desc;
        tr.append(th, td);
        return tr;
    });
    tbody.replaceChildren(...rows);
}

/** pre の実幅から桁数を求める。等幅フォントなので1文字ぶん測れば足りる。 */
function measureCols() {
    if (!pre) return 0;
    const style = getComputedStyle(pre);
    const canvas = measureCols.canvas || (measureCols.canvas = document.createElement("canvas"));
    const ctx = canvas.getContext("2d");
    ctx.font = `${style.fontSize} ${style.fontFamily}`;
    const charWidth = ctx.measureText("#").width || 8;
    const inner = pre.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    return Math.max(20, Math.min(240, Math.floor(inner / charWidth)));
}

/** 正弦波を3枚重ねた波を明度とみなし、ASCII のランプに落とす */
function renderFrame(t) {
    if (!cols) return;
    const ramp = ASCII_CHARS_NORMAL;
    const last = ramp.length - 1;
    const lines = [];

    for (let y = 0; y < ROWS; y++) {
        let line = "";
        for (let x = 0; x < cols; x++) {
            const v =
                Math.sin(x * 0.14 + t) +
                Math.sin(y * 0.55 - t * 0.8) +
                Math.sin((x + y * 2) * 0.08 + t * 1.3);
            const level = (v + 3) / 6; // -3..3 -> 0..1
            line += ramp[Math.round(level * last)];
        }
        lines.push(line);
    }
    pre.textContent = lines.join("\n");
}

function tick(now) {
    if (!running) return;
    rafId = requestAnimationFrame(tick);
    if (now - lastFrame < FRAME_MS) return;
    lastFrame = now;
    phase += 0.12;
    renderFrame(phase);
}

export function startLanding() {
    if (!pre || running) return;
    if (document.hidden) return;
    if (reduceMotion.matches) {
        renderFrame(phase); // 動かさず1枚だけ描く
        return;
    }
    running = true;
    lastFrame = 0;
    rafId = requestAnimationFrame(tick);
}

export function stopLanding() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
}

export function initLanding() {
    buildCommandTable();

    pre = document.getElementById("ascii-anim");
    if (!pre) return;
    cols = measureCols();
    renderFrame(phase);

    let resizeTimer = 0;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            cols = measureCols();
            renderFrame(phase);
        }, 150);
    });

    // 非表示のタブで回し続けない
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) stopLanding();
        else if (!document.getElementById("join-screen").hidden) startLanding();
    });

    reduceMotion.addEventListener("change", () => {
        if (reduceMotion.matches) stopLanding();
        else if (!document.getElementById("join-screen").hidden) startLanding();
    });

    startLanding();
}
