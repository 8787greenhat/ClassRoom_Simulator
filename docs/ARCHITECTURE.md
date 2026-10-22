# 系統架構與呼叫流程

## 元件

| 檔案 | 責任 | 主要呼叫對象 |
|---|---|---|
| `static/index.html`、`app.js` | 教師操作與畫面更新 | FastAPI JSON API |
| `main.py` | 請求驗證、HTTP 狀態碼、組裝服務 | `ClassroomService` |
| `service.py` | 建立課堂、選角、迷思更新、事件流程 | `Database`、`LLMProvider`、角色表 |
| `roles.py` | 五位學生的固定設定 | `StudentProfile` |
| `behavior.py` | 規劃本輪可觀察行為並檢查輸出與標籤一致 | `StudentProfile`、`StudentState` |
| `llm.py` | Ollama/Mock 回應、fallback、角色防護 | Ollama HTTP API |
| `db.py` | Session、學生狀態、逐字稿儲存 | SQLite |
| `evaluation.py` | 固定情境評測與 JSON 結果 | 角色表、LLM providers |
| `classroom_scenario.py` | 十輪完整課堂、跨輪狀態檢查與逐字稿匯出 | `ClassroomService`、LLM providers |

## 一次教師發言的呼叫鏈

```text
瀏覽器 app.js
  -> POST /api/sessions/{id}/messages
  -> main.send_message()
  -> ClassroomService.send_teacher_message()
       -> Database 讀取 session 與五位學生狀態
       -> _choose_student() 選擇回應者
       -> Database 寫入教師事件
       -> _update_misconception() 最多降低一級迷思
       -> ResilientProvider.reply()
            -> plan_student_behavior() 規劃投入、分心、離題、想像或被拉回
            -> OllamaProvider.reply()
            -> 失敗時 MockProvider.reply()
            -> enforce_role_consistency() / enforce_behavior_consistency()
       -> Database 保存該學生記憶與學生事件
       -> snapshot() 回傳完整課堂狀態
  -> app.js 重新渲染學生卡與逐字稿
```

## 狀態規則

- `StudentProfile` 是不可變角色設定：personality、ability level、misconception、participation level、speaking style。
- `StudentState` 是每個 session 獨立的可變狀態：迷思強度、參與次數、最後發言輪次、短期記憶。
- 記憶寫回 SQLite 時只保留最近 8 筆；送入模型時使用最近 6 筆。
- 每輪教師與學生事件共用同一個 `turn_number`。
- 學生事件 metadata 記錄 `behavior_type`、`guarded` 與 `guard_reason`，因此可分開分析模型原生回答和系統修正後回答。

## 測試分層

- 單元/服務測試：使用暫存 SQLite 與 `MockProvider`，快速且可重複。
- 行為評測：用固定情境計算角色一致性指標；mock 是 CI 基線，Ollama 是實驗資料。
- API smoke test：伺服器啟動後檢查 health、建立 session、發言、結束課堂。
- UI 人工測試：確認角色卡、狀態變化、逐字稿與錯誤訊息。

模型輸出具有隨機性，因此 Ollama 評測不得取代 deterministic unit tests。
