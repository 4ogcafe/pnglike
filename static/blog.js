// PngLike Public Blog Client Logic
document.addEventListener("DOMContentLoaded", () => {
  let activeCategory = "all";
  let searchQuery = "";
  let allPosts = [];
  let currentSlug = null;

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

  async function loadBlogIndex() {
    try {
      const params = new URLSearchParams();
      if (activeCategory && activeCategory !== "all") params.set("category", activeCategory);
      if (searchQuery) params.set("search", searchQuery);

      const res = await fetch(`/api/blog?${params.toString()}`);
      const data = await res.json();
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

    if (window.lucide) window.lucide.createIcons();
  }

  async function openArticleBySlug(slug, pushHistory = true) {
    try {
      const res = await fetch(`/api/blog/${encodeURIComponent(slug)}`);
      if (!res.ok) {
        showToast("Blog article not found.", "error");
        showListView(true);
        return;
      }
      const data = await res.json();
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
      if (window.lucide) window.lucide.createIcons();
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
      if (window.lucide) window.lucide.createIcons();
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

