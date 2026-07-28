(() => {
  "use strict";

  const TOKEN_KEY = "opencritique.studio.token";
  const state = {
    token: sessionStorage.getItem(TOKEN_KEY) || "",
    me: null,
    task: null,
    mode: null,
  };

  const $ = (id) => document.getElementById(id);

  function setMessage(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.classList.remove("error", "success", "muted");
    if (kind) el.classList.add(kind);
  }

  function authHeaders() {
    return {
      Authorization: `Bearer ${state.token}`,
      Accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...authHeaders(),
        ...(options.headers || {}),
      },
    });
    const text = await response.text();
    let body = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    if (!response.ok) {
      const detail =
        body && typeof body === "object" && body.detail
          ? typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail)
          : response.statusText;
      throw new Error(detail || `HTTP ${response.status}`);
    }
    return body;
  }

  function renderIdentity() {
    const identity = $("identity");
    if (!state.me) {
      identity.textContent = "Not authenticated";
      return;
    }
    identity.textContent = `${state.me.display_name || state.me.actor_id} (${state.me.role})`;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderList(items, formatter) {
    if (!items || !items.length) return "<p class='muted'>None</p>";
    return `<ul>${items.map((item) => `<li>${formatter(item)}</li>`).join("")}</ul>`;
  }

  function renderAdjudicationTask(payload) {
    $("task-header").innerHTML = `
      <p class="eyebrow">${escapeHtml(payload.case_id)} / ${escapeHtml(payload.case_version)}</p>
      <h2>${escapeHtml(payload.concern_title)}</h2>
      <p>${escapeHtml(payload.concern_summary)}</p>
      <p class="muted">Type: ${escapeHtml(payload.concern_type)} · Slot: ${escapeHtml(payload.slot)}</p>
    `;

    $("source-link").href = `/v1/artifacts/${payload.manuscript_artifact_sha256}`;
    const renderLink = $("render-link");
    if (payload.rendered_artifact_sha256) {
      renderLink.href = `/v1/artifacts/${payload.rendered_artifact_sha256}`;
      renderLink.classList.remove("hidden");
    } else {
      renderLink.classList.add("hidden");
    }

    $("task-content").innerHTML = `
      <h3>Claims</h3>
      ${renderList(payload.claims, (c) => `<strong>${escapeHtml(c.claim_id)}</strong>: ${escapeHtml(c.statement)}`)}
      <h3>Anchors</h3>
      ${renderList(
        payload.anchors,
        (a) =>
          `<strong>${escapeHtml(a.anchor_id)}</strong> (${escapeHtml(a.anchor_type)})` +
          (a.source_text ? `: ${escapeHtml(a.source_text)}` : "")
      )}
      <h3>Evidence</h3>
      ${renderList(
        payload.evidence,
        (e) => `<strong>${escapeHtml(e.evidence_id)}</strong>: ${escapeHtml(e.description)}`
      )}
      <h3>Strongest manuscript defense</h3>
      ${renderList(payload.counterpositions, (c) => escapeHtml(c.statement))}
    `;

    const evidenceBox = $("evidence-checkboxes");
    evidenceBox.innerHTML = (payload.evidence || [])
      .map(
        (item) => `
        <label class="checkbox">
          <input type="checkbox" name="evidence" value="${escapeHtml(item.evidence_id)}">
          ${escapeHtml(item.evidence_id)} — ${escapeHtml(item.description)}
        </label>`
      )
      .join("");

    $("adjudication-form").classList.remove("hidden");
    $("claim-form").classList.add("hidden");
    $("task-panel").classList.remove("hidden");
  }

  function renderClaimTask(payload) {
    $("task-header").innerHTML = `
      <p class="eyebrow">Claim reconstruction · ${escapeHtml(payload.task.task_id)}</p>
      <h2>${escapeHtml(payload.title)}</h2>
      <p class="muted">${escapeHtml(payload.domain_profile)} · ${escapeHtml(payload.language)}</p>
    `;
    $("source-link").href = `/v1/artifacts/${payload.source_artifact_sha256}`;
    $("render-link").classList.add("hidden");

    const prior = payload.prior_reconstructions || [];
    $("task-content").innerHTML = `
      <h3>Prior reconstructions</h3>
      ${
        prior.length
          ? renderList(prior, (item) => escapeHtml(JSON.stringify(item)))
          : "<p class='muted'>None visible under blinding.</p>"
      }
    `;

    const anchors = (payload.task && payload.task.anchor_context) || [];
    const anchorBox = $("claim-anchor-checkboxes");
    if (anchors.length) {
      anchorBox.innerHTML = anchors
        .map((item) => {
          const id = item.anchor_id || item.id || "";
          const label = item.source_text || item.object_label || id;
          return `<label class="checkbox"><input type="checkbox" value="${escapeHtml(id)}"> ${escapeHtml(label)}</label>`;
        })
        .join("");
    } else {
      anchorBox.innerHTML =
        '<p class="muted">No anchor context was provided. Include ocanchor_… identifiers in reconstruction notes.</p>';
    }

    $("claim-form").classList.remove("hidden");
    $("adjudication-form").classList.add("hidden");
    $("task-panel").classList.remove("hidden");
  }

  async function connect() {
    const token = $("token").value.trim();
    if (!token) {
      setMessage($("queue-message"), "Paste a bearer token to connect.", "error");
      return;
    }
    state.token = token;
    sessionStorage.setItem(TOKEN_KEY, token);
    try {
      state.me = await api("/v1/me");
      renderIdentity();
      setMessage($("queue-message"), "Connected. Claim a task to begin.", "success");
    } catch (err) {
      state.me = null;
      renderIdentity();
      setMessage($("queue-message"), err.message, "error");
    }
  }

  function disconnect() {
    state.token = "";
    state.me = null;
    state.task = null;
    state.mode = null;
    sessionStorage.removeItem(TOKEN_KEY);
    $("token").value = "";
    $("task-panel").classList.add("hidden");
    renderIdentity();
    setMessage($("queue-message"), "Session cleared.", "muted");
  }

  async function claimAdjudication() {
    try {
      const task = await api("/v1/tasks/claim", { method: "POST", body: "{}" });
      const payload = await api(`/v1/tasks/${encodeURIComponent(task.task_id)}`);
      state.task = payload;
      state.mode = "adjudication";
      renderAdjudicationTask(payload);
      setMessage($("queue-message"), `Claimed adjudication task ${task.task_id}.`, "success");
      setMessage($("submit-message"), "");
    } catch (err) {
      setMessage($("queue-message"), err.message, "error");
    }
  }

  async function claimReconstruction() {
    try {
      const task = await api("/v1/claim-tasks/claim", { method: "POST", body: "{}" });
      const payload = await api(`/v1/claim-tasks/${encodeURIComponent(task.task_id)}`);
      state.task = payload;
      state.mode = "claim";
      renderClaimTask(payload);
      setMessage($("queue-message"), `Claimed reconstruction task ${task.task_id}.`, "success");
      setMessage($("submit-message"), "");
    } catch (err) {
      setMessage($("queue-message"), err.message, "error");
    }
  }

  async function submitAdjudication(event) {
    event.preventDefault();
    if (!state.task || state.mode !== "adjudication") return;
    const evidenceIds = Array.from(
      document.querySelectorAll('input[name="evidence"]:checked')
    ).map((node) => node.value);
    const body = {
      validity: $("validity").value,
      severity: $("severity").value,
      confidence: Number($("confidence").value),
      reasoning: $("reasoning").value,
      evidence_ids: evidenceIds,
      counterposition_assessment: $("counterposition").value,
      requested_followup: [],
      anchors_reviewed: $("anchors-reviewed").checked,
      conflict_declaration: {
        status: $("conflict-status").value,
        description: $("conflict-description").value || "",
      },
    };
    try {
      const taskId = state.task.task_id;
      await api(`/v1/tasks/${encodeURIComponent(taskId)}/submit`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage($("submit-message"), "Adjudication submitted.", "success");
      $("adjudication-form").reset();
      $("confidence-value").textContent = "0.70";
      $("task-panel").classList.add("hidden");
      state.task = null;
    } catch (err) {
      setMessage($("submit-message"), err.message, "error");
    }
  }

  async function submitClaim(event) {
    event.preventDefault();
    if (!state.task || state.mode !== "claim") return;
    const selected = Array.from(
      document.querySelectorAll('#claim-anchor-checkboxes input[type="checkbox"]:checked')
    ).map((node) => node.value);
    const manual = $("claim-notes").value.match(/ocanchor_[A-Za-z0-9._-]+/g) || [];
    const anchorIds = [...new Set([...selected, ...manual])];
    if (!anchorIds.length) {
      setMessage(
        $("submit-message"),
        "Provide at least one anchor id (checkbox or ocanchor_… in notes).",
        "error"
      );
      return;
    }
    const body = {
      statement: $("claim-statement").value,
      claim_type: $("claim-type").value,
      explicitness: $("explicitness").value,
      scope: $("claim-scope").value,
      anchor_ids: anchorIds,
      reconstruction_notes: $("claim-notes").value || "",
    };
    try {
      const taskId = state.task.task.task_id;
      await api(`/v1/claim-tasks/${encodeURIComponent(taskId)}/submit`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage($("submit-message"), "Claim reconstruction submitted.", "success");
      $("claim-form").reset();
      $("task-panel").classList.add("hidden");
      state.task = null;
    } catch (err) {
      setMessage($("submit-message"), err.message, "error");
    }
  }

  async function loadAuditProtocol() {
    try {
      const protocol = await api("/v1/matcher-audit/protocol");
      const rules = await api("/v1/matcher-audit/blinding-rules");
      $("audit-protocol").textContent =
        `${protocol.protocol_id} · seed ${protocol.random_seed} · target ${protocol.target_sample_size}. ` +
        `Blinding: ${rules.rule} Human audits may invalidate policy: ${rules.human_audit_may_invalidate_policy}.`;
      $("audit-protocol").classList.remove("muted", "error");
      $("audit-protocol").classList.add("success");
      $("audit-candidate").classList.remove("hidden");
      $("audit-payload").textContent = JSON.stringify(
        {
          note: "Candidates are served without system identity. Paste a blinded_payload from the audit sample API/docs.",
          system_identity_hidden: true,
          leaderboard_hidden: true,
        },
        null,
        2
      );
    } catch (err) {
      setMessage($("audit-protocol"), err.message, "error");
    }
  }

  function bind() {
    $("connect").addEventListener("click", connect);
    $("disconnect").addEventListener("click", disconnect);
    $("claim-adjudication").addEventListener("click", claimAdjudication);
    $("claim-reconstruction").addEventListener("click", claimReconstruction);
    $("adjudication-form").addEventListener("submit", submitAdjudication);
    $("claim-form").addEventListener("submit", submitClaim);
    $("load-audit-protocol").addEventListener("click", loadAuditProtocol);
    $("confidence").addEventListener("input", (event) => {
      $("confidence-value").textContent = Number(event.target.value).toFixed(2);
    });
    if (state.token) {
      $("token").value = state.token;
      connect();
    }
  }

  document.addEventListener("DOMContentLoaded", bind);
})();
