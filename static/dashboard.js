/**
 * PngLike User Login & Studio Dashboard Controller
 * Powered by Div Sri
 */

let userToken = localStorage.getItem("pnglike_user_token") || localStorage.getItem("rembg_user_token") || "";
let currentUser = null;
let userJobsCache = [];
let pendingVerificationEmail = "";

function safeCreateIcons() {
  try {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  } catch (_) {}
}

const tabTitles = {
  overview: "My Studio Overview",
  gallery: "My Creations & History",
  settings: "Account Profile & Security",
};

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showAuthAlert(msg, isError = true) {
  const box = document.getElementById("authAlertBox");
  if (!box) return;
  box.textContent = msg;
  box.className = isError
    ? "mb-4 text-xs font-semibold rounded-xl p-3 border bg-rose-50 dark:bg-rose-950/50 border-rose-200 dark:border-rose-800 text-rose-500"
    : "mb-4 text-xs font-semibold rounded-xl p-3 border bg-emerald-50 dark:bg-emerald-950/50 border-emerald-200 dark:border-emerald-800 text-emerald-500";
  box.classList.remove("hidden");
}

function hideAuthAlert() {
  const box = document.getElementById("authAlertBox");
  if (box) box.classList.add("hidden");
}

async function userFetch(url, options = {}) {
  const headers = Object.assign({}, options.headers || {}, {
    "X-User-Token": userToken,
  });
  const res = await fetch(url, Object.assign({}, options, { headers }));
  if (res.status === 401) {
    localStorage.removeItem("rembg_user_token");
    userToken = "";
    const overlay = document.getElementById("userAuthOverlay");
    if (overlay) overlay.classList.remove("hidden");
    throw new Error("Session expired. Please sign in again.");
  }
  return res;
}

function switchAuthMode(mode) {
  hideAuthAlert();
  const loginForm = document.getElementById("userLoginForm");
  const regForm = document.getElementById("userRegisterForm");
  const verifyForm = document.getElementById("userVerifyForm");
  const tabsContainer = document.getElementById("authTabsContainer");
  const btnLogin = document.getElementById("tabBtnLogin");
  const btnReg = document.getElementById("tabBtnRegister");

  if (mode === "register") {
    loginForm?.classList.add("hidden");
    verifyForm?.classList.add("hidden");
    regForm?.classList.remove("hidden");
    tabsContainer?.classList.remove("hidden");
    if (btnReg) btnReg.className = "py-2.5 rounded-xl bg-white dark:bg-dark-900 text-indigo-600 dark:text-indigo-400 shadow-sm transition";
    if (btnLogin) btnLogin.className = "py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition";
  } else if (mode === "verify") {
    loginForm?.classList.add("hidden");
    regForm?.classList.add("hidden");
    verifyForm?.classList.remove("hidden");
    tabsContainer?.classList.add("hidden");
    const emailEl = document.getElementById("verifyTargetEmail");
    if (emailEl) emailEl.textContent = pendingVerificationEmail || "your email address";
    const codeIn = document.getElementById("verifyCodeInput");
    if (codeIn) {
      codeIn.value = "";
      setTimeout(() => codeIn.focus(), 100);
    }
  } else {
    // "login"
    regForm?.classList.add("hidden");
    verifyForm?.classList.add("hidden");
    loginForm?.classList.remove("hidden");
    tabsContainer?.classList.remove("hidden");
    if (btnLogin) btnLogin.className = "py-2.5 rounded-xl bg-white dark:bg-dark-900 text-indigo-600 dark:text-indigo-400 shadow-sm transition";
    if (btnReg) btnReg.className = "py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition";
  }
  if (window.lucide) {
    try { window.lucide.createIcons(); } catch (_) {}
  }
}

function switchUserTab(tabId) {
  document.querySelectorAll(".user-tab").forEach((el) => el.classList.add("hidden"));
  const target = document.getElementById(`tab-${tabId}`);
  if (target) target.classList.remove("hidden");

  document.querySelectorAll(".user-nav-btn").forEach((btn) => {
    if (btn.dataset.tab === tabId) {
      btn.className = "user-nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 transition";
    } else {
      btn.className = "user-nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition";
    }
  });

  const titleEl = document.getElementById("activeUserTabTitle");
  if (titleEl && tabTitles[tabId]) titleEl.textContent = tabTitles[tabId];

  const mobileSelect = document.getElementById("mobileTabSelect");
  if (mobileSelect && mobileSelect.value !== tabId) mobileSelect.value = tabId;
}

