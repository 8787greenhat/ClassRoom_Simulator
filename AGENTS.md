# ClassRoom Simulator 開發規範

## 專案目標

本專題以國中自然科「密度」為第一個受控單元，模擬五位具有不同程度、個性、參與方式與常見迷思的學生 Agent，供師培生練習班級教學。現階段先驗證 Prompt 與角色狀態；RAG、同儕互動及教學評價依 `docs/ROADMAP.md` 分階段加入。

## 每次開始工作前

1. 閱讀本檔及 `docs/PROJECT_CONTEXT.md`。
2. 閱讀 `docs/DECISIONS.md`、`docs/ROADMAP.md` 與最近一筆 `docs/DEVELOPMENT_LOG.md`。
3. 執行 `git status --short --branch`，保留使用者既有修改。
4. 先確認本次驗收條件，再改程式。

## 架構與邊界

- `classroom_simulator/main.py`：HTTP API 與靜態頁面入口；不要放核心規則。
- `classroom_simulator/service.py`：課堂流程與學生選擇規則。
- `classroom_simulator/llm.py`：模型供應者、Prompt 與角色一致性防護。
- `classroom_simulator/db.py`：SQLite 持久化；資料表變更視為重大決策。
- `classroom_simulator/roles.py`：固定學生角色的唯一來源。
- `classroom_simulator/evaluation.py`：可重複的角色行為評測。
- `tests/`：不依賴 Ollama 或網路的自動測試。

詳細呼叫關係見 `docs/ARCHITECTURE.md`。

## 必做驗證

- 每次程式修改後執行：`\.venv\Scripts\python.exe -m unittest discover -v`
- API 或 UI 修改後，額外啟動 `\.\run.ps1`，檢查 `/api/health` 與受影響流程。
- Prompt 或角色規則修改後，額外執行：`\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock`
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
