# 評測觀察台設計

- 日期：2026-11-22
- 狀態：已核准（2026-11-22）
- 適用基線：Git `743e806`、Prompt `density-v4.2`、Evaluator `2.1`

## 目的與背景

現有專案可用 CLI 執行單輪角色評測與固定十輪完整課堂，也會輸出 JSON；但缺少統一的執行入口、進度狀態、歷史報告索引、逐筆案例解釋與人工覆核介面。研究者目前只能閱讀終端摘要或散落的 JSON／Markdown，容易混淆硬性規則、模型原生輸出、Guard 修正及 fallback。

第一版評測觀察台要讓研究者在同一個本機網頁中啟動評測、查看執行狀態、檢視歷史報告、篩選逐筆結果並保存人工覆核。它不改變現有研究主張，也不把硬性規則分數包裝成學生真實度。

## 已確認的方向

- 採用「FastAPI 本機背景工作＋JSON 報告」；不在長時間 HTTP 請求中同步等待評測完成。
- 第一版同時支援從網頁啟動評測，以及讀取與人工覆核既有結果。
- 採用研究者單頁工作台：執行概覽、案例篩選、案例內容與人工覆核集中在同一頁。
- 第一版優先可用與可觀察，之後再增加取消、重試、圖表、跨報告比較等能力。
- 不修改現有課堂 SQLite schema。

## 目標

1. 從網頁選擇 provider、suite、模型與重複次數後建立評測工作。
2. 顯示 queued、running、completed、failed、interrupted 狀態與已完成／總筆數。
3. 保存可自我解釋且具版本的完整 JSON 報告。
4. 清楚分開 raw Ollama、guarded、fallback、mock 與 error。
5. 逐筆顯示教師問題、角色、預期／禁用 marker、原始回答、最終回答、Guard 原因及硬性檢查。
6. 保存人工覆核狀態與備註，且不自動宣稱人工評分結論。
7. 伺服器重啟後仍可讀取完成報告；先前 running 工作標為 interrupted。
8. 對現有 CLI、課堂流程與測試保持相容。
9. 第一版可唯讀載入四份最具後續價值的既有報告，人工覆核另存本機 overlay，不改寫封存證據。

## 非目標

- 第一版不建立外部工作佇列、獨立 worker、雲端服務或多人權限。
- 不加入 RAG、學生同儕互動或課後教師評價。
- 不建立或改變正式專家評分量尺。
- 不把 holdout v1 當成修改 Prompt 後可重複宣稱泛化改善的資料。
- 不自動提交評測資料、逐字稿或任何資料到外部服務。
- 不修改 `sessions`、`student_states` 或 `events` 的 SQLite schema。

## 反目標

- 不只顯示單一 pass rate，而隱藏來源分類與 Guard 使用量。
- 不把 guarded 或 fallback 結果算成模型原生成功。
- 不讓瀏覽器提供任意輸出路徑，避免路徑穿越或覆寫專案檔案。
- 不在報告缺欄位時由前端猜測教師問題、marker 或原始回答。
- 不讓評測工作阻塞 FastAPI 的一般課堂 API。

## 現有測試與資料基線

### 自動化測試

43 項 `unittest` 使用 MockProvider 與暫存 SQLite，驗證課堂流程、角色規則、Guard、fallback、API 與評測資料結構。這是 deterministic 程式基線，不代表模型品質。

### 單輪角色評測

`evaluation.py` 對 baseline 或 holdout 情境重複執行。每次使用新的 `StudentState`，只檢查單輪反應。現有 `passed` 需要同時符合：非空且 45 字以內、命中至少一個預期 marker、沒有禁用 marker。

### 固定十輪課堂

`classroom_scenario.py` 使用暫存 SQLite 執行十輪，檢查發言者、參與分布、跨輪迷思狀態、行為與課堂結束。指定 `--output` 時才保留 JSON。

### 重要解讀限制

- baseline 可用於開發；已使用的 holdout v1 不可重複調參後宣稱改善。
- Mock 只證明流程；hard pass rate 不是語意正確性或學生真實度。
- 現有 `AgentReply` 沒有保存 Guard 前原始文字，只有最終 `response`、`guarded` 和 `guard_reason`。
- 現有 `human_review` 尚無正式定量量尺。

### 第一版保留的既有報告

觀察台不載入所有早期 smoke 與 Prompt 開發資料，只保留未來仍會用於比較或人工覆核的四份代表性 JSON：

