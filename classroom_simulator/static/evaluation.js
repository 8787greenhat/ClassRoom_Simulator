const state = {
  runs: [],
  selectedRunId: null,
  selectedRun: null,
  selectedResultIndex: null,
  reviewTarget: "delivered",
  filters: { source: "all", hardPass: "all", role: "all", review: "all" },
  pendingEdits: new Map(),
  pollTimer: null,
  starting: false,
};

const elements = {
  form: document.querySelector("#evaluation-form"),
  provider: document.querySelector("#evaluation-provider"),
  suite: document.querySelector("#evaluation-suite"),
  model: document.querySelector("#evaluation-model"),
  repeats: document.querySelector("#evaluation-repeats"),
  startButton: document.querySelector("#start-evaluation"),
  runStatus: document.querySelector("#run-status"),
  holdoutWarning: document.querySelector("#holdout-warning"),
  refreshHistory: document.querySelector("#refresh-history"),
  runHistory: document.querySelector("#run-history"),
  runSummary: document.querySelector("#run-summary"),
  sourceFilter: document.querySelector("#source-filter"),
  hardPassFilter: document.querySelector("#hard-pass-filter"),
  roleFilter: document.querySelector("#role-filter"),
  reviewFilter: document.querySelector("#review-filter"),
  caseList: document.querySelector("#case-list"),
  caseEvidence: document.querySelector("#case-evidence"),
  reviewForm: document.querySelector("#review-form"),
  reviewTarget: document.querySelector("#review-target"),
  reviewNotes: document.querySelector("#review-notes"),
  reviewMessage: document.querySelector("#review-message"),
  saveDraft: document.querySelector("#save-review-draft"),
  completeReview: document.querySelector("#complete-review"),
};

const statusLabels = {
  queued: "排隊中",
  running: "執行中",
  completed: "已完成",
  failed: "執行失敗",
  interrupted: "已中斷",
  corrupt: "資料損壞",
};

const sourceLabels = {
  raw_ollama: "Raw Ollama",
  guarded: "Guarded",
  fallback: "Fallback",
  mock: "Mock",
  error: "Error",
};

