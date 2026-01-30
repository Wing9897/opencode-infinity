# User Service API

一個以 Express.js 打造的 JWT 保護型 REST 服務，提供 `/users` CRUD、集中式錯誤處理、Swagger/OpenAPI 文件與 node:test 自動化測試。此文件彙整所有你需要的資訊，協助快速在本地或 CI 環境啟動並維護服務。

---

## 功能概覽

| 能力                     | 說明                                                                                 |
|-------------------------|--------------------------------------------------------------------------------------|
| User CRUD               | 透過 `/users` 提供 GET/POST/PUT/DELETE，採 in-memory 儲存 (可替換成資料庫實作)。        |
| Authentication          | `/auth/login` 簽發 JWT，所有 `/users` 請求需附 `Authorization: Bearer <token>`。       |
| Validation & Errors     | 使用 validator 中介層確保輸入格式正確，統一回傳 `message` 與 `details`。               |
| Observability           | `/health`、morgan 紀錄、Helmet/CORS 強化安全，Swagger UI (`/docs`) 便於互動測試。        |
| Developer Experience    | `node --test` 覆蓋 controllers/middleware/utils，並提供完整 README/API/USAGE 文檔。     |

---

## 目錄結構

```
├── README.md            # 本文件
├── docs/
│   ├── API.md           # 詳細端點與回應格式
│   └── USAGE.md         # 實際操作指南 (含 cURL 範例)
├── src/                 # Express 應用程式 (app, routes, controllers, middleware, services, utils)
├── tests/               # node:test 測試案例
├── package.json         # 依賴與 scripts
├── .env.example         # 預設環境變數
└── ...
```

> 專案不一定會顯示所有程式檔案於 README 節錄中；請以實際 repo 為準。

---

## 快速開始

1. **安裝依賴**
   ```bash
   npm install
   ```
2. **設定環境變數**
   ```bash
   cp .env.example .env
   # 根據需求修改
   # PORT=3000
   # JWT_SECRET=super-secret-key
   # JWT_EXPIRES_IN=1h
   ```
3. **啟動 API**
   ```bash
   npm start      # production-like
   npm run dev    # development, NODE_ENV=development
   ```
4. **執行測試**
   ```bash
   npm test
   ```

成功啟動後可透過 `GET /health` 檢查狀態，並在 `http://localhost:<PORT>/docs` 使用 Swagger UI。

---

## 主要端點速覽

| Method | Path            | 描述                     | 認證 | 文件 |
|--------|-----------------|--------------------------|------|------|
| GET    | `/health`       | 回傳狀態/版本/時間戳     | ❌   | README |
| POST   | `/auth/login`   | 以 Demo 帳號換取 JWT     | ❌   | docs/API.md |
| GET    | `/users`        | 列出使用者 (可分頁)      | ✅   | docs/API.md |
| POST   | `/users`        | 建立使用者               | ✅   | docs/API.md |
| GET    | `/users/{id}`   | 查詢單一使用者           | ✅   | docs/API.md |
| PUT    | `/users/{id}`   | 更新使用者               | ✅   | docs/API.md |
| DELETE | `/users/{id}`   | 刪除使用者               | ✅   | docs/API.md |

詳細 payload/回應範例請見 [`docs/API.md`](docs/API.md)。

---

## 腳本與工具

| 指令         | 敘述                                              |
|--------------|---------------------------------------------------|
| `npm start`  | 以 `$PORT` 啟動伺服器 (預設 3000)。               |
| `npm run dev`| 設定 `NODE_ENV=development` 後啟動伺服器。        |
| `npm test`   | 執行 `tests/` 內所有 node:test 測試。             |

---

## 測試與品質

- `tests/users.test.js` 覆蓋 controller 與 auth middleware 流程。
- `tests/utils-library.test.js` 驗證 string/date/validation 工具庫。
- 建議在 PR 中加入 `npm test` 與 API smoke 測試工作流程。

---

## 常見問題

| 問題                                | 可能原因 / 解法                                                             |
|-------------------------------------|-----------------------------------------------------------------------------|
| `npm install` 失敗 (EAI_AGAIN)     | 檢查網路/代理，必要時設定 npm registry mirror。                             |
| `Authorization token missing`       | 確認 Header 為 `Authorization: Bearer <token>`。                            |
| 422 驗證錯誤                        | 參考 `docs/API.md` 的欄位限制並確保 `name/email/password` 合規。           |
| 500 伺服器錯誤                      | 查看伺服器日誌與測試輸出，確認 request body/JSON 是否有效。                |

---

## 下一步建議

1. **持久化儲存**：將 in-memory user service 換成 SQL/NoSQL。
2. **部署**：撰寫 Dockerfile，搭配 CI/CD 自動部署。
3. **安全**：整合 rate limiting、審核 JWT 來源與輪替策略。
4. **監控**：導入 APM/metrics（如 Prometheus）蒐集延遲與錯誤率。

---

## 相關文件

- [`docs/API.md`](docs/API.md) – 詳細 REST 規格
- [`docs/USAGE.md`](docs/USAGE.md) – 操作指南與 cURL 範例

---

## 工具函數庫

專案提供 `src/utils/` 工具函數，方便在 middleware/service 中重複使用。

| 模組 | 代表方法 | 用途 |
|------|----------|------|
| `stringUtils` | `toTitleCase`, `slugify`, `camelCase`, `maskEmail` | 清理或格式化任意字串 |
| `dateUtils` | `formatDate`, `addDays`, `diffInDays`, `formatRelative` | 進行日期格式化與運算 |
| `validationUtils` | `isEmail`, `isUUID`, `isStrongPassword`, `validateSchema` | 常見輸入驗證與 schema 驗證 |

使用方式：

```js
const { stringUtils, dateUtils, validationUtils } = require('./src/utils');

const title = stringUtils.toTitleCase('hello world');
const expiresAt = dateUtils.addDays(new Date(), 7);
const isValid = validationUtils.isEmail('user@example.com');
```

---

## 授權

MIT
