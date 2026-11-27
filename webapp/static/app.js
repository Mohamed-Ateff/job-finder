"use strict";

/* ====================================================================== utils */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
const store = {
  get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};
const narrow = window.matchMedia("(max-width: 760px)");

/* ================================================================ language */
let LANG = store.get("lang", store.get("guide-lang", "en")) === "ar" ? "ar" : "en";
const isAr = () => LANG === "ar";
/* t("Run Search") -> the Arabic text when the app is in Arabic; {placeholders} filled from vars (inserted as given). */
function t(text, vars) {
  let out = isAr() ? (window.AR?.[text] ?? text) : text;
  if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  return out;
}
/* count(3, "job") -> "3 jobs" / "3 وظائف" (Arabic: one, two, 3-10, 11 and up). */
const EN_COUNT = { job: ["job", "jobs"], match: ["match", "matches"], keyword: ["keyword", "keywords"], search: ["search", "searches"],
  title: ["job title", "job titles"], newjob: ["new job", "new jobs"], posting: ["posting", "postings"], cv: ["CV", "CVs"] };
function count(n, kind) {
  if (!isAr()) return `${n} ${n === 1 ? EN_COUNT[kind][0] : EN_COUNT[kind][1]}`;
  const f = window.AR_COUNT[kind];
  if (n === 1) return f[0];
  if (n === 2) return f[1];
  const m = n % 100;
  return `${n} ${m >= 3 && m <= 10 ? f[2] : f[3]}`;
}
const locale = () => (isAr() ? "ar-u-nu-latn" : undefined);

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: { "X-Requested-With": "jobauto", ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && path !== "/api/login") { showLogin(); throw new Error("auth"); }
  const isJson = (res.headers.get("content-type") || "").includes("json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) throw new Error((isJson && data.detail) || res.statusText);
  return data;
}

/* ====================================================================== dates */
const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const daysAgo = (iso) => Math.round((dayStart(new Date()) - dayStart(new Date(iso))) / 864e5);
const clock = (iso) => new Date(iso).toLocaleTimeString(locale(), { hour: "numeric", minute: "2-digit" });
function relDay(iso) {
  const n = daysAgo(iso);
  if (n === 0) return t("Today");
  if (n === 1) return t("Yesterday");
  if (n < 7) return new Date(iso).toLocaleDateString(locale(), { weekday: "long" });
  return new Date(iso).toLocaleDateString(locale(), { day: "numeric", month: "short", year: n > 300 ? "numeric" : undefined });
}
const relDateTime = (iso) => t("{day} at {time}", { day: relDay(iso), time: clock(iso) });
/* When the job site says the job was posted: "Posted today", "Posted yesterday", "Posted 3 days ago". */
function postedLabel(date) {
  if (!/^\d{4}-\d\d-\d\d$/.test(date || "")) return "";
  const [y, m, d] = date.split("-").map(Number);
  const days = Math.round((dayStart(new Date()) - new Date(y, m - 1, d)) / 864e5);
  if (days <= 0) return t("Posted today");
  if (days === 1) return t("Posted yesterday");
  return t("Posted {n} days ago", { n: days });
}
/* The same, short, for the job's facts: "Today", "Yesterday", "4 days ago". */
function postedShort(date) {
  if (!/^\d{4}-\d\d-\d\d$/.test(date || "")) return "";
  const [y, m, d] = date.split("-").map(Number);
  const days = Math.round((dayStart(new Date()) - new Date(y, m - 1, d)) / 864e5);
  return days <= 0 ? t("Today") : days === 1 ? t("Yesterday") : t("{n} days ago", { n: days });
}
function dayGroup(iso) {
  const n = daysAgo(iso);
  if (n <= 0) return t("Today");
  if (n === 1) return t("Yesterday");
  if (n < 7) return t("Previous 7 Days");
  if (n < 30) return t("Previous 30 Days");
  return new Date(iso).toLocaleDateString(locale(), { month: "long", year: "numeric" });
}

/* ====================================================================== icons */
const P = {
  tray: '<path d="M4 13.5 6.3 6.6A2 2 0 0 1 8.2 5.2h7.6a2 2 0 0 1 1.9 1.4L20 13.5v4.3a1.7 1.7 0 0 1-1.7 1.7H5.7A1.7 1.7 0 0 1 4 17.8z"/><path d="M4 13.5h4.2l1.3 2.3h5l1.3-2.3H20"/>',
  list: '<path d="M9.5 6.5h10.5M9.5 12h10.5M9.5 17.5h10.5"/><circle cx="5" cy="6.5" r="1.2" fill="currentColor" stroke="none"/><circle cx="5" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="5" cy="17.5" r="1.2" fill="currentColor" stroke="none"/>',
  envelope: '<rect x="3.5" y="5.5" width="17" height="13" rx="2.5"/><path d="m4.5 7.5 7.5 5.2 7.5-5.2"/>',
  checklist: '<path d="m3.8 6.6 1.5 1.5 3-3M3.8 12.6l1.5 1.5 3-3M3.8 18.6l1.5 1.5 3-3M11.5 7h8.5M11.5 13h8.5M11.5 19h8.5"/>',
  sliders: '<path d="M4 7.5h10M18 7.5h2M4 16.5h2M10 16.5h10"/><circle cx="16" cy="7.5" r="2"/><circle cx="8" cy="16.5" r="2"/>',
  play: '<path d="M8 5.6v12.8a.8.8 0 0 0 1.2.7l10.3-6.4a.8.8 0 0 0 0-1.4L9.2 4.9A.8.8 0 0 0 8 5.6z" fill="currentColor" stroke="none"/>',
  search: '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 4.5 4.5"/>',
  chevR: '<path d="m9.5 6 6 6-6 6"/>',
  chevL: '<path d="m15 5-7 7 7 7"/>',
  updown: '<path d="m8 9.5 4-4 4 4M8 14.5l4 4 4-4"/>',
  check: '<path d="m5.5 12.5 4 4 9-9.5"/>',
  checkCircle: '<circle cx="12" cy="12" r="9.5" fill="currentColor" stroke="none"/><path d="m7.8 12.3 2.9 2.9 5.6-6" stroke="#fff" stroke-width="2"/>',
  xCircle: '<circle cx="12" cy="12" r="9.5" fill="currentColor" stroke="none"/><path d="m8.8 8.8 6.4 6.4M15.2 8.8l-6.4 6.4" stroke="#fff" stroke-width="2"/>',
  halfCircle: '<circle cx="12" cy="12" r="9.5" fill="currentColor" stroke="none"/><path d="M8 12h8" stroke="#fff" stroke-width="2.2"/>',
  circle: '<circle cx="12" cy="12" r="8.5"/>',
  warn: '<path d="M10.3 4.3a2 2 0 0 1 3.4 0l7.2 12.6A2 2 0 0 1 19.2 20H4.8a2 2 0 0 1-1.7-3.1z" fill="currentColor" stroke="none"/><path d="M12 9v4.5M12 16.6v.1" stroke="#fff" stroke-width="2"/>',
  external: '<path d="M8.5 6.5h9v9M17.5 6.5l-11 11"/>',
  download: '<path d="M12 4.5v10m0 0 4-4m-4 4-4-4M5 19h14"/>',
  copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2.2"/><path d="M15.5 8.5V6.7a2.2 2.2 0 0 0-2.2-2.2H6.7a2.2 2.2 0 0 0-2.2 2.2v6.6a2.2 2.2 0 0 0 2.2 2.2h1.8"/>',
  close: '<path d="m6.5 6.5 11 11M17.5 6.5l-11 11"/>',
  auto: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor" stroke="none"/>',
  sun: '<circle cx="12" cy="12" r="3.6"/><path d="M12 3.2v2M12 18.8v2M3.2 12h2M18.8 12h2M5.8 5.8l1.4 1.4M16.8 16.8l1.4 1.4M5.8 18.2l1.4-1.4M16.8 7.2l1.4-1.4"/>',
  moon: '<path d="M19.5 14.6A8 8 0 0 1 9.4 4.5a8 8 0 1 0 10.1 10.1z"/>',
  arrowR: '<path d="M5 12h14m-5.5-5.5L19 12l-5.5 5.5"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.5 3.5 5.3 3.5 8.5s-1.1 6-3.5 8.5c-2.4-2.5-3.5-5.3-3.5-8.5S9.6 6 12 3.5z"/>',
  sparkles: '<path d="M11 3.5 12.9 9l5.6 1.9-5.6 1.9L11 18.3l-1.9-5.5-5.6-1.9L9.1 9z" fill="currentColor" stroke="none"/><path d="m18 14.5.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" fill="currentColor" stroke="none"/>',
  card: '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M3 10h18M7 14.5h3.5"/>',
  paperplane: '<path d="M20.5 3.5 3.5 10.6l6.8 2.6 2.6 6.8z"/><path d="m10.3 13.2 4.6-4.6"/>',
  at: '<circle cx="12" cy="12" r="3.4"/><path d="M15.4 12v1.3a2.6 2.6 0 0 0 5.1 0V12a8.5 8.5 0 1 0-3.3 6.7"/>',
  person2: '<circle cx="9" cy="8.5" r="3"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><circle cx="16.5" cy="9" r="2.4"/><path d="M16 14c2.4 0 4 1.5 4.6 4.5"/>',
  thumb: '<path d="M8 10.5v9M8 10.5 11.2 4.4a1.6 1.6 0 0 1 3 1.2L13.4 9h4.7a2 2 0 0 1 2 2.4l-1.3 6.4a2 2 0 0 1-2 1.7H8M4 10.5h4v9H4z"/>',
  stack: '<path d="m12 4 8.5 4.5L12 13 3.5 8.5z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5M3.5 16.5l8.5 4.5 8.5-4.5"/>',
  tag: '<path d="M3.5 12.6V4.8a1.3 1.3 0 0 1 1.3-1.3h7.8l8.2 8.2a1.3 1.3 0 0 1 0 1.8l-7 7a1.3 1.3 0 0 1-1.8 0z"/><circle cx="8" cy="8" r="1.4" fill="currentColor"/>',
  cap: '<path d="m2.5 9.5 9.5-4.8 9.5 4.8-9.5 4.8z"/><path d="M6.5 11.5v4.3c1.4 1.3 3.3 2 5.5 2s4.1-.7 5.5-2v-4.3M21.5 9.5v5"/>',
  rosette: '<circle cx="12" cy="9" r="5"/><path d="m8.9 13-1.4 7.5 4.5-2.4 4.5 2.4-1.4-7.5"/>',
  cpu: '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/><path d="M9.5 3.5v3M14.5 3.5v3M9.5 17.5v3M14.5 17.5v3M3.5 9.5h3M3.5 14.5h3M17.5 9.5h3M17.5 14.5h3"/>',
  shield: '<path d="M12 3.5 19 6v5.5c0 4.3-2.9 7.8-7 9-4.1-1.2-7-4.7-7-9V6z"/><path d="m8.8 12 2.2 2.2 4.2-4.4"/>',
  server: '<rect x="4" y="4.5" width="16" height="6.5" rx="1.6"/><rect x="4" y="13" width="16" height="6.5" rx="1.6"/><path d="M7.5 7.75h.1M7.5 16.25h.1" stroke-width="2.4"/>',
  doc: '<path d="M7 3.5h6.5L18 8v12.5H7z"/><path d="M13.5 3.5V8H18M9.5 12.5h5.5M9.5 16h5.5"/>',
  pin: '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
  briefcase: '<rect x="3.5" y="7" width="17" height="12.5" rx="2.6"/><path d="M9 7V5.6A1.6 1.6 0 0 1 10.6 4h2.8A1.6 1.6 0 0 1 15 5.6V7M3.5 12.2h17"/>',
  book: '<path d="M12 6.4c-1.8-1.4-4.3-2-7.5-1.9v13c3.2-.1 5.7.5 7.5 1.9 1.8-1.4 4.3-2 7.5-1.9v-13c-3.2-.1-5.7.5-7.5 1.9zM12 6.4v13"/>',
  building: '<path d="M5 20.5V5.2A1.2 1.2 0 0 1 6.2 4h7.6A1.2 1.2 0 0 1 15 5.2v15.3M15 10h3.8a1.2 1.2 0 0 1 1.2 1.2v9.3M3.5 20.5h17M8.5 7.8h3M8.5 11h3M8.5 14.2h3"/>',
  funnel: '<path d="M4 5.5h16l-6.2 7.2v5.6l-3.6 1.7v-7.3z"/>',
  gauge: '<path d="M4.4 17a8.5 8.5 0 1 1 15.2 0"/><path d="m12 13.5 3.6-4.6"/><circle cx="12" cy="13.6" r="1.3" fill="currentColor" stroke="none"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  bulb: '<path d="M9 17.5h6M10 20.5h4M12 3.5a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V17h5.2v-.7c0-.8.4-1.5 1-2A6 6 0 0 0 12 3.5z"/>',
  question: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.6M12 16.6v.1"/>',
  apps: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.8"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.8"/>',
  wrench: '<path d="M14.6 5.4a4.2 4.2 0 0 0-5.4 5.4l-5 5a1.8 1.8 0 0 0 2.6 2.6l5-5a4.2 4.2 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
  person: '<circle cx="12" cy="8.5" r="3.7"/><path d="M4.8 20c.8-3.9 3.6-6.1 7.2-6.1s6.4 2.2 7.2 6.1"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7M18.5 18.5l-1.7-1.7M7.2 7.2 5.5 5.5"/><circle cx="12" cy="12" r="6.3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  upload: '<path d="M12 15.5v-10m0 0-4 4m4-4 4 4M5 19h14"/>',
  trash: '<path d="M4.5 7h15M9.5 7V5.2a1.2 1.2 0 0 1 1.2-1.2h2.6a1.2 1.2 0 0 1 1.2 1.2V7M6.5 7l.9 11.6a1.6 1.6 0 0 0 1.6 1.4h6a1.6 1.6 0 0 0 1.6-1.4L17.5 7M10 11v5.5M14 11v5.5"/>',
  note: '<path d="M5 4.5h14v15H5z"/><path d="M8.5 9h7M8.5 12.5h7M8.5 16h4"/>',
};
const icon = (name, size = 18, cls = "", sw = 1.6) =>
  `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ""}</svg>`;

const COLORS = {
  blue: ["#47a1ff", "#0a74f0"], indigo: ["#8583ff", "#5856d6"], purple: ["#cd85ff", "#a855dc"], pink: ["#ff6f91", "#ff2d55"],
  red: ["#ff6b62", "#f2382c"], orange: ["#ffb547", "#ff9200"], green: ["#5edd7d", "#2fbf55"], teal: ["#5fd4e8", "#2aa9c2"],
  gray: ["#a9aeb6", "#878c95"], brown: ["#c9a47d", "#a3825c"], graphite: ["#7b8088", "#5b6069"],
};
/* No coloured icon tiles: rows and headings are carried by their words (kept as a no-op for old call sites). */
const tile = () => "";
const TILES = {
  ai: ["sparkles", "purple"], openai: ["sparkles", "purple"], credit: ["card", "green"], brevo: ["paperplane", "teal"], sender: ["at", "indigo"],
  recipient: ["envelope", "blue"], cc: ["person2", "gray"], go_ahead: ["thumb", "green"], tracks: ["stack", "indigo"],
  keywords: ["tag", "orange"], degree: ["cap", "brown"], certificates: ["rosette", "pink"], sources: ["globe", "teal"],
  model: ["cpu", "purple"], domain: ["shield", "green"], vps: ["server", "graphite"],
};
const initialsOf = (name) => (name || "").trim().split(/\s+/).slice(0, 2).map((w) => w[0] || "").join("").toUpperCase();
/* The company's own logo (from LinkedIn / Indeed), on a white tile like an app icon.
   No logo, or one that fails to load: a quiet building glyph, never a coloured letter. */
/* No logo from the job site: the company's first letter, like a printed letterhead. */
const letterOf = (name) => (String(name || "").trim().match(/[\p{L}\p{N}]/u)?.[0] || "").toUpperCase();
const logoFallback = (lg, letter) => (letter ? `<b class="mono">${esc(letter)}</b>` : icon("building", lg ? 32 : 20, "", 1.4));
function logo(job, cls = "") {
  // Bayt's "aggregated" logo is a blank placeholder: the company's letter says more.
  const url = job?.logo && /^https:\/\//.test(job.logo) && !/aggregated_logo/.test(job.logo) ? job.logo : "";
  const letter = letterOf(job?.company);
  if (!url) return `<span class="logo ph ${cls}" data-letter="${esc(letter)}" aria-hidden="true">${logoFallback(cls === "lg", letter)}</span>`;
  // The letter shows until the logo arrives, then the logo fades in over it.
  return `<span class="logo ${cls}" data-letter="${esc(letter)}">${logoFallback(cls === "lg", letter)}<img src="${esc(url)}" alt="${esc(job.company || "")}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></span>`;
}
document.addEventListener("load", (e) => {
  const img = e.target;
  if (img?.tagName !== "IMG" || !img.parentElement?.classList.contains("logo")) return;
  const box = img.parentElement;
  if (img.naturalWidth <= 2) {           // an empty pixel instead of a logo: keep the letter
    box.classList.add("ph");
    box.innerHTML = logoFallback(box.classList.contains("lg"), box.dataset.letter);
    return;
  }
  box.classList.add("loaded");
}, true);
document.addEventListener("error", (e) => {
  const img = e.target;
  if (img?.tagName !== "IMG" || !img.parentElement?.classList.contains("logo")) return;
  const box = img.parentElement;
  box.classList.add("ph");
  box.innerHTML = logoFallback(box.classList.contains("lg"), box.dataset.letter);
}, true);
const SITE = { linkedin: "LinkedIn", indeed: "Indeed", bayt: "Bayt", demo: "Sample job" };
const siteName = (s) => (s === "demo" ? t(SITE.demo) : SITE[s] || cap(s || ""));
/* Initials in a quiet circle, the way a printed directory would set them. */
const avatar = (c, cls = "") => `<span class="avatar ${cls}">${esc(c?.initials || initialsOf(c?.name))}</span>`;