1. `2026-11-10-qwen2.5-3b-density-v4-2-ab.json`：目前 3B baseline。
2. `2026-11-10-qwen2.5-7b-density-v4-2-ab.json`：與 3B 同設定的模型比較 baseline。
3. `2026-11-10-qwen2.5-3b-density-holdout-v1.json`：目前最重要的人工標註對象；介面必須標示「已使用，不可用於調參後宣稱改善」。
4. `2026-11-10-full-classroom-density-v4-2-run1.json`：目前最新的跨輪狀態與完整課堂回歸證據。

density-v1／v2／v3、早期 v4／v4.1 完整課堂與 smoke JSON 仍保留在 `docs/evaluations/` 作歷史證據，但不進入第一版觀察台索引。原因是 evaluator／Prompt 與欄位語意已不同，混在日常介面會增加誤讀，也不會成為未來重複執行的主要基線。

未來重複使用的資料族群固定為：目前開發 baseline、一次性 holdout、最新完整課堂回歸，以及同設定模型 A/B。新工作一律使用 report v2，不再擴充任意舊格式匯入。

## 考慮過的方案

### A. HTTP 請求內同步執行

實作最少，但 Ollama 評測可能持續數分鐘，容易逾時，無法可靠顯示進度，也會占用請求處理流程，因此不採用。

### B. FastAPI 內建背景工作＋JSON 報告

建立 in-process job manager，以背景執行緒執行 blocking Ollama 呼叫，工作狀態與報告寫入本機 JSON。能快速支援單機研究原型，且不需修改課堂資料庫。使用者已選擇此方案。

### C. 獨立 worker／queue／資料庫

可提供跨程序恢復、取消、重試與多人操作，但超過目前單機原型需求，第一版不採用。

## 整體架構

```text
evaluation.html / evaluation.js
        │
        ├─ POST /api/evaluations ──────┐
        ├─ GET  /api/evaluations       │
        ├─ GET  /api/evaluations/{id}  │
        └─ PATCH .../results/{index}/review
                                       ▼
                              EvaluationJobManager
                               │              │
                               │ background   │ atomic JSON
                               ▼              ▼
                         evaluate_provider  data/evaluations/
                               │
                    OllamaProvider / MockProvider
```

### 模組責任

- `main.py`：只放請求驗證、HTTP 路由、狀態碼與靜態頁面入口。
- `evaluation.py`：維持可從 CLI 使用的評測核心，新增可選的進度 callback 與自我解釋欄位。
- `evaluation_jobs.py`：新增工作建立、背景執行、狀態轉換、重啟復原與 JSON 儲存。
- `llm.py`／`models.py`：保留 Ollama Guard 前文字，供評測報告使用；不新增 SQLite 欄位。
- `static/evaluation.html`、`evaluation.js`、`evaluation.css`：單頁觀察台。

## JSON 儲存設計

### 目錄

第一版的本機執行資料放在：

```text
data/evaluations/<run_id>/job.json
data/evaluations/<run_id>/report.json
```

`run_id` 由 UTC 時間與隨機識別碼產生，不接受使用者指定。`data/evaluations/` 加入 `.gitignore`；需要保留為研究證據的選定報告，仍由研究者整理至 `docs/evaluations/`。

### job.json

```json
{
  "run_id": "20261122T120000Z-a1b2c3d4",
  "status": "running",
  "created_at": "...",
  "started_at": "...",
  "finished_at": null,
  "request": {
    "provider": "ollama",
    "suite": "baseline",
    "model": "qwen2.5:3b",
    "repeats": 10
  },
  "progress": {"completed": 12, "total": 50},
  "error": null
}
```

狀態只能依序轉移：

```text
queued → running → completed
                 ↘ failed
queued/running --伺服器重啟→ interrupted
```

JSON 以同目錄暫存檔寫入後原子取代，避免伺服器或程序中斷留下半份檔案。

### report.json v2

在現有報告上新增：

- `report_schema_version`
- 每筆結果的 `teacher_message`
- `misconception_strength`
- `expected_markers`
- `forbidden_markers`
- `raw_response`
- `response`（Guard 後最終回答）
- 可由 UI 更新的 `human_review`

`raw_response` 定義為 Ollama 已解析、正規化但尚未經角色／行為／長度 Guard 的文字。若 provider 失敗且沒有有效文字則為 `null`。Mock 直接執行時可與 `response` 相同。

### 既有報告與覆核 overlay

