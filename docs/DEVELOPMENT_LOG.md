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
