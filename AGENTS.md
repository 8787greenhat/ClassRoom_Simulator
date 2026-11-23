# ClassRoom Simulator 開發規範

## 專案目標

本專題以國中自然科「密度」為第一個受控單元，模擬五位具有不同程度、個性、參與方式與常見迷思的學生 Agent，供師培生練習班級教學。現階段先驗證 Prompt 與角色狀態；RAG、同儕互動及教學評價依 `docs/ROADMAP.md` 分階段加入。

原始 proposal 的持久化摘要與目前取捨記錄在 `docs/PROJECT_CONTEXT.md` 的「Proposal 對齊基準」。若新功能與該基準衝突，先提出差異與影響，不可只依對話記憶自行改變研究方向。

## 目前開發基線（2026-11-23）

- 不在本檔固定 Git commit；每次開始以實際 `git status --short --branch`、`git log -1` 與最新 `docs/DEVELOPMENT_LOG.md` 為準。
- 目前 Prompt 版本為 `density-v4.5`、evaluator 為 `2.1`，預設模型仍為 Ollama `qwen2.5:3b`；網頁可逐輪選擇本機已安裝模型，事件會記錄實際模型。空回應、JSON placeholder 等無效輸出會交由 `ResilientProvider` 使用 deterministic mock fallback。
- density-v4.5 將教師證據與學生表現分成兩階段：教師說明只暫存，學生成功用自己的話表達對應關係後才逐項更新一級；Guard 與 fallback 代寫不得確認學習。每位學生另有五項 0–1 參與／情緒狀態，會直接影響沉默、猶豫及回答行為。
- 五位學生已有獨立 session 狀態；密度概念與迷思信念均為 0–3。舊 `misconception_strength` 保留為主要迷思的相容鏡像，每次只有對應證據加理解檢核才可變動一級。
- 分心角色已有 `distracted`、`off_topic`、`imaginative`、`redirected` 等受控行為；這是國中生課堂干擾模型，不代表已完成小學生年齡或語言模型。
- `classroom_scenario.py` 提供固定 10 輪完整課堂。2026-11-10 density-v4.2 歷史回歸為硬性 10/10，其中 7 輪 raw Ollama、2 輪 guarded、1 輪 fallback；人工檢查仍發現回答不完整與角色漂移。2026-11-23 density-v4.3 只完成 7B baseline 5 案例 smoke（5/5、全為 raw），不可當成真實度改善證據。
- 自動測試基線為 118 項全數通過。holdout v1 共 50 次，硬性規則 29/50；37 次 raw Ollama、13 次 guarded。完整報告見 `docs/evaluations/2026-11-10-density-holdout-v1.md`。
- 自動分數不是學生真實度或模型原生成功率。任何報告都必須分開列出 raw Ollama、guarded 與 fallback，並保留 `human_review`；已使用的 holdout 不得再用於調參後宣稱改善。
- 2026-11-10 baseline A/B 各 50 次：3B 29/50（58%，平均 2.58 秒，14 guarded），7B 38/50（76%，平均 5.16 秒，5 guarded）；兩者均無 error。這是 evaluator 2.1 硬性規則結果，不是人工真實度。正式比較見 `docs/evaluations/2026-11-10-qwen2.5-3b-vs-7b.md`。

## 已知限制與下一步順序

1. 先完成 holdout v1 人工標註，並以 baseline／開發案例改善主動、迷思及害羞角色；不可拿 holdout v1 反覆調整。
2. 修改後建立新的 holdout v2 驗證泛化，且人工判讀與 marker 硬性分數分開報告。
3. RAG 為下一個主要階段，但開始建置前必須由使用者確認一份具授權、版本固定的密度教材。教材、教案、作業／解答與迷思案例須分層，避免學生 Agent 直接讀到教師解答。
4. RAG 第一版只做密度單元的小型 Prompt-only 對照實驗，必須記錄檢索片段、來源、越界率、回答正確性、角色真實度及延遲。
5. 個別角色真實度穩定後，才加入學生彼此附和、反駁、插話與受同學影響；目前同儕互動尚未完成。
6. 專家評分統計及真人資料仍須依下方決策門檻取得使用者確認，不提前實作或宣稱完成。

## 每次開始工作前

1. 閱讀本檔及 `docs/PROJECT_CONTEXT.md`。
2. 閱讀 `docs/DECISIONS.md`、`docs/ROADMAP.md` 與最近一筆 `docs/DEVELOPMENT_LOG.md`。
3. 執行 `git status --short --branch`，保留使用者既有修改。
4. 先確認本次驗收條件，再改程式。

