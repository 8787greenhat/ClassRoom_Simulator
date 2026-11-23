# 開發紀錄

## 2026-11-24 — 固化角色真實度後續開發順序

### 目的與變更

- 將研究查找後的改善方向寫入 `docs/ROADMAP.md`，避免後續又回到只靠單筆輸出反覆調 Prompt。
- 下一輪先建立五角色 × 六教師動作的人工開發矩陣，再處理角色知識上限、示例複製與單模型 context-first A/B；只有 Prompt 路線仍不足且已有合規人工偏好資料時，才評估本機 LoRA／DPO。
- 保持既有研究邊界：holdout v1 不調參、holdout v2 使用全新案例；RAG、多 agent、第二個 LLM judge 與真人資料不提前加入。

### 驗證

- 本批次只修改研究 Roadmap 與開發紀錄，未修改程式或資料格式，因此不重跑 Python 測試；上一個程式批次的 124/124 結果維持不變。

## 2026-11-24 — density-v4.6 教師問題與角色回答對齊

### 目的

修正教師詢問「密度是什麼」時，3B 因讀到比較題示例而回答「質量相同時看體積」的情境錯置；同時保留角色、參與狀態與既有單次重試架構。

### 變更

- 教師發言先分類為定義、比較、解釋、應用、迷思檢核、回想或一般動作；`BehaviorPlan` 新增教師動作、回答焦點及不可自行假設條件。
- 五角色仍各保留兩組合成示例，但 Prompt 只注入同題型示例；定義題不再看到「質量相同」比較題。
- 加入 deterministic 情境檢查：拒絕未明示的同質量／同體積條件與定義題改答比較題；沿用最多一次模型重試，仍失敗才使用角色化情境備援。
- 評測觀察台顯示教師動作、回答焦點及不可自行假設，Prompt 升為 `density-v4.6`，evaluator 維持 `2.1`；新增 ADR-012、研究設計／實作計畫及開發 smoke 報告。

### 驗證

- 定向測試：30 項全部通過。
- Mock baseline：5/5；Mock 完整課堂流程成功執行。
- 本機 API：`/api/health` 為 true；原問題選到小宇，保存 `teacher_move=definition`，raw Ollama 回覆「密度就是東西有多重，是質量除以體積的結果？」。
- 3B 開發 smoke：`qwen2.5:3b`、temperature 0.65、同案例 5 次皆為 raw Ollama，未重試／Guard／fallback，也未再答成同質量比較題。完整文字與限制見 `docs/evaluations/2026-11-24-density-v4.6-context-smoke.md`。
- 完整測試首次為 123/124，唯一失敗是測試仍期待舊 Prompt 版本；同步為 v4.6 後重跑，124/124 通過。

### 限制與下一步

- 規則目前只防最明顯的題型錯置，不是通用語意 judge；開發 smoke 仍出現簡繁混用及角色熟練度偏高。
- 參考角色模擬與 persona 對話研究後，下一個低成本改善應是：人工標註「是否直接回答／是否像該角色」、建立新 holdout v2，再評估 context-first 生成或輕量微調；現在不增加第二個 LLM judge 或多 agent。
- 這次沒有重用 holdout v1 調參，也不以 5 筆開發案例宣稱真實度提升。

## 2026-11-24 — density-v4.5 學生表現確認與參與／情緒狀態

### 目的

避免教師一說出正解就直接降低學生迷思，並讓注意、回答意願、挫折、尷尬與信心直接影響學生當輪行為。

### 已完成

- 把學習更新拆成「教師證據暫存 → 學生表現分類 → 提交一級」。學生只說不知道、保留原迷思、否定同材料不變性或回答錯置概念時不更新。
- Guard 改寫與 `ResilientProvider` fallback 即使文字正確也不得確認學習；直接 Mock 只供 deterministic 流程測試。教師事件保存 pending 證據，學生事件保存最終確認、來源資格與前後值。
- 新增 `engagement.py` 與五角色不同初值，以固定有界規則產生 `silent`、`hesitant` 及既有行為；成功／失敗後小幅更新信心、挫折與尷尬。
- 沿用 `concept_state_json.engagement`，沒有新增資料表或欄位；舊 row 缺值時依角色補齊。BehaviorPlan、課堂事件、學生卡與觀測台的新評測規劃均可觀察新狀態。
- Prompt 升為 `density-v4.5`，evaluator 維持 `2.1`；新增 ADR-011、設計／實作計畫並同步架構、Roadmap、測試與專案基線。