window.switchUserTab = switchUserTab;

function populateUserIdentity(user) {
  if (!user) return;
  currentUser = user;

  const initials = (user.full_name || user.username || "U").charAt(0).toUpperCase();
  const color = user.avatar_color || "#6366f1";

  const avatar = document.getElementById("sidebarUserAvatar");
  if (avatar) {
    avatar.textContent = initials;
    avatar.style.backgroundColor = color;
  }

  const sName = document.getElementById("sidebarUserName");
  if (sName) sName.textContent = user.full_name || user.username;

  const sPlan = document.getElementById("sidebarUserPlan");
  if (sPlan) sPlan.textContent = user.plan_tier || "Pro Studio";

  const wPlan = document.getElementById("welcomePlanBadge");
  if (wPlan) wPlan.textContent = `${user.plan_tier || "Pro Studio"} Member`;

  const wHead = document.getElementById("welcomeHeading");
  if (wHead) wHead.textContent = `Welcome back, ${user.full_name || user.username}!`;

  const hBadge = document.getElementById("headerUsernameBadge");
  if (hBadge) hBadge.textContent = `@${user.username}`;

  // Profile Hero Card Elements
  const heroAvatar = document.getElementById("profAvatarPreview");
  if (heroAvatar) {
    heroAvatar.textContent = initials;
    heroAvatar.style.backgroundColor = color;
  }
  const heroName = document.getElementById("profHeroName");
  if (heroName) heroName.textContent = user.full_name || user.username;
  const heroUser = document.getElementById("profHeroUsername");
  if (heroUser) heroUser.textContent = `@${user.username}`;
  const heroBio = document.getElementById("profHeroBio");
  if (heroBio) heroBio.textContent = user.bio || "Manage your personal identity, studio preferences, account security, and cloud storage.";
  const heroMember = document.getElementById("profMemberSince");
  if (heroMember) heroMember.textContent = user.created_at ? `Member since ${user.created_at.split(" ")[0]}` : "Member of PngLike Studio";
  const heroLogin = document.getElementById("profLastLogin");
  if (heroLogin) heroLogin.textContent = user.last_login ? `Last login: ${user.last_login.split(" ")[0]}` : "Active Now";
  const heroPlan = document.getElementById("profPlanBadge");
  if (heroPlan) heroPlan.textContent = `${user.plan_tier || "Pro Studio"} Member`;

  // Profile Form Fields
  const pUser = document.getElementById("profUsername");
  if (pUser) pUser.value = user.username || "";
  const pFull = document.getElementById("profFullName");
  if (pFull) pFull.value = user.full_name || "";
  const pEmail = document.getElementById("profEmail");
  if (pEmail) pEmail.value = user.email || "";
  const pBio = document.getElementById("profBio");
  if (pBio) pBio.value = user.bio || "";
  const pPhone = document.getElementById("profPhone");
  if (pPhone) pPhone.value = user.phone || "";
  const pCountry = document.getElementById("profCountry");
  if (pCountry) pCountry.value = user.country || "";
  const pFormat = document.getElementById("profPreferredFormat");
  if (pFormat) pFormat.value = user.preferred_format || "png";
  const pDark = document.getElementById("profDarkModePref");
  if (pDark) pDark.value = user.dark_mode_pref || "system";
  const pColor = document.getElementById("profAvatarColor");
  if (pColor) pColor.value = color;
  const pColorHex = document.getElementById("profAvatarColorHex");
  if (pColorHex) pColorHex.textContent = color;

  const delTarget = document.getElementById("deleteConfirmTarget");
  if (delTarget) delTarget.textContent = `delete ${user.username}`;
}

