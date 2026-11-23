# 系統架構與呼叫流程

## 元件

| 檔案 | 責任 | 主要呼叫對象 |
|---|---|---|
| `static/index.html`、`app.js` | 教師操作與畫面更新 | FastAPI 課堂 JSON API |
| `static/evaluation.html`、`evaluation.js`、`evaluation.css` | 評測執行、歷史檢視、案例篩選與人工覆核 | FastAPI 評測 JSON API |
| `main.py` | 請求驗證、HTTP 狀態碼、組裝課堂與評測服務 | `ClassroomService`、`EvaluationJobManager`、`LegacyEvaluationArchive` |
| `service.py` | 建立課堂、選角、迷思更新、事件流程 | `Database`、`LLMProvider`、角色表 |
| `roles.py` | 五位學生的固定設定 | `StudentProfile` |
| `behavior.py` | 建立結構化 `BehaviorPlan`、提供角色示例並檢查輸出與行為一致 | `StudentProfile`、`StudentState` |
| `learning.py` | 定義密度概念／迷思狀態、角色初始值、教師證據分類與單級更新 | `StudentProfile`、`StudentState` |
| `llm.py` | Ollama/Mock 回應、fallback、角色防護 | Ollama HTTP API |
| `db.py` | Session、學生狀態、逐字稿儲存 | SQLite |
| `evaluation.py` | baseline／holdout 角色評測、來源分類、人工覆核模板與 JSON 結果 | 角色表、LLM providers |
| `evaluation_jobs.py` | 單一背景 worker、工作狀態、進度、原子 JSON 與新報告覆核 | `evaluation.evaluate_provider()` |
| `evaluation_archive.py` | 固定 manifest、舊格式 adapter、來源 hash 與唯讀報告覆核 overlay | `docs/evaluations/`、`data/evaluations/legacy-reviews/` |
| `classroom_scenario.py` | 十輪完整課堂、跨輪狀態檢查與逐字稿匯出 | `ClassroomService`、LLM providers |

## 模型選擇

- `GET /api/models` 透過 Ollama `/api/tags` 回傳本機已安裝模型、參數量、量化與檔案大小；Ollama 不可用時回傳空清單。
- `POST /api/sessions/{id}/messages` 的 `model` 欄位為選填。未提供時沿用服務預設 provider；提供時必須是 `/api/models` 列出的名稱。
- 模型是「每輪選擇」而非 session 固定設定，因此沒有修改 SQLite schema，也不影響舊版只送出 `message` 的 API。
- 學生事件 metadata 保存 `provider` 與 `model`。即使該輪 Ollama 失敗而使用 mock fallback，也保留原本要求的模型名稱，避免分析時誤判。

## 一次教師發言的呼叫鏈

```text
瀏覽器 app.js
  -> GET /api/models（頁面載入時取得本機模型）
  -> POST /api/sessions/{id}/messages（message + 選填 model）
  -> main.send_message()
  -> ClassroomService.send_teacher_message()
       -> Database 讀取 session 與五位學生狀態
       -> _choose_student() 選擇回應者
       -> Database 寫入教師事件
       -> apply_teacher_evidence()
            -> 辨識明確概念關係與理解檢核
            -> 只更新命中的概念熟練度／迷思信念，各最多一級
            -> 寫入可稽核 learning_update
       -> ResilientProvider.reply()
            -> build_behavior_plan() 規劃理解、意圖、信心、迷思、語氣與本輪行為
            -> OllamaProvider.reply() 加入兩組角色示例後生成
                 -> 第一次合格：raw_ollama
                 -> 第一次不合格：附失敗原因重試一次
                 -> 重試合格：retried
                 -> 重試仍失敗：deterministic Guard，標為 guarded
            -> 失敗時 MockProvider.reply()
       -> Database 保存該學生記憶與學生事件
       -> snapshot() 回傳完整課堂狀態
  -> app.js 重新渲染學生卡與逐字稿
```

