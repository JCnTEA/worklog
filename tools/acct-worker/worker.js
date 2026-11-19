/**
 * 勤務記錄系統・帳號與紀錄服務（Cloudflare Worker）
 *
 * 設計原則
 *  - 帳密歸帳密：只存 PBKDF2 雜湊＋鹽，不存明碼密碼。
 *  - 日誌歸日誌：紀錄在前端就用密碼派生金鑰加密（AES-GCM），伺服器只轉存密文。
 *  - 權杖鎖在伺服器：GitHub token 只放環境變數（GH_TOKEN），永遠不出現在網頁或回應裡。
 */

const enc = new TextEncoder();

function j(o, st = 200) {
  const r = new Response(JSON.stringify(o), {
    status: st,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
  return cors(r);
}
function cors(res) {
  res.headers.set("access-control-allow-origin", "*");
  res.headers.set("access-control-allow-headers", "content-type");
  res.headers.set("access-control-allow-methods", "GET,POST,PUT,OPTIONS");
  return res;
}
function b64(buf) {
  const u = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]);
  return btoa(s);
}
async function pbkdf2(pass, salt, iter) {
  const key = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: enc.encode(salt), iterations: iter, hash: "SHA-256" },
    key,
    256
  );
  return b64(bits);
}
async function hmac(secret, msg) {
  const k = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64(await crypto.subtle.sign("HMAC", k, enc.encode(msg)));
}
async function sha16(s) {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return b64(d).replace(/[^A-Za-z0-9]/g, "").slice(0, 16).toLowerCase();
}
function uid(u) { return String(u || "").trim().toLowerCase(); }

async function ghPut(env, path, content, msg) {
  const base = `https://api.github.com/repos/${env.GH_REPO}/contents/${path}`;
  const h = {
    authorization: `Bearer ${env.GH_TOKEN}`,
    accept: "application/vnd.github+json",
    "content-type": "application/json",
    "user-agent": "worklog-acct-worker",
  };
  let sha;
  const cur = await fetch(base + "?ref=" + (env.GH_BRANCH || "main"), { headers: h });
  if (cur.ok) sha = (await cur.json()).sha;
  const body = { message: msg || "rec " + new Date().toISOString(), content };
  if (sha) body.sha = sha;
  const r = await fetch(base, { method: "PUT", headers: h, body: JSON.stringify(body) });
  if (!r.ok) throw new Error("GH " + r.status);
}
async function ghGet(env, path) {
  const h = {
    authorization: `Bearer ${env.GH_TOKEN}`,
    accept: "application/vnd.github+json",
    "user-agent": "worklog-acct-worker",
  };
  const r = await fetch(`https://api.github.com/repos/${env.GH_REPO}/contents/${path}?ref=` + (env.GH_BRANCH || "main"), { headers: h });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("GH " + r.status);
  const d = await r.json();
  const clean = String(d.content || "").replace(/\s/g, "");
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(clean), (c) => c.charCodeAt(0))));
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return cors(new Response(null, { status: 204 }));
    const url = new URL(req.url);
    const p = url.pathname.replace(/\/+$/, "");

    try {
      if (p === "/api/health") {
        return j({ ok: true, store: env.GH_REPO ? "github" : "kv", t: Date.now() });
      }

      if (p === "/api/reg" && req.method === "POST") {
        const b = await req.json();
        const u = uid(b.u);
        const pass = String(b.p || "");
        if (!/^[a-z0-9_.-]{3,24}$/.test(u)) return j({ err: "帳號 3–24 碼，只能用英數字與 . _ -" }, 400);
        if (pass.length < 6) return j({ err: "密碼至少 6 碼" }, 400);
        const key = "acc:" + u;
        if (await env.KV.get(key)) return j({ err: "這個帳號已經有人用了" }, 409);
        const salt = crypto.randomUUID();
        await env.KV.put(key, JSON.stringify({ salt, hash: await pbkdf2(pass, salt, 100000), at: Date.now() }));
        return j({ ok: true, u });
      }

      if (p === "/api/login" && req.method === "POST") {
        const b = await req.json();
        const u = uid(b.u);
        const pass = String(b.p || "");
        const rec = await env.KV.get("acc:" + u);
        if (!rec) return j({ err: "找不到這個帳號，先註冊" }, 404);
        const o = JSON.parse(rec);
        if ((await pbkdf2(pass, o.salt, 100000)) !== o.hash) return j({ err: "密碼不對" }, 401);
        const exp = Date.now() + 30 * 864e5;
        const token = u + "." + exp + "." + (await hmac(env.SECRET, u + "|" + exp));
        return j({ ok: true, u, exp, token });
      }

      const auth = async (tok) => {
        const parts = String(tok || "").split(".");
        if (parts.length !== 3) throw new Error("沒有登入或登入已過期");
        const [u, exp, sig] = parts;
        if (Number(exp) < Date.now()) throw new Error("登入已過期，請重新登入");
        if ((await hmac(env.SECRET, u + "|" + exp)) !== sig) throw new Error("登入驗證失敗");
        return u;
      };

      if (p === "/api/rec" && req.method === "PUT") {
        const b = await req.json();
        const u = await auth(b.token);
        const encStr = String(b.enc || "");
        if (encStr.length > 400000) return j({ err: "紀錄太大（超過 400KB）" }, 413);
        const payload = { u, at: Date.now(), enc: encStr };
        if (env.GH_REPO) await ghPut(env, "data/" + (await sha16(u)) + ".json", b64(enc.encode(JSON.stringify(payload))), "worklog rec " + u);
        else await env.KV.put("rec:" + u, JSON.stringify(payload));
        return j({ ok: true, at: payload.at });
      }

      if (p === "/api/rec" && req.method === "GET") {
        let u;
        try {
          u = await auth(url.searchParams.get("token"));
        } catch (e) {
          return j({ err: e.message }, 401);
        }
        let rec = null;
        if (env.GH_REPO) {
          rec = await ghGet(env, "data/" + (await sha16(u)) + ".json");
        } else {
          const raw = await env.KV.get("rec:" + u);
          rec = raw ? JSON.parse(raw) : null;
        }
        if (!rec) return j({ err: "雲端還沒有這個帳號的紀錄" }, 404);
        return j({ ok: true, enc: rec.enc, at: rec.at });
      }

      return j({ err: "not found" }, 404);
    } catch (e) {
      return j({ err: String((e && e.message) || e) }, 500);
    }
  },
};
