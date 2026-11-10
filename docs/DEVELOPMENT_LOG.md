# 開發紀錄

## 2026-10-22 — 建立可持續開發基線

### 目的

讓後續工作可在中斷後快速恢復，並把 Prompt/角色品質從人工感覺轉成可重複的評測資料。

### 變更

- 新增根目錄 `AGENTS.md`，定義專案邊界、測試、Git、資料安全與重大決策規則。
- 新增專案上下文、架構、路線圖及 ADR 決策紀錄。
- 新增角色一致性評測模組與固定情境。
- 新增評測單元測試與執行方式。

### 驗證

- `\.venv\Scripts\python.exe -m unittest discover -v`：11 項通過。
- `\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock`：5/5 情境通過，pass rate 1.0。
- `\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider ollama --repeats 1`：修正前 1/5；修正迎合 guard 後 3/5。詳細紀錄見 `docs/evaluations/2026-10-22-ollama-smoke.md`。
- API smoke：暫時啟動 `run.ps1`；`GET /api/health` 200、建立課堂 201、發言 200、結束課堂 200。實際使用 `qwen2.5:3b`，點名小哲後由 `misconception` 角色回答，最終狀態為 `finished`。
- `git diff --check`：通過；僅有 Windows LF/CRLF 提示，無 whitespace error。

### 下一步

- 執行 mock 評測作為固定基線。
- 將詞彙規則改為結構化/人工覆核並存的評測，降低語意合理但詞彙未命中的假陰性。
- 使用 Ollama 對每個情境至少重複 10 次並保存聚合結果。
- 依實驗結果調整 Prompt；RAG 等教材來源確定後再開始。

## 2026-10-22 — 版本化重複評測與 density-v2

### 目的

保存可重現的模型設定、Prompt/評測版本、原始回應與逐角色統計，並以同一 evaluator 比較 Prompt 修改。

### 已完成

- 評測 CLI 新增 `--output`，保存完整 UTF-8 JSON。
- 報告新增 UTC 時間、evaluator/prompt 版本、模型參數及逐情境通過率。
- `density-v1` 執行 50 次：30/50，總通過率 60%。
- 依失敗樣本建立 `density-v2` 角色專屬規則。
- 擴充迷思 guard，攔截「沒有直接關係／謝謝提醒／你說得對」等過早改口。

### 待驗證

- 已完成 15 項自動測試，全部通過。
- 已用相同 evaluator 分別執行 v1、v2、v3 各 50 次。

### v2 結果與後續

- `density-v2`：27/50（54%），低於 v1 的 60%，不接受為改善版。
- 一般角色因回答過長退步；分心角色 0/10，純 Prompt 指令未生效。
- 建立 `density-v3`：限制單句 25–40 字、不得超過 45 字，並新增只針對泛問「剛才問題」的分心角色 guard。
- `density-v3`：39/50（78%）；分心角色由 v1 的 10% 提升為 100%，總通過率較 v1 增加 18 個百分點。
- 保存三版完整原始 JSON 與三份人類可讀比較報告。

### 已知問題

- Evaluator 1.0 的迷思 marker 有假陰性；需升版後用新 holdout 情境測試，不能直接重評同一批資料宣稱改善。
- 迷思 guard 尚未涵蓋「比較重不代表密度大」句型。
- 害羞角色仍有 4/10 未呈現明確的不確定語氣。

## 2026-10-22 — 受控分心與天馬行空行為

### 目的

在不擴大成小學生年齡模型的前提下，讓分心角色能依教師情境呈現沒跟上、生活岔題、天馬行空聯想，以及被具體點名後回到課程。

### 變更

- 新增 `behavior.py`，把行為規劃從 Prompt 字串中分離並可單元測試。
- `AgentReply`、事件 metadata 與評測結果新增 `behavior_type`、`guarded`、`guard_reason`。
- 前端逐字稿顯示行為中文標籤與「系統修正」。
- 密度 Prompt 升為 `density-v4`，向模型提供本輪行為類型及指示。
- 行為標籤與模型輸出不一致時，使用可追蹤的 behavior guard 修正。

### 驗證

- 自動測試：25 項通過。
- Ollama `qwen2.5:3b` 四情境 smoke：最終輸出 4/4 符合行為；其中 3/4 經 guard 修正，1/4 為模型原生成功。
- API smoke：建立課堂 201，兩次教師發言皆 200；第一輪 metadata 為 `distracted`，第二輪為 `redirected`，事件共 4 筆。
- 瀏覽器人工測試：逐字稿可見「分心」與「被拉回課程」中文標籤，內容與 metadata 一致；需要 guard 時會額外顯示「系統修正」。
- 詳細案例見 `docs/evaluations/2026-10-22-behavior-v4-smoke.md`。

### 限制與下一步

- 目前證明的是完整系統能產生受控行為，不是模型本身已有高行為遵循率。
- 學生彼此互動仍未實作。
- 下一步建立新的 holdout 情境與人工真實度標註，不用已看過的四個案例調高 evaluator 分數。

