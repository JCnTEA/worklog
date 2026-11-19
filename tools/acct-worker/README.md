# 帳號與紀錄服務（Cloudflare Worker）

網頁只認得這個網址；GitHub 權杖、登入簽章金鑰都鎖在 Worker 的環境變數裡，不會出現在任何前端程式碼或回應。

## 部署（一次性，約 5 分鐘）

```bash
cd tools/acct-worker
npx wrangler login
npx wrangler kv namespace create KV      # 複製印出的 id，貼回 wrangler.toml
npx wrangler secret put SECRET           # 隨便一串長字（登入簽章用）
npx wrangler secret put GH_TOKEN         # GitHub fine-grained token，只勾 jcntea/worklog 的 Contents: Read/Write
npx wrangler deploy
```

部署完會印出 `https://worklog-acct.<你的子網域>.workers.dev`，把這個網址貼進網頁「帳號」面板的設定欄位（存在本機，不會公開）。

## 資料放哪

- 帳號：KV，只存 PBKDF2 雜湊＋鹽，沒有明碼密碼。
- 紀錄：`data/<帳號雜湊>.json`（`GH_REPO` 有設時）或 KV。內容是前端用密碼派生金鑰加密（AES-GCM）後的密文，伺服器與倉庫都讀不到明文。
- 不設 `GH_TOKEN` 也能跑：紀錄留在 KV，一樣可用、一樣加密。

## 端點

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | /api/health | 檢查服務與儲存後端 |
| POST | /api/reg | `{u,p}` 註冊 |
| POST | /api/login | `{u,p}` → `{token}`（30 天） |
| PUT | /api/rec | `{token, enc}` 上傳密文 |
| GET | /api/rec | `?token=` 取回密文 |
