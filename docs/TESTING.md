# 專案測試手冊

本手冊將測試分成程式回歸、固定角色情境、未見案例、完整課堂及瀏覽器人工測試。mock 結果只證明流程可重現；Ollama 結果才反映目前模型表現，但仍必須人工覆核。

## 1 環境準備

```powershell
cd F:\coding\ClassRoom_Simulator
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

要測本地模型時，確認 Ollama 已啟動且模型存在：

```powershell
ollama list
```

目前預設模型是 `qwen2.5:3b`。

## 2 自動回歸測試

不需要啟動 Ollama：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

目前基線為 36 項全部通過。此層檢查選角、獨立記憶、迷思狀態、分心行為、guard、回答長度、評測輸出與完整課堂流程。

## 3 Mock 評測

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock --suite baseline
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock --suite holdout
.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario --provider mock
```

預期 baseline 5/5、holdout 5/5、完整課堂 10/10。這只驗證測試工具與 deterministic mock，不代表 Ollama 或學生真實度。

## 4 Ollama 未見案例評測

每個 holdout 案例至少重複 10 次並保存原始資料：

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation `
  --provider ollama `
  --suite holdout `
  --repeats 10 `
  --output docs\evaluations\results\ollama-density-holdout-current.json
```

檢查 JSON 中的：

- `pass_rate`：只代表長度、角色 marker 與安全字詞等硬性規則。
- `source_usage`：分開列出 `raw_ollama`、`guarded` 與 `mock`。
- `human_review`：逐筆填寫是否直接回答、角色是否一致、是否像真實學生及備註。
- `scenario_summaries`：不要只看總分，必須逐角色查看。

同一個 holdout suite 使用後即成為已見資料，不可依其結果修改 Prompt 後再用同一套案例宣稱泛化改善。後續修改須建立新的 holdout 版本。

## 5 完整課堂回歸

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario `
  --provider ollama `
  --output docs\evaluations\results\full-classroom-density-current.json
```

至少檢查：

1. 五位角色都有參與且點名正確。
2. 迷思強度依 3→2→1 漸進，不是一次清零。
3. 分心學生可被具體問題拉回。
4. 每輪不超過 45 字，沒有 placeholder 或 AI 身分揭露。
5. `source_usage` 分開呈現原生、guard 與 fallback。
6. 人工逐輪判斷回答是否真正回應教師問題及符合角色。

## 6 API 與瀏覽器人工測試

```powershell
.\run.ps1
```

開啟 <http://127.0.0.1:8000>，依序確認：

1. `/api/health` 可正常回應。
2. 可建立密度課堂並看到五位學生。
3. 點名小哲時由迷思角色回答，簡單稱讚不會清除迷思。
4. 對小宇先用泛問測分心，再用具體密度問題將其拉回。
5. 逐字稿顯示行為標籤、模型來源與系統修正。
6. 結束課堂後不能再新增教師發言。

## 7 成果判定

一個版本只有在以下項目都留下紀錄後才算完成：

- 36 項自動測試通過。
- mock baseline、mock holdout 與 mock 完整課堂通過。
- Ollama 記錄模型、Prompt、evaluator、suite、重複次數與完整原始回答。
- raw Ollama、guarded、fallback 分開統計。
- 人工覆核與自動分數分開呈現。
- 不用已看過的 holdout 反覆調參後宣稱改善。