### 驗證

- 受影響定向測試：79 項全部通過。
- 完整測試：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`，118 項全部通過；本批次只跑一次完整套件。
- Mock baseline：5/5；Mock 十輪完整課堂：10/10，第 7、8 輪由學生表現確認後才使重量迷思 3→2→1。
- 隔離 API/UI smoke：health 正常、課堂頁 200、觀測頁 200、新課堂 5 位學生均含 engagement；使用 `data/smoke-v45/` 與 8011 埠，完成後已驗證路徑並刪除暫存資料。
- `git diff --check`：通過。
- Git：功能 commit `3baf632` 已於 2026-11-24 推送至 `origin/main`；本紀錄後續以獨立文件 commit 同步。

### 限制與下一步

- 參與／情緒是合成規則狀態，不是心理量測；門檻與變動幅度仍需用人工開發案例檢查。
- 學生表現分類仍是密度單元關鍵關係規則，不能涵蓋所有同義表達。本批次未執行 Ollama，不宣稱真實感已改善。
- 下一步先在觀測台人工比較 v4.5 的 baseline／開發案例，再建立未見的 holdout v2；不得拿 holdout v1 調參。

## 2026-11-23 — density-v4.4 概念狀態與證據對應更新

### 目的

把單一迷思強度擴充成可辨識的密度概念與具名迷思，讓學生只因對應的教師證據與理解檢核逐步改變，而不是遇到一般糾正就突然學會。

### 已完成

- 新增 `learning.py`：五項 0–3 概念熟練度（質量、體積、密度比值、同材料不變性、單位換算）與兩項 0–3 迷思信念（越重越密、切小後密度變小）。
- 為五角色設定不同初始狀態；既有 `misconception_strength` 保留並與該角色主要迷思同步。
- deterministic evidence classifier 只在教師訊息同時含明確概念關係及理解檢核時更新；每概念最多增加一級、命中迷思最多降低一級。一般稱讚、只說答錯、只提名詞與錯置概念均不降低目標迷思。
- `BehaviorPlan`、Prompt、評測報告及觀測台顯示概念／信念狀態；教師與學生事件保存同一份 `learning_update`，可核對命中概念與前後值。
- `student_states` 新增 additive `concept_state_json`。舊 row 依角色與原有 scalar 補預設；未改寫歷史事件、封存評測或 API 既有欄位。Prompt 升為 `density-v4.4`，evaluator 維持 `2.1`。
- 加入設計、實作計畫及 ADR-010，並同步架構、Roadmap、測試與專案基線。

### 驗證

- 定向測試：60 項通過；首次測試發現 Windows 測試 connection 未關閉造成暫存 DB 鎖定，關閉連線後同組全數通過，產品遷移邏輯未失敗。
- 完整測試：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`，106 項全部通過；本批次只跑一次完整套件。
- Mock baseline：5/5；Mock 十輪完整課堂：10/10。第 7、8 輪重量迷思 3→2→1，密度比值熟練度 0→1→2。
- 7B 開發 smoke：`qwen2.5:7b`、temperature 0.65、5 個 baseline 案例各 1 次；硬性規則 5/5、全為 `raw_ollama`、平均 7.7798 秒。單次結果不代表真實度改善。
- 正式本機 DB 遷移前確認無 active 評測工作並建立 `data/classroom-pre-v4-4-20261123-220124.db`；重啟後 health 正常、Ollama 可用、3 個模型、觀測頁 200，schema 已含 `concept_state_json`。備份在 Git ignore 範圍，可用來還原遷移前資料。

### 限制與下一步

- 目前 evidence classifier 是密度單元的明確關係規則，不是完整語意理解或認知診斷。
- 不以本次 5 筆 smoke 宣稱學生更真實；下一步應使用 baseline／人工開發案例做盲評，再建立 holdout v2。
- holdout v1 已使用，只能做既有人工覆核，不得用來調整 evidence 規則。

## 2026-11-23 — density-v4.3 結構化行為規劃與單次重試 MVP

### 目的

降低 deterministic Guard 直接替換固定句子造成的模板感，讓程式控制學生當輪的理解與意圖，但把實際措辭保留給本機模型。

### 已完成