/* ====================================================================== state */
const VIEWS = {
  jobs: { title: "Jobs", icon: "briefcase", kind: "list", needs: ["jobs"] },
  profile: { title: "Profile", icon: "person", kind: "page", needs: ["profile"] },
  settings: { title: "Settings", icon: "gear", kind: "page", needs: ["settings"] },
  guide: { title: "How It Works", tab: "Guide", icon: "book", kind: "page", needs: ["profile"] },
};
const ROUTE_ALIASES = { matches: "jobs", digests: "jobs", setup: "profile" };   // old links still land somewhere sensible
/* Matches split in two: jobs in the person's own country, and remote ones. Then everything, and Applied. */
const filters = () => [["matches", C().country || "Matches"], ["remote", "Remote"], ["all", "All"], ["applied", "Applied"]];
const VERDICT = { strong: "Strong", good: "Good", moderate: "Moderate", weak: "Weak" };
const MODES = {
  dry: { label: "Preview", start: "Start Preview",
    lede: () => "Finds today's roles, scores them and writes the digest and CVs — without emailing anything." },
  replay: { label: "Replay", start: "Replay Search",
    lede: () => "Scores a search you've already run, without searching the job sites again. Only jobs that haven't been scored before are evaluated." },
  real: { label: "Send", start: "Run and Send",
    lede: (o) => (o.recipient ? t("The full daily run: find, score, write CVs and email the digest to {to}.", { to: o.recipient })
      : "The full daily run: find, score, write CVs and email the digest.") },
};
/* Without the email digest a search just saves its matches here, so "real" is simply "Search". */
const SEARCH_MODE = { label: "Search", start: "Start Search",
  lede: () => "Finds today’s roles, scores them and writes a tailored CV for each strong match. Everything is saved here, ready for you to apply." };
/* Server-side labels for what a run is missing, e.g. "working OpenAI API key". */
const missingLabel = (label) => (label.startsWith("working ") ? t("working {x}", { x: t(label.slice(8)) }) : t(label));
/* One kind of search unless the email digest is on (then: preview first, or search and send). */
const modeList = (email) => (email ? ["dry", "real"] : ["real"]);
const modeInfo = (mode, email) => (!email && mode === "real" ? SEARCH_MODE : MODES[mode]);
const STEP_SHORT = { collect: "Finding postings", filter: "Filtering", score: "Scoring", cvs: "Writing CVs", send: "Saving" };
const STAGE_TEXT = { collect: "Finding new postings", filter: "Filtering and removing duplicates", score: "Scoring jobs against the profile", cvs: "Preparing CVs", send: "Saving the results" };

const S = {
  candidates: [], key: store.get("candidate", null), view: "jobs", appearance: store.get("appearance", "auto"),
  cache: {}, sel: {}, query: "", filter: "matches", forms: {}, runs: {}, finishedAt: {}, poll: null, token: 0,
  expanded: null, trackOpen: null, detailOpen: false, booted: false, painted: "", before: {},
  applying: null, company: {},
};
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const cand = () => S.candidates.find((c) => c.key === S.key) || S.candidates[0];
const first = () => (cand()?.name || "").split(" ")[0];
const C = () => (S.cache[S.key] ||= {});

async function fetchKind(kind) {
  if (kind === "summary") return api(`/api/overview/${enc(S.key)}`);
  if (kind === "jobs") {
    const r = await api(`/api/jobs/${enc(S.key)}`);
    C().country = r.country || "";
    if (r.checking_apply) watchApplyChecks(S.key);
    return r.jobs;
  }
  if (kind === "runs") return (await api(`/api/runs/${enc(S.key)}`)).runs;
  if (kind === "settings") return api("/api/settings");
  if (kind === "profile") return api(`/api/profile/${enc(S.key)}`);
  return null;
}
/* While the server asks LinkedIn how older jobs are applied to, pick up its answers every
   half minute and update only the rows (an open job and anything being typed stay as they are). */
const applyWatch = {};
function watchApplyChecks(key) {
  if (applyWatch[key]) return;
  applyWatch[key] = setTimeout(async () => {
    applyWatch[key] = null;
    let r;
    try { r = await api(`/api/jobs/${enc(key)}`); } catch { return; }
    const jobs = S.cache[key]?.jobs;
    if (!jobs) return;
    const fresh = new Map(r.jobs.map((j) => [j.url, j]));
    for (const job of jobs) {
      const f = fresh.get(job.url);
      if (f && f.apply && f.apply !== job.apply) {
        if (key === S.key) setApply(job, f.apply, f.emails);
        else { job.apply = f.apply; job.emails = f.emails; }
      }
    }
    if (r.checking_apply) watchApplyChecks(key);
  }, 30000);
}
async function need(...kinds) {
  const c = C();
  await Promise.all(kinds.filter((k) => c[k] === undefined).map(async (k) => { c[k] = await fetchKind(k); }));
}
const invalidate = (...kinds) => kinds.forEach((k) => delete C()[k]);

