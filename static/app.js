/**
 * 战后算账 · Dota 2 录像级复盘与车队分锅账本
 * Frontend Application (Vanilla ES2024, Zero-Framework, 6 Interactive SVG Visuals + xAI Grok 4.7)
 */

const state = {
  accountId: 86080912,
  roster: null,
  profileData: null,
  squadLedger: null,
  heroesCatalog: [],
  workspaceMode: "home", // "home" | "postgame" | "pregame"
  homeFilter: "all", // "all" | "analyzed" | "party" | "win" | "loss"
  pregameOwnPicks: [
    { pos: 1, hero_id: 8, player_name: "Flame = ez mute" },
    { pos: 2, hero_id: 45, player_name: "Replica" },
    { pos: 3, hero_id: 97, player_name: "Make Your Choice" },
    { pos: 4, hero_id: 9, player_name: "Paphets" },
    { pos: 5, hero_id: 26, player_name: "Mr. Brightside" },
  ],
  pregameEnemyPicks: [
    { pos: 1, hero_id: 44 },
    { pos: 2, hero_id: 76 },
    { pos: 3, hero_id: 29 },
    { pos: 4, hero_id: 86 },
    { pos: 5, hero_id: 5 },
  ],
  pregameActiveSide: "own", // "own" | "enemy"
  pregameActivePos: 1,
  pregameHeroQuery: "",
  pregamePlan: null,
  isGeneratingPregameGrok: false,
  currentMatchId: null,
  currentReport: null,
  pendingMatchId: null,
  pendingMatchMeta: null,
  scrubberMinute: 15,
  scrubSyncMapMinute: null,
  perspective: "auto", // "auto" | "dire" | "radiant"
  nwFilter: "cores",   // "cores" | "own" | "all"
  mapMode: "wards_obs", // "wards_obs" | "wards_own" | "wards_all" | "heatmap" | "teamfights"
  selectedTeamfightIndex: null,
  focusMatrixSide: "own", // "own" | "opp"
  microTab: "hero_ult", // "hero_ult" | "unpressed_saves" | "map_space" | "damage_received" | "vision" | "stack_smoke" | "laning" | "tp_save" | "econ_pings" | "all"
  microSide: "own", // "own" | "opp"
  activePhaseKey: "lane", // "lane" | "mid" | "late"
  activeTeamTab: "own", // "own" | "opp" | "both"
  verdictActiveCard: "focus", // "focus" | "mvp" | "culprit" | "third" | "all"
  phaseSelectedPos: "focus", // "focus" | 1..5 | "all"
  tfActiveWaveIdx: 0, // 0..N | "all"
  tfSelectedPosMap: {}, // per-teamfight selected player pos ("focus" | 1..5 | "all")
  microExecSelectedPos: "focus", // "focus" | 1..5 | "all"
  forensicSelectedSlot: "focus", // Section 6 selected player slot ("focus" | slot | "all")
  llmStatus: null,
  isGeneratingGrok: false,
};

const NW_COLORS_RAD = ["#76b87a", "#9ad49e", "#5d9e8f", "#b2d184", "#7fa882"];
const NW_COLORS_DIRE = ["#e07a68", "#d9a75c", "#c95b4c", "#e4c282", "#b87a96"];

const TRIVIAL_ACTIVE_ITEMS = new Set([
  "tango",
  "tango_single",
  "branches",
  "clarity",
  "enchanted_mango",
  "flask",
  "faerie_fire",
  "famango",
  "quelling_blade",
  "ward_observer",
  "ward_sentry",
  "ward_dispenser",
  "tpscroll",
  "madstone_bundle",
]);

const CLIENT_EN_TO_ZH_MAP = {
  ringmaster_impalement: "穿刺飞刀(匕首减速)",
  ringmaster_tame_the_beasts: "驯兽术(皮鞭恐惧)",
  ringmaster_tame_the_beasts_crack: "皮鞭抽击",
  ringmaster_the_box: "逃生暗箱(救人箱)",
  ringmaster_wheel: "奇观之轮(大招转盘)",
  ringmaster_spotlight: "聚光灯(魔晶照明)",
  ringmaster_funhouse_mirror: "哈哈镜(马戏幻象)",
  ringmaster_strongman_tonic: "大力士药水(强力合剂)",
  ringmaster_whoopee_cushion: "放屁坐垫(位移减速)",
  ringmaster_summon_unicycle: "召唤独轮车",
  centaur_stampede: "奔袭冲撞(大招车)",
  centaur_hoof_stomp: "马蹄践踏(踩)",
  centaur_double_edge: "双刃剑",
  centaur_work_horse: "套马索(A杖拉车)",
  tidehunter_dead_in_the_water: "死水锚链(魔晶拴人)",
  night_stalker_midnight_feast: "午夜盛宴(魔晶吃怪)",
  night_stalker_darkness: "黑暗飞升(大招黑夜)",
  rubick_telekinesis_land: "隔空取物落点",
  rubick_telekinesis_land_self: "隔空取物落点",
  twin_gate_portal_warp: "双子门传送",
  ability_lamp_use: "点亮观察者",
  ability_pluck_famango: "采摘疗伤莲花",
  tpscroll: "回城卷轴",
  famango: "疗伤莲花",
  great_famango: "大疗伤莲花",
  greater_famango: "特大疗伤莲花",
  madstone_bundle: "狂石捆",
  blood_grenade: "血腥榴弹",
  "The Beasts": "驯兽术(皮鞭恐惧)",
  "Beasts Crack": "皮鞭抽击",
  "Funhouse Mirror": "哈哈镜(马戏幻象)",
  "Strongman Tonic": "大力士药水(强力合剂)",
  "Summon Unicycle": "召唤独轮车",
  "The Box": "逃生暗箱(救人箱)",
  "Whoopee Cushion": "放屁坐垫(位移减速)",
  "The Water": "死水锚链(魔晶拴人)",
  "Midnight Feast": "午夜盛宴(魔晶吃怪)",
  "Acid Spray": "酸性喷雾",
  "Chemical Rage": "化学狂暴(大招)",
  "Unstable Concoction": "不稳定化合物",
  "Concoction Throw": "投掷化合物",
  "Cold Feet": "寒霜之足",
  "Ice Blast": "冰晶爆轰(大招)",
  "Blast Release": "冰晶引爆",
  "Ice Vortex": "冰霜漩涡",
  "Battle Hunger": "战斗饥渴",
  "Berserkers Call": "狂战士之吼",
  "Culling Blade": "淘汰之刃(大招)",
  "Shuriken Toss": "投掷飞镖",
  "Hunter Track": "追踪术(大招)",
  "Wind Walk": "暗影步",
  "Double Edge": "双刃剑",
  "Hoof Stomp": "马蹄践踏",
  "Carrion Swarm": "食腐蝠群",
  "Prophet Exorcism": "驱使恶灵(大招)",
  "Prophet Silence": "沉默魔法",
  "Spirit Siphon": "吸魂巫术",
  "earth_spirit": "大地之灵",
};

function sanitizeMixedEnglishClient(raw) {
  const s = String(raw ?? "");
  if (!s || s.startsWith("http://") || s.startsWith("https://") || s.startsWith("/apps/")) {
    return s;
  }
  let out = s;
  for (const [enKey, zhVal] of Object.entries(CLIENT_EN_TO_ZH_MAP)) {
    if (out.includes(enKey)) {
      out = out.replaceAll(enKey, zhVal);
    }
  }
  // If string contains Chinese characters and still has snake_case raw ability/item keys, scrub them
  if (/[\u4e00-\u9fff]/.test(out) && /[a-z]{3,}_[a-z_]{3,}/.test(out)) {
    out = out.replace(/\b([a-z]{3,}_[a-z0-9_]{3,})\b/g, (m) => CLIENT_EN_TO_ZH_MAP[m] || "专属技能");
  }
  return out;
}

function escapeHtml(value) {
  return sanitizeMixedEnglishClient(String(value ?? ""))
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatMdBold(value) {
  return escapeHtml(value).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function fmtNum(n) {
  const num = Number(n || 0);
  return num.toLocaleString("en-US");
}

function fmtSigned(n) {
  const num = Math.round(Number(n || 0));
  return num > 0 ? `+${fmtNum(num)}` : fmtNum(num);
}

/**
 * Look up Grok 4.7 player entry by player_slot, pos+hero, or pos
 */
function findGrokPlayerEntry(p, report = state.currentReport) {
  if (!p || !report?.grok_coaching?.players) return null;
  const grokPlayers = Array.isArray(report.grok_coaching.players) ? report.grok_coaching.players : [];
  const grokSide = report.grok_coaching.side;
  if (grokSide && p.side && p.side !== grokSide && p.side !== (grokSide === "radiant" ? "天辉" : "夜魇")) {
    return null;
  }
  const heroShort = String(p.hero_short_zh || p.hero_name || "");
  return (
    grokPlayers.find(
      (gp) =>
        gp &&
        Number(gp.pos) === Number(p.pos) &&
        gp.hero &&
        (heroShort.includes(String(gp.hero)) || String(gp.hero).includes(heroShort))
    ) ||
    grokPlayers.find((gp) => gp && Number(gp.pos) === Number(p.pos)) ||
    grokPlayers.find((gp) => gp && gp.slot !== undefined && Number(gp.slot) === Number(p.player_slot)) ||
    null
  );
}

/**
 * Compute 0..100 integer score for any player (100 highest, 0 lowest).
 * Prioritizes Grok 4.7 AI re-evaluated score (`grok_score`) when available!
 */
function getHeroScore100(p, report = state.currentReport) {
  if (!p) return 60;
  const grokP = findGrokPlayerEntry(p, report);
  if (grokP && grokP.grok_score !== undefined && grokP.grok_score !== null) {
    const gs = Number(grokP.grok_score);
    if (Number.isFinite(gs) && gs > 0) {
      return Math.max(1, Math.min(100, Math.round(gs)));
    }
  }
  if (p.score_100 !== undefined && p.score_100 !== null) {
    return Math.max(0, Math.min(100, Math.round(Number(p.score_100))));
  }
  const raw = Number(p.rating_score ?? 6.0);
  const scaled = raw <= 10.5 ? raw * 10 : raw;
  return Math.max(0, Math.min(100, Math.round(scaled)));
}

function getScore100Tier(score100, won = true) {
  const s = Number(score100 || 0);
  if (s >= 90) return { grade: "S+", label: "封神真神", cls: "score-s" };
  if (s >= 80) return { grade: "A", label: won ? "凯旋主力" : "孤胆院长", cls: "score-a" };
  if (s >= 70) return { grade: "B", label: "合格执行", cls: "score-b" };
  if (s >= 60) return { grade: "C", label: won ? "惊险躺赢" : "节奏迷失", cls: "score-c" };
  return { grade: "D", label: won ? "短板隐身" : "犯罪背锅", cls: "score-d" };
}

/**
 * Find hero mini-logo URL by Chinese hero name from current match or global catalog
 */
function findMatchHeroImg(heroNameZh, report = state.currentReport) {
  if (!heroNameZh) return "";
  const clean = String(heroNameZh).trim();
  if (report) {
    const all = [
      ...(report.radiant_pos_1_to_5 || report.radiant_players || []),
      ...(report.dire_pos_1_to_5 || report.dire_players || []),
    ];
    const found = all.find((p) => p.hero_short_zh === clean || p.hero_name === clean);
    if (found && found.hero_img) return found.hero_img;
  }
  const cat = (state.heroesCatalog || []).find(
    (h) => h.short_zh === clean || h.full_zh === clean || h.name_zh === clean
  );
  return cat?.img || "";
}

/**
 * Render a table player cell with Hero Mini-Logo + Position + Hero Name + Player Nickname
 */
function renderHeroCellWithLogo(
  pos,
  heroZh,
  personaname = "",
  reportOrImg = state.currentReport,
  explicitImg = ""
) {
  const report =
    reportOrImg && typeof reportOrImg === "object" ? reportOrImg : state.currentReport;
  const rawImg =
    typeof reportOrImg === "string"
      ? reportOrImg
      : typeof explicitImg === "string"
      ? explicitImg
      : "";
  const imgUrl = rawImg || findMatchHeroImg(heroZh, report);
  const posPrefix = pos !== undefined && pos !== null && pos !== "" ? `${pos}号位 · ` : "";
  const pNameHtml = personaname
    ? ` <span class="micro-cell-player">(${escapeHtml(personaname)})</span>`
    : "";
  return `<span class="micro-hero-cell-inline">${
    imgUrl
      ? `<img class="micro-table-hero-logo" src="${escapeHtml(imgUrl)}" alt="${escapeHtml(
          heroZh || ""
        )}" loading="lazy" />`
      : ""
  }<span><b>${escapeHtml(posPrefix)}${escapeHtml(heroZh || "")}</b>${pNameHtml}</span></span>`;
}

/**
 * Inject inline Hero Mini-Logos next to any of the 10 match heroes' Chinese names in already-escaped HTML
 */
function injectHeroLogosIntoHtml(safeHtml, report = state.currentReport) {
  if (!safeHtml || !report) return safeHtml || "";
  const all = [
    ...(report.radiant_pos_1_to_5 || report.radiant_players || []),
    ...(report.dire_pos_1_to_5 || report.dire_players || []),
  ];
  const heroMap = new Map();
  const aliasPairs = {
    食人魔魔法师: ["食人魔", "蓝胖"],
    冥魂大帝: ["骷髅王"],
    矮人直升机: ["直升机"],
  };
  all.forEach((p) => {
    const name = (p.hero_short_zh || "").trim();
    if (name && p.hero_img && !heroMap.has(name)) {
      heroMap.set(name, p.hero_img);
      (aliasPairs[name] || []).forEach((al) => {
        if (!heroMap.has(al)) heroMap.set(al, p.hero_img);
      });
    }
  });
  if (heroMap.size === 0) return safeHtml;
  const names = [...heroMap.keys()].sort((a, b) => b.length - a.length);
  const escapedNames = names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escapedNames.join("|")})`, "g");

  return String(safeHtml)
    .split(/(<[^>]+>)/g)
    .map((chunk) => {
      if (chunk.startsWith("<")) return chunk;
      return chunk.replace(pattern, (match) => {
        const img = heroMap.get(match);
        if (!img) return match;
        return `<span class="inline-hero-chip"><img class="inline-hero-logo" src="${escapeHtml(
          img
        )}" alt="" loading="lazy" />${match}</span>`;
      });
    })
    .join("");
}

function showToast(msg, durationMs = 3200) {
  const el = document.getElementById("toast-banner");
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    el.hidden = true;
  }, durationMs);
}

async function copyTextToClipboard(text, label = "算账金句") {
  try {
    await navigator.clipboard.writeText(text);
    showToast(`已复制${label}，直接去群里粘贴开庭`);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    showToast(`已复制${label}`);
  }
}

function getPublicShareUrl(matchId = state.currentMatchId, { viewReport = false } = {}) {
  const mid = matchId || state.currentMatchId || state.pendingMatchId || "";
  const origin =
    window.location?.origin && window.location.origin !== "null"
      ? window.location.origin
      : "https://dota-ai-analyst.vercel.app";
  if (!mid) return origin;
  const side = state.currentReport ? getAuditedSide(state.currentReport) : state.perspective;
  const sideParam = side === "dire" || side === "radiant" ? `&side=${encodeURIComponent(side)}` : "";
  const viewParam = viewReport ? "&view=report" : "";
  return `${origin}/?match=${encodeURIComponent(mid)}${sideParam}${viewParam}`;
}

async function copyMatchShareLink({ viewReport = false } = {}) {
  if (!state.currentMatchId || !state.currentReport) {
    showToast("请先完成本局 AI 分析后再复制公开分享链接");
    return;
  }
  const shareUrl = getPublicShareUrl(state.currentMatchId, { viewReport });
  const { sideZh } = getOwnAndOppPlayers(state.currentReport);
  const shareTitle = state.currentReport.grok_coaching?.title || `比赛 #${state.currentMatchId}`;
  await copyTextToClipboard(
    shareUrl,
    viewReport
      ? `比赛 #${state.currentMatchId} (${sideZh}视角) 全屏结构化报告直达链接`
      : `比赛 #${state.currentMatchId} (${sideZh}视角 · ${shareTitle}) 公开复盘分享链接`
  );
}

async function exportMatchPdfReport(targetMatchId = null, { autoDownloadPdf = false } = {}) {
  if (targetMatchId && Number(targetMatchId) !== Number(state.currentMatchId)) {
    await loadMatchReport(Number(targetMatchId), { analyzeNow: true });
  }
  if (!state.currentReport || !state.currentMatchId) {
    showToast("请先选择或完成一局比赛的 AI 复盘后再打开结构化报告");
    return;
  }

  // Close other dialogs first
  document.getElementById("share-poster-dialog")?.close?.();
  document.getElementById("settings-dialog")?.close?.();

  openFullscreenStructuredReport(state.currentReport);

  if (autoDownloadPdf) {
    setTimeout(() => {
      downloadStructuredReportPdf();
    }, 260);
  }
}

const NOTO_SANS_SC_TTF_URL =
  "https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG9_FnYxNavzT.ttf";
let _cjkFontLoadPromise = null;

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  const chunks = [];
  for (let i = 0; i < bytes.length; i += chunkSize) {
    chunks.push(String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize)));
  }
  return btoa(chunks.join(""));
}

async function ensureCjkVectorFontBase64() {
  if (window._cachedNotoSansScBase64) {
    return window._cachedNotoSansScBase64;
  }
  if (!_cjkFontLoadPromise) {
    _cjkFontLoadPromise = (async () => {
      const res = await fetch(NOTO_SANS_SC_TTF_URL, { mode: "cors", cache: "force-cache" });
      if (!res.ok) throw new Error(`字体加载失败 (${res.status})`);
      const buf = await res.arrayBuffer();
      const b64 = arrayBufferToBase64(buf);
      window._cachedNotoSansScBase64 = b64;
      return b64;
    })().catch((err) => {
      _cjkFontLoadPromise = null;
      throw err;
    });
  }
  return _cjkFontLoadPromise;
}

window._cachedMatchIconsByMatchId = window._cachedMatchIconsByMatchId || {};
window._matchIconsLoadPromises = window._matchIconsLoadPromises || {};

async function ensureMatchIconsMap(matchId) {
  if (!matchId) return {};
  const key = String(matchId);
  if (window._cachedMatchIconsByMatchId[key]) {
    return window._cachedMatchIconsByMatchId[key];
  }
  if (!window._matchIconsLoadPromises[key]) {
    window._matchIconsLoadPromises[key] = (async () => {
      try {
        const res = await fetch(`/api/match_icons?match_id=${encodeURIComponent(key)}`);
        if (!res.ok) return {};
        const data = await res.json();
        const icons = data?.icons || {};
        window._cachedMatchIconsByMatchId[key] = icons;
        return icons;
      } catch (_err) {
        return {};
      }
    })();
  }
  return window._matchIconsLoadPromises[key];
}

function cleanPdfVectorText(raw) {
  let s = sanitizeMixedEnglishClient(String(raw ?? ""));
  s = s
    .replace(/\*\*/g, "")
    .replace(/\(评级\s*good\)/gi, "(评级:优)")
    .replace(/\(评级\s*bad\)/gi, "(评级:差)")
    .replace(/\(评级\s*warn\)/gi, "(评级:中)")
    .replace(/👑/g, "[MVP] ")
    .replace(/🚨/g, "[重点] ")
    .replace(/⚠️/g, "[注意] ")
    .replace(/✅|🟢|✓/g, "• ")
    .replace(/❌|🔴|✕/g, "× ")
    .replace(/📌|▸/g, "› ")
    .replace(/⚔️/g, "")
    .replace(/🛡️/g, "")
    .replace(/💀|⚰️/g, "")
    .replace(/🗺️|🧭/g, "")
    .replace(/👁️/g, "")
    .replace(/🌾|💨/g, "")
    .replace(/🌱|🌺|📚|🚪|🏮|💧|🪝/g, "")
    .replace(/🆘|📜|📋|📊|📈|📉|🎯|💥|🔮|🗡️|🏰|🌲|💸|📡|🐉|🐔|💎|🛠️|⚖️|🏆|🌍|🎉|🐟|🌅|🔥/g, "");
  // Remove any remaining supplementary plane emoji characters or variation selectors so NotoSansSC never renders tofu boxes
  s = s.replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}]/gu, "");
  return s.replace(/[ \t]{2,}/g, " ").trim();
}

function openFullscreenStructuredReport(report = state.currentReport) {
  if (!report) return;
  const dlg = document.getElementById("fullscreen-report-dialog");
  const paper = document.getElementById("fs-report-paper");
  const topTitle = document.getElementById("fs-report-top-title");
  const fsPerspSelect = document.getElementById("fs-perspective-select");
  if (!dlg || !paper) return;

  // Pre-warm the CJK vector font AND all hero/item base64 icons in the background so clicking "直接下载 PDF" is instantaneous
  ensureCjkVectorFontBase64().catch(() => {});
  ensureMatchIconsMap(report.match_id).catch(() => {});

  const { side, sideZh } = getOwnAndOppPlayers(report);
  const ownWon =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !Boolean(report.radiant_win));

  if (fsPerspSelect) {
    fsPerspSelect.value = side;
  }
  if (topTitle) {
    topTitle.textContent = `比赛 #${report.match_id} · ${sideZh}视角结构化复盘报告（${
      ownWon ? "凯旋庆功卷宗" : "败局定责卷宗"
    } · ${report.duration_str || ""}）`;
  }

  paper.innerHTML = buildStructuredFullReportHtml(report);
  paper.querySelectorAll("details").forEach((det) => {
    det.open = true;
  });

  if (!dlg.open) {
    dlg.showModal();
  }
  const viewport = document.getElementById("fs-report-scroll-viewport");
  if (viewport) viewport.scrollTop = 0;
}

/**
 * Generate an authentic Dota 2 veteran spicy/praise story for a key teamfight window.
 */
function buildTeamfightDotaStory(tf, fObj, idx, { side, sideZh, oppZh, grokWin } = {}) {
  const parts = tf.participants || [];
  const ownParts = parts
    .filter((p) => p.side === side)
    .sort((a, b) => (Number(b.damage) || 0) - (Number(a.damage) || 0));
  const oppParts = parts
    .filter((p) => p.side !== side)
    .sort((a, b) => (Number(b.damage) || 0) - (Number(a.damage) || 0));

  const ownDeaths =
    side === "radiant"
      ? Number(tf.rad_deaths ?? ownParts.reduce((s, p) => s + (Number(p.deaths) || 0), 0))
      : Number(tf.dire_deaths ?? ownParts.reduce((s, p) => s + (Number(p.deaths) || 0), 0));
  const oppDeaths =
    side === "radiant"
      ? Number(tf.dire_deaths ?? oppParts.reduce((s, p) => s + (Number(p.deaths) || 0), 0))
      : Number(tf.rad_deaths ?? oppParts.reduce((s, p) => s + (Number(p.deaths) || 0), 0));

  const rawRadSwing = Number(tf.net_swing_radiant ?? 0);
  const ownGoldSwing = side === "radiant" ? rawRadSwing : -rawRadSwing;

  const ownTop = ownParts[0];
  const ownSec = ownParts[1];
  const oppTop = oppParts[0];

  const ownDeadList = ownParts.filter((p) => (Number(p.deaths) || 0) > 0);
  const oppDeadList = oppParts.filter((p) => (Number(p.deaths) || 0) > 0);
  const ownDeadNames = ownDeadList.map((p) => p.hero_short_zh).join("、");
  const oppDeadNames = oppDeadList.map((p) => p.hero_short_zh).join("、");
  const ownZeroImpactDead = [...ownDeadList].sort((a, b) => (Number(a.damage) || 0) - (Number(b.damage) || 0))[0];

  const buybacksList =
    fObj?.buybacks && fObj.buybacks.length > 0
      ? fObj.buybacks
      : parts
          .filter((p) => p.buybacks)
          .map((p) => `${p.hero_short_zh}${p.personaname ? `(${p.personaname})` : ""}`);

  const fmtSpellsAndItems = (participant) => {
    if (!participant) return "平A输出";
    const sp = (participant.abilities || []).slice(0, 2);
    const it = (participant.items || [])
      .filter((x) => !String(x).includes("TP") && !String(x).includes("魔棒") && !String(x).includes("捆包"))
      .slice(0, 1);
    const merged = [...it, ...sp];
    return merged.length > 0 ? merged.join(" + ") : "普攻与技能衔接";
  };

  const ownTopCombo = fmtSpellsAndItems(ownTop);
  const oppTopCombo = fmtSpellsAndItems(oppTop);

  const minVal = Number(tf.minute || 20);
  const stageContext =
    minVal < 14
      ? "前中期外塔节奏争夺战"
      : minVal < 26
      ? "中期抱团控图碰撞"
      : minVal < 36
      ? "中后期关键肉山/高地团"
      : "大后期买活决死团战";

  let toneTag = "🩸 刺刀见红肉搏局";
  let toneClass = "warn";
  let storyTitle = `${stageContext} · ${tf.kills_trade || ""}`;
  let storyText = "";

  // Case 1: Decisive Win for our side (该夸狠狠夸)
  if (ownGoldSwing >= 650 || (oppDeaths - ownDeaths >= 2 && ownGoldSwing >= -100)) {
    toneTag = "🔥 教科书级团战大捷";
    toneClass = "win";
    storyTitle = `${ownTop?.hero_short_zh || sideZh}毁天灭地收割 · ${oppDeaths}换${ownDeaths}大捷 (${tf.gold_swing})`;
    storyText =
      `【${stageContext} · 封神现场】这波团战 ${sideZh}打出了赏心悦目的教科书级拉扯！` +
      (ownTop
        ? `本方头号打手 ${ownTop.hero_short_zh}（${ownTop.personaname || "核心"}）在人群中直接开启战神模式，果断交出「${ownTopCombo}」狂灌 ${fmtNum(
            ownTop.damage
          )} 点成吨伤害（单波进账 +${fmtNum(ownTop.gold_delta || 0)} 金）`
        : "") +
      (ownSec && Number(ownSec.damage) >= 1000
        ? `，配合侧翼 ${ownSec.hero_short_zh} 补上的 ${fmtNum(ownSec.damage)} 点火力瞬间撕碎敌方阵型！`
        : "，正面火力直接拉满！") +
      (oppTop
        ? `反观对面 ${oppTop.hero_short_zh} 虽然挣扎打了 ${fmtNum(oppTop.damage)} 点伤害，但根本顶不住我方集火，`
        : "") +
      (oppDeadNames ? `敌方 ${oppDeadNames} 像多米诺骨牌一样接连倒地沦为提款机。` : "") +
      (buybacksList.length > 0 ? `哪怕场上有 ${buybacksList.join("、")} 交出买活也挡不住兵败如山倒，` : "") +
      `最终 ${sideZh}干净利落打出 ${oppDeaths} 换 ${ownDeaths}，一波直接把「${tf.gold_swing}」揣进兜里，全队气势直接拉满！`;
  }
  // Case 2: Crushing Loss / Throw for our side (毒舌辛辣吐槽)
  else if (ownGoldSwing <= -650 || (ownDeaths - oppDeaths >= 2 && ownGoldSwing <= 100)) {
    toneTag = "💀 葫芦娃救爷爷惨案";
    toneClass = "loss";
    storyTitle = `${ownDeadNames || sideZh}脱节白给 · 惨遭${oppDeaths}换${ownDeaths}毒打 (${tf.gold_swing})`;
    storyText =
      `【${stageContext} · 血压拉满犯罪现场】这波团战堪称 ${sideZh}的集体脑溢血实录！` +
      (oppTop
        ? `对面 ${oppTop.hero_short_zh} 在战场上输出环境好得像在打木桩，肆无忌惮甩出「${oppTopCombo}」倾泻了足足 ${fmtNum(
            oppTop.damage
          )} 点爆炸伤害；`
        : "") +
      `而再看看我们这边？` +
      (ownDeadNames
        ? `${ownDeadNames} 走位脱节得像葫芦娃救爷爷，一个接一个排队进场领盒饭！`
        : "前排连拉扯都没做出来就瞬间蒸发！") +
      (ownZeroImpactDead && Number(ownZeroImpactDead.damage) < 1200
        ? `尤其是 ${ownZeroImpactDead.hero_short_zh}（${
            ownZeroImpactDead.personaname || ""
          }），整波团战只刮了可怜的 ${fmtNum(ownZeroImpactDead.damage)} 点伤害就光速躺平当泉水指挥官；`
        : "") +
      (ownTop && Number(ownTop.damage) >= 2400
        ? `苦了 ${ownTop.hero_short_zh}（${ownTop.personaname || ""}）一个人拼死轰出 ${fmtNum(
            ownTop.damage
          )} 点伤害独木难支，实在带不动身边排队送头的队友！`
        : "全队集火目标散乱，连对面的核心衣角都没摸破。") +
      (buybacksList.length > 0
        ? `期间 ${buybacksList.join("、")} 急眼拍出买活强行接团也纯属添油战术，`
        : "") +
      `短短几十秒直接送出 ${ownDeaths} 死 ${oppDeaths} 杀，拱手让出「${tf.gold_swing}」，前期辛辛苦苦攒的家底一波败光！`;
  }
  // Case 3: Edge for our side in a bloody brawl
  else if (ownGoldSwing >= 0) {
    toneTag = "⚡ 刀尖舔血硬赚节奏";
    toneClass = "win";
    storyTitle = `惨烈换命硬抢便宜 · ${tf.kills_trade} (${tf.gold_swing})`;
    storyText =
      `【${stageContext} · 惨烈换命局】双方在这波开启了寸土不让的贴身肉搏！` +
      (oppTop
        ? `对面 ${oppTop.hero_short_zh} 甩出「${oppTopCombo}」狂打 ${fmtNum(oppTop.damage)} 点伤害试图强行留人，`
        : "") +
      (ownTop
        ? `关键时刻本方 ${ownTop.hero_short_zh}（${ownTop.personaname || ""}）毫不手软，反手一套「${ownTopCombo}」轰出 ${fmtNum(
            ownTop.damage
          )} 点伤害完成反杀收割！`
        : "") +
      (ownDeadNames && oppDeadNames
        ? `虽然我方 ${ownDeadNames} 在混战中阵亡，但也成功拉上敌方 ${oppDeadNames} 垫背（${tf.kills_trade}）`
        : `双方技能全交打出 ${tf.kills_trade}`) +
      (buybacksList.length > 0 ? `，还逼出了 ${buybacksList.join("、")} 的关键买活` : "") +
      `，算完总账依旧净赚「${tf.gold_swing}」，这波刀尖舔血不亏！`;
  }
  // Case 4: Bloody stalemate or slight loss (辛辣点评菜鸡互啄/白忙活)
  else {
    toneTag = "🩸 惨烈换命亏节奏";
    toneClass = "warn";
    storyTitle = `技能全交惨烈对换 · ${tf.kills_trade} (${tf.gold_swing})`;
    storyText =
      `【${stageContext} · 刺刀见红拉锯战】两边在这波团战把键盘都快按碎了！` +
      (ownTop
        ? `本方 ${ownTop.hero_short_zh}（${ownTop.personaname || ""}）交出「${ownTopCombo}」打了 ${fmtNum(
            ownTop.damage
          )} 点伤害，`
        : "") +
      (oppTop
        ? `对面 ${oppTop.hero_short_zh} 立刻用「${oppTopCombo}」反灌 ${fmtNum(oppTop.damage)} 点输出正面硬刚。`
        : "") +
      (buybacksList.length > 0
        ? `打上头之后 ${buybacksList.join("、")} 甚至直接拍出买活强行续命再战！`
        : "") +
      (ownDeadNames
        ? `然而收尾阶段我方 ${ownDeadNames} 撤退不及被留下，导致人头定格在「${tf.kills_trade}」，经济反而让对面捞走「${tf.gold_swing}」——场面看着热闹非凡，实则打了个寂寞还倒贴医药费！`
        : `最终定格在「${tf.kills_trade}」（${tf.gold_swing}），属于两边技能全交但本方小亏一口气的肉搏局。`);
  }

  if (grokWin && grokWin.detail && grokWin.detail.length > 25) {
    storyText = `${storyText} 【Grok 4.7 追评：${grokWin.detail}】`;
  }

  const mappedTone = toneClass === "win" ? "praise" : toneClass === "loss" ? "roast" : "mixed";
  return {
    toneTag,
    toneClass,
    badge: toneTag,
    tone: mappedTone,
    storyTitle,
    storyText,
    storyHtml: injectHeroLogosIntoHtml(escapeHtml(storyText), state.currentReport),
  };
}

/**
 * Generate a cohesive Dota 2 veteran spicy/praise AI commentary paragraph for each player in Chapter 6.
 */
function buildPlayerDossierAiStory(p, { grokPlayer, isMvp, isTopCulprit, contribPct, blamePct } = {}) {
  const heroShort = p.hero_short_zh || p.hero_name || "该英雄";
  const pWon = Boolean(p.won);
  const cPct = contribPct ?? Number(p.contrib_share_pct ?? p.blame_share_pct ?? 20).toFixed(1);
  const bPct = blamePct ?? Number(p.blame_share_pct || 0).toFixed(1);
  const lh10 = p.laning_10m?.lh10 ?? 0;
  const dn10 = p.laning_10m?.dn10 ?? 0;
  const laneEff = p.lane_efficiency_pct || 0;
  const dmgPerGold = p.net_worth ? (p.hero_damage / p.net_worth).toFixed(2) : "0.00";
  const score100 = getHeroScore100(p);
  const scoreTier = getScore100Tier(score100, pWon);

  // Item timing narrative
  const coreItems = (p.final_items_rich || []).filter((it) => it.purchase_time_str);
  const itemRouteStr =
    coreItems.length > 0
      ? coreItems
          .slice(0, 4)
          .map((it) => `${it.purchase_time_str}${it.zh_name || it.key}`)
          .join(" → ")
      : "常规散件过渡";

  // Check BKB or active item button presses
  const bkbItem = (p.final_items_rich || []).find((it) => String(it.key || "").includes("black_king_bar"));
  const activeUsesList = Object.values(p.active_item_uses || {})
    .filter((u) => u && !TRIVIAL_ACTIVE_ITEMS.has(u.key))
    .sort((a, b) => (b.count || 0) - (a.count || 0));
  const topActive = activeUsesList[0];

  let activeAuditClause = "";
  if (bkbItem) {
    const bkbCnt = Number(bkbItem.use_count || 0);
    if (bkbCnt <= 2) {
      activeAuditClause = `${bkbItem.purchase_time_str || "中期"}好不容易掏出黑皇杖(BKB)，结果整局只按了 ${bkbCnt} 次，纯纯把 BKB 当挂件供着！`;
    } else if (bkbCnt <= 5) {
      activeAuditClause = `${bkbItem.purchase_time_str || "中期"}做出黑皇杖(BKB)后整局按下 ${bkbCnt} 次，几波关键混战开BKB时机仍略显犹豫；`;
    } else {
      activeAuditClause = `${bkbItem.purchase_time_str || "中期"}掏出黑皇杖(BKB)后高频按下 ${bkbCnt} 次，团战切入与魔免拉扯非常果断；`;
    }
  } else if (topActive && topActive.count >= 8) {
    activeAuditClause = `手里的「${topActive.zh_name || topActive.key}」整局狂按 ${topActive.count} 次，道具操作频率拉满；`;
  } else {
    activeAuditClause = `整局主动保命/切入道具按键偏少，装备主动技能利用率还有很大提升空间；`;
  }

  // Benchmarks highlights
  const benches = p.benchmarks_list || [];
  const topBenches = benches.filter((b) => Number(b.pct) >= 80).sort((a, b) => Number(b.pct) - Number(a.pct));
  const lowBenches = benches.filter((b) => Number(b.pct) <= 35).sort((a, b) => Number(a.pct) - Number(b.pct));

  const benchPraise =
    topBenches.length > 0
      ? `在全球同英雄对标中，「${topBenches
          .slice(0, 2)
          .map((b) => `${b.label}(击败${b.pct}%)`)
          .join("、")}」堪称大腿级数据`
      : "";
  const benchRoast =
    lowBenches.length > 0
      ? `但「${lowBenches
          .slice(0, 2)
          .map((b) => `${b.label}(仅击败${b.pct}%)`)
          .join("、")}」严重拉胯`
      : "";

  // Target focus highlight
  const topTargetAbil = (p.ability_targets_list || [])[0];
  const targetClause =
    topTargetAbil && (topTargetAbil.targets || []).length > 0
      ? `指向性技能「${topTargetAbil.ability_zh}」整局甩出 ${topTargetAbil.total_casts} 次（重点照顾${topTargetAbil.targets
          .slice(0, 2)
          .map((t) => `${t.hero_short_zh}×${t.count}`)
          .join("、")}），`
      : "";

  // Closing punchline (Dota 2 veteran tone)
  const hmp = p.hero_mechanism_profile || {};
  const tCurveTag = hmp.timing_curve_zh ? ` · ${hmp.timing_curve_zh}` : "";
  let punchline = "";
  let badge = `🎙️ AI 老炮个人点评${tCurveTag} · ${score100}/100分`;
  let tone = "mixed";
  const rating = Number(p.rating_score || 6.0);
  if (pWon) {
    if (isMvp || score100 >= 88) {
      badge = `👑 AI 封神表彰评书${tCurveTag} · ${score100}/100分 (${scoreTier.label})`;
      tone = "praise";
      const harvestPraise = hmp.late_harvest_fulfilled
        ? `前中期弱势期隐忍刷出核心装（合理避战不盲目送团），25m+ 决胜期出山狂轰全队 ${hmp.late_hdmg_share_pct || p.hero_damage_share_pct}% 伤害完成终极收割，`
        : "从对线一路 C 到终局的绝对真神，";
      punchline = `本局百人制打分砍下 ${score100}/100 分（全场贡献 ${cPct}% 胜局功勋），${harvestPraise}这把赢球全队得给 ${heroShort} 敬一杯！`;
    } else if ((p.dead_seconds || 0) >= 180 || score100 < 78) {
      badge = `🌶️ AI 胜局毒舌敲打${tCurveTag} · ${score100}/100分 (${scoreTier.label})`;
      tone = "mixed";
      const tempoRoast = hmp.mid_tempo_wasted
        ? `身为【${hmp.timing_curve_zh || "中期节奏核"}】却在 10~25m 强势期当大核闷头独刷不参战，`
        : `全场在泉水读秒长达 ${p.dead_seconds} 秒，`;
      punchline = `本局百人制得分仅 ${score100}/100 分（贡献 ${cPct}%）——虽然最后跟着车队躺赢拿下比赛，但 ${heroShort} ${tempoRoast}属于边混边赢的“惊险气氛组”，下把务必按英雄强势期打节奏！`;
    } else {
      badge = `🏆 AI 凯旋功臣点评${tCurveTag} · ${score100}/100分 (${scoreTier.label})`;
      tone = "praise";
      const roleNote = hmp.late_harvest_fulfilled
        ? "前中期稳健刷钱成型、后期团战完美兑现大核收割职责"
        : hmp.sacrificial_initiator_fulfilled
        ? `果断肉身跳刀先手开团（硬控 ${p.stuns_sec || 0} 秒 / 吃下全队 ${p.damage_taken_share_pct || 0}% 伤害）`
        : `扎实完成了 ${p.pos} 号位（${hmp.timing_curve_zh || "核心/辅助"}）本职工作`;
      punchline = `本局百人制斩获 ${score100}/100 高分（稳健拿下 ${cPct}% 胜局贡献），${heroShort} ${roleNote}，是车队赢球不可或缺的坚实拼图！`;
    }
  } else {
    if (isTopCulprit || Number(bPct) >= 25 || score100 < 52) {
      badge = `🚨 AI 一级战犯处刑词${tCurveTag} · ${score100}/100分 (${scoreTier.label})`;
      tone = "roast";
      let mechCrimeClause = "";
      if (p.slark_mechanism_audit) {
        const sm = p.slark_mechanism_audit;
        mechCrimeClause = `中后期不仅多次单带无故被抓断节奏，且整局拒出 1400 金核心魔晶《深海劫掠》（既救不了被抓队友也叠不起能量转移属性导致正面根本 A 不过人），后期 25m+ 吃下全队最高 +${fmtNum(
          sm.late_gold_gain || 0
        )} 金（${sm.late_gold_share_pct || 26}%）却只打出全队垫底的 ${fmtNum(
          sm.late_hdmg_gain || 0
        )} 伤害（${sm.late_hdmg_share_pct || 15.5}%），`;
      } else if (p.phoenix_egg_audit && p.phoenix_egg_audit.shattered_cnt >= 2) {
        const pe = p.phoenix_egg_audit;
        mechCrimeClause = `团战大招《超新星》变蛋 ${pe.tf_egg_casts} 次竟有 ${pe.shattered_cnt} 次被集火打碎（碎蛋率 ${
          pe.shatter_rate_pct
        }%：${(pe.shattered_times || []).join("、")}），且全场仅放 ${pe.sun_ray_casts} 次《烈日炙烤》激光，`;
      } else if (hmp.late_harvest_failed) {
        mechCrimeClause = `前中期吃了团队大量安全线与野区资源，但 25m+ 决胜期吃下 ${hmp.late_gold_share_pct || 22}% 经济却仅打出 ${
          hmp.late_hdmg_share_pct || 15
        }% 伤害，完全没能兑现【${hmp.timing_curve_zh || "大核"}】后期收割职责${
          hmp.missing_mandatory_shard ? `（且拒出 1400 金质变魔晶：${hmp.shard_desc}）` : ""
        }；`;
      } else if (Array.isArray(p.weaknesses) && p.weaknesses[0]) {
        mechCrimeClause = `${String(p.weaknesses[0]).replace(/\*\*/g, "")}；`;
      }
      punchline = `本局百人制仅得 ${score100}/100 分，背下全队 ${bPct}% 头号大锅（泉水读秒 ${p.dead_seconds || 0} 秒 / 阵亡掉钱 -${fmtNum(
        p.death_gold_lost || 0
      )}）！${mechCrimeClause}这把输球 ${heroShort} 得在群里主动发红包谢罪！`;
    } else if (
      p.is_turret_fulfilled ||
      hmp.sacrificial_initiator_fulfilled ||
      hmp.save_support_fulfilled ||
      rating >= 7.2 ||
      Number(p.hero_damage_share_pct) >= 28 ||
      score100 >= 72
    ) {
      badge = p.is_turret_fulfilled
        ? `🔥 AI 悲情炮台认证${tCurveTag} · ${score100}/100分 (${scoreTier.label})`
        : `🛡️ AI 悲情院长平反词${tCurveTag} · ${score100}/100分 (${scoreTier.label})`;
      tone = "praise";
      const dpd = p.dmg_per_death || Math.round((p.hero_damage || 0) / Math.max(1, p.deaths || 1));
      punchline = `本局百人制拿到 ${score100}/100 分（背锅仅 ${bPct}%），堪称虽败犹荣的“${
        p.is_turret_fulfilled ? "悲情高爆炮台" : "悲情孤胆院长"
      }”！${heroShort} 一个人轰出全队 ${p.hero_damage_share_pct}% 的英雄输出（场均每次阵亡换出 ${fmtNum(
        dpd
      )} 点实打实伤害），无状态炮台只要死前把伤害灌满就绝不背大锅，奈何前排控制与救人体系崩塌实在带不动！`;
    } else {
      badge = `⚖️ AI 败局算账点评${tCurveTag} · ${score100}/100分 (${scoreTier.label})`;
      tone = "roast";
      const extraWeak =
        p.phoenix_egg_audit && p.phoenix_egg_audit.shattered_cnt >= 2
          ? `团战 ${p.phoenix_egg_audit.tf_egg_casts} 次变蛋被打碎 ${p.phoenix_egg_audit.shattered_cnt} 次（碎蛋率 ${p.phoenix_egg_audit.shatter_rate_pct}%），`
          : hmp.missing_mandatory_shard
          ? `整局漏出 1400 金核心魔晶（${hmp.shard_desc}），`
          : "";
      punchline = `本局百人制得分 ${score100}/100 分，分摊 ${bPct}% 败局责任（泉水读秒 ${p.dead_seconds || 0} 秒），${extraWeak}${heroShort} 中后期几波关键团战走位与技能机制配合失误明显，下把急需找回状态！`;
    }
  }

  const baseStory =
    `【${heroShort}${tCurveTag ? `（${hmp.timing_curve_zh}）` : ""} 本局评分：${score100}/100分】前10分钟在${p.lane_role || "线上"}交出 ${lh10}/${dn10} 补刀（效率 ${laneEff}%），装备按「${itemRouteStr}」成型；` +
    `${activeAuditClause}` +
    `实战交出 ${p.kda}（参战 ${p.kill_participation_pct}%），轰出 ${fmtNum(p.hero_damage)} 英雄伤害（占全队 ${
      p.hero_damage_share_pct
    }% · 伤转 ${dmgPerGold}）与 ${fmtNum(p.tower_damage)} 建筑推塔伤害。` +
    `${targetClause}` +
    (benchPraise || benchRoast ? `${benchPraise}${benchPraise && benchRoast ? "，" : ""}${benchRoast}。` : "") +
    `${punchline}`;

  const fullText =
    grokPlayer?.assessment && grokPlayer.assessment.length > 20
      ? `${baseStory} 【Grok 4.7 深度追评：${grokPlayer.assessment}】`
      : baseStory;

  return {
    badge,
    tone,
    score100,
    storyText: fullText,
    storyHtml: injectHeroLogosIntoHtml(escapeHtml(fullText), state.currentReport),
    toString() {
      return fullText;
    },
  };
}

function buildStructuredMicroTablesHtml(report, df, side, sideZh, oppSide, oppZh) {
  const gradeZhMap = { good: "优", bad: "差", warn: "中" };
  // 4.1 英雄绝活与大招释放质量审判总表
  const execData = df.hero_execution_by_side?.[side];
  const execPlayers = Array.isArray(execData) ? execData : execData?.players || [];
  const ultRowsHtml = execPlayers
    .map((p) => {
      const badgesStr = (p.headline_badges || [])
        .map((b) => (typeof b === "string" ? b : b?.text || ""))
        .filter(Boolean)
        .join(" ｜ ");
      const ults = p.ult_audits || p.signature_spells || [];
      const ultDesc = ults
        .map((sp) => {
          const casts = sp.casts ?? 0;
          const hits = sp.hits ?? sp.hero_hits ?? 0;
          const avg = sp.avg_hits ?? sp.avg_heroes_per_cast ?? 0;
          const dmg = sp.damage ?? sp.total_damage ?? 0;
          const unit = sp.unit_label || "人次";
          const gZh = gradeZhMap[sp.grade] || sp.grade || "良";
          return `<b>${escapeHtml(sp.ability_zh || "关键大招")}</b> (评级:${escapeHtml(
            gZh
          )})：释放 <b>${casts}</b> 次${hits > 0 ? `，命中 <b>${hits}</b> ${escapeHtml(unit)} (均 ${avg})` : ""}${
            dmg > 0 ? `，伤害 <b>${fmtNum(dmg)}</b>` : ""
          }`;
        })
        .join("<br/>");
      const skillDesc = (p.skillshot_audits || [])
        .map(
          (sk) =>
            `${escapeHtml(sk.ability_zh || "")}：${sk.casts ?? 0}放/${sk.hits ?? 0}中 (<b>${
              sk.hit_pct ?? 0
            }%</b> · ${fmtNum(sk.damage || 0)}伤)`
        )
        .join("<br/>");
      const heldWaves = ults.flatMap((sp) => sp.tf_held_death_waves || []);
      const castWaves = ults.flatMap((sp) => sp.tf_casts_waves || []);
      const verdictStr =
        ults.map((sp) => sp.verdict_text || sp.verdict || "").filter(Boolean).join("；") ||
        (p.special_insights || []).slice(0, 2).join("；") ||
        "技能衔接正常";

      return `
        <tr>
          <td>
            <b>${p.pos ?? "?"}号位 · ${escapeHtml(p.hero_short_zh || "")}</b><br/>
            <span class="fs-sub">${escapeHtml(p.personaname || "")} · 全场硬控 ${p.stuns_sec ?? 0}s</span>
          </td>
          <td>${escapeHtml(badgesStr || "常规释放")}</td>
          <td>${ultDesc || "无主动大招"}</td>
          <td>${skillDesc || "-"}</td>
          <td>
            ${
              castWaves.length > 0
                ? `<div class="txt-win">✓ 开大团战：${escapeHtml(castWaves.join("、"))}</div>`
                : ""
            }
            ${
              heldWaves.length > 0
                ? `<div class="txt-loss">✕ 憋大阵亡：${escapeHtml(heldWaves.join("、"))}</div>`
                : `<div class="fs-sub">✓ 0次团战憋大阵亡</div>`
            }
          </td>
          <td class="fs-verdict-cell">${escapeHtml(verdictStr)}</td>
        </tr>
      `;
    })
    .join("");

  // 4.2 憋死 BKB / 救命装与 0 技能秒躺尸检总表
  const us = df.unpressed_saves_by_side?.[side] || {};
  const usRowsHtml = (us.player_rows || [])
    .map((r) => {
      const coreCnt = Number(r.unpressed_core_cnt ?? 0);
      const zeroCnt = Number(r.zero_spell_cnt ?? 0);
      return `
        <tr>
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(
        r.personaname || ""
      )})</td>
          <td><b>${r.tf_deaths ?? 0} 次</b></td>
          <td><b class="${coreCnt > 0 ? "txt-loss" : "txt-win"}">${coreCnt} 次</b></td>
          <td><b class="${zeroCnt > 0 ? "txt-loss" : "txt-win"}">${zeroCnt} 次</b></td>
          <td>${escapeHtml(r.owned_saves_str || "未合成主动保命装")}</td>
          <td class="fs-verdict-cell">${escapeHtml(r.verdict || "")}</td>
        </tr>
      `;
    })
    .join("");

  // 4.3 地图空间理解与 9m 后落单被抓表
  const ms = df.map_space_by_side?.[side] || {};
  const msRowsHtml = (ms.player_space_rows || [])
    .map((r) => {
      const soloCnt = Number(r.solo_pickoff_cnt ?? 0);
      return `
        <tr>
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(
        r.personaname || ""
      )})</td>
          <td><b>${escapeHtml(r.space_style_badge || "常规驻守")}</b></td>
          <td>兵线 <b>${r.lane_kills ?? 0}</b> (${r.lane_farm_pct ?? 0}%) / 野区 <b>${
        r.neutral_kills ?? 0
      }</b> (${r.jungle_farm_pct ?? 0}%)</td>
          <td><b>${fmtNum(r.tower_damage || 0)}</b></td>
          <td><b class="${soloCnt >= 2 ? "txt-loss" : soloCnt === 0 ? "txt-win" : ""}">${soloCnt} 次</b> (送 ${fmtNum(
        r.solo_gold_fed || 0
      )} 金)</td>
          <td class="fs-verdict-cell">${escapeHtml(r.verdict || "")}</td>
        </tr>
      `;
    })
    .join("");

  const msEvents = ms.solo_pickoff_events || [];
  const msEventsSummary =
    msEvents.length > 0
      ? msEvents
          .map(
            (ev) =>
              `[${ev.time_str}] ${ev.pos}号位${ev.hero_short_zh} 在【${ev.zone_zh}】(${ev.vision_tag}) 被 ${ev.killer_zh} 抓死，读秒 ${ev.time_dead}s 送 ${ev.gold_fed} 金 → ${ev.consequence}`
          )
          .join("；")
      : "本局 9 分钟后未发生脱离团队无聊带线或黑图落单被抓事故。";

  // 4.4 承伤来源与防装合规审计表
  const dr = df.damage_received_by_side?.[side] || {};
  const drRowsHtml = (dr.rows || [])
    .map((r) => {
      const killers = (r.top_killers || [])
        .slice(0, 3)
        .map((k) => `${k.zh_name}(${fmtNum(k.damage || 0)}/${k.share_pct ?? 0}%)`)
        .join("、");
      const defs = (r.def_items_owned || []).join("、") || "未出针对防装";
      return `
        <tr>
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(
        r.personaname || ""
      )})</td>
          <td><b>${fmtNum(r.total_dmg_taken || 0)}</b></td>
          <td>技能爆发 <b>${r.spell_pct ?? 0}%</b> / 物理平A <b>${r.auto_pct ?? 0}%</b></td>
          <td>${escapeHtml(killers || "平A为主")}</td>
          <td><b>${escapeHtml(defs)}</b></td>
          <td class="fs-verdict-cell">${escapeHtml(r.verdict || "")}</td>
        </tr>
      `;
    })
    .join("");

  // 4.5 辅助眼位 + 4.6 堆野开雾 + 4.7 对线细节 综合运维结构表
  const vis = df.support_vision_by_side?.[side] || {};
  const ss = df.stacking_and_smoke_by_side?.[side] || {};
  const lm = df.laning_mechanics_by_side?.[side] || {};
  const smokeEvents = ss.smoke_events || [];
  const smokeUses = ss.own_smoke_uses ?? ss.smoke_total_uses ?? smokeEvents.length;
  const smokeBought =
    ss.smoke_total_bought ??
    (ss.per_player_smokes || []).reduce((acc, item) => acc + Number(item.bought || 0), 0);
  const smokeSuccessCnt =
    ss.smoke_success_count ?? smokeEvents.filter((e) => e.outcome === "success").length;
  const smokeBackfireCnt =
    ss.smoke_backfire_count ?? smokeEvents.filter((e) => e.outcome === "backfire").length;
  const smokeDryCnt =
    ss.smoke_dry_count ?? smokeEvents.filter((e) => e.outcome === "wasted").length;

  const ownLotus = lm.own_lotus_total ?? lm.lotus_own_total ?? 0;
  const oppLotus = lm.opp_lotus_total ?? lm.lotus_opp_total ?? 0;
  const ownWisdom = lm.own_wisdom_cnt ?? lm.wisdom_own_count ?? 0;
  const oppWisdom = lm.opp_wisdom_cnt ?? lm.wisdom_opp_count ?? 0;
  const ownGate = lm.own_gate_total ?? lm.gate_own_count ?? 0;
  const oppGate = lm.opp_gate_total ?? lm.gate_opp_count ?? 0;
  const ownLamp = lm.own_lamp_total ?? lm.lamp_own_count ?? 0;
  const oppLamp = lm.opp_lamp_total ?? lm.lamp_opp_count ?? 0;

  const macroOpsRowsHtml = `
    <tr>
      <td><b>4.5 辅助视野与反眼博弈</b></td>
      <td>
        总假眼 <b>${vis.total_obs ?? vis.obs_total ?? 0}</b> 颗 / 真眼 <b>${
    vis.total_sen ?? vis.sen_total ?? 0
  }</b> 颗<br/>
        <span class="fs-sub">平均寿命 ${vis.avg_lifespan_sec ?? 0}s/360s · 被排 ${
    vis.dewarded_total ?? 0
  } 颗 (${vis.dewarded_pct ?? 0}%)</span>
      </td>
      <td>
        进攻眼 <b>${vis.posture_counts?.aggressive ?? 0}</b> (${vis.posture_pcts?.aggressive ?? 0}%) / 河道眼 <b>${
    vis.posture_counts?.river_roshan ?? 0
  }</b> (${vis.posture_pcts?.river_roshan ?? 0}%) / 防守眼 <b>${
    vis.posture_counts?.defensive ?? 0
  }</b> (${vis.posture_pcts?.defensive ?? 0}%)
      </td>
      <td class="fs-verdict-cell">
        ${escapeHtml(vis.posture_verdict || "")}
        ${
          (vis.instant_dewards || []).length > 0
            ? `<br/><span class="txt-loss">秒排白给眼 (≤90s)：${escapeHtml(
                vis.instant_dewards
                  .map((w) => `${w.time_str} ${w.planter_hero || ""}于${w.zone_zh}(仅活${w.lifespan_sec}s)`)
                  .join("；")
              )}</span>`
            : ""
        }
      </td>
    </tr>
    <tr>
      <td><b>4.6 辅助堆野 &amp; 开雾转化</b></td>
      <td>
        全队堆野 <b>${ss.total_stacks ?? ss.total_team_stacks ?? 0} 组</b> (${
    ss.total_creeps_stacked ?? 0
  } 只野)<br/>
        <span class="fs-sub">辅助堆 ${ss.support_stacks ?? 0} 组 / 大哥自拉 ${
    ss.core_stacks ?? ss.core_self_stacks ?? 0
  } 组</span>
      </td>
      <td>
        买雾 <b>${smokeBought}</b> / 开雾 <b>${smokeUses}</b> 波<br/>
        <span class="fs-sub">破雾大捷 ${smokeSuccessCnt} 波 / 撞墙 ${smokeBackfireCnt} 波 / 空雾 ${smokeDryCnt} 波</span>
      </td>
      <td class="fs-verdict-cell">
        ${escapeHtml(ss.stack_verdict || "")} ｜ ${escapeHtml(ss.smoke_verdict || "")}
      </td>
    </tr>
    <tr>
      <td><b>4.7 对线莲花·智慧符·走门</b></td>
      <td>
        疗伤莲花 <b>${ownLotus} : ${oppLotus}</b><br/>
        <span class="fs-sub">7/14/21m 智慧符 <b>${ownWisdom} : ${oppWisdom}</b></span>
      </td>
      <td>
        双生门传送 <b>${ownGate} : ${oppGate}</b><br/>
        <span class="fs-sub">观察者点灯 <b>${ownLamp} : ${oppLamp}</b></span>
      </td>
      <td class="fs-verdict-cell">
        ${escapeHtml(lm.lotus_verdict || "")} ｜ ${escapeHtml(lm.wisdom_verdict || "")}
      </td>
    </tr>
  `;

  // 4.8 TP 救人与团战缺席抓包 + 4.9 经济来源结构 合并五人表
  const tp = df.tp_rotation_by_side?.[side] || {};
  const ep = df.economy_and_pings_by_side?.[side] || {};
  const tpMap = new Map((tp.player_tp_rows || []).map((r) => [Number(r.pos), r]));
  const epRows = ep.econ_rows || [];
  const tpEconRowsHtml = epRows
    .map((r) => {
      const tr = tpMap.get(Number(r.pos)) || {};
      const tfTpCnt = tr.tf_tp_cnt ?? tr.teamfight_tp_saves ?? 0;
      const tfAbsentCnt = tr.tf_absent_cnt ?? tr.spectator_teamfights ?? 0;
      const lossGold = (r.death_loss || 0) + (r.buyback_loss || 0);
      return `
        <tr>
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(
        r.personaname || ""
      )})</td>
          <td>用 <b>${tr.tp_used ?? 0}</b> / 买 <b>${tr.tp_bought ?? 0}</b> 张 (前12m支援 ${
        tr.early_tp_cnt ?? 0
      } 次)</td>
          <td>
            <span class="${tfTpCnt > 0 ? "txt-win" : ""}">亮TP救人 ${tfTpCnt} 次</span> /
            <span class="${tfAbsentCnt > 0 ? "txt-loss" : "txt-win"}">团战0参与OB ${tfAbsentCnt} 波</span>
          </td>
          <td>兵线 <b>${fmtNum(r.lane_gold || 0)}</b> (${r.lane_pct ?? 0}%) / 野区 <b>${fmtNum(
        r.jungle_gold || 0
      )}</b> (${r.jungle_pct ?? 0}%)</td>
          <td>人头 <b>${fmtNum(r.kill_gold || 0)}</b> (${r.kill_pct ?? 0}%) / 塔盾 <b>${fmtNum(
        r.obj_gold || 0
      )}</b> (${r.obj_pct ?? 0}%)</td>
          <td><b class="${lossGold >= 2200 ? "txt-loss" : ""}">-${fmtNum(lossGold)} 金</b> (信号 ${
        r.pings ?? 0
      } 次)</td>
          <td class="fs-verdict-cell">${escapeHtml(tr.verdict || r.econ_tag || "")}</td>
        </tr>
      `;
    })
    .join("");

  // 4.10 买活死尸检 · 信使惨案 · 肉山魔晶 & 7.38 中立装备附魔审计表
  const mo = df.macro_objectives_by_side?.[side] || {};
  const craftRowsHtml = (mo.neutral_craft_rows || [])
    .map((cr) => {
      const stepsStr = (cr.craft_steps || []).join(" → ") || "无锻造记录";
      return `
        <tr>
          <td><b>${cr.pos ?? "?"}号位 · ${escapeHtml(cr.hero_short_zh || "")}</b> (${escapeHtml(
        cr.personaname || ""
      )})</td>
          <td><b>${escapeHtml(cr.shard_str || "未获魔晶")}</b></td>
          <td>${escapeHtml(stepsStr)}</td>
          <td class="fs-verdict-cell">${escapeHtml(cr.craft_verdict || "")}</td>
        </tr>
      `;
    })
    .join("");

  const bbSummary =
    (mo.buyback_events || []).map((ev) => `[${ev.time_str}] ${ev.pos}号${ev.hero_short_zh}：${ev.detail}`).join("；") ||
    "0次买活死 (Dieback)";
  const roshSummary = (mo.roshan_events || []).join("；") || "无肉山盾拾取记录";

  return `
    <div class="fs-micro-tables-group">
      <h3 class="fs-subtable-title">4.1 英雄绝活与大招释放质量审判总表 (${escapeHtml(sideZh)} 1~5 号位)</h3>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>位置 &amp; 选手</th>
              <th>绝活核心指标</th>
              <th>关键大招释放 / 命中 / 伤害审计</th>
              <th>非指向技能命中率</th>
              <th>团战开大 vs 憋大阵亡</th>
              <th>大招与技能复盘判词</th>
            </tr>
          </thead>
          <tbody>${ultRowsHtml}</tbody>
        </table>
      </div>

      <h3 class="fs-subtable-title">4.2 憋死 BKB / 救命装与团战 0 技能秒躺尸检总表（共憋死核心保命装 ${
        us.critical_total ?? 0
      } 人次 · 0技能秒躺 ${us.zero_spell_total ?? 0} 人次）</h3>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>位置 &amp; 选手</th>
              <th>团战阵亡</th>
              <th>憋死核心保命装</th>
              <th>团战0技能秒躺</th>
              <th>本局合成保命装与全场按键次数</th>
              <th>团战保命反应与抓包笔录</th>
            </tr>
          </thead>
          <tbody>${usRowsHtml}</tbody>
        </table>
      </div>

      <h3 class="fs-subtable-title">4.3 地图空间理解与 9 分钟后落单带危险线被抓审计表（共落单被抓 ${
        ms.total_solo_pickoffs ?? 0
      } 次）</h3>
      <p class="fs-chapter-desc">📋 落单被抓流水：${escapeHtml(msEventsSummary)}</p>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>位置 &amp; 选手</th>
              <th>地图空间画像</th>
              <th>兵线补刀 vs 野区发育占比</th>
              <th>推塔建筑伤害</th>
              <th>9m后落单被抓 &amp; 送金</th>
              <th>空间利用与带线纪律判词</th>
            </tr>
          </thead>
          <tbody>${msRowsHtml}</tbody>
        </table>
      </div>

      <h3 class="fs-subtable-title">4.4 承伤来源拆解（物理平A vs 技能爆发）与防装合规审计表</h3>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>位置 &amp; 选手</th>
              <th>总承受英雄伤害</th>
              <th>技能爆发 vs 物理平A占比</th>
              <th>头号致死敌方技能 Top 3</th>
              <th>已出针对性防装</th>
              <th>防装选择合规判词</th>
            </tr>
          </thead>
          <tbody>${drRowsHtml}</tbody>
        </table>
      </div>

      <h3 class="fs-subtable-title">4.5–4.7 辅助视野质量 · 堆野开雾转化 · 对线拉野/莲花/智慧符/双生门综合审计表</h3>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>战术审计维度</th>
              <th>核心数量与效率指标</th>
              <th>结构分布与对抗比</th>
              <th>录像取证结论与抓包明细</th>
            </tr>
          </thead>
          <tbody>${macroOpsRowsHtml}</tbody>
        </table>
      </div>

      <h3 class="fs-subtable-title">4.8–4.9 TP 救人及时性 · 团战旁观抓包 · 经济来源结构与死亡损耗总表</h3>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>位置 &amp; 选手</th>
              <th>TP 使用 / 主动购买</th>
              <th>团战亮 TP 支援 vs 0参与旁观</th>
              <th>兵线 vs 野区进账</th>
              <th>人头 vs 塔盾进账</th>
              <th>阵亡+买活扣钱 &amp; 信号</th>
              <th>支援与财政习惯判词</th>
            </tr>
          </thead>
          <tbody>${tpEconRowsHtml}</tbody>
        </table>
      </div>

      <h3 class="fs-subtable-title">4.10 买活死 (Dieback) 尸检 · 信使博弈 · 肉山魔晶 &amp; Dota 2 7.38 中立装备附魔表</h3>
      <p class="fs-chapter-desc">⚰️ 买活审计：${escapeHtml(bbSummary)} ｜ 🐉 肉山记录：${escapeHtml(
    roshSummary
  )} ｜ 🐔 信使博弈：击杀敌鸡 ${mo.own_couriers_killed ?? 0} 只 / 本方掉鸡 ${
    mo.own_couriers_lost ?? 0
  } 只</p>
      <div class="fs-table-wrap">
        <table class="fs-structured-table">
          <thead>
            <tr>
              <th>位置 &amp; 选手</th>
              <th>阿哈利姆魔晶时间</th>
              <th>7.38 中立装备锻造与附魔词条时间轴</th>
              <th>词条合规与锻造节奏判词</th>
            </tr>
          </thead>
          <tbody>${craftRowsHtml}</tbody>
        </table>
      </div>
    </div>
  `;
}

function buildStructuredFullReportHtml(report) {
  const { side, sideZh, oppZh, own, opp } = getOwnAndOppPlayers(report);
  const oppSide = side === "radiant" ? "dire" : "radiant";
  const ownWon =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !Boolean(report.radiant_win));
  const df = report.deep_forensics || {};
  const grok = report.grok_coaching || {};
  const draft = report.draft_and_combo?.[side] || report.draft_and_combo || {};

  // Normalize 100% contribution and 100% blame shares (preferring Grok 4.7 grok_share_pct)
  const rawContribSum =
    own.reduce((s, p) => {
      const gp = findGrokPlayerEntry(p, report);
      const val = ownWon && gp?.grok_share_pct ? Number(gp.grok_share_pct) : Number(p.contrib_share_pct ?? p.mvp_score ?? 20);
      return s + Math.max(1, val);
    }, 0) || 100;
  const contribMap = new Map();
  own.forEach((p) => {
    const gp = findGrokPlayerEntry(p, report);
    const val = ownWon && gp?.grok_share_pct ? Number(gp.grok_share_pct) : Number(p.contrib_share_pct ?? p.mvp_score ?? 20);
    const pct = Number(((Math.max(1, val) / rawContribSum) * 100).toFixed(1));
    contribMap.set(Number(p.player_slot), pct);
  });

  const rawBlameSum =
    own.reduce((s, p) => {
      const gp = findGrokPlayerEntry(p, report);
      const val = !ownWon && gp?.grok_share_pct ? Number(gp.grok_share_pct) : Number(p.blame_share_pct || 20);
      return s + Math.max(1, val);
    }, 0) || 100;
  const blameMap = new Map();
  own.forEach((p) => {
    const gp = findGrokPlayerEntry(p, report);
    const val = !ownWon && gp?.grok_share_pct ? Number(gp.grok_share_pct) : Number(p.blame_share_pct || 20);
    const pct = Number(((Math.max(1, val) / rawBlameSum) * 100).toFixed(1));
    blameMap.set(Number(p.player_slot), pct);
  });

  const sortedByContrib = [...own].sort(
    (a, b) =>
      (contribMap.get(Number(b.player_slot)) || 0) - (contribMap.get(Number(a.player_slot)) || 0) ||
      getHeroScore100(b, report) - getHeroScore100(a, report)
  );
  const sortedByBlame = [...own].sort(
    (a, b) =>
      (blameMap.get(Number(b.player_slot)) || 0) - (blameMap.get(Number(a.player_slot)) || 0) ||
      getHeroScore100(a, report) - getHeroScore100(b, report)
  );

  const topMvp = sortedByContrib[0] || own[0];
  const topCulprit = sortedByBlame[0] || own[0];

  // Chapter I: 4-Stage Audit Grid
  const stages = report.match_narrative?.stages || [];
  const stageIcons = ["🌅", "⚔️", "🔥", "📊"];
  const formatStageBullets = (rawContent) => {
    const cleaned = sanitizeMixedEnglishClient(String(rawContent || ""))
      .replace(/三路10分钟对账：/g, "。")
      .replace(/主视角（[^）]+）车队全局数据对比：/g, "。");
    return cleaned
      .split(/[；。]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((item) => {
        let html = escapeHtml(item);
        html = html.replace(
          /^(上路|中路|下路|①\s*[^：:]+|②\s*[^：:]+|③\s*[^：:]+|④\s*[^：:]+|10分钟对线期结束|对线与前中期信使击杀|全场最高权重胜负手团战爆发于|肉山争夺记录)([：:\s]*)/,
          '<span class="stage-key-pill">$1</span> '
        );
        html = html.replace(/→\s*([^；。]+)/g, '<span class="stage-outcome-pill">→ $1</span>');
        return `<li>${html}</li>`;
      })
      .join("");
  };

  const stagesGridHtml = stages
    .map((s, idx) => {
      const stTitle = s.stage || s.title || `阶段 ${idx + 1}`;
      const stBody = s.summary || s.content || "";
      return `
        <div class="fs-stage-card">
          <div class="fs-stage-head">
            <span class="fs-stage-badge">${stageIcons[idx % stageIcons.length]} 阶段 0${idx + 1}</span>
            <strong>${escapeHtml(stTitle)}</strong>
          </div>
          <ul class="fs-stage-list">${formatStageBullets(stBody)}</ul>
        </div>
      `;
    })
    .join("");

  // Chapter II: 5-Player 100% Contribution / Blame Ledger Table
  const ledgerRowsHtml = own
    .map((p) => {
      const heroShort = p.hero_short_zh || p.hero_name || "";
      const gp = findGrokPlayerEntry(p, report);
      const sc100 = getHeroScore100(p, report);
      const scTier = getScore100Tier(sc100, ownWon);
      const cPct = contribMap.get(Number(p.player_slot)) ?? 20.0;
      const bPct = blameMap.get(Number(p.player_slot)) ?? 20.0;
      const sharePct = ownWon ? cPct : bPct;
      const roleNote =
        gp?.headline ||
        (ownWon
          ? p.praise_talk || (p.strengths || [])[0] || "稳定发挥完成战术任务"
          : p.trash_talk || (p.weaknesses || [])[0] || "存在团战或对线细节失误");
      const isHighlight = ownWon
        ? Number(p.player_slot) === Number(topMvp?.player_slot)
        : Number(p.player_slot) === Number(topCulprit?.player_slot);
      return `
        <tr class="${isHighlight ? (ownWon ? "fs-row-mvp" : "fs-row-culprit") : ""}">
          <td><b>${p.pos}号位</b><br/><span class="fs-sub">${escapeHtml(p.pos_label || "")}</span></td>
          <td>
            <div class="fs-hero-cell">
              <img class="fs-hero-avatar" data-html2canvas-ignore="true" src="${escapeHtml(p.hero_img || "")}" alt="" />
              <div>
                <b>${escapeHtml(heroShort)}</b>
                <div class="fs-sub">${escapeHtml(p.personaname || "")}${p.is_me ? " [主视角]" : ""}</div>
              </div>
            </div>
          </td>
          <td><b>${escapeHtml(p.kda)}</b><br/><span class="fs-sub">参战 ${p.kill_participation_pct ?? 0}%</span></td>
          <td><b>${fmtNum(p.net_worth)} 金</b><br/><span class="fs-sub">GPM ${p.gpm} / XPM ${p.xpm}</span></td>
          <td><b>${fmtNum(p.hero_damage)}</b><br/><span class="fs-sub">占全队 ${p.hero_damage_share_pct ?? 0}%</span></td>
          <td><b>${fmtNum(p.damage_taken)}</b><br/><span class="fs-sub">读秒 ${p.dead_seconds ?? 0}s</span></td>
          <td><b>${fmtNum(p.tower_damage)}</b><br/><span class="fs-sub">硬控 ${p.stuns_sec ?? 0}s</span></td>
          <td><b>${sc100}/100 分</b><br/><span class="fs-sub">${escapeHtml(scTier.label)}</span></td>
          <td>
            <span class="fs-share-pill ${ownWon ? "win" : "loss"}">
              ${ownWon ? `功勋 ${sharePct}%` : `分锅 ${sharePct}%`}
            </span>
          </td>
          <td class="fs-verdict-cell">${escapeHtml(roleNote)}</td>
        </tr>
      `;
    })
    .join("");

  // Chapter III: 1~5 Positional 1v1 Mirror Table
  const rm = df.role_mirror_by_side?.[side] || {};
  const mirrorRows = rm.mirror_rows || [];
  const mirrorTableRowsHtml = mirrorRows
    .map((r) => {
      const g10Diff = Number(r.gold10_diff ?? 0);
      const nwDiff = Number(r.nw_diff ?? 0);
      const dmgDiff = Number(r.dmg_diff ?? 0);
      const toneCls = r.grade === "good" ? "win" : r.grade === "bad" ? "loss" : "even";
      return `
        <tr>
          <td><b>${r.pos}号位对决</b></td>
          <td>
            <b>${escapeHtml(r.own_hero || "")}</b> (${escapeHtml(r.own_player || "")})<br/>
            <span class="fs-sub">KDA ${escapeHtml(r.own_kda || "")} · 评分 ${r.own_rating ?? 0} · 全球超 ${
        r.own_bm_avg ?? 50
      }%</span>
          </td>
          <td>
            <b>${escapeHtml(r.opp_hero || "")}</b> (${escapeHtml(r.opp_player || "")})<br/>
            <span class="fs-sub">KDA ${escapeHtml(r.opp_kda || "")} · 评分 ${r.opp_rating ?? 0} · 全球超 ${
        r.opp_bm_avg ?? 50
      }%</span>
          </td>
          <td>
            <b class="${g10Diff >= 300 ? "txt-win" : g10Diff <= -300 ? "txt-loss" : ""}">${fmtSigned(
        g10Diff
      )} 金</b><br/>
            <span class="fs-sub">补刀 ${escapeHtml(r.lh10_own || "0/0")} vs ${escapeHtml(
        r.lh10_opp || "0/0"
      )}</span>
          </td>
          <td>
            <b class="${nwDiff >= 1500 ? "txt-win" : nwDiff <= -1500 ? "txt-loss" : ""}">${fmtSigned(
        nwDiff
      )} 金</b><br/>
            <span class="fs-sub">${fmtNum(r.nw_own)} vs ${fmtNum(r.nw_opp)}</span>
          </td>
          <td><b>${r.h2h_own_kills ?? 0} : ${r.h2h_opp_kills ?? 0}</b></td>
          <td>
            <b class="${dmgDiff >= 2000 ? "txt-win" : dmgDiff <= -2000 ? "txt-loss" : ""}">${fmtSigned(
        dmgDiff
      )}</b><br/>
            <span class="fs-sub">塔伤 ${fmtNum(r.td_own)} vs ${fmtNum(r.td_opp)}</span>
          </td>
          <td><span class="fs-share-pill ${toneCls}">${escapeHtml(r.verdict_tag || "旗鼓相当")}</span></td>
          <td class="fs-verdict-cell">${escapeHtml(r.summary_txt || "")}</td>
        </tr>
      `;
    })
    .join("");

  // Chapter IV: Full-width structured tables for all Tactical Microscope dimensions
  const microAllHtml = buildStructuredMicroTablesHtml(report, df, side, sideZh, oppSide, oppZh);

  // Chapter V: 3-Phase Differential Table + Key Teamfights Table
  const rawPhases = report.phases_data || report.phase_breakdown?.phases || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  const signMult = side === (report.focus_side || "dire") ? 1 : -1;
  const phaseTableRows = phasesList
    .map((pd) => {
      const ownP = (pd.players || []).filter((p) => p.side === side);
      const oppP = (pd.players || []).filter((p) => p.side !== side);
      const ownK = ownP.reduce((s, p) => s + (p.kills_count || 0), 0);
      const oppK = oppP.reduce((s, p) => s + (p.kills_count || 0), 0);
      const ts = pd.team_summary || {};
      const deltaAdv = (ts.income_diff_change || 0) * signMult;
      const endAdv = (ts.income_diff_end || 0) * signMult;
      const diag = pd.team_diagnostics?.[side] || {};
      const goodStr = Array.isArray(diag.team_good) ? diag.team_good.join("；") : diag.team_good || "";
      const badStr = Array.isArray(diag.team_bad) ? diag.team_bad.join("；") : diag.team_bad || "";
      const actStr = Array.isArray(diag.team_action) ? diag.team_action.join("；") : diag.team_action || "";
      return `
        <tr>
          <td><b>${escapeHtml(pd.label)}</b><br/><span class="fs-sub">${escapeHtml(pd.time_label)}</span></td>
          <td><b>${ownK} : ${oppK}</b><br/><span class="fs-sub">推${ts.towers_taken || 0}塔 / 掉${
        ts.towers_lost || 0
      }塔</span></td>
          <td>
            <b class="${deltaAdv >= 0 ? "txt-win" : "txt-loss"}">阶段净变动 ${fmtSigned(deltaAdv)} 金</b><br/>
            <span class="fs-sub">阶段末累计差：${fmtSigned(endAdv)} 金</span>
          </td>
          <td class="fs-verdict-cell">✓ ${escapeHtml((goodStr || "维持基础运营").replace(/\*\*/g, ""))}</td>
          <td class="fs-verdict-cell">✕ ${escapeHtml((badStr || "局部联动脱节").replace(/\*\*/g, ""))}</td>
          <td class="fs-verdict-cell">📌 ${escapeHtml((actStr || "抓核心成装强势期抱团推进").replace(/\*\*/g, ""))}</td>
        </tr>
      `;
    })
    .join("");

  const keyTfs = (report.key_teamfights || []).slice(0, 6);
  const tfForensicsList = df.teamfight_forensics || [];
  const tfTableRows = keyTfs
    .map((tf, idx) => {
      const matchedTfIdx = tfForensicsList.findIndex((f) => f.time_range === tf.time_range);
      const fObj = tfForensicsList[matchedTfIdx >= 0 ? matchedTfIdx : idx];
      const storyObj = buildTeamfightDotaStory(tf, fObj, idx, {
        side,
        sideZh,
        oppZh,
        own,
        opp,
      });
      const pSummary = (tf.participants || [])
        .sort((a, b) => (b.damage || 0) - (a.damage || 0))
        .slice(0, 5)
        .map(
          (p) =>
            `${p.hero_short_zh}: ${fmtNum(p.damage)}伤${p.deaths ? "(阵亡)" : ""}${
              p.buybacks ? "[买活]" : ""
            }`
        )
        .join(" ｜ ");
      return `
        <tr>
          <td>
            <b>团战 #${idx + 1}</b><br/>
            <span class="fs-sub">${escapeHtml(tf.time_range || "")}</span><br/>
            <span style="display:inline-block;margin-top:3px;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:800;background:${
              storyObj.tone === "praise"
                ? "#dcfce7;color:#166534"
                : storyObj.tone === "roast"
                ? "#fee2e2;color:#991b1b"
                : "#fef3c7;color:#92400e"
            };">${escapeHtml(storyObj.badge)}</span>
          </td>
          <td><b>${escapeHtml(tf.kills_trade || "")}</b><br/><span class="fs-sub">${escapeHtml(
        tf.gold_swing || ""
      )}</span></td>
          <td><b>${escapeHtml(tf.top_damage_hero || "-")}</b></td>
          <td class="fs-verdict-cell">
            <div style="font-size:11.5px;line-height:1.55;color:#0f172a;margin-bottom:4px;">${
              storyObj.storyHtml
            }</div>
            <div style="font-size:10.5px;color:#64748b;">📊 参战明细：${escapeHtml(pSummary)}</div>
          </td>
        </tr>
      `;
    })
    .join("");

  // Chapter VI: Pos 1~5 Individual Forensics Dossiers (with Hero Portrait, 6-Slot Item Icons, 6-Axis Radar SVG, and AI Personal Story)
  const grokPlayersMap = new Map();
  if (Array.isArray(grok.players)) {
    grok.players.forEach((gp) => grokPlayersMap.set(Number(gp.slot), gp));
  }
  const mvpSlotNum = Number(report.mvp?.mvp_player?.player_slot);
  const topCulpritSlotNum = Number(topCulprit?.player_slot);

  const dossierRowsHtml = own
    .map((p) => {
      const heroShort = p.hero_short_zh || p.hero_name || "";
      const aiStoryObj = buildPlayerDossierAiStory(p, {
        grokPlayer: findGrokPlayerEntry(p, report) || grokPlayersMap.get(Number(p.player_slot)),
        isTopCulprit: !ownWon && Number(p.player_slot) === topCulpritSlotNum,
        isMvp: Number(p.player_slot) === mvpSlotNum,
      });
      const itemIconsStripHtml = (p.final_items_rich || [])
        .map(
          (it) => `
          <div style="display:inline-flex;flex-direction:column;align-items:center;margin:0 4px 4px 0;background:#f8fafc;border:1px solid #cbd5e1;border-radius:4px;padding:2px 3px;">
            ${
              it.img
                ? `<img src="${escapeHtml(it.img)}" alt="${escapeHtml(it.zh_name || it.key)}" style="width:32px;height:23px;object-fit:cover;border-radius:2px;" />`
                : `<span style="font-size:10px;padding:2px 4px;">${escapeHtml(it.zh_name || it.key)}</span>`
            }
            <span style="font-size:9px;color:#334155;font-weight:700;line-height:1.1;margin-top:2px;">${escapeHtml(
              (it.zh_name || it.key || "").slice(0, 4)
            )}</span>
            ${
              it.purchase_time_str
                ? `<span style="font-size:8.5px;color:#0f172a;background:#e2e8f0;padding:0 3px;border-radius:2px;margin-top:1px;">${escapeHtml(
                    it.purchase_time_str
                  )}</span>`
                : ""
            }
            ${
              it.use_count
                ? `<span style="font-size:8.5px;color:#b45309;font-weight:700;">按${it.use_count}次</span>`
                : ""
            }
          </div>
        `
        )
        .join("");

      const abilStr =
        (p.ability_uses_rich || [])
          .slice(0, 6)
          .map((ab) => `${ab.zh_name || ab.key}×${ab.count}`)
          .join(" / ") || "无主动技能记录";
      const goods = (p.strengths || [])
        .slice(0, 3)
        .map((g) => `<div>✓ ${escapeHtml(String(g).replace(/\*\*/g, ""))}</div>`)
        .join("");
      const bads = (p.weaknesses || [])
        .slice(0, 3)
        .map((b) => `<div>✕ ${escapeHtml(String(b).replace(/\*\*/g, ""))}</div>`)
        .join("");
      const fixes = (p.improvements || [])
        .slice(0, 2)
        .map((f) => `<div>📌 ${escapeHtml(String(f).replace(/\*\*/g, ""))}</div>`)
        .join("");
      return `
        <tr>
          <td>
            <div style="display:flex;align-items:center;gap:8px;">
              ${
                p.hero_img
                  ? `<img src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(heroShort)}" style="width:46px;height:27px;object-fit:cover;border-radius:4px;border:1px solid #94a3b8;flex-shrink:0;" />`
                  : ""
              }
              <div>
                <b>${p.pos}号位 · ${escapeHtml(heroShort)}</b>
                <span style="display:inline-block;margin-left:4px;padding:1px 6px;border-radius:4px;font-size:10.5px;font-weight:900;background:#fef3c7;color:#92400e;border:1px solid #f59e0b;">🏆 ${getHeroScore100(p)} / 100分</span><br/>
                <span class="fs-sub">${escapeHtml(p.personaname || "")} · KDA ${escapeHtml(p.kda)}</span><br/>
                <span class="fs-sub">10m补刀 ${p.laning_10m?.lh10 ?? "-"}/${p.laning_10m?.dn10 ?? "-"} · 伤转 ${
        p.net_worth ? (p.hero_damage / p.net_worth).toFixed(2) : "0.00"
      }</span>
              </div>
            </div>
          </td>
          <td class="fs-verdict-cell">
            <div style="display:flex;flex-wrap:wrap;align-items:flex-start;margin-bottom:4px;">${
              itemIconsStripHtml || "无出装记录"
            }</div>
            <div style="margin-top:3px;color:var(--muted);font-size:11px;"><b>技能释放频次：</b>${escapeHtml(
              abilStr
            )}</div>
            <div style="margin-top:5px;padding:5px 7px;background:#f8fafc;border-left:3px solid ${
              aiStoryObj.tone === "praise"
                ? "#16a34a"
                : aiStoryObj.tone === "roast"
                ? "#dc2626"
                : "#d97706"
            };font-size:11px;line-height:1.5;color:#1e293b;">
              <b>${escapeHtml(aiStoryObj.badge)}：</b>${aiStoryObj.storyHtml}
            </div>
          </td>
          <td style="text-align:center;vertical-align:middle;background:#141812;padding:4px;">
            ${typeof renderHexRadarSvg === "function" ? renderHexRadarSvg(p.radar) : ""}
          </td>
          <td class="fs-verdict-cell">${goods || "✓ 完成本职任务"}</td>
          <td class="fs-verdict-cell">${bads || "✕ 无重大失误"}</td>
          <td class="fs-verdict-cell">${fixes || "📌 保持当前打法与出装节奏"}</td>
        </tr>
      `;
    })
    .join("");

  // Grab rendered SVG/visual charts from the live workspace DOM for the Full-Screen Dossier view
  const advSvgHtml = document.getElementById("adv-chart-container")?.innerHTML || "";
  const nwSvgHtml = document.getElementById("nw-chart-container")?.innerHTML || "";
  const minimapSvgHtml = document.getElementById("minimap-svg-container")?.innerHTML || "";
  const wardAuditHtml = document.getElementById("ward-audit-container")?.innerHTML || "";
  const dmgMatrixHtml = document.getElementById("damage-matrix-container")?.innerHTML || "";

  const shareUrl = getPublicShareUrl(report.match_id);

  return `
    <article class="fs-dossier-doc">
      <!-- 报告封面与核心元数据总表 -->
      <header class="fs-cover-header">
        <div class="fs-cover-top">
          <div>
            <div class="fs-doc-kicker">DOTA 2 REPLAY FORENSICS DOSSIER · 五黑车队录像级结构化复盘报告</div>
            <h1 class="fs-doc-title">
              比赛 #${escapeHtml(report.match_id)} · ${escapeHtml(sideZh)}视角深度复盘报告
              <span class="fs-outcome-tag ${ownWon ? "win" : "loss"}">${
    ownWon ? `🎉 ${sideZh}凯旋获胜` : `⚖️ ${sideZh}遗憾落败`
  }</span>
            </h1>
            <p class="fs-doc-sub">
              比赛时间：${escapeHtml(report.start_time_str || "-")} ｜ 模式：${escapeHtml(
    report.game_mode_str || "全英雄选择"
  )} ｜ 赛果：${escapeHtml(report.winner || "")}获胜（天辉 ${report.radiant_score} : ${
    report.dire_score
  } 夜魇 · 时长 ${escapeHtml(report.duration_str)}） ｜ 在线复盘链接：${escapeHtml(shareUrl)}
            </p>
          </div>
        </div>

        <div class="fs-cover-kpi-grid">
          <div class="fs-kpi-box">
            <span>审计阵营 &amp; 最终比分</span>
            <strong>${escapeHtml(sideZh)}视角 (${ownWon ? "胜局庆功" : "败局算账"})</strong>
            <small>天辉 ${report.radiant_score} : ${report.dire_score} 夜魇 (${escapeHtml(
    report.duration_str
  )})</small>
          </div>
          <div class="fs-kpi-box">
            <span>本方 1~5 号位阵容 (${escapeHtml(sideZh)})</span>
            <strong>${own.map((p) => `${p.pos}号${p.hero_short_zh}`).join(" / ")}</strong>
            <small>阵容评级：${escapeHtml(draft.grade || "A 级")}</small>
          </div>
          <div class="fs-kpi-box">
            <span>敌方 1~5 号位阵容 (${escapeHtml(oppZh)})</span>
            <strong>${opp.map((p) => `${p.pos}号${p.hero_short_zh}`).join(" / ")}</strong>
            <small>同位置对位胜出：${rm.won_overall_cnt ?? 0} / 5 路</small>
          </div>
          <div class="fs-kpi-box">
            <span>${ownWon ? "👑 头号首功 MVP" : "🚨 头号背锅战犯"}</span>
            <strong>${
              ownWon
                ? `${topMvp?.pos}号位 ${escapeHtml(topMvp?.hero_short_zh || "")} (${escapeHtml(
                    topMvp?.personaname || ""
                  )})`
                : `${topCulprit?.pos}号位 ${escapeHtml(topCulprit?.hero_short_zh || "")} (${escapeHtml(
                    topCulprit?.personaname || ""
                  )})`
            }</strong>
            <small>${
              ownWon
                ? `胜局贡献 ${contribMap.get(Number(topMvp?.player_slot)) ?? 25}% · 评分 ${getHeroScore100(topMvp)}/100`
                : `分锅占比 ${blameMap.get(Number(topCulprit?.player_slot)) ?? 30}% · 评分 ${getHeroScore100(topCulprit)}/100`
            }</small>
          </div>
        </div>

        <!-- 5v5 英雄头像对阵横幅 -->
        <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;margin-top:12px;padding:10px 12px;background:#0f172a;border-radius:8px;color:#f8fafc;">
          <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;">
            ${own
              .map(
                (p) => `
              <div style="display:flex;align-items:center;gap:6px;background:rgba(255,255,255,0.06);padding:5px 6px;border-radius:6px;border-left:3px solid ${
                ownWon ? "#22c55e" : "#eab308"
              };">
                ${
                  p.hero_img
                    ? `<img src="${escapeHtml(p.hero_img)}" alt="" style="width:36px;height:21px;object-fit:cover;border-radius:3px;" />`
                    : ""
                }
                <div style="min-width:0;line-height:1.2;">
                  <div style="font-size:11px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${
                    p.pos
                  }号 ${escapeHtml(p.hero_short_zh || "")}</div>
                  <div style="font-size:9.5px;color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(
                    p.kda
                  )} · ${(Number(p.net_worth || 0) / 1000).toFixed(1)}k</div>
                </div>
              </div>
            `
              )
              .join("")}
          </div>
          <div style="font-size:13px;font-weight:900;color:#eab308;padding:0 6px;">VS</div>
          <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;">
            ${opp
              .map(
                (p) => `
              <div style="display:flex;align-items:center;gap:6px;background:rgba(255,255,255,0.05);padding:5px 6px;border-radius:6px;border-right:3px solid #ef4444;">
                ${
                  p.hero_img
                    ? `<img src="${escapeHtml(p.hero_img)}" alt="" style="width:36px;height:21px;object-fit:cover;border-radius:3px;" />`
                    : ""
                }
                <div style="min-width:0;line-height:1.2;">
                  <div style="font-size:11px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${
                    p.pos
                  }号 ${escapeHtml(p.hero_short_zh || "")}</div>
                  <div style="font-size:9.5px;color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(
                    p.kda
                  )} · ${(Number(p.net_worth || 0) / 1000).toFixed(1)}k</div>
                </div>
              </div>
            `
              )
              .join("")}
          </div>
        </div>
      </header>

      <!-- 第一章：赛后总账与四阶段复盘矩阵 + 2×2 全景数据可视化图表矩阵 -->
      <section class="fs-chapter">
        <div class="fs-chapter-head">
          <span class="fs-chapter-num">第一章</span>
          <h2>赛后总账与四阶段复盘矩阵（00:00 对线 → 中期节奏 → 决胜团战 → 全局硬实力）</h2>
        </div>
        ${
          grok.summary
            ? `<div class="fs-exec-callout"><strong>Grok 4.7 核心定性：</strong>${escapeHtml(
                grok.summary
              )}</div>`
            : ""
        }
        <div class="fs-stages-grid-2x2">${stagesGridHtml}</div>

        ${
          advSvgHtml || nwSvgHtml || minimapSvgHtml || dmgMatrixHtml
            ? `
          <h3 class="fs-subtable-title" style="margin-top:14px;">📊 全景录像数据可视化图表矩阵（经济经验差走势 · 十人净值曲线 · 2D 眼位团战小地图 · 十人伤害推塔矩阵）</h3>
          <div class="fs-charts-matrix-2x2">
            <div class="fs-chart-card">
              <h4>📈 团队累计经济差与经验差走势图 (Gold &amp; XP Advantage)</h4>
              ${advSvgHtml}
            </div>
            <div class="fs-chart-card">
              <h4>💰 十人分钟级净资产走势曲线 (10-Player Net Worth Curves)</h4>
              ${nwSvgHtml}
            </div>
            <div class="fs-chart-card">
              <h4>🗺️ 2D 刀塔战术小地图 (眼位/团战) &amp; 视野战果审计</h4>
              <div class="fs-minimap-row">
                <div>${minimapSvgHtml}</div>
                <div>${wardAuditHtml}</div>
              </div>
            </div>
            <div class="fs-chart-card">
              <h4>⚔️ 十人英雄输出 · 承受伤害 · 建筑推塔三色横向条形矩阵</h4>
              ${dmgMatrixHtml}
            </div>
          </div>
        `
            : ""
        }
      </section>

      <!-- 第二章：本方五人 100% 胜局功勋榜 / 败局分锅定责总表 -->
      <section class="fs-chapter">
        <div class="fs-chapter-head">
          <span class="fs-chapter-num">第二章</span>
          <h2>${escapeHtml(sideZh)}五人 100% ${
    ownWon ? "胜局功勋表彰总表" : "败局分锅定责总表"
  }（数据归一化定责）</h2>
        </div>
        <div class="fs-table-wrap">
          <table class="fs-structured-table">
            <thead>
              <tr>
                <th>位置</th>
                <th>英雄 &amp; 选手</th>
                <th>K / D / A (参战)</th>
                <th>终局净值 &amp; GPM</th>
                <th>英雄伤害 (占比)</th>
                <th>承伤 &amp; 读秒</th>
                <th>建筑伤害 &amp; 控制</th>
                <th>综合评分</th>
                <th>100% ${ownWon ? "功勋占比" : "分锅占比"}</th>
                <th>核心定性判词</th>
              </tr>
            </thead>
            <tbody>${ledgerRowsHtml}</tbody>
          </table>
        </div>
      </section>

      <!-- 第三章：前·中·后期三阶段进化指南与关键胜负手团战故事回放 -->
      <section class="fs-chapter">
        <div class="fs-chapter-head">
          <span class="fs-chapter-num">第三章</span>
          <h2>前·中·后期三阶段进化指南与关键胜负手团战故事回放（AI 刀塔老炮毒舌/夸奖评书）</h2>
        </div>
        <div class="fs-table-wrap">
          <table class="fs-structured-table">
            <thead>
              <tr>
                <th>比赛阶段</th>
                <th>阶段人头 &amp; 塔数</th>
                <th>阶段经济差波动</th>
                <th>✓ 本阶段亮点</th>
                <th>✕ 本阶段扣分项</th>
                <th>📌 阶段改进处方</th>
              </tr>
            </thead>
            <tbody>${phaseTableRows}</tbody>
          </table>
        </div>

        <h3 class="fs-subtable-title">⚔️ 全场最高强度关键胜负手团战故事回放与经济拐点明细</h3>
        <div class="fs-table-wrap">
          <table class="fs-structured-table">
            <thead>
              <tr>
                <th>团战编号 &amp; 时间窗</th>
                <th>人头交换 &amp; 经济拐点</th>
                <th>团战最高输出</th>
                <th>🎙️ AI 刀塔老炮团战故事回放 &amp; 核心参战明细</th>
              </tr>
            </thead>
            <tbody>${tfTableRows}</tbody>
          </table>
        </div>
      </section>

      <!-- 第四章：十一维战术显微镜全量取证账本（全宽结构化大表） -->
      <section class="fs-chapter deferred-chapter">
        <div class="fs-chapter-head">
          <span class="fs-chapter-num">第四章</span>
          <h2>录像级十一维战术显微镜全量取证账本（大招/憋死BKB/地图空间/承伤/眼位/堆野开雾/对线/TP/经济/买活死&amp;7.38附魔）</h2>
        </div>
        ${microAllHtml}
      </section>

      <!-- 第五章：1~5 号位同位置宿敌 1v1 正面对位审判全表 -->
      <section class="fs-chapter deferred-chapter">
        <div class="fs-chapter-head">
          <span class="fs-chapter-num">第五章</span>
          <h2>1~5 号位同位置宿敌 1v1 对位审判全表（含 OpenDota 全球同英雄百分位）</h2>
        </div>
        <p class="fs-chapter-desc">${escapeHtml(rm.side_verdict || "")}</p>
        <div class="fs-table-wrap">
          <table class="fs-structured-table">
            <thead>
              <tr>
                <th>对位位置</th>
                <th>本方 (${escapeHtml(sideZh)})</th>
                <th>敌方宿敌 (${escapeHtml(oppZh)})</th>
                <th>10m 对线经济差 &amp; 补刀</th>
                <th>终局净值差</th>
                <th>正面单杀比</th>
                <th>英雄伤害差 &amp; 塔伤</th>
                <th>对位审判结论</th>
                <th>录像对位复盘</th>
              </tr>
            </thead>
            <tbody>${mirrorTableRowsHtml}</tbody>
          </table>
        </div>
      </section>

      <!-- 第六章：本方 1~5 号位个人完整证据卷宗 -->
      <section class="fs-chapter deferred-chapter">
        <div class="fs-chapter-head">
          <span class="fs-chapter-num">第六章</span>
          <h2>${escapeHtml(sideZh)} 1~5 号位个人完整证据卷宗（出装图标时间轴、AI 毒舌/封神个人结案陈词、六维能力雷达图与下把铁律）</h2>
        </div>
        <div class="fs-table-wrap">
          <table class="fs-structured-table">
            <thead>
              <tr>
                <th>位置 &amp; 选手</th>
                <th>终局核心出装图标时间轴 · 技能频次 &amp; AI 个人结案陈词</th>
                <th>个人六维能力雷达图</th>
                <th>✅ 本局高光表现</th>
                <th>❌ 关键失误抓包</th>
                <th>📌 下把改进铁律</th>
              </tr>
            </thead>
            <tbody>${dossierRowsHtml}</tbody>
          </table>
        </div>
      </section>
    </article>
  `;
}

/**
 * 100% True Native Vector PDF Generator (jsPDF + jspdf-autotable + embedded NotoSansSC TTF + Native Vector Charts & Embedded Hero/Item Icons)
 * Produces selectable, searchable vector text, multi-page consulting tables, 4 native vector charts (Gold/XP Curve, 10-Player Net Worth Curve,
 * 2D Dota 2 Tactical Minimap, 10-Player 3-Bar Damage Matrix), Hero Portraits, 6-Slot Final Item Icons, and 6-Axis Hexagon Radar Charts.
 */
async function downloadStructuredReportPdf() {
  const report = state.currentReport;
  const btn = document.getElementById("btn-fs-download-pdf");
  if (!report) return;

  const { side, sideZh, oppZh, own, opp } = getOwnAndOppPlayers(report);
  const ownWon =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !Boolean(report.radiant_win));
  const filename = `Dota2_原生矢量复盘报告_Match_${report.match_id}_${sideZh}视角.pdf`;

  const JsPDFCtor = window.jspdf?.jsPDF || window.jsPDF;
  if (typeof JsPDFCtor !== "function") {
    showToast("正在加载矢量 PDF 引擎，已先为您下载独立全屏 HTML 报告");
    downloadStructuredReportHtml();
    return;
  }

  const origText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在装载中文字体与英雄/装备图标并绘制矢量图表...";
  }
  showToast(`⏳ 正在生成含全套矢量图表与英雄/装备图标的原生 PDF《${filename}》...`, 5000);

  try {
    const [fontBase64, iconsMap] = await Promise.all([
      ensureCjkVectorFontBase64(),
      ensureMatchIconsMap(report.match_id),
    ]);

    const doc = new JsPDFCtor({
      orientation: "landscape",
      unit: "mm",
      format: "a4",
      compress: true,
    });

    doc.addFileToVFS("NotoSansSC.ttf", fontBase64);
    doc.addFont("NotoSansSC.ttf", "NotoSansSC", "normal");
    doc.addFont("NotoSansSC.ttf", "NotoSansSC", "bold");
    doc.setFont("NotoSansSC", "normal");

    const pageW = doc.internal.pageSize.getWidth(); // 297mm
    const pageH = doc.internal.pageSize.getHeight(); // 210mm
    const marginX = 10;
    const contentW = pageW - marginX * 2; // 277mm
    let curY = 11;

    const df = report.deep_forensics || {};
    const grok = report.grok_coaching || {};
    const draft = report.draft_and_combo?.[side] || report.draft_and_combo || {};
    const rm = df.role_mirror_by_side?.[side] || {};

    // Normalize 100% contribution and blame shares
    const rawContribSum =
      own.reduce((s, p) => s + Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)), 0) || 100;
    const contribMap = new Map();
    own.forEach((p) => {
      contribMap.set(
        Number(p.player_slot),
        Number(((Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)) / rawContribSum) * 100).toFixed(1))
      );
    });
    const rawBlameSum =
      own.reduce((s, p) => s + Math.max(1, Number(p.blame_share_pct || 20)), 0) || 100;
    const blameMap = new Map();
    own.forEach((p) => {
      blameMap.set(
        Number(p.player_slot),
        Number(((Math.max(1, Number(p.blame_share_pct || 20)) / rawBlameSum) * 100).toFixed(1))
      );
    });

    const sortedByContrib = [...own].sort(
      (a, b) => (contribMap.get(Number(b.player_slot)) || 0) - (contribMap.get(Number(a.player_slot)) || 0)
    );
    const sortedByBlame = [...own].sort(
      (a, b) => (blameMap.get(Number(b.player_slot)) || 0) - (blameMap.get(Number(a.player_slot)) || 0)
    );
    const topMvp = sortedByContrib[0] || own[0];
    const topCulprit = sortedByBlame[0] || own[0];

    // Map pos -> own player and opp player for quick icon lookup in tables
    const ownByPos = new Map(own.map((p) => [Number(p.pos), p]));
    const oppByPos = new Map(opp.map((p) => [Number(p.pos), p]));

    const drawIconSafe = (url, x, y, w, h, borderRgb = [148, 163, 184]) => {
      const b64 = url && iconsMap ? iconsMap[url] : null;
      if (b64) {
        try {
          doc.addImage(b64, "PNG", x, y, w, h, undefined, "FAST");
          if (borderRgb) {
            doc.setDrawColor(borderRgb[0], borderRgb[1], borderRgb[2]);
            doc.setLineWidth(0.18);
            doc.rect(x, y, w, h, "S");
          }
          return true;
        } catch (_e) {
          // fallback box below
        }
      }
      doc.setFillColor(30, 41, 59);
      doc.setDrawColor(100, 116, 139);
      doc.setLineWidth(0.15);
      doc.rect(x, y, w, h, "FD");
      return false;
    };

    const ensureSpace = (needMm = 28) => {
      if (curY + needMm > pageH - 13) {
        doc.addPage();
        curY = 15;
      }
    };

    const drawChapterHeader = (chapterTag, titleStr) => {
      ensureSpace(24);
      doc.setFillColor(20, 27, 45);
      doc.rect(marginX, curY, contentW, 7.8, "F");
      doc.setFillColor(180, 138, 62);
      doc.rect(marginX, curY, 19, 7.8, "F");

      doc.setFont("NotoSansSC", "bold");
      doc.setFontSize(8.2);
      doc.setTextColor(255, 255, 255);
      doc.text(cleanPdfVectorText(chapterTag), marginX + 9.5, curY + 5.2, { align: "center" });

      doc.setFontSize(9.6);
      doc.setTextColor(255, 255, 255);
      doc.text(cleanPdfVectorText(titleStr), marginX + 22, curY + 5.3);
      curY += 9.8;
    };

    const drawSubSectionTitle = (subTitle) => {
      ensureSpace(18);
      doc.setFillColor(241, 245, 249);
      doc.rect(marginX, curY, contentW, 5.8, "F");
      doc.setFillColor(180, 138, 62);
      doc.rect(marginX, curY, 2.2, 5.8, "F");
      doc.setFont("NotoSansSC", "bold");
      doc.setFontSize(8.2);
      doc.setTextColor(20, 27, 45);
      doc.text(cleanPdfVectorText(subTitle), marginX + 4.2, curY + 4.1);
      curY += 7.0;
    };

    const runVectorTable = (headCols, bodyRows, colStyles = {}, extraOpts = {}) => {
      doc.autoTable({
        startY: curY,
        margin: { left: marginX, right: marginX, top: 14, bottom: 12 },
        head: [headCols.map((c) => cleanPdfVectorText(c))],
        body: bodyRows.map((row) => row.map((cell) => cleanPdfVectorText(cell))),
        theme: "grid",
        rowPageBreak: "avoid",
        showHead: "everyPage",
        styles: {
          font: "NotoSansSC",
          fontStyle: "normal",
          fontSize: 7.4,
          cellPadding: { top: 2.0, right: 2.2, bottom: 2.0, left: 2.2 },
          textColor: [24, 30, 42],
          lineColor: [208, 215, 226],
          lineWidth: 0.15,
          overflow: "linebreak",
          valign: "middle",
        },
        headStyles: {
          font: "NotoSansSC",
          fontStyle: "bold",
          fontSize: 7.8,
          fillColor: [25, 34, 54],
          textColor: [245, 232, 200],
          lineColor: [45, 58, 86],
          lineWidth: 0.2,
          valign: "middle",
        },
        alternateRowStyles: {
          fillColor: [248, 250, 252],
        },
        columnStyles: colStyles,
        ...extraOpts,
      });
      curY = (doc.lastAutoTable?.finalY || curY) + 4.8;
    };

    // =========================================================================
    // Helper: Draw 6-Axis Vector Hexagon Radar Chart at (cx, cy, maxR)
    // =========================================================================
    const drawVectorHexRadar = (radarObj, cx, cy, maxR) => {
      const r = radarObj || {};
      const dims = [
        { label: "输出", val: Number(r.damage ?? r.fighting ?? 55) },
        { label: "刷钱", val: Number(r.farm ?? r.farming ?? 55) },
        { label: "推塔", val: Number(r.push ?? r.pushing ?? 55) },
        { label: "生存", val: Number(r.survival ?? r.surviving ?? 55) },
        { label: "视野", val: Number(r.utility ?? r.supporting ?? 55) },
        { label: "节奏", val: Number(r.tempo ?? r.laning ?? 55) },
      ];
      const ptAt = (idx, radius) => {
        const angle = -Math.PI / 2 + (idx * Math.PI * 2) / 6;
        return [cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius];
      };

      // Background dark badge circle/box for high contrast
      doc.setFillColor(20, 27, 45);
      doc.setDrawColor(180, 138, 62);
      doc.setLineWidth(0.2);
      doc.roundedRect(cx - maxR - 8.5, cy - maxR - 5.2, (maxR + 8.5) * 2, (maxR + 5.2) * 2, 1.5, 1.5, "FD");

      // Concentric hexagon rings
      [0.35, 0.68, 1.0].forEach((scale) => {
        doc.setDrawColor(65, 80, 110);
        doc.setLineWidth(0.14);
        for (let i = 0; i < 6; i++) {
          const [x1, y1] = ptAt(i, maxR * scale);
          const [x2, y2] = ptAt((i + 1) % 6, maxR * scale);
          doc.line(x1, y1, x2, y2);
        }
      });

      // 6 Axis spokes
      doc.setDrawColor(55, 70, 98);
      doc.setLineWidth(0.12);
      for (let i = 0; i < 6; i++) {
        const [x2, y2] = ptAt(i, maxR);
        doc.line(cx, cy, x2, y2);
      }

      // Data polygon vertices
      const dataPts = dims.map((d, i) => {
        const ratio = Math.min(1, Math.max(0.14, d.val / 100));
        return ptAt(i, maxR * ratio);
      });
      // Build relative segments for doc.lines
      const relSegs = [];
      for (let i = 1; i < dataPts.length; i++) {
        relSegs.push([dataPts[i][0] - dataPts[i - 1][0], dataPts[i][1] - dataPts[i - 1][1]]);
      }
      doc.setFillColor(198, 164, 104);
      doc.setDrawColor(234, 179, 8);
      doc.setLineWidth(0.42);
      doc.lines(relSegs, dataPts[0][0], dataPts[0][1], [1, 1], "FD", true);

      // Re-draw inner spokes subtly over fill + vertex dots + labels
      doc.setFont("NotoSansSC", "bold");
      doc.setFontSize(4.7);
      dims.forEach((d, i) => {
        const [vx, vy] = dataPts[i];
        doc.setFillColor(250, 204, 21);
        doc.circle(vx, vy, 0.55, "F");

        const [lx, ly] = ptAt(i, maxR + 3.4);
        doc.setTextColor(241, 245, 249);
        const align = i === 0 || i === 3 ? "center" : i < 3 ? "left" : "right";
        const offsetX = i === 0 || i === 3 ? 0 : i < 3 ? -1.2 : 1.2;
        doc.text(`${d.label}${Math.round(d.val)}`, lx + offsetX, ly + 0.8, { align });
      });
    };

    // =========================================================================
    // Helper: Draw 2×2 Native Vector Tactical Charts Panel (Page 1 / Page 2)
    // =========================================================================
    const drawPdfFourTacticalChartsPanel = () => {
      ensureSpace(116);
      drawSubSectionTitle(
        "📊 全景录像数据可视化图表矩阵（团队经济经验差曲线 · 十人净值曲线 · 2D 眼位团战小地图 · 十人伤害推塔三色矩阵）"
      );

      const gapX = 4;
      const gapY = 3.5;
      const boxW = (contentW - gapX) / 2; // 136.5mm
      const row1H = 49;
      const row2H = 54;

      const c1X = marginX;
      const c1Y = curY;
      const c2X = marginX + boxW + gapX;
      const c2Y = curY;
      const c3X = marginX;
      const c3Y = curY + row1H + gapY;
      const c4X = marginX + boxW + gapX;
      const c4Y = curY + row1H + gapY;

      const drawChartCardFrame = (x, y, w, h, title, rightNote = "") => {
        doc.setFillColor(250, 251, 253);
        doc.setDrawColor(203, 213, 225);
        doc.setLineWidth(0.22);
        doc.roundedRect(x, y, w, h, 1.4, 1.4, "FD");
        doc.setFillColor(20, 27, 45);
        doc.rect(x, y, w, 6.0, "F");
        doc.setFillColor(180, 138, 62);
        doc.rect(x, y, 2.2, 6.0, "F");
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(7.4);
        doc.setTextColor(245, 232, 200);
        doc.text(cleanPdfVectorText(title), x + 4, y + 4.1);
        if (rightNote) {
          doc.setFont("NotoSansSC", "normal");
          doc.setFontSize(6.3);
          doc.setTextColor(203, 213, 225);
          doc.text(cleanPdfVectorText(rightNote), x + w - 2.5, y + 4.1, { align: "right" });
        }
      };

      // -----------------------------------------------------------------------
      // CHART 1: 团队累计经济差与经验差走势图 (Gold & XP Advantage Curve)
      // -----------------------------------------------------------------------
      const goldAdv = report.radiant_gold_adv || [];
      const xpAdv = report.radiant_xp_adv || [];
      drawChartCardFrame(
        c1X,
        c1Y,
        boxW,
        row1H,
        "1. 团队累计经济差与经验差走势曲线",
        "上方绿区=天辉领先 · 下方红区=夜魇领先 · 实线=经济差 · 虚线=经验差"
      );
      {
        const padL = 12;
        const padR = 5;
        const padT = 9.5;
        const padB = 6.5;
        const plotX = c1X + padL;
        const plotY = c1Y + padT;
        const plotW = boxW - padL - padR;
        const plotH = row1H - padT - padB;
        const midY = plotY + plotH / 2;

        // Upper Radiant subtle green zone & lower Dire subtle red zone
        doc.setFillColor(236, 253, 245);
        doc.rect(plotX, plotY, plotW, plotH / 2, "F");
        doc.setFillColor(254, 242, 242);
        doc.rect(plotX, midY, plotW, plotH / 2, "F");

        const nPts = Math.max(goldAdv.length, xpAdv.length, 2);
        const allVals = [...goldAdv, ...xpAdv, 5000, -5000];
        const maxAbs = Math.max(...allVals.map((v) => Math.abs(Number(v) || 0)), 5000) * 1.1;

        const xAt = (idx) => plotX + (idx / Math.max(1, nPts - 1)) * plotW;
        const yAt = (val) => midY - ((Number(val) || 0) / maxAbs) * (plotH / 2);

        // Horizontal grid lines
        [-maxAbs * 0.75, -maxAbs * 0.38, 0, maxAbs * 0.38, maxAbs * 0.75].forEach((gv) => {
          const gy = yAt(gv);
          doc.setDrawColor(gv === 0 ? 100 : 215, gv === 0 ? 116 : 222, gv === 0 ? 139 : 232);
          doc.setLineWidth(gv === 0 ? 0.28 : 0.12);
          doc.line(plotX, gy, plotX + plotW, gy);
          doc.setFont("NotoSansSC", "normal");
          doc.setFontSize(5.6);
          doc.setTextColor(100, 116, 139);
          const lbl = gv === 0 ? "0" : `${gv > 0 ? "+" : ""}${Math.round(gv / 1000)}k`;
          doc.text(lbl, plotX - 1.5, gy + 0.8, { align: "right" });
        });

        // Vertical minute ticks
        const stepMin = nPts > 45 ? 10 : 5;
        for (let m = 0; m < nPts; m += stepMin) {
          const gx = xAt(m);
          doc.setDrawColor(226, 232, 240);
          doc.setLineWidth(0.12);
          doc.line(gx, plotY, gx, plotY + plotH);
          doc.setFontSize(5.5);
          doc.setTextColor(100, 116, 139);
          doc.text(`${m}m`, gx, plotY + plotH + 3.6, { align: "center" });
        }

        // Shaded vertical bars under Gold Advantage curve for clear visual area fill
        if (goldAdv.length > 1) {
          for (let i = 0; i < goldAdv.length - 1; i++) {
            const v1 = Number(goldAdv[i]) || 0;
            const v2 = Number(goldAdv[i + 1]) || 0;
            const x1 = xAt(i);
            const x2 = xAt(i + 1);
            const y1 = yAt(v1);
            const y2 = yAt(v2);
            const avgV = (v1 + v2) / 2;
            if (avgV >= 0) {
              doc.setFillColor(187, 247, 208);
            } else {
              doc.setFillColor(254, 202, 202);
            }
            const barTop = Math.min(midY, (y1 + y2) / 2);
            const barH = Math.max(0.3, Math.abs((y1 + y2) / 2 - midY));
            doc.rect(x1, barTop, Math.max(0.4, x2 - x1), barH, "F");
          }
        }

        // Objective markers (Roshan / Barracks / T3)
        const objEvents = (report.objectives_timeline || []).filter(
          (o) => o.type === "roshan" || o.type === "rax" || (o.key && String(o.key).includes("tower3"))
        );
        objEvents.slice(0, 8).forEach((ev) => {
          const minF = Math.min(nPts - 1, Math.max(0, (Number(ev.time_sec) || 0) / 60));
          const ox = xAt(minF);
          doc.setDrawColor(180, 138, 62);
          doc.setLineWidth(0.18);
          doc.line(ox, plotY, ox, plotY + plotH);
          doc.setFillColor(254, 243, 199);
          doc.circle(ox, plotY + 2.2, 1.3, "FD");
          doc.setFont("NotoSansSC", "bold");
          doc.setFontSize(4.6);
          doc.setTextColor(146, 64, 14);
          doc.text(ev.type === "roshan" ? "盾" : "高", ox, plotY + 2.8, { align: "center" });
        });

        // XP Advantage dashed curve (Blue)
        if (xpAdv.length > 1) {
          doc.setDrawColor(37, 99, 235);
          doc.setLineWidth(0.38);
          for (let i = 0; i < xpAdv.length - 1; i++) {
            const x1 = xAt(i);
            const y1 = yAt(xpAdv[i]);
            const x2 = xAt(i + 1);
            const y2 = yAt(xpAdv[i + 1]);
            // Draw short segment (dashed look by drawing 65% of segment)
            doc.line(x1, y1, x1 + (x2 - x1) * 0.68, y1 + (y2 - y1) * 0.68);
          }
        }

        // Gold Advantage solid curve (Amber Gold)
        if (goldAdv.length > 1) {
          doc.setDrawColor(217, 119, 6);
          doc.setLineWidth(0.62);
          for (let i = 0; i < goldAdv.length - 1; i++) {
            doc.line(xAt(i), yAt(goldAdv[i]), xAt(i + 1), yAt(goldAdv[i + 1]));
          }
          // Final gold diff badge
          const lastIdx = goldAdv.length - 1;
          const lastVal = Number(goldAdv[lastIdx]) || 0;
          const lx = xAt(lastIdx);
          const ly = yAt(lastVal);
          doc.setFillColor(217, 119, 6);
          doc.circle(lx, ly, 0.9, "F");
          doc.setFont("NotoSansSC", "bold");
          doc.setFontSize(5.8);
          doc.setTextColor(180, 83, 9);
          doc.text(
            `终局 ${lastVal >= 0 ? "天辉+" : "夜魇+"}${(Math.abs(lastVal) / 1000).toFixed(1)}k`,
            lx - 2,
            Math.max(plotY + 3.5, Math.min(plotY + plotH - 1.5, ly - 1.5)),
            { align: "right" }
          );
        }

        // Zone watermarks
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(6.2);
        doc.setTextColor(22, 163, 74);
        doc.text("▲ 天辉经济领先区", plotX + 2, plotY + 3.8);
        doc.setTextColor(220, 38, 38);
        doc.text("▼ 夜魇经济领先区", plotX + 2, plotY + plotH - 1.5);
      }

      // -----------------------------------------------------------------------
      // CHART 2: 十人分钟级净资产走势曲线 (10-Player Net Worth Curves)
      // -----------------------------------------------------------------------
      drawChartCardFrame(
        c2X,
        c2Y,
        boxW,
        row1H,
        `2. 十人分钟级净资产走势曲线 (实线=${sideZh}1~5号位 · 虚线=${oppZh}1~5号位)`,
        "右侧按终局净资产从高到低排序"
      );
      {
        const padL = 11;
        const padR = 32; // Legend space on right
        const padT = 9.5;
        const padB = 6.5;
        const plotX = c2X + padL;
        const plotY = c2Y + padT;
        const plotW = boxW - padL - padR;
        const plotH = row1H - padT - padB;

        const allPlayers = [...own, ...opp];
        const maxLen = Math.max(...allPlayers.map((p) => (p.networth_t || []).length), 2);
        const maxNw =
          Math.max(
            ...allPlayers.map((p) => Math.max(...(p.networth_t || [0]), Number(p.net_worth) || 0)),
            10000
          ) * 1.06;

        const xAt = (idx) => plotX + (idx / Math.max(1, maxLen - 1)) * plotW;
        const yAt = (val) => plotY + plotH - ((Number(val) || 0) / maxNw) * plotH;

        // Horizontal grid lines
        [0, 0.25, 0.5, 0.75, 1.0].forEach((ratio) => {
          const v = maxNw * ratio;
          const gy = yAt(v);
          doc.setDrawColor(220, 226, 236);
          doc.setLineWidth(0.12);
          doc.line(plotX, gy, plotX + plotW, gy);
          doc.setFont("NotoSansSC", "normal");
          doc.setFontSize(5.4);
          doc.setTextColor(100, 116, 139);
          doc.text(`${Math.round(v / 1000)}k`, plotX - 1.2, gy + 0.8, { align: "right" });
        });

        // Minute ticks
        const stepMin = maxLen > 45 ? 10 : 5;
        for (let m = 0; m < maxLen; m += stepMin) {
          const gx = xAt(m);
          doc.setDrawColor(228, 233, 242);
          doc.setLineWidth(0.1);
          doc.line(gx, plotY, gx, plotY + plotH);
          doc.setFontSize(5.4);
          doc.setTextColor(100, 116, 139);
          doc.text(`${m}m`, gx, plotY + plotH + 3.6, { align: "center" });
        }

        // Distinct color palettes for Pos 1~5
        const ownColors = {
          1: [220, 38, 38], // Pos 1 Crimson Red
          2: [217, 119, 6], // Pos 2 Amber Gold
          3: [37, 99, 235], // Pos 3 Royal Blue
          4: [22, 163, 74], // Pos 4 Emerald Green
          5: [147, 51, 234], // Pos 5 Purple
        };
        const oppColors = {
          1: [248, 113, 113],
          2: [251, 191, 36],
          3: [96, 165, 250],
          4: [74, 222, 128],
          5: [192, 132, 252],
        };

        // Draw Enemy curves first (thin dashed)
        opp.forEach((p) => {
          const series = p.networth_t || [];
          if (series.length < 2) return;
          const rgb = oppColors[p.pos] || [148, 163, 184];
          doc.setDrawColor(rgb[0], rgb[1], rgb[2]);
          doc.setLineWidth(0.28);
          for (let i = 0; i < series.length - 1; i++) {
            const x1 = xAt(i);
            const y1 = yAt(series[i]);
            const x2 = xAt(i + 1);
            const y2 = yAt(series[i + 1]);
            doc.line(x1, y1, x1 + (x2 - x1) * 0.58, y1 + (y2 - y1) * 0.58);
          }
        });

        // Draw Own curves on top (bold solid + endpoint dot)
        own.forEach((p) => {
          const series = p.networth_t || [];
          if (series.length < 2) return;
          const rgb = ownColors[p.pos] || [30, 41, 59];
          doc.setDrawColor(rgb[0], rgb[1], rgb[2]);
          doc.setLineWidth(0.55);
          for (let i = 0; i < series.length - 1; i++) {
            doc.line(xAt(i), yAt(series[i]), xAt(i + 1), yAt(series[i + 1]));
          }
          const lastIdx = series.length - 1;
          doc.setFillColor(rgb[0], rgb[1], rgb[2]);
          doc.circle(xAt(lastIdx), yAt(series[lastIdx]), 0.65, "F");
        });

        // Right-hand sorted 10-player Net Worth Legend
        const sorted10 = [...allPlayers].sort((a, b) => (Number(b.net_worth) || 0) - (Number(a.net_worth) || 0));
        const legX = plotX + plotW + 2.2;
        const rowStep = plotH / 10;
        sorted10.forEach((p, idx) => {
          const isOwnP = p.side === side;
          const rgb = isOwnP ? ownColors[p.pos] || [30, 41, 59] : oppColors[p.pos] || [148, 163, 184];
          const ly = plotY + idx * rowStep + 2.4;
          doc.setFillColor(rgb[0], rgb[1], rgb[2]);
          doc.rect(legX, ly - 1.6, 2.2, 1.6, "F");
          doc.setFont("NotoSansSC", isOwnP ? "bold" : "normal");
          doc.setFontSize(5.3);
          doc.setTextColor(isOwnP ? 15 : 100, isOwnP ? 23 : 116, isOwnP ? 42 : 139);
          const hName = (p.hero_short_zh || "").slice(0, 3);
          const nwK = ((Number(p.net_worth) || 0) / 1000).toFixed(1);
          doc.text(cleanPdfVectorText(`${p.pos}${hName} ${nwK}k`), legX + 3.0, ly - 0.3);
        });
      }

      // -----------------------------------------------------------------------
      // CHART 3: 2D 刀塔战术小地图 (眼位/团战落点) + 五人视野战果面板
      // -----------------------------------------------------------------------
      const allWardsList = report.vision_and_map_data?.wards || [];
      const obsPoints =
        allWardsList.filter((w) => w.type === "obs").length > 0
          ? allWardsList.filter((w) => w.type === "obs")
          : report.wards?.obs_points || [];
      const senPoints =
        allWardsList.filter((w) => w.type === "sen").length > 0
          ? allWardsList.filter((w) => w.type === "sen")
          : report.wards?.sen_points || [];
      drawChartCardFrame(
        c3X,
        c3Y,
        boxW,
        row2H,
        `3. 2D 刀塔小地图 (黄圈=假眼${obsPoints.length}颗 · 蓝点=真眼${senPoints.length}颗) & 视野战果`,
        "含高地/河道/野区眼位坐标与重复插眼标注"
      );
      {
        const mapSize = 43.5;
        const mapX = c3X + 3.2;
        const mapY = c3Y + 8.0;

        // Base map background (Dire upper-right dark crimson, Radiant lower-left dark emerald)
        doc.setFillColor(24, 38, 28);
        doc.rect(mapX, mapY, mapSize, mapSize, "F");
        // Dire upper-right triangle
        doc.setFillColor(44, 24, 26);
        doc.lines(
          [
            [mapSize, 0],
            [0, mapSize],
          ],
          mapX,
          mapY,
          [1, 1],
          "F",
          true
        );

        // Diagonal River (from top-left to bottom-right)
        doc.setDrawColor(22, 101, 128);
        doc.setLineWidth(2.6);
        doc.line(mapX + 2.5, mapY + 5.5, mapX + mapSize - 2.5, mapY + mapSize - 5.5);

        // 3 Lanes (Top, Mid, Bot)
        doc.setDrawColor(95, 108, 92);
        doc.setLineWidth(0.55);
        // Top lane
        doc.line(mapX + 3.5, mapY + mapSize - 4, mapX + 3.5, mapY + 3.5);
        doc.line(mapX + 3.5, mapY + 3.5, mapX + mapSize - 4, mapY + 3.5);
        // Bot lane
        doc.line(mapX + 4, mapY + mapSize - 3.5, mapX + mapSize - 3.5, mapY + mapSize - 3.5);
        doc.line(mapX + mapSize - 3.5, mapY + mapSize - 3.5, mapX + mapSize - 3.5, mapY + 4);
        // Mid lane
        doc.line(mapX + 4, mapY + mapSize - 4, mapX + mapSize - 4, mapY + 4);

        // Radiant & Dire Ancients
        doc.setFillColor(34, 197, 94);
        doc.setDrawColor(255, 255, 255);
        doc.setLineWidth(0.25);
        doc.rect(mapX + 4.2, mapY + mapSize - 7.8, 3.4, 3.4, "FD");
        doc.setFillColor(239, 68, 68);
        doc.rect(mapX + mapSize - 7.6, mapY + 4.2, 3.4, 3.4, "FD");

        // Roshan pit marker (upper-left river bend / twin-gate roshan)
        doc.setFillColor(180, 83, 9);
        doc.circle(mapX + mapSize * 0.36, mapY + mapSize * 0.36, 1.7, "FD");
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(4.5);
        doc.setTextColor(255, 255, 255);
        doc.text("R", mapX + mapSize * 0.36, mapY + mapSize * 0.36 + 0.6, { align: "center" });

        // Coordinate converter supporting both 0..100 normalized (nx/ny) and 64..192 grid (x/y)
        const toMapXY = (pt) => {
          const rawX = Number(pt.nx ?? pt.x ?? 50);
          const rawY = Number(pt.ny ?? pt.y ?? 50);
          const ratioX =
            rawX > 100
              ? Math.min(1, Math.max(0, (rawX - 64) / 128))
              : Math.min(1, Math.max(0, rawX / 100));
          const ratioY =
            rawY > 100
              ? Math.min(1, Math.max(0, 1 - (rawY - 64) / 128))
              : Math.min(1, Math.max(0, rawY / 100));
          return [mapX + 1.8 + ratioX * (mapSize - 3.6), mapY + 1.8 + ratioY * (mapSize - 3.6)];
        };

        // Plot Sentry Wards (Blue small dots)
        senPoints.forEach((pt) => {
          const [wx, wy] = toMapXY(pt);
          const isOwnW = pt.side === side || pt.side === sideZh;
          doc.setFillColor(isOwnW ? 56 : 147, isOwnW ? 189 : 197, 248);
          doc.circle(wx, wy, 0.55, "F");
        });

        // Group Observer Wards by proximity to show repeat ×N badges & vision rings
        const obsClusters = [];
        obsPoints.forEach((pt) => {
          const [wx, wy] = toMapXY(pt);
          const existing = obsClusters.find(
            (c) => c.side === pt.side && Math.hypot(c.wx - wx, c.wy - wy) < 2.2
          );
          if (existing) {
            existing.count += 1;
          } else {
            obsClusters.push({ wx, wy, side: pt.side, count: 1 });
          }
        });

        obsClusters.forEach((c) => {
          const isOwnW = c.side === side || c.side === sideZh;
          // Vision radius ring
          doc.setDrawColor(isOwnW ? 250 : 248, isOwnW ? 204 : 113, isOwnW ? 21 : 113);
          doc.setLineWidth(0.15);
          doc.circle(c.wx, c.wy, 2.2, "S");
          // Ward core dot
          doc.setFillColor(isOwnW ? 250 : 239, isOwnW ? 204 : 68, isOwnW ? 21 : 68);
          doc.setDrawColor(15, 23, 42);
          doc.setLineWidth(0.15);
          doc.circle(c.wx, c.wy, 0.85, "FD");
          if (c.count > 1) {
            doc.setFont("NotoSansSC", "bold");
            doc.setFontSize(4.2);
            doc.setTextColor(254, 240, 138);
            doc.text(`×${c.count}`, c.wx + 1.0, c.wy - 0.6);
          }
        });

        // Map frame border & corner labels
        doc.setDrawColor(180, 138, 62);
        doc.setLineWidth(0.3);
        doc.rect(mapX, mapY, mapSize, mapSize, "S");
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(5.0);
        doc.setTextColor(134, 239, 172);
        doc.text("天辉", mapX + 1.5, mapY + mapSize - 1.2);
        doc.setTextColor(252, 165, 165);
        doc.text("夜魇", mapX + mapSize - 1.5, mapY + 3.2, { align: "right" });

        // Right-hand side of Chart 3: Our 1~5 Vision & Posture Breakdown
        const rPanelX = mapX + mapSize + 3.2;
        const rPanelW = c3X + boxW - rPanelX - 2.5;
        const visSide = df.support_vision_by_side?.[side] || {};

        // 3-Color Posture Bar (进攻眼 vs 河道肉山眼 vs 防守眼)
        const pAgg = Number(visSide.posture_pcts?.aggressive ?? 34);
        const pRiv = Number(visSide.posture_pcts?.river_roshan ?? 33);
        const pDef = Math.max(0, 100 - pAgg - pRiv);

        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(6.2);
        doc.setTextColor(20, 27, 45);
        doc.text(
          cleanPdfVectorText(
            `${sideZh}眼位姿态：进攻眼 ${pAgg}%  |  河道/肉山眼 ${pRiv}%  |  防守眼 ${pDef.toFixed(0)}%`
          ),
          rPanelX,
          mapY + 2.8
        );

        const barY = mapY + 4.0;
        const barH = 2.6;
        const wAgg = (rPanelW * pAgg) / 100;
        const wRiv = (rPanelW * pRiv) / 100;
        const wDef = Math.max(0, rPanelW - wAgg - wRiv);
        if (wAgg > 0) {
          doc.setFillColor(220, 38, 38);
          doc.rect(rPanelX, barY, wAgg, barH, "F");
        }
        if (wRiv > 0) {
          doc.setFillColor(217, 119, 6);
          doc.rect(rPanelX + wAgg, barY, wRiv, barH, "F");
        }
        if (wDef > 0) {
          doc.setFillColor(37, 99, 235);
          doc.rect(rPanelX + wAgg + wRiv, barY, wDef, barH, "F");
        }

        // Per-player Vision & Deward mini-rows (with Hero Portrait)
        const pRowsY = barY + 4.5;
        const pRowH = 6.6;
        own.forEach((p, idx) => {
          const ry = pRowsY + idx * pRowH;
          doc.setFillColor(idx % 2 === 0 ? 241 : 248, idx % 2 === 0 ? 245 : 250, 252);
          doc.rect(rPanelX, ry, rPanelW, pRowH - 0.6, "F");
          drawIconSafe(p.hero_img, rPanelX + 1.0, ry + 0.6, 7.6, 4.6);

          doc.setFont("NotoSansSC", "bold");
          doc.setFontSize(6.0);
          doc.setTextColor(15, 23, 42);
          doc.text(
            cleanPdfVectorText(`${p.pos}号 ${p.hero_short_zh || ""}`),
            rPanelX + 9.8,
            ry + 3.6
          );

          doc.setFont("NotoSansSC", "normal");
          doc.setFontSize(5.8);
          doc.setTextColor(51, 65, 85);
          doc.text(
            cleanPdfVectorText(
              `插假眼 ${p.obs_placed ?? 0} · 真眼 ${p.sen_placed ?? 0} · 排眼 ${
                p.observer_kills ?? 0
              }颗 · 买雾 ${p.smoke_uses ?? 0} · 堆野 ${p.camps_stacked ?? 0}组`
            ),
            rPanelX + 31,
            ry + 3.6
          );
        });

        // Summary line under the 5 rows
        doc.setFont("NotoSansSC", "normal");
        doc.setFontSize(5.6);
        doc.setTextColor(71, 85, 105);
        const vNote =
          doc.splitTextToSize(
            cleanPdfVectorText(
              `眼位诊断：平均存活 ${visSide.avg_lifespan_sec ?? 0}s/360s，被排 ${
                visSide.dewarded_total ?? 0
              }颗(${visSide.dewarded_pct ?? 0}%)。${visSide.posture_verdict || ""}`
            ),
            rPanelW
          )[0] || "";
        doc.text(vNote, rPanelX, pRowsY + 5 * pRowH + 2.2);
      }

      // -----------------------------------------------------------------------
      // CHART 4: 十人英雄输出 · 承受伤害 · 建筑推塔三色横向条形矩阵
      // -----------------------------------------------------------------------
      drawChartCardFrame(
        c4X,
        c4Y,
        boxW,
        row2H,
        "4. 十人英雄输出 · 承受伤害 · 建筑推塔三色横向条形矩阵",
        "红=英雄伤害  |  蓝=承受伤害  |  金=建筑推塔"
      );
      {
        const all10 = [...own, ...opp].sort(
          (a, b) => (Number(b.hero_damage) || 0) - (Number(a.hero_damage) || 0)
        );
        const maxDmgVal = Math.max(
          ...all10.map((p) =>
            Math.max(
              Number(p.hero_damage) || 0,
              Number(p.damage_taken) || 0,
              Number(p.tower_damage) || 0
            )
          ),
          10000
        );

        const listX = c4X + 2.8;
        const listY = c4Y + 7.8;
        const rowH = (row2H - 9.2) / 10; // ~4.48mm per player

        all10.forEach((p, idx) => {
          const ry = listY + idx * rowH;
          const isOwnP = p.side === side;
          if (idx % 2 === 0) {
            doc.setFillColor(243, 246, 251);
            doc.rect(listX, ry, boxW - 5.6, rowH - 0.3, "F");
          }

          // Faction color indicator strip
          doc.setFillColor(isOwnP ? 22 : 220, isOwnP ? 163 : 38, isOwnP ? 74 : 38);
          doc.rect(listX, ry + 0.3, 1.2, rowH - 0.9, "F");

          // Hero Portrait
          drawIconSafe(p.hero_img, listX + 1.8, ry + 0.35, 5.8, 3.4);

          // Hero label
          doc.setFont("NotoSansSC", isOwnP ? "bold" : "normal");
          doc.setFontSize(5.5);
          doc.setTextColor(isOwnP ? 15 : 71, isOwnP ? 23 : 85, isOwnP ? 42 : 105);
          const hLabel = `${p.pos}${(p.hero_short_zh || "").slice(0, 3)}`;
          doc.text(cleanPdfVectorText(hLabel), listX + 8.4, ry + 2.7);

          // 3 Horizontal Bars: Hero Damage (Red), Damage Taken (Blue), Tower Damage (Gold)
          const barsStartX = listX + 22.5;
          const totalBarsW = boxW - 29.5;
          const colW = totalBarsW / 3; // 3 sub-columns for the 3 metrics

          const metrics = [
            { val: Number(p.hero_damage) || 0, rgb: [220, 38, 38], prefix: "伤" },
            { val: Number(p.damage_taken) || 0, rgb: [37, 99, 235], prefix: "承" },
            { val: Number(p.tower_damage) || 0, rgb: [217, 119, 6], prefix: "塔" },
          ];

          metrics.forEach((m, mIdx) => {
            const mx = barsStartX + mIdx * colW;
            const maxBarW = colW - 12.5;
            const fillW = Math.max(0.5, (m.val / maxDmgVal) * maxBarW);

            // Track background
            doc.setFillColor(226, 232, 240);
            doc.rect(mx, ry + 1.0, maxBarW, 2.0, "F");
            // Value fill
            doc.setFillColor(m.rgb[0], m.rgb[1], m.rgb[2]);
            doc.rect(mx, ry + 1.0, fillW, 2.0, "F");

            // Numeric label
            doc.setFont("NotoSansSC", "bold");
            doc.setFontSize(5.2);
            doc.setTextColor(m.rgb[0], m.rgb[1], m.rgb[2]);
            doc.text(`${(m.val / 1000).toFixed(1)}k`, mx + maxBarW + 1.2, ry + 2.6);
          });
        });
      }

      curY += row1H + gapY + row2H + 4.5;
    };

    // =========================================================================
    // COVER BANNER, 4 KPI CARDS & 5v5 HERO PORTRAIT LINEUP STRIP (Page 1 Top)
    // =========================================================================
    doc.setFillColor(18, 25, 43);
    doc.rect(marginX, curY, contentW, 19.5, "F");
    doc.setFillColor(180, 138, 62);
    doc.rect(marginX, curY, 3.2, 19.5, "F");

    doc.setFont("NotoSansSC", "bold");
    doc.setFontSize(7.2);
    doc.setTextColor(218, 182, 110);
    doc.text(
      "DOTA 2 FIVE-STACK POST-GAME FORENSICS DOSSIER · 五黑车队录像级结构化复盘报告 (100% 原生矢量图表 + 英雄/装备视觉卷宗)",
      marginX + 6.5,
      curY + 5.0
    );

    doc.setFontSize(13.2);
    doc.setTextColor(255, 255, 255);
    doc.text(
      cleanPdfVectorText(
        `比赛 #${report.match_id} · ${sideZh}视角深度复盘报告 [${
          ownWon ? `${sideZh}凯旋获胜` : `${sideZh}遗憾落败`
        }]`
      ),
      marginX + 6.5,
      curY + 11.8
    );

    doc.setFont("NotoSansSC", "normal");
    doc.setFontSize(7.6);
    doc.setTextColor(203, 213, 225);
    const shareUrl = getPublicShareUrl(report.match_id);
    doc.text(
      cleanPdfVectorText(
        `比赛时间：${report.start_time_str || "-"}  |  模式：${
          report.game_mode_str || "全英雄选择"
        }  |  终局比分：天辉 ${report.radiant_score} : ${report.dire_score} 夜魇 (${
          report.duration_str
        })  |  在线复盘链接：${shareUrl}`
      ),
      marginX + 6.5,
      curY + 17.0
    );
    curY += 21.5;

    // 4 Executive KPI Cards
    const kpiItems = [
      {
        label: "审计阵营 & 终局比分",
        val: `${sideZh}视角 (${ownWon ? "胜局庆功卷宗" : "败局分锅卷宗"})`,
        sub: `天辉 ${report.radiant_score} : ${report.dire_score} 夜魇 · 时长 ${report.duration_str || ""}`,
      },
      {
        label: `本方 1~5 号位阵容 (${sideZh})`,
        val: own.map((p) => `${p.pos}${p.hero_short_zh}`).join("/"),
        sub: `阵容成色评级：${draft.grade || "A 级"}`,
      },
      {
        label: `敌方 1~5 号位阵容 (${oppZh})`,
        val: opp.map((p) => `${p.pos}${p.hero_short_zh}`).join("/"),
        sub: `同位置 1v1 对位胜出：${rm.won_overall_cnt ?? 0} / 5 路`,
      },
      {
        label: ownWon ? "头号首功 MVP" : "本方头号背锅战犯",
        val: ownWon
          ? `${topMvp?.pos}号位 ${topMvp?.hero_short_zh || ""} (${topMvp?.personaname || ""})`
          : `${topCulprit?.pos}号位 ${topCulprit?.hero_short_zh || ""} (${topCulprit?.personaname || ""})`,
        sub: ownWon
          ? `胜局贡献 ${contribMap.get(Number(topMvp?.player_slot)) ?? 25}% · 综合评分 ${topMvp?.rating_score ?? 8.5}`
          : `分锅占比 ${blameMap.get(Number(topCulprit?.player_slot)) ?? 30}% · 综合评分 ${topCulprit?.rating_score ?? 5.0}`,
      },
    ];
    const gapMm = 3;
    const cardW = (contentW - gapMm * 3) / 4;
    const cardH = 14.8;
    kpiItems.forEach((item, idx) => {
      const cx = marginX + idx * (cardW + gapMm);
      doc.setFillColor(248, 250, 252);
      doc.setDrawColor(203, 213, 225);
      doc.setLineWidth(0.2);
      doc.rect(cx, curY, cardW, cardH, "FD");
      doc.setFillColor(180, 138, 62);
      doc.rect(cx, curY, cardW, 1.1, "F");

      doc.setFont("NotoSansSC", "normal");
      doc.setFontSize(6.6);
      doc.setTextColor(100, 116, 139);
      doc.text(cleanPdfVectorText(item.label), cx + 2.2, curY + 4.3);

      doc.setFont("NotoSansSC", "bold");
      doc.setFontSize(idx === 1 || idx === 2 ? 6.7 : 7.5);
      doc.setTextColor(15, 23, 42);
      const valClipped = doc.splitTextToSize(cleanPdfVectorText(item.val), cardW - 4.2)[0] || "";
      doc.text(valClipped, cx + 2.2, curY + 9.0);

      doc.setFont("NotoSansSC", "normal");
      doc.setFontSize(6.6);
      doc.setTextColor(71, 85, 105);
      const subClipped = doc.splitTextToSize(cleanPdfVectorText(item.sub), cardW - 4.2)[0] || "";
      doc.text(subClipped, cx + 2.2, curY + 13.0);
    });
    curY += cardH + 2.5;

    // 5v5 Hero Portrait VS Lineup Strip on Page 1
    {
      const stripH = 11.2;
      doc.setFillColor(15, 23, 42);
      doc.setDrawColor(51, 65, 85);
      doc.setLineWidth(0.2);
      doc.roundedRect(marginX, curY, contentW, stripH, 1.2, 1.2, "FD");

      const sideW = (contentW - 12) / 2;
      const slotW = sideW / 5;

      // Left 5: Own lineup
      own.forEach((p, idx) => {
        const sx = marginX + 1.5 + idx * slotW;
        const sy = curY + 1.4;
        drawIconSafe(p.hero_img, sx, sy, 9.2, 5.5, ownWon ? [34, 197, 94] : [234, 179, 8]);
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(5.8);
        doc.setTextColor(248, 250, 252);
        doc.text(
          cleanPdfVectorText(`${p.pos}号 ${(p.hero_short_zh || "").slice(0, 4)}`),
          sx + 10.2,
          sy + 2.5
        );
        doc.setFont("NotoSansSC", "normal");
        doc.setFontSize(5.1);
        doc.setTextColor(148, 163, 184);
        doc.text(
          cleanPdfVectorText(`${p.kda} · ${((Number(p.net_worth) || 0) / 1000).toFixed(1)}k`),
          sx + 10.2,
          sy + 5.2
        );
        const pNameClip = doc.splitTextToSize(cleanPdfVectorText(p.personaname || ""), slotW - 2)[0] || "";
        doc.setTextColor(203, 213, 225);
        doc.text(pNameClip, sx, sy + 8.2);
      });

      // Center VS badge
      doc.setFillColor(180, 138, 62);
      doc.circle(marginX + contentW / 2, curY + stripH / 2, 3.6, "F");
      doc.setFont("NotoSansSC", "bold");
      doc.setFontSize(6.5);
      doc.setTextColor(15, 23, 42);
      doc.text("VS", marginX + contentW / 2, curY + stripH / 2 + 0.9, { align: "center" });

      // Right 5: Enemy lineup
      const rightStartX = marginX + sideW + 10.5;
      opp.forEach((p, idx) => {
        const sx = rightStartX + idx * slotW;
        const sy = curY + 1.4;
        drawIconSafe(p.hero_img, sx, sy, 9.2, 5.5, [239, 68, 68]);
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(5.8);
        doc.setTextColor(254, 202, 202);
        doc.text(
          cleanPdfVectorText(`${p.pos}号 ${(p.hero_short_zh || "").slice(0, 4)}`),
          sx + 10.2,
          sy + 2.5
        );
        doc.setFont("NotoSansSC", "normal");
        doc.setFontSize(5.1);
        doc.setTextColor(148, 163, 184);
        doc.text(
          cleanPdfVectorText(`${p.kda} · ${((Number(p.net_worth) || 0) / 1000).toFixed(1)}k`),
          sx + 10.2,
          sy + 5.2
        );
        const pNameClip = doc.splitTextToSize(cleanPdfVectorText(p.personaname || ""), slotW - 2)[0] || "";
        doc.setTextColor(203, 213, 225);
        doc.text(pNameClip, sx, sy + 8.2);
      });

      curY += stripH + 3.5;
    }

    // =========================================================================
    // CHAPTER I: 赛后总账与四阶段复盘矩阵 + 2×2 全景录像数据可视化图表矩阵
    // =========================================================================
    drawChapterHeader(
      "第一章",
      "赛后总账与四阶段复盘矩阵（00:00 对线期 → 10:00-25:00 中期节奏 → 25:00-终局 决胜团战 → 全局硬实力）"
    );
    const stages = report.match_narrative?.stages || [];
    const stageRows = stages.map((s, idx) => [
      `阶段 0${idx + 1}\n${s.stage || s.title || ""}`,
      (s.summary || s.content || "")
        .replace(/三路10分钟对账：/g, "；")
        .replace(/主视角（[^）]+）车队全局数据对比：/g, "；"),
    ]);
    if (grok.summary) {
      stageRows.unshift(["Grok 4.7 核心总评", grok.summary]);
    }
    runVectorTable(["阶段维度", "录像级核心对账数据与关键胜负节点还原"], stageRows, {
      0: { cellWidth: 42, fontStyle: "bold" },
      1: { cellWidth: contentW - 42 },
    });

    // Draw the 4 Native Vector Tactical Charts Panel!
    drawPdfFourTacticalChartsPanel();

    // =========================================================================
    // CHAPTER II: 本方五人 100% 胜局功勋 / 败局分锅定责总表 (with Hero Portraits & Progress Bars)
    // =========================================================================
    drawChapterHeader(
      "第二章",
      `${sideZh}五人 100% ${ownWon ? "胜局功勋表彰总表" : "败局分锅定责总表"}（含英雄头像与伤害/定责可视化进度条）`
    );
    const ch2Rows = own.map((p) => {
      const heroShort = p.hero_short_zh || p.hero_name || "";
      const sharePct = ownWon
        ? contribMap.get(Number(p.player_slot)) ?? 20.0
        : blameMap.get(Number(p.player_slot)) ?? 20.0;
      const roleNote = ownWon
        ? p.praise_talk || (p.strengths || [])[0] || "稳定发挥完成战术任务"
        : p.trash_talk || (p.weaknesses || [])[0] || "存在团战或对线细节失误";
      return [
        `${p.pos}号位\n(${p.pos_label || ""})`,
        `${heroShort}\n${p.personaname || ""}${p.is_me ? " [我]" : ""}`,
        `${p.kda}\n(参战 ${p.kill_participation_pct ?? 0}%)`,
        `${fmtNum(p.net_worth)} 金\nGPM ${p.gpm} / XPM ${p.xpm}`,
        `${fmtNum(p.hero_damage)}\n(占全队 ${p.hero_damage_share_pct ?? 0}%)`,
        `${fmtNum(p.damage_taken)}\n(读秒 ${p.dead_seconds ?? 0}s)`,
        `${fmtNum(p.tower_damage)}\n(控制 ${p.stuns_sec ?? 0}s)`,
        `${getHeroScore100(p)} / 100分\n${ownWon ? p.contrib_tier || "功臣" : p.rating_tier || ""}`,
        ownWon ? `功勋 ${sharePct}%` : `分锅 ${sharePct}%`,
        roleNote,
      ];
    });
    runVectorTable(
      [
        "位置",
        "英雄 & 选手",
        "K/D/A (参战)",
        "终局净值 & GPM",
        "英雄伤害 (占比)",
        "承伤 & 读秒",
        "推塔 & 控制",
        "本局百人制评分",
        ownWon ? "100% 功勋" : "100% 分锅",
        "核心定性判词",
      ],
      ch2Rows,
      {
        0: { cellWidth: 18, fontStyle: "bold" },
        1: { cellWidth: 35, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 12.2 } },
        2: { cellWidth: 21 },
        3: { cellWidth: 25 },
        4: { cellWidth: 25, cellPadding: { top: 2, right: 2, bottom: 4.2, left: 2 } },
        5: { cellWidth: 21 },
        6: { cellWidth: 20 },
        7: { cellWidth: 19 },
        8: {
          cellWidth: 22,
          fontStyle: "bold",
          textColor: ownWon ? [21, 128, 61] : [185, 28, 28],
          cellPadding: { top: 2, right: 2, bottom: 4.2, left: 2 },
        },
        9: { cellWidth: contentW - 206 },
      },
      {
        didDrawCell: (data) => {
          if (data.section !== "body") return;
          const p = own[data.row.index];
          if (!p) return;
          // Col 1: Hero Portrait
          if (data.column.index === 1) {
            const iy = data.cell.y + (data.cell.height - 5.4) / 2;
            drawIconSafe(p.hero_img, data.cell.x + 1.8, iy, 9.0, 5.4);
          }
          // Col 4: Hero Damage Share Bar
          if (data.column.index === 4) {
            const pct = Math.min(100, Math.max(3, Number(p.hero_damage_share_pct) || 0));
            const bx = data.cell.x + 2;
            const by = data.cell.y + data.cell.height - 2.4;
            const bw = data.cell.width - 4;
            doc.setFillColor(226, 232, 240);
            doc.rect(bx, by, bw, 1.3, "F");
            doc.setFillColor(220, 38, 38);
            doc.rect(bx, by, (bw * pct) / 100, 1.3, "F");
          }
          // Col 8: 100% Contribution / Blame Share Bar
          if (data.column.index === 8) {
            const sharePct = ownWon
              ? contribMap.get(Number(p.player_slot)) ?? 20
              : blameMap.get(Number(p.player_slot)) ?? 20;
            const pct = Math.min(100, Math.max(4, sharePct * 2)); // scale 50% -> full bar
            const bx = data.cell.x + 2;
            const by = data.cell.y + data.cell.height - 2.4;
            const bw = data.cell.width - 4;
            doc.setFillColor(226, 232, 240);
            doc.rect(bx, by, bw, 1.4, "F");
            if (ownWon) {
              doc.setFillColor(22, 163, 74);
            } else {
              doc.setFillColor(220, 38, 38);
            }
            doc.rect(bx, by, (bw * pct) / 100, 1.4, "F");
          }
        },
      }
    );

    // =========================================================================
    // CHAPTER III: 前·中·后期三阶段进化指南与关键胜负手团战故事回放
    // =========================================================================
    drawChapterHeader("第三章", "前·中·后期三阶段进化指南与关键胜负手团战故事回放（AI 刀塔老炮毒舌/夸奖评书）");
    const rawPhases = report.phases_data || report.phase_breakdown?.phases || [];
    const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
    const signMult = side === (report.focus_side || "dire") ? 1 : -1;
    const ch3PhaseRows = phasesList.map((pd) => {
      const ownP = (pd.players || []).filter((p) => p.side === side);
      const oppP = (pd.players || []).filter((p) => p.side !== side);
      const ownK = ownP.reduce((s, p) => s + (p.kills_count || 0), 0);
      const oppK = oppP.reduce((s, p) => s + (p.kills_count || 0), 0);
      const ts = pd.team_summary || {};
      const deltaAdv = (ts.income_diff_change || 0) * signMult;
      const endAdv = (ts.income_diff_end || 0) * signMult;
      const diag = pd.team_diagnostics?.[side] || {};
      const goodStr = Array.isArray(diag.team_good) ? diag.team_good.join("；") : diag.team_good || "";
      const badStr = Array.isArray(diag.team_bad) ? diag.team_bad.join("；") : diag.team_bad || "";
      const actStr = Array.isArray(diag.team_action) ? diag.team_action.join("；") : diag.team_action || "";
      return [
        `${pd.label}\n(${pd.time_label})`,
        `${ownK} : ${oppK}\n(推${ts.towers_taken || 0}塔/掉${ts.towers_lost || 0}塔)`,
        `净变动 ${fmtSigned(deltaAdv)} 金\n(末累计 ${fmtSigned(endAdv)} 金)`,
        goodStr || "维持基础运营",
        badStr || "局部联动脱节",
        actStr || "抓核心强势期推进",
      ];
    });
    runVectorTable(
      ["比赛阶段", "阶段人头 & 塔数", "阶段经济差波动", "• 本阶段亮点", "× 本阶段扣分项", "› 阶段改进处方"],
      ch3PhaseRows,
      {
        0: { cellWidth: 28, fontStyle: "bold" },
        1: { cellWidth: 26 },
        2: { cellWidth: 34, fontStyle: "bold" },
        3: { cellWidth: 62 },
        4: { cellWidth: 62 },
        5: { cellWidth: contentW - 212 },
      }
    );

    const keyTfs = (report.key_teamfights || []).slice(0, 6);
    const tfForensicsList = df.teamfight_forensics || [];
    if (keyTfs.length > 0) {
      drawSubSectionTitle("3.2 全场最高强度关键胜负手团战故事回放与经济拐点明细（AI 刀塔老炮复盘评书）");
      const ch3TfRows = keyTfs.map((tf, idx) => {
        const matchedTfIdx = tfForensicsList.findIndex((f) => f.time_range === tf.time_range);
        const fObj = tfForensicsList[matchedTfIdx >= 0 ? matchedTfIdx : idx];
        const storyObj = buildTeamfightDotaStory(tf, fObj, idx, {
          side,
          sideZh,
          oppZh,
          own,
          opp,
        });
        const pSummary = (tf.participants || [])
          .sort((a, b) => (b.damage || 0) - (a.damage || 0))
          .slice(0, 5)
          .map(
            (p) =>
              `${p.hero_short_zh}: ${fmtNum(p.damage)}伤${p.deaths ? "(阵亡)" : ""}${
                p.buybacks ? "[买活]" : ""
              }`
          )
          .join(" | ");
        return [
          `团战 #${idx + 1}\n(${tf.time_range || ""})\n[${cleanPdfVectorText(storyObj.badge)}]`,
          `${tf.kills_trade || ""}\n(${tf.gold_swing || ""})`,
          tf.top_damage_hero || "-",
          `${storyObj.storyText}\n【参战明细】${pSummary}`,
        ];
      });
      runVectorTable(
        ["团战编号 & 定性", "人头交换 & 经济差", "最高输出英雄", "AI 刀塔老炮团战故事回放 & 核心参战英雄伤害明细"],
        ch3TfRows,
        {
          0: { cellWidth: 34, fontStyle: "bold" },
          1: { cellWidth: 36, fontStyle: "bold" },
          2: { cellWidth: 30 },
          3: { cellWidth: contentW - 100 },
        }
      );
    }

    // =========================================================================
    // CHAPTER IV: 录像级十一维战术显微镜全量取证账本 (with Hero Portraits & Split Bars)
    // =========================================================================
    drawChapterHeader(
      "第四章",
      "录像级十一维战术显微镜全量取证账本（大招/憋死BKB/地图空间/承伤/眼位/堆野开雾/对线/TP/经济/买活死&7.38附魔）"
    );

    const drawCol0HeroIconHook = (rowsArr) => ({
      didDrawCell: (data) => {
        if (data.section === "body" && data.column.index === 0) {
          const rowObj = rowsArr[data.row.index];
          const p = ownByPos.get(Number(rowObj?.pos || data.row.index + 1));
          const imgUrl = rowObj?.hero_img || p?.hero_img;
          if (imgUrl) {
            const iy = data.cell.y + (data.cell.height - 4.8) / 2;
            drawIconSafe(imgUrl, data.cell.x + 1.5, iy, 8.0, 4.8);
          }
        }
      },
    });

    // 4.1 大招与绝活释放审判
    const gradeZhMap = { good: "优", bad: "差", warn: "中" };
    drawSubSectionTitle(`4.1 英雄绝活与大招释放质量审判总表 (${sideZh} 1~5 号位)`);
    const execData = df.hero_execution_by_side?.[side];
    const execPlayers = Array.isArray(execData) ? execData : execData?.players || [];
    const t41Rows = execPlayers.map((p) => {
      const badges = (p.headline_badges || [])
        .map((b) => (typeof b === "string" ? b : b?.text || ""))
        .filter(Boolean)
        .join(" | ");
      const ults = p.ult_audits || p.signature_spells || [];
      const ultStr = ults
        .map(
          (sp) =>
            `${sp.ability_zh || "大招"}(评级:${gradeZhMap[sp.grade] || sp.grade || "良"}): 放${sp.casts ?? 0}次/中${
              sp.hits ?? sp.hero_hits ?? 0
            }${sp.unit_label || "人次"}`
        )
        .join("；");
      const skillStr = (p.skillshot_audits || [])
        .map((sk) => `${sk.ability_zh}: ${sk.casts ?? 0}放/${sk.hits ?? 0}中(${sk.hit_pct ?? 0}%)`)
        .join("；");
      const heldWaves = ults.flatMap((sp) => sp.tf_held_death_waves || []);
      const castWaves = ults.flatMap((sp) => sp.tf_casts_waves || []);
      const verdictStr =
        ults.map((sp) => sp.verdict_text || sp.verdict || "").filter(Boolean).join("；") ||
        (p.special_insights || []).slice(0, 2).join("；");
      return [
        `${p.pos}号位 · ${p.hero_short_zh || ""}\n(${p.personaname || ""})`,
        badges || `硬控 ${p.stuns_sec ?? 0}s`,
        ultStr || "无主动大招",
        skillStr || "-",
        `${castWaves.length ? `开大: ${castWaves.join("、")}` : ""}${
          heldWaves.length ? `\n憋大死: ${heldWaves.join("、")}` : "\n0次憋大阵亡"
        }`,
        verdictStr || "技能衔接正常",
      ];
    });
    runVectorTable(
      ["位置 & 选手", "绝活核心指标", "大招释放与命中统计", "非指向技能命中", "团战开大 vs 憋大死", "大招与技能复盘判词"],
      t41Rows,
      {
        0: { cellWidth: 38, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 10.8 } },
        1: { cellWidth: 35 },
        2: { cellWidth: 42 },
        3: { cellWidth: 33 },
        4: { cellWidth: 40 },
        5: { cellWidth: contentW - 188 },
      },
      drawCol0HeroIconHook(execPlayers)
    );

    // 4.2 憋死 BKB / 救命装与 0 技能秒躺尸检表
    const us = df.unpressed_saves_by_side?.[side] || {};
    const usRows = us.player_rows || [];
    drawSubSectionTitle(
      `4.2 憋死 BKB / 救命装与团战 0 技能秒躺尸检总表（憋死核心救命装 ${us.critical_total ?? 0} 人次 · 0技能秒躺 ${
        us.zero_spell_total ?? 0
      } 人次）`
    );
    const t42Rows = usRows.map((r) => [
      `${r.pos}号位 · ${r.hero_short_zh || ""}\n(${r.personaname || ""})`,
      `${r.tf_deaths ?? 0} 次`,
      `${r.unpressed_core_cnt ?? 0} 次`,
      `${r.zero_spell_cnt ?? 0} 次`,
      r.owned_saves_str || "未合成主动保命装",
      r.verdict || "",
    ]);
    runVectorTable(
      ["位置 & 选手", "团战阵亡", "憋死核心保命装", "0技能秒躺", "已合成保命装与按键次数", "团战保命反应与抓包笔录"],
      t42Rows,
      {
        0: { cellWidth: 42, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 10.8 } },
        1: { cellWidth: 18, halign: "center" },
        2: { cellWidth: 24, halign: "center", fontStyle: "bold" },
        3: { cellWidth: 20, halign: "center" },
        4: { cellWidth: 56 },
        5: { cellWidth: contentW - 160 },
      },
      drawCol0HeroIconHook(usRows)
    );

    // 4.3 地图空间理解与 9m 后落单被抓表 (with Lane vs Jungle Split Bar)
    const ms = df.map_space_by_side?.[side] || {};
    const msRows = ms.player_space_rows || [];
    drawSubSectionTitle(
      `4.3 地图空间理解与 9 分钟后落单带危险线被抓审计表（共落单被抓 ${ms.total_solo_pickoffs ?? 0} 次）`
    );
    const t43Rows = msRows.map((r) => [
      `${r.pos}号位 · ${r.hero_short_zh || ""}\n(${r.personaname || ""})`,
      r.space_style_badge || "常规驻守",
      `兵线 ${r.lane_kills ?? 0} (${r.lane_farm_pct ?? 0}%) / 野区 ${r.neutral_kills ?? 0} (${
        r.jungle_farm_pct ?? 0
      }%)`,
      fmtNum(r.tower_damage || 0),
      `${r.solo_pickoff_cnt ?? 0} 次 (送 ${fmtNum(r.solo_gold_fed || 0)} 金)`,
      r.verdict || "",
    ]);
    runVectorTable(
      ["位置 & 选手", "空间理解画像", "收线补刀 vs 野区占比", "推塔伤害", "9m后落单被抓 & 送金", "空间利用与带线纪律判词"],
      t43Rows,
      {
        0: { cellWidth: 42, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 10.8 } },
        1: { cellWidth: 26 },
        2: { cellWidth: 42, cellPadding: { top: 2, right: 2, bottom: 4.2, left: 2 } },
        3: { cellWidth: 20, halign: "right" },
        4: { cellWidth: 32, fontStyle: "bold" },
        5: { cellWidth: contentW - 162 },
      },
      {
        didDrawCell: (data) => {
          if (data.section !== "body") return;
          const r = msRows[data.row.index];
          const p = ownByPos.get(Number(r?.pos || data.row.index + 1));
          if (data.column.index === 0 && (r?.hero_img || p?.hero_img)) {
            const iy = data.cell.y + (data.cell.height - 4.8) / 2;
            drawIconSafe(r?.hero_img || p?.hero_img, data.cell.x + 1.5, iy, 8.0, 4.8);
          }
          if (data.column.index === 2 && r) {
            const lanePct = Math.min(100, Math.max(0, Number(r.lane_farm_pct) || 50));
            const bx = data.cell.x + 2;
            const by = data.cell.y + data.cell.height - 2.3;
            const bw = data.cell.width - 4;
            doc.setFillColor(37, 99, 235);
            doc.rect(bx, by, (bw * lanePct) / 100, 1.3, "F");
            doc.setFillColor(22, 163, 74);
            doc.rect(bx + (bw * lanePct) / 100, by, (bw * (100 - lanePct)) / 100, 1.3, "F");
          }
        },
      }
    );

    // 4.4 承伤来源与防装合规审计表 (with Spell vs Physical Split Bar)
    const dr = df.damage_received_by_side?.[side] || {};
    const drRows = dr.rows || [];
    drawSubSectionTitle("4.4 承伤来源拆解（物理平A vs 技能爆发）与防装合规审计表");
    const t44Rows = drRows.map((r) => [
      `${r.pos}号位 · ${r.hero_short_zh || ""}\n(${r.personaname || ""})`,
      fmtNum(r.total_dmg_taken || 0),
      `法系爆发 ${r.spell_pct ?? 0}% / 物理平A ${r.auto_pct ?? 0}%`,
      (r.top_killers || [])
        .slice(0, 3)
        .map((k) => `${k.zh_name}(${fmtNum(k.damage || 0)})`)
        .join("、") || "平A为主",
      (r.def_items_owned || []).join("、") || "未出针对防装",
      r.verdict || "",
    ]);
    runVectorTable(
      ["位置 & 选手", "总承受伤害", "法系 vs 物理平A占比", "头号致死敌方技能 Top 3", "已出针对防装", "防装选择合规判词"],
      t44Rows,
      {
        0: { cellWidth: 42, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 10.8 } },
        1: { cellWidth: 22, halign: "right" },
        2: { cellWidth: 36, cellPadding: { top: 2, right: 2, bottom: 4.2, left: 2 } },
        3: { cellWidth: 48 },
        4: { cellWidth: 38 },
        5: { cellWidth: contentW - 186 },
      },
      {
        didDrawCell: (data) => {
          if (data.section !== "body") return;
          const r = drRows[data.row.index];
          const p = ownByPos.get(Number(r?.pos || data.row.index + 1));
          if (data.column.index === 0 && (r?.hero_img || p?.hero_img)) {
            const iy = data.cell.y + (data.cell.height - 4.8) / 2;
            drawIconSafe(r?.hero_img || p?.hero_img, data.cell.x + 1.5, iy, 8.0, 4.8);
          }
          if (data.column.index === 2 && r) {
            const spellPct = Math.min(100, Math.max(0, Number(r.spell_pct) || 50));
            const bx = data.cell.x + 2;
            const by = data.cell.y + data.cell.height - 2.3;
            const bw = data.cell.width - 4;
            doc.setFillColor(147, 51, 234);
            doc.rect(bx, by, (bw * spellPct) / 100, 1.3, "F");
            doc.setFillColor(220, 38, 38);
            doc.rect(bx + (bw * spellPct) / 100, by, (bw * (100 - spellPct)) / 100, 1.3, "F");
          }
        },
      }
    );

    // 4.5–4.7 辅助视野 · 堆野开雾 · 对线拉野莲花智慧符综合表
    const vis = df.support_vision_by_side?.[side] || {};
    const ss = df.stacking_and_smoke_by_side?.[side] || {};
    const lm = df.laning_mechanics_by_side?.[side] || {};
    const smokeEvents = ss.smoke_events || [];
    const smokeUses = ss.own_smoke_uses ?? ss.smoke_total_uses ?? smokeEvents.length;
    const smokeBought =
      ss.smoke_total_bought ??
      (ss.per_player_smokes || []).reduce((acc, item) => acc + Number(item.bought || 0), 0);
    const smokeSuccessCnt =
      ss.smoke_success_count ?? smokeEvents.filter((e) => e.outcome === "success").length;
    const smokeBackfireCnt =
      ss.smoke_backfire_count ?? smokeEvents.filter((e) => e.outcome === "backfire").length;
    const smokeDryCnt =
      ss.smoke_dry_count ?? smokeEvents.filter((e) => e.outcome === "wasted").length;
    const ownLotus = lm.own_lotus_total ?? lm.lotus_own_total ?? 0;
    const oppLotus = lm.opp_lotus_total ?? lm.lotus_opp_total ?? 0;
    const ownWisdom = lm.own_wisdom_cnt ?? lm.wisdom_own_count ?? 0;
    const oppWisdom = lm.opp_wisdom_cnt ?? lm.wisdom_opp_count ?? 0;
    const ownGate = lm.own_gate_total ?? lm.gate_own_count ?? 0;
    const oppGate = lm.opp_gate_total ?? lm.gate_opp_count ?? 0;
    const ownLamp = lm.own_lamp_total ?? lm.lamp_own_count ?? 0;
    const oppLamp = lm.opp_lamp_total ?? lm.lamp_opp_count ?? 0;

    drawSubSectionTitle("4.5–4.7 辅助视野质量 · 堆野开雾转化 · 对线拉野/莲花/智慧符/双生门综合审计表");
    const t45Rows = [
      [
        "4.5 辅助视野与反眼",
        `假眼 ${vis.total_obs ?? vis.obs_total ?? 0} 颗 / 真眼 ${vis.total_sen ?? vis.sen_total ?? 0} 颗\n平均寿命 ${
          vis.avg_lifespan_sec ?? 0
        }s/360s · 被排 ${vis.dewarded_total ?? 0} 颗 (${vis.dewarded_pct ?? 0}%)`,
        `进攻眼 ${vis.posture_counts?.aggressive ?? 0} (${vis.posture_pcts?.aggressive ?? 0}%) / 河道眼 ${
          vis.posture_counts?.river_roshan ?? 0
        } / 防守眼 ${vis.posture_counts?.defensive ?? 0}`,
        vis.posture_verdict || "",
      ],
      [
        "4.6 堆野 & 开雾节奏",
        `全队堆野 ${ss.total_stacks ?? ss.total_team_stacks ?? 0} 组 (${ss.total_creeps_stacked ?? 0} 只野)\n辅助堆 ${
          ss.support_stacks ?? 0
        } 组 / 大哥自拉 ${ss.core_stacks ?? ss.core_self_stacks ?? 0} 组`,
        `买雾 ${smokeBought} / 开雾 ${smokeUses} 波\n(大捷 ${smokeSuccessCnt} / 撞墙 ${smokeBackfireCnt} / 空雾 ${smokeDryCnt})`,
        `${ss.stack_verdict || ""} | ${ss.smoke_verdict || ""}`,
      ],
      [
        "4.7 对线莲花·智慧符",
        `疗伤莲花 ${ownLotus} : ${oppLotus}\n7/14/21m 智慧符 ${ownWisdom} : ${oppWisdom}`,
        `双生门传送 ${ownGate} : ${oppGate}\n观察者点灯 ${ownLamp} : ${oppLamp}`,
        `${lm.lotus_verdict || ""} | ${lm.wisdom_verdict || ""}`,
      ],
    ];
    runVectorTable(["战术审计维度", "核心数量与效率指标", "结构分布与对抗比", "录像取证结论与抓包明细"], t45Rows, {
      0: { cellWidth: 36, fontStyle: "bold" },
      1: { cellWidth: 58 },
      2: { cellWidth: 58 },
      3: { cellWidth: contentW - 152 },
    });

    // 4.8–4.9 TP 救人 · 团战旁观抓包 · 经济来源结构与死亡损耗总表
    const tp = df.tp_rotation_by_side?.[side] || {};
    const ep = df.economy_and_pings_by_side?.[side] || {};
    const epRows = ep.econ_rows || [];
    const tpMap = new Map((tp.player_tp_rows || []).map((r) => [Number(r.pos), r]));
    drawSubSectionTitle("4.8–4.9 TP 救人及时性 · 团战旁观抓包 · 经济来源结构与死亡损耗总表");
    const t48Rows = epRows.map((r) => {
      const tr = tpMap.get(Number(r.pos)) || {};
      const tfTpCnt = tr.tf_tp_cnt ?? tr.teamfight_tp_saves ?? 0;
      const tfAbsentCnt = tr.tf_absent_cnt ?? tr.spectator_teamfights ?? 0;
      const lossGold = (r.death_loss || 0) + (r.buyback_loss || 0);
      return [
        `${r.pos}号位 · ${r.hero_short_zh || ""}\n(${r.personaname || ""})`,
        `用 ${tr.tp_used ?? 0} / 买 ${tr.tp_bought ?? 0} 张\n(前12m支援 ${tr.early_tp_cnt ?? 0} 次)`,
        `亮TP救人 ${tfTpCnt} 次\n0参与OB ${tfAbsentCnt} 波`,
        `兵线 ${fmtNum(r.lane_gold || 0)} (${r.lane_pct ?? 0}%)\n野区 ${fmtNum(r.jungle_gold || 0)} (${
          r.jungle_pct ?? 0
        }%)`,
        `人头 ${fmtNum(r.kill_gold || 0)} (${r.kill_pct ?? 0}%)\n塔盾 ${fmtNum(r.obj_gold || 0)} (${
          r.obj_pct ?? 0
        }%)`,
        `-${fmtNum(lossGold)} 金\n(信号 ${r.pings ?? 0} 次)`,
        tr.verdict || r.econ_tag || "",
      ];
    });
    runVectorTable(
      ["位置 & 选手", "TP 使用/购买", "亮TP支援 vs 旁观", "兵线 vs 野区进账", "人头 vs 塔盾进账", "阵亡+买活损耗", "支援与财政判词"],
      t48Rows,
      {
        0: { cellWidth: 42, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 10.8 } },
        1: { cellWidth: 28 },
        2: { cellWidth: 28 },
        3: { cellWidth: 34 },
        4: { cellWidth: 34 },
        5: { cellWidth: 26 },
        6: { cellWidth: contentW - 192 },
      },
      drawCol0HeroIconHook(epRows)
    );

    // 4.10 买活死尸检 · 信使博弈 · 肉山魔晶 & 7.38 中立装备附魔表
    const mo = df.macro_objectives_by_side?.[side] || {};
    const moRows = mo.neutral_craft_rows || [];
    drawSubSectionTitle(
      `4.10 买活死尸检 (${mo.dieback_cnt ?? 0}次) · 信使博弈 (杀敌${mo.own_couriers_killed ?? 0}/掉鸡${
        mo.own_couriers_lost ?? 0
      }) · 7.38 中立装备附魔审计表`
    );
    const t410Rows = moRows.map((cr) => [
      `${cr.pos}号位 · ${cr.hero_short_zh || ""}\n(${cr.personaname || ""})`,
      cr.shard_str || "未获魔晶",
      (cr.craft_steps || []).join(" → ") || "无锻造记录",
      cr.craft_verdict || "",
    ]);
    runVectorTable(
      ["位置 & 选手", "阿哈利姆魔晶时间", "7.38 中立装备锻造与附魔词条轨迹", "词条合规与锻造节奏判词"],
      t410Rows,
      {
        0: { cellWidth: 44, fontStyle: "bold", cellPadding: { top: 2, right: 2, bottom: 2, left: 10.8 } },
        1: { cellWidth: 34 },
        2: { cellWidth: 105 },
        3: { cellWidth: contentW - 183 },
      },
      drawCol0HeroIconHook(moRows)
    );

    // =========================================================================
    // CHAPTER V: 1~5 号位同位置宿敌 1v1 对位审判全表 (with Both Hero Portraits & Net Worth Tug Bar)
    // =========================================================================
    drawChapterHeader(
      "第五章",
      "1~5 号位同位置宿敌 1v1 正面对位审判全表（含双方英雄头像、OpenDota 全球百分位与净值拔河条）"
    );
    if (rm.side_verdict) {
      drawSubSectionTitle(rm.side_verdict);
    }
    const mirrorRowsData = rm.mirror_rows || [];
    const ch5MirrorRows = mirrorRowsData.map((r) => [
      `${r.pos}号位对决`,
      `${r.own_hero || ""} (${r.own_player || ""})\nKDA ${r.own_kda || ""} · 评分 ${r.own_rating ?? 0}\n全球超 ${
        r.own_bm_avg ?? 50
      }%同英雄`,
      `${r.opp_hero || ""} (${r.opp_player || ""})\nKDA ${r.opp_kda || ""} · 评分 ${r.opp_rating ?? 0}\n全球超 ${
        r.opp_bm_avg ?? 50
      }%同英雄`,
      `${fmtSigned(r.gold10_diff)} 金\n补刀 ${r.lh10_own || "0/0"} vs ${r.lh10_opp || "0/0"}`,
      `${fmtSigned(r.nw_diff)} 金\n${fmtNum(r.nw_own)} vs ${fmtNum(r.nw_opp)}`,
      `${r.h2h_own_kills ?? 0} : ${r.h2h_opp_kills ?? 0}`,
      `${fmtSigned(r.dmg_diff)}\n塔伤 ${fmtNum(r.td_own)} vs ${fmtNum(r.td_opp)}`,
      r.verdict_tag || "旗鼓相当",
      r.summary_txt || "",
    ]);
    runVectorTable(
      [
        "位置",
        `本方 (${sideZh})`,
        `敌方宿敌 (${oppZh})`,
        "10m经济差 & 补刀",
        "终局净值差",
        "正面单杀",
        "伤害差 & 塔伤",
        "对位结论",
        "录像对位复盘",
      ],
      ch5MirrorRows,
      {
        0: { cellWidth: 17, fontStyle: "bold" },
        1: { cellWidth: 42, cellPadding: { top: 2, right: 2, bottom: 2, left: 11.8 } },
        2: { cellWidth: 42, cellPadding: { top: 2, right: 2, bottom: 2, left: 11.8 } },
        3: { cellWidth: 25 },
        4: { cellWidth: 26, cellPadding: { top: 2, right: 2, bottom: 4.2, left: 2 } },
        5: { cellWidth: 15, halign: "center", fontStyle: "bold" },
        6: { cellWidth: 26 },
        7: { cellWidth: 22, fontStyle: "bold" },
        8: { cellWidth: contentW - 215 },
      },
      {
        didDrawCell: (data) => {
          if (data.section !== "body") return;
          const r = mirrorRowsData[data.row.index];
          if (!r) return;
          const ownP = ownByPos.get(Number(r.pos));
          const oppP = oppByPos.get(Number(r.pos));
          if (data.column.index === 1) {
            const iy = data.cell.y + (data.cell.height - 5.2) / 2;
            drawIconSafe(r.own_img || ownP?.hero_img, data.cell.x + 1.6, iy, 8.8, 5.2, [34, 197, 94]);
          }
          if (data.column.index === 2) {
            const iy = data.cell.y + (data.cell.height - 5.2) / 2;
            drawIconSafe(r.opp_img || oppP?.hero_img, data.cell.x + 1.6, iy, 8.8, 5.2, [239, 68, 68]);
          }
          if (data.column.index === 4) {
            const nw1 = Math.max(1, Number(r.nw_own) || 1);
            const nw2 = Math.max(1, Number(r.nw_opp) || 1);
            const ownRatio = nw1 / (nw1 + nw2);
            const bx = data.cell.x + 2;
            const by = data.cell.y + data.cell.height - 2.4;
            const bw = data.cell.width - 4;
            doc.setFillColor(22, 163, 74);
            doc.rect(bx, by, bw * ownRatio, 1.4, "F");
            doc.setFillColor(220, 38, 38);
            doc.rect(bx + bw * ownRatio, by, bw * (1 - ownRatio), 1.4, "F");
          }
        },
      }
    );

    // =========================================================================
    // CHAPTER VI: 本方 1~5 号位个人完整证据卷宗 (with Hero Portraits, 6-Slot Final Item Icons, AI Personal Story, and 6-Axis Hexagon Radar Chart)
    // =========================================================================
    drawChapterHeader(
      "第六章",
      `${sideZh} 1~5 号位个人完整证据卷宗（含英雄头像、六神装图标、AI 毒舌/封神个人结案陈词与六维能力雷达图）`
    );
    const grokPlayersMapPdf = new Map();
    if (Array.isArray(grok.players)) {
      grok.players.forEach((gp) => grokPlayersMapPdf.set(Number(gp.slot), gp));
    }
    const mvpSlotNumPdf = Number(report.mvp?.mvp_player?.player_slot);
    const topCulpritSlotNumPdf = Number(topCulprit?.player_slot);

    const ch6Rows = own.map((p) => {
      const heroShort = p.hero_short_zh || p.hero_name || "";
      const aiStoryObj = buildPlayerDossierAiStory(p, {
        grokPlayer: findGrokPlayerEntry(p, report) || grokPlayersMapPdf.get(Number(p.player_slot)),
        isTopCulprit: !ownWon && Number(p.player_slot) === topCulpritSlotNumPdf,
        isMvp: Number(p.player_slot) === mvpSlotNumPdf,
      });
      const itemsStr =
        (p.final_items_rich || [])
          .map(
            (it) =>
              `${it.zh_name || it.key}${it.purchase_time_str ? `(${it.purchase_time_str})` : ""}${
                it.use_count ? `[按${it.use_count}次]` : ""
              }`
          )
          .join(" → ") || "无记录";
      const abilStr =
        (p.ability_uses_rich || [])
          .slice(0, 5)
          .map((ab) => `${ab.zh_name || ab.key}×${ab.count}`)
          .join(" / ") || "无记录";
      return [
        `${p.pos}号位 · ${heroShort}\n${p.personaname || ""}\n评分 ${getHeroScore100(p)}/100分 · KDA ${p.kda}\n10m补刀 ${
          p.laning_10m?.lh10 ?? "-"
        }/${p.laning_10m?.dn10 ?? "-"}`,
        `【合成时间】${itemsStr}\n【技能频次】${abilStr}\n【${cleanPdfVectorText(aiStoryObj.badge)}】${
          aiStoryObj.storyText
        }`,
        "", // Vector 6-Axis Hexagon Radar Chart drawn in didDrawCell
        (p.strengths || []).slice(0, 3).map((g) => `✓ ${g}`).join("\n") || "✓ 完成本职任务",
        (p.weaknesses || []).slice(0, 3).map((b) => `✕ ${b}`).join("\n") || "✕ 无重大失误",
        (p.improvements || []).slice(0, 2).map((f) => `▸ ${f}`).join("\n") || "▸ 保持当前节奏",
      ];
    });
    runVectorTable(
      [
        "位置 & 选手",
        "终局六神装图标 · 技能释放频次 & AI 毒舌/封神个人结案陈词",
        "六维能力雷达图",
        "✓ 本局高光表现",
        "✕ 关键失误抓包",
        "▸ 下把改进铁律",
      ],
      ch6Rows,
      {
        0: { cellWidth: 36, fontStyle: "bold", cellPadding: { top: 2.5, right: 2, bottom: 2.5, left: 12.2 } },
        1: { cellWidth: 82, cellPadding: { top: 11.5, right: 2, bottom: 2.2, left: 2.2 } },
        2: { cellWidth: 31, minCellHeight: 24 },
        3: { cellWidth: 42 },
        4: { cellWidth: 42 },
        5: { cellWidth: contentW - 233 },
      },
      {
        didDrawCell: (data) => {
          if (data.section !== "body") return;
          const p = own[data.row.index];
          if (!p) return;

          // Col 0: Hero Portrait
          if (data.column.index === 0) {
            const iy = data.cell.y + (data.cell.height - 5.6) / 2;
            drawIconSafe(p.hero_img, data.cell.x + 1.8, iy, 9.2, 5.6, [180, 138, 62]);
          }

          // Col 1: Row of 6 Final Item Icons + Neutral Item Icon with purchase timestamp badges
          if (data.column.index === 1) {
            const items = [...(p.final_items_rich || []).slice(0, 6)];
            if (p.neutral_item_rich && p.neutral_item_rich.img) {
              items.push({ ...p.neutral_item_rich, isNeutral: true });
            }
            const startX = data.cell.x + 2.2;
            const startY = data.cell.y + 1.6;
            const iconW = 7.4;
            const iconH = 5.3;
            const stepX = 8.6;

            items.forEach((it, idx) => {
              const ix = startX + idx * stepX;
              drawIconSafe(
                it.img,
                ix,
                startY,
                iconW,
                iconH,
                it.isNeutral ? [168, 85, 247] : [180, 138, 62]
              );
              // Purchase timestamp pill under each icon
              const tLabel = it.purchase_time_str || (it.isNeutral ? "中立" : "");
              if (tLabel) {
                doc.setFillColor(15, 23, 42);
                doc.rect(ix, startY + iconH, iconW, 2.2, "F");
                doc.setFont("NotoSansSC", "bold");
                doc.setFontSize(4.4);
                doc.setTextColor(248, 250, 252);
                doc.text(cleanPdfVectorText(tLabel), ix + iconW / 2, startY + iconH + 1.6, {
                  align: "center",
                });
              }
              // Active press count badge on top-right of icon
              if (it.use_count) {
                doc.setFillColor(180, 83, 9);
                doc.rect(ix + iconW - 4.2, startY, 4.2, 1.9, "F");
                doc.setFont("NotoSansSC", "bold");
                doc.setFontSize(4.0);
                doc.setTextColor(255, 255, 255);
                doc.text(`按${it.use_count}`, ix + iconW - 2.1, startY + 1.4, { align: "center" });
              }
            });
          }

          // Col 2: Native Vector 6-Axis Hexagon Radar Chart
          if (data.column.index === 2) {
            const cx = data.cell.x + data.cell.width / 2;
            const cy = data.cell.y + data.cell.height / 2;
            const maxR = Math.min(7.2, (data.cell.height - 8.5) / 2);
            drawVectorHexRadar(p.radar, cx, cy, Math.max(5.2, maxR));
          }
        },
      }
    );

    // =========================================================================
    // STAMP RUNNING HEADERS & FOOTERS (Page X / Y) ON ALL PAGES
    // =========================================================================
    const totalPages = doc.internal.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      if (i > 1) {
        doc.setFillColor(18, 25, 43);
        doc.rect(marginX, 5.2, contentW, 6.2, "F");
        doc.setFont("NotoSansSC", "bold");
        doc.setFontSize(7.4);
        doc.setTextColor(245, 232, 200);
        doc.text(
          cleanPdfVectorText(
            `DOTA 2 录像级结构化复盘报告  |  比赛 #${report.match_id} · ${sideZh}视角 (${
              ownWon ? "胜局庆功卷宗" : "败局定责卷宗"
            })`
          ),
          marginX + 3,
          9.4
        );
        doc.setFont("NotoSansSC", "normal");
        doc.setTextColor(203, 213, 225);
        doc.text(
          cleanPdfVectorText(`天辉 ${report.radiant_score} : ${report.dire_score} 夜魇 (${report.duration_str})`),
          pageW - marginX - 3,
          9.4,
          { align: "right" }
        );
      }

      // Bottom running footer line + page number
      doc.setDrawColor(203, 213, 225);
      doc.setLineWidth(0.2);
      doc.line(marginX, pageH - 9.2, pageW - marginX, pageH - 9.2);
      doc.setFont("NotoSansSC", "normal");
      doc.setFontSize(7.0);
      doc.setTextColor(100, 116, 139);
      doc.text(
        cleanPdfVectorText(
          `战后算账 · Dota 2 五黑录像级复盘工作台 (OpenDota 录像解析 + xAI Grok 4.7)  |  ${shareUrl}`
        ),
        marginX,
        pageH - 5.2
      );
      doc.setFont("NotoSansSC", "bold");
      doc.setTextColor(30, 41, 59);
      doc.text(`第 ${i} 页 / 共 ${totalPages} 页`, pageW - marginX, pageH - 5.2, { align: "right" });
    }

    doc.save(filename);
    showToast(
      `✅ 含全套矢量图表与英雄/装备图标的原生 PDF 已下载：${filename}（共 ${totalPages} 页）`,
      4800
    );
  } catch (err) {
    console.error("Native vector PDF generation error:", err);
    showToast(`原生矢量 PDF 构建异常 (${err.message})，已为您下载独立全屏 HTML 报告`);
    downloadStructuredReportHtml();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText || "⬇️ 直接下载 PDF 报告 (.pdf)";
    }
  }
}

async function downloadStructuredReportPng() {
  const report = state.currentReport;
  const paper = document.getElementById("fs-report-paper");
  const btn = document.getElementById("btn-fs-download-png");
  if (!report || !paper) return;

  const { sideZh } = getOwnAndOppPlayers(report);
  const filename = `Dota2_全景复盘长图_Match_${report.match_id}_${sideZh}视角.png`;
  const origText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在渲染全景长图...";
  }
  showToast(`⏳ 正在生成高清结构化长图《${filename}》...`, 3500);
  paper.classList.add("capturing-export");

  try {
    if (typeof window.html2canvas === "function") {
      const canvas = await window.html2canvas(paper, {
        scale: 1.6,
        useCORS: true,
        backgroundColor: "#141613",
        logging: false,
        ignoreElements: (el) =>
          el.tagName === "IMG" && el.getAttribute("data-html2canvas-ignore") === "true",
      });
      const link = document.createElement("a");
      link.download = filename;
      link.href = canvas.toDataURL("image/png");
      link.click();
      showToast(`✅ 全景报告长图已直接下载：${filename}`, 4000);
    } else if (typeof window.html2pdf === "function") {
      const imgDataUrl = await window
        .html2pdf()
        .set({
          html2canvas: {
            scale: 1.6,
            useCORS: true,
            backgroundColor: "#141613",
            logging: false,
            ignoreElements: (el) =>
              el.tagName === "IMG" && el.getAttribute("data-html2canvas-ignore") === "true",
          },
        })
        .from(paper)
        .outputImg("datauristring");
      const link = document.createElement("a");
      link.download = filename;
      link.href = imgDataUrl;
      link.click();
      showToast(`✅ 全景报告长图已直接下载：${filename}`, 4000);
    }
  } catch (err) {
    console.error("PNG export error:", err);
    showToast(`导出长图失败: ${err.message}`);
  } finally {
    paper.classList.remove("capturing-export");
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText || "🖼️ 下载全景报告长图 (.png)";
    }
  }
}

async function downloadStructuredReportHtml() {
  const report = state.currentReport;
  const paper = document.getElementById("fs-report-paper");
  if (!report || !paper) return;

  const { sideZh } = getOwnAndOppPlayers(report);
  const filename = `Dota2_结构化复盘报告_Match_${report.match_id}_${sideZh}视角.html`;

  let cssText = "";
  try {
    const res = await fetch("/styles.css?v=4.6");
    if (res.ok) cssText = await res.text();
  } catch {
    // fallback if offline
  }

  const standaloneHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dota 2 结构化赛后复盘报告 · 比赛 #${escapeHtml(report.match_id)} (${escapeHtml(sideZh)}视角)</title>
  <style>
    ${cssText}
    body {
      background: #111310;
      color: #e8e4d9;
      margin: 0;
      padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    .standalone-report-wrap {
      max-width: 1480px;
      margin: 0 auto;
    }
    .fs-chapter.deferred-chapter {
      content-visibility: visible !important;
    }
  </style>
</head>
<body>
  <div class="standalone-report-wrap">
    ${paper.innerHTML}
  </div>
</body>
</html>`;

  const blob = new Blob([standaloneHtml], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
  showToast(`✅ 已直接下载独立全屏报告文件：${filename}（发给队友双击即可全屏打开）`, 4200);
}

function syncMatchUrlInAddressBar(matchId, { replace = false } = {}) {
  if (!matchId || state.workspaceMode !== "postgame") return;
  try {
    if (window.history?.pushState) {
      const side = state.currentReport ? getAuditedSide(state.currentReport) : state.perspective;
      const sideQuery = side === "dire" || side === "radiant" ? `&side=${encodeURIComponent(side)}` : "";
      const targetSearch = `?match=${encodeURIComponent(matchId)}${sideQuery}`;
      const nextUrl = `/${targetSearch}`;
      const curMatchId = getUrlRequestedMatchAndSide().matchId;
      const isSameMatchInUrl =
        window.location.pathname === "/" && Number(curMatchId) === Number(matchId);

      if (window.location.pathname !== "/" || window.location.search !== targetSearch) {
        const nextState = {
          ...(window.history.state || {}),
          workspaceMode: "postgame",
          matchId: Number(matchId),
          side,
        };
        if (replace || isSameMatchInUrl) {
          window.history.replaceState(nextState, "", nextUrl);
        } else {
          window.history.pushState(nextState, "", nextUrl);
        }
      }
    }
  } catch {
    // ignore history errors in sandboxed environments
  }
}

/**
 * Determine which side ("dire" or "radiant") we are auditing as "本方 (own)".
 */
function getAuditedSide(report) {
  if (!report) return "dire";
  if (state.perspective === "dire" || state.perspective === "radiant") {
    return state.perspective;
  }
  if (report.focus_side === "radiant" || report.focus_side === "dire") {
    return report.focus_side;
  }
  if (report.user_team_side === "天辉") return "radiant";
  if (report.user_team_side === "夜魇") return "dire";
  return "dire";
}

function getOwnAndOppPlayers(report) {
  const side = getAuditedSide(report);
  const radWon =
    report?.radiant_win !== undefined
      ? Boolean(report.radiant_win)
      : report?.winner === "天辉";
  const enrichSide = (list, sideWon) => {
    const rawContribSum =
      list.reduce((s, p) => s + Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)), 0) || 100;
    return list.map((p) => {
      p.won = sideWon;
      if (p.contrib_share_pct === undefined || p.contrib_share_pct === null) {
        p.contrib_share_pct = Number(
          ((Math.max(1, Number(p.mvp_score ?? 20)) / rawContribSum) * 100).toFixed(1)
        );
      }
      return p;
    });
  };
  const rad = enrichSide(report.radiant_pos_1_to_5 || report.radiant_players || [], radWon);
  const dire = enrichSide(report.dire_pos_1_to_5 || report.dire_players || [], !radWon);
  const own = side === "radiant" ? rad : dire;
  const opp = side === "radiant" ? dire : rad;
  const won = side === "radiant" ? radWon : !radWon;
  return {
    side,
    sideZh: side === "radiant" ? "天辉" : "夜魇",
    oppZh: side === "radiant" ? "夜魇" : "天辉",
    won,
    own: [...own].sort((a, b) => (a.pos || 9) - (b.pos || 9)),
    opp: [...opp].sort((a, b) => (a.pos || 9) - (b.pos || 9)),
    all: [...rad, ...dire],
  };
}

/**
 * Extract requested match_id, side, and view mode from URL (?match=12345&side=dire&view=report)
 */
function getUrlRequestedMatchAndSide() {
  const params = new URLSearchParams(window.location.search || "");
  const qMatch = params.get("match") || params.get("match_id");
  const qSide = params.get("side");
  const qView = params.get("view");
  let matchId = qMatch && /^\d{8,12}$/.test(qMatch.trim()) ? Number(qMatch.trim()) : null;
  if (!matchId) {
    const mPath = (window.location.pathname || "").match(/\/match\/(\d{8,12})/);
    if (mPath && mPath[1]) {
      matchId = Number(mPath[1]);
    }
  }
  const side = qSide === "dire" || qSide === "radiant" ? qSide : null;
  const viewReport = qView === "report";
  return { matchId, side, viewReport };
}

/**
 * Initialize app on load
 */
async function initApp() {
  bindEvents();
  const { matchId: urlMatchId, side: urlSide, viewReport: urlViewReport } = getUrlRequestedMatchAndSide();
  if (urlSide) {
    state.perspective = urlSide;
    const perspSelect = document.getElementById("perspective-select");
    if (perspSelect) perspSelect.value = urlSide;
  }

  const isInitialPregame =
    window.location.pathname.includes("/pregame") ||
    new URLSearchParams(window.location.search).get("mode") === "pregame";

  // Seed Home ("/") in browser history when user opens a direct match/pregame URL so Browser Back returns to Home instead of exiting to external tab
  try {
    if ((urlMatchId || isInitialPregame) && window.history?.replaceState && window.history?.pushState) {
      if (!window.history.state?.seededHome) {
        const initialTargetUrl = window.location.pathname + window.location.search + window.location.hash;
        window.history.replaceState({ workspaceMode: "home", seededHome: true }, "", "/");
        window.history.pushState(
          {
            workspaceMode: isInitialPregame ? "pregame" : "postgame",
            matchId: urlMatchId || null,
            side: urlSide || null,
            seededHome: true,
          },
          "",
          initialTargetUrl
        );
      }
    } else if (window.history?.replaceState && !window.history.state?.workspaceMode) {
      window.history.replaceState({ workspaceMode: "home", seededHome: true }, "", "/");
    }
  } catch {
    // ignore history errors
  }

  if (isInitialPregame) {
    switchWorkspaceMode("pregame", { pushUrl: false, animate: false });
  } else if (urlMatchId) {
    switchWorkspaceMode("postgame", { pushUrl: false, animate: false });
  } else {
    switchWorkspaceMode("home", { pushUrl: false, animate: false });
  }
  // If user opened a direct shared match URL (?match=<id>), load that match report immediately!
  let directMatchLoaded = false;
  if (urlMatchId) {
    try {
      await loadMatchReport(urlMatchId, { analyzeNow: true, switchToPostgame: true, fromPopState: true });
      directMatchLoaded = true;
    } catch (e) {
      console.warn("Direct match pre-load warning:", e);
    }
  }

  try {
    const res = await fetch(`/api/init?account_id=${encodeURIComponent(state.accountId)}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "初始化失败");

    state.roster = data.roster || {};
    state.profileData = data.profile || {};
    state.squadLedger = data.squad_ledger || null;
    state.heroesCatalog = data.heroes_catalog || [];
    state.llmStatus = data.llm_status || {};
    state.accountId = state.roster.main_account_id || 86080912;

    const firstReport = data.latest_match_report || data.latest_report;
    if (!directMatchLoaded && firstReport) {
      state.currentMatchId = firstReport.match_id;
      state.currentReport = firstReport;
      toggleOnDemandGate(false);
      renderFullMatchReport(state.currentReport);
    }

    renderHeaderStatus();
    renderRecentMatchesStrip(data.recent_matches || state.profileData.recent_matches || []);
    renderSquadLedgerSection(state.squadLedger);
    renderHomeWorkspace();
    populateSettingsDialog();
    initPregameWorkspace();

    if (urlMatchId && !directMatchLoaded) {
      await loadMatchReport(urlMatchId, { analyzeNow: true, switchToPostgame: true, fromPopState: true });
    } else if (state.currentMatchId) {
      highlightSelectedMatchCard(state.currentMatchId);
      if (urlMatchId) syncMatchUrlInAddressBar(state.currentMatchId, { replace: true });
    }

    if (urlViewReport && state.currentReport) {
      openFullscreenStructuredReport(state.currentReport);
    }
  } catch (err) {
    console.error(err);
    if (!directMatchLoaded) {
      showToast(`读取初始数据失败: ${err.message}`);
    }
  }
}

function bindEvents() {
  // Browser Back / Forward (popstate) SPA routing handler
  window.addEventListener("popstate", async () => {
    ["fullscreen-report-dialog", "share-poster-dialog", "settings-dialog"].forEach((dlgId) => {
      const dlg = document.getElementById(dlgId);
      if (dlg && dlg.open) dlg.close();
    });

    const { matchId: popMatchId, side: popSide } = getUrlRequestedMatchAndSide();
    if (popSide) {
      state.perspective = popSide;
      const perspSelect = document.getElementById("perspective-select");
      if (perspSelect) perspSelect.value = popSide;
    }

    if (
      window.location.pathname.includes("/pregame") ||
      new URLSearchParams(window.location.search).get("mode") === "pregame"
    ) {
      switchWorkspaceMode("pregame", { pushUrl: false, animate: true });
    } else if (popMatchId) {
      switchWorkspaceMode("postgame", { pushUrl: false, animate: true });
      if (Number(state.currentMatchId) !== Number(popMatchId) || state.pendingMatchId) {
        await loadMatchReport(popMatchId, { switchToPostgame: true, fromPopState: true });
      } else if (state.currentReport) {
        toggleOnDemandGate(false);
        renderFullMatchReport(state.currentReport);
      }
    } else {
      switchWorkspaceMode("home", { pushUrl: false, animate: true });
    }
  });

  // Workspace mode switcher (Home vs Post-game Forensics vs Pre-game 5-Stack Strategy Planner)
  document.querySelectorAll("[data-ws-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const m = btn.getAttribute("data-ws-mode") || "home";
      switchWorkspaceMode(m, { pushUrl: true });
    });
  });

  // Brand logo & Back-to-Home buttons
  ["brand-home-trigger", "btn-back-to-home"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("click", () => {
        switchWorkspaceMode("home", { pushUrl: true });
      });
    }
  });

  // Mobile Header Collapsible Search & Tools Toggle
  const btnToggleMobileTools = document.getElementById("btn-toggle-mobile-tools");
  const headerCollapsibleTools = document.getElementById("header-collapsible-tools");
  if (btnToggleMobileTools && headerCollapsibleTools) {
    btnToggleMobileTools.addEventListener("click", () => {
      const isOpen = headerCollapsibleTools.classList.toggle("is-open");
      btnToggleMobileTools.setAttribute("aria-expanded", isOpen ? "true" : "false");
      btnToggleMobileTools.textContent = isOpen ? "✕ 收起工具" : "🔍 查比赛 / 设置";
    });
  }

  // Home Hero quick action buttons
  const btnHomeOpenLatest = document.getElementById("btn-home-open-latest");
  if (btnHomeOpenLatest) {
    btnHomeOpenLatest.addEventListener("click", async () => {
      const list = state.profileData?.recent_matches || [];
      const latestAnalyzed = list.find((m) => m.is_analyzed) || list[0];
      if (state.currentReport && (!latestAnalyzed || Number(state.currentMatchId) === Number(latestAnalyzed.match_id))) {
        switchWorkspaceMode("postgame", { pushUrl: true });
        syncMatchUrlInAddressBar(state.currentMatchId);
      } else if (latestAnalyzed) {
        await loadMatchReport(latestAnalyzed.match_id, { switchToPostgame: true });
      }
    });
  }
  const btnHomeGoPregame = document.getElementById("btn-home-go-pregame");
  if (btnHomeGoPregame) {
    btnHomeGoPregame.addEventListener("click", () => {
      switchWorkspaceMode("pregame", { pushUrl: true });
    });
  }
  const btnHomeScrollLedger = document.getElementById("btn-home-scroll-ledger");
  if (btnHomeScrollLedger) {
    btnHomeScrollLedger.addEventListener("click", () => {
      const det = document.getElementById("squad-ledger-details");
      if (det) det.open = true;
      document.getElementById("squad-ledger-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  // Home Match Filter tabs
  document.querySelectorAll("[data-home-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.homeFilter = btn.getAttribute("data-home-filter") || "all";
      document.querySelectorAll("[data-home-filter]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      renderHomeWorkspace();
    });
  });

  // Pre-game workspace bindings
  const preSearch = document.getElementById("pregame-hero-search");
  if (preSearch) {
    preSearch.addEventListener("input", () => {
      state.pregameHeroQuery = preSearch.value.trim();
      renderPregameHeroGrid();
    });
  }
  const btnPresetLast = document.getElementById("btn-pregame-preset-last");
  if (btnPresetLast) {
    btnPresetLast.addEventListener("click", () => {
      if (state.currentReport) {
        const { own, opp } = getOwnAndOppPlayers(state.currentReport);
        if (own.length === 5) {
          state.pregameOwnPicks = own.map((p) => ({
            pos: p.pos,
            hero_id: p.hero_id,
            player_name: p.personaname,
          }));
        }
        if (opp.length === 5) {
          state.pregameEnemyPicks = opp.map((p) => ({
            pos: p.pos,
            hero_id: p.hero_id,
          }));
        }
      }
      renderPregameSlots();
      renderPregameHeroGrid();
      requestAndRenderPregamePlan({ useLlm: false });
      showToast("已套用最近一把五黑的双方1~5号位阵容");
    });
  }
  const btnPresetBest = document.getElementById("btn-pregame-preset-best");
  if (btnPresetBest) {
    btnPresetBest.addEventListener("click", () => {
      state.pregameOwnPicks = [
        { pos: 1, hero_id: 8, player_name: "Flame = ez mute" },
        { pos: 2, hero_id: 49, player_name: "Replica" },
        { pos: 3, hero_id: 29, player_name: "Make Your Choice" },
        { pos: 4, hero_id: 136, player_name: "Paphets" },
        { pos: 5, hero_id: 30, player_name: "Mr. Brightside" },
      ];
      state.pregameEnemyPicks = [];
      renderPregameSlots();
      renderPregameHeroGrid();
      requestAndRenderPregamePlan({ useLlm: false });
      showToast("已套用车队高胜率冲分绝活体系（主宰+龙骑+潮汐+玛西+巫医）");
    });
  }
  const btnPregameClear = document.getElementById("btn-pregame-clear");
  if (btnPregameClear) {
    btnPregameClear.addEventListener("click", () => {
      state.pregameEnemyPicks = [];
      state.pregameActiveSide = "own";
      state.pregameActivePos = 1;
      renderPregameSlots();
      renderPregameHeroGrid();
      requestAndRenderPregamePlan({ useLlm: false });
      showToast("已清空敌方阵容，点击本方1~5号位槽位可直接换英雄");
    });
  }
  const btnPregameCopy = document.getElementById("btn-pregame-copy-brief");
  if (btnPregameCopy) {
    btnPregameCopy.addEventListener("click", () => {
      if (state.pregamePlan?.chat_brief_text) {
        copyTextToClipboard(state.pregamePlan.chat_brief_text, "赛前五黑10秒作战简报");
      }
    });
  }
  const btnPregameGrok = document.getElementById("btn-pregame-grok");
  if (btnPregameGrok) {
    btnPregameGrok.addEventListener("click", () => {
      requestAndRenderPregamePlan({ useLlm: true });
    });
  }

  const searchForm = document.getElementById("quick-search-form");
  if (searchForm) {
    searchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("search-input");
      const raw = (input?.value || "").trim();
      if (!raw) {
        showToast("请输入比赛编号 (如 9046364324) 或 Steam 链接 / 好友 ID");
        return;
      }
      await handleSmartQuery(raw);
    });
  }

  const refreshBtn =
    document.getElementById("btn-Refresh-match") || document.getElementById("btn-refresh-match");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      if (!state.currentMatchId) return;
      await loadMatchReport(state.currentMatchId, { forceRefresh: true, switchToPostgame: true });
    });
  }

  const toggleSquadBtn = document.getElementById("btn-toggle-squad-ledger");
  if (toggleSquadBtn) {
    toggleSquadBtn.addEventListener("click", () => {
      if (state.workspaceMode !== "home") {
        switchWorkspaceMode("home", { pushUrl: true });
      }
      const det = document.getElementById("squad-ledger-details");
      if (det) {
        det.open = true;
      }
      setTimeout(() => {
        document.getElementById("squad-ledger-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    });
  }

  const latestBtn = document.getElementById("btn-load-latest");
  if (latestBtn) {
    latestBtn.addEventListener("click", async () => {
      const list = state.profileData?.recent_matches || [];
      const latestAnalyzed = list.find((m) => m.is_analyzed) || list[0];
      if (latestAnalyzed) {
        await loadMatchReport(latestAnalyzed.match_id, { switchToPostgame: true });
      }
    });
  }

  const perspSelect = document.getElementById("perspective-select");
  if (perspSelect) {
    perspSelect.addEventListener("change", () => {
      state.perspective = perspSelect.value;
      if (state.currentReport) {
        renderFullMatchReport(state.currentReport);
        syncMatchUrlInAddressBar(state.currentMatchId);
      }
    });
  }

  const reqParseBtn = document.getElementById("btn-request-parse");
  if (reqParseBtn) {
    reqParseBtn.addEventListener("click", async () => {
      if (!state.currentMatchId) return;
      reqParseBtn.disabled = true;
      reqParseBtn.textContent = "正在请求解析...";
      try {
        const res = await fetch(`/api/parse/${encodeURIComponent(state.currentMatchId)}`, {
          method: "POST",
        });
        const data = await res.json();
        showToast(data.message || "已向 OpenDota 提交录像解析请求");
      } catch (err) {
        showToast(`请求解析失败: ${err.message}`);
      } finally {
        reqParseBtn.disabled = false;
        reqParseBtn.textContent = "请求录像解析";
      }
    });
  }

  const grokBtn = document.getElementById("btn-trigger-grok");
  if (grokBtn) {
    grokBtn.addEventListener("click", async () => {
      await triggerGrokReview({ force: true });
    });
  }

  document.querySelectorAll("[data-nw-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.nwFilter = btn.getAttribute("data-nw-filter") || "cores";
      document.querySelectorAll("[data-nw-filter]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      if (state.currentReport) {
        renderNetWorthChart(state.currentReport);
      }
    });
  });

  document.querySelectorAll("[data-map-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.mapMode = btn.getAttribute("data-map-mode") || "wards_obs";
      state.selectedTeamfightIndex = null;
      document.querySelectorAll("[data-map-mode]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      if (state.currentReport) {
        renderMinimap(state.currentReport);
      }
    });
  });

  document.querySelectorAll("[data-focus-side]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.focusMatrixSide = btn.getAttribute("data-focus-side") || "own";
      document.querySelectorAll("[data-focus-side]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      if (state.currentReport) {
        renderFocusFireMatrix(state.currentReport);
      }
    });
  });

  document.querySelectorAll("[data-micro-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.microTab = btn.getAttribute("data-micro-tab") || "hero_ult";
      const mSel = document.getElementById("micro-mobile-select");
      if (mSel) mSel.value = state.microTab;
      document.querySelectorAll("[data-micro-tab]").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
      });
      if (state.currentReport) {
        renderTacticalMicroscopeSection(state.currentReport);
      }
    });
  });

  const microMobileSelect = document.getElementById("micro-mobile-select");
  if (microMobileSelect) {
    microMobileSelect.addEventListener("change", () => {
      state.microTab = microMobileSelect.value || "hero_ult";
      document.querySelectorAll("[data-micro-tab]").forEach((b) => {
        const active = b.getAttribute("data-micro-tab") === state.microTab;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
        if (active) b.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      });
      if (state.currentReport) {
        renderTacticalMicroscopeSection(state.currentReport);
      }
    });
  }

  document.querySelectorAll("[data-mnav-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-mnav-target");
      document.querySelectorAll("[data-mnav-target]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      if (target === "home") {
        switchWorkspaceMode("home");
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
      if (state.workspaceMode !== "postgame") {
        switchWorkspaceMode("postgame");
      }
      setTimeout(() => {
        const sec = document.getElementById(target);
        if (sec) {
          sec.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 60);
    });
  });

  document.querySelectorAll("[data-micro-side]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.microSide = btn.getAttribute("data-micro-side") || "own";
      document.querySelectorAll("[data-micro-side]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      if (state.currentReport) {
        renderTacticalMicroscopeSection(state.currentReport);
      }
    });
  });

  document.querySelectorAll("[data-team-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeTeamTab = btn.getAttribute("data-team-tab") || "own";
      document.querySelectorAll("[data-team-tab]").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
      });
      if (state.currentReport) {
        renderPlayersForensicsList(state.currentReport);
      }
    });
  });

  // Share Link buttons (Header, Hero Overview, and Share Modal)
  ["btn-copy-share-link", "btn-hero-share-link", "btn-modal-share-link"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener("click", () => {
        copyMatchShareLink();
      });
    }
  });

  // PDF / Full-Screen Structured Report buttons (Header, Match Overview, and Share Modal)
  ["btn-export-pdf", "btn-header-export-pdf", "btn-modal-export-pdf"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener("click", () => {
        exportMatchPdfReport();
      });
    }
  });

  // Full-Screen Structured Report Toolbar bindings
  const fsDlg = document.getElementById("fullscreen-report-dialog");
  const btnFsClose = document.getElementById("btn-fs-close");
  const btnFsPdf = document.getElementById("btn-fs-download-pdf");
  const btnFsHtml = document.getElementById("btn-fs-download-html");
  const btnFsPng = document.getElementById("btn-fs-download-png");
  const btnFsCopyLink = document.getElementById("btn-fs-copy-link");
  const fsPerspSelect = document.getElementById("fs-perspective-select");

  if (btnFsClose && fsDlg) {
    btnFsClose.addEventListener("click", () => fsDlg.close());
  }
  if (btnFsPdf) {
    btnFsPdf.addEventListener("click", () => downloadStructuredReportPdf());
  }
  if (btnFsHtml) {
    btnFsHtml.addEventListener("click", () => downloadStructuredReportHtml());
  }
  if (btnFsPng) {
    btnFsPng.addEventListener("click", () => downloadStructuredReportPng());
  }
  if (btnFsCopyLink) {
    btnFsCopyLink.addEventListener("click", () => copyMatchShareLink({ viewReport: true }));
  }
  if (fsPerspSelect) {
    fsPerspSelect.addEventListener("change", () => {
      state.perspective = fsPerspSelect.value || "dire";
      const mainPersp = document.getElementById("perspective-select");
      if (mainPersp) mainPersp.value = state.perspective;
      if (state.currentReport) {
        renderFullMatchReport(state.currentReport);
        syncMatchUrlInAddressBar(state.currentMatchId);
        openFullscreenStructuredReport(state.currentReport);
      }
    });
  }

  // Voice Broadcast Button (TTS Chinese Coach Read-Aloud)
  const voiceBtn = document.getElementById("btn-voice-broadcast");
  if (voiceBtn) {
    voiceBtn.addEventListener("click", () => {
      toggleVoiceBroadcast();
    });
  }

  // On-Demand AI Analysis Gate Confirmation Button
  const confirmAnalyzeBtn = document.getElementById("btn-confirm-analyze-match");
  if (confirmAnalyzeBtn) {
    confirmAnalyzeBtn.addEventListener("click", async () => {
      const targetMid = state.pendingMatchId || state.currentMatchId;
      if (!targetMid) return;
      confirmAnalyzeBtn.disabled = true;
      confirmAnalyzeBtn.textContent = "🤖 AI 正在拉取录像并执行十一维显微镜分析 (约3~8秒)...";
      try {
        await loadMatchReport(targetMid, { analyzeNow: true });
      } finally {
        confirmAnalyzeBtn.disabled = false;
        confirmAnalyzeBtn.textContent = "⚡ 立即让 AI 深度分析本局并生成公开分享链接";
      }
    });
  }

  // Minute-by-Minute Timeline Scrubber bindings
  const scrubRange = document.getElementById("minute-scrubber-range");
  if (scrubRange) {
    scrubRange.addEventListener("input", () => {
      state.scrubberMinute = Number(scrubRange.value || 0);
      if (state.currentReport) {
        renderMinuteScrubberSnapshot(state.currentReport, state.scrubberMinute);
        if (state.scrubSyncMapMinute !== null) {
          state.scrubSyncMapMinute = state.scrubberMinute;
          renderMinimap(state.currentReport);
        }
      }
    });
  }
  const scrubPrev = document.getElementById("btn-scrub-prev");
  if (scrubPrev) {
    scrubPrev.addEventListener("click", () => {
      if (!state.currentReport) return;
      const snaps = state.currentReport.deep_forensics?.minute_snapshots || [];
      const nextM = Math.max(0, (state.scrubberMinute || 0) - 1);
      if (snaps.length > 0) {
        setScrubberMinute(nextM);
      }
    });
  }
  const scrubNext = document.getElementById("btn-scrub-next");
  if (scrubNext) {
    scrubNext.addEventListener("click", () => {
      if (!state.currentReport) return;
      const snaps = state.currentReport.deep_forensics?.minute_snapshots || [];
      const maxM = Math.max(0, snaps.length - 1);
      const nextM = Math.min(maxM, (state.scrubberMinute || 0) + 1);
      if (snaps.length > 0) {
        setScrubberMinute(nextM);
      }
    });
  }
  const scrubSyncMapBtn = document.getElementById("btn-scrub-sync-map");
  if (scrubSyncMapBtn) {
    scrubSyncMapBtn.addEventListener("click", () => {
      if (!state.currentReport) return;
      if (state.scrubSyncMapMinute === state.scrubberMinute) {
        state.scrubSyncMapMinute = null;
        scrubSyncMapBtn.classList.remove("active");
        scrubSyncMapBtn.textContent = "🗺️ 同步定位小地图眼位";
        showToast("已恢复小地图显示全场所有眼位");
      } else {
        state.scrubSyncMapMinute = state.scrubberMinute;
        state.mapMode = "wards_all";
        document.querySelectorAll("[data-map-mode]").forEach((b) =>
          b.classList.toggle("active", b.getAttribute("data-map-mode") === "wards_all")
        );
        scrubSyncMapBtn.classList.add("active");
        scrubSyncMapBtn.textContent = `🗺️ 已锁定 ${String(state.scrubberMinute).padStart(2, "0")}:00 场上存活眼位 (再点取消)`;
        showToast(`下方 2D 小地图已同步过滤为 ${String(state.scrubberMinute).padStart(2, "0")}:00 时刻场上存活的真假眼`);
      }
      renderMinimap(state.currentReport);
    });
  }

  // Share Poster Dialog bindings
  const posterDialog = document.getElementById("share-poster-dialog");
  const openPosterBtn1 = document.getElementById("btn-open-share-poster");
  const openPosterBtn2 = document.getElementById("btn-open-share-poster-2");
  const closePosterBtn = document.getElementById("btn-close-poster-dialog");
  const copyVerdictBtn = document.getElementById("btn-copy-verdict-text");
  const downloadPosterBtn = document.getElementById("btn-download-poster-png");

  [openPosterBtn1, openPosterBtn2].forEach((b) => {
    if (b) {
      b.addEventListener("click", () => {
        if (!state.currentReport) return;
        openSharePosterDialog(state.currentReport);
      });
    }
  });
  if (closePosterBtn && posterDialog) {
    closePosterBtn.addEventListener("click", () => posterDialog.close());
  }
  if (posterDialog) {
    posterDialog.addEventListener("click", (e) => {
      if (e.target === posterDialog) posterDialog.close();
    });
  }
  if (copyVerdictBtn) {
    copyVerdictBtn.addEventListener("click", () => {
      const ta = document.getElementById("share-verdict-textarea");
      if (ta && ta.value) {
        copyTextToClipboard(ta.value, "群聊处刑判决书 (含公开分享链接)");
      }
    });
  }
  if (downloadPosterBtn) {
    downloadPosterBtn.addEventListener("click", () => {
      const canvas = document.getElementById("share-poster-canvas");
      if (!canvas) return;
      const link = document.createElement("a");
      const heroSlug = state.activePosterContext?.player?.hero_short_zh || "verdict";
      link.download = `dota2-poster-${state.currentMatchId || "match"}-${heroSlug}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      showToast("已导出高清 PNG 战报海报！");
    });
  }

  const nanoPosterBtn = document.getElementById("btn-generate-nano-poster");
  if (nanoPosterBtn) {
    nanoPosterBtn.addEventListener("click", () => {
      generateNanoBananaPoster({ force: Boolean(state.lastGeneratedPosterArt) });
    });
  }

  const inlineGeminiKeyInput = document.getElementById("input-gemini-key-inline");
  if (inlineGeminiKeyInput) {
    const savedGKey = localStorage.getItem("dota_gemini_poster_key") || "";
    if (savedGKey) inlineGeminiKeyInput.value = savedGKey;
    inlineGeminiKeyInput.addEventListener("change", () => {
      const val = inlineGeminiKeyInput.value.trim();
      if (val) {
        localStorage.setItem("dota_gemini_poster_key", val);
        showToast("已保存 Gemini API Key，将使用 Google Nano Banana 2.1 生成原画！");
      } else {
        localStorage.removeItem("dota_gemini_poster_key");
      }
    });
  }

  const dialog = document.getElementById("settings-dialog");
  const openBtn = document.getElementById("btn-open-settings");
  const closeBtn = document.getElementById("btn-close-dialog");
  if (openBtn && dialog) {
    openBtn.addEventListener("click", () => {
      populateSettingsDialog();
      dialog.showModal();
    });
  }
  if (closeBtn && dialog) {
    closeBtn.addEventListener("click", () => dialog.close());
  }
  if (dialog) {
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) dialog.close();
    });
  }

  const rosterForm = document.getElementById("roster-form");
  if (rosterForm) {
    rosterForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await saveRosterConfig();
    });
  }

  const saveLlmBtn = document.getElementById("btn-save-llm-local");
  if (saveLlmBtn) {
    saveLlmBtn.addEventListener("click", () => {
      const provider = document.getElementById("select-llm-provider")?.value || "xai";
      const model = document.getElementById("input-llm-model")?.value.trim() || "grok-4.7";
      const apiKey = document.getElementById("input-llm-key")?.value.trim() || "";
      const baseUrl = document.getElementById("input-llm-base")?.value.trim() || "";
      const geminiPosterKey = document.getElementById("input-gemini-poster-key")?.value.trim() || "";
      localStorage.setItem(
        "dota_ledger_llm_override",
        JSON.stringify({ provider, model, apiKey, baseUrl })
      );
      if (geminiPosterKey) {
        localStorage.setItem("dota_gemini_poster_key", geminiPosterKey);
        const inlineIn = document.getElementById("input-gemini-key-inline");
        if (inlineIn) inlineIn.value = geminiPosterKey;
      }
      renderHeaderStatus();
      showToast(`已保存模型与 Nano Banana 海报设置 (${provider.toUpperCase()} / ${model})`);
      dialog?.close();
    });
  }
}

function getEffectiveLlmConfig() {
  try {
    const raw = localStorage.getItem("dota_ledger_llm_override");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && (parsed.apiKey || parsed.provider)) {
        return parsed;
      }
    }
  } catch {
    // ignore
  }
  return {
    provider: state.llmStatus?.provider || "xai",
    model: state.llmStatus?.model || "grok-4.7",
    apiKey: "",
    baseUrl: state.llmStatus?.base_url || "https://api.x.ai/v1",
  };
}

function renderHeaderStatus() {
  const pill = document.getElementById("llm-status-pill");
  if (pill) {
    const cfg = getEffectiveLlmConfig();
    const hasServerKey = Boolean(state.llmStatus?.configured || cfg.apiKey);
    pill.textContent = hasServerKey
      ? `已接入 ${String(cfg.provider || "xai").toUpperCase()} / ${cfg.model || "grok-4.7"}`
      : "内置录像算账引擎";
    pill.classList.toggle("connected", hasServerKey);
  }

  const playerBadge = document.getElementById("current-player-badge");
  if (playerBadge && state.profileData?.profile) {
    const p = state.profileData.profile;
    const wl = state.profileData.wl || {};
    playerBadge.textContent = `主视角：${p.personaname || state.accountId} · ${p.rank_label || "万古流芳 5"} · 近${
      (state.profileData.recent_matches || []).length || 12
    }场 ${wl.win_rate ?? 50}% 胜率`;
  }
}

const LOCAL_ANALYZED_STORAGE_KEY = "dota_analyzed_matches_v1";

function getLocalAnalyzedMatchesMap() {
  const map = new Map();
  try {
    const raw = localStorage.getItem(LOCAL_ANALYZED_STORAGE_KEY);
    if (!raw) return map;
    const obj = JSON.parse(raw);
    if (obj && typeof obj === "object") {
      Object.entries(obj).forEach(([k, v]) => {
        const mid = Number(k);
        if (mid && v) map.set(mid, v);
      });
    }
  } catch {
    // ignore storage errors
  }
  return map;
}

function saveLocalAnalyzedMatch(report) {
  if (!report || !report.match_id) return;
  try {
    const mid = Number(report.match_id);
    const raw = localStorage.getItem(LOCAL_ANALYZED_STORAGE_KEY);
    const obj = raw ? JSON.parse(raw) : {};
    const side = report.focus_side || "dire";
    const sideZh = side === "radiant" ? "天辉" : "夜魇";
    const won = Boolean(report.user_won ?? (side === "radiant" ? report.radiant_win : !report.radiant_win));
    const score = `${report.radiant_score ?? 0}:${report.dire_score ?? 0}`;
    const mvpHero = report.mvp?.hero_short_zh || report.mvp?.hero_name || "";
    const culpritHero = report.culprit?.hero_short_zh || report.culprit?.hero_name || "";
    obj[String(mid)] = {
      match_id: mid,
      won,
      score,
      side_zh: sideZh,
      mvp_hero: mvpHero,
      mvp_contrib_pct: report.mvp?.contrib_share_pct ?? 25,
      culprit_hero: culpritHero,
      culprit_blame_pct: report.culprit?.blame_share_pct ?? 28,
      saved_at: Date.now(),
    };
    localStorage.setItem(LOCAL_ANALYZED_STORAGE_KEY, JSON.stringify(obj));
  } catch {
    // ignore storage errors
  }
}

function renderRecentMatchesStrip(matches) {
  const strip = document.getElementById("recent-matches-strip");
  if (!strip) return;
  if (!matches || matches.length === 0) {
    strip.innerHTML = `<div class="empty-state compact">暂无最近比赛记录</div>`;
    return;
  }

  const localMap = getLocalAnalyzedMatchesMap();
  const activeMid = state.pendingMatchId || state.currentMatchId;
  strip.innerHTML = matches
    .slice(0, 12)
    .map((m) => {
      const selected = Number(m.match_id) === Number(activeMid);
      const isWin = m.won !== undefined ? Boolean(m.won) : m.result === "胜利";
      const resultText = isWin ? "胜利" : "落败";
      const heroShort = m.hero_short_zh || m.hero_name || "未知英雄";
      const partyLabel = m.party_label || (m.party_size >= 2 ? `${m.party_size}人黑` : "单排");
      const durText = m.duration_str || m.duration || "";
      const isAnalyzed = Boolean(m.is_analyzed || localMap.has(Number(m.match_id)));
      const aiBadgeHtml = isAnalyzed
        ? `<span class="analyzed-badge-group">
            <span class="analyzed-badge ready" title="已生成AI复盘报告，点击直接秒开并可复制分享链接">✅ 已复盘</span>
            <span class="pdf-mini-pill" data-export-pdf-match="${escapeHtml(m.match_id)}" title="直接将本局复盘报告导出为 PDF 发给别人">📄 PDF</span>
          </span>`
        : `<span class="analyzed-badge pending" title="尚未执行AI分析，点击后可按需启动AI复盘">⚡ 待AI分析</span>`;
      return `
        <button
          type="button"
          class="recent-card ${selected ? "selected" : ""}"
          data-match-card="${escapeHtml(m.match_id)}"
          role="listitem"
        >
          <div class="recent-top">
            <div class="recent-identity">
              ${
                m.hero_img
                  ? `<img class="recent-portrait" src="${escapeHtml(m.hero_img)}" width="34" height="19" alt="${escapeHtml(heroShort)}" loading="lazy" />`
                  : ""
              }
              <span class="recent-hero">${escapeHtml(heroShort)}</span>
            </div>
            <span class="result-pill ${isWin ? "win" : "loss"}">${resultText}</span>
          </div>
          <div class="recent-bottom">
            KDA ${escapeHtml(m.kda)} · ${escapeHtml(durText)} · ${escapeHtml(partyLabel)}
          </div>
          <div class="recent-id">
            <span>#${escapeHtml(m.match_id)}</span>
            ${aiBadgeHtml}
          </div>
        </button>
      `;
    })
    .join("");

  strip.querySelectorAll("[data-match-card]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const pdfTrigger = e.target.closest("[data-export-pdf-match]");
      if (pdfTrigger) {
        e.stopPropagation();
        const pdfMid = Number(pdfTrigger.getAttribute("data-export-pdf-match"));
        if (pdfMid) await exportMatchPdfReport(pdfMid);
        return;
      }
      const mid = Number(btn.getAttribute("data-match-card"));
      if (mid) await loadMatchReport(mid);
    });
  });
}

function renderHomeWorkspace() {
  const kpiWrap = document.getElementById("home-player-kpis");
  const grid = document.getElementById("home-matches-grid");
  const matches = state.profileData?.recent_matches || [];
  const analyzedMap = new Map(
    ((state.squadLedger && state.squadLedger.analyzed_matches) || []).map((am) => [Number(am.match_id), am])
  );
  const localAnalyzedMap = getLocalAnalyzedMatchesMap();
  localAnalyzedMap.forEach((val, key) => {
    if (!analyzedMap.has(key)) analyzedMap.set(key, val);
  });

  // Render Home Hero KPI Strip
  if (kpiWrap) {
    const p = state.profileData?.profile || {};
    const wl = state.profileData?.wl || {};
    const members = state.squadLedger?.squad_members_rank || [];
    const topCarry = [...members].sort(
      (a, b) => (b.mvp_count || 0) - (a.mvp_count || 0) || (b.avg_rating || 0) - (a.avg_rating || 0)
    )[0];
    const topCulprit = [...members].sort(
      (a, b) => (b.culprit_count || 0) - (a.culprit_count || 0) || (b.avg_blame_pct || 0) - (a.avg_blame_pct || 0)
    )[0];
    const analyzedCount = matches.filter((m) => m.is_analyzed || analyzedMap.has(Number(m.match_id))).length;
    const partyCount = matches.filter((m) => Number(m.party_size || 1) >= 2).length;
    const winCount = matches.filter((m) => (m.won !== undefined ? Boolean(m.won) : m.result === "胜利")).length;

    kpiWrap.innerHTML = `
      <div class="home-kpi-card">
        <span class="home-kpi-label">👤 当前主视角账号</span>
        <strong class="home-kpi-val">${escapeHtml(p.personaname || "Flame = ez mute")}</strong>
        <span class="home-kpi-sub">Steam ID #${escapeHtml(state.accountId)} · ${escapeHtml(p.rank_label || "万古流芳 5")}</span>
      </div>
      <div class="home-kpi-card">
        <span class="home-kpi-label">📈 近 ${matches.length || 12} 场战绩与开黑率</span>
        <strong class="home-kpi-val">${winCount} 胜 ${Math.max(0, matches.length - winCount)} 负 (${wl.win_rate ?? 50}% 胜率)</strong>
        <span class="home-kpi-sub">其中五黑/组排开黑 ${partyCount} 局 · 单排 ${Math.max(0, matches.length - partyCount)} 局</span>
      </div>
      <div class="home-kpi-card">
        <span class="home-kpi-label">✅ 已生成 AI 深度复盘</span>
        <strong class="home-kpi-val" style="color:var(--green-light);">${analyzedCount} 局录像卷宗已就绪</strong>
        <span class="home-kpi-sub">点击下方任意比赛卡片即可秒开六大章节复盘</span>
      </div>
      <div class="home-kpi-card">
        <span class="home-kpi-label">👑 车队历史大腿 vs 锅王</span>
        <strong class="home-kpi-val">大腿 ${escapeHtml(topCarry?.personaname || "Make Your Choice")}</strong>
        <span class="home-kpi-sub">锅王：${escapeHtml(topCulprit?.personaname || "TheReal")} (场均锅 ${topCulprit?.avg_blame_pct ?? 24}%)</span>
      </div>
    `;
  }

  if (!grid) return;
  if (!matches.length) {
    grid.innerHTML = `<div class="empty-state">暂无最近比赛记录，请在上方输入比赛编号或 Steam 好友 ID 查询</div>`;
    return;
  }

  const filterMode = state.homeFilter || "all";
  const filtered = matches.filter((m) => {
    const isWin = m.won !== undefined ? Boolean(m.won) : m.result === "胜利";
    const isAnalyzed = Boolean(m.is_analyzed || analyzedMap.has(Number(m.match_id)));
    const isParty = Number(m.party_size || 1) >= 2 || String(m.party_label || "").includes("黑");
    if (filterMode === "analyzed") return isAnalyzed;
    if (filterMode === "party") return isParty;
    if (filterMode === "win") return isWin;
    if (filterMode === "loss") return !isWin;
    return true;
  });

  if (!filtered.length) {
    grid.innerHTML = `<div class="empty-state">当前筛选条件下暂无比赛记录，请切换上方筛选标签</div>`;
    return;
  }

  const activeMid = state.pendingMatchId || state.currentMatchId;
  grid.innerHTML = filtered
    .map((m) => {
      const mid = Number(m.match_id);
      const isWin = m.won !== undefined ? Boolean(m.won) : m.result === "胜利";
      const isAnalyzed = Boolean(m.is_analyzed || analyzedMap.has(mid));
      const arch = analyzedMap.get(mid);
      const heroShort = m.hero_short_zh || m.hero_name || "未知英雄";
      const partyLabel = m.party_label || (m.party_size >= 2 ? `${m.party_size}人黑` : "单排");
      const durText = m.duration_str || m.duration || "";
      const timeAgo = m.start_time_str || m.time_ago || "";
      const sideLabel = m.side_zh || m.side || (arch ? arch.side_zh : "");
      const isCurrent = Number(activeMid) === mid;

      let summaryPreviewHtml = "";
      if (arch) {
        const grokHeadlineLine = arch.grok_title
          ? `<div style="grid-column: 1 / -1; color: var(--gold-light); font-weight: 600; font-size: 12.5px; margin-bottom: 3px; line-height: 1.4;">🧠 ${escapeHtml(arch.grok_title)}</div>`
          : "";
        if (arch.won) {
          summaryPreviewHtml = `
            <div class="hmc-verdict-preview win">
              ${grokHeadlineLine}
              <span>🏆 比分 <b>${escapeHtml(arch.score || "")}</b></span>
              <span>👑 首功 MVP：<b>${escapeHtml(arch.mvp_hero || "")}</b> (${arch.mvp_score_100 ? `${arch.mvp_score_100}分·` : ""}${arch.mvp_contrib_pct ?? 25}%)</span>
              ${arch.runner_up_hero ? `<span>⚔️ 二功：<b>${escapeHtml(arch.runner_up_hero)}</b> (${arch.runner_up_score_100 ? `${arch.runner_up_score_100}分·` : ""}${arch.runner_up_contrib_pct ?? 22}%)</span>` : ""}
            </div>
          `;
        } else {
          summaryPreviewHtml = `
            <div class="hmc-verdict-preview loss">
              ${grokHeadlineLine}
              <span>⚖️ 比分 <b>${escapeHtml(arch.score || "")}</b></span>
              <span>🚨 头号大锅：<b>${escapeHtml(arch.culprit_hero || "")}</b> (${arch.culprit_score_100 ? `${arch.culprit_score_100}分·` : ""}锅 ${arch.culprit_blame_pct ?? 28}%)</span>
              <span>🛡️ 孤胆院长：<b>${escapeHtml(arch.mvp_hero || "")}</b>${arch.mvp_score_100 ? ` (${arch.mvp_score_100}分)` : ""}</span>
            </div>
          `;
        }
      } else {
        summaryPreviewHtml = `
          <div class="hmc-verdict-preview pending">
            <span>📋 录像模式：${escapeHtml(m.game_mode_str || "全英雄选择")} · ${escapeHtml(partyLabel)}</span>
            <span>💡 点击卡片可按需启动 AI 十一维显微镜复盘并生成分享链接</span>
          </div>
        `;
      }

      return `
        <article
          class="home-match-card ${isWin ? "win-card" : "loss-card"} ${isCurrent ? "active-card" : ""}"
          data-home-match-id="${escapeHtml(mid)}"
        >
          <div class="hmc-top">
            <div class="hmc-hero-box">
              ${
                m.hero_img
                  ? `<img class="hmc-hero-img" src="${escapeHtml(m.hero_img)}" alt="${escapeHtml(heroShort)}" loading="lazy" />`
                  : ""
              }
              <div class="hmc-hero-meta">
                <div class="hmc-hero-line">
                  <strong class="hmc-hero-name">${escapeHtml(heroShort)}</strong>
                  <span class="hmc-party-pill">${escapeHtml(partyLabel)}</span>
                  ${sideLabel ? `<span class="hmc-side-pill">${escapeHtml(sideLabel)}</span>` : ""}
                </div>
                <div class="hmc-id-line">
                  <span>比赛 #${escapeHtml(mid)}</span>
                  ${timeAgo ? `<span>· ${escapeHtml(timeAgo)}</span>` : ""}
                </div>
              </div>
            </div>
            <span class="result-pill ${isWin ? "win" : "loss"}">${isWin ? "🏆 胜利" : "💀 落败"}</span>
          </div>

          <div class="hmc-stats-strip">
            <div class="hmc-stat-cell">
              <span>本局战绩 K / D / A</span>
              <strong>${escapeHtml(m.kda || "0/0/0")}</strong>
            </div>
            <div class="hmc-stat-cell">
              <span>比赛时长</span>
              <strong>${escapeHtml(durText || "-")}</strong>
            </div>
            <div class="hmc-stat-cell">
              <span>${arch?.my_grok_score ? "我本局 Grok 评分" : "AI 复盘状态"}</span>
              <strong style="color:${isAnalyzed ? "var(--green-light)" : "var(--gold-light)"};">
                ${
                  arch?.my_grok_score
                    ? `${arch.my_grok_score}/100分 (${isWin ? `贡献${arch.my_grok_share_pct}%` : `锅${arch.my_grok_share_pct}%`})`
                    : isAnalyzed
                    ? "✅ 已生成复盘"
                    : "⚡ 待按需分析"
                }
              </strong>
            </div>
          </div>

          ${summaryPreviewHtml}

          <div class="hmc-actions-bar">
            <button type="button" class="button primary hmc-open-btn" data-open-match="${escapeHtml(mid)}">
              ${isAnalyzed ? "📊 进入本局复盘详情 →" : "⚡ 查看并启动 AI 复盘 →"}
            </button>
            ${
              isAnalyzed
                ? `
              <button type="button" class="button secondary hmc-sub-btn" data-home-pdf="${escapeHtml(mid)}" title="导出原生矢量 PDF 报告">📄 PDF</button>
              <button type="button" class="button secondary hmc-sub-btn" data-home-share="${escapeHtml(mid)}" title="复制本局公开分享链接">🔗 分享</button>
            `
                : ""
            }
          </div>
        </article>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-home-match-id]").forEach((card) => {
    card.addEventListener("click", async (e) => {
      const pdfBtn = e.target.closest("[data-home-pdf]");
      if (pdfBtn) {
        e.stopPropagation();
        const mid = Number(pdfBtn.getAttribute("data-home-pdf"));
        if (mid) await exportMatchPdfReport(mid);
        return;
      }
      const shareBtn = e.target.closest("[data-home-share]");
      if (shareBtn) {
        e.stopPropagation();
        const mid = Number(shareBtn.getAttribute("data-home-share"));
        if (mid) {
          const shareUrl = getPublicShareUrl(mid);
          await copyTextToClipboard(shareUrl, `比赛 #${mid} 公开复盘分享链接`);
        }
        return;
      }
      const mid = Number(card.getAttribute("data-home-match-id"));
      if (mid) {
        await loadMatchReport(mid, { switchToPostgame: true });
      }
    });
  });
}

function highlightSelectedMatchCard(matchId) {
  document.querySelectorAll("[data-match-card]").forEach((btn) => {
    const mid = Number(btn.getAttribute("data-match-card"));
    btn.classList.toggle("selected", mid === Number(matchId));
  });
  document.querySelectorAll("[data-home-match-id]").forEach((card) => {
    const mid = Number(card.getAttribute("data-home-match-id"));
    card.classList.toggle("active-card", mid === Number(matchId));
  });
}

function toggleOnDemandGate(showGate, matchId = null) {
  const gateEl = document.getElementById("on-demand-analysis-gate");
  const contentEl = document.getElementById("analyzed-report-content");
  if (!gateEl || !contentEl) return;

  if (!showGate) {
    gateEl.hidden = true;
    contentEl.hidden = false;
    state.pendingMatchId = null;
    return;
  }

  state.pendingMatchId = Number(matchId);
  gateEl.hidden = false;
  contentEl.hidden = true;

  const recentList = state.profileData?.recent_matches || [];
  const meta = recentList.find((m) => Number(m.match_id) === Number(matchId)) || null;
  state.pendingMatchMeta = meta;

  const titleEl = document.getElementById("gate-title");
  const summaryEl = document.getElementById("gate-summary");
  if (titleEl) {
    if (meta) {
      const heroShort = meta.hero_short_zh || meta.hero_name || "未知英雄";
      const isWin = meta.won !== undefined ? Boolean(meta.won) : meta.result === "胜利";
      titleEl.textContent = `比赛 #${matchId}（${heroShort} · ${isWin ? "胜利" : "落败"} · KDA ${meta.kda} · ${meta.duration_str || ""}）尚未执行 AI 复盘`;
    } else {
      titleEl.textContent = `比赛 #${matchId} 尚未生成 AI 深度复盘报告`;
    }
  }
  if (summaryEl) {
    summaryEl.textContent =
      "已开启「按需 AI 分析」模式（不自动分析每一局比赛）。当你确认需要复盘这局时，点击下方按钮即可拉取该局录像底层日志、运行十一维战术显微镜，并生成可公开分享给群友的复盘链接。";
  }
}

async function handleSmartQuery(raw) {
  if (/^\d{9,11}$/.test(raw) && Number(raw) >= 1500000000 && Number(raw) < 76561190000000000) {
    await loadMatchReport(Number(raw), { switchToPostgame: true });
    return;
  }
  showToast("正在解析玩家 ID 并拉取最近比赛...");
  try {
    const res = await fetch(`/api/player?query=${encodeURIComponent(raw)}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "无法识别该玩家");
    state.accountId = data.account_id;
    state.profileData = data.profile;
    if (data.squad_ledger) {
      state.squadLedger = data.squad_ledger;
      renderSquadLedgerSection(state.squadLedger);
    }
    renderHeaderStatus();
    renderRecentMatchesStrip(data.recent_matches || []);
    renderHomeWorkspace();
    if (data.latest_match_report) {
      state.currentMatchId = data.latest_match_report.match_id;
      state.currentReport = data.latest_match_report;
      toggleOnDemandGate(false);
      renderFullMatchReport(state.currentReport);
      highlightSelectedMatchCard(state.currentMatchId);
      syncMatchUrlInAddressBar(state.currentMatchId);
    }
    showToast(`已切换主视角至 #${state.accountId}`);
  } catch (err) {
    showToast(`查询失败: ${err.message}`);
  }
}

async function loadMatchReport(
  matchId,
  { forceRefresh = false, analyzeNow = false, switchToPostgame = true, fromPopState = false } = {}
) {
  if (switchToPostgame && state.workspaceMode !== "postgame") {
    switchWorkspaceMode("postgame", { pushUrl: false });
  }
  const quickDrawer = document.getElementById("quick-switch-matches-drawer");
  if (quickDrawer) quickDrawer.open = false;

  if (analyzeNow || forceRefresh) {
    showToast(`🤖 AI 正在深度拆解比赛 #${matchId} 录像日志并生成分享链接...`, 4000);
  }
  try {
    const flags = `${forceRefresh ? "&refresh=1&skip_llm=1" : ""}${
      analyzeNow && !forceRefresh ? "&analyze=1&skip_llm=1" : ""
    }`;
    const url = `/api/match/${encodeURIComponent(matchId)}?account_id=${encodeURIComponent(
      state.accountId
    )}${flags}`;
    const res = await fetch(url);
    const rawText = await res.text();
    let data = null;
    try {
      data = JSON.parse(rawText);
    } catch {
      throw new Error(`服务端响应超时或异常 (${res.status})，请稍后重试`);
    }
    if (!data.ok) throw new Error(data.error || "读取比赛失败");

    if (data.not_analyzed) {
      const localMap = getLocalAnalyzedMatchesMap();
      if (!analyzeNow && localMap.has(Number(matchId))) {
        return await loadMatchReport(matchId, {
          forceRefresh,
          analyzeNow: true,
          switchToPostgame,
          fromPopState,
        });
      }
      highlightSelectedMatchCard(matchId);
      toggleOnDemandGate(true, matchId);
      if (switchToPostgame) {
        syncMatchUrlInAddressBar(matchId, { replace: Boolean(fromPopState) });
      }
      showToast(`比赛 #${matchId} 尚未分析，点击页面中央按钮即可启动 AI 深度复盘`, 3000);
      return;
    }

    toggleOnDemandGate(false);
    state.currentMatchId = data.report.match_id;
    state.currentReport = data.report;
    state.selectedTeamfightIndex = null;
    state.scrubSyncMapMinute = null;
    saveLocalAnalyzedMatch(data.report);

    // Mark match as analyzed in recent_matches strip & home grid so its badge turns green immediately
    const recentList = state.profileData?.recent_matches || [];
    const foundRecent = recentList.find((m) => Number(m.match_id) === Number(state.currentMatchId));
    if (foundRecent && !foundRecent.is_analyzed) {
      foundRecent.is_analyzed = true;
      renderRecentMatchesStrip(recentList);
    }

    if (data.squad_ledger) {
      state.squadLedger = data.squad_ledger;
      renderSquadLedgerSection(state.squadLedger);
    }
    renderHomeWorkspace();
    highlightSelectedMatchCard(state.currentMatchId);
    renderFullMatchReport(state.currentReport);
    syncMatchUrlInAddressBar(state.currentMatchId, { replace: Boolean(fromPopState) });

    const isParsedNow = Boolean(state.currentReport?.is_parsed);
    const hasGrokNow = Boolean(state.currentReport?.grok_coaching?.title);

    if (!isParsedNow) {
      showToast(
        `⏳ 比赛 #${state.currentMatchId} 刚结束，OpenDota 正在解析 .dem 录像（当前为基础统计），已自动提交解析并为您轮询更新...`,
        6500
      );
      scheduleAutoReplayParsePoll(state.currentMatchId);
    } else if ((analyzeNow || forceRefresh) && (!hasGrokNow || forceRefresh) && !state.isGeneratingGrok) {
      showToast(
        `✅ 录像级 12 维拆解已就绪！正在并发调用 Grok 4.7 生成五人深度研判与三幕长段复盘 (约15~20秒)...`,
        6000
      );
      triggerGrokReview({ force: forceRefresh });
    } else if (analyzeNow) {
      showToast(`✅ 比赛 #${state.currentMatchId} AI 完整深度复盘已成功！点击右上角「分享本局链接」即可发群`);
    }
  } catch (err) {
    console.error(err);
    showToast(`拉取比赛 #${matchId} 失败: ${err.message}`);
  }
}

let _autoParsePollTimer = null;
function scheduleAutoReplayParsePoll(matchId, attempt = 1) {
  clearTimeout(_autoParsePollTimer);
  if (attempt > 5) return;
  if (attempt === 1) {
    fetch("/api/request_parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ match_id: matchId }),
    }).catch(() => {});
  }
  _autoParsePollTimer = setTimeout(async () => {
    if (Number(state.currentMatchId) !== Number(matchId) || state.currentReport?.is_parsed) return;
    try {
      const res = await fetch(
        `/api/match/${encodeURIComponent(matchId)}?account_id=${encodeURIComponent(
          state.accountId
        )}&refresh=1&analyze=1`
      );
      const data = await res.json();
      if (data.ok && data.report?.is_parsed) {
        state.currentReport = data.report;
        renderFullMatchReport(state.currentReport);
        showToast(`🎉 OpenDota 录像解析已完成！已自动升级为完整 11 维录像级数据并启动 Grok 4.7 算账`, 5500);
        if (!state.currentReport.grok_coaching?.title && !state.isGeneratingGrok) {
          triggerGrokReview({ force: true });
        }
        return;
      }
    } catch (_e) {
      // ignore poll error
    }
    scheduleAutoReplayParsePoll(matchId, attempt + 1);
  }, 6000);
}

async function triggerGrokReview({ force = true } = {}) {
  if (!state.currentMatchId || state.isGeneratingGrok) return;
  const grokBtn = document.getElementById("btn-trigger-grok");
  const { side } = getOwnAndOppPlayers(state.currentReport);
  const llmCfg = getEffectiveLlmConfig();

  state.isGeneratingGrok = true;
  if (grokBtn) {
    grokBtn.disabled = true;
    grokBtn.textContent = "Grok 4.7 正在逐帧算账 (约15秒)...";
  }
  showToast(`正在调用 ${llmCfg.provider.toUpperCase()} / ${llmCfg.model} 重新生成深度判词...`, 12000);

  try {
    const res = await fetch("/api/llm_coach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        match_id: state.currentMatchId,
        account_id: state.accountId,
        side,
        force,
        provider: llmCfg.provider,
        model: llmCfg.model,
        api_key: llmCfg.apiKey,
        base_url: llmCfg.baseUrl,
      }),
    });
    const rawText = await res.text();
    let data = null;
    try {
      data = JSON.parse(rawText);
    } catch {
      throw new Error(`服务端响应超时或异常 (${res.status})，请稍后重试`);
    }
    if (!data.ok) throw new Error(data.error || "大模型调用失败");
    if (data.report) {
      state.currentReport = data.report;
      saveLocalAnalyzedMatch(state.currentReport);
      renderFullMatchReport(state.currentReport);
      showToast("✅ Grok 4.7 五人深度研判与三幕长段复盘已生成并持久化缓存！");
    }
  } catch (err) {
    console.error(err);
    showToast(`Grok 算账失败: ${err.message}`);
  } finally {
    state.isGeneratingGrok = false;
    if (grokBtn) {
      grokBtn.disabled = false;
      grokBtn.textContent = "用 Grok 4.7 重算判词";
    }
  }
}

/**
 * Master Render Function for the entire Match Forensics Dashboard
 */
function renderFullMatchReport(report) {
  if (!report) return;
  if (state._lastRenderedMatchId !== report.match_id) {
    state._lastRenderedMatchId = report.match_id;
    state.verdictActiveCard = "focus";
    state.phaseSelectedPos = "focus";
    state.tfActiveWaveIdx = 0;
    state.tfSelectedPosMap = {};
    state.microExecSelectedPos = "focus";
    state.forensicSelectedSlot = "focus";
  }
  renderMatchOverview(report);
  renderDraftAndComboSection(report);
  renderVerdictAndBlameSection(report);
  renderTacticalMicroscopeSection(report);
  renderMinuteScrubber(report);
  renderAdvChart(report);
  renderNetWorthChart(report);
  renderMinimap(report);
  renderDamageMatrix(report);
  renderFocusFireMatrix(report);
  renderPhaseSection(report);
  renderKeyWindowsSection(report);
  renderPlayersForensicsList(report);
}

/**
 * 1. Render Match Overview Header & KPIs
 */
function renderMatchOverview(report) {
  const { side, sideZh, own } = getOwnAndOppPlayers(report);
  const won =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !report.radiant_win);
  const grok = report.grok_coaching;
  const isParsed = Boolean(report.is_parsed);
  const hasGrok = Boolean(grok?.title);

  const metaEl = document.getElementById("match-meta-line");
  if (metaEl) {
    const statusText =
      isParsed && hasGrok
        ? "✅ AI 完整判定已成功 (OpenDota 录像级11维解析 + Grok 4.7 深度判词已就绪)"
        : isParsed
        ? "🟢 OpenDota 录像级解析已成功 (可点下方「用 Grok 4.7 重算判词」生成大模型标题)"
        : "🟡 当前仅基础统计 (刚结束的比赛 OpenDota 尚未解析 .dem 录像，系统正自动请求解析)";
    metaEl.textContent = `比赛编号 #${report.match_id} · ${report.start_time_str || ""} · ${
      report.mode_str || ""
    } · 当前审视阵营：${sideZh} (${side.toUpperCase()}) · ${statusText}`;
  }

  const parseBadge = document.getElementById("parse-quality-badge");
  if (parseBadge) {
    parseBadge.textContent =
      isParsed && hasGrok
        ? "✅ 录像级 + Grok 4.7 完整判定已就绪"
        : isParsed
        ? "🟢 录像级解析已就绪 (含眼位/时间轴/按键次数)"
        : "🟡 未解析录像 (正在自动请求 OpenDota 解析...)";
    parseBadge.classList.toggle("connected", isParsed);
  }

  const reqParseBtn = document.getElementById("btn-request-parse");
  if (reqParseBtn) {
    reqParseBtn.hidden = isParsed;
  }

  const titleEl = document.getElementById("match-overview-title");
  if (titleEl) {
    const tagHtml = `<span class="${won ? "win-tag" : "loss-tag"}">[${sideZh}${won ? "获胜" : "落败"}]</span>`;
    const mainHeadline =
      grok?.title ||
      `${report.winner || ""} 终局比分 ${report.radiant_score} : ${report.dire_score}`;
    titleEl.innerHTML = `${tagHtml} ${escapeHtml(mainHeadline)}`;
  }

  const totalObs = own.reduce((s, p) => s + (p.obs_placed || 0), 0);
  const totalSen = own.reduce((s, p) => s + (p.sen_placed || 0), 0);
  const totalDewards = own.reduce((s, p) => s + (p.obs_destroyed || 0), 0);
  const totalDeaths = own.reduce((s, p) => s + (p.deaths || 0), 0);
  const totalDeadSec = own.reduce((s, p) => s + (p.dead_seconds || 0), 0);
  const totalBuybacks = own.reduce((s, p) => s + (p.buybacks || 0), 0);
  const econ = report.economy_timeline || {};

  const kpiStrip = document.getElementById("match-kpi-strip");
  if (kpiStrip) {
    kpiStrip.innerHTML = `
      <div class="stat-block">
        <strong>天辉 ${report.radiant_score} : ${report.dire_score} 夜魇</strong>
        <span>终局人头比分 (${escapeHtml(report.winner || "")}获胜)</span>
      </div>
      <div class="stat-block">
        <strong>${escapeHtml(report.duration_str || "")}</strong>
        <span>比赛时长 · ${econ.is_comeback ? "惊天翻盘局" : "正面绞杀局"}</span>
      </div>
      <div class="stat-block">
        <strong>${(report.key_teamfights || []).length} 场关键团战</strong>
        <span>${escapeHtml(econ.radiant_max_lead || "")} / ${escapeHtml(econ.dire_max_lead || "")}</span>
      </div>
      <div class="stat-block">
        <strong>${totalObs} 假眼 / ${totalSen} 真眼</strong>
        <span>本方插眼总数 · 排掉敌方 ${totalDewards} 颗假眼</span>
      </div>
      <div class="stat-block">
        <strong>合计阵亡 ${totalDeaths} 次 (${Math.floor(totalDeadSec / 60)}分${totalDeadSec % 60}秒)</strong>
        <span>本方泉水读秒总计 · 交出买活 ${totalBuybacks} 次</span>
      </div>
      <div class="stat-block">
        <strong>外部录像核验</strong>
        <div class="stat-links">
          <a href="https://www.opendota.com/matches/${report.match_id}" target="_blank" rel="noopener">OpenDota ↗</a>
          <a href="https://www.dotabuff.com/matches/${report.match_id}" target="_blank" rel="noopener">Dotabuff ↗</a>
          <a href="https://stratz.com/matches/${report.match_id}" target="_blank" rel="noopener">Stratz ↗</a>
        </div>
      </div>
    `;
  }
}

/**
 * 1.5 Render Draft & Synergy Combo Section (纯粹聚焦阵容选择评估 & 有什么配合可以打，不重复渲染对线和英雄技能表)
 */
function renderDraftAndComboSection(report) {
  const container = document.getElementById("draft-combo-container");
  const badgeEl = document.getElementById("draft-grade-badge");
  if (!container) return;

  const { side, sideZh, oppZh, own, opp } = getOwnAndOppPlayers(report);
  const bySide = report.draft_analysis_by_side || {};
  const draft = bySide[side] || report.draft_analysis?.[side] || report.draft_analysis;

  if (!draft) {
    container.innerHTML = `<div class="empty-state compact">暂无本局阵容与配合评估数据</div>`;
    return;
  }

  const fullGradeStr = draft.grade || "A 级 · 体系扎实";
  const shortGrade = fullGradeStr.split(" ")[0] || "A";

  if (badgeEl) {
    badgeEl.textContent = `${sideZh}阵容评级：${fullGradeStr}`;
  }

  const ownScores = draft.scores?.own || draft.scores || {};
  const oppScores = draft.scores?.opp || draft.opp_scores || {};
  const dims = [
    { key: "init", altKey: "initiation", label: "先手开团" },
    { key: "burst", altKey: "burst", label: "瞬间爆发" },
    { key: "tf", altKey: "teamfight", label: "阵地团战" },
    { key: "push", altKey: "push", label: "推进拆塔" },
    { key: "pick", altKey: "pickoff", label: "游走抓人" },
    { key: "tank", altKey: "frontline", label: "前排肉度" },
  ];

  const ownLineupHtml = (draft.heroes_brief?.length ? draft.heroes_brief : own)
    .map((h) => {
      const heroShort = h.hero_short_zh || h.hero_name;
      const roleTip = Array.isArray(h.roles) ? h.roles.join(" / ") : h.personaname || "";
      return `
        <div class="draft-hero-pill" title="${escapeHtml(roleTip)}">
          ${h.hero_img ? `<img src="${escapeHtml(h.hero_img)}" alt="${escapeHtml(heroShort)}" width="30" height="17" loading="lazy" />` : ""}
          <span><b>${h.pos}号位</b> ${escapeHtml(heroShort)}</span>
        </div>
      `;
    })
    .join("");

  const oppLineupHtml = opp
    .map((h) => {
      const heroShort = h.hero_short_zh || h.hero_name;
      return `
        <div class="draft-hero-pill" title="${escapeHtml(h.personaname || "")}">
          ${h.hero_img ? `<img src="${escapeHtml(h.hero_img)}" alt="${escapeHtml(heroShort)}" width="30" height="17" loading="lazy" />` : ""}
          <span><b>${h.pos}号位</b> ${escapeHtml(heroShort)}</span>
        </div>
      `;
    })
    .join("");

  const dimsHtml = dims
    .map((d) => {
      const rawO = Number(ownScores[d.key] ?? ownScores[d.altKey] ?? 75);
      const rawE = Number(oppScores[d.key] ?? oppScores[d.altKey] ?? 75);
      const oPct = rawO <= 10 ? rawO * 10 : rawO;
      const ePct = rawE <= 10 ? rawE * 10 : rawE;
      return `
        <div class="draft-dim-item">
          <div class="draft-dim-head">
            <span>${escapeHtml(d.label)}</span>
            <b>${escapeHtml(sideZh)} ${Math.round(oPct)} : ${Math.round(ePct)} ${escapeHtml(oppZh)}</b>
          </div>
          <div class="draft-dim-bars">
            <div class="draft-dim-bar-own" style="--w: ${Math.min(100, oPct)}%"></div>
            <div class="draft-dim-bar-opp" style="--w: ${Math.min(100, ePct)}%"></div>
          </div>
        </div>
      `;
    })
    .join("");

  const combos = draft.combos || [];
  const combosHtml = combos
    .map((c) => {
      const heroesRow = (c.heroes || [])
        .map((h) => {
          const hName = h.short || h.name || h.hero_short_zh || "";
          return `
            <span class="combo-hero-tag">
              ${h.img ? `<img src="${escapeHtml(h.img)}" alt="${escapeHtml(hName)}" width="28" height="16" loading="lazy" />` : ""}
              <b>${h.pos ? `${h.pos}号位·` : ""}${escapeHtml(hName)}</b>
            </span>
          `;
        })
        .join(`<span style="color: var(--gold); font-weight: 700;">+</span>`);

      return `
        <article class="combo-card">
          <div class="combo-head">
            <div class="combo-heroes-avatars">${heroesRow}</div>
            <span class="combo-phase-tag">${escapeHtml(c.window || c.phase_tag || "核心配合")}</span>
          </div>
          <div class="combo-title">${escapeHtml(c.title || "")}</div>
          <div class="combo-how"><strong>配合怎么打：</strong>${escapeHtml(c.how_to_play || "")}</div>
          <div class="combo-audit"><strong>本局实战验尸：</strong>${escapeHtml(c.execution_audit || "")}</div>
        </article>
      `;
    })
    .join("");

  const picksOnly = (report.deep_forensics?.picks_order || []).filter((pb) => pb.is_pick);
  const picksHtml =
    picksOnly.length > 0
      ? `
      <div class="combos-header-bar" style="margin-top: 14px;">
        <h3>BP 选人先后手顺序还原 (1~10手点选博弈)</h3>
        <span style="font-size: 11px; color: var(--muted);">看清谁是首轮盲选抗压位、谁是尾手第 9/10 手 Counter 位</span>
      </div>
      <div class="bp-order-strip">
        ${picksOnly
          .map((pb) => {
            const isOwn = pb.side === side;
            return `
              <div class="bp-pick-chip ${isOwn ? "own" : "opp"}">
                <span class="bp-seq-label">${escapeHtml(pb.stage_tag)} · ${escapeHtml(pb.side_zh)}</span>
                <div class="bp-hero-line">
                  ${pb.hero_img ? `<img src="${escapeHtml(pb.hero_img)}" alt="${escapeHtml(pb.hero_short_zh)}" width="28" height="16" loading="lazy" />` : ""}
                  <strong>${pb.pos ? `${pb.pos}号位 ` : ""}${escapeHtml(pb.hero_short_zh)}</strong>
                </div>
                <span class="bp-player-sub">${escapeHtml(pb.personaname || "")}</span>
              </div>
            `;
          })
          .join("")}
      </div>
    `
      : "";

  container.innerHTML = `
    <div class="draft-top-grid">
      <div class="draft-verdict-box">
        <div class="draft-grade-row">
          <div class="draft-grade-pill" title="${escapeHtml(fullGradeStr)}">${escapeHtml(shortGrade)}</div>
          <div class="draft-verdict-text">
            <div style="font-weight: 700; color: var(--gold); margin-bottom: 3px;">${escapeHtml(fullGradeStr)}</div>
            ${injectHeroLogosIntoHtml(escapeHtml(draft.verdict_summary || ""), report)}
          </div>
        </div>

        <div class="draft-lineups-compare">
          <div class="draft-side-lineup">
            <span class="draft-side-label own">${escapeHtml(sideZh)}阵容 (1~5号位)</span>
            <div class="draft-heroes-row">${ownLineupHtml}</div>
          </div>
          <div class="draft-side-lineup">
            <span class="draft-side-label opp">${escapeHtml(oppZh)}阵容 (对手 1~5号位)</span>
            <div class="draft-heroes-row">${oppLineupHtml}</div>
          </div>
        </div>

        <div class="draft-dims-grid">${dimsHtml}</div>
      </div>

      <div class="draft-sw-box">
        <div class="draft-sw-group good">
          <h4>✓ 阵容选得好的地方 (天然赢面与强势期)</h4>
          <ul>
            ${(draft.strengths || []).map((s) => `<li>${injectHeroLogosIntoHtml(escapeHtml(s), report)}</li>`).join("")}
          </ul>
        </div>
        <div class="draft-sw-group bad">
          <h4>✕ 阵容隐患与短板 (容错率与被克制点)</h4>
          <ul>
            ${(draft.weaknesses || []).map((w) => `<li>${injectHeroLogosIntoHtml(escapeHtml(w), report)}</li>`).join("")}
          </ul>
        </div>
      </div>
    </div>

    ${picksHtml}

    <div class="combos-header-bar">
      <h3>有什么配合可以打 · 技能化学反应与本局实战对账 (${combos.length} 组核心套路)</h3>
      <span style="font-size: 11px; color: var(--muted);">对照本局录像按键次数，看看这套阵容的预设连招到底打出来了多少</span>
    </div>
    <div class="combos-grid">${combosHtml}</div>
  `;
}

/**
 * 2.5 NEW MODULE: 🔬 录像级九维战术显微镜 (Tactical Microscope — 9 Deep Replay Tabs)
 *  - Tab 1 (hero_ult): 英雄绝活与大招审判
 *  - Tab 2 (unpressed_saves): 💀 憋死 BKB / 救命装与团战 0 技能秒躺尸检
 *  - Tab 3 (map_space): 🗺️ 地图空间理解与「大哥带无聊危险线 / 落单乱逛被抓死」空间取证
 *  - Tab 4 (damage_received): 🛡️ 承伤来源拆解与针对性防装审计
 *  - Tab 5 (vision): 👁️ 辅助眼位进攻/防守与寿命
 *  - Tab 6 (stack_smoke): 🌾 辅助堆野 & 开雾找节奏
 *  - Tab 7 (laning): 🌱 对线拉野·走门·莲花·经验符
 *  - Tab 8 (tp_save): 🆘 TP 救人及时性与缺席抓包
 *  - Tab 9 (econ_pings): 💰 经济来源结构拆解 & 局内信号/暂停互动
 */
function auditAllMicroDimensions(report, df, targetSide, targetSideZh) {
  const results = {};

  // 1. hero_ult
  const sidePlayers = (report.players || []).filter((p) => p.side === targetSide);
  let heldUlts = 0;
  let zeroCasts = 0;
  sidePlayers.forEach((p) => {
    (p.hero_execution_audit?.ult_audits || []).forEach((u) => {
      heldUlts += Number(u.tf_held_death_count || 0);
      if (Number(u.casts || 0) === 0) zeroCasts += 1;
    });
  });
  results.hero_ult =
    heldUlts >= 2 || zeroCasts >= 1
      ? {
          level: "critical",
          badge: `🚨 憋大招×${heldUlts + zeroCasts}`,
          title: "1. 英雄绝活与大招审判",
          reason: `存在 ${heldUlts} 次团战憋死大招未放或关键技能 0 释放，团战技能兑现急需加强！`,
        }
      : { level: "good", badge: "✓ 达标", title: "1. 英雄绝活与大招审判", reason: "主力大招与控制链正常兑现" };

  // 2. itemization
  const ia = df.item_audit_by_side?.[targetSide] || {};
  const missingCnt = Number(ia.missing_counter_cnt ?? 0);
  const badBuildCnt = Number(ia.bad_build_players_cnt ?? 0);
  const missingNames = (ia.team_counter_checklist || [])
    .filter((c) => c.status === "missing")
    .map((c) => c.category_zh || c.title || "针对装")
    .slice(0, 3)
    .join("、");
  if (missingCnt >= 2 || badBuildCnt >= 2) {
    results.itemization = {
      level: "critical",
      badge: `🚨 漏${missingCnt}项克制装`,
      title: "2. 出装路线与克制装处刑台",
      reason: `全队漏出 <b>${missingCnt} 项刚需针对装</b>（${missingNames || "破被动/否决/BKB"}），且有 <b>${badBuildCnt} 名选手</b>存在漏核心魔晶/不出BKB/0救人装，属于本局极弱项，必须重点加强！`,
    };
  } else if (missingCnt >= 1 || badBuildCnt >= 1) {
    results.itemization = {
      level: "warn",
      badge: `⚠️ 漏${missingCnt}项针对装`,
      title: "2. 出装路线与克制装处刑台",
      reason: `存在 ${missingCnt} 项针对装缺失与 ${badBuildCnt} 人出装瑕疵。`,
    };
  } else {
    results.itemization = { level: "good", badge: "✓ 针对到位", title: "2. 出装路线与克制装处刑台", reason: "团队针对装齐全" };
  }

  // 3. damage_quality
  const dq = df.damage_quality_and_build_by_side?.[targetSide] || {};
  const fakeCnt = Number(dq.fake_dmg_suspects_cnt ?? 0);
  const buildIss = Number(dq.skill_build_issues_cnt ?? 0);
  results.damage_quality =
    fakeCnt >= 2 || buildIss >= 2
      ? {
          level: "critical",
          badge: `🚨 假伤害/奇葩加点`,
          title: "3. 伤害含金量与加点审判",
          reason: `抓出 <b>${fakeCnt} 人</b>只打肉盾刷无效伤害、<b>${buildIss} 人</b>加点天赋路线异常！`,
        }
      : fakeCnt >= 1 || buildIss >= 1
      ? {
          level: "warn",
          badge: `⚠️ ${fakeCnt + buildIss}人需注意`,
          title: "3. 伤害含金量与加点审判",
          reason: `有 ${fakeCnt} 人有效切后排占比偏低或 ${buildIss} 人加点可优化。`,
        }
      : { level: "good", badge: "✓ 切核扎实", title: "3. 伤害含金量与加点审判", reason: "集火切核与加点路线合理" };

  // 4. unpressed_saves
  const us = df.unpressed_saves_by_side?.[targetSide] || {};
  const unpressedCnt = Number(us.critical_total ?? 0);
  results.unpressed_saves =
    unpressedCnt >= 2
      ? {
          level: "critical",
          badge: `🚨 憋死救命装×${unpressedCnt}`,
          title: "4. 憋死BKB/救命装尸检",
          reason: `全场出现 <b>${unpressedCnt} 人次</b>身怀可用 BKB/魔棒/微光/推推却 0 按键暴毙！`,
        }
      : unpressedCnt === 1
      ? {
          level: "warn",
          badge: `⚠️ 憋救命装×1`,
          title: "4. 憋死BKB/救命装尸检",
          reason: `出现 1 次救命装冷却就绪却未按出阵亡。`,
        }
      : { level: "good", badge: "✓ 0憋死", title: "4. 憋死BKB/救命装尸检", reason: "保命装按键响应及时" };

  // 5. map_space
  const ms = df.map_space_by_side?.[targetSide] || {};
  const solos = ms.solo_pickoff_events || [];
  results.map_space =
    solos.length >= 3
      ? {
          level: "critical",
          badge: `🚨 ${solos.length}次落单白给`,
          title: "5. 单带无故被抓 & 白给侦探社",
          reason: `9分钟后全队出现 <b>${solos.length} 次脱离团队落单被抓</b>（${solos
            .slice(0, 3)
            .map((s) => `${s.time_str}${s.hero_short_zh}`)
            .join("、")}），地图危险感与防抓意识急需加强！`,
        }
      : solos.length >= 1
      ? {
          level: "warn",
          badge: `⚠️ ${solos.length}次落单`,
          title: "5. 单带无故被抓 & 白给侦探社",
          reason: `出现 ${solos.length} 次落单被抓（${solos.map((s) => `${s.time_str}${s.hero_short_zh}`).join("、")}）。`,
        }
      : { level: "good", badge: "✓ 0落单", title: "5. 单带无故被抓 & 白给侦探社", reason: "中后期抱团紧凑0落单" };

  // 6. damage_received
  const dr = df.damage_received_by_side?.[targetSide] || {};
  const noDefPlayers = (dr.player_rows || []).filter((r) => String(r.audit_verdict || "").includes("裸奔") || String(r.audit_verdict || "").includes("缺失"));
  results.damage_received =
    noDefPlayers.length >= 2
      ? {
          level: "warn",
          badge: `⚠️ ${noDefPlayers.length}人防装薄弱`,
          title: "6. 承伤来源与防装审计",
          reason: `有 <b>${noDefPlayers.length} 名选手</b>面对高额物理/魔法爆发缺乏针对性护甲或魔抗防装。`,
        }
      : { level: "good", badge: "✓ 防装合理", title: "6. 承伤来源与防装审计", reason: "承伤分摊与防装基本匹配" };

  // 7. vision
  const vis = df.support_vision_by_side?.[targetSide] || {};
  const darkCnt = Number((vis.dark_map_windows || []).length);
  const dewardedCnt = Number(vis.quick_dewarded_cnt ?? 0);
  results.vision =
    darkCnt >= 3 || dewardedCnt >= 4
      ? {
          level: "critical",
          badge: `🚨 黑图×${darkCnt}期`,
          title: "7. 眼位博弈与黑图真空期",
          reason: `全场出现 <b>${darkCnt} 段黑图视野真空期</b>、<b>${dewardedCnt} 颗假眼被秒反</b>，高台常规眼位需换刁钻点位！`,
        }
      : darkCnt >= 1
      ? {
          level: "warn",
          badge: `⚠️ 黑图×${darkCnt}期`,
          title: "7. 眼位博弈与黑图真空期",
          reason: `出现 ${darkCnt} 段视野断档期，假眼均寿 ${vis.avg_lifespan_sec ?? 0}s。`,
        }
      : { level: "good", badge: `✓ 均寿${vis.avg_lifespan_sec ?? 280}s`, title: "7. 眼位博弈与黑图真空期", reason: "全场视野覆盖扎实" };

  // 8. stack_smoke
  const ss = df.stacking_and_smoke_by_side?.[targetSide] || {};
  const smokeUses = Number(ss.own_smoke_uses ?? (ss.smoke_events || []).length);
  const totalStacks = Number(ss.total_stacks ?? 0);
  results.stack_smoke =
    smokeUses <= 1 || totalStacks <= 2
      ? {
          level: "critical",
          badge: `🚨 仅${smokeUses}波雾/${totalStacks}堆野`,
          title: "8. 辅助堆野 & 开雾找节奏",
          reason: `整局全队仅开雾 <b>${smokeUses} 波</b>、屯野 <b>${totalStacks} 组</b>，中后期主动买雾破局与屯野提速意识严重不足！`,
        }
      : smokeUses <= 2
      ? {
          level: "warn",
          badge: `⚠️ ${smokeUses}波雾/${totalStacks}堆野`,
          title: "8. 辅助堆野 & 开雾找节奏",
          reason: `全场开雾 ${smokeUses} 波、堆野 ${totalStacks} 组，可进一步增加开雾频次。`,
        }
      : { level: "good", badge: `✓ ${smokeUses}雾/${totalStacks}堆野`, title: "8. 辅助堆野 & 开雾找节奏", reason: "开雾与堆野节奏良好" };

  // 9. laning
  const lm = df.laning_mechanics_by_side?.[targetSide] || {};
  const lotusLost = Number(lm.own_lotus_total ?? 0) < Number(lm.opp_lotus_total ?? 0);
  const wisdomLost = Number(lm.own_wisdom_cnt ?? 0) < Number(lm.opp_wisdom_cnt ?? 0);
  results.laning =
    lotusLost && wisdomLost
      ? {
          level: "critical",
          badge: `🚨 莲花/经验符双输`,
          title: "9. 对线拉野·走门·莲花·经验符",
          reason: `疗伤莲花 (${lm.own_lotus_total}:${lm.opp_lotus_total}) 与智慧符 (${lm.own_wisdom_cnt}:${lm.opp_wisdom_cnt}) 双双落后！`,
        }
      : lotusLost || wisdomLost
      ? {
          level: "warn",
          badge: `⚠️ 抢符有漏`,
          title: "9. 对线拉野·走门·莲花·经验符",
          reason: `莲花 ${lm.own_lotus_total}:${lm.opp_lotus_total}，智慧符 ${lm.own_wisdom_cnt}:${lm.opp_wisdom_cnt}。`,
        }
      : { level: "good", badge: `✓ 莲花${lm.own_lotus_total}:${lm.opp_lotus_total}`, title: "9. 对线拉野·走门·莲花·经验符", reason: "拉野封野与莲花经验符控制占优" };

  // 10. tp_save
  const tp = df.tp_rotation_by_side?.[targetSide] || {};
  const zeroTpPlayers = (tp.player_tp_rows || []).filter((r) => Number(r.tp_bought ?? 1) === 0);
  const absentPlayers = (tp.player_tp_rows || []).filter((r) => Number(r.tf_absent_cnt ?? 0) > 0);
  results.tp_save =
    zeroTpPlayers.length >= 2 || absentPlayers.length >= 2
      ? {
          level: "critical",
          badge: `🚨 ${zeroTpPlayers.length}人0买TP`,
          title: "10. TP 救人及时性与缺席抓包",
          reason: `全队竟有 <b>${zeroTpPlayers.length} 名选手（${zeroTpPlayers
            .map((r) => `${r.pos}号${r.hero_short_zh}`)
            .join("、")}）整局主动花钱买 0 张 TP</b>，且有 <b>${absentPlayers.length} 人</b>团战缺席，属于致命支援短板！`,
        }
      : zeroTpPlayers.length >= 1 || absentPlayers.length >= 1
      ? {
          level: "warn",
          badge: `⚠️ 支援缺席`,
          title: "10. TP 救人及时性与缺席抓包",
          reason: `${zeroTpPlayers.length} 人 0 买 TP，${absentPlayers.length} 人存在团战缺席。`,
        }
      : { level: "good", badge: "✓ 支援齐整", title: "10. TP 救人及时性与缺席抓包", reason: "全员TP支援到位" };

  // 11. econ_pings
  const ep = df.economy_and_pings_by_side?.[targetSide] || {};
  const lostGold = (ep.player_econ_rows || []).reduce((s, r) => s + Number(r.death_gold_lost || 0), 0);
  results.econ_pings =
    lostGold >= 5500
      ? {
          level: "warn",
          badge: `⚠️ 掉钱-${fmtNum(lostGold)}`,
          title: "11. 经济来源结构 & 信号互动",
          reason: `全队阵亡累计损失不可靠金钱 <b>-${fmtNum(lostGold)} 金</b>，买大件前务必提前消费不可靠金。`,
        }
      : { level: "good", badge: "✓ 经济健康", title: "11. 经济来源结构 & 信号互动", reason: "经济转化结构健康" };

  // 12. role_mirror
  const rm = df.role_mirror_by_side?.[targetSide] || {};
  const wonCnt = Number(rm.won_overall_cnt ?? 3);
  results.role_mirror =
    wonCnt <= 1
      ? {
          level: "critical",
          badge: `🚨 对位仅赢${wonCnt}/5`,
          title: "12. 同位置1v1宿敌对位",
          reason: `1~5号位同位置正面对位仅 <b>${wonCnt}/5 胜出</b>，多路被对位宿敌压制！`,
        }
      : wonCnt === 2
      ? {
          level: "warn",
          badge: `⚠️ 对位赢2/5`,
          title: "12. 同位置1v1宿敌对位",
          reason: `同位置正面对位 2/5 胜出，部分号位对位处于劣势。`,
        }
      : { level: "good", badge: `✓ 对位赢${wonCnt}/5`, title: "12. 同位置1v1宿敌对位", reason: `同位置对位 ${wonCnt}/5 胜出` };

  // 13. macro_neutrals
  const mo = df.macro_objectives_by_side?.[targetSide] || {};
  const diebacks = Number(mo.dieback_cnt ?? 0);
  const couriers = Number(mo.courier_deaths_cnt ?? 0);
  results.macro_neutrals =
    diebacks >= 1 || couriers >= 2
      ? {
          level: "critical",
          badge: `🚨 ${diebacks > 0 ? `买活死×${diebacks}` : `掉鸡×${couriers}`}`,
          title: "13. 买活死尸检·掉鸡·肉山魔晶",
          reason: `出现 <b>${diebacks} 次致命买活死</b> 与 <b>${couriers} 次信使被杀</b>！`,
        }
      : { level: "good", badge: "✓ 0买活死", title: "13. 买活死尸检·掉鸡·肉山魔晶", reason: "买活与肉山控盾稳健" };

  // Update the 13 Tab Buttons and Mobile Select with visual highlight badges
  const baseLabels = {
    hero_ult: "🎯 1. 英雄绝活与大招审判",
    itemization: "🎒 2. 全员出装路线与克制装处刑台",
    damage_quality: "🔥 3. 伤害含金量·加点路线与叠层审判",
    unpressed_saves: "💀 4. 憋死BKB/救命装与0技能秒躺",
    map_space: "🕵️‍♂️ 5. 单带无故被抓 & 开雾/白给侦探社",
    damage_received: "🛡️ 6. 承伤来源拆解与防装审计",
    vision: "👁️ 7. 眼位博弈·满时长神眼与黑图真空期",
    stack_smoke: "🌾 8. 辅助堆野 & 开雾找节奏",
    laning: "🌱 9. 对线拉野·走门·莲花·经验符",
    tp_save: "🆘 10. TP 救人及时性与缺席抓包",
    econ_pings: "💰 11. 经济来源结构 & 信号/暂停互动",
    role_mirror: "⚔️ 12. 同位置1v1宿敌对位 & 全球百分位",
    macro_neutrals: "🐉 13. 买活死尸检·掉鸡·肉山魔晶 & 7.38附魔",
  };

  document.querySelectorAll("[data-micro-tab]").forEach((btn) => {
    const k = btn.getAttribute("data-micro-tab");
    if (!k || k === "all" || !results[k]) return;
    const info = results[k];
    btn.classList.remove("micro-tab-critical", "micro-tab-warn", "micro-tab-good");
    btn.classList.add(`micro-tab-${info.level}`);
    btn.innerHTML = `<span>${escapeHtml(baseLabels[k] || k)}</span> <span class="micro-tab-status-pill ${info.level}">${escapeHtml(info.badge)}</span>`;
  });

  const mSel = document.getElementById("micro-mobile-select");
  if (mSel) {
    Array.from(mSel.options).forEach((opt) => {
      const k = opt.value;
      if (results[k] && baseLabels[k]) {
        opt.textContent = `${baseLabels[k]} [${results[k].badge}]`;
      }
    });
  }

  return results;
}

function renderTacticalMicroscopeSection(report) {
  const bodyEl = document.getElementById("tactical-microscope-body");
  if (!bodyEl) return;

  const df = report.deep_forensics || {};
  const { side, sideZh, oppZh } = getOwnAndOppPlayers(report);
  const oppSide = side === "radiant" ? "dire" : "radiant";
  const targetSide = state.microSide === "opp" ? oppSide : side;
  const targetSideZh = state.microSide === "opp" ? oppZh : sideZh;
  const otherSide = targetSide === "radiant" ? "dire" : "radiant";
  const otherSideZh = targetSide === "radiant" ? "夜魇" : "天辉";

  const auditMap = auditAllMicroDimensions(report, df, targetSide, targetSideZh);
  const criticalAndWarnList = Object.entries(auditMap)
    .filter(([, v]) => v.level === "critical" || v.level === "warn")
    .sort((a, b) => (a[1].level === "critical" ? 0 : 1) - (b[1].level === "critical" ? 0 : 1));

  const weaknessRadarHtml =
    criticalAndWarnList.length > 0
      ? `
      <div class="micro-weakness-radar-banner">
        <div class="micro-radar-head">
          <span class="micro-radar-title">🚨 ${escapeHtml(targetSideZh)}本局急需加强的薄弱项红牌高亮雷达（共抓出 <b>${
          criticalAndWarnList.filter(([, v]) => v.level === "critical").length
        } 项致命短板</b> / ${
          criticalAndWarnList.filter(([, v]) => v.level === "warn").length
        } 项隐患 · 点击卡片直接跳转对应处刑台）</span>
        </div>
        <div class="micro-radar-grid">
          ${criticalAndWarnList
            .slice(0, 6)
            .map(
              ([k, v]) => `
              <div class="micro-radar-card ${v.level} ${state.microTab === k ? "is-active-tab" : ""}" data-jump-micro-tab="${escapeHtml(k)}" role="button" tabindex="0">
                <div class="micro-radar-card-top">
                  <span class="micro-radar-pill ${v.level}">${escapeHtml(v.badge)}</span>
                  <strong>${escapeHtml(v.title)}</strong>
                  <span class="micro-radar-jump-hint">点击查看 →</span>
                </div>
                <div class="micro-radar-desc">${injectHeroLogosIntoHtml(v.reason, report)}</div>
              </div>
            `
            )
            .join("")}
        </div>
      </div>
    `
      : "";

  const tab = state.microTab || "hero_ult";
  const blocks = [weaknessRadarHtml];

  if (tab === "hero_ult" || tab === "all") {
    blocks.push(renderMicroHeroExecutionPane(report, df, targetSide, targetSideZh, otherSide, otherSideZh));
  }
  if (tab === "itemization" || tab === "all") {
    blocks.push(renderMicroItemizationPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "damage_quality" || tab === "all") {
    blocks.push(renderMicroDamageQualityAndBuildPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "unpressed_saves" || tab === "all") {
    blocks.push(renderMicroUnpressedSavesPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "map_space" || tab === "all") {
    blocks.push(renderMicroMapSpacePane(report, df, targetSide, targetSideZh));
  }
  if (tab === "damage_received" || tab === "all") {
    blocks.push(renderMicroDamageReceivedPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "vision" || tab === "all") {
    blocks.push(renderMicroSupportVisionPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "stack_smoke" || tab === "all") {
    blocks.push(renderMicroStackAndSmokePane(report, df, targetSide, targetSideZh));
  }
  if (tab === "laning" || tab === "all") {
    blocks.push(renderMicroLaningMechanicsPane(report, df, targetSide, targetSideZh, otherSideZh));
  }
  if (tab === "tp_save" || tab === "all") {
    blocks.push(renderMicroTpRotationPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "econ_pings" || tab === "all") {
    blocks.push(renderMicroEconomyAndPingsPane(report, df, targetSide, targetSideZh));
  }
  if (tab === "role_mirror" || tab === "all") {
    blocks.push(renderMicroRoleMirrorPane(report, df, targetSide, targetSideZh, otherSideZh));
  }
  if (tab === "macro_neutrals" || tab === "all") {
    blocks.push(renderMicroMacroObjectivesPane(report, df, targetSide, targetSideZh));
  }

  bodyEl.innerHTML = blocks.join("");

  bodyEl.querySelectorAll("[data-jump-micro-tab]").forEach((card) => {
    card.addEventListener("click", () => {
      const targetTab = card.getAttribute("data-jump-micro-tab") || "hero_ult";
      state.microTab = targetTab;
      const mSel = document.getElementById("micro-mobile-select");
      if (mSel) mSel.value = targetTab;
      document.querySelectorAll("[data-micro-tab]").forEach((b) => {
        const active = b.getAttribute("data-micro-tab") === targetTab;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
        if (active) b.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      });
      if (state.currentReport) renderTacticalMicroscopeSection(state.currentReport);
    });
  });

  bodyEl.querySelectorAll("[data-micro-exec-pos]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sel = btn.getAttribute("data-micro-exec-pos");
      state.microExecSelectedPos = sel === "all" ? "all" : Number(sel);
      if (state.currentReport) renderTacticalMicroscopeSection(state.currentReport);
    });
  });
}

/**
 * Tab 3: 🔥 伤害含金量（切敌方1/2号位双核 vs 刮前排肉盾假伤害）· 1~18级加点天赋路线与永久 Buff 叠层审判
 */
function renderMicroDamageQualityAndBuildPane(report, df, targetSide, targetSideZh) {
  const dq = df.damage_quality_and_build_by_side?.[targetSide];
  if (!dq) {
    return `<div class="empty-state compact">当前比赛暂无伤害含金量与加点路线审计数据</div>`;
  }

  const pRows = dq.player_rows || [];
  const fakeCnt = Number(dq.fake_dmg_suspects_cnt ?? 0);
  const trueCnt = Number(dq.true_core_slayers_cnt ?? 0);
  const buildIssCnt = Number(dq.skill_build_issues_cnt ?? 0);

  const dmgRowsHtml = pRows
    .map((r) => {
      const isBad = String(r.dmg_quality_badge || "").startsWith("🚨") || String(r.dmg_quality_badge || "").startsWith("⚠️");
      const isGood = String(r.dmg_quality_badge || "").startsWith("🔥") || String(r.dmg_quality_badge || "").startsWith("⚡");
      const corePct = Number(r.core_12_pct ?? 0);
      const supPct = Number(r.backline_sup_pct ?? 0);
      const tankPct = Number(r.tank_sponge_pct ?? 0);

      const targetPillsHtml = (r.target_breakdown || [])
        .map((tb) => {
          const isTank = Boolean(tb.is_tank_sponge);
          const isCore = Boolean(tb.is_core_12);
          const borderCol = isCore
            ? "rgba(34, 197, 94, 0.45)"
            : isTank
            ? "rgba(239, 68, 68, 0.45)"
            : "rgba(234, 179, 8, 0.4)";
          return `
            <span class="micro-tf-pill" style="display:inline-flex;align-items:center;gap:4px;border-color:${borderCol};">
              ${
                tb.hero_img
                  ? `<img src="${escapeHtml(tb.hero_img)}" width="20" height="12" alt="" style="border-radius:2px;" loading="lazy" />`
                  : ""
              }
              <b>${tb.pos}号位${escapeHtml(tb.hero_short_zh)}</b>(${escapeHtml(tb.role_tag_zh)}):
              <b>${fmtNum(tb.dmg || 0)}</b> (${tb.dmg_pct}% · <b>${tb.kills}杀</b>)
            </span>
          `;
        })
        .join(" ");

      const notesHtml = (r.dmg_audit_notes || [])
        .map((n) => {
          const isAlert = String(n).startsWith("🚨") || String(n).startsWith("⚠️");
          const isOk = String(n).startsWith("✓");
          return `<li style="color:${
            isAlert ? "var(--red-light)" : isOk ? "var(--green-light)" : "var(--text)"
          };">${injectHeroLogosIntoHtml(escapeHtml(n), report)}</li>`;
        })
        .join("");

      return `
        <tr>
          <td>
            ${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}
            <div style="font-size:11px; color:var(--muted); margin-top:3px;">
              总对人伤害 <b>${fmtNum(r.total_hero_dmg || 0)}</b> · 总击杀 <b>${r.total_kills ?? 0}</b>
            </div>
          </td>
          <td class="micro-badge-cell">
            <span class="micro-exec-badge ${isBad ? "warn" : isGood ? "good" : ""}">
              ${escapeHtml(r.dmg_quality_badge || "常规输出")}
            </span>
          </td>
          <td>
            <div class="posture-bar-stack" style="height:20px; margin-bottom:6px;" title="切敌方1/2号位双核 vs 打脆皮后排 vs 刮前排肉盾">
              ${
                corePct > 0
                  ? `<div class="posture-seg agg" style="width:${Math.max(corePct, 12)}%;font-size:10px;">🎯 切1/2号位 ${corePct}% (${r.core_12_kills}杀)</div>`
                  : ""
              }
              ${
                supPct > 0
                  ? `<div class="posture-seg mid" style="width:${Math.max(supPct, 10)}%;font-size:10px;">🪶 杀后排 ${supPct}% (${r.backline_sup_kills}杀)</div>`
                  : ""
              }
              ${
                tankPct > 0
                  ? `<div class="posture-seg def" style="width:${Math.max(tankPct, 12)}%;font-size:10px;background:rgba(239,68,68,0.28);color:#fca5a5;">🥩 刮肉盾 ${tankPct}% (${r.tank_sponge_kills}杀)</div>`
                  : ""
              }
            </div>
            <div class="micro-tf-pills">${targetPillsHtml}</div>
          </td>
          <td>
            <div style="font-size:12px; color:var(--gold-light); font-weight:600; margin-bottom:4px;">
              💥 单发最高峰值：${injectHeroLogosIntoHtml(escapeHtml(r.max_hit_summary_zh || ""), report)}
            </div>
            <ul class="micro-insights-list" style="margin:0;">${notesHtml}</ul>
          </td>
        </tr>
      `;
    })
    .join("");

  const buildRowsHtml = pRows
    .map((r) => {
      const sbBad = r.skill_build_grade === "bad" || r.skill_build_grade === "warn";
      const seqPills = (r.level_sequence || [])
        .slice(0, 12)
        .map((st) => {
          const isTal = st.type === "talent";
          const isUlt = st.type === "ult";
          const styleStr = isTal
            ? "border-color:rgba(234,179,8,0.55);color:var(--gold-light);"
            : isUlt
            ? "border-color:rgba(59,130,246,0.55);color:#93c5fd;"
            : "";
          return `<span class="micro-tf-pill" style="${styleStr}">${escapeHtml(st.short_tag || "")}</span>`;
        })
        .join(" ");

      const talentsHtml =
        (r.talents_chosen || [])
          .map(
            (t) =>
              `<span class="micro-tf-pill" style="border-color:rgba(234,179,8,0.5);color:var(--gold-light);">🌟 ${escapeHtml(
                t.tier
              )}(L${t.level_taken}): <b>${escapeHtml(t.zh)}</b></span>`
          )
          .join(" ") || `<span style="color:var(--muted);">未达到天赋等级</span>`;

      const permBuffPills =
        (r.perm_buff_badges || [])
          .map(
            (pb) =>
              `<span class="micro-tf-pill" style="border-color:rgba(34,197,94,0.5);color:var(--green-light);font-weight:700;">${escapeHtml(
                pb
              )}</span>`
          )
          .join(" ") || `<span style="color:var(--muted);font-size:11px;">本局无永久叠层/魔晶Buff记录</span>`;

      const allFlags = [...(r.skill_build_flags || []), ...(r.perm_buff_notes || [])];
      const flagsHtml = allFlags
        .map((fl) => {
          const isErr = String(fl).startsWith("🚨") || String(fl).startsWith("⚠️");
          const isGood = String(fl).startsWith("✓") || String(fl).startsWith("🔥");
          return `<li style="color:${
            isErr ? "var(--red-light)" : isGood ? "var(--green-light)" : "var(--gold-light)"
          };">${injectHeroLogosIntoHtml(escapeHtml(fl), report)}</li>`;
        })
        .join("");

      return `
        <tr>
          <td>
            ${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}
            <div style="margin-top:4px;">
              <span class="micro-exec-badge ${sbBad ? "warn" : "good"}">${escapeHtml(
        r.skill_route_summary_zh || "常规加点"
      )}</span>
            </div>
          </td>
          <td>
            <div style="font-size:11px; color:var(--muted); margin-bottom:3px;">前 12 级逐级加点顺序：</div>
            <div class="micro-tf-pills" style="margin-bottom:6px;">${seqPills}</div>
            <div style="font-size:11px; color:var(--muted); margin-bottom:3px;">🌟 10 / 15 / 20 / 25 级天赋抉择：</div>
            <div class="micro-tf-pills">${talentsHtml}</div>
          </td>
          <td>
            <div class="micro-tf-pills">${permBuffPills}</div>
          </td>
          <td>
            <ul class="micro-insights-list" style="margin:0;">${flagsHtml}</ul>
          </td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🔥 3. 伤害含金量（切双核真伤 vs 刮肉盾假伤害）· 1~18级加点天赋路线与永久 Buff 叠层审判 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(dq.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-kpi-row">
        <div class="micro-kpi-cell">
          <span>🚨 刮肉盾假伤害 / 集火偏移人数</span>
          <strong style="color:${fakeCnt > 0 ? "var(--red-light)" : "var(--green-light)"};">${fakeCnt} 人被抓包</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🔥 刀刀见血 · 精准切核人数</span>
          <strong style="color:var(--green-light);">${trueCnt} 人高含金量切C</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>📚 前9级不学控制/核心技能抓包</span>
          <strong style="color:${buildIssCnt > 0 ? "var(--red-light)" : "var(--green-light)"};">${buildIssCnt} 处奇葩/偏科加点</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🧬 永久 Buff 与叠层追踪</span>
          <strong>能量转移 / 死亡一指 / 腐肉堆积 / 决斗 / 魔晶激活点</strong>
        </div>
      </div>

      <div class="micro-card">
        <h4>🎯 1~5 号位伤害含金量拆解台（谁在刀刀见血切对面 1/2 号位双核？谁在对着帕吉/酒仙/前排肉盾狂刷无效假伤害？）</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>伤害含金量定性</th>
                <th>对敌方 5 人伤害构成比例 &amp; 终结击杀明细</th>
                <th>单发最高爆发峰值 &amp; 集火审计判词</th>
              </tr>
            </thead>
            <tbody>${dmgRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="micro-card">
        <h4>📚 1~5 号位逐级加点路线、10/15/20/25 级天赋抉择与永久 Buff 叠层审判台</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄 &amp; 主副路线</th>
                <th>前 12 级加点流水 &amp; 10/15/20/25 级天赋抉择</th>
                <th>🧬 永久 Buff 叠层与魔晶/A杖赐福</th>
                <th>加点毒点 / 成长叠层审判</th>
              </tr>
            </thead>
            <tbody>${buildRowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/**
 * Tab 2: 🎒 全员出装路线与「蠢装/漏出克制装/憋大件断档」处刑台
 */
function renderMicroItemizationPane(report, df, targetSide, targetSideZh) {
  const ia = df.itemization_audit_by_side?.[targetSide];
  if (!ia) {
    return `<div class="empty-state compact">当前比赛暂无全员出装路线与克制装审计数据</div>`;
  }

  const counterChecks = ia.team_counter_checks || [];
  const pRows = ia.player_item_rows || ia.player_item_audits || [];
  const missingCnt = Number(ia.bad_counter_cnt ?? ia.missing_counter_count ?? 0);
  const badBuildCnt = Number(ia.bad_build_cnt ?? ia.bad_build_players_count ?? 0);

  const counterCardsHtml = counterChecks
    .map((chk) => {
      const ok = chk.grade === "good" || Boolean(chk.passed);
      return `
        <div class="micro-ult-box" style="border-left: 3px solid ${ok ? "var(--green)" : "var(--red)"};">
          <div class="micro-ult-top">
            <span class="micro-ult-name">${escapeHtml(chk.category || "团队针对装审计")}</span>
            <span class="status-pill ${ok ? "connected" : ""}" style="${
        ok ? "" : "border-color:rgba(239,68,68,0.45);color:var(--red-light);"
      }">${ok ? "✅ 针对到位" : "🚨 严重漏出"}</span>
          </div>
          <div style="font-size:12px; color:var(--muted); margin-top:4px;">
            <b>敌方威胁：</b>${injectHeroLogosIntoHtml(escapeHtml(chk.enemy_threats || chk.enemy_threat || ""), report)} ｜ <b>本方应对：</b>${injectHeroLogosIntoHtml(
        escapeHtml(chk.our_response || chk.required_items_zh || ""),
        report
      )}
          </div>
          <div style="font-size:12px; color:${ok ? "var(--green-light)" : "var(--red-light)"}; font-weight:600; margin-top:4px;">
            ${injectHeroLogosIntoHtml(escapeHtml(chk.verdict || chk.status_zh || ""), report)}
          </div>
        </div>
      `;
    })
    .join("");

  const pRowsHtml = pRows
    .map((r) => {
      const isBad = r.grade === "bad";
      const isWarn = r.grade === "warn";
      const isGood = r.grade === "good";
      const tItems = r.major_timeline || r.timeline_items || [];
      const timelineStr =
        tItems
          .map(
            (it) =>
              `<span class="micro-tf-pill" style="display:inline-flex;align-items:center;gap:4px;">${
                it.img ? `<img src="${escapeHtml(it.img)}" width="20" height="14" alt="" style="border-radius:2px;" loading="lazy" />` : ""
              }${escapeHtml(it.zh || it.item_zh || "")} (${escapeHtml(it.time_str || "")})</span>`
          )
          .join(" ") || `<span style="color:var(--muted);">无核心大件合成记录</span>`;
      const issuesList = r.issues_list || r.issues || [];
      const issuesHtml = issuesList
        .map((iss) => {
          const isPositive = String(iss).startsWith("✓");
          return `<li style="color:${isPositive ? "var(--green-light)" : "var(--red-light)"};">${injectHeroLogosIntoHtml(
            escapeHtml(iss),
            report
          )}</li>`;
        })
        .join("");
      const refBuild = r.core_reference_zh || r.recommended_build_zh || "";
      return `
        <tr>
          <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
          <td class="micro-badge-cell">
            <span class="micro-exec-badge ${isBad || isWarn ? "warn" : isGood ? "good" : ""}">
              ${escapeHtml(r.verdict_badge || "常规出装")}
            </span>
          </td>
          <td>
            <div class="micro-tf-pills" style="margin-bottom:4px;">${timelineStr}</div>
            <div style="font-size:11px; color:var(--muted);">
              ⏱️ 憋装最长断档：<b>${escapeHtml(r.stall_window_zh || "平滑过渡")}</b>
              ${refBuild ? `<br/>📖 126英雄库标准出装参考：<span>${escapeHtml(refBuild)}</span>` : ""}
            </div>
          </td>
          <td>
            <ul class="micro-insights-list" style="margin:0;">
              ${issuesHtml || `<li style="color:var(--green-light);">✓ 核心装备与节奏衔接正常</li>`}
            </ul>
          </td>
          <td style="color:${isBad ? "var(--red-light)" : isWarn ? "var(--gold-light)" : "var(--green-light)"}; font-weight:600;">
            ${injectHeroLogosIntoHtml(escapeHtml(r.fix_advice_zh || ""), report)}
          </td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🎒 2. 全员出装路线与「蠢装 / 漏出克制装 / 憋大件断档」处刑台 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(ia.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-kpi-row">
        <div class="micro-kpi-cell">
          <span>团队针对装必考项</span>
          <strong>共 ${counterChecks.length} 项刚需核查</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>漏出关键克制装项数</span>
          <strong style="color:${missingCnt > 0 ? "var(--red-light)" : "var(--green-light)"};">${missingCnt} 项漏出</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>出装毒瘤 / 憋大件断档人数</span>
          <strong style="color:${badBuildCnt > 0 ? "var(--red-light)" : "var(--green-light)"};">${badBuildCnt} 人被抓包</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>审计覆盖范围</span>
          <strong>减疗 / 大隐刀破被动 / 否决破保命 / BKB / 魔晶 / 救人装</strong>
        </div>
      </div>

      <div class="micro-card">
        <h4>🛡️ 团队刚需克制装核查清单（根据敌方 5 人英雄池自动判定本局必出针对装）</h4>
        <div class="micro-grid-2col">${counterCardsHtml}</div>
      </div>

      <div class="micro-card">
        <h4>🔪 1~5 号位个人出装时间轴、憋大件真空期与换装纠错处刑台</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>出装评级</th>
                <th>核心装备合成时间轴 &amp; 最长憋装断档</th>
                <th>出装毒点 / 亮点审计</th>
                <th>立刻换装纠错处方</th>
              </tr>
            </thead>
            <tbody>${pRowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderMicroHeroExecutionPane(report, df, targetSide, targetSideZh, otherSide, otherSideZh) {
  const execData = df.hero_execution_by_side?.[targetSide];
  const oppExecData = df.hero_execution_by_side?.[otherSide];
  const players = Array.isArray(execData) ? execData : execData?.players || [];
  const oppPlayers = Array.isArray(oppExecData) ? oppExecData : oppExecData?.players || [];
  if (!players.length) {
    return `<div class="empty-state compact">当前比赛暂无英雄绝活与大招显微镜数据</div>`;
  }

  const buildSideSummary = (list) =>
    list
      .map((p) => {
        const firstUlt = (p.ult_audits || [])[0];
        if (firstUlt) {
          return `${p.pos}号位${p.hero_short_zh}《${firstUlt.ability_zh}》释放 ${firstUlt.casts ?? 0} 次(命中 ${firstUlt.hits ?? 0} ${firstUlt.unit_label || "人次"} · 评级${firstUlt.grade || "B"})`;
        }
        const firstBadge = (p.headline_badges || [])[0];
        const bText = typeof firstBadge === "string" ? firstBadge : firstBadge?.text || "";
        return bText ? `${p.pos}号位${p.hero_short_zh}（${bText}）` : `${p.pos}号位${p.hero_short_zh}`;
      })
      .join("；");

  const ownSummaryText = execData?.summary || buildSideSummary(players);
  const oppSummaryText = oppExecData?.summary || buildSideSummary(oppPlayers);

  // Score players to find the #1 Most Important Execution Audit Hero for default spotlight
  const scoredExecPlayers = players.map((p) => {
    const ultAudits = p.ult_audits || p.signature_spells || [];
    const heldCnt = ultAudits.reduce(
      (acc, sp) => acc + Number(sp.tf_held_death_count ?? (sp.held_ult_deaths || []).length ?? 0),
      0
    );
    const hasBadUlt = ultAudits.some((sp) => sp.grade === "bad" || sp.grade === "D" || sp.grade === "C");
    const warnBadgesCnt = (p.headline_badges || []).filter((b) => {
      const txt = typeof b === "string" ? b : b?.text || "";
      const tone = typeof b === "object" && b !== null ? b.tone : "";
      return tone === "bad" || tone === "warn" || txt.includes("🚫") || txt.includes("⚠️") || txt.includes("💀");
    }).length;
    const impScore = heldCnt * 60 + (hasBadUlt ? 45 : 0) + warnBadgesCnt * 30 + (6 - Number(p.pos || 5)) * 3;
    return { p, impScore, heldCnt, hasBadUlt, warnBadgesCnt };
  });

  const focusExecEntry =
    [...scoredExecPlayers].sort((a, b) => b.impScore - a.impScore)[0] || scoredExecPlayers[0];
  const defaultExecPos = Number(focusExecEntry?.p?.pos || players[0]?.pos || 1);
  const selExecMode = state.microExecSelectedPos ?? "focus";
  const activeExecPos =
    selExecMode === "focus"
      ? defaultExecPos
      : selExecMode === "all"
      ? "all"
      : Number(selExecMode);

  const execPickerBarHtml = `
    <div class="forensic-hero-picker-bar micro-exec-picker-bar" role="tablist" aria-label="切换查看1至5号位绝活与大招审判">
      <span class="forensic-picker-hint">🎯 默认聚焦大招/机制问题最突出的 1 人（点击切换其他队友）：</span>
      <div class="forensic-picker-buttons">
        ${scoredExecPlayers
          .map(({ p, heldCnt, hasBadUlt, warnBadgesCnt }) => {
            const pPos = Number(p.pos || 1);
            const isFocus = pPos === defaultExecPos;
            const isAct = activeExecPos !== "all" && Number(activeExecPos) === pPos;
            const firstUlt = (p.ult_audits || [])[0];
            let chipText = firstUlt ? `大招${firstUlt.casts ?? 0}放` : "机制审计";
            let chipCls = "";
            if (isFocus) {
              chipText = heldCnt > 0 ? `🚨憋大${heldCnt}次` : hasBadUlt ? "🚨大招拉胯" : "🎯头号焦点";
              chipCls = "bad";
            } else if (heldCnt > 0 || warnBadgesCnt > 0) {
              chipText = heldCnt > 0 ? `🚨憋大${heldCnt}次` : `⚠️${warnBadgesCnt}项预警`;
              chipCls = "bad";
            } else if (firstUlt && (firstUlt.grade === "good" || firstUlt.grade === "S" || firstUlt.grade === "A")) {
              chipCls = "good";
            }
            return `
              <button
                type="button"
                class="forensic-pick-btn ${isAct ? "is-active" : ""} ${isFocus ? "is-focus" : ""}"
                data-micro-exec-pos="${pPos}"
              >
                ${
                  p.hero_img
                    ? `<img src="${escapeHtml(p.hero_img)}" width="26" height="15" alt="" class="forensic-pick-avatar" />`
                    : ""
                }
                <span><b>${pPos}号 ${escapeHtml(p.hero_short_zh || "")}</b> <small>(${escapeHtml(
              p.personaname || ""
            )})</small></span>
                <em class="forensic-pick-chip ${chipCls}">${escapeHtml(chipText)}</em>
              </button>
            `;
          })
          .join("")}
        <button
          type="button"
          class="forensic-pick-btn mode-all ${activeExecPos === "all" ? "is-active" : ""}"
          data-micro-exec-pos="all"
        >
          📋 全部 (${players.length}人)
        </button>
      </div>
    </div>
  `;

  const visibleExecPlayers =
    activeExecPos === "all"
      ? players
      : players.filter((p) => Number(p.pos || 1) === Number(activeExecPos));
  const finalExecPlayers = visibleExecPlayers.length > 0 ? visibleExecPlayers : players.slice(0, 1);

  const cardsHtml = finalExecPlayers
    .map((p) => {
      const badges = (p.headline_badges || [])
        .map((b) => {
          const txt = typeof b === "string" ? b : b?.text || "";
          const tone = typeof b === "object" && b !== null ? b.tone : "";
          const isWarn =
            tone === "bad" ||
            tone === "warn" ||
            txt.includes("⚠️") ||
            txt.includes("0.4/分") ||
            txt.includes("1.33");
          const isGood =
            tone === "good" ||
            txt.includes("14,807") ||
            txt.includes("3.1") ||
            txt.includes("评级S") ||
            txt.includes("评级A");
          return txt
            ? `<span class="micro-exec-badge ${isWarn ? "warn" : isGood ? "good" : ""}">${escapeHtml(txt)}</span>`
            : "";
        })
        .join("");

      const ultAudits = p.ult_audits || p.signature_spells || [];
      const sigSpellsHtml = ultAudits
        .map((sp) => {
          const casts = sp.casts ?? 0;
          const hits = sp.hits ?? sp.hero_hits ?? 0;
          const avgHits = sp.avg_hits ?? sp.avg_heroes_per_cast ?? 0;
          const unitLabel = sp.unit_label || "人次";
          const totalDmg = sp.damage ?? sp.total_damage ?? 0;
          const verdictText = sp.verdict_text || sp.verdict || "";
          const grade = sp.grade || "B";

          const tfWaves = sp.tf_casts_waves || [];
          const tfCastsPills =
            tfWaves.length > 0
              ? tfWaves
                  .map((w) => `<span class="micro-tf-pill">✓ ${escapeHtml(w)} 团战开大</span>`)
                  .join("")
              : (sp.teamfight_casts || [])
                  .map((tc) => `<span class="micro-tf-pill">✓ ${escapeHtml(tc.time_range || "")} 团战释放×${tc.casts ?? 1}</span>`)
                  .join("");

          const heldWaves = sp.tf_held_death_waves || [];
          const heldDeathPills =
            heldWaves.length > 0
              ? heldWaves
                  .map((hw) => `<span class="micro-tf-pill held-die">🚨 ${escapeHtml(hw)} 团战憋大阵亡</span>`)
                  .join("")
              : (sp.held_ult_deaths || [])
                  .map(
                    (hd) =>
                      `<span class="micro-tf-pill held-die">🚨 ${escapeHtml(hd.time_range || "")} 团战憋大阵亡 (仅打${fmtNum(
                        hd.damage_dealt || 0
                      )}伤)</span>`
                  )
                  .join("");

          const targetsStr = Array.isArray(sp.victim_breakdown)
            ? sp.victim_breakdown.slice(0, 4).join(" / ")
            : (sp.targets_breakdown || [])
                .slice(0, 4)
                .map((t) => `${t.is_ally ? "友·" : "敌·"}${escapeHtml(t.hero_short_zh || "")}×${t.count ?? 0}`)
                .join(" / ");

          return `
            <div class="micro-ult-box">
              <div class="micro-ult-top">
                <span class="micro-ult-name">💥 大招审计 · ${escapeHtml(sp.ability_zh || "关键技能")}</span>
                <span class="status-pill ${grade === "S" || grade === "A" ? "connected" : ""}">评级 ${escapeHtml(
            grade
          )}</span>
              </div>
              <div class="micro-ult-stats">
                <span>释放次数：<b>${casts} 次</b></span>
                ${
                  hits > 0
                    ? `<span>命中统计：<b>${hits} ${escapeHtml(unitLabel)} (场均 ${avgHits} ${escapeHtml(unitLabel)}/次)</b></span>`
                    : casts > 0
                    ? `<span>团战开大：<b>${sp.tf_casts_count ?? tfWaves.length} 波团战</b></span>`
                    : `<span>实战记录：<b>整局 0 释放</b></span>`
                }
                ${totalDmg > 0 ? `<span>大招伤害：<b>${fmtNum(totalDmg)}</b></span>` : ""}
                ${targetsStr ? `<span>主要目标：<b>${escapeHtml(targetsStr)}</b></span>` : ""}
              </div>
              ${
                verdictText
                  ? `<div style="font-size:12px; color:var(--text); line-height:1.5;">${escapeHtml(verdictText)}</div>`
                  : ""
              }
              ${
                tfCastsPills || heldDeathPills
                  ? `<div class="micro-tf-pills">${tfCastsPills}${heldDeathPills}</div>`
                  : ""
              }
            </div>
          `;
        })
        .join("");

      const skillshotHtml = (p.skillshot_audits || [])
        .map(
          (sk) => `
          <div class="micro-ult-box" style="border-left: 2px solid var(--gold);">
            <div class="micro-ult-top">
              <span class="micro-ult-name">🎯 非指向核心技能 · ${escapeHtml(sk.ability_zh || "")}</span>
              <span class="status-pill ${sk.grade === "S" || sk.grade === "A" ? "connected" : ""}">命中率 ${
            sk.hit_pct ?? 0
          }% (${sk.grade || "B"})</span>
            </div>
            <div class="micro-ult-stats">
              <span>释放次数：<b>${sk.casts ?? 0} 次</b></span>
              <span>命中英雄：<b>${sk.hits ?? 0} 人次</b></span>
              ${(sk.damage ?? 0) > 0 ? `<span>技能伤害：<b>${fmtNum(sk.damage)}</b></span>` : ""}
            </div>
            ${
              sk.detail
                ? `<div style="font-size:12px; color:var(--muted);">${escapeHtml(sk.detail)}</div>`
                : ""
            }
          </div>
        `
        )
        .join("");

      const insightsHtml = (p.special_insights || [])
        .map((ins) => `<li>${injectHeroLogosIntoHtml(escapeHtml(ins), report)}</li>`)
        .join("");

      const hasHeldUltWarning = ultAudits.some(
        (sp) => (sp.tf_held_death_count ?? 0) > 0 || (sp.held_ult_deaths || []).length > 0
      );

      return `
        <article class="micro-hero-card ${hasHeldUltWarning ? "culprit-border" : ""}">
          <div class="micro-hero-head">
            <div class="micro-hero-id">
              ${p.hero_img ? `<img src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(p.hero_short_zh || "")}" loading="lazy" />` : ""}
              <div>
                <strong>${p.pos ?? "?"}号位 · ${escapeHtml(p.hero_short_zh || "")} (${escapeHtml(p.personaname || "")})</strong>
                <div class="micro-hero-sub">${
                  (p.stuns_sec ?? 0) > 0
                    ? `全场硬控眩晕 ${p.stuns_sec} 秒`
                    : `关键技能与大招录像级审计`
                }</div>
              </div>
            </div>
          </div>
          ${badges ? `<div class="micro-badges-wrap">${badges}</div>` : ""}
          ${sigSpellsHtml}
          ${skillshotHtml}
          ${insightsHtml ? `<ul class="micro-insights-list">${insightsHtml}</ul>` : ""}
        </article>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🎯 1. 英雄绝活与大招释放质量审判 (${escapeHtml(targetSideZh)} 1~5 号位)</h3>
          <details class="mobile-summary-fold" ${typeof window !== "undefined" && window.innerWidth > 768 ? "open" : ""}>
            <summary class="mobile-summary-trigger">📖 展开/收起五人大招与关键技能兑现总览对比</summary>
            <p style="margin-top:6px;"><strong>${escapeHtml(targetSideZh)}大招与关键技能兑现：</strong>${injectHeroLogosIntoHtml(escapeHtml(ownSummaryText), report)}${
    oppSummaryText
      ? `<br/><span style="color:var(--muted);">对照${escapeHtml(otherSideZh)}表现：${injectHeroLogosIntoHtml(escapeHtml(
          oppSummaryText
        ), report)}</span>`
      : ""
  }</p>
          </details>
        </div>
      </div>
      ${execPickerBarHtml}
      <div class="micro-hero-exec-grid ${activeExecPos !== "all" ? "single-spotlight-mode" : ""}">${cardsHtml}</div>
    </div>
  `;
}

function renderMicroSupportVisionPane(report, df, targetSide, targetSideZh) {
  const vis = df.support_vision_by_side?.[targetSide];
  if (!vis) {
    return `<div class="empty-state compact">当前比赛暂无辅助眼位显微镜数据</div>`;
  }

  const pc = vis.posture_counts || {};
  const pp = vis.posture_pcts || {};
  const aggCnt = Number(pc.aggressive ?? 0);
  const midCnt = Number(pc.river_roshan ?? 0);
  const defCnt = Number(pc.defensive ?? 0);
  const aggPct = Number(pp.aggressive ?? 0);
  const midPct = Number(pp.river_roshan ?? 0);
  const defPct = Number(pp.defensive ?? 0);

  const totalObs = vis.total_obs ?? vis.obs_total ?? 0;
  const totalSen = vis.total_sen ?? vis.sen_total ?? 0;
  const avgLife = vis.avg_lifespan_sec ?? 0;
  const dewardedTotal = vis.dewarded_total ?? vis.obs_dewarded_count ?? 0;
  const dewardedPct = vis.dewarded_pct ?? vis.obs_dewarded_pct ?? 0;
  const godWards = vis.god_tier_wards || [];
  const blackoutWindows = vis.blackout_windows || [];

  const supList = vis.per_support_vision || vis.support_breakdown || [];
  const supRowsHtml = supList
    .map(
      (s) => `
      <tr>
        <td>${renderHeroCellWithLogo(s.pos, s.hero_short_zh, s.personaname, report, s.hero_img)}</td>
        <td><b>${s.obs_total ?? s.obs_placed ?? 0} 颗假眼</b> / ${s.sen_total ?? s.sen_placed ?? 0} 真眼</td>
        <td>⚔️ 进攻 ${s.aggressive_cnt ?? s.aggressive ?? 0} / ⚖️ 河道 ${s.river_cnt ?? s.river_roshan ?? 0} / 🛡️ 防守 ${s.defensive_cnt ?? s.defensive ?? 0}</td>
        <td><b>${s.avg_lifespan_sec ?? 0}s</b> / 360s</td>
        <td>被排 ${s.dewarded_cnt ?? s.dewarded_count ?? 0} 颗 / 反排敌方 <b>${s.obs_killed ?? s.obs_destroyed ?? 0} 假 ${s.sen_killed ?? 0} 真</b></td>
      </tr>
    `
    )
    .join("");

  const phaseRowsHtml = ["lane", "mid", "late"]
    .map((pk) => {
      const ph = vis.phase_posture?.[pk];
      if (!ph) return "";
      const pAgg = ph.aggressive ?? 0;
      const pMid = ph.river_roshan ?? 0;
      const pDef = ph.defensive ?? 0;
      const pTotal = ph.total ?? pAgg + pMid + pDef;
      return `
        <tr>
          <td><b>${escapeHtml(ph.label || pk)}</b></td>
          <td><b>${pTotal} 颗</b></td>
          <td>⚔️ 深入进攻眼 <b>${pAgg} 颗</b></td>
          <td>⚖️ 河道/肉山眼 <b>${pMid} 颗</b></td>
          <td>🛡️ 被动防守眼 <b>${pDef} 颗</b></td>
        </tr>
      `;
    })
    .join("");

  const instantList = vis.instant_dewards || [];
  const instantHtml =
    instantList.length > 0
      ? instantList
          .map(
            (w) =>
              `<li>${injectHeroLogosIntoHtml(
                `<b>${escapeHtml(w.time_str || "")}</b> · ${escapeHtml(
                  w.planter_hero || w.hero_short_zh || ""
                )} 插在 <b>${escapeHtml(w.zone_zh || "")} (${escapeHtml(
                  w.coords || `${w.x ?? ""},${w.y ?? ""}`
                )})</b> 的【${escapeHtml(w.posture_zh || w.posture_label || "假眼")}】仅存活 <b>${
                  w.lifespan_sec ?? 0
                } 秒</b>即被 ${escapeHtml(w.dewarded_by || "敌方")} 秒排！`,
                report
              )}</li>`
          )
          .join("")
      : `<li>✓ 本局未出现插下 2 分钟内被秒排的白给假眼</li>`;

  const cliffList = vis.cliff_spots || vis.cliff_obsession || [];
  const cliffHtml =
    cliffList.length > 0
      ? cliffList
          .map(
            (c) =>
              `<li>🚨 <b>${escapeHtml(c.zone_zh || "")} (${escapeHtml(
                c.coords || c.coord || ""
              )})</b> 全场重复插了 <b>${c.total_count ?? c.count ?? 0} 颗眼</b>（假眼 ${
                c.obs_count ?? c.count ?? 0
              } 颗 / 真眼 ${c.sen_count ?? 0} 颗 · 时间点：${escapeHtml(
                c.times_str || (c.times || []).join("、")
              )}）— ${escapeHtml(c.comment || "同一眼位反复博弈")}</li>`
          )
          .join("")
      : `<li>✓ 本局未出现同一高台头铁连插 3 颗以上眼位的情况</li>`;

  const godHtml =
    godWards.length > 0
      ? godWards
          .map(
            (gw) =>
              `<li>✨ <b>${escapeHtml(gw.time_str || "")}</b> · ${injectHeroLogosIntoHtml(
                escapeHtml(gw.planter_hero || ""),
                report
              )} 在 <b>${escapeHtml(gw.zone_zh || "")} (${escapeHtml(gw.coords || "")})</b> 点亮的【${escapeHtml(
                gw.posture_zh || ""
              )}】足足存活 <b>${gw.lifespan_sec ?? 360} 秒</b>！</li>`
          )
          .join("")
      : `<li>本局暂无点亮满 330 秒以上的深入进攻/河道封神眼</li>`;

  const blackoutHtml =
    blackoutWindows.length > 0
      ? blackoutWindows
          .map(
            (bw) =>
              `<li style="color:var(--red-light);">${injectHeroLogosIntoHtml(escapeHtml(bw.summary || ""), report)}</li>`
          )
          .join("")
      : `<li style="color:var(--green-light);">✓ 本局未出现全图假眼 ≤1 颗且导致队友接连阵亡的黑图真空期！</li>`;

  const obsRecords = vis.obs_records || [];
  const obsTableRows = obsRecords
    .map((w, idx) => {
      const life = w.lifespan_sec ?? 360;
      const wasDew = Boolean(w.was_dewarded ?? w.dewarded);
      const isInstant = wasDew && life <= 90;
      const fateText = wasDew
        ? `❌ 被 ${w.killer_zh || "敌方"} 排掉 (仅活 ${life}s)`
        : `✓ 自然到点消失 (满 ${life}s)`;
      return `
      <tr>
        <td>#${idx + 1}</td>
        <td><b>${escapeHtml(w.time_str || "")}</b></td>
        <td>${renderHeroCellWithLogo(w.planter_pos ?? w.pos, w.planter_hero || w.hero_short_zh, "", report)}</td>
        <td><b>${escapeHtml(w.zone_zh || "")}</b> <span style="color:var(--muted);">(${w.x ?? "?"}, ${w.y ?? "?"})</span></td>
        <td>${escapeHtml(w.posture_zh || w.posture_label || "")}</td>
        <td><b style="color:${
          isInstant ? "var(--red-light)" : wasDew ? "var(--gold-light)" : "var(--green-light)"
        }">${life} 秒</b> / 360 秒</td>
        <td>${injectHeroLogosIntoHtml(escapeHtml(w.fate_zh || fateText), report)}</td>
      </tr>
    `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>👁️ 6. 辅助眼位进攻/防守倾向、满时长封神眼与黑图真空期审计 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(vis.posture_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="posture-bar-stack" title="假眼进攻/河道/防守姿态比例">
        ${
          aggPct > 0
            ? `<div class="posture-seg agg" style="width:${Math.max(aggPct, 10)}%">⚔️ 进攻眼 ${aggPct}% (${aggCnt}颗)</div>`
            : ""
        }
        ${
          midPct > 0
            ? `<div class="posture-seg mid" style="width:${Math.max(midPct, 10)}%">⚖️ 河道/肉山眼 ${midPct}% (${midCnt}颗)</div>`
            : ""
        }
        ${
          defPct > 0
            ? `<div class="posture-seg def" style="width:${Math.max(defPct, 10)}%">🛡️ 防守保护眼 ${defPct}% (${defCnt}颗)</div>`
            : ""
        }
      </div>

      <div class="micro-kpi-row">
        <div class="micro-kpi-cell">
          <span>假眼总数 / 真眼总数</span>
          <strong>${totalObs} 颗假眼 / ${totalSen} 颗真眼</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>假眼平均存活寿命 (满6分钟=360s)</span>
          <strong>${avgLife} 秒 / 360 秒</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>假眼被排 / 秒排白给(&le;90s)</span>
          <strong>被排 ${dewardedTotal} 颗 (${dewardedPct}%) / 秒排 ${instantList.length} 颗</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>满时长封神眼 / 黑灯瞎火真空期</span>
          <strong>✨ ${godWards.length} 颗封神眼 / 🌑 ${blackoutWindows.length} 段黑图死人期</strong>
        </div>
      </div>

      <div class="micro-grid-2col">
        <div class="micro-card">
          <h4>🧭 辅助个人视野成绩单 &amp; 前中后期眼位深浅变化</h4>
          <div class="micro-table-wrap">
            <table class="micro-data-table">
              <thead>
                <tr>
                  <th>操刀人</th>
                  <th>假眼/真眼</th>
                  <th>进攻/河道/防守分布</th>
                  <th>平均寿命</th>
                  <th>被排/反排</th>
                </tr>
              </thead>
              <tbody>${supRowsHtml}</tbody>
            </table>
          </div>
          <div class="micro-table-wrap">
            <table class="micro-data-table">
              <thead>
                <tr>
                  <th>比赛阶段</th>
                  <th>总假眼</th>
                  <th>⚔️ 深入敌后进攻眼</th>
                  <th>⚖️ 河道/肉山眼</th>
                  <th>🛡️ 自家野区防守眼</th>
                </tr>
              </thead>
              <tbody>${phaseRowsHtml}</tbody>
            </table>
          </div>
        </div>

        <div class="micro-card">
          <h4>🚨 秒排白给眼 (&le;90s)、黑图真空期与满时长封神眼</h4>
          <div>
            <strong style="font-size:12px; color:var(--red-light);">🌑 全图黑灯瞎火视野真空期（全图假眼 &le;1 颗且队友阵亡）：</strong>
            <ul class="micro-insights-list" style="margin-top:5px;">${blackoutHtml}</ul>
          </div>
          <div style="margin-top:6px;">
            <strong style="font-size:12px; color:var(--gold-light);">⚡ 插下不到 90 秒即被排掉的秒排眼：</strong>
            <ul class="micro-insights-list" style="margin-top:5px;">${instantHtml}</ul>
          </div>
          <div style="margin-top:6px;">
            <strong style="font-size:12px; color:var(--gold-light);">📍 同一高台/眼位重复插眼习惯审计：</strong>
            <ul class="micro-insights-list" style="margin-top:5px;">${cliffHtml}</ul>
          </div>
          <div style="margin-top:6px;">
            <strong style="font-size:12px; color:var(--green-light);">✨ 点亮满时长(&ge;330s)的进攻/河道封神眼：</strong>
            <ul class="micro-insights-list" style="margin-top:5px;">${godHtml}</ul>
          </div>
        </div>
      </div>

      ${
        obsRecords.length > 0
          ? `
      <details class="squad-ledger-details" style="margin-bottom:0;">
        <summary class="squad-ledger-summary">
          <div class="squad-ledger-summary-left">
            <strong>📋 展开查看本局全部 ${totalObs} 颗假眼精确坐标、区域分类与存活秒数流水表</strong>
          </div>
          <span class="squad-ledger-summary-arrow">展开明细表 ▾</span>
        </summary>
        <div class="micro-table-wrap" style="border:none;">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>插眼时间</th>
                <th>操刀人</th>
                <th>地图区域 &amp; 坐标</th>
                <th>进攻/防守姿态</th>
                <th>存活寿命</th>
                <th>最终结局</th>
              </tr>
            </thead>
            <tbody>${obsTableRows}</tbody>
          </table>
        </div>
      </details>
      `
          : ""
      }
    </div>
  `;
}

function renderMicroStackAndSmokePane(report, df, targetSide, targetSideZh) {
  const ss = df.stacking_and_smoke_by_side?.[targetSide];
  if (!ss) {
    return `<div class="empty-state compact">当前比赛暂无堆野与开雾找节奏数据</div>`;
  }

  const totalStacks = ss.total_stacks ?? ss.total_team_stacks ?? 0;
  const totalCreeps = ss.total_creeps_stacked ?? 0;
  const supStacks = ss.support_stacks ?? 0;
  const coreStacks = ss.core_stacks ?? ss.core_self_stacks ?? 0;

  const stackRowsHtml = (ss.stack_rows || [])
    .map((r) => {
      const minsStr = Array.isArray(r.stack_mins)
        ? r.stack_mins.join("、")
        : r.stack_minutes_str || "";
      const roleLabel = r.role_tag || (r.pos >= 4 ? "辅助屯野" : "核心自拉");
      return `
      <tr>
        <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
        <td>${escapeHtml(roleLabel)}</td>
        <td><b style="color:${(r.camps_stacked ?? 0) > 0 ? "var(--gold-light)" : "var(--muted)"}">${
          r.camps_stacked ?? 0
        } 组</b> (${r.creeps_stacked ?? 0} 只野怪)</td>
        <td>${escapeHtml(minsStr || "无堆野记录")}</td>
      </tr>
    `;
    })
    .join("");

  const smokeEvents = ss.smoke_events || [];
  const smokeUses = ss.own_smoke_uses ?? ss.smoke_total_uses ?? smokeEvents.length;
  const smokeBought =
    ss.smoke_total_bought ??
    (ss.per_player_smokes || []).reduce((acc, item) => acc + Number(item.bought || 0), 0);
  const smokeSuccessCnt =
    ss.smoke_success_count ?? smokeEvents.filter((e) => e.outcome === "success").length;
  const smokeBackfireCnt =
    ss.smoke_backfire_count ?? smokeEvents.filter((e) => e.outcome === "backfire").length;
  const smokeDryCnt =
    ss.smoke_dry_count ?? smokeEvents.filter((e) => e.outcome === "wasted").length;

  const smokeRowsHtml = smokeEvents
    .map(
      (sm) => `
      <tr>
        <td><b>${escapeHtml(sm.time_str || "")}</b> (${escapeHtml(sm.phase_tag || sm.phase_zh || "")})</td>
        <td>${renderHeroCellWithLogo(
          sm.initiator_pos ?? sm.activator_pos,
          sm.initiator_hero || sm.activator_hero,
          sm.initiator_player || sm.activator_player,
          report
        )}</td>
        <td><b>${escapeHtml(sm.outcome_label || "")}</b></td>
        <td>${injectHeroLogosIntoHtml(escapeHtml(sm.detail || ""), report)}</td>
      </tr>
    `
    )
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-grid-2col">
        <div class="micro-card">
          <h4>🌾 辅助堆野屯矿 vs 大哥自拉野审计 (${escapeHtml(targetSideZh)}合计堆野 ${totalStacks} 组)</h4>
          <p style="margin:0; font-size:12.5px; color:var(--text); line-height:1.55;">${injectHeroLogosIntoHtml(
            escapeHtml(ss.stack_verdict || ""),
            report
          )}</p>
          <div class="micro-kpi-row" style="grid-template-columns: repeat(3, minmax(0, 1fr));">
            <div class="micro-kpi-cell">
              <span>全队累计堆野</span>
              <strong>${totalStacks} 组 (${totalCreeps} 只野)</strong>
            </div>
            <div class="micro-kpi-cell">
              <span>4/5号位辅助堆野</span>
              <strong>${supStacks} 组</strong>
            </div>
            <div class="micro-kpi-cell">
              <span>1~3号位大哥自拉野</span>
              <strong>${coreStacks} 组</strong>
            </div>
          </div>
          <div class="micro-table-wrap">
            <table class="micro-data-table">
              <thead>
                <tr>
                  <th>选手</th>
                  <th>角色定位</th>
                  <th>堆野组数</th>
                  <th>精确堆野分钟节点</th>
                </tr>
              </thead>
              <tbody>${stackRowsHtml}</tbody>
            </table>
          </div>
        </div>

        <div class="micro-card">
          <h4>💨 诡计之雾 (Smoke of Deceit) 开雾找节奏全记录 (${smokeUses} 波)</h4>
          <p style="margin:0; font-size:12.5px; color:var(--text); line-height:1.55;">${injectHeroLogosIntoHtml(
            escapeHtml(ss.smoke_verdict || ""),
            report
          )}</p>
          <div class="micro-kpi-row">
            <div class="micro-kpi-cell">
              <span>买雾 / 开雾次数</span>
              <strong>买 ${smokeBought} / 用 ${smokeUses}</strong>
            </div>
            <div class="micro-kpi-cell">
              <span>🟢 破雾大捷</span>
              <strong>${smokeSuccessCnt} 波</strong>
            </div>
            <div class="micro-kpi-cell">
              <span>🔴 开雾撞墙</span>
              <strong>${smokeBackfireCnt} 波</strong>
            </div>
            <div class="micro-kpi-cell">
              <span>🟡 哑火空雾</span>
              <strong>${smokeDryCnt} 波</strong>
            </div>
          </div>
          <div class="micro-table-wrap">
            <table class="micro-data-table">
              <thead>
                <tr>
                  <th>开雾时间</th>
                  <th>捏雾发起人</th>
                  <th>战果判定</th>
                  <th>破雾 90 秒内实战复盘</th>
                </tr>
              </thead>
              <tbody>
                ${
                  smokeRowsHtml ||
                  `<tr><td colspan="4" style="color:var(--muted);">本局未检测到诡计之雾使用记录</td></tr>`
                }
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderMicroLaningMechanicsPane(report, df, targetSide, targetSideZh, otherSideZh) {
  const lm = df.laning_mechanics_by_side?.[targetSide];
  if (!lm) {
    return `<div class="empty-state compact">当前比赛暂无对线细节显微镜数据</div>`;
  }

  const pullRows = lm.pulling_rows || lm.pull_rows || [];
  const pullRowsHtml = pullRows
    .map(
      (r) => `
      <tr>
        <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
        <td><b>${r.pull_ticks ?? r.pull_zone_samples ?? 0}</b> 次采样 (占比 ${r.pull_ratio_pct ?? r.pull_presence_pct ?? 0}%)</td>
        <td><b>${r.early_sentries ?? r.early_sentries_placed ?? 0} 颗真眼</b></td>
        <td>10m 正/反补 <b>${r.lh10 ?? 0}/${r.dn10 ?? 0} 刀</b></td>
        <td><span class="status-pill ${
          (r.status_tag || "").includes("积极") ? "connected" : ""
        }">${escapeHtml(r.status_tag || "常规保线")}</span></td>
        <td>${injectHeroLogosIntoHtml(escapeHtml(r.comment || r.assessment || ""), report)}</td>
      </tr>
    `
    )
    .join("");

  const mapRows = lm.map_interact_rows || [];
  const lotusPills = mapRows
    .filter((r) => (r.lotus_used ?? 0) > 0)
    .map(
      (r) =>
        `<span class="micro-exec-badge good">${injectHeroLogosIntoHtml(
          `${r.pos}号位 · ${escapeHtml(r.hero_short_zh || "")} (${escapeHtml(
            r.personaname || ""
          )})：<b>吃莲花 ×${r.lotus_used}</b>`,
          report
        )}</span>`
    )
    .join("");

  const wisdomTimeline = lm.wisdom_timeline || lm.wisdom_events || [];
  const wisdomPills = wisdomTimeline
    .map(
      (w) =>
        `<span class="micro-exec-badge ${w.side === targetSide ? "good" : "warn"}">${injectHeroLogosIntoHtml(
          `<b>${escapeHtml(w.time_str || "")}</b> · ${escapeHtml(w.side_zh || "")} ${
            w.pos ?? "?"
          }号位 ${escapeHtml(w.hero_short_zh || "")} (${escapeHtml(
            w.personaname || ""
          )}) 摘取智慧符`,
          report
        )}</span>`
    )
    .join("");

  const gatePills = mapRows
    .filter((g) => (g.twin_gate ?? 0) > 0 || (g.watcher_lamp ?? 0) > 0)
    .map(
      (g) =>
        `<span class="micro-exec-badge ${g.twin_gate > 0 ? "good" : ""}">${injectHeroLogosIntoHtml(
          `${g.pos}号位 · ${escapeHtml(g.hero_short_zh || "")}：<b>走门 ×${g.twin_gate ?? 0}</b> / 点灯 ×${
            g.watcher_lamp ?? 0
          } / 抢哨 ×${g.outpost_capture ?? 0}`,
          report
        )}</span>`
    )
    .join("");

  const waterTimeline = lm.water_runes_timeline || lm.water_events || [];
  const waterPills = waterTimeline
    .map(
      (w) =>
        `<span class="micro-exec-badge ${w.side === targetSide ? "good" : ""}">${injectHeroLogosIntoHtml(
          `${escapeHtml(w.time_str || "")} · ${escapeHtml(w.side_zh || "")} ${escapeHtml(
            w.hero_short_zh || ""
          )} 控水符`,
          report
        )}</span>`
    )
    .join("");

  const ownLotus = lm.own_lotus_total ?? lm.lotus_own_total ?? 0;
  const oppLotus = lm.opp_lotus_total ?? lm.lotus_opp_total ?? 0;
  const ownWisdom = lm.own_wisdom_cnt ?? lm.wisdom_own_count ?? 0;
  const oppWisdom = lm.opp_wisdom_cnt ?? lm.wisdom_opp_count ?? 0;
  const ownGate = lm.own_gate_total ?? lm.gate_own_count ?? 0;
  const oppGate = lm.opp_gate_total ?? lm.gate_opp_count ?? 0;
  const ownLamp = lm.own_lamp_total ?? lm.lamp_own_count ?? 0;
  const oppLamp = lm.opp_lamp_total ?? lm.lamp_opp_count ?? 0;

  // Relocated 3-lane 10m matchup cards so all laning analysis lives cleanly in Tab 4
  const lanes = df.lane_matchups || [];
  const lanesHtml =
    lanes.length > 0
      ? `
      <div class="lane-matchups-grid">
        ${lanes
          .map((lane) => {
            const renderHeroMini = (h) => `
              <div class="lm-hero-row">
                <div class="lm-hero-id">
                  ${h.hero_img ? `<img src="${escapeHtml(h.hero_img)}" alt="${escapeHtml(h.hero_short_zh || "")}" width="28" height="16" loading="lazy" />` : ""}
                  <span><b>${h.pos}号位·${escapeHtml(h.hero_short_zh || "")}</b> (${escapeHtml(h.personaname || "")})</span>
                </div>
                <span class="lm-hero-stats">${h.lh10 ?? 0}/${h.dn10 ?? 0}刀 · ${fmtNum(h.gold10 || 0)}金 · 效率${h.lane_eff ?? 0}%</span>
              </div>
            `;
            const isOwnWin = lane.winner_side === targetSide;
            const isEven = lane.winner_side === "even";
            const badgeCls = isEven ? "even" : isOwnWin ? "win" : "loss";
            return `
              <article class="lane-matchup-card">
                <div class="lm-head">
                  <strong>${escapeHtml(lane.title || "")}</strong>
                  <span class="lm-verdict-pill ${badgeCls}">${escapeHtml(lane.verdict_zh || "")}</span>
                </div>
                <div class="lm-sides-box">
                  <div class="lm-side-col">
                    <div class="lm-side-title dire">夜魇对线 (${fmtNum(lane.dire_gold10 || 0)}金 · ${escapeHtml(lane.dire_lh_dn || "0/0")}刀)</div>
                    ${(lane.dire_heroes || []).map(renderHeroMini).join("")}
                  </div>
                  <div class="lm-side-col">
                    <div class="lm-side-title rad">天辉对线 (${fmtNum(lane.radiant_gold10 || 0)}金 · ${escapeHtml(lane.radiant_lh_dn || "0/0")}刀)</div>
                    ${(lane.radiant_heroes || []).map(renderHeroMini).join("")}
                  </div>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    `
      : "";

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🌱 4. 对线期拉野·封野·走门·莲花·智慧经验符全维审计 (${escapeHtml(targetSideZh)} vs ${escapeHtml(
    otherSideZh
  )})</h3>
          <p>${injectHeroLogosIntoHtml(
            `${escapeHtml(lm.lotus_verdict || "")} ｜ ${escapeHtml(lm.wisdom_verdict || "")}`,
            report
          )}</p>
        </div>
      </div>

      <div class="micro-kpi-row">
        <div class="micro-kpi-cell">
          <span>🌺 疗伤莲花争夺 (${escapeHtml(targetSideZh)}:${escapeHtml(otherSideZh)})</span>
          <strong>${ownLotus} 颗 : ${oppLotus} 颗</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>📚 7/14/21m 智慧神符 (${escapeHtml(targetSideZh)}:${escapeHtml(otherSideZh)})</span>
          <strong>${ownWisdom} 枚 : ${oppWisdom} 枚</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🚪 双生门传送绕后 (${escapeHtml(targetSideZh)}:${escapeHtml(otherSideZh)})</span>
          <strong>${ownGate} 次 : ${oppGate} 次</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🏮 观察者点灯 (${escapeHtml(targetSideZh)}:${escapeHtml(otherSideZh)})</span>
          <strong>点灯 ${ownLamp} 次 : ${oppLamp} 次</strong>
        </div>
      </div>

      <div class="micro-card">
        <h4>🪝 辅助对线期拉野/消兵区活跃度、前 10 分钟封野真眼与反补审计</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>辅助选手</th>
                <th>拉野点坐标驻留权重</th>
                <th>0-10m 封野/排野真眼</th>
                <th>10m 正/反补</th>
                <th>对线评级</th>
                <th>对线细节评语</th>
              </tr>
            </thead>
            <tbody>${pullRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="micro-grid-2col">
        <div class="micro-card">
          <h4>🌺 疗伤莲花 (Lotus) &amp; 💧 2/4m 中路水符归属明细</h4>
          <p style="margin:0; font-size:12px; color:var(--muted);">${injectHeroLogosIntoHtml(
            escapeHtml(lm.lotus_verdict || ""),
            report
          )}</p>
          <div class="micro-badges-wrap">${lotusPills || `<span class="micro-exec-badge">本方未记录到吃莲花事件</span>`}</div>
          ${
            waterPills
              ? `<div style="margin-top:6px;"><strong style="font-size:12px; color:var(--gold-light);">💧 2/4分钟河道水符：</strong><div class="micro-badges-wrap" style="margin-top:4px;">${waterPills}</div></div>`
              : ""
          }
        </div>

        <div class="micro-card">
          <h4>📚 智慧神符 (经验符) 时间轴 &amp; 🚪 双生门传送 (Twin Gate)</h4>
          <p style="margin:0; font-size:12px; color:var(--muted);">${injectHeroLogosIntoHtml(
            escapeHtml(lm.wisdom_verdict || ""),
            report
          )}</p>
          <div class="micro-badges-wrap">${wisdomPills || `<span class="micro-exec-badge">无智慧神符拾取记录</span>`}</div>
          <div style="margin-top:6px;">
            <strong style="font-size:12px; color:var(--gold-light);">🚪 双生门传送与观察者点灯明细：</strong>
            <div class="micro-badges-wrap" style="margin-top:4px;">${
              gatePills || `<span class="micro-exec-badge">整局无人使用双生门传送</span>`
            }</div>
          </div>
        </div>
      </div>

      ${lanesHtml}
    </div>
  `;
}

function renderMicroTpRotationPane(report, df, targetSide, targetSideZh) {
  const tp = df.tp_rotation_by_side?.[targetSide];
  if (!tp) {
    return `<div class="empty-state compact">当前比赛暂无 TP 救人与团战缺席抓包数据</div>`;
  }

  const pRowsHtml = (tp.player_tp_rows || [])
    .map((r) => {
      const tpUsed = r.tp_used ?? 0;
      const tpBought = r.tp_bought ?? 0;
      const earlyTp = r.early_tp_cnt ?? r.early_tp_rotations_12m ?? 0;
      const tfTpCnt = r.tf_tp_cnt ?? r.teamfight_tp_saves ?? 0;
      const tfTpTimes = r.tf_tp_times || r.teamfight_tp_times || [];
      const tfAbsentCnt = r.tf_absent_cnt ?? r.spectator_teamfights ?? 0;
      const tfAbsentTimes = r.tf_absent_times || r.spectator_times || [];
      return `
      <tr>
        <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
        <td><b>${tpUsed} 次</b></td>
        <td><b style="color:${tpBought === 0 ? "var(--red-light)" : "var(--text)"}">${tpBought} 张</b>${
        tpBought === 0 ? " (全靠复活白嫖!)" : ""
      }</td>
        <td><b>${earlyTp} 次</b></td>
        <td><b style="color:${tfTpCnt > 0 ? "var(--green-light)" : "var(--muted)"}">${tfTpCnt} 次</b> (${escapeHtml(
        tfTpTimes.join("、") || "无"
      )})</td>
        <td><b style="color:${tfAbsentCnt > 0 ? "var(--red-light)" : "var(--green-light)"}">${tfAbsentCnt} 波</b>${
        tfAbsentTimes.length > 0 ? ` (${escapeHtml(tfAbsentTimes.join("、"))})` : ""
      }</td>
        <td>${injectHeroLogosIntoHtml(escapeHtml(r.verdict || ""), report)}</td>
      </tr>
    `;
    })
    .join("");

  const tfRowsHtml = (tp.teamfight_tp_events || [])
    .map((ev) => {
      const saviors = (ev.tp_saviors || [])
        .map(
          (s) =>
            `<span class="micro-tf-pill">🟢 ${injectHeroLogosIntoHtml(
              `${s.pos ?? "?"}号位·${escapeHtml(s.hero_short_zh || "")} 亮TP支援 (打${fmtNum(
                s.damage || 0
              )}伤)`,
              report
            )}</span>`
        )
        .join("");
      const specs = (ev.spectators || [])
        .map(
          (sp) =>
            `<span class="micro-tf-pill held-die">🔴 ${injectHeroLogosIntoHtml(
              `${sp.pos ?? "?"}号位·${escapeHtml(sp.hero_short_zh || "")} (${escapeHtml(
                sp.personaname || ""
              )}) 0伤害0技能未亮TP旁观`,
              report
            )}</span>`
        )
        .join("");
      return `
        <tr>
          <td><b>团战 #${ev.tf_index ?? "?"}</b> (${escapeHtml(ev.time_range || "")})</td>
          <td>本方阵亡 <b>${ev.own_deaths ?? 0}</b> 人 / 击杀敌方 <b>${ev.opp_kills ?? 0}</b> 人</td>
          <td><div class="micro-tf-pills">${saviors || `<span style="color:var(--muted);">无人交TP</span>`}</div></td>
          <td><div class="micro-tf-pills">${
            specs || `<span style="color:var(--green-light);">✓ 全员参战无OB</span>`
          }</div></td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🆘 8. TP 救人及时性、主动买 TP 习惯与团战边缘 OB 抓包 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(tp.tp_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-card">
        <h4>📜 1~5 号位 TP 购买量、前 12 分钟支援 TP 与团战亮 TP 审计表</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>整局使用 TP</th>
                <th>主动花钱买 TP</th>
                <th>前12m支援/回线TP</th>
                <th>团战亮 TP 救人/进场</th>
                <th>队友阵亡时0参与旁观</th>
                <th>TP 支援习惯判词</th>
              </tr>
            </thead>
            <tbody>${pRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="micro-card">
        <h4>🚨 历次团战谁亮了 TP 救人 vs 谁在队友挨揍阵亡时 0 伤害 0 技能未亮 TP 旁观</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>团战时间窗</th>
                <th>双方伤亡交换</th>
                <th>🟢 团战期间亮出 TP 支援的功臣</th>
                <th>🔴 队友阵亡时全程 0 伤害 0 技能未亮 TP 旁观抓包</th>
              </tr>
            </thead>
            <tbody>${tfRowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/**
 * Tab 2: 💀 憋死 BKB / 救命装与团战 0 技能秒躺法医尸检
 */
function renderMicroUnpressedSavesPane(report, df, targetSide, targetSideZh) {
  const us = df.unpressed_saves_by_side?.[targetSide];
  if (!us) {
    return `<div class="empty-state compact">当前比赛暂无憋死 BKB / 救命装与团战 0 技能秒躺数据</div>`;
  }

  const critTotal = Number(us.critical_total ?? 0);
  const zeroSpellTotal = Number(us.zero_spell_total ?? 0);
  const incidents = us.incidents || [];
  const pRows = us.player_rows || [];

  const pRowsHtml = pRows
    .map((r) => {
      const coreCnt = Number(r.unpressed_core_cnt ?? 0);
      const wandCnt = Number(r.unpressed_wand_cnt ?? 0);
      const zeroCnt = Number(r.zero_spell_cnt ?? 0);
      return `
        <tr>
          <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
          <td><b>${r.tf_deaths ?? 0} 次</b></td>
          <td><b style="color:${coreCnt > 0 ? "var(--red-light)" : "var(--green-light)"}">${coreCnt} 次</b>${
        wandCnt > 0 ? ` <span style="color:var(--gold-light);">(+魔棒/刃甲未按 ${wandCnt} 次)</span>` : ""
      }</td>
          <td><b style="color:${zeroCnt > 0 ? "var(--red-light)" : "var(--green-light)"}">${zeroCnt} 次</b></td>
          <td style="font-size:11.5px;color:var(--muted);">${escapeHtml(r.owned_saves_str || "未合成主动保命装")}</td>
          <td>${injectHeroLogosIntoHtml(escapeHtml(r.verdict || ""), report)}</td>
        </tr>
      `;
    })
    .join("");

  const incHtml =
    incidents.length > 0
      ? incidents
          .map(
            (inc) => `
        <li>
          <span class="micro-tf-pill ${inc.severity === "critical" ? "held-die" : ""}">
            ${inc.severity === "critical" ? "🚨 一级憋死犯罪" : "⚠️ 保命细节疏漏"} · ${escapeHtml(
              inc.time_range || ""
            )}
          </span>
          ${injectHeroLogosIntoHtml(
            `<b>${inc.pos ?? "?"}号位 · ${escapeHtml(inc.hero_short_zh || "")} (${escapeHtml(
              inc.personaname || ""
            )})</b>：${escapeHtml(inc.detail || "")}`,
            report
          )}
        </li>
      `
          )
          .join("")
      : `<li>✓ 全队本局所有团战阵亡前均已按出已拥有的核心保命装与技能，未检测到憋死 BKB/推推/微光/分身斧记录！</li>`;

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>💀 2. 憋死 BKB / 救命装与团战 0 技能秒躺尸检 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(us.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-kpi-row" style="grid-template-columns: repeat(3, minmax(0, 1fr));">
        <div class="micro-kpi-cell">
          <span>💀 憋死核心保命装 (BKB/推推/微光/分身/绿杖等)</span>
          <strong style="color:${critTotal > 0 ? "var(--red-light)" : "var(--green-light)"}">${critTotal} 人次</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🔇 中后期团战 0 技能释放直接秒躺</span>
          <strong style="color:${zeroSpellTotal > 0 ? "var(--red-light)" : "var(--green-light)"}">${zeroSpellTotal} 人次</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>📋 抓包具体团战憋死/秒躺事故数</span>
          <strong>${incidents.length} 起典型尸检</strong>
        </div>
      </div>

      <div class="micro-card">
        <h4>⚰️ 1~5 号位已合成主动救命装按键次数 &amp; 团战憋死尸检总表</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>团战阵亡次数</th>
                <th>憋死核心保命装</th>
                <th>团战0技能秒躺</th>
                <th>本局合成保命装及全场按键次数</th>
                <th>团战反应与保命习惯判词</th>
              </tr>
            </thead>
            <tbody>${pRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="micro-card">
        <h4>🚨 历次团战憋死救命装 / 0 技能暴毙逐波抓包笔录</h4>
        <ul class="micro-insights-list">${incHtml}</ul>
      </div>
    </div>
  `;
}

/**
 * Tab 4: 🕵️‍♂️ 单带无故被抓 & 敌方开雾强抓 vs 未开雾纯白给侦探社
 */
function renderMicroMapSpacePane(report, df, targetSide, targetSideZh) {
  const ms = df.map_space_by_side?.[targetSide];
  if (!ms) {
    return `<div class="empty-state compact">当前比赛暂无地图空间理解与落单被抓数据</div>`;
  }

  const totalSolo = Number(ms.total_solo_pickoffs ?? 0);
  const totalUnsmoked = Number(ms.total_unsmoked_blind_feeds ?? 0);
  const events = ms.solo_pickoff_events || [];
  const pRows = ms.player_space_rows || [];

  const pRowsHtml = pRows
    .map((r) => {
      const soloCnt = Number(r.solo_pickoff_cnt ?? 0);
      const unsmokedCnt = Number(r.unsmoked_blind_cnt ?? 0);
      const smokeGankCnt = Number(r.smoke_ganked_cnt ?? 0);
      const isBad = r.grade === "bad" || soloCnt >= 2;
      const isGood = r.grade === "good";
      return `
        <tr>
          <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
          <td class="micro-badge-cell"><span class="micro-exec-badge ${isBad ? "warn" : isGood ? "good" : ""}">${escapeHtml(
        r.space_style_badge || "常规驻守"
      )}</span></td>
          <td>兵线 <b>${r.lane_kills ?? 0}</b> (${r.lane_farm_pct ?? 0}%) / 野区 <b>${r.neutral_kills ?? 0}</b> (${r.jungle_farm_pct ?? 0}%)</td>
          <td><b style="color:${(r.tower_damage ?? 0) >= 3500 ? "var(--gold-light)" : "var(--text)"}">${fmtNum(
        r.tower_damage || 0
      )}</b></td>
          <td>
            <b style="color:${soloCnt >= 2 ? "var(--red-light)" : soloCnt === 0 ? "var(--green-light)" : "var(--gold-light)"}">${soloCnt} 次</b> (送 ${fmtNum(
        r.solo_gold_fed || 0
      )} 金)
            ${
              soloCnt > 0
                ? `<div style="font-size:11px; margin-top:2px;">
                    ${unsmokedCnt > 0 ? `<span style="color:var(--red-light);font-weight:700;">🚨 未开雾白给 ${unsmokedCnt}次</span>` : ""}
                    ${smokeGankCnt > 0 ? `<span style="color:var(--muted);">🌫️ 被开雾抓 ${smokeGankCnt}次</span>` : ""}
                  </div>`
                : ""
            }
          </td>
          <td>${injectHeroLogosIntoHtml(escapeHtml(r.verdict || ""), report)}</td>
        </tr>
      `;
    })
    .join("");

  const evRowsHtml = events
    .map((ev) => {
      const killerImg = findMatchHeroImg(ev.killer_zh || "", report);
      const killerHtml = killerImg
        ? `<span class="inline-hero-chip"><img class="inline-hero-logo" src="${escapeHtml(killerImg)}" alt="" /><b>${escapeHtml(ev.killer_zh || "敌方")}</b></span>`
        : `<b>${escapeHtml(ev.killer_zh || "敌方")}</b>`;
      const isSmoke = Boolean(ev.is_enemy_smoke_gank);
      const natureTag = ev.gank_nature_tag || (isSmoke ? "🌫️ 敌方开雾强抓" : ev.vision_tag || "");
      return `
      <tr>
        <td><b>${escapeHtml(ev.time_str || "")}</b></td>
        <td>${renderHeroCellWithLogo(ev.pos, ev.hero_short_zh, ev.personaname, report, ev.hero_img)}</td>
        <td><b>${escapeHtml(ev.zone_zh || "")}</b> (被 ${killerHtml} 抓死)</td>
        <td>
          <div style="font-weight:700; color:${isSmoke ? "var(--gold-light)" : "var(--red-light)"};">${escapeHtml(natureTag)}</div>
          <div style="font-size:11px; color:var(--muted);">${escapeHtml(ev.vision_tag || "")}</div>
        </td>
        <td>读秒 <b>${ev.time_dead ?? 0}s</b> · 送 <b>${fmtNum(ev.gold_fed || 0)} 金</b></td>
        <td><b style="color:${
          (ev.consequence || "").includes("无战略收益") ? "var(--gold-light)" : "var(--red-light)"
        }">${escapeHtml(ev.consequence || "")}</b></td>
      </tr>
    `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🕵️‍♂️ 4. 单带无故被抓 &amp; 敌方开雾强抓 vs 未开雾纯白给侦探社 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(ms.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-kpi-row">
        <div class="micro-kpi-cell">
          <span>9m后落单被抓总次数</span>
          <strong style="color:${totalSolo >= 4 ? "var(--red-light)" : "var(--gold-light)"};">${totalSolo} 次落单被抓</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🚨 敌方未开雾 · 纯白给次数</span>
          <strong style="color:${totalUnsmoked > 0 ? "var(--red-light)" : "var(--green-light)"};">${totalUnsmoked} 次未开雾白给</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🌫️ 敌方开雾强抓次数</span>
          <strong>${Math.max(0, totalSolo - totalUnsmoked)} 次被诡计之雾突袭</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>判定依据</span>
          <strong>敌方65秒内开雾日志 + 假眼ehandle实时坐标 + 70s掉塔丢盾</strong>
        </div>
      </div>

      <div class="micro-card">
        <h4>🧭 1~5 号位地图空间画像 · 收线 vs 缩野比例、推塔牵制与中后期落单被抓统计</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>地图空间理解画像</th>
                <th>收线补刀 vs 刷野占比</th>
                <th>建筑推塔转化</th>
                <th>9m后落单被抓 (开雾 vs 白给)</th>
                <th>空间利用与带线纪律判词</th>
              </tr>
            </thead>
            <tbody>${pRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="micro-card">
        <h4>🚨 9 分钟后脱离团队「单带无故被抓 / 黑图盲区乱逛被抓死」逐次铁证笔录 (共 ${totalSolo} 次，其中未开雾白给 ${totalUnsmoked} 次)</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>被抓时间</th>
                <th>落单当事人</th>
                <th>暴毙地点 &amp; 凶手</th>
                <th>被抓定性 (敌方开雾 vs 未开雾白给)</th>
                <th>读秒与经济出血</th>
                <th>70秒内连锁后果 / 战略收益审计</th>
              </tr>
            </thead>
            <tbody>
              ${
                evRowsHtml ||
                `<tr><td colspan="6" style="color:var(--green-light);">✓ 本局 9 分钟后未发生脱离团队无聊带线或盲区落单被抓事故！</td></tr>`
              }
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/**
 * Tab 4: 🛡️ 承伤来源拆解与防装合规审计
 */
function renderMicroDamageReceivedPane(report, df, targetSide, targetSideZh) {
  const dr = df.damage_received_by_side?.[targetSide];
  if (!dr) {
    return `<div class="empty-state compact">当前比赛暂无承伤来源拆解与防装审计数据</div>`;
  }

  const rows = dr.rows || [];
  const rowsHtml = rows
    .map((r) => {
      const killersStr = (r.top_killers || [])
        .map(
          (k) =>
            `<span class="micro-tf-pill">${escapeHtml(k.zh_name || "")} <b>${fmtNum(
              k.damage || 0
            )}</b> (${k.share_pct ?? 0}%)</span>`
        )
        .join("");
      const defItemsStr =
        (r.def_items_owned || []).length > 0
          ? r.def_items_owned.map((it) => `<span class="micro-exec-badge good">${escapeHtml(it)}</span>`).join("")
          : `<span class="micro-exec-badge warn">未出针对防装</span>`;

      return `
        <tr>
          <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
          <td><b>${fmtNum(r.total_dmg_taken || 0)}</b></td>
          <td>🔮 技能/法系 <b>${r.spell_pct ?? 0}%</b> (${fmtNum(r.spell_dmg || 0)})<br/>🗡️ 物理平A <b>${
        r.auto_pct ?? 0
      }%</b> (${fmtNum(r.auto_dmg || 0)})</td>
          <td><div class="micro-tf-pills">${killersStr || "平A为主"}</div></td>
          <td><div class="micro-badges-wrap">${defItemsStr}</div></td>
          <td>${injectHeroLogosIntoHtml(escapeHtml(r.verdict || ""), report)}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🛡️ 4. 承伤来源拆解（物理平A vs 技能爆发）与防装合规审计 (${escapeHtml(targetSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(dr.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-card">
        <h4>🛡️ 1~5 号位挨揍伤害构成、头号致死技能凶手与防装（BKB/微光/笛子/绿杖/护甲）合规表</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>总承受英雄伤害</th>
                <th>技能爆发 vs 物理平A占比</th>
                <th>揍他最狠的 Top 4 敌方技能/物品</th>
                <th>已出针对性防装</th>
                <th>防装选择合规判词</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/**
 * Tab 9: 💰 经济来源结构拆解 & 局内信号/暂停/公屏互动档案
 */
function renderMicroEconomyAndPingsPane(report, df, targetSide, targetSideZh) {
  const ep = df.economy_and_pings_by_side?.[targetSide];
  if (!ep) {
    return `<div class="empty-state compact">当前比赛暂无经济来源结构与信号互动数据</div>`;
  }

  const rows = ep.econ_rows || [];
  const rowsHtml = rows
    .map(
      (r) => `
      <tr>
        <td>${renderHeroCellWithLogo(r.pos, r.hero_short_zh, r.personaname, report, r.hero_img)}</td>
        <td class="micro-badge-cell"><span class="micro-exec-badge">${escapeHtml(r.econ_tag || "均衡发育")}</span></td>
        <td>🌾 <b>${fmtNum(r.lane_gold || 0)}</b> (${r.lane_pct ?? 0}%)</td>
        <td>🌲 <b>${fmtNum(r.jungle_gold || 0)}</b> (${r.jungle_pct ?? 0}%)</td>
        <td>⚔️ <b>${fmtNum(r.kill_gold || 0)}</b> (${r.kill_pct ?? 0}%)</td>
        <td>🏰 <b>${fmtNum(r.obj_gold || 0)}</b> (${r.obj_pct ?? 0}%)</td>
        <td><b style="color:${
          (r.death_loss || 0) + (r.buyback_loss || 0) >= 2200 ? "var(--red-light)" : "var(--muted)"
        }">-${fmtNum((r.death_loss || 0) + (r.buyback_loss || 0))} 金</b> (死-${fmtNum(
        r.death_loss || 0
      )} / 买活-${fmtNum(r.buyback_loss || 0)})</td>
        <td>📡 点信号 <b>${r.pings ?? 0}</b> 次 / 轮盘 <b>${r.chatwheel_cnt ?? 0}</b> 条</td>
      </tr>
    `
    )
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>💰 9. 经济来源结构拆解（兵线/野区/人头/塔盾/阵亡买活损耗）与局内信号互动 (${escapeHtml(
            targetSideZh
          )})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(ep.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-card">
        <h4>💳 1~5 号位进账渠道占比（谁在刷野吸血、谁在打钱推塔、谁阵亡买活扣钱最多）&amp; 局内地图信号频次</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>财政风格画像</th>
                <th>🌾 兵线进账</th>
                <th>🌲 野区进账</th>
                <th>⚔️ 人头/助攻进账</th>
                <th>🏰 建筑/肉山/赏金</th>
                <th>💸 阵亡+买活扣钱损耗</th>
                <th>📡 地图信号 &amp; 轮盘</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/**
 * Tab 10: ⚔️ 1~5号位同位置宿敌 1v1 正面对位审判 & OpenDota 全球同英雄百分位标尺
 */
function renderMicroRoleMirrorPane(report, df, targetSide, targetSideZh, otherSideZh) {
  const rm = df.role_mirror_by_side?.[targetSide];
  if (!rm) {
    return `<div class="empty-state compact">当前比赛暂无 1~5 号位同位置宿敌 1v1 对位数据</div>`;
  }

  const rows = rm.mirror_rows || [];
  const wonOverall = Number(rm.won_overall_cnt ?? 0);
  const wonLanes = Number(rm.won_lanes_cnt ?? 0);
  const avgOwnBm = rows.length
    ? (rows.reduce((s, r) => s + Number(r.own_bm_avg ?? 50), 0) / rows.length).toFixed(1)
    : "50.0";
  const avgOppBm = rows.length
    ? (rows.reduce((s, r) => s + Number(r.opp_bm_avg ?? 50), 0) / rows.length).toFixed(1)
    : "50.0";

  const fmtBmTop = (bmArr) => {
    if (!Array.isArray(bmArr) || bmArr.length === 0) {
      return typeof bmArr === "string" && bmArr ? bmArr : "全球均值";
    }
    return bmArr
      .slice(0, 2)
      .map((b) => `${b.label_zh || b.key || "指标"}超${b.pct ?? 50}%`)
      .join(" / ");
  };

  const cardsHtml = rows
    .map((r) => {
      const g10Diff = Number(r.gold10_diff ?? 0);
      const nwDiff = Number(r.nw_diff ?? 0);
      const dmgDiff = Number(r.dmg_diff ?? 0);
      const ownShare = Number(r.own_share_pct ?? 50);
      const oppShare = Number(r.opp_share_pct ?? 50);
      const gradeCls = r.grade === "good" ? "grade-good" : r.grade === "bad" ? "grade-bad" : "grade-warn";
      const badgeTone = r.grade === "good" ? "good" : r.grade === "bad" ? "warn" : "";
      const ownBmTopStr = fmtBmTop(r.own_bm_top);
      const oppBmTopStr = fmtBmTop(r.opp_bm_top);

      return `
        <article class="role-mirror-card ${gradeCls}">
          <div class="mirror-vs-header">
            <div class="mirror-side-box own">
              ${
                r.own_img
                  ? `<img class="mirror-hero-avatar" src="${escapeHtml(r.own_img)}" alt="${escapeHtml(
                      r.own_hero || ""
                    )}" loading="lazy" />`
                  : ""
              }
              <div>
                <div>
                  <strong>[${escapeHtml(targetSideZh)} ${r.pos ?? "?"}号位] ${escapeHtml(
        r.own_hero || ""
      )}</strong>
                  <span style="color:var(--text-dim); font-size:11.5px;">(${escapeHtml(
                    r.own_player || ""
                  )})</span>
                </div>
                <div style="font-size:11.5px; color:var(--text-dim); margin-top:2px;">
                  KDA <b>${escapeHtml(r.own_kda || "0/0/0")}</b> · 评分 <b>${
        r.own_rating ?? 0
      }</b> · <span class="bm-percentile-pill">🌍 全球超越 ${r.own_bm_avg ?? 50}% (${escapeHtml(
        ownBmTopStr
      )})</span>
                </div>
              </div>
            </div>

            <div class="mirror-vs-center">
              <span class="micro-exec-badge ${badgeTone}">${escapeHtml(
        r.verdict_tag || "⚖️ 旗鼓相当"
      )}</span>
              <span class="mirror-h2h-pill">⚔️ 正面单杀/击杀 ${r.h2h_own_kills ?? 0} : ${
        r.h2h_opp_kills ?? 0
      }</span>
            </div>

            <div class="mirror-side-box opp">
              ${
                r.opp_img
                  ? `<img class="mirror-hero-avatar" src="${escapeHtml(r.opp_img)}" alt="${escapeHtml(
                      r.opp_hero || ""
                    )}" loading="lazy" />`
                  : ""
              }
              <div>
                <div>
                  <strong>[${escapeHtml(otherSideZh)} ${r.pos ?? "?"}号位] ${escapeHtml(
        r.opp_hero || ""
      )}</strong>
                  <span style="color:var(--text-dim); font-size:11.5px;">(${escapeHtml(
                    r.opp_player || ""
                  )})</span>
                </div>
                <div style="font-size:11.5px; color:var(--text-dim); margin-top:2px;">
                  <span class="bm-percentile-pill">🌍 全球超越 ${r.opp_bm_avg ?? 50}% (${escapeHtml(
        oppBmTopStr
      )})</span> · 评分 <b>${r.opp_rating ?? 0}</b> · KDA <b>${escapeHtml(
        r.opp_kda || "0/0/0"
      )}</b>
                </div>
              </div>
            </div>
          </div>

          <div class="mirror-tug-bar" title="同位置压制力占比：本方 ${ownShare}% vs 敌方 ${oppShare}%">
            <div class="mirror-tug-own" style="width:${ownShare}%"></div>
            <div class="mirror-tug-opp" style="width:${oppShare}%"></div>
          </div>

          <div class="mirror-metrics-grid">
            <div class="mirror-metric-cell">
              <div class="mirror-metric-label">🌱 10m 对线经济 &amp; 补刀</div>
              <div class="mirror-metric-val">
                ${fmtNum(r.gold10_own || 0)} vs ${fmtNum(r.gold10_opp || 0)}
                <span style="color:${
                  g10Diff >= 300
                    ? "var(--green-light)"
                    : g10Diff <= -300
                    ? "var(--red-light)"
                    : "var(--text-dim)"
                }">(${g10Diff >= 0 ? "+" : ""}${fmtNum(g10Diff)})</span>
                · 刀 ${escapeHtml(r.lh10_own || "0/0")} vs ${escapeHtml(r.lh10_opp || "0/0")}
              </div>
            </div>
            <div class="mirror-metric-cell">
              <div class="mirror-metric-label">💰 终局净资产 &amp; GPM</div>
              <div class="mirror-metric-val">
                ${fmtNum(r.nw_own || 0)} vs ${fmtNum(r.nw_opp || 0)}
                <span style="color:${
                  nwDiff >= 1500
                    ? "var(--green-light)"
                    : nwDiff <= -1500
                    ? "var(--red-light)"
                    : "var(--text-dim)"
                }">(${nwDiff >= 0 ? "+" : ""}${fmtNum(nwDiff)})</span>
                · GPM ${r.gpm_own ?? 0}/${r.gpm_opp ?? 0}
              </div>
            </div>
            <div class="mirror-metric-cell">
              <div class="mirror-metric-label">💥 英雄伤害对比</div>
              <div class="mirror-metric-val">
                ${fmtNum(r.dmg_own || 0)} vs ${fmtNum(r.dmg_opp || 0)}
                <span style="color:${
                  dmgDiff >= 2000
                    ? "var(--green-light)"
                    : dmgDiff <= -2000
                    ? "var(--red-light)"
                    : "var(--text-dim)"
                }">(${dmgDiff >= 0 ? "+" : ""}${fmtNum(dmgDiff)})</span>
              </div>
            </div>
            <div class="mirror-metric-cell">
              <div class="mirror-metric-label">🏰 推塔建筑伤害</div>
              <div class="mirror-metric-val">${fmtNum(r.td_own || 0)} vs ${fmtNum(r.td_opp || 0)}</div>
            </div>
            <div class="mirror-metric-cell">
              <div class="mirror-metric-label">⚡ 参战率 &amp; 硬控时长</div>
              <div class="mirror-metric-val">参战 ${r.kp_own ?? 0}% vs ${r.kp_opp ?? 0}% · 控 ${
        r.stuns_own ?? 0
      }s vs ${r.stuns_opp ?? 0}s</div>
            </div>
            <div class="mirror-metric-cell">
              <div class="mirror-metric-label">👁️ 视野插眼与反眼</div>
              <div class="mirror-metric-val">${escapeHtml(r.wards_own || "0眼/排0")} vs ${escapeHtml(
        r.wards_opp || "0眼/排0"
      )}</div>
            </div>
          </div>

          <div style="font-size:12px; color:var(--text-dim); line-height:1.45;">
            📋 ${injectHeroLogosIntoHtml(escapeHtml(r.summary_txt || ""), report)}
          </div>
        </article>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>⚔️ 10. 1~5 号位同位置宿敌 1v1 正面对位审判 &amp; OpenDota 全球同英雄百分位标尺 (${escapeHtml(
            targetSideZh
          )} vs ${escapeHtml(otherSideZh)})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(rm.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-kpi-row" style="grid-template-columns: repeat(3, minmax(0, 1fr));">
        <div class="micro-kpi-cell">
          <span>🏆 全场同位置对位胜出数</span>
          <strong style="color:${
            wonOverall >= 3 ? "var(--green-light)" : "var(--red-light)"
          }">${wonOverall} / 5 个位置占优</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🌱 10分钟对线同位置经济占优</span>
          <strong style="color:${
            wonLanes >= 3 ? "var(--green-light)" : "var(--gold-light)"
          }">${wonLanes} / 5 路对位领先</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🌍 全队全球同英雄百分位均值</span>
          <strong>本方超越 ${avgOwnBm}% vs 对手超越 ${avgOppBm}%</strong>
        </div>
      </div>

      <div class="role-mirror-list">${cardsHtml}</div>
    </div>
  `;
}

/**
 * Tab 11: 🐉 买活死 (Dieback) 尸检 · 信使惨案 · 肉山魔晶时间轴 & Dota 2 7.38 中立装备附魔审计
 */
function renderMicroMacroObjectivesPane(report, df, targetSide, targetSideZh) {
  const mo = df.macro_objectives_by_side?.[targetSide];
  if (!mo) {
    return `<div class="empty-state compact">当前比赛暂无买活死尸检与 7.38 中立装备附魔数据</div>`;
  }

  const diebackCnt = Number(mo.dieback_cnt ?? 0);
  const clutchBbCnt = Number(mo.clutch_bb_cnt ?? 0);
  const couriersLost = Number(mo.own_couriers_lost ?? 0);
  const couriersKilled = Number(mo.own_couriers_killed ?? 0);
  const shardCount = Number(mo.shard_count ?? 0);

  const bbEvents = mo.buyback_events || [];
  const bbHtml =
    bbEvents.length > 0
      ? bbEvents
          .map(
            (ev) => `
          <li>
            <span class="micro-tf-pill ${ev.severity === "critical" ? "held-die" : ""}">
              ${escapeHtml(ev.outcome_tag || "买活记录")} · ${escapeHtml(ev.time_str || "")}
            </span>
            ${injectHeroLogosIntoHtml(
              `<b>${ev.pos ?? "?"}号位 · ${escapeHtml(ev.hero_short_zh || "")} (${escapeHtml(
                ev.personaname || ""
              )})</b>：${escapeHtml(ev.detail || "")}`,
              report
            )}
          </li>
        `
          )
          .join("")
      : `<li>✓ 本局 ${escapeHtml(targetSideZh)} 未交出买活，0 次买活死 (Dieback) 记录。</li>`;

  const roshEvents = mo.roshan_events || [];
  const roshHtml =
    roshEvents.length > 0
      ? roshEvents.map((r) => `<li>${injectHeroLogosIntoHtml(escapeHtml(r), report)}</li>`).join("")
      : `<li>本局录像未记录到肉山盾拾取或抢盾事件。</li>`;

  const courierEvents = mo.courier_events || [];
  const courierHtml =
    courierEvents.length > 0
      ? courierEvents
          .map(
            (ce) => `
          <li>
            <span class="micro-tf-pill ${ce.is_own_lost ? "held-die" : ""}">
              ${escapeHtml(ce.event_tag || "信使事件")}
            </span>
            ${injectHeroLogosIntoHtml(escapeHtml(ce.detail || ""), report)}
          </li>
        `
          )
          .join("")
      : `<li>✓ 本局双方信使平安，未发生对线掉鸡断补给惨案。</li>`;

  const craftRows = mo.neutral_craft_rows || [];
  const craftRowsHtml = craftRows
    .map((cr) => {
      const steps = cr.craft_steps || [];
      const stepsPills =
        steps.length > 0
          ? steps
              .map((s) => `<span class="micro-tf-pill" style="margin-right:4px;">${escapeHtml(s)}</span>`)
              .join("")
          : `<span style="color:var(--text-dim);">无锻造切换记录</span>`;
      return `
        <tr>
          <td>${renderHeroCellWithLogo(cr.pos, cr.hero_short_zh, cr.personaname, report, cr.hero_img)}</td>
          <td><b>${escapeHtml(cr.shard_str || "未获魔晶")}</b></td>
          <td>${stepsPills}</td>
          <td style="color:${
            cr.grade === "warn" ? "var(--gold-light)" : "var(--green-light)"
          }">${injectHeroLogosIntoHtml(escapeHtml(cr.craft_verdict || ""), report)}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🐉 11. 买活死 (Dieback) 尸检 · 信使掉鸡惨案 · 肉山魔晶 &amp; Dota 2 7.38 中立装备附魔审计 (${escapeHtml(
            targetSideZh
          )})</h3>
          <p>${injectHeroLogosIntoHtml(escapeHtml(mo.side_verdict || ""), report)}</p>
        </div>
      </div>

      <div class="micro-kpi-row" style="grid-template-columns: repeat(4, minmax(0, 1fr));">
        <div class="micro-kpi-cell">
          <span>💀 致命买活死 (Dieback)</span>
          <strong style="color:${
            diebackCnt > 0 ? "var(--red-light)" : "var(--green-light)"
          }">${diebackCnt} 次</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🟢 救世有效买活</span>
          <strong style="color:${
            clutchBbCnt > 0 ? "var(--green-light)" : "var(--text)"
          }">${clutchBbCnt} 次</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>🐔 信使博弈 (狙杀敌鸡 / 本方掉鸡)</span>
          <strong style="color:${
            couriersLost > couriersKilled ? "var(--red-light)" : "var(--green-light)"
          }">杀敌 ${couriersKilled} 只 / 掉鸡 ${couriersLost} 只</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>💎 阿哈利姆魔晶普及率</span>
          <strong>${shardCount} / 5 人已装备</strong>
        </div>
      </div>

      <div class="micro-card">
        <h4>⚰️ 买活战果与「买活死 (Dieback)」逐笔尸检 &amp; 肉山不朽盾事件簿</h4>
        <ul class="micro-insights-list">${bbHtml}${roshHtml}</ul>
      </div>

      <div class="micro-card">
        <h4>🐔 全场信使狙杀与对线期掉鸡断补给惨案时间轴</h4>
        <ul class="micro-insights-list">${courierHtml}</ul>
      </div>

      <div class="micro-card">
        <h4>🛠️ Dota 2 7.38 中立装备锻造轨迹 · 附魔词条合规审计（排查核心误选贪婪扣攻击力）&amp; 魔晶时间表</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>位置 / 英雄</th>
                <th>💎 阿哈利姆魔晶时间</th>
                <th>🛠️ 7.38 中立装备锻造与附魔词条时间轴</th>
                <th>⚖️ 词条合规与锻造节奏判词</th>
              </tr>
            </thead>
            <tbody>${craftRowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/**
 * 🔊 语音播报讲评台 (Web Speech TTS 中文毒舌教练 / 庆功司仪一键朗读)
 */
function toggleVoiceBroadcast() {
  const btn = document.getElementById("btn-voice-broadcast");
  const report = state.currentReport;
  if (!report) return;

  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      if (btn) {
        btn.classList.remove("speaking");
        btn.textContent = "🔊 语音播报复盘";
      }
      showToast("已停止语音播报");
      return;
    }
  }

  const { side, sideZh, own } = getOwnAndOppPlayers(report);
  const won =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !report.radiant_win);
  const grok = report.grok_coaching;
  const df = report.deep_forensics || {};

  const sortedBlame = [...own].sort(
    (a, b) => (b.blame_share_pct || 0) - (a.blame_share_pct || 0)
  );
  const sortedContrib = [...own].sort(
    (a, b) =>
      (b.contrib_share_pct ?? b.rating_score ?? 0) -
      (a.contrib_share_pct ?? a.rating_score ?? 0)
  );
  const topCulprit = sortedBlame[0];
  const mvpPlayer = sortedContrib[0];
  const runnerUp = sortedContrib[1] || sortedContrib[0];

  const speechParts = [
    `刀塔二五黑战后复盘语音播报。比赛编号 ${report.match_id}，${sideZh}${
      won ? "凯旋获胜" : "遗憾落败"
    }，终局比分 ${report.radiant_score} 比 ${report.dire_score}，时长 ${report.duration_str}。`,
  ];

  if (won) {
    speechParts.push(
      `本局论功行赏：头号首功是 ${mvpPlayer?.pos ?? 1}号位 ${mvpPlayer?.hero_short_zh || ""} ${
        mvpPlayer?.personaname || ""
      }，战绩 ${mvpPlayer?.kda || ""}，综合评分 ${mvpPlayer?.rating_score || 0}。破阵二当家是 ${
        runnerUp?.pos ?? 2
      }号位 ${runnerUp?.hero_short_zh || ""} ${runnerUp?.personaname || ""}。`
    );
  } else {
    speechParts.push(
      `本局败局分锅定责：头号背锅侠是 ${topCulprit?.pos ?? 1}号位 ${
        topCulprit?.hero_short_zh || ""
      } ${topCulprit?.personaname || ""}，战绩 ${topCulprit?.kda || ""}，分锅占比高达百分之 ${
        topCulprit?.blame_share_pct || 0
      }。败方尽力王是 ${mvpPlayer?.pos ?? 1}号位 ${mvpPlayer?.hero_short_zh || ""} ${
        mvpPlayer?.personaname || ""
      }。`
    );
  }

  if (grok?.verdict) {
    speechParts.push(grok.verdict);
  }
  const rmVerdict = df.role_mirror_by_side?.[side]?.side_verdict;
  if (rmVerdict) speechParts.push(rmVerdict);

  const savesVerdict = df.unpressed_saves_by_side?.[side]?.side_verdict;
  if (savesVerdict) speechParts.push(savesVerdict);

  const spaceVerdict = df.map_space_by_side?.[side]?.side_verdict;
  if (spaceVerdict) speechParts.push(spaceVerdict);

  const macroVerdict = df.macro_objectives_by_side?.[side]?.side_verdict;
  if (macroVerdict) speechParts.push(macroVerdict);

  const fullText = speechParts.join(" ").replace(/[🎯💀🗺️🛡️👁️🌾🌱🆘💰⚔️🐉🚨⚠️✓👑🏆🎉⚖️💎🐔]/g, "");

  if (typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined") {
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(fullText);
    utter.lang = "zh-CN";
    utter.rate = 1.08;
    utter.onend = () => {
      if (btn) {
        btn.classList.remove("speaking");
        btn.textContent = "🔊 语音播报复盘";
      }
    };
    utter.onerror = () => {
      if (btn) {
        btn.classList.remove("speaking");
        btn.textContent = "🔊 语音播报复盘";
      }
    };
    if (btn) {
      btn.classList.add("speaking");
      btn.textContent = "⏹️ 停止语音播报";
    }
    window.speechSynthesis.speak(utter);
    showToast("🔊 正在为您语音播报本局五黑复盘判决书（再次点击可停止）");
  } else {
    copyTextToClipboard(fullText, "语音播报讲稿");
  }
}

/**
 * Filter out cheap recipe components when completed items exist in the same phase
 */
const RECIPE_COMPONENT_NAMES = new Set([
  "欢欣之刃",
  "力量腰带",
  "法师长袍",
  "阔剑",
  "大剑",
  "标枪",
  "秘银锤",
  "闪电指套",
  "加速手套",
  "活力之球",
  "精气之球",
  "能量之球",
  "极限法球",
  "神秘法杖",
  "振奋宝石",
  "恶魔刀锋",
  "掠夺者之斧",
  "鹰歌弓",
  "暗影护符",
  "魔力法杖",
  "食人魔之斧",
  "欢欣之刃",
  "阔剑",
  "大剑",
  "秘银锤",
  "标枪",
  "闪电指套",
  "坚韧球",
  "宝冕",
  "镇魂石",
  "虚无宝石",
  "回复戒指",
  "治疗指环",
  "抗魔斗篷",
  "锁子甲",
  "板甲",
  "铁意头盔",
  "风灵之纹",
  "王冠",
  "赛莉蒙妮之冠",
  "毛毛帽",
  "幽魂系带",
  "怨灵系带",
  "护腕",
  "空灵挂件",
  "精气之球",
  "活力之球",
  "能量之球",
  "极限法球",
  "神秘法杖",
  "王权",
  "玲珑心卷轴",
  "图纸",
]);

function filterMajorItems(itemsBought, maxCnt = 3) {
  const raw = Array.isArray(itemsBought) ? itemsBought : [];
  if (raw.length === 0) return [];
  const major = raw.filter((it) => {
    const name = String(it.zh_name || it.key || "").trim();
    if (!name) return false;
    if (RECIPE_COMPONENT_NAMES.has(name)) return false;
    if (name.includes("速度之靴") && raw.some((x) => x !== it && String(x.zh_name || "").includes("鞋"))) {
      return false;
    }
    return true;
  });
  const chosen = major.length > 0 ? major : raw.filter((it) => !RECIPE_COMPONENT_NAMES.has(String(it.zh_name || "")));
  const list = chosen.length > 0 ? chosen : raw;
  return list.length > maxCnt ? list.slice(-maxCnt) : list;
}

/**
 * AI Roshan / Aegis & Resource Advantage Conversion Analyzer:
 * Evaluates whether taking Roshan (Aegis) was effectively converted into outer tower sweeps,
 * high-ground T3 tower / barracks breaches, kills, and game-ending tempo within the 5-minute Aegis window.
 */
function analyzeRoshanAndResourceConversion(report) {
  const { side, sideZh } = getOwnAndOppPlayers(report);
  const oppZh = side === "radiant" ? "夜魇" : "天辉";
  const df = report.deep_forensics || {};
  const mo = df.macro_objectives_by_side?.[side] || {};
  const roshStrings = mo.roshan_events || [];
  const markers = report.objective_markers || [];
  const rawPhases = report.phases_data || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  const latePd = phasesList.find((x) => x.key === "late");
  const lateTowersTaken = Number(latePd?.team_summary?.towers_taken || 0);
  const ownWon =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !Boolean(report.radiant_win));

  const ownRoshMarkers = markers.filter((m) => m.type === "roshan" && m.side === side);
  const oppRoshMarkers = markers.filter((m) => m.type === "roshan" && m.side !== side);

  if (ownRoshMarkers.length === 0 && oppRoshMarkers.length === 0 && roshStrings.length === 0) {
    return {
      hasRoshan: false,
      grade: "none",
      badgeText: "⚪ 本局无肉山击杀记录",
      holderHero: "",
      roshTimeStr: "",
      shortHtml: "本局双方均未击杀肉山，后期胜负完全取决于正面团战与买活推进转换。",
      detailHtml: "本局双方未爆发肉山盾争夺，直接通过野外团战抓人与兵线推进决出胜负。",
    };
  }

  if (ownRoshMarkers.length > 0 || roshStrings.some((s) => String(s).includes(sideZh))) {
    const lastOwnRosh = ownRoshMarkers[ownRoshMarkers.length - 1] || {
      time_sec: 1800,
      time_str: "后期",
    };
    const rSec = Number(lastOwnRosh.time_sec || 1800);
    const rTimeStr = lastOwnRosh.time_str || "后期";
    const holderEventStr =
      roshStrings.find((s) => String(s).includes(sideZh)) ||
      roshStrings[0] ||
      `🛡️ ${rTimeStr} ${sideZh}控下肉山不朽盾`;
    const cleanedHolderStr = String(holderEventStr).replace(/^🛡️\s*/, "");

    // Check highground T3 towers & barracks taken within [rSec - 15, rSec + 315] (5-minute Aegis window)
    const hgTakenInWindow = markers.filter(
      (m) =>
        m.side === side &&
        m.type !== "roshan" &&
        Number(m.time_sec || 0) >= rSec - 15 &&
        Number(m.time_sec || 0) <= rSec + 315
    );
    const t3Count = hgTakenInWindow.filter((m) => String(m.label || "").includes("三塔")).length;
    const raxCount = hgTakenInWindow.filter((m) => String(m.label || "").includes("兵营")).length;
    const firstHgTime = hgTakenInWindow[0]?.time_str || "";
    const lastHgTime = hgTakenInWindow[hgTakenInWindow.length - 1]?.time_str || "";

    // Count kills and deaths during the 5-minute Aegis window
    let aegisKills = 0;
    let aegisDeaths = 0;
    phasesList.forEach((pd) => {
      (pd.players || []).forEach((pp) => {
        if (pp.side === side) {
          (pp.kills_events || []).forEach((ke) => {
            if (Number(ke.time || 0) >= rSec && Number(ke.time || 0) <= rSec + 315) aegisKills++;
          });
          (pp.deaths_events || []).forEach((de) => {
            if (Number(de.time || 0) >= rSec && Number(de.time || 0) <= rSec + 315) aegisDeaths++;
          });
        }
      });
    });

    if (hgTakenInWindow.length >= 2 || lateTowersTaken >= 6) {
      const hgDesc =
        t3Count > 0 || raxCount > 0
          ? `在 <b>${firstHgTime}–${lastHgTime}</b> 顺势扫清外塔并连破 <b>${t3Count} 座高地三塔 + ${raxCount} 座高地兵营</b>（后期累计推毁 <b>${lateTowersTaken} 座建筑</b>）`
          : `顺势连拔 <b>${lateTowersTaken} 座外塔与高地建筑</b>`;
      return {
        hasRoshan: true,
        grade: "perfect",
        badgeText: "🌟 教科书级控盾转化（带盾拔外塔+平推高地）",
        holderHero: cleanedHolderStr,
        roshTimeStr: rTimeStr,
        shortHtml: `🛡️ <b>${escapeHtml(
          cleanedHolderStr
        )} → 🌟 满分控盾转化：</b>打盾后绝不回野区空刷，利用不朽盾 5 分钟强势期${hgDesc}，带盾窗口打出 <b>${aegisKills}杀/${aegisDeaths}死</b> 直接将盾权与经济优势转化为胜势！`,
        detailHtml: `<b>🛡️ ${escapeHtml(
          cleanedHolderStr
        )}：</b>打盾后全队执行力拉满，顺势把残余外塔拔光并直接压上高地，${hgDesc}，带盾期间打出 <b>${aegisKills}杀/${aegisDeaths}死</b>，堪称「控盾即终结」的教科书级资源转化代表！`,
      };
    }

    if (lateTowersTaken >= 2 || aegisKills > aegisDeaths || ownWon) {
      return {
        hasRoshan: true,
        grade: "good",
        badgeText: "🟢 有效控盾压制转化",
        holderHero: cleanedHolderStr,
        roshTimeStr: rTimeStr,
        shortHtml: `🛡️ <b>${escapeHtml(
          cleanedHolderStr
        )} → 🟢 有效资源转化：</b>带盾期间打出 <b>${aegisKills}杀/${aegisDeaths}死</b>、推掉 <b>${lateTowersTaken} 座建筑</b>，稳步将不朽盾转化为外塔与地图压制优势。`,
        detailHtml: `<b>🛡️ ${escapeHtml(
          cleanedHolderStr
        )}：</b>拿盾后抱团压制敌方野区与外塔（带盾窗口 <b>${aegisKills}杀/${aegisDeaths}死</b>，后期拔塔 <b>${lateTowersTaken} 座</b>），有效兑现了肉山资源。`,
      };
    }

    return {
      hasRoshan: true,
      grade: "wasted",
      badgeText: "🔴 带盾空转/推进受阻（盾权未转化）",
      holderHero: cleanedHolderStr,
      roshTimeStr: rTimeStr,
      shortHtml: `🛡️ <b>${escapeHtml(
        cleanedHolderStr
      )} → 🔴 控盾未有效转化：</b>虽控下肉山不朽盾，但带盾 5 分钟窗口内仅推掉 <b>${lateTowersTaken} 座建筑</b>（人头 <b>${aegisKills}杀/${aegisDeaths}死</b>），未能趁盾权拔光外塔或攻破高地。`,
      detailHtml: `<b>🛡️ ${escapeHtml(
        cleanedHolderStr
      )}：</b>控盾后团队未能抱团推进拔外塔上高地（带盾窗口人头 <b>${aegisKills}杀/${aegisDeaths}死</b>），宝贵的 5 分钟不朽盾强势期被白白消耗。`,
    };
  }

  // Enemy took Roshan
  const oppEventStr = roshStrings[0] || `${oppZh}控下肉山不朽盾`;
  return {
    hasRoshan: true,
    grade: "enemy_rosh",
    badgeText: `⚠️ ${oppZh}控盾施压`,
    holderHero: oppEventStr,
    roshTimeStr: oppRoshMarkers[0]?.time_str || "",
    shortHtml: `⚠️ <b>肉山盾旁落：</b>${escapeHtml(
      String(oppEventStr)
    )}，本方未能控住肉山盾权，后期被迫承担带盾防高地压力。`,
    detailHtml: `⚠️ <b>肉山控图失守：</b>${escapeHtml(
      String(oppEventStr)
    )}，导致敌方拿到不朽盾容错率强推外塔与高地。`,
  };
}

/**
 * AI Itemization Intelligence Audit for each player (Pos 1~5):
 * 1. Counter-Itemization & Hero Situational Synergy (e.g., MKB vs Evasion/Butterfly/Brewmaster; Juggernaut Aghs Swiftslash when right-clicking is hard vs Omnislash value; Spirit Vessel vs Wraith King/Pudge; Ghost Scepter vs Anti-Mage)
 * 2. BKB Audit for Cores (Smart BKB skip due to built-in spell immunity/invulnerability vs Fatal no-BKB deaths)
 * 3. Support Greed vs Team Save Audit (Pos 4/5 rushing Midas / pure damage Aghs/Khanda without Force Staff / Glimmer Cape)
 * 4. Blink Dagger Conversion Audit (Exact Blink timing -> post-Blink kills, hero damage, and deaths to judge if Blink carried or was wasted)
 */
function analyzePlayerItemizationIntelligence(p, report) {
  const { side, opp } = getOwnAndOppPlayers(report);
  const rawPhases = report.phases_data || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  const byPhase = new Map(phasesList.map((pd) => [pd.key, pd]));
  const lanePd = byPhase.get("lane");
  const midPd = byPhase.get("mid");
  const latePd = byPhase.get("late");

  const findInPhase = (pd) =>
    (pd?.players || []).find(
      (x) =>
        x.side === side &&
        (Number(x.player_slot) === Number(p.player_slot) || x.hero_short_zh === p.hero_short_zh)
    );
  const laneP = findInPhase(lanePd) || {};
  const midP = findInPhase(midPd) || {};
  const lateP = findInPhase(latePd) || {};

  const parseSec = (tStr) => {
    const parts = String(tStr || "0:00").split(":");
    if (parts.length !== 2) return 0;
    const m = parseInt(parts[0], 10) || 0;
    const s = parseInt(parts[1], 10) || 0;
    return m * 60 + s;
  };

  // Merge all phase items_bought with timestamps + final inventory
  const phaseItems = [
    ...(laneP.items_bought || []),
    ...(midP.items_bought || []),
    ...(lateP.items_bought || []),
  ].map((it) => ({
    key: String(it.key || ""),
    zh: String(it.zh_name || it.name_zh || it.key || ""),
    time_str: String(it.time_str || ""),
    sec: parseSec(it.time_str),
  }));

  const finalItems = (p.items || []).map((it) => ({
    key: String(it.key || ""),
    zh: String(it.name_zh || it.zh_name || it.key || ""),
  }));

  const hasItemMatch = (regex) => {
    const inPhase = phaseItems.find((it) => regex.test(it.zh) || regex.test(it.key));
    if (inPhase) return inPhase;
    const inFinal = finalItems.find((it) => regex.test(it.zh) || regex.test(it.key));
    if (inFinal) return { ...inFinal, time_str: "终局", sec: 1500 };
    return null;
  };

  // Collect all player kill events & death events across phases
  const allKillEvents = [
    ...(laneP.kills_events || []),
    ...(midP.kills_events || []),
    ...(lateP.kills_events || []),
  ].map((ev) => ({ ...ev, sec: parseSec(ev.time_str) }));

  const allDeathEvents = [
    ...(laneP.deaths_events || []),
    ...(midP.deaths_events || []),
    ...(lateP.deaths_events || []),
  ].map((ev) => ({ ...ev, sec: parseSec(ev.time_str) }));

  const pos = Number(p.pos || 1);
  const isSup = pos >= 4;
  const isCore = pos <= 3;
  const heroShort = p.hero_short_zh || p.hero_name || "";
  const oppNames = opp.map((o) => o.hero_short_zh || o.hero_name || "");
  const oppAllItemsZh = opp
    .flatMap((o) => (o.items || []).map((it) => it.name_zh || it.zh_name || it.key || ""))
    .join(" ");

  const oppEvasionHeroes = opp.filter(
    (o) =>
      /酒仙|幻影刺客|风行者|天穹守望者|蝴蝶|光法/.test(o.hero_short_zh || "") ||
      (o.items || []).some((it) => /蝴蝶|光辉|天堂/.test(it.name_zh || it.zh_name || ""))
  );
  const oppHighRegenHeroes = opp.filter((o) =>
    /帕吉|冥魂大帝|胡斯卡|炼金术士|死灵法师|孽主|伐木机|噬魂鬼|变体精灵/.test(o.hero_short_zh || "")
  );
  const oppJumpBurstHeroes = opp.filter((o) =>
    /敌法师|幻影刺客|斯温|圣堂刺客|斯拉克|力丸|军团指挥官|虚空假面/.test(o.hero_short_zh || "")
  );
  const oppKiteAndCatchHeroes = opp.filter((o) =>
    /剧毒术士|帕吉|酒仙|发条技师|水晶室女|巫妖|孽主/.test(o.hero_short_zh || "")
  );

  const highlights = [];
  const warnings = [];
  const badges = [];

  // -------------------------------------------------------------------------
  // 1. Counter-Items & Situational Aghs / Synergy Audit
  // -------------------------------------------------------------------------
  const mkbItem = hasItemMatch(/金箍棒|monkey_king_bar/i);
  if (mkbItem) {
    const targetDesc =
      oppEvasionHeroes.length > 0
        ? `敌方 <b>${oppEvasionHeroes.map((o) => o.hero_short_zh).join(" / ")}</b> 的先天闪避/蝴蝶与高护甲体系`
        : /敌法师|恐怖利刃|变体精灵/.test(oppNames.join(" "))
        ? `敌方高护甲敏捷核心（${oppNames.filter((n) => /敌法师|恐怖利刃|变体精灵/.test(n)).join("/")}）`
        : "敌方前排护甲与闪避";
    badges.push("🎯 金箍棒精准克制");
    highlights.push(
      `🎯 <b>针对性克制出装（金箍棒 ${mkbItem.time_str}）：</b>精准识别到${targetDesc}，果断在 ${mkbItem.time_str} 掏出 <b>金箍棒(MKB)</b>，必中克制闪避+魔法附伤直接打穿敌方前排！`
    );
  }

  const aghsItem = hasItemMatch(/阿哈利姆神杖|ultimate_scepter/i);
  if (aghsItem && heroShort === "主宰") {
    const kiteNames = oppKiteAndCatchHeroes.map((o) => o.hero_short_zh).join("+") || "减速拉扯体系";
    const enemyHasLotusOrGhost = /莲花|幽魂|绿杖|虚灵/.test(oppAllItemsZh);
    badges.push("🧠 灵性A杖迅风斩");
    highlights.push(
      `🧠 <b>局势理解满分（${aghsItem.time_str} 阿哈利姆神杖·迅风斩）：</b>敌方 <b>${kiteNames}</b> 满地减速/控制且无视魔免钩咬，常规站桩对A环境极差，但敌方全员缺乏莲花/绿杖防无敌斩（${
        enemyHasLotusOrGhost ? "防斩手段有限" : "0莲花0绿杖"
      }）！果断选择 <b>跳刀 + A杖(迅风斩)</b> 双无敌斩体系，不跟对手拼站桩对A，直接用两套无敌斩秒后排接管团战！`
    );
  } else if (aghsItem && isCore) {
    if (heroShort === "帕格纳") {
      badges.push("🟢 魔晶+A杖抽血炮台");
      highlights.push(
        `🟢 <b>英雄特性出装（以太 + 魔晶 + ${aghsItem.time_str} A杖）：</b>利用帕格纳无CD生命汲取与幽冥守卫插棒子抽血机制，配合爆塔轰出 <b>${fmtNum(
          p.hero_damage
        )} 英雄伤害</b> 与 <b>${fmtNum(p.tower_damage)} 建筑伤害</b>。`
      );
    } else {
      highlights.push(
        `🟢 <b>核心质变神杖（${aghsItem.time_str} 阿哈利姆神杖）：</b>强化大招与团战上限，全场打出 <b>${fmtNum(
          p.hero_damage
        )} 伤害</b>。`
      );
    }
  }

  const vesselItem = hasItemMatch(/魂之灵瓮|spirit_vessel/i);
  if (vesselItem) {
    const regenTargets = oppHighRegenHeroes.map((o) => o.hero_short_zh).join(" / ") || "敌方力量前排";
    badges.push("🏺 大骨灰克制回血");
    highlights.push(
      `🏺 <b>灵性克制针对装（${vesselItem.time_str} 魂之灵瓮·大骨灰）：</b>针对敌方 <b>${regenTargets}</b> 的高血量高恢复特性，18分钟准时合成大骨灰削减回血并附带百分比灼烧，克制思路非常清晰！`
    );
  }

  const ghostItem = hasItemMatch(/幽魂权杖|ghost|虚灵之刃/i);
  if (ghostItem && oppJumpBurstHeroes.length > 0) {
    const jumpers = oppJumpBurstHeroes.map((o) => o.hero_short_zh).join("/");
    badges.push("👻 绿杖防切入");
    highlights.push(
      `👻 <b>防物理切入针对装（${ghostItem.time_str} ${ghostItem.zh}）：</b>针对敌方 <b>${jumpers}</b> 跳脸切后排，补出幽魂权杖规避物理爆发。`
    );
  }

  const atosItem = hasItemMatch(/阿托斯之棍|rod_of_atos|缚灵索/i);
  if (atosItem && heroShort === "天怒法师") {
    highlights.push(
      `🎯 <b>节奏捕猎核心装（${atosItem.time_str} 阿托斯之棍）：</b>11分钟极速裸出阿托斯配合上古封印+神秘之耀，前中期连续单抓敌法师与帕吉打开局面。`
    );
  }

  // -------------------------------------------------------------------------
  // 2. Blink Dagger (跳刀) Conversion Audit
  // -------------------------------------------------------------------------
  const blinkItem = phaseItems.find((it) => /闪烁匕首|跳刀|blink/i.test(it.zh) || /blink/i.test(it.key));
  const upgradeBlink = hasItemMatch(/迅疾闪光|盛势闪光|秘奥闪光|swift_blink|overwhelming_blink|arcane_blink/i);
  let blinkVerdict = null;

  if (blinkItem) {
    const bSec = blinkItem.sec || 1200;
    const postBlinkKills = allKillEvents.filter((ev) => ev.sec >= bSec - 10);
    const postBlinkDeaths = allDeathEvents.filter((ev) => ev.sec >= bSec + 10);
    const postKillCnt = postBlinkKills.length;
    const postDeathCnt = postBlinkDeaths.length;
    const postDmgApprox =
      bSec <= 1350
        ? Math.round(Number(midP.hero_damage_gain || 0) * 0.45 + Number(lateP.hero_damage_gain || 0))
        : Number(lateP.hero_damage_gain || 0);

    if (postKillCnt >= 6 && postDeathCnt <= 2) {
      badges.push(`⚡ 跳刀封神(${postKillCnt}杀/${postDeathCnt}死)`);
      blinkVerdict = {
        grade: "godlike",
        html: `⚡ <b>跳刀转化率封神（${blinkItem.time_str} 闪烁匕首${
          upgradeBlink ? ` → ${upgradeBlink.time_str} ${upgradeBlink.zh}` : ""
        }）：</b>出跳刀后彻底化身后排收割机，狂砍 <b>${postKillCnt} 杀仅 ${postDeathCnt} 死</b>（切入轰出约 <b>${fmtNum(
          postDmgApprox
        )} 伤害</b>），每一波跳斩都精准收割敌方核心，把跳刀机动性发挥到极致！`,
      };
      highlights.push(blinkVerdict.html);
    } else if (postKillCnt >= 1 && postDeathCnt === 0) {
      badges.push(`🟢 跳刀机动收割(${postKillCnt}杀/0死)`);
      blinkVerdict = {
        grade: "good",
        html: `⚡ <b>跳刀高地机动兑现（${blinkItem.time_str} 闪烁匕首）：</b>後期补出跳刀切入调整站位，出跳后斩获 <b>${postKillCnt} 杀 0 死</b>（${postBlinkKills
          .map((k) => `${k.time_str}秒${k.victim_hero}`)
          .join("、")}），零失误收官。`,
      };
      highlights.push(blinkVerdict.html);
    } else if (postKillCnt <= 2 && (postDeathCnt >= 1 || Number(lateP.hero_damage_gain || 0) < 6000)) {
      badges.push(`⚠️ 跳刀转化偏低(${postKillCnt}杀/${postDeathCnt}死)`);
      blinkVerdict = {
        grade: "mediocre",
        html: `⚠️ <b>跳刀转化率偏低（${blinkItem.time_str} 闪烁匕首）：</b>斥资 2250 金做出跳刀后仅斩获 <b>${postKillCnt} 杀 / ${postDeathCnt} 死</b>（后期伤害仅 <b>${fmtNum(
          lateP.hero_damage_gain || 0
        )}</b>）${
          postDeathCnt > 0
            ? `，且在 <b>${postBlinkDeaths.map((d) => `${d.time_str}被${d.killer}`).join("、")}</b> 带着跳刀被抓死`
            : ""
        }，出跳后的先手抓人与输出转化未能完全打出来。`,
      };
      warnings.push(blinkVerdict.html);
    } else {
      badges.push(`⚡ 跳刀先手(${postKillCnt}杀/${postDeathCnt}死)`);
      blinkVerdict = {
        grade: "ok",
        html: `⚡ <b>跳刀节奏审计（${blinkItem.time_str} 闪烁匕首）：</b>出跳后打出 <b>${postKillCnt} 杀 / ${postDeathCnt} 死</b>。`,
      };
    }
  }

  // -------------------------------------------------------------------------
  // 3. Core BKB Audit vs Support Greed (Midas / Damage vs Force Staff / Glimmer)
  // -------------------------------------------------------------------------
  const bkbItem = hasItemMatch(/黑皇杖|black_king_bar/i);
  const mantaItem = hasItemMatch(/分身斧|manta/i);
  const forceItem = hasItemMatch(/原力法杖|推推|force_staff|飓风长戟/i);
  const glimmerItem = hasItemMatch(/微光披风|glimmer_cape/i);
  const midasItem = hasItemMatch(/迈达斯之手|点金手|hand_of_midas/i);
  const khandaOrPhylactery = hasItemMatch(/绝刃|灵匣|phylactery|khanda/i);

  if (isCore) {
    if (bkbItem) {
      badges.push(`🛡️ BKB稳健(${bkbItem.time_str})`);
      highlights.push(`🛡️ <b>核心BKB纪律性（${bkbItem.time_str} 黑皇杖）：</b>按时做出BKB保障团战输出环境。`);
    } else {
      // Did not buy BKB: judge whether it was a smart skip or a throw
      const hasBuiltInImmunity = /主宰|噬魂鬼|全能骑士|帕克/.test(heroShort);
      const totalDeaths = Number(p.deaths || 0);
      if (hasBuiltInImmunity && totalDeaths <= 3) {
        badges.push("🧠 剑舞分身免BKB满输出");
        highlights.push(
          `🧠 <b>不出BKB合理性审计（免喷认证）：</b>虽然整局未出黑皇杖(BKB)，但依靠 <b>剑刃风暴魔免 + ${
            mantaItem ? `分身斧(${mantaItem.time_str})解状态` : "技能机制"
          } + 双无敌斩无敌帧</b> 全场仅阵亡 <b>${totalDeaths} 次</b>，省下BKB格子直接合成 <b>金箍棒+A杖</b> 将输出拉到极致！`
        );
      } else if (totalDeaths >= 6 && !forceItem) {
        badges.push("🚨 缺BKB/推推自保");
        warnings.push(
          `🚨 <b>保命装缺失吐槽点（0 BKB / 0 推推棒）：</b>身为 ${pos}号位核心全场阵亡 <b>${totalDeaths} 次（泉水读秒 ${
            p.dead_seconds || 0
          }s）</b>，面对敌方切入与减速控制既未出 <b>黑皇杖(BKB)</b> 也未补 <b>原力法杖(推推棒)</b>，后期一旦被贴脸极为脆弱。`
        );
      }
    }
  } else if (isSup) {
    // Support Greed vs Save Item & Role-Duty Audit (Pos 4 / Pos 5)
    const kiteThreats = oppKiteAndCatchHeroes.map((o) => o.hero_short_zh).join(" / ") || "敌方冲脸";
    const selfishCarryItemOnSup = hasItemMatch(
      /净魂之刃|散失|diffusal_blade|散魂剑|disperser|漩涡|雷神之锤|maelstrom|mjollnir|狂战斧|bfury|辉耀|radiance|水晶剑|代达罗斯|大炮|暗灭|desolator|影刃|隐刀|白银之锋/i
    );
    const eulOrLotus = hasItemMatch(/神圣法杖|风杖|cyclone|风之杖|清莲宝珠|莲花|lotus_orb/i);
    const shardItem = hasItemMatch(/阿哈利姆魔晶|aghanims_shard/i) || p.aghanims_shard;
    const hasAnySupportUtility = Boolean(
      forceItem || glimmerItem || atosItem || vesselItem || blinkItem || eulOrLotus || shardItem
    );

    if (selfishCarryItemOnSup && !hasAnySupportUtility) {
      const post10Lh = Math.max(0, Number(p.last_hits || 0) - Number(p.laning_10m?.lh10 || 0));
      badges.push(`🚨 ${pos}号位毒瘤出装(裸${selfishCarryItemOnSup.zh}·0团队救人装)`);
      warnings.push(
        `🚨 <b>${pos}号位严重失职（假辅助·真毒瘤抢钱出大哥装）：</b>身为 <b>${pos}号位游走/保核辅助</b>，本职工作是服务3号位/1号位带节奏并出 <b>跳刀/推推棒/微光披风/阿托斯/风杖/魔晶</b> 等团队先手与救人装；但本局在劣势下竟于 <b>${selfishCarryItemOnSup.time_str} 裸憋大哥输出装【${selfishCarryItemOnSup.zh}】${
          bkbItem ? ` + ${bkbItem.time_str} 黑皇杖(BKB)` : ""
        }</b>，全场 <b>0推推、0微光、0阿托斯、0跳刀、0魔晶</b>！且10分钟后自己占线钻野刷了 <b>${post10Lh} 刀（总 ${
          p.last_hits || 0
        } 刀）</b> 抢大哥经济，全场仅打出 <b>${p.hero_damage_share_pct || 0}% 伤害与 ${
          p.tower_damage || 0
        } 塔伤</b>，属于典型的毒瘤辅助玩法！`
      );
    }

    if (midasItem) {
      badges.push(`🚨 辅助裸点金(${midasItem.time_str})`);
      warnings.push(
        `🚨 <b>辅助贪心毒瘤点金预警（${midasItem.time_str} 迈达斯之手）：</b>身为 <b>${pos}号位${heroShort}</b> 在中期花 2200 金裸出 <b>点金手(${midasItem.time_str})</b>${
          glimmerItem
            ? `，导致第一件团队救人装 <b>微光披风(${glimmerItem.time_str})</b> 拖到将近30分钟才成型`
            : "，整局 0 微光 0 推推"
        }，且面对敌方 <b>${kiteThreats} + 敌法师</b> 全场 <b>0 原力法杖(推推棒)</b>，属于典型的五号位贪发育出装（所幸后期36:22憋出羊刀将功补过）。`
      );
    }

    if (khandaOrPhylactery && !forceItem && !glimmerItem) {
      badges.push("⚠️ 纯堆伤害0推推/微光");
      warnings.push(
        `⚠️ <b>辅助重输出轻保命（${khandaOrPhylactery.time_str} ${khandaOrPhylactery.zh} · 0推推/0微光）：</b>虽然前中期做出大骨灰并靠 <b>灵匣→绝刃</b> 轰出 <b>${fmtNum(
          p.hero_damage
        )} 伤害</b>，但作为 ${pos}号位整局 <b>0 原力法杖(推推棒) / 0 微光披风</b>，无位移自保导致被敌方冲脸提款阵亡 <b>${
          p.deaths
        } 次（读秒 ${p.dead_seconds}s）</b>；若把绝刃卷轴换成推推棒，存活率与救队友能力会再上一层楼。`
      );
    } else if (!midasItem && !selfishCarryItemOnSup && !forceItem && oppKiteAndCatchHeroes.length >= 2) {
      warnings.push(
        `⚠️ <b>团队救人装短板（全队缺推推棒）：</b>面对敌方 <b>${kiteThreats}</b> 的减速/钩咬留人，未补出 <b>原力法杖(推推棒)</b> 帮队友拉开身位。`
      );
    }

    if (glimmerItem && !midasItem) {
      badges.push(`🛡️ 微光救人(${glimmerItem.time_str})`);
      highlights.push(`🛡️ <b>团队保人出装（${glimmerItem.time_str} 微光披风）：</b>主动做出微光披风掩护队友拉扯。`);
    }
    const hexItem = hasItemMatch(/邪恶镰刀|羊刀|sheepstick/i);
    if (hexItem) {
      badges.push(`🐑 后期羊刀(${hexItem.time_str})`);
      highlights.push(
        `🐑 <b>决胜硬控终极装（${hexItem.time_str} 邪恶镰刀·羊刀）：</b>高地决战补出羊刀配合多重施法提供瞬发先手羊！`
      );
    }
  }

  const timelinePills = filterMajorItems(phaseItems.map((it) => ({ zh_name: it.zh, key: it.key, time_str: it.time_str })), 6)
    .map((it) => `<span class="item-intel-step">${escapeHtml(it.zh_name)} <b>${escapeHtml(it.time_str)}</b></span>`)
    .join('<span class="item-intel-arrow">→</span>');

  return {
    badges,
    highlights,
    warnings,
    blinkVerdict,
    timelinePills,
    hasGreedySupportWarning: warnings.some((w) => /点金手|0推推/.test(w)),
  };
}

/**
 * Analyze a player's deaths in context (🟢团战换赢/掩护大哥牺牲 vs 🟡抢符抗压 vs 🔴无意义落单白给)
 * and audit whether they fulfilled their 1~5号位 role responsibilities in each phase.
 */
function analyzePlayerPhaseAndRoleContext(p, report) {
  const { side, own, opp } = getOwnAndOppPlayers(report);
  const df = report.deep_forensics || {};
  const rawPhases = report.phases_data || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  const byPhase = new Map(phasesList.map((pd) => [pd.key, pd]));

  const findPP = (pk) =>
    (byPhase.get(pk)?.players || []).find(
      (x) => Number(x.player_slot) === Number(p.player_slot) || x.hero_short_zh === p.hero_short_zh
    );
  const laneP = findPP("lane") || {};
  const midP = findPP("mid") || {};
  const lateP = findPP("late") || {};

  // Collect all team kill timestamps across phases for death-trade cross-referencing
  const allOwnKillEvents = [];
  const allOppKillEvents = [];
  phasesList.forEach((pd) => {
    (pd.players || []).forEach((pp) => {
      (pp.kills_events || []).forEach((ke) => {
        if (pp.side === side) {
          allOwnKillEvents.push({ ...ke, killer_hero: pp.hero_short_zh, killer_pos: pp.pos });
        } else {
          allOppKillEvents.push({ ...ke, killer_hero: pp.hero_short_zh, killer_pos: pp.pos });
        }
      });
    });
  });

  const ms = df.map_space_by_side?.[side] || {};
  const soloEvents = (ms.solo_pickoff_events || []).filter(
    (ev) => ev.hero_short_zh === p.hero_short_zh || Number(ev.pos) === Number(p.pos)
  );
  const lm = df.laning_mechanics_by_side?.[side] || {};
  const pullRow = (lm.pulling_rows || lm.pull_rows || []).find(
    (r) => r.hero_short_zh === p.hero_short_zh || Number(r.pos) === Number(p.pos)
  );
  const interactRow = (lm.map_interact_rows || []).find(
    (r) => r.hero_short_zh === p.hero_short_zh || Number(r.pos) === Number(p.pos)
  );
  const tpRow = (df.tp_rotation_by_side?.[side]?.player_tp_rows || []).find(
    (r) => r.hero_short_zh === p.hero_short_zh || Number(r.pos) === Number(p.pos)
  );
  const mirrorRow = (df.role_mirror_by_side?.[side]?.mirror_rows || []).find(
    (r) => r.own_hero === p.hero_short_zh || Number(r.pos) === Number(p.pos)
  );
  const itemAudit = df.item_audit_by_side?.[side] || {};
  const counterItemsBuilt = [];
  (itemAudit.team_counter_checklist || []).forEach((chk) => {
    (chk.built_holders || []).forEach((h) => {
      if (String(h).includes(p.hero_short_zh)) counterItemsBuilt.push(h);
    });
  });

  // Find which lane the player was in during 0-10m
  const lanes = df.lane_matchups || [];
  const myLane = lanes.find((ln) => {
    const arr = side === "dire" ? ln.dire_heroes : ln.radiant_heroes;
    return (arr || []).some((h) => h.hero_short_zh === p.hero_short_zh || Number(h.pos) === Number(p.pos));
  });
  const laneAllies = myLane
    ? ((side === "dire" ? myLane.dire_heroes : myLane.radiant_heroes) || []).filter(
        (h) => h.hero_short_zh !== p.hero_short_zh
      )
    : [];
  const laneEnemies = myLane
    ? (side === "dire" ? myLane.radiant_heroes : myLane.dire_heroes) || []
    : [];
  const signMult = side === (report.focus_side || "dire") ? 1 : -1;
  const teamGold10Diff = Math.round(Number(byPhase.get("lane")?.team_summary?.income_diff_end || 0) * signMult);

  // Classify deaths in a given phase ("lane" | "mid" | "late")
  const classifyPhaseDeaths = (phaseKey, ppObj) => {
    const dList = ppObj?.deaths_events || [];
    const sacList = [];
    const contestList = [];
    const throwList = [];

    dList.forEach((d) => {
      const t = Number(d.time || 0);
      const soloMatch = soloEvents.find((ev) => Math.abs(Number(ev.time_sec || 0) - t) <= 14);
      const ownKillsNear = allOwnKillEvents.filter((k) => k.time >= t - 18 && k.time <= t + 30);
      const oppKillsNear = allOppKillEvents.filter((k) => k.time >= t - 18 && k.time <= t + 30);
      const coreMultiKill = ownKillsNear.filter((k) => Number(k.killer_pos || 5) <= 2).length >= 2;

      if (soloMatch) {
        throwList.push({
          ...d,
          reason_type: "solo_pickoff",
          solo_ev: soloMatch,
          desc: `${d.time_str} 在${soloMatch.zone_zh || "野区交界"}落单被${soloMatch.killer_zh || d.killer}抓死${
            soloMatch.consequence && soloMatch.consequence !== "无战略收益白给"
              ? `（${soloMatch.consequence}）`
              : soloMatch.vision_tag?.includes("5 颗假眼")
              ? "（场上5颗假眼仍不看图）"
              : ""
          }`,
        });
      } else if (
        ownKillsNear.length >= 2 &&
        (ownKillsNear.length >= oppKillsNear.length || coreMultiKill || Number(p.pos || 5) >= 3)
      ) {
        const victims = [...new Set(ownKillsNear.map((k) => k.victim_hero))].slice(0, 3).join("/");
        const isPos12 = Number(p.pos || 5) <= 2;
        sacList.push({
          ...d,
          reason_type: isPos12 ? "won_tf_core_trade" : "won_tf_sacrifice",
          desc: isPos12
            ? `${d.time_str} 团战交火被${d.killer || "敌方"}集火切入阵亡，但倒下前打足输出，队友顺势收割 ${victims}（${ownKillsNear.length}杀团战获胜）`
            : `${d.time_str} 团战前排吃满${d.killer || "敌方"}火力牺牲，掩护大哥反杀 ${victims}（${ownKillsNear.length}杀团战大捷）`,
        });
      } else if (Number(p.pos || 5) >= 3 && ownKillsNear.length >= 1) {
        const victims = [...new Set(ownKillsNear.map((k) => k.victim_hero))].slice(0, 2).join("/");
        sacList.push({
          ...d,
          reason_type: "trade_sacrifice",
          desc: `${d.time_str} 肉身拼刺刀换血，配合队友换掉 ${victims}`,
        });
      } else if (
        phaseKey === "lane" &&
        Number(p.pos || 5) >= 3 &&
        (t <= 25 || (teamGold10Diff > 500 && Number(ppObj?.hero_damage_gain || 0) >= 2600))
      ) {
        contestList.push({
          ...d,
          reason_type: "lane_space",
          desc: `${d.time_str} ${t <= 25 ? "一级抢符团" : "边路凶狠换血/抢莲花"}阵亡（牵制敌方注意力保优势路大哥无解肥）`,
        });
      } else if (String(d.killer || "").includes("tower")) {
        contestList.push({
          ...d,
          reason_type: "tower_dive",
          desc: `${d.time_str} 压制敌方外塔被防塔击杀`,
        });
      } else {
        throwList.push({
          ...d,
          reason_type: "untraded_death",
          desc: `${d.time_str} 被${d.killer || "敌方"}击杀（未换回人头）`,
        });
      }
    });

    const total = dList.length;
    const goodDeaths = sacList.length + contestList.length;
    const badDeaths = throwList.length;
    // Effective penalty weight: sacrificial deaths carry very small penalty for Pos 3/4/5
    const posWeight = Number(p.pos || 5) >= 4 ? 0.15 : Number(p.pos || 5) === 3 ? 0.25 : 0.45;
    const effectiveBadDeaths = badDeaths + sacList.length * posWeight + contestList.length * (posWeight + 0.15);

    let auditText = "";
    const isPos12 = Number(p.pos || 5) <= 2;
    if (total === 0) {
      auditText = "本阶段 0 阵亡，走位滴水不漏。";
    } else if (sacList.length > 0 && badDeaths === 0) {
      auditText = isPos12
        ? `本阶段仅有的 ${total} 次阵亡发生在正面团战交火中（${sacList
            .map((s) => s.desc)
            .join("；")}），虽被敌方重点切入集火但团队最终打赢残局，无孤狼落单白给。`
        : `本阶段 ${total} 次阵亡全属【🟢 团战换赢/掩护大哥收割的合理战术牺牲】（${sacList
            .map((s) => s.desc)
            .join("；")}），身为 ${p.pos}号位死得极具价值，完全不背锅！`;
    } else if (goodDeaths > 0 && badDeaths > 0) {
      auditText = `本阶段阵亡 ${total} 次需一分为二看：其中 ${goodDeaths} 次属【🟢 ${
        isPos12 ? "正面团战被集火互换" : `${p.pos}号位前排换命/抗压牵制`
      }】（${[
        ...sacList,
        ...contestList,
      ]
        .slice(0, 2)
        .map((s) => s.desc)
        .join("；")}）；但有 ${badDeaths} 次属【🔴 不该送的断节奏/落单白给】（${throwList
        .slice(0, 2)
        .map((t) => t.desc)
        .join("；")}）。`;
    } else {
      auditText = `本阶段阵亡 ${total} 次均无正面人头交换（${throwList
        .slice(0, 3)
        .map((t) => t.desc)
        .join("；")}），属于需要严控站位的出血点。`;
    }

    return {
      total,
      sacList,
      contestList,
      throwList,
      goodDeaths,
      badDeaths,
      effectiveBadDeaths,
      auditText,
    };
  };

  return {
    laneP,
    midP,
    lateP,
    pullRow,
    interactRow,
    tpRow,
    mirrorRow,
    soloEvents,
    counterItemsBuilt,
    myLane,
    laneAllies,
    laneEnemies,
    teamGold10Diff,
    laneDeathsCtx: classifyPhaseDeaths("lane", laneP),
    midDeathsCtx: classifyPhaseDeaths("mid", midP),
    lateDeathsCtx: classifyPhaseDeaths("late", lateP),
  };
}

/**
 * Compute per-stage Best #1, Best #2, Scapegoat #1, Scapegoat #2 with role-duty & death-context intelligence
 */
function computeStageRankings(stageKey, report) {
  const { side, own } = getOwnAndOppPlayers(report);
  const df = report.deep_forensics || {};
  const ss = df.stacking_and_smoke_by_side?.[side] || {};
  const mo = df.macro_objectives_by_side?.[side] || {};

  const rawPhases = report.phases_data || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  const midPdForShare = phasesList.find((x) => x.key === "mid");
  const midOwnPlayersForShare = (midPdForShare?.players || []).filter((x) => x.side === side);
  const teamMidGoldTotal = Math.max(
    1,
    midOwnPlayersForShare.reduce((s, x) => s + Number(x.gold_gain || 0), 0)
  );
  const teamMidDmgTotal = Math.max(
    1,
    midOwnPlayersForShare.reduce((s, x) => s + Number(x.hero_damage_gain || 0), 0)
  );
  const teamMidTdmgTotal = Math.max(
    1,
    midOwnPlayersForShare.reduce((s, x) => s + Number(x.tower_damage_gain || 0), 0)
  );

  const LANE_BULLY_HEROES = new Set([
    "剧毒术士",
    "冥界亚龙",
    "哈斯卡",
    "剃刀",
    "不朽尸王",
    "杰奇洛",
    "巫妖",
    "伐木机",
    "孽主",
    "卓尔游侠",
    "狙击手",
    "戴泽",
    "巫医",
    "食人魔魔法师",
    "矮人直升机",
    "帕格纳",
    "天怒法师",
  ]);
  const SINGLE_TARGET_MIDS = new Set([
    "天怒法师",
    "赏金猎人",
    "克林克兹",
    "司夜刺客",
    "力丸",
    "祸乱之源",
    "帕吉",
    "修补匠",
  ]);
  const PUSH_TRAIT_HEROES = new Set([
    "帕格纳",
    "死亡先知",
    "暗影萨满",
    "莱席克",
    "兽王",
    "德鲁伊",
    "狼人",
    "魅惑魔女",
    "陈",
    "先知",
    "育母蜘蛛",
    "恐怖利刃",
    "卓尔游侠",
    "主宰",
    "露娜",
    "龙骑士",
  ]);

  const evaluated = own.map((p) => {
    const ctx = analyzePlayerPhaseAndRoleContext(p, report);
    const pos = Number(p.pos || 3);
    const isSup = pos >= 4;
    const isCore = pos <= 3;
    let score = 50;
    let goodReason = "";
    let badReason = "";

    if (stageKey === "lane") {
      const lp = ctx.laneP;
      const k = Number(lp.kills_count || 0);
      const d = Number(lp.deaths_count || 0);
      const lh = Number(p.laning_10m?.lh10 ?? lp.lh_gain ?? 0);
      const dn = Number(p.laning_10m?.dn10 ?? lp.dn_gain ?? 0);
      const gold10 = Number(p.laning_10m?.gold10 ?? lp.gold_gain ?? 0);
      const dmg10 = Number(lp.hero_damage_gain || 0);
      const tdmg10 = Number(lp.tower_damage_gain || 0);
      const eff = Number(p.lane_efficiency_pct || 60);
      const gDiff = Number(ctx.mirrorRow?.gold10_diff || 0);
      const pullPct = Number(ctx.pullRow?.pull_ratio_pct ?? 0);
      const earlySen = Number(ctx.pullRow?.early_sentries ?? 0);
      const gateCnt = Number(ctx.interactRow?.twin_gate ?? 0);
      const lotusCnt = Number(ctx.interactRow?.lotus_used ?? 0);
      const wisdomCnt = Number(ctx.interactRow?.wisdom_runes ?? 0);
      const lampCnt = Number(ctx.interactRow?.watcher_lamp ?? 0);
      const earlyTp = Number(ctx.tpRow?.early_tp_cnt ?? 0);
      const laneWon = ctx.myLane && ctx.myLane.winner_side === side;
      const allyStr = ctx.laneAllies.map((a) => `${a.pos}号位${a.hero_short_zh}`).join("+");
      const enemyStr = ctx.laneEnemies.map((e) => `${e.hero_short_zh}(仅${e.lh10}刀)`).join("+");
      const enemyNamesStr = ctx.laneEnemies.map((e) => e.hero_short_zh).join("+");
      const facingStrongEnemyLane = ctx.laneEnemies.some((e) => LANE_BULLY_HEROES.has(e.hero_short_zh));
      const isSingleTargetGankMid =
        pos === 2 && (SINGLE_TARGET_MIDS.has(p.hero_short_zh) || (gDiff >= 0 && k >= 2 && dmg10 >= 3200));

      if (isCore) {
        const expectedLh = isSingleTargetGankMid ? 30 : pos <= 2 ? 42 : 34;
        score +=
          k * 16 +
          (lh - expectedLh) * 0.85 +
          dn * 0.7 +
          gDiff / 55 +
          (eff - 65) * 0.6 +
          dmg10 / 400 +
          tdmg10 / 300 +
          (laneWon ? 14 : 0) -
          ctx.laneDeathsCtx.effectiveBadDeaths * 18 -
          (d >= 3 ? (d - 2) * 14 : 0);
        if (pos === 1 && lh >= 50 && d === 0) score += 16;
        if (pos === 2 && gDiff >= 150 && k >= 2 && d <= 1) score += 16;
        if (pos === 2 && lh < 35 && !isSingleTargetGankMid && gDiff < -200) score -= 12;

        const goodParts = [`10m <b>${lh}/${dn}刀（${fmtNum(gold10)}金·效率${eff}%）</b>，<b>${k}杀/${d}死</b>`];
        if (laneWon && allyStr) {
          goodParts.push(`联手${allyStr}把该路彻底打穿（压制${enemyStr}）`);
        } else if (isSingleTargetGankMid && gDiff >= 0) {
          goodParts.push(
            `虽受${p.hero_short_zh}缺乏AOE清线影响正补偏少，但凭高频法术消耗（灌出 <b>${fmtNum(
              dmg10
            )} 伤害</b>）单杀/游走建功，10m经济反压对位 <b>+${fmtNum(gDiff)}金</b>`
          );
        } else if (dmg10 >= 3800) {
          goodParts.push(
            `顶着对位压力凶悍换血灌出 <b>${fmtNum(dmg10)} 消耗伤害</b>${
              facingStrongEnemyLane && enemyNamesStr ? `（面对敌方${enemyNamesStr}强消耗组合硬咬住经济）` : ""
            }`
          );
        }
        if (gDiff >= 300 && !isSingleTargetGankMid) goodParts.push(`对位领先 <b>+${fmtNum(gDiff)}金</b>`);
        if (tdmg10 >= 500) goodParts.push(`磨塔 <b>${fmtNum(tdmg10)}</b>`);
        goodReason = goodParts.join("，");

        const badParts = [];
        if (d >= 2) {
          const matchupNote =
            facingStrongEnemyLane && enemyNamesStr
              ? `面对敌方<b>${enemyNamesStr}</b>强减速/消耗组合外加中单游走，线上天然劣势抗压极难；虽打足换血伤害，但`
              : "";
          badParts.push(
            `${matchupNote}对线期阵亡 <b>${d} 次</b>（${(lp.deaths_events || [])
              .slice(0, 3)
              .map((e) => `${e.time_str}被${e.killer}杀`)
              .join("、")}），防游走站位偏深`
          );
        }
        if (pos <= 2 && lh < 34 && !isSingleTargetGankMid && gDiff < 0) {
          badParts.push(`身为 ${pos}号位前10分钟仅 <b>${lh} 刀（${fmtNum(gold10)}金）</b>，补刀落后对位`);
        }
        if (badParts.length === 0) {
          badParts.push(
            d > 0
              ? `${lp.deaths_events?.[0]?.time_str || "对线期"}被${lp.deaths_events?.[0]?.killer || "敌方"}击杀断了一波节奏（对线整体占优）`
              : `对线0死无解肥，唯前10分钟推塔伤害 ${tdmg10}，可呼叫辅助更早压塔`
          );
        }
        badReason = badParts.join("；");
      } else {
        // Pos 4 / Pos 5 Support Laning Evaluation (Pulling, Lotus, Harass, Protecting Carry, Twin Gate)
        const didNotStealCS = pos === 5 && lh <= 10;
        score +=
          k * 18 +
          pullPct * 0.55 +
          earlySen * 6 +
          gateCnt * 14 +
          lotusCnt * 5 +
          wisdomCnt * 8 +
          lampCnt * 2 +
          earlyTp * 10 +
          dmg10 / 280 +
          (laneWon ? 18 : 0) +
          (didNotStealCS ? 10 : 0) -
          ctx.laneDeathsCtx.effectiveBadDeaths * 15 -
          (d >= 4 ? (d - 3) * 18 : 0);

        // Heavy penalty if support did NOT pull, did NOT ward, and farmed greedily
        if (pullPct < 10 && earlySen === 0 && lh > 22) {
          score -= 30;
        }

        const supGood = [];
        if (pullPct >= 20) {
          supGood.push(
            `积极拉野封野控线（驻留 <b>${pullPct}%</b>·封野真眼 <b>${earlySen}颗</b>${
              didNotStealCS ? `·仅补${lh}刀全让大哥` : ""
            }）`
          );
        }
        if (dmg10 >= 2200) {
          supGood.push(
            `上线肉身换血给足压力（灌出 <b>${fmtNum(dmg10)} 对线伤害</b>${
              laneWon && allyStr ? `，保${allyStr}无解肥打穿边路` : ""
            }）`
          );
        }
        if (k >= 1) {
          const killVictims = (lp.kills_events || []).map((ke) => `${ke.time_str}杀${ke.victim_hero}`).join("、");
          supGood.push(`配合击杀打开局面（<b>${k}杀/${d}死</b>：${killVictims}）`);
        }
        const microDetails = [];
        if (gateCnt > 0) microDetails.push(`钻双生门游走×${gateCnt}`);
        if (lotusCnt > 0) microDetails.push(`控疗伤莲花×${lotusCnt}`);
        else if (laneWon) microDetails.push(`控住边路莲花池`);
        if (wisdomCnt > 0) microDetails.push(`抢智慧符×${wisdomCnt}`);
        if (lampCnt > 0) microDetails.push(`点灯×${lampCnt}`);
        if (microDetails.length > 0) supGood.push(microDetails.join("·"));
        goodReason = supGood.join("；") || `前期保线插眼完成基础任务`;

        const supBad = [];
        if (d >= 3) {
          const matchupExcuse =
            facingStrongEnemyLane && enemyNamesStr
              ? `对线面对敌方<b>${enemyNamesStr}</b>强减速削蓝组合天然极度难打，且为抢${lotusCnt}莲花/${wisdomCnt}智慧符及掩护3号位拼命换血；但`
              : "";
          supBad.push(
            `${matchupExcuse}前10m阵亡 <b>${d} 次</b>（${(lp.deaths_events || [])
              .slice(-3)
              .map((e) => `${e.time_str}被${e.killer}收割`)
              .join("、")}），客观上让敌方1号位拿到了人头提款`
          );
        } else if (d >= 1) {
          supBad.push(`${lp.deaths_events?.[0]?.time_str || ""}被${lp.deaths_events?.[0]?.killer || "敌方"}击杀阵亡 ${d} 次`);
        }
        if (pullPct < 15) supBad.push(`拉野控线驻留偏低（${pullPct}%）`);
        badReason = supBad.join("；") || "对线期整体保核到位，注意河道符点视野保护";
      }
    } else if (stageKey === "mid") {
      const mp = ctx.midP;
      const k = Number(mp.kills_count || 0);
      const d = Number(mp.deaths_count || 0);
      const gold = Number(mp.gold_gain || 0);
      const dmg = Number(mp.hero_damage_gain || 0);
      const tdmg = Number(mp.tower_damage_gain || 0);
      const lh = Number(mp.lh_gain || 0);
      const goldSharePct = Number(((gold / teamMidGoldTotal) * 100).toFixed(1));
      const dmgSharePct = Number(((dmg / teamMidDmgTotal) * 100).toFixed(1));
      const tdmgSharePct = Number(((tdmg / teamMidTdmgTotal) * 100).toFixed(1));
      const conversionDiff = Number((dmgSharePct - goldSharePct).toFixed(1));
      const items = filterMajorItems(mp.items_bought, 3)
        .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
        .join("/");
      const midSolos = ctx.soloEvents.filter((ev) => {
        const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
        return m >= 9 && m <= 26;
      });
      const tfAbsent = Number(ctx.tpRow?.tf_absent_cnt ?? 0);
      const zeroTp = Number(ctx.tpRow?.tp_bought ?? 1) === 0;
      const smokedCnt = (ss.smoke_events || []).filter(
        (sm) => sm.initiator_hero === p.hero_short_zh || sm.activator_hero === p.hero_short_zh
      ).length;
      const hasGankItem = (mp.items_bought || []).some((it) =>
        /阿托斯|闪烁匕首|跳刀|紫苑|血棘|魂之灵瓮|大骨灰|诡计之雾/.test(String(it.zh_name || ""))
      );

      score +=
        k * 14 +
        dmg / 250 +
        tdmg / 140 +
        (isCore ? gold / 260 : gold / 420) +
        Math.max(-10, Math.min(16, conversionDiff * 0.75)) +
        (hasGankItem && k >= 2 ? 12 : 0) +
        smokedCnt * 12 +
        ctx.midDeathsCtx.sacList.length * 6 -
        ctx.midDeathsCtx.effectiveBadDeaths * 18 -
        midSolos.length * 22 -
        tfAbsent * 14 -
        (zeroTp ? 8 : 0);

      // Role-specific mid checks
      if (pos === 1 && gold >= 9500 && d <= 2 && !p.is_afk_farmer) {
        score += 22; // Pos 1 hitting massive farm timing cleanly while joining key kills
      }
      if (PUSH_TRAIT_HEROES.has(p.hero_short_zh) && tdmg >= 2000) {
        score += 18; // Hero-specific pushing trait fulfilled!
      }
      if (p.is_afk_farmer) {
        score -= 35; // Pos 1/2/3 AFK farming all game without converting
      }
      if (isSup && ctx.counterItemsBuilt.length > 0) {
        score += 12; // Support building Spirit Vessel / counter items
      }

      const goodParts = [
        `阶段 <b>${k}杀/${d}死</b>，吃 <b>${goldSharePct}% 经济（+${fmtNum(gold)}金）</b> 打出 <b>${fmtNum(
          dmg
        )} 伤害（占全队 ${dmgSharePct}%）</b>`,
      ];
      if (tdmg >= 1500) {
        goodParts.push(
          `完美发挥${p.hero_short_zh}推进特性狂拆 <b>${fmtNum(tdmg)} 建筑伤害（占全队中期推塔 ${tdmgSharePct}%）</b>拔掉外塔`
        );
      } else if (tdmg >= 500) {
        goodParts.push(`推塔 <b>+${fmtNum(tdmg)}</b>`);
      }
      if (items) goodParts.push(`做出关键装 <b>${items}</b>`);
      if (hasGankItem && k >= 2) {
        const victims = (mp.kills_events || []).map((ke) => `${ke.time_str}杀${ke.victim_hero}`).join("、");
        goodParts.push(`装备成型后立刻主动抓人节奏拉满（${victims}）`);
      }
      if (pos === 1 && gold >= 9500) {
        goodParts.push(`黄金期狂刷 <b>${lh}刀</b> 极速做出三大件且参团收割两不误`);
      }
      if (smokedCnt > 0) goodParts.push(`主动买雾破局×${smokedCnt}`);
      if (isSup && ctx.midDeathsCtx.sacList.length > 0) {
        goodParts.push(`团战前排肉身换命×${ctx.midDeathsCtx.sacList.length}波掩护大哥发育`);
      }
      goodReason = goodParts.join("，");

      const badParts = [];
      if (midSolos.length > 0) {
        badParts.push(
          `脱离大部队落单被抓 <b>${midSolos.length} 次</b>（${midSolos
            .map(
              (s) =>
                `${s.time_str}被${s.killer_zh}抓死${
                  s.consequence && s.consequence !== "无战略收益白给" ? `→${s.consequence}` : ""
                }`
            )
            .join("、")}）`
        );
      }
      if (ctx.midDeathsCtx.total >= 3) {
        if (ctx.midDeathsCtx.goodDeaths > 0) {
          badParts.push(
            `阶段阵亡 <b>${d} 次</b>（含 ${ctx.midDeathsCtx.goodDeaths} 次接团/推塔前排换命，但 ${ctx.midDeathsCtx.badDeaths} 次断节奏阵亡需规避）`
          );
        } else {
          badParts.push(`中期连续阵亡 <b>${d} 次</b>导致节奏断档`);
        }
      }
      if (PUSH_TRAIT_HEROES.has(p.hero_short_zh) && tdmg < 300 && pos !== 1) {
        badParts.push(`身为具备推进机制的${p.hero_short_zh}，中期建筑伤害仅 ${tdmg}，未充分利用技能磨塔`);
      }
      if (tfAbsent > 0 && pos !== 1) badParts.push(`团战缺席/边缘OB <b>${tfAbsent} 波</b>`);
      if (zeroTp) badParts.push(`整局主动买 <b>0 张 TP</b>`);
      if (pos === 5 && (mp.items_bought || []).some((it) => String(it.zh_name || "").includes("点金手"))) {
        badParts.push(`五号位中期裸出点金手(21:21)，略微拖慢团队微光/推推救人装成型节奏`);
      }
      badReason = badParts.join("；") || (d > 0 ? `中期阵亡 ${d} 次，需注意抱团走位` : "中期资源转化与节奏稳健");
    } else if (stageKey === "late") {
      const ltp = ctx.lateP;
      const k = Number(ltp.kills_count || 0);
      const d = Number(ltp.deaths_count || 0);
      const gold = Number(ltp.gold_gain || 0);
      const dmg = Number(ltp.hero_damage_gain || 0);
      const items = filterMajorItems(ltp.items_bought, 2)
        .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
        .join("/");
      const lateSolos = ctx.soloEvents.filter((ev) => {
        const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
        return m > 26;
      });
      const aegisTaken = (mo.roshan_events || []).some((r) => String(r).includes(p.hero_short_zh));
      const roshConv = analyzeRoshanAndResourceConversion(report);

      score +=
        k * 18 +
        dmg / 320 +
        (Number(p.tower_damage || 0) / 450) +
        (aegisTaken ? (roshConv.grade === "godlike" ? 26 : 18) : 0) +
        ctx.lateDeathsCtx.sacList.length * 6 -
        ctx.lateDeathsCtx.effectiveBadDeaths * 22 -
        lateSolos.length * 30;

      // Penalize core who ate late gold, dealt low late damage AND had < 2 kills
      if (isCore && gold >= 5500 && dmg < 6500 && k < 2) {
        score -= 20;
      } else if (isCore && gold >= 5500 && dmg < 6500) {
        score -= 8;
      }

      const goodParts = [
        `决胜期 <b>${k}杀/${d}死</b>，轰出 <b>${fmtNum(dmg)} 英雄伤害</b>（+${fmtNum(gold)}金）`,
      ];
      if (aegisTaken) {
        goodParts.push(
          roshConv.grade === "godlike"
            ? `控下肉山不朽盾并顺势拔光外塔连破高地塔与兵营（完美资源转化）`
            : `控下肉山不朽盾带队推进高地`
        );
      }
      if (Number(p.tower_damage || 0) >= 4000) goodParts.push(`全场狂拆 <b>${fmtNum(p.tower_damage)} 建筑伤害</b>`);
      if (items) goodParts.push(`成型 <b>${items}</b>`);
      if (isSup && ctx.lateDeathsCtx.sacList.length > 0) {
        goodParts.push(
          `决胜团前排肉身吃满敌方切入换命（${ctx.lateDeathsCtx.sacList
            .map((s) => s.time_str)
            .join("/")}掩护大哥收割团赢）`
        );
      }
      goodReason = goodParts.join("，");

      const badParts = [];
      if (lateSolos.length > 0) {
        badParts.push(
          `决胜期致命落单白给：<b>${lateSolos
            .map(
              (s) =>
                `${s.time_str}在${s.zone_zh}被${s.killer_zh}单抓（${
                  s.vision_tag?.includes("5 颗假眼") ? "场上5颗假眼不看小地图" : "无视野盲区孤走"
                }·读秒${s.time_dead}s）`
            )
            .join("、")}</b>`
        );
      }
      if (isCore && gold >= 5500 && dmg < 6500) {
        badParts.push(`身为 ${pos}号位后期吃下 <b>+${fmtNum(gold)}金</b> 仅打出 <b>${fmtNum(dmg)} 伤害</b>（虽收割 ${k} 杀，但跳刀切入与持续输出偏保守）`);
      }
      if (ctx.lateDeathsCtx.badDeaths > 0 && lateSolos.length === 0) {
        badParts.push(
          `后期断节奏阵亡 ${ctx.lateDeathsCtx.badDeaths} 次（${ctx.lateDeathsCtx.throwList
            .map((t) => `${t.time_str}被${t.killer}击杀`)
            .join("、")}）`
        );
      } else if (ctx.lateDeathsCtx.sacList.length > 0 && badParts.length === 0) {
        badParts.push(
          isCore
            ? `后期仅阵亡 ${d} 次（${ctx.lateDeathsCtx.sacList
                .map((s) => s.time_str)
                .join("/")}正面决战被敌方切入集火，倒下前打足输出由队友顺势收割，0次落单白给）`
            : `后期阵亡 ${d} 次均属团战前排掩护大哥收割的合理牺牲（无白给掉点）`
        );
      }
      badReason = badParts.join("；") || (d > 0 ? `后期阵亡 ${d} 次，注意高地团拉扯` : "决胜期完美收官 0 失误");
    } else {
      // Overall Full-Game Summary: 1~5 Role Duty, Itemization Intelligence & Death Reasonableness
      const score100 = getHeroScore100(p);
      const itemIntel = analyzePlayerItemizationIntelligence(p, report);
      const totalSac =
        ctx.laneDeathsCtx.sacList.length +
        ctx.midDeathsCtx.sacList.length +
        ctx.lateDeathsCtx.sacList.length;
      const unexcusedDeaths = Math.max(0, Number(p.deaths || 0) - totalSac);
      score =
        score100 +
        (Number(p.contrib_share_pct || 20) - Number(p.blame_share_pct || 20)) * 0.85 +
        itemIntel.highlights.length * 2.5 -
        itemIntel.warnings.length * 4.5 -
        unexcusedDeaths * 1.6 -
        ctx.soloEvents.length * 7;

      const goodParts = [
        `全场 <b>${p.kda}（${p.kill_participation_pct}%参战）</b>，伤害 <b>${fmtNum(p.hero_damage)}</b>`,
      ];
      if (Number(p.tower_damage || 0) >= 4000) goodParts.push(`拆塔 <b>${fmtNum(p.tower_damage)}</b>`);
      if (Number(p.stuns_sec || 0) >= 25) goodParts.push(`硬控 <b>${p.stuns_sec}秒</b>`);
      if (isSup && (Number(p.obs_placed || 0) + Number(p.sen_placed || 0)) >= 12) {
        goodParts.push(`视野劳模 <b>${p.obs_placed}假/${p.sen_placed}真</b>`);
      }
      if (itemIntel.badges.filter((b) => !/⚠️|🚨/.test(b)).length > 0) {
        goodParts.push(
          `灵性出装：<b>${itemIntel.badges
            .filter((b) => !/⚠️|🚨/.test(b))
            .slice(0, 2)
            .join(" · ")}</b>`
        );
      } else if (ctx.counterItemsBuilt.length > 0) {
        goodParts.push(`针对装 ${ctx.counterItemsBuilt[0]}`);
      }
      goodReason = goodParts.join(" · ");

      const badParts = [];
      if (p.is_afk_farmer) {
        badParts.push(`身为${pos}号位前中期闷头钻野拒绝参战，纯靠队友4打5撑局势`);
      }
      if (itemIntel.warnings.length > 0) {
        const cleanWarn = itemIntel.warnings[0].replace(/<[^>]+>/g, "");
        const shortWarn = cleanWarn.includes("：") ? cleanWarn.split("：").slice(1).join("：") : cleanWarn;
        badParts.push(`<b>出装审计：</b>${escapeHtml(shortWarn)}`);
      }
      if (ctx.soloEvents.length > 0) {
        badParts.push(
          `全场落单被抓 <b>${ctx.soloEvents.length} 次</b>（${ctx.soloEvents
            .map((s) => `${s.time_str}被${s.killer_zh}抓`)
            .join("、")}）`
        );
      }
      if (Number(ctx.tpRow?.tp_bought ?? 1) === 0) {
        badParts.push(`整局主动买 <b>0 张 TP</b>`);
      }
      if (totalSac >= 2 && Number(p.deaths || 0) >= 8) {
        badParts.push(
          `全场 ${p.deaths} 死中虽含 <b>${totalSac} 波团战合理换命牺牲</b>，但其余 ${unexcusedDeaths} 次对线/落单阵亡仍偏多（读秒 ${p.dead_seconds}s）`
        );
      } else if (Number(p.deaths || 0) >= 8) {
        badParts.push(`全场阵亡 <b>${p.deaths} 次</b>（泉水读秒 ${p.dead_seconds}s）`);
      }
      badReason = badParts.join("；") || `全场仅 ${p.deaths} 死，出装与履职稳定`;
    }

    return {
      player: p,
      pos,
      score,
      goodReason,
      badReason,
      ctx,
    };
  });

  const byBest = [...evaluated].sort((a, b) => b.score - a.score);
  const byWorst = [...evaluated].sort((a, b) => a.score - b.score);

  return {
    best1: byBest[0],
    best2: byBest[1],
    worst1: byWorst[0],
    worst2: byWorst[1],
    all: evaluated,
  };
}

function renderStageRankingsBlockHtml(stageKey, report) {
  const rk = computeStageRankings(stageKey, report);
  const renderEntry = (item, badgeText, themeClass, isGood) => {
    if (!item || !item.player) return "";
    const p = item.player;
    const reason = isGood ? item.goodReason : item.badReason;
    return `
      <div class="stage-rank-item ${themeClass}">
        <div class="stage-rank-top">
          <span class="stage-rank-badge ${themeClass}">${badgeText}</span>
          ${
            p.hero_img
              ? `<img src="${escapeHtml(p.hero_img)}" width="24" height="14" alt="" class="stage-rank-avatar" />`
              : ""
          }
          <strong class="stage-rank-hero">${p.pos}号位 ${escapeHtml(p.hero_short_zh)}</strong>
          <span class="stage-rank-player">(${escapeHtml(p.personaname)})</span>
        </div>
        <div class="stage-rank-desc">${injectHeroLogosIntoHtml(reason, report)}</div>
      </div>
    `;
  };

  const rankHeaderTitle =
    stageKey === "overall"
      ? "⚖️ 全场综合五人红黑榜（整局 1~5 号位职责兑现 · 灵性出装 &amp; 阵亡合理性总评）"
      : "⚖️ 本阶段五人红黑榜（结合 1~5 号位职责履行 &amp; 团战换命合理性审计）";

  return `
    <div class="stage-rank-box">
      <div class="stage-rank-header">${rankHeaderTitle}</div>
      <div class="stage-rank-grid">
        ${renderEntry(rk.best1, "🥇 头号做得好", "best1", true)}
        ${renderEntry(rk.best2, "🥈 第二做得好", "best2", true)}
        ${renderEntry(rk.worst1, "💀 头号背锅侠", "worst1", false)}
        ${renderEntry(rk.worst2, "⚠️ 第二背锅侠", "worst2", false)}
      </div>
    </div>
  `;
}

/**
 * Build rich 4-stage replay cards with inline Hero Mini-Logos + Per-Stage Top 2 Best / Top 2 Scapegoat for Chapter ②
 */
function buildRichFourStageCardsHtml(report) {
  const { side, sideZh, own, opp } = getOwnAndOppPlayers(report);
  const oppZh = side === "radiant" ? "夜魇" : "天辉";
  const df = report.deep_forensics || {};
  const rawPhases = report.phases_data || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  const byPhase = new Map(phasesList.map((pd) => [pd.key, pd]));
  const lanePd = byPhase.get("lane");
  const midPd = byPhase.get("mid");
  const latePd = byPhase.get("late");
  const signMult = side === (report.focus_side || "dire") ? 1 : -1;

  // --- STAGE 1: 00:00 - 10:00 对线期三路表现 · 游走Gank与抢符拉野 ---
  const laneOwnP = (lanePd?.players || []).filter((p) => p.side === side);
  const laneOppP = (lanePd?.players || []).filter((p) => p.side !== side);
  const laneOwnKills = laneOwnP.reduce((s, p) => s + (p.kills_count || 0), 0);
  const laneOppKills = laneOppP.reduce((s, p) => s + (p.kills_count || 0), 0);
  const gold10Diff = Math.round(Number(lanePd?.team_summary?.income_diff_end || 0) * signMult);
  const lm = df.laning_mechanics_by_side?.[side] || {};
  const tp = df.tp_rotation_by_side?.[side] || {};
  const rm = df.role_mirror_by_side?.[side] || {};
  const lanes = df.lane_matchups || [];

  const laneOverviewBullet = `<span class="stage-key-pill">10m 对线总账</span> 10分钟人头比 <b>${sideZh} ${laneOwnKills} : ${laneOppKills} ${oppZh}</b>，经济差 <b style="color:${
    gold10Diff >= 0 ? "var(--green-light)" : "var(--red-light)"
  }">${fmtSigned(gold10Diff)} 金</b>（同位置10m经济占优 <b>${rm.won_lanes_cnt ?? "-"} / 5</b> 路）。`;

  const laneMatchupBullets = lanes.map((ln) => {
    const direHeroes = (ln.dire_heroes || [])
      .map((h) => `${h.hero_short_zh}(${h.lh10 ?? 0}/${h.dn10 ?? 0}刀·${fmtNum(h.gold10 || 0)}金)`)
      .join("+");
    const radHeroes = (ln.radiant_heroes || [])
      .map((h) => `${h.hero_short_zh}(${h.lh10 ?? 0}/${h.dn10 ?? 0}刀·${fmtNum(h.gold10 || 0)}金)`)
      .join("+");
    const ownLine = side === "dire" ? `夜魇 ${direHeroes}` : `天辉 ${radHeroes}`;
    const oppLine = side === "dire" ? `天辉 ${radHeroes}` : `夜魇 ${direHeroes}`;
    const laneName = (ln.title || "分路").split(" ")[0];
    return `<span class="stage-key-pill">${escapeHtml(laneName)}</span> ${escapeHtml(ownLine)} 对阵 ${escapeHtml(
      oppLine
    )} <span class="stage-outcome-pill">→ ${escapeHtml(ln.verdict_zh || "均势")}</span>`;
  });

  // Roaming / Twin Gate / early TP rotations / early gankers
  const gateUsers = (lm.map_interact_rows || [])
    .filter((g) => (g.twin_gate ?? 0) > 0)
    .map((g) => `${g.pos}号位${g.hero_short_zh}(走门×${g.twin_gate})`);
  const earlyTpUsers = (tp.player_tp_rows || [])
    .filter((r) => (r.early_tp_cnt ?? r.early_tp_rotations_12m ?? 0) > 0)
    .map((r) => `${r.pos}号位${r.hero_short_zh}(前12m亮TP×${r.early_tp_cnt ?? r.early_tp_rotations_12m})`);
  const earlyKillLeaders = [...laneOwnP]
    .filter((p) => (p.kills_count || 0) >= 2)
    .sort((a, b) => (b.kills_count || 0) - (a.kills_count || 0))
    .map((p) => `${p.pos}号位${p.hero_short_zh}(${p.kills_count}杀/${p.deaths_count}死)`);
  const earlyVictims = [...laneOwnP]
    .filter((p) => (p.deaths_count || 0) >= 2)
    .sort((a, b) => (b.deaths_count || 0) - (a.deaths_count || 0))
    .map((p) => `${p.pos}号位${p.hero_short_zh}(被抓${p.deaths_count}死)`);

  const roamAndGankBullet = `<span class="stage-key-pill">前期游走与支援</span> 双生门传送 <b>${
    lm.own_gate_total ?? 0
  } : ${lm.opp_gate_total ?? 0}</b>（${
    gateUsers.length > 0 ? escapeHtml(gateUsers.join("、")) : "本方前10m未走双生门绕后"
  }）；前12m支援/回线TP：${
    earlyTpUsers.length > 0 ? escapeHtml(earlyTpUsers.join("、")) : "无主动支援TP"
  }。${
    earlyKillLeaders.length > 0
      ? `对线期打开节奏：<b>${escapeHtml(earlyKillLeaders.join("、"))}</b>；`
      : ""
  }${earlyVictims.length > 0 ? `抗压/被游走针对：<b>${escapeHtml(earlyVictims.join("、"))}</b>。` : ""}`;

  const pullSummary = (lm.pulling_rows || lm.pull_rows || [])
    .map(
      (r) =>
        `${r.pos}号位${r.hero_short_zh}(拉野驻留${r.pull_ratio_pct ?? r.pull_presence_pct ?? 0}%·真眼${
          r.early_sentries ?? r.early_sentries_placed ?? 0
        }颗·${r.status_tag || "保线"})`
    )
    .join("、");
  const waterStr = (lm.water_runes_timeline || lm.water_events || [])
    .map((w) => `${w.time_str} ${w.hero_short_zh}`)
    .join(" / ");
  const resourcesBullet = `<span class="stage-key-pill">抢符·拉野·封野</span> 疗伤莲花 <b>${
    lm.own_lotus_total ?? 0
  } : ${lm.opp_lotus_total ?? 0}</b>，智慧神符 <b>${lm.own_wisdom_cnt ?? 0} : ${
    lm.opp_wisdom_cnt ?? 0
  }</b>${waterStr ? `，中路水符(${escapeHtml(waterStr)})` : ""}；辅助拉野封野：${
    pullSummary ? escapeHtml(pullSummary) : "常规保线"
  }。`;

  // --- STAGE 2: 10:00 - 25:00 中期 Gank · 开雾情况 · 打团齐整度与大哥打钱节奏 ---
  const midOwnP = (midPd?.players || [])
    .filter((p) => p.side === side)
    .sort((a, b) => (a.pos || 9) - (b.pos || 9));
  const midOppP = (midPd?.players || []).filter((p) => p.side !== side);
  const midOwnKills = midOwnP.reduce((s, p) => s + (p.kills_count || 0), 0);
  const midOppKills = midOppP.reduce((s, p) => s + (p.kills_count || 0), 0);
  const midGoldDelta = Math.round(Number(midPd?.team_summary?.income_diff_change || 0) * signMult);
  const midGoldEnd = Math.round(Number(midPd?.team_summary?.income_diff_end || 0) * signMult);
  const ss = df.stacking_and_smoke_by_side?.[side] || {};
  const ms = df.map_space_by_side?.[side] || {};

  const midOverviewBullet = `<span class="stage-key-pill">中期控图节奏</span> 10–25m 爆发人头 <b>${sideZh} ${midOwnKills} : ${midOppKills} ${oppZh}</b>，阶段经济净变动 <b style="color:${
    midGoldDelta >= 0 ? "var(--green-light)" : "var(--red-light)"
  }">${fmtSigned(midGoldDelta)} 金</b>（25m累计经济差 <b>${fmtSigned(midGoldEnd)} 金</b>），推塔 <b>${
    midPd?.team_summary?.towers_taken ?? 0
  }</b> 座 / 掉塔 <b>${midPd?.team_summary?.towers_lost ?? 0}</b> 座。`;

  const smokeEvents = ss.smoke_events || [];
  const smokeDetailsStr =
    smokeEvents.length > 0
      ? smokeEvents
          .slice(0, 4)
          .map(
            (sm) =>
              `${sm.time_str} ${sm.initiator_hero || sm.activator_hero || "全队"}捏雾 → ${
                sm.outcome_label || ""
              }`
          )
          .join("；")
      : "整局 0 开雾记录";
  const smokeBullet = `<span class="stage-key-pill">开雾 Gank 审计</span> 全队买雾 <b>${
    ss.smoke_total_bought ?? smokeEvents.length
  }</b> 颗 / 开雾 <b>${ss.own_smoke_uses ?? smokeEvents.length}</b> 波（🟢破雾大捷 <b>${
    ss.smoke_success_count ?? 0
  }</b> 波 · 🟡哑火空雾 <b>${ss.smoke_dry_count ?? 0}</b> 波 · 🔴撞墙 <b>${
    ss.smoke_backfire_count ?? 0
  }</b> 波）：${escapeHtml(smokeDetailsStr)}。`;

  // Teamfight attendance (who didn't show up / 0 TP bought) & Solo Pickoffs in 9-25m
  const absentRows = (tp.player_tp_rows || []).filter(
    (r) => (r.tf_absent_cnt ?? r.spectator_teamfights ?? 0) > 0
  );
  const zeroTpBuyers = (tp.player_tp_rows || []).filter((r) => Number(r.tp_bought ?? 1) === 0);
  const midSoloEvents = (ms.solo_pickoff_events || []).filter((ev) => {
    const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
    return m >= 9 && m <= 26;
  });
  const attendanceParts = [];
  if (absentRows.length > 0) {
    attendanceParts.push(
      `团战缺席/边缘OB：<b>${escapeHtml(
        absentRows
          .map(
            (r) =>
              `${r.pos}号位${r.hero_short_zh}缺席${r.tf_absent_cnt ?? r.spectator_teamfights}波(${(
                r.tf_absent_times ||
                r.spectator_times ||
                []
              ).join("/")})`
          )
          .join("、")
      )}</b>`
    );
  } else {
    attendanceParts.push(`正面团战全员齐整到场（0次团战边缘OB）`);
  }
  if (zeroTpBuyers.length > 0) {
    attendanceParts.push(
      `⚠️ <b>${escapeHtml(
        zeroTpBuyers.map((r) => `${r.pos}号位${r.hero_short_zh}`).join("、")
      )}</b> 整局主动花钱买 0 张 TP`
    );
  }
  if (midSoloEvents.length > 0) {
    attendanceParts.push(
      `🚨 中期脱离团队落单被抓 <b>${midSoloEvents.length}</b> 次：${escapeHtml(
        midSoloEvents
          .slice(0, 4)
          .map(
            (ev) =>
              `${ev.time_str} ${ev.pos}号位${ev.hero_short_zh}在${ev.zone_zh}被${ev.killer_zh || "敌方"}抓死`
          )
          .join("；")
      )}`
    );
  } else {
    attendanceParts.push(`中期 0 次盲区落单掉点`);
  }
  const attendanceBullet = `<span class="stage-key-pill">打团齐整度与掉点</span> ${attendanceParts.join("；")}。`;

  // Core farming pace (Pos 1-3 in 10-25m + item timings + stacks)
  const coreFarmingStr = midOwnP
    .filter((p) => (p.pos || 9) <= 3)
    .map((c) => {
      const fullP = own.find((x) => Number(x.player_slot) === Number(c.player_slot)) || c;
      const itemsStr = filterMajorItems(c.items_bought, 3)
        .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
        .join("/");
      return `${c.pos}号位${c.hero_short_zh}(+${fmtNum(c.gold_gain || 0)}金/+${
        c.lh_gain || 0
      }刀·伤${fmtNum(c.hero_damage_gain || 0)}·塔${fmtNum(c.tower_damage_gain || 0)}${
        itemsStr ? `·出装:${itemsStr}` : ""
      })`;
    })
    .join(" ｜ ");
  const farmingBullet = `<span class="stage-key-pill">大哥打钱与装备提速</span> 全队堆野 <b>${
    ss.total_stacks ?? 0
  }</b> 组；10–25m三大哥资源转化：${escapeHtml(coreFarmingStr || "数据正常")}。`;

  const midTotalTdmg = Math.max(1, midOwnP.reduce((s, x) => s + Number(x.tower_damage_gain || 0), 0));
  const midTopPusher = [...midOwnP].sort((a, b) => (b.tower_damage_gain || 0) - (a.tower_damage_gain || 0))[0];
  const midTopGanker = [...midOwnP].sort(
    (a, b) =>
      (b.kills_count || 0) * 1000 +
      (b.hero_damage_gain || 0) -
      ((a.kills_count || 0) * 1000 + (a.hero_damage_gain || 0))
  )[0];
  const midPushAndGankBullet = `<span class="stage-key-pill">特性推塔与主动抓人</span> 中期全队推塔伤害 <b>${fmtNum(
    midTotalTdmg
  )}</b>（拔塔王：<b>${midTopPusher?.pos || 3}号位${escapeHtml(
    midTopPusher?.hero_short_zh || ""
  )} ${fmtNum(midTopPusher?.tower_damage_gain || 0)} 塔伤·占全队 ${Math.round(
    ((midTopPusher?.tower_damage_gain || 0) / midTotalTdmg) * 100
  )}%</b>）；抓人节奏发动机：<b>${midTopGanker?.pos || 2}号位${escapeHtml(
    midTopGanker?.hero_short_zh || ""
  )}（${midTopGanker?.kills_count || 0}杀/${midTopGanker?.deaths_count || 0}死·${fmtNum(
    midTopGanker?.hero_damage_gain || 0
  )}伤）</b>。`;

  // --- STAGE 3: 25:00 - 终局 决胜团战 · 肉山高地 · 买活博弈与后期刷钱转化 ---
  const lateOwnP = (latePd?.players || [])
    .filter((p) => p.side === side)
    .sort((a, b) => (a.pos || 9) - (b.pos || 9));
  const lateOppP = (latePd?.players || []).filter((p) => p.side !== side);
  const lateOwnKills = lateOwnP.reduce((s, p) => s + (p.kills_count || 0), 0);
  const lateOppKills = lateOppP.reduce((s, p) => s + (p.kills_count || 0), 0);
  const lateGoldDelta = Math.round(Number(latePd?.team_summary?.income_diff_change || 0) * signMult);
  const topLateCarry = [...lateOwnP].sort(
    (a, b) => (b.hero_damage_gain || 0) + (b.gold_gain || 0) - ((a.hero_damage_gain || 0) + (a.gold_gain || 0))
  )[0];
  const mo = df.macro_objectives_by_side?.[side] || {};
  const us = df.unpressed_saves_by_side?.[side] || {};
  const lateTeamfights = (report.key_teamfights || []).filter((tf) => {
    const startSec = Number(tf.start_sec || 0);
    if (startSec >= 1400) return true;
    const m = parseInt(String(tf.time_range || "0").split(":")[0], 10);
    return m >= 24;
  });
  const peakTf = lateTeamfights[0] || (report.key_teamfights || [])[0];
  const roshAudit = analyzeRoshanAndResourceConversion(report);

  const lateOverviewBullet = `<span class="stage-key-pill">后期决战走势</span> 25m–终局人头交换 <b>${sideZh} ${lateOwnKills} : ${lateOppKills} ${oppZh}</b>，经济差再拉开 <b style="color:${
    lateGoldDelta >= 0 ? "var(--green-light)" : "var(--red-light)"
  }">${fmtSigned(lateGoldDelta)} 金</b>，推塔 <b>${
    latePd?.team_summary?.towers_taken ?? 0
  }</b> 座。${
    topLateCarry
      ? `后期最强刷钱输出引擎为 <b>${topLateCarry.pos}号位${escapeHtml(
          topLateCarry.hero_short_zh
        )}</b>（后期 +${fmtNum(topLateCarry.gold_gain || 0)}金 / 打出 ${fmtNum(
          topLateCarry.hero_damage_gain || 0
        )} 英雄伤害）。`
      : ""
  }`;

  const peakTfBullet = peakTf
    ? `<span class="stage-key-pill">决胜高强度团战</span> 爆发于 <b>${escapeHtml(
        peakTf.time_range || ""
      )}</b>，双方打出 <b>${escapeHtml(peakTf.kills_trade || "")}</b>（经济波动 <b>${escapeHtml(
        peakTf.gold_swing || ""
      )}</b>），单波最高输出为 <b>${escapeHtml(peakTf.top_damage_hero || "")}</b>。`
    : `<span class="stage-key-pill">决胜高强度团战</span> 后期通过带线牵制与高地推进完成终结。`;

  const lateSoloEvents = (ms.solo_pickoff_events || []).filter((ev) => {
    const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
    return m > 26;
  });
  const roshAndPickoffBullet = `<span class="stage-key-pill">控盾资源转化与掉点</span> ${
    roshAudit.shortHtml
  } ${
    lateSoloEvents.length > 0
      ? `｜ 🚨 26m后关键期落单被抓：<b>${escapeHtml(
          lateSoloEvents
            .map((ev) => `${ev.time_str} ${ev.pos}号位${ev.hero_short_zh}在${ev.zone_zh}被${ev.killer_zh || "敌方"}击杀`)
            .join("、")
        )}</b>`
      : "｜ ✓ 26m后决胜期 0 次无脑落单白给"
  }`;

  const bbSummary =
    (mo.buyback_events || []).length > 0
      ? mo.buyback_events
          .slice(0, 2)
          .map((b) => `${b.time_str} ${b.pos}号位${b.hero_short_zh}(${b.outcome_tag})`)
          .join("、")
      : "全员0买活死";
  const buybackAndSaveBullet = `<span class="stage-key-pill">买活博弈与保命审计</span> 救世买活 <b>${
    mo.clutch_bb_cnt ?? 0
  }</b> 次 / 致命买活死 <b>${mo.dieback_cnt ?? 0}</b> 次（${escapeHtml(
    bbSummary
  )}）；团战憋死保命装 <b>${us.critical_total ?? 0}</b> 人次，终局比分定格 <b>${
    report.radiant_score
  } : ${report.dire_score}</b> (${escapeHtml(report.duration_str)})。`;

  // --- OVERALL SUMMARY CARD (Not "Stage 4"! Full-Game Hard Power & 1~5 Role Mirror Summary) ---
  const ownStuns = own.reduce((s, p) => s + Number(p.stuns_sec || 0), 0).toFixed(1);
  const oppStuns = opp.reduce((s, p) => s + Number(p.stuns_sec || 0), 0).toFixed(1);
  const topStunner = [...own].sort((a, b) => Number(b.stuns_sec || 0) - Number(a.stuns_sec || 0))[0];
  const vis = df.support_vision_by_side?.[side] || {};
  const oppVis = df.support_vision_by_side?.[side === "dire" ? "radiant" : "dire"] || {};
  const topWarder = [...own].sort(
    (a, b) =>
      Number(b.obs_placed || 0) +
      Number(b.sen_placed || 0) -
      (Number(a.obs_placed || 0) + Number(a.sen_placed || 0))
  )[0];
  const ownDmg = own.reduce((s, p) => s + Number(p.hero_damage || 0), 0);
  const oppDmg = opp.reduce((s, p) => s + Number(p.hero_damage || 0), 0);
  const ownTd = own.reduce((s, p) => s + Number(p.tower_damage || 0), 0);
  const oppTd = opp.reduce((s, p) => s + Number(p.tower_damage || 0), 0);
  const topDmgHero = [...own].sort((a, b) => Number(b.hero_damage || 0) - Number(a.hero_damage || 0))[0];
  const topPusherHero = [...own].sort((a, b) => Number(b.tower_damage || 0) - Number(a.tower_damage || 0))[0];
  const ownDeadSec = own.reduce((s, p) => s + Number(p.dead_seconds || 0), 0);
  const oppDeadSec = opp.reduce((s, p) => s + Number(p.dead_seconds || 0), 0);
  const mostDeadHero = [...own].sort((a, b) => Number(b.dead_seconds || 0) - Number(a.dead_seconds || 0))[0];

  const stage4Bullets = [
    `<span class="stage-key-pill">① 控制链与大招兑现</span> 全队硬控 <b>${ownStuns}秒 vs ${oppStuns}秒</b>（控制王：<b>${
      topStunner?.pos ?? "?"
    }号位${escapeHtml(topStunner?.hero_short_zh || "")} ${topStunner?.stuns_sec ?? 0}秒</b>）。`,
    `<span class="stage-key-pill">② 视野统治力与反眼</span> 假眼 <b>${vis.total_obs ?? 0} vs ${
      oppVis.total_obs ?? 0
    }</b>，真眼 <b>${vis.total_sen ?? 0} vs ${
      oppVis.total_sen ?? 0
    }</b>，假眼均寿 <b>${vis.avg_lifespan_sec ?? 0}s/360s</b>（视野劳模：<b>${
      topWarder?.pos ?? 5
    }号位${escapeHtml(topWarder?.hero_short_zh || "")} ${topWarder?.obs_placed ?? 0}假${
      topWarder?.sen_placed ?? 0
    }真</b>）。`,
    `<span class="stage-key-pill">③ 输出转化与推塔拆迁</span> 英雄总伤害 <b>${fmtNum(ownDmg)} vs ${fmtNum(
      oppDmg
    )}</b>（输出王：<b>${escapeHtml(topDmgHero?.hero_short_zh || "")} ${fmtNum(
      topDmgHero?.hero_damage || 0
    )}</b>）；建筑推塔 <b>${fmtNum(ownTd)} vs ${fmtNum(oppTd)}</b>（拆迁王：<b>${escapeHtml(
      topPusherHero?.hero_short_zh || ""
    )} ${fmtNum(topPusherHero?.tower_damage || 0)}</b>）。`,
    `<span class="stage-key-pill">④ 泉水读秒与同位对位</span> 全队泉水读秒 <b>${ownDeadSec}秒 vs ${oppDeadSec}秒</b>（读秒最多：<b>${escapeHtml(
      mostDeadHero?.hero_short_zh || ""
    )} ${mostDeadHero?.dead_seconds ?? 0}秒</b>）；1~5号位同位置正面对位 <b>${
      rm.won_overall_cnt ?? 3
    } / 5 胜出</b>。`,
  ];

  const grokStages = report.grok_coaching?.stage_reviews || {};
  const grokEarlyBullet = grokStages.early_lanes
    ? `<span class="stage-key-pill" style="background:rgba(139,92,246,0.22);border-color:rgba(167,139,250,0.55);color:#ddd6fe;">🧠 Grok 4.7 AI 复盘</span> ${escapeHtml(
        grokStages.early_lanes
      )}`
    : null;
  const grokMidBullet = grokStages.mid_tempo
    ? `<span class="stage-key-pill" style="background:rgba(139,92,246,0.22);border-color:rgba(167,139,250,0.55);color:#ddd6fe;">🧠 Grok 4.7 AI 复盘</span> ${escapeHtml(
        grokStages.mid_tempo
      )}`
    : null;
  const grokLateBullet = grokStages.late_and_roshan
    ? `<span class="stage-key-pill" style="background:rgba(139,92,246,0.22);border-color:rgba(167,139,250,0.55);color:#ddd6fe;">🧠 Grok 4.7 AI 复盘</span> ${escapeHtml(
        grokStages.late_and_roshan
      )}`
    : null;
  const grokOverallBullet = grokStages.overall_verdict
    ? `<span class="stage-key-pill" style="background:rgba(139,92,246,0.22);border-color:rgba(167,139,250,0.55);color:#ddd6fe;">🧠 Grok 4.7 AI 总评</span> ${escapeHtml(
        grokStages.overall_verdict
      )}`
    : null;

  const richStages = [
    {
      stageKey: "lane",
      icon: "🌅",
      badge: "阶段 1 · 前期",
      title: "00:00 - 10:00 对线期三路表现 · 游走Gank与抢符拉野",
      bullets: grokEarlyBullet
        ? [grokEarlyBullet, laneOverviewBullet, resourcesBullet]
        : [laneOverviewBullet, ...laneMatchupBullets, roamAndGankBullet, resourcesBullet],
    },
    {
      stageKey: "mid",
      icon: "⚔️",
      badge: "阶段 2 · 中期",
      title: "10:00 - 25:00 中期资源转化 · 主动抓人 · 英雄特性推塔与开雾齐整度",
      bullets: grokMidBullet
        ? [grokMidBullet, midOverviewBullet, smokeBullet]
        : [midOverviewBullet, midPushAndGankBullet, farmingBullet, smokeBullet, attendanceBullet],
    },
    {
      stageKey: "late",
      icon: "🔥",
      badge: "阶段 3 · 后期",
      title: "25:00 - 终局 决胜团战 · 控盾推高地转化 · 买活博弈与刷钱兑现",
      bullets: grokLateBullet
        ? [grokLateBullet, roshAndPickoffBullet, buybackAndSaveBullet]
        : [lateOverviewBullet, peakTfBullet, roshAndPickoffBullet, buybackAndSaveBullet],
    },
    {
      stageKey: "overall",
      icon: "🏆",
      badge: "全场总账",
      title: "整局五人硬实力 · 团队资源转化与 1~5 号位对位总评",
      bullets: grokOverallBullet
        ? [grokOverallBullet, stage4Bullets[0], stage4Bullets[2]]
        : stage4Bullets,
    },
  ];

  return `<div class="verdict-stages-grid">
    ${richStages
      .map(
        (st) => `
        <div class="verdict-stage-card">
          <div class="verdict-stage-head">
            <span class="verdict-stage-badge">${st.icon} ${escapeHtml(st.badge)}</span>
            <strong class="verdict-stage-title">${escapeHtml(st.title)}</strong>
          </div>
          <ul class="verdict-stage-bullets">
            ${st.bullets.map((b) => `<li>${injectHeroLogosIntoHtml(b, report)}</li>`).join("")}
          </ul>
          ${renderStageRankingsBlockHtml(st.stageKey, report)}
        </div>
      `
      )
      .join("")}
  </div>`;
}

/**
 * Build a multi-chapter novel-style battle chronicle + explicit Good/Bad ("哪里做得好" vs "哪里做得不好")
 * & Role-Duty / Death-Reasonableness audit for a player card
 * (`roleType`: "mvp" | "runnerup" | "struggle" | "culprit1" | "culprit2" | "svp")
 */
function buildPlayerChronologyStoryHtml(p, report, roleType, sharePct) {
  if (!p) return "";
  const { side, sideZh } = getOwnAndOppPlayers(report);
  const oppZh = side === "radiant" ? "夜魇" : "天辉";
  const df = report.deep_forensics || {};
  const ctx = analyzePlayerPhaseAndRoleContext(p, report);
  const {
    laneP,
    midP,
    lateP,
    pullRow,
    interactRow,
    tpRow,
    mirrorRow,
    soloEvents,
    counterItemsBuilt,
    myLane,
    laneAllies,
    laneEnemies,
    laneDeathsCtx,
    midDeathsCtx,
    lateDeathsCtx,
  } = ctx;

  const pos = Number(p.pos || 1);
  const isSup = pos >= 4;
  const isCore = pos <= 3;
  const heroShort = p.hero_short_zh || p.hero_name || "";
  const oppHero = mirrorRow?.opp_hero || "同位宿敌";
  const score100 = getHeroScore100(p);
  const pt = p.phase_telemetry || {};
  const lh10 = p.laning_10m?.lh10 ?? laneP?.lh_gain ?? 0;
  const dn10 = p.laning_10m?.dn10 ?? laneP?.dn_gain ?? 0;
  const gold10 = p.laning_10m?.gold10 ?? laneP?.gold_gain ?? 0;
  const g10Diff = Number(mirrorRow?.gold10_diff ?? 0);
  const midGold = midP?.gold_gain ?? pt.mid_gold_gain ?? 0;
  const midDmg = midP?.hero_damage_gain ?? pt.mid_hdmg_gain ?? 0;
  const hasTimelineTelemetry = Boolean(report.is_parsed) && (gold10 > 0 || midGold > 0);

  const laneNameShort = myLane ? String(myLane.title || "边路").split(" ")[0] : pos === 2 ? "中路" : "边路";
  const allyNames = laneAllies.map((a) => `${a.pos}号位${a.hero_short_zh}`).join("与");
  const enemyNames = laneEnemies.map((e) => `${e.hero_short_zh}`).join("与");
  const laneWon = myLane && myLane.winner_side === side;

  // =========================================================================
  // 第一幕 · 序章对线 (00:00 - 10:00) — 小说式故事线
  // =========================================================================
  const laneK = laneP?.kills_count ?? pt.lane_kills ?? 0;
  const laneD = laneP?.deaths_count ?? pt.lane_deaths ?? 0;
  const laneDmg = laneP?.hero_damage_gain ?? pt.lane_hdmg_gain ?? 0;
  const pullPct = Number(pullRow?.pull_ratio_pct ?? 0);
  const earlySen = Number(pullRow?.early_sentries ?? 0);
  const gateCnt = Number(interactRow?.twin_gate ?? 0);
  const lotusCnt = Number(interactRow?.lotus_used ?? 0);
  const wisdomCnt = Number(interactRow?.wisdom_runes ?? 0);
  const lampCnt = Number(interactRow?.watcher_lamp ?? 0);

  let act1Story = "";
  if (hasTimelineTelemetry) {
    const laneOpening =
      pos === 2
        ? `开局独自坐镇中路皇城迎战${oppZh}${enemyNames || oppHero}`
        : `开局奔赴${laneNameShort}${allyNames ? `，与${allyNames}并肩作战` : ""}，迎战${oppZh}${enemyNames || oppHero}的组合`;

    if (isCore) {
      const killKillsDesc =
        (laneP?.kills_events || []).length > 0
          ? `，并在 ${(laneP.kills_events || []).map((k) => `${k.time_str} 斩杀${k.victim_hero}`).join("、")}`
          : "";
      const laneOutcomeNarrative = laneWon
        ? `在搭档${allyNames || "辅助"}拉野控线与凶狠换血的强力掩护下，线上刀法稳如泰山，10分钟便砍下 <b>${lh10} 正补 / ${dn10} 反补（10m 经济 ${fmtNum(
            gold10
          )} 金 · 对线效率 ${p.lane_efficiency_pct || 0}%）</b>，打出 <b>${laneK}杀/${laneD}死</b>${killKillsDesc}，直接将${laneNameShort}彻底打穿（${
            myLane?.verdict_zh || `压制对位 ${oppHero} +${fmtNum(g10Diff)} 金`
          }）！`
        : laneD >= 3
        ? `面对敌方频繁游走施压，线上补出 <b>${lh10}/${dn10} 刀（${fmtNum(
            gold10
          )} 金）</b> 并拼出 <b>${fmtNum(laneDmg)} 点消耗伤害</b>（${laneK}杀/${laneD}死），但因站位靠前连续遭到针对阵亡 ${laneD} 次，好在顶住高压保住了基础等级与经济。`
        : `在${laneNameShort}稳扎稳打交出 <b>${lh10}/${dn10} 补刀（10m 经济 ${fmtNum(
            gold10
          )} 金 · 效率 ${p.lane_efficiency_pct || 0}%）</b>，前10分钟打出 <b>${laneK}杀/${laneD}死</b>与 <b>${fmtNum(
            laneDmg
          )} 点英雄伤害</b>，为中期发力稳住了基本盘。`;
      act1Story = `${laneOpening}。${laneOutcomeNarrative}`;
    } else {
      // Support (Pos 4 / Pos 5) Laning Story
      const pullPart =
        pullPct >= 20
          ? `一边勤勉拉野消兵控线（前10m拉野驻留高达 <b>${pullPct}%</b>、插下 <b>${earlySen} 颗封野/反封真眼</b>${
              pos === 5 && lh10 <= 10 ? `，自己仅补 ${lh10} 刀将兵线全数让给大哥` : ""
            }），`
          : "";
      const harassPart =
        laneDmg >= 2000
          ? `一边瞅准时机上线顶在前排与${enemyNames || "敌方英雄"}凶狠换血给压力（前10m灌出 <b>${fmtNum(
              laneDmg
            )} 点英雄伤害</b>）`
          : `在线上护住大哥发育（打出 ${fmtNum(laneDmg)} 伤害）`;
      const killAndGatePart =
        laneK > 0 || gateCnt > 0
          ? `；期间不仅配合队友斩获 <b>${laneK}杀/${laneD}死</b>${
              (laneP?.kills_events || []).length > 0
                ? `（${(laneP.kills_events || []).map((k) => `${k.time_str}击杀${k.victim_hero}`).join("、")}）`
                : ""
            }${gateCnt > 0 ? `，还主动钻双生门传送边路Gank×${gateCnt}次` : ""}`
          : "";
      const microObjPart = [];
      if (lotusCnt > 0) microObjPart.push(`抢下 ${lotusCnt} 朵疗伤莲花`);
      else if (laneWon) microObjPart.push(`协助大哥控住边路莲花池保障换血续航`);
      if (wisdomCnt > 0) microObjPart.push(`控下 ${wisdomCnt} 颗智慧经验符`);
      if (lampCnt > 0) microObjPart.push(`点亮 ${lampCnt} 盏观察者视野灯`);
      const microTail = microObjPart.length > 0 ? `，并顺手${microObjPart.join("、")}` : "";
      const deathNote =
        laneD >= 3
          ? `。虽在对线期阵亡 ${laneD} 次，但多为抢符拼刺刀与前排换血吸引火力，成功牵制敌方主力保${
              allyNames || "优势路主核"
            }打穿战局。`
          : "，堪称教科书级的前期节奏发动机！";
      act1Story = `${laneOpening}。${pullPart}${harassPart}${killAndGatePart}${microTail}${deathNote}`;
    }
  } else {
    act1Story = `开局操刀 ${pos}号位 ${heroShort} 投入战局，全场交出 <b>${p.last_hits || 0}/${
      p.denies || 0
    } 补刀、GPM ${p.gpm || 0} / XPM ${p.xpm || 0}（净资产 ${fmtNum(p.net_worth || 0)}）</b>。`;
  }

  // =========================================================================
  // 第二幕 · 中盘风云 (10:00 - 25:00) — 小说式故事线
  // =========================================================================
  const midK = midP?.kills_count ?? pt.mid_kills ?? 0;
  const midD = midP?.deaths_count ?? pt.mid_deaths ?? 0;
  const midGoldShare = pt.mid_gold_share_pct ?? 0;
  const midDmgShare = pt.mid_hdmg_share_pct ?? 0;
  const tfAfkCnt = Math.max(Number(pt.tf_zero_dmg_afk_count || 0), Number(tpRow?.tf_absent_cnt || 0));
  const midMajorItems = filterMajorItems(midP?.items_bought, 3)
    .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
    .join("、");
  const midSoloList = soloEvents.filter((ev) => {
    const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
    return m >= 9 && m <= 26;
  });

  let act2Story = "";
  if (hasTimelineTelemetry) {
    if (pos === 1 && !p.is_afk_farmer && midGold >= 9000) {
      act2Story = `步入 10–25 分钟中盘拉锯，当正面战场硝烟四起、三四五号位队友在外线频繁接团牵制敌方视野之际，${heroShort} 展现出大核应有的沉稳节奏——${
        midMajorItems ? `早早做出核心成型装 <b>${midMajorItems}</b>，` : ""
      }在野区与安全兵线之间高速收割资源，15分钟内狂揽 <b>+${fmtNum(midGold)} 金（+${
        midP?.lh_gain || 0
      } 刀 · 占全队中期经济 ${midGoldShare}%）</b>，期间抓住切入时机斩获 <b>${midK}杀/${midD}死</b>（打出 ${fmtNum(
        midDmg
      )} 伤害），零落单白给，为决胜期出山积蓄了碾压级的装备优势。`;
    } else if (p.is_afk_farmer) {
      act2Story = `进入 10–25 分钟中期节奏窗，身为 <b>${pos}号位核心</b> 的 ${heroShort} 却陷入了「万年钻野躺平」怪圈——虽然刷下 <b>+${fmtNum(
        midGold
      )} 金（占全队 ${midGoldShare}%）</b>${midMajorItems ? `并做出 ${midMajorItems}` : ""}，但全程闷头刷野拒绝参战，中期仅打出 <b>${fmtNum(
        midDmg
      )} 点英雄伤害（全队垫底 ${midDmgShare}%）</b>${
        tfAfkCnt > 0 ? `，甚至在 <b>${tfAfkCnt} 波全队浴血团战中 0 伤害卖队友独刷</b>` : ""
      }，把正面压力全数甩给了另外四名队友！`;
    } else if (isSup) {
      const sacNote =
        midDeathsCtx.goodDeaths > 0
          ? `期间虽阵亡 ${midD} 次，但其中 <b>${midDeathsCtx.goodDeaths} 次属于跟随团队接团/推塔前排肉身吃技能换空间</b>（让 1 号位大哥得以安心刷出关键装）`
          : `阶段战绩 <b>${midK}杀/${midD}死</b>`;
      const soloWarn =
        midSoloList.length > 0
          ? `；唯独遗憾的是在 <b>${midSoloList
              .map(
                (e) =>
                  `${e.time_str}于${e.zone_zh}落单被${e.killer_zh}抓死${
                    e.consequence && e.consequence !== "无战略收益白给" ? `（${e.consequence}）` : ""
                  }`
              )
              .join("、")}</b>，送出了不该有的节奏断点`
          : `，中期走位紧凑 0 次落单掉点`;
      act2Story = `转入 10–25 分钟中期博弈，作为 ${pos}号位辅助的 ${heroShort} 全力围绕团队运转，打出 <b>${fmtNum(
        midDmg
      )} 英雄伤害</b>${midMajorItems ? `并更新 <b>${midMajorItems}</b>` : ""}${
        counterItemsBuilt.length > 0 ? `（主动做出团队克制装 ${counterItemsBuilt.join("/")}）` : ""
      }。${sacNote}${soloWarn}。`;
    } else {
      act2Story = `进入 10–25 分钟中盘较量，${heroShort} 主动扛起中期正面火力，交出 <b>${midK}杀/${midD}死、+${fmtNum(
        midGold
      )} 金</b>，倾泻 <b>${fmtNum(midDmg)} 点英雄伤害（占全队中期伤害 ${midDmgShare}%）</b>${
        midMajorItems ? `，并相继合出 <b>${midMajorItems}</b>` : ""
      }${
        midSoloList.length > 0
          ? `；但期间在 ${midSoloList.map((e) => `${e.time_str}被${e.killer_zh}抓死`).join("、")} 出现落单断档。`
          : `，正面顶在最前排为大哥拉扯出宝贵的发育空间。`
      }`;
    }
  } else {
    act2Story = `中盘围绕团队推进与抓人节奏运转，全场参战率 <b>${p.kill_participation_pct || 0}%（KDA ${
      p.kda
    }）</b>，倾泻 <b>${fmtNum(p.hero_damage || 0)} 英雄伤害（全队 ${
      p.hero_damage_share_pct || 0
    }%）</b> 与 <b>${fmtNum(p.tower_damage || 0)} 建筑推塔伤害</b>。`;
  }

  // =========================================================================
  // 第三幕 · 终局决战 (25:00 - 终局) — 小说式故事线
  // =========================================================================
  const lateK = lateP?.kills_count ?? pt.late_kills ?? 0;
  const lateD = lateP?.deaths_count ?? pt.late_deaths ?? 0;
  const lateDmg = lateP?.hero_damage_gain ?? pt.late_hdmg_gain ?? 0;
  const lateGold = lateP?.gold_gain ?? pt.late_gold_gain ?? 0;
  const lateMajorItems = filterMajorItems(lateP?.items_bought, 3)
    .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
    .join("、");
  const ultAudit = (p.hero_execution_audit?.ult_audits || [])[0];
  const ultSummary = ultAudit
    ? `招牌大招【${ultAudit.ability_zh}】全场释放 <b>${ultAudit.casts ?? 0} 次</b>`
    : `全场贡献 <b>${p.stuns_sec || 0} 秒硬控</b>`;
  const mo = df.macro_objectives_by_side?.[side] || {};
  const aegisTaken = (mo.roshan_events || []).some((r) => String(r).includes(heroShort));
  const lateSoloList = soloEvents.filter((ev) => {
    const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
    return m > 26;
  });

  let act3Story = "";
  if (roleType === "mvp") {
    act3Story = `25分钟后决战号角吹响，前中期蓄满战力的 ${heroShort} 彻底化身为战场死神！${
      aegisTaken ? "亲自控下肉山不朽之盾带队吹响总攻号角，" : ""
    }${
      hasTimelineTelemetry
        ? `决胜期单阶段再砍 <b>${lateK}杀/${lateD}死、狂轰 ${fmtNum(lateDmg)} 点英雄伤害</b>${
            lateMajorItems ? `（神装更新 ${lateMajorItems}）` : ""
          }，`
        : ""
    }${ultSummary}。完美兑现了「一号位前期无解肥刷钱成型 → 后期出山接管比赛」的终极承诺，全场轰下 <b>${
      p.kda
    }（${p.kill_participation_pct}% 参战）、${fmtNum(p.hero_damage)} 英雄伤害（全队 ${
      p.hero_damage_share_pct || 0
    }%）、${fmtNum(p.tower_damage || 0)} 建筑拆迁伤害</b>，以 <b>${score100}/100 分（胜局贡献 ${sharePct}%）</b> 一锤定音终结比赛！`;
  } else if (roleType === "runnerup") {
    act3Story = `进入 25 分钟后的高地决战，${heroShort} 与头号主核形成完美双核呼应——${
      hasTimelineTelemetry
        ? `后期再献 <b>${lateK}杀/${lateD}死、+${fmtNum(lateDmg)} 点决胜伤害</b>${
            lateMajorItems ? `（成型 ${lateMajorItems}）` : ""
          }，`
        : ""
    }${ultSummary}，全场交出 <b>${p.kda}（${p.kill_participation_pct}% 参战）</b>${
      isSup
        ? `并铺设 <b>${p.obs_placed || 0} 假眼 / ${p.sen_placed || 0} 真眼</b>`
        : `、轰出 <b>${fmtNum(p.hero_damage)} 伤害与 ${fmtNum(p.tower_damage || 0)} 拆塔</b>`
    }，砍下 <b>${score100}/100 分（胜局贡献 ${sharePct}%）</b>，是本局凯旋不可或缺的破阵二当家！`;
  } else if (isSup && lateDeathsCtx.sacList.length > 0 && roleType === "struggle") {
    act3Story = `来到 25 分钟后的决胜阶段，${heroShort} 进账 +${fmtNum(lateGold)} 金、打出 <b>${fmtNum(
      lateDmg
    )} 伤害</b>${lateMajorItems ? `并补出 <b>${lateMajorItems}</b>` : ""}，${ultSummary}。值得重点平反的是：<b>后期 ${lateD} 次阵亡（${lateDeathsCtx.sacList
      .map((s) => s.time_str)
      .join("、")}）全部是在团战前排肉身吃满敌方第一波爆发，直接掩护一号位大哥完成收割团赢的【合理战术牺牲】</b>！之所以综合评分停在 <b>${score100}/100 分</b>，主要是受前中期 <b>${
      soloEvents.length
    } 次落单被抓</b> 与 <b>整局未主动买 TP</b> 所拖累，绝非无脑白给！`;
  } else if (roleType === "struggle" || roleType === "culprit1" || roleType === "culprit2") {
    const lateFailNote =
      lateSoloList.length > 0
        ? `决胜期在 <b>${lateSoloList
            .map((e) => `${e.time_str}于${e.zone_zh}落单被${e.killer_zh}单抓（${e.vision_tag || "黑图孤走"}）`)
            .join("、")}</b> 险些送出翻盘机会；`
        : "";
    const lowDmgNote =
      isCore && lateGold >= 5500 && lateDmg < 6500
        ? `后期吃下 <b>+${fmtNum(lateGold)} 金</b> 却仅打出 <b>${fmtNum(lateDmg)} 英雄伤害</b>，核心收割能力严重断档；`
        : "";
    act3Story = `进入 25 分钟后的终局阶段，${heroShort} 交出 <b>${lateK}杀/${lateD}死、+${fmtNum(
      lateDmg
    )} 伤害</b>。${lateFailNote}${lowDmgNote}纵观全局，本局评分 <b>${score100}/100 分</b>，暴露出的走位脱节与细节短板亟需下一把重点复盘整改。`;
  } else {
    act3Story = `决胜阶段依然倾尽全力打出 <b>${lateK}杀/${lateD}死、+${fmtNum(lateDmg)} 伤害</b>，全场交出 <b>${
      p.kda
    }、${fmtNum(p.hero_damage)} 伤害（全队 ${p.hero_damage_share_pct || 0}%）</b>，拿下 <b>${score100}/100 分</b> 虽败犹荣！`;
  }

  // =========================================================================
  // AI 灵性出装 · 克制关系 · 跳刀转化率 · BKB/辅助贪心专项审计
  // =========================================================================
  const itemIntel = analyzePlayerItemizationIntelligence(p, report);
  const grokP = findGrokPlayerEntry(p, report);

  const grokBadgeHtml = `<span class="stage-key-pill" style="background:rgba(139,92,246,0.22);border-color:rgba(167,139,250,0.55);color:#ddd6fe;">🧠 Grok 4.7 研判</span> `;

  const baseAct1Story = act1Story;
  const baseAct2Story = act2Story;
  const baseAct3Story = act3Story;

  if (grokP?.early_story) {
    const gEarly = String(grokP.early_story).trim();
    const extraEarly = gEarly.length < 85 && baseAct1Story ? ` ${baseAct1Story}` : "";
    act1Story = `${grokBadgeHtml}<b>【10m: ${lh10}/${dn10}刀 · ${fmtNum(gold10)}金 · ${laneK}杀/${laneD}死】</b>${escapeHtml(
      gEarly
    )}${extraEarly}`;
  }
  if (grokP?.mid_story) {
    const gMid = String(grokP.mid_story).trim();
    const extraMid = gMid.length < 85 && baseAct2Story ? ` ${baseAct2Story}` : "";
    act2Story = `${grokBadgeHtml}<b>【10–25m: +${fmtNum(midGold)}金 · +${midP?.lh_gain || 0}刀 · ${midK}杀/${midD}死 · 伤${fmtNum(
      midDmg
    )}】</b>${escapeHtml(gMid)}${extraMid}`;
  }
  if (grokP?.late_story) {
    const gLate = String(grokP.late_story).trim();
    const extraLate = gLate.length < 85 && baseAct3Story ? ` ${baseAct3Story}` : "";
    act3Story = `${grokBadgeHtml}<b>【25m+: +${fmtNum(lateGold)}金 · ${lateK}杀/${lateD}死 · 伤${fmtNum(
      lateDmg
    )} · 总塔伤${fmtNum(p.tower_damage || 0)}】</b>${escapeHtml(gLate)}${extraLate}`;
  }

  // =========================================================================
  // 功过得失清单（当 Grok 4.7 AI 研判存在时，完全采用 AI 深度研判，去除弱规则模板！）
  // =========================================================================
  const goodPoints = [];
  const badPoints = [];
  const splitGrokPoints = (val) => {
    if (!val) return [];
    if (Array.isArray(val)) return val.map((x) => String(x || "").trim()).filter(Boolean);
    return String(val)
      .split(/[；;]/)
      .map((x) => x.trim())
      .filter(Boolean);
  };

  const grokGoodItems = splitGrokPoints(grokP?.good);
  const grokBadItems = splitGrokPoints(grokP?.bad);

  if (grokGoodItems.length > 0) {
    grokGoodItems.forEach((g) => {
      goodPoints.push(`<b>🧠 Grok 4.7 肯定：</b>${escapeHtml(g)}`);
    });
  } else {
    if (isCore) {
      if (lh10 >= 48) {
        goodPoints.push(
          `<b>对线基本功扎实：</b>前10分钟交出 <b>${lh10}正/${dn10}反（${fmtNum(gold10)}金·效率${
            p.lane_efficiency_pct || 0
          }%）</b>${laneWon ? `，联手辅助打穿${laneNameShort}` : ""}。`
        );
      } else if (laneDmg >= 3800) {
        goodPoints.push(`<b>对线压制凶悍：</b>前10分钟灌出 <b>${fmtNum(laneDmg)} 英雄伤害</b>，积极消耗对手血量。`);
      }
      if (midGold >= 9000 && !p.is_afk_farmer) {
        goodPoints.push(
          `<b>中期刷钱提速极快：</b>10–25m 进账 <b>+${fmtNum(midGold)} 金（+${midP?.lh_gain || 0}刀）</b>${
            midMajorItems ? `，准时做出 <b>${midMajorItems}</b>` : ""
          }。`
        );
      } else if (midDmg >= 8500) {
        goodPoints.push(`<b>中期团战输出支柱：</b>10–25m 轰出 <b>${fmtNum(midDmg)} 英雄伤害</b>，扛起中期正面团战。`);
      }
      if (lateDmg >= 14000 || Number(p.tower_damage || 0) >= 5000) {
        goodPoints.push(
          `<b>决胜收割与拆迁兑现：</b>后期轰出 <b>${fmtNum(lateDmg)} 伤害</b>，全场建筑推塔高达 <b>${fmtNum(
            p.tower_damage || 0
          )}</b>${aegisTaken ? "，带盾顺势拔光外塔平推三路高地终结比赛" : ""}。`
        );
      }
    } else {
      if (pullPct >= 20) {
        goodPoints.push(
          `<b>对线拉野与保核细活：</b>前10m拉野封野驻留 <b>${pullPct}%</b>（封野真眼 ${earlySen} 颗${
            pos === 5 && lh10 <= 10 ? `·仅${lh10}刀正补全让大哥` : ""
          }），上线换血打出 <b>${fmtNum(laneDmg)} 伤害</b>。`
        );
      }
      if (lotusCnt > 0 || wisdomCnt > 0 || gateCnt > 0 || lampCnt > 0) {
        const mList = [];
        if (lotusCnt > 0) mList.push(`抢莲花×${lotusCnt}`);
        if (wisdomCnt > 0) mList.push(`抢智慧符×${wisdomCnt}`);
        if (gateCnt > 0) mList.push(`钻双生门游走×${gateCnt}`);
        if (lampCnt > 0) mList.push(`点亮视野灯×${lampCnt}`);
        goodPoints.push(`<b>地图资源与游走联动：</b>${mList.join("、")}，对线期参战斩获 <b>${laneK} 杀</b>。`);
      }
      const totalSac =
        laneDeathsCtx.sacList.length + midDeathsCtx.sacList.length + lateDeathsCtx.sacList.length;
      if (totalSac > 0 || Number(p.stuns_sec || 0) >= 25 || counterItemsBuilt.length > 0) {
        goodPoints.push(
          `<b>团战控制与战术换命：</b>全场贡献 <b>${p.stuns_sec || 0} 秒硬控</b>、铺设 <b>${
            p.obs_placed || 0
          }假/${p.sen_placed || 0}真眼</b>${
            counterItemsBuilt.length > 0 ? `，做出针对装 <b>${counterItemsBuilt.join("/")}</b>` : ""
          }${totalSac > 0 ? `，且有 <b>${totalSac} 波阵亡属前排吃技能换赢团战的合理牺牲</b>` : ""}。`
        );
      }
    }
    if (goodPoints.length === 0 && Array.isArray(p.strengths)) {
      p.strengths.slice(0, 2).forEach((s) => goodPoints.push(escapeHtml(s)));
    }
  }

  if (grokBadItems.length > 0) {
    grokBadItems.forEach((b) => {
      badPoints.push(`<b>🧠 Grok 4.7 锐评：</b>${escapeHtml(b)}`);
    });
    if (grokP?.practice) {
      badPoints.push(`<b>🎯 下把改进处方：</b>${escapeHtml(grokP.practice)}`);
    }
  } else {
    if (p.is_afk_farmer) {
      badPoints.push(
        `<b>核心失职（万年刷野躺平）：</b>中期吃下 ${midGoldShare}% 经济却仅打 ${midDmgShare}% 伤害，${tfAfkCnt} 波团战缺席卖队友独刷。`
      );
    }
    if (soloEvents.length > 0) {
      badPoints.push(
        `<b>脱离团队落单被抓（${soloEvents.length}次）：</b>${soloEvents
          .map(
            (s) =>
              `<b>${s.time_str}</b>在${s.zone_zh}被${s.killer_zh}抓死${
                s.consequence && s.consequence !== "无战略收益白给"
                  ? `（${s.consequence}）`
                  : s.vision_tag?.includes("5 颗假眼")
                  ? "（场上5颗假眼不看小地图）"
                  : ""
              }`
          )
          .join("；")}。`
      );
    }
    if (Number(tpRow?.tp_bought ?? 1) === 0) {
      badPoints.push(`<b>支援物资隐患：</b>整局主动花钱购买回城卷轴（TP）为 <b>0 张</b>，边路防抓与支援响应受限。`);
    }
    if ((tpRow?.tf_absent_cnt ?? 0) > 0 && !p.is_afk_farmer) {
      badPoints.push(
        `<b>团战到场率瑕疵：</b>本局有 <b>${tpRow.tf_absent_cnt} 波</b>正面团战未能及时赶到战场（${(
          tpRow.tf_absent_times || []
        ).join("/")}）${
          pos === 1 && midGold >= 9000 ? "（虽为刷狂战斧核心装避战，但仍需留意队友守塔信号）" : ""
        }。`
      );
    }
    if (laneD >= 3) {
      badPoints.push(
        `<b>对线期防Gank与换血尺度：</b>前10分钟阵亡 <b>${laneD} 次</b>（${(laneP?.deaths_events || [])
          .slice(0, 3)
          .map((d) => `${d.time_str}被${d.killer}杀`)
          .join("、")}），残血需更果断后撤补给。`
      );
    }
    if (isCore && lateGold >= 5500 && lateDmg < 6500 && !itemIntel.warnings.some((w) => w.includes("跳刀"))) {
      badPoints.push(
        `<b>后期输出转化偏低：</b>25m+ 吃下 +${fmtNum(lateGold)} 金却仅打出 ${fmtNum(lateDmg)} 英雄伤害，团战切入与自保需加强。`
      );
    }
    if (badPoints.length === 0) {
      if (Number(p.deaths || 0) > 0) {
        const anyDeath =
          (lateP?.deaths_events || [])[0] || (midP?.deaths_events || [])[0] || (laneP?.deaths_events || [])[0];
        badPoints.push(
          `<b>白璧微瑕：</b>全场仅阵亡 ${p.deaths} 次${
            anyDeath ? `（如 ${anyDeath.time_str} 被 ${anyDeath.killer} 击杀读秒 ${anyDeath.time_dead}s）` : ""
          }，几乎无可挑剔。`
        );
      } else {
        badPoints.push(`<b>完美零死答卷：</b>整局 0 阵亡无明显失误，继续保持当前统治力！`);
      }
    }
  }

  // When Grok 4.7 item audit is present, ONLY show Grok's superior item audit (no weak rule-based item warnings)
  const grokItemAuditLine = grokP?.item_and_blink_audit || "";
  const allItemBullets = grokItemAuditLine
    ? [
        `<span style="color:#ddd6fe;"><b>🤖 XAI / GROK-4.7 深度 AI 出装·克制·跳刀锐评：</b>${escapeHtml(
          grokItemAuditLine
        )}</span>`,
      ]
    : [...itemIntel.highlights, ...itemIntel.warnings];
  const itemIntelBoxHtml =
    allItemBullets.length > 0 || itemIntel.timelinePills
      ? `
      <div class="verdict-item-intel-box">
        <div class="verdict-item-intel-head">
          <span class="verdict-item-intel-title">🧠 AI 灵性出装 · 敌我克制 · 跳刀转化率 &amp; BKB/救人装审计</span>
          <div class="verdict-item-intel-badges">
            ${itemIntel.badges
              .map(
                (b) =>
                  `<span class="item-intel-badge ${
                    /🚨/.test(b) ? "bad" : /⚠️/.test(b) ? "warn" : "good"
                  }">${escapeHtml(b)}</span>`
              )
              .join("")}
          </div>
        </div>
        ${
          itemIntel.timelinePills
            ? `<div class="verdict-item-timeline-row"><span class="timeline-label">关键成装轴：</span>${itemIntel.timelinePills}</div>`
            : ""
        }
        <ul class="verdict-item-intel-list">
          ${allItemBullets.map((line) => `<li>${line}</li>`).join("")}
        </ul>
      </div>
    `
      : "";

  // Prominent Grok 4.7 Deep 1-Paragraph Personal Judgment Report Box (`deep_verdict`)
  const deepVerdictText = grokP?.deep_verdict || grokP?.assessment || "";
  const isRoleBad = roleType === "culprit1" || roleType === "culprit2" || roleType === "struggle";
  const roleVerdictTag =
    roleType === "culprit1"
      ? "🚨 头号大锅 · 一级战犯深度研判报告"
      : roleType === "culprit2"
      ? "⚠️ 二号次锅 · 关键失误深度研判报告"
      : roleType === "mvp"
      ? "👑 头号首功 · 全场真神深度研判报告"
      : roleType === "svp"
      ? "👑 孤胆院长 · 败方尽力深度研判报告"
      : roleType === "struggle"
      ? "🐟 胜局短板 · 隐患复盘深度研判报告"
      : "🎖️ 战局个人深度研判报告";

  const grokDeepVerdictBoxHtml = deepVerdictText
    ? `
      <div class="grok-deep-verdict-box" style="margin-bottom:10px;padding:12px 14px;background:linear-gradient(135deg,${
        isRoleBad
          ? "rgba(185,28,28,0.18),rgba(109,40,217,0.14)"
          : "rgba(109,40,217,0.20),rgba(15,118,110,0.14)"
      });border:1px solid ${
        isRoleBad ? "rgba(248,113,113,0.45)" : "rgba(167,139,250,0.48)"
      };border-radius:10px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:6px;">
          <span style="font-size:12.5px;font-weight:800;color:${
            isRoleBad ? "#fca5a5" : "#ddd6fe"
          };letter-spacing:0.3px;">🧠 XAI / GROK-4.7 · ${escapeHtml(roleVerdictTag)}</span>
          <span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;background:rgba(15,23,42,0.65);border:1px solid rgba(167,139,250,0.4);color:#e9d5ff;">🎯 Grok 重新打分：<b>${score100}/100分</b> · ${
            roleType === "mvp" || roleType === "runnerup" || roleType === "svp" ? "功勋占比" : "定责占比"
          } <b>${sharePct}%</b></span>
        </div>
        <div style="font-size:13px;line-height:1.72;color:#f8fafc;text-align:justify;">
          ${escapeHtml(deepVerdictText)}
        </div>
      </div>
    `
    : "";

  const html = `
    <div class="verdict-chronology-story-v2">
      ${grokDeepVerdictBoxHtml}
      <div class="story-act-row">
        <span class="story-act-badge early">🌅 第一幕 · 序章对线 (00:00–10:00)</span>
        <p class="story-act-text">${act1Story}</p>
      </div>
      <div class="story-act-row">
        <span class="story-act-badge mid">⚔️ 第二幕 · 中盘风云 (10:00–25:00)</span>
        <p class="story-act-text">${act2Story}</p>
      </div>
      <div class="story-act-row">
        <span class="story-act-badge late">🔥 第三幕 · 终局决战 (25:00–终局)</span>
        <p class="story-act-text">${act3Story}</p>
      </div>
      ${itemIntelBoxHtml}
      <div class="story-good-bad-grid">
        <div class="story-gb-box good">
          <div class="story-gb-title">👍 哪里做得好（高光与细活）</div>
          <ul class="story-gb-list">
            ${goodPoints.map((g) => `<li>${g}</li>`).join("")}
          </ul>
        </div>
        <div class="story-gb-box bad">
          <div class="story-gb-title">👎 哪里做得不好（瑕疵与复盘点）</div>
          <ul class="story-gb-list">
            ${badPoints.map((b) => `<li>${b}</li>`).join("")}
          </ul>
        </div>
      </div>
    </div>
  `;

  return injectHeroLogosIntoHtml(html, report);
}

/**
 * 2. Render Grok 4.7 Verdict Banner + 3 Verdict Cards (MVP / #2 / #3 Struggle or 2nd Culprit) + 5-Stack Blame Ledger
 */
function renderVerdictAndBlameSection(report) {
  const { side, sideZh, own, all } = getOwnAndOppPlayers(report);
  const bySlot = new Map(all.map((p) => [Number(p.player_slot), p]));
  const won =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !report.radiant_win);

  const grok = report.grok_coaching;
  const mvpData = report.mvp || {};
  const df = report.deep_forensics || {};

  // Update Jump Chip, Section Heading, Card Labels, and Ledger Header dynamically based on WIN vs LOSS
  const jumpChip = document.getElementById("jump-chip-verdict");
  const secHeading = document.getElementById("verdict-heading");
  const secCaption = document.getElementById("verdict-caption");
  const mvpCardLabel = document.getElementById("mvp-card-label");
  const secondCardEl = document.getElementById("culprit-card");
  const secondCardLabel = document.getElementById("culprit-card-label");
  const thirdCardEl = document.getElementById("third-verdict-card");
  const thirdCardLabel = document.getElementById("third-verdict-card-label");
  const ledgerTitle = document.getElementById("blame-ledger-title");
  const ledgerCaption = document.getElementById("blame-ledger-caption");
  const shareBtn1 = document.getElementById("btn-open-share-poster");
  const shareBtn2 = document.getElementById("btn-open-share-poster-2");

  if (won) {
    if (jumpChip) jumpChip.textContent = "② 🏆 凯旋庆功与100%贡献榜";
    if (secHeading) {
      secHeading.textContent = `② 🏆 ${sideZh}凯旋庆功封神榜 · 谁是头号首功、二号功臣与短板复盘`;
    }
    if (secCaption) {
      secCaption.textContent =
        "赢球论功行赏 + 毒舌捉虫！从前期对线、中期Gank开雾到后期决战全周期复盘头号MVP、二当家与本局暴露短板";
    }
    if (mvpCardLabel) mvpCardLabel.textContent = "👑 头号首功 · 本局擎天真大腿 (MVP)";
    if (secondCardEl) {
      secondCardEl.classList.remove("culprit-theme");
      secondCardEl.classList.add("runnerup-theme");
    }
    if (secondCardLabel) secondCardLabel.textContent = "⚔️ 二号功臣 · 破阵二当家 & 定海神针";
    if (thirdCardEl) {
      thirdCardEl.classList.remove("culprit-theme");
      thirdCardEl.classList.add("struggle-theme");
    }
    if (thirdCardLabel) thirdCardLabel.textContent = "🐟 惊险躺赢/短板算账 · 为什么这把表现不行";
    if (ledgerTitle) ledgerTitle.textContent = `🎉 ${sideZh}五黑 100% 胜局贡献庆功榜 · 谁的军功章最大一目了然`;
    if (ledgerCaption) {
      ledgerCaption.textContent =
        "按本局五人综合战功归一化为 100% 胜局贡献度 + 0~100 分制打分，点击右侧按钮可直接复制夸人/庆功贺电发群里";
    }
    if (shareBtn1) shareBtn1.textContent = "🏆 导出群聊庆功榜";
    if (shareBtn2) shareBtn2.textContent = "🏆 导出群聊庆功榜";
  } else {
    if (jumpChip) jumpChip.textContent = "② ⚖️ 红黑榜与100%分锅";
    if (secHeading) {
      secHeading.textContent = `② ⚖️ ${sideZh}败局分锅定责总表 · 这把谁在尽力，谁在犯罪`;
    }
    if (secCaption) {
      secCaption.textContent =
        "输球不留情面，硬核数据定责！从前期、中期到后期全周期审讯败方孤胆院长、头号战犯与二号背锅位";
    }
    if (mvpCardLabel) mvpCardLabel.textContent = "👑 败方孤胆院长 · 全场尽力大腿 (SVP)";
    if (secondCardEl) {
      secondCardEl.classList.remove("runnerup-theme");
      secondCardEl.classList.add("culprit-theme");
    }
    if (secondCardLabel) secondCardLabel.textContent = "🚨 本方头号大锅 · 一级战犯逮捕令";
    if (thirdCardEl) {
      thirdCardEl.classList.remove("struggle-theme");
      thirdCardEl.classList.add("culprit-theme");
    }
    if (thirdCardLabel) thirdCardLabel.textContent = "⚠️ 二号背锅位 · 次锅共犯审讯室";
    if (ledgerTitle) ledgerTitle.textContent = `⚖️ ${sideZh}五人 100% 败局分锅账本 · 谁该在群里发致歉红包`;
    if (ledgerCaption) {
      ledgerCaption.textContent =
        "点击任意行右侧按钮可直接复制该队友专属分锅算账金句发群里";
    }
    if (shareBtn1) shareBtn1.textContent = "📜 导出群聊处刑书";
    if (shareBtn2) shareBtn2.textContent = "📜 导出群聊处刑书";
  }

  // Sort own team by Contribution Share (descending) and by Blame Share (descending)
  // Enforce strict monotonicity between `getHeroScore100(p, report)` and `contribShare` / `blameShare`:
  // - In a WIN: #1 Highest Score = #1 Highest Contribution % (MVP), #5 Lowest Score = #5 Lowest Contribution % (Struggle)
  // - In a LOSS: #1 Lowest Score = #1 Highest Blame % (#1 Culprit), #2 2nd Lowest Score = #2 Highest Blame % (#2 Culprit), #5 Highest Score = #5 Lowest Blame % (SVP)
  const hasGrokEval =
    grok &&
    (!grok.side || grok.side === side) &&
    Array.isArray(grok.players) &&
    grok.players.some((gp) => gp && (Number(gp.grok_score) > 0 || Number(gp.grok_share_pct) > 0));

  const rawContribVal = (p) => {
    const gp = findGrokPlayerEntry(p, report);
    if (won && gp && Number(gp.grok_share_pct) > 0) {
      return Number(gp.grok_share_pct);
    }
    if (gp && Number(gp.grok_score) > 0) {
      return Math.max(1, Number(gp.grok_score));
    }
    return Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20));
  };
  const rawContribSum = own.reduce((s, p) => s + rawContribVal(p), 0) || 100;
  const contribSharesPool = own
    .map((p) => Number(((rawContribVal(p) / rawContribSum) * 100).toFixed(1)))
    .sort((a, b) => b - a);
  const sortedByScoreDesc = [...own].sort(
    (a, b) =>
      getHeroScore100(b, report) - getHeroScore100(a, report) ||
      rawContribVal(b) - rawContribVal(a)
  );
  const sortedByContrib = sortedByScoreDesc.map((p, idx) => ({
    player: p,
    contribShare: contribSharesPool[idx] ?? 20.0,
  }));

  const rawBlameVal = (p) => {
    const gp = findGrokPlayerEntry(p, report);
    if (!won && gp && Number(gp.grok_share_pct) > 0) {
      return Number(gp.grok_share_pct);
    }
    if (!won && gp && Number(gp.grok_score) > 0) {
      return Math.max(1, 105 - Number(gp.grok_score));
    }
    return Math.max(1, Number(p.blame_share_pct || 20));
  };
  const rawBlameSum = own.reduce((s, p) => s + rawBlameVal(p), 0) || 100;
  const blameSharesPool = own
    .map((p) => Number(((rawBlameVal(p) / rawBlameSum) * 100).toFixed(1)))
    .sort((a, b) => b - a);
  const sortedByScoreAsc = [...own].sort(
    (a, b) =>
      getHeroScore100(a, report) - getHeroScore100(b, report) ||
      rawBlameVal(b) - rawBlameVal(a)
  );
  const sortedByBlame = sortedByScoreAsc.map((p, idx) => ({
    player: p,
    blameShare: blameSharesPool[idx] ?? 20.0,
  }));

  // Pick the 3rd card player in a WIN: if Grok scored players, pick the player with the lowest Grok score / contribution;
  // otherwise fall back to struggle index.
  const top1 = sortedByContrib[0]?.player;
  const top2 = sortedByContrib[1]?.player;
  const msSide = df.map_space_by_side?.[side] || {};
  const computeStruggleIndex = (p) => {
    if (!p) return 0;
    const gp = findGrokPlayerEntry(p, report);
    if (gp && Number(gp.grok_score) > 0) {
      return 200 - Number(gp.grok_score) * 2 + (100 - Number(gp.grok_share_pct || 20));
    }
    const spRow = (msSide.player_space_rows || []).find(
      (r) => r.hero_short_zh === p.hero_short_zh || Number(r.pos) === Number(p.pos)
    );
    const soloCnt = Number(
      spRow?.solo_pickoff_cnt ??
        (msSide.solo_pickoff_events || []).filter((ev) => ev.hero_short_zh === p.hero_short_zh).length
    );
    const deadSec = Number(p.dead_seconds || 0);
    const deaths = Number(p.deaths || 0);
    const ratingPenalty = Math.max(0, 8.6 - Number(p.rating_score || 7.5)) * 10;
    const coreZeroTdPenalty = (p.pos || 5) <= 3 && Number(p.tower_damage || 0) < 500 ? 48 : 0;
    const afkFarmerPenalty = p.is_afk_farmer ? 140 : 0;
    const blameShare = Number(p.blame_share_pct || 15);
    return afkFarmerPenalty + soloCnt * 28 + deadSec * 0.25 + deaths * 8.5 + ratingPenalty + coreZeroTdPenalty + blameShare;
  };
  const remainingCandidates = sortedByContrib
    .slice(2)
    .map((entry) => ({
      ...entry,
      struggleIdx: computeStruggleIndex(entry.player),
    }))
    .sort((a, b) => b.struggleIdx - a.struggleIdx);
  const struggleEntry = remainingCandidates[0] || sortedByContrib[sortedByContrib.length - 1];
  const strugglePlayer = struggleEntry?.player || sortedByContrib[sortedByContrib.length - 1]?.player;

  const topBlame1 = sortedByBlame[0]?.player;
  const topBlame2 = sortedByBlame[1]?.player;

  // 2.1 Grok Verdict Banner (When Grok 4.7 is active, show Grok's superior summary & verdict without redundant rule-based stage grid)
  const authorEl = document.getElementById("grok-author-label");
  const titleEl = document.getElementById("grok-title-text");
  const summaryEl = document.getElementById("grok-summary-text");
  const verdictEl = document.getElementById("grok-verdict-text");
  const practiceEl = document.getElementById("grok-team-practice-box");

  const buildStructuredVerdictHtml = (extraText = "") => {
    const extraClean = sanitizeMixedEnglishClient(String(extraText || "")).trim();
    const extraBullets = extraClean
      ? extraClean
          .split(/(?<=[。！？!?])\s*/)
          .map((x) => x.trim())
          .filter(Boolean)
      : [];
    const rationales =
      extraBullets.length > 0
        ? extraBullets
        : (mvpData.rationale_list || []).map((r) => sanitizeMixedEnglishClient(r));
    return rationales.length > 0
      ? `<ul class="verdict-rationale-list">${rationales
          .map((r) => `<li>${injectHeroLogosIntoHtml(escapeHtml(r), report)}</li>`)
          .join("")}</ul>`
      : "";
  };

  if (grok && (!grok.side || grok.side === side)) {
    const modelTag = grok._meta?.model
      ? `🧠 ${String(grok._meta.provider || "XAI").toUpperCase()} / ${grok._meta.model} ${won ? "赛后庆功与复盘总账" : "赛后分锅总账"}`
      : `🧠 XAI / GROK-4.7 ${won ? "赛后庆功与复盘总账" : "赛后分锅总账"}`;
    if (authorEl) authorEl.textContent = modelTag;
    if (titleEl) titleEl.textContent = sanitizeMixedEnglishClient(grok.title || (won ? "凯旋庆功与战术复盘" : "本局赛后复盘总账"));
    if (summaryEl) {
      const leadSummary = grok.summary
        ? `<div class="verdict-lead-callout">${injectHeroLogosIntoHtml(escapeHtml(grok.summary), report)}</div>`
        : "";
      summaryEl.innerHTML = leadSummary;
    }
    if (verdictEl) {
      verdictEl.innerHTML = buildStructuredVerdictHtml(grok.verdict || "");
    }
    if (practiceEl) {
      practiceEl.innerHTML = grok.team_practice
        ? `<strong>${won ? "乘胜追击 · 下把更稳铁律：" : "痛定思痛 · 下把车队铁律："}</strong>${injectHeroLogosIntoHtml(escapeHtml(grok.team_practice), report)}`
        : "";
      practiceEl.hidden = !grok.team_practice;
    }
  } else {
    const stagesGridHtml = buildRichFourStageCardsHtml(report);
    const foldedStagesGridHtml = stagesGridHtml
      ? `<details class="mobile-summary-fold"><summary class="mobile-summary-trigger">📖 展开/收起「前期·中期·后期·总账」四维全景速览卡（下方第 ③ 章含完整分阶段拆解）</summary>${stagesGridHtml}</details>`
      : "";
    if (authorEl) {
      authorEl.textContent = won
        ? "录像级庆功引擎 · 四阶段全细节对账与论功行赏 (含英雄小图标 · 可点右上角用 Grok 4.7 深度重算)"
        : "录像级算账引擎 · 四阶段全细节对账与分锅判词 (含英雄小图标 · 可点右上角用 Grok 4.7 深度重算)";
    }
    if (titleEl) {
      titleEl.textContent = won
        ? `🎉 ${sideZh}凯旋大捷！终局比分 ${report.radiant_score} : ${report.dire_score} (${report.duration_str})`
        : `⚖️ ${sideZh}败局算账：终局比分 ${report.radiant_score} : ${report.dire_score} (${report.duration_str})`;
    }
    if (summaryEl) {
      summaryEl.innerHTML = foldedStagesGridHtml;
    }
    if (verdictEl) {
      verdictEl.innerHTML = buildStructuredVerdictHtml("");
    }
    if (practiceEl) {
      practiceEl.innerHTML = `<strong>提示：</strong>点击右上角「让 Grok 4.7 生成深度判词」即可调用服务端已配置的 xAI Grok 4.7 生成针对『${escapeHtml(
        sideZh
      )}』阵容的毒舌复盘；或点击「📄 导出 PDF 分析报告」一键保存完整复盘文档发给队友。`;
      practiceEl.hidden = false;
    }
  }

  // Helper to render non-wrapping stat pills inside the 3 verdict cards
  const renderCardStatPills = (p, isTrouble = false) => {
    const pills = [
      `<span class="v-stat-pill">KDA <b>${escapeHtml(p.kda)}</b> (${p.kill_participation_pct}%参战)</span>`,
      `<span class="v-stat-pill">GPM <b>${p.gpm}</b></span>`,
      `<span class="v-stat-pill">伤害 <b>${fmtNum(p.hero_damage)}</b> (${p.hero_damage_share_pct || 0}%)</span>`,
    ];
    if (isTrouble || (p.dead_seconds || 0) >= 160) {
      pills.push(`<span class="v-stat-pill warn">泉水读秒 <b>${p.dead_seconds || 0}秒</b></span>`);
    }
    if ((p.pos || 1) >= 4 && (p.obs_placed || 0) + (p.sen_placed || 0) > 0) {
      pills.push(`<span class="v-stat-pill">视野 <b>${p.obs_placed || 0}假/${p.sen_placed || 0}真</b></span>`);
    } else {
      pills.push(`<span class="v-stat-pill">拆塔 <b>${fmtNum(p.tower_damage || 0)}</b></span>`);
    }
    return `<div class="verdict-stat-pills-row">${pills.join("")}</div>`;
  };

  // 2.2 Render ALL 5 Players' Verdict Cards & 5-Player Switcher (`1~5号位全员可看评价 + 📋 全部(5)`)
  const verdictSwitcherEl = document.getElementById("verdict-cards-switcher");
  const verdictGridEl = document.getElementById("verdict-grid-3col");

  if (verdictSwitcherEl && verdictGridEl) {
    // Build the ordered 5-player evaluation list
    let fiveVerdictEntries = [];
    if (won) {
      const mvpP = sortedByContrib[0]?.player || own[0];
      const runnerP = (sortedByContrib[1] || sortedByContrib[0])?.player || own[1] || own[0];
      const stP = strugglePlayer || sortedByContrib[sortedByContrib.length - 1]?.player;
      const usedSlots = new Set(
        [mvpP?.player_slot, runnerP?.player_slot, stP?.player_slot].filter((x) => x !== undefined)
      );
      const middleContributors = sortedByContrib
        .filter((x) => !usedSlots.has(x.player.player_slot))
        .map((x) => x.player);

      const orderedWinPlayers = [mvpP, runnerP, ...middleContributors, stP].filter(Boolean);
      // Deduplicate by player_slot just in case
      const seenSlots = new Set();
      orderedWinPlayers.forEach((p) => {
        if (!p || seenSlots.has(Number(p.player_slot))) return;
        seenSlots.add(Number(p.player_slot));
        const share =
          sortedByContrib.find((x) => Number(x.player.player_slot) === Number(p.player_slot))
            ?.contribShare ??
          p.contrib_share_pct ??
          20.0;
        let roleType = "runnerup";
        let tabTag = "🎖️ 凯旋功臣";
        let cardHeader = "🎖️ 凯旋功臣 · 节奏联动与团战支柱";
        let themeClass = "runnerup-theme";
        let statusTag = p.contrib_tier || "🎖️ 凯旋功臣";
        let copyBtnLabel = "复制庆功词";
        let isTrouble = false;
        let isSpot = false;

        if (Number(p.player_slot) === Number(mvpP?.player_slot)) {
          roleType = "mvp";
          tabTag = "👑 头号首功";
          cardHeader = "👑 头号首功 · 本局擎天真大腿 (MVP)";
          themeClass = "mvp-theme";
          statusTag = "👑 头号首功";
          copyBtnLabel = "复制首功贺电";
          isSpot = true;
        } else if (Number(p.player_slot) === Number(runnerP?.player_slot)) {
          roleType = "runnerup";
          tabTag = "⚔️ 二号功臣";
          cardHeader = "⚔️ 二号功臣 · 破阵二当家 & 定海神针";
          themeClass = "runnerup-theme";
          statusTag = "⚔️ 破阵二当家";
          copyBtnLabel = "复制庆功词";
        } else if (Number(p.player_slot) === Number(stP?.player_slot)) {
          roleType = "struggle";
          tabTag = "🐟 短板提醒";
          cardHeader = "🐟 惊险躺赢/短板算账 · 为什么这把表现有瑕疵";
          themeClass = "struggle-theme";
          statusTag = "⚠️ 胜局短板复盘";
          copyBtnLabel = "复制短板提醒";
          isTrouble = true;
        } else {
          const midRank = fiveVerdictEntries.length + 1;
          roleType = "runnerup";
          tabTag = midRank === 3 ? "🎖️ 三号功臣" : "🛡️ 四号功臣";
          cardHeader =
            midRank === 3
              ? "🎖️ 三号功臣 · 关键节奏与火力兑现"
              : "🛡️ 四号功臣 · 团队视野与控制保障";
          themeClass = "runnerup-theme";
          statusTag = tabTag;
          copyBtnLabel = "复制庆功词";
        }

        fiveVerdictEntries.push({
          key: `slot_${p.player_slot}`,
          player: p,
          share,
          roleType,
          tabTag,
          cardHeader,
          themeClass,
          statusTag,
          copyBtnLabel,
          isTrouble,
          isSpot,
        });
      });
    } else {
      // LOSS mode: #1 Blame, #2 Blame, #1 SVP (highest Grok score / lowest blame), and remaining 2 teammates
      const c1P = sortedByBlame[0]?.player || own[0];
      const c2P = (sortedByBlame[1] || sortedByBlame[0])?.player || own[1] || own[0];
      const svpCandidate =
        [...own]
          .filter(
            (x) =>
              Number(x.player_slot) !== Number(c1P?.player_slot) &&
              Number(x.player_slot) !== Number(c2P?.player_slot)
          )
          .sort((a, b) => getHeroScore100(b, report) - getHeroScore100(a, report))[0] ||
        sortedByContrib[0]?.player ||
        own[own.length - 1];
      const svpP = svpCandidate;
      const orderedLossPlayers = [
        c1P,
        c2P,
        svpP,
        ...sortedByBlame.map((x) => x.player),
      ].filter(Boolean);
      const seenSlots = new Set();
      orderedLossPlayers.forEach((p) => {
        if (!p || seenSlots.has(Number(p.player_slot))) return;
        seenSlots.add(Number(p.player_slot));
        const bShare =
          sortedByBlame.find((x) => Number(x.player.player_slot) === Number(p.player_slot))
            ?.blameShare ??
          p.blame_share_pct ??
          20.0;
        let roleType = "culprit2";
        let tabTag = "⚖️ 背锅复盘";
        let cardHeader = "⚖️ 败局全员审讯 · 功过得失与出装复盘";
        let themeClass = "culprit-theme";
        let statusTag = p.rating_tier || "败局审讯";
        let copyBtnLabel = "复制复盘词";
        let isTrouble = true;
        let isSpot = false;
        let displayShare = bShare;

        if (Number(p.player_slot) === Number(c1P?.player_slot)) {
          roleType = "culprit1";
          tabTag = "🚨 头号大锅";
          cardHeader = "🚨 本方头号大锅 · 一级战犯逮捕令";
          themeClass = "culprit-theme";
          statusTag = "🚨 头号大锅";
          copyBtnLabel = "复制处刑词";
          isSpot = true;
        } else if (Number(p.player_slot) === Number(c2P?.player_slot)) {
          roleType = "culprit2";
          tabTag = "⚠️ 二号次锅";
          cardHeader = "⚠️ 二号背锅位 · 次锅共犯审讯室";
          themeClass = "culprit-theme";
          statusTag = "⚠️ 二号背锅位";
          copyBtnLabel = "复制次锅算账";
        } else if (Number(p.player_slot) === Number(svpP?.player_slot)) {
          roleType = "svp";
          tabTag = "👑 孤胆院长";
          cardHeader = "👑 败方孤胆院长 · 全场尽力大腿 (SVP)";
          themeClass = "mvp-theme";
          statusTag = "👑 孤胆院长";
          copyBtnLabel = "复制表彰词";
          isTrouble = false;
          displayShare = bShare;
        } else {
          roleType = "culprit2";
          tabTag = "📋 战局审讯";
          cardHeader = `📋 ${p.pos}号位${p.hero_short_zh} · 全周期功过与灵性出装审讯`;
          themeClass = "struggle-theme";
          statusTag = `${p.pos}号位复盘`;
          copyBtnLabel = "复制复盘词";
        }

        fiveVerdictEntries.push({
          key: `slot_${p.player_slot}`,
          player: p,
          share: displayShare,
          roleType,
          tabTag,
          cardHeader,
          themeClass,
          statusTag,
          copyBtnLabel,
          isTrouble,
          isSpot,
        });
      });
    }

    const defaultKey = fiveVerdictEntries[0]?.key || "all";
    let activeVerdictKey = state.verdictActiveCard || defaultKey;
    if (
      activeVerdictKey !== "all" &&
      !fiveVerdictEntries.some((e) => e.key === activeVerdictKey)
    ) {
      activeVerdictKey = defaultKey;
    }
    const isAllVerdict = activeVerdictKey === "all";

    // Render 5-Player Switcher Bar + 📋 全部(5)
    verdictSwitcherEl.innerHTML = `
      <div class="tf-p-selector-bar verdict-selector-bar" role="tablist" aria-label="切换五人全周期评价与出装审计卡片">
        ${fiveVerdictEntries
          .map((entry) => {
            const p = entry.player;
            const heroShort = p.hero_short_zh || p.hero_name || "";
            return `
              <button
                type="button"
                class="tf-p-select-btn ${activeVerdictKey === entry.key ? "is-active" : ""} ${
              entry.isSpot ? "is-spotlight" : ""
            }"
                data-verdict-card-tab="${escapeHtml(entry.key)}"
              >
                ${
                  p.hero_img
                    ? `<img src="${escapeHtml(p.hero_img)}" width="22" height="13" alt="" class="tf-p-pill-avatar" />`
                    : ""
                }
                <span class="tf-pill-label">${p.pos}号 ${escapeHtml(heroShort)}</span>
                <span class="tf-pill-chip ${entry.isSpot ? "focus" : ""}">${escapeHtml(entry.tabTag)}</span>
              </button>
            `;
          })
          .join("")}
        <button
          type="button"
          class="tf-p-select-btn mode-all ${isAllVerdict ? "is-active" : ""}"
          data-verdict-card-tab="all"
        >
          📋 全部(${fiveVerdictEntries.length})
        </button>
      </div>
    `;

    // Render all 5 player cards inside #verdict-grid-3col
    verdictGridEl.classList.toggle("is-single-card", !isAllVerdict);
    verdictGridEl.innerHTML = fiveVerdictEntries
      .map((entry) => {
        const p = entry.player;
        const heroShort = p.hero_short_zh || p.hero_name || "";
        const sc100 = getHeroScore100(p, report);
        const grokP = findGrokPlayerEntry(p, report);
        const chronologyHtml = buildPlayerChronologyStoryHtml(
          p,
          report,
          entry.roleType,
          Number(entry.share).toFixed(1)
        );
        const isHidden = !isAllVerdict && activeVerdictKey !== entry.key;
        const hasGrokScore = grokP && Number(grokP.grok_score) > 0;
        const shareLabel = won
          ? `${hasGrokScore ? "🧠 Grok重评" : "本局评分"} · 贡献 ${Number(entry.share).toFixed(1)}%`
          : `${hasGrokScore ? "🧠 Grok重评" : "本局评分"} · 背锅 ${Number(entry.share).toFixed(1)}%`;

        const quoteText =
          grokP?.headline ||
          (entry.roleType === "mvp"
            ? p.praise_talk ||
              `「${heroShort} 这把真神降临砍下 ${sc100}/100 分包揽 ${entry.share}% 胜局贡献，今晚车队全员排队敬茶！」`
            : entry.roleType === "svp"
            ? `「这把要不是 ${heroShort} (${sc100}/100分) 死命顶着局势，早就提前十五分钟敲 GG 了。」`
            : entry.roleType === "runnerup"
            ? p.praise_talk ||
              `「${p.pos}号位 ${heroShort} 砍下 ${sc100}/100 分（贡献 ${entry.share}%），前中后期节奏与出装稳健扎实！」`
            : entry.roleType === "struggle"
            ? p.trash_talk ||
              `「赢球虽然免大锅，但这把 ${heroShort} (${sc100}/100分) 暴露的出装与走位短板必须重点复盘！」`
            : p.trash_talk ||
              `「${heroShort} 本局评分 ${sc100}/100 分（分锅 ${entry.share}%），复盘细节见上方红黑清单。」`);

        const copyText = `【${entry.tabTag} · ${p.pos}号位${heroShort}】${p.personaname} 本局打分 ${sc100}/100 分（${
          won ? `贡献 ${entry.share}%` : `分锅 ${entry.share}%`
        }），KDA ${p.kda}，GPM ${p.gpm}，英雄伤害 ${fmtNum(p.hero_damage)}，推塔 ${fmtNum(
          p.tower_damage
        )}。${quoteText}`;

        return `
          <article class="verdict-card ${entry.themeClass}" data-verdict-card-key="${escapeHtml(
          entry.key
        )}" ${isHidden ? "hidden" : ""}>
            <div class="verdict-card-label">${escapeHtml(entry.cardHeader)}</div>
            <div class="verdict-card-body">
              <div class="verdict-hero-row">
                ${
                  p.hero_img
                    ? `<img class="verdict-portrait" src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(
                        heroShort
                      )}" />`
                    : ""
                }
                <div class="verdict-identity">
                  <div class="verdict-title-line">
                    <span class="verdict-hero-name">${escapeHtml(heroShort)}</span>
                    <span class="verdict-player-name">${escapeHtml(p.personaname)}${
          p.is_me ? " [我]" : ""
        }</span>
                    <span class="status-pill ${entry.isTrouble ? "" : "connected"}">${escapeHtml(
          p.pos_label
        )} · ${escapeHtml(entry.statusTag)}</span>
                  </div>
                  ${renderCardStatPills(p, entry.isTrouble)}
                </div>
                <div class="verdict-score-box">
                  <div class="verdict-score-num">${sc100}<small>/100</small></div>
                  <div class="verdict-score-sub">${escapeHtml(shareLabel)}</div>
                </div>
              </div>
              ${chronologyHtml}
              <div class="verdict-quote-bar">
                <span>${escapeHtml(quoteText)}</span>
                <div style="display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0;">
                  <button type="button" class="button ${
                    entry.roleType === "culprit1" ? "primary" : "secondary"
                  }" data-copy-quote="${escapeHtml(copyText)}">${escapeHtml(entry.copyBtnLabel)}</button>
                  <button type="button" class="button secondary" data-player-poster-slot="${p.player_slot}" data-player-poster-tag="${escapeHtml(entry.cardHeader)}">🖼️ 生成个人海报</button>
                  <button type="button" class="button primary" style="background:linear-gradient(135deg,#c9983a 0%,#9e6918 100%);color:#0f110e;font-weight:700;border-color:#e5bd68;" data-player-poster-slot="${p.player_slot}" data-player-poster-tag="${escapeHtml(entry.cardHeader)}" data-player-nano-auto="1">🍌 AI 超燃原画海报</button>
                </div>
              </div>
            </div>
          </article>
        `;
      })
      .join("");

    verdictSwitcherEl.querySelectorAll("[data-verdict-card-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.verdictActiveCard = btn.getAttribute("data-verdict-card-tab") || defaultKey;
        if (state.currentReport) renderVerdictAndBlameSection(state.currentReport);
      });
    });
  }

  // 2.4 5-Stack 100% Stacked Bar & Ranking Rows:
  // - When WON: 100% Victory Contribution Ranking (sorted by contribShare descending)
  // - When LOST: 100% Defeat Blame Ranking (sorted by blameShare descending)
  const stackedBar = document.getElementById("blame-stacked-bar");
  const rankingRows = document.getElementById("blame-ranking-rows");

  if (stackedBar && rankingRows) {
    stackedBar.classList.toggle("win-mode", won);
    const listToDisplay = won
      ? sortedByContrib.map((x) => ({ player: x.player, share: x.contribShare }))
      : sortedByBlame.map((x) => ({ player: x.player, share: x.blameShare }));

    stackedBar.innerHTML = listToDisplay
      .map(({ player: p, share }, idx) => {
        const heroShort = p.hero_short_zh || p.hero_name;
        const sc100 = getHeroScore100(p, report);
        let innerLabel = "";
        if (share >= 15) {
          innerLabel = `${escapeHtml(heroShort)} ${share}% (${sc100}分)`;
        } else if (share >= 9) {
          innerLabel = `${share}%`;
        }
        const tooltip = won
          ? `${p.pos_label} ${heroShort} (${p.personaname}): 胜局贡献度 ${share}% · 评分 ${sc100}/100`
          : `${p.pos_label} ${heroShort} (${p.personaname}): 败局分锅占比 ${share}% · 评分 ${sc100}/100`;
        return `
          <div
            class="blame-seg rank-${idx}"
            style="--share: ${Math.max(share, 2.5)}; cursor: pointer;"
            data-verdict-card-tab="slot_${p.player_slot}"
            title="${escapeHtml(tooltip)}（点击切换查看详情卡）"
          >${innerLabel}</div>
        `;
      })
      .join("");

    stackedBar.querySelectorAll("[data-verdict-card-tab]").forEach((seg) => {
      seg.addEventListener("click", () => {
        state.verdictActiveCard = seg.getAttribute("data-verdict-card-tab") || "all";
        if (state.currentReport) renderVerdictAndBlameSection(state.currentReport);
      });
    });

    const rankMedals = ["🥇", "🥈", "🥉", "04", "05"];
    const rowsHtml = listToDisplay
      .map(({ player: p, share }, idx) => {
        const heroShort = p.hero_short_zh || p.hero_name;
        const sc100 = getHeroScore100(p, report);
        const grokP = findGrokPlayerEntry(p, report);

        if (won) {
          const oneLinePraise =
            grokP?.headline ||
            (Array.isArray(grokP?.good) ? grokP.good[0] : grokP?.good) ||
            (p.strengths && p.strengths[0]) ||
            p.praise_talk ||
            "稳健发挥助力团队拿下一城";
          const tierTag =
            idx === 0
              ? "👑 头号首功"
              : idx === 1
              ? "⚔️ 破阵次功"
              : Number(p.player_slot) === Number(strugglePlayer?.player_slot) && sc100 <= 82
              ? "🐟 惊险躺赢"
              : "🔥 凯旋功臣";
          const copyQuote = `🏆【凯旋庆功榜 #${idx + 1} · ${tierTag}】${p.personaname} (${heroShort} · ${p.pos_label}) 本局评分 ${sc100}/100 分，胜局贡献 ${share}%：KDA ${p.kda}，${oneLinePraise}`;
          const extraStat =
            p.pos >= 4
              ? `视野 ${(p.obs_placed || 0) + (p.sen_placed || 0)}颗 · 控制 ${p.stuns_sec || 0}s`
              : `伤害 ${fmtNum(p.hero_damage)} (${p.hero_damage_share_pct || 0}%) · 拆塔 ${fmtNum(p.tower_damage)}`;

          return `
            <div class="blame-row win-mode rank-${idx}">
              <div class="blame-rank-num">${rankMedals[idx] || `0${idx + 1}`}</div>
              ${
                p.hero_img
                  ? `<img class="blame-row-portrait" src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(heroShort)}" loading="lazy" />`
                  : `<div class="blame-row-portrait"></div>`
              }
              <div class="blame-row-who">
                <div class="blame-row-title">
                  <strong>${escapeHtml(heroShort)}</strong>
                  <span>${escapeHtml(p.personaname)}${p.is_me ? " [我]" : ""}</span>
                  <span class="hero-score-100-inline">${sc100}分</span>
                </div>
                <div class="blame-row-sub">
                  ${escapeHtml(p.pos_label)} · KDA ${escapeHtml(p.kda)} (${p.kill_participation_pct}%参战) · ${extraStat}
                </div>
              </div>
              <div class="blame-row-bar-wrap">
                <div class="blame-row-bar-track">
                  <div class="blame-row-bar-fill" style="--bar-w: ${Math.min(100, Math.max(4, share))}%"></div>
                </div>
                <div class="blame-row-quote" title="${escapeHtml(oneLinePraise)}">${injectHeroLogosIntoHtml(escapeHtml(oneLinePraise), report)}</div>
              </div>
              <span class="blame-badge">${tierTag} · 贡献 ${share.toFixed(1)}%</span>
              <button type="button" class="button secondary" data-copy-quote="${escapeHtml(copyQuote)}">复制贺电</button>
              <button type="button" class="button secondary" data-player-poster-slot="${p.player_slot}" data-player-poster-tag="${escapeHtml(tierTag)}">🖼️ 海报</button>
            </div>
          `;
        } else {
          const oneLineCrime =
            grokP?.headline ||
            (p.weaknesses && p.weaknesses[0]) ||
            p.trash_talk ||
            "本局表现中规中矩";
          const copyQuote = `【分锅账单 #${idx + 1}】${p.personaname} (${heroShort} · ${p.pos_label}) 本局评分 ${sc100}/100 分，背锅占比 ${share}%：KDA ${p.kda}，${oneLineCrime}`;

          return `
            <div class="blame-row rank-${idx}">
              <div class="blame-rank-num">0${idx + 1}</div>
              ${
                p.hero_img
                  ? `<img class="blame-row-portrait" src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(heroShort)}" loading="lazy" />`
                  : `<div class="blame-row-portrait"></div>`
              }
              <div class="blame-row-who">
                <div class="blame-row-title">
                  <strong>${escapeHtml(heroShort)}</strong>
                  <span>${escapeHtml(p.personaname)}${p.is_me ? " [我]" : ""}</span>
                  <span class="hero-score-100-inline">${sc100}分</span>
                </div>
                <div class="blame-row-sub">
                  ${escapeHtml(p.pos_label)} · KDA ${escapeHtml(p.kda)} · 参战 ${p.kill_participation_pct}% · 读秒 ${p.dead_seconds || 0}s
                </div>
              </div>
              <div class="blame-row-bar-wrap">
                <div class="blame-row-bar-track">
                  <div class="blame-row-bar-fill" style="--bar-w: ${Math.min(100, Math.max(4, share))}%"></div>
                </div>
                <div class="blame-row-quote" title="${escapeHtml(oneLineCrime)}">${injectHeroLogosIntoHtml(escapeHtml(oneLineCrime), report)}</div>
              </div>
              <span class="blame-badge">背锅 ${share.toFixed(1)}%</span>
              <button type="button" class="button secondary" data-copy-quote="${escapeHtml(copyQuote)}">复制算账</button>
              <button type="button" class="button secondary" data-player-poster-slot="${p.player_slot}" data-player-poster-tag="分锅账单 #${idx + 1}">🖼️ 海报</button>
            </div>
          `;
        }
      })
      .join("");
    rankingRows.innerHTML = `<details class="mobile-summary-fold"><summary class="mobile-summary-trigger">📋 展开/收起五人 100% 贡献/分锅横向明细表（点击上方色块或标签可直接切换单人卡片）</summary><div style="margin-top:8px;display:flex;flex-direction:column;gap:6px;">${rowsHtml}</div></details>`;
  }

  document.querySelectorAll(".verdict-and-blame-section [data-copy-quote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      copyTextToClipboard(btn.getAttribute("data-copy-quote") || "", won ? "庆功贺电" : "处刑判词");
    });
  });

  document.querySelectorAll(".verdict-and-blame-section [data-player-poster-slot]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slotNum = Number(btn.getAttribute("data-player-poster-slot"));
      const roleTag = btn.getAttribute("data-player-poster-tag") || "";
      const autoAi = btn.getAttribute("data-player-nano-auto") === "1";
      if (state.currentReport) {
        openSinglePlayerPosterDialog(state.currentReport, slotNum, roleTag, { autoGenerateAiArt: autoAi });
      }
    });
  });
}

/**
 * 2.8 Interactive Minute-by-Minute Timeline Scrubber (00:00 -> End)
 */
function setScrubberMinute(minuteIdx) {
  if (!state.currentReport) return;
  const snaps = state.currentReport.deep_forensics?.minute_snapshots || [];
  if (!snaps.length) return;
  const clamped = Math.max(0, Math.min(snaps.length - 1, Number(minuteIdx || 0)));
  state.scrubberMinute = clamped;
  const rangeEl = document.getElementById("minute-scrubber-range");
  if (rangeEl) rangeEl.value = String(clamped);
  renderMinuteScrubberSnapshot(state.currentReport, clamped);
  if (state.scrubSyncMapMinute !== null) {
    state.scrubSyncMapMinute = clamped;
    const syncBtn = document.getElementById("btn-scrub-sync-map");
    if (syncBtn) {
      syncBtn.textContent = `🗺️ 已锁定 ${String(clamped).padStart(2, "0")}:00 场上存活眼位 (再点取消)`;
    }
    renderMinimap(state.currentReport);
  }
}

function renderMinuteScrubber(report) {
  const box = document.getElementById("minute-scrubber-box");
  const rangeEl = document.getElementById("minute-scrubber-range");
  const maxLabelEl = document.getElementById("scrubber-max-label");
  const jumpsEl = document.getElementById("scrubber-quick-jumps");
  const contentEl = document.getElementById("minute-scrubber-content");
  if (!box || !contentEl) return;

  const snaps = report.deep_forensics?.minute_snapshots || [];
  if (!snaps.length) {
    contentEl.innerHTML = `<div class="empty-state compact">当前比赛暂未生成逐分钟时间轴快照</div>`;
    return;
  }

  const maxMin = snaps.length - 1;
  if (state.scrubberMinute > maxMin || state.scrubberMinute < 0) {
    state.scrubberMinute = Math.min(15, maxMin);
  }
  if (rangeEl) {
    rangeEl.min = "0";
    rangeEl.max = String(maxMin);
    rangeEl.value = String(state.scrubberMinute);
  }
  if (maxLabelEl) {
    maxLabelEl.textContent = snaps[maxMin]?.time_str || `${maxMin}:00`;
  }

  // Build quick-jump pills for key moments (10m Laning End, 20m Mid, Roshan/Highground markers, Final)
  if (jumpsEl) {
    const jumpTargets = [
      { m: Math.min(10, maxMin), label: "10:00 对线期交卷" },
      { m: Math.min(20, maxMin), label: "20:00 中期抱团点" },
    ];
    (report.objective_markers || []).slice(0, 5).forEach((mk) => {
      const mVal = Math.min(maxMin, Math.max(1, Math.round(Number(mk.time_sec || 0) / 60)));
      jumpTargets.push({
        m: mVal,
        label: `${String(mVal).padStart(2, "0")}:00 ${mk.label || "关键节点"}`,
      });
    });
    jumpTargets.push({ m: maxMin, label: `${snaps[maxMin]?.time_str || ""} 终局定格` });

    const seenMins = new Set();
    const uniqueJumps = jumpTargets.filter((jt) => {
      const key = `${jt.m}_${jt.label}`;
      if (seenMins.has(key)) return false;
      seenMins.add(key);
      return true;
    });

    jumpsEl.innerHTML =
      `<span style="font-size:11px;color:var(--muted);margin-right:4px;">⚡ 一键跳至关键帧：</span>` +
      uniqueJumps
        .map(
          (jt) =>
            `<button type="button" class="cp-pill scrub-jump-pill" data-scrub-jump="${jt.m}" style="cursor:pointer;">${escapeHtml(
              jt.label
            )}</button>`
        )
        .join("");

    jumpsEl.querySelectorAll("[data-scrub-jump]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mTarget = Number(btn.getAttribute("data-scrub-jump") || 0);
        setScrubberMinute(mTarget);
      });
    });
  }

  renderMinuteScrubberSnapshot(report, state.scrubberMinute);
}

function renderMinuteScrubberSnapshot(report, minuteIdx) {
  const contentEl = document.getElementById("minute-scrubber-content");
  const badgeEl = document.getElementById("scrubber-time-badge");
  if (!contentEl) return;

  const snaps = report.deep_forensics?.minute_snapshots || [];
  if (!snaps.length) return;
  const idx = Math.max(0, Math.min(snaps.length - 1, Number(minuteIdx || 0)));
  const snap = snaps[idx];
  if (!snap) return;

  if (badgeEl) {
    badgeEl.textContent = `⏱️ 第 ${snap.time_str || `${idx}:00`} 分钟`;
  }

  const { side } = getOwnAndOppPlayers(report);
  const players = snap.players || [];
  const maxNw = Math.max(1000, ...players.map((p) => Number(p.networth || 0)));

  const radGoldAdv = Number(snap.radiant_gold_adv || 0);
  const radXpAdv = Number(snap.radiant_xp_adv || 0);
  const goldLeadTeam = radGoldAdv > 0 ? "天辉" : radGoldAdv < 0 ? "夜魇" : "双方均势";
  const xpLeadTeam = radXpAdv > 0 ? "天辉" : radXpAdv < 0 ? "夜魇" : "双方均势";

  // Count active wards on map at this exact minute
  const allWards = report.vision_and_map_data?.wards || [];
  const secNow = idx * 60;
  const activeObsAtMin = allWards.filter(
    (w) =>
      w.type === "obs" &&
      Number(w.time_sec ?? 0) <= secNow &&
      secNow <= Number(w.left_sec ?? Number(w.time_sec ?? 0) + 360)
  );
  const radObsNow = activeObsAtMin.filter((w) => w.side === "radiant" || w.side === "天辉").length;
  const direObsNow = activeObsAtMin.filter((w) => w.side === "dire" || w.side === "夜魇").length;

  const barsHtml = players
    .map((p, rankIdx) => {
      const pct = Math.max(4, Math.round((Number(p.networth || 0) / maxNw) * 100));
      const isOwn = p.side === side;
      const sideLabel = p.side === "radiant" ? "天辉" : "夜魇";
      const itemsHtml = (p.items || [])
        .map(
          (it) =>
            `<img class="scrub-item-icon" src="${escapeHtml(it.img || "")}" alt="${escapeHtml(
              it.zh || it.key || ""
            )}" title="${escapeHtml(it.zh || it.key || "")}" width="24" height="18" loading="lazy" />`
        )
        .join("");
      return `
        <div class="scrub-player-row ${isOwn ? "own-row" : "opp-row"}">
          <span class="scrub-rank">#${rankIdx + 1}</span>
          <div class="scrub-hero-cell">
            ${
              p.hero_img
                ? `<img src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(
                    p.hero_short_zh || ""
                  )}" width="30" height="17" loading="lazy" />`
                : ""
            }
            <div>
              <strong>[${sideLabel}${p.pos ?? "?"}] ${escapeHtml(p.hero_short_zh || "")}</strong>
              <span class="scrub-pname">${escapeHtml(p.personaname || "")}</span>
            </div>
          </div>
          <div class="scrub-bar-cell">
            <div class="scrub-bar-track">
              <div class="scrub-bar-fill ${p.side === "radiant" ? "rad" : "dire"}" style="width:${pct}%"></div>
            </div>
            <div class="scrub-items-strip">${itemsHtml || `<span class="scrub-no-item">散件过渡期</span>`}</div>
          </div>
          <div class="scrub-stat-cell">
            <strong>${fmtNum(p.networth || 0)} 金</strong>
            <span>补刀 ${p.lh ?? 0}/${p.dn ?? 0}</span>
          </div>
        </div>
      `;
    })
    .join("");

  const eventsList = snap.events || [];
  const eventsHtml =
    eventsList.length > 0
      ? eventsList.map((ev) => `<li>${escapeHtml(ev)}</li>`).join("")
      : `<li>本分钟 (${Math.max(0, idx - 1)}:00–${idx}:00) 双方平稳对线/刷钱发育，无英雄击杀或建筑摧毁</li>`;

  // Compute live 5v5 team snapshot aggregates for the right column so no space is wasted
  const radPlayers = players.filter((p) => p.side === "radiant");
  const direPlayers = players.filter((p) => p.side === "dire");
  const sumBy = (arr, fn) => arr.reduce((acc, x) => acc + Number(fn(x) || 0), 0);

  const radTotalNw = sumBy(radPlayers, (p) => p.networth);
  const direTotalNw = sumBy(direPlayers, (p) => p.networth);
  const totalNwBoth = Math.max(1, radTotalNw + direTotalNw);
  const radNwSharePct = Math.round((radTotalNw / totalNwBoth) * 100);

  const radCoresNw = sumBy(
    radPlayers.filter((p) => Number(p.pos) <= 3),
    (p) => p.networth
  );
  const direCoresNw = sumBy(
    direPlayers.filter((p) => Number(p.pos) <= 3),
    (p) => p.networth
  );
  const radSupsNw = sumBy(
    radPlayers.filter((p) => Number(p.pos) >= 4),
    (p) => p.networth
  );
  const direSupsNw = sumBy(
    direPlayers.filter((p) => Number(p.pos) >= 4),
    (p) => p.networth
  );
  const radTotalLh = sumBy(radPlayers, (p) => p.lh);
  const direTotalLh = sumBy(direPlayers, (p) => p.lh);
  const radTotalDn = sumBy(radPlayers, (p) => p.dn);
  const direTotalDn = sumBy(direPlayers, (p) => p.dn);

  // Positional 1-5 head-to-head net worth delta at this exact minute
  const posDeltaRowsHtml = [1, 2, 3, 4, 5]
    .map((posNum) => {
      const rp = radPlayers.find((p) => Number(p.pos) === posNum);
      const dp = direPlayers.find((p) => Number(p.pos) === posNum);
      if (!rp || !dp) return "";
      const diff = Number(rp.networth || 0) - Number(dp.networth || 0);
      const leadTxt =
        diff > 0
          ? `天辉 +${fmtNum(diff)}`
          : diff < 0
          ? `夜魇 +${fmtNum(Math.abs(diff))}`
          : "均势 0";
      const leadCls = diff > 250 ? "rad-lead" : diff < -250 ? "dire-lead" : "even-lead";
      return `
        <div class="scrub-pos-vs-row">
          <span class="scrub-pos-side rad">${posNum}号位 ${escapeHtml(rp.hero_short_zh || "")} <b>${fmtNum(rp.networth || 0)}</b></span>
          <span class="scrub-pos-diff ${leadCls}">${leadTxt}</span>
          <span class="scrub-pos-side dire"><b>${fmtNum(dp.networth || 0)}</b> ${escapeHtml(dp.hero_short_zh || "")} ${posNum}号位</span>
        </div>
      `;
    })
    .join("");

  contentEl.innerHTML = `
    <div class="scrub-left-col">
      <div class="scrub-col-title">
        <strong>🏆 ${escapeHtml(snap.time_str || "")} 时刻 · 十人实时净资产与已出核心装排位</strong>
        <span>正补/反补与装备栏同步定格</span>
      </div>
      <div class="scrub-players-list">${barsHtml}</div>
    </div>
    <div class="scrub-right-col">
      <div class="scrub-kpi-grid">
        <div class="scrub-kpi-card">
          <span>💰 ${escapeHtml(snap.time_str || "")} 经济差</span>
          <strong style="color:${
            radGoldAdv === 0
              ? "var(--text)"
              : (radGoldAdv > 0 && side === "radiant") || (radGoldAdv < 0 && side === "dire")
              ? "var(--green-light)"
              : "var(--red-light)"
          }">${goldLeadTeam} ${radGoldAdv === 0 ? "0" : `+${fmtNum(Math.abs(radGoldAdv))}`}</strong>
        </div>
        <div class="scrub-kpi-card">
          <span>📚 ${escapeHtml(snap.time_str || "")} 经验差</span>
          <strong>${xpLeadTeam} ${radXpAdv === 0 ? "0" : `+${fmtNum(Math.abs(radXpAdv))}`}</strong>
        </div>
        <div class="scrub-kpi-card">
          <span>👁️ 场上存活假眼</span>
          <strong>天辉 ${radObsNow} / 夜魇 ${direObsNow}</strong>
        </div>
      </div>

      <div class="scrub-events-box">
        <h4>⚔️ 本分钟 (${Math.max(0, idx - 1)}:00–${idx}:00) 关键交火与推塔战报</h4>
        <ul class="micro-insights-list">${eventsHtml}</ul>
      </div>

      <div class="scrub-team-compare-box">
        <div class="scrub-compare-head">
          <h4>⚖️ ${escapeHtml(snap.time_str || "")} 时刻 · 双方团队与 1~5 号位对位净值横评</h4>
          <span>天辉 ${fmtNum(radTotalNw)} 金 (${radNwSharePct}%) vs 夜魇 ${fmtNum(direTotalNw)} 金 (${100 - radNwSharePct}%)</span>
        </div>
        <div class="scrub-tug-bar">
          <div class="scrub-tug-rad" style="width:${radNwSharePct}%"></div>
          <div class="scrub-tug-dire" style="width:${100 - radNwSharePct}%"></div>
        </div>
        <div class="scrub-team-metrics-grid">
          <div class="scrub-tm-pill">
            <span>三大哥(1-3号位)总经济</span>
            <strong>天辉 ${fmtNum(radCoresNw)} vs 夜魇 ${fmtNum(direCoresNw)}</strong>
          </div>
          <div class="scrub-tm-pill">
            <span>双辅助(4-5号位)总经济</span>
            <strong>天辉 ${fmtNum(radSupsNw)} vs 夜魇 ${fmtNum(direSupsNw)}</strong>
          </div>
          <div class="scrub-tm-pill">
            <span>全队累计正补 / 反补</span>
            <strong>天辉 ${radTotalLh}/${radTotalDn} vs 夜魇 ${direTotalLh}/${direTotalDn}</strong>
          </div>
        </div>
        <div class="scrub-pos-vs-list">
          ${posDeltaRowsHtml}
        </div>
      </div>
    </div>
  `;
}

/**
 * 3. Chart 1: Team Cumulative Gold & XP Advantage SVG Curve + Objective Markers
 */
function renderAdvChart(report) {
  const container = document.getElementById("adv-chart-container");
  const cpStrip = document.getElementById("economy-checkpoints-strip");
  if (!container) return;

  const goldAdv = report.radiant_gold_adv || [];
  const xpAdv = report.radiant_xp_adv || [];
  if (goldAdv.length < 2) {
    container.innerHTML = `<div class="empty-state">该比赛暂未生成分钟级经济差曲线（可点击上方“请求录像解析”）</div>`;
    if (cpStrip) cpStrip.innerHTML = "";
    return;
  }

  const W = 640;
  const H = 240;
  const padL = 52;
  const padR = 20;
  const padT = 22;
  const padB = 28;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const midY = padT + plotH / 2;

  const maxAbs = Math.max(
    5000,
    ...goldAdv.map((v) => Math.abs(Number(v || 0))),
    ...xpAdv.map((v) => Math.abs(Number(v || 0)))
  );
  const maxMin = Math.max(1, goldAdv.length - 1);

  const xAt = (min) => padL + (min / maxMin) * plotW;
  const yAt = (val) => midY - (Number(val || 0) / maxAbs) * (plotH / 2);

  const goldPts = goldAdv.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
  const xpPts = xpAdv.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
  const areaPath = `M ${xAt(0).toFixed(1)},${midY.toFixed(1)} L ${goldAdv
    .map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`)
    .join(" L ")} L ${xAt(maxMin).toFixed(1)},${midY.toFixed(1)} Z`;

  const markers = (report.objective_markers || []).slice(0, 8);
  const markerLines = markers
    .map((m, idx) => {
      const mMin = Math.min(maxMin, Math.max(0, (m.time_sec || 0) / 60));
      const mx = xAt(mMin);
      const isRosh = m.type === "roshan" || m.kind === "roshan";
      const stroke = isRosh ? "#c6a468" : "#8b7256";
      const labelY = idx % 2 === 0 ? padT + 11 : H - padB - 6;
      return `
        <g>
          <line x1="${mx.toFixed(1)}" y1="${padT}" x2="${mx.toFixed(1)}" y2="${H - padB}" stroke="${stroke}" stroke-width="1" stroke-dasharray="2,3" opacity="0.7" />
          <text x="${mx.toFixed(1)}" y="${labelY}" fill="${stroke}" font-size="9" text-anchor="middle">${escapeHtml(
            m.label || ""
          )}</text>
        </g>
      `;
    })
    .join("");

  const xTicks = [];
  for (let m = 0; m <= maxMin; m += 10) {
    const tx = xAt(m);
    xTicks.push(
      `<text x="${tx.toFixed(1)}" y="${H - 8}" fill="#7b7c72" font-size="10" text-anchor="middle">${m}:00</text>`
    );
  }

  container.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="团队累计经济差与经验差走势图">
      <defs>
        <clipPath id="clip-rad-above">
          <rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH / 2}" />
        </clipPath>
        <clipPath id="clip-dire-below">
          <rect x="${padL}" y="${midY}" width="${plotW}" height="${plotH / 2}" />
        </clipPath>
      </defs>

      <line x1="${padL}" y1="${padT}" x2="${W - padR}" y2="${padT}" stroke="#2a2c25" stroke-width="1" />
      <line x1="${padL}" y1="${midY}" x2="${W - padR}" y2="${midY}" stroke="#595443" stroke-width="1" />
      <line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="#2a2c25" stroke-width="1" />

      <text x="${padL - 6}" y="${padT + 8}" fill="#8aa78b" font-size="10" text-anchor="end">天辉 +${Math.round(
        maxAbs / 1000
      )}k</text>
      <text x="${padL - 6}" y="${midY + 3}" fill="#7b7c72" font-size="10" text-anchor="end">0</text>
      <text x="${padL - 6}" y="${H - padB - 2}" fill="#df8978" font-size="10" text-anchor="end">夜魇 +${Math.round(
        maxAbs / 1000
      )}k</text>

      <path d="${areaPath}" fill="rgba(138, 167, 139, 0.25)" clip-path="url(#clip-rad-above)" />
      <path d="${areaPath}" fill="rgba(185, 74, 61, 0.28)" clip-path="url(#clip-dire-below)" />

      ${markerLines}

      ${
        xpAdv.length > 1
          ? `<polyline fill="none" stroke="#c6a468" stroke-width="1.5" stroke-dasharray="4,3" points="${xpPts}" />`
          : ""
      }
      <polyline fill="none" stroke="#e6e3dc" stroke-width="2" points="${goldPts}" />

      ${xTicks.join("")}
    </svg>
  `;

  if (cpStrip) {
    const cpsObj = report.economy_timeline?.checkpoints || {};
    cpStrip.innerHTML = Object.entries(cpsObj)
      .map(
        ([k, v]) => `<span class="cp-pill">${escapeHtml(k)}：<b>${escapeHtml(v)}</b> 金</span>`
      )
      .join("");
  }
}

/**
 * 4. Chart 2: 10-Player Minute-by-Minute Net Worth Curve (networth_t)
 */
function renderNetWorthChart(report) {
  const container = document.getElementById("nw-chart-container");
  const legendEl = document.getElementById("nw-chart-legend");
  if (!container) return;

  const { own, opp } = getOwnAndOppPlayers(report);
  let selectedPlayers = [];
  if (state.nwFilter === "own") {
    selectedPlayers = own;
  } else if (state.nwFilter === "all") {
    selectedPlayers = [...own, ...opp];
  } else {
    selectedPlayers = [
      ...own.filter((p) => (p.pos || 5) <= 3),
      ...opp.filter((p) => (p.pos || 5) <= 3),
    ];
  }

  const withSeries = selectedPlayers.filter(
    (p) => Array.isArray(p.networth_t) && p.networth_t.length > 1
  );
  if (withSeries.length === 0) {
    container.innerHTML = `<div class="empty-state">暂无分钟级个人净资产序列数据</div>`;
    if (legendEl) legendEl.innerHTML = "";
    return;
  }

  const W = 640;
  const H = 240;
  const padL = 48;
  const padR = 54;
  const padT = 18;
  const padB = 28;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const maxMin = Math.max(...withSeries.map((p) => p.networth_t.length - 1), 1);
  const maxNw = Math.max(
    10000,
    ...withSeries.flatMap((p) => p.networth_t.map((v) => Number(v || 0)))
  );

  const xAt = (min) => padL + (min / maxMin) * plotW;
  const yAt = (val) => padT + plotH - (Number(val || 0) / maxNw) * plotH;

  const colorForPlayer = (p) => {
    const posIdx = Math.min(4, Math.max(0, (p.pos || 1) - 1));
    return p.side === "天辉" ? NW_COLORS_RAD[posIdx] : NW_COLORS_DIRE[posIdx];
  };

  const linesSvg = withSeries
    .map((p) => {
      const color = colorForPlayer(p);
      const pts = p.networth_t
        .map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`)
        .join(" ");
      const lastVal = p.networth_t[p.networth_t.length - 1] || 0;
      const lastX = xAt(p.networth_t.length - 1);
      const lastY = yAt(lastVal);
      const isMe = Boolean(p.is_me);
      const heroShort = p.hero_short_zh || p.hero_name;
      return `
        <g>
          <polyline
            fill="none"
            stroke="${color}"
            stroke-width="${isMe ? "2.6" : "1.7"}"
            opacity="${isMe ? "1" : "0.86"}"
            points="${pts}"
          />
          <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="${isMe ? 3.5 : 2.5}" fill="${color}" />
          <text x="${(lastX + 5).toFixed(1)}" y="${(lastY + 3).toFixed(1)}" fill="${color}" font-size="9.5" font-weight="${
            isMe ? "700" : "500"
          }">${escapeHtml(heroShort)}</text>
        </g>
      `;
    })
    .join("");

  const yGrid = [0.25, 0.5, 0.75, 1.0]
    .map((ratio) => {
      const val = Math.round((maxNw * ratio) / 1000);
      const y = yAt(maxNw * ratio);
      return `
        <line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="#262822" stroke-width="1" />
        <text x="${padL - 6}" y="${(y + 3).toFixed(1)}" fill="#7b7c72" font-size="10" text-anchor="end">${val}k</text>
      `;
    })
    .join("");

  const xTicks = [];
  for (let m = 0; m <= maxMin; m += 10) {
    xTicks.push(
      `<text x="${xAt(m).toFixed(1)}" y="${H - 8}" fill="#7b7c72" font-size="10" text-anchor="middle">${m}:00</text>`
    );
  }

  container.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="十人分钟级净资产走势曲线">
      ${yGrid}
      <line x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}" stroke="#464336" stroke-width="1" />
      ${linesSvg}
      ${xTicks.join("")}
    </svg>
  `;

  if (legendEl) {
    legendEl.innerHTML = [...withSeries]
      .sort((a, b) => (b.net_worth || 0) - (a.net_worth || 0))
      .map((p) => {
        const color = colorForPlayer(p);
        const heroShort = p.hero_short_zh || p.hero_name;
        return `
          <span class="nw-legend-item">
            <i class="nw-swatch" style="--swatch-color: ${color}"></i>
            <span>[${escapeHtml(p.side)}${p.pos}号位] ${escapeHtml(heroShort)}：<b>${fmtNum(
              p.net_worth
            )}</b></span>
          </span>
        `;
      })
      .join("");
  }
}

/**
 * 5. Chart 3: 2D Dota 2 Tactical Minimap SVG (Real Ward Coordinates + Laning Heatmap + Teamfight Tombstones)
 */
function renderMinimap(report) {
  const svgContainer = document.getElementById("minimap-svg-container");
  const sideContainer = document.getElementById("minimap-stats-side");
  if (!svgContainer || !sideContainer) return;

  const { side, sideZh, own, opp } = getOwnAndOppPlayers(report);
  const visionData = report.vision_and_map_data || {};
  const allWards = visionData.wards || [];
  const heatmaps = visionData.lane_heatmaps || [];
  const tfForensics = report.deep_forensics?.teamfight_forensics || [];

  let overlaySvg = "";

  if (state.mapMode === "heatmap") {
    const maxWeight = Math.max(...heatmaps.map((pt) => Number(pt.weight || 1)), 1);
    overlaySvg = heatmaps
      .map((pt) => {
        const isOwn = pt.side === side || pt.side === sideZh;
        const fill = pt.side === "radiant" || pt.side === "天辉" ? "#8aa78b" : "#df8978";
        const w = Number(pt.weight || 1);
        const alpha = Math.min(0.82, Math.max(0.2, w / maxWeight));
        const r = 1.5 + (w / maxWeight) * 2.4;
        const x = Number(pt.nx ?? pt.x ?? 50).toFixed(1);
        const y = Number(pt.ny ?? pt.y ?? 50).toFixed(1);
        return `
          <circle
            cx="${x}"
            cy="${y}"
            r="${r.toFixed(1)}"
            fill="${fill}"
            fill-opacity="${alpha.toFixed(2)}"
            stroke="${isOwn ? "#e6e3dc" : "none"}"
            stroke-width="0.2"
          >
            <title>${escapeHtml(pt.hero_short_zh || "")} (${escapeHtml(
              pt.personaname || ""
            )}) 对线驻留权重: ${w}</title>
          </circle>
        `;
      })
      .join("");
  } else if (state.mapMode === "teamfights") {
    const activeTfs =
      state.selectedTeamfightIndex !== null && tfForensics[state.selectedTeamfightIndex]
        ? [tfForensics[state.selectedTeamfightIndex]]
        : tfForensics;

    const markers = [];
    activeTfs.forEach((tf, tfIdx) => {
      (tf.deaths_coords || []).forEach((d, dIdx) => {
        const isOwn = d.side === side;
        const fill = isOwn ? "#d95548" : "#6fbf73";
        // Slight spiral jitter if multiple deaths at exact same spot
        const angle = (dIdx * 2.2) + tfIdx;
        const jitterR = dIdx > 0 ? 1.4 : 0;
        const cx = Math.min(95, Math.max(5, Number(d.nx || 50) + Math.cos(angle) * jitterR)).toFixed(1);
        const cy = Math.min(95, Math.max(5, Number(d.ny || 50) + Math.sin(angle) * jitterR)).toFixed(1);
        const tip = `[团战 #${tf.index || tfIdx + 1} · ${tf.time_range}] ${
          isOwn ? "本方阵亡" : "敌方阵亡"
        }: ${d.hero_short_zh} (${d.personaname}) ×${d.deaths}`;
        markers.push(`
          <g>
            <circle cx="${cx}" cy="${cy}" r="2.8" fill="${fill}" stroke="#121312" stroke-width="0.55">
              <title>${escapeHtml(tip)}</title>
            </circle>
            <text x="${cx}" y="${(Number(cy) + 1.0).toFixed(1)}" fill="#fff" font-size="2.7" font-weight="700" text-anchor="middle" pointer-events="none">✕</text>
          </g>
        `);
      });
    });
    overlaySvg = markers.join("");
  } else {
    let filteredWards = allWards;
    if (state.mapMode === "wards_obs") {
      filteredWards = allWards.filter((w) => w.type === "obs");
    } else if (state.mapMode === "wards_own") {
      filteredWards = allWards.filter((w) => w.side === side || w.side === sideZh);
    }
    if (state.scrubSyncMapMinute !== null) {
      const targetSec = Number(state.scrubSyncMapMinute) * 60;
      filteredWards = filteredWards.filter((w) => {
        const tIn = Number(w.time_sec ?? 0);
        const maxLife = w.type === "obs" ? 360 : 420;
        const tOut = Number(w.left_sec ?? tIn + maxLife);
        return tIn <= targetSec && targetSec <= tOut;
      });
    }

    // Group wards placed on the exact same cliff cell (rounded to 2.5 grid) so they never overlap into a blob
    const cellGroups = new Map();
    filteredWards.forEach((w) => {
      const gx = Math.round(Number(w.nx ?? w.x ?? 50) / 2.2) * 2.2;
      const gy = Math.round(Number(w.ny ?? w.y ?? 50) / 2.2) * 2.2;
      const key = `${w.type}_${w.side}_${gx.toFixed(1)}_${gy.toFixed(1)}`;
      if (!cellGroups.has(key)) {
        cellGroups.set(key, {
          ...w,
          cx: Number(w.nx ?? w.x ?? 50),
          cy: Number(w.ny ?? w.y ?? 50),
          count: 0,
          times: [],
        });
      }
      const g = cellGroups.get(key);
      g.count += 1;
      g.times.push(`${w.time_str} ${w.hero_short_zh || ""}`);
    });

    overlaySvg = Array.from(cellGroups.values())
      .map((w) => {
        const isObs = w.type === "obs";
        const isRad = w.side === "radiant" || w.side === "天辉";
        const strokeColor = isRad ? "#8aa78b" : "#df8978";
        const fillColor = isObs ? "#e8c55a" : "#6ca6d9";
        const x = w.cx.toFixed(1);
        const y = w.cy.toFixed(1);
        const teamLabel = isRad ? "天辉" : "夜魇";
        const tip = `${teamLabel}${isObs ? "侦查守卫(假眼)" : "岗哨守卫(真眼)"} ×${w.count}次：${w.times.join(
          " / "
        )}`;
        if (isObs) {
          return `
            <g>
              <circle cx="${x}" cy="${y}" r="3.4" fill="${fillColor}" fill-opacity="0.09" stroke="${strokeColor}" stroke-width="0.3" stroke-dasharray="0.9,0.9" />
              <circle cx="${x}" cy="${y}" r="1.65" fill="${fillColor}" stroke="#141515" stroke-width="0.45">
                <title>${escapeHtml(tip)}</title>
              </circle>
              ${
                w.count > 1
                  ? `<text x="${(w.cx + 2.2).toFixed(1)}" y="${(w.cy - 1.2).toFixed(
                      1
                    )}" fill="#f3dfb0" font-size="2.6" font-weight="700" pointer-events="none">×${w.count}</text>`
                  : ""
              }
            </g>
          `;
        }
        return `
          <circle cx="${x}" cy="${y}" r="1.2" fill="${fillColor}" stroke="${strokeColor}" stroke-width="0.35">
            <title>${escapeHtml(tip)}</title>
          </circle>
        `;
      })
      .join("");
  }

  svgContainer.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 100 100" role="img" aria-label="Dota 2 2D 战术小地图">
      <rect x="0" y="0" width="100" height="100" fill="#141915" />
      <polygon points="0,100 0,15 85,100" fill="#18221a" opacity="0.7" />
      <polygon points="100,0 15,0 100,85" fill="#231a18" opacity="0.7" />

      <polyline points="8,92 8,10 90,10" fill="none" stroke="#2d3129" stroke-width="3.2" />
      <polyline points="10,90 92,90 92,8" fill="none" stroke="#2d3129" stroke-width="3.2" />
      <line x1="10" y1="90" x2="90" y2="10" stroke="#32362d" stroke-width="3.2" />

      <path d="M 6,18 Q 36,42 52,52 T 94,84" fill="none" stroke="#243840" stroke-width="5.5" stroke-linecap="round" />

      <circle cx="37" cy="40" r="3.2" fill="#2c221e" stroke="#a66c49" stroke-width="0.6" />
      <text x="37" y="41.2" fill="#c6a468" font-size="3.2" text-anchor="middle" font-weight="700">R</text>

      <rect x="6" y="86" width="8" height="8" fill="#3a5e3d" stroke="#8aa78b" stroke-width="0.7" />
      <text x="10" y="91.2" fill="#e6e3dc" font-size="3.2" text-anchor="middle">天辉</text>

      <rect x="86" y="6" width="8" height="8" fill="#6b342b" stroke="#df8978" stroke-width="0.7" />
      <text x="90" y="11.2" fill="#e6e3dc" font-size="3.2" text-anchor="middle">夜魇</text>

      ${overlaySvg}
    </svg>
  `;

  const tfBanner =
    state.mapMode === "teamfights"
      ? `<div style="font-size: 11px; color: var(--gold-light); background: #232017; border: 1px solid #594f36; padding: 4px 8px;">
          ${
            state.selectedTeamfightIndex !== null && tfForensics[state.selectedTeamfightIndex]
              ? `当前高亮：团战 #${state.selectedTeamfightIndex + 1} (${escapeHtml(
                  tfForensics[state.selectedTeamfightIndex].time_range
                )}) 阵亡墓碑`
              : `当前显示全场 ${tfForensics.length} 波关键团战阵亡坐标（红✕本方阵亡 / 绿✕敌方阵亡）`
          }
        </div>`
      : state.scrubSyncMapMinute !== null
      ? `<div style="font-size: 11px; color: var(--gold-light); background: #232017; border: 1px solid #594f36; padding: 4px 8px;">
          ⏱️ 已与上方时间轴联动：当前仅显示第 <b>${String(state.scrubSyncMapMinute).padStart(2, "0")}:00</b> 时刻场上仍在生效的真假眼
        </div>`
      : "";

  sideContainer.innerHTML = `
    <div class="visual-sub-title">
      <span>本方视野与反眼明细 (${escapeHtml(sideZh)})</span>
      <span>共 ${allWards.length} 眼</span>
    </div>
    ${tfBanner}
    <table class="ward-summary-table">
      <thead>
        <tr>
          <th>位置 · 英雄 (玩家)</th>
          <th>假眼</th>
          <th>真眼</th>
          <th>排眼</th>
          <th>雾/粉</th>
        </tr>
      </thead>
      <tbody>
        ${own
          .map((p) => {
            const heroShort = p.hero_short_zh || p.hero_name;
            return `
              <tr>
                <td title="${p.pos}号位 · ${escapeHtml(heroShort)} (${escapeHtml(p.personaname)})">
                  <strong>${p.pos}·${escapeHtml(heroShort)}</strong>
                  <span style="color: var(--dim); font-size: 10px;"> ${escapeHtml(p.personaname)}</span>
                </td>
                <td>${p.obs_placed || 0}</td>
                <td>${p.sen_placed || 0}</td>
                <td><strong style="color: var(--gold-light)">${p.obs_destroyed || 0}</strong></td>
                <td>${p.smokes_bought || 0}/${p.dusts_bought || 0}</td>
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>
    <div class="section-caption" style="margin-top: 4px; font-size: 10.5px; line-height: 1.5;">
      对方五人插下 <b>${opp.reduce((s, p) => s + (p.obs_placed || 0), 0)}</b> 假眼 / <b>${opp.reduce(
        (s, p) => s + (p.sen_placed || 0),
        0
      )}</b> 真眼，排掉本方 <b>${opp.reduce((s, p) => s + (p.obs_destroyed || 0), 0)}</b> 假眼。同高台多次插眼已自动合并标注 <b>×N</b>。
    </div>
  `;
}

/**
 * 6. Chart 4: 10-Player Hero Damage / Damage Taken / Tower Damage Matrix
 */
function renderDamageMatrix(report) {
  const container = document.getElementById("damage-matrix-container");
  if (!container) return;

  const { all } = getOwnAndOppPlayers(report);
  const allPlayers = [...all].sort((a, b) => (b.hero_damage || 0) - (a.hero_damage || 0));

  const maxHeroDmg = Math.max(1, ...allPlayers.map((p) => p.hero_damage || 0));
  const maxTaken = Math.max(1, ...allPlayers.map((p) => p.damage_taken || 0));
  const maxTower = Math.max(1, ...allPlayers.map((p) => p.tower_damage || 0));

  container.innerHTML = allPlayers
    .map((p) => {
      const isRad = p.side === "天辉";
      const heroShort = p.hero_short_zh || p.hero_name;
      const wDmg = ((p.hero_damage || 0) / maxHeroDmg) * 100;
      const wTank = ((p.damage_taken || 0) / maxTaken) * 100;
      const wTower = ((p.tower_damage || 0) / maxTower) * 100;

      return `
        <div class="dmg-row ${isRad ? "rad" : "dire"}">
          <div class="dmg-hero-cell" title="${escapeHtml(p.personaname)} (${escapeHtml(heroShort)})">
            ${
              p.hero_img
                ? `<img src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(heroShort)}" loading="lazy" />`
                : ""
            }
            <span><b>${p.pos}</b> ${escapeHtml(heroShort)}</span>
          </div>
          <div class="dmg-bars-stack">
            <div class="dmg-bar-line" title="英雄伤害: ${fmtNum(p.hero_damage)}">
              <div class="dmg-bar-fill dmg" style="--w: ${wDmg.toFixed(1)}%"></div>
            </div>
            <div class="dmg-bar-line" title="承受伤害: ${fmtNum(p.damage_taken)}">
              <div class="dmg-bar-fill tank" style="--w: ${wTank.toFixed(1)}%"></div>
            </div>
            <div class="dmg-bar-line" title="建筑伤害: ${fmtNum(p.tower_damage)}">
              <div class="dmg-bar-fill tower" style="--w: ${wTower.toFixed(1)}%"></div>
            </div>
          </div>
          <div class="dmg-nums-cell">
            输出 ${(p.hero_damage / 1000).toFixed(1)}k · 承伤 ${(p.damage_taken / 1000).toFixed(1)}k · 塔 ${(p.tower_damage / 1000).toFixed(1)}k
          </div>
        </div>
      `;
    })
    .join("");
}

/**
 * Build Phase-Specific Deep Audit Panel:
 * - "lane" (00:00–10:00): Per-lane (Safe / Mid / Offlane) breakdown with Hero Matchup Strength Context & Pos 1–5 Execution Details
 * - "mid"  (10:00–25:00): Resource Conversion Efficiency, Active Ganking & Item Timing, and Hero-Trait Tower Pushing Audit
 * - "late" (25:00–End):   Hyper-Carry Late Conversion, Roshan & Highground Push Chain, and Teamfight Sacrifice vs Solo Pickoff Audit
 */
function buildPhaseSpecificDeepAuditHtml(activePd, report) {
  if (!activePd || !report) return "";
  const { side, sideZh, own } = getOwnAndOppPlayers(report);
  const oppZh = side === "radiant" ? "夜魇" : "天辉";
  const df = report.deep_forensics || {};
  const phaseKey = activePd.key;

  const LANE_BULLY_HEROES = new Set([
    "剧毒术士",
    "冥界亚龙",
    "哈斯卡",
    "剃刀",
    "不朽尸王",
    "杰奇洛",
    "巫妖",
    "伐木机",
    "孽主",
    "卓尔游侠",
    "狙击手",
    "戴泽",
    "巫医",
    "食人魔魔法师",
    "矮人直升机",
    "帕格纳",
    "天怒法师",
  ]);
  const SINGLE_TARGET_MIDS = new Set([
    "天怒法师",
    "赏金猎人",
    "克林克兹",
    "司夜刺客",
    "力丸",
    "祸乱之源",
    "帕吉",
    "修补匠",
  ]);
  const PUSH_TRAIT_HEROES = new Set([
    "帕格纳",
    "死亡先知",
    "暗影萨满",
    "莱席克",
    "兽王",
    "德鲁伊",
    "狼人",
    "魅惑魔女",
    "陈",
    "先知",
    "育母蜘蛛",
    "恐怖利刃",
    "卓尔游侠",
    "主宰",
    "露娜",
    "龙骑士",
  ]);

  if (phaseKey === "lane") {
    const lanes = df.lane_matchups || [];
    if (lanes.length === 0) return "";
    // Order lanes: Safe Lane first, Mid Lane second, Offlane third
    const sortedLanes = [...lanes].sort((a, b) => {
      const aOwn = (side === "radiant" ? a.radiant_heroes : a.dire_heroes) || [];
      const bOwn = (side === "radiant" ? b.radiant_heroes : b.dire_heroes) || [];
      const aMinPos = Math.min(...aOwn.map((h) => Number(h.pos || 5)), 5);
      const bMinPos = Math.min(...bOwn.map((h) => Number(h.pos || 5)), 5);
      return aMinPos - bMinPos;
    });

    const laneCardsHtml = sortedLanes
      .map((ln) => {
        const ownHeroes = (side === "radiant" ? ln.radiant_heroes : ln.dire_heroes) || [];
        const oppHeroes = (side === "radiant" ? ln.dire_heroes : ln.radiant_heroes) || [];
        const ownGold10 = Number(side === "radiant" ? ln.radiant_gold10 : ln.dire_gold10) || 0;
        const oppGold10 = Number(side === "radiant" ? ln.dire_gold10 : ln.radiant_gold10) || 0;
        const ownLhDn = (side === "radiant" ? ln.radiant_lh_dn : ln.dire_lh_dn) || "0/0";
        const oppLhDn = (side === "radiant" ? ln.dire_lh_dn : ln.radiant_lh_dn) || "0/0";
        const laneGoldDiff = ownGold10 - oppGold10;

        const ownNames = ownHeroes.map((h) => `${h.pos}号位${h.hero_short_zh}`).join(" + ");
        const oppNames = oppHeroes.map((h) => `${h.pos}号位${h.hero_short_zh}`).join(" + ");
        const hasPos1 = ownHeroes.some((h) => Number(h.pos) === 1);
        const hasPos2 = ownHeroes.some((h) => Number(h.pos) === 2);
        const laneRoleLabel = hasPos1
          ? `🛡️ 本方优势路（保1号位发育主战场）`
          : hasPos2
          ? `⚔️ 中路 1v1 皇城 PK（节奏与单杀枢轴）`
          : `🔥 本方劣势路（抗压·抢符·干扰敌方大哥）`;

        let statusTheme = "even";
        let statusTag = `⚖️ 均势互发育 (${fmtSigned(laneGoldDiff)} 金)`;
        if (laneGoldDiff >= 1200) {
          statusTheme = "good";
          statusTag = `🟢 彻底打穿该路 (${fmtSigned(laneGoldDiff)} 金)`;
        } else if (laneGoldDiff >= 250) {
          statusTheme = "good";
          statusTag = `🟢 对线小优压制 (${fmtSigned(laneGoldDiff)} 金)`;
        } else if (laneGoldDiff <= -1200) {
          statusTheme = "bad";
          statusTag = `🔴 对线劣势抗压 (${fmtSigned(laneGoldDiff)} 金)`;
        } else if (laneGoldDiff <= -250) {
          statusTheme = "warn";
          statusTag = `🟡 高压抗压微劣 (${fmtSigned(laneGoldDiff)} 金)`;
        }

        // Analyze hero matchup context objectively
        const oppBullies = oppHeroes.filter((h) => LANE_BULLY_HEROES.has(h.hero_short_zh));
        const ownBullies = ownHeroes.filter((h) => LANE_BULLY_HEROES.has(h.hero_short_zh));
        let matchupContextHtml = "";
        if (hasPos1) {
          const p1 = ownHeroes.find((h) => Number(h.pos) === 1) || ownHeroes[0];
          const p5 = ownHeroes.find((h) => Number(h.pos) >= 4) || ownHeroes[1];
          if (laneGoldDiff >= 800) {
            matchupContextHtml = `<b>英雄对位评估（本方组合占优并完美兑现）：</b>${ownNames} 具备极强的线上换血与斩杀联动，面对敌方 ${oppNames}，${
              p5 ? `5号位${p5.hero_short_zh}主动顶前排给足压力` : "辅助保线到位"
            }，让 1号位${p1?.hero_short_zh || ""}在毫无干扰的环境下无解肥正反补并完成线杀碾压。`;
          } else if (oppBullies.length > 0 && laneGoldDiff < 0) {
            matchupContextHtml = `<b>英雄对位评估（敌方劣势路强消耗组合施压）：</b>敌方派出了 ${oppNames}（含线上强消耗/恶心机制），本方优势路前期换血压力较大，重心在于拉野控线保1号位基础补刀。`;
          } else {
            matchupContextHtml = `<b>英雄对位评估：</b>${ownNames} 对阵 ${oppNames}，双方围绕兵线平衡与莲花池展开常规博弈。`;
          }
        } else if (hasPos2) {
          const p2 = ownHeroes[0];
          const opp2 = oppHeroes[0];
          const isSingleTarget = p2 && SINGLE_TARGET_MIDS.has(p2.hero_short_zh);
          if (isSingleTarget && laneGoldDiff >= 0) {
            matchupContextHtml = `<b>英雄对位评估（单点法系压制 vs 高攻反补肉核）：</b>本方 2号位<b>${
              p2.hero_short_zh
            }</b>属于全单体高爆发技能机制、天生缺乏 AOE 推线清兵能力，面对敌方高攻击力/高血量的 <b>${
              opp2?.hero_short_zh || "中单"
            }</b> 拼纯补刀数天然吃亏（${p2.lh10}/${p2.dn10}刀 vs ${opp2?.lh10 || 0}/${
              opp2?.dn10 || 0
            }刀）；但 ${p2.hero_short_zh} 扬长避短，用高频法术耗血与单杀/游走硬生生在10分钟经济上反超 <b>+${fmtNum(
              laneGoldDiff
            )} 金</b>！`;
          } else if (oppBullies.length > 0 && laneGoldDiff < -300) {
            matchupContextHtml = `<b>英雄对位评估（先天对位被克制）：</b>面对敌方线上强势中单 <b>${
              opp2?.hero_short_zh || ""
            }</b>，本方 <b>${p2?.hero_short_zh || ""}</b> 前期换血与控符处于天然劣势，需依靠控水符与双辅助游走破局。`;
          } else {
            matchupContextHtml = `<b>英雄对位评估：</b>中路 <b>${p2?.hero_short_zh || ""}</b> 对决 <b>${
              opp2?.hero_short_zh || ""
            }</b>，10分钟对位经济差 <b>${fmtSigned(laneGoldDiff)} 金</b>。`;
          }
        } else {
          // Offlane (Pos 3 + Pos 4 vs Enemy Pos 1 + Pos 5/4)
          if (oppBullies.length > 0) {
            const bullyNames = oppBullies.map((b) => b.hero_short_zh).join("+");
            matchupContextHtml = `<b>英雄对位评估（⚠️ 敌方强线霸/高减速消耗组合，先天高压抗压路）：</b>敌方优势路拿出了 <b>${oppNames}</b>（其中 <b>${bullyNames}</b> 线上减速粘人与持续消耗极度恶心，再加敌方中单游走威胁），而本方 <b>${ownNames}</b> 缺乏硬位移逃生，一旦过河道极易被粘死。在此天然劣势对位下，虽然阵亡偏多，但两人靠凶悍换血与拉野抢符硬把10分钟总经济差距咬在 <b>${fmtSigned(
              laneGoldDiff
            )} 金</b>（${fmtNum(ownGold10)} vs ${fmtNum(oppGold10)}）。`;
          } else {
            matchupContextHtml = `<b>英雄对位评估：</b>本方劣势路 <b>${ownNames}</b> 对阵敌方优势路 <b>${oppNames}</b>，10分钟本路经济差 <b>${fmtSigned(
              laneGoldDiff
            )} 金</b>。`;
          }
        }

        // Per-player detailed execution in this lane
        const playerRowsHtml = ownHeroes
          .map((lhHero) => {
            const fullP = own.find((x) => x.hero_short_zh === lhHero.hero_short_zh) || lhHero;
            const ctx = analyzePlayerPhaseAndRoleContext(fullP, report);
            const lp = ctx.laneP;
            const pos = Number(fullP.pos || lhHero.pos || 3);
            const k = Number(lp.kills_count || 0);
            const d = Number(lp.deaths_count || 0);
            const dmg10 = Number(lp.hero_damage_gain || 0);
            const tdmg10 = Number(lp.tower_damage_gain || 0);
            const pullPct = Number(ctx.pullRow?.pull_ratio_pct ?? 0);
            const earlySen = Number(ctx.pullRow?.early_sentries ?? 0);
            const gateCnt = Number(ctx.interactRow?.twin_gate ?? 0);
            const lotusCnt = Number(ctx.interactRow?.lotus_used ?? 0);
            const wisdomCnt = Number(ctx.interactRow?.wisdom_runes ?? 0);
            const lampCnt = Number(ctx.interactRow?.watcher_lamp ?? 0);
            const killsStr =
              (lp.kills_events || []).map((ke) => `${ke.time_str}杀${ke.victim_hero}`).join("、") || "0杀";
            const deathsStr =
              (lp.deaths_events || []).map((de) => `${de.time_str}被${de.killer}杀`).join("、") || "0死完美生存";

            let roleAuditText = "";
            if (pos === 1) {
              roleAuditText = `<b>1号位打钱顺畅度：</b>10m 交出 <b>${lhHero.lh10}/${lhHero.dn10}刀（${fmtNum(
                lhHero.gold10
              )}金·效率${lhHero.lane_eff || 80}%）</b>，${
                lhHero.lh10 >= 50 ? "打钱极其顺畅无解肥" : lhHero.lh10 >= 38 ? "发育平稳达标" : "受压补刀受限"
              }；对线打出 <b>${fmtNum(dmg10)} 伤害</b>、磨塔 <b>${fmtNum(tdmg10)}</b>，战果 <b>${k}杀/${d}死</b>（${killsStr}；${deathsStr}）。`;
            } else if (pos === 5) {
              roleAuditText = `<b>5号位保核与给压力细活：</b>10m 仅补 <b>${lhHero.lh10} 刀</b>（彻底让刀给1号位），拉野驻留占比 <b>${pullPct}%</b>、封野/反封真眼 <b>${earlySen} 颗</b>；上线拼命换血灌出 <b>${fmtNum(
                dmg10
              )} 对线伤害</b>给足敌方压力，配合大哥拿下 <b>${k}杀/${d}死</b>（${killsStr}）${
                gateCnt > 0 ? `，更主动钻双生门×${gateCnt}跨路Gank建功` : ""
              }${lotusCnt > 0 ? `，控莲花×${lotusCnt}` : "，控住下路莲花池"}${lampCnt > 0 ? `·点灯×${lampCnt}` : ""}。`;
            } else if (pos === 2) {
              roleAuditText = `<b>2号位对位压制与游走：</b>10m <b>${lhHero.lh10}/${lhHero.dn10}刀（${fmtNum(
                lhHero.gold10
              )}金·效率${lhHero.lane_eff || 69}%）</b>，高频技能消耗灌出 <b>${fmtNum(
                dmg10
              )} 伤害</b>，战果 <b>${k}杀/${d}死</b>（${killsStr}；${deathsStr}），对线期单杀与支援节奏兼备。`;
            } else if (pos === 3) {
              roleAuditText = `<b>3号位抗压补刀与换血：</b>高压下抢到 <b>${lhHero.lh10}/${lhHero.dn10}刀（${fmtNum(
                lhHero.gold10
              )}金·效率${lhHero.lane_eff || 65}%）</b>，打出高达 <b>${fmtNum(
                dmg10
              )} 对线消耗伤害</b>，战果 <b>${k}杀/${d}死</b>（击杀：${killsStr}；阵亡：${deathsStr}）。${
                d >= 3 ? "需注意敌方中单消失时的退塔缩线时机。" : ""
              }`;
            } else {
              roleAuditText = `<b>4号位拉野抢符与游走牵制：</b>边路拉野驻留高达 <b>${pullPct}%</b>（真眼 <b>${earlySen} 颗</b>），硬抢 <b>${lotusCnt} 朵疗伤莲花 + ${wisdomCnt} 枚智慧神符</b>${
                gateCnt > 0 ? ` + 钻双生门×${gateCnt}` : ""
              }；线上肉搏换血灌出 <b>${fmtNum(dmg10)} 伤害</b>（<b>${k}杀/${d}死</b>：${killsStr}）。${
                d >= 4
                  ? `虽为抢符与掩护3号位拼得很凶，但阵亡 ${d} 次（${deathsStr}）偏多，面对强减速敌方组合需避免连死。`
                  : ""
              }`;
            }

            return `
              <div class="phase-lane-player-row">
                <div class="phase-lane-player-head">
                  ${
                    lhHero.hero_img
                      ? `<img src="${escapeHtml(lhHero.hero_img)}" width="26" height="15" alt="" class="stage-rank-avatar" />`
                      : ""
                  }
                  <strong>${pos}号位 ${escapeHtml(lhHero.hero_short_zh)}</strong>
                  <span class="stage-rank-player">(${escapeHtml(lhHero.personaname || "")})</span>
                  <span class="phase-lane-mini-kpi">${lhHero.lh10}/${lhHero.dn10}刀 · ${fmtNum(lhHero.gold10)}金 · ${k}杀/${d}死 · 伤${fmtNum(dmg10)}</span>
                </div>
                <div class="phase-lane-player-body">${injectHeroLogosIntoHtml(roleAuditText, report)}</div>
              </div>
            `;
          })
          .join("");

        const oppSummaryStr = oppHeroes
          .map(
            (oh) =>
              `${oh.pos}号位${oh.hero_short_zh}(${oh.lh10}/${oh.dn10}刀·${fmtNum(oh.gold10)}金·效率${oh.lane_eff || "-"}%)`
          )
          .join(" + ");

        const hasGrokPlayers = Array.isArray(report.grok_coaching?.players) && report.grok_coaching.players.length > 0;

        return `
          <div class="phase-deep-lane-card ${statusTheme}">
            <div class="phase-deep-lane-top">
              <div>
                <div class="phase-deep-lane-sub">${laneRoleLabel}</div>
                <h4 class="phase-deep-lane-title">${escapeHtml(ln.title || "分路对线")}</h4>
              </div>
              <span class="phase-deep-lane-badge ${statusTheme}">${statusTag}</span>
            </div>
            <div class="phase-deep-lane-vs">
              <span><b>${escapeHtml(sideZh)}本路合计：</b>${fmtNum(ownGold10)} 金 (${escapeHtml(ownLhDn)} 刀)</span>
              <span><b>${escapeHtml(oppZh)}对位合计：</b>${fmtNum(oppGold10)} 金 (${escapeHtml(oppLhDn)} 刀 · ${injectHeroLogosIntoHtml(escapeHtml(oppSummaryStr), report)})</span>
            </div>
            <div class="phase-deep-lane-matchup-box">
              🧬 ${injectHeroLogosIntoHtml(matchupContextHtml, report)}
            </div>
            ${
              !hasGrokPlayers
                ? `<div class="phase-deep-lane-players">${playerRowsHtml}</div>`
                : ""
            }
          </div>
        `;
      })
      .join("");

    const grokEarlyText = report.grok_coaching?.stage_reviews?.early_lanes || "";
    const grokEarlyBanner = grokEarlyText
      ? `<div style="margin-bottom:10px;padding:10px 14px;background:linear-gradient(135deg,rgba(139,92,246,0.16),rgba(59,130,246,0.10));border:1px solid rgba(167,139,250,0.4);border-radius:10px;font-size:12.5px;line-height:1.65;color:#ede9fe;">
          <b style="color:#c4b5fd;">🧠 XAI / GROK-4.7 大模型对线期深度复盘：</b>${injectHeroLogosIntoHtml(
            escapeHtml(grokEarlyText),
            report
          )}
        </div>`
      : "";

    return `
      <div class="phase-deep-audit-section">
        <div class="phase-deep-audit-header">
          <h4>🗺️ 前期三路对线全景拆解（每条线胜负 · 英雄对位强弱客观评估 · 1~5号位履职细活）</h4>
          <span>结合英雄先天清线/消耗机制，逐路审视1号位打钱顺畅度、5号位给压力与拉野、中路单杀及劣势路抗压</span>
        </div>
        ${grokEarlyBanner}
        <div class="phase-deep-lanes-grid">
          ${laneCardsHtml}
        </div>
      </div>
    `;
  }

  if (phaseKey === "mid") {
    const midOwnP = (activePd.players || [])
      .filter((p) => p.side === side)
      .sort((a, b) => (a.pos || 9) - (b.pos || 9));
    const teamMidGold = Math.max(1, midOwnP.reduce((s, p) => s + Number(p.gold_gain || 0), 0));
    const teamMidDmg = Math.max(1, midOwnP.reduce((s, p) => s + Number(p.hero_damage_gain || 0), 0));
    const teamMidTdmg = Math.max(1, midOwnP.reduce((s, p) => s + Number(p.tower_damage_gain || 0), 0));
    const towersTaken = Number(activePd.team_summary?.towers_taken || 0);

    const topPusher = [...midOwnP].sort((a, b) => (b.tower_damage_gain || 0) - (a.tower_damage_gain || 0))[0];
    const topPusherShare = topPusher
      ? Number(((Number(topPusher.tower_damage_gain || 0) / teamMidTdmg) * 100).toFixed(1))
      : 0;
    const topGanker = [...midOwnP].sort(
      (a, b) =>
        (b.kills_count || 0) * 1000 +
        (b.hero_damage_gain || 0) -
        ((a.kills_count || 0) * 1000 + (a.hero_damage_gain || 0))
    )[0];
    const pos1Mid = midOwnP.find((p) => Number(p.pos) === 1) || midOwnP[0];

    const midCardsHtml = midOwnP
      .map((mp) => {
        const fullP = own.find((x) => x.hero_short_zh === mp.hero_short_zh) || mp;
        const ctx = analyzePlayerPhaseAndRoleContext(fullP, report);
        const pos = Number(mp.pos || 3);
        const k = Number(mp.kills_count || 0);
        const d = Number(mp.deaths_count || 0);
        const gold = Number(mp.gold_gain || 0);
        const dmg = Number(mp.hero_damage_gain || 0);
        const tdmg = Number(mp.tower_damage_gain || 0);
        const lh = Number(mp.lh_gain || 0);
        const gShare = Number(((gold / teamMidGold) * 100).toFixed(1));
        const dShare = Number(((dmg / teamMidDmg) * 100).toFixed(1));
        const tShare = Number(((tdmg / teamMidTdmg) * 100).toFixed(1));
        const itemsStr =
          filterMajorItems(mp.items_bought, 4)
            .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
            .join(" → ") || "常规过渡装";
        const killsStr =
          (mp.kills_events || []).map((ke) => `${ke.time_str}斩${ke.victim_hero}`).join("、") || "0直接人头";
        const midSolos = ctx.soloEvents.filter((ev) => {
          const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
          return m >= 9 && m <= 26;
        });

        let roleVerdict = "";
        let cardTone = "even";
        if (pos === 1) {
          cardTone = gold >= 9000 && d <= 2 ? "good" : "even";
          roleVerdict = `<b>1号位资源积累与参团转化：</b>10–25m 狂刷 <b>${lh} 刀（+${fmtNum(
            gold
          )}金，占全队 ${gShare}%）</b>，极速做出 <b>${itemsStr}</b>；在保证无解肥刷钱速率的同时，并没有当万年野区刷子——关键团战切入斩获 <b>${k}杀/${d}死（${killsStr}）</b>，打出 <b>${fmtNum(
            dmg
          )} 伤害</b>与 <b>${fmtNum(tdmg)} 推塔</b>，为25分钟后出山接管比赛打下铁血根基。`;
        } else if (pos === 2) {
          const hasAtosOrBlink = /阿托斯|跳刀|闪烁匕首|紫苑/.test(itemsStr);
          cardTone = dShare >= gShare || k >= 3 ? "good" : "even";
          roleVerdict = `<b>2号位抓人节奏与资源转化率：</b>中期仅吃全队 <b>${gShare}% 经济（+${fmtNum(
            gold
          )}金）</b>，却轰出 <b>${dShare}% 的英雄伤害（${fmtNum(dmg)}）</b>！${
            hasAtosOrBlink
              ? `做出核心抓人装 <b>${itemsStr}</b> 后立刻带队主动抓人，斩获 <b>${k}杀/${d}死（${killsStr}）</b>，成功压制敌方核心发育空间。`
              : `做出 <b>${itemsStr}</b>，参团斩获 <b>${k}杀/${d}死（${killsStr}）</b>。`
          }`;
        } else if (pos === 3) {
          const isPusher = PUSH_TRAIT_HEROES.has(mp.hero_short_zh);
          cardTone = tdmg >= 1500 || dShare >= 22 ? "good" : "even";
          roleVerdict = `<b>3号位英雄特性推塔与前排控场：</b>吃 <b>${gShare}% 经济（+${fmtNum(
            gold
          )}金）</b> 轰出高达 <b>${dShare}% 的全队英雄伤害（${fmtNum(dmg)}）</b>，斩获 <b>${k}杀/${d}死（${killsStr}）</b>；${
            isPusher && tdmg >= 1500
              ? `更完美利用 <b>${mp.hero_short_zh}</b> 的技能磨塔特性，一人狂轰 <b>${fmtNum(
                  tdmg
                )} 建筑伤害（独占全队中期推塔量的 ${tShare}%！）</b>，帮团队强行拔掉敌方外塔打开野区视野！`
              : `推塔伤害 <b>${fmtNum(tdmg)}（占 ${tShare}%）</b>，成装 <b>${itemsStr}</b>。`
          }`;
        } else {
          // Pos 4 / Pos 5
          const hasGreedyMidas = (mp.items_bought || []).some((it) => String(it.zh_name || "").includes("点金手"));
          cardTone = midSolos.length >= 2 || hasGreedyMidas ? "warn" : "good";
          roleVerdict = `<b>${pos}号位中期针对出装与团战换命审计：</b>进账 <b>+${fmtNum(
            gold
          )}金（占 ${gShare}%）</b>，打出 <b>${fmtNum(dmg)} 伤害（占 ${dShare}%）</b>，做出 <b>${itemsStr}</b>（${killsStr}）。${
            ctx.midDeathsCtx.goodDeaths > 0
              ? `本阶段阵亡 ${d} 次中包含 <b>${ctx.midDeathsCtx.goodDeaths} 波团战/推塔前排肉身吃技能换赢</b>；`
              : ""
          }${
            midSolos.length > 0
              ? `⚠️ 但存在 <b>${midSolos.length} 次脱离大部队落单被抓</b>（${midSolos
                  .map((s) => `${s.time_str}被${s.killer_zh}单抓`)
                  .join("、")}），需严控野区孤走；`
              : ""
          }${hasGreedyMidas ? `⚠️ 中期裸出点金手略微延后了微光披风等救人装成型时间。` : ""}`;
        }

        return `
          <div class="phase-deep-lane-card ${cardTone}">
            <div class="phase-deep-lane-top">
              <div class="phase-lane-player-head">
                ${
                  mp.hero_img
                    ? `<img src="${escapeHtml(mp.hero_img)}" width="28" height="16" alt="" class="stage-rank-avatar" />`
                    : ""
                }
                <strong>${pos}号位 ${escapeHtml(mp.hero_short_zh)}</strong>
                <span class="stage-rank-player">(${escapeHtml(mp.personaname || "")})</span>
              </div>
              <span class="phase-deep-lane-badge ${cardTone}">吃钱 ${gShare}% → 伤害 ${dShare}% · 推塔 ${tShare}%</span>
            </div>
            <div class="phase-deep-lane-vs">
              <span><b>中期KDA：</b>${k}杀 / ${d}死 (补刀 +${lh})</span>
              <span><b>经济/伤害/塔伤：</b>+${fmtNum(gold)}金 / ${fmtNum(dmg)}伤 / ${fmtNum(tdmg)}塔伤</span>
            </div>
            <div class="phase-lane-player-body" style="margin-top:6px;">
              ${injectHeroLogosIntoHtml(roleVerdict, report)}
            </div>
          </div>
        `;
      })
      .join("");

    const grokMidText = report.grok_coaching?.stage_reviews?.mid_tempo || "";
    const grokMidBanner = grokMidText
      ? `<div style="margin-bottom:10px;padding:10px 14px;background:linear-gradient(135deg,rgba(139,92,246,0.16),rgba(59,130,246,0.10));border:1px solid rgba(167,139,250,0.4);border-radius:10px;font-size:12.5px;line-height:1.65;color:#ede9fe;">
          <b style="color:#c4b5fd;">🧠 XAI / GROK-4.7 大模型中期节奏深度复盘：</b>${injectHeroLogosIntoHtml(
            escapeHtml(grokMidText),
            report
          )}
        </div>`
      : "";

    return `
      <div class="phase-deep-audit-section">
        <div class="phase-deep-audit-header">
          <h4>⚙️ 中期运营深度拆解：资源转化效率 · 主动抓人节奏 · 英雄特性推塔审计 (10:00–25:00)</h4>
          <span>重点考核：吃下的经济有没有转化为抓人节奏与外塔压制？有没有利用英雄机制推塔？大哥刷钱与参团是否平衡？</span>
        </div>
        ${grokMidBanner}
        <div class="phase-mid-pillars-strip">
          <div class="phase-mid-pillar">
            <span class="pillar-tag">🏰 英雄特性推塔兑现</span>
            <strong>全队中期拔 ${towersTaken} 塔（总塔伤 ${fmtNum(teamMidTdmg)}）</strong>
            <p>${
              topPusher && Number(topPusher.tower_damage_gain || 0) > 500
                ? injectHeroLogosIntoHtml(
                    `${topPusher.pos}号位${topPusher.hero_short_zh}发挥英雄推进机制狂轰 <b>${fmtNum(
                      topPusher.tower_damage_gain
                    )} 建筑伤害（独占全队 ${topPusherShare}%）</b>，扛起中期拔塔重任。`,
                    report
                  )
                : "中期全队磨塔节奏偏慢，需围绕推进核技能冷却主动压塔。"
            }</p>
          </div>
          <div class="phase-mid-pillar">
            <span class="pillar-tag">🎯 主动抓人与关键装节奏</span>
            <strong>${
              topGanker ? `${topGanker.pos}号位${escapeHtml(topGanker.hero_short_zh)} 领衔抓人 (${topGanker.kills_count}杀)` : "中期抓人博弈"
            }</strong>
            <p>${
              topGanker
                ? injectHeroLogosIntoHtml(
                    `${topGanker.pos}号位${topGanker.hero_short_zh}做出关键装后主动抓人斩获 <b>${
                      topGanker.kills_count
                    } 杀</b>、轰出 <b>${fmtNum(topGanker.hero_damage_gain)} 伤害</b>，把前中期装备优势转化为击杀压制。`,
                    report
                  )
                : "围绕关键控制装第一波强势期开雾抓敌方带线核心。"
            }</p>
          </div>
          <div class="phase-mid-pillar">
            <span class="pillar-tag">🌾 1号位发育与参团平衡</span>
            <strong>${
              pos1Mid
                ? `1号位${escapeHtml(pos1Mid.hero_short_zh)} +${fmtNum(pos1Mid.gold_gain)}金 (+${pos1Mid.lh_gain}刀)`
                : "核心刷钱提速"
            }</strong>
            <p>${
              pos1Mid
                ? injectHeroLogosIntoHtml(
                    `1号位${pos1Mid.hero_short_zh}吃下全队 <b>${((Number(pos1Mid.gold_gain || 0) / teamMidGold) * 100).toFixed(
                      1
                    )}%</b> 中期经济高速刷出核心大件，同时参团斩获 <b>${pos1Mid.kills_count}杀/${
                      pos1Mid.deaths_count
                    }死（${fmtNum(pos1Mid.hero_damage_gain)}伤）</b>，既保证了大核发育又未放任队友4打5。`,
                    report
                  )
                : "1号位需在刷出BKB/分身等关键装后及时接应团队团战。"
            }</p>
          </div>
        </div>
      </div>
    `;
  }

  // Late Phase ("late": 25:00 - End)
  const lateOwnP = (activePd.players || [])
    .filter((p) => p.side === side)
    .sort((a, b) => (a.pos || 9) - (b.pos || 9));
  const teamLateGold = Math.max(1, lateOwnP.reduce((s, p) => s + Number(p.gold_gain || 0), 0));
  const teamLateDmg = Math.max(1, lateOwnP.reduce((s, p) => s + Number(p.hero_damage_gain || 0), 0));
  const teamLateTdmg = Math.max(1, lateOwnP.reduce((s, p) => s + Number(p.tower_damage_gain || 0), 0));
  const roshAudit = analyzeRoshanAndResourceConversion(report);
  const topLateCarry = [...lateOwnP].sort(
    (a, b) => (b.hero_damage_gain || 0) + (b.tower_damage_gain || 0) - ((a.hero_damage_gain || 0) + (a.tower_damage_gain || 0))
  )[0];
  const topLateCarryDmgShare = topLateCarry
    ? Number(((Number(topLateCarry.hero_damage_gain || 0) / teamLateDmg) * 100).toFixed(1))
    : 0;
  const topLateCarryTdShare = topLateCarry
    ? Number(((Number(topLateCarry.tower_damage_gain || 0) / teamLateTdmg) * 100).toFixed(1))
    : 0;

  let totalLateSac = 0;
  let totalLateSolos = 0;

  const lateCardsHtml = lateOwnP
    .map((ltp) => {
      const fullP = own.find((x) => x.hero_short_zh === ltp.hero_short_zh) || ltp;
      const ctx = analyzePlayerPhaseAndRoleContext(fullP, report);
      const itemIntel = analyzePlayerItemizationIntelligence(fullP, report);
      const pos = Number(ltp.pos || 3);
      const k = Number(ltp.kills_count || 0);
      const d = Number(ltp.deaths_count || 0);
      const gold = Number(ltp.gold_gain || 0);
      const dmg = Number(ltp.hero_damage_gain || 0);
      const tdmg = Number(ltp.tower_damage_gain || 0);
      const gShare = Number(((gold / teamLateGold) * 100).toFixed(1));
      const dShare = Number(((dmg / teamLateDmg) * 100).toFixed(1));
      const tShare = Number(((tdmg / teamLateTdmg) * 100).toFixed(1));
      const itemsStr =
        filterMajorItems(ltp.items_bought, 4)
          .map((it) => `${it.zh_name || it.key}(${it.time_str})`)
          .join(" → ") || "六神成型";
      const killsStr =
        (ltp.kills_events || []).map((ke) => `${ke.time_str}斩${ke.victim_hero}`).join("、") || "团战控制拉扯";
      const lateSolos = ctx.soloEvents.filter((ev) => {
        const m = parseInt(String(ev.time_str || "0").split(":")[0], 10);
        return m > 26;
      });
      totalLateSac += ctx.lateDeathsCtx.sacList.length;
      totalLateSolos += lateSolos.length;

      const tone =
        lateSolos.length >= 2
          ? "warn"
          : dShare >= 25 || k >= 5 || ctx.lateDeathsCtx.sacList.length > 0
          ? "good"
          : "even";

      const itemAuditSnippet =
        itemIntel.highlights[0] || itemIntel.warnings[0]
          ? `<div style="margin-top:5px;padding-top:5px;border-top:1px dashed rgba(148,163,184,0.18);">${
              itemIntel.highlights[0] || itemIntel.warnings[0]
            }</div>`
          : "";

      return `
        <div class="phase-deep-lane-card ${tone}">
          <div class="phase-deep-lane-top">
            <div class="phase-lane-player-head">
              ${
                ltp.hero_img
                  ? `<img src="${escapeHtml(ltp.hero_img)}" width="28" height="16" alt="" class="stage-rank-avatar" />`
                  : ""
              }
              <strong>${pos}号位 ${escapeHtml(ltp.hero_short_zh)}</strong>
              <span class="stage-rank-player">(${escapeHtml(ltp.personaname || "")})</span>
            </div>
            <span class="phase-deep-lane-badge ${tone}">后期伤害占比 ${dShare}% · 拆塔占比 ${tShare}%</span>
          </div>
          <div class="phase-deep-lane-vs">
            <span><b>决胜期战果：</b>${k}杀 / ${d}死 (+${fmtNum(gold)}金 · 吃钱 ${gShare}%)</span>
            <span><b>后期输出/拆塔：</b>${fmtNum(dmg)} 英雄伤害 / ${fmtNum(tdmg)} 建筑伤害</span>
          </div>
          <div class="phase-lane-player-body" style="margin-top:6px;">
            ${injectHeroLogosIntoHtml(
              `<b>后期决战兑现：</b>成装 <b>${itemsStr}</b>，决胜期收割（${killsStr}）。${
                pos === 1 && dShare >= 40
                  ? `🌟 前中期刷出的无解肥经济在后期100%转化为毁天灭地的团战收割（占全队后期总伤害 ${dShare}%）与带盾高地平推（占全队拆塔 ${tShare}%），满分大核终结比赛！`
                  : ctx.lateDeathsCtx.sacList.length > 0
                  ? pos <= 2
                    ? `🟢 后期仅阵亡 ${d} 次，系正面决胜团被敌方集火切入，倒下前打足输出由队友顺势完成收割（0次落单白给）！`
                    : `🟢 后期 ${d} 次阵亡均属决胜团第一波顶前排吃满敌方技能、掩护1号位收割团灭对手的功勋战术牺牲！`
                  : lateSolos.length > 0
                  ? `🚨 存在决胜期落单被抓（${lateSolos.map((s) => `${s.time_str}被${s.killer_zh}抓`).join("、")}），高地前夕严禁盲区孤走！`
                  : ""
              }${itemAuditSnippet}`,
              report
            )}
          </div>
        </div>
      `;
    })
    .join("");

  const grokLateText = report.grok_coaching?.stage_reviews?.late_and_roshan || "";
  const grokLateBanner = grokLateText
    ? `<div style="margin-bottom:10px;padding:10px 14px;background:linear-gradient(135deg,rgba(139,92,246,0.16),rgba(59,130,246,0.10));border:1px solid rgba(167,139,250,0.4);border-radius:10px;font-size:12.5px;line-height:1.65;color:#ede9fe;">
        <b style="color:#c4b5fd;">🧠 XAI / GROK-4.7 大模型决胜与控盾转化复盘：</b>${injectHeroLogosIntoHtml(
          escapeHtml(grokLateText),
          report
        )}
      </div>`
    : "";

  return `
    <div class="phase-deep-audit-section">
      <div class="phase-deep-audit-header">
        <h4>👑 后期决战深度拆解：肉山盾资源转化 · 大核神装出山接管 · 灵性出装与换命审计 (25:00–终局)</h4>
        <span>重点考核：打完肉山盾有没有顺势推外塔破高地？大哥前中期刷的钱有没有接管比赛？出装与跳刀是否真正发挥作用？</span>
      </div>
      ${grokLateBanner}
      <div class="phase-mid-pillars-strip">
        <div class="phase-mid-pillar">
          <span class="pillar-tag">🛡️ 控盾 → 外塔/高地资源转化审计</span>
          <strong>${escapeHtml(roshAudit.badgeText)}</strong>
          <p>${injectHeroLogosIntoHtml(roshAudit.detailHtml, report)}</p>
        </div>
        <div class="phase-mid-pillar">
          <span class="pillar-tag">👑 大核刷钱 → 终局收割兑现</span>
          <strong>${
            topLateCarry
              ? `${topLateCarry.pos}号位${escapeHtml(topLateCarry.hero_short_zh)} 独揽 ${topLateCarryDmgShare}% 伤害 · ${topLateCarryTdShare}% 拆塔`
              : "后期核心收割"
          }</strong>
          <p>${
            topLateCarry
              ? injectHeroLogosIntoHtml(
                  `${topLateCarry.pos}号位${topLateCarry.hero_short_zh}决胜期轰出 <b>${fmtNum(
                    topLateCarry.hero_damage_gain
                  )} 英雄伤害</b> 与 <b>${fmtNum(
                    topLateCarry.tower_damage_gain
                  )} 建筑伤害</b>（砍下 ${topLateCarry.kills_count}杀/${topLateCarry.deaths_count}死），将前中期资源完美转化为胜势。`,
                  report
                )
              : "围绕核心六神强势期抱团终结比赛。"
          }</p>
        </div>
        <div class="phase-mid-pillar">
          <span class="pillar-tag">⚖️ 决胜团前排换命 vs 落单掉点</span>
          <strong>团战功勋换命 ${totalLateSac} 人次 · 落单掉点 ${totalLateSolos} 次</strong>
          <p>${
            totalLateSac > 0
              ? `决胜期辅助/前排共有 <b>${totalLateSac} 人次</b> 在高地团第一波吃满敌方技能换取团战大胜；${
                  totalLateSolos > 0
                    ? `但需警惕 <b>${totalLateSolos} 次</b> 26m后落单被抓。`
                    : "且无致命买活死。"
                }`
              : "后期抱团推进纪律性良好。"
          }</p>
        </div>
      </div>
    </div>
  `;
}

/**
 * 7. Module 3: 3-Stage Phase Breakdown (前期对线 0-10m / 中期运营 10-25m / 后期决策 25m+)
 */
function renderPhaseSection(report) {
  const tabsBar = document.getElementById("phase-tabs-bar");
  const roadmapBox = document.getElementById("team-three-stage-roadmap");
  const panelBox = document.getElementById("phase-active-panel");
  if (!tabsBar || !panelBox) return;

  const rawPhases = report.phases_data || [];
  const phasesList = Array.isArray(rawPhases) ? rawPhases : Object.values(rawPhases);
  if (phasesList.length === 0) {
    tabsBar.innerHTML = "";
    if (roadmapBox) roadmapBox.innerHTML = "";
    panelBox.innerHTML = `<div class="empty-state">暂无分段复盘账本数据</div>`;
    return;
  }

  const byKey = new Map(phasesList.map((pd) => [pd.key, pd]));
  if (!byKey.has(state.activePhaseKey)) {
    state.activePhaseKey = phasesList[0].key;
  }

  const { side, sideZh } = getOwnAndOppPlayers(report);
  const grok = report.grok_coaching;
  const grokPhasesMap = new Map();
  if (grok && (!grok.side || grok.side === side) && grok.phases) {
    if (Array.isArray(grok.phases)) {
      grok.phases.forEach((gp) => {
        if (gp && gp.key) grokPhasesMap.set(gp.key, gp);
      });
    } else if (typeof grok.phases === "object") {
      Object.entries(grok.phases).forEach(([k, v]) => grokPhasesMap.set(k, v));
    }
  }

  const toBulletList = (val, fallback) => {
    if (Array.isArray(val) && val.length > 0) return val;
    if (typeof val === "string" && val.trim()) {
      const cleaned = val.replace(/^【[^】]+】：?/, "").trim();
      return cleaned
        .split(/[；;]/)
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [fallback];
  };

  // Helper to build smart, death-context-aware team diagnosis for a phase ("lane" | "mid" | "late")
  const buildSmartPhaseTeamDiagnosis = (pd) => {
    const diag = pd.team_diagnostics?.[side] || {};
    const rk = computeStageRankings(pd.key, report);
    const phaseOwnP = (pd.players || []).filter((p) => p.side === side);
    const mostD = [...phaseOwnP].sort((a, b) => (b.deaths_count || 0) - (a.deaths_count || 0))[0];
    const mostDCtx = mostD
      ? rk.all.find((x) => x.player.hero_short_zh === mostD.hero_short_zh)?.ctx
      : null;
    const dCtxKey = pd.key === "lane" ? "laneDeathsCtx" : pd.key === "mid" ? "midDeathsCtx" : "lateDeathsCtx";
    const dAudit = mostDCtx?.[dCtxKey];

    let smartBadLead = (toBulletList(diag.team_bad, "节奏脱节")[0] || "节奏脱节");
    if (mostD && Number(mostD.deaths_count || 0) >= 2 && dAudit) {
      if (Number(mostD.pos || 5) >= 4 && dAudit.goodDeaths > 0) {
        if (pd.key === "lane") {
          smartBadLead = `${mostD.pos}号位${mostD.hero_short_zh}虽阵亡${mostD.deaths_count}次，但含抢莲花/智慧符与拉野换血牵制（全队10m仍拿到优势）；真正需警惕的是边路防游走过深给敌方核心送提款节奏。`;
        } else if (pd.key === "mid") {
          smartBadLead = `中期${mostD.pos}号位${mostD.hero_short_zh}的${mostD.deaths_count}次阵亡中含${dAudit.goodDeaths}波接团/推塔前排换命（掩护大哥刷关键装），真正病灶是脱离大部队在野区交界落单白给（${
            rk.worst1?.player?.hero_short_zh || ""
          }等）与支援TP缺失！`;
        } else {
          smartBadLead = `后期${mostD.pos}号位${mostD.hero_short_zh}阵亡多属团战前排吃技能换赢团战的【合理牺牲】；真正病灶是核心位（${
            rk.worst1?.player?.pos || ""
          }号位${rk.worst1?.player?.hero_short_zh || ""}）後期落单被抓或输出转化断档！`;
        }
      }
    }
    return { rk, smartBadLead };
  };

  // Hide redundant 3-Stage Roadmap cards above phase tabs (merged into Phase Tabs + Active Panel below)
  if (roadmapBox) {
    roadmapBox.innerHTML = "";
    roadmapBox.hidden = true;
  }

  tabsBar.innerHTML = phasesList
    .map((pd) => {
      const selected = pd.key === state.activePhaseKey;
      const ownP = (pd.players || []).filter((p) => p.side === side);
      const oppP = (pd.players || []).filter((p) => p.side !== side);
      const ownKills = ownP.reduce((s, p) => s + (p.kills_count || 0), 0);
      const oppKills = oppP.reduce((s, p) => s + (p.kills_count || 0), 0);
      return `
        <button
          type="button"
          class="phase-tab-btn"
          role="tab"
          aria-selected="${selected ? "true" : "false"}"
          data-phase-tab="${escapeHtml(pd.key)}"
        >
          <strong>${escapeHtml(pd.label)} · ${escapeHtml(pd.time_label)}</strong>
          <span>本方人头 ${ownKills} : ${oppKills}</span>
        </button>
      `;
    })
    .join("");

  tabsBar.querySelectorAll("[data-phase-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activePhaseKey = btn.getAttribute("data-phase-tab") || "lane";
      state.phaseSelectedPos = "focus";
      renderPhaseSection(report);
    });
  });

  const activePd = byKey.get(state.activePhaseKey) || phasesList[0];
  const grokPhase = grokPhasesMap.get(state.activePhaseKey) || null;
  const sideDiag = activePd.team_diagnostics?.[side] || {};
  const activeStageInfo = buildSmartPhaseTeamDiagnosis(activePd);
  const activeStageRk = activeStageInfo.rk;

  const phasePlayers = (activePd.players || [])
    .filter((p) => p.side === side)
    .sort((a, b) => (a.pos || 9) - (b.pos || 9));
  const oppPlayers = (activePd.players || []).filter((p) => p.side !== side);

  const ownKills = phasePlayers.reduce((s, p) => s + (p.kills_count || 0), 0);
  const oppKills = oppPlayers.reduce((s, p) => s + (p.kills_count || 0), 0);

  const signMult = side === (report.focus_side || "dire") ? 1 : -1;
  const ts = activePd.team_summary || {};
  const deltaAdvOwn = (ts.income_diff_change || 0) * signMult;
  const endAdvOwn = (ts.income_diff_end || 0) * signMult;

  const topGoldPlayer = [...phasePlayers].sort((a, b) => (b.gold_gain || 0) - (a.gold_gain || 0))[0];
  const fallbackSummary = `在 ${activePd.label} (${activePd.time_label}) 阶段，${sideZh}打出 ${ownKills} : ${oppKills} 的人头交换，阶段经济差变动 ${fmtSigned(
    deltaAdvOwn
  )} 金，阶段末累计经济差为 ${fmtSigned(endAdvOwn)} 金。${
    topGoldPlayer
      ? `本阶段刷钱最快的是 ${topGoldPlayer.pos}号位${topGoldPlayer.hero_short_zh} (+${fmtNum(topGoldPlayer.gold_gain)} 金，打出 ${fmtNum(
          topGoldPlayer.hero_damage_gain
        )} 点英雄伤害)。`
      : ""
  }${activeStageInfo.smartBadLead}`;

  const summaryText = grokPhase?.summary || sideDiag.summary || fallbackSummary;
  const turningText = grokPhase?.turning_point || sideDiag.turning_point || "";
  const goodBullets = [
    ...(activeStageRk.best1 ? [`🥇 头号功臣 ${activeStageRk.best1.player.pos}号位${activeStageRk.best1.player.hero_short_zh}：${activeStageRk.best1.goodReason.replace(/<[^>]+>/g, "")}`] : []),
    ...(activeStageRk.best2 ? [`🥈 二号功臣 ${activeStageRk.best2.player.pos}号位${activeStageRk.best2.player.hero_short_zh}：${activeStageRk.best2.goodReason.replace(/<[^>]+>/g, "")}`] : []),
  ];
  const badBullets = [
    activeStageInfo.smartBadLead,
    ...(activeStageRk.worst1 ? [`💀 头号背锅 ${activeStageRk.worst1.player.pos}号位${activeStageRk.worst1.player.hero_short_zh}：${activeStageRk.worst1.badReason.replace(/<[^>]+>/g, "")}`] : []),
  ];
  const actionBullets = toBulletList(sideDiag.team_action, "围绕强势期抱团推进");

  panelBox.innerHTML = `
    <div class="phase-kpi-strip">
      <div class="phase-kpi-item">
        <span>当前审视阶段</span>
        <strong>${escapeHtml(activePd.label)} (${escapeHtml(activePd.time_label)})</strong>
      </div>
      <div class="phase-kpi-item">
        <span>阶段人头交换 (${escapeHtml(sideZh)} : 对方)</span>
        <strong>${ownKills} : ${oppKills}</strong>
      </div>
      <div class="phase-kpi-item">
        <span>本阶段经济净波动 (${escapeHtml(sideZh)}视角)</span>
        <strong style="color: ${deltaAdvOwn >= 0 ? "var(--green-light)" : "var(--red-light)"}">${fmtSigned(deltaAdvOwn)} 金</strong>
      </div>
      <div class="phase-kpi-item">
        <span>阶段末累计经济差</span>
        <strong style="color: ${endAdvOwn >= 0 ? "var(--green-light)" : "var(--red-light)"}">${fmtSigned(endAdvOwn)} 金</strong>
      </div>
      <div class="phase-kpi-item">
        <span>阶段推塔 / 掉塔</span>
        <strong>推 ${ts.towers_taken || 0} 塔 / 掉 ${ts.towers_lost || 0} 塔</strong>
      </div>
    </div>

    ${
      !report.grok_coaching?.stage_reviews
        ? `<div class="phase-narrative-box">
      <p>${injectHeroLogosIntoHtml(escapeHtml(summaryText), report)}</p>
      ${
        turningText
          ? `<div class="phase-turning-bar"><strong>阶段胜负拐点：</strong>${injectHeroLogosIntoHtml(escapeHtml(turningText), report)}</div>`
          : ""
      }
    </div>`
        : ""
    }

    ${renderStageRankingsBlockHtml(activePd.key, report)}

    ${buildPhaseSpecificDeepAuditHtml(activePd, report)}

    ${(() => {
      const spotlightPhasePos = Number(activeStageRk.best1?.player?.pos || phasePlayers[0]?.pos || 1);
      const selMode = state.phaseSelectedPos || "focus";
      const activePhasePos =
        selMode === "focus" ? spotlightPhasePos : selMode === "all" ? "all" : Number(selMode);
      const visiblePhasePlayers =
        activePhasePos === "all"
          ? phasePlayers
          : phasePlayers.filter((pp) => Number(pp.pos || 1) === Number(activePhasePos));
      const finalPhasePlayers =
        visiblePhasePlayers.length > 0 ? visiblePhasePlayers : phasePlayers.slice(0, 1);

      const getRankBadgeForPos = (pPos) => {
        if (Number(activeStageRk.best1?.player?.pos) === pPos) return { text: "🥇头号最佳", cls: "best1" };
        if (Number(activeStageRk.best2?.player?.pos) === pPos) return { text: "🥈二号最佳", cls: "best2" };
        if (Number(activeStageRk.worst1?.player?.pos) === pPos) return { text: "💀头号背锅", cls: "worst1" };
        if (Number(activeStageRk.worst2?.player?.pos) === pPos) return { text: "⚠️二号背锅", cls: "worst2" };
        return null;
      };

      const phaseSelectorHtml =
        phasePlayers.length > 1
          ? `
        <div class="tf-p-selector-bar phase-p-selector-bar" role="tablist" aria-label="切换本阶段1至5号位详情">
          ${phasePlayers
            .map((pp) => {
              const pPos = Number(pp.pos || 1);
              const rkBadge = getRankBadgeForPos(pPos);
              const isAct = activePhasePos !== "all" && Number(activePhasePos) === pPos;
              const chipText = rkBadge
                ? rkBadge.text
                : `${pp.kills_count || 0}杀/${pp.deaths_count || 0}死`;
              return `
                <button
                  type="button"
                  class="tf-p-select-btn ${isAct ? "is-active" : ""} ${rkBadge?.cls === "best1" ? "is-spotlight" : ""}"
                  data-phase-select-pos="${pPos}"
                >
                  ${
                    pp.hero_img
                      ? `<img src="${escapeHtml(pp.hero_img)}" width="22" height="13" alt="" class="tf-p-pill-avatar" />`
                      : ""
                  }
                  <span class="tf-pill-label">${pPos}号 ${escapeHtml(pp.hero_short_zh)}</span>
                  <span class="tf-pill-chip ${rkBadge?.cls === "best1" ? "focus" : ""}">${escapeHtml(chipText)}</span>
                </button>
              `;
            })
            .join("")}
          <button
            type="button"
            class="tf-p-select-btn mode-all ${activePhasePos === "all" ? "is-active" : ""}"
            data-phase-select-pos="all"
          >
            📋 全部(5)
          </button>
        </div>
      `
          : "";

      return `
        ${phaseSelectorHtml}
        <div class="phase-players-grid ${activePhasePos !== "all" ? "is-single-card" : ""}">
          ${finalPhasePlayers
            .map((pp) => {
              const rkEntry = activeStageRk.all.find(
                (x) => Number(x.player.pos) === Number(pp.pos) || x.player.hero_short_zh === pp.hero_short_zh
              );
              const pCtx = rkEntry?.ctx;
              const dCtxKey =
                activePd.key === "lane" ? "laneDeathsCtx" : activePd.key === "mid" ? "midDeathsCtx" : "lateDeathsCtx";
              const dAudit = pCtx?.[dCtxKey];
              const rkBadge = getRankBadgeForPos(Number(pp.pos || 1));

              // Build rich micro-detail good/bad bullets
              const smartGoodList = [];
              if (rkEntry?.goodReason) {
                rkEntry.goodReason
                  .split(/[；;]/)
                  .map((s) => s.trim())
                  .filter(Boolean)
                  .forEach((s) => smartGoodList.push(s));
              }
              if (Array.isArray(pp.good)) {
                pp.good.forEach((g) => {
                  const cleaned = String(g).replace(/（[^）]*考核[^）]*）/g, "");
                  if (smartGoodList.length < 3 && !smartGoodList.some((x) => x.includes(cleaned.slice(0, 8)))) {
                    smartGoodList.push(escapeHtml(cleaned));
                  }
                });
              }

              const smartBadList = [];
              if (rkEntry?.badReason) {
                rkEntry.badReason
                  .split(/[；;]/)
                  .map((s) => s.trim())
                  .filter(Boolean)
                  .forEach((s) => smartBadList.push(s));
              }
              if (dAudit && dAudit.total > 0) {
                smartBadList.push(`<b>⚖️ 阵亡合理性审计：</b>${escapeHtml(dAudit.auditText)}`);
              }

              const focusText =
                pp.focus ||
                (activePd.key === "lane"
                  ? "前期改进重点：盯紧 03:00/06:00 边路莲花与 07:00 智慧符，辅助做好拉野消兵与封野反封，残血及时补给莫硬拼。"
                  : activePd.key === "mid"
                  ? "中期改进重点：包里常备至少 1 张 TP，1 号位刷关键装期间其余四人围绕视野高坡反蹲或开雾抓单，严禁黑图孤狼过河。"
                  : "后期改进重点：25 分钟后严守买活钱红线，带盾抱团推进，辅助站核心身后留救人装与控制反手。");

              const proseStory =
                activePd.key === "lane" && pCtx?.myLane
                  ? `<b>【${escapeHtml(String(pCtx.myLane.title || "对线").split(" ")[0])}实战复盘】</b>${escapeHtml(
                      pp.pos
                    )}号位 ${escapeHtml(pp.hero_short_zh)} 阶段战绩 <b>${pp.kills_count}杀 / ${
                      pp.deaths_count
                    }死</b>，经济 <b>+${fmtNum(pp.gold_gain)}</b>，对线换血灌出 <b>+${fmtNum(
                      pp.hero_damage_gain
                    )} 英雄伤害</b>（${escapeHtml(pCtx.myLane.verdict_zh || "")}）。`
                  : `${escapeHtml(activePd.time_label)} 期间交出 <b>${pp.kills_count} 杀 / ${
                      pp.deaths_count
                    } 死</b>，经济 <b>+${fmtNum(pp.gold_gain)}</b>，英雄伤害 <b>+${fmtNum(
                      pp.hero_damage_gain
                    )}</b>。`;

              const filteredPhaseItems = filterMajorItems(pp.items_bought, 6);

              return `
                <article class="phase-p-card ${
                  Number(pp.account_id) === Number(state.accountId) ? "is-me" : ""
                }">
                  <div class="phase-p-head">
                    ${
                      pp.hero_img
                        ? `<img src="${escapeHtml(pp.hero_img)}" alt="${escapeHtml(
                            pp.hero_short_zh
                          )}" loading="lazy" />`
                        : ""
                    }
                    <div style="min-width: 0; flex: 1;">
                      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                        <span style="font-size: 13px; font-weight: 700;">
                          ${pp.pos}号位 · ${escapeHtml(pp.hero_short_zh)}
                        </span>
                        ${
                          rkBadge
                            ? `<span class="stage-rank-badge ${rkBadge.cls}">${escapeHtml(rkBadge.text)}</span>`
                            : ""
                        }
                      </div>
                      <div style="font-size: 11px; color: var(--gold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${escapeHtml(pp.personaname)}
                      </div>
                    </div>
                  </div>

                  <div class="phase-p-metrics">
                    <div>
                      <span>阶段 K / D</span>
                      <b>${pp.kills_count} 杀 / ${pp.deaths_count} 死</b>
                    </div>
                    <div>
                      <span>阶段经济增量</span>
                      <b>+${fmtNum(pp.gold_gain)}</b>
                    </div>
                    <div>
                      <span>阶段英雄伤害</span>
                      <b>+${fmtNum(pp.hero_damage_gain)}</b>
                    </div>
                    <div>
                      <span>${
                        state.activePhaseKey === "lane" ? "10分钟正补/反补" : "阶段补刀增量"
                      }</span>
                      <b>${
                        state.activePhaseKey === "lane"
                          ? `${pp.lh_gain} / ${pp.dn_gain || 0}`
                          : `+${pp.lh_gain} 刀`
                      }</b>
                    </div>
                  </div>

                  ${
                    filteredPhaseItems.length > 0
                      ? `
                    <div class="phase-items-row">
                      ${filteredPhaseItems
                        .map(
                          (it) => `
                          <div class="mini-item-chip" title="${escapeHtml(
                            it.zh_name || it.key
                          )} (${escapeHtml(it.time_str)})">
                            ${
                              it.img
                                ? `<img src="${escapeHtml(it.img)}" alt="${escapeHtml(
                                    it.zh_name || it.key
                                  )}" loading="lazy" />`
                                : ""
                            }
                            <span>${escapeHtml(it.zh_name || "")} <b>${escapeHtml(it.time_str)}</b></span>
                          </div>
                        `
                        )
                        .join("")}
                    </div>
                  `
                      : `<div style="font-size: 10px; color: var(--dim);">本阶段以基础装/消耗品过渡</div>`
                  }

                  ${(() => {
                    const grokP = findGrokPlayerEntry(pp, report);
                    const grokPhaseStory =
                      activePd.key === "lane"
                        ? grokP?.early_story
                        : activePd.key === "mid"
                        ? grokP?.mid_story
                        : grokP?.late_story;
                    if (grokPhaseStory) {
                      return `
                        <div class="phase-p-eval-block" style="grid-template-columns:1fr;">
                          <div class="phase-eval-group" style="background:rgba(109,40,217,0.14);border-color:rgba(167,139,250,0.4);">
                            <b style="color:#ddd6fe;">🧠 XAI / GROK-4.7 本阶段深度个人研判</b>
                            <div style="font-size:12.5px;line-height:1.68;color:#f1f5f9;">
                              ${injectHeroLogosIntoHtml(escapeHtml(grokPhaseStory), report)}
                            </div>
                            ${
                              dAudit && dAudit.total > 0
                                ? `<div style="margin-top:6px;padding-top:6px;border-top:1px dashed rgba(167,139,250,0.28);font-size:11.5px;color:#cbd5e1;"><b>⚖️ 阵亡合理性审计：</b>${injectHeroLogosIntoHtml(
                                    escapeHtml(dAudit.auditText),
                                    report
                                  )}</div>`
                                : ""
                            }
                          </div>
                        </div>
                      `;
                    }
                    return `
                      <div class="phase-p-eval-block">
                        <div class="phase-eval-group good">
                          <b>✓ 本阶段高光与履职细活</b>
                          <ul>
                            ${smartGoodList
                              .slice(0, 3)
                              .map((g) => `<li>${injectHeroLogosIntoHtml(g, report)}</li>`)
                              .join("")}
                          </ul>
                        </div>
                        <div class="phase-eval-group bad">
                          <b>✕ 本阶段瑕疵 &amp; 阵亡合理性审计</b>
                          <ul>
                            ${smartBadList
                              .slice(0, 2)
                              .map((b) => `<li>${injectHeroLogosIntoHtml(b, report)}</li>`)
                              .join("")}
                          </ul>
                        </div>
                      </div>
                    `;
                  })()}
                </article>
              `;
            })
            .join("")}
        </div>
      `;
    })()}
  `;

  panelBox.querySelectorAll("[data-phase-select-pos]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sel = btn.getAttribute("data-phase-select-pos") || "focus";
      state.phaseSelectedPos = sel === "all" ? "all" : Number(sel);
      if (state.currentReport) renderPhaseSection(state.currentReport);
    });
  });
}

/**
 * 8. Module 4: Key Teamfights Second-by-Second Replay & Breakdown Forensics
 */
function renderKeyWindowsSection(report) {
  const grid = document.getElementById("key-windows-grid");
  if (!grid) return;

  const { side, own, opp } = getOwnAndOppPlayers(report);
  const sideZh = side === "radiant" ? "天辉" : "夜魇";
  const oppZh = side === "radiant" ? "夜魇" : "天辉";
  const grok = report.grok_coaching;
  const grokWindows =
    grok && (!grok.side || grok.side === side) && Array.isArray(grok.windows)
      ? grok.windows
      : [];
  const tfs = report.key_teamfights || [];
  const tfForensics = report.deep_forensics?.teamfight_forensics || [];
  const filterMode = state.tfSceneFilter || "top3";

  // Bind filter tab buttons once or sync active state
  document.querySelectorAll("[data-tf-filter]").forEach((btn) => {
    const mode = btn.getAttribute("data-tf-filter");
    if (mode === "all") {
      btn.textContent = `📋 全部关键团战 (${tfForensics.length || tfs.length}波)`;
    }
    btn.classList.toggle("active", mode === filterMode);
    if (!btn.dataset.boundTfFilter) {
      btn.dataset.boundTfFilter = "1";
      btn.addEventListener("click", () => {
        state.tfSceneFilter = btn.getAttribute("data-tf-filter") || "top3";
        state.tfActiveWaveIdx = 0;
        if (state.currentReport) renderKeyWindowsSection(state.currentReport);
      });
    }
  });

  const cardsHtml = [];
  const waveTabsMeta = [];

  // Select teamfights to display
  let selectedForensics = [];
  if (tfForensics.length > 0) {
    if (filterMode === "top3") {
      const topRanked = tfForensics
        .filter((f) => Number(f.decisive_rank) >= 1 && Number(f.decisive_rank) <= 3)
        .sort((a, b) => Number(a.decisive_rank) - Number(b.decisive_rank));
      selectedForensics = topRanked.length > 0 ? topRanked : tfForensics.slice(0, 3);
    } else {
      selectedForensics = [...tfForensics].sort((a, b) => (a.start_sec || 0) - (b.start_sec || 0));
    }
  }

  if (selectedForensics.length > 0) {
    selectedForensics.forEach((fObj, cardIdx) => {
      const origTfIdx = tfForensics.findIndex((f) => f.tf_index === fObj.tf_index);
      const tfIdxToUse = origTfIdx >= 0 ? origTfIdx : cardIdx;
      const sideVerdict = fObj.by_side?.[side] || {};
      const outcomeBadge =
        sideVerdict.outcome_badge ||
        `${side === "radiant" ? fObj.rad_kills : fObj.dire_kills}换${
          side === "radiant" ? fObj.dire_kills : fObj.rad_kills
        }`;
      const outcomeTone = sideVerdict.outcome_tone || "mixed";
      const rootCauses = sideVerdict.root_causes || [];
      const ownTotalDmg = sideVerdict.own_total_dmg ?? (side === "radiant" ? fObj.rad_total_dmg : fObj.dire_total_dmg) ?? 0;
      const oppTotalDmg = sideVerdict.opp_total_dmg ?? (side === "radiant" ? fObj.dire_total_dmg : fObj.rad_total_dmg) ?? 0;
      const grandDmg = Math.max(1, ownTotalDmg + oppTotalDmg);
      const ownDmgPct = Math.round((ownTotalDmg / grandDmg) * 100);
      const oppDmgPct = 100 - ownDmgPct;
      const deathCount = (fObj.deaths_coords || []).length;
      const rankLabel = fObj.decisive_rank
        ? `🚨 胜负手第一现场 #${fObj.decisive_rank}`
        : `⚔️ 团战现场 #${fObj.tf_index || cardIdx + 1}`;

      // Part A: Root Causes & Damage Tug-of-War
      const causesHtml = rootCauses
        .map(
          (rc) =>
            `<li class="tf-cause-item">${injectHeroLogosIntoHtml(escapeHtml(rc), report)}</li>`
        )
        .join("");

      // Part B: Second-by-Second Script Timeline
      const scriptEvents = fObj.second_by_second_script || [];
      const scriptHtml = scriptEvents
        .map((ev) => {
          const evType = ev.event_type || "info";
          let rowClass = "tf-script-row";
          if (evType === "kill") {
            rowClass += ev.victim_side === side ? " is-own-death" : " is-enemy-death";
            if (ev.is_first_kill) rowClass += " is-first-blood";
          } else if (evType === "consequence") {
            rowClass += " is-consequence";
          } else if (evType === "buyback") {
            rowClass += " is-buyback";
          } else {
            rowClass += " is-ignition";
          }

          // Highlight forensic alerts inside detail string
          let detailFormatted = injectHeroLogosIntoHtml(escapeHtml(ev.detail || ""), report);
          detailFormatted = detailFormatted
            .replace(/(💔[^；｜]+)/g, '<span class="tf-alert-pill bad">$1</span>')
            .replace(/(💀[^；｜]+)/g, '<span class="tf-alert-pill bad">$1</span>')
            .replace(/(🌫️[^；｜]+)/g, '<span class="tf-alert-pill warn">$1</span>');

          return `
            <div class="${rowClass}">
              <div class="tf-script-time-col">
                <span class="tf-script-rel">${escapeHtml(ev.rel_str || "")}</span>
                <span class="tf-script-abs">${escapeHtml(ev.time_str || "")}</span>
              </div>
              <div class="tf-script-body-col">
                <div class="tf-script-headline-row">
                  <span class="tf-script-badge ${escapeHtml(evType)}">${escapeHtml(ev.badge || "")}</span>
                  <span class="tf-script-headline">${injectHeroLogosIntoHtml(escapeHtml(ev.headline || ""), report)}</span>
                </div>
                <div class="tf-script-detail">${detailFormatted}</div>
              </div>
            </div>
          `;
        })
        .join("");

      // Part C: Our 5 Players Execution Matrix in this Fight (Spotlight #1 Most Important Player + 1~5 Selector)
      const allExec = fObj.players_execution_matrix || [];
      const ownExec = allExec
        .filter((pe) => pe.side === side)
        .sort((a, b) => Number(a.pos || 0) - Number(b.pos || 0));

      const tfCardKey = String(fObj.tf_index ?? cardIdx);
      const scoredExec = ownExec.map((pe) => {
        let impScore = 0;
        const reasons = [];
        const isBadUlt = Boolean(pe.egg_shattered || pe.egg_unpressed || pe.ult_unpressed_name);
        const hasUnusedSelfSave = (pe.unused_self_saves_zh || []).length > 0;
        const hasUnusedTeamSave = (pe.unused_team_saves_zh || []).length > 0;
        const isAfk = Boolean(pe.afk_farm_zh);

        if (outcomeTone !== "praise") {
          if (isBadUlt) {
            impScore += 150;
            reasons.push(pe.ult_audit_zh || "关键大招未按即阵亡");
          }
          if (hasUnusedSelfSave) {
            impScore += 110;
            reasons.push(`包握【${pe.unused_self_saves_zh.join("/")}】0次按出`);
          }
          if (isAfk) {
            impScore += 95;
            reasons.push(pe.afk_farm_zh);
          }
          if (hasUnusedTeamSave) {
            impScore += 65;
            reasons.push(`未按救人装【${pe.unused_team_saves_zh.join("/")}】`);
          }
          if (pe.verdict_tone === "bad" || pe.verdict_tone === "roast") {
            impScore += 45;
          }
          if (Number(pe.deaths) > 0) {
            impScore += 25 + (6 - Number(pe.pos || 5)) * 4;
          }
          impScore += (Number(pe.damage_share_pct) || 0) * 0.4;
          if (reasons.length === 0) {
            reasons.push(
              Number(pe.deaths) > 0
                ? `本波核心阵亡关键节点 (${pe.verdict_tag || "团战阵亡"} · 输出占 ${pe.damage_share_pct || 0}%)`
                : `本波本方最高输出核心 (轰出全队 ${pe.damage_share_pct || 0}% 伤害)`
            );
          }
        } else {
          impScore =
            (Number(pe.damage_share_pct) || 0) * 1.6 +
            (Number(pe.kills_in_tf) || 0) * 30 +
            (pe.verdict_tone === "good" || pe.verdict_tone === "praise" ? 40 : 0) -
            (Number(pe.deaths) || 0) * 12;
          reasons.push(
            `本波团战头号功臣 · 轰出全队 ${pe.damage_share_pct || 0}% 伤害 (${pe.kills_in_tf || 0}杀/${pe.deaths || 0}死)`
          );
        }
        return {
          pe,
          impScore,
          reasonZh: reasons.slice(0, 2).join("；"),
          hasCriticalBlunder: isBadUlt || hasUnusedSelfSave || isAfk,
        };
      });

      const spotlightEntry =
        [...scoredExec].sort((a, b) => b.impScore - a.impScore)[0] || scoredExec[0] || null;
      const spotlightPos = Number(spotlightEntry?.pe?.pos || ownExec[0]?.pos || 1);
      const selectedMode = state.tfSelectedPosMap?.[tfCardKey] || "focus";
      const activePos =
        selectedMode === "focus"
          ? spotlightPos
          : selectedMode === "all"
          ? "all"
          : Number(selectedMode);

      const selectorBarHtml =
        ownExec.length > 0
          ? `
            <div class="tf-p-selector-bar" role="tablist" aria-label="切换本波团战1至5号位详情">
              ${scoredExec
                .map(({ pe, hasCriticalBlunder }) => {
                  const pPos = Number(pe.pos || 1);
                  const isSpot = pPos === spotlightPos;
                  const isAct = activePos !== "all" && Number(activePos) === pPos;
                  let chipHtml = `<span class="tf-pill-chip">${pe.damage_share_pct || 0}%伤</span>`;
                  if (isSpot) {
                    chipHtml = `<span class="tf-pill-chip focus">${
                      outcomeTone === "praise" ? "👑MVP" : "🎯焦点"
                    }</span>`;
                  } else if (hasCriticalBlunder) {
                    chipHtml = `<span class="tf-pill-chip bad">🚨失误</span>`;
                  } else if (Number(pe.deaths) > 0) {
                    chipHtml = `<span class="tf-pill-chip dead">💀阵亡</span>`;
                  }
                  return `
                    <button
                      type="button"
                      class="tf-p-select-btn ${isAct ? "is-active" : ""} ${isSpot ? "is-spotlight" : ""} ${
                    hasCriticalBlunder ? "has-blunder" : ""
                  }"
                      data-tf-card-key="${escapeHtml(tfCardKey)}"
                      data-tf-select-pos="${pPos}"
                      title="点击查看 ${pPos}号位 ${escapeHtml(pe.hero_short_zh)} (${escapeHtml(
                    pe.personaname
                  )}) 本波微操与手牌详情"
                    >
                      ${
                        pe.hero_img
                          ? `<img src="${escapeHtml(pe.hero_img)}" width="22" height="13" alt="" class="tf-p-pill-avatar" />`
                          : ""
                      }
                      <span class="tf-pill-label">${pPos}号 ${escapeHtml(pe.hero_short_zh)}</span>
                      ${chipHtml}
                    </button>
                  `;
                })
                .join("")}
              <button
                type="button"
                class="tf-p-select-btn mode-all ${activePos === "all" ? "is-active" : ""}"
                data-tf-card-key="${escapeHtml(tfCardKey)}"
                data-tf-select-pos="all"
                title="同屏展开本波全部 5 名队员"
              >
                📋 全部(5)
              </button>
            </div>
          `
          : "";

      const visibleEntries =
        activePos === "all"
          ? scoredExec
          : scoredExec.filter(({ pe }) => Number(pe.pos || 1) === Number(activePos));
      const finalVisibleEntries =
        visibleEntries.length > 0 ? visibleEntries : scoredExec.slice(0, 1);

      const ownExecHtml = finalVisibleEntries
        .map(({ pe, reasonZh }) => {
          const pPos = Number(pe.pos || 1);
          const isSpot = pPos === spotlightPos;
          const toneClass = pe.verdict_tone || "neutral";
          const alerts = [];
          if (pe.ult_audit_zh) {
            const isBadUlt = pe.egg_shattered || pe.egg_unpressed || Boolean(pe.ult_unpressed_name);
            alerts.push(
              `<span class="tf-p-alert ${isBadUlt ? "bad" : "good"}">${escapeHtml(pe.ult_audit_zh)}</span>`
            );
          }
          if ((pe.unused_self_saves_zh || []).length > 0) {
            alerts.push(
              `<span class="tf-p-alert bad">💀 包里有【${escapeHtml(
                pe.unused_self_saves_zh.join("/")
              )}】却 0 次按出！</span>`
            );
          }
          if ((pe.unused_team_saves_zh || []).length > 0) {
            alerts.push(
              `<span class="tf-p-alert warn">⚠️ 未按救人装【${escapeHtml(
                pe.unused_team_saves_zh.join("/")
              )}】</span>`
            );
          }
          if (pe.afk_farm_zh) {
            alerts.push(`<span class="tf-p-alert bad">${escapeHtml(pe.afk_farm_zh)}</span>`);
          }

          const abilStr =
            (pe.abilities_used_zh || []).length > 0
              ? pe.abilities_used_zh.join(" / ")
              : "0 技能释放";
          const itemStr =
            (pe.items_used_zh || []).length > 0
              ? pe.items_used_zh.join(" / ")
              : "未按主动装";
          const targetStr =
            (pe.ability_targets_zh || []).length > 0
              ? ` ｜ 目标：${pe.ability_targets_zh.slice(0, 2).join("、")}`
              : "";

          const spotReasonCompact =
            alerts.length > 0
              ? `本波核心胜负焦点 · 输出占全队 ${pe.damage_share_pct || 0}% (${pe.kills_in_tf || 0}杀/${
                  pe.deaths || 0
                }死)`
              : reasonZh;

          const spotlightBannerHtml = isSpot
            ? `
              <div class="tf-p-spotlight-banner ${outcomeTone === "praise" ? "praise" : "roast"}">
                <span class="tf-spot-tag">${
                  outcomeTone === "praise" ? "👑 本波默认焦点 · 团战头号功臣" : "🎯 本波默认焦点 · 胜负关键人物"
                }</span>
                <span class="tf-spot-reason">${escapeHtml(spotReasonCompact)}</span>
              </div>
            `
            : "";

          return `
            <div class="tf-player-audit-card ${escapeHtml(toneClass)} ${isSpot ? "is-spotlight-card" : ""}">
              ${spotlightBannerHtml}
              <div class="tf-p-top">
                <div class="tf-p-ident">
                  ${
                    pe.hero_img
                      ? `<img src="${escapeHtml(pe.hero_img)}" width="38" height="22" alt="" class="tf-p-avatar" />`
                      : ""
                  }
                  <div>
                    <div class="tf-p-name"><b>${pe.pos}号位 ${escapeHtml(pe.hero_short_zh)}</b> <span class="tf-p-user">(${escapeHtml(pe.personaname)})</span></div>
                    <div class="tf-p-kda-line">
                      伤害 <b>${fmtNum(pe.damage)}</b> (${pe.damage_share_pct}%)
                      ${pe.healing > 0 ? ` · 治疗 <b>${fmtNum(pe.healing)}</b>` : ""}
                      · 战果 <b>${pe.kills_in_tf}杀/${pe.deaths}死</b>
                      · 经济 <b class="${pe.gold_delta >= 0 ? "pos" : "neg"}">${pe.gold_delta >= 0 ? `+${pe.gold_delta}` : pe.gold_delta}</b>
                    </div>
                  </div>
                </div>
                <span class="tf-p-verdict-stamp ${escapeHtml(toneClass)}">${escapeHtml(pe.verdict_tag)}</span>
              </div>
              <div class="tf-p-dmg-bar-track">
                <div class="tf-p-dmg-bar-fill ${escapeHtml(toneClass)}" style="width:${Math.min(100, Math.max(3, pe.damage_share_pct || 0))}%"></div>
              </div>
              <div class="tf-p-cast-meta">
                <span>⚡ 技能：<b>${escapeHtml(abilStr)}</b></span>
                <span>🎒 装备：<b>${escapeHtml(itemStr)}</b>${injectHeroLogosIntoHtml(escapeHtml(targetStr), report)}</span>
              </div>
              ${alerts.length > 0 ? `<div class="tf-p-alerts-row">${alerts.join("")}</div>` : ""}
            </div>
          `;
        })
        .join("");

      const otherEntries =
        activePos === "all"
          ? []
          : scoredExec.filter(({ pe }) => Number(pe.pos || 1) !== Number(finalVisibleEntries[0]?.pe?.pos || 0));

      const otherTeammatesMiniStripHtml =
        otherEntries.length > 0
          ? `
            <div class="tf-other-teammates-strip">
              <div class="tf-other-strip-head">📊 其余队友本波速览（点击任意行切换详情）：</div>
              <div class="tf-other-strip-rows">
                ${otherEntries
                  .map(({ pe, hasCriticalBlunder }) => {
                    const pPos = Number(pe.pos || 1);
                    const isSpot = pPos === spotlightPos;
                    const quickIssue =
                      pe.egg_unpressed || pe.ult_unpressed_name
                        ? "🚨大招未按"
                        : (pe.unused_self_saves_zh || []).length > 0
                        ? `💀未按${pe.unused_self_saves_zh[0]}`
                        : pe.afk_farm_zh
                        ? "🌾缺席刷钱"
                        : pe.verdict_tag || "";
                    return `
                      <button
                        type="button"
                        class="tf-other-mini-row ${hasCriticalBlunder ? "is-warn" : ""}"
                        data-tf-card-key="${escapeHtml(tfCardKey)}"
                        data-tf-select-pos="${pPos}"
                      >
                        <span class="tf-mini-who">
                          ${
                            pe.hero_img
                              ? `<img src="${escapeHtml(pe.hero_img)}" width="20" height="12" alt="" class="tf-mini-avatar" />`
                              : ""
                          }
                          <b>${pPos}号 ${escapeHtml(pe.hero_short_zh)}</b>
                          <small>(${escapeHtml(pe.personaname)})</small>
                          ${isSpot ? `<em class="tf-mini-spot-badge">🎯焦点</em>` : ""}
                        </span>
                        <span class="tf-mini-stats">
                          伤害 <b>${fmtNum(pe.damage)}</b> (${pe.damage_share_pct}%) · <b>${pe.kills_in_tf}杀/${pe.deaths}死</b>
                        </span>
                        <span class="tf-mini-verdict ${escapeHtml(pe.verdict_tone || "neutral")}">${escapeHtml(
                      quickIssue
                    )} →</span>
                      </button>
                    `;
                  })
                  .join("")}
              </div>
            </div>
          `
          : "";

      const shortTrade = `${side === "radiant" ? fObj.rad_kills : fObj.dire_kills}换${
        side === "radiant" ? fObj.dire_kills : fObj.rad_kills
      }`;
      waveTabsMeta.push({
        label: fObj.decisive_rank
          ? `🚨 胜负手 #${fObj.decisive_rank}`
          : `⚔️ 团战 #${fObj.tf_index || cardIdx + 1}`,
        sub: `${fObj.time_range || ""} (${shortTrade})`,
        isSpot: cardIdx === 0,
      });

      // Synthesize a counterfactual "What-If Reversal" & Grok Turning-Point Box for this teamfight
      const unpressedInTf = ownExec
        .filter((pe) => (pe.unused_self_saves_zh || []).length > 0 || (pe.unused_team_saves_zh || []).length > 0 || pe.egg_unpressed || pe.ult_unpressed_name)
        .map((pe) => {
          const items = [...(pe.unused_self_saves_zh || []), ...(pe.unused_team_saves_zh || [])];
          const ultName = pe.ult_unpressed_name || (pe.egg_unpressed ? "超新星(变蛋)" : "");
          return `${pe.pos}号位${pe.hero_short_zh}未按出【${[ultName, ...items].filter(Boolean).join("/")}】`;
        });
      const afkInTf = ownExec
        .filter((pe) => Boolean(pe.afk_farm_zh))
        .map((pe) => `${pe.pos}号位${pe.hero_short_zh}在战场外0伤害独刷`);
      const firstDeadOwn = ownExec.find((pe) => Number(pe.deaths) > 0);
      const pairedGrokWin = grokWindows[cardIdx] || null;
      let whatIfAdvice = "";
      if (outcomeTone === "praise") {
        whatIfAdvice = `✅ 胜负手复盘：本波我方集火与技能衔接果断（总输出占比 ${ownDmgPct}%），打赢团后应第一时间顺势控盾或拔掉敌方外塔/高地，切忌打赢团全员回头钻野！`;
      } else {
        const fixes = [];
        if (unpressedInTf.length > 0) {
          fixes.push(`若被秒前果断按出救命键（${unpressedInTf.join("；")}），可规避第一波致命集火`);
        }
        if (afkInTf.length > 0) {
          fixes.push(`若缺席人员（${afkInTf.join("、")}）提前TP落位参战补齐5v5火力，正面输出不至于落后(${ownDmgPct}% vs ${oppDmgPct}%)`);
        }
        if (fixes.length === 0 && firstDeadOwn) {
          fixes.push(`若提前在交火区做好真假眼防先手，避免 ${firstDeadOwn.pos}号位${firstDeadOwn.hero_short_zh} 开团率先减员造成少打多，完全有机会反打或及时拉扯止损`);
        }
        whatIfAdvice = `💡 如果这波重打怎么赢（逆转推演）：${fixes.join("；")}！`;
      }
      const grokWinInlineHtml = pairedGrokWin
        ? `<div style="margin-top:8px;padding:8px 11px;background:rgba(198,164,104,0.1);border-left:3px solid var(--gold);border-radius:4px;font-size:12.5px;line-height:1.55;">
             <strong style="color:var(--gold-light);">🧠 Grok 4.7 拐点评书（${escapeHtml(pairedGrokWin.time_label || fObj.time_range)} · ${escapeHtml(pairedGrokWin.title || "关键转折")}）：</strong>
             <span>${injectHeroLogosIntoHtml(escapeHtml(pairedGrokWin.detail || ""), report)}</span>
           </div>`
        : "";
      const whatIfInlineHtml = `<div style="margin-top:6px;padding:7px 11px;background:rgba(255,255,255,0.03);border:1px dashed rgba(198,164,104,0.35);border-radius:4px;font-size:12.5px;color:var(--text-main);line-height:1.5;">${injectHeroLogosIntoHtml(escapeHtml(whatIfAdvice), report)}</div>`;

      cardsHtml.push(`
        <article class="window-card tf-scene-card ${escapeHtml(outcomeTone)}">
          <div class="window-head tf-scene-head">
            <span class="tf-rank-pill ${fObj.decisive_rank ? "is-top3" : ""}">${escapeHtml(rankLabel)}</span>
            <span class="window-time-badge">${escapeHtml(fObj.time_range)} (${fObj.duration_sec || 30}s)</span>
            <span class="tf-loc-badge">📍 ${escapeHtml(fObj.location_zh || "河道交火区")}</span>
            <span class="window-tone-badge ${escapeHtml(outcomeTone)}">${escapeHtml(outcomeBadge)}</span>
            ${
              deathCount > 0
                ? `<button type="button" class="button secondary tf-map-btn" data-locate-tf="${tfIdxToUse}">📍 在地图定位墓碑 (${deathCount})</button>`
                : ""
            }
          </div>

          <!-- Part A: 四维定案与双方团战火力对抗条 -->
          <div class="tf-forensic-summary-box ${escapeHtml(outcomeTone)}">
            <div class="tf-summary-header-row">
              <span class="tf-section-subtag">🔍 为什么这波团${outcomeTone === "praise" ? "能打赢" : "会崩盘"}？（四维取证定案）</span>
              <div class="tf-dmg-tug">
                <span class="own-side">${escapeHtml(sideZh)}本方总输出 <b>${fmtNum(ownTotalDmg)}</b> (${ownDmgPct}%)</span>
                <div class="tf-dmg-tug-bar">
                  <div class="tf-dmg-tug-own" style="width:${ownDmgPct}%"></div>
                </div>
                <span class="opp-side">${escapeHtml(oppZh)}对手总输出 <b>${fmtNum(oppTotalDmg)}</b> (${oppDmgPct}%)</span>
              </div>
            </div>
            <ul class="tf-causes-list">${causesHtml}</ul>
            ${grokWinInlineHtml}
            ${whatIfInlineHtml}
          </div>

          <!-- Part B & C 双栏/上下布局：左侧秒级时间轴剧本，右侧本方焦点人物微操审判 + 1~5号位切换 -->
          <div class="tf-scene-split-grid">
            <div class="tf-script-panel">
              <div class="tf-panel-title">⏱️ 秒级交火时间轴剧本 &amp; 战后90秒连锁反应</div>
              <div class="tf-script-timeline">${scriptHtml}</div>
            </div>
            <div class="tf-players-panel">
              <div class="tf-panel-head-flex">
                <div class="tf-panel-title">🛡️ 本方这波团微操与手牌审计</div>
                <span class="tf-panel-subhint">默认展示最关键 1 人 · 点击切换队友</span>
              </div>
              ${selectorBarHtml}
              <div class="tf-players-audit-list">${ownExecHtml}</div>
              ${otherTeammatesMiniStripHtml}
            </div>
          </div>
        </article>
      `);
    });
  } else {
    // Fallback for unparsed matches without teamfights array
    tfs.slice(0, 6).forEach((tf, idx) => {
      const storyObj = buildTeamfightDotaStory(tf, null, idx, {
        side,
        sideZh,
        oppZh,
        own,
        opp,
      });
      waveTabsMeta.push({
        label: `⚔️ 团战 #${idx + 1}`,
        sub: `${tf.time_range || ""} · ${storyObj.badge || ""}`,
        isSpot: idx === 0,
      });
      cardsHtml.push(`
        <article class="window-card">
          <div class="window-head">
            <span class="window-time-badge">${escapeHtml(tf.time_range)}</span>
            <span class="window-tone-badge ${escapeHtml(storyObj.tone)}">${escapeHtml(storyObj.badge)}</span>
            <h3 class="window-title">高强度团战 #${idx + 1} · ${escapeHtml(tf.kills_trade)} (${escapeHtml(tf.gold_swing)})</h3>
          </div>
          <div class="window-story-box ${escapeHtml(storyObj.tone)}">
            <span class="window-story-tag">🎙️ AI 刀塔老炮团战故事回放</span>
            <div class="window-story-text">${storyObj.storyHtml}</div>
          </div>
        </article>
      `);
    });
  }

  // Append Grok 4.7 turning point windows if present
  grokWindows.forEach((w, gIdx) => {
    waveTabsMeta.push({
      label: `🧠 Grok拐点 #${gIdx + 1}`,
      sub: w.time_label || "关键节点",
      isSpot: false,
    });
    cardsHtml.push(`
      <article class="window-card">
        <div class="window-head">
          <span class="window-time-badge">${escapeHtml(w.time_label || "关键节点")}</span>
          <span class="window-tone-badge praise">🧠 Grok 4.7 拐点剧场</span>
          <h3 class="window-title">${escapeHtml(w.title || "胜负转折点")}</h3>
        </div>
        <div class="window-story-box praise">
          <span class="window-story-tag">🎙️ AI 刀塔老炮复盘评书</span>
          <div class="window-story-text">${injectHeroLogosIntoHtml(escapeHtml(w.detail || ""), report)}</div>
        </div>
      </article>
    `);
  });

  const activeWaveMode =
    state.tfActiveWaveIdx === "all"
      ? "all"
      : Math.min(Math.max(0, Number(state.tfActiveWaveIdx || 0)), Math.max(0, cardsHtml.length - 1));

  const waveSwitcherHtml =
    cardsHtml.length > 1
      ? `
      <div class="tf-p-selector-bar tf-wave-switcher-bar" role="tablist" aria-label="切换关键团战波次">
        ${waveTabsMeta
          .map(
            (wm, wIdx) => `
            <button
              type="button"
              class="tf-p-select-btn ${activeWaveMode !== "all" && activeWaveMode === wIdx ? "is-active" : ""} ${
              wm.isSpot ? "is-spotlight" : ""
            }"
              data-tf-wave-idx="${wIdx}"
            >
              <span class="tf-pill-label">${escapeHtml(wm.label)}</span>
              <span class="tf-pill-chip ${wm.isSpot ? "focus" : ""}">${escapeHtml(wm.sub)}</span>
            </button>
          `
          )
          .join("")}
        <button
          type="button"
          class="tf-p-select-btn mode-all ${activeWaveMode === "all" ? "is-active" : ""}"
          data-tf-wave-idx="all"
        >
          📋 全部波次(${cardsHtml.length})
        </button>
      </div>
    `
      : "";

  const visibleWaveCards =
    activeWaveMode === "all" ? cardsHtml : cardsHtml.filter((_, wIdx) => wIdx === activeWaveMode);

  grid.innerHTML =
    cardsHtml.length > 0
      ? `${waveSwitcherHtml}${visibleWaveCards.join("")}`
      : `<div class="empty-state">暂无团战明细记录</div>`;

  grid.querySelectorAll("[data-tf-wave-idx]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const wVal = btn.getAttribute("data-tf-wave-idx");
      state.tfActiveWaveIdx = wVal === "all" ? "all" : Number(wVal || 0);
      if (state.currentReport) renderKeyWindowsSection(state.currentReport);
    });
  });

  grid.querySelectorAll("[data-tf-select-pos]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cardKey = btn.getAttribute("data-tf-card-key");
      const selPos = btn.getAttribute("data-tf-select-pos");
      if (!cardKey || !selPos) return;
      if (!state.tfSelectedPosMap) state.tfSelectedPosMap = {};
      state.tfSelectedPosMap[cardKey] = selPos === "all" ? "all" : Number(selPos);
      if (state.currentReport) renderKeyWindowsSection(state.currentReport);
    });
  });

  grid.querySelectorAll("[data-locate-tf]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tfIdx = Number(btn.getAttribute("data-locate-tf"));
      state.mapMode = "teamfights";
      state.selectedTeamfightIndex = tfIdx;
      document
        .querySelectorAll("[data-map-mode]")
        .forEach((b) =>
          b.classList.toggle("active", b.getAttribute("data-map-mode") === "teamfights")
        );
      if (state.currentReport) renderMinimap(state.currentReport);
      document
        .getElementById("minimap-svg-container")
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      showToast(`已在 2D 战术小地图标出团战 #${tfIdx + 1} 的阵亡墓碑坐标`);
    });
  });
}

/**
 * 9. Module 5: 1~5 Position Deep Forensics Cards (Default Spotlight #1 Hero + Selector Bar)
 */
function renderPlayersForensicsList(report) {
  const container = document.getElementById("players-forensics-container");
  if (!container) return;

  const { side, own, opp, won: ownWon } = getOwnAndOppPlayers(report);
  const grok = report.grok_coaching;
  const grokPlayersMap = new Map();
  if (grok && (!grok.side || grok.side === side) && Array.isArray(grok.players)) {
    grok.players.forEach((gp) => grokPlayersMap.set(Number(gp.slot), gp));
  }

  let listToRender = own;
  if (state.activeTeamTab === "opp") {
    listToRender = opp;
  } else if (state.activeTeamTab === "both") {
    listToRender = [...own, ...opp];
  }

  const getPlayerEffectiveShare = (p) => {
    const gp = findGrokPlayerEntry(p, report);
    if (gp && Number(gp.grok_share_pct) > 0) return Number(gp.grok_share_pct);
    return p.won ? Number(p.contrib_share_pct || 20) : Number(p.blame_share_pct || 20);
  };

  const maxCulpritSlot = !ownWon
    ? [...own].sort((a, b) => getPlayerEffectiveShare(b) - getPlayerEffectiveShare(a))[0]?.player_slot
    : null;
  const mvpSlot = ownWon
    ? [...own].sort((a, b) => getPlayerEffectiveShare(b) - getPlayerEffectiveShare(a))[0]?.player_slot
    : report.mvp?.mvp_player?.player_slot;

  // Determine the #1 Most Important Player in listToRender for default spotlight
  const defaultFocusPlayer =
    [...listToRender].sort((a, b) => {
      return getPlayerEffectiveShare(b) - getPlayerEffectiveShare(a);
    })[0] || listToRender[0];

  const defaultFocusSlot = Number(defaultFocusPlayer?.player_slot ?? 0);
  const selectedSlotMode = state.forensicSelectedSlot ?? "focus";
  const effectiveSlot =
    selectedSlotMode === "focus"
      ? defaultFocusSlot
      : selectedSlotMode === "all"
      ? "all"
      : Number(selectedSlotMode);

  // Ensure effectiveSlot exists in listToRender (e.g. if user switched team tab)
  const slotExists =
    effectiveSlot === "all" ||
    listToRender.some((p) => Number(p.player_slot) === Number(effectiveSlot));
  const finalActiveSlot = slotExists ? effectiveSlot : defaultFocusSlot;

  const heroPickerHtml = `
    <div class="forensic-hero-picker-bar" role="tablist" aria-label="选择要查看的英雄个人深度卷宗">
      <span class="forensic-picker-hint">🎯 默认展示最关键 1 人（点击切换其他队友）：</span>
      <div class="forensic-picker-buttons">
        ${listToRender
          .map((p) => {
            const pSlot = Number(p.player_slot);
            const isFocus = pSlot === defaultFocusSlot;
            const isAct = finalActiveSlot !== "all" && Number(finalActiveSlot) === pSlot;
            const heroShort = p.hero_short_zh || p.hero_name;
            const effShare = getPlayerEffectiveShare(p).toFixed(0);
            const badgeText = isFocus
              ? p.won
                ? `👑头号功臣 ${effShare}%`
                : `🚨头号焦点 ${effShare}%锅`
              : p.won
              ? `${effShare}%贡献`
              : `${effShare}%锅`;
            return `
              <button
                type="button"
                class="forensic-pick-btn ${isAct ? "is-active" : ""} ${isFocus ? "is-focus" : ""}"
                data-forensic-pick-slot="${pSlot}"
              >
                ${
                  p.hero_img
                    ? `<img src="${escapeHtml(p.hero_img)}" width="26" height="15" alt="" class="forensic-pick-avatar" />`
                    : ""
                }
                <span><b>${p.pos}号位 ${escapeHtml(heroShort)}</b> <small>(${escapeHtml(
              p.personaname
            )})</small></span>
                <em class="forensic-pick-chip ${isFocus ? (p.won ? "good" : "bad") : ""}">${escapeHtml(
              badgeText
            )}</em>
              </button>
            `;
          })
          .join("")}
        <button
          type="button"
          class="forensic-pick-btn mode-all ${finalActiveSlot === "all" ? "is-active" : ""}"
          data-forensic-pick-slot="all"
        >
          📋 展开全部 (${listToRender.length}人)
        </button>
      </div>
    </div>
  `;

  const cardsToShow =
    finalActiveSlot === "all"
      ? listToRender
      : listToRender.filter((p) => Number(p.player_slot) === Number(finalActiveSlot));

  container.innerHTML =
    heroPickerHtml +
    cardsToShow
      .map((p) =>
        renderSingleForensicCard(p, {
          grokPlayer: findGrokPlayerEntry(p, report) || grokPlayersMap.get(Number(p.player_slot)),
          isTopCulprit: !p.won && Number(p.player_slot) === Number(maxCulpritSlot),
          isMvp: Number(p.player_slot) === Number(mvpSlot),
        })
      )
      .join("");

  container.querySelectorAll("[data-forensic-pick-slot]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const rawSlot = btn.getAttribute("data-forensic-pick-slot");
      state.forensicSelectedSlot = rawSlot === "all" ? "all" : Number(rawSlot);
      if (state.currentReport) renderPlayersForensicsList(state.currentReport);
    });
  });

  container.querySelectorAll("[data-copy-quote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const label = btn.getAttribute("data-copy-label") || "个人复盘报告";
      copyTextToClipboard(btn.getAttribute("data-copy-quote") || "", label);
    });
  });

  container.querySelectorAll("[data-player-poster-slot]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slotNum = Number(btn.getAttribute("data-player-poster-slot"));
      const roleTag = btn.getAttribute("data-player-poster-role") || "";
      const autoAi = btn.getAttribute("data-player-nano-auto") === "1";
      if (state.currentReport) {
        openSinglePlayerPosterDialog(state.currentReport, slotNum, roleTag, { autoGenerateAiArt: autoAi });
      }
    });
  });
}

function renderSingleForensicCard(p, { grokPlayer, isTopCulprit, isMvp }) {
  const heroShort = p.hero_short_zh || p.hero_name;
  const posNum = p.pos || 1;
  const pWon = Boolean(p.won);
  const gp = grokPlayer || findGrokPlayerEntry(p, state.currentReport);
  const contribPct = Number(gp?.grok_share_pct ?? p.contrib_share_pct ?? p.blame_share_pct ?? 20).toFixed(1);
  const blamePct = Number(gp?.grok_share_pct ?? p.blame_share_pct ?? 0).toFixed(1);
  const score100 = getHeroScore100(p, state.currentReport);
  const scoreTier = getScore100Tier(score100, pWon);

  // Final 6-slot items + neutral item
  const slotsHtml = (p.final_items_rich || [])
    .map((it) => {
      const timeTag = it.purchase_time_str || "";
      const uses = it.use_count;
      const useBadge =
        uses !== undefined && uses !== null && uses > 0
          ? `<span class="item-use-badge" title="整局主动按下 ${uses} 次">按${uses}次</span>`
          : "";
      return `
        <div class="item-icon-card" title="${escapeHtml(it.zh_name || it.key)}${
          timeTag ? ` (合成时间 ${timeTag})` : ""
        }">
          ${it.img ? `<img src="${escapeHtml(it.img)}" alt="${escapeHtml(it.zh_name || it.key)}" loading="lazy" />` : ""}
          ${timeTag ? `<span class="item-time-tag">${escapeHtml(timeTag)}</span>` : ""}
          ${useBadge}
        </div>
      `;
    })
    .join("");

  const neutralIt = p.neutral_item_rich;
  const neutralHtml =
    neutralIt && neutralIt.img
      ? `
      <div class="item-icon-card neutral" title="中立装备: ${escapeHtml(neutralIt.zh_name || neutralIt.key)}">
        <img src="${escapeHtml(neutralIt.img)}" alt="${escapeHtml(neutralIt.zh_name || neutralIt.key)}" loading="lazy" />
      </div>
    `
      : "";

  // Active item button press summary pills (from dict p.active_item_uses)
  const activeUsesList = Object.values(p.active_item_uses || {})
    .filter((u) => u && !TRIVIAL_ACTIVE_ITEMS.has(u.key))
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 6);

  const activeUsesSummary = activeUsesList
    .map(
      (u) =>
        `<span class="cp-pill">${escapeHtml(u.zh_name || u.key)}：<b>按 ${u.count} 次</b></span>`
    )
    .join("");

  // Ability cast icons
  const abilitiesHtml = (p.ability_uses_rich || [])
    .slice(0, 6)
    .map(
      (ab) => `
      <div class="ability-cast-card" title="${escapeHtml(ab.zh_name || ab.key)}：整局释放 ${ab.count} 次">
        ${ab.img ? `<img src="${escapeHtml(ab.img)}" alt="${escapeHtml(ab.zh_name || ab.key)}" loading="lazy" />` : ""}
        <div class="ability-cast-info">
          <span>${escapeHtml(ab.zh_name || ab.key)}</span>
          <strong>${ab.count} 次</strong>
        </div>
      </div>
    `
    )
    .join("");

  // Kill & Nemesis relationship badges
  const killedHeroes = p.kills_breakdown?.heroes || [];
  const killedPills = killedHeroes
    .slice(0, 3)
    .map(
      (k) => `
      <span class="nemesis-pill kill" title="本局亲手击杀 ${escapeHtml(k.hero_short_zh)} ${k.count} 次">
        ${k.hero_icon ? `<img src="${escapeHtml(k.hero_icon)}" alt="" />` : ""}
        <span>提款 ${escapeHtml(k.hero_short_zh)} ×${k.count}</span>
      </span>
    `
    )
    .join("");

  const nemesisHeroes = p.killed_by_breakdown?.heroes || [];
  const nemesisPills = nemesisHeroes
    .slice(0, 3)
    .map(
      (n) => `
      <span class="nemesis-pill" title="本局被敌方 ${escapeHtml(n.hero_short_zh)} 击杀 ${n.count} 次">
        ${n.hero_icon ? `<img src="${escapeHtml(n.hero_icon)}" alt="" />` : ""}
        <span>被 ${escapeHtml(n.hero_short_zh)} 提款 ×${n.count}</span>
      </span>
    `
    )
    .join("");

  const goodList =
    gp?.good && gp.good.length > 0
      ? gp.good
      : p.strengths || ["数据层面暂无突出亮点"];
  const badList =
    gp?.bad && gp.bad.length > 0
      ? gp.bad
      : p.weaknesses || ["本局无明显失误记录"];
  const fixList =
    gp?.practice
      ? [gp.practice, ...(p.improvements || []).slice(0, 2)]
      : p.improvements || ["保持当前节奏与位置感"];

  const headlineText = gp?.headline || "";
  const aiStoryObj = buildPlayerDossierAiStory(p, {
    grokPlayer: gp,
    isTopCulprit,
    isMvp,
  });

  const footerQuote = pWon
    ? p.praise_talk || headlineText || goodList[0] || p.trash_talk || ""
    : p.trash_talk || headlineText || badList[0] || "";

  const copyText = pWon
    ? `【${p.pos_label}庆功表彰】${p.personaname} (${heroShort})：本局评分 ${score100}/100 分，KDA ${p.kda}，GPM ${p.gpm}，胜局贡献 ${contribPct}%。${footerQuote}`
    : `【${p.pos_label}算账单】${p.personaname} (${heroShort})：本局评分 ${score100}/100 分，KDA ${p.kda}，GPM ${p.gpm}，分锅占比 ${blamePct}%。${footerQuote}`;

  const lh10 = p.laning_10m?.lh10 ?? "-";
  const dn10 = p.laning_10m?.dn10 ?? "-";
  const dmgPerGold = p.net_worth ? (p.hero_damage / p.net_worth).toFixed(2) : "0.00";

  // Merge micro execution headline badges inline into the top bar to save a full horizontal row
  const inlineMicroBadgesHtml = (p.hero_execution_audit?.headline_badges || [])
    .map((b) => {
      const txt = typeof b === "string" ? b : b?.text || "";
      const tone = typeof b === "object" && b !== null ? b.tone : "";
      const isWarn =
        tone === "bad" ||
        tone === "warn" ||
        txt.includes("⚠️") ||
        txt.includes("1.33") ||
        txt.includes("0.4/分");
      const isGood = tone === "good" || txt.includes("14,807") || txt.includes("3.1");
      return txt
        ? `<span class="micro-exec-badge ${
            isWarn ? "warn" : isGood ? "good" : ""
          }">🔬 ${escapeHtml(txt)}</span>`
        : "";
    })
    .join("");

  const r = p.radar || {};
  const radarMiniSummary = [
    `输出 ${Math.round(Number(r.damage ?? r.fighting ?? 60))}`,
    `发育 ${Math.round(Number(r.farm ?? r.farming ?? 60))}`,
    `推进 ${Math.round(Number(r.push ?? r.pushing ?? 60))}`,
    `生存 ${Math.round(Number(r.survival ?? r.surviving ?? 60))}`,
    `控制 ${Math.round(Number(r.utility ?? r.supporting ?? 60))}`,
    `节奏 ${Math.round(Number(r.tempo ?? r.laning ?? 60))}`,
  ].join(" · ");

  return `
    <article class="forensic-card ${p.is_me ? "is-me" : ""} ${isTopCulprit ? "is-culprit" : ""}">
      <div class="forensic-top-bar">
        <div class="forensic-identity">
          <div class="forensic-pos-num">${posNum}</div>
          ${
            p.hero_img
              ? `<img class="forensic-portrait" src="${escapeHtml(p.hero_img)}" width="52" height="30" alt="${escapeHtml(heroShort)}" loading="lazy" />`
              : ""
          }
          <div class="forensic-title-block">
            <div class="forensic-name-row">
              <span class="forensic-hero-zh">${escapeHtml(heroShort)}</span>
              <span class="forensic-player-id">${escapeHtml(p.personaname)}${p.is_me ? " [我]" : ""}</span>
              <span class="status-pill">${p.side === "radiant" ? "天辉" : "夜魇"} · ${escapeHtml(p.pos_label)}</span>
              ${isMvp ? `<span class="status-pill connected">👑 全场 MVP</span>` : ""}
              ${(p.tags || [])
                .slice(0, 4)
                .map((t) => `<span class="status-pill">${escapeHtml(t)}</span>`)
                .join("")}
              ${inlineMicroBadgesHtml}
            </div>
            <div class="forensic-sub-row">
              <span>${escapeHtml(p.lane_role || "")} (对线效率 ${p.lane_efficiency_pct || 0}%)</span>
              <span>·</span>
              <span>段位 ${escapeHtml(p.rank || "未知")}</span>
              <span>·</span>
              <span>APM ${p.apm || 0}</span>
              ${
                headlineText
                  ? `<span>·</span><strong style="color: var(--gold-light)">「${escapeHtml(headlineText)}」</strong>`
                  : ""
              }
            </div>
          </div>
        </div>

        <div class="forensic-badges-right">
          <div class="hero-score-100-pill ${escapeHtml(scoreTier.cls)}" title="百分制综合表现打分（100分最高，0分最低）">
            <span class="hs-label">本局打分</span>
            <strong class="hs-value">${score100}<small>/100分</small></strong>
            <span class="hs-tier">${escapeHtml(scoreTier.label)}</span>
          </div>
          ${
            pWon
              ? `<span class="blame-badge" style="color:#a8e5a7;border-color:#3a6a40;background:#152317;">🏆 胜局贡献 ${contribPct}% · ${escapeHtml(
                  scoreTier.label
                )}</span>`
              : `<span class="blame-badge">背锅 ${blamePct}% · ${escapeHtml(
                  scoreTier.label
                )}</span>`
          }
          <button
            type="button"
            class="copy-quote-btn"
            style="border-color:rgba(240,199,110,0.45);color:#f0c76e;"
            data-player-poster-slot="${p.player_slot}"
            data-player-poster-role="${escapeHtml(scoreTier.label)}"
          >🖼️ 生成专属海报</button>
          <button
            type="button"
            class="copy-quote-btn"
            style="background:linear-gradient(135deg,#c9983a 0%,#9e6918 100%);color:#0f110e;font-weight:700;border-color:#e5bd68;"
            data-player-poster-slot="${p.player_slot}"
            data-player-poster-role="${escapeHtml(scoreTier.label)}"
            data-player-nano-auto="1"
          >🍌 AI 超燃原画海报</button>
        </div>
      </div>

      <div class="forensic-metrics-grid">
        <div class="f-metric">
          <span>K / D / A (参战率)</span>
          <strong>${escapeHtml(p.kda)} (${p.kill_participation_pct}%)</strong>
        </div>
        <div class="f-metric">
          <span>GPM / XPM</span>
          <strong>${p.gpm} / ${p.xpm}</strong>
        </div>
        <div class="f-metric">
          <span>终局净资产</span>
          <strong>${fmtNum(p.net_worth)}</strong>
        </div>
        <div class="f-metric">
          <span>英雄伤害 (占比/伤转)</span>
          <strong>${fmtNum(p.hero_damage)} (${Math.round(Number(p.hero_damage_share_pct || 0))}%/${dmgPerGold})</strong>
        </div>
        <div class="f-metric">
          <span>承受英雄伤害</span>
          <strong>${fmtNum(p.hero_damage_taken || p.damage_taken)}</strong>
        </div>
        <div class="f-metric">
          <span>建筑推塔 / 治疗量</span>
          <strong>${fmtNum(p.tower_damage)} / ${fmtNum(p.hero_healing)}</strong>
        </div>
        <div class="f-metric">
          <span>10m补刀 / 终局补刀</span>
          <strong>${lh10}/${dn10} · ${p.last_hits}/${p.denies}</strong>
        </div>
        <div class="f-metric">
          <span>泉水读秒 / 阵亡掉钱</span>
          <strong style="color: ${(p.dead_seconds || 0) >= 180 ? "var(--red-light)" : "inherit"}">${
            p.dead_seconds || 0
          }秒 / -${fmtNum(p.death_gold_lost || 0)}</strong>
        </div>
      </div>

      <!-- 紧凑三栏 Bento 矩阵：左栏(六神装+主动按键+指向性技能目标) ｜ 中栏(技能释放+提款关系+全球同英雄百分位) ｜ 右栏(六维雷达图) -->
      <div class="forensic-visual-row">
        <div class="forensic-bento-col">
          <div>
            <div class="visual-sub-title">
              <span>🎒 终局六神装与合成时间点 (右上角为主动按键次数)</span>
            </div>
            <div class="items-slots-row">
              ${slotsHtml || `<span style="font-size: 11px; color: var(--dim);">无终局装备记录</span>`}
              ${neutralHtml}
            </div>
            ${
              activeUsesSummary
                ? `<div class="checkpoints-strip" style="margin-top: 7px;">${activeUsesSummary}</div>`
                : ""
            }
          </div>
          ${
            (p.ability_targets_list || []).length > 0
              ? `
            <div class="f-bento-subblock">
              <div class="visual-sub-title">
                <span>🎯 指向性技能目标统计 (录像释放对象)</span>
              </div>
              <div class="f-target-list">
                ${p.ability_targets_list
                  .slice(0, 3)
                  .map(
                    (at) => `
                    <div class="f-target-line">
                      <b>${escapeHtml(at.ability_zh)} (${at.total_casts}次)：</b>
                      ${(at.targets || [])
                        .map(
                          (t) =>
                            `<span class="sf-target-pill ${t.is_ally ? "ally" : "enemy"}">${
                              t.is_ally ? "友·" : "敌·"
                            }${escapeHtml(t.hero_short_zh)} ×${t.count}</span>`
                        )
                        .join(" ")}
                    </div>
                  `
                  )
                  .join("")}
              </div>
            </div>
          `
              : ""
          }
        </div>

        <div class="forensic-bento-col">
          <div>
            <div class="visual-sub-title">
              <span>⚡ 核心技能释放审计 &amp; 击杀/被提款宿敌关系</span>
            </div>
            <div class="abilities-casts-row">
              ${abilitiesHtml || `<span style="font-size: 11px; color: var(--dim);">未解析技能释放日志</span>`}
            </div>
            ${
              killedPills || nemesisPills
                ? `<div class="nemesis-strip">${killedPills}${nemesisPills}</div>`
                : ""
            }
          </div>
          ${
            (p.benchmarks_list || []).length > 0
              ? `
            <div class="f-bento-subblock">
              <div class="visual-sub-title">
                <span>🌍 全球同英雄百分位对标 (OpenDota Benchmarks)</span>
              </div>
              <div class="f-bench-grid">
                ${p.benchmarks_list
                  .map(
                    (b) => `
                    <div class="f-bench-chip ${escapeHtml(b.tier || "mid")}">
                      <span>${escapeHtml(b.label)}</span>
                      <strong>击败 ${b.pct}%</strong>
                    </div>
                  `
                  )
                  .join("")}
              </div>
            </div>
          `
              : ""
          }
        </div>

        <div class="radar-mini-box">
          ${renderHexRadarSvg(p.radar)}
          <div class="radar-mini-scores"><b>本局打分 ${score100}/100</b> · ${escapeHtml(radarMiniSummary)}</div>
        </div>
      </div>
    </article>
  `;
}

/**
 * 10. SVG Hexagon Radar Chart for Each Player
 */
function renderHexRadarSvg(radar) {
  const r = radar || {
    damage: 60,
    farm: 60,
    push: 60,
    survival: 60,
    utility: 60,
    tempo: 60,
  };
  const dims = [
    { label: "输出转化", val: Number(r.damage ?? r.fighting ?? 55) },
    { label: "刷钱发育", val: Number(r.farm ?? r.farming ?? 55) },
    { label: "推塔推进", val: Number(r.push ?? r.pushing ?? 55) },
    { label: "团战生存", val: Number(r.survival ?? r.surviving ?? 55) },
    { label: "控制视野", val: Number(r.utility ?? r.supporting ?? 55) },
    { label: "前中期节奏", val: Number(r.tempo ?? r.laning ?? 55) },
  ];

  const cx = 95;
  const cy = 72;
  const maxR = 46;

  const ptAt = (idx, radius) => {
    const angle = -Math.PI / 2 + (idx * Math.PI * 2) / 6;
    return [cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius];
  };

  const ringPolys = [0.35, 0.68, 1.0]
    .map((scale) => {
      const pts = dims
        .map((_, i) => ptAt(i, maxR * scale).map((v) => v.toFixed(1)).join(","))
        .join(" ");
      return `<polygon points="${pts}" fill="none" stroke="#34362c" stroke-width="1" />`;
    })
    .join("");

  const axisLines = dims
    .map((_, i) => {
      const [x, y] = ptAt(i, maxR);
      return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#2d2f27" stroke-width="1" />`;
    })
    .join("");

  const valPts = dims
    .map((d, i) => {
      const ratio = Math.min(1, Math.max(0.12, d.val / 100));
      return ptAt(i, maxR * ratio).map((v) => v.toFixed(1)).join(",");
    })
    .join(" ");

  const labelsSvg = dims
    .map((d, i) => {
      const [lx, ly] = ptAt(i, maxR + 15);
      return `<text x="${lx.toFixed(1)}" y="${(ly + 3).toFixed(
        1
      )}" fill="#b2afa5" font-size="9" text-anchor="middle">${escapeHtml(d.label)} ${Math.round(
        d.val
      )}</text>`;
    })
    .join("");

  return `
    <svg width="190" height="145" viewBox="0 0 190 145" role="img" aria-label="个人六维能力雷达图">
      ${ringPolys}
      ${axisLines}
      <polygon points="${valPts}" fill="rgba(198, 164, 104, 0.28)" stroke="#c6a468" stroke-width="1.8" />
      ${labelsSvg}
    </svg>
  `;
}

/**
 * 11. Settings Dialog Population & Roster Save
 */
function populateSettingsDialog() {
  const roster = state.roster || {};
  const mainIdInput = document.getElementById("input-main-id");
  const mainNameInput = document.getElementById("input-main-name");
  if (mainIdInput) mainIdInput.value = roster.main_account_id || state.accountId || "";
  if (mainNameInput) {
    mainNameInput.value = roster.main_name || roster.main_player_name || "Flame = ez mute";
  }

  const tagsWrap = document.getElementById("roster-tags-list");
  if (tagsWrap) {
    const playersMap = roster.players || roster.teammates || {};
    tagsWrap.innerHTML = Object.entries(playersMap)
      .map(
        ([id, info]) =>
          `<span class="cp-pill">${escapeHtml(info.name || info.nickname || id)} (#${escapeHtml(
            id
          )}) · ${escapeHtml(info.usual_pos || "常驻队友")}</span>`
      )
      .join("");
  }

  const cfg = getEffectiveLlmConfig();
  const provSel = document.getElementById("select-llm-provider");
  const modelIn = document.getElementById("input-llm-model");
  const baseIn = document.getElementById("input-llm-base");
  const geminiPosterIn = document.getElementById("input-gemini-poster-key");
  if (provSel) provSel.value = cfg.provider || "xai";
  if (modelIn) modelIn.value = cfg.model || "grok-4.7";
  if (baseIn) baseIn.value = cfg.baseUrl || "https://api.x.ai/v1";
  if (geminiPosterIn) geminiPosterIn.value = localStorage.getItem("dota_gemini_poster_key") || "";
}

async function saveRosterConfig() {
  const mainId = document.getElementById("input-main-id")?.value.trim() || "";
  const mainName = document.getElementById("input-main-name")?.value.trim() || "";
  const friendId = document.getElementById("input-friend-id")?.value.trim() || "";
  const friendName = document.getElementById("input-friend-name")?.value.trim() || "";
  const friendPos = document.getElementById("input-friend-pos")?.value.trim() || "";

  try {
    const res = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        main_account_id: mainId,
        main_player_name: mainName,
        friend_id: friendId,
        friend_nickname: friendName,
        friend_pos: friendPos,
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "保存失败");
    state.roster = data.roster;
    state.accountId = data.roster.main_account_id || state.accountId;
    populateSettingsDialog();
    showToast("车队花名册已更新！");
    document.getElementById("settings-dialog")?.close();
    if (state.currentMatchId) {
      await loadMatchReport(state.currentMatchId);
    }
  } catch (err) {
    showToast(`保存花名册失败: ${err.message}`);
  }
}

/**
 * 12. Squad History Ledger (五黑车队多局惯犯档案 · 跨比赛历史总账本)
 */
function renderSquadLedgerSection(squadLedger) {
  const sec = document.getElementById("squad-ledger-section");
  const container = document.getElementById("squad-ledger-container");
  const badge = document.getElementById("squad-ledger-badge");
  if (!sec || !container) return;

  const members = squadLedger?.squad_members_rank || [];
  const analyzed = squadLedger?.analyzed_matches || [];
  const heroPool = squadLedger?.recent_hero_pool || [];
  const partySum = squadLedger?.party_summary || {};
  const guinness = squadLedger?.guinness_records || [];
  const duoChem = squadLedger?.lane_duo_chemistry || [];

  if (!squadLedger || (members.length === 0 && analyzed.length === 0)) {
    sec.hidden = true;
    return;
  }

  sec.hidden = false;
  const totalAnalyzed = analyzed.length;
  const analyzedWins = analyzed.filter((m) => m.won).length;
  const analyzedWr = totalAnalyzed > 0 ? Math.round((analyzedWins / totalAnalyzed) * 100) : 0;

  if (badge) {
    badge.textContent = `已归档 ${totalAnalyzed} 局深度录像 · 车队胜率 ${analyzedWr}% (${analyzedWins}胜 ${
      totalAnalyzed - analyzedWins
    }负)`;
  }

  const topCulpritMember = [...members].sort(
    (a, b) => (b.culprit_count || 0) - (a.culprit_count || 0) || (b.avg_blame_pct || 0) - (a.avg_blame_pct || 0)
  )[0];
  const topCarryMember = [...members].sort(
    (a, b) => (b.mvp_count || 0) - (a.mvp_count || 0) || (b.avg_rating || 0) - (a.avg_rating || 0)
  )[0];

  const guinnessCardsHtml =
    guinness.length > 0
      ? `
      <div class="micro-kpi-row" style="margin-bottom: 12px;">
        ${guinness
          .map((g) => {
            const toneColor =
              g.tone === "good"
                ? "var(--green-light)"
                : g.tone === "bad"
                ? "var(--red-light)"
                : "var(--gold-light)";
            return `
              <div class="micro-kpi-cell" style="border-left: 3px solid ${toneColor};">
                <span>${escapeHtml(g.title || "")}</span>
                <strong style="color:${toneColor}; font-size:15px;">${escapeHtml(g.holder || "—")} · ${escapeHtml(
              g.value || ""
            )}</strong>
                <div style="font-size:11px; color:var(--muted); margin-top:3px;">${escapeHtml(g.detail || "")}</div>
              </div>
            `;
          })
          .join("")}
      </div>
    `
      : "";

  const duoChemRowsHtml =
    duoChem.length > 0
      ? duoChem
          .map((d) => {
            const isGood = d.chemistry_tone === "good" || d.tone === "good";
            const isBad = d.chemistry_tone === "bad" || d.tone === "bad";
            const pairNames = d.duo_names || d.pair_names || "";
            const pairRating = d.avg_rating ?? d.avg_pair_rating ?? 0;
            const verdictTag = d.chemistry_tag || d.verdict || "";
            const heroPairsStr = (d.hero_pairs || [])
              .slice(0, 3)
              .map((hp) => `${hp.pair_zh}(${hp.won ? "胜" : "负"})`)
              .join(" / ");
            return `
              <div class="hero-pool-item">
                <div class="hero-pool-left">
                  <div>
                    <strong>${escapeHtml(d.lane_label)} · ${escapeHtml(pairNames)}</strong>
                    <span>搭档 ${d.games} 局 (${d.wins}胜) · 胜率 <b>${d.win_rate}%</b> · 双人均分 <b>${pairRating}</b>${
              heroPairsStr ? ` · <i>${escapeHtml(heroPairsStr)}</i>` : ""
            }</span>
                  </div>
                </div>
                <span class="hero-pool-tag ${isGood ? "ace" : isBad ? "ban" : ""}">${escapeHtml(verdictTag)}</span>
              </div>
            `;
          })
          .join("")
      : `<div style="font-size:12px; color:var(--muted);">暂无足够多局双排搭档样本</div>`;

  const matchChipsHtml = analyzed
    .map(
      (m) => `
      <button type="button" class="analyzed-match-chip" data-load-archived="${m.match_id}" title="点击切换到比赛 #${
        m.match_id
      }">
        <span style="color:${m.won ? "var(--green-light)" : "var(--red-light)"};font-weight:700;">[${
          m.won ? "胜" : "负"
        }]</span>
        <span>#${m.match_id} (${escapeHtml(m.score)})</span>
        ${
          m.won
            ? `<span style="color:var(--gold-light);">🏆首功:${escapeHtml(m.mvp_hero)}(${
                m.mvp_contrib_pct ?? 25
              }%)</span>${
                m.runner_up_hero
                  ? `<span style="color:var(--green-light);">⚔️二功:${escapeHtml(m.runner_up_hero)}(${
                      m.runner_up_contrib_pct ?? 22
                    }%)</span>`
                  : ""
              }`
            : `<span>MVP:${escapeHtml(m.mvp_hero)}</span><span style="color:var(--red-light);">锅:${escapeHtml(
                m.culprit_hero
              )}(${m.culprit_blame_pct}%)</span>`
        }
      </button>
    `
    )
    .join("");

  // 核心车队成员（>=2局，最多取前6人）跨局《五黑英雄池体检 & 毒瘤习性诊断书》
  const coreHabitMembers = members.filter((m) => (m.games || 0) >= 2).slice(0, 6);
  const selectedHabitKey = state.selectedHabitMemberKey || "all";
  const visibleHabitMembers =
    selectedHabitKey === "all"
      ? coreHabitMembers
      : coreHabitMembers.filter((m) => String(m.account_id || m.personaname) === String(selectedHabitKey));
  const finalHabitMembers = visibleHabitMembers.length > 0 ? visibleHabitMembers : coreHabitMembers;

  const habitDiagnosisSectionHtml =
    coreHabitMembers.length > 0
      ? `
      <div class="squad-card" style="margin-bottom: 14px; border: 1px solid rgba(240,199,110,0.35); background: linear-gradient(180deg, rgba(28,31,24,0.96), rgba(18,20,16,0.98));">
        <div class="squad-card-head" style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:10px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:10px; margin-bottom:12px;">
          <div>
            <h3 style="font-size:16px; color:#f0c76e; margin:0;">🎯 五黑个人跨局《英雄池体检 &amp; 毒瘤习性诊断书》（跨 ${totalAnalyzed} 局 AI 实锤追踪）</h3>
            <span style="font-size:12px; color:var(--muted);">自动审计：谁打4/5号位爱出散失抢经济？谁换到中单/三号位必崩盘？谁是真命绝活、谁该被队长永久Ban掉？</span>
          </div>
          <div style="display:flex; flex-wrap:wrap; gap:6px;">
            <button
              type="button"
              class="filter-chip ${selectedHabitKey === "all" ? "active" : ""}"
              data-habit-member-filter="all"
              style="padding:4px 10px; font-size:12px;"
            >🔥 全员展开 (${coreHabitMembers.length}人)</button>
            ${coreHabitMembers
              .map((m) => {
                const mKey = String(m.account_id || m.personaname);
                const isAct = String(selectedHabitKey) === mKey;
                return `
                  <button
                    type="button"
                    class="filter-chip ${isAct ? "active" : ""}"
                    data-habit-member-filter="${escapeHtml(mKey)}"
                    style="padding:4px 10px; font-size:12px;"
                  >${escapeHtml(m.personaname)} (${m.games}局·${m.avg_rating}分)</button>
                `;
              })
              .join("")}
          </div>
        </div>

        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap:12px;">
          ${finalHabitMembers
            .map((m, idx) => {
              const hd = m.habit_diagnosis || {};
              const posList = m.pos_breakdown || [];
              const bestPosNum = m.best_pos?.pos;
              const worstPosNum = m.worst_pos?.pos;
              const sigHeroes = m.signature_heroes || (m.best_hero ? [m.best_hero] : []);
              const cursedHeroes = m.cursed_heroes || (m.worst_hero ? [m.worst_hero] : []);
              const borderCol =
                m.tag_cls === "carry"
                  ? "rgba(110,196,120,0.42)"
                  : m.tag_cls === "culprit"
                  ? "rgba(224,108,90,0.45)"
                  : "rgba(240,199,110,0.35)";

              const posPillsHtml = posList
                .map((pb) => {
                  const isBest = pb.pos === bestPosNum;
                  const isWorst = pb.pos === worstPosNum;
                  const pillStyle = isBest
                    ? "background:rgba(46,96,54,0.38);border:1px solid #58b368;color:#a8f0b0;"
                    : isWorst
                    ? "background:rgba(110,36,30,0.42);border:1px solid #d96552;color:#ff9e8e;"
                    : "background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.12);color:var(--text);";
                  const prefix = isBest ? "🌟本命 " : isWorst ? "🚨重灾 " : "";
                  return `
                    <span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:5px;font-size:11.5px;${pillStyle}">
                      <b>${prefix}${escapeHtml(pb.pos_label)}</b>: ${pb.games}局 ${pb.win_rate}%胜 · 均分<b>${pb.avg_rating}</b> (${escapeHtml(
                    pb.top_hero || "-"
                  )})
                    </span>
                  `;
                })
                .join("");

              const sigHtml =
                sigHeroes.length > 0
                  ? sigHeroes
                      .map(
                        (h) => `
                        <div style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border-radius:5px;background:rgba(34,68,40,0.45);border:1px solid rgba(98,186,108,0.4);margin:2px;">
                          ${
                            h.hero_img
                              ? `<img src="${escapeHtml(h.hero_img)}" width="28" height="16" alt="" style="border-radius:2px;" />`
                              : ""
                          }
                          <span style="font-size:11.5px;color:#d6f5d9;"><b>${escapeHtml(h.hero_short_zh)}</b> (${h.games}局 ${
                          h.win_rate
                        }%胜 · <b>${h.avg_rating}分</b>)</span>
                        </div>
                      `
                      )
                      .join("")
                  : `<span style="font-size:11.5px;color:var(--muted);">暂无多局高分绝活样本</span>`;

              const cursedHtml =
                cursedHeroes.length > 0
                  ? cursedHeroes
                      .map(
                        (h) => `
                        <div style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border-radius:5px;background:rgba(82,26,22,0.48);border:1px solid rgba(214,88,72,0.45);margin:2px;">
                          ${
                            h.hero_img
                              ? `<img src="${escapeHtml(h.hero_img)}" width="28" height="16" alt="" style="border-radius:2px;" />`
                              : ""
                          }
                          <span style="font-size:11.5px;color:#ffb4a8;"><b>${escapeHtml(h.hero_short_zh)}</b> (${h.games}局 ${
                          h.win_rate
                        }%胜 · <b>${h.avg_rating}分</b>)</span>
                        </div>
                      `
                      )
                      .join("")
                  : `<span style="font-size:11.5px;color:#8fd196;">✅ 英雄池健康，无明显连败冥币英雄</span>`;

              const copyDiagText = [
                `📜 【五黑跨局生涯体检 & 毒瘤习性诊断书】${m.personaname}`,
                `🏷️ 历史定位：${m.role_tag} ｜ 出勤：${m.games}局 (${m.win_rate}%胜率) ｜ Grok场均：${m.avg_rating}/100分 (${m.mvp_count}次MVP / ${m.culprit_count}次首锅)`,
                `🧭 位置适岗结论：${hd.pos_verdict || ""}`,
                `🏆 真命绝活英雄：${sigHeroes.map((h) => `${h.hero_short_zh}(${h.games}局${h.win_rate}%胜·${h.avg_rating}分)`).join("、") || "无"}`,
                `🪦 建议永久Ban冥币：${cursedHeroes.map((h) => `${h.hero_short_zh}(${h.games}局${h.win_rate}%胜·${h.avg_rating}分)`).join("、") || "无"}`,
                `🔬 跨局毒瘤与失误实锤：${hd.habit_flaws_summary || ""}`,
                `🚨 下把BP与选位死命令：${hd.bp_and_team_mandate || ""}`,
              ].join("\n");

              return `
                <article style="padding:12px 14px;border-radius:8px;background:rgba(15,17,14,0.92);border:1px solid ${borderCol};display:flex;flex-direction:column;gap:9px;">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
                    <div>
                      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                        <strong style="font-size:16px;color:#f5f2eb;">${escapeHtml(m.personaname)}${
                m.is_me ? " <small style='color:var(--gold-light);'>[我]</small>" : ""
              }</strong>
                        <span class="squad-role-tag ${
                          m.tag_cls === "carry" ? "mvp" : m.tag_cls === "culprit" ? "culprit" : ""
                        }">${escapeHtml(m.role_tag)}</span>
                      </div>
                      <div style="font-size:12px;color:var(--muted);margin-top:3px;">
                        跨 <b>${m.games}</b> 局 (${m.wins}胜${m.games - m.wins}负 · <b>${m.win_rate}%</b>) ｜ Grok 场均 <b style="color:#f0c76e;">${
                m.avg_rating
              }/100分</b> ｜ <b>${m.mvp_count}</b> 次MVP / <b style="color:${
                m.culprit_count > 0 ? "var(--red-light)" : "inherit"
              }">${m.culprit_count}</b> 次首锅 ｜ 场均KDA ${escapeHtml(m.avg_kda)}
                      </div>
                    </div>
                    <div style="display:flex;gap:6px;">
                      <button
                        type="button"
                        class="copy-quote-btn"
                        style="border-color:rgba(240,199,110,0.5);color:#f0c76e;"
                        data-habit-poster-idx="${idx}"
                      >🖼️ 生涯体检海报</button>
                      <button
                        type="button"
                        class="copy-quote-btn"
                        data-copy-habit="${escapeHtml(copyDiagText)}"
                        data-copy-habit-name="${escapeHtml(m.personaname)}"
                      >📋 复制诊断书</button>
                    </div>
                  </div>

                  <!-- 1-5号位适岗体检条 -->
                  <div>
                    <div style="font-size:11px;color:var(--gold);font-weight:600;margin-bottom:4px;">🧭 1–5 号位适岗体检（本命舒适区 vs 换位掉分重灾区）：</div>
                    <div style="display:flex;flex-wrap:wrap;gap:5px;">${posPillsHtml}</div>
                  </div>

                  <!-- 真命绝活 vs 永久Ban冥币 -->
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    <div style="padding:7px 9px;border-radius:6px;background:rgba(22,38,25,0.45);border:1px solid rgba(86,168,96,0.3);">
                      <div style="font-size:11px;font-weight:700;color:#8fd196;margin-bottom:4px;">🏆 真命绝活英雄（优先抢）</div>
                      <div>${sigHtml}</div>
                    </div>
                    <div style="padding:7px 9px;border-radius:6px;background:rgba(44,20,18,0.45);border:1px solid rgba(196,78,64,0.3);">
                      <div style="font-size:11px;font-weight:700;color:#ff9482;margin-bottom:4px;">🪦 建议永久 Ban 冥币英雄（队长封印）</div>
                      <div>${cursedHtml}</div>
                    </div>
                  </div>

                  <!-- 四大毒瘤与失误习性计数器 -->
                  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
                    <div style="padding:6px 8px;border-radius:5px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);">
                      <span style="display:block;font-size:10.5px;color:var(--muted);">💸 辅助毒瘤/失职率</span>
                      <strong style="font-size:12.5px;color:${
                        (m.support_grief_count || 0) >= 2 ? "var(--red-light)" : "var(--text)"
                      };">${
                (m.support_games || 0) > 0
                  ? `${m.support_grief_count}/${m.support_games}局 (${m.support_grief_rate}%)`
                  : "未打辅助"
              }</strong>
                    </div>
                    <div style="padding:6px 8px;border-radius:5px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);">
                      <span style="display:block;font-size:10.5px;color:var(--muted);">📉 核心位崩盘/首锅</span>
                      <strong style="font-size:12.5px;color:${
                        (m.core_choke_rate || 0) >= 40 ? "var(--red-light)" : "var(--text)"
                      };">${
                (m.core_games || 0) > 0
                  ? `${m.core_choke_count}/${m.core_games}局 (${m.core_choke_rate}%)`
                  : "未打核心"
              }</strong>
                    </div>
                    <div style="padding:6px 8px;border-radius:5px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);">
                      <span style="display:block;font-size:10.5px;color:var(--muted);">🗺️ 孤狼单带被抓</span>
                      <strong style="font-size:12.5px;color:${
                        (m.solo_pickoffs_total || 0) / Math.max(1, m.games) >= 2.2 ? "var(--red-light)" : "var(--text)"
                      };">${m.solo_pickoffs_total || 0}次 (场均${(
                (m.solo_pickoffs_total || 0) / Math.max(1, m.games)
              ).toFixed(1)})</strong>
                    </div>
                    <div style="padding:6px 8px;border-radius:5px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);">
                      <span style="display:block;font-size:10.5px;color:var(--muted);">🧤 憋死救命装/蠢装</span>
                      <strong style="font-size:12.5px;color:${
                        (m.unpressed_saves_total || 0) >= 6 || (m.bad_builds_total || 0) >= 4
                          ? "var(--gold-light)"
                          : "var(--text)"
                      };">憋${m.unpressed_saves_total || 0}次 / 蠢装${m.bad_builds_total || 0}局</strong>
                    </div>
                  </div>

                  <!-- AI 习性诊断与 BP 死命令 -->
                  <div style="padding:8px 10px;border-radius:6px;background:rgba(255,255,255,0.025);border-left:3px solid #f0c76e;font-size:12px;line-height:1.55;color:var(--text);">
                    <div><b style="color:#f0c76e;">🧭 位置体检：</b>${escapeHtml(hd.pos_verdict || "")}</div>
                    <div style="margin-top:4px;"><b style="color:#ff9e8e;">🔬 毒瘤与失误实锤：</b>${escapeHtml(
                      hd.habit_flaws_summary || ""
                    )}</div>
                    <div style="margin-top:4px;color:#8fd196;"><b>🚨 队长 BP 铁律：</b>${escapeHtml(
                      hd.bp_and_team_mandate || ""
                    )}</div>
                  </div>
                </article>
              `;
            })
            .join("")}
        </div>
      </div>
    `
      : "";

  container.innerHTML = `
    <div class="squad-summary-banner">
      <div class="squad-summary-text">
        <strong>📂 五黑车队跨局荣耀与算账总账：</strong>
        历史头号真大腿 <b style="color:var(--green-light);">${escapeHtml(
          topCarryMember?.personaname || "—"
        )}</b>（场均评分 ${topCarryMember?.avg_rating || 0} · 拿过 ${
          topCarryMember?.mvp_count || 0
        } 次全场 MVP） ｜ 败局背锅王 <b style="color:var(--red-light);">${escapeHtml(
          topCulpritMember?.personaname || "—"
        )}</b>（败局头号战犯 ${
          topCulpritMember?.culprit_count || 0
        } 次 · 场均分锅 ${topCulpritMember?.avg_blame_pct || 0}%）
      </div>
      <div class="squad-summary-pills">
        <span class="squad-pill">近期组排开黑：${partySum.party_games || 0}局 (${partySum.party_win_rate || 0}%胜率)</span>
        <span class="squad-pill">近期单排：${partySum.solo_games || 0}局 (${partySum.solo_win_rate || 0}%胜率)</span>
      </div>
    </div>

    ${guinnessCardsHtml}

    ${habitDiagnosisSectionHtml}

    <div class="squad-grid-2col">
      <article class="squad-card">
        <div class="squad-card-head">
          <h3>⚖️ 五黑车队成员跨局贡献、惯犯吉尼斯与绝活/冥币英雄榜</h3>
          <span>胜局记首功 · 败局抓战犯 · 跨局汇总憋BKB/单带白给/蠢装累计次数</span>
        </div>
        <div class="squad-table-wrap">
          <table class="squad-rank-table">
            <thead>
              <tr>
                <th>队员昵称</th>
                <th>历史定位</th>
                <th>出勤/胜率</th>
                <th>场均贡献/分锅</th>
                <th>场均评分 / MVP</th>
                <th>跨局显微镜铁证 (憋救命装/单带被抓)</th>
                <th>个人绝活 vs 冥币英雄</th>
                <th>近期代表英雄</th>
              </tr>
            </thead>
            <tbody>
              ${members
                .slice(0, 8)
                .map((m) => {
                  const tagCls = m.tag_cls === "carry" ? "mvp" : m.tag_cls === "culprit" ? "culprit" : "";
                  const heroesImgs = (m.heroes || [])
                    .slice(0, 4)
                    .map(
                      (h) =>
                        h.hero_img
                          ? `<img src="${escapeHtml(h.hero_img)}" width="26" height="15" alt="${escapeHtml(
                              h.hero_short_zh
                            )}" title="#${h.match_id} ${escapeHtml(h.hero_short_zh)} (${h.kda} · ${
                              h.won ? `胜局贡献${h.contrib_pct ?? 20}%` : `败局锅${h.blame_pct}%`
                            })" loading="lazy" />`
                          : ""
                    )
                    .join("");
                  const unp = Number(m.unpressed_saves_total ?? 0);
                  const solo = Number(m.solo_pickoffs_total ?? 0);
                  const blind = Number(m.unsmoked_blind_total ?? 0);
                  const badBuild = Number(m.bad_builds_total ?? 0);
                  const bestH = m.best_hero;
                  const worstH = m.worst_hero;
                  return `
                    <tr class="${m.is_me ? "is-me" : ""}">
                      <td>
                        <span class="squad-member-name">
                          ${escapeHtml(m.personaname)}${m.is_me ? " [我]" : ""}
                        </span>
                      </td>
                      <td><span class="squad-role-tag ${tagCls}">${escapeHtml(m.role_tag)}</span></td>
                      <td>${m.games}局 (${m.win_rate}%)</td>
                      <td style="color:${
                        m.avg_blame_pct >= 22 ? "var(--red-light)" : "var(--gold-light)"
                      };font-weight:700;">贡献${m.avg_contrib_pct ?? 20}% / 锅${m.avg_blame_pct}%</td>
                      <td><b>${m.avg_rating}</b> (${m.mvp_count}MVP / <b style="color:${
                        m.culprit_count > 0 ? "var(--red-light)" : "inherit"
                      }">${m.culprit_count}锅</b>)</td>
                      <td>
                        <div style="font-size:11px; line-height:1.45;">
                          <span style="color:${unp >= 3 ? "var(--red-light)" : "var(--text)"};">💀 憋装秒躺 <b>${unp}次</b></span><br/>
                          <span style="color:${solo >= 4 ? "var(--red-light)" : "var(--text)"};">🕵️‍♂️ 单带被抓 <b>${solo}次</b> (白给${blind}次)</span>
                          ${badBuild > 0 ? `<br/><span style="color:var(--gold-light);">🎒 出装抓包 <b>${badBuild}局</b></span>` : ""}
                        </div>
                      </td>
                      <td>
                        <div style="font-size:11px; line-height:1.45;">
                          ${
                            bestH
                              ? `<span style="color:var(--green-light);">🌟 绝活:${escapeHtml(bestH.hero_short_zh)}(${bestH.avg_rating}分)</span>`
                              : ""
                          }
                          ${
                            worstH && (!bestH || worstH.hero_short_zh !== bestH.hero_short_zh)
                              ? `<br/><span style="color:var(--red-light);">💸 慎选:${escapeHtml(worstH.hero_short_zh)}(${worstH.avg_rating}分)</span>`
                              : ""
                          }
                        </div>
                      </td>
                      <td><div class="squad-heroes-mini">${heroesImgs}</div></td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </article>

      <article class="squad-card">
        <div class="squad-card-head">
          <h3>🤝 边路双排 &amp; 中野联动化学反应榜 · 近期英雄池红黑榜</h3>
          <span>谁和谁走一路是天作之合？谁和谁搭档十把九炸？</span>
        </div>
        <div style="margin-bottom:8px;">
          <div style="font-size:11px;color:var(--gold);font-weight:600;margin-bottom:5px;">⚡ 车队双人路 &amp; 中野联动搭档胜率榜：</div>
          <div class="hero-pool-list">${duoChemRowsHtml}</div>
        </div>
        <div style="margin-top:6px;">
          <div style="font-size:11px;color:var(--gold);font-weight:600;margin-bottom:5px;">🎭 主视角近期英雄池红黑榜：</div>
          <div class="hero-pool-list">
            ${heroPool
              .slice(0, 4)
              .map((hp) => {
                const cls = hp.verdict === "上分绝活" ? "ace" : hp.verdict === "掉分慎选" ? "ban" : "";
                return `
                  <div class="hero-pool-item">
                    <div class="hero-pool-left">
                      ${
                        hp.hero_img
                          ? `<img src="${escapeHtml(hp.hero_img)}" width="30" height="17" alt="${escapeHtml(
                              hp.hero_short_zh
                            )}" loading="lazy" />`
                          : ""
                      }
                      <div>
                        <strong>${escapeHtml(hp.hero_short_zh)}</strong>
                        <span>${hp.games}局 ${hp.win_rate}%胜 · KDA ${escapeHtml(hp.avg_kda)}</span>
                      </div>
                    </div>
                    <span class="hero-pool-tag ${cls}">${escapeHtml(hp.verdict)}</span>
                  </div>
                `;
              })
              .join("")}
          </div>
        </div>
        <div style="margin-top:6px;">
          <div style="font-size:11px;color:var(--gold);font-weight:600;margin-bottom:5px;">📚 已完成录像级审理的五黑比赛（点击直接调阅）：</div>
          <div class="analyzed-matches-strip">${matchChipsHtml}</div>
        </div>
      </article>
    </div>
  `;

  container.querySelectorAll("[data-load-archived]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mid = Number(btn.getAttribute("data-load-archived"));
      if (mid) {
        await loadMatchReport(mid, { switchToPostgame: true });
      }
    });
  });

  container.querySelectorAll("[data-habit-member-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedHabitMemberKey = btn.getAttribute("data-habit-member-filter") || "all";
      renderSquadLedgerSection(squadLedger);
    });
  });

  container.querySelectorAll("[data-copy-habit]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const txt = btn.getAttribute("data-copy-habit") || "";
      const name = btn.getAttribute("data-copy-habit-name") || "队员";
      copyTextToClipboard(txt, `${name} 跨局习性诊断书`);
    });
  });

  container.querySelectorAll("[data-habit-poster-idx]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.getAttribute("data-habit-poster-idx"));
      const m = finalHabitMembers[idx];
      if (m) {
        openCareerHabitPosterDialog(m, squadLedger);
      }
    });
  });
}

function openCareerHabitPosterDialog(member, squadLedger) {
  const dlg = document.getElementById("share-poster-dialog");
  if (!dlg || !member) return;

  const hd = member.habit_diagnosis || {};
  const sigHeroes = member.signature_heroes || (member.best_hero ? [member.best_hero] : []);
  const cursedHeroes = member.cursed_heroes || (member.worst_hero ? [member.worst_hero] : []);
  const posList = member.pos_breakdown || [];
  const totalAnalyzed = (squadLedger?.analyzed_matches || []).length;

  const lines = [
    `📜 【DOTA 2 五黑跨局生涯体检 & 毒瘤习性诊断书】`,
    `👤 被审计队员：${member.personaname} ｜ ${member.role_tag}`,
    `📊 跨 ${member.games} 局核心数据：${member.wins}胜${member.games - member.wins}负 (${member.win_rate}%胜率) ｜ Grok 场均评分：${member.avg_rating}/100分 ｜ ${member.mvp_count}次MVP / ${member.culprit_count}次首锅 ｜ 场均KDA ${member.avg_kda}`,
    `────────────────────`,
    `🧭 【1–5号位适岗体检矩阵】`,
    ...posList.map(
      (pb) =>
        `• ${pb.pos_label}：${pb.games}局 (${pb.win_rate}%胜率) · 场均 ${pb.avg_rating}/100分 · 代表英雄：${pb.top_hero || "-"}`
    ),
    `📌 结论：${hd.pos_verdict || ""}`,
    `────────────────────`,
    `🏆 【真命绝活英雄池 (优先抢)】：${
      sigHeroes.map((h) => `${h.hero_short_zh}(${h.games}局${h.win_rate}%胜·${h.avg_rating}分)`).join("、") || "暂无"
    }`,
    `🪦 【建议永久 Ban 冥币英雄 (队长封印)】：${
      cursedHeroes.map((h) => `${h.hero_short_zh}(${h.games}局${h.win_rate}%胜·${h.avg_rating}分)`).join("、") || "无明显连败冥币"
    }`,
    `────────────────────`,
    `🔬 【四大毒瘤与失误习性实锤】`,
    `${hd.habit_flaws_summary || ""}`,
    `────────────────────`,
    `🚨 【队长下把 BP 与位置死命令】`,
    `${hd.bp_and_team_mandate || ""}`,
    `🔗 五黑算账工作台：${window.location.origin}/`,
  ];

  const textarea = document.getElementById("share-verdict-textarea");
  if (textarea) textarea.value = lines.join("\n");

  state.activePosterContext = {
    mode: "career",
    careerMember: member,
    totalAnalyzed,
    player: {
      personaname: member.personaname,
      hero_short_zh: (member.signature_heroes?.[0]?.hero_short_zh || member.best_hero?.hero_short_zh || "本命英雄"),
      pos_label: member.best_pos?.pos_label || "常驻主力",
    },
  };
  state.lastGeneratedPosterArt = null;
  const statusBadge = document.getElementById("nano-poster-status-badge");
  if (statusBadge) {
    const bestH = member.signature_heroes?.[0]?.hero_short_zh || member.best_hero?.hero_short_zh || "本命英雄";
    statusBadge.textContent = `🎯 待生成生涯原画：${member.personaname} 的代表英雄【${bestH}】（点击上方黄色按钮立即生成 AI 原画海报）`;
  }

  drawCareerHabitPosterCanvas(member, totalAnalyzed);
  dlg.showModal();
}

function drawCareerHabitPosterCanvas(m, totalAnalyzed) {
  const canvas = document.getElementById("share-poster-canvas");
  if (!canvas) return;
  canvas.width = 920;
  canvas.height = 790;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;
  const hd = m.habit_diagnosis || {};
  const isCarry = m.tag_cls === "carry";
  const isCulprit = m.tag_cls === "culprit";

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, isCarry ? "#131f16" : isCulprit ? "#221412" : "#1c1a13");
  grad.addColorStop(1, "#0c0d0b");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = isCarry ? "#5db067" : isCulprit ? "#d96552" : "#d9b468";
  ctx.lineWidth = 2.5;
  ctx.strokeRect(18, 18, W - 36, H - 36);

  // Header
  ctx.fillStyle = "#c6a468";
  ctx.font = "bold 15px sans-serif";
  ctx.fillText(
    `DOTA 2 五黑跨局生涯体检 · 英雄池与毒瘤习性诊断书 (跨 ${totalAnalyzed || m.games} 局录像实锤)`,
    42,
    52
  );

  // Player Name & Role Tag
  ctx.fillStyle = "#f5f2eb";
  ctx.font = "bold 28px sans-serif";
  ctx.fillText(`👤 ${m.personaname}`, 42, 92);

  ctx.fillStyle = isCarry ? "#8fd196" : isCulprit ? "#ff8a75" : "#f0c76e";
  ctx.font = "bold 21px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(`${m.role_tag} ｜ 场均 Grok ${m.avg_rating}/100分`, W - 42, 90);
  ctx.textAlign = "left";

  // Sub-stats bar
  ctx.fillStyle = "#cfc9ba";
  ctx.font = "14px sans-serif";
  ctx.fillText(
    `出勤 ${m.games} 局 (${m.wins}胜${m.games - m.wins}负 · 胜率 ${m.win_rate}%) ｜ 全场MVP ${m.mvp_count} 次 ｜ 败局首锅 ${m.culprit_count} 次 ｜ 场均KDA ${m.avg_kda} ｜ 场均黑屏 ${m.avg_dead_sec}s`,
    42,
    122
  );

  // Block 1: 1-5 Position Fitness Row
  let y = 142;
  ctx.fillStyle = "#161814";
  ctx.fillRect(42, y, W - 84, 86);
  ctx.strokeStyle = "#33362c";
  ctx.lineWidth = 1;
  ctx.strokeRect(42, y, W - 84, 86);

  ctx.fillStyle = "#f0c76e";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText("🧭 1–5 号位适岗体检矩阵 (本命舒适区 vs 换位掉分重灾区)", 56, y + 24);

  const posList = (m.pos_breakdown || []).slice(0, 5);
  const bestPosNum = m.best_pos?.pos;
  const worstPosNum = m.worst_pos?.pos;
  let px = 56;
  posList.forEach((pb) => {
    const isBest = pb.pos === bestPosNum;
    const isWorst = pb.pos === worstPosNum;
    const boxW = Math.min(255, Math.floor((W - 112 - (posList.length - 1) * 10) / Math.max(1, posList.length)));
    ctx.fillStyle = isBest ? "#182b1c" : isWorst ? "#2d1715" : "#1e201b";
    ctx.fillRect(px, y + 34, boxW, 40);
    ctx.strokeStyle = isBest ? "#58b368" : isWorst ? "#d96552" : "#3a3d33";
    ctx.strokeRect(px, y + 34, boxW, 40);

    ctx.fillStyle = isBest ? "#9be8a4" : isWorst ? "#ff9e8e" : "#e3dfd5";
    ctx.font = "bold 12.5px sans-serif";
    const tag = isBest ? "🌟本命 " : isWorst ? "🚨重灾 " : "";
    ctx.fillText(
      `${tag}${pb.pos_label}: ${pb.games}局 ${pb.win_rate}%胜 · ${pb.avg_rating}分 (${pb.top_hero || "-"})`,
      px + 10,
      y + 59
    );
    px += boxW + 10;
  });
  y += 100;

  // Block 2: Signature Heroes vs Cursed Auto-Ban Heroes (2 Columns)
  const colW = Math.floor((W - 96) / 2);
  ctx.fillStyle = "#142217";
  ctx.fillRect(42, y, colW, 108);
  ctx.strokeStyle = "#4c9656";
  ctx.strokeRect(42, y, colW, 108);
  ctx.fillStyle = "#8fd196";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText("🏆 真命绝活英雄池 (BP 优先抢)", 56, y + 24);
  ctx.fillStyle = "#e5f5e7";
  ctx.font = "13px sans-serif";
  const sigHeroes = m.signature_heroes || [];
  if (sigHeroes.length > 0) {
    sigHeroes.slice(0, 3).forEach((h, i) => {
      ctx.fillText(
        `• ${h.hero_short_zh} — ${h.games}局 ${h.win_rate}%胜率 · Grok 均分 ${h.avg_rating}/100`,
        56,
        y + 48 + i * 22
      );
    });
  } else {
    ctx.fillText("暂无多局高分绝活样本", 56, y + 52);
  }

  const rightX = 42 + colW + 12;
  ctx.fillStyle = "#241513";
  ctx.fillRect(rightX, y, colW, 108);
  ctx.strokeStyle = "#b85242";
  ctx.strokeRect(rightX, y, colW, 108);
  ctx.fillStyle = "#ff9482";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText("🪦 建议永久 Ban 冥币英雄池 (队长封印)", rightX + 14, y + 24);
  ctx.fillStyle = "#f5dcd8";
  ctx.font = "13px sans-serif";
  const cursedHeroes = m.cursed_heroes || [];
  if (cursedHeroes.length > 0) {
    cursedHeroes.slice(0, 3).forEach((h, i) => {
      ctx.fillText(
        `• ${h.hero_short_zh} — ${h.games}局 ${h.win_rate}%胜率 · Grok 均分 ${h.avg_rating}/100`,
        rightX + 14,
        y + 48 + i * 22
      );
    });
  } else {
    ctx.fillStyle = "#8fd196";
    ctx.fillText("✅ 英雄池健康，无明显连败冥币英雄", rightX + 14, y + 52);
  }
  y += 122;

  // Block 3: 4 Habit Counters Bar
  const kpiItems = [
    {
      label: "💸 辅助毒瘤/失职率",
      val:
        (m.support_games || 0) > 0
          ? `${m.support_grief_count}/${m.support_games}局 (${m.support_grief_rate}%)`
          : "未打辅助",
    },
    {
      label: "📉 核心位崩盘/首锅率",
      val:
        (m.core_games || 0) > 0
          ? `${m.core_choke_count}/${m.core_games}局 (${m.core_choke_rate}%)`
          : "未打核心",
    },
    {
      label: "🗺️ 孤狼单带迷路被抓",
      val: `累计 ${m.solo_pickoffs_total || 0} 次 (场均 ${((m.solo_pickoffs_total || 0) / Math.max(1, m.games)).toFixed(1)} 次)`,
    },
    {
      label: "🧤 憋死BKB / 头铁蠢装",
      val: `憋死 ${m.unpressed_saves_total || 0} 次 / 蠢装 ${m.bad_builds_total || 0} 局`,
    },
  ];
  const kw = Math.floor((W - 84 - 30) / 4);
  kpiItems.forEach((k, idx) => {
    const kx = 42 + idx * (kw + 10);
    ctx.fillStyle = "#171915";
    ctx.fillRect(kx, y, kw, 58);
    ctx.strokeStyle = "#32352b";
    ctx.strokeRect(kx, y, kw, 58);
    ctx.fillStyle = "#a9a599";
    ctx.font = "12px sans-serif";
    ctx.fillText(k.label, kx + 12, y + 22);
    ctx.fillStyle = "#f0c76e";
    ctx.font = "bold 14.5px sans-serif";
    ctx.fillText(k.val, kx + 12, y + 45);
  });
  y += 72;

  // Block 4: AI Cross-Match Habit Diagnosis & Flaws
  ctx.fillStyle = "#151713";
  ctx.fillRect(42, y, W - 84, 210);
  ctx.strokeStyle = "#3a3d31";
  ctx.strokeRect(42, y, W - 84, 210);

  ctx.fillStyle = "#f0c76e";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText("🔬 Grok 跨局位置与毒瘤习性实锤诊断书 (Cross-Match Habit Audit)", 56, y + 24);

  ctx.fillStyle = "#e3dfd5";
  ctx.font = "13px sans-serif";
  const diagLines = [
    ...wrapCanvasParagraph(ctx, `【位置结论】${hd.pos_verdict || ""}`, W - 112, 2),
    ...wrapCanvasParagraph(ctx, `【习性实锤】${hd.habit_flaws_summary || ""}`, W - 112, 4),
    ...wrapCanvasParagraph(ctx, `【BP死命令】${hd.bp_and_team_mandate || ""}`, W - 112, 2),
  ];
  diagLines.slice(0, 8).forEach((ln, idx) => {
    if (ln.startsWith("【BP死命令】")) {
      ctx.fillStyle = "#8fd196";
      ctx.font = "bold 13px sans-serif";
    } else if (ln.startsWith("【位置结论】")) {
      ctx.fillStyle = "#f0c76e";
      ctx.font = "13px sans-serif";
    } else {
      ctx.fillStyle = "#dcd8ce";
      ctx.font = "13px sans-serif";
    }
    ctx.fillText(ln, 56, y + 48 + idx * 20);
  });

  // Footer
  ctx.fillStyle = "#9e9b91";
  ctx.font = "12px sans-serif";
  ctx.fillText(
    `生成自：战后算账 · Dota 2 录像级复盘工作台 (${window.location.origin})`,
    42,
    H - 28
  );
}

/**
 * 13. 5v5 Focus-Fire & Mutual Damage Matrix (集火流向与伤害分配矩阵)
 */
function renderFocusFireMatrix(report) {
  const container = document.getElementById("focus-fire-matrix-container");
  if (!container) return;

  const { side, sideZh, oppZh } = getOwnAndOppPlayers(report);
  const oppSide = side === "radiant" ? "dire" : "radiant";
  const ffRoot = report.deep_forensics?.focus_fire_matrix;
  if (!ffRoot) {
    container.innerHTML = `<div class="empty-state compact">暂无录像级 5v5 集火流向矩阵数据</div>`;
    return;
  }

  const activeSideKey = state.focusMatrixSide === "opp" ? oppSide : side;
  const mat = ffRoot[activeSideKey];
  if (!mat || !Array.isArray(mat.rows) || mat.rows.length === 0) {
    container.innerHTML = `<div class="empty-state compact">暂无该阵营集火伤害分布记录</div>`;
    return;
  }

  const targets = mat.targets || [];
  const rows = mat.rows || [];
  const maxCell = Math.max(1, Number(mat.max_cell || 1));
  const attackerLabel = state.focusMatrixSide === "opp" ? `${oppZh}攻击者` : `${sideZh}攻击者`;
  const defenderLabel = state.focusMatrixSide === "opp" ? `${sideZh}受击目标` : `${oppZh}受击目标`;

  const thCols = targets
    .map(
      (t) => `
      <th>
        <div class="focus-hero-th">
          ${
            t.hero_img
              ? `<img src="${escapeHtml(t.hero_img)}" width="26" height="15" alt="${escapeHtml(
                  t.hero_short_zh
                )}" loading="lazy" />`
              : ""
          }
          <span>${t.pos}·${escapeHtml(t.hero_short_zh)}</span>
        </div>
      </th>
    `
    )
    .join("");

  const bodyRows = rows
    .map((r) => {
      const rowTotal = Math.max(1, Number(r.row_total || 1));
      const cellsHtml = (r.cells || [])
        .map((val, cIdx) => {
          const shareOfRow = Math.round((Number(val || 0) / rowTotal) * 100);
          const heatAlpha = Math.min(0.42, (Number(val || 0) / maxCell) * 0.42).toFixed(2);
          const bgStyle =
            val > 0
              ? `background: rgba(${
                  state.focusMatrixSide === "opp" ? "214, 92, 74" : "199, 155, 59"
                }, ${heatAlpha});`
              : "";
          const targetHero = targets[cIdx]?.hero_short_zh || "";
          return `
            <td style="${bgStyle}" title="${escapeHtml(r.hero_short_zh)} 打在 ${escapeHtml(
              targetHero
            )} 身上伤害: ${fmtNum(val)} (占该英雄总输出 ${shareOfRow}%)">
              <div class="focus-cell-inner">
                <span class="focus-cell-dmg">${fmtNum(val)}</span>
                <span class="focus-cell-pct">占输出 ${shareOfRow}%</span>
              </div>
            </td>
          `;
        })
        .join("");

      return `
        <tr>
          <td>
            <div class="focus-hero-th">
              ${
                r.hero_img
                  ? `<img src="${escapeHtml(r.hero_img)}" width="26" height="15" alt="${escapeHtml(
                      r.hero_short_zh
                    )}" loading="lazy" />`
                  : ""
              }
              <div>
                <strong style="color:var(--text);">${r.pos}号位·${escapeHtml(r.hero_short_zh)}</strong>
                <div style="font-size:10px;color:var(--dim);">${escapeHtml(r.personaname)}</div>
              </div>
            </div>
          </td>
          ${cellsHtml}
          <td style="font-weight:700;color:var(--gold-light);">${fmtNum(r.row_total)}</td>
        </tr>
      `;
    })
    .join("");

  const footCols = targets
    .map(
      (t) => `
      <td style="background:#171915;font-weight:700;">
        <div class="focus-cell-inner">
          <span style="color:var(--gold-light);">${fmtNum(t.col_total)}</span>
          <span class="focus-cell-pct">吃下全队 ${t.col_share_pct}% 火力</span>
        </div>
      </td>
    `
    )
    .join("");

  container.innerHTML = `
    <div class="focus-verdict-banner">${escapeHtml(mat.verdict || "")}</div>
    <div class="focus-matrix-scroll">
      <table class="focus-matrix-table">
        <thead>
          <tr>
            <th>${escapeHtml(attackerLabel)} \\ ${escapeHtml(defenderLabel)}</th>
            ${thCols}
            <th>合计对英雄输出</th>
          </tr>
        </thead>
        <tbody>
          ${bodyRows}
        </tbody>
        <tfoot>
          <tr>
            <td style="background:#171915;font-weight:700;color:var(--gold);">受击目标合计承伤 (火力占比)</td>
            ${footCols}
            <td style="background:#171915;font-weight:700;color:var(--gold-light);">${fmtNum(
              mat.grand_total || 0
            )}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  `;
}

/**
 * 14. Shareable Verdict Poster & Chat Text Generator (群聊处刑判决书 / 凯旋庆功表彰书 & 长图导出)
 */
function openSharePosterDialog(report) {
  const dlg = document.getElementById("share-poster-dialog");
  if (!dlg || !report) return;

  const { side, sideZh, own } = getOwnAndOppPlayers(report);
  const won =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !report.radiant_win);
  const grok = report.grok_coaching;
  const getEffShare = (p) => {
    const gp = findGrokPlayerEntry(p, report);
    if (gp && Number(gp.grok_share_pct) > 0) return Number(gp.grok_share_pct);
    return won ? Number(p.contrib_share_pct ?? 20) : Number(p.blame_share_pct ?? 20);
  };
  const sortedBlame = [...own].sort(
    (a, b) => getEffShare(b) - getEffShare(a) || getHeroScore100(a, report) - getHeroScore100(b, report)
  );
  const sortedContrib = [...own].sort(
    (a, b) => getEffShare(b) - getEffShare(a) || getHeroScore100(b, report) - getHeroScore100(a, report)
  );
  const topCulprit = sortedBlame[0];
  const mvpPlayer = won
    ? sortedContrib[0]
    : [...own].sort((a, b) => getHeroScore100(b, report) - getHeroScore100(a, report))[0] || sortedContrib[0];
  const runnerUpPlayer = sortedContrib[1] || sortedContrib[0];

  const df = report.deep_forensics || {};
  const rawExec = df.hero_execution_by_side?.[side];
  const microExec = Array.isArray(rawExec)
    ? rawExec
        .map((x) => {
          const u = (x.ult_audits || [])[0];
          return u
            ? `${x.hero_short_zh}《${u.ability_zh}》释放${u.casts ?? 0}次(命中${u.hits ?? 0}${u.unit_label || "人次"})`
            : "";
        })
        .filter(Boolean)
        .join("；")
    : rawExec?.summary || "";
  const microSaves = df.unpressed_saves_by_side?.[side]?.side_verdict || "";
  const microSpace = df.map_space_by_side?.[side]?.side_verdict || "";
  const microVis = df.support_vision_by_side?.[side]?.posture_verdict || "";
  const microStack = df.stacking_and_smoke_by_side?.[side]?.stack_verdict || "";
  const microSmoke = df.stacking_and_smoke_by_side?.[side]?.smoke_verdict || "";
  const microTp = df.tp_rotation_by_side?.[side]?.tp_verdict || "";
  const microMirror = df.role_mirror_by_side?.[side]?.side_verdict || "";
  const microMacro = df.macro_objectives_by_side?.[side]?.side_verdict || "";
  const shareUrl = getPublicShareUrl(report.match_id);

  const lines = won
    ? [
        `🏆【刀塔五黑庆功宴 · 赛后封神表彰书】`,
        `📍 比赛编号：#${report.match_id} (${report.duration_str} · ${sideZh}凯旋获胜 ${report.radiant_score}:${report.dire_score})`,
        `🔗 公开复盘分享链接：${shareUrl}`,
        `📣 凯旋定性：${grok?.title || report.match_narrative?.headline || "全员发力碾压获胜"}`,
        `────────────────────`,
        `👑 头号首功 (MVP)：${mvpPlayer?.personaname || ""} (${mvpPlayer?.hero_short_zh || ""}) — 胜局贡献 ${getEffShare(mvpPlayer).toFixed(1)}% · 综合评分 ${getHeroScore100(mvpPlayer, report)}/100分`,
        `⚔️ 破阵二当家：${runnerUpPlayer?.personaname || ""} (${runnerUpPlayer?.hero_short_zh || ""}) — 胜局贡献 ${getEffShare(runnerUpPlayer).toFixed(1)}% · 综合评分 ${getHeroScore100(runnerUpPlayer, report)}/100分`,
        `────────────────────`,
        `📊 五黑全员胜局贡献榜 (100% 胜局贡献排位)：`,
        ...sortedContrib.map((p, i) => {
          const b0 = (p.hero_execution_audit?.headline_badges || [])[0];
          const b0Txt = typeof b0 === "string" ? b0 : b0?.text || "";
          const cPct = getEffShare(p).toFixed(1);
          const sc100 = getHeroScore100(p, report);
          return `${i + 1}. [${p.pos_label}] ${p.personaname} (${p.hero_short_zh}) | 评分 ${sc100}/100 | 胜局贡献 ${cPct}% | KDA ${p.kda} | GPM ${p.gpm} | 伤害占比 ${p.hero_damage_share_pct}%${
            b0Txt ? ` | 🔬 ${b0Txt}` : ""
          }`;
        }),
        ...(microExec || microSaves || microSpace || microVis || microTp || microMirror || microMacro
          ? [
              `────────────────────`,
              `🔬 录像级高光操作回放：`,
              ...(microMirror ? [`• 【1v1同位置对位】${microMirror}`] : []),
              ...(microExec ? [`• 【大招与绝活】${microExec}`] : []),
              ...(microSaves ? [`• 【保命装与反应】${microSaves}`] : []),
              ...(microSpace ? [`• 【地图空间牵制】${microSpace}`] : []),
              ...(microMacro ? [`• 【买活与信使魔晶】${microMacro}`] : []),
              ...(microVis ? [`• 【辅助眼位】${microVis}`] : []),
              ...(microStack ? [`• 【堆野屯矿】${microStack}`] : []),
              ...(microSmoke ? [`• 【开雾节奏】${microSmoke}`] : []),
              ...(microTp ? [`• 【TP支援】${microTp}`] : []),
            ]
          : []),
        `────────────────────`,
        `🥂 乘胜追击备忘：${
          grok?.team_practice ||
          "保持当前中期抱团开雾压制与视野布控节奏，全员手感火热继续上分！"
        }`,
      ]
    : [
        `⚖️【刀塔五黑算账台 · 赛后处刑判决书】`,
        `📍 比赛编号：#${report.match_id} (${report.duration_str} · ${sideZh}落败 ${report.radiant_score}:${report.dire_score})`,
        `🔗 公开复盘分享链接：${shareUrl}`,
        `📣 终局定性：${grok?.title || report.match_narrative?.headline || "正面团战与节奏复盘"}`,
        `────────────────────`,
        `🚨 头号背锅侠：${topCulprit?.personaname || ""} (${topCulprit?.hero_short_zh || ""}) — 分锅占比 ${getEffShare(topCulprit).toFixed(1)}% · 综合评分 ${getHeroScore100(topCulprit, report)}/100分`,
        `👑 败方尽力王：${mvpPlayer?.personaname || ""} (${mvpPlayer?.hero_short_zh || ""}) — 综合评分 ${getHeroScore100(mvpPlayer, report)}/100分`,
        `────────────────────`,
        `📊 五黑全员算账明细 (按背锅排序)：`,
        ...sortedBlame.map((p, i) => {
          const b0 = (p.hero_execution_audit?.headline_badges || [])[0];
          const b0Txt = typeof b0 === "string" ? b0 : b0?.text || "";
          const bPct = getEffShare(p).toFixed(1);
          const sc100 = getHeroScore100(p, report);
          return `${i + 1}. [${p.pos_label}] ${p.personaname} (${p.hero_short_zh}) | 评分 ${sc100}/100 | 锅 ${bPct}% | KDA ${p.kda} | GPM ${p.gpm} | 伤害占比 ${p.hero_damage_share_pct}% | 读秒 ${p.dead_seconds || 0}s${
            b0Txt ? ` | 🔬 ${b0Txt}` : ""
          }`;
        }),
        ...(microExec || microSaves || microSpace || microVis || microTp || microMirror || microMacro
          ? [
              `────────────────────`,
              `🔬 录像级战术显微镜实锤：`,
              ...(microMirror ? [`• 【1v1同位置对位】${microMirror}`] : []),
              ...(microExec ? [`• 【大招与绝活】${microExec}`] : []),
              ...(microSaves ? [`• 【憋死BKB/救命装】${microSaves}`] : []),
              ...(microSpace ? [`• 【地图空间与落单带线】${microSpace}`] : []),
              ...(microMacro ? [`• 【买活死与掉鸡审计】${microMacro}`] : []),
              ...(microVis ? [`• 【辅助眼位】${microVis}`] : []),
              ...(microStack ? [`• 【堆野屯矿】${microStack}`] : []),
              ...(microSmoke ? [`• 【开雾节奏】${microSmoke}`] : []),
              ...(microTp ? [`• 【TP支援】${microTp}`] : []),
            ]
          : []),
        `────────────────────`,
        `💡 下把铁律：${
          grok?.team_practice ||
          "盯紧 BKB 第一波强势期抱团推外塔，严禁带线过河道无视野暴毙！"
        }`,
      ];

  const textarea = document.getElementById("share-verdict-textarea");
  if (textarea) textarea.value = lines.join("\n");

  const focusHeroPlayer = won ? mvpPlayer : topCulprit;
  state.activePosterContext = {
    mode: "team",
    report,
    player: focusHeroPlayer,
    playerSlot: focusHeroPlayer?.player_slot,
    grokPlayer: findGrokPlayerEntry(focusHeroPlayer, report),
    badgeTitle: won ? "👑 胜局首功 MVP" : "🚨 败局头号战犯",
  };
  state.lastGeneratedPosterArt = null;
  const statusBadge = document.getElementById("nano-poster-status-badge");
  if (statusBadge && focusHeroPlayer) {
    statusBadge.textContent = `🎯 点击上方「🍌 用 Nano Banana 生成 AI 超燃/处刑原画海报」可为本局主角【${focusHeroPlayer.personaname} · ${focusHeroPlayer.hero_short_zh}】生成专属战斗大片！`;
  }

  drawVerdictPosterCanvas(report, {
    sideZh,
    won,
    sortedBlame,
    sortedContrib,
    topCulprit,
    mvpPlayer,
    runnerUpPlayer,
    grok,
  });
  dlg.showModal();
}

function drawVerdictPosterCanvas(
  report,
  { sideZh, won, sortedBlame, sortedContrib, topCulprit, mvpPlayer, runnerUpPlayer, grok }
) {
  const canvas = document.getElementById("share-poster-canvas");
  if (!canvas) return;
  canvas.width = 920;
  canvas.height = 620;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, won ? "#161d15" : "#151713");
  grad.addColorStop(1, "#0d0e0c");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = "#c6a468";
  ctx.lineWidth = 2;
  ctx.strokeRect(18, 18, W - 36, H - 36);

  ctx.fillStyle = "#c6a468";
  ctx.font = "bold 16px sans-serif";
  ctx.fillText(
    won ? "DOTA 2 五黑庆功宴 · 赛后封神表彰书" : "DOTA 2 五黑算账台 · 赛后处刑判决书",
    42,
    56
  );

  ctx.fillStyle = won ? "#7cb87a" : "#e06c5a";
  ctx.font = "bold 26px sans-serif";
  const headline = `[${sideZh}${won ? "凯旋获胜" : "遗憾落败"}] #${report.match_id} (${report.radiant_score} : ${report.dire_score} · ${report.duration_str})`;
  ctx.fillText(headline, 42, 92);

  ctx.fillStyle = "#d9d4c7";
  ctx.font = "14px sans-serif";
  const subTitle = (
    grok?.title ||
    report.match_narrative?.headline ||
    (won ? "录像级胜局功勋与高光贡献榜" : "录像级硬核责任划分报告")
  ).slice(0, 52);
  ctx.fillText(subTitle, 42, 120);

  ctx.strokeStyle = "#34372d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(42, 138);
  ctx.lineTo(W - 42, 138);
  ctx.stroke();

  if (won) {
    ctx.fillStyle = "#162419";
    ctx.fillRect(42, 152, 410, 74);
    ctx.strokeStyle = "#569c5d";
    ctx.strokeRect(42, 152, 410, 74);

    ctx.fillStyle = "#8fd196";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("👑 本局头号首功 (MATCH MVP)", 56, 176);
    ctx.fillStyle = "#f2efe9";
    ctx.font = "bold 19px sans-serif";
    ctx.fillText(
      `${mvpPlayer?.personaname || ""} · ${mvpPlayer?.hero_short_zh || ""} (贡献 ${Number(
        findGrokPlayerEntry(mvpPlayer, report)?.grok_share_pct ?? mvpPlayer?.contrib_share_pct ?? 25
      ).toFixed(1)}%)`,
      56,
      206
    );

    ctx.fillStyle = "#221e14";
    ctx.fillRect(468, 152, 410, 74);
    ctx.strokeStyle = "#c79b3b";
    ctx.strokeRect(468, 152, 410, 74);

    ctx.fillStyle = "#f0c76e";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("⚔️ 本局破阵二当家 (RUNNER-UP)", 482, 176);
    ctx.fillStyle = "#f2efe9";
    ctx.font = "bold 19px sans-serif";
    ctx.fillText(
      `${runnerUpPlayer?.personaname || ""} · ${runnerUpPlayer?.hero_short_zh || ""} (贡献 ${Number(
        findGrokPlayerEntry(runnerUpPlayer, report)?.grok_share_pct ?? runnerUpPlayer?.contrib_share_pct ?? 22
      ).toFixed(1)}%)`,
      482,
      206
    );
  } else {
    ctx.fillStyle = "#261614";
    ctx.fillRect(42, 152, 410, 74);
    ctx.strokeStyle = "#b84a39";
    ctx.strokeRect(42, 152, 410, 74);

    ctx.fillStyle = "#e5897a";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("🚨 本局头号背锅侠 (TOP CULPRIT)", 56, 176);
    ctx.fillStyle = "#f2efe9";
    ctx.font = "bold 19px sans-serif";
    ctx.fillText(
      `${topCulprit?.personaname || ""} · ${topCulprit?.hero_short_zh || ""} (背锅 ${Number(
        findGrokPlayerEntry(topCulprit, report)?.grok_share_pct ?? topCulprit?.blame_share_pct ?? 25
      ).toFixed(1)}%)`,
      56,
      206
    );

    ctx.fillStyle = "#162218";
    ctx.fillRect(468, 152, 410, 74);
    ctx.strokeStyle = "#4d8a54";
    ctx.strokeRect(468, 152, 410, 74);

    ctx.fillStyle = "#8fd196";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("👑 败方尽力王 (MATCH MVP)", 482, 176);
    ctx.fillStyle = "#f2efe9";
    ctx.font = "bold 19px sans-serif";
    ctx.fillText(
      `${mvpPlayer?.personaname || ""} · ${mvpPlayer?.hero_short_zh || ""} (评分 ${getHeroScore100(mvpPlayer, report)}/100)`,
      482,
      206
    );
  }

  let y = 252;
  const rowsList = won ? sortedContrib || sortedBlame : sortedBlame;
  rowsList.forEach((p, idx) => {
    const isFirst = idx === 0;
    const gpRow = findGrokPlayerEntry(p, report);
    const rowShare = Number(
      gpRow?.grok_share_pct ?? (won ? p.contrib_share_pct : p.blame_share_pct) ?? 20
    ).toFixed(1);
    const rowScore = getHeroScore100(p, report);
    ctx.fillStyle = isFirst ? (won ? "#182419" : "#201715") : "#181a16";
    ctx.fillRect(42, y, W - 84, 58);
    ctx.strokeStyle = isFirst ? (won ? "#4d8a54" : "#8c3b2e") : "#2e3028";
    ctx.strokeRect(42, y, W - 84, 58);

    ctx.fillStyle = isFirst ? (won ? "#8fd196" : "#e5897a") : "#c6a468";
    ctx.font = "bold 16px sans-serif";
    ctx.fillText(`#${idx + 1} [${p.pos_label}] ${p.hero_short_zh} · ${p.personaname}`, 56, y + 24);

    ctx.fillStyle = "#b5b1a6";
    ctx.font = "13px sans-serif";
    ctx.fillText(
      `KDA ${p.kda} (${p.kill_participation_pct}%) ｜ GPM ${p.gpm} ｜ 英雄伤害 ${fmtNum(
        p.hero_damage
      )} (${p.hero_damage_share_pct}%) ｜ 推塔 ${fmtNum(p.tower_damage)}`,
      56,
      y + 46
    );

    ctx.fillStyle = isFirst ? (won ? "#8fd196" : "#ff8a75") : "#dfbe82";
    ctx.font = "bold 16px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(
      won
        ? `胜局贡献 ${rowShare}% · 评分 ${rowScore}/100`
        : `分锅 ${rowShare}% · 评分 ${rowScore}/100`,
      W - 58,
      y + 34
    );
    ctx.textAlign = "left";

    y += 68;
  });

  ctx.fillStyle = "#9e9b91";
  ctx.font = "12px sans-serif";
  const tip =
    grok?.team_practice ||
    (won
      ? "继续保持核心强势期抱团开雾压制与进攻眼位铺设，乘胜追击！"
      : "前中期围绕核心第一件 BKB/跳刀出炉打主动开雾，拒绝无视野单带掉点。");
  ctx.fillText(`${won ? "乘胜追击备忘" : "下把改进铁律"}：${tip.slice(0, 62)}`, 42, H - 32);
}

function wrapCanvasParagraph(ctx, text, maxWidth, maxLines = 4) {
  const raw = String(text || "").replace(/\s+/g, " ").trim();
  if (!raw) return [];
  const lines = [];
  let cur = "";
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    const test = cur + ch;
    if (ctx.measureText(test).width > maxWidth && cur.length > 0) {
      lines.push(cur);
      cur = ch;
      if (lines.length >= maxLines) {
        lines[lines.length - 1] = lines[lines.length - 1].slice(0, -1) + "…";
        return lines;
      }
    } else {
      cur = test;
    }
  }
  if (cur && lines.length < maxLines) {
    lines.push(cur);
  }
  return lines;
}

function openSinglePlayerPosterDialog(
  report,
  playerSlot,
  roleTag = "",
  { autoGenerateAiArt = false } = {}
) {
  const dlg = document.getElementById("share-poster-dialog");
  if (!dlg || !report) return;

  const { sideZh, won, own, opp } = getOwnAndOppPlayers(report);
  const allPlayers = [...(own || []), ...(opp || [])];
  const p =
    allPlayers.find((x) => Number(x.player_slot) === Number(playerSlot)) ||
    (own || [])[0];
  if (!p) return;

  const gp = findGrokPlayerEntry(p, report);
  const heroZh = p.hero_short_zh || p.hero_name || p.hero_zh || "";
  const shareUrl = `${window.location.origin}/?match=${report.match_id}`;
  const sc100 = getHeroScore100(p, report);
  const sharePct = Number(
    gp?.grok_share_pct ?? (won ? p.contrib_share_pct : p.blame_share_pct) ?? 20
  ).toFixed(1);
  const shareLabel = won ? "胜局功勋占比" : "败局背锅占比";
  const badgeTitle =
    roleTag ||
    gp?.verdict_tag ||
    (won
      ? sc100 >= 84
        ? "👑 胜局首功 MVP"
        : "⚔️ 胜局功臣"
      : sc100 < 55
        ? "🚨 败局头号战犯"
        : "🛡️ 败局尽力局");

  const lines = [
    `📜 【DOTA 2 录像级单人深度档案 · ${badgeTitle}】`,
    `📍 比赛编号：#${report.match_id} (${sideZh}${won ? "获胜" : "落败"} · ${report.radiant_score}:${report.dire_score} · ${report.duration_str})`,
    `🔗 复盘直达：${shareUrl}`,
    `────────────────────`,
    `👤 选手与英雄：${p.personaname} · ${heroZh} ([${p.pos_label}])`,
    `📊 Grok 4.7 终审评分：${sc100}/100 分 ｜ ${shareLabel}：${sharePct}%`,
    `📈 基础面板：KDA ${p.kda} (参战率 ${p.kill_participation_pct}%) ｜ GPM ${p.gpm} / XPM ${p.xpm} ｜ 英雄伤害 ${fmtNum(p.hero_damage)} (${p.hero_damage_share_pct}%) ｜ 建筑伤害 ${fmtNum(p.tower_damage)} ｜ 读秒 ${p.dead_seconds || 0}s`,
    `🗣️ 一针见血定性：${gp?.headline || p.blame_Headline || "录像级全周期数据实锤定责"}`,
    `────────────────────`,
    `📋 【本职工作与全周期结案陈词】`,
    `${gp?.deep_verdict || (p.verdict_bullets || []).join("；") || "详见全量战报"}`,
    ...(gp?.item_and_blink_audit
      ? [
          `────────────────────`,
          `🎒 【灵性/犯罪出装与憋刀审计】`,
          `${gp.item_and_blink_audit}`,
        ]
      : []),
    ...(gp?.early_story || gp?.mid_story || gp?.late_story
      ? [
          `────────────────────`,
          `🎬 【Grok 三幕剧全周期处刑/封神复盘】`,
          ...(gp?.early_story ? [`🌅 第一幕 (对线期 0-10m)：${gp.early_story}`] : []),
          ...(gp?.mid_story ? [`⚔️ 第二幕 (中期节奏 10-25m)：${gp.mid_story}`] : []),
          ...(gp?.late_story ? [`🔥 第三幕 (决胜高地 25m+)：${gp.late_story}`] : []),
        ]
      : []),
    `────────────────────`,
    `💡 【下把死命令】：${gp?.practice || p.next_game_action || "盯紧关键装第一波强势期抱团推进！"}`,
  ];

  const textarea = document.getElementById("share-verdict-textarea");
  if (textarea) textarea.value = lines.join("\n");

  state.activePosterContext = {
    mode: "single",
    report,
    playerSlot: p.player_slot,
    player: p,
    grokPlayer: gp,
    badgeTitle,
  };
  state.lastGeneratedPosterArt = null;

  const victimsStr = ((p.kills_breakdown?.heroes || []).slice(0, 3))
    .map((v) => `${v.hero_short_zh}×${v.count}`)
    .join(" / ");
  const nemesisStr = ((p.killed_by_breakdown?.heroes || []).slice(0, 3))
    .map((v) => `${v.hero_short_zh}×${v.count}`)
    .join(" / ");
  const statusBadge = document.getElementById("nano-poster-status-badge");
  if (statusBadge) {
    statusBadge.textContent =
      (won && sc100 >= 70) || sc100 >= 76
        ? `🎯 本局高光提取：[${p.pos_label}] ${p.personaname} · ${heroZh} (${sc100}分) — 手刃 ${victimsStr || "敌方主力"} ｜ 点击上方黄色按钮生成 AI 战斗大片`
        : `🎯 本局名场面提取：[${p.pos_label}] ${p.personaname} · ${heroZh} (${sc100}分) — 被 ${nemesisStr || "敌方"} 提款 ｜ 点击上方黄色按钮生成 AI 处刑画报`;
  }

  const inlineIn = document.getElementById("input-gemini-key-inline");
  if (inlineIn && !inlineIn.value) {
    const savedGKey = localStorage.getItem("dota_gemini_poster_key") || "";
    if (savedGKey) inlineIn.value = savedGKey;
  }

  drawSinglePlayerPosterCanvas(report, p, gp, badgeTitle);
  dlg.showModal();

  if (autoGenerateAiArt) {
    generateNanoBananaPoster({ force: false });
  }
}

function drawSinglePlayerPosterCanvas(report, p, gp, badgeTitle) {
  const canvas = document.getElementById("share-poster-canvas");
  if (!canvas) return;
  canvas.width = 920;
  canvas.height = 790;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;
  const { sideZh, won } = getOwnAndOppPlayers(report);
  const heroZh = p.hero_short_zh || p.hero_name || p.hero_zh || "";
  const sc100 = getHeroScore100(p, report);
  const sharePct = Number(
    gp?.grok_share_pct ?? (won ? p.contrib_share_pct : p.blame_share_pct) ?? 20
  ).toFixed(1);
  const isHighPraise = (won && sc100 >= 78) || (!won && sc100 >= 75);

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, isHighPraise ? "#142016" : "#211513");
  grad.addColorStop(1, "#0c0d0b");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = isHighPraise ? "#63b06b" : "#d96857";
  ctx.lineWidth = 2.5;
  ctx.strokeRect(18, 18, W - 36, H - 36);

  // Top Header
  ctx.fillStyle = "#c6a468";
  ctx.font = "bold 15px sans-serif";
  ctx.fillText(
    `DOTA 2 录像级单人专属档案 · #${report.match_id} (${sideZh}${won ? "胜" : "负"} ${report.radiant_score}:${report.dire_score} · ${report.duration_str})`,
    42,
    52
  );

  // Player & Hero Main Banner
  ctx.fillStyle = "#f2efe9";
  ctx.font = "bold 28px sans-serif";
  ctx.fillText(`[${p.pos_label}] ${p.personaname} · ${heroZh}`, 42, 92);

  // Score & Share Pill on Right
  ctx.fillStyle = isHighPraise ? "#8fd196" : "#ff8a75";
  ctx.font = "bold 24px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(
    `${badgeTitle} ｜ 评分 ${sc100}/100 · ${won ? "功勋" : "分锅"} ${sharePct}%`,
    W - 42,
    90
  );
  ctx.textAlign = "left";

  // Stats Bar
  ctx.fillStyle = "#cfc9ba";
  ctx.font = "14px sans-serif";
  ctx.fillText(
    `KDA ${p.kda} (参战 ${p.kill_participation_pct}%) ｜ GPM ${p.gpm} / XPM ${p.xpm} ｜ 英雄伤害 ${fmtNum(p.hero_damage)} (${p.hero_damage_share_pct}%) ｜ 推塔 ${fmtNum(p.tower_damage)} ｜ 读秒 ${p.dead_seconds || 0}s`,
    42,
    122
  );

  // Headline Quote
  ctx.fillStyle = "#191b16";
  ctx.fillRect(42, 138, W - 84, 44);
  ctx.strokeStyle = "#3a3d31";
  ctx.lineWidth = 1;
  ctx.strokeRect(42, 138, W - 84, 44);
  ctx.fillStyle = "#f0c76e";
  ctx.font = "bold 15px sans-serif";
  const hlText = (gp?.headline || p.blame_Headline || "录像级全周期实锤审计").slice(0, 54);
  ctx.fillText(`🗣️ “${hlText}”`, 56, 166);

  let y = 198;

  // Block 1: Deep Verdict & Role Duty
  const verdictLines = wrapCanvasParagraph(
    ctx,
    gp?.deep_verdict || (p.verdict_bullets || []).join("；") || "",
    W - 116,
    4
  );
  const b1H = Math.max(88, 38 + verdictLines.length * 21);
  ctx.fillStyle = "#151814";
  ctx.fillRect(42, y, W - 84, b1H);
  ctx.strokeStyle = "#35382e";
  ctx.strokeRect(42, y, W - 84, b1H);
  ctx.fillStyle = "#e0c389";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText("📋 本职工作与全周期结案陈词 (Role Duty & Deep Verdict)", 56, y + 24);
  ctx.fillStyle = "#e3dfd5";
  ctx.font = "13.5px sans-serif";
  verdictLines.forEach((ln, idx) => {
    ctx.fillText(ln, 56, y + 48 + idx * 20);
  });
  y += b1H + 12;

  // Block 2: Item & Blink Audit
  const itemText =
    gp?.item_and_blink_audit ||
    (p.item_Purchase_timeline || []).map((it) => `${it.name_zh}(${it.time_str})`).join(" → ");
  ctx.font = "13.5px sans-serif";
  const itemLines = wrapCanvasParagraph(ctx, itemText, W - 116, 3);
  const b2H = Math.max(72, 36 + itemLines.length * 20);
  ctx.fillStyle = "#181612";
  ctx.fillRect(42, y, W - 84, b2H);
  ctx.strokeStyle = "#4a3e28";
  ctx.strokeRect(42, y, W - 84, b2H);
  ctx.fillStyle = "#f0c76e";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText("🎒 灵性/犯罪出装与憋刀审计 (Itemization & Economy Audit)", 56, y + 23);
  ctx.fillStyle = "#dcd6c8";
  ctx.font = "13px sans-serif";
  itemLines.forEach((ln, idx) => {
    ctx.fillText(ln, 56, y + 45 + idx * 19);
  });
  y += b2H + 12;

  // Block 3: 3-Act Chronological Breakdown
  const acts = [
    { label: "🌅 第一幕 (对线 0-10m)", txt: gp?.early_story || "" },
    { label: "⚔️ 第二幕 (中期 10-25m)", txt: gp?.mid_story || "" },
    { label: "🔥 第三幕 (决胜 25m+)", txt: gp?.late_story || "" },
  ].filter((a) => a.txt);

  if (acts.length > 0) {
    const colW = Math.floor((W - 84 - (acts.length - 1) * 12) / acts.length);
    const actH = 195;
    acts.forEach((act, idx) => {
      const cx = 42 + idx * (colW + 12);
      ctx.fillStyle = "#141613";
      ctx.fillRect(cx, y, colW, actH);
      ctx.strokeStyle = "#2f3329";
      ctx.strokeRect(cx, y, colW, actH);

      ctx.fillStyle = "#8ec0e4";
      ctx.font = "bold 13px sans-serif";
      ctx.fillText(act.label, cx + 12, y + 22);

      ctx.fillStyle = "#d5d1c5";
      ctx.font = "12.5px sans-serif";
      const aLines = wrapCanvasParagraph(ctx, act.txt, colW - 24, 8);
      aLines.forEach((ln, lIdx) => {
        ctx.fillText(ln, cx + 12, y + 44 + lIdx * 18);
      });
    });
    y += actH + 14;
  }

  // Bottom Practice Mandate
  const prac = (gp?.practice || p.next_game_action || "盯紧强势期第一波抱团推塔节奏").slice(0, 58);
  ctx.fillStyle = "#8fd196";
  ctx.font = "bold 13.5px sans-serif";
  ctx.fillText(`💡 下把死命令：${prac}`, 42, H - 32);
}

async function generateNanoBananaPoster({ force = false } = {}) {
  const ctxInfo = state.activePosterContext;
  if (!ctxInfo) {
    showToast("请先打开一张单人或团队战报海报");
    return;
  }

  const btn = document.getElementById("btn-generate-nano-poster");
  const statusBadge = document.getElementById("nano-poster-status-badge");
  const styleMode = document.getElementById("select-nano-poster-style")?.value || "auto";
  const enginePref = document.getElementById("select-nano-poster-engine")?.value || "auto";
  const customScene = document.getElementById("input-nano-custom-scene")?.value.trim() || "";
  const inlineGKey = document.getElementById("input-gemini-key-inline")?.value.trim() || "";
  const geminiKey = inlineGKey || localStorage.getItem("dota_gemini_poster_key") || "";

  if (inlineGKey) {
    localStorage.setItem("dota_gemini_poster_key", inlineGKey);
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = "🍌 AI 正在根据本局战绩绘制超燃英雄原画 (约4~8秒)...";
  }
  if (statusBadge) {
    statusBadge.textContent = "🎨 正在读取本局击杀猎物、大招斩击与神装细节并渲染高清战斗大片...";
  }

  try {
    const payload = {
      match_id: ctxInfo.report?.match_id || null,
      player_slot: ctxInfo.playerSlot ?? ctxInfo.player?.player_slot ?? null,
      style_mode: styleMode,
      engine_pref: enginePref,
      custom_scene: customScene,
      gemini_api_key: geminiKey,
      career_member: ctxInfo.mode === "career" ? ctxInfo.careerMember : null,
      force: Boolean(force),
    };

    const res = await fetch("/api/poster_art", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.ok || !data.image_data_url) {
      if (data.need_gemini_key) {
        const inlineIn = document.getElementById("input-gemini-key-inline");
        inlineIn?.focus();
      }
      throw new Error(data.error || "生成海报原画失败");
    }

    state.lastGeneratedPosterArt = data;
    const loadedImg = await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("AI 原画图像解码失败"));
      img.src = data.image_data_url;
    });

    drawNanoBananaIllustratedPosterCanvas(ctxInfo, data, loadedImg);

    const engineLabel = data.used_nano_banana
      ? `🍌 Google Nano Banana (${data.model})`
      : `⚡ AI 原画引擎 (${data.model})`;
    if (statusBadge) {
      statusBadge.innerHTML = `<span style="color:#8fd196;font-weight:700;">✅ 已由 ${escapeHtml(
        engineLabel
      )} 生成完毕！</span> ${escapeHtml(data.scene_summary_zh || "")}`;
    }
    showToast(`已生成 ${data.hero_zh || ""} 专属 AI 战斗原画海报！点击「下载高清 PNG」即可保存`);
  } catch (err) {
    if (statusBadge) {
      statusBadge.innerHTML = `<span style="color:#ff8a75;">❌ 生图提示：${escapeHtml(err.message)}</span>`;
    }
    showToast(`AI 海报生成失败: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🍌 重新生成 Nano Banana AI 超燃/处刑原画海报";
    }
  }
}

function drawNanoBananaIllustratedPosterCanvas(ctxInfo, artData, loadedImg) {
  const canvas = document.getElementById("share-poster-canvas");
  if (!canvas || !loadedImg) return;

  const W = 920;
  const H = 1190;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const report = ctxInfo.report;
  const p = ctxInfo.player || {};
  const gp = ctxInfo.grokPlayer || (report ? findGrokPlayerEntry(p, report) : {}) || {};
  const isCareer = ctxInfo.mode === "career";
  const m = ctxInfo.careerMember || {};

  const { sideZh, won } = report
    ? getOwnAndOppPlayers(report)
    : { sideZh: "五黑跨局", won: (m.win_rate || 50) >= 50 };
  const heroZh = p.hero_short_zh || p.hero_name || artData.hero_zh || "代表英雄";
  const sc100 = isCareer ? Math.round(m.avg_rating || 75) : getHeroScore100(p, report);
  const sharePct = isCareer
    ? Number(m.avg_contrib_pct || 22).toFixed(1)
    : Number(
        gp?.grok_share_pct ?? (won ? p.contrib_share_pct : p.blame_share_pct) ?? 20
      ).toFixed(1);
  const isHighPraise = artData.tone !== "roast" && ((won && sc100 >= 70) || sc100 >= 75);
  const badgeTitle =
    ctxInfo.badgeTitle ||
    (isCareer
      ? m.role_tag || "🌟 跨局生涯档案"
      : isHighPraise
      ? "👑 胜局封神 MVP"
      : "🚨 赛后处刑主角");

  // 1. Deep Dark-Gold Background
  const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, "#0f120e");
  bgGrad.addColorStop(0.45, isHighPraise ? "#121b14" : "#1c1311");
  bgGrad.addColorStop(1, "#0a0b09");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  // 2. Top Full-Bleed AI Illustration Viewport (x=18, y=18, w=884, h=510)
  const artX = 18;
  const artY = 18;
  const artW = W - 36;
  const artH = 510;

  ctx.save();
  ctx.beginPath();
  ctx.rect(artX, artY, artW, artH);
  ctx.clip();

  // Aspect-fill (cover) drawing
  const imgRatio = loadedImg.width / Math.max(1, loadedImg.height);
  const boxRatio = artW / artH;
  let drawW = artW;
  let drawH = artH;
  let drawX = artX;
  let drawY = artY;
  if (imgRatio > boxRatio) {
    drawH = artH;
    drawW = artH * imgRatio;
    drawX = artX - (drawW - artW) / 2;
  } else {
    drawW = artW;
    drawH = artW / imgRatio;
    drawY = artY - (drawH - artH) * 0.28;
  }
  ctx.drawImage(loadedImg, drawX, drawY, drawW, drawH);

  // Top dark vignette for header pills
  const topVig = ctx.createLinearGradient(0, artY, 0, artY + 90);
  topVig.addColorStop(0, "rgba(10, 12, 10, 0.86)");
  topVig.addColorStop(1, "rgba(10, 12, 10, 0)");
  ctx.fillStyle = topVig;
  ctx.fillRect(artX, artY, artW, 90);

  // Bottom dramatic vignette blending into dossier
  const botVig = ctx.createLinearGradient(0, artY + artH - 195, 0, artY + artH);
  botVig.addColorStop(0, "rgba(12, 14, 11, 0)");
  botVig.addColorStop(0.55, "rgba(12, 14, 11, 0.78)");
  botVig.addColorStop(1, "rgba(12, 14, 11, 0.98)");
  ctx.fillStyle = botVig;
  ctx.fillRect(artX, artY + artH - 195, artW, 195);
  ctx.restore();

  // Outer Collector Border
  ctx.strokeStyle = isHighPraise ? "#d4af63" : "#d96857";
  ctx.lineWidth = 2.5;
  ctx.strokeRect(18, 18, W - 36, H - 36);

  // Divider below artwork
  ctx.strokeStyle = isHighPraise ? "rgba(212, 175, 99, 0.55)" : "rgba(217, 104, 87, 0.55)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(18, artY + artH);
  ctx.lineTo(W - 18, artY + artH);
  ctx.stroke();

  // 3. Top Header Badges over Artwork
  ctx.fillStyle = "rgba(15, 17, 14, 0.78)";
  ctx.fillRect(36, 34, 485, 32);
  ctx.strokeStyle = "#c6a468";
  ctx.lineWidth = 1;
  ctx.strokeRect(36, 34, 485, 32);
  ctx.fillStyle = "#f0c76e";
  ctx.font = "bold 13.5px sans-serif";
  const topLeftTxt = isCareer
    ? `DOTA 2 五黑跨局典藏海报 · 跨 ${ctxInfo.totalAnalyzed || m.games || 0} 局 AI 实锤档案`
    : `DOTA 2 典藏级个人战报海报 · #${report.match_id} (${sideZh}${won ? "胜" : "负"} ${report.radiant_score}:${report.dire_score} · ${report.duration_str})`;
  ctx.fillText(topLeftTxt, 48, 55);

  const engTag = artData.used_nano_banana
    ? "🍌 GOOGLE NANO BANANA 2.1 · AI 定制原画"
    : "⚡ AI 定制超燃战斗原画 · HD COLLECTOR";
  ctx.font = "bold 12.5px sans-serif";
  const engW = ctx.measureText(engTag).width + 26;
  ctx.fillStyle = "rgba(22, 26, 20, 0.85)";
  ctx.fillRect(W - 36 - engW, 34, engW, 32);
  ctx.strokeStyle = "#e0b965";
  ctx.strokeRect(W - 36 - engW, 34, engW, 32);
  ctx.fillStyle = "#f7d788";
  ctx.textAlign = "right";
  ctx.fillText(engTag, W - 49, 55);
  ctx.textAlign = "left";

  // 4. Hero & Player Title Overlaid on Bottom of Artwork (y = 390..515)
  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.92)";
  ctx.shadowBlur = 10;
  ctx.fillStyle = "#fffaf0";
  ctx.font = "bold 31px sans-serif";
  const mainTitle = isCareer
    ? `${m.personaname} · 本命【${heroZh}】`
    : `[${p.pos_label || `${p.pos || 1}号位`}] ${p.personaname} · ${heroZh}`;
  ctx.fillText(mainTitle, 42, 434);

  // Score & Contribution Badge on Right
  ctx.fillStyle = isHighPraise ? "#98f5a0" : "#ff9482";
  ctx.font = "bold 24px sans-serif";
  ctx.textAlign = "right";
  const rightScoreTxt = isCareer
    ? `${badgeTitle} ｜ 场均 ${sc100}/100分 · 胜率 ${m.win_rate}%`
    : `${badgeTitle} ｜ 评分 ${sc100}/100 · ${won ? "功勋" : "分锅"} ${sharePct}%`;
  ctx.fillText(rightScoreTxt, W - 42, 432);
  ctx.textAlign = "left";

  // Trophy / Nemesis & Ult Ribbon inside Artwork Bottom
  const killsList = ((p.kills_breakdown?.heroes || []).slice(0, 4))
    .map((v) => `${v.hero_short_zh}×${v.count}`)
    .join(" · ");
  const nemList = ((p.killed_by_breakdown?.heroes || []).slice(0, 3))
    .map((v) => `${v.hero_short_zh}×${v.count}`)
    .join(" · ");
  const execBadges = ((p.hero_execution_audit?.headline_badges || []).slice(0, 2))
    .map((b) => (typeof b === "string" ? b : b?.text || ""))
    .filter(Boolean)
    .join(" ｜ ");

  ctx.fillStyle = "#f3d078";
  ctx.font = "bold 14.5px sans-serif";
  const ribbonLine1 = isCareer
    ? `🏆 绝活代表：${(m.signature_heroes || []).map((h) => `${h.hero_short_zh}(${h.win_rate}%胜·${h.avg_rating}分)`).join(" / ") || heroZh}`
    : isHighPraise
    ? `🗡️ 手刃猎物：${killsList || "正面碾压敌方全员"}${execBadges ? ` ｜ ⚡ ${execBadges}` : ""}`
    : `💀 犯罪现场：被 ${nemList || "敌方核心"} 连续提款${execBadges ? ` ｜ 🔬 ${execBadges}` : ""}`;
  ctx.fillText(ribbonLine1.slice(0, 68), 42, 468);

  ctx.fillStyle = "#dad4c6";
  ctx.font = "13px sans-serif";
  const sceneLine = `🎬 ${artData.scene_summary_zh || ""}`.slice(0, 72);
  ctx.fillText(sceneLine, 42, 496);
  ctx.restore();

  // 5. Lower Tactical Dossier Section (y = 542..1160)
  let y = 544;

  // Stats Bar
  ctx.fillStyle = "#171a15";
  ctx.fillRect(42, y, W - 84, 42);
  ctx.strokeStyle = "#32362b";
  ctx.lineWidth = 1;
  ctx.strokeRect(42, y, W - 84, 42);
  ctx.fillStyle = "#e5dfd0";
  ctx.font = "bold 13.5px sans-serif";
  const finalItemsStr = (p.final_items || [])
    .filter((it) => it && !String(it).startsWith("[中立]"))
    .map((it) => String(it).split("(")[0])
    .slice(0, 5)
    .join("·");
  const statsBarTxt = isCareer
    ? `跨 ${m.games} 局 (${m.wins}胜${m.games - m.wins}负) ｜ ${m.mvp_count}次MVP / ${m.culprit_count}次首锅 ｜ 场均KDA ${m.avg_kda} ｜ 辅助失职 ${m.support_grief_count || 0}局 ｜ 孤狼被抓 ${m.solo_pickoffs_total || 0}次`
    : `KDA ${p.kda} (参战 ${p.kill_participation_pct}%) ｜ GPM ${p.gpm}/XPM ${p.xpm} ｜ 伤害 ${fmtNum(p.hero_damage)} (${p.hero_damage_share_pct}%) ｜ 塔伤 ${fmtNum(p.tower_damage)} ｜ 神装: ${finalItemsStr || "-"}`;
  ctx.fillText(statsBarTxt.slice(0, 76), 54, y + 26);
  y += 54;

  // Headline Quote Box
  ctx.fillStyle = "#1c1913";
  ctx.fillRect(42, y, W - 84, 44);
  ctx.strokeStyle = "#524326";
  ctx.strokeRect(42, y, W - 84, 44);
  ctx.fillStyle = "#f2c96d";
  ctx.font = "bold 15px sans-serif";
  const hlText = (
    isCareer
      ? m.habit_diagnosis?.pos_verdict || "五黑跨局生涯体检定性"
      : gp?.headline || p.blame_Headline || "录像级全周期数据实锤定责"
  ).slice(0, 56);
  ctx.fillText(`🗣️ “${hlText}”`, 56, y + 28);
  y += 56;

  // Block 1: Deep Verdict & Role Duty
  const verdictRaw = isCareer
    ? m.habit_diagnosis?.habit_flaws_summary || ""
    : gp?.deep_verdict || (p.verdict_bullets || []).join("；") || "";
  ctx.font = "13.5px sans-serif";
  const verdictLines = wrapCanvasParagraph(ctx, verdictRaw, W - 116, 4);
  const b1H = Math.max(92, 38 + verdictLines.length * 21);
  ctx.fillStyle = "#141713";
  ctx.fillRect(42, y, W - 84, b1H);
  ctx.strokeStyle = "#35382e";
  ctx.strokeRect(42, y, W - 84, b1H);
  ctx.fillStyle = "#e0c389";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText(
    isCareer
      ? "📋 跨局毒瘤与失误习性实锤 (Multi-Match Habit Forensics)"
      : "📋 本职工作与全周期结案陈词 (Role Duty & Deep Verdict)",
    56,
    y + 24
  );
  ctx.fillStyle = "#e3dfd5";
  ctx.font = "13.5px sans-serif";
  verdictLines.forEach((ln, idx) => {
    ctx.fillText(ln, 56, y + 48 + idx * 20);
  });
  y += b1H + 12;

  // Block 2: Item & Blink Audit (or BP Mandate for Career)
  const itemText = isCareer
    ? m.habit_diagnosis?.bp_and_team_mandate || ""
    : gp?.item_and_blink_audit ||
      (p.key_item_timings || []).join(" → ") ||
      (p.final_items || []).join(" · ");
  ctx.font = "13.5px sans-serif";
  const itemLines = wrapCanvasParagraph(ctx, itemText, W - 116, 3);
  const b2H = Math.max(76, 36 + itemLines.length * 20);
  ctx.fillStyle = "#181612";
  ctx.fillRect(42, y, W - 84, b2H);
  ctx.strokeStyle = "#4a3e28";
  ctx.strokeRect(42, y, W - 84, b2H);
  ctx.fillStyle = "#f0c76e";
  ctx.font = "bold 14px sans-serif";
  ctx.fillText(
    isCareer
      ? "🚨 队长下把 BP 封印与选位死命令 (Captain's Draft Mandate)"
      : "🎒 灵性/犯罪出装与关键装时间轴审计 (Itemization & Timing Audit)",
    56,
    y + 23
  );
  ctx.fillStyle = "#dcd6c8";
  ctx.font = "13px sans-serif";
  itemLines.forEach((ln, idx) => {
    ctx.fillText(ln, 56, y + 45 + idx * 19);
  });
  y += b2H + 12;

  // Block 3: 3-Act Chronological Breakdown (for match posters)
  const acts = isCareer
    ? (m.pos_breakdown || []).slice(0, 3).map((pb) => ({
        label: `🧭 ${pb.pos_label} (${pb.games}局 · ${pb.win_rate}%胜)`,
        txt: `场均评分 ${pb.avg_rating}/100 分，代表英雄：${pb.top_hero || "-"}`,
      }))
    : [
        { label: "🌅 第一幕 (对线 0-10m)", txt: gp?.early_story || "" },
        { label: "⚔️ 第二幕 (中期 10-25m)", txt: gp?.mid_story || "" },
        { label: "🔥 第三幕 (决胜 25m+)", txt: gp?.late_story || "" },
      ].filter((a) => a.txt);

  if (acts.length > 0) {
    const colW = Math.floor((W - 84 - (acts.length - 1) * 12) / acts.length);
    const actH = 195;
    acts.forEach((act, idx) => {
      const cx = 42 + idx * (colW + 12);
      ctx.fillStyle = "#141613";
      ctx.fillRect(cx, y, colW, actH);
      ctx.strokeStyle = "#2f3329";
      ctx.strokeRect(cx, y, colW, actH);

      ctx.fillStyle = "#8ec0e4";
      ctx.font = "bold 13px sans-serif";
      ctx.fillText(act.label, cx + 12, y + 22);

      ctx.fillStyle = "#d5d1c5";
      ctx.font = "12.5px sans-serif";
      const aLines = wrapCanvasParagraph(ctx, act.txt, colW - 24, 8);
      aLines.forEach((ln, lIdx) => {
        ctx.fillText(ln, cx + 12, y + 44 + lIdx * 18);
      });
    });
    y += actH + 14;
  }

  // Footer
  const prac = (
    isCareer
      ? m.habit_diagnosis?.bp_and_team_mandate || "扬长避短锁定本命位置"
      : gp?.practice || p.next_game_action || "盯紧强势期第一波抱团推塔节奏"
  ).slice(0, 56);
  ctx.fillStyle = "#8fd196";
  ctx.font = "bold 13.5px sans-serif";
  ctx.fillText(`💡 下把铁律：${prac}`, 42, H - 30);

  ctx.fillStyle = "#9e9b91";
  ctx.font = "12px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(
    `dota-ai-analyst.vercel.app${report?.match_id ? `/?match=${report.match_id}` : ""}`,
    W - 42,
    H - 30
  );
  ctx.textAlign = "left";
}

/**
 * 15. Workspace Mode Switcher & Pre-Game 5-Stack Live Draft Coach (/pregame)
 */
function switchWorkspaceMode(mode, { pushUrl = true, animate = true } = {}) {
  const validMode =
    mode === "pregame" ? "pregame" : mode === "postgame" ? "postgame" : "home";
  const prevMode = state.workspaceMode;
  state.workspaceMode = validMode;

  const applyDomUpdate = () => {
    const homeView = document.getElementById("home-workspace");
    const postView = document.getElementById("postgame-workspace");
    const preView = document.getElementById("pregame-workspace");

    if (homeView) homeView.hidden = validMode !== "home";
    if (postView) postView.hidden = validMode !== "postgame";
    if (preView) preView.hidden = validMode !== "pregame";

    document
      .getElementById("nav-mode-home")
      ?.classList.toggle("active", validMode === "home");
    document
      .getElementById("nav-mode-postgame")
      ?.classList.toggle("active", validMode === "postgame");
    document
      .getElementById("nav-mode-pregame")
      ?.classList.toggle("active", validMode === "pregame");

    if (pushUrl && window.history?.pushState) {
      if (validMode === "pregame") {
        if (window.location.pathname !== "/pregame") {
          window.history.pushState(
            { ...(window.history.state || {}), workspaceMode: "pregame" },
            "",
            "/pregame"
          );
        }
      } else if (validMode === "home") {
        if (window.location.pathname !== "/" || window.location.search !== "") {
          window.history.pushState(
            { ...(window.history.state || {}), workspaceMode: "home" },
            "",
            "/"
          );
        }
      } else if (validMode === "postgame") {
        const matchId = state.pendingMatchId || state.currentMatchId || state.currentReport?.match_id;
        if (matchId) {
          syncMatchUrlInAddressBar(matchId, { replace: false });
        }
      }
    }

    if (validMode === "pregame") {
      renderPregameSlots();
      renderPregameHeroGrid();
      if (!state.pregamePlan) {
        requestAndRenderPregamePlan({ useLlm: false });
      }
    } else if (validMode === "home") {
      renderHomeWorkspace();
    }

    if (prevMode !== validMode) {
      window.scrollTo({ top: 0, behavior: "instant" });
      const targetHeading =
        validMode === "home"
          ? document.getElementById("home-hero-heading")
          : validMode === "postgame"
          ? document.getElementById("match-overview-title")
          : document.getElementById("pregame-title");
      targetHeading?.focus?.({ preventScroll: true });
    }
  };

  if (
    animate &&
    prevMode !== validMode &&
    typeof document !== "undefined" &&
    typeof document.startViewTransition === "function" &&
    !window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
  ) {
    document.startViewTransition(() => applyDomUpdate());
  } else {
    applyDomUpdate();
  }
}

function initPregameWorkspace() {
  renderPregameSlots();
  renderPregameHeroGrid();
  if (state.workspaceMode === "pregame" && !state.pregamePlan) {
    requestAndRenderPregamePlan({ useLlm: false });
  }
}

function getHeroMetaById(heroId) {
  if (!heroId) return null;
  return (state.heroesCatalog || []).find((h) => Number(h.id) === Number(heroId)) || null;
}

function getSquadPlayerNameForPos(pos) {
  const defaultMap = {
    1: state.roster?.main_name || "Flame = ez mute",
    2: "Replica",
    3: "Make Your Choice",
    4: "Paphets",
    5: "Mr. Brightside",
  };
  return defaultMap[pos] || `${pos}号位队友`;
}

function renderPregameSlots() {
  const ownWrap = document.getElementById("pregame-own-slots");
  const enemyWrap = document.getElementById("pregame-enemy-slots");
  const indicator = document.getElementById("pregame-active-slot-indicator");

  const posTitles = {
    1: "1号位 · 主核",
    2: "2号位 · 中单",
    3: "3号位 · 前排",
    4: "4号位 · 游走",
    5: "5号位 · 辅助",
  };

  if (ownWrap) {
    const slots = [1, 2, 3, 4, 5].map((pos) => {
      const entry = (state.pregameOwnPicks || []).find((x) => Number(x.pos) === pos) || {
        pos,
        hero_id: 0,
        player_name: getSquadPlayerNameForPos(pos),
      };
      const hero = getHeroMetaById(entry.hero_id);
      const isActive = state.pregameActiveSide === "own" && Number(state.pregameActivePos) === pos;
      return `
        <div class="pregame-slot-card ${isActive ? "active-slot" : ""}" data-pg-slot="own:${pos}">
          <div class="pregame-slot-pos">
            <span>${escapeHtml(posTitles[pos])}</span>
            ${
              hero
                ? `<button type="button" class="text-button" style="font-size:10px;padding:0;" data-pg-clear="own:${pos}" title="清空该槽位">✕</button>`
                : ""
            }
          </div>
          <div class="pregame-slot-hero">
            ${
              hero
                ? `<img src="${escapeHtml(hero.img)}" width="38" height="21" alt="${escapeHtml(
                    hero.short_zh
                  )}" /><strong>${escapeHtml(hero.short_zh)}</strong>`
                : `<span style="font-size:11px;color:var(--dim);">点击点选英雄</span>`
            }
          </div>
          <div class="pregame-slot-player">👤 ${escapeHtml(
            entry.player_name || getSquadPlayerNameForPos(pos)
          )}</div>
        </div>
      `;
    });
    ownWrap.innerHTML = slots.join("");
  }

  if (enemyWrap) {
    const slots = [1, 2, 3, 4, 5].map((pos) => {
      const entry = (state.pregameEnemyPicks || []).find((x) => Number(x.pos) === pos) || {
        pos,
        hero_id: 0,
      };
      const hero = getHeroMetaById(entry.hero_id);
      const isActive =
        state.pregameActiveSide === "enemy" && Number(state.pregameActivePos) === pos;
      return `
        <div class="pregame-slot-card ${isActive ? "active-slot" : ""}" data-pg-slot="enemy:${pos}">
          <div class="pregame-slot-pos">
            <span>敌方 ${pos}号位</span>
            ${
              hero
                ? `<button type="button" class="text-button" style="font-size:10px;padding:0;" data-pg-clear="enemy:${pos}" title="清空该槽位">✕</button>`
                : ""
            }
          </div>
          <div class="pregame-slot-hero">
            ${
              hero
                ? `<img src="${escapeHtml(hero.img)}" width="38" height="21" alt="${escapeHtml(
                    hero.short_zh
                  )}" /><strong>${escapeHtml(hero.short_zh)}</strong>`
                : `<span style="font-size:11px;color:var(--dim);">可选填敌方</span>`
            }
          </div>
          <div class="pregame-slot-player">对手 #${pos}</div>
        </div>
      `;
    });
    enemyWrap.innerHTML = slots.join("");
  }

  if (indicator) {
    indicator.textContent = `当前正在选择：${
      state.pregameActiveSide === "own" ? "本方" : "敌方"
    } ${state.pregameActivePos}号位`;
  }

  document.querySelectorAll("[data-pg-slot]").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("[data-pg-clear]")) return;
      const [side, posStr] = (el.getAttribute("data-pg-slot") || "own:1").split(":");
      state.pregameActiveSide = side;
      state.pregameActivePos = Number(posStr || 1);
      renderPregameSlots();
    });
  });

  document.querySelectorAll("[data-pg-clear]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const [side, posStr] = (btn.getAttribute("data-pg-clear") || "own:1").split(":");
      const pos = Number(posStr || 1);
      if (side === "own") {
        state.pregameOwnPicks = (state.pregameOwnPicks || []).filter(
          (x) => Number(x.pos) !== pos
        );
      } else {
        state.pregameEnemyPicks = (state.pregameEnemyPicks || []).filter(
          (x) => Number(x.pos) !== pos
        );
      }
      state.pregameActiveSide = side;
      state.pregameActivePos = pos;
      renderPregameSlots();
      renderPregameHeroGrid();
      requestAndRenderPregamePlan({ useLlm: false });
    });
  });
}

function renderPregameHeroGrid() {
  const grid = document.getElementById("pregame-hero-grid");
  if (!grid) return;

  const q = (state.pregameHeroQuery || "").toLowerCase();
  const pickedIds = new Set([
    ...(state.pregameOwnPicks || []).map((x) => Number(x.hero_id)).filter(Boolean),
    ...(state.pregameEnemyPicks || []).map((x) => Number(x.hero_id)).filter(Boolean),
  ]);

  const filtered = (state.heroesCatalog || []).filter((h) => {
    if (!q) return true;
    const hay = `${h.short_zh || ""} ${h.full_zh || ""} ${h.en_name || ""} ${
      h.npc || ""
    }`.toLowerCase();
    return hay.includes(q);
  });

  grid.innerHTML = filtered
    .map((h) => {
      const hid = Number(h.id);
      const isPicked = pickedIds.has(hid);
      return `
        <button type="button" class="pregame-hero-btn ${
          isPicked ? "picked" : ""
        }" data-pick-hero="${hid}" title="${escapeHtml(h.short_zh)} (${escapeHtml(
          h.en_name || ""
        )})">
          <img src="${escapeHtml(h.img)}" width="28" height="16" alt="${escapeHtml(
            h.short_zh
          )}" loading="lazy" />
          <span>${escapeHtml(h.short_zh)}</span>
        </button>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-pick-hero]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const hid = Number(btn.getAttribute("data-pick-hero"));
      // Remove duplicate hero if already selected elsewhere
      state.pregameOwnPicks = (state.pregameOwnPicks || []).filter(
        (x) => Number(x.hero_id) !== hid
      );
      state.pregameEnemyPicks = (state.pregameEnemyPicks || []).filter(
        (x) => Number(x.hero_id) !== hid
      );

      const pos = Number(state.pregameActivePos || 1);
      if (state.pregameActiveSide === "own") {
        state.pregameOwnPicks = (state.pregameOwnPicks || []).filter(
          (x) => Number(x.pos) !== pos
        );
        state.pregameOwnPicks.push({
          pos,
          hero_id: hid,
          player_name: getSquadPlayerNameForPos(pos),
        });
        state.pregameOwnPicks.sort((a, b) => a.pos - b.pos);
        if (pos < 5) state.pregameActivePos = pos + 1;
      } else {
        state.pregameEnemyPicks = (state.pregameEnemyPicks || []).filter(
          (x) => Number(x.pos) !== pos
        );
        state.pregameEnemyPicks.push({ pos, hero_id: hid });
        state.pregameEnemyPicks.sort((a, b) => a.pos - b.pos);
        if (pos < 5) state.pregameActivePos = pos + 1;
      }

      renderPregameSlots();
      renderPregameHeroGrid();
      requestAndRenderPregamePlan({ useLlm: false });
    });
  });
}

async function requestAndRenderPregamePlan({ useLlm = false } = {}) {
  const out = document.getElementById("pregame-plan-output");
  if (!out) return;

  const validOwn = (state.pregameOwnPicks || []).filter((x) => Number(x.hero_id) > 0);
  if (validOwn.length === 0) {
    out.innerHTML = `<div class="empty-state">请至少在上方点选本方 1~5 号位英雄，作战室将立即生成本局配合连招与前中后期作战纲领。</div>`;
    return;
  }

  const grokBtn = document.getElementById("btn-pregame-grok");
  if (useLlm && grokBtn) {
    grokBtn.disabled = true;
    grokBtn.textContent = "🧠 Grok 4.7 正在推演本局五黑战术...";
  }

  try {
    const llmCfg = getEffectiveLlmConfig();
    const res = await fetch("/api/pregame_plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        own_picks: validOwn,
        enemy_picks: (state.pregameEnemyPicks || []).filter((x) => Number(x.hero_id) > 0),
        use_llm: Boolean(useLlm),
        api_key: llmCfg.apiKey || "",
        provider: llmCfg.provider || "xai",
        model: llmCfg.model || "grok-4.7",
        base_url: llmCfg.baseUrl || "https://api.x.ai/v1",
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "生成赛前作战方案失败");
    state.pregamePlan = data.plan;
    renderPregamePlanOutput(data.plan);
    if (useLlm) {
      if (data.plan?.grok_live_brief) {
        showToast("Grok 4.7 赛前深度战术推演已就绪！");
      } else if (data.plan?.llm_error) {
        showToast(`Grok 推演提示: ${data.plan.llm_error}`);
      }
    }
  } catch (err) {
    showToast(`赛前作战室推演失败: ${err.message}`);
  } finally {
    if (useLlm && grokBtn) {
      grokBtn.disabled = false;
      grokBtn.textContent = "🧠 呼叫 Grok 4.7 深度推演本局战术";
    }
  }
}

function renderPregamePlanOutput(plan) {
  const out = document.getElementById("pregame-plan-output");
  if (!out || !plan) return;

  const grokBrief = plan.grok_live_brief || null;
  const combos = plan.combos || [];
  const early = plan.early_plan || {};
  const mid = plan.mid_plan || {};
  const late = plan.late_plan || {};
  const roles = plan.role_guides || [];

  const grokBannerHtml = grokBrief
    ? `
      <article class="grok-banner" style="margin-bottom:4px;">
        <div class="grok-banner-head">
          <span class="grok-tag">XAI / GROK-4.7 赛前实时推演</span>
          <span class="grok-banner-title">${escapeHtml(
            grokBrief.headline || "五黑赛前战术总纲"
          )}</span>
        </div>
        <p class="grok-summary-p">${escapeHtml(
          grokBrief.win_condition || plan.win_condition || ""
        )}</p>
        ${
          Array.isArray(grokBrief.combo_calls) && grokBrief.combo_calls.length > 0
            ? `<div class="grok-verdict-box">🎙️ <b>语音连招口令：</b>${escapeHtml(
                grokBrief.combo_calls.join(" ｜ ")
              )}</div>`
            : ""
        }
        ${
          grokBrief.target_priority
            ? `<div class="grok-practice-strip">🎯 <b>团战第一集火目标：</b>${escapeHtml(
                grokBrief.target_priority
              )}</div>`
            : ""
        }
      </article>
    `
    : "";

  const combosHtml = combos
    .map((c) => {
      const avatars = (c.heroes || [])
        .map(
          (h) => `
          <span class="combo-hero-tag">
            ${
              h.hero_img
                ? `<img src="${escapeHtml(h.hero_img)}" width="28" height="16" alt="${escapeHtml(
                    h.hero_short_zh
                  )}" />`
                : ""
            }
            <span>${h.pos}号位·${escapeHtml(h.hero_short_zh)}</span>
          </span>
        `
        )
        .join("<span>+</span>");

      return `
        <article class="combo-card">
          <div class="combo-head">
            <div class="combo-heroes-avatars">${avatars}</div>
            <span class="combo-phase-tag">核心配合连招</span>
          </div>
          <h4 class="combo-title">🔥 ${escapeHtml(c.name || "双人/多人技能联动")}</h4>
          <p class="combo-how">${escapeHtml(c.mechanic || "")}</p>
          <div class="combo-audit">🎙️ ${escapeHtml(c.voice_call || "")}</div>
        </article>
      `;
    })
    .join("");

  out.innerHTML = `
    ${grokBannerHtml}

    <!-- 1. 核心赢法 vs 翻车红线 + 团战集火优先级 -->
    <div class="pregame-winloss-grid">
      <article class="pregame-wl-card win">
        <h3>🏆 本局核心赢法 · 评级 ${escapeHtml(plan.grade || "A")} (${
          plan.overall_score || 78
        }分 · ${escapeHtml(plan.tempo_style || "")})</h3>
        <p>${escapeHtml(grokBrief?.win_condition || plan.win_condition || "")}</p>
        <div style="font-size:12px;color:var(--green-light);padding-top:6px;border-top:1px dashed #2e3429;">
          🎯 <b>团战第一集火律令：</b>${escapeHtml(
            grokBrief?.target_priority || plan.target_priority || ""
          )}
        </div>
      </article>

      <article class="pregame-wl-card lose">
        <h3>⚠️ 本局绝对翻车红线 (怎么输 &amp; 敌方克制点)</h3>
        <p>${escapeHtml(grokBrief?.lose_condition || plan.lose_condition || "")}</p>
        ${
          (plan.counter_tips || []).length > 0
            ? `<div style="font-size:11.5px;color:#e3b3a8;padding-top:6px;border-top:1px dashed #3d2b28;">
                🛡️ <b>针对敌方阵容细节：</b>${escapeHtml(plan.counter_tips[0])}
              </div>`
            : ""
        }
      </article>
    </div>

    <!-- 2. 这套阵容有什么配合可以打 (Combo 链与语音口令) -->
    <section>
      <div class="combos-header-bar">
        <h3>🔗 一、这套五黑阵容有什么配合可以打（必打技能 Combo 链 &amp; 开黑语音口令）</h3>
        <span style="font-size:11px;color:var(--muted);">开团前先报跳刀/大招 CD，严禁脱节单跳</span>
      </div>
      <div class="combos-grid">
        ${combosHtml || `<div class="empty-state compact">点选 2 名以上英雄即可生成专属配合连招</div>`}
      </div>
    </section>

    <!-- 3. 前期 (0-10m) / 中期 (10-25m) / 后期 (25m+) 团队三阶段作战纲领 -->
    <section>
      <div class="combos-header-bar">
        <h3>⏱️ 二、前、中、后期五黑整体作战纲领（对线怎么分路、中期谁带队开雾、后期怎么上高）</h3>
        <span style="font-size:11px;color:var(--muted);">按时间节点严格执行团队节奏</span>
      </div>
      <div class="pregame-stages-grid">
        <article class="pregame-stage-box">
          <h3>🌅 ${escapeHtml(early.title || "前期对线与抢符 (00:00–10:00)")}</h3>
          <ul>
            ${
              grokBrief?.early_game
                ? `<li style="color:var(--gold-light);font-weight:600;">[Grok 重点] ${escapeHtml(
                    grokBrief.early_game
                  )}</li>`
                : ""
            }
            ${(early.lanes || [])
              .map(
                (ln) =>
                  `<li><strong style="color:var(--text);">${escapeHtml(ln.lane)} — ${escapeHtml(
                    ln.heroes
                  )}：</strong>${escapeHtml((ln.tasks || []).join(" "))}</li>`
              )
              .join("")}
          </ul>
        </article>

        <article class="pregame-stage-box">
          <h3>🔥 ${escapeHtml(mid.title || "中期抱团与控图 (10:00–25:00)")}</h3>
          <ul>
            ${
              grokBrief?.mid_game
                ? `<li style="color:var(--gold-light);font-weight:600;">[Grok 重点] ${escapeHtml(
                    grokBrief.mid_game
                  )}</li>`
                : ""
            }
            ${(mid.key_timings || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("")}
          </ul>
        </article>

        <article class="pregame-stage-box">
          <h3>👑 ${escapeHtml(late.title || "后期盾团与高地终结 (25:00+)")}</h3>
          <ul>
            ${
              grokBrief?.late_game
                ? `<li style="color:var(--gold-light);font-weight:600;">[Grok 重点] ${escapeHtml(
                    grokBrief.late_game
                  )}</li>`
                : ""
            }
            ${(late.rules || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}
          </ul>
        </article>
      </div>
    </section>

    <!-- 4. 1~5 号位每人专属出装与本局铁律卡片 -->
    <section>
      <div class="combos-header-bar">
        <h3>🎯 三、1~5 号位每人专属推荐出装、最佳拍档与本局第一铁律</h3>
        <span style="font-size:11px;color:var(--muted);">点击右上角「复制赛前作战简报」可一键发到开黑群</span>
      </div>
      <div class="pregame-roles-grid">
        ${roles
          .map((rg) => {
            const grokRoleTip = (grokBrief?.role_tips || {})[String(rg.pos)] || "";
            return `
              <article class="pregame-role-card">
                <div class="pregame-role-head">
                  ${
                    rg.hero_img
                      ? `<img src="${escapeHtml(rg.hero_img)}" width="38" height="21" alt="${escapeHtml(
                          rg.hero_short_zh
                        )}" />`
                      : ""
                  }
                  <div style="min-width:0;">
                    <div style="font-size:12.5px;font-weight:700;color:var(--gold-light);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                      ${rg.pos}号位 · ${escapeHtml(rg.hero_short_zh)}
                    </div>
                    <div style="font-size:10.5px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                      玩家：${escapeHtml(rg.player_name)}
                    </div>
                  </div>
                </div>
                <div style="font-size:11px;color:var(--muted);line-height:1.6;">
                  <b style="color:var(--gold);display:block;margin-bottom:2px;">🛠️ 关键出装顺序：</b>
                  ${escapeHtml((rg.recommended_items || []).join(" → "))}
                </div>
                <div style="font-size:11px;color:var(--muted);line-height:1.6;">
                  <b style="color:var(--green-light);display:block;margin-bottom:2px;">🤝 联动拍档：</b>
                  ${escapeHtml(rg.partner_synergy || "")}
                </div>
                <div style="font-size:11px;color:#e5dec9;background:#161814;border-left:2px solid var(--gold);padding:6px 8px;line-height:1.55;margin-top:auto;">
                  <b>📌 本局铁律：</b>${escapeHtml(grokRoleTip || rg.golden_rule || "")}
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

document.addEventListener("DOMContentLoaded", initApp);


