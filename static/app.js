const loginPanel = document.getElementById("login-panel");
const dashboard = document.getElementById("dashboard");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const sessionsBody = document.getElementById("sessions-body");
const eventList = document.getElementById("event-list");
const toast = document.getElementById("toast");
let currentSessionId = null;
let eventSource = null;
let toastTimer = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof data.detail === "string" ? data.detail : "Request failed.";
    throw new Error(message);
  }
  return data;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function formatDate(timestamp) {
  return new Date(timestamp * 1000).toLocaleString([], {
    month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = value % 60;
  if (hours) return hours + "h " + minutes + "m";
  if (minutes) return minutes + "m " + secs + "s";
  return secs + "s";
}

function deviceLabel(userAgent) {
  if (!userAgent) return "Unknown client";
  if (/Firefox/i.test(userAgent)) return "Firefox browser";
  if (/Edg/i.test(userAgent)) return "Microsoft Edge";
  if (/Chrome/i.test(userAgent)) return "Chrome browser";
  if (/Safari/i.test(userAgent)) return "Safari browser";
  return userAgent.slice(0, 35);
}

function showLogin() {
  dashboard.hidden = true;
  loginPanel.hidden = false;
  document.getElementById("user-avatar").textContent = "?";
  if (eventSource) eventSource.close();
}

function showDashboard() {
  loginPanel.hidden = true;
  dashboard.hidden = false;
}

function addEvent(event) {
  const empty = eventList.querySelector(".muted");
  if (empty) empty.remove();
  const row = document.createElement("div");
  row.className = "event-item";
  const dot = document.createElement("span");
  dot.className = "event-indicator";
  const textWrap = document.createElement("div");
  const title = document.createElement("strong");
  const subtitle = document.createElement("small");
  const labels = {
    "session.created": "New session created",
    "session.revoked": "Session revoked",
    "session.expired": "Session expired",
  };
  title.textContent = labels[event.type] || "Session activity";
  subtitle.textContent = (event.session_id || "Session") .slice(0, 8) + " · " +
    new Date((event.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString();
  textWrap.append(title, subtitle);
  row.append(dot, textWrap);
  eventList.prepend(row);
  while (eventList.children.length > 6) eventList.lastElementChild.remove();
}

function connectEvents() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/events");
  eventSource.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data);
      addEvent(event);
      refreshSessions();
    } catch (_) { /* Ignore malformed event messages. */ }
  };
  eventSource.onerror = () => {
    // EventSource reconnects automatically. The dashboard remains usable.
  };
}

async function refreshSessions() {
  const result = await api("/api/sessions");
  const sessions = result.sessions || [];
  document.getElementById("active-count").textContent = result.total;
  const current = sessions.find((item) => item.session_id === currentSessionId);
  document.getElementById("current-ttl").textContent = current
    ? formatDuration(current.ttl_seconds) : "—";
  document.getElementById("current-status").textContent = current ? "Active" : "Not found";

  sessionsBody.replaceChildren();
  if (!sessions.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.className = "empty-cell";
    cell.textContent = "No active sessions found.";
    row.append(cell);
    sessionsBody.append(row);
    return;
  }

  for (const session of sessions) {
    const row = document.createElement("tr");
    const idCell = document.createElement("td");
    const id = document.createElement("span");
    id.className = "session-id";
    id.textContent = session.session_id.slice(0, 8) + "…";
    id.title = session.session_id;
    idCell.append(id);

    const deviceCell = document.createElement("td");
    const device = document.createElement("span");
    device.className = "device-name";
    device.textContent = deviceLabel(session.user_agent);
    const browser = document.createElement("span");
    browser.className = "device-sub";
    browser.textContent = session.user_agent ? session.user_agent.slice(0, 48) : "Demo session";
    deviceCell.append(device, browser);

    const ipCell = document.createElement("td");
    ipCell.textContent = session.client_ip || "unknown";
    const createdCell = document.createElement("td");
    createdCell.textContent = formatDate(session.created_at);
    const ttlCell = document.createElement("td");
    ttlCell.textContent = formatDuration(session.ttl_seconds);
    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = session.is_current ? "current-badge" : "status-badge";
    badge.textContent = session.is_current ? "CURRENT" : "ACTIVE";
    statusCell.append(badge);

    const actionCell = document.createElement("td");
    const revoke = document.createElement("button");
    revoke.className = "revoke-button";
    revoke.type = "button";
    revoke.textContent = "Revoke";
    revoke.disabled = session.is_current;
    revoke.title = session.is_current
      ? "Use Sign out this session to revoke the current session"
      : "Revoke this session";
    revoke.addEventListener("click", () => revokeSession(session.session_id));
    actionCell.append(revoke);

    row.append(idCell, deviceCell, ipCell, createdCell, ttlCell, statusCell, actionCell);
    sessionsBody.append(row);
  }
}

async function revokeSession(sessionId) {
  try {
    await api("/api/sessions/" + encodeURIComponent(sessionId), { method: "DELETE" });
    showToast("Session revoked successfully.");
    await refreshSessions();
  } catch (error) {
    showToast(error.message);
  }
}

async function initializeDashboard() {
  try {
    const result = await api("/api/sessions/me");
    currentSessionId = result.session.session_id;
    document.getElementById("welcome-user").textContent = result.session.username;
    document.getElementById("user-avatar").textContent =
      result.session.username.slice(0, 2).toUpperCase();
    showDashboard();
    await refreshSessions();
    connectEvents();
  } catch (error) {
    currentSessionId = null;
    showLogin();
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const username = document.getElementById("username").value.trim();
  try {
    await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ username }),
    });
    await initializeDashboard();
    showToast("Your session has been created.");
  } catch (error) {
    loginError.textContent = error.message;
  }
});

document.getElementById("refresh-button").addEventListener("click", async () => {
  try {
    await refreshSessions();
    showToast("Sessions refreshed.");
  } catch (error) {
    showToast(error.message);
    if (error.message.includes("valid session")) showLogin();
  }
});

document.getElementById("logout-button").addEventListener("click", async () => {
  try {
    await api("/api/sessions/me", { method: "DELETE" });
    currentSessionId = null;
    showLogin();
    showToast("Current session signed out.");
  } catch (error) {
    showToast(error.message);
  }
});

initializeDashboard();
