# 密度概念狀態與證據更新設計

## 目的

把單一迷思強度擴充成可觀察的密度概念熟練度與具名迷思信念，讓學生只在教師提供對應概念證據並檢核理解時漸進改變，避免因一般糾正或無關解釋突然變懂。

## 狀態

- 概念熟練度 0–3：`mass`、`volume`、`density_ratio`、`material_invariance`、`unit_conversion`。
- 迷思信念 0–3：`heavier_means_denser`、`smaller_piece_less_dense`。
- 五位角色使用不同初始狀態；既有 `misconception_strength` 保留，並與該角色主要迷思信念同步。
- 使用 `student_states.concept_state_json` 保存 `mastery` 與 `beliefs`。既有資料庫啟動時只新增帶 `{}` 預設值的 JSON 欄位；讀取舊資料時依角色補預設，下一次保存寫回完整狀態。

## 更新規則

教師訊息先被 deterministic evidence classifier 分析。只有同時具備「明確概念關係證據」與「要求學生解釋、舉例或確認理解」時：

- 對應概念熟練度最多增加一級。
- 被直接處理的迷思信念最多降低一級。
- 一般稱讚、只說答錯、只提名詞或處理另一個迷思都不降低目前信念。

每輪保存命中的概念、是否有理解檢核、熟練度／信念前後值，供觀測與研究稽核。

## 生成整合

`BehaviorPlan` 加入完整 `concept_mastery` 與 `misconception_beliefs`，並以較弱概念生成理解摘要。Prompt 版本升為 `density-v4.4`；Guard、重試與 evaluator 2.1 不改。

## 不做

- 不使用 holdout v1 調整證據詞或宣稱泛化改善。
- 不加入 RAG、情緒狀態或真人學生資料。
- 不讓 LLM 自己決定狀態更新，避免無法重現。

## 驗收

- 新舊 SQLite 資料都可讀寫，舊 API 欄位保持可用。
- 一般／錯置回饋不降低目標迷思；針對性證據加理解檢核才逐次更新。
- `BehaviorPlan`、課堂 snapshot 與事件 metadata 可觀察概念與信念狀態。
- Mock baseline、十輪課堂與完整測試通過；完整測試只跑一次。