/* ================================================================ appearance */
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
function applyAppearance(pref, animate = false) {
  S.appearance = pref;
  store.set("appearance", pref);
  const root = document.documentElement;
  if (animate) {
    root.classList.add("theme-fade");
    clearTimeout(applyAppearance.t);
    applyAppearance.t = setTimeout(() => root.classList.remove("theme-fade"), 360);
  }
  root.dataset.theme = pref === "dark" || (pref === "auto" && darkQuery.matches) ? "dark" : "light";
  $$('[data-seg="appearance"]').forEach((g) => setSeg(g, pref));
  $$("[data-appearance]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.appearance === pref)));
}
darkQuery.addEventListener("change", () => S.appearance === "auto" && applyAppearance("auto", true));

/* ================================================================ components */
function seg(name, options, value, cls = "") {
  const i = Math.max(0, options.findIndex(([v]) => v === value));
  return `<div class="seg ${cls}" data-seg="${name}" role="tablist" style="--n:${options.length};--i:${i}">${
    options.map(([v, label, title]) => `<button type="button" role="tab" data-value="${esc(v)}" aria-selected="${v === value}"${title ? ` title="${esc(title)}" aria-label="${esc(title)}"` : ""}>${label}</button>`).join("")
  }</div>`;
}
function setSeg(group, value) {
  const buttons = [...group.children];
  const i = buttons.findIndex((b) => b.dataset.value === value);
  if (i < 0) return;
  buttons.forEach((b, j) => b.setAttribute("aria-selected", String(j === i)));
  group.style.setProperty("--i", i);
}

let hudTimer;
function hud(text, glyph = "check") {
  $(".hud")?.remove();
  const el = document.createElement("div");
  el.className = "hud";
  el.innerHTML = `${icon(glyph, 46, "", 2)}<span>${esc(t(text))}</span>`;
  document.body.append(el);
  requestAnimationFrame(() => el.classList.add("in"));
  clearTimeout(hudTimer);
  hudTimer = setTimeout(() => { el.classList.remove("in"); setTimeout(() => el.remove(), 300); }, 1300);
}
function banner(text) {
  $(".banner")?.remove();
  const el = document.createElement("div");
  el.className = "banner";
  el.setAttribute("role", "alert");
  el.innerHTML = `${icon("warn", 16)}<span dir="auto">${esc(t(text))}</span><button class="icon-btn" data-action="dismiss" aria-label="${esc(t("Dismiss"))}">${icon("close", 13, "", 2)}</button>`;
  document.body.append(el);
  setTimeout(() => el.remove(), 7000);
}

/* ===================================================================== shell */
function renderShell() {
  $("#root").innerHTML = `
    <div class="window" id="window">
      <aside class="sidebar" id="sidebar"></aside>
      <section class="content">
        <header class="bar" id="bar"></header>
        <div id="demo-bar"></div>
        <main id="main" style="flex:1;min-height:0;display:flex;flex-direction:column"></main>
      </section>
    </div>
    <nav class="tabbar" id="tabbar"></nav>`;
}

function paintSidebar() {
  const sum = C().summary, c = cand();
  const matches = sum ? (sum.metrics.strong || 0) + (sum.metrics.good || 0) : 0;
  const todo = { profile: sum?.readiness?.profile || 0, settings: sum?.readiness?.settings || 0 };
  const counts = { jobs: matches || "", ...todo };
  const item = (id) => `<a class="sb-item ${S.view === id ? "active" : ""}" href="#/${id}">${icon(VIEWS[id].icon, 17)}<span>${esc(t(VIEWS[id].title))}</span><span class="sb-count${id in todo ? " todo" : ""}">${counts[id] || ""}</span></a>`;
  $("#sidebar").innerHTML = `
    <button class="account" data-action="account" aria-haspopup="menu" title="${esc(c.system_label)}">${avatar(c)}
      <span class="account-text"><bdi class="account-name">${esc(c.name)}</bdi></span>
      ${icon("updown", 13, "chev", 2)}</button>
    <nav class="sb-nav">
      ${item("jobs")}${item("profile")}${item("settings")}
      <div class="sb-gap"></div>
      ${item("guide")}
    </nav>
    <div class="sb-foot"><div id="sb-status">${statusHtml()}</div></div>`;
  const tabs = ["jobs", "profile", "settings", "guide"];
  $("#tabbar").innerHTML = tabs.map((id) => `<a class="tab ${S.view === id ? "active" : ""}" href="#/${id}">${icon(VIEWS[id].icon, 24, "", 1.5)}
    ${todo[id] ? `<span class="badge">${todo[id]}</span>` : ""}<span>${esc(t(VIEWS[id].tab || VIEWS[id].title))}</span></a>`).join("");
}
/* Appearance and language: plain segmented controls in Settings. */
const appearancePick = () => seg("appearance", [["auto", esc(t("Automatic"))], ["light", esc(t("Light"))], ["dark", esc(t("Dark"))]], S.appearance);
const langPick = () => seg("lang", [["en", "English"], ["ar", '<span lang="ar">العربية</span>']], LANG);

function barSubtitle() {
  const c = C(), sum = c.summary;
  if (S.view === "jobs") {
    const all = c.jobs || [];
    if (!all.length) return t("No jobs yet");
    const m = all.filter(isMatch).length, applied = all.filter((j) => j.applied).length;
    const vars = { m: isAr() ? m : count(m, "match"), all: all.length, applied };
    return applied ? t("{m} · {all} scored · {applied} applied", vars) : t("{m} · {all} scored", vars);
  }
  if (S.view === "guide") return t("Everything about how the app works");
  if (S.view === "settings") return t("For the whole app and everyone in it");
  if (S.view === "profile" && sum) {
    const open = sum.readiness.profile;
    return open ? t("{n} still needed", { n: open }) : t("Saved automatically as you type");
  }
  return cand()?.system_label || "";
}

function paintBar() {
  const v = VIEWS[S.view];
  const running = S.runs[S.key]?.status === "running" || C().summary?.active?.external;
  const searchable = v.kind === "list";
  $("#bar").innerHTML = `
    <button class="back" data-action="back">${icon("chevL", 20, "flip", 2.2)}${esc(t(v.title))}</button>
    <button class="nav-avatar" data-action="account" aria-label="${esc(t("Switch person"))}">${avatar(cand())}</button>
    <div class="bar-title">${v.kind === "list" ? `<h1>${esc(t(v.title))}</h1><p dir="auto">${esc(barSubtitle())}</p>` : ""}</div>
    <div class="bar-right">
      ${searchable ? `<label class="search">${icon("search", 14)}<input id="q" type="search" placeholder="${esc(t("Search"))}" value="${esc(S.query)}" autocomplete="off" spellcheck="false"></label>` : ""}
      ${runButton(running)}
    </div>`;
}

function paintDemoBar() {
  $("#demo-bar").innerHTML = S.demo
    ? `<div class="demo-bar" role="status"><span>${t("<b>Demo Mode</b> — sample jobs and a simulated AI. Nothing is emailed, and your real data isn’t touched.")}</span>
        <button class="btn link" data-action="demo-reset">${esc(t("Reset Demo"))}</button><button class="btn link" data-action="demo-off">${esc(t("Turn Off"))}</button></div>`
    : "";
}

/* Switch the whole interface between English and Arabic (right to left). */
function applyLang(lang) {
  LANG = lang === "ar" ? "ar" : "en";
  store.set("lang", LANG);
  document.documentElement.lang = LANG;
  document.documentElement.dir = isAr() ? "rtl" : "ltr";
  closeFloating();
  transition(() => { paintSidebar(); paintBar(); paintDemoBar(); paintMain(false); });
}

async function setDemo(on) {
  try {
    const r = await api("/api/demo", { method: "POST", body: { on } });
    S.demo = r.demo;
    S.cache = {};
    S.runs = {};
    S.sel = {};
    paintDemoBar();
    await render();
    hud(t(on ? "Demo Mode On" : "Demo Mode Off"), "check");
  } catch (err) { if (err.message !== "auth") banner(err.message); }
}

/* Search status at the foot of the sidebar, like Mail's "Updated Just Now". */
function statusHtml() {
  const run = S.runs[S.key], sum = C().summary;
  const wrap = (inner, extra = "") => `<button class="sb-status" data-action="activity" aria-label="${esc(t("Search activity"))}">${inner}${extra}</button>`;
  if (run?.status === "running") {
    const order = run.stages.map(([k]) => k);
    const pct = Math.round(((order.indexOf(run.stage) + .5) / order.length) * 100);
    return wrap(`<span class="spin"></span><span><b>${esc(t(STAGE_TEXT[run.stage] || "Working"))}…</b></span>`,
      `<i class="progress"><i style="width:${pct}%"></i></i>`);
  }
  if (sum?.active?.external) return wrap(`<span class="spin"></span><span><b>${esc(t("Scheduled search running…"))}</b></span>`);
  if (run && Date.now() - (S.finishedAt[S.key] || 0) < 90000) {
    const ok = run.status === "finished";
    return wrap(`${icon(ok ? "checkCircle" : "xCircle", 14, ok ? "ok" : "bad")}<span><b>${esc(t(ok ? "Search finished" : "Search stopped"))}</b></span>`);
  }
  const last = sum?.runs?.[0];
  return wrap(`<span>${esc(last ? t("Last search {when}", { when: relDateTime(last.started) }) : t("No searches yet"))}</span>`);
}

/* ===================================================================== router */
function route() {
  let name = (location.hash.replace(/^#\/?/, "") || "jobs").split("/")[0];
  if (ROUTE_ALIASES[name]) {
    if (name === "matches") S.filter = "matches";
    name = ROUTE_ALIASES[name];
  }
  const next = VIEWS[name] ? name : "jobs";
  if (next !== S.view) { S.query = ""; S.detailOpen = false; flushSave(); }
  S.view = next;
  closeFloating();
  render();
}

/* Page and person changes cross-fade (View Transitions); everything else repaints in place. */
function transition(paint) {
  if (!document.startViewTransition || reduceMotion.matches) return paint();
  const vt = document.startViewTransition(paint);
  // A quicker click starts a new transition and skips this one: that's expected, not an error.
  [vt.ready, vt.finished, vt.updateCallbackDone].forEach((p) => p.catch(() => {}));
}

async function render({ quiet = false } = {}) {
  const token = ++S.token;
  if (!C().summary && !quiet) paintSkeleton();
  try {
    await need("summary", ...VIEWS[S.view].needs);
  } catch (err) {
    if (err.message !== "auth") banner(err.message);
    return;
  }
  if (token !== S.token) return;
  adoptRun(C().summary?.active);
  const where = `${S.key}/${S.view}`;
  // The transition runs this a moment later; if another page was opened meanwhile, it paints instead.
  const paint = () => { if (token !== S.token) return; paintSidebar(); paintBar(); paintDemoBar(); paintMain(quiet); };
  if (!quiet && S.painted && S.painted !== where) transition(paint);
  else paint();
  S.painted = where;
}

/* While the first data loads: the shape of the page, gently pulsing - never a blank window. */
function paintSkeleton() {
  const main = $("#main");
  if (!main || main.childElementCount) return;
  const rows = Array.from({ length: 7 }, () =>
    '<div class="sk-row"><i class="sk sk-logo"></i><span><i class="sk sk-line"></i><i class="sk sk-line short"></i></span></div>').join("");
  main.innerHTML = `<div class="split skeleton"><div class="list-pane">${rows}</div><div class="detail-pane"></div></div>`;
}

function paintMain(quiet) {
  const main = $("#main");
  const v = VIEWS[S.view];
  if (v.kind === "page") {
    const prev = $(".page", main);
    const y = quiet && prev ? prev.scrollTop : 0;
    const html = S.view === "settings" ? settingsHtml() : S.view === "guide" ? guideHtml() : profileHtml();
    main.innerHTML = `<div class="page${S.view === "guide" ? " page-guide" : ""}">${html}</div>`;
    $$("textarea.area", main).forEach(autoGrow);
    $(".page", main).scrollTop = y;
    return;
  }
  let split = $(".split", main);
  if (!split || split.dataset.view !== S.view) {
    main.innerHTML = `<div class="split" data-view="${S.view}"><div class="list-pane" id="list"></div><div class="detail-pane" id="detail"></div></div>`;
    split = $(".split", main);
  }
  paintList(quiet);
  paintDetail(!quiet);
}

/* =============================================================== lists */
const isMatch = (j) => j.verdict === "strong" || j.verdict === "good";function jobsFor() {
  let rows = C().jobs || [];
  if (S.filter === "matches") rows = rows.filter((j) => isMatch(j) && !j.remote);
  else if (S.filter === "remote") rows = rows.filter((j) => isMatch(j) && j.remote);  else if (S.filter === "applied") rows = rows.filter((j) => j.applied);
  const q = S.query.trim().toLowerCase();
  if (q) rows = rows.filter((j) => `${j.title} ${j.company} ${j.location} ${j.track_name}`.toLowerCase().includes(q));
  // The latest search's jobs first, best score first; everything older below, as before.
  const fresh = rows.filter((j) => j.new).sort((a, b) => b.fit - a.fit);
  return [...fresh, ...rows.filter((j) => !j.new)];
}
const itemsFor = jobsFor;
const idOf = (x) => x.url;

function paintList(quiet) {
  const list = $("#list");
  const items = itemsFor();
  if (!narrow.matches && !items.some((x) => idOf(x) === S.sel[S.view])) S.sel[S.view] = items[0] ? idOf(items[0]) : null;
  const all = C().jobs || [];
  // Nothing at all yet (not just a filter or search with no hits): one calm, centred empty state, no reader pane.
  const blank = !all.length && !S.query;
  $(".split")?.classList.toggle("is-empty", blank);
  const counts = { new: all.filter((j) => j.new).length, matches: all.filter((j) => isMatch(j) && !j.remote).length,
    remote: all.filter((j) => isMatch(j) && j.remote).length, all: all.length, applied: all.filter((j) => j.applied).length };
  const tools = all.length ? `<div class="list-tools">${seg("filter",
    filters().map(([v, label]) => [v, `<span class="seg-label">${esc(t(label))}</span><span class="seg-n">${counts[v]}</span>`]), S.filter)}</div>` : "";
  let body = "";
  if (!items.length) {
    body = emptyListHtml();
  } else {
    let group = null;
    for (const x of items) {
      const g = x.new ? t("New from the latest search") : dayGroup(x.evaluated);
      if (g !== group) { body += `<div class="day${x.new ? " is-new" : ""}">${esc(g)}</div>`; group = g; }
      body += jobRow(x);
    }
  }
  const y = list.scrollTop;
  list.classList.toggle("has-tools", Boolean(tools));
  list.innerHTML = `<h2 class="large-title">${esc(t(VIEWS[S.view].title))}</h2>${tools}${all.length ? searchCardHtml() : ""}${body}`;
  if (quiet) list.scrollTop = y;
}

/* No jobs at all yet: say plainly what a search will do, and offer it. While it runs, its steps. */
function welcomeHtml() {
  const sum = C().summary, run = S.runs[S.key];
  const name = `<bdi>${esc(first())}</bdi>`;
  const head = "";
  if (run?.status === "running" || sum?.active?.external) {
    const order = run?.stages?.map(([k]) => k) || Object.keys(STEP_SHORT);
    const at = Math.max(0, order.indexOf(run?.stage));
    return `<div class="welcome running">${head}<h2>${t("Finding jobs for {name}", { name })}</h2>
      <ol class="stepper">${order.map((k, i) => `<li class="${i < at ? "done" : i === at ? "now" : ""}"><i>${icon("check", 11, "", 3)}</i>
        <span>${esc(t(STEP_SHORT[k] || k))}</span></li>`).join("")}</ol>
      <p class="run-detail" aria-live="polite">${esc(runDetail(run))}</p>
      ${run ? `<p class="run-time">${esc(fmtElapsed(run.elapsed))}</p>` : ""}</div>`;
  }
  if (sum && !sum.can_run) {
    const where = sum.blocked === "settings" ? "settings" : "profile";
    return `<div class="welcome">${head}<h2>${t("Find jobs for {name}", { name })}</h2>
      <p>${esc(t(where === "profile" ? "Add the job titles to search in the profile, then search."
        : "Finish Settings, then search."))}</p>
      <div class="actions"><a class="btn primary large" href="#/${where}">${esc(t(where === "profile" ? "Open Profile" : "Open Settings"))}</a></div></div>`;
  }
  return `<div class="welcome">${head}<h2>${t(S.demo ? "Try a demo search for {name}" : "Find jobs for {name}", { name })}</h2>
    <p>${esc(S.demo ? t("Sample jobs and simulated scoring.") : planLine(sum?.plan))}</p>
    <div class="actions"><button class="btn primary large" data-action="run">${icon("search", 14, "", 2.3)} ${esc(t("Find New Jobs"))}</button></div></div>`;
}

function emptyListHtml() {
  if (S.query) return `<div class="empty">${icon("search", 38, "", 1.4)}<h2>${esc(t("No Results"))}</h2><p>${esc(t("Nothing matches “{q}”.", { q: S.query }))}</p></div>`;
  const all = C().jobs || [], runs = C().summary?.runs || [];
  const name = `<bdi>${esc(first())}</bdi>`;
  if (!all.length) return welcomeHtml();
  if (all.length && S.filter === "matches") {
    return `<div class="empty">${icon("tray", 40, "", 1.3)}<h2>${esc(t("No Strong Matches Yet"))}</h2>
      <p>${esc(t("{jobs} scored so far, none at {good} or above.", { jobs: count(all.length, "job"), good: C().summary.thresholds.good }))}</p>
      <button class="btn large" data-filter-to="all">${esc(t("Show All Jobs"))}</button></div>`;
  }
  if (all.length && S.filter === "remote") {
    return `<div class="empty">${icon("globe", 40, "", 1.3)}<h2>${esc(t("No Remote Matches Yet"))}</h2>
      <p>${esc(t("Remote jobs that fit are listed here. They’re searched when the profile includes remote work."))}</p>
      <button class="btn large" data-filter-to="all">${esc(t("Show All Jobs"))}</button></div>`;
  }
  if (all.length && S.filter === "applied") {
    return `<div class="empty">${icon("checkCircle", 40, "", 1.3)}<h2>${esc(t("Nothing Applied Yet"))}</h2>
      <p>${esc(t("After you apply for a job, press Mark as Applied on it. It will be listed here, so you never apply twice."))}</p></div>`;
  }
  return welcomeHtml();
}

/* Text from the posting (titles, companies) keeps its own direction inside the Arabic layout. */
const bd = (s) => `<bdi>${esc(s)}</bdi>`;

function jobRow(j) {
  const sel = S.sel[S.view] === j.url ? " selected" : "";
  const city = (j.location || "").split(/[,·]/)[0].trim();
  const mark = j.applied ? `<span class="applied-mark" title="${esc(t("Applied"))}">${icon("check", 11, "", 2.6)}</span>` : "";
  const how = j.source !== "demo" && (isEasy(j) || j.apply === "closed")
    ? `<span class="${j.apply === "closed" ? "closed" : "easy"}">${esc(t(APPLY[j.apply].name))}</span>` : "";
  const meta = [how, ...[j.remote ? t("Remote") : "", siteName(j.source), postedLabel(j.posted), j.applied ? t("Applied") : ""]
    .filter(Boolean).map(esc)]
    .filter(Boolean).join(" · ");
  return `<button class="row${sel}${j.applied ? " is-applied" : ""}" data-id="${esc(j.url)}">
    ${mark}${logo(j)}
    <span class="row-text"><span class="row-title" dir="auto">${esc(j.title)}</span><span class="row-sub" dir="auto">${[j.company, city].filter(Boolean).map(bd).join(" · ")}</span>
      <span class="row-meta">${j.new ? `<span class="new-pill">${esc(t("New"))}</span>` : ""}${meta}</span></span>
    <span class="score"><b class="v-${esc(j.verdict)}">${esc(j.fit)}</b><small>${esc(t(VERDICT[j.verdict] || ""))}</small></span>
    <span class="row-x" role="button" data-delete-job="${esc(j.url)}" title="${esc(t("Delete Job"))}" aria-label="${esc(t("Delete Job"))}">${icon("trash", 14, "", 1.8)}</span></button>`;
}

/* One line about a search, for the activity popover. */
function runLine(r) {
  if (r.outcome === "saved" || r.outcome === "sent") return t("{matches} found", { matches: count(r.matches, "match") });
  if (r.outcome === "nothing_to_send") return t("Nothing new this time");
  if (r.outcome === "previewed") return t("Preview");
  return r.evaluated ? t("{jobs} scored", { jobs: count(r.evaluated, "job") }) : t("Stopped before scoring");
}

/* ============================================================= detail */
function paintDetail(animate) {
  const pane = $("#detail");
  const id = S.sel[S.view];
  const item = itemsFor().find((x) => idOf(x) === id);
  pane.classList.toggle("open", narrow.matches && S.detailOpen && Boolean(item));
  $("#window").classList.toggle("detail-open", narrow.matches && S.detailOpen && Boolean(item));
  if (!item) {
    pane.innerHTML = `<div class="placeholder">${icon("briefcase", 40, "", 1.2)}<span>${esc(t("Select a Job"))}</span></div>`;
    return;
  }
  pane.innerHTML = jobDetail(item);
  if (!animate) $(".detail", pane)?.classList.remove("fade");
  pane.scrollTop = 0;
  const pending = $("[data-fetch-description]", pane);
  if (pending) loadDescription(pending.dataset.fetchDescription);
  if (!item.apply && /linkedin\.com\/jobs\/view\//.test(item.url)) loadApplyType(item.url);
  if (S.company[applyKey(item.url)] === undefined && $("#company-line", pane)) loadCompany(item.url);
  const frame = $("iframe", pane);
  if (frame) frame.addEventListener("load", () => fitFrame(frame));
}

function fitFrame(frame) {
  try {
    const doc = frame.contentDocument;
    frame.style.height = `${doc.documentElement.scrollHeight}px`;
  } catch { /* cross-origin fallback keeps the default height */ }
}

const section = (title, html) => `<section class="d-section"><h3>${esc(t(title))}</h3>${html}</section>`;
/* ChatGPT writes these in Arabic (right to left); free mode quotes the English posting (left to right). */
const prose = (text) => (/[؀-ۿ]/.test(text)
  ? `<p class="ar" dir="rtl" lang="ar">${esc(text)}</p>` : `<p class="en" dir="ltr" lang="en">${esc(text)}</p>`);

const VERDICT_LINE = {
  strong: "Apply first.",
  good: "Worth a careful look.",
  moderate: "Partly fits. Read it before applying.",
  weak: "Not a fit for this profile.",
};
const LEVEL_NAME = { executive: "Executive", director: "Director", "mid-senior": "Senior", early: "Entry or specialist level", junior: "Junior" };

/* Why this job fits, in two plain lines built from how the free scoring judged it. */
function whyHtml(j) {
  const b = j.breakdown;
  if (!b) return j.reasoning ? section("Why It Fits", prose(j.reasoning)) : "";
  if (b.nationality) return section("Why It Fits", `<p>${esc(t("Open only to a specific nationality, so it scores 0."))}</p>`);
  // Names from the posting keep their own direction inside an Arabic sentence (<bdi>); our own sentences are trusted text.
  const level = esc(t(LEVEL_NAME[b.level.level] || b.level.level || ""));
  const terms = `<bdi>${esc((b.field.terms || []).slice(0, 4).join(", "))}</bdi>`;
  const said = [
    { match: t("The title matches “{terms}”.", { terms: `<bdi>${esc((b.title.terms || [])[0] || "")}</bdi>` }),
      partial: t("The title is close to the profile’s job titles."),
      none: t("The title isn’t one of the profile’s job titles.") }[b.title.state],
    { match: t("{level} is a level the profile targets.", { level }),
      near: t("{level} is one step from the profile’s levels.", { level }),
      unclear: "",
      junior: t("The level is junior for this profile.") }[b.level.state],
    { match: t("The posting asks for {terms}.", { terms }),
      few: t("The posting asks for {terms}.", { terms }),
      none: t("The posting doesn’t mention the profile’s skills."),
      no_description: t("The site didn’t share the description, so only the title was judged.") }[b.field.state],
    b.stack?.length ? t("It’s a {tech} job, which isn’t in the profile’s skills, so it scores lower.",
      { tech: `<bdi>${esc(b.stack.join(", "))}</bdi>` }) : "",
    b.years ? t("It asks for {asked}+ years of experience; the profile has {has}.", { asked: esc(b.years.asked), has: esc(b.years.has) }) : "",
  ].filter(Boolean);
  return section("Why It Fits", `<p>${said.join(" ")}</p>`);
}

/* The posting, read into headings, paragraphs and list items. Lines a site broke mid-sentence
   ("We are seeking an experienced" / "Card Product Manager" / "to lead…") are joined back up. */
const BULLET_ONLY = /^[-•*·●▪]$/, BULLET = /^[-•*·●▪]\s+(.+)$/;
const JOINS_NEXT = /\b(?:a|an|the|of|to|for|and|or|with|in|on|as|by|our|your|experienced|seasoned|skilled|talented|motivated|dynamic|highly|strong|qualified|passionate|exceptional)$/i;
function isHeading(s) {
  if (s.length > 70) return false;
  if (/:$/.test(s) || (s === s.toUpperCase() && /[A-Z]/.test(s))) return true;
  const words = s.split(/\s+/);
  return s.length <= 48 && words.length <= 6 && !/[.!?,;:)]$/.test(s) && /^[A-Z0-9&(]/.test(words[words.length - 1]);
}
function postingItems(text) {
  const items = [];
  let bullet = false;
  for (const raw of String(text || "").split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    if (BULLET_ONLY.test(line)) { bullet = true; continue; }        // "-" on its own line, the item on the next
    const m = line.match(BULLET);
    const li = Boolean(m) || bullet;
    const body = m ? m[1] : line;
    bullet = false;
    const prev = items[items.length - 1];
    if (prev && !li && (/^[a-z]/.test(body) || (JOINS_NEXT.test(prev.text) && !/[.!?:;]$/.test(prev.text)))) {
      prev.text += ` ${body}`;
      continue;
    }
    items.push({ li, text: body });
  }
  return items.map((x) => ({ ...x, h: !x.li && isHeading(x.text) }));
}
function formatPosting(text) {
  const out = [];
  let list = [];
  const flush = () => { if (list.length) { out.push(`<ul>${list.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`); list = []; } };
  for (const x of postingItems(text)) {
    if (x.li) { list.push(x.text); continue; }
    flush();
    out.push(x.h ? `<h4>${esc(x.text.replace(/:$/, ""))}</h4>` : `<p>${esc(x.text)}</p>`);
  }
  flush();
  return out.join("");
}

/* What the job is, in two or three lines: the part of the posting about the role itself
   (not the company's own introduction), cut at the end of a sentence. */
const COMPANY_HEAD = /who we are|our story|company (?:overview|profile|description)|^about (?!the (?:role|job|position|opportunity))/i;
const ROLE_HEAD = /role|position|job|opportunity|purpose|summary|overview|what you|mission|responsibilit|accountabilit|description/i;
const COMPANY_TALK = /\b(?:is a (?:leading|global|new-age|premier)|founded in|headquartered|we are a |our mission is)/i;
function roleSummary(text) {
  const blocks = [];
  let cur = { head: "", paras: [], bullets: [] };
  for (const x of postingItems(text)) {
    if (x.h) { blocks.push(cur); cur = { head: x.text.replace(/:$/, ""), paras: [], bullets: [] }; }
    else if (x.li) cur.bullets.push(x.text);
    else cur.paras.push(x.text);
  }
  blocks.push(cur);
  const own = blocks.filter((b) => !COMPANY_HEAD.test(b.head));
  const roleBlock = own.find((b) => ROLE_HEAD.test(b.head) && b.paras.some((p) => p.length >= 40));
  const para = roleBlock?.paras.find((p) => p.length >= 40)
    || own.flatMap((b) => b.paras).find((p) => p.length >= 60 && !COMPANY_TALK.test(p))
    || own.flatMap((b) => b.paras).find((p) => p.length >= 60);
  const out = para || (own.find((b) => ROLE_HEAD.test(b.head) && b.bullets.length) || own.find((b) => b.bullets.length))?.bullets.slice(0, 3).join("; ") || "";
  if (out.length <= 300) return out;
  const cut = out.slice(0, 300), end = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  return end > 140 ? cut.slice(0, end + 1) : `${cut.slice(0, cut.lastIndexOf(" "))}…`;
}
function aboutHtml(j) {
  const text = j.description || "";
  if (text.length >= 150) {
    const summary = !j.breakdown && j.summary ? j.summary : roleSummary(text);
    return section("About the Role", `${summary ? `<p class="role-summary" dir="auto">${esc(summary)}</p>` : ""}
      <button class="link-more" data-action="posting-more">${esc(t("Read the full posting"))}</button>
      <div class="posting" id="posting" dir="auto" hidden>${formatPosting(text)}</div>`);
  }
  if (!j.breakdown && j.summary) return section("About the Role", prose(j.summary));
  if (j.source === "linkedin" && !S.noDescription?.[j.url]) {
    return section("About the Role", `<p class="d-note posting-loading" data-fetch-description="${esc(j.url)}"><span class="spin"></span>
      ${esc(t("Reading the posting from LinkedIn…"))}</p>`);
  }
  return section("About the Role", `<p class="d-note">${esc(t("{site} didn’t share the description. Open the posting to read it.", { site: siteName(j.source) }))}</p>`);
}
/* An older job saved without its description: read it from LinkedIn now, then show it in place. */
async function loadDescription(url) {
  S.noDescription ||= {};
  let text = "";
  try { text = (await api(`/api/job-description/${enc(S.key)}?url=${enc(url)}`)).description || ""; } catch { /* shown as unavailable */ }
  const job = (C().jobs || []).find((x) => x.url === url);
  if (text.length >= 150 && job) job.description = text;
  else S.noDescription[url] = true;
  const holder = $(`[data-fetch-description="${CSS.escape(url)}"]`);
  if (holder && job) holder.closest(".d-section").outerHTML = aboutHtml(job);
}
const meterRow = (label, value, hint) => `<div class="meter-row" title="${esc(t(hint))}"><span>${esc(t(label))}</span>
  <i class="bar"><i style="width:${Math.max(0, Math.min(100, Number(value) || 0))}%"></i></i><b>${esc(value ?? "–")}</b></div>`;

/* ============================================================ applying */
/* How a job is applied to, as the search (or a later look at LinkedIn) found it. */
const APPLY = {
  easy: { name: "Easy Apply", line: "A few minutes on {site} with your saved profile." },
  email: { name: "Apply by email", line: "The posting asks for CVs by email." },
  site: { name: "Company site", line: "On the employer’s own site, usually a longer form." },
  closed: { name: "Closed", line: "{site} no longer takes applications for this job." },
};
const isEasy = (j) => j.apply === "easy" || j.apply === "email";
const applyKey = (url) => `${S.key}|${url}`;

function applyHowHtml(j) {
  const how = APPLY[j.apply];
  if (!how || j.source === "demo") return `<p class="apply-how" id="apply-how" hidden></p>`;
  const line = t(how.line, { site: bd(siteName(j.source)) });
  return `<p class="apply-how${isEasy(j) ? " is-easy" : ""}" id="apply-how"><b>${esc(t(how.name))}</b> · ${line}</p>`;
}

/* The email addresses in the posting: click one to write to it, or copy it. */
function jobEmailHtml(j) {
  const emails = j.emails || [];
  if (!emails.length || j.source === "demo") return `<div class="job-email" id="job-email" hidden></div>`;
  return `<div class="job-email" id="job-email">${emails.map(emailItem).join("")}</div>`;
}

/* The company's website and its HR / careers / contact addresses, found on the company's own site
   (most postings don't give an address). Looked up when a job is opened, once per company. */
const emailItem = (m) => `<span class="job-email-item">${icon("envelope", 14, "", 1.8)}<a href="mailto:${esc(m)}" title="${esc(t("Write an email"))}" dir="ltr">${esc(m)}</a>
  <button class="btn link-quiet" data-copy="${esc(m)}">${esc(t("Copy"))}</button></span>`;
function companyHtml(j) {
  if (j.source === "demo") return "";
  const info = S.company[applyKey(j.url)];
  if (!info) {
    return `<div class="job-email company-line" id="company-line" data-company="${esc(j.url)}"><span class="job-email-item muted">
      <span class="spin"></span>${esc(t("Looking for the company’s email…"))}</span></div>`;
  }
  const emails = (info.emails || []).filter((m) => !(j.emails || []).includes(m));
  if (!info.site && !emails.length) return `<div class="job-email company-line" id="company-line" data-company="${esc(j.url)}" hidden></div>`;
  const host = (info.site || "").replace(/^https?:\/\/(www\.)?/, "").replace(/\/.*$/, "");
  return `<div class="job-email company-line" id="company-line" data-company="${esc(j.url)}">
    ${info.site ? `<span class="job-email-item">${icon("globe", 14, "", 1.8)}<a href="${esc(safeUrl(info.site))}" target="_blank" rel="noopener" dir="ltr"
      title="${esc(t("The company’s website"))}">${esc(host)}</a></span>` : ""}
    ${emails.map(emailItem).join("")}
    ${info.site && !emails.length ? `<span class="job-email-item muted">${esc(t("No email on the company’s website"))}</span>` : ""}</div>`;
}
async function loadCompany(url) {
  const id = applyKey(url);
  if (S.company[id]) return;
  S.company[id] = null;
  let info = { site: "", emails: [] };
  try { info = await api(`/api/company-contact/${enc(S.key)}?url=${enc(url)}`); } catch { /* nothing to show */ }
  S.company[id] = info;
  const job = (C().jobs || []).find((x) => x.url === url), holder = $(`#company-line[data-company="${CSS.escape(url)}"]`);
  if (job && holder) holder.outerHTML = companyHtml(job);
}

/* The main button: apply the way this job is applied to. Opening the posting is its own button. */
function applyBtnHtml(j) {
  const site = bd(siteName(j.source));
  if (j.source === "demo") {
    return `<button class="btn primary" id="apply-btn" disabled title="${esc(t("Demo Mode uses sample jobs, so there is no real posting"))}">${esc(t("Sample Posting"))}</button>`;
  }
  if (j.apply === "closed") return `<span id="apply-btn" hidden></span>`;
  if (j.apply === "email" && j.emails?.length) {
    return `<a class="btn primary" id="apply-btn" data-action="apply" data-url="${esc(j.url)}" href="mailto:${esc(j.emails[0])}">${icon("envelope", 14, "", 1.9)} ${esc(t("Apply by Email"))}</a>`;
  }
  const label = j.apply === "easy" ? t("Easy Apply on {site}", { site }) : t("Apply on {site}", { site });
  return `<a class="btn primary" id="apply-btn" data-action="apply" data-url="${esc(j.url)}" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener">${label}</a>`;
}

/* One CV button; the format is chosen from a small menu under it. */
function openCvMenu(anchor) {
  const open = $(".menu.cv-menu");
  closeFloating();
  if (open) return;
  const href = anchor.dataset.cv;
  const menu = document.createElement("div");
  menu.className = "menu cv-menu";
  menu.setAttribute("role", "menu");
  menu.innerHTML = [["pdf", "PDF", "Best for applying online"], ["docx", "Word", "To edit before sending"]].map(([f, name, sub]) =>
    `<a role="menuitem" href="${esc(f === "pdf" ? `${href}&format=pdf` : href)}" download data-cv-format>
      <span class="file-tag">${f === "pdf" ? "PDF" : "DOC"}</span>
      <span class="account-text"><span class="account-name">${esc(t(name))}</span><span class="account-sub">${esc(t(sub))}</span></span></a>`).join("");
  document.body.append(menu);
  placeBelow(menu, anchor, "start");
}

/* An older LinkedIn job saved before the app noted how it's applied to: ask now, once. */
async function loadApplyType(url) {
  S.applyAsked ||= {};
  if (S.applyAsked[applyKey(url)]) return;
  S.applyAsked[applyKey(url)] = true;
  try {
    const r = await api(`/api/apply-type/${enc(S.key)}?url=${enc(url)}`);
    const job = (C().jobs || []).find((x) => x.url === url);
    if (job && r.apply) setApply(job, r.apply, r.emails);
  } catch { /* stays unknown */ }
}

/* A job's apply type changed: update its row and, if it's open, the line and the button in place. */
function setApply(job, kind, emails) {
  job.apply = kind;
  if (emails) job.emails = emails;
  if (S.view === "jobs") paintList(true);
  if (S.sel[S.view] !== job.url) return;
  for (const [id, html] of [["#apply-how", applyHowHtml], ["#apply-btn", applyBtnHtml], ["#job-email", jobEmailHtml]]) {
    const el = $(id);
    if (el) el.outerHTML = html(job);
  }
}

/* Apply: the posting opens (or an email to the address in it), and the CV for this job downloads as
   a PDF, ready to attach. Coming back to the app afterwards asks whether to mark the job as applied. */
function startApply(btn) {
  const job = (C().jobs || []).find((x) => x.url === btn.dataset.url);
  if (!job) return;
  if (job.cv_url) {
    const a = Object.assign(document.createElement("a"), { href: `${job.cv_url}&format=pdf`, download: "" });
    document.body.append(a);
    a.click();
    a.remove();
  }
  S.applying = { key: S.key, url: job.url, at: Date.now() };
}

function askApplied() {
  const a = S.applying;
  if (!a || Date.now() - a.at < 4000) return;
  S.applying = null;
  const job = a.key === S.key && (C().jobs || []).find((x) => x.url === a.url);
  if (!job || job.applied) return;
  toast(t("Did you apply to {company}?", { company: job.company || job.title }), t("Mark as Applied"),
    () => { if (!job.applied) toggleApplied(job.url); }, "check", 15000);
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") askApplied(); });
window.addEventListener("focus", askApplied);

/* Copy text, and show it on the thing clicked for a moment rather than with a big notice. */
async function copyText(text, el) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text });
    document.body.append(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove();
    if (!ok) return banner(t("Select the text and copy it by hand."));
  }
  if (!el) return hud("Copied", "check");
  const label = el.textContent;
  el.textContent = t("Copied");
  el.classList.add("copied");
  clearTimeout(el._copied);
  el._copied = setTimeout(() => { el.textContent = label; el.classList.remove("copied"); }, 1400);
}

function jobDetail(j) {
  const cvHref = j.cv_url || "";
  const site = siteName(j.source);
  // The four facts a client looks for, in one quiet strip.
  // "Riyadh, Riyadh, Saudi Arabia" -> "Riyadh, Saudi Arabia"
  const where = [...new Map((j.location || "").split(",").map((s) => s.trim()).filter(Boolean)
    .map((s) => [s.toLowerCase(), s])).values()].join(", ");
  const place = j.remote ? [t("Remote"), where].filter(Boolean).join(" · ") : where;
  const facts = [
    ["Posted", postedShort(j.posted)],
    ["Found", relDateTime(j.evaluated)],
    ["Site", site],
    ["Location", place],
  ].filter(([, v]) => v);
  const appliedLabel = t(j.applied ? "Applied. Click to clear the mark" : "Mark as Applied");
  return `<article class="detail fade">
    <header class="d-hero">${logo(j, "lg")}
      <div class="d-hero-text"><div class="d-kicker">${bd(j.company || "")}${j.new ? ` <span class="new-pill">${esc(t("New"))}</span>` : ""}</div>
        <h2 class="d-title">${bd(j.title)}</h2></div></header>
    <div class="fit v-${esc(j.verdict)}">
      <b class="fit-num">${esc(j.fit)}</b>
      <div class="fit-text"><span class="fit-verdict">${esc(t("{verdict} fit", { verdict: t(VERDICT[j.verdict] || "") }))}</span>
        <span class="fit-line">${esc(t(VERDICT_LINE[j.verdict] || ""))}</span></div>
    </div>
    <div class="d-actions">
      ${applyBtnHtml(j)}
      ${j.source === "demo" ? "" : `<a class="btn" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener">${esc(t("Open Job"))} ${icon("external", 12, "flip", 2.2)}</a>`}
      ${cvHref ? `<button class="btn" data-action="cv-menu" data-cv="${esc(cvHref)}" aria-haspopup="menu">${icon("download", 14, "", 1.9)} ${esc(t("Download CV"))} ${icon("updown", 11, "", 2)}</button>` : ""}
      ${j.source === "demo" ? "" : `<button class="btn" data-action="email-job" data-url="${esc(j.url)}">${icon("envelope", 14, "", 1.8)} ${esc(t("Email Me"))}</button>`}
      <span class="d-icons">
        <button class="icon-btn applied-btn${j.applied ? " on" : ""}" data-applied="${esc(j.url)}" aria-pressed="${Boolean(j.applied)}"
          title="${esc(appliedLabel)}" aria-label="${esc(appliedLabel)}">${j.applied ? icon("checkCircle", 18) : icon("check", 16, "", 2.2)}</button>
        <button class="icon-btn delete" data-delete-job="${esc(j.url)}" title="${esc(t("Delete Job"))}" aria-label="${esc(t("Delete Job"))}">${icon("trash", 16, "", 1.8)}</button>
      </span>
    </div>
    ${applyHowHtml(j)}
    ${jobEmailHtml(j)}
    ${companyHtml(j)}
    <dl class="facts">${facts.map(([k, v]) => `<div><dt>${esc(t(k))}</dt><dd>${bd(v)}</dd></div>`).join("")}</dl>
    ${aboutHtml(j)}
    ${whyHtml(j)}
  </article>`;
}

function select(id, { open = true } = {}) {
  S.sel[S.view] = id;
  $$("#list .row").forEach((row) => row.classList.toggle("selected", row.dataset.id === id));
  if (narrow.matches && open) S.detailOpen = true;
  paintDetail(true);
}

/* ============================================================== pages */
function groupTitle(text, aside = "") {
  return `<div class="group-title">${esc(text)}${aside ? `<span>${aside}</span>` : ""}</div>`;
}

/* ============================================================ settings */
const PERIODS = { 24: "24 hours", 72: "3 days", 168: "7 days" };

function settingsHtml() {
  const s = C().settings;
  const periods = s.search_periods.map((h) => [String(h), esc(t(PERIODS[h] || `${h} h`))]);
  return `<div class="doc settings"><div class="doc-main">
    <header class="doc-head"><h1>${esc(t("Settings"))}</h1></header>
    <section class="psec" id="p-general"><h2>${esc(t("General"))}</h2><div class="group">
      ${row("Appearance", "", appearancePick())}
      ${row("Language", "", langPick())}
      ${row("Look back", "How far back each search reads new postings.", seg("hours", periods, String(s.search_hours), "hours"))}
      ${row("Search every morning", t("From {hour}:00 Cairo time, for everyone here. The 5 best matches are emailed to each person with email set up, quickest to apply first.", { hour: s.daily_hour }),
        seg("daily", [["off", esc(t("Off"))], ["on", esc(t("On"))]], s.daily ? "on" : "off"))}
    </div></section>
    ${mailHtml()}
    ${s.groups.map(setupGroup).join("")}
  </div></div>`;
}

/* Email for the person selected: where their matches go and the free Resend key that sends them.
   Each person's emails go only to their own address. */
let mailLoading = false;
async function loadMail() {
  if (mailLoading) return;
  mailLoading = true;
  const key = S.key;
  try { S.mail = await api(`/api/profile/${enc(key)}/email`); } catch (err) { if (err.message !== "auth") banner(err.message); }
  mailLoading = false;
  const el = $("#p-mail");
  if (el && S.mail?.key === S.key) el.outerHTML = mailHtml();
}
/* One settings row: what it is on the left, its control on the right. */
const row = (title, sub, control) => `<div class="item-wrap"><div class="item"><span class="item-main"><span class="item-title">${esc(t(title))}</span>${
  sub ? `<span class="item-sub">${esc(t(sub))}</span>` : ""}</span><span class="item-control">${control}</span></div></div>`;

/* An editable row (like the key rows below it): the value on the right; click to change it in place. */
function mailRow(field, title, sub, value, ok, form) {
  const open = S.mailOpen === field;
  return `<div class="item-wrap"><button class="item" data-action="mail-edit" data-field="${field}" aria-expanded="${open}">
      <span class="item-main"><span class="item-title">${esc(t(title))}</span><span class="item-sub">${sub}</span></span>
      <span class="item-value"><span>${value}</span>${ok ? icon("checkCircle", 15, "good") : ""}</span>${icon("chevR", 12, "chev flip", 2)}</button>
    ${open ? `<div class="item-edit">${form}</div>` : ""}</div>`;
}

function mailHtml() {
  const m = S.mail;
  if (!m || m.key !== S.key) { setTimeout(loadMail); return `<section class="psec" id="p-mail"><h2>${esc(t("Email"))}</h2></section>`; }
  const ready = Boolean(m.email && m.has_key);
  const save = `<button class="btn" type="button" data-action="mail-cancel">${esc(t("Cancel"))}</button><button class="btn primary" type="submit">${esc(t("Save"))}</button>`;
  return `<section class="psec" id="p-mail"><h2>${esc(t("Email"))}</h2>
    <p class="psec-note">${t("For {name}: after each search, the best matches arrive in one email, each with its CV as PDF and Word.", { name: `<bdi>${esc(m.name)}</bdi>` })}</p>
    <div class="group">
      ${mailRow("email", "Send matches to", esc(t("Only this person’s matches go here.")),
        m.email ? `<bdi>${esc(m.email)}</bdi>` : esc(t("Not added")), Boolean(m.email),
        `<form data-mail-email><input class="field" name="email" type="email" value="${esc(m.email)}" placeholder="you@gmail.com" dir="ltr" autocomplete="email">${save}</form>`)}
      ${mailRow("key", "Resend key", t("Free at {site}: sign up with the address above, then API Keys, Create API Key.",
          { site: `<a href="https://resend.com/signup" target="_blank" rel="noopener">resend.com</a>` }),
        esc(t(m.has_key ? "Saved" : "Not added")), m.has_key,
        `<form data-mail-key><input class="field" name="key" type="password" placeholder="re_…" dir="ltr" autocomplete="off">${save}</form>`)}
      ${row("Test email", ready ? "Sends a short email to check that it arrives." : "Add the address and the key first.",
        `<button class="btn" type="button" data-action="mail-test" ${ready ? "" : "disabled"}>${esc(t("Send Test"))}</button>`)}
    </div>
    <p class="field-error" id="mail-error" dir="auto" hidden></p></section>`;
}

async function saveMail(body, done) {
  const err = $("#mail-error");
  if (err) err.hidden = true;
  try {
    S.mail = await api(`/api/profile/${enc(S.key)}/email`, { method: "POST", body: { email: S.mail.email, key: "", test: false, ...body } });
    const cache = S.cache[S.key];
    if (cache) delete cache.profile;
    S.mailOpen = null;
    $("#p-mail").outerHTML = mailHtml();
    hud(done, "check");
  } catch (e2) {
    if (e2.message === "auth") return;
    $("#p-mail").outerHTML = mailHtml();             // the button is usable again; the reason shows under the rows
    const el = $("#mail-error");
    if (el) { el.textContent = t(e2.message); el.hidden = false; }
  }
}

/* Setup rows arrive in English from the server; in Arabic, use their translation (by row id). */
function setupText(i) {
  const ar = isAr() && window.AR_SETUP.items[i.id];
  if (!ar) return { title: i.title, why: i.why, where: i.where };
  const model = (i.why || "").match(/use (\S+?)\.?$/)?.[1] || "";
  const fill = (s) => s && s.replace("{name}", first()).replace("{model}", model);
  return { title: fill(ar.title) || i.title, why: fill(ar.why) || i.why, where: ar.where || i.where };
}

function setupGroup(g) {
  if (!g.items.length) return "";
  const title = isAr() && window.AR_SETUP.groups[g.id] ? window.AR_SETUP.groups[g.id].replace("{name}", first()) : g.title;
  return `<section class="psec" id="p-${esc(g.id)}"><h2>${esc(title)}</h2>
    <div class="group">${g.items.map(setupItem).join("")}</div></section>`;
}

function setupItem(i) {
  const [glyph, color] = TILES[i.id] || ["checklist", "gray"];
  const tx = setupText(i);
  const sub = i.problem ? `<span class="item-sub problem" dir="auto">${esc(i.problem)}</span>` : `<span class="item-sub">${esc(tx.why)}</span>`;
  const main = `<span class="item-main"><span class="item-title">${esc(tx.title)}</span>${sub}</span>`;
  if (i.kind === "toggle") {
    // A real setting (System Settings style switch), unlike the checklist's done-marks.
    return `<div class="item-wrap"><label class="item">${tile(glyph, color)}${main}
      <span class="switch"><input type="checkbox" data-setting="${esc(i.env)}" data-on="${esc(i.on_value)}" data-off="${esc(i.off_value)}"
        ${i.on ? "checked" : ""} aria-label="${esc(tx.title)}"><i></i></span></label></div>`;
  }
  if (i.kind === "env") {
    const open = S.expanded === i.env;
    const shown = i.display === "Saved" ? t("Saved") : i.display;
    const value = i.problem ? `<span class="bad">${esc(t("Not accepted"))}</span>${icon("warn", 15, "bad")}`
      : i.ok ? `<span><bdi>${esc(shown)}</bdi></span>${icon("checkCircle", 15, "good")}` : `<span>${esc(t(i.optional ? "None" : "Not added"))}</span>`;
    return `<div class="item-wrap"><button class="item" data-action="edit-env" data-env="${esc(i.env)}" aria-expanded="${open}">
        ${tile(glyph, color)}${main}<span class="item-value">${value}</span>${icon("chevR", 12, "chev flip", 2)}</button>
      ${open ? `<div class="item-edit">${tx.where ? `<p>${t("Find it in {where}.", { where: `<bdi>${esc(tx.where)}</bdi>` })}</p>` : ""}<p class="field-error" id="err-${esc(i.env)}" dir="auto" hidden></p>
        <form data-env-form="${esc(i.env)}"><input class="field" name="value" dir="ltr" type="${i.secret ? "password" : "text"}" autocomplete="off" spellcheck="false"
          placeholder="${esc(i.secret ? t("Paste the key") : i.env.startsWith("EMAIL_CC") ? "one@company.com, two@company.com" : "name@company.com")}">
          <button class="btn" type="button" data-action="cancel-env">${esc(t("Cancel"))}</button><button class="btn primary" type="submit">${esc(t("Save"))}</button></form></div>` : ""}
    </div>`;
  }
  // A to-do, not a setting: a round checkmark like Reminders, not an on/off switch.
  return `<div class="item-wrap"><label class="item">${tile(glyph, color)}${main}
    <span class="done-mark"><input type="checkbox" data-check="${esc(i.id)}" data-scope="${esc(i.scope)}" ${i.ok ? "checked" : ""} aria-label="${esc(t("Done: {title}", { title: tx.title }))}">
      <i>${icon("check", 12, "", 2.8)}</i></span></label></div>`;
}

/* ============================================================= profile */
/* The profile is edited in place, like a contact card: every change is saved a moment later. */
const LEVEL_LABEL = { entry: "Entry level", associate: "Associate", "mid-senior": "Mid–Senior", director: "Director", executive: "Executive" };
const FOUND_LABEL = {
  name: "Name", headline: "Headline", email: "Email", phone: "Phone", linkedin: "LinkedIn", city: "City", titles: "Job titles",
  nationality: "Nationality", keywords: "Your field", exclude: "Skip titles with", exclude_companies: "Skip companies",
  preferences: "Work Preferences",
  summary: "Summary", achievements: "Key Achievements", experience: "Experience", skills: "Skills", education: "Education",
  certifications: "Certifications", languages: "Languages", training: "Training", awards: "Awards",
};
const MODE_LABEL = { "on-site": "On-site", hybrid: "Hybrid", remote: "Remote" };
const TYPE_LABEL = { "full-time": "Full-time", "part-time": "Part-time", contract: "Contract" };

function formFor() {
  const v = C().profile;
  if (S.formView !== v) { S.form = structuredClone(v.profile); S.formView = v; }
  return S.form;
}
const getPath = (obj, path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
function setPath(obj, path, value) {
  const keys = path.split(".");
  const last = keys.pop();
  keys.reduce((o, k) => o[k], obj)[last] = value;
}
const asLines = (text) => text.split("\n").map((s) => s.trim()).filter(Boolean);
const asParas = (text) => text.split(/\n\s*\n/).map((s) => s.replace(/\s*\n\s*/g, " ").trim()).filter(Boolean);
function fieldValue(el) {
  const kind = el.dataset.kind;
  return kind === "lines" ? asLines(el.value) : kind === "paras" ? asParas(el.value) : el.value;
}

/* The profile reads like a document: a section list on the left, and on the right each section's
   properties - a label, and the value itself, edited in place (no boxes until you point at it). */
const prop = (label, control, { top = false, need = "", help = "", raw = false } = {}) =>
  `<div class="prop${top ? " top" : ""}"><div class="prop-k">${raw ? label : esc(t(label))}${need}${help ? `<small>${esc(t(help))}</small>` : ""}</div>
    <div class="prop-v">${control}</div></div>`;
const edit = (path, value, { type = "text", placeholder = "", dir = "auto", cls = "" } = {}) =>
  `<input class="ed${cls ? ` ${cls}` : ""}" data-f="${path}" type="${type}" value="${esc(value)}" placeholder="${esc(t(placeholder))}" dir="${dir}" spellcheck="false" autocomplete="off">`;
const area = (path, value, placeholder, kind = "lines", rows = 3) =>
  `<textarea class="ed area" data-f="${path}" data-kind="${kind}" rows="${rows}" dir="auto" placeholder="${esc(t(placeholder))}">${
    esc(kind === "paras" ? value.join("\n\n") : kind === "lines" ? value.join("\n") : value)}</textarea>`;
const tokenEditor = (path, values, placeholder) =>
  `<div class="tokens edit" data-tokens="${path}">${values.map((v, i) => `<span class="token" dir="auto">${esc(v)}<button type="button" class="token-x"
    data-token-remove="${path}" data-i="${i}" aria-label="${esc(t("Remove {x}", { x: v }))}">${icon("close", 8, "", 2.4)}</button></span>`).join("")}
    <input class="token-input" data-token-add="${path}" dir="auto" placeholder="${esc(t(placeholder))}" enterkeyhint="done" autocomplete="off"></div>`;
// optional: every chip can be turned off (a preference); otherwise one always stays chosen.
const chips = (path, options, selected, optional = false) => `<div class="chips"${optional ? " data-optional" : ""}>${options.map(([v, label]) =>
  `<button type="button" class="chip" data-chip="${path}" data-value="${esc(v)}" aria-pressed="${selected.includes(v)}">${esc(label)}</button>`).join("")}</div>`;
const needTag = (key, missing) => `<span class="need" data-need="${key}"${missing.includes(key) ? "" : " hidden"}>${esc(t("Needed"))}</span>`;
const psec = (id, title, body, note = "") => `<section class="psec" id="p-${id}"><h2>${esc(title)}</h2>${note ? `<p class="psec-note">${note}</p>` : ""}${body}</section>`;

function expEntry(e, i) {
  const p = `cv.experience.${i}`;
  return `<div class="entry">
    ${edit(`${p}.role_title`, e.role_title, { placeholder: "Job title", cls: "entry-title" })}
    <div class="entry-meta">${edit(`${p}.company`, e.company, { placeholder: "Company" })}<span class="d-dot">·</span>${edit(`${p}.period`, e.period, { placeholder: "e.g. Jan 2020 – Present" })}</div>
    ${edit(`${p}.role_description`, e.role_description, { placeholder: "One line about the role (optional)", cls: "entry-desc" })}
    ${area(`${p}.bullets`, e.bullets, "What you did and achieved, one point per line", "lines", Math.max(2, Math.min(7, e.bullets.length + 1)))}
    <button type="button" class="icon-btn entry-x" data-remove="cv.experience" data-i="${i}" title="${esc(t("Remove this role"))}" aria-label="${esc(t("Remove this role"))}">${icon("trash", 14, "", 1.7)}</button>
  </div>`;
}

function eduEntry(e, i) {
  const p = `cv.education.${i}`;
  return `<div class="entry">
    ${edit(`${p}.credential`, e.credential, { placeholder: "Degree or qualification", cls: "entry-title" })}
    <div class="entry-meta">${edit(`${p}.institution`, e.institution, { placeholder: "University or school" })}<span class="d-dot">·</span>${edit(`${p}.detail`, e.detail, { placeholder: "Year" })}</div>
    <button type="button" class="icon-btn entry-x" data-remove="cv.education" data-i="${i}" title="${esc(t("Remove"))}" aria-label="${esc(t("Remove"))}">${icon("trash", 14, "", 1.7)}</button>
  </div>`;
}

/* The page head (repainted after each save): the name, one line under it, and the two CV actions. */
function profileHead(v, f) {
  const name = f.name || cand()?.name || "";
  const place = [f.city, t(f.search.country)].filter(Boolean).join(isAr() ? "، " : ", ");
  const line = [f.headline ? `<bdi>${esc(f.headline)}</bdi>` : "", place ? esc(place) : ""].filter(Boolean).join(` <span class="d-dot">·</span> `);
  const status = v.missing.length
    ? `<p class="doc-status warn" id="profile-status"><i></i>${esc(t("Add {list} to start searching", {
      list: v.missing.map((m) => t({ name: "a name", titles: "job titles", cv: "CV details" }[m])).join(isAr() ? " و" : " and ") }))}</p>`
    : `<p class="doc-status ok" id="profile-status"><i></i>${esc(t("Ready to search"))}</p>`;
  return `<header class="doc-head profile-head">
      <div class="doc-head-row">
        <div class="doc-head-text"><h1 dir="auto">${esc(name)}</h1>
          <p class="doc-sub">${line || `<span class="muted">${esc(t("Add a headline"))}</span>`}</p>${status}</div>
        <div class="doc-actions">
          <label class="btn" title="${esc(t("A PDF or Word file: a CV, or a CV with its discovery record"))}">${icon("upload", 14, "", 1.9)}<span>${esc(t("Upload PDF"))}</span><input type="file" data-import accept=".pdf,.docx,.txt" hidden></label>
          <a class="btn" href="/api/profile/${enc(v.key)}/cv" download>${icon("download", 14, "", 1.9)}<span>${esc(t("Preview CV"))}</span></a>
          <button type="button" class="btn danger" data-action="clear-jobs">${icon("trash", 14, "", 1.8)}<span>${esc(t("Clear Jobs"))}</span></button>
        </div>
      </div>
      <div class="save-state" id="save-state" aria-live="polite"></div>
    </header>`;
}

function importNotice() {
  if (S.imported?.key !== S.key || !S.imported.found.length) return "";
  const parts = S.imported.found.map((k) => t(FOUND_LABEL[k] || k)).join(isAr() ? "، " : ", ");
  const from = { questionnaire: "Filled in from the questionnaire", record: "Filled in from the discovery record",
    "cv+record": "Filled in from the CV and the discovery record" }[S.imported.source] || "Filled in from the CV";
  return `<div class="notice"><div class="notice-text"><b>${esc(t(from))}</b>
      <p>${esc(parts)}</p></div>
    <button class="icon-btn" data-action="dismiss-import" aria-label="${esc(t("Dismiss"))}">${icon("close", 12, "", 2)}</button></div>`;
}

/* Each section can be repainted on its own, so adding a title or a role never redraws the page. */
const PROFILE_SECTIONS = {
  personal: (v, f) => psec("personal", t("Personal Details"), `<div class="props">
      ${prop("Full name", edit("name", f.name, { placeholder: "First and last name" }), { need: needTag("name", v.missing) })}
      ${prop("Headline", edit("headline", f.headline, { placeholder: "e.g. Senior Financial Analyst" }))}
      ${prop("Email", edit("email", f.email, { type: "email", dir: "ltr", placeholder: "name@example.com" }))}
      ${prop("Phone", edit("phone", f.phone, { type: "tel", dir: "ltr", placeholder: "+966 5x xxx xxxx" }))}
      ${prop("City", edit("city", f.city, { placeholder: "e.g. Riyadh" }))}
      ${prop("Nationality", edit("nationality", f.nationality, { placeholder: "e.g. Saudi" }), { help: "Jobs open only to other nationalities are skipped." })}
      ${prop("LinkedIn", edit("linkedin", f.linkedin, { dir: "ltr", placeholder: "linkedin.com/in/…" }))}
      ${prop("Website", edit("website", f.website || "", { dir: "ltr", placeholder: "yourname.dev" }), { help: "Portfolio or personal site, on the CV." })}
    </div>`),
  search: (v, f) => {
    const s = f.search, opt = v.options;
    return psec("search", t("Job Search"), `<div class="props">
      ${prop("Job titles", tokenEditor("search.titles", s.titles, "Add a job title, then press Enter"), { top: true, need: needTag("titles", v.missing) })}
      ${prop("Country", `<select class="ed" data-f="search.country">${opt.countries.map((c) =>
        `<option value="${esc(c)}" ${c === s.country ? "selected" : ""}>${esc(t(c))}</option>`).join("")}</select>`)}
      ${prop("Seniority", chips("search.levels", opt.levels.map((l) => [l, t(LEVEL_LABEL[l] || l)]), s.levels))}
      ${prop("Job sites", chips("search.sites", opt.sites.map((x) => [x.key, x.label]), s.sites))}
      ${prop("Your field", tokenEditor("search.keywords", s.keywords, "Add an industry, speciality or tool"),
        { top: true, help: "Jobs whose posting mentions these score higher." })}
      ${prop("Skip titles with", tokenEditor("search.exclude", s.exclude, "Add a word, e.g. Sales"), { top: true })}
      ${prop("Skip companies", tokenEditor("search.exclude_companies", s.exclude_companies, "Add a company"), { top: true })}
    </div>`);
  },
  prefs: (v, f) => {
    const p = f.preferences, opt = v.options;
    return psec("prefs", t("Work Preferences"), `<div class="props">
      ${prop("Years of experience", edit("preferences.years", p.years, { placeholder: "e.g. 9" }))}
      ${prop("Work arrangement", chips("preferences.work_modes", opt.work_modes.map((m) => [m, t(MODE_LABEL[m] || m)]), p.work_modes, true))}
      ${prop("Job type", chips("preferences.job_types", opt.job_types.map((x) => [x, t(TYPE_LABEL[x] || x)]), p.job_types, true))}
      ${prop("Relocation", area("preferences.relocate", p.relocate, "e.g. Jeddah or Dubai", "text", 1))}
      ${prop("Notice period", edit("preferences.notice", p.notice, { placeholder: "e.g. One month" }))}
      ${prop("Expected salary", edit("preferences.salary", p.salary, { placeholder: "e.g. 30,000 SAR a month" }))}
      ${prop("Residency or visa", edit("preferences.visa", p.visa, { placeholder: "e.g. Transferable iqama" }))}
      ${prop("Anything else", area("preferences.other", p.other, "Must-haves, deal-breakers, companies they’d love to join", "text", 2), { top: true })}
    </div>`, esc(t("For applying by hand, and for ChatGPT when it’s on. Never written into a CV.")));
  },
  summary: (v, f) => psec("summary", t("Summary"), area("cv.summary", f.cv.summary,
    "Two or three sentences on experience and strengths. A blank line starts a new paragraph.", "paras", 4)),
  achievements: (v, f) => psec("achievements", t("Key Achievements"),
    area("cv.achievements", f.cv.achievements, "One achievement per line", "lines", Math.max(3, Math.min(9, f.cv.achievements.length + 1)))),
  experience: (v, f) => psec("experience", t("Experience"), `<div class="entries">${f.cv.experience.map(expEntry).join("")}</div>
    <button type="button" class="btn quiet add" data-add="cv.experience">${icon("plus", 13, "", 2.2)}<span>${esc(t("Add Role"))}</span></button>`),
  skills: (v, f) => psec("skills", t("Skills"), tokenEditor("cv.skills", f.cv.skills, "Add a skill")),
  education: (v, f) => psec("education", t("Education"), `<div class="entries">${f.cv.education.map(eduEntry).join("")}</div>
    <button type="button" class="btn quiet add" data-add="cv.education">${icon("plus", 13, "", 2.2)}<span>${esc(t("Add Education"))}</span></button>`),
  more: (v, f) => psec("more", t("More for the CV"), `<div class="props">${[["certifications", "Certifications"], ["languages", "Languages"],
    ["training", "Training"], ["awards", "Awards"]].map(([k, label]) =>
      prop(label, area(`cv.${k}`, f.cv[k], "One per line", "lines", Math.max(1, Math.min(8, f.cv[k].length || 1))), { top: true })).join("")}</div>`),
  notes: (v, f) => psec("notes", t("Notes for ChatGPT"), area("notes", f.notes, "e.g. Egyptian, living in Riyadh. Won’t relocate. Available in one month.", "text", 2)),
};
const profileSection = (id, v, f) => PROFILE_SECTIONS[id](v, f);
const SECTION_OF = (path) => (path.startsWith("search.") ? "search" : path.startsWith("preferences.") ? "prefs"
  : { "cv.skills": "skills", "cv.experience": "experience", "cv.education": "education" }[path]);

function profileHtml() {
  const v = C().profile, f = formFor();
  const groupTitleOf = (g) => (isAr() && window.AR_SETUP.groups[g.id] ? window.AR_SETUP.groups[g.id].replace("{name}", first()) : g.title);
  // Only what the client uses. Notes are read by ChatGPT alone, so they show only when it is on.
  const ai = Boolean(v.chatgpt);
  const toc = [["personal", "Personal Details"], ["search", "Job Search"], ["prefs", "Work Preferences"], ["summary", "Summary"], ["achievements", "Key Achievements"],
    ["experience", "Experience"], ["skills", "Skills"], ["education", "Education"], ["more", "More for the CV"],
    ...(ai ? [["notes", "Notes for ChatGPT"]] : []),
    ...v.groups.map((g) => [g.id, groupTitleOf(g), true])];
  return `<div class="doc profile">
    <nav class="doc-toc" aria-label="${esc(t("Profile"))}">${toc.map(([id, label, raw]) =>
      `<button type="button" class="toc-link" data-goto="p-${id}">${esc(raw ? label : t(label))}</button>`).join("")}</nav>
    <div class="doc-main">
      ${profileHead(v, f)}
      ${importNotice()}
      ${Object.keys(PROFILE_SECTIONS).filter((id) => ai || id !== "notes").map((id) => profileSection(id, v, f)).join("")}
      ${v.groups.map(setupGroup).join("")}
      <div class="doc-end"><button type="button" class="btn quiet danger" data-action="delete-profile">${esc(t("Delete Profile…"))}</button></div>
    </div>
  </div>`;
}

function guideHtml() {
  const lang = LANG;
  const search = C().profile?.profile?.search || {}, th = C().summary?.thresholds || { strong: 75, good: 70, moderate: 51 };
  const keywords = (search.titles || []).length;
  const sites = (search.sites || []).map((s) => SITE[s] || s);
  const g = window.guideContent(lang, {
    name: first(), sites: sites.length ? sites : ["LinkedIn", "Indeed"], keywords,
    searches: Math.max(1, Math.ceil(keywords / 4)), location: search.country || "Saudi Arabia", t: th,
  });
  return `<div class="doc guide" dir="${lang === "ar" ? "rtl" : "ltr"}" lang="${lang}">
    <nav class="doc-toc" aria-label="${esc(g.toc)}">${g.sections.map((s) =>
      `<button type="button" class="toc-link" data-goto="g-${s.id}">${s.title}</button>`).join("")}</nav>
    <div class="doc-main">
      <header class="doc-head"><h1>${g.title}</h1></header>
      ${g.sections.map((s) => `<section class="psec g-section" id="g-${s.id}"><h2>${s.title}</h2><div class="g-card">${s.html}</div></section>`).join("")}
    </div>
  </div>`;
}

/* ============================================================ floating */
function closeFloating() {
  $$(".popover, .menu").forEach((el) => el.remove());
}

function placeBelow(el, anchor, align = "center") {
  const r = anchor.getBoundingClientRect();
  const w = el.offsetWidth;
  let left = align === "start" ? (isAr() ? r.right - w : r.left) : r.left + r.width / 2 - w / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
  el.style.left = `${left}px`;
  el.style.top = `${r.bottom + 6}px`;
}

function openAccountMenu(anchor) {
  if ($(".menu")) return closeFloating();
  closeFloating();
  const menu = document.createElement("div");
  menu.className = "menu";
  menu.setAttribute("role", "menu");
  menu.innerHTML = S.candidates.map((c) => `<button role="menuitem" data-candidate="${esc(c.key)}">${avatar(c)}
      <span class="account-text"><span class="account-name" dir="auto">${esc(c.name)}</span><span class="account-sub" dir="auto">${esc(c.kind === "simple" ? t("Added in the app") : c.system_label)}</span></span>
      <span class="tick">${c.key === S.key ? icon("check", 14, "", 2.2) : ""}</span></button>`).join("")
    + `<div class="menu-sep"></div><button role="menuitem" data-action="new-profile"><span class="avatar add">${icon("plus", 14, "", 2.2)}</span>
      <span class="account-text"><span class="account-name">${esc(t("New Profile…"))}</span><span class="account-sub">${esc(t("From a PDF or a name"))}</span></span></button>`;
  document.body.append(menu);
  placeBelow(menu, anchor, "start");
}

function openActivity(anchor) {
  if ($(".popover")) return closeFloating();
  closeFloating();
  const pop = document.createElement("div");
  pop.className = "popover";
  pop.id = "activity-pop";
  document.body.append(pop);
  paintActivityPopover();
  if (anchor.closest(".sidebar")) {
    // Opens upward from the sidebar foot; pinned by its bottom edge so it can grow as the log fills.
    const r = anchor.getBoundingClientRect();
    pop.classList.add("up");
    pop.style.left = `${isAr() ? Math.max(8, r.right - pop.offsetWidth) : Math.max(8, r.left)}px`;
    pop.style.top = "auto";
    pop.style.bottom = `${window.innerHeight - r.top + 6}px`;
  } else {
    placeBelow(pop, anchor);
  }
}

function paintActivityPopover() {
  const pop = $("#activity-pop");
  if (!pop) return;
  const run = S.runs[S.key], sum = C().summary;
  if (!run) {
    const last = sum?.runs?.[0];
    if (sum?.active?.external) {
      pop.innerHTML = `<h3>${esc(t("Scheduled search running"))}</h3><p class="sub">${esc(t("It was started outside this app. Its jobs appear in Jobs when it finishes."))}</p>`;
      return;
    }
    pop.innerHTML = last
      ? `<h3>${esc(t("Last search"))}</h3><p class="sub">${esc(relDateTime(last.started))} · ${esc(runLine(last))}</p>
         <div class="info" style="margin-bottom:12px"><div><span>${esc(t("Jobs scored"))}</span><b>${last.evaluated}</b></div><div><span>${esc(t("Strong or good"))}</span><b>${last.matches}</b></div><div><span>${esc(t("CVs prepared"))}</span><b>${last.cvs.length}</b></div></div>
         <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn" data-action="show-jobs">${esc(t("Show Jobs"))}</button><button class="btn primary" data-action="run">${esc(t("Find New Jobs"))}</button></div>`
      : `<h3>${esc(t("No searches yet"))}</h3>
         <div style="display:flex;justify-content:flex-end"><button class="btn primary" data-action="run">${esc(t("Find New Jobs"))}</button></div>`;
    return;
  }
  const order = run.stages.map(([k]) => k);
  const at = order.indexOf(run.stage);
  const steps = run.stages.map(([k, label], i) => {
    let cls = "", glyph = icon("circle", 15, "", 1.5);
    if (run.status === "finished" || i < at) { cls = "done"; glyph = icon("checkCircle", 16); }
    else if (i === at && run.status === "running") { cls = "now"; glyph = '<span class="spin"></span>'; }
    else if (i === at) { cls = "fail"; glyph = icon("xCircle", 16); }
    return `<div class="step ${cls}"><span class="si">${glyph}</span>${esc(t(label))}</div>`;
  }).join("");
  const title = run.status === "running" ? `${t(STAGE_TEXT[run.stage] || "Working")}…`
    : t(run.status === "finished" ? "Search finished" : run.status === "busy" ? "Another search is running" : "Search stopped");
  const sub = `${t(modeInfo(run.mode, S.email)?.label || "Search")} · ${fmtElapsed(run.elapsed)}${S.email && run.status === "finished" && run.mode !== "real" ? t(" · nothing was emailed") : ""}`;
  const reason = run.status === "failed" || run.status === "error" || run.status === "stopped" ? stopReason(run) : "";
  const keepLog = $(".log", pop);
  const logOpen = pop.dataset.log === "1";
  pop.innerHTML = `<h3>${esc(title)}</h3><p class="sub">${esc(sub)}</p>
    ${reason ? `<p class="pop-reason">${icon("warn", 14)}<span dir="auto">${esc(cap(reason))}.</span></p>` : ""}<div class="steps">${steps}</div>
    <div style="display:flex;gap:8px;justify-content:space-between;align-items:center">
      <button class="btn link" data-action="toggle-log">${esc(t(logOpen ? "Hide Log" : "Show Log"))}</button>
      ${run.status === "finished" ? `<button class="btn primary" data-action="show-jobs">${esc(t("Show Jobs"))}</button>` : ""}</div>
    ${logOpen ? `<pre class="log" dir="ltr">${run.lines.map(logLine).join("\n")}</pre>` : ""}`;
  const log = $(".log", pop);
  if (log) log.scrollTop = keepLog ? keepLog.scrollTop + 1e6 : log.scrollHeight;
}

/* The pipeline logs "stopped: <reason>" when a whole run fails for one cause (a rejected key, no credit). */
function stopReason(run) {
  for (let i = (run.lines || []).length - 1; i >= 0; i--) {
    const m = run.lines[i].match(/stopped: (.+)$/);
    if (m) return m[1].trim().replace(/\.$/, "");
  }
  return "";
}

function fmtElapsed(s) {
  const m = Math.floor(s / 60), r = s % 60;
  return m ? t("{m} min {s} s", { m, s: r }) : t("{s} s", { s: r });
}
function logLine(line) {
  const m = line.match(/^\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d) (\w+)\s+(.*)$/);
  if (!m) return esc(line);
  const cls = m[2] === "WARNING" ? "w" : m[2] === "ERROR" ? "e" : "";
  return `${m[1]}  <span class="${cls}">${esc(m[3])}</span>`;
}