## 2026-10-22 — 十輪完整課堂測試

### 目的

以固定、可重跑的完整密度課堂檢查五角色參與、點名、迷思狀態、分心拉回、provider fallback、逐字稿與結束課堂，而非只測單句回應。

### 變更

- 新增 `classroom_scenario.py` 與 10 輪完整課堂情境。
- 新增逐輪硬性檢查、provider 使用統計及完整 JSON 匯出。
- 發現 Ollama 會回傳空值或 schema placeholder，Prompt 升為 `density-v4.1`，新增 placeholder 拒絕與單行正規化。
- 新增 5 項相關回歸測試；完整測試總數增為 30。

### 結果

- Run 1：揭露 placeholder 假陽性並保留原始結果。
- Run 2：9/10 輪通過硬性檢查；7 輪 raw Ollama、1 輪 guarded、2 輪 mock fallback。
- 五角色皆參與、20 筆事件、點名 10/10、迷思 3→2→1、課堂正常結束。
- 完整逐字稿與人工判讀見 `docs/evaluations/2026-10-22-full-classroom-review.md`。

## 2026-10-22 — Proposal 對齊與下次開發交接

### Proposal 核心

- 保留五位獨立學生、課堂管理、逐字稿與事件紀錄、證據式教師評價及人工評分比較等核心承諾。
- 研究定位為師培練習與反思工具，不代表真實學生，也不取代正式教師評鑑。
- 依教授與學長姐建議，第一階段已由任意主題收斂至國中自然科密度，並要求學生迷思不因一次提示立即消失。

### 下次開發目標

1. 先修正迷思迎合、回答過長與未實際回應教師問題。
2. 建立全新 holdout 情境與人工標註，分開檢查 raw Ollama、guarded 與 fallback。
3. 通過固定版本驗證後，再以一份具授權且版本固定的密度教材進行小型 RAG pilot。
4. RAG 必須分開學生教材、教師教案／解答及迷思案例，並與 Prompt-only 比較正確性、越界率、角色真實度和延遲。

### 尚待使用者決定

- RAG 第一版採用的教材名稱、版本、授權狀態與可否納入專案測試資料。

## 2026-11-10 — Density v4.2 與 holdout v1

### 目的

接續角色可靠度工作，處理過早道謝與過長回答，建立不可反覆調參的未見案例，並把硬性規則與人工語意覆核分開。

### 變更

- Prompt 升為 `density-v4.2`；迷思強度大於等於 2 時，「謝謝老師／謝謝」會觸發角色 guard。
- 新增 45 字回答長度 guard；優先保留限制內的完整句，否則截為 44 字加刪節號，並記錄 `response_length` guard reason。
- Evaluator 升為 `2.0`，加入獨立 holdout v1、`source_category`、`source_usage` 與逐筆 `human_review` 模板。
- 完整課堂也分開記錄 raw Ollama、guarded、fallback，且每輪保留人工覆核欄位。
- 新增 `docs/TESTING.md`，整理自動、mock、Ollama、完整課堂及瀏覽器測試方式。

### 驗證

- 自動測試：36 項全部通過。
- Mock baseline：5/5；mock holdout：5/5；mock 完整課堂：10/10。
- Ollama holdout v1：29/50（58%）；37 次 raw Ollama、13 次 guarded、0 fallback。
- 角色通過率：主動 80%、一般 50%、迷思 40%、害羞 30%、分心 90%。
- density-v4.2 完整課堂：硬性 10/10；7 次 raw Ollama、2 次 guarded、1 次 fallback。

### 判讀與限制

- Marker evaluator 對「單位是否一致」「跟不上／再講一遍」「可能……吧」等合理表達仍有假陰性，因此 58% 不是人工真實度分數。
- 迷思學生仍有直接說出正解的角色漂移；害羞學生常過度確定；主動學生有時沒有延伸問題。
- holdout v1 已使用，不得再依其結果調整後重跑並宣稱泛化改善。下一版修改須用 baseline／開發案例，完成後建立 holdout v2。
- RAG 尚未開始，教材來源、授權與版本仍待使用者決定。

## 2026-11-10 — Windows PowerShell 啟動修正

### 問題

`run.ps1` 原為 UTF-8 無 BOM，且錯誤訊息包含中文。Windows PowerShell 5.1 依系統 ANSI code page 解讀後產生亂碼，部分中文字節使結尾雙引號無法正確解析，因而回報字串與 `}` 未結束。

### 修正與驗證

- 將啟動腳本改為純 ASCII，避免依賴 Windows PowerShell 版本與系統 code page。
- 新增回歸測試，要求 `run.ps1` 可完整以 ASCII 解碼並保留 uvicorn 與 `.venv` 啟動命令。
- 37 項自動測試全部通過；Windows PowerShell 5.1 解析回報 `PARSE_OK`。
- 使用獨立暫存資料庫與測試埠啟動 FastAPI，`/api/health` 回傳 `ok: true`，完成後已停止程序並刪除暫存資料。
