// Cloudflare Worker。
// 通常はブラウザから Achex に直接つながるので、この Worker はほぼ静的配信専用。
// /ws は直結できなかった場合のフォールバック用リレー、/probe と /echo は疎通診断用。

const ACHEX_ORIGIN = "https://cloud.achex.ca";
const ACHEX_URL = `${ACHEX_ORIGIN}/chat`;

// Achex は Origin ヘッダの無い WebSocket ハンドシェイクを拒否するため、
// Python 版と同じく Origin を上流に送る。
const UPSTREAM_HEADERS = {
    Upgrade: "websocket",
    Origin: ACHEX_ORIGIN,
};

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);

        if (url.pathname === "/ws") return handleRelay(request);
        if (url.pathname === "/probe") return handleProbe(url);
        if (url.pathname === "/echo") return handleEcho(request);

        // 静的アセットは assets バインディングに任せる
        if (env.ASSETS) return env.ASSETS.fetch(request);
        return new Response("Not found", { status: 404 });
    },
};

/** ブラウザ ⇄ Worker ⇄ Achex の素通しリレー。中身は解釈も書き換えもしない。 */
async function handleRelay(request) {
    if (request.headers.get("Upgrade") !== "websocket") {
        return new Response("expected a websocket upgrade", { status: 426 });
    }

    let upstream;
    try {
        upstream = await fetch(ACHEX_URL, { headers: UPSTREAM_HEADERS });
    } catch (e) {
        return new Response(`upstream connect failed: ${e}`, { status: 502 });
    }

    const remote = upstream.webSocket;
    if (!remote) {
        return new Response(`upstream did not upgrade (status ${upstream.status})`, { status: 502 });
    }
    remote.accept();

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    server.accept();

    const forward = (from, to) => {
        from.addEventListener("message", (e) => {
            try { to.send(e.data); } catch (_) {}
        });
        from.addEventListener("close", (e) => {
            // 1005/1006 はそのまま渡せないので通常終了に丸める
            const code = e.code >= 1000 && e.code !== 1005 && e.code !== 1006 ? e.code : 1000;
            try { to.close(code, e.reason); } catch (_) {}
        });
        from.addEventListener("error", () => {
            try { to.close(1011, "relay error"); } catch (_) {}
        });
    };
    forward(server, remote);
    forward(remote, server);

    return new Response(null, { status: 101, webSocket: client });
}

/** Achex に到達できるかを CF エッジから確認する */
async function handleProbe(url) {
    const withHeaders = url.searchParams.get("headers") !== "0";
    const headers = withHeaders ? UPSTREAM_HEADERS : { Upgrade: "websocket" };
    const started = Date.now();
    try {
        const res = await fetch(ACHEX_URL, { headers });
        const body = { ok: true, status: res.status, hasWebSocket: !!res.webSocket, ms: Date.now() - started, sentHeaders: headers };
        if (res.webSocket) {
            try { res.webSocket.accept(); res.webSocket.close(1000); } catch (_) {}
        }
        return json(body);
    } catch (e) {
        return json({ ok: false, error: String(e), ms: Date.now() - started, sentHeaders: headers }, 200);
    }
}

/** 受け取ったヘッダをそのまま返す。/probe が送ったヘッダが実際に届いているかの確認用。 */
function handleEcho(request) {
    return json({ receivedHeaders: Object.fromEntries(request.headers), cf: request.cf ?? null });
}

function json(obj, status = 200) {
    return new Response(JSON.stringify(obj, null, 2), {
        status,
        headers: { "content-type": "application/json; charset=utf-8" },
    });
}