function openSheet(html, { wide = false } = {}) {
  closeSheet(true);
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  scrim.dataset.action = "close-sheet";
  const sheet = document.createElement("div");
  sheet.className = `sheet${wide ? " wide" : ""}`;
  sheet.setAttribute("role", "dialog");
  sheet.setAttribute("aria-modal", "true");
  sheet.innerHTML = html;
  document.body.append(scrim, sheet);
  setTimeout(() => $("[autofocus], .sheet-foot .primary", sheet)?.focus({ preventScroll: true }), 50);
}
function closeSheet(instant = false) {
  const sheet = $(".sheet"), scrim = $(".scrim");
  if (!sheet) return;
  if (instant) { sheet.remove(); scrim?.remove(); return; }
  sheet.classList.add("out");
  scrim?.classList.add("out");
  setTimeout(() => { sheet.remove(); scrim?.remove(); }, 190);
}

/* ============================================================ run sheet */
async function openRunSheet() {
  closeFloating();
  let o;
  try { o = await api(`/api/run-options/${enc(S.key)}`); } catch (err) { if (err.message !== "auth") banner(err.message); return; }
  S.runOpts = o;
  S.before[S.key] = (C().jobs || []).length;
  S.email = Boolean(o.email);
  const modes = modeList(S.email);
  const f = (S.forms[S.key] ||= { mode: modes[0], limit: 5, cvs: true, confirm: false, sources: [...o.sources_default], replay: "" });
  if (!modes.includes(f.mode)) f.mode = modes[0];
  if (!o.replayable.some((r) => r.stamp === f.replay)) f.replay = o.replayable[0]?.stamp || "";
  f.confirm = false;
  openSheet(`<div class="sheet-body"><h2>${t(S.demo ? "Run a Demo Search for {name}" : "Run a Search for {name}", { name: `<bdi>${esc(first())}</bdi>` })}</h2>
      ${seg("mode", modes.map((k) => [k, esc(t(modeInfo(k, S.email).label))]), f.mode)}
      <div id="run-form">${runFormHtml()}</div></div>
    <div class="sheet-foot" id="run-foot">${runFootHtml()}</div>`);
}

