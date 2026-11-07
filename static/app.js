// PngLike Studio Client Application Logic
document.addEventListener("DOMContentLoaded", () => {
  // Default 9 IMAGE Tools Catalog (Free tools listed first; Background Remover is default)
  const DEFAULT_TOOLS = [
    { id: "bg-remover", name: "Background Remover", badge: "Free • Default", is_free: true, requires_image: true, desc: "Instant AI background cutout with hair-level alpha refinement, mask preview, and studio backdrop replacement." },
    { id: "image-editor", name: "Image Editor", badge: "Free Studio", is_free: true, requires_image: true, desc: "Color grading, exposure, contrast, saturation, warmth, sharpness, rotation, flip, and aspect cropping." },
    { id: "skin-enhancer", name: "Skin Enhancer", badge: "Free Portrait", is_free: true, requires_image: true, desc: "Studio portrait retouching with blemish smoothing, warm radiance glow, and eye/hair crispness." },
    { id: "image-upscaler", name: "Image Upscaler", badge: "Pro Super-Res", is_free: false, requires_image: true, desc: "2x and 4x Lanczos-4 super-resolution upscaling with bilateral denoising and unsharp edge enhancement." },
    { id: "image-extender", name: "Image Extender", badge: "Pro Outpaint", is_free: false, requires_image: true, desc: "Expand canvas to 16:9, 9:16, 1:1, 4:3, or 21:9 using Telea Navier-Stokes outpainting and reflection." },
    { id: "variations", name: "Variations", badge: "Pro Restyle", is_free: false, requires_image: true, desc: "Generate artistic style variations: Cyberpunk, Watercolor, Oil Painting, Sketch, Pop Art, Anime, Noir, and Warm." },
    { id: "cinematic-shot", name: "Cinematic Shot", badge: "Pro Anamorphic", is_free: false, requires_image: true, desc: "AI depth-of-field bokeh, Teal & Orange / Bleach Bypass color grading, anamorphic lens flare, and 2.39:1 letterbox." },
    { id: "relight", name: "Relight", badge: "Pro 3D Light", is_free: false, requires_image: true, desc: "AI subject segmentation with surface-normal estimation, directional 3D point lighting, neon split, and rim glow." },
    { id: "change-camera", name: "Change Camera", badge: "Pro Perspective", is_free: false, requires_image: true, desc: "3D homography camera angle tilt/pan/dutch-roll and optical lens distortion (Wide, Telephoto, Fisheye, Dolly)." }
  ];

  const TOOL_ICONS = {
    "image-editor": "sliders",
    "image-upscaler": "maximize-2",
    "image-extender": "expand",
    "variations": "copy",
    "cinematic-shot": "film",
    "bg-remover": "scissors",
    "skin-enhancer": "user-check",
    "relight": "sun",
    "change-camera": "camera"
  };

  const TOOL_HERO_COPY = {
    "image-editor": {
      title: "Edit & Color-Grade Photos",
      highlight: "Instantly in Studio",
      subtitle: "Fine-tune brightness, contrast, saturation, sharpness, warmth, aspect crop, rotation, and studio color filters."
    },
    "image-upscaler": {
      title: "Upscale Images 2x & 4x",
      highlight: "with Super-Resolution",
      subtitle: "Enhance photo resolution by 2x or 4x with bilateral denoising and crisp unsharp edge enhancement."
    },
    "image-extender": {
      title: "Extend & Outpaint Images",
      highlight: "to Any Aspect Ratio",
      subtitle: "Expand vertical or square photos into 16:9, 9:16, 1:1, 4:3, or 21:9 frames with seamless border synthesis."
    },
    "variations": {
      title: "Generate Style Variations",
      highlight: "Instantly with AI",
      subtitle: "Reimagine your photo across 8 artistic styles: Cyberpunk, Watercolor, Oil Painting, Sketch, Pop Art, Anime, Noir, and Warm."
    },
    "cinematic-shot": {
      title: "Create Cinematic Shots",
      highlight: "with AI Depth Bokeh",
      subtitle: "Transform photos into movie stills with AI subject depth-of-field bokeh, Hollywood LUT grading, anamorphic flare, and 2.39:1 letterbox."
    },
    "bg-remover": {
      title: "Remove Image Backgrounds",
      highlight: "Instantly with AI",
      subtitle: "High-precision AI background cutout for portraits, products, and graphics with transparent PNG export and studio backdrops."
    },
    "skin-enhancer": {
      title: "Retouch Portrait Skin",
      highlight: "with Studio Precision",
      subtitle: "Smooth blemishes and add warm skin radiance while keeping eyes, eyelashes, and natural portrait details sharp."
    },
    "relight": {
      title: "Relight Photos in 3D",
      highlight: "with Studio Lighting",
      subtitle: "Isolate your subject and apply directional 3D key lights, dual-neon split lighting, rim glow, and background dimming."
    },
    "change-camera": {
      title: "Change Camera & Lens",
      highlight: "in 3D Perspective",
      subtitle: "Transform camera tilt, pan, and Dutch roll angles with 24mm Wide, 85mm Telephoto, 12mm Fisheye, and Dolly Zoom optics."
    }
  };

  // Application State
  const state = {
    activeTool: "bg-remover",
    toolsCatalog: [...DEFAULT_TOOLS],
    originalFile: null,
    originalUrl: null,
    originalImgElement: null,
    cutoutBlob: null,
    cutoutImgElement: null,
    backdropImgElement: null,
    sliderPos: 50, // Percentage 0 - 100
    isDraggingSlider: false,
    viewMode: 'split', // 'split', 'side', 'cutout'
    bgMode: 'transparent', // 'transparent', 'solid', 'gradient', 'backdrop'
    solidColor: '#ffffff',
    gradientStyle: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    backdropBlur: 0,
    exportFormat: 'png',
    isProcessing: false,
    telemetry: {
      timeMs: 0,
      width: 0,
      height: 0
    }
  };

  // DOM Elements
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const browseBtn = document.getElementById("browseBtn");
  const uploadView = document.getElementById("uploadView");
  const editorView = document.getElementById("editorView");
  const reuploadBtn = document.getElementById("reuploadBtn");
  const samplesContainer = document.getElementById("samplesContainer");
  const processingOverlay = document.getElementById("processingOverlay");

  // Canvas & Stage
  const imageStage = document.getElementById("imageStage");
  const sliderWrapper = document.getElementById("sliderWrapper");
  const sideBySideWrapper = document.getElementById("sideBySideWrapper");
  const outputCanvas = document.getElementById("outputCanvas");
  const sideOutputCanvas = document.getElementById("sideOutputCanvas");
  const originalImg = document.getElementById("originalImg");
  const sideOriginalImg = document.getElementById("sideOriginalImg");
  const originalClipLayer = document.getElementById("originalClipLayer");
  const sliderDivider = document.getElementById("sliderDivider");
  const processedBackdropLayer = document.getElementById("processedBackdropLayer");

  // View Mode Buttons
  const viewSplitBtn = document.getElementById("viewSplitBtn");
  const viewSideBtn = document.getElementById("viewSideBtn");
  const viewCutoutBtn = document.getElementById("viewCutoutBtn");

  // Background Control Elements
  const bgModeTransparent = document.getElementById("bgModeTransparent");
  const bgModeSolid = document.getElementById("bgModeSolid");
  const bgModeGradient = document.getElementById("bgModeGradient");
  const bgModeBackdrop = document.getElementById("bgModeBackdrop");
  const solidColorPanel = document.getElementById("solidColorPanel");
  const gradientPanel = document.getElementById("gradientPanel");
  const backdropPanel = document.getElementById("backdropPanel");
  const customColorInput = document.getElementById("customColorInput");
  const backdropFileInput = document.getElementById("backdropFileInput");
  const backdropBlurSlider = document.getElementById("backdropBlurSlider");
  const blurValText = document.getElementById("blurValText");

  // AI & Quality Controls
  const modelSelect = document.getElementById("modelSelect");
  const alphaMattingToggle = document.getElementById("alphaMattingToggle");
  const alphaMattingControls = document.getElementById("alphaMattingControls");
  const afSlider = document.getElementById("afSlider");
  const abSlider = document.getElementById("abSlider");
  const aeSlider = document.getElementById("aeSlider");
  const afValText = document.getElementById("afValText");
  const abValText = document.getElementById("abValText");
  const aeValText = document.getElementById("aeValText");
  const postProcessToggle = document.getElementById("postProcessToggle");
  const maskOnlyToggle = document.getElementById("maskOnlyToggle");
  const reprocessBtn = document.getElementById("reprocessBtn");

  // Export Controls
  const downloadBtn = document.getElementById("downloadBtn");
  const copyClipboardBtn = document.getElementById("copyClipboardBtn");
  const exportFormatInputs = document.querySelectorAll('input[name="exportFormat"]');

  // Stats Telemetry
  const statDimensions = document.getElementById("statDimensions");
  const statTime = document.getElementById("statTime");
  const modelStatusText = document.getElementById("modelStatusText");

  // Tabs
  const tabStudioBtn = document.getElementById("tabStudioBtn");
  const tabBatchBtn = document.getElementById("tabBatchBtn");
  const tabHistoryBtn = document.getElementById("tabHistoryBtn");
  const mobileTabStudioBtn = document.getElementById("mobileTabStudioBtn");
  const mobileTabBatchBtn = document.getElementById("mobileTabBatchBtn");
  const mobileTabHistoryBtn = document.getElementById("mobileTabHistoryBtn");
  const studioSection = document.getElementById("studioSection");
  const batchSection = document.getElementById("batchSection");
  const historySection = document.getElementById("historySection");

  // MySQL & Presets Elements
  const dbStatusBtn = document.getElementById("dbStatusBtn");
  const dbStatusText = document.getElementById("dbStatusText");
  const presetSelect = document.getElementById("presetSelect");
  const savePresetBtn = document.getElementById("savePresetBtn");
  const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
  const clearHistoryBtn = document.getElementById("clearHistoryBtn");
  const historyGrid = document.getElementById("historyGrid");
  const historyEmptyState = document.getElementById("historyEmptyState");
  const metricTotalJobs = document.getElementById("metricTotalJobs");
  const metricAvgTime = document.getElementById("metricAvgTime");
  const metricTopModel = document.getElementById("metricTopModel");
  const metricTotalStorage = document.getElementById("metricTotalStorage");
  const metricDbEngine = document.getElementById("metricDbEngine");
  const metricDbHost = document.getElementById("metricDbHost");

  // MySQL Modal Elements
  const dbConfigModal = document.getElementById("dbConfigModal");
  const openDbModalBtn = document.getElementById("openDbModalBtn");
  const closeDbModalBtn = document.getElementById("closeDbModalBtn");
  const cancelDbModalBtn = document.getElementById("cancelDbModalBtn");
  const saveDbConfigBtn = document.getElementById("saveDbConfigBtn");
  const dbModalStatusBanner = document.getElementById("dbModalStatusBanner");
  const dbHostInput = document.getElementById("dbHostInput");
  const dbPortInput = document.getElementById("dbPortInput");
  const dbUserInput = document.getElementById("dbUserInput");
  const dbPassInput = document.getElementById("dbPassInput");
  const dbNameInput = document.getElementById("dbNameInput");

  let savedPresets = [];

  // Batch Elements
  const batchDropZone = document.getElementById("batchDropZone");
  const batchFileInput = document.getElementById("batchFileInput");
  const batchProcessContainer = document.getElementById("batchProcessContainer");
  const batchCountText = document.getElementById("batchCountText");
  const batchProgressBarContainer = document.getElementById("batchProgressBarContainer");
  const batchProgressBar = document.getElementById("batchProgressBar");
  const batchStartBtn = document.getElementById("batchStartBtn");
  const batchDownloadZipBtn = document.getElementById("batchDownloadZipBtn");
  const batchItemsGrid = document.getElementById("batchItemsGrid");

  let batchFiles = [];
  let batchZipBlob = null;
  let userQuotaCache = null;

  // Initialize App
  initTheme();
  renderToolsMenus();
  loadSiteConfig();
  checkServerStatus();
  loadSampleImages();
  loadPresets();
  setupEventListeners();
  setupAllToolsEventListeners();
  fetchAndRenderQuota();

  // ----------------------------------------------------
  // EVENT LISTENERS SETUP
  // ----------------------------------------------------
  function setupEventListeners() {
    // Prevent synthetic fileInput click events from bubbling up to parent containers
    if (fileInput) {
      fileInput.addEventListener("click", (e) => {
        e.stopPropagation();
      });
    }

    // Browse Button & Dropzone
    if (browseBtn) {
      browseBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (fileInput) {
          fileInput.value = "";
          fileInput.click();
        }
      });
    }

    if (dropZone) {
      dropZone.addEventListener("click", (e) => {
        if (e.target === fileInput || (browseBtn && browseBtn.contains(e.target))) {
          return;
        }
        if (fileInput) {
          fileInput.value = "";
          fileInput.click();
        }
      });

      dropZone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (fileInput) {
            fileInput.value = "";
            fileInput.click();
          }
        }
      });
    }

    if (fileInput) {
      fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
          handleImageFile(e.target.files[0]);
        }
      });
    }

    if (reuploadBtn) {
      reuploadBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (fileInput) {
          fileInput.value = "";
          fileInput.click();
        }
      });
    }

    // Drag and drop events for dropzone
    ["dragenter", "dragover"].forEach(event => {
      dropZone.addEventListener(event, (e) => {
        e.preventDefault();
        dropZone.classList.add("border-blue-500", "scale-[1.01]");
      });
    });

    ["dragleave", "drop"].forEach(event => {
      dropZone.addEventListener(event, (e) => {
        e.preventDefault();
        dropZone.classList.remove("border-blue-500", "scale-[1.01]");
      });
    });

    dropZone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleImageFile(e.dataTransfer.files[0]);
      }
    });

    // Global Paste Support (Ctrl + V)
    window.addEventListener("paste", (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (let item of items) {
        if (item.type.indexOf("image") !== -1) {
          const file = item.getAsFile();
          if (file) {
            handleImageFile(file);
            showToast("Pasted image from clipboard!", "success");
            break;
          }
        }
      }
    });

    // Comparison Slider Interaction
    setupSliderInteraction();

    // View Mode Switching
    viewSplitBtn.addEventListener("click", () => setViewMode("split"));
    viewSideBtn.addEventListener("click", () => setViewMode("side"));
    viewCutoutBtn.addEventListener("click", () => setViewMode("cutout"));

    // Background Mode Switching
    bgModeTransparent.addEventListener("click", () => setBgMode("transparent"));
    bgModeSolid.addEventListener("click", () => setBgMode("solid"));
    bgModeGradient.addEventListener("click", () => setBgMode("gradient"));
    bgModeBackdrop.addEventListener("click", () => setBgMode("backdrop"));

    // Solid Color Swatches
    document.querySelectorAll(".color-swatch").forEach(swatch => {
      swatch.addEventListener("click", () => {
        state.solidColor = swatch.getAttribute("data-color");
        setBgMode("solid");
        renderCompositedOutput();
      });
    });

    customColorInput.addEventListener("input", (e) => {
      state.solidColor = e.target.value;
      setBgMode("solid");
      renderCompositedOutput();
    });

    // Gradient Presets
    document.querySelectorAll(".gradient-swatch").forEach(swatch => {
      swatch.addEventListener("click", () => {
        state.gradientStyle = swatch.getAttribute("data-gradient");
        setBgMode("gradient");
        renderCompositedOutput();
      });
    });

    // Backdrop Image Upload & Blur
    backdropFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = (event) => {
          const img = new Image();
          img.onload = () => {
            state.backdropImgElement = img;
            setBgMode("backdrop");
            renderCompositedOutput();
          };
          img.src = event.target.result;
        };
        reader.readAsDataURL(file);
      }
    });

    backdropBlurSlider.addEventListener("input", (e) => {
      state.backdropBlur = parseInt(e.target.value, 10);
      blurValText.innerText = `${state.backdropBlur}px`;
      if (state.bgMode === "backdrop") {
        renderCompositedOutput();
      }
    });

    // Alpha Matting Sliders & Toggle
    alphaMattingToggle.addEventListener("change", () => {
      if (alphaMattingToggle.checked) {
        alphaMattingControls.classList.remove("hidden");
      } else {
        alphaMattingControls.classList.add("hidden");
      }
    });

    afSlider.addEventListener("input", (e) => {
      afValText.innerText = e.target.value;
    });
    abSlider.addEventListener("input", (e) => {
      abValText.innerText = e.target.value;
    });
    aeSlider.addEventListener("input", (e) => {
      aeValText.innerText = e.target.value;
    });

    // Re-run AI inference
    reprocessBtn.addEventListener("click", () => {
      if (state.originalFile) {
        processBackgroundRemoval(state.originalFile);
      }
    });

    // Export Format Radios
    exportFormatInputs.forEach(input => {
      input.addEventListener("change", (e) => {
        state.exportFormat = e.target.value;
        // Update radio styles
        document.querySelectorAll(".format-choice").forEach(lbl => {
          lbl.classList.remove("border-blue-500", "bg-blue-50", "dark:bg-blue-950/40", "text-blue-600", "dark:text-blue-400");
          lbl.classList.add("border-slate-200", "dark:border-slate-700");
        });
        const parent = e.target.closest(".format-choice");
        if (parent) {
          parent.classList.add("border-blue-500", "bg-blue-50", "dark:bg-blue-950/40", "text-blue-600", "dark:text-blue-400");
          parent.classList.remove("border-slate-200", "dark:border-slate-700");
        }
      });
    });

    // Download & Clipboard Actions
    downloadBtn.addEventListener("click", handleDownload);
    copyClipboardBtn.addEventListener("click", handleCopyToClipboard);

    // Tab Navigation
    tabStudioBtn.addEventListener("click", () => switchMainTab("studio"));
    tabBatchBtn.addEventListener("click", () => switchMainTab("batch"));
    tabHistoryBtn.addEventListener("click", () => switchMainTab("history"));
    mobileTabStudioBtn.addEventListener("click", () => switchMainTab("studio"));
    mobileTabBatchBtn.addEventListener("click", () => switchMainTab("batch"));
    mobileTabHistoryBtn.addEventListener("click", () => switchMainTab("history"));

    // MySQL Database & Presets Events
    dbStatusBtn.addEventListener("click", openDbConfigModal);
    openDbModalBtn.addEventListener("click", openDbConfigModal);
    closeDbModalBtn.addEventListener("click", () => dbConfigModal.classList.add("hidden"));
    cancelDbModalBtn.addEventListener("click", () => dbConfigModal.classList.add("hidden"));
    saveDbConfigBtn.addEventListener("click", handleSaveDbConfig);
    refreshHistoryBtn.addEventListener("click", loadHistoryAndAnalytics);
    clearHistoryBtn.addEventListener("click", handleClearAllHistory);
    if (presetSelect) presetSelect.addEventListener("change", handleApplyPreset);
    if (savePresetBtn) savePresetBtn.addEventListener("click", handleSaveNewPreset);

    // Restriction Modal Close Listener
    document.getElementById("closeRestrictionModalBtn")?.addEventListener("click", () => {
      document.getElementById("guestRestrictionModal")?.classList.add("hidden");
    });

    // Batch Processing Events
    setupBatchProcessingEvents();
  }

  // ----------------------------------------------------
  // GUEST & REGISTERED ACCESS RESTRICTIONS & GLOBAL QUOTA TIMER
  // ----------------------------------------------------
  let quotaCountdownInterval = null;
  let activeLimitationToaster = null;
  let wasRestingBefore = false;

  function stopGlobalQuotaCountdown() {
    if (quotaCountdownInterval) {
      clearInterval(quotaCountdownInterval);
      quotaCountdownInterval = null;
    }
  }

  function showLimitationToaster(data) {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    if (activeLimitationToaster) {
      activeLimitationToaster.remove();
      activeLimitationToaster = null;
    }

    const toaster = document.createElement("div");
    toaster.className = "pointer-events-auto bg-slate-900/95 dark:bg-dark-900/95 text-white border-2 border-amber-500/70 shadow-2xl shadow-amber-500/20 rounded-3xl p-4 sm:p-5 flex flex-col gap-3 backdrop-blur-xl transform transition-all duration-300 translate-y-3 opacity-0 w-full sm:w-[380px] relative overflow-hidden";
    
    const resetTimeUtc = data?.reset_time_utc || "";
    const resetTimestamp = data?.reset_timestamp || (Math.floor(Date.now() / 1000) + 1800);
    const serverTimestamp = data?.server_timestamp || Math.floor(Date.now() / 1000);
    const serverOffset = serverTimestamp - Math.floor(Date.now() / 1000);

    toaster.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center shrink-0 shadow-inner animate-pulse">
            <i data-lucide="timer" class="w-5 h-5"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                Limitation Reached
              </span>
              <span class="text-[10px] text-slate-400 font-mono">10/10 Used</span>
            </div>
            <h4 class="text-sm font-bold text-white mt-0.5">30-Minute Rest Cooldown</h4>
          </div>
        </div>
        <button type="button" class="toaster-close-btn p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition" aria-label="Close">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <p class="text-xs text-slate-300 leading-relaxed">
        You have completed your 10-image limitation. A 30-minute rest cooldown is active to protect server resources. 10 fresh uses will unlock automatically.
      </p>

      <div class="px-3.5 py-2.5 rounded-2xl bg-slate-800/80 border border-amber-500/30 flex items-center justify-between">
        <div class="flex items-center gap-1.5 text-xs text-amber-200">
          <i data-lucide="clock" class="w-3.5 h-3.5 text-amber-400"></i>
          <span class="font-medium">Global Reset Countdown:</span>
        </div>
        <span class="toaster-live-timer font-mono text-sm font-extrabold text-amber-400 tracking-wider">
          ${data?.time_remaining_formatted || "30:00"}
        </span>
      </div>

      ${resetTimeUtc ? `
      <div class="text-[10px] text-slate-400 flex items-center justify-between px-1">
        <span>Global Reset Moment:</span>
        <span class="font-mono text-slate-300">${resetTimeUtc} (UTC)</span>
      </div>
      ` : ""}

      <div class="h-1 w-full bg-slate-800 rounded-full overflow-hidden mt-1">
        <div class="toaster-progress-bar h-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all duration-1000" style="width: 100%;"></div>
      </div>
    `;

    container.appendChild(toaster);
    safeCreateIcons();

    setTimeout(() => {
      toaster.classList.remove("translate-y-3", "opacity-0");
    }, 10);

    activeLimitationToaster = toaster;

    toaster.querySelector(".toaster-close-btn")?.addEventListener("click", () => {
      toaster.classList.add("translate-y-3", "opacity-0");
      setTimeout(() => {
        if (activeLimitationToaster === toaster) activeLimitationToaster = null;
        toaster.remove();
      }, 300);
    });

    const timerEl = toaster.querySelector(".toaster-live-timer");
    const progressEl = toaster.querySelector(".toaster-progress-bar");
    const totalRestSeconds = 30 * 60;

    const toasterInterval = setInterval(() => {
      if (!toaster.isConnected) {
        clearInterval(toasterInterval);
        return;
      }
      const currentGlobalTime = Math.floor(Date.now() / 1000) + serverOffset;
      const remaining = Math.max(0, resetTimestamp - currentGlobalTime);

      if (remaining <= 0) {
        clearInterval(toasterInterval);
        if (timerEl) timerEl.textContent = "00:00";
        if (progressEl) progressEl.style.width = "0%";
        setTimeout(() => {
          toaster.classList.add("translate-y-3", "opacity-0");
          setTimeout(() => {
            if (activeLimitationToaster === toaster) activeLimitationToaster = null;
            toaster.remove();
          }, 300);
          showToast("🎉 30-Minute Rest complete! 10 fresh images are now available.", "success");
          fetchAndRenderQuota();
        }, 1500);
        return;
      }

      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      if (timerEl) {
        timerEl.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
      }
      if (progressEl) {
        const pct = Math.min(100, Math.max(0, (remaining / totalRestSeconds) * 100));
        progressEl.style.width = `${pct}%`;
      }
    }, 1000);
  }

  function startGlobalQuotaCountdown(resetTimestamp, serverTimestamp) {
    stopGlobalQuotaCountdown();

    const clientNow = Math.floor(Date.now() / 1000);
    const serverOffset = serverTimestamp ? (serverTimestamp - clientNow) : 0;

    const tick = () => {
      const currentGlobalTime = Math.floor(Date.now() / 1000) + serverOffset;
      const remaining = Math.max(0, resetTimestamp - currentGlobalTime);

      const pill = document.getElementById("accessQuotaPill");
      const text = document.getElementById("accessQuotaText");

      if (remaining <= 0) {
        stopGlobalQuotaCountdown();
        if (text) {
          text.innerHTML = `<span class="text-emerald-500 font-bold">Pro Studio</span> • Quota Reset! Refreshing...`;
        }
        setTimeout(fetchAndRenderQuota, 1200);
        return;
      }

      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      const formatted = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

      if (text) {
        text.innerHTML = `<span class="text-amber-500 font-bold flex items-center gap-1"><i data-lucide="clock" class="w-3.5 h-3.5"></i> Rest Cooldown</span> • <span class="font-mono font-bold">${formatted}</span>`;
        if (pill) {
          pill.className = "hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border bg-amber-50/60 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300";
        }
      }
      safeCreateIcons();
    };

    tick();
    quotaCountdownInterval = setInterval(tick, 1000);
  }

  async function fetchAndRenderQuota() {
    try {
      const activeUserToken = localStorage.getItem("rembg_user_token") || "";
      const headers = activeUserToken ? { "X-User-Token": activeUserToken } : {};
      const res = await fetch("/api/user/quota", { headers });
      if (!res.ok) return;
      const data = await res.json();
      userQuotaCache = data;

      const pill = document.getElementById("accessQuotaPill");
      const text = document.getElementById("accessQuotaText");
      if (pill && text) {
        pill.classList.remove("hidden");
        if (data.is_registered) {
          if (data.is_resting && data.reset_timestamp) {
            startGlobalQuotaCountdown(data.reset_timestamp, data.server_timestamp);
            if (!wasRestingBefore) {
              wasRestingBefore = true;
              showLimitationToaster(data);
            }
          } else {
            stopGlobalQuotaCountdown();
            if (wasRestingBefore) {
              wasRestingBefore = false;
              showToast("🎉 Rest cooldown complete! 10 fresh images are now available.", "success");
            }
            text.innerHTML = `<span class="text-emerald-500 font-bold">Pro Studio</span> • <strong class="text-emerald-600 dark:text-emerald-400 font-bold">${data.remaining_today}/${data.daily_limit} left</strong> (30m rest)`;
            pill.className = "hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border bg-emerald-50/60 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300";
          }
        } else {
          stopGlobalQuotaCountdown();
          text.innerHTML = `Guest: <strong class="text-indigo-600 dark:text-indigo-400 font-bold">${data.remaining_today}/${data.daily_limit} free</strong> left`;
          pill.className = "hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border bg-slate-100 dark:bg-slate-800/80 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300";
        }
      }

      // Mark restricted tools in UI
      const restricted = data.restricted_tools || [];
      document.querySelectorAll("[data-tool-id]").forEach((btn) => {
        const tid = btn.getAttribute("data-tool-id");
        if (!data.is_registered && restricted.includes(tid)) {
          if (!btn.querySelector(".pro-lock-badge")) {
            const badge = document.createElement("span");
            badge.className = "pro-lock-badge text-[9px] px-1.5 py-0.5 rounded font-mono font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20 shrink-0";
            badge.textContent = "Pro";
            btn.appendChild(badge);
          }
        } else {
          btn.querySelector(".pro-lock-badge")?.remove();
        }
      });
    } catch (e) {
      console.warn("Could not load quota:", e);
    }
  }

  function showGuestRestrictionModal(customMsg = "") {
    const modal = document.getElementById("guestRestrictionModal");
    if (!modal) return;
    const msgEl = document.getElementById("restrictionModalMessage");
    const titleEl = document.getElementById("restrictionModalTitle");
    if (msgEl && customMsg) {
      msgEl.textContent = customMsg;
    }
    if (titleEl) {
      if (customMsg.includes("cooldown") || customMsg.includes("limitation reached") || customMsg.includes("limit reached")) {
        titleEl.textContent = "30-Minute Rest Cooldown Active";
        fetchAndRenderQuota();
      } else {
        titleEl.textContent = "Unlock All 9 AI Tools";
      }
    }
    modal.classList.remove("hidden");
    safeCreateIcons();
  }

  // ----------------------------------------------------
  // SERVER STATUS, DYNAMIC CMS CONFIG & SAMPLES
  // ----------------------------------------------------
  async function loadSiteConfig() {
    try {
      const res = await fetch("/api/site-config");
      if (!res.ok) return;
      const data = await res.json();
      const s = data.settings || {};

      // Apply Dynamic Branding & Copy
      if (s.site_title) {
        if (s.site_title !== "PngLike") {
          document.title = `${s.site_title} — ${s.site_tagline || "9-in-1 AI Image Suite"}`;
        }
        const titleEl = document.getElementById("brandSiteTitle");
        if (titleEl) titleEl.innerText = s.site_title;
      }
      if (s.site_badge) {
        const badgeEl = document.getElementById("brandSiteBadge");
        if (badgeEl) badgeEl.innerText = s.site_badge;
      }
      if (s.site_tagline) {
        const tagEl = document.getElementById("brandSiteTagline");
        if (tagEl) tagEl.innerText = s.site_tagline;
      }
      if (s.hero_title) {
        const h1 = document.getElementById("heroMainTitle");
        if (h1) h1.innerText = s.hero_title;
      }
      if (s.hero_highlight) {
        const hh = document.getElementById("heroHighlightTitle");
        if (hh) hh.innerText = s.hero_highlight;
      }
      if (s.hero_subtitle) {
        const hs = document.getElementById("heroSubtitleText");
        if (hs) hs.innerText = s.hero_subtitle;
      }
      if (s.footer_text) {
        const ft = document.getElementById("footerCustomText");
        if (ft) ft.innerText = s.footer_text;
      }

      // Announcement Banner
      const annBar = document.getElementById("siteAnnouncementBar");
      const annText = document.getElementById("siteAnnouncementText");
      if (annBar && annText) {
        const cleanAnn = (s.announcement_text || "").replace(/MySQL|U2-Net/gi, "").trim();
        if (s.announcement_enabled && cleanAnn && !/MySQL|U2-Net/i.test(s.announcement_text || "")) {
          annText.innerText = s.announcement_text;
          annBar.classList.remove("hidden");
        } else {
          annBar.classList.add("hidden");
        }
      }

      // Maintenance Mode Banner
      const maintBanner = document.getElementById("maintenanceBanner");
      const maintText = document.getElementById("maintenanceMessageText");
      if (maintBanner && maintText) {
        if (s.maintenance_mode) {
          maintText.innerText = s.maintenance_message || "Service is undergoing scheduled maintenance.";
          maintBanner.classList.remove("hidden");
        } else {
          maintBanner.classList.add("hidden");
        }
      }

      // Feature Flags
      if (s.enable_batch_mode === false) {
        tabBatchBtn.classList.add("hidden");
        mobileTabBatchBtn.classList.add("hidden");
      }
      if (s.enable_history_tab === false) {
        tabHistoryBtn.classList.add("hidden");
        mobileTabHistoryBtn.classList.add("hidden");
      }
      const alphaSec = document.getElementById("alphaMattingSection");
      if (alphaSec) {
        alphaSec.classList.toggle("hidden", s.enable_alpha_matting === false);
      }
      if (bgModeBackdrop) {
        bgModeBackdrop.classList.toggle("hidden", s.enable_custom_backdrop === false);
      }

      // Dynamic Cutout Precision Modes Dropdown (Clean consumer-friendly labels)
      const STUDIO_PRECISION_LABELS = {
        "u2net": "High Precision Studio (Default)",
        "u2netp": "Fast Express Cutout",
        "u2net_human_seg": "Portrait & Hair Detail",
        "isnet-general-use": "General Objects & Products",
        "isnet-anime": "Anime & Illustration",
        "silueta": "Compact Object Cutout"
      };
      if (data.models && data.models.length > 0) {
        modelSelect.innerHTML = "";
        data.models.forEach(m => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = STUDIO_PRECISION_LABELS[m.id] || m.description || "Studio Cutout Mode";
          if (m.id === s.default_model) opt.selected = true;
          modelSelect.appendChild(opt);
        });
      }

      // Dynamic 10 Image Tools Menu
      if (data.tools && data.tools.length > 0) {
        state.toolsCatalog = data.tools.map(t => ({
          id: t.id,
          name: t.name,
          badge: t.badge || "AI",
          requires_image: t.requires_image !== false,
          desc: t.description || ""
        }));
        renderToolsMenus();
      }
      if (s.default_tool) {
        const hashTool = window.location.hash ? window.location.hash.replace("#", "") : "";
        const initialTool = state.toolsCatalog.some(t => t.id === hashTool) ? hashTool : s.default_tool;
        selectTool(initialTool, false);
      }

      // Check if user is signed in to personalize the header Dashboard button
      const savedUserToken = localStorage.getItem("rembg_user_token") || "";
      if (savedUserToken) {
        fetch("/api/auth/me", { headers: { "X-User-Token": savedUserToken } })
          .then(r => (r.ok ? r.json() : null))
          .then(uData => {
            if (uData && uData.user) {
              const authLbl = document.getElementById("headerUserAuthLabel");
              if (authLbl) authLbl.innerText = `${uData.user.username} • Dashboard`;
            }
          })
          .catch(() => {});
      }
    } catch (e) {
      console.warn("Could not load site config:", e);
    }
  }

  // ----------------------------------------------------
  // ALL 9 IMAGE TOOLS NAVIGATION & SPA DOCK CONTROLS
  // ----------------------------------------------------
  function safeCreateIcons() {
    try {
      if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.lucide.createIcons();
      }
    } catch (e) {
      console.warn("Icon render warning:", e);
    }
  }

  let autoRunTimer = null;
  function debouncedAutoRunTool(delayMs = 180) {
    if (autoRunTimer) clearTimeout(autoRunTimer);
    autoRunTimer = setTimeout(() => {
      executeActiveTool();
    }, delayMs);
  }

  function renderToolsMenus() {
    const sidebarList = document.getElementById("sidebarAllToolsList");
    const headerList = document.getElementById("headerAllToolsList");
    const ribbonList = document.getElementById("spaToolsRibbon");
    if (!sidebarList && !headerList && !ribbonList) return;

    const buildItem = (tool, isPopover) => {
      const isActive = state.activeTool === tool.id;
      const isFree = tool.is_free !== false && ["bg-remover", "image-editor", "skin-enhancer"].includes(tool.id);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("data-tool-id", tool.id);
      if (isPopover) {
        btn.className = `w-full text-left px-3 py-2 rounded-xl text-sm transition flex items-center justify-between ${
          isActive
            ? "bg-blue-50 dark:bg-blue-950/70 text-blue-600 dark:text-blue-400 font-bold"
            : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white font-medium"
        }`;
      } else {
        btn.className = `shrink-0 lg:w-full text-left px-3 py-2 rounded-xl text-sm transition flex items-center justify-between gap-2 ${
          isActive
            ? "bg-blue-50 dark:bg-blue-950/70 text-blue-600 dark:text-blue-400 font-bold shadow-sm border border-blue-200/70 dark:border-blue-800/60"
            : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/70 hover:text-slate-900 dark:hover:text-white font-medium"
        }`;
      }
      btn.innerHTML = `
        <span class="truncate flex items-center gap-1.5">
          ${tool.name}
          ${isFree ? '<span class="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 shrink-0">FREE</span>' : '<span class="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300 shrink-0">PRO</span>'}
        </span>
        ${isActive ? '<span class="w-1.5 h-1.5 rounded-full bg-blue-600 dark:bg-blue-400 shrink-0"></span>' : ''}
      `;
      btn.addEventListener("click", () => {
        const pop = document.getElementById("allToolsPopover");
        if (pop) pop.classList.add("hidden");
        switchMainTab("studio");
        selectTool(tool.id, true);
      });
      return btn;
    };

    const buildRibbonPill = (tool) => {
      const isActive = state.activeTool === tool.id;
      const isFree = tool.is_free !== false && ["bg-remover", "image-editor", "skin-enhancer"].includes(tool.id);
      const iconName = TOOL_ICONS[tool.id] || "wand-2";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("data-ribbon-tool-id", tool.id);
      btn.className = `relative flex flex-col items-center justify-center p-2.5 rounded-2xl border text-center transition-all ${
        isActive
          ? "bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-500/20 scale-[1.01]"
          : "bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700/80 hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-slate-800"
      }`;
      btn.innerHTML = `
        <div class="relative w-full flex items-center justify-center">
          <i data-lucide="${iconName}" class="w-4 h-4 mb-1"></i>
          ${isFree ? '<span class="absolute -top-1.5 -right-1 text-[8px] font-black px-1 rounded-sm bg-emerald-500 text-white leading-tight shadow-xs">FREE</span>' : ''}
        </div>
        <span class="text-[11px] font-bold leading-tight truncate w-full">${tool.name}</span>
      `;
      btn.addEventListener("click", () => {
        switchMainTab("studio");
        selectTool(tool.id, true);
      });
      return btn;
    };

    if (sidebarList) {
      sidebarList.innerHTML = "";
      state.toolsCatalog.forEach(t => sidebarList.appendChild(buildItem(t, false)));
    }
    if (headerList) {
      headerList.innerHTML = "";
      state.toolsCatalog.forEach(t => headerList.appendChild(buildItem(t, true)));
    }
    if (ribbonList) {
      ribbonList.innerHTML = "";
      state.toolsCatalog.forEach(t => ribbonList.appendChild(buildRibbonPill(t)));
      safeCreateIcons();
    }
  }

  function selectTool(toolId, autoRunIfLoaded = false) {
    const tool = state.toolsCatalog.find(t => t.id === toolId) || state.toolsCatalog[0];
    if (!tool) return;
    state.activeTool = tool.id;

    renderToolsMenus();

    // Update header & banner pills
    const headerPill = document.getElementById("activeToolHeaderPill");
    if (headerPill) headerPill.innerText = tool.name;

    const bannerName = document.getElementById("activeToolBannerName");
    if (bannerName) bannerName.innerText = tool.name;

    const bannerBadge = document.getElementById("activeToolBannerBadge");
    if (bannerBadge) bannerBadge.innerText = tool.badge || "Working Mode";

    const sampleLabel = document.getElementById("sampleActiveToolLabel");
    if (sampleLabel) sampleLabel.innerText = tool.name;

    const rightBadge = document.getElementById("ViewportRightBadge");
    if (rightBadge) rightBadge.innerText = tool.name;

    const sideBadge = document.getElementById("sideResultBadge");
    if (sideBadge) sideBadge.innerText = tool.name;

    // Dynamically update Hero Heading & Description for the selected tool
    const heroCopy = TOOL_HERO_COPY[tool.id];
    if (heroCopy) {
      const h1Main = document.getElementById("heroMainTitle");
      const h1High = document.getElementById("heroHighlightTitle");
      const hSub = document.getElementById("heroSubtitleText");
      if (h1Main) h1Main.innerText = heroCopy.title;
      if (h1High) h1High.innerText = heroCopy.highlight;
      if (hSub) hSub.innerText = heroCopy.subtitle;
    }

    // Show matching right-hand tool control panel
    document.querySelectorAll(".tool-control-panel").forEach(panel => {
      panel.classList.add("hidden");
    });
    const activePanel = document.getElementById(`toolPanel-${tool.id}`);
    if (activePanel) {
      activePanel.classList.remove("hidden");
    }

    // If user is in editorView (an image is loaded) and switches tools, automatically run the selected tool!
    if (autoRunIfLoaded && state.originalFile) {
      executeActiveTool();
    }
  }

  function setupAllToolsEventListeners() {
    // Header "All tools" popover toggle
    const menuBtn = document.getElementById("allToolsMenuBtn");
    const popover = document.getElementById("allToolsPopover");
    if (menuBtn && popover) {
      menuBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        popover.classList.toggle("hidden");
      });
      document.addEventListener("click", (e) => {
        if (!popover.contains(e.target) && e.target !== menuBtn) {
          popover.classList.add("hidden");
        }
      });
    }

    // Bind all ".run-active-tool-btn" buttons across the 9 tool panels
    document.querySelectorAll(".run-active-tool-btn").forEach(btn => {
      btn.addEventListener("click", () => executeActiveTool());
    });

    // Bind automatic execution whenever a user changes any select, checkbox, color, or range input in any tool panel
    document.querySelectorAll(".tool-control-panel select, .tool-control-panel input[type='checkbox'], .tool-control-panel input[type='color']").forEach(el => {
      if (el.id === "presetSelect" || el.id === "customColorInput") return;
      el.addEventListener("change", () => {
        debouncedAutoRunTool(80);
      });
    });
    document.querySelectorAll(".tool-control-panel input[type='range']").forEach(el => {
      if (el.id === "backdropBlurSlider") return;
      el.addEventListener("change", () => {
        debouncedAutoRunTool(120);
      });
    });

    // Bind "Use Output as Base" button for chaining tools
    const chainBtn = document.getElementById("chainOutputBtn");
    if (chainBtn) {
      chainBtn.addEventListener("click", handleChainOutputAsBase);
    }

    // Bind Single-Page Showcase Grid "Open <Tool>" & "Try Sample" buttons
    document.querySelectorAll(".spa-launch-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const toolId = btn.getAttribute("data-launch-tool");
        switchMainTab("studio");
        selectTool(toolId, false);
        window.scrollTo({ top: 0, behavior: "smooth" });
        if (state.originalFile) {
          executeActiveTool();
        } else {
          await autoLoadDefaultSampleAndRun();
        }
      });
    });

    document.querySelectorAll(".spa-demo-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const toolId = btn.getAttribute("data-demo-tool");
        switchMainTab("studio");
        selectTool(toolId, false);
        window.scrollTo({ top: 0, behavior: "smooth" });
        await autoLoadDefaultSampleAndRun();
      });
    });

    // Listen to URL hash changes (#image-editor, #bg-remover, etc.)
    window.addEventListener("hashchange", () => {
      const hashTool = window.location.hash ? window.location.hash.replace("#", "") : "";
      if (state.toolsCatalog.some(t => t.id === hashTool)) {
        switchMainTab("studio");
        selectTool(hashTool, true);
      }
    });

    // Bind live readout labels for tool sliders
    const bindSliderReadout = (sliderId, labelId, suffix = "") => {
      const s = document.getElementById(sliderId);
      const l = document.getElementById(labelId);
      if (s && l) {
        s.addEventListener("input", () => {
          l.innerText = `${s.value}${suffix}`;
        });
      }
    };
    bindSliderReadout("edBrightness", "edBrightVal");
    bindSliderReadout("edContrast", "edContrastVal");
    bindSliderReadout("edSaturation", "edSatVal");
    bindSliderReadout("edSharpness", "edSharpVal");
    bindSliderReadout("edWarmth", "edWarmthVal");
    bindSliderReadout("upDenoise", "upDenoiseVal");
    bindSliderReadout("upSharpen", "upSharpenVal");
    bindSliderReadout("extPercent", "extPercentVal", "%");
    bindSliderReadout("varStrength", "varStrengthVal");
    bindSliderReadout("cineBokeh", "cineBokehVal");
    bindSliderReadout("cineGrain", "cineGrainVal");
    bindSliderReadout("skinSmoothing", "skinSmoothVal");
    bindSliderReadout("skinRadiance", "skinRadVal");
    bindSliderReadout("skinCrispness", "skinCrispVal");
    bindSliderReadout("relIntensity", "relIntensityVal");
    bindSliderReadout("relAmbientDim", "relDimVal");
    bindSliderReadout("camIntensity", "camIntVal");

    const relC1 = document.getElementById("relColor1");
    const relC1Txt = document.getElementById("relColor1Text");
    if (relC1 && relC1Txt) relC1.addEventListener("input", () => { relC1Txt.innerText = relC1.value; });

    const relC2 = document.getElementById("relColor2");
    const relC2Txt = document.getElementById("relColor2Text");
    if (relC2 && relC2Txt) relC2.addEventListener("input", () => { relC2Txt.innerText = relC2.value; });

    const resetEditorBtn = document.getElementById("resetEditorBtn");
    if (resetEditorBtn) {
      resetEditorBtn.addEventListener("click", () => {
        document.getElementById("edFilterPreset").value = "none";
        document.getElementById("edCropRatio").value = "original";
        document.getElementById("edBrightness").value = "1.0";
        document.getElementById("edBrightVal").innerText = "1.00";
        document.getElementById("edContrast").value = "1.0";
        document.getElementById("edContrastVal").innerText = "1.00";
        document.getElementById("edSaturation").value = "1.0";
        document.getElementById("edSatVal").innerText = "1.00";
        document.getElementById("edSharpness").value = "1.0";
        document.getElementById("edSharpVal").innerText = "1.00";
        document.getElementById("edWarmth").value = "0.0";
        document.getElementById("edWarmthVal").innerText = "0.00";
        document.getElementById("edRotate").value = "0";
        document.getElementById("edFlipH").checked = false;
        document.getElementById("edFlipV").checked = false;
        executeActiveTool();
      });
    }
  }

  async function autoLoadDefaultSampleAndRun() {
    try {
      const imgRes = await fetch("/static/samples/portrait_person.jpg");
      if (!imgRes.ok) throw new Error("Sample fetch failed");
      const blob = await imgRes.blob();
      const file = new File([blob], "portrait_person.jpg", { type: "image/jpeg" });
      handleImageFile(file);
    } catch (err) {
      showToast("Please upload or drop an image to process.", "info");
    }
  }

  function handleChainOutputAsBase() {
    if (!state.cutoutImgElement) {
      showToast("No processed output available yet.", "error");
      return;
    }
    outputCanvas.toBlob((blob) => {
      if (!blob) return;
      const chainedFile = new File([blob], `chained_${state.activeTool}.png`, { type: "image/png" });
      state.originalFile = chainedFile;
      state.originalUrl = URL.createObjectURL(chainedFile);
      const img = new Image();
      img.onload = () => {
        state.originalImgElement = img;
        originalImg.src = state.originalUrl;
        sideOriginalImg.src = state.originalUrl;
        updateStageDimensions(img.naturalWidth, img.naturalHeight);
        showToast("Output promoted to Base Image! Pick another tool to stack effects.", "success");
      };
      img.src = state.originalUrl;
    }, "image/png");
  }

  async function checkServerStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) throw new Error("Status " + res.status);
      const data = await res.json();
      if (data.status === "online" && modelStatusText) {
        modelStatusText.innerText = `${data.default_model.toUpperCase()} Loaded • Ready`;
      }
      if (data.database) {
        updateDbBadge(data.database);
      }
    } catch (e) {
      if (modelStatusText) modelStatusText.innerText = "Connecting...";
    }
  }

  function updateDbBadge(dbInfo) {
    const dbName = dbInfo.database || dbInfo.db_name || "rembg_studio";
    const isConnected = dbInfo.connected ?? dbInfo.db_connected;
    if (dbStatusText) {
      dbStatusText.innerText = isConnected ? `MySQL: ${dbName}` : `MySQL Setup (${dbName})`;
    }
  }

  async function loadSampleImages() {
    try {
      const res = await fetch("/api/samples");
      if (!res.ok) {
        renderDefaultSamples();
        return;
      }
      const data = await res.json();
      if (!data.samples || data.samples.length === 0) {
        renderDefaultSamples();
        return;
      }
      renderSampleCards(data.samples);
    } catch (err) {
      renderDefaultSamples();
    }
  }

  function renderDefaultSamples() {
    const defaults = [
      { name: "Coffee Mug", category: "Object", filename: "coffee_mug.jpg", url: "/static/samples/coffee_mug.jpg" },
      { name: "Portrait Person", category: "Portrait", filename: "portrait_person.jpg", url: "/static/samples/portrait_person.jpg" },
      { name: "Sneaker Shoe", category: "Product", filename: "sneaker_shoe.jpg", url: "/static/samples/sneaker_shoe.jpg" }
    ];
    renderSampleCards(defaults);
  }

  function renderSampleCards(samples) {
    if (!samplesContainer) return;
    samplesContainer.innerHTML = "";
    samples.forEach(sample => {
      const card = document.createElement("div");
      card.className = "group relative rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-white dark:bg-dark-900 shadow-sm hover:shadow-md hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer transition p-2";
      card.innerHTML = `
        <div class="aspect-[4/3] rounded-xl overflow-hidden bg-slate-100 dark:bg-slate-800 mb-2">
          <img src="${sample.url}" alt="${sample.name} sample photo for AI image tools" width="280" height="210" loading="lazy" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
        </div>
        <div class="flex items-center justify-between px-1">
          <span class="text-xs font-semibold text-slate-800 dark:text-slate-200">${sample.name}</span>
          <span class="text-[10px] text-blue-500 font-medium">${sample.category}</span>
        </div>
      `;

      card.addEventListener("click", async () => {
        showToast(`Loading ${sample.name}...`, "info");
        try {
          const imgRes = await fetch(sample.url);
          const blob = await imgRes.blob();
          const file = new File([blob], sample.filename, { type: "image/jpeg" });
          handleImageFile(file);
        } catch (err) {
          showToast("Failed to load sample image", "error");
        }
      });

      samplesContainer.appendChild(card);
    });
    safeCreateIcons();
  }

  // ----------------------------------------------------
  // IMAGE PROCESSING PIPELINE (ALL 9 WORKING TOOLS)
  // ----------------------------------------------------
  function handleImageFile(file) {
    if (!file.type.startsWith("image/")) {
      showToast("Please select a valid image file.", "error");
      return;
    }

    state.originalFile = file;
    state.originalUrl = URL.createObjectURL(file);

    const img = new Image();
    img.onload = () => {
      state.originalImgElement = img;
      state.telemetry.width = img.naturalWidth;
      state.telemetry.height = img.naturalHeight;

      originalImg.src = state.originalUrl;
      sideOriginalImg.src = state.originalUrl;

      uploadView.classList.add("hidden");
      editorView.classList.remove("hidden");

      updateStageDimensions(img.naturalWidth, img.naturalHeight);

      // Run whichever of the 9 tools is currently selected
      executeActiveTool();
    };
    img.src = state.originalUrl;
  }

  async function processBackgroundRemoval(file) {
    return executeActiveTool(file);
  }

  async function executeActiveTool(overrideFile = null) {
    const toolId = state.activeTool || "bg-remover";
    const fileToUse = overrideFile || state.originalFile;

    if (!fileToUse) {
      await autoLoadDefaultSampleAndRun();
      return;
    }

    const toolMeta = state.toolsCatalog.find(t => t.id === toolId) || { name: "AI Tool" };

    // Check Guest Tool Access Restriction upfront
    if (userQuotaCache && !userQuotaCache.is_registered && userQuotaCache.restricted_tools?.includes(toolId)) {
      showGuestRestrictionModal(`The '${toolMeta.name}' tool is reserved for registered members. Create a free account or sign in in 30 seconds to access all 9 AI studio tools!`);
      return;
    }

    // Check Limitation Rest Cooldown upfront
    if (userQuotaCache?.is_registered && userQuotaCache?.is_resting) {
      showLimitationToaster(userQuotaCache);
      return;
    }

    state.isProcessing = true;
    processingOverlay.classList.remove("hidden");
    processingOverlay.style.opacity = "1";
    const procTitle = document.getElementById("processingTitleText");
    const procSub = document.getElementById("processingSubText");
    if (procTitle) procTitle.innerText = `Running ${toolMeta.name}...`;
    if (procSub) procSub.innerText = toolMeta.desc || "Processing with AI engine";

    const formData = new FormData();
    formData.append("tool_id", toolId);
    formData.append("format", "png");
    formData.append("file", fileToUse);

    // Collect parameters for the active tool
    if (toolId === "bg-remover") {
      formData.append("model", modelSelect.value);
      formData.append("alpha_matting", alphaMattingToggle.checked ? "true" : "false");
      formData.append("af", afSlider.value);
      formData.append("ab", abSlider.value);
      formData.append("ae", aeSlider.value);
      formData.append("post_process_mask", postProcessToggle.checked ? "true" : "false");
      formData.append("only_mask", maskOnlyToggle.checked ? "true" : "false");
    } else if (toolId === "image-editor") {
      formData.append("filter_preset", document.getElementById("edFilterPreset")?.value || "none");
      formData.append("crop_ratio", document.getElementById("edCropRatio")?.value || "original");
      formData.append("brightness", document.getElementById("edBrightness")?.value || "1.0");
      formData.append("contrast", document.getElementById("edContrast")?.value || "1.0");
      formData.append("saturation", document.getElementById("edSaturation")?.value || "1.0");
      formData.append("sharpness", document.getElementById("edSharpness")?.value || "1.0");
      formData.append("warmth", document.getElementById("edWarmth")?.value || "0.0");
      formData.append("rotate", document.getElementById("edRotate")?.value || "0");
      formData.append("flip_h", document.getElementById("edFlipH")?.checked ? "true" : "false");
      formData.append("flip_v", document.getElementById("edFlipV")?.checked ? "true" : "false");
    } else if (toolId === "image-upscaler") {
      formData.append("scale", document.getElementById("upScaleFactor")?.value || "2");
      formData.append("denoise", document.getElementById("upDenoise")?.value || "0.35");
      formData.append("sharpen", document.getElementById("upSharpen")?.value || "0.65");
    } else if (toolId === "image-extender") {
      formData.append("target_ratio", document.getElementById("extTargetRatio")?.value || "16:9");
      formData.append("extender_mode", document.getElementById("extMode")?.value || "ai_outpaint");
      formData.append("expand_percent", document.getElementById("extPercent")?.value || "25");
    } else if (toolId === "variations") {
      formData.append("variation_style", document.getElementById("varStyle")?.value || "cyberpunk");
      formData.append("strength", document.getElementById("varStrength")?.value || "0.80");
    } else if (toolId === "cinematic-shot") {
      formData.append("color_grade", document.getElementById("cineGrade")?.value || "teal_orange");
      formData.append("bokeh_blur", document.getElementById("cineBokeh")?.value || "0.65");
      formData.append("film_grain", document.getElementById("cineGrain")?.value || "0.18");
      formData.append("letterbox", document.getElementById("cineLetterbox")?.checked ? "true" : "false");
      formData.append("anamorphic_flare", document.getElementById("cineFlare")?.checked ? "true" : "false");
    } else if (toolId === "skin-enhancer") {
      formData.append("smoothing", document.getElementById("skinSmoothing")?.value || "0.65");
      formData.append("radiance", document.getElementById("skinRadiance")?.value || "0.35");
      formData.append("detail_crispness", document.getElementById("skinCrispness")?.value || "0.50");
    } else if (toolId === "relight") {
      formData.append("light_position", document.getElementById("relPosition")?.value || "neon_split");
      formData.append("light_color", document.getElementById("relColor1")?.value || "#ff5500");
      formData.append("secondary_color", document.getElementById("relColor2")?.value || "#00ccff");
      formData.append("light_intensity", document.getElementById("relIntensity")?.value || "0.80");
      formData.append("ambient_dim", document.getElementById("relAmbientDim")?.value || "0.50");
    } else if (toolId === "change-camera") {
      formData.append("camera_angle", document.getElementById("camAngle")?.value || "tilt_up");
      formData.append("lens_type", document.getElementById("camLens")?.value || "wide_24mm");
      formData.append("camera_intensity", document.getElementById("camIntensity")?.value || "0.65");
    }

    try {
      const endpoint = toolId === "bg-remover" ? "/api/remove" : "/api/tools/process";
      const activeUserToken = localStorage.getItem("rembg_user_token") || "";
      const reqHeaders = activeUserToken ? { "X-User-Token": activeUserToken } : {};
      const res = await fetch(endpoint, {
        method: "POST",
        headers: reqHeaders,
        body: formData
      });

      if (!res.ok) {
        let errorDetail = `${toolMeta.name} execution failed.`;
        try {
          const errData = await res.json();
          errorDetail = errData.detail || errorDetail;
        } catch (_) {
          errorDetail = (await res.text()) || errorDetail;
        }

        if (res.status === 403 || res.status === 429) {
          if (res.status === 429 && (errorDetail.includes("limitation reached") || errorDetail.includes("rest cooldown"))) {
            showLimitationToaster(userQuotaCache || {
              reset_timestamp: Math.floor(Date.now() / 1000) + 1800,
              time_remaining_formatted: "30:00"
            });
            fetchAndRenderQuota();
            return;
          }
          showGuestRestrictionModal(errorDetail);
          return;
        }
        throw new Error(errorDetail);
      }

      const timeMs = res.headers.get("X-Process-Time-Ms") || "0";
      state.telemetry.timeMs = parseFloat(timeMs);
      statTime.querySelector("span").innerText = `${state.telemetry.timeMs} ms`;

      state.cutoutBlob = await res.blob();
      const cutoutUrl = URL.createObjectURL(state.cutoutBlob);

      const cutoutImg = new Image();
      cutoutImg.onload = () => {
        state.cutoutImgElement = cutoutImg;

        updateStageDimensions(cutoutImg.naturalWidth, cutoutImg.naturalHeight);
        renderCompositedOutput();
        showToast(`${toolMeta.name} completed in ${state.telemetry.timeMs}ms!`, "success");
        fetchAndRenderQuota();
      };
      cutoutImg.src = cutoutUrl;

    } catch (err) {
      console.error(err);
      showToast(err.message || `Failed to run ${toolMeta.name}`, "error");
    } finally {
      state.isProcessing = false;
      processingOverlay.style.opacity = "0";
      setTimeout(() => processingOverlay.classList.add("hidden"), 200);
    }
  }

  // ----------------------------------------------------
  // REAL-TIME CANVAS COMPOSITOR
  // ----------------------------------------------------
  function renderCompositedOutput() {
    if (!state.cutoutImgElement) return;

    const width = state.cutoutImgElement.naturalWidth || state.originalImgElement.naturalWidth;
    const height = state.cutoutImgElement.naturalHeight || state.originalImgElement.naturalHeight;

    // Synchronize canvas buffer dimensions
    [outputCanvas, sideOutputCanvas].forEach(canvas => {
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, width, height);

      // Render Background Layer (applies when Background Remover is active or image has alpha)
      if (state.activeTool !== "bg-remover" || state.bgMode === "transparent") {
        processedBackdropLayer.className = "absolute inset-0 bg-checkerboard flex items-center justify-center";
        processedBackdropLayer.style.background = "";
      } else if (state.bgMode === "solid") {
        processedBackdropLayer.className = "absolute inset-0 flex items-center justify-center";
        processedBackdropLayer.style.background = state.solidColor;
        ctx.fillStyle = state.solidColor;
        ctx.fillRect(0, 0, width, height);
      } else if (state.bgMode === "gradient") {
        processedBackdropLayer.className = "absolute inset-0 flex items-center justify-center";
        processedBackdropLayer.style.background = state.gradientStyle;
        drawCssGradientToCanvas(ctx, state.gradientStyle, width, height);
      } else if (state.bgMode === "backdrop" && state.backdropImgElement) {
        processedBackdropLayer.className = "absolute inset-0 flex items-center justify-center";
        processedBackdropLayer.style.background = "#000";
        ctx.save();
        if (state.backdropBlur > 0) {
          ctx.filter = `blur(${state.backdropBlur}px)`;
        }
        drawImageCover(ctx, state.backdropImgElement, 0, 0, width, height);
        ctx.restore();
      }

      // Draw processed result
      ctx.drawImage(state.cutoutImgElement, 0, 0, width, height);
    });
  }

  function drawImageCover(ctx, img, x, y, w, h) {
    const imgRatio = img.naturalWidth / img.naturalHeight;
    const canvasRatio = w / h;
    let sW, sH, sX, sY;

    if (imgRatio > canvasRatio) {
      sH = img.naturalHeight;
      sW = sH * canvasRatio;
      sX = (img.naturalWidth - sW) / 2;
      sY = 0;
    } else {
      sW = img.naturalWidth;
      sH = sW / canvasRatio;
      sX = 0;
      sY = (img.naturalHeight - sH) / 2;
    }

    ctx.drawImage(img, sX, sY, sW, sH, x, y, w, h);
  }

  function drawCssGradientToCanvas(ctx, gradientCss, w, h) {
    // Standard 135deg top-left to bottom-right
    const grad = ctx.createLinearGradient(0, 0, w, h);
    if (gradientCss.includes("#667eea")) {
      grad.addColorStop(0, "#667eea");
      grad.addColorStop(1, "#764ba2");
    } else if (gradientCss.includes("#ff9a9e")) {
      grad.addColorStop(0, "#ff9a9e");
      grad.addColorStop(1, "#fecfef");
    } else if (gradientCss.includes("#ff758c")) {
      grad.addColorStop(0, "#ff758c");
      grad.addColorStop(1, "#ff7eb3");
    } else if (gradientCss.includes("#0ba360")) {
      grad.addColorStop(0, "#0ba360");
      grad.addColorStop(1, "#3cba92");
    } else if (gradientCss.includes("#2af598")) {
      grad.addColorStop(0, "#2af598");
      grad.addColorStop(1, "#009efd");
    } else if (gradientCss.includes("#f83600")) {
      grad.addColorStop(0, "#f83600");
      grad.addColorStop(1, "#f9d423");
    } else if (gradientCss.includes("#b224ef")) {
      grad.addColorStop(0, "#b224ef");
      grad.addColorStop(1, "#7579ff");
    } else {
      grad.addColorStop(0, "#232526");
      grad.addColorStop(1, "#414345");
    }
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);
  }

  // ----------------------------------------------------
  // STAGE & COMPARISON SLIDER
  // ----------------------------------------------------
  function updateStageDimensions(imgW, imgH) {
    statDimensions.querySelector("span").innerText = `${imgW} x ${imgH} px`;

    // Calculate maximum fitting dimensions inside the viewport
    const container = document.getElementById("viewportContainer");
    const rawW = (container && container.clientWidth > 64) ? container.clientWidth - 32 : 760;
    const rawH = (container && container.clientHeight > 64) ? container.clientHeight - 32 : 480;
    const maxW = Math.max(260, Math.min(rawW, 900));
    const maxH = Math.max(260, Math.min(rawH, 540));

    const ratio = Math.min(maxW / imgW, maxH / imgH, 1);
    const displayW = Math.max(120, Math.round(imgW * ratio));
    const displayH = Math.max(120, Math.round(imgH * ratio));

    imageStage.style.width = `${displayW}px`;
    imageStage.style.height = `${displayH}px`;

    outputCanvas.style.width = `${displayW}px`;
    outputCanvas.style.height = `${displayH}px`;

    originalImg.style.width = `${displayW}px`;
    originalImg.style.height = `${displayH}px`;

    if (state.viewMode === "cutout") {
      updateSliderPosition(0);
    } else {
      updateSliderPosition(50);
    }
  }

  function setupSliderInteraction() {
    const handleMove = (clientX) => {
      const rect = imageStage.getBoundingClientRect();
      let pos = ((clientX - rect.left) / rect.width) * 100;
      pos = Math.max(0, Math.min(100, pos));
      updateSliderPosition(pos);
    };

    sliderDivider.addEventListener("mousedown", (e) => {
      state.isDraggingSlider = true;
      e.preventDefault();
    });

    imageStage.addEventListener("mousedown", (e) => {
      state.isDraggingSlider = true;
      handleMove(e.clientX);
    });

    window.addEventListener("mousemove", (e) => {
      if (!state.isDraggingSlider) return;
      handleMove(e.clientX);
    });

    window.addEventListener("mouseup", () => {
      state.isDraggingSlider = false;
    });

    // Touch support for mobile devices
    sliderDivider.addEventListener("touchstart", (e) => {
      state.isDraggingSlider = true;
    }, { passive: true });

    imageStage.addEventListener("touchstart", (e) => {
      state.isDraggingSlider = true;
      if (e.touches[0]) handleMove(e.touches[0].clientX);
    }, { passive: true });

    window.addEventListener("touchmove", (e) => {
      if (!state.isDraggingSlider || !e.touches[0]) return;
      handleMove(e.touches[0].clientX);
    }, { passive: true });

    window.addEventListener("touchend", () => {
      state.isDraggingSlider = false;
    });

    // Window resize observer
    window.addEventListener("resize", () => {
      if (state.originalImgElement) {
        updateStageDimensions(state.originalImgElement.naturalWidth, state.originalImgElement.naturalHeight);
      }
    });
  }

  function updateSliderPosition(percent) {
    state.sliderPos = percent;
    originalClipLayer.style.width = `${percent}%`;
    sliderDivider.style.left = `${percent}%`;
  }

  // ----------------------------------------------------
  // VIEW MODE SWITCHING
  // ----------------------------------------------------
  function setViewMode(mode) {
    state.viewMode = mode;
    [viewSplitBtn, viewSideBtn, viewCutoutBtn].forEach(btn => {
      btn.classList.remove("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      btn.classList.add("text-slate-600", "dark:text-slate-400");
    });

    if (mode === "split") {
      viewSplitBtn.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      viewSplitBtn.classList.remove("text-slate-600", "dark:text-slate-400");
      sliderWrapper.classList.remove("hidden");
      sideBySideWrapper.classList.add("hidden");
      updateSliderPosition(50);
      originalClipLayer.style.display = "block";
      sliderDivider.style.display = "block";
    } else if (mode === "side") {
      viewSideBtn.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      viewSideBtn.classList.remove("text-slate-600", "dark:text-slate-400");
      sliderWrapper.classList.add("hidden");
      sideBySideWrapper.classList.remove("hidden");
    } else if (mode === "cutout") {
      viewCutoutBtn.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      viewCutoutBtn.classList.remove("text-slate-600", "dark:text-slate-400");
      sliderWrapper.classList.remove("hidden");
      sideBySideWrapper.classList.add("hidden");
      updateSliderPosition(0);
      originalClipLayer.style.display = "none";
      sliderDivider.style.display = "none";
    }
  }

  // ----------------------------------------------------
  // BACKGROUND STUDIO CONTROL
  // ----------------------------------------------------
  function setBgMode(mode) {
    state.bgMode = mode;
    [bgModeTransparent, bgModeSolid, bgModeGradient, bgModeBackdrop].forEach(btn => {
      btn.classList.remove("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      btn.classList.add("text-slate-600", "dark:text-slate-400");
    });

    solidColorPanel.classList.add("hidden");
    gradientPanel.classList.add("hidden");
    backdropPanel.classList.add("hidden");

    if (mode === "transparent") {
      bgModeTransparent.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      bgModeTransparent.classList.remove("text-slate-600", "dark:text-slate-400");
    } else if (mode === "solid") {
      bgModeSolid.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      bgModeSolid.classList.remove("text-slate-600", "dark:text-slate-400");
      solidColorPanel.classList.remove("hidden");
    } else if (mode === "gradient") {
      bgModeGradient.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      bgModeGradient.classList.remove("text-slate-600", "dark:text-slate-400");
      gradientPanel.classList.remove("hidden");
    } else if (mode === "backdrop") {
      bgModeBackdrop.classList.add("bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-white", "shadow-sm");
      bgModeBackdrop.classList.remove("text-slate-600", "dark:text-slate-400");
      backdropPanel.classList.remove("hidden");
    }

    renderCompositedOutput();
  }

  // ----------------------------------------------------
  // EXPORT & DOWNLOAD ACTIONS
  // ----------------------------------------------------
  function handleDownload() {
    if (!state.cutoutImgElement) {
      showToast("No processed image ready for download.", "error");
      return;
    }

    const fmt = state.exportFormat;
    let mimeType = "image/png";
    let ext = "png";

    if (fmt === "jpg") {
      mimeType = "image/jpeg";
      ext = "jpg";
    } else if (fmt === "webp") {
      mimeType = "image/webp";
      ext = "webp";
    }

    // Export using the full-resolution canvas (fill white if exporting JPG in transparent mode)
    let exportCanvas = outputCanvas;
    if (fmt === "jpg" && state.bgMode === "transparent") {
      exportCanvas = document.createElement("canvas");
      exportCanvas.width = outputCanvas.width;
      exportCanvas.height = outputCanvas.height;
      const ectx = exportCanvas.getContext("2d");
      ectx.fillStyle = "#ffffff";
      ectx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
      ectx.drawImage(outputCanvas, 0, 0);
    }

    exportCanvas.toBlob((blob) => {
      if (!blob) {
        showToast("Export failed.", "error");
        return;
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const baseName = state.originalFile ? state.originalFile.name.replace(/\.[^/.]+$/, "") : "cutout";
      link.download = `${baseName}_nobg.${ext}`;
      link.href = url;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      showToast(`Downloaded ${link.download}`, "success");
    }, mimeType, 0.95);
  }

  async function handleCopyToClipboard() {
    if (!state.cutoutImgElement) {
      showToast("No processed image to copy.", "error");
      return;
    }

    try {
      // Must be PNG format for clipboard
      outputCanvas.toBlob(async (blob) => {
        if (!blob) throw new Error("Could not create PNG blob");
        await navigator.clipboard.write([
          new ClipboardItem({ "image/png": blob })
        ]);
        showToast("Copied transparent PNG directly to clipboard!", "success");
      }, "image/png");
    } catch (err) {
      console.error(err);
      showToast("Clipboard copy failed: " + err.message, "error");
    }
  }

  // ----------------------------------------------------
  // BATCH PROCESSING
  // ----------------------------------------------------
  function setupBatchProcessingEvents() {
    const batchBrowseBtn = document.getElementById("batchBrowseBtn");

    if (batchFileInput) {
      batchFileInput.addEventListener("click", (e) => {
        e.stopPropagation();
      });
    }

    if (batchBrowseBtn) {
      batchBrowseBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (batchFileInput) {
          batchFileInput.value = "";
          batchFileInput.click();
        }
      });
    }

    if (batchDropZone) {
      batchDropZone.addEventListener("click", (e) => {
        if (e.target === batchFileInput || (batchBrowseBtn && batchBrowseBtn.contains(e.target))) {
          return;
        }
        if (batchFileInput) {
          batchFileInput.value = "";
          batchFileInput.click();
        }
      });
    }

    if (batchFileInput) {
      batchFileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
          handleBatchFiles(Array.from(e.target.files));
        }
      });
    }

    batchDropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      batchDropZone.classList.add("border-blue-500");
    });

    batchDropZone.addEventListener("dragleave", () => {
      batchDropZone.classList.remove("border-blue-500");
    });

    batchDropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      batchDropZone.classList.remove("border-blue-500");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleBatchFiles(Array.from(e.dataTransfer.files));
      }
    });

    batchStartBtn.addEventListener("click", runBatchProcessing);

    batchDownloadZipBtn.addEventListener("click", () => {
      if (batchZipBlob) {
        const url = URL.createObjectURL(batchZipBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "background_removed_images.zip";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    });
  }

  function handleBatchFiles(files) {
    const validImages = files.filter(f => f.type.startsWith("image/"));
    if (validImages.length === 0) {
      showToast("No valid images selected.", "error");
      return;
    }

    batchFiles = validImages;
    batchCountText.innerText = `${batchFiles.length} Images Selected`;
    batchProcessContainer.classList.remove("hidden");
    batchItemsGrid.innerHTML = "";
    batchDownloadZipBtn.classList.add("hidden");

    batchFiles.forEach((file, index) => {
      const card = document.createElement("div");
      card.id = `batch-card-${index}`;
      card.className = "bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-2.5 flex flex-col items-center gap-2 shadow-sm";
      card.innerHTML = `
        <div class="w-full aspect-square rounded-xl overflow-hidden bg-slate-100 dark:bg-slate-800 flex items-center justify-center relative">
          <img src="${URL.createObjectURL(file)}" class="w-full h-full object-cover">
          <div class="batch-status-badge absolute top-2 right-2 bg-slate-900/70 text-white text-[10px] px-2 py-0.5 rounded-md">
            Pending
          </div>
        </div>
        <span class="text-xs font-medium text-slate-700 dark:text-slate-300 truncate w-full text-center">${file.name}</span>
      `;
      batchItemsGrid.appendChild(card);
    });
  }

  async function runBatchProcessing() {
    if (!batchFiles || batchFiles.length === 0) return;

    // Check Limitation Rest Cooldown upfront for batch
    if (userQuotaCache?.is_registered && userQuotaCache?.is_resting) {
      showLimitationToaster(userQuotaCache);
      return;
    }

    batchStartBtn.disabled = true;
    batchStartBtn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Processing...</span>`;
    safeCreateIcons();

    batchProgressBarContainer.classList.remove("hidden");
    batchProgressBar.style.width = "0%";

    const formData = new FormData();
    batchFiles.forEach(file => formData.append("files", file));
    formData.append("model", "u2netp"); // Use lightweight u2netp for faster batch processing
    formData.append("format", "png");

    // Animate progress simulation
    let progress = 10;
    const progressInterval = setInterval(() => {
      if (progress < 90) {
        progress += 10;
        batchProgressBar.style.width = `${progress}%`;
      }
    }, 400);

    try {
      const activeUserToken = localStorage.getItem("rembg_user_token") || "";
      const batchHeaders = activeUserToken ? { "X-User-Token": activeUserToken } : {};
      const res = await fetch("/api/batch-remove", {
        method: "POST",
        headers: batchHeaders,
        body: formData
      });

      if (!res.ok) {
        let errDetail = "Batch processing failed on server.";
        try {
          const errData = await res.json();
          errDetail = errData.detail || errDetail;
        } catch (_) {}
        throw new Error(errDetail);
      }

      clearInterval(progressInterval);
      batchProgressBar.style.width = "100%";

      batchZipBlob = await res.blob();
      showToast("Batch processing complete! ZIP archive ready.", "success");

      // Update card badges to Done
      document.querySelectorAll(".batch-status-badge").forEach(badge => {
        badge.innerText = "Done";
        badge.className = "batch-status-badge absolute top-2 right-2 bg-emerald-600 text-white text-[10px] px-2 py-0.5 rounded-md";
      });

      batchDownloadZipBtn.classList.remove("hidden");
    } catch (err) {
      clearInterval(progressInterval);
      if (err.message?.includes("limitation reached") || err.message?.includes("rest cooldown")) {
        showLimitationToaster(userQuotaCache || {
          reset_timestamp: Math.floor(Date.now() / 1000) + 1800,
          time_remaining_formatted: "30:00"
        });
        fetchAndRenderQuota();
      } else {
        showToast(err.message, "error");
      }
    } finally {
      batchStartBtn.disabled = false;
      batchStartBtn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Process All</span>`;
      safeCreateIcons();
    }
  }

  // ----------------------------------------------------
  // MYSQL PRESETS, HISTORY & DATABASE CONFIGURATION
  // ----------------------------------------------------
  async function loadPresets() {
    if (!presetSelect) return;
    try {
      const res = await fetch("/api/presets");
      const data = await res.json();
      savedPresets = data.presets || [];
      presetSelect.innerHTML = `<option value="">-- Select Saved Studio Preset --</option>`;
      savedPresets.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        presetSelect.appendChild(opt);
      });
    } catch (e) {
      console.warn("Could not load presets:", e);
    }
  }

  function handleApplyPreset() {
    const id = parseInt(presetSelect.value, 10);
    const preset = savedPresets.find(p => p.id === id);
    if (!preset) return;

    modelSelect.value = preset.model_used;
    alphaMattingToggle.checked = Boolean(preset.alpha_matting);
    if (alphaMattingToggle.checked) {
      alphaMattingControls.classList.remove("hidden");
    } else {
      alphaMattingControls.classList.add("hidden");
    }
    afSlider.value = preset.af_threshold;
    afValText.innerText = preset.af_threshold;
    abSlider.value = preset.ab_threshold;
    abValText.innerText = preset.ab_threshold;
    aeSlider.value = preset.ae_size;
    aeValText.innerText = preset.ae_size;
    postProcessToggle.checked = Boolean(preset.post_process_mask);

    if (preset.bg_mode === "solid" && preset.bg_value) {
      state.solidColor = preset.bg_value;
      setBgMode("solid");
    } else if (preset.bg_mode === "gradient" && preset.bg_value) {
      state.gradientStyle = preset.bg_value;
      setBgMode("gradient");
    } else {
      setBgMode("transparent");
    }

    showToast(`Applied Studio preset: "${preset.name}"`, "success");
    if (state.originalFile) {
      processBackgroundRemoval(state.originalFile);
    }
  }

  async function handleSaveNewPreset() {
    const name = window.prompt("Enter a name for this Studio Workflow Preset:", "Custom Studio Preset");
    if (!name || !name.trim()) return;

    const payload = {
      name: name.trim(),
      model_used: modelSelect.value,
      alpha_matting: alphaMattingToggle.checked,
      af_threshold: parseInt(afSlider.value, 10),
      ab_threshold: parseInt(abSlider.value, 10),
      ae_size: parseInt(aeSlider.value, 10),
      post_process_mask: postProcessToggle.checked,
      bg_mode: state.bgMode,
      bg_value: state.bgMode === "solid" ? state.solidColor : (state.bgMode === "gradient" ? state.gradientStyle : null),
      export_format: state.exportFormat,
    };

    try {
      const res = await fetch("/api/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to save preset");
      await loadPresets();
      showToast(`Saved studio preset "${name.trim()}"!`, "success");
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  async function loadHistoryAndAnalytics() {
    try {
      const [dbRes, histRes] = await Promise.all([
        fetch("/api/db/status"),
        fetch("/api/history?limit=48"),
      ]);
      const dbStats = await dbRes.json();
      const histData = await histRes.json();

      metricTotalJobs.innerText = dbStats.total_jobs ?? 0;
      metricAvgTime.innerText = `${dbStats.avg_process_time_ms ?? 0} ms`;
      metricTopModel.innerText = dbStats.top_model || "u2net";
      const kb = Math.round((dbStats.total_output_bytes || 0) / 1024);
      metricTotalStorage.innerText = kb > 1024 ? `${(kb / 1024).toFixed(1)} MB saved` : `${kb} KB saved`;
      metricDbEngine.innerText = dbStats.db_dialect || "MySQL";
      metricDbHost.innerText = `${dbStats.db_host || "127.0.0.1:3306"} / ${dbStats.db_name || "rembg_studio"}`;
      updateDbBadge(dbStats);

      const jobs = histData.jobs || [];
      historyGrid.innerHTML = "";

      if (jobs.length === 0) {
        historyEmptyState.classList.remove("hidden");
      } else {
        historyEmptyState.classList.add("hidden");
        jobs.forEach(job => {
          const card = document.createElement("div");
          card.className = "bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-3 flex flex-col justify-between shadow-sm hover:shadow-md transition";
          const kbSize = Math.max(1, Math.round((job.output_size_bytes || 0) / 1024));
          card.innerHTML = `
            <div>
              <div class="aspect-[4/3] rounded-xl overflow-hidden bg-checkerboard border border-slate-200 dark:border-slate-800 mb-2.5 relative flex items-center justify-center">
                <img src="${job.output_url}" alt="${job.original_filename}" class="max-w-full max-h-full object-contain">
                <span class="absolute top-2 left-2 bg-slate-900/75 text-white text-[10px] font-semibold px-2 py-0.5 rounded-md">${job.model_used}</span>
                <span class="absolute top-2 right-2 bg-emerald-600/90 text-white text-[10px] font-semibold px-2 py-0.5 rounded-md">${job.process_time_ms} ms</span>
              </div>
              <div class="px-1">
                <h4 class="font-bold text-xs text-slate-800 dark:text-slate-200 truncate" title="${job.original_filename}">${job.original_filename}</h4>
                <div class="flex items-center justify-between text-[11px] text-slate-400 mt-0.5">
                  <span>${job.original_width}×${job.original_height} px • ${kbSize} KB</span>
                  <span>#${job.id}</span>
                </div>
                <span class="text-[10px] text-slate-400 block mt-0.5">${job.created_at || ""}</span>
              </div>
            </div>
            <div class="flex items-center gap-1.5 mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800">
              <a href="${job.output_url}" download="${job.output_filename}" class="flex-1 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-semibold flex items-center justify-center gap-1 transition">
                <i data-lucide="download" class="w-3 h-3"></i>
                <span>Download</span>
              </a>
              <button data-delete-id="${job.id}" class="delete-job-btn p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 transition" title="Delete from MySQL">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              </button>
            </div>
          `;

          card.querySelector(".delete-job-btn").addEventListener("click", async () => {
            if (!confirm(`Delete record #${job.id}?`)) return;
            try {
              const uToken = localStorage.getItem("pnglike_user_token") || localStorage.getItem("rembg_user_token") || "";
              const aToken = localStorage.getItem("pnglike_admin_token") || localStorage.getItem("rembg_admin_token") || "";
              const headers = {};
              if (uToken) headers["X-User-Token"] = uToken;
              if (aToken) headers["X-Admin-Token"] = aToken;

              const delRes = await fetch(`/api/history/${job.id}`, { method: "DELETE", headers });
              if (delRes.ok) {
                showToast(`Deleted job #${job.id} from MySQL`, "info");
                loadHistoryAndAnalytics();
              } else {
                const errData = await delRes.json().catch(() => ({}));
                showToast(errData.detail || "Failed to delete record", "error");
              }
            } catch (err) {
              showToast("Failed to delete record", "error");
            }
          });

          historyGrid.appendChild(card);
        });
        safeCreateIcons();
      }
    } catch (e) {
      console.error("Failed to load MySQL history:", e);
    }
  }

  async function handleClearAllHistory() {
    if (!confirm("Are you sure you want to clear all history records?")) return;
    try {
      const aToken = localStorage.getItem("pnglike_admin_token") || localStorage.getItem("rembg_admin_token") || "";
      const headers = {};
      if (aToken) headers["X-Admin-Token"] = aToken;
      const res = await fetch("/api/history", { method: "DELETE", headers });
      if (res.ok) {
        showToast("Cleared all job history from MySQL.", "success");
        loadHistoryAndAnalytics();
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast(errData.detail || "Admin authentication required to clear all history.", "error");
      }
    } catch (e) {
      showToast("Failed to clear history", "error");
    }
  }

  async function openDbConfigModal() {
    dbConfigModal.classList.remove("hidden");
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      const db = data.database || {};
      dbHostInput.value = db.host || "127.0.0.1";
      dbPortInput.value = db.port || 3306;
      dbUserInput.value = db.user || "root";
      dbNameInput.value = db.database || "rembg_studio";

      if (db.connected) {
        dbModalStatusBanner.className = "text-xs p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-mono break-all";
        dbModalStatusBanner.innerText = `Connected to MySQL (${db.user}@${db.host}:${db.port}/${db.database})`;
      } else {
        dbModalStatusBanner.className = "text-xs p-3 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 font-mono break-all";
        dbModalStatusBanner.innerText = `MySQL server at ${db.host}:${db.port} not connected (${db.error || "Check MySQL service & credentials"}). Running with active fallback engine.`;
      }
    } catch (e) {
      dbModalStatusBanner.innerText = "Unable to query database status.";
    }
  }

  async function handleSaveDbConfig() {
    saveDbConfigBtn.disabled = true;
    saveDbConfigBtn.innerText = "Connecting...";
    try {
      const payload = {
        host: dbHostInput.value.trim() || "127.0.0.1",
        port: parseInt(dbPortInput.value, 10) || 3306,
        user: dbUserInput.value.trim() || "root",
        password: dbPassInput.value,
        database: dbNameInput.value.trim() || "rembg_studio",
      };
      const res = await fetch("/api/db/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      updateDbBadge(data);
      if (data.connected) {
        dbModalStatusBanner.className = "text-xs p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-mono break-all";
        dbModalStatusBanner.innerText = `Connected to MySQL (${data.user}@${data.host}:${data.port}/${data.database})!`;
        showToast("Connected to MySQL database successfully!", "success");
        loadHistoryAndAnalytics();
        loadPresets();
      } else {
        dbModalStatusBanner.className = "text-xs p-3 rounded-xl bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 font-mono break-all";
        dbModalStatusBanner.innerText = `Connection error: ${data.error || "Could not reach MySQL server"}. Settings saved to .env.`;
        showToast("Saved MySQL settings to .env (MySQL server offline)", "info");
      }
    } catch (e) {
      showToast("Failed to update MySQL config", "error");
    } finally {
      saveDbConfigBtn.disabled = false;
      saveDbConfigBtn.innerHTML = `<i data-lucide="plug-zap" class="w-3.5 h-3.5"></i><span>Test & Connect MySQL</span>`;
      safeCreateIcons();
    }
  }

  // ----------------------------------------------------
  // NAVIGATION & THEME HELPERS
  // ----------------------------------------------------
  function switchMainTab(tab) {
    const activeDesktop = "flex items-center gap-2 px-4 py-1.5 rounded-lg bg-white dark:bg-slate-700 text-blue-600 dark:text-white shadow-sm transition-all";
    const inactiveDesktop = "flex items-center gap-2 px-4 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all";
    const activeMobile = "flex-1 py-1.5 rounded-lg text-xs font-medium text-center bg-blue-50 text-blue-600 dark:bg-slate-800 dark:text-blue-400";
    const inactiveMobile = "flex-1 py-1.5 rounded-lg text-xs font-medium text-center text-slate-600 dark:text-slate-400";

    studioSection.classList.toggle("hidden", tab !== "studio");
    batchSection.classList.toggle("hidden", tab !== "batch");
    historySection.classList.toggle("hidden", tab !== "history");

    tabStudioBtn.className = tab === "studio" ? activeDesktop : inactiveDesktop;
    tabBatchBtn.className = tab === "batch" ? activeDesktop : inactiveDesktop;

    mobileTabStudioBtn.className = tab === "studio" ? activeMobile : inactiveMobile;
    mobileTabBatchBtn.className = tab === "batch" ? activeMobile : inactiveMobile;

    if (tab === "history") {
      loadHistoryAndAnalytics();
    }
  }

  function initTheme() {
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    const isDark = localStorage.getItem("theme") !== "light";
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }

    themeToggleBtn.addEventListener("click", () => {
      const currentlyDark = document.documentElement.classList.contains("dark");
      if (currentlyDark) {
        document.documentElement.classList.remove("dark");
        localStorage.setItem("theme", "light");
      } else {
        document.documentElement.classList.add("dark");
        localStorage.setItem("theme", "dark");
      }
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

    toast.className = `${bg} pointer-events-auto border px-4 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-xs font-semibold transform transition-all duration-300 translate-y-2 opacity-0`;
    toast.innerHTML = `<i data-lucide="${icon}" class="w-4 h-4"></i><span>${message}</span>`;
    container.appendChild(toast);
    safeCreateIcons();

    setTimeout(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);

    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
});