## 輕量 Superpowers 開發流程

除非使用者明確要求其他流程，後續開發採以下方式，避免重複規劃、重複驗證及不必要的 agent 成本：

1. **前期設計**：新功能、架構或資料意義變更，只在開始時各使用一次 `brainstorming` 與 `writing-plans`，定義範圍、架構、資料意義、風險及驗收條件。設計確認後不重跑；只有需求或範圍實質改變才重新討論。需求明確的小修、文件或單純維護可直接處理。
2. **開發實作**：由主 agent 依已確認計畫直接實作，搭配 `token-efficiency`，只讀取目前工作需要的檔案與輸出。預設不使用 `executing-plans`、`subagent-driven-development`、逐 Task reviewer 或其他多 agent 流程；只有使用者明確要求時才啟用。
3. **分段驗證**：開發中先跑受影響的定向測試；一個開發批次收尾或 commit 前，只跑一次完整測試。仍須依下方「必做驗證」補跑與變更類型直接相關的評測或 smoke test。
4. **高風險審查**：只有評分／報告對應錯誤、資料互相覆蓋或遺失、並行寫入、資料庫 schema、API 不相容、安全／個資、研究證據不可逆變更等風險，才使用針對性 code review。一般 UI、文件及低風險小修不啟動 reviewer。
5. **完成與紀錄**：驗證結果、限制及下一步照常寫入 `docs/DEVELOPMENT_LOG.md`。不因流程工具產生額外重複報告；以專案文件、測試結果及 Git 狀態為準。

## 架構與邊界

- `classroom_simulator/main.py`：HTTP API 與靜態頁面入口；不要放核心規則。
- `classroom_simulator/service.py`：課堂流程與學生選擇規則。
- `classroom_simulator/llm.py`：模型供應者、Prompt 與角色一致性防護。
- `classroom_simulator/db.py`：SQLite 持久化；資料表變更視為重大決策。
- `classroom_simulator/roles.py`：固定學生角色的唯一來源。
- `classroom_simulator/behavior.py`：受控行為規劃與輸出一致性 guard。
- `classroom_simulator/evaluation.py`：可重複的角色行為評測。
- `classroom_simulator/classroom_scenario.py`：完整課堂情境、逐輪硬性檢查與紀錄匯出。
- `tests/`：不依賴 Ollama 或網路的自動測試。

詳細呼叫關係見 `docs/ARCHITECTURE.md`。

## 必做驗證

- 程式修改期間先跑受影響的定向測試；開發批次收尾或 commit 前執行一次完整測試：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- API 或 UI 修改後，額外啟動 `.\run.ps1`，檢查 `/api/health` 與受影響流程。
- Prompt 或角色規則修改後，額外執行：`.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock`
- 跨輪狀態、選角、迷思或 fallback 修改後，額外執行：`.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario --provider mock`
- 若使用 Ollama 做人工/模型評測，必須記錄模型名稱、參數、執行次數與結果；不得用單次輸出宣稱有效。

## 紀錄與 Git

- 每個完成的開發批次都在 `docs/DEVELOPMENT_LOG.md` 新增日期、目的、變更、驗證結果及未解問題。
- 會影響研究設計或後續相容性的選擇寫入 `docs/DECISIONS.md`。
- 大修正通過測試後才 commit；commit 訊息說明成果，不寫模糊的「update」。
- Push 前確認沒有 `.env`、資料庫、逐字稿、金鑰或個資被追蹤。
- 不重寫或刪除使用者既有 Git 歷史。

## 必須先由使用者決定的事項

下列事項只先整理選項與建議，不自行決定：

- 擴大或更換課程單元。
- RAG 教材來源、授權與版本，以及是否允許上傳教材。
- 更換主要模型、引入付費 API，或把資料送到外部服務。
- 新增蒐集個資、錄音、研究受試者資料或雲端儲存。
- 改變專家評分量尺、統計驗證方法或研究問題。
- 不相容的 API、資料庫 schema 或角色定義變更。
- GitHub 可見性、部署上線或對外發布。

## 安全與資料

- 預設只使用合成資料；不要提交真實學生姓名、錄音、逐字稿或評分資料。
- 密鑰僅由環境變數提供，禁止寫入原始碼與文件範例值。
- `data/*.db` 必須維持在 `.gitignore`。
