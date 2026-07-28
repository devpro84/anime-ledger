(() => {
  "use strict";

  const DATA_URL = "data/anime.json";
  const DEMO_LIST = ["Shonen", "Shojo", "Seinen", "Josei", "Kodomomuke"];
  const GENRE_LIST = ["Isekai", "Mecha", "Slice of Life", "Fantasy / Action", "Other"];
  const STAR_KEY = "ledger-starred";
  const DISMISS_KEY = "ledger-install-dismissed";
  const STAR_ICON_PATH =
    "M12 1.6l2.85 6.53 7.1.62-5.38 4.68 1.62 6.97L12 16.6l-6.19 3.8 1.62-6.97-5.38-4.68 7.1-.62L12 1.6z";

  let ALL = [];
  const openRanks = new Set();
  const starred = new Set(JSON.parse(localStorage.getItem(STAR_KEY) || "[]"));

  const state = {
    search: "",
    demo: new Set(),
    genre: new Set(),
    starredOnly: false,
    sort: "rank",
  };

  const $list = document.getElementById("list");
  const $empty = document.getElementById("empty-state");
  const $count = document.getElementById("result-count");
  const $search = document.getElementById("search-input");
  const $sort = document.getElementById("sort-select");
  const $starredToggle = document.getElementById("starred-toggle");
  const $clear = document.getElementById("clear-filters");
  const $emptyClear = document.getElementById("empty-clear");

  function slug(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function saveStarred() {
    localStorage.setItem(STAR_KEY, JSON.stringify([...starred]));
  }

  function buildChipGroup(containerId, list, set, varPrefix) {
    const wrap = document.getElementById(containerId);
    wrap.innerHTML = "";
    list.forEach((name) => {
      const s = slug(name);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip";
      btn.setAttribute("aria-pressed", set.has(name) ? "true" : "false");
      btn.innerHTML = `<span class="dot" style="--dot-color:var(--${varPrefix}-${s})"></span>${name}`;
      btn.addEventListener("click", () => {
        if (set.has(name)) set.delete(name);
        else set.add(name);
        btn.setAttribute("aria-pressed", set.has(name) ? "true" : "false");
        renderList();
      });
      wrap.appendChild(btn);
    });
  }

  function renderChips() {
    buildChipGroup("demo-chips", DEMO_LIST, state.demo, "demo");
    buildChipGroup("genre-chips", GENRE_LIST, state.genre, "genre");
  }

  function matches(item) {
    if (state.starredOnly && !starred.has(item.rank)) return false;
    if (state.demo.size && !state.demo.has(item.demographic.tag)) return false;
    if (state.genre.size && !state.genre.has(item.genre.tag)) return false;
    if (state.search) {
      const q = state.search.toLowerCase();
      if (!item.title.toLowerCase().includes(q)) return false;
    }
    return true;
  }

  function sortItems(items) {
    const arr = [...items];
    if (state.sort === "rank") arr.sort((a, b) => a.rank - b.rank);
    else if (state.sort === "points") arr.sort((a, b) => b.total_points - a.total_points);
    else if (state.sort === "title") arr.sort((a, b) => a.title.localeCompare(b.title));
    return arr;
  }

  function voteCell(label, value) {
    return `<div class="vote-cell"><span class="k">${label}</span><span class="v">${value}</span></div>`;
  }

  function placeholderHTML() {
    return `<span class="thumb-placeholder" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="${STAR_ICON_PATH}"/></svg></span>`;
  }

  function cardHTML(item) {
    const isOpen = openRanks.has(item.rank);
    const isStarred = starred.has(item.rank);
    const demoSlug = slug(item.demographic.tag);
    const genreSlug = slug(item.genre.tag);
    const thumbInner = item.image
      ? `<img src="${esc(item.image)}" alt="" loading="lazy" decoding="async" width="44" height="62" onerror="this.closest('.thumb').classList.add('thumb-broken')">`
      : "";
    const coverInner = item.image
      ? `<img src="${esc(item.image)}" alt="" loading="lazy" decoding="async" onerror="this.closest('.detail-cover').classList.add('thumb-broken')">`
      : "";
    return `
    <article class="card${isOpen ? " open" : ""}">
      <div class="card-row" data-rank="${item.rank}" tabindex="0" role="button" aria-expanded="${isOpen}">
        <span class="rank">#${item.rank}</span>
        <span class="thumb${item.image ? "" : " thumb-broken"}">${thumbInner}${placeholderHTML()}</span>
        <span class="card-main">
          <span class="title">${esc(item.title)}</span>
          <span class="tags">
            <span class="tag" style="--tag-color:var(--demo-${demoSlug})"><span class="dot"></span>${item.demographic.tag}</span>
            <span class="tag" style="--tag-color:var(--genre-${genreSlug})"><span class="dot"></span>${item.genre.tag}</span>
          </span>
        </span>
        <span class="points"><span class="n">${item.total_points.toLocaleString()}</span><span class="u">pts</span></span>
        <button type="button" class="star-btn" data-rank="${item.rank}" aria-pressed="${isStarred}" aria-label="${isStarred ? "Remove from my picks" : "Add to my picks"}">
          <svg viewBox="0 0 24 24"><path d="${STAR_ICON_PATH}"/></svg>
        </button>
        <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div class="details">
        <div class="details-inner">
          <div class="details-content">
            <div class="detail-cover-row">
              <span class="detail-cover${item.image ? "" : " thumb-broken"}">${coverInner}${placeholderHTML()}</span>
              <p class="synopsis">${item.synopsis ? esc(item.synopsis) : "No synopsis available yet."}</p>
            </div>
            <div class="votes-table">
              ${voteCell("1st", item.votes.first_place)}
              ${voteCell("2nd", item.votes.second_place)}
              ${voteCell("3rd", item.votes.third_place)}
              ${voteCell("4th–5th", item.votes.fourth_fifth_place)}
              ${voteCell("6th–10th", item.votes.sixth_tenth_place)}
              ${voteCell("11th–20th", item.votes.eleventh_twentieth_place)}
            </div>
            <p class="desc-block"><strong>${esc(item.demographic.tag)}.</strong> ${esc(item.demographic.description)}</p>
            <p class="desc-block"><strong>${esc(item.genre.tag)}.</strong> ${esc(item.genre.description)}</p>
          </div>
        </div>
      </div>
    </article>`;
  }

  function renderList() {
    const filtered = sortItems(ALL.filter(matches));
    const starredNote = starred.size ? ` · ${starred.size} starred` : "";
    $count.textContent = `${filtered.length} of ${ALL.length} shown${starredNote}`;

    if (!filtered.length) {
      $list.innerHTML = "";
      $empty.hidden = false;
      return;
    }
    $empty.hidden = true;
    $list.innerHTML = filtered.map(cardHTML).join("");
  }

  function toggleStar(rank) {
    if (starred.has(rank)) starred.delete(rank);
    else starred.add(rank);
    saveStarred();
    renderList();
  }

  function toggleOpen(rank) {
    if (openRanks.has(rank)) openRanks.delete(rank);
    else openRanks.add(rank);
    renderList();
  }

  function clearFilters() {
    state.search = "";
    state.demo.clear();
    state.genre.clear();
    state.starredOnly = false;
    state.sort = "rank";
    $search.value = "";
    $sort.value = "rank";
    $starredToggle.setAttribute("aria-pressed", "false");
    renderChips();
    renderList();
  }

  $list.addEventListener("click", (e) => {
    const starBtn = e.target.closest(".star-btn");
    if (starBtn) {
      toggleStar(Number(starBtn.dataset.rank));
      return;
    }
    const row = e.target.closest(".card-row");
    if (row) toggleOpen(Number(row.dataset.rank));
  });

  $list.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const row = e.target.closest(".card-row");
    if (row) {
      e.preventDefault();
      toggleOpen(Number(row.dataset.rank));
    }
  });

  let searchTimer;
  $search.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const value = e.target.value;
    searchTimer = setTimeout(() => {
      state.search = value.trim();
      renderList();
    }, 120);
  });

  $sort.addEventListener("change", (e) => {
    state.sort = e.target.value;
    renderList();
  });

  $starredToggle.addEventListener("click", () => {
    state.starredOnly = !state.starredOnly;
    $starredToggle.setAttribute("aria-pressed", String(state.starredOnly));
    renderList();
  });

  $clear.addEventListener("click", clearFilters);
  $emptyClear.addEventListener("click", clearFilters);

  // ---- Install prompt (Android/Chrome + manual iOS tip) ----
  const $toast = document.getElementById("install-toast");
  const $installBtn = document.getElementById("install-btn");
  const $installDismiss = document.getElementById("install-dismiss");
  let deferredPrompt = null;

  function isIOS() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  }
  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (!localStorage.getItem(DISMISS_KEY)) $toast.hidden = false;
  });

  $installBtn.addEventListener("click", async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
    }
    $toast.hidden = true;
  });

  $installDismiss.addEventListener("click", () => {
    $toast.hidden = true;
    localStorage.setItem(DISMISS_KEY, "1");
  });

  if (isIOS() && !isStandalone() && !localStorage.getItem(DISMISS_KEY)) {
    $toast.querySelector("span").textContent = 'Install: tap Share, then "Add to Home Screen".';
    $installBtn.hidden = true;
    $toast.hidden = false;
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }

  // ---- Init ----
  async function init() {
    renderChips();
    try {
      const res = await fetch(DATA_URL, { cache: "no-cache" });
      ALL = await res.json();
    } catch (err) {
      $count.textContent = "Failed to load dataset.";
      return;
    }
    renderList();
  }

  init();
})();
