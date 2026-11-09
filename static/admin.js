// PngLike Admin Portal Client Logic
document.addEventListener("DOMContentLoaded", () => {
  let adminToken = localStorage.getItem("pnglike_admin_token") || localStorage.getItem("rembg_admin_token") || "";
  function safeCreateIcons() {
    try {
      if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.safeCreateIcons();
      }
    } catch (_) {}
  }

  // DOM References
  const loginOverlay = document.getElementById("loginOverlay");
  const loginForm = document.getElementById("loginForm");
  const loginUsername = document.getElementById("loginUsername");
  const loginPassword = document.getElementById("loginPassword");
  const loginErrorMsg = document.getElementById("loginErrorMsg");
  const logoutBtn = document.getElementById("logoutBtn");
  const adminUserLabel = document.getElementById("adminUserLabel");
  const pageHeaderTitle = document.getElementById("pageHeaderTitle");
  const headerDbBadge = document.getElementById("headerDbBadge");

  // Initialize Theme & Session
  initTheme();
  setupNavigation();
  setupEventListeners();
  verifyExistingSession();

  async function safeJsonFromRes(res) {
    if (!res) return {};
    try {
      const text = await res.text();
      const trimmed = (text || "").trim();
      if (!trimmed || trimmed.startsWith("<")) return {};
      return JSON.parse(trimmed);
    } catch (_) {
      return {};
    }
  }

  async function adminFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers || {}, {
      "X-Admin-Token": adminToken,
    });
    const res = await fetch(url, Object.assign({}, options, { headers }));
    if (res.status === 401) {
      loginOverlay.classList.remove("hidden");
      throw new Error("Admin session expired. Please sign in.");
    }
    // Wrap res.json to protect against HTML 404/500/Cloudflare responses
    res.json = async () => await safeJsonFromRes(res);
    return res;
  }

  async function verifyExistingSession() {
    if (!adminToken) {
      loginOverlay.classList.remove("hidden");
      return;
    }
    try {
      const res = await adminFetch("/api/admin/me");
      if (!res.ok) throw new Error("Invalid token");
      const data = await res.json();
      onLoginSuccess(data.admin);
    } catch (e) {
      loginOverlay.classList.remove("hidden");
    }
  }

  function onLoginSuccess(admin) {
    loginOverlay.classList.add("hidden");
    adminUserLabel.innerText = "@" + (admin.username || "admin");
    document.getElementById("admNewUsername").value = admin.username || "admin";
    loadAdminProfile(true);
    loadOverview();
  }

  function setupNavigation() {
    const tabTitles = {
      overview: "Overview & Analytics",
      cms: "Frontend CMS & Feature Flags",
      blog: "Blog & Tutorials Manager",
      indexnow: "IndexNow & Real-Time Search Engine Indexing",
      users: "Users & Subscriptions Manager",
      models: "AI Models & RAM Cache Manager",
      samples: "Sample Gallery Manager",
      presets: "MySQL Workflow Presets",
      jobs: "Jobs & Storage Moderation",
      database: "MySQL Connection & Admin Security",
      profile: "Admin Profile & Security Center",
    };

    function closeAdminMobileDrawer() {
      const sidebar = document.getElementById("adminSidebar");
      const backdrop = document.getElementById("adminMobileBackdrop");
      if (sidebar) sidebar.classList.add("-translate-x-full");
      if (backdrop) backdrop.classList.add("hidden");
    }

    function openAdminMobileDrawer() {
      const sidebar = document.getElementById("adminSidebar");
      const backdrop = document.getElementById("adminMobileBackdrop");
      if (sidebar) sidebar.classList.remove("-translate-x-full");
      if (backdrop) backdrop.classList.remove("hidden");
    }

    document.getElementById("adminMobileMenuBtn")?.addEventListener("click", openAdminMobileDrawer);
    document.getElementById("adminMobileCloseBtn")?.addEventListener("click", closeAdminMobileDrawer);
    document.getElementById("adminMobileBackdrop")?.addEventListener("click", closeAdminMobileDrawer);

    document.querySelectorAll(".admin-nav-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        closeAdminMobileDrawer();
        const tab = btn.getAttribute("data-tab");
        pageHeaderTitle.innerText = tabTitles[tab] || "Admin Dashboard";

        document.querySelectorAll(".admin-nav-btn").forEach(b => {
          b.className = "admin-nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition";
        });
        btn.className = "admin-nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 transition";

        document.querySelectorAll(".admin-section").forEach(sec => sec.classList.add("hidden"));
        const targetSection = document.getElementById(`tab-${tab}`);
        if (targetSection) targetSection.classList.remove("hidden");

        if (tab === "overview") loadOverview();
        if (tab === "cms") loadCmsSettings();
        if (tab === "blog") loadAdminBlog();
        if (tab === "indexnow") loadIndexNowTab();
        if (tab === "users") loadAdminUsers();
        if (tab === "models") loadAdminModels();
        if (tab === "samples") loadAdminSamples();
        if (tab === "presets") loadAdminPresets();
        if (tab === "jobs") loadAdminJobs();
        if (tab === "database") loadDatabaseTab();
        if (tab === "profile") loadAdminProfile();
        setTimeout(() => {
          if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
          }
        }, 50);
      });
    });

    // Quick navigation triggers to Profile tab
    const sidebarProfileBtn = document.getElementById("adminSidebarProfileBtn");
    if (sidebarProfileBtn) {
      sidebarProfileBtn.addEventListener("click", () => {
        const profBtn = document.querySelector('[data-tab="profile"]');
        if (profBtn) profBtn.click();
      });
    }

    const headerProfileBtn = document.getElementById("adminHeaderProfileBtn");
    if (headerProfileBtn) {
      headerProfileBtn.addEventListener("click", () => {
        const profBtn = document.querySelector('[data-tab="profile"]');
        if (profBtn) profBtn.click();
      });
    }
  }

  function setupEventListeners() {
    // Login Submit
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      loginErrorMsg.classList.add("hidden");
      try {
        const res = await fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: loginUsername.value.trim(),
            password: loginPassword.value,
          }),
        });
        const data = await safeJsonFromRes(res);
        if (!res.ok) throw new Error(data.detail || (res.status === 404 ? "Admin API service not found (404)." : "Login failed"));
        adminToken = data.token;
        localStorage.setItem("rembg_admin_token", adminToken);
        onLoginSuccess(data.admin);
        showToast(`Welcome back, ${data.admin.username}!`, "success");
      } catch (err) {
        loginErrorMsg.innerText = err.message;
        loginErrorMsg.classList.remove("hidden");
      }
    });

    // Logout
    logoutBtn.addEventListener("click", async () => {
      try {
        await adminFetch("/api/admin/logout", { method: "POST" });
      } catch (e) {}
      adminToken = "";
      localStorage.removeItem("rembg_admin_token");
      loginOverlay.classList.remove("hidden");
      showToast("Signed out of Admin Portal.", "info");
    });

    document.getElementById("overviewRefreshBtn").addEventListener("click", loadOverview);
    document.getElementById("saveCmsBtn").addEventListener("click", saveCmsSettings);

    // Sample Upload
    document.getElementById("uploadSampleForm").addEventListener("submit", handleUploadSample);

    // Preset Create
    document.getElementById("createPresetForm").addEventListener("submit", handleCreatePreset);

    // Jobs Moderation
    document.getElementById("jobsFilterBtn").addEventListener("click", loadAdminJobs);
    document.getElementById("purgeAllJobsBtn").addEventListener("click", handlePurgeAllJobs);

    // MySQL & Security
    document.getElementById("admSaveDbBtn")?.addEventListener("click", handleSaveMySQLConfig);
    document.getElementById("admUpdateCredsBtn")?.addEventListener("click", handleUpdateAdminCreds);
    document.getElementById("admSaveSmtpBtn")?.addEventListener("click", handleSaveSmtpSettings);
    document.getElementById("admTestSmtpBtn")?.addEventListener("click", handleTestSmtpConnection);

    // Blog Manager Listeners
    const blogEditorForm = document.getElementById("blogEditorForm");
    if (blogEditorForm) {
      blogEditorForm.addEventListener("submit", handleSaveBlogPost);
    }
    const blogCancelEditBtn = document.getElementById("blogCancelEditBtn");
    if (blogCancelEditBtn) {
      blogCancelEditBtn.addEventListener("click", resetBlogEditorForm);
    }
    const adminBlogFilterBtn = document.getElementById("adminBlogFilterBtn");
    if (adminBlogFilterBtn) {
      adminBlogFilterBtn.addEventListener("click", loadAdminBlog);
    }
    const blogTitleInput = document.getElementById("blogTitleInput");
    const blogSlugInput = document.getElementById("blogSlugInput");
    if (blogTitleInput && blogSlugInput) {
      blogTitleInput.addEventListener("input", () => {
        const editId = document.getElementById("blogEditPostId").value;
        if (!editId) {
          blogSlugInput.value = blogTitleInput.value
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, "")
            .trim()
            .replace(/[\s_-]+/g, "-");
        }
      });
    }
    const blogCoverFileInput = document.getElementById("blogCoverFileInput");
    if (blogCoverFileInput) {
      blogCoverFileInput.addEventListener("change", handleBlogCoverUpload);
    }
    document.querySelectorAll(".blog-fmt-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const tagType = btn.getAttribute("data-blog-tag");
        insertBlogFormattingSnippet(tagType);
      });
    });

    // Admin Profile & Security Center Listeners
    const adminProfileForm = document.getElementById("adminProfileForm");
    if (adminProfileForm) {
      adminProfileForm.addEventListener("submit", handleSaveAdminProfile);
    }

    const adminPasswordForm = document.getElementById("adminPasswordForm");
    if (adminPasswordForm) {
      adminPasswordForm.addEventListener("submit", handleAdminPasswordChange);
    }

    const admNewPasswordInput = document.getElementById("admNewPasswordInput");
    if (admNewPasswordInput) {
      admNewPasswordInput.addEventListener("input", (e) => updatePasswordStrength(e.target.value));
    }

    const adminAvatarFileInput = document.getElementById("adminAvatarFileInput");
    if (adminAvatarFileInput) {
      adminAvatarFileInput.addEventListener("change", handleAdminAvatarUpload);
    }

    document.getElementById("profUploadPhotoBtn")?.addEventListener("click", () => {
      adminAvatarFileInput?.click();
    });

    document.getElementById("profAvatarContainer")?.addEventListener("click", () => {
      adminAvatarFileInput?.click();
    });

    document.getElementById("profRemovePhotoBtn")?.addEventListener("click", handleRemoveAdminAvatar);

    document.querySelectorAll(".prof-color-swatch").forEach(btn => {
      btn.addEventListener("click", () => {
        const color = btn.getAttribute("data-color");
        document.getElementById("profAvatarColor").value = color;
        document.querySelectorAll(".prof-color-swatch").forEach(b => b.classList.remove("ring-2", "ring-offset-2", "ring-indigo-500"));
        btn.classList.add("ring-2", "ring-offset-2", "ring-indigo-500");
        const heroAvatar = document.getElementById("profHeroAvatar");
        if (heroAvatar && !heroAvatar.querySelector("img")) {
          heroAvatar.style.backgroundColor = color;
        }
      });
    });

    document.getElementById("refreshSessionsBtn")?.addEventListener("click", loadAdminSessions);
    document.getElementById("revokeOtherSessionsBtn")?.addEventListener("click", handleRevokeOtherAdminSessions);
    document.getElementById("exportAdminProfileBtn")?.addEventListener("click", handleExportAdminProfile);

    // IndexNow Action Listeners
    document.getElementById("btnIndexNowSubmitAll")?.addEventListener("click", async () => {
      const btn = document.getElementById("btnIndexNowSubmitAll");
      const origText = btn.innerHTML;
      try {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Submitting...</span>`;
        safeCreateIcons();
        const res = await adminFetch("/api/admin/indexnow/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target: "sitemap" }),
        });
        const data = await res.json();
        showToast(data.message || `Submitted ${data.urls_count} URLs to IndexNow!`, data.success ? "success" : "error");
        loadIndexNowTab();
      } catch (e) {
        showToast(e.message, "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = origText;
        safeCreateIcons();
      }
    });

    document.getElementById("btnIndexNowSubmitHome")?.addEventListener("click", async () => {
      const btn = document.getElementById("btnIndexNowSubmitHome");
      const origText = btn.innerHTML;
      try {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Pinging...</span>`;
        safeCreateIcons();
        const res = await adminFetch("/api/admin/indexnow/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target: "home" }),
        });
        const data = await res.json();
        showToast(data.message || "Submitted Homepage to IndexNow!", data.success ? "success" : "error");
        loadIndexNowTab();
      } catch (e) {
        showToast(e.message, "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = origText;
        safeCreateIcons();
      }
    });

    document.getElementById("btnIndexNowSubmitBlog")?.addEventListener("click", async () => {
      const btn = document.getElementById("btnIndexNowSubmitBlog");
      const origText = btn.innerHTML;
      try {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Submitting...</span>`;
        safeCreateIcons();
        const res = await adminFetch("/api/admin/indexnow/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target: "blog" }),
        });
        const data = await res.json();
        showToast(data.message || "Submitted Blog posts to IndexNow!", data.success ? "success" : "error");
        loadIndexNowTab();
      } catch (e) {
        showToast(e.message, "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = origText;
        safeCreateIcons();
      }
    });

    document.getElementById("btnIndexNowSubmitCustom")?.addEventListener("click", async () => {
      const input = document.getElementById("idxCustomUrlsInput");
      const raw = (input?.value || "").trim();
      if (!raw) {
        showToast("Please enter at least one URL to submit.", "error");
        return;
      }
      const urls = raw.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
      const btn = document.getElementById("btnIndexNowSubmitCustom");
      const origText = btn.innerHTML;
      try {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Submitting...</span>`;
        safeCreateIcons();
        const res = await adminFetch("/api/admin/indexnow/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ urls: urls, triggered_by: "custom_input" }),
        });
        const data = await res.json();
        showToast(data.message || `Submitted ${urls.length} custom URL(s)!`, data.success ? "success" : "error");
        if (data.success && input) input.value = "";
        loadIndexNowTab();
      } catch (e) {
        showToast(e.message, "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = origText;
        safeCreateIcons();
      }
    });

    document.getElementById("indexNowConfigForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          indexnow_key: document.getElementById("idxConfigKey").value.trim(),
          indexnow_host: document.getElementById("idxConfigHost").value.trim(),
          indexnow_key_location: document.getElementById("idxConfigKeyLocation").value.trim(),
          indexnow_auto_submit_blog: document.getElementById("idxAutoBlogToggle").checked,
          indexnow_auto_submit_cms: document.getElementById("idxAutoCmsToggle").checked,
        };
        const res = await adminFetch("/api/admin/indexnow/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        showToast("IndexNow configuration saved successfully!", "success");
        loadIndexNowTab();
      } catch (err) {
        showToast(err.message, "error");
      }
    });

    document.getElementById("btnRefreshIndexNowLog")?.addEventListener("click", () => {
      loadIndexNowTab();
      showToast("IndexNow logs refreshed.", "info");
    });

    document.getElementById("btnClearIndexNowLog")?.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to clear the IndexNow submission history?")) return;
      try {
        await adminFetch("/api/admin/indexnow/history", { method: "DELETE" });
        showToast("IndexNow submission history cleared.", "success");
        loadIndexNowTab();
      } catch (e) {
        showToast(e.message, "error");
      }
    });
  }

  // --------------------------------------------------------
  // TAB 1: OVERVIEW & ANALYTICS
  // --------------------------------------------------------
  async function loadOverview() {
    try {
      const res = await adminFetch("/api/admin/overview");
      const data = await res.json();
      const a = data.analytics || {};
      const s = data.settings || {};
      currentSettings = s;

      document.getElementById("kpiTotalJobs").innerText = a.total_jobs ?? 0;
      document.getElementById("kpiAvgTime").innerText = `${a.avg_process_time_ms ?? 0} ms`;
      const kb = Math.round((a.total_output_bytes || 0) / 1024);
      document.getElementById("kpiStorage").innerText = kb > 1024 ? `${(kb / 1024).toFixed(2)} MB` : `${kb} KB`;
      document.getElementById("kpiPresetsSamples").innerText = `${a.total_presets || 0} Presets • ${a.total_samples || 0} Samples • ${a.total_blog_posts || 0} Blogs`;
      document.getElementById("kpiRamModels").innerText = (data.cached_sessions || []).join(", ") || "None";
      document.getElementById("kpiDefaultModel").innerText = `Default: ${s.default_model || "u2net"}`;

      headerDbBadge.innerText = a.db_connected ? `MySQL: ${a.db_name}` : `Fallback DB (${a.db_name})`;

      // Models Breakdown
      const breakdownEl = document.getElementById("modelsBreakdownList");
      breakdownEl.innerHTML = "";
      const mb = a.models_breakdown || {};
      const entries = Object.entries(mb);
      if (entries.length === 0) {
        breakdownEl.innerHTML = `<p class="text-slate-400">No jobs processed yet.</p>`;
      } else {
        entries.forEach(([modelName, count]) => {
          const pct = Math.min(100, Math.round((count / Math.max(1, a.total_jobs)) * 100));
          breakdownEl.innerHTML += `
            <div>
              <div class="flex justify-between font-semibold mb-1">
                <span>${modelName}</span>
                <span>${count} jobs (${pct}%)</span>
              </div>
              <div class="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div class="bg-blue-600 h-full rounded-full" style="width: ${pct}%"></div>
              </div>
            </div>
          `;
        });
      }

      // Frontend Status Summary
      const summaryEl = document.getElementById("frontendStatusSummary");
      const badge = (on, label) => `
        <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-center justify-between">
          <span class="font-medium">${label}</span>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${on ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400" : "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400"}">${on ? "ENABLED" : "OFF"}</span>
        </div>
      `;
      summaryEl.innerHTML = [
        badge(!s.maintenance_mode, "Public Access"),
        badge(s.enable_batch_mode, "Batch Remover Tab"),
        badge(s.enable_history_tab, "Public MySQL History"),
        badge(s.enable_alpha_matting, "Alpha Matting Controls"),
        badge(s.enable_custom_backdrop, "Custom Image Backdrop"),
        badge(s.announcement_enabled, "Announcement Banner"),
      ].join("");

      // Recent Jobs Table
      const tbody = document.getElementById("overviewRecentTable");
      tbody.innerHTML = "";
      (data.recent_jobs || []).forEach(job => {
        tbody.innerHTML += `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <td class="py-2">
              <img src="${job.output_url}" class="w-10 h-10 rounded-lg object-contain bg-checkerboard border border-slate-200 dark:border-slate-700">
            </td>
            <td class="py-2 font-semibold">${job.original_filename}</td>
            <td class="py-2"><span class="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 font-mono">${job.model_used}</span></td>
            <td class="py-2 text-slate-500">${job.original_width}×${job.original_height}</td>
            <td class="py-2 text-emerald-600 dark:text-emerald-400 font-semibold">${job.process_time_ms} ms</td>
            <td class="py-2 text-slate-400">${job.created_at || ""}</td>
          </tr>
        `;
      });
    } catch (e) {
      console.error(e);
    }
  }

  // --------------------------------------------------------
  // TAB 2: FRONTEND CMS & FEATURE FLAGS
  // --------------------------------------------------------
  async function loadCmsSettings() {
    try {
      const res = await adminFetch("/api/admin/settings");
      const data = await res.json();
      const s = data.settings || {};
      currentSettings = s;

      document.getElementById("cmsSiteTitle").value = s.site_title || "";
      document.getElementById("cmsSiteTagline").value = s.site_tagline || "";
      document.getElementById("cmsSiteBadge").value = s.site_badge || "";
      document.getElementById("cmsHeroTitle").value = s.hero_title || "";
      document.getElementById("cmsHeroHighlight").value = s.hero_highlight || "";
      document.getElementById("cmsHeroSubtitle").value = s.hero_subtitle || "";
      document.getElementById("cmsAnnouncementText").value = s.announcement_text || "";
      document.getElementById("cmsFooterText").value = s.footer_text || "";
      document.getElementById("cmsDefaultModel").value = s.default_model || "u2net";
      document.getElementById("cmsMaxUploadMb").value = s.max_upload_mb ?? 25;
      document.getElementById("cmsMaxBatchFiles").value = s.max_batch_files ?? 50;

      document.getElementById("cmsAnnouncementEnabled").checked = Boolean(s.announcement_enabled);
      document.getElementById("cmsEnableBatch").checked = Boolean(s.enable_batch_mode);
      document.getElementById("cmsEnableHistory").checked = Boolean(s.enable_history_tab);
      document.getElementById("cmsEnableAlpha").checked = Boolean(s.enable_alpha_matting);
      document.getElementById("cmsEnableBackdrop").checked = Boolean(s.enable_custom_backdrop);
      document.getElementById("cmsMaintenanceMode").checked = Boolean(s.maintenance_mode);
      document.getElementById("cmsMaintenanceMessage").value = s.maintenance_message || "";

      const defToolEl = document.getElementById("cmsDefaultTool");
      if (defToolEl) defToolEl.value = s.default_tool || "bg-remover";

      const allToolsList = [
        { id: "image-editor", name: "Image Editor" },
        { id: "image-upscaler", name: "Image Upscaler" },
        { id: "image-extender", name: "Image Extender" },
        { id: "variations", name: "Variations" },
        { id: "cinematic-shot", name: "Cinematic Shot" },
        { id: "bg-remover", name: "Background Remover" },
        { id: "skin-enhancer", name: "Skin Enhancer" },
        { id: "relight", name: "Relight" },
        { id: "change-camera", name: "Change Camera" },
      ];
      const enabledToolsSet = new Set(s.enabled_tools || allToolsList.map(t => t.id));
      const toolsContainer = document.getElementById("cmsToolsCheckboxes");
      if (toolsContainer) {
        toolsContainer.innerHTML = "";
        allToolsList.forEach(t => {
          const checked = enabledToolsSet.has(t.id) ? "checked" : "";
          toolsContainer.innerHTML += `
            <label class="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 cursor-pointer">
              <span class="text-xs font-semibold truncate pr-2">${t.name}</span>
              <input type="checkbox" class="cms-tool-cb w-4 h-4 accent-blue-600 shrink-0" value="${t.id}" ${checked}>
            </label>
          `;
        });
      }
    } catch (e) {
      showToast("Failed to load CMS settings", "error");
    }
  }

  async function saveCmsSettings() {
    const enabledTools = Array.from(document.querySelectorAll(".cms-tool-cb:checked")).map(cb => cb.value);
    const payload = {
      site_title: document.getElementById("cmsSiteTitle").value.trim(),
      site_tagline: document.getElementById("cmsSiteTagline").value.trim(),
      site_badge: document.getElementById("cmsSiteBadge").value.trim(),
      hero_title: document.getElementById("cmsHeroTitle").value.trim(),
      hero_highlight: document.getElementById("cmsHeroHighlight").value.trim(),
      hero_subtitle: document.getElementById("cmsHeroSubtitle").value.trim(),
      announcement_text: document.getElementById("cmsAnnouncementText").value.trim(),
      footer_text: document.getElementById("cmsFooterText").value.trim(),
      default_model: document.getElementById("cmsDefaultModel").value,
      default_tool: document.getElementById("cmsDefaultTool")?.value || "bg-remover",
      enabled_tools: enabledTools.length > 0 ? enabledTools : ["bg-remover"],
      max_upload_mb: parseInt(document.getElementById("cmsMaxUploadMb").value, 10) || 25,
      max_batch_files: parseInt(document.getElementById("cmsMaxBatchFiles").value, 10) || 50,
      announcement_enabled: document.getElementById("cmsAnnouncementEnabled").checked,
      enable_batch_mode: document.getElementById("cmsEnableBatch").checked,
      enable_history_tab: document.getElementById("cmsEnableHistory").checked,
      enable_alpha_matting: document.getElementById("cmsEnableAlpha").checked,
      enable_custom_backdrop: document.getElementById("cmsEnableBackdrop").checked,
      maintenance_mode: document.getElementById("cmsMaintenanceMode").checked,
      maintenance_message: document.getElementById("cmsMaintenanceMessage").value.trim(),
    };

    try {
      const res = await adminFetch("/api/admin/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to save settings");
      const data = await res.json();
      currentSettings = data.settings;
      showToast("Saved & published settings to MySQL and live Frontend!", "success");
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  // --------------------------------------------------------
  // TAB: BLOG MANAGER (CREATE, EDIT, PUBLISH, DELETE)
  // --------------------------------------------------------
  async function loadAdminBlog() {
    try {
      const search = document.getElementById("adminBlogSearchInput")?.value.trim() || "";
      const status = document.getElementById("adminBlogStatusFilter")?.value || "";
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (status) params.set("status", status);

      const res = await adminFetch(`/api/admin/blog?${params.toString()}`);
      const data = await res.json();
      const stats = data.stats || {};

      document.getElementById("blogKpiTotal").innerText = stats.total_posts ?? 0;
      document.getElementById("blogKpiPublished").innerText = stats.published_posts ?? 0;
      document.getElementById("blogKpiDraftsFeatured").innerText = `${stats.draft_posts ?? 0} / ${stats.featured_posts ?? 0}`;
      document.getElementById("blogKpiViews").innerText = stats.total_views ?? 0;

      const tbody = document.getElementById("adminBlogTableBody");
      tbody.innerHTML = "";

      (data.posts || []).forEach(post => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/40";
        tr.innerHTML = `
          <td class="py-2.5">
            <img src="${post.cover_image || '/static/samples/portrait_person.jpg'}" class="w-12 h-9 rounded-lg object-cover border border-slate-200 dark:border-slate-700">
          </td>
          <td class="py-2.5 max-w-[260px]">
            <div class="font-bold text-slate-900 dark:text-white truncate" title="${post.title}">${post.title}</div>
            <div class="text-[11px] font-mono text-slate-400 truncate">/blog/${post.slug}</div>
          </td>
          <td class="py-2.5">
            <span class="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 font-semibold">${post.category}</span>
          </td>
          <td class="py-2.5">
            <button class="toggle-blog-pub-btn px-2.5 py-0.5 rounded-full text-[10px] font-bold ${post.is_published ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'}">
              ${post.is_published ? "PUBLISHED" : "DRAFT"}
            </button>
          </td>
          <td class="py-2.5">
            <button class="toggle-blog-feat-btn px-2 py-0.5 rounded text-xs font-bold ${post.is_featured ? 'text-amber-500' : 'text-slate-400 hover:text-amber-400'}" title="Toggle Featured">
              ${post.is_featured ? "★ Featured" : "☆ Standard"}
            </button>
          </td>
          <td class="py-2.5 font-mono text-slate-500">${post.views_count}</td>
          <td class="py-2.5 text-slate-400">${post.published_date || ""}</td>
          <td class="py-2.5 text-right space-x-2 whitespace-nowrap">
            <button class="indexnow-blog-btn text-emerald-600 dark:text-emerald-400 hover:underline font-bold" title="Instant IndexNow Push to Bing & Search Engines">⚡ Index</button>
            <button class="edit-blog-btn text-indigo-600 dark:text-indigo-400 hover:underline font-bold">Edit</button>
            <a href="/blog/${post.slug}" target="_blank" class="text-blue-500 hover:underline font-semibold">View</a>
            <button class="del-blog-btn text-rose-500 hover:underline font-semibold">Delete</button>
          </td>
        `;

        tr.querySelector(".toggle-blog-pub-btn").addEventListener("click", async () => {
          await adminFetch(`/api/admin/blog/${post.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_published: !post.is_published }),
          });
          showToast(`Updated status for "${post.title}"`, "success");
          loadAdminBlog();
        });

        tr.querySelector(".toggle-blog-feat-btn").addEventListener("click", async () => {
          await adminFetch(`/api/admin/blog/${post.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_featured: !post.is_featured }),
          });
          showToast(`Updated featured status for "${post.title}"`, "success");
          loadAdminBlog();
        });

        tr.querySelector(".edit-blog-btn").addEventListener("click", () => {
          startEditBlogPost(post);
        });

        tr.querySelector(".del-blog-btn").addEventListener("click", async () => {
          await adminFetch(`/api/admin/blog/${post.id}`, { method: "DELETE" });
          showToast(`Deleted blog article "${post.title}"`, "info");
          loadAdminBlog();
        });

        tr.querySelector(".indexnow-blog-btn")?.addEventListener("click", async () => {
          try {
            showToast(`Submitting /blog/${post.slug} to IndexNow...`, "info");
            const res = await adminFetch("/api/admin/indexnow/submit", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ urls: [`https://pnglike.com/blog/${post.slug}`], triggered_by: "blog_row_push" }),
            });
            const d = await res.json();
            showToast(d.message || "Submitted to IndexNow!", d.success ? "success" : "error");
          } catch (e) {
            showToast(e.message, "error");
          }
        });

        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error("Failed to load blog posts:", e);
    }
  }

  function startEditBlogPost(post) {
    document.getElementById("blogEditPostId").value = post.id;
    document.getElementById("blogFormHeaderTitle").innerText = `Edit Blog Article #${post.id}`;
    document.getElementById("blogEditModeBadge").classList.remove("hidden");
    document.getElementById("blogCancelEditBtn").classList.remove("hidden");
    document.getElementById("blogSaveSubmitText").innerText = "Update Blog Article";

    document.getElementById("blogTitleInput").value = post.title || "";
    document.getElementById("blogSlugInput").value = post.slug || "";
    document.getElementById("blogCategoryInput").value = post.category || "AI Tutorials";
    document.getElementById("blogAuthorInput").value = post.author || "Div Sri";
    document.getElementById("blogReadTimeInput").value = post.read_time_minutes || 4;
    document.getElementById("blogTagsInput").value = post.tags || "";
    document.getElementById("blogCoverInput").value = post.cover_image || "/static/samples/portrait_person.jpg";
    document.getElementById("blogExcerptInput").value = post.excerpt || "";
    document.getElementById("blogContentInput").value = post.content || "";
    document.getElementById("blogMetaTitleInput").value = post.meta_title || "";
    document.getElementById("blogMetaDescInput").value = post.meta_description || "";
    document.getElementById("blogPublishedToggle").checked = Boolean(post.is_published);
    document.getElementById("blogFeaturedToggle").checked = Boolean(post.is_featured);

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function resetBlogEditorForm() {
    document.getElementById("blogEditorForm").reset();
    document.getElementById("blogEditPostId").value = "";
    document.getElementById("blogFormHeaderTitle").innerText = "Create New Blog Article";
    document.getElementById("blogEditModeBadge").classList.add("hidden");
    document.getElementById("blogCancelEditBtn").classList.add("hidden");
    document.getElementById("blogSaveSubmitText").innerText = "Publish Blog Article";
    document.getElementById("blogCategoryInput").value = "AI Tutorials";
    document.getElementById("blogAuthorInput").value = "Div Sri";
    document.getElementById("blogReadTimeInput").value = 4;
    document.getElementById("blogCoverInput").value = "/static/samples/portrait_person.jpg";
    document.getElementById("blogPublishedToggle").checked = true;
    document.getElementById("blogFeaturedToggle").checked = false;
  }

  async function handleSaveBlogPost(e) {
    e.preventDefault();
    const editId = document.getElementById("blogEditPostId").value;
    const payload = {
      title: document.getElementById("blogTitleInput").value.trim(),
      slug: document.getElementById("blogSlugInput").value.trim() || null,
      category: document.getElementById("blogCategoryInput").value.trim() || "AI Tutorials",
      author: document.getElementById("blogAuthorInput").value.trim() || "Div Sri",
      read_time_minutes: parseInt(document.getElementById("blogReadTimeInput").value, 10) || 4,
      tags: document.getElementById("blogTagsInput").value.trim(),
      cover_image: document.getElementById("blogCoverInput").value.trim() || "/static/samples/portrait_person.jpg",
      excerpt: document.getElementById("blogExcerptInput").value.trim(),
      content: document.getElementById("blogContentInput").value.trim(),
      meta_title: document.getElementById("blogMetaTitleInput").value.trim() || null,
      meta_description: document.getElementById("blogMetaDescInput").value.trim() || null,
      is_published: document.getElementById("blogPublishedToggle").checked,
      is_featured: document.getElementById("blogFeaturedToggle").checked,
    };

    try {
      const url = editId ? `/api/admin/blog/${editId}` : "/api/admin/blog";
      const method = editId ? "PUT" : "POST";
      const res = await adminFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to save blog article");
      }
      showToast(editId ? "Blog article updated in MySQL!" : "Published new blog article to /blog!", "success");
      resetBlogEditorForm();
      loadAdminBlog();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function handleBlogCoverUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await adminFetch("/api/admin/blog/upload-cover", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Cover upload failed");
      const data = await res.json();
      document.getElementById("blogCoverInput").value = data.url;
      showToast("Uploaded blog cover image!", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  function insertBlogFormattingSnippet(tagType) {
    const area = document.getElementById("blogContentInput");
    if (!area) return;
    const snippets = {
      h2: "\n<h2>Section Heading</h2>\n",
      h3: "\n<h3>Sub-heading</h3>\n",
      p: "\n<p>Write your paragraph here...</p>\n",
      ul: "\n<ul>\n  <li>First key point</li>\n  <li>Second key point</li>\n</ul>\n",
      quote: "\n<blockquote>Pro Tip: Add an actionable workflow recommendation here.</blockquote>\n",
      code: "<code>u2net</code>",
    };
    const snippet = snippets[tagType] || "";
    const start = area.selectionStart ?? area.value.length;
    const end = area.selectionEnd ?? area.value.length;
    area.value = area.value.slice(0, start) + snippet + area.value.slice(end);
    area.focus();
  }

  // --------------------------------------------------------
  // TAB 3: AI MODELS & RAM CACHE
  // --------------------------------------------------------
  async function loadAdminModels() {
    try {
      const res = await adminFetch("/api/admin/models");
      const data = await res.json();
      const grid = document.getElementById("adminModelsGrid");
      grid.innerHTML = "";

      const enabledSet = new Set(
        (data.models || []).filter(m => m.is_enabled).map(m => m.id)
      );

      (data.models || []).forEach(m => {
        const card = document.createElement("div");
        card.className = "p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 flex flex-col justify-between gap-3";
        card.innerHTML = `
          <div>
            <div class="flex items-center justify-between mb-1">
              <div class="flex items-center gap-2">
                <h4 class="font-bold text-sm text-slate-900 dark:text-white">${m.name}</h4>
                ${m.is_default ? `<span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-600 text-white font-bold">Default</span>` : ""}
              </div>
              <span class="text-xs font-mono text-slate-400">${m.size}</span>
            </div>
            <p class="text-xs text-slate-500 dark:text-slate-400 mb-3">${m.description}</p>
            <div class="flex flex-wrap items-center gap-2 text-[11px]">
              <span class="px-2 py-0.5 rounded-md font-semibold ${m.is_downloaded ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400" : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400"}">
                ${m.is_downloaded ? "On Disk (.onnx)" : "Downloads on Demand"}
              </span>
              <span class="px-2 py-0.5 rounded-md font-semibold ${m.is_loaded ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-400" : "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400"}">
                ${m.is_loaded ? "Loaded in RAM" : "Not in RAM"}
              </span>
            </div>
          </div>

          <div class="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-slate-700">
            <label class="flex items-center gap-2 text-xs font-semibold cursor-pointer">
              <input type="checkbox" class="toggle-model-cb w-4 h-4 accent-blue-600" data-id="${m.id}" ${m.is_enabled ? "checked" : ""}>
              <span>Show on Frontend</span>
            </label>

            <div class="flex items-center gap-2">
              ${!m.is_default ? `<button data-default-id="${m.id}" class="set-default-model-btn px-2.5 py-1 rounded-lg border border-slate-300 dark:border-slate-600 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-700">Set Default</button>` : ""}
              ${m.is_loaded
                ? `<button data-unload-id="${m.id}" class="unload-model-btn px-2.5 py-1 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 text-xs font-semibold">Unload RAM</button>`
                : `<button data-load-id="${m.id}" class="load-model-btn px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-xs font-semibold">Load RAM</button>`
              }
            </div>
          </div>
        `;

        // Toggle Frontend visibility
        card.querySelector(".toggle-model-cb").addEventListener("change", async (e) => {
          if (e.target.checked) {
            enabledSet.add(m.id);
          } else {
            if (enabledSet.size <= 1) {
              e.target.checked = true;
              showToast("At least one AI model must remain enabled on the frontend.", "error");
              return;
            }
            enabledSet.delete(m.id);
          }
          await adminFetch("/api/admin/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled_models: Array.from(enabledSet) }),
          });
          showToast(`Updated frontend availability for ${m.id}`, "success");
        });

        // Set Default Model
        const defBtn = card.querySelector(".set-default-model-btn");
        if (defBtn) {
          defBtn.addEventListener("click", async () => {
            enabledSet.add(m.id);
            await adminFetch("/api/admin/settings", {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                default_model: m.id,
                enabled_models: Array.from(enabledSet),
              }),
            });
            showToast(`Set ${m.id} as default frontend model!`, "success");
            loadAdminModels();
          });
        }

        // Load / Unload RAM
        const loadBtn = card.querySelector(".load-model-btn");
        if (loadBtn) {
          loadBtn.addEventListener("click", async () => {
            loadBtn.innerText = "Loading...";
            loadBtn.disabled = true;
            await adminFetch(`/api/admin/models/${m.id}/load`, { method: "POST" });
            showToast(`Loaded ${m.id} into RAM cache!`, "success");
            loadAdminModels();
          });
        }

        const unloadBtn = card.querySelector(".unload-model-btn");
        if (unloadBtn) {
          unloadBtn.addEventListener("click", async () => {
            await adminFetch(`/api/admin/models/${m.id}/unload`, { method: "POST" });
            showToast(`Unloaded ${m.id} from RAM cache.`, "info");
            loadAdminModels();
          });
        }

        grid.appendChild(card);
      });
    } catch (e) {
      console.error(e);
    }
  }

  // --------------------------------------------------------
  // TAB 4: SAMPLE GALLERY MANAGER
  // --------------------------------------------------------
  async function loadAdminSamples() {
    try {
      const res = await adminFetch("/api/admin/samples");
      const data = await res.json();
      const grid = document.getElementById("adminSamplesGrid");
      grid.innerHTML = "";

      (data.samples || []).forEach(sample => {
        const card = document.createElement("div");
        card.className = "bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-3 flex flex-col justify-between shadow-sm";
        card.innerHTML = `
          <div>
            <div class="aspect-[4/3] rounded-xl overflow-hidden bg-slate-100 dark:bg-slate-800 mb-2.5 relative">
              <img src="${sample.url}" class="w-full h-full object-cover">
              <span class="absolute top-2 left-2 bg-slate-900/75 text-white text-[10px] font-semibold px-2 py-0.5 rounded-md">${sample.category}</span>
              <span class="absolute top-2 right-2 px-2 py-0.5 rounded-md text-[10px] font-bold ${sample.is_active ? "bg-emerald-600 text-white" : "bg-slate-700 text-slate-300"}">
                ${sample.is_active ? "Visible" : "Hidden"}
              </span>
            </div>
            <h4 class="font-bold text-xs text-slate-900 dark:text-white px-1">${sample.title}</h4>
            <p class="text-[11px] text-slate-400 px-1 font-mono truncate">${sample.filename}</p>
          </div>
          <div class="flex items-center justify-between mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800">
            <button class="toggle-sample-btn text-xs font-semibold px-3 py-1 rounded-lg ${sample.is_active ? "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300" : "bg-emerald-600 text-white"}">
              ${sample.is_active ? "Hide on Frontend" : "Show on Frontend"}
            </button>
            <button class="delete-sample-btn p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40">
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
        `;

        card.querySelector(".toggle-sample-btn").addEventListener("click", async () => {
          await adminFetch(`/api/admin/samples/${sample.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !sample.is_active }),
          });
          showToast(`Updated visibility for "${sample.title}"`, "success");
          loadAdminSamples();
        });

        card.querySelector(".delete-sample-btn").addEventListener("click", async () => {
          await adminFetch(`/api/admin/samples/${sample.id}`, { method: "DELETE" });
          showToast(`Removed sample "${sample.title}" from MySQL`, "info");
          loadAdminSamples();
        });

        grid.appendChild(card);
      });
      safeCreateIcons();
    } catch (e) {
      console.error(e);
    }
  }

  async function handleUploadSample(e) {
    e.preventDefault();
    const fileInput = document.getElementById("newSampleFile");
    if (!fileInput.files || !fileInput.files[0]) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("title", document.getElementById("newSampleTitle").value.trim());
    formData.append("category", document.getElementById("newSampleCategory").value.trim());
    formData.append("is_active", "true");

    try {
      const res = await adminFetch("/api/admin/samples", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Failed to upload sample image");
      document.getElementById("uploadSampleForm").reset();
      showToast("Uploaded new sample image to MySQL & Frontend!", "success");
      loadAdminSamples();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // --------------------------------------------------------
  // TAB 5: WORKFLOW PRESETS MANAGER
  // --------------------------------------------------------
  async function loadAdminPresets() {
    try {
      const res = await fetch("/api/presets");
      const data = await res.json();
      const list = document.getElementById("adminPresetsList");
      list.innerHTML = "";

      (data.presets || []).forEach(p => {
        const card = document.createElement("div");
        card.className = "bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm";
        card.innerHTML = `
          <div>
            <div class="flex items-center justify-between mb-2">
              <h4 class="font-bold text-sm text-slate-900 dark:text-white">${p.name}</h4>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 font-bold">${p.model_used}</span>
            </div>
            <div class="text-xs text-slate-500 space-y-1">
              <div>Alpha Matting: <strong class="text-slate-700 dark:text-slate-300">${p.alpha_matting ? "Enabled" : "Off"}</strong></div>
              <div>Background: <strong class="text-slate-700 dark:text-slate-300">${p.bg_mode} ${p.bg_value || ""}</strong></div>
              <div>Export Format: <strong class="text-slate-700 dark:text-slate-300 uppercase">${p.export_format}</strong></div>
            </div>
          </div>
          <div class="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-end">
            <button class="del-preset-btn text-xs text-rose-500 hover:underline flex items-center gap-1">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              <span>Delete Preset</span>
            </button>
          </div>
        `;
        card.querySelector(".del-preset-btn").addEventListener("click", async () => {
          if (!confirm(`Delete preset "${p.name}"?`)) return;
          try {
            const res = await adminFetch(`/api/presets/${p.id}`, { method: "DELETE" });
            if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              throw new Error(err.detail || "Failed to delete preset");
            }
            showToast(`Deleted preset "${p.name}"`, "info");
            loadAdminPresets();
          } catch (err) {
            showToast(err.message || "Failed to delete preset.", "error");
          }
        });
        list.appendChild(card);
      });
      safeCreateIcons();
    } catch (e) {
      console.error(e);
    }
  }

  async function handleCreatePreset(e) {
    e.preventDefault();
    const bgMode = document.getElementById("newPresetBgMode").value;
    const payload = {
      name: document.getElementById("newPresetName").value.trim(),
      model_used: document.getElementById("newPresetModel").value,
      alpha_matting: false,
      af_threshold: 240,
      ab_threshold: 10,
      ae_size: 10,
      post_process_mask: true,
      bg_mode: bgMode,
      bg_value: bgMode === "solid" ? "#ffffff" : null,
      export_format: document.getElementById("newPresetFormat").value,
    };

    try {
      const res = await adminFetch("/api/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to save preset");
      document.getElementById("createPresetForm").reset();
      showToast("Saved new Studio preset to MySQL!", "success");
      loadAdminPresets();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // --------------------------------------------------------
  // TAB 6: JOBS & STORAGE MODERATION
  // --------------------------------------------------------
  async function loadAdminJobs() {
    try {
      const search = document.getElementById("jobsSearchInput").value.trim();
      const model = document.getElementById("jobsModelFilter").value;
      const params = new URLSearchParams({ limit: "100" });
      if (search) params.set("search", search);
      if (model) params.set("model", model);

      const res = await adminFetch(`/api/admin/jobs?${params.toString()}`);
      const data = await res.json();
      const tbody = document.getElementById("adminJobsTableBody");
      tbody.innerHTML = "";

      (data.jobs || []).forEach(job => {
        const kb = Math.max(1, Math.round((job.output_size_bytes || 0) / 1024));
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/40";
        tr.innerHTML = `
          <td class="py-2.5 font-mono text-slate-400">#${job.id}</td>
          <td class="py-2.5">
            <img src="${job.output_url}" class="w-10 h-10 rounded-lg object-contain bg-checkerboard border border-slate-200 dark:border-slate-700">
          </td>
          <td class="py-2.5 font-semibold max-w-[180px] truncate" title="${job.original_filename}">${job.original_filename}</td>
          <td class="py-2.5"><span class="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 font-mono">${job.model_used}</span></td>
          <td class="py-2.5 text-slate-500">${job.original_width}×${job.original_height}</td>
          <td class="py-2.5 text-slate-500">${kb} KB</td>
          <td class="py-2.5 text-emerald-600 dark:text-emerald-400 font-semibold">${job.process_time_ms} ms</td>
          <td class="py-2.5 text-slate-400">${job.created_at || ""}</td>
          <td class="py-2.5 text-right space-x-2">
            <a href="${job.output_url}" download="${job.output_filename}" class="text-blue-500 hover:underline font-semibold">Download</a>
            <button class="del-job-btn text-rose-500 hover:underline font-semibold">Delete</button>
          </td>
        `;
        tr.querySelector(".del-job-btn").addEventListener("click", async () => {
          if (!confirm(`Are you sure you want to delete job #${job.id} (${job.original_filename})?`)) return;
          try {
            const res = await adminFetch(`/api/history/${job.id}`, { method: "DELETE" });
            if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              throw new Error(err.detail || `Failed to delete job #${job.id}`);
            }
            showToast(`Deleted job #${job.id} and output file.`, "info");
            loadAdminJobs();
            if (typeof loadOverviewTab === "function") loadOverviewTab();
          } catch (err) {
            showToast(err.message || "Failed to delete job.", "error");
          }
        });
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error(e);
    }
  }

  async function handlePurgeAllJobs() {
    if (!confirm("Are you sure you want to purge ALL jobs and stored files? This cannot be undone.")) return;
    try {
      const res = await adminFetch("/api/history", { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to purge jobs");
      }
      const data = await res.json();
      showToast(`Purged ${data.count ?? "all"} jobs from MySQL and cleaned up output storage.`, "success");
      loadAdminJobs();
      if (typeof loadOverviewTab === "function") loadOverviewTab();
    } catch (err) {
      showToast(err.message || "Failed to purge jobs.", "error");
    }
  }

  // --------------------------------------------------------
  // TAB 7: MYSQL & ADMIN SECURITY
  // --------------------------------------------------------
  async function loadDatabaseTab() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      const db = data.database || {};
      document.getElementById("admDbHost").value = db.host || "127.0.0.1";
      document.getElementById("admDbPort").value = db.port || 3306;
      document.getElementById("admDbUser").value = db.user || "root";
      document.getElementById("admDbName").value = db.database || "rembg_studio";

      const box = document.getElementById("adminDbStatusBox");
      box.innerText = db.connected
        ? `Connected: mysql+pymysql://${db.user}@${db.host}:${db.port}/${db.database} (${db.total_jobs} jobs)`
        : `Offline Fallback Mode: ${db.error || "MySQL server unreachable"}`;

      await loadSmtpSettings();
    } catch (e) {}
  }

  async function loadSmtpSettings() {
    try {
      const res = await adminFetch("/api/admin/smtp");
      if (!res.ok) return;
      const data = await res.json();
      const s = data.smtp || {};
      const enEl = document.getElementById("admSmtpEnabled");
      if (enEl) enEl.checked = s.smtp_enabled !== false;
      const hEl = document.getElementById("admSmtpHost");
      if (hEl) hEl.value = s.smtp_host || "smtp.gmail.com";
      const pEl = document.getElementById("admSmtpPort");
      if (pEl) pEl.value = s.smtp_port || 587;
      const tlsEl = document.getElementById("admSmtpUseTls");
      if (tlsEl) tlsEl.checked = s.smtp_use_tls !== false;
      const uEl = document.getElementById("admSmtpUser");
      if (uEl) uEl.value = s.smtp_user || "";
      const passEl = document.getElementById("admSmtpPass");
      if (passEl && s.password) passEl.value = s.password;
      const fnEl = document.getElementById("admSmtpFromName");
      if (fnEl) fnEl.value = s.smtp_from_name || "PngLike AI Studio — Powered by Div Sri";
      const feEl = document.getElementById("admSmtpFromEmail");
      if (feEl) feEl.value = s.smtp_from_email || "";
    } catch (_) {}
  }

  async function handleSaveSmtpSettings() {
    const statusBox = document.getElementById("admSmtpStatusBox");
    if (statusBox) statusBox.classList.add("hidden");
    const payload = {
      smtp_enabled: document.getElementById("admSmtpEnabled")?.checked ?? true,
      smtp_host: document.getElementById("admSmtpHost")?.value?.trim() || "smtp.gmail.com",
      smtp_port: parseInt(document.getElementById("admSmtpPort")?.value, 10) || 587,
      smtp_user: document.getElementById("admSmtpUser")?.value?.trim() || "",
      smtp_password: document.getElementById("admSmtpPass")?.value || "",
      smtp_from_name: document.getElementById("admSmtpFromName")?.value?.trim() || "PngLike AI Studio — Powered by Div Sri",
      smtp_from_email: document.getElementById("admSmtpFromEmail")?.value?.trim() || "",
      smtp_use_tls: document.getElementById("admSmtpUseTls")?.checked ?? true,
    };

    try {
      const res = await adminFetch("/api/admin/smtp", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to update SMTP settings");
      showToast(data.message || "Saved Gmail SMTP configuration!", "success");
      if (statusBox) {
        statusBox.textContent = "Saved Gmail SMTP configuration in MySQL database.";
        statusBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-500";
        statusBox.classList.remove("hidden");
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function handleTestSmtpConnection() {
    const statusBox = document.getElementById("admSmtpStatusBox");
    if (statusBox) statusBox.classList.add("hidden");
    const host = document.getElementById("admSmtpHost")?.value?.trim() || "smtp.gmail.com";
    const port = parseInt(document.getElementById("admSmtpPort")?.value, 10) || 587;
    const user = document.getElementById("admSmtpUser")?.value?.trim() || "";
    const password = document.getElementById("admSmtpPass")?.value || "";
    const use_tls = document.getElementById("admSmtpUseTls")?.checked ?? true;
    const test_recipient = document.getElementById("admSmtpTestRecipient")?.value?.trim() || user;

    if (!user) {
      showToast("Please enter your Gmail address first", "error");
      return;
    }

    showToast("Testing Gmail SMTP connection...", "info");
    try {
      const res = await adminFetch("/api/admin/smtp/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host, port, user, password, use_tls, test_recipient }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "SMTP test failed");
      showToast("Gmail SMTP Connected Successfully! " + (data.message || ""), "success");
      if (statusBox) {
        statusBox.textContent = `Connected to ${host}:${port} successfully. ${data.message || ""}`;
        statusBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-500";
        statusBox.classList.remove("hidden");
      }
    } catch (err) {
      showToast(err.message, "error");
      if (statusBox) {
        statusBox.textContent = `SMTP Connection Failed: ${err.message}`;
        statusBox.className = "p-3 rounded-xl text-xs font-semibold bg-rose-500/10 border border-rose-500/30 text-rose-500";
        statusBox.classList.remove("hidden");
      }
    }
  }

  // --------------------------------------------------------
  // USERS MANAGER TAB
  // --------------------------------------------------------
  let adminUsersCache = [];

  const admUsersSearch = document.getElementById("admUsersSearchInput");
  if (admUsersSearch) {
    admUsersSearch.addEventListener("input", () => renderAdminUsersTable(adminUsersCache));
  }

  async function loadAdminUsers() {
    try {
      const res = await adminFetch("/api/admin/users");
      if (!res.ok) throw new Error("Failed to fetch users");
      const data = await res.json();
      adminUsersCache = data.users || [];

      const total = adminUsersCache.length;
      const active = adminUsersCache.filter(u => u.is_active && u.email_verified).length;
      const pending = adminUsersCache.filter(u => !u.email_verified).length;
      const suspended = adminUsersCache.filter(u => !u.is_active && u.email_verified).length;

      const tEl = document.getElementById("admUsersTotalCount");
      const aEl = document.getElementById("admUsersActiveCount");
      const pEl = document.getElementById("admUsersPendingCount");
      const sEl = document.getElementById("admUsersSuspendedCount");
      if (tEl) tEl.innerText = total;
      if (aEl) aEl.innerText = active;
      if (pEl) pEl.innerText = pending;
      if (sEl) sEl.innerText = suspended;

      renderAdminUsersTable(adminUsersCache);
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  function renderAdminUsersTable(users) {
    const tbody = document.getElementById("adminUsersTableBody");
    if (!tbody) return;

    const q = (document.getElementById("admUsersSearchInput")?.value || "").trim().toLowerCase();
    const filtered = (users || []).filter(
      u =>
        !q ||
        (u.username || "").toLowerCase().includes(q) ||
        (u.email || "").toLowerCase().includes(q) ||
        (u.full_name || "").toLowerCase().includes(q)
    );

    tbody.innerHTML = filtered
      .map(
        u => `
        <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
          <td class="py-3 pr-3">
            <div class="flex items-center gap-2.5">
              <div class="w-7 h-7 rounded-lg text-white font-bold text-xs flex items-center justify-center shrink-0" style="background-color: ${u.avatar_color || '#6366f1'}">
                ${(u.full_name || u.username || "U").charAt(0).toUpperCase()}
              </div>
              <div>
                <p class="font-bold text-slate-900 dark:text-white">${u.full_name || u.username}</p>
                <p class="text-[11px] text-slate-400 font-mono">@${u.username}</p>
              </div>
            </div>
          </td>
          <td class="py-3 pr-3 font-mono text-[11px] text-slate-600 dark:text-slate-300">${u.email}</td>
          <td class="py-3 pr-3">
            <select data-user-plan-id="${u.id}" class="adm-user-plan-select bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2 py-1 text-[11px] font-semibold">
              <option value="Free" ${u.plan_tier === "Free" ? "selected" : ""}>Free</option>
              <option value="Pro Studio" ${u.plan_tier === "Pro Studio" ? "selected" : ""}>Pro Studio</option>
              <option value="Enterprise" ${u.plan_tier === "Enterprise" ? "selected" : ""}>Enterprise</option>
            </select>
          </td>
          <td class="py-3 pr-3 font-mono font-bold">${u.jobs_count || 0}</td>
          <td class="py-3 pr-3">
            <div class="flex flex-col gap-1">
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold w-fit ${
                u.email_verified
                  ? "bg-emerald-500/15 text-emerald-500"
                  : "bg-amber-500/15 text-amber-500"
              }">
                ${u.email_verified ? "Verified" : "Pending Verification"}
              </span>
              <span class="text-[10px] font-semibold text-slate-400">
                ${u.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </td>
          <td class="py-3 pr-3 text-[11px] text-slate-400">${(u.created_at || "").split("T")[0]}</td>
          <td class="py-3 text-right space-x-1.5 whitespace-nowrap">
            ${
              !u.email_verified
                ? `<button data-verify-user-id="${u.id}" class="adm-verify-user-btn px-2.5 py-1 rounded-lg text-[11px] font-bold bg-indigo-500/15 text-indigo-500 hover:bg-indigo-500/25">
                     Verify & Activate
                   </button>`
                : ""
            }
            <button data-toggle-user-id="${u.id}" data-current-active="${u.is_active ? '1' : '0'}" class="adm-toggle-user-btn px-2.5 py-1 rounded-lg text-[11px] font-bold ${
              u.is_active
                ? "bg-amber-500/15 text-amber-500 hover:bg-amber-500/25"
                : "bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/25"
            }">
              ${u.is_active ? "Suspend" : "Activate"}
            </button>
            <button data-del-user-id="${u.id}" class="adm-del-user-btn px-2.5 py-1 rounded-lg bg-rose-500/15 text-rose-500 hover:bg-rose-500/25 text-[11px] font-bold">
              Delete
            </button>
          </td>
        </tr>
      `
      )
      .join("");

    tbody.querySelectorAll(".adm-verify-user-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const uid = btn.getAttribute("data-verify-user-id");
        try {
          const res = await adminFetch(`/api/admin/users/${uid}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email_verified: true, is_active: true }),
          });
          if (res.ok) {
            showToast(`User #${uid} verified and activated!`, "success");
            loadAdminUsers();
          }
        } catch (err) {
          showToast("Failed to verify user", "error");
        }
      });
    });

    tbody.querySelectorAll(".adm-user-plan-select").forEach(sel => {
      sel.addEventListener("change", async () => {
        const uid = sel.getAttribute("data-user-plan-id");
        const plan_tier = sel.value;
        try {
          const res = await adminFetch(`/api/admin/users/${uid}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plan_tier }),
          });
          if (res.ok) {
            showToast(`Updated user #${uid} plan to ${plan_tier}`, "success");
            loadAdminUsers();
          }
        } catch (err) {
          showToast("Failed to update user plan", "error");
        }
      });
    });

    tbody.querySelectorAll(".adm-toggle-user-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const uid = btn.getAttribute("data-toggle-user-id");
        const currentlyActive = btn.getAttribute("data-current-active") === "1";
        try {
          const res = await adminFetch(`/api/admin/users/${uid}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !currentlyActive }),
          });
          if (res.ok) {
            showToast(`User #${uid} ${!currentlyActive ? "activated" : "suspended"}`, "info");
            loadAdminUsers();
          }
        } catch (err) {
          showToast("Failed to toggle user status", "error");
        }
      });
    });

    tbody.querySelectorAll(".adm-del-user-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const uid = btn.getAttribute("data-del-user-id");
        if (!confirm(`Delete user account #${uid}?`)) return;
        try {
          const res = await adminFetch(`/api/admin/users/${uid}`, { method: "DELETE" });
          if (res.ok) {
            showToast(`Deleted user #${uid}`, "info");
            loadAdminUsers();
          }
        } catch (err) {
          showToast("Failed to delete user", "error");
        }
      });
    });
  }

  async function handleSaveMySQLConfig() {
    try {
      const payload = {
        host: document.getElementById("admDbHost").value.trim(),
        port: parseInt(document.getElementById("admDbPort").value, 10) || 3306,
        user: document.getElementById("admDbUser").value.trim(),
        password: document.getElementById("admDbPass").value,
        database: document.getElementById("admDbName").value.trim(),
      };
      const res = await adminFetch("/api/db/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      loadDatabaseTab();
      if (data.connected) {
        showToast("Connected to MySQL and provisioned tables!", "success");
      } else {
        showToast("Saved to .env (MySQL unreachable: " + data.error + ")", "error");
      }
    } catch (e) {
      showToast("Failed to update MySQL config", "error");
    }
  }

  async function handleUpdateAdminCreds() {
    const newUsername = document.getElementById("admNewUsername").value.trim();
    const newPassword = document.getElementById("admNewPassword").value;
    if (!newUsername) {
      showToast("Username cannot be empty.", "error");
      return;
    }
    try {
      const res = await adminFetch("/api/admin/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          new_username: newUsername,
          new_password: newPassword || null,
        }),
      });
      if (!res.ok) throw new Error("Failed to update credentials");
      const data = await res.json();
      adminUserLabel.innerText = data.admin.username;
      document.getElementById("admNewPassword").value = "";
      showToast("Updated Administrator credentials in MySQL!", "success");
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  // --------------------------------------------------------
  // ADMIN PROFILE & SECURITY CENTER
  // --------------------------------------------------------
  let currentAdminProfile = null;

  function getInitials(name) {
    if (!name) return "AD";
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function updateAdminIdentityUI(profile) {
    if (!profile) return;
    const fullName = profile.full_name || profile.username || "Administrator";
    const handle = "@" + (profile.username || "admin");
    const role = profile.role || "superadmin";
    const initials = getInitials(fullName);
    const color = profile.avatar_color || "#4f46e5";

    // Sidebar Identity
    const sideName = document.getElementById("adminSidebarFullName");
    if (sideName) sideName.innerText = fullName;
    const sideRole = document.getElementById("adminSidebarRole");
    if (sideRole) sideRole.innerText = role;
    if (adminUserLabel) adminUserLabel.innerText = handle;

    const sideAvatar = document.getElementById("adminSidebarAvatar");
    if (sideAvatar) {
      if (profile.avatar_url) {
        sideAvatar.innerHTML = `<img src="${profile.avatar_url}" alt="${fullName}" class="w-full h-full object-cover">`;
      } else {
        sideAvatar.innerText = initials;
        sideAvatar.style.backgroundColor = color;
      }
    }

    // Top Header Identity
    const headName = document.getElementById("adminHeaderName");
    if (headName) headName.innerText = fullName;
    const headAvatar = document.getElementById("adminHeaderAvatar");
    if (headAvatar) {
      if (profile.avatar_url) {
        headAvatar.innerHTML = `<img src="${profile.avatar_url}" alt="${fullName}" class="w-full h-full object-cover">`;
      } else {
        headAvatar.innerText = initials;
        headAvatar.style.backgroundColor = color;
      }
    }

    // Hero Avatar
    const heroAvatar = document.getElementById("profHeroAvatar");
    if (heroAvatar) {
      if (profile.avatar_url) {
        heroAvatar.innerHTML = `<img src="${profile.avatar_url}" alt="${fullName}" class="w-full h-full object-cover">`;
      } else {
        heroAvatar.innerText = initials;
        heroAvatar.style.backgroundColor = color;
      }
    }
  }

  async function loadAdminProfile(background = false) {
    try {
      const res = await adminFetch("/api/admin/profile");
      if (!res.ok) throw new Error("Failed to load admin profile");
      const data = await res.json();
      currentAdminProfile = data.profile;

      updateAdminIdentityUI(currentAdminProfile);

      if (background) return;

      const p = currentAdminProfile;
      // Populate Hero Card
      const heroName = document.getElementById("profHeroFullName");
      if (heroName) heroName.innerText = p.full_name || p.username;
      const heroUser = document.getElementById("profHeroUsername");
      if (heroUser) heroUser.innerText = "@" + p.username;
      const heroDesig = document.getElementById("profHeroDesignation");
      if (heroDesig) heroDesig.innerText = p.designation || "Lead AI Systems Architect";
      const heroDept = document.getElementById("profHeroDepartment");
      if (heroDept) heroDept.innerText = p.department || "DevOps & Infrastructure";
      const heroLoc = document.getElementById("profHeroLocation");
      if (heroLoc) heroLoc.innerText = p.location || "Tokyo, Japan";
      const heroTz = document.getElementById("profHeroTimezone");
      if (heroTz) heroTz.innerText = p.timezone_pref || "Asia/Tokyo (UTC+9)";
      const heroRole = document.getElementById("profHeroRole");
      if (heroRole) heroRole.innerText = (p.role || "superadmin").toUpperCase();

      if (p.stats) {
        const sj = document.getElementById("profStatJobs");
        if (sj) sj.innerText = p.stats.total_jobs ?? 0;
        const su = document.getElementById("profStatUsers");
        if (su) su.innerText = p.stats.total_users ?? 0;
        const sp = document.getElementById("profStatPosts");
        if (sp) sp.innerText = p.stats.total_blog_posts ?? 0;
        const ss = document.getElementById("profStatSessions");
        if (ss) ss.innerText = p.stats.active_sessions ?? 1;
      }

      // Populate Form Fields
      const fn = document.getElementById("profFullName");
      if (fn) fn.value = p.full_name || "";
      const un = document.getElementById("profUsername");
      if (un) un.value = p.username || "";
      const em = document.getElementById("profEmail");
      if (em) em.value = p.email || "";
      const ph = document.getElementById("profPhone");
      if (ph) ph.value = p.phone || "";
      const ds = document.getElementById("profDesignation");
      if (ds) ds.value = p.designation || "";
      const dp = document.getElementById("profDepartment");
      if (dp) dp.value = p.department || "";
      const lc = document.getElementById("profLocation");
      if (lc) lc.value = p.location || "";
      const bio = document.getElementById("profBio");
      if (bio) bio.value = p.bio || "";
      const tz = document.getElementById("profTimezone");
      if (tz) tz.value = p.timezone_pref || "Asia/Tokyo (UTC+9)";
      const ac = document.getElementById("profAvatarColor");
      if (ac) ac.value = p.avatar_color || "#4f46e5";

      // Color Swatches Selection
      document.querySelectorAll(".prof-color-swatch").forEach(btn => {
        const c = btn.getAttribute("data-color");
        if (c && c.toLowerCase() === (p.avatar_color || "#4f46e5").toLowerCase()) {
          btn.classList.add("ring-2", "ring-offset-2", "ring-indigo-500");
        } else {
          btn.classList.remove("ring-2", "ring-offset-2", "ring-indigo-500");
        }
      });

      // Toggles
      const notifSystem = document.getElementById("profEmailNotifToggle");
      if (notifSystem) notifSystem.checked = Boolean(p.email_notifications);
      const notifSec = document.getElementById("profSecurityAlertToggle");
      if (notifSec) notifSec.checked = Boolean(p.security_alerts);

      const lastUpd = document.getElementById("profLastUpdated");
      if (lastUpd) {
        lastUpd.innerText = p.updated_at ? `Last saved: ${p.updated_at}` : "Profile up to date";
      }

      loadAdminSessions();
      safeCreateIcons();
    } catch (e) {
      if (!background) showToast(e.message, "error");
    }
  }

  async function handleSaveAdminProfile(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById("saveAdminProfileBtn");
    const origHTML = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Saving...</span>`;
      safeCreateIcons();
    }

    const payload = {
      full_name: document.getElementById("profFullName")?.value.trim() || "",
      email: document.getElementById("profEmail")?.value.trim() || "",
      phone: document.getElementById("profPhone")?.value.trim() || "",
      designation: document.getElementById("profDesignation")?.value.trim() || "",
      department: document.getElementById("profDepartment")?.value.trim() || "",
      location: document.getElementById("profLocation")?.value.trim() || "",
      timezone_pref: document.getElementById("profTimezone")?.value || "Asia/Tokyo (UTC+9)",
      bio: document.getElementById("profBio")?.value.trim() || "",
      avatar_color: document.getElementById("profAvatarColor")?.value || "#4f46e5",
      email_notifications: Boolean(document.getElementById("profEmailNotifToggle")?.checked),
      security_alerts: Boolean(document.getElementById("profSecurityAlertToggle")?.checked),
    };

    try {
      const res = await adminFetch("/api/admin/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to update profile");
      currentAdminProfile = data.profile;
      updateAdminIdentityUI(currentAdminProfile);
      showToast("Administrator profile saved successfully in MySQL!", "success");
      const lastUpd = document.getElementById("profLastUpdated");
      if (lastUpd) lastUpd.innerText = "Last saved: Just now";
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHTML;
        safeCreateIcons();
      }
    }
  }

  async function handleAdminAvatarUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      showToast("Avatar file exceeds 5 MB limit.", "error");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);

    try {
      showToast("Uploading and optimizing profile photo...", "info");
      const res = await fetch("/api/admin/profile/avatar", {
        method: "POST",
        headers: { "X-Admin-Token": adminToken },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to upload avatar");
      currentAdminProfile = data.profile;
      updateAdminIdentityUI(currentAdminProfile);
      showToast("Profile avatar updated successfully!", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      e.target.value = "";
    }
  }

  async function handleRemoveAdminAvatar() {
    if (!confirm("Remove custom avatar photo and restore initials badge?")) return;
    try {
      const res = await adminFetch("/api/admin/profile/avatar", { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to remove avatar");
      currentAdminProfile = data.profile;
      updateAdminIdentityUI(currentAdminProfile);
      showToast("Avatar removed. Restored color initials badge.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function handleAdminPasswordChange(e) {
    if (e) e.preventDefault();
    const curr = document.getElementById("admCurrPassword")?.value || "";
    const newPwd = document.getElementById("admNewPasswordInput")?.value || "";
    const confPwd = document.getElementById("admConfirmPasswordInput")?.value || "";

    if (!curr) {
      showToast("Please enter your current password.", "error");
      return;
    }
    if (!newPwd || newPwd.length < 8) {
      showToast("New password must be at least 8 characters.", "error");
      return;
    }
    if (newPwd !== confPwd) {
      showToast("New password and confirmation do not match.", "error");
      return;
    }

    try {
      const res = await adminFetch("/api/admin/profile/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: curr,
          new_password: newPwd,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Password change failed");
      const cp = document.getElementById("admCurrPassword");
      if (cp) cp.value = "";
      const np = document.getElementById("admNewPasswordInput");
      if (np) np.value = "";
      const cnp = document.getElementById("admConfirmPasswordInput");
      if (cnp) cnp.value = "";
      updatePasswordStrength("");
      showToast("Password updated in MySQL! Other sessions revoked.", "success");
      loadAdminSessions();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  function updatePasswordStrength(val) {
    const bar = document.getElementById("profPwdStrengthBar");
    const text = document.getElementById("profPwdStrengthText");
    if (!bar || !text) return;

    if (!val) {
      bar.style.width = "0%";
      bar.className = "h-full w-0 transition-all duration-300 rounded-full bg-slate-400";
      text.innerText = "Enter password";
      text.className = "font-semibold text-slate-400";
      return;
    }

    let score = 0;
    if (val.length >= 8) score += 1;
    if (val.length >= 12) score += 1;
    if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score += 1;
    if (/[0-9]/.test(val)) score += 1;
    if (/[^A-Za-z0-9]/.test(val)) score += 1;

    if (score <= 2) {
      bar.style.width = "30%";
      bar.className = "h-full transition-all duration-300 rounded-full bg-rose-500";
      text.innerText = "Weak";
      text.className = "font-semibold text-rose-500";
    } else if (score <= 4) {
      bar.style.width = "70%";
      bar.className = "h-full transition-all duration-300 rounded-full bg-amber-500";
      text.innerText = "Good";
      text.className = "font-semibold text-amber-500";
    } else {
      bar.style.width = "100%";
      bar.className = "h-full transition-all duration-300 rounded-full bg-emerald-500";
      text.innerText = "Strong (Optimal)";
      text.className = "font-semibold text-emerald-500";
    }
  }

  async function loadAdminSessions() {
    const container = document.getElementById("adminSessionsContainer");
    if (!container) return;
    try {
      const res = await adminFetch("/api/admin/profile/sessions");
      if (!res.ok) throw new Error("Failed to load sessions");
      const data = await res.json();
      const sessions = data.sessions || [];
      const statEl = document.getElementById("profStatSessions");
      if (statEl) statEl.innerText = sessions.length;

      if (!sessions.length) {
        container.innerHTML = `<p class="text-xs text-slate-400 py-3 text-center">No active sessions found.</p>`;
        return;
      }

      container.innerHTML = sessions.map(s => `
        <div class="p-3 rounded-2xl ${s.is_current ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800/80' : 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700/60'} border flex items-center justify-between text-xs transition">
          <div class="flex items-center gap-2.5">
            <span class="w-2 h-2 rounded-full ${s.is_current ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}"></span>
            <div>
              <div class="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                <span>Session #${s.id}</span>
                ${s.is_current ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold uppercase">THIS DEVICE</span>' : ''}
              </div>
              <div class="text-[10px] text-slate-400 font-mono">
                Token: ${s.token_preview || '••••••••'} • Created: ${s.created_at || 'Recently'}
              </div>
            </div>
          </div>
          ${!s.is_current ? `
            <button type="button" onclick="handleRevokeSingleSession(${s.id})" class="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-600 text-[10px] font-semibold flex items-center gap-1 transition">
              <i data-lucide="trash-2" class="w-3 h-3"></i>
              <span>Revoke</span>
            </button>
          ` : '<span class="text-[10px] text-slate-400 font-medium">Active now</span>'}
        </div>
      `).join("");
      safeCreateIcons();
    } catch (e) {
      container.innerHTML = `<p class="text-xs text-rose-500 py-2">Failed to load active sessions.</p>`;
    }
  }

  window.handleRevokeSingleSession = async function(sessionId) {
    if (!confirm(`Are you sure you want to revoke session #${sessionId}?`)) return;
    try {
      const res = await adminFetch(`/api/admin/profile/sessions/${sessionId}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to revoke session");
      showToast("Session revoked.", "info");
      loadAdminSessions();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  async function handleRevokeOtherAdminSessions() {
    if (!confirm("Are you sure you want to sign out all other devices and browser sessions?")) return;
    try {
      const res = await adminFetch("/api/admin/profile/sessions/revoke-others", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to revoke other sessions");
      showToast(data.message || "All other sessions revoked.", "success");
      loadAdminSessions();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  function handleExportAdminProfile() {
    if (!currentAdminProfile) {
      showToast("Profile data not loaded yet.", "error");
      return;
    }
    const exportData = {
      profile: currentAdminProfile,
      system: {
        exported_at: new Date().toISOString(),
        user_agent: navigator.userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
      }
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `admin_profile_${currentAdminProfile.username || "admin"}_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Admin profile and audit data downloaded!", "success");
  }

  // --------------------------------------------------------
  // INDEXNOW & INSTANT SEO ENGINE
  // --------------------------------------------------------
  async function loadIndexNowTab() {
    try {
      const res = await adminFetch("/api/admin/indexnow/status");
      if (!res.ok) throw new Error("Failed to load IndexNow status.");
      const data = await res.json();

      // Update Health Badges
      const keyBadge = document.getElementById("idxKeyStatusBadge");
      if (keyBadge) {
        if (data.key_file_exists) {
          keyBadge.innerText = "Hosted & Valid";
          keyBadge.parentElement.className = "flex items-center justify-center gap-1.5 mt-1 text-emerald-600 dark:text-emerald-400 font-bold text-xs";
        } else {
          keyBadge.innerText = "File Missing";
          keyBadge.parentElement.className = "flex items-center justify-center gap-1.5 mt-1 text-rose-600 dark:text-rose-400 font-bold text-xs";
        }
      }

      const autoBadge = document.getElementById("idxAutoStatusBadge");
      if (autoBadge) {
        autoBadge.innerText = (data.auto_submit_blog && data.auto_submit_cms) ? "Enabled (Blog + CMS)" : data.auto_submit_blog ? "Blog Only" : "Manual Only";
      }

      // Populate Settings Inputs
      const keyInput = document.getElementById("idxConfigKey");
      if (keyInput) keyInput.value = data.key || "";

      const hostInput = document.getElementById("idxConfigHost");
      if (hostInput) hostInput.value = data.host || "pnglike.com";

      const keyLocInput = document.getElementById("idxConfigKeyLocation");
      if (keyLocInput) keyLocInput.value = data.key_location || `https://${data.host}/${data.key}.txt`;

      const keyLink = document.getElementById("idxKeyFileLink");
      if (keyLink) {
        keyLink.href = data.key_location || `https://${data.host}/${data.key}.txt`;
      }

      const blogToggle = document.getElementById("idxAutoBlogToggle");
      if (blogToggle) blogToggle.checked = !!data.auto_submit_blog;

      const cmsToggle = document.getElementById("idxAutoCmsToggle");
      if (cmsToggle) cmsToggle.checked = !!data.auto_submit_cms;

      // Populate Submissions Table
      renderIndexNowSubmissions(data.submissions || []);
      safeCreateIcons();
    } catch (err) {
      showToast(err.message || "Could not load IndexNow settings.", "error");
    }
  }

  function renderIndexNowSubmissions(submissions) {
    const tbody = document.getElementById("idxSubmissionsTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!submissions || submissions.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="py-8 text-center text-slate-400">
            <i data-lucide="inbox" class="w-6 h-6 mx-auto mb-2 opacity-50"></i>
            <div>No IndexNow submissions recorded yet. Use the quick buttons above to submit pages.</div>
          </td>
        </tr>
      `;
      safeCreateIcons();
      return;
    }

    submissions.forEach(sub => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50 dark:hover:bg-slate-800/40 text-xs";

      let statusBadge = "";
      if (sub.status === "success" || sub.status_code === 200) {
        statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">200 OK • PUSHED</span>`;
      } else if (sub.status_code === 202) {
        statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">202 ACCEPTED</span>`;
      } else if (sub.status === "warning" || sub.status_code === 429) {
        statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">RATE LIMITED</span>`;
      } else {
        statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">${sub.status_code || "ERR"} FAILED</span>`;
      }

      const previewUrls = (sub.urls || []).slice(0, 2).map(u => {
        try {
          return new URL(u).pathname || u;
        } catch (_) {
          return u;
        }
      }).join(", ");
      const extraCount = (sub.urls || []).length > 2 ? ` +${(sub.urls || []).length - 2} more` : "";

      tr.innerHTML = `
        <td class="py-2.5 font-mono text-slate-500 whitespace-nowrap">${sub.submitted_at || "-"}</td>
        <td class="py-2.5">
          <span class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold uppercase text-[10px]">${sub.triggered_by || "manual"}</span>
        </td>
        <td class="py-2.5 font-bold text-slate-800 dark:text-slate-200">${sub.urls_count || (sub.urls || []).length}</td>
        <td class="py-2.5 max-w-[240px] truncate text-slate-600 dark:text-slate-300 font-mono text-[11px]" title="${(sub.urls || []).join('\n')}">
          ${previewUrls}${extraCount}
        </td>
        <td class="py-2.5 font-mono text-slate-500">${sub.status_code ? `HTTP ${sub.status_code}` : "N/A"}</td>
        <td class="py-2.5 text-right whitespace-nowrap">${statusBadge}</td>
      `;
      tbody.appendChild(tr);
    });
    safeCreateIcons();
  }

  // --------------------------------------------------------
  // THEME & TOAST
  // --------------------------------------------------------
  function initTheme() {
    const btn = document.getElementById("adminThemeBtn");
    const isDark = localStorage.getItem("theme") !== "light";
    document.documentElement.classList.toggle("dark", isDark);
    btn.addEventListener("click", () => {
      const nextDark = !document.documentElement.classList.contains("dark");
      document.documentElement.classList.toggle("dark", nextDark);
      localStorage.setItem("theme", nextDark ? "dark" : "light");
      safeCreateIcons();
    });
  }

  function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    let bg = "bg-slate-900 text-white border-slate-700";
    let icon = "info";
    if (type === "success") {
      bg = "bg-emerald-600 text-white border-emerald-500";
      icon = "check-circle";
    } else if (type === "error") {
      bg = "bg-rose-600 text-white border-rose-500";
      icon = "alert-circle";
    }
    toast.className = `${bg} pointer-events-auto border px-4 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-xs font-semibold`;
    toast.innerHTML = `<i data-lucide="${icon}" class="w-4 h-4"></i><span>${message}</span>`;
    container.appendChild(toast);
    safeCreateIcons();
    setTimeout(() => toast.remove(), 3500);
  }
});
