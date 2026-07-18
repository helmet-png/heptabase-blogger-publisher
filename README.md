# Heptabase → Blogger Publisher

Publish a Heptabase card to Blogger as a draft, in one click — **with highlights preserved**.

> 中文版請往下捲，或直接跳到 [繁體中文說明](#繁體中文說明)。

Heptabase's Markdown export drops highlights (they live in the card's internal
ProseMirror data, not in Markdown syntax). This tool reads the card's raw
ProseMirror JSON through the Heptabase CLI instead, converts it to
Blogger-safe HTML with **inline styles** (so your Blogger theme can't strip
the formatting), and pushes it to Blogger via the Blogger API v3 as a draft.

Single Python file, standard library only. No `pip install`, no Node.

## Features

- **Highlights** → `<mark>` (the reason this tool exists)
- **Math** (`math_inline` / `math_display`) → rendered with MathJax
- Tables, ordered / bulleted / to-do lists, blockquotes, code blocks
- Text color and background color marks
- Embedded card references are replaced with the card's title
- Headings are demoted one level (the card's H1 is dropped if it duplicates the post title) so the Blogger post title stays the top-level heading
- Live preview of exactly what will land in Blogger, before you publish
- Always creates a **draft** — you press the final Publish inside Blogger

Images are not imported yet: a placeholder box is inserted reminding you to
upload them in the Blogger editor.

## Requirements

- **Heptabase desktop app**, running (the tool talks to its bundled CLI)
- **Python 3.8+**
- A **Google account** with a Blogger blog
- A **Google Cloud OAuth client** (see setup below — a one-time, ~10 minute step)

## Setup

1. `python app.py` (or double-click `start.bat` on Windows). It opens
   `http://localhost:8822` in your browser.
2. Follow the in-app wizard. On the current (2025–2026) Google Cloud Console
   the old "OAuth consent screen" now lives under **Google Auth Platform**:
   - Create a project in [Google Cloud Console](https://console.cloud.google.com/projectcreate) and switch to it
   - Enable [Blogger API v3](https://console.cloud.google.com/apis/library/blogger.googleapis.com)
   - Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) → **Get started**: app name, support email, Audience = **External**, contact email
   - **Critical:** on the **Audience** tab, add your own Gmail under **Test users** (skip this and authorization will fail)
   - On the **Clients** tab → **Create client** → application type **Desktop app**
   - Paste the Client ID + Secret into the page and authorize once (if you see "Google hasn't verified this app", click Advanced → Go to … — it's your own test app)
3. Pick which blog to publish to. Done — credentials are saved to a local
   `config.json` (git-ignored) and you won't need to sign in again.

## Usage

1. Make sure the Heptabase desktop app is open.
2. Run the tool, search for a card, click it to preview.
3. Adjust the post title if you like, then **push the draft to Blogger**.
4. Open the draft in Blogger, review, and publish.

## How it works

`heptabase note read <cardId>` returns the card as ProseMirror JSON. A small
recursive renderer walks the node tree and emits HTML where every element
carries an inline `style` attribute, which is what keeps the layout intact
regardless of the Blogger theme. The result is sent to
`POST /blogs/{blogId}/posts?isDraft=true`.

## Configuration & security

`config.json` holds your OAuth `client_secret`, `refresh_token`, and selected
blog. It is **git-ignored** and never leaves your machine. See
`config.example.json` for the shape.

## License

[MIT](LICENSE)

---

## 繁體中文說明

一鍵把 Heptabase 卡片發布成 Blogger 草稿，**而且保留 highlight（螢光筆標記）**。

Heptabase 的 Markdown 匯出會丟失 highlight（它存在卡片內部的 ProseMirror 資料裡，
不在 Markdown 語法中）。本工具改為透過 Heptabase CLI 讀取卡片的原始 ProseMirror
JSON，轉成**全 inline style** 的 Blogger-safe HTML（這樣 Blogger 佈景主題就蓋不掉
排版），再經 Blogger API v3 推送成草稿。

單一 Python 檔、純標準庫，不需要 `pip install`，也不需要 Node。

### 功能

- **Highlight** → `<mark>`（這是本工具存在的理由）
- **數學公式**（`math_inline` / `math_display`）→ 以 MathJax 渲染
- 表格、編號 / 項目 / 待辦清單、引用、程式碼區塊
- 文字色與背景色標記
- 嵌入的卡片參照會代換成該卡片的標題
- 標題層級整體降一級（開頭 H1 若與文章標題重複則自動略過），讓 Blogger 文章標題維持最高層級
- 發布前即時預覽「貼進 Blogger 後真正的樣子」
- 一律建立**草稿** —— 最終發布由你在 Blogger 按下

圖片目前不會匯入：會插入一個占位框，提醒你在 Blogger 編輯器手動上傳。

### 需求

- **Heptabase 桌面 App**，且須開著（工具靠它內建的 CLI 運作）
- **Python 3.8 以上**
- 一個有 Blogger 網誌的 **Google 帳號**
- 一組 **Google Cloud OAuth 用戶端**（見下方設定，一次性約 10 分鐘）

### 設定

1. 執行 `python app.py`（Windows 可雙擊 `start.bat`），會自動開啟
   `http://localhost:8822`。
2. 跟著頁面上的精靈操作。注意 Google 在 2025–2026 改版，舊的「OAuth 同意畫面」
   已整併進「**Google 驗證平台**」（第一次進去會跳「開始使用」精靈）：
   - 在 [Google Cloud Console](https://console.cloud.google.com/projectcreate) 建立專案並切換過去
   - 啟用 [Blogger API v3](https://console.cloud.google.com/apis/library/blogger.googleapis.com)
   - 開 [Google 驗證平台](https://console.cloud.google.com/auth/overview) →「開始使用」：填應用程式名稱、支援信箱，目標對象選「**外部**」，填聯絡 email
   - **最關鍵：** 到「**目標對象**」分頁，把自己的 Gmail 加入「**測試使用者**」（漏了必定授權失敗）
   - 到「**用戶端**」分頁 →「建立用戶端」→ 應用程式類型選「**電腦版應用程式**」
   - 把 Client ID + Secret 貼進頁面，授權一次（若出現「Google 尚未驗證這個應用程式」，按「進階 → 前往…」即可，因為是你自己的測試應用程式）
3. 選擇要發布到哪個網誌。完成 —— 憑證會存進本機的 `config.json`（已被 git 忽略），
   之後不必再登入。

### 使用

1. 確認 Heptabase 桌面 App 已開啟。
2. 執行工具，搜尋卡片，點一下即可預覽。
3. 需要的話調整文章標題，然後**推送草稿到 Blogger**。
4. 到 Blogger 開啟草稿、檢查、發布。

### 運作原理

`heptabase note read <cardId>` 會回傳卡片的 ProseMirror JSON。一個小型遞迴轉換器
走訪節點樹，輸出每個元素都帶 inline `style` 的 HTML —— 這正是排版不會被 Blogger
佈景主題破壞的關鍵。結果送往 `POST /blogs/{blogId}/posts?isDraft=true`。

### 設定與安全

`config.json` 存放你的 OAuth `client_secret`、`refresh_token` 與所選網誌，
**已被 git 忽略**，不會離開你的電腦。格式範本見 `config.example.json`。

### 授權

[MIT](LICENSE)