function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }
  if (!response.ok) {
    const message = payload && payload.detail ? payload.detail : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function formatDate(value) {
  if (!value) return "時間未保存";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

function formatPercent(value) {
  if (typeof value !== "number") return "尚無";
  return `${Math.round(value * 1000) / 10}%`;
}

function isActiveStatus(status) {
  return status === "queued" || status === "running";
}

function hasActiveRun() {
  return state.runs.some((run) => isActiveStatus(run.status));
}

function updateStartState() {
  const useOllama = elements.provider.value === "ollama";
  elements.model.disabled = !useOllama;
  elements.model.required = useOllama;
  elements.startButton.disabled = state.starting || hasActiveRun();
  elements.startButton.textContent = hasActiveRun() ? "已有評測執行中" : "開始評測";
}

function updateHoldoutWarning() {
  const selectedReport = state.selectedRun && state.selectedRun.report;
  const usedHoldout = selectedReport && selectedReport.used_holdout;
  elements.holdoutWarning.hidden = !(usedHoldout || elements.suite.value === "holdout");
}

async function loadModels() {
  try {
    const payload = await requestJson("/api/models");
    elements.model.replaceChildren();
    if (!payload.models.length) {
      const option = createElement("option", "", "沒有可用的 Ollama 模型");
      option.value = "";
      elements.model.append(option);
      return;
    }
    for (const model of payload.models) {
      const option = createElement("option", "", model.name);
      option.value = model.name;
      if (model.name === payload.default) option.selected = true;
      elements.model.append(option);
    }
  } catch (error) {
    elements.model.replaceChildren(createElement("option", "", "模型清單載入失敗"));
    elements.runStatus.textContent = error.message;
  } finally {
    updateStartState();
  }
}

function runTitle(run) {
  if (run.title) return run.title;
  const request = run.request || {};
  return `${request.provider || "未知 provider"} · ${request.suite || "未知情境組"}`;
}

function renderHistory() {
  elements.runHistory.replaceChildren();
  if (!state.runs.length) {
    elements.runHistory.append(createElement("li", "empty-state", "尚無評測紀錄。"));
    updateStartState();
    return;
  }

  for (const run of state.runs) {
    const item = document.createElement("li");
    const button = createElement("button", "list-button");
    button.type = "button";
    button.dataset.runId = run.run_id;
    button.setAttribute("aria-current", String(run.run_id === state.selectedRunId));
    button.append(createElement("strong", "list-title", runTitle(run)));
    const status = statusLabels[run.status] || run.status || "未知狀態";
    const kind = run.legacy ? "歷史封存" : "本機工作";
    button.append(createElement("span", "list-meta", `${kind} · ${status} · ${formatDate(run.created_at || run.generated_at)}`));
    button.addEventListener("click", () => selectRun(run.run_id));
    item.append(button);
    elements.runHistory.append(item);
  }
  updateStartState();
}

async function loadHistory(selectNewest = true) {
  try {
    const payload = await requestJson("/api/evaluations");
    state.runs = payload.evaluations;
    renderHistory();
    if (selectNewest && !state.selectedRunId && state.runs.length) {
      await selectRun(state.runs[0].run_id);
    }
  } catch (error) {
    elements.runStatus.textContent = `歷史載入失敗：${error.message}`;
  }
}

function schedulePoll() {
  clearTimeout(state.pollTimer);
  state.pollTimer = null;
  if (!state.selectedRun || !isActiveStatus(state.selectedRun.status)) return;
  state.pollTimer = window.setTimeout(pollSelectedRun, 1000);
}

async function pollSelectedRun() {
  if (!state.selectedRunId) return;
  try {
    const detail = await requestJson(`/api/evaluations/${encodeURIComponent(state.selectedRunId)}`);
    state.selectedRun = detail;
    const index = state.runs.findIndex((run) => run.run_id === detail.run_id);
    if (index >= 0) {
      const summary = { ...state.runs[index], ...detail };
      delete summary.report;
      state.runs[index] = summary;
    }
    renderHistory();
    renderSelectedRun();
    if (!isActiveStatus(detail.status)) await loadHistory(false);
  } catch (error) {
    elements.runStatus.textContent = `進度更新失敗：${error.message}`;
  } finally {
    schedulePoll();
  }
}

async function selectRun(runId) {
  savePendingReview();
  clearTimeout(state.pollTimer);
  state.pollTimer = null;
  state.selectedRunId = runId;
  state.selectedResultIndex = null;
  state.reviewTarget = "delivered";
  renderHistory();
  elements.runSummary.textContent = "載入評測明細中";
  elements.caseList.replaceChildren();
  elements.caseEvidence.textContent = "載入中";
  elements.reviewForm.hidden = true;
  try {
    state.selectedRun = await requestJson(`/api/evaluations/${encodeURIComponent(runId)}`);
    renderSelectedRun();
    schedulePoll();
  } catch (error) {
    state.selectedRun = null;
    elements.runSummary.textContent = `明細載入失敗：${error.message}`;
    elements.caseEvidence.textContent = "無法讀取這份評測。";
  }
}

function renderSelectedRun() {
  const detail = state.selectedRun;
  if (!detail) return;
  const status = statusLabels[detail.status] || detail.status;
  const progress = detail.progress || { completed: 0, total: 0 };
  if (!detail.report) {
    elements.runSummary.textContent = `${status} · ${progress.completed}/${progress.total}`;
    elements.runStatus.textContent = detail.error || `${status}：${progress.completed}/${progress.total}`;
    elements.caseList.replaceChildren(createElement("li", "empty-state", "工作完成後顯示案例。"));
    elements.caseEvidence.textContent = detail.error || "等待評測結果。";
    elements.reviewForm.hidden = true;
    updateStartState();
    updateHoldoutWarning();
    return;
  }

  const report = detail.report;
  const summary = report.summary || report;
  const total = summary.total_runs ?? report.total_runs ?? report.results.length;
  const passed = summary.passed_runs ?? report.passed_runs;
  const passRate = summary.pass_rate ?? report.pass_rate;
  elements.runSummary.textContent = `${status} · ${passed ?? "?"}/${total} 通過 · 硬性規則通過率 ${formatPercent(passRate)}`;
  elements.runStatus.textContent = detail.legacy ? "正在檢查唯讀歷史報告" : "評測已完成";
  populateRoleFilter(report.results);
  renderCases();
  updateStartState();
  updateHoldoutWarning();
}

function populateRoleFilter(results) {
  const current = elements.roleFilter.value;
  const roles = [...new Set(results.map((result) => result.role_id).filter(Boolean))].sort();
  elements.roleFilter.replaceChildren();
  const all = createElement("option", "", "全部角色");
  all.value = "all";
  elements.roleFilter.append(all);
  for (const role of roles) {
    const option = createElement("option", "", role);
    option.value = role;
    elements.roleFilter.append(option);
  }
  elements.roleFilter.value = roles.includes(current) ? current : "all";
  state.filters.role = elements.roleFilter.value;
}

function reviewStatus(result) {
  const reviews = Object.values(result.human_review || {});
  if (!reviews.length) return "unavailable";
  return reviews.every((review) => review.status === "completed") ? "completed" : "pending";
}

function resultMatches(result) {
  if (state.filters.source !== "all" && result.source_category !== state.filters.source) return false;
  if (state.filters.hardPass === "passed" && !result.passed) return false;
  if (state.filters.hardPass === "failed" && result.passed) return false;
  if (state.filters.role !== "all" && result.role_id !== state.filters.role) return false;
  if (state.filters.review !== "all" && reviewStatus(result) !== state.filters.review) return false;
  return true;
}

function filteredResultIndexes() {
  const report = state.selectedRun && state.selectedRun.report;
  if (!report) return [];
  return report.results
    .map((result, index) => ({ result, index }))
    .filter(({ result }) => resultMatches(result))
    .map(({ index }) => index);
}

function renderCases() {
  const report = state.selectedRun.report;
  const indexes = filteredResultIndexes();
  elements.caseList.replaceChildren();
  if (!indexes.length) {
    elements.caseList.append(createElement("li", "empty-state", "沒有符合篩選條件的案例。"));
    state.selectedResultIndex = null;
    renderCaseDetail();
    return;
  }

  for (const index of indexes) {
    const result = report.results[index];
    const item = document.createElement("li");
    const button = createElement("button", "list-button");
    button.type = "button";
    button.setAttribute("aria-current", String(index === state.selectedResultIndex));
    const source = sourceLabels[result.source_category] || result.source_category || "來源未知";
    const hardResult = result.passed ? "硬性通過" : "硬性未通過";
    button.append(createElement("strong", "list-title", `${index + 1}. ${result.role_id || "角色未保存"}`));
    button.append(createElement("span", "list-meta", `${source} · ${hardResult} · ${reviewStatus(result)}`));
    button.addEventListener("click", () => selectResult(index));
    item.append(button);
    elements.caseList.append(item);
  }

  if (state.selectedResultIndex === null || !indexes.includes(state.selectedResultIndex)) {
    state.selectedResultIndex = indexes[0];
    state.reviewTarget = "delivered";
  }
  renderCaseDetail();
}

function selectResult(index) {
  savePendingReview();
  state.selectedResultIndex = index;
  state.reviewTarget = "delivered";
  renderCases();
}

function addBadge(container, text, good = null) {
  const badge = createElement("span", "badge", text);
  if (good === true) badge.classList.add("good");
  if (good === false) badge.classList.add("bad");
  container.append(badge);
}

function addEvidenceCard(container, title, content, wide = false) {
  const card = createElement("section", `evidence-card${wide ? " wide" : ""}`);
  card.append(createElement("h4", "", title));
  card.append(createElement("p", "", content));
  container.append(card);
}

function missingValue(value, legacy = false) {
  if (value !== null && value !== undefined && value !== "") return String(value);
  return legacy ? "舊報告未保存" : "未保存";
}

function renderCaseDetail() {
  const report = state.selectedRun && state.selectedRun.report;
  const index = state.selectedResultIndex;
  if (!report || index === null || !report.results[index]) {
    elements.caseEvidence.replaceChildren();
    elements.caseEvidence.className = "empty-state";
    elements.caseEvidence.textContent = "選擇案例查看證據。";
    elements.reviewForm.hidden = true;
    return;
  }

  const result = report.results[index];
  elements.caseEvidence.replaceChildren();
  elements.caseEvidence.className = "";
  const badges = createElement("div", "badge-row");
  addBadge(badges, result.role_id || "角色未保存");
  addBadge(badges, sourceLabels[result.source_category] || result.source_category || "來源未知");
  addBadge(badges, result.passed ? "硬性通過" : "硬性未通過", Boolean(result.passed));
  if (result.guarded) addBadge(badges, `Guard：${result.guard_reason || "原因未保存"}`, false);
  elements.caseEvidence.append(badges);

  const grid = createElement("div", "evidence-grid");
  addEvidenceCard(grid, "教師問題", missingValue(result.teacher_message, state.selectedRun.legacy), true);
  addEvidenceCard(grid, "Guard 前原始回答", missingValue(result.raw_response, state.selectedRun.legacy));
  addEvidenceCard(grid, "實際送出的回答", result.error || missingValue(result.response, state.selectedRun.legacy));
  addEvidenceCard(grid, "情境", `${result.scenario_id || "未保存"} · 迷思強度 ${missingValue(result.misconception_strength, state.selectedRun.legacy)}`);
  const expected = Array.isArray(result.expected_markers) ? result.expected_markers.join("、") || "無" : missingValue(null, state.selectedRun.legacy);
  const forbidden = Array.isArray(result.forbidden_markers) ? result.forbidden_markers.join("、") || "無" : missingValue(null, state.selectedRun.legacy);
  addEvidenceCard(grid, "Marker 證據", `預期：${expected}\n禁用：${forbidden}`);
  const checkLines = Object.entries(result.checks || {}).map(([name, passed]) => `${passed ? "通過" : "未通過"}：${name}`);
  addEvidenceCard(grid, "硬性檢查", checkLines.length ? checkLines.join("\n") : missingValue(null, state.selectedRun.legacy), true);
  elements.caseEvidence.append(grid);
  renderReviewForm(result);
}

function pendingKey(target = state.reviewTarget) {
  return `${state.selectedRunId}:${state.selectedResultIndex}:${target}`;
}

function readReviewForm() {
  const values = { notes: elements.reviewNotes.value };
  for (const name of ["directly_answers_teacher_request", "role_consistency", "student_realism"]) {
    const selected = elements.reviewForm.querySelector(`input[name="${name}"]:checked`);
    values[name] = selected ? selected.value : null;
  }
  return values;
}

function savePendingReview(target = state.reviewTarget) {
  if (elements.reviewForm.hidden || state.selectedResultIndex === null) return;
  state.pendingEdits.set(pendingKey(target), readReviewForm());
}

function renderReviewForm(result) {
  const targets = result.human_review || {};
  const targetNames = Object.keys(targets);
  if (!targetNames.length) {
    elements.reviewForm.hidden = true;
    return;
  }

  elements.reviewForm.hidden = false;
  elements.reviewTarget.replaceChildren();
  for (const target of targetNames) {
    const label = target === "raw_model" ? "Raw model（Guard 前）" : "Delivered（實際送出）";
    const option = createElement("option", "", label);
    option.value = target;
    elements.reviewTarget.append(option);
  }
  if (!targetNames.includes(state.reviewTarget)) state.reviewTarget = targetNames[0];
  elements.reviewTarget.value = state.reviewTarget;

  const saved = targets[state.reviewTarget] || {};
  const draft = state.pendingEdits.get(pendingKey()) || saved;
  for (const name of ["directly_answers_teacher_request", "role_consistency", "student_realism"]) {
    for (const input of elements.reviewForm.querySelectorAll(`input[name="${name}"]`)) {
      input.checked = input.value === draft[name];
    }
  }
  elements.reviewNotes.value = draft.notes || "";
  elements.reviewMessage.textContent = saved.status === "completed" ? `已完成覆核 · ${formatDate(saved.reviewed_at)}` : "尚未完成覆核";
}

async function saveReview(complete) {
  const report = state.selectedRun && state.selectedRun.report;
  const result = report && report.results[state.selectedResultIndex];
  if (!result) return;
  savePendingReview();
  const review = state.pendingEdits.get(pendingKey()) || readReviewForm();
  const payload = { target: state.reviewTarget, ...review, complete };
  elements.saveDraft.disabled = true;
  elements.completeReview.disabled = true;
  elements.reviewMessage.textContent = complete ? "完成覆核中" : "保存草稿中";
  try {
    const updated = await requestJson(`/api/evaluations/${encodeURIComponent(state.selectedRunId)}/results/${state.selectedResultIndex}/review`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.pendingEdits.delete(pendingKey());
    state.selectedRun = updated;
    const previousIndex = state.selectedResultIndex;
    if (complete) {
      const indexes = filteredResultIndexes();
      const position = indexes.indexOf(previousIndex);
      state.selectedResultIndex = indexes[position + 1] ?? previousIndex;
      state.reviewTarget = "delivered";
    }
    renderSelectedRun();
    elements.reviewMessage.textContent = complete ? "覆核已完成" : "草稿已保存";
  } catch (error) {
    elements.reviewMessage.textContent = `保存失敗：${error.message}。未送出的內容仍保留。`;
  } finally {
    elements.saveDraft.disabled = false;
    elements.completeReview.disabled = false;
  }
}

async function createEvaluation(event) {
  event.preventDefault();
  state.starting = true;
  updateStartState();
  elements.runStatus.textContent = "建立評測工作中";
  const provider = elements.provider.value;
  const payload = { provider, suite: elements.suite.value, repeats: Number(elements.repeats.value) };
  if (provider === "ollama") payload.model = elements.model.value;
  try {
    const job = await requestJson("/api/evaluations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.runs = [job, ...state.runs.filter((run) => run.run_id !== job.run_id)];
    state.starting = false;
    renderHistory();
    await selectRun(job.run_id);
  } catch (error) {
    elements.runStatus.textContent = `無法建立評測：${error.message}`;
  } finally {
    state.starting = false;
    updateStartState();
  }
}

function updateFilters() {
  savePendingReview();
  state.filters = {
    source: elements.sourceFilter.value,
    hardPass: elements.hardPassFilter.value,
    role: elements.roleFilter.value,
    review: elements.reviewFilter.value,
  };
  renderCases();
}

elements.form.addEventListener("submit", createEvaluation);
elements.provider.addEventListener("change", updateStartState);
elements.suite.addEventListener("change", updateHoldoutWarning);
elements.refreshHistory.addEventListener("click", () => loadHistory(false));
elements.sourceFilter.addEventListener("change", updateFilters);
elements.hardPassFilter.addEventListener("change", updateFilters);
elements.roleFilter.addEventListener("change", updateFilters);
elements.reviewFilter.addEventListener("change", updateFilters);
elements.reviewTarget.addEventListener("change", () => {
  savePendingReview(state.reviewTarget);
  state.reviewTarget = elements.reviewTarget.value;
  renderCaseDetail();
});
elements.reviewForm.addEventListener("input", savePendingReview);
elements.saveDraft.addEventListener("click", () => saveReview(false));
elements.completeReview.addEventListener("click", () => saveReview(true));
window.addEventListener("beforeunload", () => clearTimeout(state.pollTimer));

Promise.all([loadModels(), loadHistory()]).then(() => {
  elements.runStatus.textContent = state.runs.length ? "評測紀錄已載入" : "尚無評測紀錄";
  updateStartState();
  updateHoldoutWarning();
});