- 新增可序列化 `BehaviorPlan`，記錄行為類型、理解、意圖、信心、情緒提示、迷思、語氣及必要／禁止語意；既有行為標籤 API 保持相容。
- 五位角色各加入兩組合成示例，只作為口吻與推理引導；尚未宣稱為真人學生語料。
- Prompt 升為 `density-v4.3`。第一次 Ollama 回答未通過角色、行為或長度規則時，會附失敗原因重試一次；重試仍失敗才使用既有 deterministic Guard。
- 新增 `retried` 來源分類。`AgentReply`、課堂事件與新評測報告保存 `behavior_plan`、`generation_attempts`、`retry_count`；未修改 SQLite schema，舊報告缺少新欄位時仍可讀。
- 觀測台加入 Retried 篩選、結構化規劃與逐次生成證據，並把易混淆的「Guard 前原始回答」改名為「第一次模型回答（後處理前）」。
- 新增 ADR-009、設計／實作計畫並同步架構、Roadmap、測試手冊與專案基線。

### 驗證

- 定向測試：58 項全部通過。
- 完整測試：`\.venv\Scripts\python.exe -m unittest discover -s tests -v`，95 項全部通過；本批次只跑一次完整套件。
- Mock baseline：5/5；Mock 十輪完整課堂：10/10，final checks 全部通過。
- 7B 開發 smoke：`qwen2.5:7b`、temperature 0.65、5 個 baseline 案例各 1 次；硬性規則 5/5、5 次均為 `raw_ollama`、平均 5.9927 秒。這只證明流程可執行，不代表學生真實度改善。
- 重啟 Tailscale 觀測平台後：health 正常、Ollama 可用、3 個模型、觀測頁 200，Retried 與結構化行為規劃資產已載入；未建立額外 smoke 工作。

### 限制與下一步

- 合成示例仍需人工檢查語氣；目前只驗證單次 7B baseline，不能與 density-v4.2 的 50 次結果直接宣稱品質提升。
- 先用 baseline／人工開發案例檢查自然度與重試行為；holdout v1 只做既有人工覆核，不得用來調整 density-v4.3。
- 調整完成後建立 holdout v2，分開報告 raw、retried、guarded、fallback 與人工判讀。

## 2026-11-23 — 設定輕量 Superpowers 開發流程

### 目的

降低後續開發的規劃、agent 與重複測試成本，同時保留架構決策、資料語意與高風險變更的必要查核。

### 已完成

- 在 `AGENTS.md` 固定後續流程：大型功能前期各使用一次 `brainstorming`／`writing-plans`；確認後由主 agent 直接實作並搭配 `token-efficiency`。
- 開發中只跑定向測試，批次收尾或 commit 前只跑一次完整測試。
- 一般工作不再預設使用 `executing-plans`、subagent、逐 Task reviewer；只有評分報告錯配、資料覆寫／遺失、並行寫入、schema／相容性、安全與研究證據等高風險變更才做針對性 code review。
- 本次只調整專案規範與紀錄，未修改全域 Superpowers plugin 或執行程式碼。

### 驗證

- `git diff --check`：通過。
- 文件規則變更，未執行 Python 測試。

## 2026-11-23 — 評測觀察台 Task 6：文件、隔離 smoke 與正式收尾

### 目的

完成評測觀察台第一版的可重現文件、Mock 驗證、歷史資料人工觀察與資料安全檢查；依使用者要求不執行 Ollama 推論。

### 已完成

- 更新架構、Roadmap、測試手冊與 ADR，記錄背景工作、JSON 儲存、固定 legacy manifest、不可變封存報告與人工覆核 overlay。
- 將評測觀察台／人工標註放在後續 Prompt 調整與 RAG 之前；holdout v1 只供重現與人工覆核。
- `.superpowers/` 與 `data/evaluations/` 已在 Task 1 忽略，`data/.gitkeep` 仍保留；Task 6 驗證現有規則，不建立無意義 `.gitignore` diff。
- 隔離 API smoke 首次在 Windows 並行輪詢時捕捉到 `job.json.tmp -> job.json` 短暫 `PermissionError`；新增最多 5 次、短退避的原子 replace 重試。持續拒絕仍拋錯並由工作記錄失敗。
- 瀏覽器檢查發現完整課堂 legacy summary 仍使用 `passed_turns/turn_pass_rate`，導致共同 UI 顯示 `?/10`；adapter 現在保留原欄位並補上 `total_runs/passed_runs/pass_rate`。
- 新增 2 項 Windows 原子 replace 回歸測試，並擴充完整課堂 adapter 測試的共同摘要契約。
- 最終獨立 code review 找到歷史資料可靠度與人工覆核安全問題：UI 非同步回應可能混用報告、單一損壞檔案可能拖垮歷史清單、壞 job 可能阻止啟動、來源對不上時會隱藏既有回答、並行覆核可能互相覆蓋。已以一次 TDD 修正批次處理。
- UI 現在把選取 token 與覆核目的地綁定；歷史摘要顯示來源、模型、Prompt/evaluator、平均延遲（有保存時）及覆核數；重開 holdout 報告仍顯示不可調參警告。
- Legacy archive 現在逐份隔離損壞、保留來源缺失時的原始回答、序列化 overlay 寫入，且 archive hash 變更或 overlay 損壞時保留舊覆核並禁止覆寫。
- Local job 讀取會驗證 JSON object、目錄 run id、status 與 completed report；壞資料只標成 `corrupt`，不阻止服務啟動。