四份既有 JSON 視為唯讀研究證據，不直接寫回 `docs/evaluations/results/`。觀察台使用固定 manifest 登記檔案及類型，讀取時轉成共同的 view model；缺少 `raw_response` 等新欄位時明確顯示「舊報告未保存」，不得以最終回答猜測。

既有單輪報告雖未內嵌 `teacher_message` 與 marker，但 `scenario_id` 可對應 evaluator 2.1 的固定情境。第一版建立版本鎖定的 legacy scenario catalog，保存 evaluator 版本、suite、scenario id、教師問題、初始迷思與 marker，並由固定 manifest 指明報告使用哪一版 catalog。這是有來源的歷史資料補充，不直接讀取可能已被未來修改的最新 `SCENARIOS` 常數。若 id、版本或 catalog 無法對應，介面顯示缺失，不能猜測。

人工覆核另存至：

```text
data/evaluations/legacy-reviews/<report-id>.json
```

overlay 以報告相對路徑與內容雜湊識別來源；若封存報告內容改變，舊覆核不會靜默套用到不同資料。

### 人工覆核

第一版不建立新的 1–5 專家量尺。沿用現有欄位，介面使用 `yes`／`no`／`uncertain`：

- `directly_answers_teacher_request`
- `role_consistency`
- `student_realism`
- `notes`
- `status`：`pending` 或 `completed`
- `reviewed_at`

人工覆核分成兩個可能的 target：

- `delivered`：師培生實際會看到的最終回答，所有非 error 結果都可覆核。
- `raw_model`：Guard 前的模型原始回答，只在 `guarded` 且有保存 `raw_response` 時另外覆核。

`raw_ollama` 的最終回答就是模型原始回答，因此只需一份 `delivered` 覆核，分析時可同時代表 native output。`fallback`／`mock` 只覆核 delivered，不能列入模型原生成功。舊 guarded 報告沒有保存 raw text 時，`raw_model` 顯示 unavailable，不要求補評。

「保存草稿」可保留部分欄位與 `pending`；只有研究者明確按下「完成覆核」，且該 target 的三個判讀欄位皆有 `yes`、`no` 或 `uncertain` 值時，才標成 `completed`。備註選填。一筆結果只有在所有 applicable targets 都完成後，才計入 result-level completed。這些欄位只保存人工判讀，不計算正式研究總分。未來若要採定量量尺，必須另由使用者確認並新增 ADR。

## API 設計

### `POST /api/evaluations`

建立工作。欄位：`provider`、`suite`、`model`、`repeats`。`provider=ollama` 時模型必須在 `/api/models` 清單中；`mock` 不接受模型。回傳 `202 Accepted` 與 job snapshot。

### `GET /api/evaluations`

回傳新工作及固定 manifest 中四份既有報告的摘要，依建立時間新到舊排序。不回傳完整逐筆結果。舊報告會標示 `legacy`、`report_type` 與缺失能力。

### `GET /api/evaluations/{run_id}`

回傳 job 狀態；完成後一併回傳完整 report。找不到回傳 404；損壞 JSON 回傳可解釋錯誤，不讓整個清單失敗。

既有報告的 `run_id` 由固定 manifest 提供；API 透過對應 adapter 產生共同 view model。第一版只支援單輪 evaluator 與指定的最新完整課堂兩種舊格式。

### `PATCH /api/evaluations/{run_id}/results/{result_index}/review`

只允許更新指定 target 的 human review 欄位。工作未完成、索引不存在、target 不適用或欄位不合法時回傳 409／404／422。更新後重新計算 target-level 與 result-level `human_review_status`，並原子保存報告。

### 第一版不提供

- 取消工作
- 刪除報告
- 重新排程
- 任意檔案匯入／上傳

### Provider 與並行語意

網頁啟動的單輪 Ollama 評測沿用 CLI 的 `OllamaProvider` 行為：單筆 `RuntimeError` 記為 `error`，不自動改用 Mock fallback，以維持新舊單輪報告可比較。`fallback` 分類仍可出現在既有完整課堂報告；未來若網頁支援完整課堂執行，再沿用其 `ResilientProvider` 行為。

第一版同一時間最多執行一個背景評測工作。FastAPI 課堂 API 仍可回應，但評測與課堂共用本機 Ollama，課堂模型回覆可能變慢；介面在評測執行時顯示警告。第一版不建立 Ollama 推論排程器，也不承諾評測期間的課堂推論延遲。

## UI 設計

### 主要區域