function runFormHtml() {
  const o = S.runOpts, f = S.forms[S.key];
  const missing = o.missing[f.mode];
  const rows = [];
  const demoLede = {
    dry: "Picks sample jobs, scores them with the simulated AI and writes the digest and CVs. Nothing is emailed.",
    replay: "Scores a sample search again. Only jobs that haven’t been scored before are evaluated.",
    real: o.email ? "The full daily run with sample jobs. The digest is marked as sent in the demo data, but nothing is emailed."
      : "Picks sample jobs, scores them with the simulated AI and writes a tailored CV for each strong match.",
  }[f.mode];
  if (f.mode === "replay") {
    rows.push(`<div class="item"><span class="item-main"><span class="item-title">${esc(t("Saved search"))}</span></span>
      ${o.replayable.length ? `<select class="field" data-field="replay">${o.replayable.map((r) => `<option value="${esc(r.stamp)}" ${r.stamp === f.replay ? "selected" : ""}>${esc(relDateTime(r.stamp.replace(/^(\d{4})(\d\d)(\d\d)-(\d\d)(\d\d)(\d\d)$/, "$1-$2-$3T$4:$5:$6")))}</option>`).join("")}</select>`
        : `<span class="item-value"><span>${esc(t("None yet"))}</span></span>`}</div>`);
  } else if (!o.demo) {
    rows.push(`<div class="item"><span class="item-main"><span class="item-title">${esc(t("Job sites"))}</span></span>
      <span style="display:flex;gap:14px">${o.sources_all.map((s) => `<label class="check"><input type="checkbox" data-source="${esc(s.key)}" ${f.sources.includes(s.key) ? "checked" : ""}>${esc(s.label)}</label>`).join("")}</span></div>`);
  }
  rows.push(`<div class="item"><span class="item-main"><span class="item-title">${esc(t("Score up to"))}</span></span>
    <select class="field" data-field="limit">${[5, 10, 20, 50, 0].map((v) => `<option value="${v}" ${v === f.limit ? "selected" : ""}>${esc(v ? count(v, "job") : t("All new jobs"))}</option>`).join("")}</select></div>`);
  rows.push(`<label class="item" style="cursor:pointer"><span class="item-main"><span class="item-title">${esc(t("Write tailored CVs"))}</span></span>
    <span class="switch"><input type="checkbox" data-field="cvs" ${f.cvs ? "checked" : ""}><i></i></span></label>`);
  if (f.mode === "real" && o.email) {
    rows.push(`<label class="item" style="cursor:pointer"><span class="item-main"><span class="item-title">${esc(t(o.demo ? "Mark the digest as sent" : "Email the digest"))}</span>
      <span class="item-sub">${o.demo ? esc(t("Demo Mode — nothing is emailed")) : o.recipient ? t("To {to}", { to: `<bdi>${esc(o.recipient)}</bdi>` }) : esc(t("No recipient set yet"))}</span></span>
      <span class="switch"><input type="checkbox" data-field="confirm" ${f.confirm ? "checked" : ""}><i></i></span></label>`);
  }
  const needs = missing.map((m) => `<bdi>${esc(missingLabel(m.label))}</bdi>`).join(isAr() ? "، " : ", ");
  const where = missing.some((m) => m.where === "profile") ? "profile" : "settings";
  const link = `<a href="#/${where}" data-action="close-sheet">${esc(t(where === "profile" ? "Profile" : "Settings"))}</a>`;
  return `<p class="lede">${esc(t(o.demo ? demoLede : modeInfo(f.mode, o.email).lede(o)))}</p><div class="group">${rows.join("")}</div>
    ${missing.length ? `<div class="warn">${icon("warn", 15)}<span>${t("Add the {list} in {link} first.", { list: needs, link })}</span></div>` : ""}
    ${o.active?.external ? `<div class="warn">${icon("warn", 15)}<span>${esc(t("A scheduled search is running right now. Try again when it finishes."))}</span></div>` : ""}
    ${f.mode !== "replay" && !o.demo ? `<p class="group-foot" style="margin:8px 2px 0">${esc(t("The score limit keeps the AI cost down; the job sites are still searched in full."))}</p>` : ""}`;
}