function renderRecentOverview(jobs) {
  const container = document.getElementById("overviewRecentGrid");
  if (!container) return;

  if (!jobs || jobs.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-10 text-center text-slate-400">
        <p class="text-xs font-semibold mb-2">No processed images in your personal history yet.</p>
        <a href="/" class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition">
          <span>Process Your First Image</span>
        </a>
      </div>
    `;
    return;
  }

  container.innerHTML = jobs
    .slice(0, 6)
    .map(
      (j) => {
        const imgUrl = j.output_url || j.result_url || "";
        const fname = j.original_filename || j.filename || "cutout.png";
        const mdl = j.model_used || j.model || "u2net";
        return `
      <div class="group relative rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-slate-50 dark:bg-slate-800/40 flex flex-col">
        <div class="aspect-square checkerboard flex items-center justify-center p-2 overflow-hidden">
          <img src="${escapeHtml(imgUrl)}" alt="${escapeHtml(fname)}" class="max-h-full max-w-full object-contain group-hover:scale-105 transition">
        </div>
        <div class="p-2.5 flex items-center justify-between gap-2 bg-white dark:bg-dark-900 border-t border-slate-200/70 dark:border-slate-800">
          <div class="min-w-0">
            <p class="text-[11px] font-bold truncate">${escapeHtml(fname)}</p>
            <p class="text-[10px] text-slate-400 truncate">${escapeHtml(mdl)} • ${j.process_time_ms}ms</p>
          </div>
          <a href="${escapeHtml(imgUrl)}" download="${escapeHtml(j.output_filename || fname)}" class="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 shrink-0" title="Download">
            <i data-lucide="download" class="w-3.5 h-3.5"></i>
          </a>
        </div>
      </div>
    `;
      }
    )
    .join("");
  safeCreateIcons();
}

function renderModelBreakdown(breakdown, totalJobs) {
  const container = document.getElementById("userModelBreakdown");
  if (!container) return;
  const entries = Object.entries(breakdown || {});
  if (entries.length === 0) {
    container.innerHTML = `<p class="text-slate-400 text-xs py-6 text-center">Run any AI tool to see your model telemetry here.</p>`;
    return;
  }

  container.innerHTML = entries
    .sort((a, b) => b[1] - a[1])
    .map(([model, count]) => {
      const pct = totalJobs > 0 ? Math.round((count / totalJobs) * 100) : 0;
      return `
        <div class="space-y-1">
          <div class="flex justify-between text-xs">
            <span class="font-semibold text-slate-700 dark:text-slate-300 truncate">${escapeHtml(model)}</span>
            <span class="font-mono text-slate-500">${count} (${pct}%)</span>
          </div>
          <div class="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-indigo-500 to-blue-500 rounded-full" style="width: ${Math.max(pct, 6)}%"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderUserGallery(jobs) {
  const container = document.getElementById("userGalleryGrid");
  if (!container) return;

  const q = (document.getElementById("userGallerySearch")?.value || "").trim().toLowerCase();
  const filtered = (jobs || []).filter(
    (j) =>
      !q ||
      (j.original_filename || j.filename || "").toLowerCase().includes(q) ||
      (j.model_used || j.model || "").toLowerCase().includes(q)
  );

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-400">
        <p class="text-sm font-semibold mb-1">No matching creations found.</p>
        <p class="text-xs">Process images in the <a href="/" class="text-indigo-500 underline">AI Image Studio</a> while signed in to build your personal gallery.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered
    .map(
      (j) => {
        const imgUrl = j.output_url || j.result_url || "";
        const fname = j.original_filename || j.filename || "cutout.png";
        const mdl = j.model_used || j.model || "u2net";
        const w = j.original_width || j.width || 0;
        const h = j.original_height || j.height || 0;
        return `
      <div class="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-dark-900 shadow-sm flex flex-col justify-between">
        <div class="aspect-square checkerboard flex items-center justify-center p-3 overflow-hidden relative group">
          <img src="${escapeHtml(imgUrl)}" alt="${escapeHtml(fname)}" class="max-h-full max-w-full object-contain group-hover:scale-105 transition">
          <span class="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md bg-slate-900/75 text-white text-[10px] font-mono">
            ${escapeHtml((j.output_format || "PNG").toUpperCase())}
          </span>
        </div>
        <div class="p-3.5 space-y-2 border-t border-slate-200/70 dark:border-slate-800">
          <div>
            <p class="text-xs font-bold truncate" title="${escapeHtml(fname)}">${escapeHtml(fname)}</p>
            <p class="text-[11px] text-slate-400">${escapeHtml(mdl)} • ${w}×${h} • ${j.process_time_ms}ms</p>
          </div>
          <div class="flex items-center justify-between gap-2 pt-1">
            <a href="${escapeHtml(imgUrl)}" download="${escapeHtml(j.output_filename || fname)}" class="flex-1 py-1.5 px-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold flex items-center justify-center gap-1.5 transition">
              <i data-lucide="download" class="w-3.5 h-3.5"></i>
              <span>Download</span>
            </a>
            <button type="button" onclick="deleteUserJobItem(${j.id})" class="p-1.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 text-rose-500 transition" title="Delete from my history">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      </div>
    `;
      }
    )
    .join("");
  safeCreateIcons();
}

async function deleteUserJobItem(jobId) {
  try {
    const res = await userFetch(`/api/user/jobs/${jobId}`, { method: "DELETE" });
    if (res.ok) {
      await loadUserDashboard();
    }
  } catch (err) {
    console.error(err);
  }
}

window.deleteUserJobItem = deleteUserJobItem;

async function loadUserDashboard() {
  if (!userToken) {
    document.getElementById("userAuthOverlay")?.classList.remove("hidden");
    return;
  }

  try {
    const res = await userFetch("/api/user/dashboard");
    if (!res.ok) throw new Error("Failed to load dashboard");
    const data = await res.json();

    document.getElementById("userAuthOverlay")?.classList.add("hidden");
    populateUserIdentity(data.user);

    const stats = data.stats || {};
    document.getElementById("kpiUserTotalJobs").textContent = stats.total_jobs ?? 0;
    document.getElementById("kpiUserAvgTime").textContent = `${stats.avg_process_time_ms ?? 0} ms`;
    document.getElementById("kpiUserStorage").textContent = `${stats.total_storage_mb ?? 0} MB`;
    document.getElementById("kpiUserFavModel").textContent = stats.favorite_model || "isnet-general-use";

    userJobsCache = data.jobs || [];
    renderRecentOverview(userJobsCache);
    renderModelBreakdown(stats.model_breakdown || {}, stats.total_jobs || 0);
    renderUserGallery(userJobsCache);
  } catch (err) {
    console.warn("Auth check / dashboard load:", err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  safeCreateIcons();

  // Check URL query/hash for ?mode=register
  if (window.location.search.includes("register") || window.location.hash === "#register") {
    switchAuthMode("register");
  }

  document.getElementById("tabBtnLogin")?.addEventListener("click", () => switchAuthMode("login"));
  document.getElementById("tabBtnRegister")?.addEventListener("click", () => switchAuthMode("register"));

  // Sidebar navigation
  document.querySelectorAll(".user-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchUserTab(btn.dataset.tab));
  });
  document.getElementById("mobileTabSelect")?.addEventListener("change", (e) => {
    switchUserTab(e.target.value);
  });

  // Theme toggle
  document.getElementById("themeToggleBtn")?.addEventListener("click", () => {
    document.documentElement.classList.toggle("dark");
  });

  // Refresh button
  document.getElementById("refreshDashboardBtn")?.addEventListener("click", () => {
    loadUserDashboard();
  });

  // Gallery search filter
  document.getElementById("userGallerySearch")?.addEventListener("input", () => {
    renderUserGallery(userJobsCache);
  });

  // 1-Click Demo Login
  document.getElementById("quickDemoLoginBtn")?.addEventListener("click", () => {
    document.getElementById("loginIdentifier").value = "demo";
    document.getElementById("loginPassword").value = "user123";
    document.getElementById("userLoginForm").requestSubmit();
  });

  // Sign In Submit
  document.getElementById("userLoginForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthAlert();
    const identifier = document.getElementById("loginIdentifier").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 403) {
          // Account not active yet (requires email verification)
          if (identifier.includes("@")) {
            pendingVerificationEmail = identifier;
          }
          switchAuthMode("verify");
          showAuthAlert(data.detail || "Your account is not active yet. Please enter your 6-digit verification code to activate it.");
          return;
        }
        showAuthAlert(data.detail || "Invalid login credentials");
        return;
      }
      userToken = data.token;
      localStorage.setItem("rembg_user_token", userToken);
      document.getElementById("userAuthOverlay")?.classList.add("hidden");
      await loadUserDashboard();
    } catch (err) {
      showAuthAlert("Network error while signing in.");
    }
  });

  // --------------------------------------------------------
  // REAL-TIME REGISTRATION SECURITY CHECKERS
  // --------------------------------------------------------
  const regEmailInput = document.getElementById("regEmail");
  const regPwInput = document.getElementById("regPassword");
  const emailWarnBox = document.getElementById("regEmailSecurityWarning");
  const emailWarnText = document.getElementById("regEmailWarningText");

  const DISPOSABLE_DOMAINS = [
    "tempmail.com", "10minutemail.com", "mailinator.com", "guerrillamail.com",
    "yopmail.com", "trashmail.com", "sharklasers.com", "throwawaymail.com",
    "dispostable.com", "temp-mail.org", "maildrop.cc", "nada.ltd"
  ];

  if (regEmailInput) {
    regEmailInput.addEventListener("input", () => {
      const val = regEmailInput.value.trim().toLowerCase();
      if (!val) {
        emailWarnBox?.classList.add("hidden");
        return;
      }

      // Plus addressing check (name+1@domain.com)
      if (val.includes("+") || val.includes("%2b")) {
        if (emailWarnBox && emailWarnText) {
          emailWarnText.textContent = "Email aliases and sub-addressing (e.g. name+1@domain.com) are rejected for account security. Please use your standard email.";
          emailWarnBox.classList.remove("hidden");
        }
        return;
      }

      // Disposable email domain check
      const atIdx = val.indexOf("@");
      if (atIdx !== -1) {
        const domain = val.slice(atIdx + 1);
        if (DISPOSABLE_DOMAINS.some(d => domain.includes(d))) {
          if (emailWarnBox && emailWarnText) {
            emailWarnText.textContent = "Disposable / temporary email domains are not permitted. Please use a permanent email address.";
            emailWarnBox.classList.remove("hidden");
          }
          return;
        }
      }

      emailWarnBox?.classList.add("hidden");
    });
  }

  if (regPwInput) {
    regPwInput.addEventListener("input", () => {
      const pw = regPwInput.value;
      const hasLen = pw.length >= 8;
      const hasUpper = /[A-Z]/.test(pw);
      const hasLower = /[a-z]/.test(pw);
      const hasNum = /[0-9]/.test(pw);
      const hasSpec = /[!@#$%^&*(),.?":{}|<>\-_+=\[\]\\/`~;']/.test(pw);
      const hasNumAndSpec = hasNum && hasSpec;

      const updateRule = (elId, passed) => {
        const el = document.getElementById(elId);
        if (!el) return;
        el.className = passed
          ? "flex items-center gap-1 text-emerald-500 font-semibold"
          : "flex items-center gap-1 text-slate-400";
        const icon = el.querySelector("i");
        if (icon) {
          icon.setAttribute("data-lucide", passed ? "check-circle-2" : "circle");
        }
      };

      updateRule("chkLen", hasLen);
      updateRule("chkUpper", hasUpper);
      updateRule("chkLower", hasLower);
      updateRule("chkNumSpec", hasNumAndSpec);
      safeCreateIcons();

      let score = 0;
      if (hasLen) score += 1;
      if (hasUpper) score += 1;
      if (hasLower) score += 1;
      if (hasNum) score += 1;
      if (hasSpec) score += 1;

      const bar = document.getElementById("pwStrengthBar");
      const lbl = document.getElementById("pwStrengthLabel");

      if (!pw) {
        if (bar) bar.style.width = "0%";
        if (lbl) {
          lbl.textContent = "Empty";
          lbl.className = "font-bold text-slate-400";
        }
      } else if (score <= 2) {
        if (bar) {
          bar.style.width = "30%";
          bar.className = "h-full transition-all duration-300 rounded-full bg-rose-500";
        }
        if (lbl) {
          lbl.textContent = "Weak";
          lbl.className = "font-bold text-rose-500";
        }
      } else if (score === 3 || score === 4) {
        if (bar) {
          bar.style.width = "65%";
          bar.className = "h-full transition-all duration-300 rounded-full bg-amber-500";
        }
        if (lbl) {
          lbl.textContent = "Moderate";
          lbl.className = "font-bold text-amber-500";
        }
      } else {
        if (bar) {
          bar.style.width = "100%";
          bar.className = "h-full transition-all duration-300 rounded-full bg-emerald-500";
        }
        if (lbl) {
          lbl.textContent = "Strong";
          lbl.className = "font-bold text-emerald-500";
        }
      }
    });
  }

  // Register Submit
  document.getElementById("userRegisterForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthAlert();
    const username = document.getElementById("regUsername").value.trim();
    const full_name = document.getElementById("regFullName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const password = document.getElementById("regPassword").value;
    const honeypot = document.getElementById("regHoneypot")?.value || "";

    // Client-side instant pre-flight checks
    if (email.includes("+") || email.includes("%2b")) {
      showAuthAlert("Email aliases and sub-addressing (e.g. name+1@domain.com) are rejected. Please use your standard email.");
      return;
    }
    if (password.length < 8) {
      showAuthAlert("Password must be at least 8 characters long.");
      return;
    }
    if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
      showAuthAlert("Password must contain uppercase, lowercase, and a number.");
      return;
    }
    if (!/[!@#$%^&*(),.?":{}|<>\-_+=\[\]\\/`~;']/.test(password)) {
      showAuthAlert("Password must contain at least one special character (!@#$%^&*...).");
      return;
    }

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          email,
          password,
          full_name,
          website: honeypot
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        showAuthAlert(data.detail || "Could not create account.");
        return;
      }

      pendingVerificationEmail = data.email || email;
      switchAuthMode("verify");

      // Handle dev mode code preview
      const devBanner = document.getElementById("verifyDevBanner");
      const devPill = document.getElementById("verifyDevCodePill");
      if (data.dev_code && devBanner && devPill) {
        devPill.textContent = data.dev_code;
        devBanner.classList.remove("hidden");
        const fillCode = () => {
          const codeInput = document.getElementById("verifyCodeInput");
          if (codeInput) codeInput.value = data.dev_code;
        };
        document.getElementById("verifyDevAutoFillBtn")?.replaceWith(document.getElementById("verifyDevAutoFillBtn").cloneNode(true));
        document.getElementById("verifyDevAutoFillBtn")?.addEventListener("click", fillCode);
        devPill.replaceWith(devPill.cloneNode(true));
        document.getElementById("verifyDevCodePill")?.addEventListener("click", fillCode);
      } else if (devBanner) {
        devBanner.classList.add("hidden");
      }

      showAuthAlert(
        data.message || `Account created! We've sent a 6-digit code to ${pendingVerificationEmail}. Please enter it below to activate your account.`,
        false
      );
    } catch (err) {
      showAuthAlert("Network error while creating account.");
    }
  });

  // Verify Code Submit
  document.getElementById("userVerifyForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthAlert();
    const code = document.getElementById("verifyCodeInput").value.trim();
    if (!code) {
      showAuthAlert("Please enter your 6-digit verification code.");
      return;
    }
    if (!pendingVerificationEmail) {
      const promptEmail = prompt("Please confirm your email address:", "");
      if (!promptEmail) return;
      pendingVerificationEmail = promptEmail.trim();
    }

    try {
      const res = await fetch("/api/auth/verify-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: pendingVerificationEmail, code }),
      });
      const data = await res.json();
      if (!res.ok) {
        showAuthAlert(data.detail || "Invalid or expired verification code.");
        return;
      }

      userToken = data.token;
      localStorage.setItem("rembg_user_token", userToken);
      document.getElementById("userAuthOverlay")?.classList.add("hidden");
      await loadUserDashboard();
    } catch (err) {
      showAuthAlert("Network error while verifying code.");
    }
  });

  // Resend Verification Code
  document.getElementById("verifyResendBtn")?.addEventListener("click", async () => {
    hideAuthAlert();
    if (!pendingVerificationEmail) {
      const promptEmail = prompt("Please confirm your email address to resend the code:", "");
      if (!promptEmail) return;
      pendingVerificationEmail = promptEmail.trim();
    }

    try {
      const res = await fetch("/api/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: pendingVerificationEmail }),
      });
      const data = await res.json();
      if (!res.ok) {
        showAuthAlert(data.detail || "Could not resend code. Please try again.");
        return;
      }

      const devBanner = document.getElementById("verifyDevBanner");
      const devPill = document.getElementById("verifyDevCodePill");
      if (data.dev_code && devBanner && devPill) {
        devPill.textContent = data.dev_code;
        devBanner.classList.remove("hidden");
      }
      showAuthAlert(data.message || `A fresh 6-digit code was sent to ${pendingVerificationEmail}`, false);
    } catch (err) {
      showAuthAlert("Network error while requesting a new code.");
    }
  });

  // Back to Sign In
  document.getElementById("verifyBackToSignInBtn")?.addEventListener("click", () => {
    switchAuthMode("login");
  });

  // Logout
  document.getElementById("userLogoutBtn")?.addEventListener("click", async () => {
    try {
      await userFetch("/api/auth/logout", { method: "POST" });
    } catch (_) {}
    localStorage.removeItem("rembg_user_token");
    userToken = "";
    currentUser = null;
    document.getElementById("userAuthOverlay")?.classList.remove("hidden");
  });

  // Clear all personal jobs
  document.getElementById("clearUserJobsBtn")?.addEventListener("click", async () => {
    if (!confirm("Clear all processed images from your personal history?")) return;
    try {
      const res = await userFetch("/api/user/jobs", { method: "DELETE" });
      if (res.ok) await loadUserDashboard();
    } catch (err) {
      console.error(err);
    }
  });

  // Avatar theme color picker & live preview
  function updateAvatarColor(col) {
    if (!col) return;
    const colorInput = document.getElementById("profAvatarColor");
    if (colorInput) colorInput.value = col;
    const hex = document.getElementById("profAvatarColorHex");
    if (hex) hex.textContent = col;
    const preview = document.getElementById("profAvatarPreview");
    if (preview) preview.style.backgroundColor = col;
    const sidebar = document.getElementById("sidebarUserAvatar");
    if (sidebar) sidebar.style.backgroundColor = col;
  }

  document.getElementById("profAvatarColor")?.addEventListener("input", (e) => {
    updateAvatarColor(e.target.value);
  });

  document.querySelectorAll(".prof-color-swatch").forEach((btn) => {
    btn.addEventListener("click", () => {
      const col = btn.getAttribute("data-color");
      updateAvatarColor(col);
    });
  });

  // Password visibility toggle
  document.querySelectorAll(".toggle-password-visibility").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const input = document.getElementById(targetId);
      if (!input) return;
      const isPw = input.type === "password";
      input.type = isPw ? "text" : "password";
    });
  });

  // Real-time password criteria checklist
  function updatePasswordChecklist(val) {
    const lenPass = val.length >= 8;
    const upPass = /[A-Z]/.test(val);
    const numPass = /[0-9]/.test(val);
    const symPass = /[^A-Za-z0-9]/.test(val);

    const toggleReq = (elId, pass) => {
      const el = document.getElementById(elId);
      if (!el) return;
      if (pass) {
        el.className = "flex items-center gap-1.5 text-emerald-500 font-bold";
      } else {
        el.className = "flex items-center gap-1.5 text-slate-400 font-normal";
      }
    };

    toggleReq("pwReqLen", lenPass);
    toggleReq("pwReqUpper", upPass);
    toggleReq("pwReqNum", numPass);
    toggleReq("pwReqSym", symPass);
  }

  document.getElementById("profNewPassword")?.addEventListener("input", (e) => {
    updatePasswordChecklist(e.target.value);
  });

  // Save Profile Changes
  document.getElementById("userProfileForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const full_name = document.getElementById("profFullName")?.value.trim() || "";
    const email = document.getElementById("profEmail")?.value.trim() || "";
    const avatar_color = document.getElementById("profAvatarColor")?.value || "#6366f1";
    const bio = document.getElementById("profBio")?.value.trim() || "";
    const phone = document.getElementById("profPhone")?.value.trim() || "";
    const country = document.getElementById("profCountry")?.value.trim() || "";
    const preferred_format = document.getElementById("profPreferredFormat")?.value || "png";
    const dark_mode_pref = document.getElementById("profDarkModePref")?.value || "system";
    const current_password = document.getElementById("profCurrentPassword")?.value || "";
    const new_password = document.getElementById("profNewPassword")?.value || "";
    const confirm_password = document.getElementById("profConfirmPassword")?.value || "";

    const errEl = document.getElementById("profErrorStatus");
    const errMsg = document.getElementById("profErrorMsg");
    const statusEl = document.getElementById("profSaveStatus");
    if (errEl) errEl.classList.add("hidden");
    if (statusEl) statusEl.classList.add("hidden");

    if (new_password) {
      if (new_password !== confirm_password) {
        if (errEl && errMsg) {
          errMsg.textContent = "New password and confirmation password do not match.";
          errEl.classList.remove("hidden");
        }
        return;
      }
      if (!current_password) {
        if (errEl && errMsg) {
          errMsg.textContent = "Current password is required to change password.";
          errEl.classList.remove("hidden");
        }
        return;
      }
    }

    const payload = {
      full_name,
      email,
      avatar_color,
      bio,
      phone,
      country,
      preferred_format,
      dark_mode_pref,
    };
    if (new_password) {
      payload.new_password = new_password;
      payload.current_password = current_password;
    }

    try {
      const res = await userFetch("/api/user/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        if (errEl && errMsg) {
          errMsg.textContent = data.detail || "Failed to update profile";
          errEl.classList.remove("hidden");
        }
        return;
      }
      const curPw = document.getElementById("profCurrentPassword");
      const newPw = document.getElementById("profNewPassword");
      const confPw = document.getElementById("profConfirmPassword");
      if (curPw) curPw.value = "";
      if (newPw) newPw.value = "";
      if (confPw) confPw.value = "";
      updatePasswordChecklist("");
      populateUserIdentity(data.user);

      if (statusEl) {
        statusEl.classList.remove("hidden");
        setTimeout(() => statusEl.classList.add("hidden"), 4000);
      }
      safeCreateIcons();
    } catch (err) {
      if (errEl && errMsg) {
        errMsg.textContent = err.message || "Network error updating profile";
        errEl.classList.remove("hidden");
      }
    }
  });

  // Export Account Data (JSON)
  document.getElementById("exportUserDataBtn")?.addEventListener("click", async () => {
    try {
      const res = await userFetch("/api/user/export");
      if (!res.ok) throw new Error("Could not export account data");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pnglike_account_${currentUser?.username || "profile"}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message);
    }
  });

  // Delete Account Modal & Confirmation
  const delModal = document.getElementById("deleteAccountModal");
  document.getElementById("openDeleteAccountModalBtn")?.addEventListener("click", () => {
    if (delModal) delModal.classList.remove("hidden");
  });
  document.getElementById("closeDeleteAccountModalBtn")?.addEventListener("click", () => {
    if (delModal) delModal.classList.add("hidden");
  });
  document.getElementById("deleteAccountForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const confirmPhrase = document.getElementById("deleteConfirmPhraseInput").value.trim();
    const password = document.getElementById("deleteAccountPassword").value;
    try {
      const res = await userFetch("/api/user/delete-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_phrase: confirmPhrase, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "Account deletion failed");
        return;
      }
      localStorage.removeItem("rembg_user_token");
      alert("Your account and personal image history have been permanently deleted.");
      window.location.href = "/";
    } catch (err) {
      alert(err.message || "Failed to delete account");
    }
  });

  // Handle 1-click email token verification or direct mode parameter
  const urlParams = new URLSearchParams(window.location.search);
  const verifyToken = urlParams.get("token") || urlParams.get("verify_token");
  if (verifyToken) {
    (async () => {
      try {
        const res = await fetch(`/api/auth/verify?token=${encodeURIComponent(verifyToken)}`);
        const data = await res.json();
        if (res.ok && data.token) {
          userToken = data.token;
          localStorage.setItem("rembg_user_token", userToken);
          window.history.replaceState({}, document.title, window.location.pathname);
          document.getElementById("userAuthOverlay")?.classList.add("hidden");
          await loadUserDashboard();
          return;
        } else {
          showAuthAlert(data.detail || "Verification link is invalid or has expired.");
          switchAuthMode("verify");
        }
      } catch (err) {
        showAuthAlert("Could not process verification link.");
      }
    })();
  } else if (urlParams.get("mode") === "register" || window.location.pathname === "/register") {
    switchAuthMode("register");
  } else if (urlParams.get("mode") === "verify") {
    switchAuthMode("verify");
  }

  // Initial load
  loadUserDashboard();
});