## 狀態規則

- `StudentProfile` 是不可變角色設定：personality、ability level、misconception、participation level、speaking style。
- `StudentState` 是每個 session 獨立的可變狀態：迷思強度、參與次數、最後發言輪次、短期記憶。
- `concept_mastery` 保存五項 0–3 熟練度；`misconception_beliefs` 保存具名 0–3 迷思。`misconception_strength` 與角色主要迷思同步，供舊程式與報告相容。
- `student_states.concept_state_json` 保存兩組 map。既有 SQLite 啟動時以 additive migration 新增欄位；舊 row 的 `{}` 依角色與既有迷思強度補值，不刪改其他欄位。
- 記憶寫回 SQLite 時只保留最近 8 筆；送入模型時使用最近 6 筆。
- 每輪教師與學生事件共用同一個 `turn_number`。
- 學生事件 metadata 記錄 `model`、`behavior_type`、`behavior_plan`、`generation_attempts`、`retry_count`、`guarded` 與 `guard_reason`，因此不改 SQLite schema 也能分開分析第一次生成、重試與系統改寫。
- density-v4.4 另在教師／學生事件保存相同的 `learning_update`，學生事件保存更新後 `concept_mastery` 與 `misconception_beliefs`；這次新增 JSON 欄位但不改事件表 schema。

## 評測觀察台呼叫鏈

```text
瀏覽器 evaluation.js
  -> GET /api/evaluations（新工作摘要 + 四份固定歷史報告）
  -> POST /api/evaluations（provider + suite + model + repeats）
  -> EvaluationJobManager.create_job()
       -> 單一 ThreadPoolExecutor worker
       -> evaluation.evaluate_provider()
       -> 原子寫入 job.json / report.json
  -> GET /api/evaluations/{run_id}（輪詢狀態與完整 report）
  -> PATCH .../results/{index}/review（草稿或完成覆核）
       -> 新報告：原子更新 report.json
       -> 舊報告：只寫 legacy review overlay
```

- 新工作放在 `data/evaluations/<run_id>/job.json` 與 `report.json`，不進入課堂 SQLite。
- 同時間只執行一個背景評測。伺服器重啟時，未完成工作標為 `interrupted`，第一版不自動續跑。
- 四份歷史報告由 `docs/evaluations/observatory-manifest.json` 明確登記，不掃描任意 JSON。
- 歷史報告維持唯讀；人工覆核另存 `data/evaluations/legacy-reviews/<report-id>.json`，並以 SHA-256 綁定來源內容。
- `raw_response` 是第一次模型正規化回答；`generation_attempts` 保存每次文字及驗證失敗原因；`response` 是實際送出回答。舊報告缺少新欄位時不反推。
- `human_review.delivered` 覆核實際回答；`retried` 或 `guarded` 且保存 raw text 的新結果另有 `human_review.raw_model`。
- `BehaviorPlan` 是幕後決策，不是固定句子；每角色兩組示例是合成開發資料，尚未經真人學生語料驗證。
- 硬性通過率只代表 marker、長度與禁詞規則，不等於語意正確或學生真實度。holdout v1 已使用，只供重現與人工覆核。

## 測試分層

- 單元/服務測試：使用暫存 SQLite 與 `MockProvider`，快速且可重複。
- 行為評測：用固定情境計算角色一致性指標；可用 `--model` 指定 Ollama 模型，並保存逐輪延遲與 error。mock 是 CI 基線，Ollama 是實驗資料。
- API smoke test：伺服器啟動後檢查 health、建立 session、發言、結束課堂。
- 評測觀察台測試：檢查背景工作、歷史 adapter、覆核保存、UI 契約與 JavaScript 語法。
- UI 人工測試：確認角色卡、評測歷史、案例證據、窄版佈局、覆核重載與錯誤訊息。

模型輸出具有隨機性，因此 Ollama 評測不得取代 deterministic unit tests。
