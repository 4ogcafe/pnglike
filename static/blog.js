// PngLike Public Blog Client Logic
document.addEventListener("DOMContentLoaded", () => {
  function safeCreateIcons() {
    try {
      if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.lucide.createIcons();
      }
    } catch (_) {}
  }
  let activeCategory = "all";
  let searchQuery = "";
  let allPosts = [];
  let currentSlug = null;

  const FALLBACK_BLOG_POSTS = [
    {
      id: 1,
      title: "Mastering Hair-Level AI Background Removal with U2-Net & Alpha Matting",
      slug: "mastering-ai-background-removal-u2net-alpha-matting",
      excerpt: "Learn how to combine U2-Net deep salient object detection with foreground/background alpha matting thresholds for studio-grade hair, fur, and semi-transparent cutouts.",
      category: "AI Tutorials",
      tags: "u2net,alpha-matting,background-remover,onnx,portrait",
      tag_list: ["u2net", "alpha-matting", "background-remover", "onnx", "portrait"],
      cover_image: "/static/samples/portrait_person.jpg",
      author: "Div Sri",
      read_time_minutes: 5,
      is_published: true,
      is_featured: true,
      views_count: 142,
      published_date: "Nov 06, 2026",
      meta_title: "Mastering Hair-Level AI Background Removal with U2-Net — PngLike Blog",
      meta_description: "Step-by-step guide to achieving razor-sharp hair and fur cutouts using U2-Net ONNX neural segmentation and alpha matting in PngLike Studio.",
      content: "<h2>Why Standard Cutouts Struggle with Hair and Fine Edges</h2><p>Traditional binary segmentation masks classify every pixel as either 100% foreground or 100% background. While that works well for hard-edged boxes or shoes, human hair, pet fur, and glass edges contain mixed transparency (alpha values between <code>0.05</code> and <code>0.95</code>).</p><h3>1. Choosing the Right ONNX Neural Model</h3><ul><li><strong>U2-Net (High Quality)</strong>: Our flagship 176 MB two-level nested U-structure architecture. Ideal for general studio photography and complex silhouettes.</li><li><strong>U2-Net Human Segmentation</strong>: Specifically fine-tuned on human portraits, clothing textures, and flyaway hair strands.</li><li><strong>IS-Net Anime</strong>: Engineered for 2D illustrations, cel-shaded artwork, and vector linework.</li></ul><h3>2. Fine-Tuning Alpha Matting Thresholds</h3><p>When you enable <strong>Alpha Matting</strong> in PngLike's Background Remover panel, the trimap refinement solver uses three key parameters:</p><ul><li><strong>Foreground Threshold (default 240)</strong>: Pixels with probability above this value are locked as pure opaque subject. Lowering to <code>225</code> preserves more wisps of hair.</li><li><strong>Background Threshold (default 10)</strong>: Pixels below this probability are cleared to 0% alpha. Raising to <code>20</code> eliminates color spill from studio backdrops.</li><li><strong>Erode Size (default 10)</strong>: Controls the width of the unknown trimap boundary zone where closed-form alpha matting computes sub-pixel transparency.</li></ul><blockquote>Pro Tip: Enable <strong>Post-Process Mask</strong> alongside Alpha Matting to automatically smooth morphological jagged edges before compositing onto a solid or gradient backdrop.</blockquote>"
    },
    {
      id: 2,
      title: "E-Commerce Product Photography: Creating Pure White Studio Catalogs in Seconds",
      slug: "ecommerce-product-photography-pure-white-studio-catalogs",
      excerpt: "How online sellers and brand designers use PngLike's Batch Studio, 4x Super-Resolution Upscaler, and Pure White (#FFFFFF) presets to meet Amazon and Shopify marketplace specs.",
      category: "Product Photography",
      tags: "ecommerce,batch-processing,product-photos,upscaler,presets",
      tag_list: ["ecommerce", "batch-processing", "product-photos", "upscaler", "presets"],
      cover_image: "/static/samples/product_sneaker.jpg",
      author: "Div Sri",
      read_time_minutes: 4,
      is_published: true,
      is_featured: true,
      views_count: 98,
      published_date: "Nov 06, 2026",
      meta_title: "E-Commerce Product Photography Guide — Pure White Studio Cutouts",
      meta_description: "Automate Amazon and Shopify product photography with PngLike Batch Studio, pure #FFFFFF backdrops, and 4x Lanczos super-resolution upscaling.",
      content: "<h2>Marketplace Compliance Made Effortless</h2><p>Major e-commerce marketplaces require primary product listings to feature a pure white (<code>RGB 255, 255, 255</code> / <code>#FFFFFF</code>) background with crisp object edges and high resolution (at least 1600px on the longest side).</p><h3>Step 1: One-Click 'E-Commerce White Studio' Preset</h3><p>Inside the PngLike AI Image Studio, select the <strong>E-Commerce White Studio</strong> preset from the top preset selector. This automatically configures:</p><ul><li>Model: <code>u2net</code> with morphological mask post-processing enabled</li><li>Background Mode: Solid <code>#ffffff</code> pure studio white</li><li>Export Format: High-quality 95% JPEG or lossless PNG</li></ul><h3>Step 2: Upscaling Low-Resolution Vendor Photos</h3><p>Switch directly to the <strong>Image Upscaler</strong> tool in the 9-in-1 Dock to boost supplier images by <strong>2x or 4x</strong> using Lanczos-4 interpolation paired with bilateral noise reduction and unsharp edge enhancement.</p><h3>Step 3: Multi-Image ZIP Batch Processing</h3><p>Have 50 product SKUs to shoot? Open the <strong>Batch Studio</strong> tab, drag and drop your entire folder, and download a single ready-to-publish ZIP archive in seconds.</p>"
    },
    {
      id: 3,
      title: "Inside PngLike 9-in-1 AI Image Suite: 3D Relighting, Cinematic Bokeh & Camera Warp",
      slug: "inside-pnglike-9-in-1-ai-image-suite-3d-relight-cinematic",
      excerpt: "Explore the computer vision pipelines behind PngLike's 9 working IMAGE tools—from surface-normal 3D studio relighting to anamorphic bokeh and projective homography camera shifts.",
      category: "Computer Vision",
      tags: "relight,cinematic-shot,change-camera,skin-enhancer,computer-vision",
      tag_list: ["relight", "cinematic-shot", "change-camera", "skin-enhancer", "computer-vision"],
      cover_image: "/static/samples/coffee_mug.jpg",
      author: "Div Sri",
      read_time_minutes: 6,
      is_published: true,
      is_featured: false,
      views_count: 76,
      published_date: "Nov 06, 2026",
      meta_title: "Inside PngLike 9-in-1 AI Image Suite: Relight, Cinematic & Camera Tools",
      meta_description: "Deep dive into the 9 neural and computer vision tools powering PngLike Studio: 3D Relight, Cinematic Shot, Skin Enhancer, Image Extender, and Change Camera.",
      content: "<h2>One Unified Workspace, Nine Specialized Vision Engines</h2><p>PngLike (Powered by Div Sri) combines ONNX Runtime neural segmentation with real-time NumPy/Pillow signal processing so every tool runs locally on your machine with zero cloud latency or privacy risks.</p><h3>Highlights from the 9-Tool Dock</h3><ul><li><strong>Relight (3D Light)</strong>: Isolates the foreground subject via U2-Net, estimates a 3D hemisphere surface normal map from luminance gradients, and casts dual directional key and rim lights (including Neon Split).</li><li><strong>Cinematic Shot (Anamorphic)</strong>: Separates foreground and background planes to apply optical depth-of-field bokeh blur, Teal & Orange Hollywood LUT grading, horizontal anamorphic lens flares, and 2.39:1 widescreen letterbox bars.</li><li><strong>Skin Enhancer (Portrait)</strong>: Uses YCbCr chrominance skin-tone masking and frequency separation to smooth blemishes while preserving sharp eye, eyelash, and pore detail.</li><li><strong>Change Camera (Perspective)</strong>: Applies 3D projective homography matrices (Tilt Up, Tilt Down, Pan Left/Right, Dutch Roll) and radial Barrel/Pincushion lens profiles (24mm Wide, 16mm Fisheye, 85mm Telephoto).</li></ul>"
    }
  ];

  const blogListView = document.getElementById("blogListView");
  const blogArticleView = document.getElementById("blogArticleView");
  const blogPostsGrid = document.getElementById("blogPostsGrid");
  const featuredPostContainer = document.getElementById("featuredPostContainer");
  const blogCategoriesBar = document.getElementById("blogCategoriesBar");
  const blogCountLabel = document.getElementById("blogCountLabel");
  const blogEmptyState = document.getElementById("blogEmptyState");
  const blogSearchInput = document.getElementById("blogSearchInput");
  const blogSearchBtn = document.getElementById("blogSearchBtn");
  const resetBlogFilterBtn = document.getElementById("resetBlogFilterBtn");
  const backToBlogListBtn = document.getElementById("backToBlogListBtn");
  const copyArticleLinkBtn = document.getElementById("copyArticleLinkBtn");
  const navAllArticlesBtn = document.getElementById("navAllArticlesBtn");

  initTheme();
  setupListeners();
  handleInitialRoute();

  window.addEventListener("popstate", () => {
    handleInitialRoute();
  });

  function getSlugFromLocation() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("post")) return params.get("post");
    if (params.get("slug")) return params.get("slug");
    const pathParts = window.location.pathname.split("/").filter(Boolean);
    if (pathParts.length >= 2 && pathParts[0] === "blog") {
      return decodeURIComponent(pathParts[1]);
    }
    return null;
  }

  async function handleInitialRoute() {
    const slug = getSlugFromLocation();
    await loadBlogIndex();
    if (slug) {
      await openArticleBySlug(slug, false);
    } else {
      showListView(false);
    }
  }

  function setupListeners() {
    blogSearchBtn.addEventListener("click", () => {
      searchQuery = blogSearchInput.value.trim();
      loadBlogIndex();
    });

    blogSearchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        searchQuery = blogSearchInput.value.trim();
        loadBlogIndex();
      }
    });

    resetBlogFilterBtn.addEventListener("click", () => {
      activeCategory = "all";
      searchQuery = "";
      blogSearchInput.value = "";
      loadBlogIndex();
    });

    backToBlogListBtn.addEventListener("click", () => {
      showListView(true);
    });

    navAllArticlesBtn.addEventListener("click", (e) => {
      e.preventDefault();
      showListView(true);
    });

    copyArticleLinkBtn.addEventListener("click", () => {
      navigator.clipboard?.writeText(window.location.href);
      showToast("Article link copied to clipboard!", "success");
    });
  }

  function getFallbackBlogData() {
    const categories = Array.from(new Set(FALLBACK_BLOG_POSTS.map(p => p.category)));
    const posts = FALLBACK_BLOG_POSTS.filter(p => {
      if (activeCategory && activeCategory !== "all" && p.category.toLowerCase() !== activeCategory.toLowerCase()) {
        return false;
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          p.title.toLowerCase().includes(q) ||
          p.excerpt.toLowerCase().includes(q) ||
          p.tags.toLowerCase().includes(q) ||
          p.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
    return { posts, categories };
  }

  async function loadBlogIndex() {
    try {
      const params = new URLSearchParams();
      if (activeCategory && activeCategory !== "all") params.set("category", activeCategory);
      if (searchQuery) params.set("search", searchQuery);

      let data = null;
      try {
        const res = await fetch(`/api/blog?${params.toString()}`);
        if (res.ok) {
          const text = await res.text();
          if (text && !text.trim().startsWith("<")) {
            data = JSON.parse(text);
          }
        }
      } catch (_) {}

      if (!data || !Array.isArray(data.posts)) {
        data = getFallbackBlogData();
      }

      allPosts = data.posts || [];

      if (data.settings) {
        const bar = document.getElementById("siteAnnouncementBar");
        const txt = document.getElementById("siteAnnouncementText");
        if (bar && txt) {
          txt.innerText = data.settings.announcement_text || "";
          bar.classList.toggle("hidden", !data.settings.announcement_enabled);
        }
      }

      renderCategoryButtons(data.categories || []);
      renderBlogList(allPosts);
    } catch (err) {
      console.error("Failed to load blog posts:", err);
      const fallback = getFallbackBlogData();
      allPosts = fallback.posts;
      renderCategoryButtons(fallback.categories);
      renderBlogList(allPosts);
    }
  }

  function renderCategoryButtons(categories) {
    const allCats = ["all", ...categories];
    blogCategoriesBar.innerHTML = "";
    allCats.forEach(cat => {
      const isSelected = activeCategory.toLowerCase() === cat.toLowerCase();
      const btn = document.createElement("button");
      btn.className = isSelected
        ? "blog-cat-btn px-4 py-1.5 rounded-full text-xs font-bold bg-blue-600 text-white shadow-sm transition"
        : "blog-cat-btn px-4 py-1.5 rounded-full text-xs font-semibold bg-white dark:bg-dark-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:border-blue-500 transition";
      btn.innerText = cat === "all" ? "All Articles" : cat;
      btn.addEventListener("click", () => {
        activeCategory = cat;
        loadBlogIndex();
      });
      blogCategoriesBar.appendChild(btn);
    });
  }

  function renderBlogList(posts) {
    blogCountLabel.innerText = `${posts.length} ${posts.length === 1 ? "article" : "articles"} published`;

    if (posts.length === 0) {
      featuredPostContainer.classList.add("hidden");
      blogPostsGrid.innerHTML = "";
      blogEmptyState.classList.remove("hidden");
      return;
    }

    blogEmptyState.classList.add("hidden");

    // Highlight top featured post when on "all" without search filter
    const featured = (!searchQuery && activeCategory === "all") ? posts.find(p => p.is_featured) : null;
    const gridPosts = featured ? posts.filter(p => p.id !== featured.id) : posts;

    if (featured) {
      featuredPostContainer.classList.remove("hidden");
      featuredPostContainer.innerHTML = `
        <div class="bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 hover:border-blue-500 rounded-3xl overflow-hidden shadow-sm transition grid grid-cols-1 lg:grid-cols-12 cursor-pointer group" data-open-slug="${featured.slug}">
          <div class="lg:col-span-6 aspect-[16/10] lg:aspect-auto bg-slate-100 dark:bg-slate-800 relative overflow-hidden">
            <img src="${featured.cover_image || '/static/samples/portrait_person.jpg'}" alt="${featured.title}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">
            <span class="absolute top-4 left-4 px-3 py-1 rounded-full bg-amber-500 text-slate-950 text-[11px] font-extrabold uppercase tracking-wider shadow">
              ★ Featured Guide
            </span>
          </div>
          <div class="lg:col-span-6 p-6 sm:p-8 flex flex-col justify-between space-y-4">
            <div class="space-y-3">
              <div class="flex items-center gap-2.5 text-xs">
                <span class="px-2.5 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 font-bold">${featured.category}</span>
                <span class="text-slate-400">•</span>
                <span class="text-slate-500 dark:text-slate-400">${featured.read_time_minutes} min read</span>
                <span class="text-slate-400">•</span>
                <span class="text-slate-500 dark:text-slate-400">${featured.views_count} views</span>
              </div>
              <h2 class="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition leading-snug">
                ${featured.title}
              </h2>
              <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-3">
                ${featured.excerpt}
              </p>
            </div>
            <div class="pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-2 text-xs">
                <div class="w-6 h-6 rounded-full bg-gradient-to-tr from-rose-500 to-indigo-600 text-white font-bold flex items-center justify-center text-[10px]">DS</div>
                <span class="font-bold text-slate-800 dark:text-slate-200">${featured.author}</span>
                <span class="text-slate-400">• ${featured.published_date}</span>
              </div>
              <span class="inline-flex items-center gap-1 text-xs font-bold text-blue-600 dark:text-blue-400">
                <span>Read Article</span>
                <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
              </span>
            </div>
          </div>
        </div>
      `;
      featuredPostContainer.querySelector("[data-open-slug]")?.addEventListener("click", () => {
        openArticleBySlug(featured.slug, true);
      });
    } else {
      featuredPostContainer.classList.add("hidden");
    }

    blogPostsGrid.innerHTML = "";
    gridPosts.forEach(post => {
      const card = document.createElement("article");
      card.className = "bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 hover:border-blue-500 rounded-3xl overflow-hidden shadow-sm transition flex flex-col justify-between cursor-pointer group";
      card.innerHTML = `
        <div>
          <div class="aspect-[16/10] bg-slate-100 dark:bg-slate-800 relative overflow-hidden">
            <img src="${post.cover_image || '/static/samples/portrait_person.jpg'}" alt="${post.title}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">
            <span class="absolute top-3 left-3 px-2.5 py-0.5 rounded-md bg-slate-900/80 text-white text-[10px] font-bold uppercase tracking-wider">
              ${post.category}
            </span>
            ${post.is_featured ? `<span class="absolute top-3 right-3 px-2 py-0.5 rounded-md bg-amber-500 text-slate-950 text-[10px] font-extrabold">★ Featured</span>` : ""}
          </div>
          <div class="p-5 space-y-2.5">
            <div class="flex items-center gap-2 text-[11px] text-slate-400">
              <span>${post.published_date}</span>
              <span>•</span>
              <span>${post.read_time_minutes} min read</span>
              <span>•</span>
              <span>${post.views_count} views</span>
            </div>
            <h3 class="text-base font-bold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition leading-snug">
              ${post.title}
            </h3>
            <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-3">
              ${post.excerpt}
            </p>
          </div>
        </div>
        <div class="px-5 py-3.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
          <span class="font-semibold text-slate-700 dark:text-slate-300">By ${post.author}</span>
          <span class="font-bold text-blue-600 dark:text-blue-400 flex items-center gap-1">
            <span>Read</span>
            <i data-lucide="arrow-up-right" class="w-3.5 h-3.5"></i>
          </span>
        </div>
      `;
      card.addEventListener("click", () => openArticleBySlug(post.slug, true));
      blogPostsGrid.appendChild(card);
    });

    safeCreateIcons();
  }

  async function openArticleBySlug(slug, pushHistory = true) {
    try {
      let data = null;
      try {
        const res = await fetch(`/api/blog/${encodeURIComponent(slug)}`);
        if (res.ok) {
          const text = await res.text();
          if (text && !text.trim().startsWith("<")) {
            data = JSON.parse(text);
          }
        }
      } catch (_) {}

      if (!data || !data.post) {
        const localPost = FALLBACK_BLOG_POSTS.find(p => p.slug === slug);
        if (!localPost) {
          showToast("Blog article not found.", "error");
          showListView(true);
          return;
        }
        data = {
          post: localPost,
          related: FALLBACK_BLOG_POSTS.filter(p => p.slug !== slug)
        };
      }

      const post = data.post;
      const related = data.related || [];
      currentSlug = post.slug;

      if (pushHistory) {
        window.history.pushState({ slug: post.slug }, post.title, `/blog/${post.slug}`);
      }

      // Update SEO & Page Metadata
      document.title = `${post.meta_title || post.title} — PngLike Blog`;
      const metaDesc = document.getElementById("pageMetaDescription");
      if (metaDesc) metaDesc.setAttribute("content", post.meta_description || post.excerpt);

      // Populate Article View
      document.getElementById("articleCoverImg").src = post.cover_image || "/static/samples/portrait_person.jpg";
      document.getElementById("articleCoverImg").alt = post.title;
      document.getElementById("articleCategoryBadge").innerText = post.category;
      document.getElementById("articleReadTime").innerHTML = `<i data-lucide="clock" class="w-3.5 h-3.5"></i> ${post.read_time_minutes} min read`;
      document.getElementById("articleViewsCount").innerHTML = `<i data-lucide="eye" class="w-3.5 h-3.5"></i> ${post.views_count} views`;
      document.getElementById("articleTitle").innerText = post.title;
      document.getElementById("articleExcerpt").innerText = post.excerpt;
      document.getElementById("articleAuthor").innerText = post.author;
      document.getElementById("articleDate").innerText = `Published ${post.published_date}`;
      document.getElementById("articleBodyContent").innerHTML = post.content;

      const tagsEl = document.getElementById("articleTagsContainer");
      tagsEl.innerHTML = "";
      (post.tag_list || []).forEach(tag => {
        const pill = document.createElement("span");
        pill.className = "px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[11px] font-mono";
        pill.innerText = `#${tag}`;
        tagsEl.appendChild(pill);
      });

      // Related posts
      const relSection = document.getElementById("relatedArticlesSection");
      const relGrid = document.getElementById("relatedArticlesGrid");
      relGrid.innerHTML = "";
      if (related.length === 0) {
        relSection.classList.add("hidden");
      } else {
        relSection.classList.remove("hidden");
        related.forEach(rel => {
          const item = document.createElement("div");
          item.className = "bg-white dark:bg-dark-900 border border-slate-200 dark:border-slate-800 hover:border-blue-500 rounded-2xl p-4 cursor-pointer transition flex flex-col justify-between";
          item.innerHTML = `
            <div>
              <span class="text-[10px] font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">${rel.category}</span>
              <h4 class="font-bold text-xs sm:text-sm text-slate-900 dark:text-white mt-1 mb-1.5 line-clamp-2">${rel.title}</h4>
              <p class="text-[11px] text-slate-500 line-clamp-2">${rel.excerpt}</p>
            </div>
            <div class="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
              <span>${rel.read_time_minutes} min read</span>
              <span class="text-blue-500 font-bold">Read →</span>
            </div>
          `;
          item.addEventListener("click", () => openArticleBySlug(rel.slug, true));
          relGrid.appendChild(item);
        });
      }

      blogListView.classList.add("hidden");
      blogArticleView.classList.remove("hidden");
      window.scrollTo({ top: 0, behavior: "smooth" });
      safeCreateIcons();
    } catch (e) {
      console.error(e);
    }
  }

  function showListView(pushHistory = true) {
    currentSlug = null;
    if (pushHistory && window.location.pathname !== "/blog") {
      window.history.pushState({}, "PngLike Blog", "/blog");
    }
    document.title = "PngLike Blog — AI Image Tutorials, Computer Vision & Product Photography | Powered by Div Sri";
    blogArticleView.classList.add("hidden");
    blogListView.classList.remove("hidden");
    loadBlogIndex();
  }

  function initTheme() {
    const btn = document.getElementById("themeToggleBtn");
    const isDark = localStorage.getItem("theme") !== "light";
    document.documentElement.classList.toggle("dark", isDark);
    btn?.addEventListener("click", () => {
      const nextDark = !document.documentElement.classList.contains("dark");
      document.documentElement.classList.toggle("dark", nextDark);
      localStorage.setItem("theme", nextDark ? "dark" : "light");
      safeCreateIcons();
    });
  }

  function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;
    const toast = document.createElement("div");
    const bg = type === "success" ? "bg-emerald-600 text-white border-emerald-500" : "bg-slate-900 text-white border-slate-700";
    toast.className = `${bg} pointer-events-auto border px-4 py-3 rounded-2xl shadow-xl flex items-center gap-2 text-xs font-semibold`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }
});

