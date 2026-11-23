class EvaluationSelectionGuard {
  static reviewPath({ runId, resultIndex }) {
    return `/api/evaluations/${encodeURIComponent(runId)}/results/${resultIndex}/review`;
  }

  static showsHoldoutWarning({ report, request, formSuite }) {
    return Boolean(
      (report && (report.used_holdout || report.suite === "holdout"))
      || (request && request.suite === "holdout")
      || formSuite === "holdout"
    );
  }

  constructor() {
    this.runId = null;
    this.version = 0;
  }

  select(runId) {
    this.runId = runId;
    this.version += 1;
    return Object.freeze({ runId, version: this.version });
  }

  current() {
    return Object.freeze({ runId: this.runId, version: this.version });
  }

  isCurrent(token) {
    return Boolean(
      token
      && token.runId === this.runId
      && token.version === this.version
    );
  }
}

if (typeof window !== "undefined") {
  window.EvaluationSelectionGuard = EvaluationSelectionGuard;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = EvaluationSelectionGuard;
}
