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

目前預設模型是 `qwen2.5:3b`。可用 `--model qwen2.5:7b` 指定另一個已安裝模型；網頁也可逐輪切換。

## 2 自動回歸測試

不需要啟動 Ollama：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

目前基線為 106 項全部通過。此層檢查選角、獨立記憶、具名概念／迷思狀態、舊 SQLite 遷移、證據對應更新、結構化行為規劃、單次重試、生成證據、分心行為、guard、回答長度、模型 API／metadata、單輪模型錯誤容錯、背景工作、Windows 原子寫入重試、損壞 job/report 隔離、歷史報告 adapter 與來源缺失、並行人工覆核、UI 非同步選取安全、UI 契約、PowerShell 啟動相容性、評測輸出與完整課堂流程。

## 3 Mock 評測

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock --suite baseline
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock --suite holdout
.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario --provider mock
```

預期 baseline 5/5、holdout 5/5、完整課堂 10/10。這只驗證測試工具與 deterministic mock，不代表 Ollama 或學生真實度。

## 4 評測觀察台與歷史資料

不需要 Ollama 即可觀察四份既有報告：

```powershell
.\run.ps1
```

開啟 <http://127.0.0.1:8000/evaluations>，確認：

1. 歷史清單固定包含 3B baseline、7B baseline、holdout v1 與最新完整課堂。
2. 每筆案例分開顯示教師問題、來源分類、硬性 checks、第一次模型回答、結構化行為規劃、生成嘗試及實際回答。
3. 舊報告沒有保存 raw text 時顯示「舊報告未保存」，不可用 final response 補猜。
4. 可依來源、硬性結果、角色及覆核狀態篩選。
5. delivered 覆核可保存草稿；三個判讀欄位完整後才可標記完成。
6. retried 或 guarded 且保存 raw text 的新結果顯示 raw_model target。
7. holdout v1 顯示已使用警告；不得用它反覆調參後宣稱改善。

本機新工作與覆核寫入 `data/evaluations/`，已由 Git 忽略。四份 `docs/evaluations/` 封存報告不會被介面直接改寫。

## 5 Ollama 未見案例評測

每個 holdout 案例至少重複 10 次並保存原始資料：

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation `
  --provider ollama `
  --model qwen2.5:7b `
  --suite holdout `
  --repeats 10 `
  --output docs\evaluations\results\ollama-density-holdout-current.json
```

檢查 JSON 中的：

- `pass_rate`：只代表長度、角色 marker 與安全字詞等硬性規則。
- `source_usage`：分開列出 `raw_ollama`、`retried`、`guarded`、`fallback` 與 `mock`。
- `behavior_plan`／`generation_attempts`／`retry_count`：核對幕後規劃、第一次與重試回答及各次失敗原因。
- `concept_mastery`／`misconception_beliefs`：確認每項狀態介於 0–3，且與角色及當輪證據一致。
- `human_review`：逐筆填寫是否直接回答、角色是否一致、是否像真實學生及備註。
- `scenario_summaries`：不要只看總分，必須逐角色查看。
- `latency_seconds`：平均、中位與最大生成時間。
- `error`／`source_usage.error`：模型單輪失敗會留下錯誤並繼續整批評測，不會遺失其他結果。

同一個 holdout suite 使用後即成為已見資料，不可依其結果修改 Prompt 後再用同一套案例宣稱泛化改善。後續修改須建立新的 holdout 版本。

## 6 完整課堂回歸

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario `
  --provider ollama `
  --model qwen2.5:7b `
  --output docs\evaluations\results\full-classroom-density-current.json
```

至少檢查：

1. 五位角色都有參與且點名正確。
2. 迷思強度依 3→2→1 漸進，不是一次清零。
3. 第 7、8 輪的 `density_ratio` 依 0→1→2 漸進；一般稱讚或錯置概念不降低「越重越密」信念。
4. 分心學生可被具體問題拉回。
5. 每輪不超過 45 字，沒有 placeholder 或 AI 身分揭露。
6. `source_usage` 分開呈現原生、重試成功、guard 與 fallback。
7. 人工逐輪判斷回答是否真正回應教師問題及符合角色。

## 7 API 與瀏覽器人工測試

```powershell
.\run.ps1
```

開啟 <http://127.0.0.1:8000>，依序確認：

1. `/api/health` 可正常回應。
2. 模型下拉選單列出 Ollama 已安裝模型及參數量／大小。
3. 可建立密度課堂並看到五位學生。
4. 同一堂課分別選 3B、7B 各送一輪，逐字稿顯示正確模型名稱。
5. 點名小哲時由迷思角色回答，簡單稱讚不會清除迷思。
6. 對小宇先用泛問測分心，再用具體密度問題將其拉回。
7. 逐字稿顯示行為標籤、provider 與系統修正。
8. 結束課堂後不能再新增教師發言。

評測觀察台 smoke 另確認：桌面與窄版 layout、Mock 工作建立與完成、四份 legacy 報告、案例篩選、缺失 raw 標示、delivered review 保存／重載，以及 holdout／共用 Ollama 警告。

## 8 成果判定

一個版本只有在以下項目都留下紀錄後才算完成：

- 106 項自動測試通過。
- mock baseline、mock holdout 與 mock 完整課堂通過。
- Ollama 記錄模型、Prompt、evaluator、suite、重複次數與完整原始回答。
- raw Ollama、guarded、fallback 分開統計。
- 人工覆核與自動分數分開呈現。
- 不用已看過的 holdout 反覆調參後宣稱改善。