1. 左側導覽：執行紀錄、人工覆核、模型比較（第一版可先標示稍後提供）、返回課堂模擬。
2. 頁首：目前工作名稱、版本、狀態、人工覆核完成數與「開始新評測」。
3. 摘要卡：硬性通過率、raw Ollama、guarded／fallback、平均延遲。
4. 案例清單：依通過狀態、來源分類、角色與覆核狀態篩選。
5. 案例詳情：教師問題、原始／最終回答、marker、各項硬性檢查、Guard 原因和錯誤。
6. 人工覆核：三個是／否／無法判定欄位、備註、保存草稿、完成覆核並下一筆；guarded 且有 raw text 時可切換「模型原始」與「系統最終」。

### 新評測表單

- provider：Mock 或 Ollama
- suite：baseline 或 holdout
- model：只在 Ollama 時顯示本機已安裝模型
- repeats：有上限的正整數
- holdout 顯示警告：「holdout v1 已使用；只能重現，不能用於調參後宣稱泛化改善。」

### 執行更新

第一版使用短間隔 polling 查詢正在執行的 job；只有頁面顯示 running 時輪詢，完成、失敗或離開頁面即停止。之後可改為 SSE，但不是 MVP 必要條件。

## 錯誤與恢復

- 單一 RuntimeError 保存為該結果的 `error`，遵循現有 evaluation 行為；整批是否繼續由評測核心決定。
- 背景工作未捕捉例外時將 job 標成 failed，保存簡短錯誤訊息，不回傳 traceback 給前端。
- 啟動時掃描 queued／running job 並標成 interrupted，不自動重跑，避免重複實驗。
- 損壞或缺少 report 的工作仍列在歷史清單，並顯示資料錯誤。
- 人工覆核保存失敗時保留表單內容並顯示錯誤，不假裝成功。
- 同時建立第二個評測工作時回傳 409，並提供目前執行中的工作摘要。

## 測試策略

### 單元測試

- raw response 在 Guard 前正確保存。
- report v2 包含情境說明與來源分類。
- job 狀態轉移及原子寫入。
- 伺服器重啟把未完成工作標成 interrupted。
- 人工覆核只更新允許欄位並重新計數。
- 既有報告 adapter、內容雜湊與 review overlay 不改寫封存 JSON。
- legacy scenario catalog 必須以 evaluator 版本與 manifest 對應，未知 id 不得套用最新情境猜測。
- Ollama 單筆失敗記為 error，不轉成 Mock fallback。
- 同一時間只允許一個背景工作。
- guarded 新報告的 raw model 與 delivered review 可分別保存與計數。
- 路徑識別碼與輸入驗證。

### API 測試

- Mock 工作可建立、查詢並完成。
- 列出歷史工作。
- 讀取完成報告。
- 保存人工覆核。
- 無效模型、suite、repeats、run_id 和結果索引。

### 必做驗證

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock
.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario --provider mock
```

由於包含 API／UI 修改，還要以 `run.ps1` 檢查 `/api/health`、建立 Mock 評測、輪詢完成、讀取報告、保存人工覆核及瀏覽器主要流程。

## 分階段實作

1. 擴充報告格式與 raw response，先以測試鎖定資料語意。
2. 建立 JSON store 與背景 job manager。
3. 加入 FastAPI 評測 API。
4. 建立單頁觀察台與新評測表單。
5. 完成 API／UI smoke、文件、Roadmap、ADR（若需要）與 Development Log。

## 驗收條件

- 使用者可在網頁建立 Mock 評測並看到 queued／running／completed。
- 完成後可檢視每一筆情境、raw／final 回答、Guard 原因與硬性檢查。
- 可依來源、通過狀態、角色及人工覆核狀態篩選。
- 可保存人工覆核並在重新整理後讀回。
- 伺服器重啟後完成報告仍存在，未完成工作顯示 interrupted。
- 課堂 SQLite schema 不變，現有 CLI 與 43 項基線行為相容。
- 所有必要測試與 smoke 流程通過。
- `docs/DEVELOPMENT_LOG.md` 記錄目的、變更、驗證和未解問題；`docs/ROADMAP.md` 反映評測觀察台位於下一輪角色調整之前。

## 待未來決定

- 正式專家評分量尺、評分者身份欄位與一致性統計。
- 是否支援匯入既有任意 JSON；第一版不提供。
- 取消／重跑／刪除工作的操作與資料保留期限。
- 跨報告比較圖表與 CSV 匯出。
- 是否將選定研究報告從本機資料區正式封存到版本控制。
