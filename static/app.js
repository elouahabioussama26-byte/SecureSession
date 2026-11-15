const authScreen = document.getElementById("auth-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const authForm = document.getElementById("auth-form");
const authError = document.getElementById("auth-error");
const loginTab = document.getElementById("login-tab");
const registerTab = document.getElementById("register-tab");
const confirmGroup = document.getElementById("confirm-group");
const passwordInput = document.getElementById("auth-password");
const confirmInput = document.getElementById("auth-confirm");
const submitButton = document.getElementById("auth-submit");
const submitLabel = document.getElementById("submit-label");
const sessionsBody = document.getElementById("sessions-body");
const eventList = document.getElementById("event-list");
const toast = document.getElementById("toast");
const logoutDialog = document.getElementById("logout-dialog");

let authMode = "login";
let currentSessionId = null;
let currentUsername = null;
let eventSource = null;
let toastTimer = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    throw new Error(message);
  }
  return data;
}

function showToast(message, type = "success") {
  toast.textContent = message;
  toast.dataset.type = type;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
}

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === "register";
  loginTab.classList.toggle("active", !registering);
  registerTab.classList.toggle("active", registering);
  loginTab.setAttribute("aria-selected", String(!registering));
  registerTab.setAttribute("aria-selected", String(registering));
  confirmGroup.hidden = !registering;
  confirmInput.required = registering;
  passwordInput.autocomplete = registering ? "new-password" : "current-password";
  document.getElementById("auth-eyebrow").textContent = registering ? "START WITH A SECURE ACCOUNT" : "YOUR WORKSPACE AWAITS";
  document.getElementById("auth-title").textContent = registering ? "Create your account" : "Welcome back";
  document.getElementById("auth-subtitle").textContent = registering
    ? "A few details and your secure workspace is ready."
    : "Sign in to review and manage your active sessions.";
  submitLabel.textContent = registering ? "Create secure account" : "Sign in to your account";
  document.getElementById("auth-switch").childNodes[0].textContent = registering
    ? "Already have an account? " : "New to SecureSession? ";
  document.getElementById("switch-mode").textContent = registering ? "Sign in" : "Create an account";
  authError.textContent = "";
}

function showAuth(message = "") {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  currentSessionId = null;
  currentUsername = null;
  dashboardScreen.hidden = true;
  authScreen.hidden = false;
  authForm.reset();
  setAuthMode("login");
  authError.textContent = message;
}

function showDashboard(session) {
  currentSessionId = session.session_id;
  currentUsername = session.username;
  authScreen.hidden = true;
  dashboardScreen.hidden = false;

  const username = session.username || "User";
  const initials = username.slice(0, 2).toUpperCase();
  document.getElementById("welcome-user").textContent = username;
  document.getElementById("sidebar-username").textContent = username;
  document.getElementById("sidebar-avatar").textContent = initials;
  document.getElementById("profile-avatar").textContent = initials;
  document.getElementById("profile-username").textContent = username;
  document.getElementById("detail-username").textContent = username;
  document.getElementById("detail-session").textContent = session.session_id.slice(0, 8) + "…";
  document.getElementById("detail-session").title = session.session_id;
  document.getElementById("detail-created").textContent = formatDate(session.created_at);
}

function formatDate(timestamp) {
  return new Date(timestamp * 1000).toLocaleString([], {
    year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit",
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
  if (!userAgent) return "Unknown browser";
  if (/Firefox/i.test(userAgent)) return "Firefox";
  if (/Edg/i.test(userAgent)) return "Microsoft Edge";
  if (/Chrome/i.test(userAgent)) return "Google Chrome";
  if (/Safari/i.test(userAgent)) return "Safari";
  return "Browser";
}

function addEvent(event) {
  const empty = eventList.querySelector(".empty-activity");
  if (empty) empty.remove();
  const row = document.createElement("div");
  row.className = "event-item";
  const dot = document.createElement("span");
  dot.className = "event-dot";
  const content = document.createElement("div");
  const title = document.createElement("strong");
  const subtitle = document.createElement("small");
  const labels = {
    "session.created": "New session created",
    "session.revoked": "Session revoked",
    "session.expired": "Session expired",
  };
  title.textContent = labels[event.type] || "Session activity";
  subtitle.textContent = (event.session_id || "Session").slice(0, 8) + " · " +
    new Date((event.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString();
  content.append(title, subtitle);
  row.append(dot, content);
  eventList.prepend(row);
  while (eventList.children.length > 5) eventList.lastElementChild.remove();
}

function connectEvents() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/events");
  eventSource.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data);
      addEvent(event);
      refreshSessions();
    } catch (_) {
      // Ignore malformed events; the next event can still be processed.
    }
  };
  eventSource.onerror = () => {
    // EventSource retries automatically if the connection is interrupted.
  };
}

