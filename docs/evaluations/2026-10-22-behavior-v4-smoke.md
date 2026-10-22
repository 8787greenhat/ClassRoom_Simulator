# Density v4 — 受控行為 smoke test

## 設定

- 模型：`qwen2.5:3b`
- Prompt：`density-v4`
- 角色：分心學生小宇
- 日期：2026-10-22
- 每個行為一個開發 smoke 情境，不作研究結論。

## 結果

| 預期行為 | 最終回答 | 模型原生 | Guard 原因 |
|---|---|---:|---|
| `distracted` | 老師，我剛剛有點沒跟上，可以再說一次問題嗎？ | 否 | `role_consistency` |
| `imaginative` | 如果把一顆星球壓成彈珠那麼小，它的密度會不會超大？ | 否 | `behavior_consistency` |
| `off_topic` | 老師，我剛剛在想午餐的布丁，前面那題沒有聽到。 | 否 | `behavior_consistency` |
| `redirected` | 質量相同時比較密度要看體積，體積小的密度大。 | 是 | — |

## 判讀

完整系統輸出 4/4 符合預期行為，但 raw Ollama 只有 1/4。本結果支持「行為控制與標記功能可運作」，不支持「模型能自然穩定模擬分心學生」。正式評測必須分開報告 raw 與 guarded 成績。