function runFootHtml() {
  const o = S.runOpts, f = S.forms[S.key];
  const blocked = o.missing[f.mode].length || o.active?.external || S.runs[S.key]?.status === "running"
    || (f.mode === "replay" && !f.replay) || (f.mode !== "replay" && !f.sources.length && !o.demo) || (f.mode === "real" && o.email && !f.confirm);
  return `<button class="btn" data-action="close-sheet">${esc(t("Cancel"))}</button>
    <button class="btn primary" data-action="start" ${blocked ? "disabled" : ""}>${esc(t(modeInfo(f.mode, o.email).start))}</button>`;
}

function repaintRunSheet() {
  if (!$("#run-form")) return;
  $("#run-form").innerHTML = runFormHtml();
  $("#run-foot").innerHTML = runFootHtml();
}

async function startRun() {
  const f = S.forms[S.key];
  const btn = $('[data-action="start"]');
  if (btn) btn.disabled = true;
  try {
    const run = await api("/api/run", {
      method: "POST",
      body: { candidate: S.key, mode: f.mode, limit: f.limit, sources: f.sources, no_cv: !f.cvs, replay: f.replay || null, confirm: f.confirm },
    });
    S.runs[S.key] = { ...run, lines: run.lines || [], next: run.next || 0 };
    closeSheet();
    paintBar();
    ensurePolling();
  } catch (err) {
    if (err.message !== "auth") banner(err.message);
    repaintRunSheet();
  }
}

function adoptRun(run) {
  if (!run || run.external || S.runs[run.candidate]?.id === run.id) return;
  S.runs[run.candidate] = { ...run, lines: [], next: 0 };
  ensurePolling();
}
function ensurePolling() { if (!S.poll) S.poll = setInterval(pollRuns, 700); }

async function pollRuns() {
  const live = Object.values(S.runs).filter((r) => r.status === "running");
  if (!live.length) { clearInterval(S.poll); S.poll = null; return; }
  for (const run of live) {
    try {
      const d = await api(`/api/run/${run.id}?since=${run.next}`);
      Object.assign(run, d, { lines: run.lines.concat(d.lines), next: d.next });
      if (run.candidate === S.key) { paintActivityOnly(); paintActivityPopover(); }
      if (d.status !== "running") {
        S.finishedAt[run.candidate] = Date.now();
        S.cache[run.candidate] = {};
        if (run.candidate === S.key) {
          await render({ quiet: true });
          paintActivityPopover();
          const added = (C().jobs || []).length - (S.before[run.candidate] ?? 0);
          if (d.status === "finished" && S.email && run.mode === "real") hud("Digest Sent", "check");
          else if (d.status === "finished") hud(added > 0 ? t("{jobs} added", { jobs: count(added, "newjob") }) : "No new jobs this time", "check");
          else if (d.status === "busy") banner("Another search for this person was already running.");
          else banner(stopReason(run) ? t("The search stopped: {reason}.", { reason: stopReason(run) }) : "The search stopped. Open the activity view to see the log.");
        }
      }
    } catch { /* transient — retried on the next tick */ }
  }
}
function paintActivityOnly() {
  const status = $("#sb-status");
  if (status) status.innerHTML = statusHtml();
  const btn = $("#bar .btn.run");
  if (btn) btn.outerHTML = runButton(S.runs[S.key]?.status === "running" || C().summary?.active?.external);
  paintSearchCard();
}

/* The one search button: finds jobs posted since the last search and adds them to the list. */
const runButton = (running) => `<button class="btn run${running ? " busy" : ""}" data-action="${running ? "activity" : "run"}"
  title="${esc(t("Looks for jobs posted since the last search and adds the new ones to the list"))}">${
  running ? '<span class="spin"></span>' : icon("search", 13, "", 2.3)}<span class="lbl">${esc(t(running ? "Searching…" : "Find New Jobs"))}</span></button>`;

/* "LinkedIn · Indeed · Saudi Arabia · Last 24 hours" */
function planLine(plan) {
  if (!plan) return "";
  return [...plan.sites, t(plan.country), t("Last {period}", { period: t(PERIODS[plan.hours] || `${plan.hours} hours`) })].join(" · ");
}