async function refreshSessions() {
  const result = await api("/api/sessions");
  const sessions = result.sessions || [];
  const current = sessions.find((item) => item.session_id === currentSessionId);
  document.getElementById("active-count").textContent = String(result.total);
  document.getElementById("session-count-label").textContent =
    result.total + (result.total === 1 ? " active session" : " active sessions");
  document.getElementById("current-ttl").textContent = current
    ? formatDuration(current.ttl_seconds) : "—";
  document.getElementById("current-status").textContent = current ? "Active" : "Expired";

  sessionsBody.replaceChildren();
  if (!sessions.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "empty-cell";
    cell.textContent = "No active sessions found for your account.";
    row.append(cell);
    sessionsBody.append(row);
    return;
  }

  for (const session of sessions) {
    const row = document.createElement("tr");
    const deviceCell = document.createElement("td");
    const device = document.createElement("span");
    device.className = "device-name";
    device.textContent = deviceLabel(session.user_agent);
    const deviceSub = document.createElement("span");
    deviceSub.className = "device-sub";
    deviceSub.textContent = session.user_agent ? session.user_agent.slice(0, 55) : "Session client";
    deviceCell.append(device, deviceSub);

    const ipCell = document.createElement("td");
    ipCell.textContent = session.client_ip || "unknown";
    const createdCell = document.createElement("td");
    createdCell.textContent = formatDate(session.created_at);
    const ttlCell = document.createElement("td");
    ttlCell.textContent = formatDuration(session.ttl_seconds);
    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = session.is_current ? "current-badge" : "active-badge";
    badge.textContent = session.is_current ? "THIS DEVICE" : "ACTIVE";
    statusCell.append(badge);

    const actionCell = document.createElement("td");
    if (session.is_current) {
      const current = document.createElement("span");
      current.className = "current-label";
      current.textContent = "Current";
      actionCell.append(current);
    } else {
      const revoke = document.createElement("button");
      revoke.className = "revoke-button";
      revoke.type = "button";
      revoke.textContent = "Revoke";
      revoke.addEventListener("click", () => revokeSession(session.session_id));
      actionCell.append(revoke);
    }

    row.append(deviceCell, ipCell, createdCell, ttlCell, statusCell, actionCell);
    sessionsBody.append(row);
  }
}

async function revokeSession(sessionId) {
  try {
    await api("/api/sessions/" + encodeURIComponent(sessionId), { method: "DELETE" });
    showToast("That session has been revoked.");
    await refreshSessions();
  } catch (error) {
    showToast(error.message, "error");
    if (error.message.toLowerCase().includes("session has expired")) showAuth(error.message);
  }
}

async function initializeDashboard() {
  try {
    const result = await api("/api/sessions/me");
    showDashboard(result.session);
    await refreshSessions();
    connectEvents();
  } catch (_) {
    showAuth();
  }
}

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authError.textContent = "";

  const username = document.getElementById("auth-username").value.trim();
  const password = passwordInput.value;
  const confirm = confirmInput.value;

  if (authMode === "register" && password !== confirm) {
    authError.textContent = "Your passwords do not match.";
    confirmInput.focus();
    return;
  }
  if (password.length < 8) {
    authError.textContent = "Your password must contain at least 8 characters.";
    passwordInput.focus();
    return;
  }

  submitButton.disabled = true;
  submitButton.classList.add("loading");
  submitLabel.textContent = authMode === "register" ? "Creating account…" : "Signing in…";

  try {
    const path = authMode === "register" ? "/api/accounts" : "/api/sessions";
    const result = await api(path, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    await initializeDashboard();
    showToast(authMode === "register" ? "Your account is ready. Welcome!" : "You are signed in.");
  } catch (error) {
    authError.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.classList.remove("loading");
    submitLabel.textContent = authMode === "register" ? "Create secure account" : "Sign in to your account";
  }
});

loginTab.addEventListener("click", () => setAuthMode("login"));
registerTab.addEventListener("click", () => setAuthMode("register"));
document.getElementById("switch-mode").addEventListener("click", () => {
  setAuthMode(authMode === "login" ? "register" : "login");
});
document.getElementById("toggle-password").addEventListener("click", (event) => {
  const visible = passwordInput.type === "text";
  passwordInput.type = visible ? "password" : "text";
  event.currentTarget.textContent = visible ? "Show" : "Hide";
  event.currentTarget.setAttribute("aria-label", visible ? "Show password" : "Hide password");
});

function openLogoutDialog() {
  if (typeof logoutDialog.showModal === "function") logoutDialog.showModal();
  else if (window.confirm("Sign out of SecureSession?")) performLogout();
}
document.getElementById("logout-button").addEventListener("click", openLogoutDialog);
document.getElementById("sidebar-logout").addEventListener("click", openLogoutDialog);
document.getElementById("cancel-logout").addEventListener("click", () => logoutDialog.close());
document.getElementById("confirm-logout").addEventListener("click", performLogout);

async function performLogout() {
  const confirmButton = document.getElementById("confirm-logout");
  confirmButton.disabled = true;
  try {
    await api("/api/sessions/me", { method: "DELETE" });
    logoutDialog.close();
    showAuth("You have been signed out successfully.");
  } catch (error) {
    logoutDialog.close();
    showToast(error.message, "error");
  } finally {
    confirmButton.disabled = false;
  }
}

document.getElementById("refresh-button").addEventListener("click", async () => {
  const button = document.getElementById("refresh-button");
  button.disabled = true;
  try {
    await refreshSessions();
    showToast("Sessions refreshed.");
  } catch (error) {
    showToast(error.message, "error");
    if (error.message.toLowerCase().includes("session has expired")) showAuth(error.message);
  } finally {
    button.disabled = false;
  }
});

initializeDashboard();
