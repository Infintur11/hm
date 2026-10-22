// ==========================================
// Real-Time Cross-Tab Session Controller
// ==========================================
const HMS_AUTH = (function() {
  let channel = null;
  try {
    if (typeof BroadcastChannel !== "undefined") {
      channel = new BroadcastChannel("hms_auth_sync");
    }
  } catch (e) {
    channel = null;
  }

  function isProtectedPage() {
    const path = window.location.pathname;
    const publicPaths = ["/login", "/"];
    if (publicPaths.includes(path)) return false;
    if (path.startsWith("/receipt/")) return false;
    return true;
  }

  function clearLocalSession() {
    try {
      localStorage.removeItem("hms_session_active");
      document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax;";
      document.cookie = "session_active=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax;";
    } catch (e) {}
  }

  function handleLogoutOrExpiry(reason) {
    if (window.__isRedirecting) return;
    window.__isRedirecting = true;
    clearLocalSession();

    if (isProtectedPage()) {
      window.location.replace("/login?expired=1");
    }
  }

  function notifyLogout() {
    clearLocalSession();
    try {
      localStorage.setItem("hms_auth_sync", JSON.stringify({ action: "LOGOUT", time: Date.now() }));
    } catch (e) {}
    if (channel) {
      try {
        channel.postMessage({ action: "LOGOUT", time: Date.now() });
      } catch (e) {}
    }
  }

  function notifySessionExpired() {
    clearLocalSession();
    try {
      localStorage.setItem("hms_auth_sync", JSON.stringify({ action: "EXPIRED", time: Date.now() }));
    } catch (e) {}
    if (channel) {
      try {
        channel.postMessage({ action: "EXPIRED", time: Date.now() });
      } catch (e) {}
    }
  }

  function notifyLogin() {
    try {
      localStorage.setItem("hms_session_active", "1");
      document.cookie = "session_active=1; path=/; max-age=43200; SameSite=Lax";
      localStorage.setItem("hms_auth_sync", JSON.stringify({ action: "LOGIN", time: Date.now() }));
    } catch (e) {}
    if (channel) {
      try {
        channel.postMessage({ action: "LOGIN", time: Date.now() });
      } catch (e) {}
    }
  }

  // 1. Listen for real-time messages from other open tabs
  if (channel) {
    channel.onmessage = function(event) {
      if (event && event.data && (event.data.action === "LOGOUT" || event.data.action === "EXPIRED")) {
        handleLogoutOrExpiry(event.data.action);
      }
    };
  }

  // 2. Storage event listener (fallback & cross-tab sync across window boundaries)
  window.addEventListener("storage", function(e) {
    if (e.key === "hms_auth_sync" && e.newValue) {
      try {
        const data = JSON.parse(e.newValue);
        if (data.action === "LOGOUT" || data.action === "EXPIRED") {
          handleLogoutOrExpiry(data.action);
        }
      } catch (err) {}
    }
  });

  // 3. Real-time check when user switches back to this tab
  function checkSessionOnFocus() {
    if (isProtectedPage() && !window.__isRedirecting) {
      const hasCookie = document.cookie.indexOf("session_active=") !== -1 || document.cookie.indexOf("access_token=") !== -1;
      const hasStorage = localStorage.getItem("hms_session_active") === "1";
      if (!hasCookie && !hasStorage) {
        handleLogoutOrExpiry("FOCUS_NO_SESSION");
      }
    }
  }

  document.addEventListener("visibilitychange", function() {
    if (document.visibilityState === "visible") {
      checkSessionOnFocus();
    }
  });

  window.addEventListener("focus", checkSessionOnFocus);

  return {
    notifyLogout,
    notifySessionExpired,
    notifyLogin,
    clearLocalSession,
    handleLogoutOrExpiry,
    isProtectedPage
  };
})();

window.HMS_AUTH = HMS_AUTH;

async function apiFetch(url, options = {}) {
  const defaultHeaders = {
    "Content-Type": "application/json",
    "Accept": "application/json"
  };

  options.headers = { ...defaultHeaders, ...options.headers };

  try {
    const response = await fetch(url, options);
    
    if (response.status === 401) {
      if (!window.__isRedirecting) {
        window.__isRedirecting = true;
        HMS_AUTH.notifySessionExpired();
        HMS_AUTH.clearLocalSession();
        // Redirect immediately with zero lag and no duplicate toasts
        window.location.replace("/login?expired=1");
      }
      return null;
    }

    const data = await response.json();
    
    if (!response.ok) {
      let errorMsg = "Request failed. Please check your input.";
      if (typeof data.detail === "string") {
        errorMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map(e => {
          const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : "";
          const msg = e.msg || (typeof e === "string" ? e : JSON.stringify(e));
          return field ? `${String(field).replace(/_/g, " ")}: ${msg}` : msg;
        }).join(" | ");
      } else if (data.detail && typeof data.detail === "object") {
        errorMsg = data.detail.message || data.detail.msg || JSON.stringify(data.detail);
      } else if (data.message) {
        errorMsg = data.message;
      }
      showToast(errorMsg, "danger");
      throw new Error(errorMsg);
    }

    return data;
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
}

let lastToastTime = 0;
let lastToastMsg = "";

function showToast(message, type = "info") {
  let displayMessage = message;
  if (typeof message === "object" && message !== null) {
    if (message.message) {
      displayMessage = message.message;
    } else if (message.detail) {
      displayMessage = typeof message.detail === "string" ? message.detail : JSON.stringify(message.detail);
    } else if (Array.isArray(message)) {
      displayMessage = message.map(m => typeof m === "string" ? m : JSON.stringify(m)).join(", ");
    } else {
      displayMessage = JSON.stringify(message);
    }
  }

  // Deduplicate identical toasts within 1.5 seconds to prevent stacked duplicate alerts
  const now = Date.now();
  if (displayMessage === lastToastMsg && (now - lastToastTime) < 1500) {
    return;
  }
  lastToastTime = now;
  lastToastMsg = displayMessage;

  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  const iconMap = {
    success: `<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
    danger: `<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    warning: `<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    info: `<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
  };

  toast.innerHTML = `
    <div style="display:flex; align-items:center; gap:0.5rem;">
      <span>${iconMap[type] || ""}</span>
      <span>${displayMessage}</span>
    </div>
    <button onclick="this.parentElement.remove()" style="background:none; border:none; cursor:pointer; color:inherit; font-size:1.15rem; line-height:1;">&times;</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.add("active");
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.remove("active");
}

// Global hotkeys
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    const searchInput = document.querySelector(".search-box input");
    if (searchInput) searchInput.focus();
  }
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-backdrop.active").forEach(m => m.classList.remove("active"));
  }
});