/* One click: no options to pick. The person's own job sites, every new job scored, CVs for good matches. */
async function quickSearch() {
  closeFloating();
  const sum = C().summary;
  if (S.runs[S.key]?.status === "running" || sum?.active?.external) return;
  if (sum && !sum.can_run) {
    const where = sum.blocked === "settings" ? "settings" : "profile";
    banner(where === "settings" ? "Finish Settings before searching." : "Add the job titles to search in the profile first.");
    if (S.view !== where) location.hash = `#/${where}`;
    return;
  }
  S.before[S.key] = (C().jobs || []).length;
  try {
    const run = await api("/api/run", { method: "POST", body: { candidate: S.key, mode: "real" } });
    S.runs[S.key] = { ...run, lines: run.lines || [], next: run.next || 0 };
    if (S.view !== "jobs") location.hash = "#/jobs";
    paintBar();
    paintActivityOnly();
    ensurePolling();
  } catch (err) {
    if (err.message !== "auth") banner(err.message);
  }
}

/* One plain line about what the search is doing right now, read from its log:
   "Searching LinkedIn and Bayt… · 54 postings found", "21 jobs fit the profile", "Writing 7 CVs…". */
function runDetail(run) {
  if (!run?.lines?.length) return "";
  const searching = new Set(), found = {};
  let fit = null, scoring = null, writing = null, saving = false;
  for (const line of run.lines) {
    const s = String(line);
    let m;
    if ((m = s.match(/scrape: (\w+)/))) searching.add(m[1]);
    else if ((m = s.match(/\b(\w+): (\d+) raw items/))) found[m[1]] = Number(m[2]);
    else if ((m = s.match(/\bfilter: \d+ -> (\d+)/))) fit = Number(m[1]);
    else if ((m = s.match(/\bevaluate: round \d+, (\d+) jobs/))) scoring = Number(m[1]);
    else if ((m = s.match(/\bcv: generating (\d+)/))) writing = Number(m[1]);
    else if (/\bselected \d+ of|\bnothing to send/.test(s)) saving = true;
  }
  if (saving) return t("Saving the results…");
  if (writing !== null) return t("Writing {cvs}…", { cvs: count(writing, "cv") });
  if (scoring !== null) return t("Scoring {jobs}…", { jobs: count(scoring, "job") });
  if (fit !== null) return t("{jobs} fit the profile", { jobs: count(fit, "job") });
  const pending = [...searching].filter((s) => !(s in found)).map((s) => SITE[s] || cap(s));
  const total = Object.values(found).reduce((a, b) => a + b, 0);
  const and = isAr() ? " و" : " and ";
  const sites = pending.length > 1 ? `${pending.slice(0, -1).join(isAr() ? "، " : ", ")}${and}${pending.at(-1)}` : pending[0] || "";
  return [sites ? t("Searching {sites}…", { sites }) : "", total ? t("{postings} found", { postings: count(total, "posting") }) : ""]
    .filter(Boolean).join("  ·  ");
}

/* Live progress where the jobs appear: a card above the list, or the steps in an empty list. */
function searchCardHtml() {
  const run = S.runs[S.key];
  if (!run || run.status !== "running") return "";
  const order = run.stages.map(([k]) => k);
  const pct = Math.round(((Math.max(0, order.indexOf(run.stage)) + .5) / order.length) * 100);
  return `<div class="search-card" id="search-card"><div class="sc-top"><span class="spin"></span>
      <b>${esc(t(STAGE_TEXT[run.stage] || "Working"))}…</b><span class="sc-time">${esc(fmtElapsed(run.elapsed))}</span></div>
    <i class="progress"><i style="width:${pct}%"></i></i><p class="sc-detail">${esc(runDetail(run))}</p></div>`;
}
function searchSteps(run) {
  const order = run.stages.map(([k]) => k), at = order.indexOf(run.stage);
  return `<ol class="steps big">${run.stages.map(([k], i) => {
    const state = i < at ? "done" : i === at ? "now" : "";
    const glyph = state === "done" ? icon("checkCircle", 18) : state === "now" ? '<span class="spin"></span>' : icon("circle", 18, "", 1.4);
    return `<li class="step ${state}"><span class="si">${glyph}</span>${esc(t(STAGE_TEXT[k] || k))}</li>`;
  }).join("")}</ol>`;
}
function paintSearchCard() {
  if (S.view !== "jobs" || !$("#list")) return;
  if (!(C().jobs || []).length) {
    const empty = $("#list .welcome");
    const run = S.runs[S.key];
    // While it runs, only the bar, the step and the time change - in place, so it never flickers.
    if (empty?.classList.contains("running") && run?.status === "running") {
      const at = Math.max(0, run.stages.map(([k]) => k).indexOf(run.stage));
      $$(".stepper li", empty).forEach((li, i) => { li.className = i < at ? "done" : i === at ? "now" : ""; });
      const detail = $(".run-detail", empty), text = runDetail(run);
      if (detail && detail.textContent !== text) detail.textContent = text;
      const time = $(".run-time", empty);
      if (time) time.textContent = fmtElapsed(run.elapsed);
      return;
    }
    if (empty) empty.outerHTML = emptyListHtml();
    return;
  }
  const html = searchCardHtml(), el = $("#search-card");
  if (el && html) {          // update the words and the bar in place, so the spinner never restarts
    const fresh = Object.assign(document.createElement("div"), { innerHTML: html }).firstElementChild;
    for (const sel of ["b", ".sc-time", ".sc-detail"]) {
      const now = $(sel, el), next = $(sel, fresh);
      if (now && next && now.textContent !== next.textContent) now.textContent = next.textContent;
    }
    const bar = $(".progress > i", el), nextBar = $(".progress > i", fresh);
    if (bar && nextBar) bar.style.width = nextBar.style.width;
    return;
  }
  if (el) el.remove(); else if (html) $("#list .list-tools")?.insertAdjacentHTML("afterend", html);
}

/* ======================================================== knowledge view */
async function openKnowledge(name) {
  try {
    const text = await api(`/api/knowledge/${enc(S.key)}/${enc(name)}`);
    openSheet(`<div class="sheet-body"><h2 dir="auto">${esc(name.replace(/_/g, " ").replace(/\.md$/, ""))}</h2>
        <p class="lede" style="min-height:0">${esc(t("{n} characters, exactly as the AI receives them.", { n: text.length.toLocaleString("en-US") }))}</p>
        <pre class="doc-view" dir="auto">${esc(text)}</pre></div>
      <div class="sheet-foot"><button class="btn primary" data-action="close-sheet">${esc(t("Done"))}</button></div>`, { wide: true });
  } catch (err) { if (err.message !== "auth") banner(err.message); }
}

/* ============================================================ profiles */
/* Saving: a moment after each change, the whole profile is sent; the page isn't repainted,
   so the field being typed in keeps its place. */
let saveTimer = null, pendingSave = null;
function scheduleSave(delay = 500) {
  pendingSave = { key: S.key, form: S.form };
  clearTimeout(saveTimer);
  setSaveState("saving");
  saveTimer = setTimeout(flushSave, delay);
}
function flushSave() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (!pendingSave) return Promise.resolve();
  const { key, form } = pendingSave;
  pendingSave = null;
  return saveProfile(key, form);
}
async function saveProfile(key, form) {
  try {
    const v = await api(`/api/profile/${enc(key)}`, { method: "POST", body: { profile: form } });
    const cache = S.cache[key];
    if (cache) {
      cache.profile = v;
      delete cache.summary;
      if (key === S.key && S.form === form) S.formView = v;      // keep what's being typed; adopt the saved view
    }
    const person = S.candidates.find((p) => p.key === key);
    if (person && v.profile.name && person.name !== v.profile.name) { person.name = v.profile.name; person.initials = initialsOf(v.profile.name); }
    if (key !== S.key) return;
    setSaveState(pendingSave ? "saving" : "saved");
    await need("summary");
    if (key !== S.key) return;
    paintSidebar();
    paintBar();
    if (S.view === "profile") {
      const head = $(".profile-head");
      if (head) { head.outerHTML = profileHead(v, S.form); setSaveState(pendingSave ? "saving" : "saved"); }
      $$("[data-need]").forEach((el) => { el.hidden = !v.missing.includes(el.dataset.need); });
    }
  } catch (err) {
    if (err.message !== "auth") setSaveState("error", err.message);
  }
}
let saveStateTimer;
function setSaveState(state, message = "") {
  const el = $("#save-state");
  if (!el) return;
  clearTimeout(saveStateTimer);
  el.className = `save-state ${state}`;
  el.innerHTML = state === "saving" ? `<span class="spin"></span>${esc(t("Saving…"))}`
    : state === "saved" ? `${icon("check", 12, "", 2.6)}${esc(t("Saved"))}`
    : `${icon("warn", 13)}<span dir="auto">${esc(t(message))}</span>`;
  if (state === "saved") saveStateTimer = setTimeout(() => el.classList.add("gone"), 1800);
}

/* Structural edits (a token, a chip, a role added or removed) redraw only their own section,
   so nothing else on the page moves or flickers. */
function editForm(change, focus, path) {
  change(S.form);
  const id = path && SECTION_OF(path);
  const el = id && $(`#p-${id}`);
  if (el) {
    el.outerHTML = profileSection(id, C().profile, S.form);
    $$(`#p-${id} textarea.area`).forEach(autoGrow);
  } else {
    paintMain(true);
  }
  if (focus) $(focus)?.focus();
  scheduleSave(250);
}
function addToken(input) {
  const value = input.value.replace(/[,،]\s*$/, "").trim();
  if (!value) return;
  const path = input.dataset.tokenAdd;
  const list = getPath(S.form, path);
  input.value = "";
  if (list.some((x) => x.toLowerCase() === value.toLowerCase())) return;
  editForm(() => list.push(value), `[data-token-add="${path}"]`, path);
}

const MAX_CV_BYTES = 8 * 1024 * 1024;
async function fileBody(file) {
  if (file.size > MAX_CV_BYTES) throw new Error(t("That file is larger than 8 MB."));
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) throw new Error(t("Choose a PDF or Word (.docx) file."));
  const data = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(new Error(t("The file couldn’t be read.")));
    reader.readAsDataURL(file);
  });
  return { filename: file.name, data };
}

async function importCv(file) {
  const key = S.key;
  flushSave();
  const btn = $(".doc-actions label.btn");
  if (btn) { btn.classList.add("busy"); btn.querySelector("span").textContent = t("Reading…"); }
  try {
    const v = await api(`/api/profile/${enc(key)}/import`, { method: "POST", body: await fileBody(file) });
    const cache = S.cache[key] ||= {};
    cache.profile = v;
    delete cache.summary;
    S.imported = { key, found: v.found, source: v.source };
    const person = S.candidates.find((p) => p.key === key);
    if (person) { person.name = v.profile.name; person.initials = initialsOf(v.profile.name); }
    if (key === S.key) { await render({ quiet: true }); hud(v.source === "questionnaire" ? "Answers Imported" : v.source === "cv" ? "CV Imported" : "Imported", "check"); }
  } catch (err) {
    if (err.message !== "auth") banner(err.message);
    if (btn) { btn.classList.remove("busy"); btn.querySelector("span").textContent = t("Upload PDF"); }
  }
}

/* A new person starts from the questionnaire: send it, then add the filled-in file here. A CV, or
   just a name, still works. */
function openNewProfile() {
  closeFloating();
  S.newFile = null;
  openSheet(`<div class="sheet-body"><h2>${esc(t("New Profile"))}</h2>
      <p class="lede" style="min-height:0">${esc(t("Upload their PDF: a CV, or a CV with its discovery record. Everything in it is used for the search."))}</p>
      <label class="drop" id="drop">${icon("doc", 28, "", 1.4)}<span class="drop-text"><b id="drop-name">${esc(t("Choose a PDF"))}</b>
        <small id="drop-sub">${esc(t("Or a Word file. You can also drop it here."))}</small></span>
        <input type="file" data-new-file accept=".pdf,.docx,.txt" hidden></label>
      <div class="group"><label class="item field-row"><span class="item-title">${esc(t("Full name"))}</span>
        <input class="inline" id="new-name" dir="auto" placeholder="${esc(t("Optional with a file"))}" autocomplete="off"></label></div>
      <p class="field-error" id="new-error" dir="auto" hidden></p></div>
    <div class="sheet-foot"><button class="btn" data-action="close-sheet">${esc(t("Cancel"))}</button>
      <button class="btn primary" data-action="create-profile">${esc(t("Create Profile"))}</button></div>`);
  setTimeout(() => $("#new-name")?.focus(), 60);
}
function pickNewFile(file) {
  if (!file) return;
  S.newFile = file;
  $("#drop")?.classList.add("has-file");
  $("#drop-name").textContent = file.name;
  $("#drop-sub").textContent = t("The profile will be filled in from this file.");
}
async function createProfile() {
  const btn = $('[data-action="create-profile"]');
  const name = ($("#new-name")?.value || "").trim();
  const error = (msg) => { const el = $("#new-error"); el.textContent = msg; el.hidden = false; };
  if (!name && !S.newFile) return error(t("Choose a file or type a name."));
  btn.disabled = true;
  btn.innerHTML = `<span class="spin"></span>${esc(t(S.newFile ? "Reading…" : "Creating…"))}`;
  try {
    const body = { name };
    if (S.newFile) body.file = await fileBody(S.newFile);
    const r = await api("/api/profiles", { method: "POST", body });
    S.candidates = (await api("/api/session")).candidates;
    S.key = r.key;
    store.set("candidate", S.key);
    S.cache[S.key] = {};
    S.imported = { key: r.key, found: r.found, source: r.source };
    S.query = ""; S.filter = "matches"; S.expanded = null; S.detailOpen = false;
    closeSheet();
    if (!$("#window")) renderShell();               // the first profile: the app's own screens appear now
    if (location.hash === "#/profile") render(); else location.hash = "#/profile";
    hud("Profile Created", "check");
  } catch (err) {
    if (err.message === "auth") return;
    error(t(err.message));
    btn.disabled = false;
    btn.textContent = t("Create Profile");
  }
}

function confirmDelete() {
  const name = `<bdi>${esc(cand()?.name || "")}</bdi>`;
  openSheet(`<div class="sheet-body"><h2>${t("Delete {name}’s profile?", { name })}</h2>
      <p class="lede" style="min-height:0">${esc(t("The profile and its jobs leave the app. A backup copy is kept on this computer."))}</p></div>
    <div class="sheet-foot"><button class="btn" data-action="close-sheet">${esc(t("Cancel"))}</button>
      <button class="btn destructive" data-action="delete-profile-yes">${esc(t("Delete"))}</button></div>`);
}
async function deleteProfile() {
  const key = S.key;
  try {
    await api(`/api/profile/${enc(key)}/delete`, { method: "POST" });
    S.candidates = (await api("/api/session")).candidates;
    delete S.cache[key];
    closeSheet();
    if (!S.candidates.length) { S.key = null; store.set("candidate", null); showNoProfiles(); hud("Profile Deleted", "check"); return; }
    S.key = S.candidates[0].key;
    store.set("candidate", S.key);
    if (location.hash === "#/jobs") render(); else location.hash = "#/jobs";
    hud("Profile Deleted", "check");
  } catch (err) {
    if (err.message !== "auth") banner(err.message);
    closeSheet();
  }
}

/* ================================================================ login */
function showLogin() {
  $("#root").innerHTML = `<div class="login"><form class="login-box" data-login>
      <span class="app-icon" style="width:76px;height:76px">${icon("tray", 36, "", 1.6)}</span>
      <h1>Job Automation</h1><p>${esc(t("Enter the password to continue."))}</p>
      <div class="login-field"><input class="field" type="password" name="password" placeholder="${esc(t("Password"))}" autocomplete="current-password" autofocus>
        <button type="submit" aria-label="${esc(t("Continue"))}">${icon("arrowR", 15, "flip", 2.2)}</button></div></form></div>`;
  $(".login input").focus();
}

