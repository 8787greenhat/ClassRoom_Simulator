# 情境對題角色回答設計

## 問題與目標

實際課堂中，教師問「密度是什麼」，分心角色卻回答「質量相同時看體積」。回答在物理條件下可能成立，但答的是另一個題型，且明顯受固定示例帶動。v4.6 的目標是先對準教師當下的語用任務，再套用角色、能力、迷思與情緒；不能只做到「提到密度且像某角色」。

## 研究依據

- [RoleLLM](https://aclanthology.org/2024.findings-acl.878/) 將角色設定、情境式指令與口吻模仿分開；顯示角色能力需要情境條件化資料，而非只有一段 persona。
- [SimsChat](https://aclanthology.org/2025.findings-emnlp.1100/) 的消融結果指出預先定義的角色面向與 scene construction 對角色一致性有顯著貢獻。
- [Post Persona Alignment](https://aclanthology.org/2025.findings-emnlp.1098/) 先依對話情境產生一般回應，再做 persona 對齊；支持「先對題、再角色化」的分層順序。
- [Developing Authentic Simulated Learners](https://arxiv.org/abs/2604.04361) 指出 zero/few-shot 模擬學生常產生不真實的知識與語言；微調、多代理與 DPO 均可改善，但需要資料與更高成本。
- [Misconception Faithfulness](https://arxiv.org/abs/2605.12748) 顯示學生模擬應以互動中的信念選擇性更新評估，而不是只看單句像不像學生；v4.5 的證據更新保留，v4.6 不以對題修正覆蓋迷思狀態。

## 方案比較

### A. 只改小宇的示例

最快，但其他角色與題型仍會複製不相干示例；不採用。

### B. 教師題型規劃＋同題型示例＋對題驗證（採用）

先用 deterministic 規則分類教師動作，再把回答焦點與禁止自行加入的條件寫進 BehaviorPlan。只提供同題型角色示例；第一次回答若改答別題或加入教師未給條件，沿用既有一次重試，第二次仍失敗才使用具名來源的情境 fallback。這符合目前本機 3B／7B、單次重試與可觀測證據架構。

### C. 第二個 LLM judge／多代理或微調

可能提高語意覆蓋與真實度，但會增加延遲、評分偏誤及資料需求。先列為後續實驗，不在本批次加入。

## 設計

教師動作第一版固定為：`definition`、`comparison`、`explanation`、`application`、`misconception_check`、`recall`、`generic`。

```text
教師發言
→ classify_teacher_move()
→ 建立 response_focus／forbidden_assumptions
→ 投影角色與參與情緒
→ 只選同題型的角色示例
→ Ollama 生成
→ validate_question_alignment()
→ 合格送出；不合格重試一次；仍失敗才情境 fallback
```

BehaviorPlan 新增：

- `teacher_move`：教師當輪語用任務。
- `response_focus`：學生這一輪應回答的核心，不指定完整句子。
- `forbidden_assumptions`：教師沒提供、學生不可自行補成題目條件的假設。

定義題至少禁止自行改成「質量相同／體積相同時怎麼比較」。比較題只能使用教師明示的條件。`validate_question_alignment()` 的失敗原因保存於既有 `generation_attempts.validation_failures`，觀測台不新增資料表。

每角色仍保留兩組合成示例，但加上 `teacher_move` 標記；當輪只注入相同題型示例，沒有相符示例就不塞入錯題型示例。示例只作開發資料，不宣稱來自真人學生。

## 驗收

- 截圖中的教師問題被分類為 `definition`。
- 小宇的規劃聚焦「密度的意思」，禁止自行加入質量相同／體積相同。
- 截圖回答觸發對題失敗並進入重試；自然的不確定定義回答可通過。
- 比較題仍允許使用教師已明示的相同質量／體積條件。
- BehaviorPlan、生成嘗試與觀測台顯示題型與回答焦點。
- Mock baseline、Mock 十輪課堂、完整測試及 3B 截圖案例開發 smoke 通過；3B smoke 只證明該案例改善，不宣稱整體真實度。