### 驗證

- 完整測試：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`，89 項全部通過。
- Mock 單輪評測：baseline 5/5，來源均為 mock；Mock 完整課堂：10/10，final checks 全部通過。
- `git diff --check`：通過。
- 隔離 API smoke 使用 `data/evaluations/task6-smoke/`：health 200、觀察台 200、固定 legacy 4 份、建立 Mock 工作 202、完成 5/5、覆核保存／重載 200、課堂建立 201、發言 200、結束 200。隔離目錄驗證路徑後已刪除，無法復原且不影響其他本機資料。
- 瀏覽器 smoke：1440px 雙欄與 390px 單欄成立；新 Mock 5/5；四份 legacy 分別為 7B baseline 38/50、3B baseline 29/50、完整課堂 10/10、holdout v1 29/50；raw Ollama 篩選、舊報告缺失 raw、legacy 覆核完成／重載、holdout 與共用 Ollama 警告均正常；console 0 errors。
- Reviewer 修正後隔離 smoke：health 與觀察台 200、歷史清單 4 份；完整課堂顯示 10/10、7 raw Ollama／2 guarded／1 fallback，holdout 顯示 29/50、37 raw／13 guarded；模型／版本／覆核數與兩種硬性規則說明可見，holdout 警告在表單維持 baseline 時仍可見，console 0 errors。未執行 Ollama 推論。

### 限制與下一步

- 本批次未執行 Ollama，不宣稱模型品質、角色真實度或專家評分效度改善。
- 目前只完成工具與標註流程；下一步由研究者先觀察並標註既有 baseline、holdout 與完整課堂資料，再決定角色規則修改。
- holdout v1 已使用，不得作為後續調參依據；修改後必須建立 holdout v2。
- 本機 `main` 尚未 push；是否推送由使用者決定。

## 2026-11-23 — 評測觀察台 Task 5：單頁研究工作區

### 目的

提供不干擾主要課堂頁面的獨立研究介面，讓研究者從瀏覽器啟動評測、追蹤進度、查看案例證據、篩選結果並保存人工覆核。

### 已完成

- 將 `/evaluations` 暫時頁面改為獨立 responsive 工作區；主課堂頁只新增導覽連結，未改動既有課堂 JavaScript 或 SQLite schema。
- 執行區支援 Mock／Ollama、baseline／holdout、已安裝模型及重複次數；有 active job 時停用第二次啟動。
- 歷史區合併本機工作與四份固定封存報告；只在 selected／new job 為 queued 或 running 時輪詢，頁面離開時停止 timer。
- 案例區支援 source、硬性結果、角色與人工覆核狀態篩選；分開顯示教師問題、marker、Guard 前回答、實際回答及硬性 checks。
- 舊報告缺少 raw text 時顯示「舊報告未保存」；holdout v1 維持已使用警告；硬性規則通過率不描述為語意正確或學生真實度。
- 覆核區依資料提供 delivered／raw_model target，支援保存草稿、完成並前往下一筆；API 錯誤時保留未送出欄位。
- 新增 5 項 UI 契約測試，檢查資產、雙向導覽、原生可及控制、研究警告、responsive layout、API endpoint 接線及 JavaScript 語法。

### 驗證

- Task 5 UI 契約：5 項全部通過；定向 UI／evaluation API／既有 API 回歸：14 項全部通過。
- 完整測試：`\.venv\Scripts\python.exe -m unittest discover -s tests -v`，79 項全部通過。
- `run.ps1` 瀏覽器 smoke：頁面與資產 200；Mock 工作 202 後完成 5/5；角色篩選、草稿保存、完成覆核、legacy holdout 警告與缺失 raw 標示均可見；瀏覽器 console 無 error。
- `git diff --check`：通過；只執行 deterministic Mock 流程，未執行 Ollama 品質評測。

### 尚未完成／下一步

- Task 6 尚未開始：同步架構、測試、Roadmap、決策文件，執行最終 smoke 與整體 code review。
- 目前尚未 push；本機 `main` 保留 Task 3–5 commits，等待使用者決定何時推送。

## 2026-11-23 — 評測觀察台 Task 4：FastAPI 評測端點

### 目的

把背景評測工作與四份固定歷史報告接到獨立 HTTP API，讓下一階段觀察介面能啟動、輪詢、查看及人工覆核評測，同時維持課堂 API 與 SQLite schema 不變。

### 已完成

- 新增 `GET /evaluations` 與暫時頁面入口；目前只顯示 API 已就緒，完整 HTML／CSS／JavaScript 工作區留在 Task 5。
- 新增建立、列表、明細與逐筆覆核端點；新工作與 legacy 報告使用共同 detail wrapper，歷史列表不回傳完整 `results`。
- Mock 與 Ollama 都沿用既有 `evaluate_provider()`；Ollama 必須明確選擇本機已安裝模型，單筆 RuntimeError 仍保存為 `error`，不自動改用 Mock。
- 同時間只接受一個評測工作；第二個工作回傳 409。無效 provider／suite／repeats／model／review 回傳 422，缺少 run 或結果回傳 404，損壞資料回傳不含本機路徑的可解釋錯誤。
- 人工覆核 API 支援 delivered／raw_model target、草稿及完成狀態；legacy 覆核仍寫入 overlay，不改動封存報告。
- 新增 6 項 API 測試，涵蓋 Mock 完整流程、四份歷史報告、模型驗證、併發限制、草稿／完成覆核、安全 id、損壞資料與 provider error evidence。

### 驗證

- API／service 定向回歸：24 項全部通過。
- 完整測試：`\.venv\Scripts\python.exe -m unittest discover -s tests -v`，74 項全部通過。
- `run.ps1` HTTP smoke：`/api/health` 200、歷史 4 份、Mock 建立 202、評測完成 5/5、`/evaluations` 200；服務已正常停止。
- `git diff --check`：通過；未執行 Ollama 品質評測，本批次不宣稱角色真實度或模型成功率改善。

### 尚未完成／下一步

- Task 5 尚未開始：建立正式觀察台工作區、篩選、逐筆證據檢視、輪詢與覆核操作介面。
- Task 6 尚未開始：架構／測試／Roadmap／決策文件整理與最終 smoke/review。

## 2026-11-22 — 評測觀察台 Task 3：歷史報告與覆核 overlay

### 目的

讓後續觀察台只讀取四份仍具研究與比較價值的歷史報告，將不同舊格式正規化，同時允許人工覆核但不改寫已封存的研究證據。

### 已完成

- 新增固定 manifest，只納入 3B／7B density-v4.2 baseline、holdout v1 與最新 density-v4.2 十輪完整課堂。
- 新增版本鎖定情境 catalog；依實際封存資料明確綁定 baseline evaluator 2.1 與 holdout evaluator 2.0，避免未來程式常數變更後錯配舊報告。
- 新增 `LegacyEvaluationArchive`，以兩個明確 adapter 正規化單輪與完整課堂格式，不掃描或匯入任意 JSON。
- 驗證 manifest 路徑不可離開 `docs/evaluations/`，並以 SHA-256 綁定封存檔與人工覆核 overlay。
- 人工覆核只寫入 `data/evaluations/legacy-reviews/`；原始封存 JSON 維持唯讀。來源 hash 改變時不套用舊覆核，並標示 stale。
- 舊 guarded 報告沒有保存 raw text 時明確標為 unavailable，不使用 final response 猜測原始回答。

### 驗證

- Task 3 專屬測試：9 項全部通過，涵蓋固定清單、兩種 adapter、版本／scenario provenance、路徑限制、缺檔／壞 JSON、唯讀 archive、overlay 重載、hash 錯配及無效 review target。
- 完整測試：`\.venv\Scripts\python.exe -m unittest discover -s tests -v`，68 項全部通過。
- `git diff --check`：通過。
- 未執行 Ollama 品質評測；本批次不改變或宣稱模型角色表現。

### 尚未完成／下一步

- 尚未建立 FastAPI 評測端點與實際觀察台頁面，因此功能目前仍是後端資料層。
- 下次依實作計畫從 Task 4 繼續；Task 4–6 尚未開始。

## 2026-11-22 — 評測觀察台第一批次（Task 1–2）

### 目的

先建立評測觀察台的資料基礎與背景工作層，讓後續 API／UI 能讀到可解釋的原始回答、Guard 後回答、執行進度與人工覆核，而不修改既有課堂 SQLite schema 或把評測邏輯塞進 `ClassroomService`。

### 已完成

- 新增正式設計與實作計畫，選定本機單一背景 worker、原子 JSON、四份重要歷史報告及獨立人工覆核 overlay 的後續架構。
- `AgentReply` 新增 `raw_response`；Ollama 在角色、行為及長度 Guard 前保存正規化文字，Mock 保存相同的 raw／final 回答。
- 評測報告升為 schema `2.0`，每筆內嵌教師問題、迷思強度、預期／禁用 marker、raw／final 回答及 target-aware `human_review`。
- `evaluate_provider()` 新增逐筆進度 callback；RuntimeError 仍記為 `error`，不以 Mock fallback 墊高單輪評測結果。
- 新增 `evaluation_jobs.py`：同時只執行一個背景評測、保存 queued／running／completed／failed／interrupted、原子寫入 `job.json`／`report.json`、隔離損壞工作、重啟後中斷復原及安全 run id。
- 人工覆核支援 delivered／raw_model 分開保存、草稿與完成狀態、yes／no／uncertain 驗證、完成數重新計算及重載持久化；不改動 hard pass 結果。
- `.superpowers/` 與 `data/evaluations/` 加入 `.gitignore`，避免暫存 ledger、背景工作與人工覆核資料誤入版本控制。

### 驗證

- 開發前基線：43 項自動測試全部通過。
- Task 1：先確認 raw response 與 report v2 測試失敗，再完成實作；相關 21 項回歸通過。
- Task 2：先確認背景模組不存在與 `update_review()` 不存在的 RED 結果，再完成實作。
- 完整測試：`\.venv\Scripts\python.exe -m unittest discover -s tests -v`，59 項全部通過。
- 未執行 Ollama 品質評測，因此本批次不宣稱角色真實度或模型成功率改善。

### 尚未完成／下一步

- 依使用者要求在 Task 2 後暫停；尚未建立歷史報告 adapter、FastAPI 評測端點與單頁觀察台，因此目前還不能從網頁啟動或查看評測。
- 下次從實作計畫 Task 3 繼續：四份固定歷史報告、版本鎖定情境目錄與唯讀 review overlay。
- Task 4–6 仍包含 API、獨立 evaluation HTML／JS／CSS、瀏覽器 smoke、完整架構／ADR／Roadmap 文件與最終 review。

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

## 2026-11-10 — 逐輪模型選擇與 3B／7B 比較

### 目的

檢驗模型能力是否是角色效果不佳的來源，讓測試介面可直接切換本機已安裝模型，並以相同設定比較 3B 與 7B。

### 變更

- 新增 `GET /api/models`；網頁模型選單顯示 Ollama 本機模型、參數量與大小。
- 教師每輪訊息可選填 `model`，服務驗證模型確實已安裝；不修改 session 或資料庫 schema。
- 學生事件保存模型名稱；即使 Ollama 失敗使用 fallback，也保留原本要求的模型。
- Evaluation 2.1 新增 `--model`、逐輪與彙總延遲、單輪 RuntimeError 紀錄；壞 JSON 不再中止並遺失整批結果。
- 完整課堂 CLI 同樣新增 `--model`。

### 驗證

- 自動測試：43 項全部通過。
- Mock baseline：5/5；mock 完整課堂：10/10。
- 瀏覽器：模型選單正確列出 `llama3.2:1b`、`qwen2.5:3b`、`qwen2.5:7b`；同一堂課先用 7B、再用 3B，兩輪逐字稿均顯示正確模型與 `ollama` provider。
- 3B baseline 50 次：29/50（58%），36 raw、14 guarded、0 error；平均 2.5752 秒。
- 7B baseline 50 次：38/50（76%），45 raw、5 guarded、0 error；平均 5.1554 秒。
- 完整比較與案例見 `docs/evaluations/2026-11-10-qwen2.5-3b-vs-7b.md`。

### 判讀與未解問題

- 7B 的增益主要來自害羞角色（3/10→10/10）；迷思角色反而 5/10→4/10，不能只看總分。
- evaluator marker 仍會漏判同義句／簡繁差異，硬性 76% 不等於學生真實度。
- 預設仍保留 3B；品質評測建議選 7B。是否正式更換研究主模型，待人工量尺與新 holdout v2 後決定。
