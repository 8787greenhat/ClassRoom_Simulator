const state = { sessionId: null, snapshot: null, busy: false };

const elements = {
  status: document.querySelector("#model-status"),
  topic: document.querySelector("#topic"),
  objective: document.querySelector("#objective"),
  start: document.querySelector("#start-button"),
  finish: document.querySelector("#finish-button"),
  students: document.querySelector("#students"),
  messages: document.querySelector("#messages"),
  title: document.querySelector("#session-title"),
  turnCount: document.querySelector("#turn-count"),
  form: document.querySelector("#message-form"),
  input: document.querySelector("#teacher-message"),
  send: document.querySelector("#send-button"),
};

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || "請求失敗");
  return body;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setBusy(busy) {
  state.busy = busy;
  const active = state.snapshot?.session?.status === "active";
  elements.send.disabled = busy || !active;
  elements.input.disabled = busy || !active;
  elements.start.disabled = busy;
  elements.finish.disabled = busy || !active;
  elements.send.textContent = busy ? "回應中…" : "送出";
}

function render(snapshot) {
  state.snapshot = snapshot;
  const session = snapshot.session;
  const studentEvents = snapshot.events.filter((event) => event.speaker_type === "student");
  const latestStudent = studentEvents.at(-1)?.speaker_id;
  elements.title.textContent = `${session.topic}${session.status === "finished" ? "（已結束）" : ""}`;
  elements.turnCount.textContent = `${studentEvents.length} 輪`;

  elements.students.innerHTML = snapshot.students.map((student) => {
    const strength = student.state.misconception_strength;
    return `
      <article class="student-card ${student.id === latestStudent ? "speaking" : ""}" style="--student-color:${student.color}">
        <div class="student-name"><span>${escapeHtml(student.name)}</span><span>${student.state.participation_count} 次</span></div>
        <div class="student-role">${escapeHtml(student.personality)}</div>
        <div class="student-meta">
          <span class="chip">程度 ${escapeHtml(student.ability_level)}</span>
          ${student.misconception ? `<span class="chip">迷思 ${strength}/3</span>` : ""}
          <span class="chip">記憶 ${Math.floor(student.state.memory.length / 2)} 輪</span>
        </div>
      </article>`;
  }).join("");

  if (!snapshot.events.length) {
    elements.messages.innerHTML = '<div class="empty-state">課堂已建立。輸入第一句教學內容開始模擬。</div>';
  } else {
    const studentsById = Object.fromEntries(snapshot.students.map((student) => [student.id, student]));
    elements.messages.innerHTML = snapshot.events.map((event) => {
      const teacher = event.speaker_type === "teacher";
      const student = studentsById[event.speaker_id];
      const provider = event.metadata?.provider ? `<span class="provider">· ${escapeHtml(event.metadata.provider)}</span>` : "";
      return `
        <article class="message ${teacher ? "teacher" : "student"}">
          <div class="message-body">
            <div class="message-meta">${teacher ? "教師" : escapeHtml(student?.name || event.speaker_id)} · 第 ${event.turn_number} 輪 ${provider}</div>
            <div class="bubble">${escapeHtml(event.content)}</div>
          </div>
        </article>`;
    }).join("");
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }
  setBusy(false);
}

async function checkHealth() {
  try {
    const health = await request("/api/health");
    if (health.ollama_available) {
      elements.status.textContent = `Ollama · ${health.model}`;
      elements.status.classList.add("online");
    } else {
      elements.status.textContent = "模擬回應模式";
      elements.status.classList.add("fallback");
    }
  } catch {
    elements.status.textContent = "服務未連線";
  }
}

elements.start.addEventListener("click", async () => {
  setBusy(true);
  try {
    const snapshot = await request("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ topic: elements.topic.value, objective: elements.objective.value }),
    });
    state.sessionId = snapshot.session.id;
    render(snapshot);
    elements.input.focus();
  } catch (error) {
    alert(error.message);
    setBusy(false);
  }
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = elements.input.value.trim();
  if (!message || !state.sessionId) return;
  elements.input.value = "";
  setBusy(true);
  try {
    render(await request(`/api/sessions/${state.sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }));
  } catch (error) {
    alert(error.message);
    elements.input.value = message;
    setBusy(false);
  }
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.finish.addEventListener("click", async () => {
  if (!state.sessionId) return;
  setBusy(true);
  try {
    render(await request(`/api/sessions/${state.sessionId}/finish`, { method: "POST" }));
  } catch (error) {
    alert(error.message);
    setBusy(false);
  }
});

checkHealth();

