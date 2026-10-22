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