/* ================================================================ events */
document.addEventListener("click", async (e) => {
  const el = e.target;
  const segBtn = el.closest(".seg button");
  if (segBtn) {
    const group = segBtn.parentElement;
    setSeg(group, segBtn.dataset.value);
    return onSeg(group.dataset.seg, segBtn.dataset.value);
  }
  if (el.closest("[data-cv-format]")) return setTimeout(closeFloating);     // the download goes ahead, then the menu closes
  if (!el.closest(".menu, .popover, [data-action='account'], [data-action='activity'], [data-action='cv-menu']")) closeFloating();

  const action = el.closest("[data-action]")?.dataset.action;
  if (action === "account") return openAccountMenu(el.closest("[data-action]"));
  if (action === "activity") return openActivity(el.closest("[data-action]"));
  if (action === "run") return S.email ? openRunSheet() : quickSearch();
  if (action === "clear-jobs") return confirmClearJobs();
  if (action === "clear-jobs-yes") return clearJobs();
  if (action === "close-sheet") return closeSheet();
  if (action === "new-profile") return openNewProfile();
  if (action === "create-profile") return createProfile();
  if (action === "posting-more") {             // the whole posting replaces its two-line summary
    const full = $("#posting");
    if (full) { full.hidden = false; full.parentElement.querySelector(".role-summary")?.remove(); }
    el.closest("[data-action]").remove();
    return;
  }
  if (action === "mail-edit") {
    const field = el.closest("[data-field]").dataset.field;
    S.mailOpen = S.mailOpen === field ? null : field;
    $("#p-mail").outerHTML = mailHtml();
    if (S.mailOpen) $(`#p-mail .item-edit input`)?.focus();
    return;
  }
  if (action === "mail-cancel") { S.mailOpen = null; $("#p-mail").outerHTML = mailHtml(); return; }
  if (action === "mail-test") {
    const btn = el.closest("button");
    btn.disabled = true;
    btn.innerHTML = `<span class="spin"></span> ${esc(t("Sending…"))}`;
    await saveMail({ test: true }, "Test Email Sent");
    return;
  }
  if (action === "copy-script") {
    try { await navigator.clipboard.writeText(S.mail?.script || ""); hud("Copied", "check"); } catch { banner(t("Select the script and copy it by hand.")); }
    return;
  }
  if (action === "apply") return startApply(el.closest("[data-action]"));
  if (action === "cv-menu") return openCvMenu(el.closest("[data-action]"));
  if (action === "email-job") {
    const btn = el.closest("button");
    btn.disabled = true;
    const label = btn.innerHTML;
    btn.innerHTML = `<span class="spin"></span> ${esc(t("Sending…"))}`;
    try {
      const r = await api("/api/email-job", { method: "POST", body: { candidate: S.key, url: btn.dataset.url } });
      hud(t("Sent to {to}", { to: r.to }), "check");
    } catch (err) { if (err.message !== "auth") banner(t(err.message)); }
    btn.disabled = false;
    btn.innerHTML = label;
    return;
  }
  if (action === "delete-profile") return confirmDelete();
  if (action === "delete-profile-yes") return deleteProfile();
  if (action === "dismiss-import") { S.imported = null; return el.closest(".notice")?.remove(); }
  if (action === "start") return startRun();
  if (action === "dismiss") return el.closest(".banner")?.remove();
  if (action === "demo-on") return setDemo(true);
  if (action === "demo-off") return setDemo(false);
  if (action === "demo-reset") {
    try {
      await api("/api/demo/reset", { method: "POST" });
      S.cache = {}; S.runs = {}; S.sel = {};
      await render();
      return hud("Demo Reset", "check");
    } catch (err) { if (err.message !== "auth") banner(err.message); return; }
  }
  if (action === "back") { S.detailOpen = false; return paintDetail(false); }
  if (action === "show-jobs") {
    closeFloating();
    S.filter = "matches";
    if (S.view !== "jobs") { location.hash = "#/jobs"; return; }
    paintList(false); return paintDetail(true);
  }
  if (action === "toggle-log") {
    const pop = $("#activity-pop");
    pop.dataset.log = pop.dataset.log === "1" ? "0" : "1";
    return paintActivityPopover();
  }
  if (action === "edit-env") {
    const env = el.closest("[data-env]").dataset.env;
    S.expanded = S.expanded === env ? null : env;
    paintMain(true);
    if (S.expanded) $(`[data-env-form="${CSS.escape(env)}"] input`)?.focus();
    return;
  }
  if (action === "cancel-env") { S.expanded = null; return paintMain(true); }
  if (action === "export") {
    const btn = el.closest("button");
    btn.disabled = true;
    btn.innerHTML = `<span class="spin"></span> ${esc(t("Exporting"))}`;
    try {
      await api(`/api/knowledge/${enc(S.key)}/export`, { method: "POST" });
      invalidate("profile");
      await render({ quiet: true });
      hud("Exported", "check");
    } catch (err) { if (err.message !== "auth") banner(err.message); btn.disabled = false; }
    return;
  }

  const tokenX = el.closest("[data-token-remove]");
  if (tokenX) {
    const path = tokenX.dataset.tokenRemove;
    return editForm((f) => getPath(f, path).splice(Number(tokenX.dataset.i), 1), null, path);
  }
  const chip = el.closest("[data-chip]");
  if (chip) {
    const path = chip.dataset.chip, list = getPath(S.form, path), value = chip.dataset.value, i = list.indexOf(value);
    if (i >= 0 && list.length === 1 && !chip.closest("[data-optional]")) return;   // at least one stays chosen
    return editForm(() => (i >= 0 ? list.splice(i, 1) : list.push(value)), null, path);
  }
  const add = el.closest("[data-add]");
  if (add) {
    const path = add.dataset.add, list = getPath(S.form, path);
    const blank = path === "cv.experience" ? { role_title: "", company: "", period: "", role_description: "", bullets: [] }
      : { credential: "", institution: "", detail: "" };
    const first = path === "cv.experience" ? "role_title" : "credential";
    return editForm(() => list.push(blank), `[data-f="${path}.${list.length}.${first}"]`, path);
  }
  const remove = el.closest("[data-remove]");
  if (remove) {
    const path = remove.dataset.remove;
    return editForm((f) => getPath(f, path).splice(Number(remove.dataset.i), 1), null, path);
  }

  const cbtn = el.closest("[data-candidate]");
  if (cbtn) {
    closeFloating();
    if (cbtn.dataset.candidate !== S.key) {
      flushSave();
      S.key = cbtn.dataset.candidate;
      store.set("candidate", S.key);
      S.query = ""; S.filter = "matches"; S.expanded = null; S.trackOpen = null; S.detailOpen = false;
      render();
    }
    return;
  }
  const del = el.closest("[data-delete-job]");
  if (del) { e.preventDefault(); return deleteJob(del.dataset.deleteJob); }
  const copy = el.closest("[data-copy]");
  if (copy) return copyText(copy.dataset.copy, copy);
  const appliedBtn = el.closest("[data-applied]");
  if (appliedBtn) return toggleApplied(appliedBtn.dataset.applied);
  const row = el.closest("#list .row");
  if (row) return select(row.dataset.id);
  const filterTo = el.closest("[data-filter-to]");
  if (filterTo) { S.filter = filterTo.dataset.filterTo; paintList(false); return paintDetail(true); }
  const toc = el.closest("[data-goto]");
  if (toc) { document.getElementById(toc.dataset.goto)?.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "start" }); return; }
  const kn = el.closest("[data-knowledge]");
  if (kn) return openKnowledge(kn.dataset.knowledge);
  const tr = el.closest("[data-track]");
  if (tr) { const n = Number(tr.dataset.track); S.trackOpen = S.trackOpen === n ? null : n; return paintMain(true); }
  const ap = el.closest("[data-appearance]");
  if (ap) return applyAppearance(ap.dataset.appearance, true);
  const lg = el.closest("[data-lang]");
  if (lg && lg.dataset.lang !== LANG) return applyLang(lg.dataset.lang);
});

/* Delete a job: gone from the list at once (the next one is selected), with Undo for a few seconds.
   It stays known to the app, so no later search brings it back. */
async function deleteJob(url) {
  const key = S.key, jobs = C().jobs || [];
  const at = jobs.findIndex((j) => j.url === url);
  if (at < 0) return;
  const before = itemsFor(), vi = before.findIndex((x) => x.url === url);
  const [job] = jobs.splice(at, 1);
  const after = itemsFor();
  S.sel[S.view] = after[Math.min(vi, after.length - 1)]?.url || null;
  if (narrow.matches) S.detailOpen = false;
  paintList(true); paintDetail(false); paintBar();
  const restore = async () => {
    try {
      await api("/api/jobs/delete", { method: "POST", body: { candidate: key, url, deleted: false } });
      if (S.key === key) { invalidate("jobs", "summary"); S.sel[S.view] = url; await render({ quiet: true }); }
    } catch (err) { if (err.message !== "auth") banner(err.message); }
  };
  toast(t("Job deleted"), t("Undo"), restore);
  try {
    await api("/api/jobs/delete", { method: "POST", body: { candidate: key, url } });
    if (S.key === key) { delete C().summary; await need("summary"); paintSidebar(); paintBar(); }
  } catch (err) {
    jobs.splice(at, 0, job);
    if (S.key === key) { paintList(true); paintDetail(false); }
    if (err.message !== "auth") banner(err.message);
  }
}

/* A small notice at the bottom with one action (Undo), like Photos and Mail. */
let toastTimer;
function toast(text, actionLabel, onAction, glyph = "trash", ms = 6000) {
  $(".toast")?.remove();
  clearTimeout(toastTimer);
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  el.innerHTML = `${icon(glyph, 15, "", 1.8)}<span>${esc(text)}</span>${actionLabel ? `<button class="toast-btn">${esc(actionLabel)}</button>` : ""}`;
  document.body.append(el);
  requestAnimationFrame(() => el.classList.add("in"));
  const close = () => { el.classList.remove("in"); setTimeout(() => el.remove(), 260); };
  el.querySelector(".toast-btn")?.addEventListener("click", () => { close(); onAction?.(); });
  toastTimer = setTimeout(close, ms);
}

function confirmClearJobs() {
  const name = `<bdi>${esc(first())}</bdi>`;
  openSheet(`<div class="sheet-body"><h2>${t("Clear {name}’s jobs?", { name })}</h2>
      <p class="lede" style="min-height:0">${esc(t("Every job, CV and Applied mark in the list is removed, and the next search starts fresh. A copy is kept in the backups folder."))}</p></div>
    <div class="sheet-foot"><button class="btn" data-action="close-sheet">${esc(t("Cancel"))}</button>
      <button class="btn destructive" data-action="clear-jobs-yes">${esc(t("Clear Jobs"))}</button></div>`);
}
async function clearJobs() {
  const key = S.key;
  try {
    await api("/api/jobs/clear", { method: "POST", body: { candidate: key } });
    S.cache[key] = {};
    S.sel = {};
    closeSheet();
    await render({ quiet: true });
    hud("Jobs Cleared", "check");
  } catch (err) {
    closeSheet();
    if (err.message !== "auth") banner(err.message);
  }
}

/* Mark a job as applied (by hand, on the employer's site). Optimistic, like Mail's flag. */
async function toggleApplied(url) {
  const key = S.key, job = (C().jobs || []).find((j) => j.url === url);
  if (!job) return;
  const before = job.applied, on = !before;
  job.applied = on ? new Date().toISOString() : null;
  paintBar(); paintList(true); paintDetail(false);
  try {
    const r = await api("/api/applied", { method: "POST", body: { candidate: key, url, applied: on } });
    job.applied = r.applied;
    if (key === S.key) { paintBar(); paintList(true); paintDetail(false); }
    if (on) hud("Marked as Applied", "check");
  } catch (err) {
    job.applied = before;
    if (key === S.key) { paintBar(); paintList(true); paintDetail(false); }
    if (err.message !== "auth") banner(err.message);
  }
}

function onSeg(name, value) {
  if (name === "appearance") return applyAppearance(value, true);
  if (name === "filter") { S.filter = value; paintList(false); paintBar(); return paintDetail(true); }
  if (name === "lang") return value !== LANG && applyLang(value);
  if (name === "hours") return saveSetting("SEARCH_HOURS", value);
  if (name === "daily") return saveSetting("DAILY_SEARCH", value);
  if (name === "mode") { S.forms[S.key].mode = value; S.forms[S.key].confirm = false; return repaintRunSheet(); }
}

async function saveSetting(name, value) {
  try {
    await api("/api/settings", { method: "POST", body: { values: { [name]: value } } });
    invalidate("settings", "summary");
    await render({ quiet: true });
    hud("Saved", "check");
  } catch (err) { if (err.message !== "auth") banner(err.message); }
}

document.addEventListener("change", async (e) => {
  const el = e.target;
  if (el.dataset.f !== undefined && S.form) {
    setPath(S.form, el.dataset.f, fieldValue(el));
    return scheduleSave(150);
  }
  if (el.dataset.import !== undefined) {
    const file = el.files?.[0];
    el.value = "";
    return file && importCv(file);
  }
  if (el.dataset.newFile !== undefined) return pickNewFile(el.files?.[0]);
  if (el.dataset.demo !== undefined) return setDemo(el.checked);
  const f = S.forms[S.key];
  if (el.dataset.source && f) {
    f.sources = el.checked ? [...new Set([...f.sources, el.dataset.source])] : f.sources.filter((s) => s !== el.dataset.source);
    return ($("#run-foot").innerHTML = runFootHtml());
  }
  if (el.dataset.field && f) {
    if (el.dataset.field === "cvs") f.cvs = el.checked;
    if (el.dataset.field === "confirm") f.confirm = el.checked;
    if (el.dataset.field === "replay") f.replay = el.value;
    if (el.dataset.field === "limit") f.limit = Number(el.value);
    return ($("#run-foot").innerHTML = runFootHtml());
  }
  if (el.dataset.setting) {
    const value = el.checked ? el.dataset.on : el.dataset.off;
    try {
      await api("/api/settings", { method: "POST", body: { values: { [el.dataset.setting]: value } } });
      invalidate("settings", "profile", "summary");
      Object.values(S.cache).forEach((c) => delete c.profile);    // every profile shows or hides its ChatGPT parts
      await render({ quiet: true });
      hud(el.checked ? "ChatGPT On" : "Free Mode", "check");
    } catch (err) { if (err.message !== "auth") banner(err.message); el.checked = !el.checked; }
    return;
  }
  if (el.dataset.check) {
    try {
      await api("/api/checklist", { method: "POST", body: { scope: el.dataset.scope, item: el.dataset.check, done: el.checked } });
      invalidate("settings", "profile", "summary");
      await render({ quiet: true });
    } catch (err) { if (err.message !== "auth") banner(err.message); el.checked = !el.checked; }
  }
});

document.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  if (form.matches("[data-login]")) {
    try {
      await api("/api/login", { method: "POST", body: { password: form.password.value } });
      S.booted = false;
      return boot();
    } catch {
      form.classList.remove("shake"); void form.offsetWidth; form.classList.add("shake");
      form.password.select();
      return;
    }
  }
  if (form.matches("[data-mail-email]")) {
    const email = form.email.value.trim();
    return saveMail({ email }, email ? "Saved" : "Emails Off");
  }
  if (form.matches("[data-mail-key]")) {
    const key = form.key.value.trim();
    if (!key) return form.key.focus();
    return saveMail({ key }, "Saved");
  }
  if (form.matches("[data-env-form]")) {
    const value = form.value.value.trim();
    if (!value) return form.value.focus();
    const save = form.querySelector('[type="submit"]');
    const note = document.getElementById(`err-${form.dataset.envForm}`);
    if (save) { save.disabled = true; save.innerHTML = `<span class="spin"></span> ${esc(t("Checking"))}`; }
    try {
      await api("/api/settings", { method: "POST", body: { values: { [form.dataset.envForm]: value } } });
      S.expanded = null;
      invalidate("settings", "profile", "summary");
      await render({ quiet: true });
      hud("Saved", "check");
    } catch (err) {
      if (save) { save.disabled = false; save.textContent = t("Save"); }
      if (err.message === "auth") return;
      // Say why right under the field, where the eye already is.
      if (note) { note.textContent = err.message; note.hidden = false; form.value.select(); } else banner(err.message);
    }
  }
});

document.addEventListener("input", (e) => {
  const el = e.target;
  if (el.dataset?.f !== undefined && S.form) {
    setPath(S.form, el.dataset.f, fieldValue(el));
    if (el.tagName === "TEXTAREA") autoGrow(el);
    return scheduleSave(900);
  }
  if (e.target.id === "q") {
    S.query = e.target.value;
    paintList(false);
    paintDetail(false);
    const p = $("#bar .bar-title p");
    if (p) p.textContent = barSubtitle();
  }
});

function autoGrow(area) {
  area.style.height = "auto";
  area.style.height = `${area.scrollHeight + 2}px`;
}
document.addEventListener("focusout", (e) => {
  if (e.target.dataset?.tokenAdd !== undefined && e.target.value.trim()) addToken(e.target);
});
/* A questionnaire or CV dropped on the New Profile sheet. */
document.addEventListener("dragover", (e) => {
  const drop = e.target.closest?.("#drop");
  if (!drop) return;
  e.preventDefault();
  drop.classList.add("over");
});
document.addEventListener("dragleave", (e) => e.target.closest?.("#drop")?.classList.remove("over"));
document.addEventListener("drop", (e) => {
  const drop = e.target.closest?.("#drop");
  if (!drop) return;
  e.preventDefault();
  drop.classList.remove("over");
  pickNewFile(e.dataTransfer?.files?.[0]);
});

document.addEventListener("keydown", (e) => {
  if (e.target.dataset?.tokenAdd !== undefined && (e.key === "Enter" || e.key === "," || e.key === "،")) {
    e.preventDefault();
    return addToken(e.target);
  }
  if (e.key === "Enter" && e.target.id === "new-name") return createProfile();
  if ((e.key === "Delete" || e.key === "Backspace") && e.target.closest?.("#list .row") && S.sel[S.view]) {
    e.preventDefault();
    return deleteJob(S.sel[S.view]);
  }
  if (e.key === "Escape") {
    if ($(".sheet")) return closeSheet();
    if ($(".popover, .menu")) return closeFloating();
    if (S.detailOpen) { S.detailOpen = false; return paintDetail(false); }
  }
  if ((e.key === "ArrowDown" || e.key === "ArrowUp") && e.target.closest?.("#list")) {
    const rows = $$("#list .row");
    const i = rows.findIndex((r) => r.classList.contains("selected"));
    const next = rows[Math.max(0, Math.min(rows.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
    if (next) {
      e.preventDefault();
      next.focus({ preventScroll: false });
      next.scrollIntoView({ block: "nearest" });
      select(next.dataset.id, { open: false });
    }
  }
  if (e.key === "/" && !e.target.closest("input, textarea") && $("#q")) { e.preventDefault(); $("#q").focus(); }
});

narrow.addEventListener("change", () => { S.detailOpen = false; render({ quiet: true }); });

/* ================================================================== boot */
async function boot() {
  applyAppearance(S.appearance);
  let session;
  try { session = await api("/api/session"); } catch (err) {
    if (err.message === "auth") return;
    $("#root").innerHTML = `<div class="login"><div class="login-box"><h1>${esc(t("Can’t reach Job Automation"))}</h1><p dir="auto">${esc(err.message)}</p></div></div>`;
    return;
  }
  if (session.auth_required && !session.authed) return showLogin();
  S.candidates = session.candidates;
  S.demo = Boolean(session.demo);
  S.email = Boolean(session.email);
  if (!S.booted) {
    window.addEventListener("hashchange", () => { if (S.candidates.length) route(); });
    S.booted = true;
  }
  if (!S.candidates.length) return showNoProfiles();
  if (!S.candidates.some((c) => c.key === S.key)) S.key = S.candidates[0].key;
  renderShell();
  route();
}

/* Nobody in the app yet (or everyone was deleted): one calm screen that starts the first profile. */
function showNoProfiles() {
  $("#root").innerHTML = `<div class="login"><div class="login-box first-run">
      <span class="app-icon" style="width:72px;height:72px">${icon("briefcase", 32, "", 1.6)}</span>
      <h1>${esc(t("Add the first person"))}</h1>
      <p>${esc(t("Start from their PDF, or just their name. The app then finds jobs for them and writes a CV for each one."))}</p>
      <button class="btn primary large" data-action="new-profile">${icon("plus", 14, "", 2.3)} ${esc(t("New Profile"))}</button></div></div>`;
}

boot();
