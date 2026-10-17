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
  workspaceMode: "postgame", // "postgame" | "pregame"
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

function fmtNum(n) {
  const num = Number(n || 0);
  return num.toLocaleString("en-US");
}

function fmtSigned(n) {
  const num = Math.round(Number(n || 0));
  return num > 0 ? `+${fmtNum(num)}` : fmtNum(num);
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
    storyHtml: escapeHtml(storyText),
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
  let punchline = "";
  let badge = "🎙️ AI 老炮个人点评";
  let tone = "mixed";
  const rating = Number(p.rating_score || 6.0);
  if (pWon) {
    if (isMvp || rating >= 8.0) {
      badge = "👑 AI 封神表彰评书";
      tone = "praise";
      punchline = `全场贡献 ${cPct}% 胜局功勋（评分 ${rating.toFixed(1)}），从对线一路C到终局的绝对真神，这把赢球全队得给你敬一杯！`;
    } else if ((p.dead_seconds || 0) >= 180) {
      badge = "🌶️ AI 胜局毒舌敲打";
      tone = "mixed";
      punchline = `虽然最后躺赢拿下比赛（贡献 ${cPct}%），但全场在泉水读秒长达 ${p.dead_seconds} 秒，属于边送边赢的“气氛组功臣”，下把少走两步危险线！`;
    } else {
      badge = "🏆 AI 凯旋功臣点评";
      tone = "praise";
      punchline = `稳健拿下 ${cPct}% 胜局贡献（评分 ${rating.toFixed(1)}），完美执行了 ${p.pos} 号位本职工作，是车队赢球不可或缺的坚实拼图！`;
    }
  } else {
    if (isTopCulprit || Number(bPct) >= 25) {
      badge = "🚨 AI 一级战犯处刑词";
      tone = "roast";
      punchline = `全场背下 ${bPct}% 头号大锅（泉水读秒 ${p.dead_seconds || 0} 秒 / 阵亡掉钱 -${fmtNum(
        p.death_gold_lost || 0
      )}）！${
        p.pos <= 3 && (p.tower_damage || 0) < 1200
          ? `占着 ${fmtNum(p.net_worth)} 净资产却只摸了 ${fmtNum(p.tower_damage || 0)} 点建筑伤害，纯纯的刷钱不拆塔提款机，`
          : ""
      }这把输球你得在群里主动发红包谢罪！`;
    } else if (rating >= 7.2 || Number(p.hero_damage_share_pct) >= 28) {
      badge = "🛡️ AI 悲情院长平反词";
      tone = "praise";
      punchline = `虽败犹荣的“悲情院长”（评分 ${rating.toFixed(1)}，背锅仅 ${bPct}%）！一个人扛起全队 ${
        p.hero_damage_share_pct
      }% 的英雄输出，${
        p.pos <= 2 && (p.tower_damage || 0) < 1000
          ? `美中不足是建筑推塔伤害偏低（仅 ${fmtNum(p.tower_damage || 0)}），团赢后没能转化成实质塔数，`
          : ""
      }奈何身边队友倒得比野怪还快，实在带不动！`;
    } else {
      badge = "⚖️ AI 败局算账点评";
      tone = "roast";
      punchline = `本局分摊 ${bPct}% 败局责任（泉水读秒 ${p.dead_seconds || 0} 秒），中后期几波关键团战走位与技能衔接跟着全队一起随波逐流，下把急需找回状态！`;
    }
  }

  const baseStory =
    `前10分钟在${p.lane_role || "线上"}交出 ${lh10}/${dn10} 补刀（效率 ${laneEff}%），装备按「${itemRouteStr}」成型；` +
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
    storyText: fullText,
    storyHtml: escapeHtml(fullText),
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

  // Normalize 100% contribution and 100% blame shares
  const rawContribSum =
    own.reduce((s, p) => s + Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)), 0) || 100;
  const contribMap = new Map();
  own.forEach((p) => {
    const pct = Number(
      ((Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)) / rawContribSum) * 100).toFixed(1)
    );
    contribMap.set(Number(p.player_slot), pct);
  });

  const rawBlameSum =
    own.reduce((s, p) => s + Math.max(1, Number(p.blame_share_pct || 20)), 0) || 100;
  const blameMap = new Map();
  own.forEach((p) => {
    const pct = Number(((Math.max(1, Number(p.blame_share_pct || 20)) / rawBlameSum) * 100).toFixed(1));
    blameMap.set(Number(p.player_slot), pct);
  });

  const sortedByContrib = [...own].sort(
    (a, b) => (contribMap.get(Number(b.player_slot)) || 0) - (contribMap.get(Number(a.player_slot)) || 0)
  );
  const sortedByBlame = [...own].sort(
    (a, b) => (blameMap.get(Number(b.player_slot)) || 0) - (blameMap.get(Number(a.player_slot)) || 0)
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
      const cPct = contribMap.get(Number(p.player_slot)) ?? 20.0;
      const bPct = blameMap.get(Number(p.player_slot)) ?? 20.0;
      const sharePct = ownWon ? cPct : bPct;
      const roleNote = ownWon
        ? p.praise_talk || (p.strengths || [])[0] || "稳定发挥完成战术任务"
        : p.trash_talk || (p.weaknesses || [])[0] || "存在团战或对线细节失误";
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
          <td><b>${p.rating_score ?? 0} 分</b><br/><span class="fs-sub">${escapeHtml(
        ownWon ? p.contrib_tier || "核心功臣" : p.rating_tier || "常规表现"
      )}</span></td>
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
        grokPlayer: grokPlayersMap.get(Number(p.player_slot)),
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
                <b>${p.pos}号位 · ${escapeHtml(heroShort)}</b><br/>
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
                ? `胜局贡献 ${contribMap.get(Number(topMvp?.player_slot)) ?? 25}% · 评分 ${
                    topMvp?.rating_score ?? 8.5
                  }`
                : `分锅占比 ${blameMap.get(Number(topCulprit?.player_slot)) ?? 30}% · 评分 ${
                    topCulprit?.rating_score ?? 5.0
                  }`
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

        <h3 class="fs-subtable-title">⚔️ 全场最高烈度关键胜负手团战故事回放与经济拐点明细</h3>
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
        `${p.rating_score ?? 0} 分\n${ownWon ? p.contrib_tier || "功臣" : p.rating_tier || ""}`,
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
        "综合评分",
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
      drawSubSectionTitle("3.2 全场最高烈度关键胜负手团战故事回放与经济拐点明细（AI 刀塔老炮复盘评书）");
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
        grokPlayer: grokPlayersMapPdf.get(Number(p.player_slot)),
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
        `${p.pos}号位 · ${heroShort}\n${p.personaname || ""}\nKDA ${p.kda}\n10m补刀 ${
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

function syncMatchUrlInAddressBar(matchId) {
  if (!matchId || state.workspaceMode === "pregame") return;
  try {
    if (window.history?.replaceState) {
      const side = state.currentReport ? getAuditedSide(state.currentReport) : state.perspective;
      const sideQuery = side === "dire" || side === "radiant" ? `&side=${encodeURIComponent(side)}` : "";
      const nextUrl = `/?match=${encodeURIComponent(matchId)}${sideQuery}`;
      if (window.location.search !== `?match=${encodeURIComponent(matchId)}${sideQuery}`) {
        window.history.replaceState({}, "", nextUrl);
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
  if (
    window.location.pathname.includes("/pregame") ||
    new URLSearchParams(window.location.search).get("mode") === "pregame"
  ) {
    switchWorkspaceMode("pregame", { pushUrl: false });
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

    renderHeaderStatus();
    renderRecentMatchesStrip(data.recent_matches || state.profileData.recent_matches || []);
    renderSquadLedgerSection(state.squadLedger);
    populateSettingsDialog();
    initPregameWorkspace();

    const firstReport = data.latest_match_report || data.latest_report;
    if (urlMatchId && (!firstReport || Number(firstReport.match_id) !== Number(urlMatchId))) {
      // Shared URL with explicit ?match=<id> always loads/builds the full match report directly
      await loadMatchReport(urlMatchId, { analyzeNow: true });
    } else if (firstReport) {
      state.currentMatchId = firstReport.match_id;
      state.currentReport = firstReport;
      toggleOnDemandGate(false);
      renderFullMatchReport(state.currentReport);
      highlightSelectedMatchCard(state.currentMatchId);
      syncMatchUrlInAddressBar(state.currentMatchId);
    } else if ((data.recent_matches || []).length > 0) {
      await loadMatchReport(data.recent_matches[0].match_id);
    }

    if (urlViewReport && state.currentReport) {
      openFullscreenStructuredReport(state.currentReport);
    }
  } catch (err) {
    console.error(err);
    showToast(`读取初始数据失败: ${err.message}`);
  }
}

function bindEvents() {
  // Workspace mode switcher (Post-game Forensics vs Pre-game 5-Stack Strategy Planner)
  document.querySelectorAll("[data-ws-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const m = btn.getAttribute("data-ws-mode") || "postgame";
      switchWorkspaceMode(m, { pushUrl: true });
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
      if (state.workspaceMode !== "postgame") {
        switchWorkspaceMode("postgame", { pushUrl: true });
      }
      await handleSmartQuery(raw);
    });
  }

  const refreshBtn =
    document.getElementById("btn-Refresh-match") || document.getElementById("btn-refresh-match");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      if (!state.currentMatchId) return;
      await loadMatchReport(state.currentMatchId, { forceRefresh: true });
    });
  }

  const toggleSquadBtn = document.getElementById("btn-toggle-squad-ledger");
  if (toggleSquadBtn) {
    toggleSquadBtn.addEventListener("click", () => {
      const det = document.getElementById("squad-ledger-details");
      if (det) {
        det.open = !det.open;
      } else {
        const sec = document.getElementById("squad-ledger-section");
        if (sec) sec.classList.toggle("collapsed");
      }
    });
  }

  const latestBtn = document.getElementById("btn-load-latest");
  if (latestBtn) {
    latestBtn.addEventListener("click", async () => {
      const list = state.profileData?.recent_matches || [];
      const latestAnalyzed = list.find((m) => m.is_analyzed) || list[0];
      if (latestAnalyzed) {
        await loadMatchReport(latestAnalyzed.match_id);
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
      link.download = `dota2-verdict-${state.currentMatchId || "match"}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      showToast("已导出高清 PNG 战报长图！");
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
      localStorage.setItem(
        "dota_ledger_llm_override",
        JSON.stringify({ provider, model, apiKey, baseUrl })
      );
      renderHeaderStatus();
      showToast(`已保存模型设置 (${provider.toUpperCase()} / ${model})`);
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

function renderRecentMatchesStrip(matches) {
  const strip = document.getElementById("recent-matches-strip");
  if (!strip) return;
  if (!matches || matches.length === 0) {
    strip.innerHTML = `<div class="empty-state compact">暂无最近比赛记录</div>`;
    return;
  }

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
      const isAnalyzed = Boolean(m.is_analyzed);
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

function highlightSelectedMatchCard(matchId) {
  document.querySelectorAll("[data-match-card]").forEach((btn) => {
    const mid = Number(btn.getAttribute("data-match-card"));
    btn.classList.toggle("selected", mid === Number(matchId));
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
      "已开启「按需 AI 分析」模式（不自动分析每一局比赛）。当你确认需要复盘这局时，点击下方按钮即可拉取该局录像底层日志、运行九维战术显微镜，并生成可公开分享给群友的复盘链接。";
  }
}

async function handleSmartQuery(raw) {
  if (/^\d{9,11}$/.test(raw) && Number(raw) >= 1500000000 && Number(raw) < 76561190000000000) {
    await loadMatchReport(Number(raw));
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

async function loadMatchReport(matchId, { forceRefresh = false, analyzeNow = false } = {}) {
  if (analyzeNow || forceRefresh) {
    showToast(`🤖 AI 正在深度拆解比赛 #${matchId} 录像日志并生成分享链接...`, 4000);
  }
  try {
    const flags = `${forceRefresh ? "&refresh=1" : ""}${analyzeNow ? "&analyze=1" : ""}`;
    const url = `/api/match/${encodeURIComponent(matchId)}?account_id=${encodeURIComponent(
      state.accountId
    )}${flags}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "读取比赛失败");

    if (data.not_analyzed) {
      highlightSelectedMatchCard(matchId);
      toggleOnDemandGate(true, matchId);
      showToast(`比赛 #${matchId} 尚未分析，点击页面中央按钮即可启动 AI 深度复盘`, 3000);
      return;
    }

    toggleOnDemandGate(false);
    state.currentMatchId = data.report.match_id;
    state.currentReport = data.report;
    state.selectedTeamfightIndex = null;
    state.scrubSyncMapMinute = null;

    // Mark match as analyzed in recent_matches strip so its badge turns green immediately
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
    highlightSelectedMatchCard(state.currentMatchId);
    renderFullMatchReport(state.currentReport);
    syncMatchUrlInAddressBar(state.currentMatchId);
    if (analyzeNow) {
      showToast(`✅ 比赛 #${state.currentMatchId} AI 深度复盘已完成！点击右上角「分享本局链接」即可发群`);
    }
  } catch (err) {
    console.error(err);
    showToast(`拉取比赛 #${matchId} 失败: ${err.message}`);
  }
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
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "大模型调用失败");
    if (data.report) {
      state.currentReport = data.report;
      renderFullMatchReport(state.currentReport);
      showToast("Grok 4.7 赛后总账已更新并落盘缓存！");
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

  const metaEl = document.getElementById("match-meta-line");
  if (metaEl) {
    metaEl.textContent = `比赛编号 #${report.match_id} · ${report.start_time_str || ""} · ${
      report.mode_str || ""
    } · 当前审视阵营：${sideZh} (${side.toUpperCase()}) · ${
      report.is_parsed ? "OpenDota 录像级解析已就绪" : "基础统计模式 (可请求录像解析)"
    }`;
  }

  const parseBadge = document.getElementById("parse-quality-badge");
  if (parseBadge) {
    parseBadge.textContent = report.is_parsed
      ? "录像级解析 (含眼位/时间轴/按键次数)"
      : "未解析录像 (点击上方可请求解析)";
    parseBadge.classList.toggle("connected", Boolean(report.is_parsed));
  }

  const reqParseBtn = document.getElementById("btn-request-parse");
  if (reqParseBtn) {
    reqParseBtn.hidden = Boolean(report.is_parsed);
  }

  const titleEl = document.getElementById("match-overview-title");
  const grok = report.grok_coaching;
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
            ${escapeHtml(draft.verdict_summary || "")}
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
            ${(draft.strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
          </ul>
        </div>
        <div class="draft-sw-group bad">
          <h4>✕ 阵容隐患与短板 (容错率与被克制点)</h4>
          <ul>
            ${(draft.weaknesses || []).map((w) => `<li>${escapeHtml(w)}</li>`).join("")}
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

  const tab = state.microTab || "hero_ult";
  const blocks = [];

  if (tab === "hero_ult" || tab === "all") {
    blocks.push(renderMicroHeroExecutionPane(report, df, targetSide, targetSideZh, otherSide, otherSideZh));
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

  const cardsHtml = players
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
        .map((ins) => `<li>${escapeHtml(ins)}</li>`)
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
          <p><strong>${escapeHtml(targetSideZh)}大招与关键技能兑现：</strong>${escapeHtml(ownSummaryText)}${
    oppSummaryText
      ? `<br/><span style="color:var(--muted);">对照${escapeHtml(otherSideZh)}表现：${escapeHtml(
          oppSummaryText
        )}</span>`
      : ""
  }</p>
        </div>
      </div>
      <div class="micro-hero-exec-grid">${cardsHtml}</div>
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

  const supList = vis.per_support_vision || vis.support_breakdown || [];
  const supRowsHtml = supList
    .map(
      (s) => `
      <tr>
        <td><b>${s.pos ?? "?"}号位 · ${escapeHtml(s.hero_short_zh || "")}</b> (${escapeHtml(s.personaname || "")})</td>
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
              `<li><b>${escapeHtml(w.time_str || "")}</b> · ${escapeHtml(
                w.planter_hero || w.hero_short_zh || ""
              )} 插在 <b>${escapeHtml(w.zone_zh || "")} (${escapeHtml(
                w.coords || `${w.x ?? ""},${w.y ?? ""}`
              )})</b> 的【${escapeHtml(w.posture_zh || w.posture_label || "假眼")}】仅存活 <b>${
                w.lifespan_sec ?? 0
              } 秒</b>即被 ${escapeHtml(w.dewarded_by || "敌方")} 秒排！</li>`
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
        <td>${w.planter_pos ?? w.pos ?? "?"}号位 · ${escapeHtml(w.planter_hero || w.hero_short_zh || "")}</td>
        <td><b>${escapeHtml(w.zone_zh || "")}</b> <span style="color:var(--muted);">(${w.x ?? "?"}, ${w.y ?? "?"})</span></td>
        <td>${escapeHtml(w.posture_zh || w.posture_label || "")}</td>
        <td><b style="color:${
          isInstant ? "var(--red-light)" : wasDew ? "var(--gold-light)" : "var(--green-light)"
        }">${life} 秒</b> / 360 秒</td>
        <td>${escapeHtml(w.fate_zh || fateText)}</td>
      </tr>
    `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>👁️ 2. 辅助眼位进攻/防守倾向与存活寿命审计 (${escapeHtml(targetSideZh)})</h3>
          <p>${escapeHtml(vis.posture_verdict || "")}</p>
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
          <span>假眼被敌方排掉比例</span>
          <strong>被排 ${dewardedTotal} 颗 (${dewardedPct}%)</strong>
        </div>
        <div class="micro-kpi-cell">
          <span>秒排白给眼 (&le;90s) / 同高台死磕</span>
          <strong>${instantList.length} 颗秒排 / ${cliffList.length} 处高台</strong>
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
          <h4>🚨 秒排白给眼 (&le;90s) &amp; 同高台头铁连插抓包台</h4>
          <div>
            <strong style="font-size:12px; color:var(--gold-light);">⚡ 插下不到 90 秒即被排掉的秒排眼：</strong>
            <ul class="micro-insights-list" style="margin-top:5px;">${instantHtml}</ul>
          </div>
          <div style="margin-top:6px;">
            <strong style="font-size:12px; color:var(--gold-light);">📍 同一高台/眼位重复插眼习惯审计：</strong>
            <ul class="micro-insights-list" style="margin-top:5px;">${cliffHtml}</ul>
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
        <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
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
        <td>${sm.initiator_pos ?? sm.activator_pos ?? "?"}号位 · ${escapeHtml(
        sm.initiator_hero || sm.activator_hero || ""
      )} (${escapeHtml(sm.initiator_player || sm.activator_player || "")})</td>
        <td><b>${escapeHtml(sm.outcome_label || "")}</b></td>
        <td>${escapeHtml(sm.detail || "")}</td>
      </tr>
    `
    )
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-grid-2col">
        <div class="micro-card">
          <h4>🌾 辅助堆野屯矿 vs 大哥自拉野审计 (${escapeHtml(targetSideZh)}合计堆野 ${totalStacks} 组)</h4>
          <p style="margin:0; font-size:12.5px; color:var(--text); line-height:1.55;">${escapeHtml(
            ss.stack_verdict || ""
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
          <p style="margin:0; font-size:12.5px; color:var(--text); line-height:1.55;">${escapeHtml(
            ss.smoke_verdict || ""
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
        <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
        <td><b>${r.pull_ticks ?? r.pull_zone_samples ?? 0}</b> 次采样 (占比 ${r.pull_ratio_pct ?? r.pull_presence_pct ?? 0}%)</td>
        <td><b>${r.early_sentries ?? r.early_sentries_placed ?? 0} 颗真眼</b></td>
        <td>10m 正/反补 <b>${r.lh10 ?? 0}/${r.dn10 ?? 0} 刀</b></td>
        <td><span class="status-pill ${
          (r.status_tag || "").includes("积极") ? "connected" : ""
        }">${escapeHtml(r.status_tag || "常规保线")}</span></td>
        <td>${escapeHtml(r.comment || r.assessment || "")}</td>
      </tr>
    `
    )
    .join("");

  const mapRows = lm.map_interact_rows || [];
  const lotusPills = mapRows
    .filter((r) => (r.lotus_used ?? 0) > 0)
    .map(
      (r) =>
        `<span class="micro-exec-badge good">${r.pos}号位 · ${escapeHtml(r.hero_short_zh || "")} (${escapeHtml(
          r.personaname || ""
        )})：<b>吃莲花 ×${r.lotus_used}</b></span>`
    )
    .join("");

  const wisdomTimeline = lm.wisdom_timeline || lm.wisdom_events || [];
  const wisdomPills = wisdomTimeline
    .map(
      (w) =>
        `<span class="micro-exec-badge ${w.side === targetSide ? "good" : "warn"}"><b>${escapeHtml(
          w.time_str || ""
        )}</b> · ${escapeHtml(w.side_zh || "")} ${w.pos ?? "?"}号位 ${escapeHtml(
          w.hero_short_zh || ""
        )} (${escapeHtml(w.personaname || "")}) 摘取智慧符</span>`
    )
    .join("");

  const gatePills = mapRows
    .filter((g) => (g.twin_gate ?? 0) > 0 || (g.watcher_lamp ?? 0) > 0)
    .map(
      (g) =>
        `<span class="micro-exec-badge ${g.twin_gate > 0 ? "good" : ""}">${g.pos}号位 · ${escapeHtml(
          g.hero_short_zh || ""
        )}：<b>走门 ×${g.twin_gate ?? 0}</b> / 点灯 ×${g.watcher_lamp ?? 0} / 抢哨 ×${g.outpost_capture ?? 0}</span>`
    )
    .join("");

  const waterTimeline = lm.water_runes_timeline || lm.water_events || [];
  const waterPills = waterTimeline
    .map(
      (w) =>
        `<span class="micro-exec-badge ${w.side === targetSide ? "good" : ""}">${escapeHtml(
          w.time_str || ""
        )} · ${escapeHtml(w.side_zh || "")} ${escapeHtml(w.hero_short_zh || "")} 控水符</span>`
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
          <p>${escapeHtml(lm.lotus_verdict || "")} ｜ ${escapeHtml(lm.wisdom_verdict || "")}</p>
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
          <p style="margin:0; font-size:12px; color:var(--muted);">${escapeHtml(lm.lotus_verdict || "")}</p>
          <div class="micro-badges-wrap">${lotusPills || `<span class="micro-exec-badge">本方未记录到吃莲花事件</span>`}</div>
          ${
            waterPills
              ? `<div style="margin-top:6px;"><strong style="font-size:12px; color:var(--gold-light);">💧 2/4分钟河道水符：</strong><div class="micro-badges-wrap" style="margin-top:4px;">${waterPills}</div></div>`
              : ""
          }
        </div>

        <div class="micro-card">
          <h4>📚 智慧神符 (经验符) 时间轴 &amp; 🚪 双生门传送 (Twin Gate)</h4>
          <p style="margin:0; font-size:12px; color:var(--muted);">${escapeHtml(lm.wisdom_verdict || "")}</p>
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
        <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
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
        <td>${escapeHtml(r.verdict || "")}</td>
      </tr>
    `;
    })
    .join("");

  const tfRowsHtml = (tp.teamfight_tp_events || [])
    .map((ev) => {
      const saviors = (ev.tp_saviors || [])
        .map(
          (s) =>
            `<span class="micro-tf-pill">🟢 ${s.pos ?? "?"}号位·${escapeHtml(
              s.hero_short_zh || ""
            )} 亮TP支援 (打${fmtNum(s.damage || 0)}伤)</span>`
        )
        .join("");
      const specs = (ev.spectators || [])
        .map(
          (sp) =>
            `<span class="micro-tf-pill held-die">🔴 ${sp.pos ?? "?"}号位·${escapeHtml(
              sp.hero_short_zh || ""
            )} (${escapeHtml(sp.personaname || "")}) 0伤害0技能未亮TP旁观</span>`
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
          <p>${escapeHtml(tp.tp_verdict || "")}</p>
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
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
          <td><b>${r.tf_deaths ?? 0} 次</b></td>
          <td><b style="color:${coreCnt > 0 ? "var(--red-light)" : "var(--green-light)"}">${coreCnt} 次</b>${
        wandCnt > 0 ? ` <span style="color:var(--gold-light);">(+魔棒/刃甲未按 ${wandCnt} 次)</span>` : ""
      }</td>
          <td><b style="color:${zeroCnt > 0 ? "var(--red-light)" : "var(--green-light)"}">${zeroCnt} 次</b></td>
          <td style="font-size:11.5px;color:var(--muted);">${escapeHtml(r.owned_saves_str || "未合成主动保命装")}</td>
          <td>${escapeHtml(r.verdict || "")}</td>
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
          <b>${inc.pos ?? "?"}号位 · ${escapeHtml(inc.hero_short_zh || "")} (${escapeHtml(
              inc.personaname || ""
            )})</b>：${escapeHtml(inc.detail || "")}
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
          <p>${escapeHtml(us.side_verdict || "")}</p>
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
 * Tab 3: 🗺️ 地图空间理解与「大哥带无聊危险线 / 落单乱逛被抓死」空间取证
 */
function renderMicroMapSpacePane(report, df, targetSide, targetSideZh) {
  const ms = df.map_space_by_side?.[targetSide];
  if (!ms) {
    return `<div class="empty-state compact">当前比赛暂无地图空间理解与落单被抓数据</div>`;
  }

  const totalSolo = Number(ms.total_solo_pickoffs ?? 0);
  const events = ms.solo_pickoff_events || [];
  const pRows = ms.player_space_rows || [];

  const pRowsHtml = pRows
    .map((r) => {
      const soloCnt = Number(r.solo_pickoff_cnt ?? 0);
      const isBad = r.grade === "bad" || soloCnt >= 2;
      const isGood = r.grade === "good";
      return `
        <tr>
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
          <td><span class="micro-exec-badge ${isBad ? "warn" : isGood ? "good" : ""}">${escapeHtml(
        r.space_style_badge || "常规驻守"
      )}</span></td>
          <td>兵线 <b>${r.lane_kills ?? 0}</b> (${r.lane_farm_pct ?? 0}%) / 野区 <b>${r.neutral_kills ?? 0}</b> (${r.jungle_farm_pct ?? 0}%)</td>
          <td><b style="color:${(r.tower_damage ?? 0) >= 3500 ? "var(--gold-light)" : "var(--text)"}">${fmtNum(
        r.tower_damage || 0
      )}</b></td>
          <td><b style="color:${soloCnt >= 2 ? "var(--red-light)" : soloCnt === 0 ? "var(--green-light)" : "var(--gold-light)"}">${soloCnt} 次</b> (送 ${fmtNum(
        r.solo_gold_fed || 0
      )} 金)</td>
          <td>${escapeHtml(r.verdict || "")}</td>
        </tr>
      `;
    })
    .join("");

  const evRowsHtml = events
    .map(
      (ev) => `
      <tr>
        <td><b>${escapeHtml(ev.time_str || "")}</b></td>
        <td><b>${ev.pos ?? "?"}号位 · ${escapeHtml(ev.hero_short_zh || "")}</b> (${escapeHtml(ev.personaname || "")})</td>
        <td><b>${escapeHtml(ev.zone_zh || "")}</b> (被 ${escapeHtml(ev.killer_zh || "敌方")} 抓死)</td>
        <td>${escapeHtml(ev.vision_tag || "")}</td>
        <td>读秒 <b>${ev.time_dead ?? 0}s</b> · 送 <b>${fmtNum(ev.gold_fed || 0)} 金</b></td>
        <td><b style="color:${
          (ev.consequence || "").includes("无战略收益") ? "var(--gold-light)" : "var(--red-light)"
        }">${escapeHtml(ev.consequence || "")}</b></td>
      </tr>
    `
    )
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🗺️ 3. 地图空间理解与「大哥带无聊危险线 / 落单乱逛被抓死」空间取证 (${escapeHtml(targetSideZh)})</h3>
          <p>${escapeHtml(ms.side_verdict || "")}</p>
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
                <th>9m后落单被抓</th>
                <th>空间利用与带线纪律判词</th>
              </tr>
            </thead>
            <tbody>${pRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="micro-card">
        <h4>🚨 9 分钟后脱离团队「无聊带危险线 / 黑图盲区乱逛被抓死」全记录 (共 ${totalSolo} 次)</h4>
        <div class="micro-table-wrap">
          <table class="micro-data-table">
            <thead>
              <tr>
                <th>被抓时间</th>
                <th>落单当事人</th>
                <th>暴毙地点 &amp; 凶手</th>
                <th>当时场上假眼视野</th>
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
          <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
          <td><b>${fmtNum(r.total_dmg_taken || 0)}</b></td>
          <td>🔮 技能/法系 <b>${r.spell_pct ?? 0}%</b> (${fmtNum(r.spell_dmg || 0)})<br/>🗡️ 物理平A <b>${
        r.auto_pct ?? 0
      }%</b> (${fmtNum(r.auto_dmg || 0)})</td>
          <td><div class="micro-tf-pills">${killersStr || "平A为主"}</div></td>
          <td><div class="micro-badges-wrap">${defItemsStr}</div></td>
          <td>${escapeHtml(r.verdict || "")}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="micro-pane-block">
      <div class="micro-pane-banner">
        <div>
          <h3>🛡️ 4. 承伤来源拆解（物理平A vs 技能爆发）与防装合规审计 (${escapeHtml(targetSideZh)})</h3>
          <p>${escapeHtml(dr.side_verdict || "")}</p>
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
        <td><b>${r.pos ?? "?"}号位 · ${escapeHtml(r.hero_short_zh || "")}</b> (${escapeHtml(r.personaname || "")})</td>
        <td><span class="micro-exec-badge">${escapeHtml(r.econ_tag || "均衡发育")}</span></td>
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
          <p>${escapeHtml(ep.side_verdict || "")}</p>
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
            📋 ${escapeHtml(r.summary_txt || "")}
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
          <p>${escapeHtml(rm.side_verdict || "")}</p>
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
            <b>${ev.pos ?? "?"}号位 · ${escapeHtml(ev.hero_short_zh || "")} (${escapeHtml(
              ev.personaname || ""
            )})</b>：${escapeHtml(ev.detail || "")}
          </li>
        `
          )
          .join("")
      : `<li>✓ 本局 ${escapeHtml(targetSideZh)} 未交出买活，0 次买活死 (Dieback) 记录。</li>`;

  const roshEvents = mo.roshan_events || [];
  const roshHtml =
    roshEvents.length > 0
      ? roshEvents.map((r) => `<li>${escapeHtml(r)}</li>`).join("")
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
            ${escapeHtml(ce.detail || "")}
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
          <td><b>${cr.pos ?? "?"}号位 · ${escapeHtml(cr.hero_short_zh || "")}</b> (${escapeHtml(
        cr.personaname || ""
      )})</td>
          <td><b>${escapeHtml(cr.shard_str || "未获魔晶")}</b></td>
          <td>${stepsPills}</td>
          <td style="color:${
            cr.grade === "warn" ? "var(--gold-light)" : "var(--green-light)"
          }">${escapeHtml(cr.craft_verdict || "")}</td>
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
          <p>${escapeHtml(mo.side_verdict || "")}</p>
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
 * 2. Render Grok 4.7 Verdict Banner + MVP Card + Culprit Card + 5-Stack Blame Ledger
 */
function renderVerdictAndBlameSection(report) {
  const { side, sideZh, own, all } = getOwnAndOppPlayers(report);
  const bySlot = new Map(all.map((p) => [Number(p.player_slot), p]));
  const won =
    (side === "radiant" && Boolean(report.radiant_win)) ||
    (side === "dire" && !report.radiant_win);

  const grok = report.grok_coaching;
  const mvpData = report.mvp || {};

  // Update Jump Chip, Section Heading, Card Labels, and Ledger Header dynamically based on WIN vs LOSS
  const jumpChip = document.getElementById("jump-chip-verdict");
  const secHeading = document.getElementById("verdict-heading");
  const secCaption = document.getElementById("verdict-caption");
  const mvpCardLabel = document.getElementById("mvp-card-label");
  const secondCardEl = document.getElementById("culprit-card");
  const secondCardLabel = document.getElementById("culprit-card-label");
  const ledgerTitle = document.getElementById("blame-ledger-title");
  const ledgerCaption = document.getElementById("blame-ledger-caption");
  const shareBtn1 = document.getElementById("btn-open-share-poster");
  const shareBtn2 = document.getElementById("btn-open-share-poster-2");

  if (won) {
    if (jumpChip) jumpChip.textContent = "② 🏆 凯旋庆功与100%贡献榜";
    if (secHeading) {
      secHeading.textContent = `② 🏆 ${sideZh}凯旋庆功封神榜 · 谁是头号首功 & 100% 胜局贡献排座次`;
    }
    if (secCaption) {
      secCaption.textContent =
        "赢球不背锅，全员论功行赏！结合英雄输出转化、推塔终结、团战控制与视野节奏核算五人 100% 胜局贡献度";
    }
    if (mvpCardLabel) mvpCardLabel.textContent = "👑 头号首功 · 本局擎天真大腿 (MVP)";
    if (secondCardEl) {
      secondCardEl.classList.remove("culprit-theme");
      secondCardEl.classList.add("runnerup-theme");
    }
    if (secondCardLabel) secondCardLabel.textContent = "⚔️ 二号功臣 · 破阵二当家 & 定海神针";
    if (ledgerTitle) ledgerTitle.textContent = `🎉 ${sideZh}五黑 100% 胜局贡献庆功榜 · 谁的军功章最大一目了然`;
    if (ledgerCaption) {
      ledgerCaption.textContent =
        "按本局五人综合战功归一化为 100% 胜局贡献度，点击任意行右侧按钮可直接复制夸人/庆功贺电发群里";
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
        "输球不留情面，硬核数据定责！一屏看清全场真大腿、败方孤胆院长、头号战犯与 100% 责任切分";
    }
    if (mvpCardLabel) mvpCardLabel.textContent = "👑 全场头号功臣 · MVP / 败方孤胆院长";
    if (secondCardEl) {
      secondCardEl.classList.remove("runnerup-theme");
      secondCardEl.classList.add("culprit-theme");
    }
    if (secondCardLabel) secondCardLabel.textContent = "🚨 本方头号大锅 · 一级战犯逮捕令";
    if (ledgerTitle) ledgerTitle.textContent = `⚖️ ${sideZh}五人 100% 败局分锅账本 · 谁该在群里发致歉红包`;
    if (ledgerCaption) {
      ledgerCaption.textContent =
        "点击任意行右侧按钮可直接复制该队友专属分锅算账金句发群里";
    }
    if (shareBtn1) shareBtn1.textContent = "📜 导出群聊处刑书";
    if (shareBtn2) shareBtn2.textContent = "📜 导出群聊处刑书";
  }

  // Sort own team by Contribution Share (descending) and by Blame Share (descending)
  const rawContribSum =
    own.reduce((s, p) => s + Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)), 0) || 100;
  const sortedByContrib = [...own]
    .map((p) => ({
      player: p,
      contribShare: Number(
        (
          (Math.max(1, Number(p.contrib_share_pct ?? p.mvp_score ?? 20)) / rawContribSum) *
          100
        ).toFixed(1)
      ),
    }))
    .sort(
      (a, b) =>
        b.contribShare - a.contribShare ||
        (b.player.rating_score || 0) - (a.player.rating_score || 0)
    );

  const rawBlameSum =
    own.reduce((s, p) => s + Math.max(1, Number(p.blame_share_pct || 20)), 0) || 100;
  const sortedByBlame = [...own]
    .map((p) => ({
      player: p,
      blameShare: Number(((Math.max(1, Number(p.blame_share_pct || 20)) / rawBlameSum) * 100).toFixed(1)),
    }))
    .sort((a, b) => b.blameShare - a.blameShare);

  // 2.1 Grok Verdict Banner (Structured 2x2 Stage Cards + Scannable Verdict Highlights)
  const authorEl = document.getElementById("grok-author-label");
  const titleEl = document.getElementById("grok-title-text");
  const summaryEl = document.getElementById("grok-summary-text");
  const verdictEl = document.getElementById("grok-verdict-text");
  const practiceEl = document.getElementById("grok-team-practice-box");
  const stages = report.match_narrative?.stages || [];

  const formatStageContentToBullets = (rawContent) => {
    const cleaned = sanitizeMixedEnglishClient(String(rawContent || ""))
      .replace(/三路10分钟对账：/g, "。")
      .replace(/主视角（[^）]+）车队全局数据对比：/g, "。");
    const parts = cleaned
      .split(/[；。]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    return parts
      .map((item) => {
        let html = escapeHtml(item);
        // Highlight key prefixes like 上路 / 中路 / 下路 / ① 控制时长 / ② 视野与开雾 / ③ 建筑伤害 / ④ 全队泉水读秒总时长
        html = html.replace(
          /^(上路|中路|下路|①\s*[^：:]+|②\s*[^：:]+|③\s*[^：:]+|④\s*[^：:]+|10分钟对线期结束|对线与前中期信使击杀|全场最高权重胜负手团战爆发于|肉山争夺记录)([：:\s]*)/,
          '<span class="stage-key-pill">$1</span> '
        );
        // Highlight lane or battle outcomes after →
        html = html.replace(
          /→\s*([^；。]+)/g,
          '<span class="stage-outcome-pill">→ $1</span>'
        );
        return `<li>${html}</li>`;
      })
      .join("");
  };

  const stageIcons = ["🌅", "⚔️", "🔥", "📊"];
  const stagesGridHtml =
    stages.length > 0
      ? `<div class="verdict-stages-grid">
          ${stages
            .map((s, idx) => {
              const stTitle = s.stage || s.title || `阶段 ${idx + 1}`;
              const stBody = s.summary || s.content || "";
              const icon = stageIcons[idx % stageIcons.length];
              return `
                <div class="verdict-stage-card">
                  <div class="verdict-stage-head">
                    <span class="verdict-stage-badge">${icon} 阶段 ${idx + 1}</span>
                    <strong class="verdict-stage-title">${escapeHtml(stTitle)}</strong>
                  </div>
                  <ul class="verdict-stage-bullets">
                    ${formatStageContentToBullets(stBody)}
                  </ul>
                </div>
              `;
            })
            .join("")}
        </div>`
      : "";

  const top1 = sortedByContrib[0]?.player;
  const top2 = sortedByContrib[1]?.player;
  const lucky5 = sortedByContrib[sortedByContrib.length - 1]?.player;
  const topBlame1 = sortedByBlame[0]?.player;
  const topBlame2 = sortedByBlame[1]?.player;

  const buildStructuredVerdictHtml = (extraText = "") => {
    const extraClean = sanitizeMixedEnglishClient(String(extraText || "")).trim();
    const extraBullets = extraClean
      ? extraClean
          .split(/(?<=[。！？!?])\s*/)
          .map((x) => x.trim())
          .filter(Boolean)
      : [];

    if (won) {
      return `
        <div class="verdict-highlight-grid">
          <div class="verdict-hl-item gold">
            <span class="verdict-hl-tag">👑 头号首功 MVP</span>
            <div class="verdict-hl-main">
              ${top1?.hero_img ? `<img src="${escapeHtml(top1.hero_img)}" width="32" height="18" alt="" />` : ""}
              <strong>${top1?.pos ?? 1}号位 ${escapeHtml(top1?.hero_short_zh || "")}</strong>
              <span class="verdict-hl-player">(${escapeHtml(top1?.personaname || "")})</span>
            </div>
            <span class="verdict-hl-metric">胜局贡献 <b>${sortedByContrib[0]?.contribShare ?? 25}%</b> · 评分 <b>${top1?.rating_score ?? 8.5}</b></span>
          </div>
          <div class="verdict-hl-item green">
            <span class="verdict-hl-tag">⚔️ 破阵二当家</span>
            <div class="verdict-hl-main">
              ${top2?.hero_img ? `<img src="${escapeHtml(top2.hero_img)}" width="32" height="18" alt="" />` : ""}
              <strong>${top2?.pos ?? 2}号位 ${escapeHtml(top2?.hero_short_zh || "")}</strong>
              <span class="verdict-hl-player">(${escapeHtml(top2?.personaname || "")})</span>
            </div>
            <span class="verdict-hl-metric">胜局贡献 <b>${sortedByContrib[1]?.contribShare ?? 22}%</b> · 评分 <b>${top2?.rating_score ?? 8.0}</b></span>
          </div>
          <div class="verdict-hl-item muted">
            <span class="verdict-hl-tag">🐟 惊险躺赢锦鲤</span>
            <div class="verdict-hl-main">
              ${lucky5?.hero_img ? `<img src="${escapeHtml(lucky5.hero_img)}" width="32" height="18" alt="" />` : ""}
              <strong>${lucky5?.pos ?? 5}号位 ${escapeHtml(lucky5?.hero_short_zh || "")}</strong>
              <span class="verdict-hl-player">(${escapeHtml(lucky5?.personaname || "")})</span>
            </div>
            <span class="verdict-hl-metric">胜局贡献 <b>${sortedByContrib[sortedByContrib.length - 1]?.contribShare ?? 12}%</b> · 评分 <b>${lucky5?.rating_score ?? 6.5}</b></span>
          </div>
        </div>
        ${
          extraBullets.length > 0
            ? `<ul class="verdict-rationale-list">${extraBullets
                .map((b) => `<li>${escapeHtml(b)}</li>`)
                .join("")}</ul>`
            : ""
        }
      `;
    }

    const rationales =
      extraBullets.length > 0
        ? extraBullets
        : (mvpData.rationale_list || []).map((r) => sanitizeMixedEnglishClient(r));
    return `
      <div class="verdict-highlight-grid">
        <div class="verdict-hl-item crimson">
          <span class="verdict-hl-tag">🚨 本局首锅战犯</span>
          <div class="verdict-hl-main">
            ${topBlame1?.hero_img ? `<img src="${escapeHtml(topBlame1.hero_img)}" width="32" height="18" alt="" />` : ""}
            <strong>${topBlame1?.pos ?? 1}号位 ${escapeHtml(topBlame1?.hero_short_zh || "")}</strong>
            <span class="verdict-hl-player">(${escapeHtml(topBlame1?.personaname || "")})</span>
          </div>
          <span class="verdict-hl-metric">分锅占比 <b>${sortedByBlame[0]?.blameShare ?? 30}%</b> · 评分 <b>${topBlame1?.rating_score ?? 5.0}</b></span>
        </div>
        <div class="verdict-hl-item warn">
          <span class="verdict-hl-tag">⚠️ 次锅背锅位</span>
          <div class="verdict-hl-main">
            ${topBlame2?.hero_img ? `<img src="${escapeHtml(topBlame2.hero_img)}" width="32" height="18" alt="" />` : ""}
            <strong>${topBlame2?.pos ?? 2}号位 ${escapeHtml(topBlame2?.hero_short_zh || "")}</strong>
            <span class="verdict-hl-player">(${escapeHtml(topBlame2?.personaname || "")})</span>
          </div>
          <span class="verdict-hl-metric">分锅占比 <b>${sortedByBlame[1]?.blameShare ?? 24}%</b> · 评分 <b>${topBlame2?.rating_score ?? 5.5}</b></span>
        </div>
        <div class="verdict-hl-item green">
          <span class="verdict-hl-tag">🛡️ 本方尽力大腿</span>
          <div class="verdict-hl-main">
            ${top1?.hero_img ? `<img src="${escapeHtml(top1.hero_img)}" width="32" height="18" alt="" />` : ""}
            <strong>${top1?.pos ?? 1}号位 ${escapeHtml(top1?.hero_short_zh || "")}</strong>
            <span class="verdict-hl-player">(${escapeHtml(top1?.personaname || "")})</span>
          </div>
          <span class="verdict-hl-metric">仅分锅 <b>${
            sortedByBlame[sortedByBlame.length - 1]?.blameShare ?? 10
          }%</b> · 评分 <b>${top1?.rating_score ?? 7.5}</b></span>
        </div>
      </div>
      ${
        rationales.length > 0
          ? `<ul class="verdict-rationale-list">${rationales
              .map((r) => `<li>${escapeHtml(r)}</li>`)
              .join("")}</ul>`
          : ""
      }
    `;
  };

  if (grok && (!grok.side || grok.side === side)) {
    const modelTag = grok._meta?.model
      ? `${String(grok._meta.provider || "XAI").toUpperCase()} / ${grok._meta.model} ${won ? "赛后庆功与复盘总账" : "赛后分锅总账"}`
      : `XAI / GROK-4.7 ${won ? "赛后庆功与复盘总账" : "赛后分锅总账"}`;
    if (authorEl) authorEl.textContent = modelTag;
    if (titleEl) titleEl.textContent = sanitizeMixedEnglishClient(grok.title || (won ? "凯旋庆功与战术复盘" : "本局赛后复盘总账"));
    if (summaryEl) {
      const leadSummary = grok.summary
        ? `<div class="verdict-lead-callout">${escapeHtml(grok.summary)}</div>`
        : "";
      summaryEl.innerHTML = `${leadSummary}${stagesGridHtml}`;
    }
    if (verdictEl) {
      verdictEl.innerHTML = buildStructuredVerdictHtml(grok.verdict || "");
    }
    if (practiceEl) {
      practiceEl.innerHTML = grok.team_practice
        ? `<strong>${won ? "乘胜追击 · 下把更稳铁律：" : "痛定思痛 · 下把车队铁律："}</strong>${escapeHtml(grok.team_practice)}`
        : "";
      practiceEl.hidden = !grok.team_practice;
    }
  } else {
    if (authorEl) {
      authorEl.textContent = won
        ? "录像级庆功引擎 · 四阶段对账与论功行赏 (可点右上角用 Grok 4.7 深度重算)"
        : "录像级算账引擎 · 四阶段对账与分锅判词 (可点右上角用 Grok 4.7 深度重算)";
    }
    if (titleEl) {
      titleEl.textContent = won
        ? `🎉 ${sideZh}凯旋大捷！终局比分 ${report.radiant_score} : ${report.dire_score} (${report.duration_str})`
        : `⚖️ ${sideZh}败局算账：终局比分 ${report.radiant_score} : ${report.dire_score} (${report.duration_str})`;
    }
    if (summaryEl) {
      summaryEl.innerHTML = stagesGridHtml;
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

  // 2.2 Left Card: When WON -> #1 Top Contributor on our winning team; When LOST -> Match MVP / Our SVP
  const mvpBody = document.getElementById("mvp-card-body");
  let mvpPlayer = won ? sortedByContrib[0]?.player : mvpData.mvp_player || all[0];
  const grokMvp = grok?.mvp && (!grok.side || grok.side === side) ? grok.mvp : null;
  if (!won && grokMvp && bySlot.has(Number(grokMvp.slot))) {
    mvpPlayer = bySlot.get(Number(grokMvp.slot));
  } else if (mvpPlayer && bySlot.has(Number(mvpPlayer.player_slot))) {
    mvpPlayer = bySlot.get(Number(mvpPlayer.player_slot));
  }
  const mvpContribPct =
    sortedByContrib.find((x) => Number(x.player.player_slot) === Number(mvpPlayer?.player_slot))
      ?.contribShare ??
    mvpPlayer?.contrib_share_pct ??
    26.0;

  if (mvpBody && mvpPlayer) {
    const heroShort = mvpPlayer.hero_short_zh || mvpPlayer.hero_name;
    const grokMvpPlayer = (grok?.players || []).find(
      (gp) => Number(gp.slot) === Number(mvpPlayer.player_slot)
    );
    const evidences = [];
    if (Array.isArray(mvpPlayer.strengths)) {
      mvpPlayer.strengths.slice(0, 3).forEach((r) => evidences.push(r));
    }
    if (Array.isArray(grokMvpPlayer?.good)) {
      grokMvpPlayer.good.slice(0, 2).forEach((g) => {
        if (!evidences.includes(g)) evidences.push(g);
      });
    }
    if (evidences.length === 0 && grokMvp?.reason) evidences.push(grokMvp.reason);
    if (evidences.length === 0 && Array.isArray(mvpData.rationale_list)) {
      mvpData.rationale_list.slice(0, 3).forEach((r) => evidences.push(r));
    }

    const mvpCopyText = won
      ? `🏆【凯旋头号首功 MVP】${mvpPlayer.personaname} (${heroShort} · ${mvpPlayer.pos_label})：独占全队 ${mvpContribPct}% 胜局贡献！KDA ${mvpPlayer.kda}，GPM ${mvpPlayer.gpm}，英雄伤害 ${fmtNum(mvpPlayer.hero_damage)}，推塔 ${fmtNum(mvpPlayer.tower_damage)}。${mvpPlayer.praise_talk || evidences[0] || ""}`
      : `【本局大腿 MVP】${mvpPlayer.personaname} (${heroShort} · ${mvpPlayer.pos_label})：KDA ${mvpPlayer.kda}，GPM ${mvpPlayer.gpm}，英雄伤害 ${fmtNum(mvpPlayer.hero_damage)}。${evidences[0] || ""}`;

    mvpBody.innerHTML = `
      <div class="verdict-hero-row">
        ${
          mvpPlayer.hero_img
            ? `<img class="verdict-portrait" src="${escapeHtml(mvpPlayer.hero_img)}" alt="${escapeHtml(heroShort)}" />`
            : ""
        }
        <div class="verdict-identity">
          <div class="verdict-title-line">
            <span class="verdict-hero-name">${escapeHtml(heroShort)}</span>
            <span class="verdict-player-name">${escapeHtml(mvpPlayer.personaname)}${mvpPlayer.is_me ? " [我]" : ""}</span>
            <span class="status-pill connected">${escapeHtml(mvpPlayer.pos_label)} · ${escapeHtml(
      won ? mvpPlayer.contrib_tier || "👑 头号首功" : mvpPlayer.rating_tier || "全场真大腿"
    )}</span>
          </div>
          <div class="verdict-sub-meta">
            KDA ${escapeHtml(mvpPlayer.kda)} (${mvpPlayer.kill_participation_pct}% 参战) · GPM ${mvpPlayer.gpm} · 伤害 ${fmtNum(mvpPlayer.hero_damage)} (${mvpPlayer.hero_damage_share_pct || 0}%) · 拆塔 ${fmtNum(mvpPlayer.tower_damage)}
          </div>
        </div>
        <div class="verdict-score-box">
          <div class="verdict-score-num">${
            won
              ? `${Number(mvpContribPct).toFixed(1)}%`
              : Number(mvpPlayer.mvp_score || mvpPlayer.rating_score || 85).toFixed(1)
          }</div>
          <div class="verdict-score-sub">${
            won ? `胜局贡献度 (评分 ${mvpPlayer.rating_score})` : "MVP 战功分"
          }</div>
        </div>
      </div>
      <ul class="verdict-evidence-list">
        ${evidences
          .slice(0, 4)
          .map((item) => `<li>${escapeHtml(item)}</li>`)
          .join("")}
      </ul>
      <div class="verdict-quote-bar">
        <span>${escapeHtml(
          won
            ? mvpPlayer.praise_talk ||
                `「${heroShort} 这把真神降临包揽 ${mvpContribPct}% 胜局贡献，今晚车队全员排队敬茶！」`
            : `「这把要不是 ${heroShort} 死命顶着局势，早就提前十五分钟敲 GG 了。」`
        )}</span>
        <button type="button" class="button secondary" data-copy-quote="${escapeHtml(mvpCopyText)}">${
      won ? "复制首功贺电" : "复制表彰词"
    }</button>
      </div>
    `;
  }

  // 2.3 Right Card:
  // - When WON: Show #2 Contributor ("⚔️ 二号功臣 · 破阵二当家") + fun shoutout to the 5th contributor ("🎉 躺赢锦鲤")!
  // - When LOST: Show #1 Blame Culprit ("🚨 本方头号大锅 · 一级战犯逮捕令")!
  const culpritBody = document.getElementById("culprit-card-body");
  if (culpritBody) {
    if (won) {
      const runnerEntry = sortedByContrib[1] || sortedByContrib[0];
      const runner = runnerEntry?.player || own[0];
      const runnerShare = runnerEntry?.contribShare ?? runner?.contrib_share_pct ?? 22.0;
      const luckyEntry = sortedByContrib[sortedByContrib.length - 1];
      const luckyPlayer = luckyEntry?.player;
      const grokRunner = (grok?.players || []).find(
        (gp) => Number(gp.slot) === Number(runner?.player_slot)
      );

      const heroShort = runner.hero_short_zh || runner.hero_name;
      const highlights = [];
      if (Array.isArray(runner.strengths)) {
        runner.strengths.slice(0, 3).forEach((s) => highlights.push(s));
      }
      if (Array.isArray(grokRunner?.good)) {
        grokRunner.good.slice(0, 2).forEach((g) => {
          if (!highlights.includes(g)) highlights.push(g);
        });
      }
      if (luckyPlayer && Number(luckyPlayer.player_slot) !== Number(runner.player_slot)) {
        highlights.push(
          `🎉 本局气氛组/躺赢锦鲤提名：${luckyPlayer.pos}号位 ${luckyPlayer.hero_short_zh} (${luckyPlayer.personaname}) — 贡献 ${luckyEntry.contribShare}%（KDA ${luckyPlayer.kda}），成功吸引敌方火力，赢球全员免锅！`
        );
      }

      const runnerCopyText = `⚔️【凯旋二号功臣】${runner.personaname} (${heroShort} · ${runner.pos_label}) 本局胜局贡献 ${runnerShare}%（综合评分 ${runner.rating_score}）！KDA ${runner.kda}，参战率 ${runner.kill_participation_pct}%，英雄伤害 ${fmtNum(runner.hero_damage)}。${
        runner.praise_talk || highlights[0] || ""
      }`;

      culpritBody.innerHTML = `
        <div class="verdict-hero-row">
          ${
            runner.hero_img
              ? `<img class="verdict-portrait" src="${escapeHtml(runner.hero_img)}" alt="${escapeHtml(heroShort)}" />`
              : ""
          }
          <div class="verdict-identity">
            <div class="verdict-title-line">
              <span class="verdict-hero-name">${escapeHtml(heroShort)}</span>
              <span class="verdict-player-name">${escapeHtml(runner.personaname)}${runner.is_me ? " [我]" : ""}</span>
              <span class="status-pill connected">${escapeHtml(runner.pos_label)} · ${escapeHtml(
        runner.contrib_tier || "⚔️ 破阵二当家"
      )}</span>
            </div>
            <div class="verdict-sub-meta">
              KDA ${escapeHtml(runner.kda)} · 参战率 ${runner.kill_participation_pct}% · 伤害 ${fmtNum(runner.hero_damage)} (${runner.hero_damage_share_pct || 0}%) · 控制 ${runner.stuns_sec || 0}秒
            </div>
          </div>
          <div class="verdict-score-box">
            <div class="verdict-score-num">${Number(runnerShare).toFixed(1)}%</div>
            <div class="verdict-score-sub">胜局贡献度 (评分 ${runner.rating_score})</div>
          </div>
        </div>
        <ul class="verdict-evidence-list">
          ${highlights
            .slice(0, 4)
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join("")}
        </ul>
        <div class="verdict-quote-bar">
          <span>${escapeHtml(
            runner.praise_talk || `「左膀右臂定海神针！这把赢下来必须记 ${heroShort} 半座军功章！」`
          )}</span>
          <button type="button" class="button secondary" data-copy-quote="${escapeHtml(runnerCopyText)}">复制庆功词</button>
        </div>
      `;
    } else {
      const culpritEntry = sortedByBlame[0];
      const culprit = culpritEntry?.player || own[0];
      const culpritShare = culpritEntry?.blameShare ?? culprit?.blame_share_pct ?? 25.0;
      const grokCulprit = (grok?.players || []).find(
        (gp) => Number(gp.slot) === Number(culprit?.player_slot)
      );
      const heroShort = culprit.hero_short_zh || culprit.hero_name;
      const crimes = [];
      if (grokCulprit?.assessment) crimes.push(grokCulprit.assessment);
      if (Array.isArray(grokCulprit?.bad)) {
        grokCulprit.bad.forEach((b) => crimes.push(b));
      }
      if (crimes.length === 0 && Array.isArray(culprit.weaknesses)) {
        culprit.weaknesses.forEach((b) => crimes.push(b));
      }

      const culpritCopyText = `【头号战犯逮捕令】${culprit.personaname} (${heroShort} · ${culprit.pos_label}) 本局分锅占比 ${culpritShare}%！KDA ${culprit.kda}，泉水读秒 ${culprit.dead_seconds || 0} 秒。${
        culprit.trash_talk || crimes[0] || ""
      }`;

      culpritBody.innerHTML = `
        <div class="verdict-hero-row">
          ${
            culprit.hero_img
              ? `<img class="verdict-portrait" src="${escapeHtml(culprit.hero_img)}" alt="${escapeHtml(heroShort)}" />`
              : ""
          }
          <div class="verdict-identity">
            <div class="verdict-title-line">
              <span class="verdict-hero-name">${escapeHtml(heroShort)}</span>
              <span class="verdict-player-name">${escapeHtml(culprit.personaname)}${culprit.is_me ? " [我]" : ""}</span>
              <span class="status-pill">${escapeHtml(culprit.pos_label)} · ${escapeHtml(culprit.rating_tier || "头号大锅")}</span>
            </div>
            <div class="verdict-sub-meta">
              KDA ${escapeHtml(culprit.kda)} · 参战率 ${culprit.kill_participation_pct}% · 泉水读秒 ${culprit.dead_seconds || 0}秒 · 阵亡掉钱 ${fmtNum(culprit.death_gold_lost || 0)}
            </div>
          </div>
          <div class="verdict-score-box">
            <div class="verdict-score-num">${Number(culpritShare).toFixed(1)}%</div>
            <div class="verdict-score-sub">全队分锅占比</div>
          </div>
        </div>
        <ul class="verdict-evidence-list">
          ${crimes
            .slice(0, 4)
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join("")}
        </ul>
        <div class="verdict-quote-bar">
          <span>${escapeHtml(grokCulprit?.headline || culprit.trash_talk || "这把大锅请稳稳背好，群里发个红包不过分吧？")}</span>
          <button type="button" class="button primary" data-copy-quote="${escapeHtml(culpritCopyText)}">复制处刑词</button>
        </div>
      `;
    }
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
        let innerLabel = "";
        if (share >= 15) {
          innerLabel = `${escapeHtml(heroShort)} ${share}%`;
        } else if (share >= 9) {
          innerLabel = `${share}%`;
        }
        const tooltip = won
          ? `${p.pos_label} ${heroShort} (${p.personaname}): 胜局贡献度 ${share}%`
          : `${p.pos_label} ${heroShort} (${p.personaname}): 败局分锅占比 ${share}%`;
        return `
          <div
            class="blame-seg rank-${idx}"
            style="--share: ${Math.max(share, 2.5)}"
            title="${escapeHtml(tooltip)}"
          >${innerLabel}</div>
        `;
      })
      .join("");

    const rankMedals = ["🥇", "🥈", "🥉", "04", "05"];
    rankingRows.innerHTML = listToDisplay
      .map(({ player: p, share }, idx) => {
        const heroShort = p.hero_short_zh || p.hero_name;
        const grokP = (grok?.players || []).find((gp) => Number(gp.slot) === Number(p.player_slot));

        if (won) {
          const oneLinePraise =
            (grokP?.good && grokP.good[0]) ||
            (p.strengths && p.strengths[0]) ||
            p.praise_talk ||
            "稳健发挥助力团队拿下一城";
          const tierTag =
            idx === 0
              ? "👑 头号首功"
              : idx === 1
              ? "⚔️ 破阵次功"
              : idx === 4 && (p.deaths || 0) >= 8
              ? "🎉 躺赢锦鲤"
              : "🔥 凯旋功臣";
          const copyQuote = `🏆【凯旋庆功榜 #${idx + 1} · ${tierTag}】${p.personaname} (${heroShort} · ${p.pos_label}) 胜局贡献 ${share}% (评分 ${p.rating_score})：KDA ${p.kda}，${oneLinePraise}`;
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
                </div>
                <div class="blame-row-sub">
                  ${escapeHtml(p.pos_label)} · KDA ${escapeHtml(p.kda)} (${p.kill_participation_pct}%参战) · ${extraStat}
                </div>
              </div>
              <div class="blame-row-bar-wrap">
                <div class="blame-row-bar-track">
                  <div class="blame-row-bar-fill" style="--bar-w: ${Math.min(100, Math.max(4, share))}%"></div>
                </div>
                <div class="blame-row-quote" title="${escapeHtml(oneLinePraise)}">${escapeHtml(oneLinePraise)}</div>
              </div>
              <span class="blame-badge">${tierTag} · 贡献 ${share.toFixed(1)}%</span>
              <button type="button" class="button secondary" data-copy-quote="${escapeHtml(copyQuote)}">复制贺电</button>
            </div>
          `;
        } else {
          const oneLineCrime =
            grokP?.headline ||
            (p.weaknesses && p.weaknesses[0]) ||
            p.trash_talk ||
            "本局表现中规中矩";
          const copyQuote = `【分锅账单 #${idx + 1}】${p.personaname} (${heroShort} · ${p.pos_label}) 背锅占比 ${share}%：KDA ${p.kda}，${oneLineCrime}`;

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
                </div>
                <div class="blame-row-sub">
                  ${escapeHtml(p.pos_label)} · KDA ${escapeHtml(p.kda)} · 参战 ${p.kill_participation_pct}% · 读秒 ${p.dead_seconds || 0}s
                </div>
              </div>
              <div class="blame-row-bar-wrap">
                <div class="blame-row-bar-track">
                  <div class="blame-row-bar-fill" style="--bar-w: ${Math.min(100, Math.max(4, share))}%"></div>
                </div>
                <div class="blame-row-quote" title="${escapeHtml(oneLineCrime)}">${escapeHtml(oneLineCrime)}</div>
              </div>
              <span class="blame-badge">背锅 ${share.toFixed(1)}%</span>
              <button type="button" class="button secondary" data-copy-quote="${escapeHtml(copyQuote)}">复制算账</button>
            </div>
          `;
        }
      })
      .join("");
  }

  document.querySelectorAll(".verdict-and-blame-section [data-copy-quote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      copyTextToClipboard(btn.getAttribute("data-copy-quote") || "", won ? "庆功贺电" : "处刑判词");
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

  // Render 3-Stage Team Progression Roadmap (前期能做什么 / 中期能做什么 / 后期能做什么)
  if (roadmapBox) {
    const stageTitles = {
      lane: "前期团队能做什么 (00:00–10:00 对线与抢符)",
      mid: "中期团队能做什么 (10:00–25:00 抱团与控图)",
      late: "后期团队能做什么 (25:00–终局 盾奶与上高)",
    };
    roadmapBox.innerHTML = phasesList
      .map((pd) => {
        const isCurrent = pd.key === state.activePhaseKey;
        const diag = pd.team_diagnostics?.[side] || {};
        const actionList = toBulletList(diag.team_action, "围绕强势期抱团推进");
        const badList = toBulletList(diag.team_bad, "节奏脱节");
        return `
          <div
            class="roadmap-stage-card ${isCurrent ? "active-stage" : ""}"
            data-roadmap-stage="${escapeHtml(pd.key)}"
            style="cursor: pointer;"
            title="点击切换到 ${escapeHtml(pd.label)} 详细算账"
          >
            <div class="roadmap-stage-head">
              <span class="roadmap-stage-title">${escapeHtml(stageTitles[pd.key] || pd.label)}</span>
              <span class="roadmap-stage-badge">${escapeHtml(pd.time_label)}</span>
            </div>
            <div style="font-size: 11px; color: var(--red-light); line-height: 1.45;">
              <strong>本局病灶：</strong>${escapeHtml(badList[0] || "节奏脱节")}
            </div>
            <ul class="roadmap-stage-list">
              ${actionList.map((act) => `<li>${escapeHtml(act)}</li>`).join("")}
            </ul>
          </div>
        `;
      })
      .join("");

    roadmapBox.querySelectorAll("[data-roadmap-stage]").forEach((card) => {
      card.addEventListener("click", () => {
        state.activePhaseKey = card.getAttribute("data-roadmap-stage") || "lane";
        renderPhaseSection(report);
      });
    });
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
      renderPhaseSection(report);
    });
  });

  const activePd = byKey.get(state.activePhaseKey) || phasesList[0];
  const grokPhase = grokPhasesMap.get(state.activePhaseKey) || null;
  const sideDiag = activePd.team_diagnostics?.[side] || {};

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
  const mostDeathsPlayer = [...phasePlayers].sort((a, b) => (b.deaths_count || 0) - (a.deaths_count || 0))[0];
  const fallbackSummary = `在 ${activePd.label} (${activePd.time_label}) 阶段，${sideZh}打出 ${ownKills} : ${oppKills} 的人头交换，阶段经济差变动 ${fmtSigned(
    deltaAdvOwn
  )} 金，阶段末累计经济差为 ${fmtSigned(endAdvOwn)} 金。${
    topGoldPlayer
      ? `本阶段刷钱最快的是 ${topGoldPlayer.hero_short_zh} (+${fmtNum(topGoldPlayer.gold_gain)} 金，造成 ${fmtNum(
          topGoldPlayer.hero_damage_gain
        )} 点英雄伤害)`
      : ""
  }${
    mostDeathsPlayer && mostDeathsPlayer.deaths_count > 0
      ? `；而 ${mostDeathsPlayer.hero_short_zh} 在该阶段阵亡 ${mostDeathsPlayer.deaths_count} 次 (${(
          mostDeathsPlayer.deaths_events || []
        )
          .map((d) => d.time_str)
          .join(" / ")})，是这一阶段最需要复盘的出血点。`
      : "。"
  }`;

  const summaryText = grokPhase?.summary || sideDiag.summary || fallbackSummary;
  const turningText = grokPhase?.turning_point || sideDiag.turning_point || "";
  const goodBullets = toBulletList(sideDiag.team_good, "核心保持基础发育");
  const badBullets = toBulletList(sideDiag.team_bad, "联动配合不够紧密");
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

    <div class="phase-narrative-box">
      <p>${escapeHtml(summaryText)}</p>
      ${
        turningText
          ? `<div class="phase-turning-bar"><strong>阶段胜负拐点：</strong>${escapeHtml(turningText)}</div>`
          : ""
      }
    </div>

    <div class="phase-team-diag-grid">
      <div class="phase-team-diag-card good">
        <h4>✓ 本阶段全队哪里做得好 (${escapeHtml(activePd.label)})</h4>
        <ul>
          ${goodBullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </div>
      <div class="phase-team-diag-card bad">
        <h4>✕ 本阶段全队哪里做得不好 (复盘扣分项)</h4>
        <ul>
          ${badBullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </div>
      <div class="phase-team-diag-card action">
        <h4>→ 团队在${escapeHtml(activePd.label)}应该怎么做 (进步指南)</h4>
        <ul>
          ${actionBullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </div>
    </div>

    <div class="phase-players-grid">
      ${phasePlayers
        .map((pp) => {
          const goodItems = Array.isArray(pp.good) && pp.good.length > 0 ? pp.good : ["维持了本阶段基础任务"];
          const badItems = Array.isArray(pp.bad) && pp.bad.length > 0 ? pp.bad : ["需要进一步提升该阶段技能与跑图效率"];
          const focusText = pp.focus || "下一把在该阶段优先盯紧核心装时间点与队友第一波开雾信号。";
          const assessmentText =
            pp.assessment ||
            `${activePd.time_label} 期间 ${pp.kills_count} 杀 ${pp.deaths_count} 死，经济 +${fmtNum(
              pp.gold_gain
            )}，英雄伤害 +${fmtNum(pp.hero_damage_gain)}。`;

          return `
            <article class="phase-p-card ${Number(pp.account_id) === Number(state.accountId) ? "is-me" : ""}">
              <div class="phase-p-head">
                ${
                  pp.hero_img
                    ? `<img src="${escapeHtml(pp.hero_img)}" alt="${escapeHtml(pp.hero_short_zh)}" loading="lazy" />`
                    : ""
                }
                <div style="min-width: 0;">
                  <div style="font-size: 13px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${pp.pos}号位 · ${escapeHtml(pp.hero_short_zh)}
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
                  <span>${state.activePhaseKey === "lane" ? "10分钟正补/反补" : "阶段补刀增量"}</span>
                  <b>${
                    state.activePhaseKey === "lane"
                      ? `${pp.lh_gain} / ${pp.dn_gain || 0}`
                      : `+${pp.lh_gain} 刀`
                  }</b>
                </div>
              </div>

              ${
                (pp.items_bought || []).length > 0
                  ? `
                <div class="phase-items-row">
                  ${pp.items_bought
                    .map(
                      (it) => `
                      <div class="mini-item-chip" title="${escapeHtml(it.zh_name || it.key)} (${escapeHtml(it.time_str)})">
                        ${it.img ? `<img src="${escapeHtml(it.img)}" alt="${escapeHtml(it.zh_name || it.key)}" loading="lazy" />` : ""}
                        <span>${escapeHtml(it.time_str)}</span>
                      </div>
                    `
                    )
                    .join("")}
                </div>
              `
                  : `<div style="font-size: 10px; color: var(--dim);">本阶段无核心成装更新</div>`
              }

              <div class="phase-p-prose">${escapeHtml(assessmentText)}</div>

              <div class="phase-p-eval-block">
                <div class="phase-eval-group good">
                  <b>✓ 哪里做得好</b>
                  <ul>
                    ${goodItems.slice(0, 2).map((g) => `<li>${escapeHtml(g)}</li>`).join("")}
                  </ul>
                </div>
                <div class="phase-eval-group bad">
                  <b>✕ 哪里做得不好</b>
                  <ul>
                    ${badItems.slice(0, 2).map((b) => `<li>${escapeHtml(b)}</li>`).join("")}
                  </ul>
                </div>
                <div class="phase-eval-focus">
                  <strong>阶段改进：</strong>${escapeHtml(focusText)}
                </div>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

/**
 * 8. Module 4: Key Teamfights & Turning Windows
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

  const cardsHtml = [];

  grokWindows.forEach((w) => {
    cardsHtml.push(`
      <article class="window-card">
        <div class="window-head">
          <span class="window-time-badge">${escapeHtml(w.time_label || "关键节点")}</span>
          <span class="window-tone-badge praise">🧠 Grok 4.7 拐点剧场</span>
          <h3 class="window-title">${escapeHtml(w.title || "胜负转折点")}</h3>
        </div>
        <div class="window-story-box praise">
          <span class="window-story-tag">🎙️ AI 刀塔老炮复盘评书</span>
          <div class="window-story-text">${escapeHtml(w.detail || "")}</div>
        </div>
      </article>
    `);
  });

  tfs.slice(0, grokWindows.length > 0 ? 4 : 6).forEach((tf, idx) => {
    const pRows = (tf.participants || [])
      .sort((a, b) => (b.damage || 0) - (a.damage || 0))
      .slice(0, 6)
      .map(
        (p) =>
          `${p.hero_short_zh}: ${fmtNum(p.damage)}伤${p.deaths ? " (阵亡)" : ""}${
            p.buybacks ? " [买活]" : ""
          }${
            (p.abilities || []).length > 0 ? ` [${p.abilities.slice(0, 2).join("/")}]` : ""
          }`
      )
      .join(" ｜ ");
    const matchedTfIdx = tfForensics.findIndex((f) => f.time_range === tf.time_range);
    const tfIdxToUse = matchedTfIdx >= 0 ? matchedTfIdx : idx;
    const fObj = tfForensics[tfIdxToUse];
    const deathCount = (fObj?.deaths_coords || []).length;
    const buybacksList = fObj?.buybacks || [];
    const storyObj = buildTeamfightDotaStory(tf, fObj, idx, {
      side,
      sideZh,
      oppZh,
      own,
      opp,
    });

    cardsHtml.push(`
      <article class="window-card">
        <div class="window-head">
          <span class="window-time-badge">${escapeHtml(tf.time_range)}</span>
          <span class="window-tone-badge ${escapeHtml(storyObj.tone)}">${escapeHtml(storyObj.badge)}</span>
          <h3 class="window-title">高烈度团战 #${idx + 1} · ${escapeHtml(tf.kills_trade)} (${escapeHtml(tf.gold_swing)})</h3>
          ${
            deathCount > 0
              ? `<button type="button" class="button secondary" style="margin-left:auto;padding:3px 8px;font-size:11px;" data-locate-tf="${tfIdxToUse}">📍 在地图定位墓碑 (${deathCount})</button>`
              : ""
          }
        </div>
        <div class="window-story-box ${escapeHtml(storyObj.tone)}">
          <span class="window-story-tag">🎙️ AI 刀塔老炮团战故事回放</span>
          <div class="window-story-text">${storyObj.storyHtml}</div>
        </div>
        <div class="window-stat-strip">
          <span>💥 最高输出：<b>${escapeHtml(tf.top_damage_hero || "-")}</b></span>
          ${
            buybacksList.length > 0
              ? `<span>💰 交出买活：<b>${escapeHtml(buybacksList.join("、"))}</b></span>`
              : ""
          }
          <span class="window-participants-inline">${escapeHtml(pRows)}</span>
        </div>
      </article>
    `);
  });

  grid.innerHTML =
    cardsHtml.length > 0
      ? cardsHtml.join("")
      : `<div class="empty-state">暂无团战明细记录</div>`;

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
 * 9. Module 5: 1~5 Position Deep Forensics Cards
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

  const maxCulpritSlot = !ownWon
    ? [...own].sort((a, b) => (b.blame_share_pct || 0) - (a.blame_share_pct || 0))[0]?.player_slot
    : null;
  const mvpSlot = report.mvp?.mvp_player?.player_slot;

  container.innerHTML = listToRender
    .map((p) =>
      renderSingleForensicCard(p, {
        grokPlayer: grokPlayersMap.get(Number(p.player_slot)),
        isTopCulprit: !p.won && Number(p.player_slot) === Number(maxCulpritSlot),
        isMvp: Number(p.player_slot) === Number(mvpSlot),
      })
    )
    .join("");

  container.querySelectorAll("[data-copy-quote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const label = btn.getAttribute("data-copy-label") || "个人复盘报告";
      copyTextToClipboard(btn.getAttribute("data-copy-quote") || "", label);
    });
  });
}

function renderSingleForensicCard(p, { grokPlayer, isTopCulprit, isMvp }) {
  const heroShort = p.hero_short_zh || p.hero_name;
  const posNum = p.pos || 1;
  const pWon = Boolean(p.won);
  const contribPct = Number(p.contrib_share_pct ?? p.blame_share_pct ?? 20).toFixed(1);
  const blamePct = Number(p.blame_share_pct || 0).toFixed(1);

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
    grokPlayer?.good && grokPlayer.good.length > 0
      ? grokPlayer.good
      : p.strengths || ["数据层面暂无突出亮点"];
  const badList =
    grokPlayer?.bad && grokPlayer.bad.length > 0
      ? grokPlayer.bad
      : p.weaknesses || ["本局无明显失误记录"];
  const fixList =
    grokPlayer?.practice
      ? [grokPlayer.practice, ...(p.improvements || []).slice(0, 2)]
      : p.improvements || ["保持当前节奏与位置感"];

  const headlineText = grokPlayer?.headline || "";
  const aiStoryObj = buildPlayerDossierAiStory(p, {
    grokPlayer,
    isTopCulprit,
    isMvp,
  });

  const footerQuote = pWon
    ? p.praise_talk || headlineText || goodList[0] || p.trash_talk || ""
    : p.trash_talk || headlineText || badList[0] || "";

  const copyText = pWon
    ? `【${p.pos_label}庆功表彰】${p.personaname} (${heroShort})：KDA ${p.kda}，GPM ${p.gpm}，胜局贡献 ${contribPct}%。${footerQuote}`
    : `【${p.pos_label}算账单】${p.personaname} (${heroShort})：KDA ${p.kda}，GPM ${p.gpm}，分锅占比 ${blamePct}%。${footerQuote}`;

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
              ? `<img class="forensic-portrait" src="${escapeHtml(p.hero_img)}" alt="${escapeHtml(heroShort)}" loading="lazy" />`
              : ""
          }
          <div class="forensic-title-block">
            <div class="forensic-name-row">
              <span class="forensic-hero-zh">${escapeHtml(heroShort)}</span>
              <span class="forensic-player-id">${escapeHtml(p.personaname)}${p.is_me ? " [我]" : ""}</span>
              <span class="status-pill">${escapeHtml(p.side)} · ${escapeHtml(p.pos_label)}</span>
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
          <span class="status-pill connected">综合评分 ${Number(p.rating_score || 60).toFixed(1)}</span>
          ${
            pWon
              ? `<span class="blame-badge" style="color:#a8e5a7;border-color:#3a6a40;background:#152317;">🏆 胜局贡献 ${contribPct}% · ${escapeHtml(
                  p.contrib_tier || p.rating_tier || "凯旋功臣"
                )}</span>`
              : `<span class="blame-badge">背锅 ${blamePct}% · ${escapeHtml(
                  p.rating_tier || "普通背锅"
                )}</span>`
          }
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

      <!-- AI 毒舌/封神个人结案陈词 (Chapter 6 AI Storytelling) -->
      <div class="forensic-ai-story-box ${escapeHtml(aiStoryObj.tone)}">
        <span class="forensic-ai-badge ${escapeHtml(aiStoryObj.tone)}">${escapeHtml(aiStoryObj.badge)}</span>
        <div class="forensic-ai-text">${aiStoryObj.storyHtml}</div>
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
          <div class="radar-mini-scores">${escapeHtml(radarMiniSummary)}</div>
        </div>
      </div>

      <div class="forensic-prose-grid">
        <div class="prose-col good">
          <h4>${pWon ? "🏆 凯旋高光与胜局贡献" : "哪里干得漂亮 (高光与贡献)"}</h4>
          <ul>
            ${goodList.map((g) => `<li>${escapeHtml(g)}</li>`).join("")}
          </ul>
        </div>
        <div class="prose-col bad">
          <h4>${pWon ? "🔍 胜局复盘小瑕疵 (美中不足)" : "哪里在犯罪 (背锅铁证)"}</h4>
          <ul>
            ${badList.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}
          </ul>
        </div>
        <div class="prose-col fix">
          <h4>${pWon ? "🚀 乘胜追击进阶建议" : "下把怎么改 (具体可执行动作)"}</h4>
          <ul>
            ${fixList.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}
          </ul>
        </div>
      </div>

      <div class="forensic-trash-footer">
        <span><strong>${pWon ? "🏆 专属庆功贺词：" : "专属算账金句："}</strong>${escapeHtml(footerQuote)}</span>
        <button type="button" class="button secondary" data-copy-label="${pWon ? "个人庆功词" : "个人算账报告"}" data-copy-quote="${escapeHtml(copyText)}">${
          pWon ? "复制庆功词" : "复制这段喷他"
        }</button>
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
  if (provSel) provSel.value = cfg.provider || "xai";
  if (modelIn) modelIn.value = cfg.model || "grok-4.7";
  if (baseIn) baseIn.value = cfg.baseUrl || "https://api.x.ai/v1";
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

    <div class="squad-grid-2col">
      <article class="squad-card">
        <div class="squad-card-head">
          <h3>⚖️ 五黑车队成员跨局贡献与分锅总榜</h3>
          <span>胜局记首功 · 败局抓战犯 · 谁是大腿谁是惯犯一目了然</span>
        </div>
        <div class="squad-table-wrap">
          <table class="squad-rank-table">
            <thead>
              <tr>
                <th>队员昵称</th>
                <th>历史定位</th>
                <th>出勤/胜率</th>
                <th>场均贡献/分锅</th>
                <th>场均评分</th>
                <th>MVP / 败局锅王</th>
                <th>场均KDA / 读秒</th>
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
                      <td>${m.avg_rating}</td>
                      <td>${m.mvp_count}次 / <b style="color:${
                        m.culprit_count > 0 ? "var(--red-light)" : "inherit"
                      }">${m.culprit_count}次</b></td>
                      <td>${escapeHtml(m.avg_kda)} (${m.avg_dead_sec}s)</td>
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
          <h3>🎭 近期英雄池红黑榜 &amp; 已审理录像档案库</h3>
          <span>点击下方任意已归档比赛可秒切换复盘</span>
        </div>
        <div class="hero-pool-list">
          ${heroPool
            .slice(0, 6)
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
        await loadMatchReport(mid);
      }
    });
  });
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
        `👑 头号首功 (MVP)：${mvpPlayer?.personaname || ""} (${mvpPlayer?.hero_short_zh || ""}) — 胜局贡献 ${Number(
          mvpPlayer?.contrib_share_pct ?? 25
        ).toFixed(1)}% · 综合评分 ${mvpPlayer?.rating_score || 0}`,
        `⚔️ 破阵二当家：${runnerUpPlayer?.personaname || ""} (${runnerUpPlayer?.hero_short_zh || ""}) — 胜局贡献 ${Number(
          runnerUpPlayer?.contrib_share_pct ?? 22
        ).toFixed(1)}% · 综合评分 ${runnerUpPlayer?.rating_score || 0}`,
        `────────────────────`,
        `📊 五黑全员胜局贡献榜 (100% 胜局贡献排位)：`,
        ...sortedContrib.map((p, i) => {
          const b0 = (p.hero_execution_audit?.headline_badges || [])[0];
          const b0Txt = typeof b0 === "string" ? b0 : b0?.text || "";
          const cPct = Number(p.contrib_share_pct ?? 20).toFixed(1);
          return `${i + 1}. [${p.pos_label}] ${p.personaname} (${p.hero_short_zh}) | 胜局贡献 ${cPct}% (${
            p.contrib_tier || p.rating_tier || "功臣"
          }) | KDA ${p.kda} | GPM ${p.gpm} | 伤害占比 ${p.hero_damage_share_pct}%${
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
        `🚨 头号背锅侠：${topCulprit?.personaname || ""} (${topCulprit?.hero_short_zh || ""}) — 分锅占比 ${topCulprit?.blame_share_pct || 0}%`,
        `👑 败方尽力王：${mvpPlayer?.personaname || ""} (${mvpPlayer?.hero_short_zh || ""}) — 综合评分 ${mvpPlayer?.rating_score || 0}`,
        `────────────────────`,
        `📊 五黑全员算账明细 (按背锅排序)：`,
        ...sortedBlame.map((p, i) => {
          const b0 = (p.hero_execution_audit?.headline_badges || [])[0];
          const b0Txt = typeof b0 === "string" ? b0 : b0?.text || "";
          return `${i + 1}. [${p.pos_label}] ${p.personaname} (${p.hero_short_zh}) | KDA ${p.kda} | GPM ${p.gpm} | 伤害占比 ${p.hero_damage_share_pct}% | 读秒 ${p.dead_seconds || 0}s | 锅 ${p.blame_share_pct}%${
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
        mvpPlayer?.contrib_share_pct ?? 25
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
        runnerUpPlayer?.contrib_share_pct ?? 22
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
      `${topCulprit?.personaname || ""} · ${topCulprit?.hero_short_zh || ""} (背锅 ${topCulprit?.blame_share_pct || 0}%)`,
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
      `${mvpPlayer?.personaname || ""} · ${mvpPlayer?.hero_short_zh || ""} (评分 ${mvpPlayer?.rating_score || 0})`,
      482,
      206
    );
  }

  let y = 252;
  const rowsList = won ? sortedContrib || sortedBlame : sortedBlame;
  rowsList.forEach((p, idx) => {
    const isFirst = idx === 0;
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
        ? `胜局贡献 ${Number(p.contrib_share_pct ?? 20).toFixed(1)}% · 评分 ${p.rating_score}`
        : `分锅 ${p.blame_share_pct}% · 评分 ${p.rating_score}`,
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

/**
 * 15. Workspace Mode Switcher & Pre-Game 5-Stack Live Draft Coach (/pregame)
 */
function switchWorkspaceMode(mode, { pushUrl = true } = {}) {
  state.workspaceMode = mode === "pregame" ? "pregame" : "postgame";
  const isPregame = state.workspaceMode === "pregame";

  const postView = document.getElementById("postgame-workspace");
  const preView = document.getElementById("pregame-workspace");
  if (postView) postView.hidden = isPregame;
  if (preView) preView.hidden = !isPregame;

  document
    .getElementById("nav-mode-postgame")
    ?.classList.toggle("active", !isPregame);
  document
    .getElementById("nav-mode-pregame")
    ?.classList.toggle("active", isPregame);

  if (pushUrl && window.history?.replaceState) {
    const targetPath = isPregame ? "/pregame" : "/";
    if (window.location.pathname !== targetPath) {
      window.history.replaceState({}, "", targetPath);
    }
  }

  if (isPregame) {
    renderPregameSlots();
    renderPregameHeroGrid();
    if (!state.pregamePlan) {
      requestAndRenderPregamePlan({ useLlm: false });
    }
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


