# ClassRoom Simulator 第一版

這是 proposal 的文字版最小可行產品。教師在瀏覽器輸入教學內容，Session Manager 每輪選擇一位學生回應，並把逐字稿、角色狀態與時間寫入 SQLite。

## 已完成

- 五位預設學生角色：主動、一般、迷思、害羞、分心
- 每位學生獨立的 personality、ability level、misconception、participation level 與 memory
- 點名優先、參與次數平衡的發言選擇
- 迷思強度 0 至 3；簡單稱讚不會讓迷思立即消失
- Ollama `qwen2.5:3b` 串接
- Ollama 未啟動時自動切換為可預測的模擬回應
- SQLite 保存課堂、學生狀態及逐字稿
- 單頁網頁介面與核心流程測試
- 可重複的五角色一致性評測工具

## 安裝

需要 Python 3.10 以上。

```powershell
cd F:\coding\ClassRoom_Simulator
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

若要使用本地模型，先安裝並啟動 Ollama，再下載模型：

```powershell
ollama pull qwen2.5:3b
```

未安裝 Ollama 也可以執行，畫面會顯示「模擬回應模式」。

## 執行

```powershell
.\run.ps1
```

開啟 <http://127.0.0.1:8000>。API 文件在 <http://127.0.0.1:8000/docs>。

## 測試

核心測試不需要啟動 Ollama：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

執行固定角色情境評測：

```powershell
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider ollama --repeats 10
```

mock 用來確認評測流程可重複；Ollama 結果才用來觀察模型角色表現。研究結論不應建立在單次輸出上。

專案架構、路線圖與重大決策分別記錄在 `docs/ARCHITECTURE.md`、`docs/ROADMAP.md` 與 `docs/DECISIONS.md`。每次開發前先閱讀 `AGENTS.md`。

## 第一輪測試腳本

1. 建立新課堂。
2. 輸入：「密度是什麼？有人可以說說看嗎？」
3. 輸入：「小哲，物體越重，密度就一定越大嗎？」
4. 輸入：「密度是質量除以體積，所以不能只看質量。你用一個例子再說一次，對不對？」
5. 確認小哲的迷思強度只下降一級，而不是立刻清零。

## 後續範圍

- 重複執行 Ollama 角色評測並比較 Prompt 版本
- 確認教材來源與授權後，將密度單元教材切片並加入 RAG
- 讓學生在受控條件下回應同儕
- 教學評價量尺、證據引用與報告頁面
- Web Speech API 語音輸入

