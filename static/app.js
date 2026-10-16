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
  perspective: "auto", // "auto" | "dire" | "radiant"
  nwFilter: "cores",   // "cores" | "own" | "all"
  mapMode: "wards_obs", // "wards_obs" | "wards_own" | "wards_all" | "heatmap" | "teamfights"
  selectedTeamfightIndex: null,
  focusMatrixSide: "own", // "own" | "opp"
  microTab: "hero_ult", // "hero_ult" | "vision" | "stack_smoke" | "laning" | "tp_save" | "all"
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

function escapeHtml(value) {
  return String(value ?? "")
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
  const rad = report.radiant_pos_1_to_5 || report.radiant_players || [];
  const dire = report.dire_pos_1_to_5 || report.dire_players || [];
  const own = side === "radiant" ? rad : dire;
  const opp = side === "radiant" ? dire : rad;
  return {
    side,
    sideZh: side === "radiant" ? "天辉" : "夜魇",
    oppZh: side === "radiant" ? "夜魇" : "天辉",
    own: [...own].sort((a, b) => (a.pos || 9) - (b.pos || 9)),
    opp: [...opp].sort((a, b) => (a.pos || 9) - (b.pos || 9)),
    all: [...rad, ...dire],
  };
}

/**
 * Initialize app on load
 */
async function initApp() {
  bindEvents();
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
    if (firstReport) {
      state.currentMatchId = firstReport.match_id;
      state.currentReport = firstReport;
      renderFullMatchReport(state.currentReport);
      highlightSelectedMatchCard(state.currentMatchId);
    } else if ((data.recent_matches || []).length > 0) {
      await loadMatchReport(data.recent_matches[0].match_id);
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
      if (list.length > 0) {
        await loadMatchReport(list[0].match_id);
      }
    });
  }

  const perspSelect = document.getElementById("perspective-select");
  if (perspSelect) {
    perspSelect.addEventListener("change", () => {
      state.perspective = perspSelect.value;
      if (state.currentReport) {
        renderFullMatchReport(state.currentReport);
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
        copyTextToClipboard(ta.value, "群聊处刑判决书");
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

  strip.innerHTML = matches
    .slice(0, 12)
    .map((m) => {
      const selected = Number(m.match_id) === Number(state.currentMatchId);
      const isWin = m.won !== undefined ? Boolean(m.won) : m.result === "胜利";
      const resultText = isWin ? "胜利" : "落败";
      const heroShort = m.hero_short_zh || m.hero_name || "未知英雄";
      const partyLabel = m.party_label || (m.party_size >= 2 ? `${m.party_size}人黑` : "单排");
      const durText = m.duration_str || m.duration || "";
      const parsedLabel = m.is_parsed ? "录像已解" : "基础数据";
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
            <span>${escapeHtml(parsedLabel)}</span>
          </div>
        </button>
      `;
    })
    .join("");

  strip.querySelectorAll("[data-match-card]").forEach((btn) => {
    btn.addEventListener("click", async () => {
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
      renderFullMatchReport(state.currentReport);
      highlightSelectedMatchCard(state.currentMatchId);
    }
    showToast(`已切换主视角至 #${state.accountId}`);
  } catch (err) {
    showToast(`查询失败: ${err.message}`);
  }
}

async function loadMatchReport(matchId, { forceRefresh = false } = {}) {
  showToast(`正在拉取比赛 #${matchId} 录像账本...`, 2000);
  try {
    const url = `/api/match/${encodeURIComponent(matchId)}?account_id=${encodeURIComponent(
      state.accountId
    )}${forceRefresh ? "&refresh=1" : ""}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "读取比赛失败");

    state.currentMatchId = data.report.match_id;
    state.currentReport = data.report;
    state.selectedTeamfightIndex = null;
    if (data.squad_ledger) {
      state.squadLedger = data.squad_ledger;
      renderSquadLedgerSection(state.squadLedger);
    }
    highlightSelectedMatchCard(state.currentMatchId);
    renderFullMatchReport(state.currentReport);
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
 * 2.5 NEW MODULE: 🔬 录像级战术显微镜 (Tactical Microscope — 5 Deep Replay Tabs)
 *  - Tab 1 (hero_ult): 英雄绝活与大招审判 (如猛犸两极反转大几个、哪波团憋大暴毙、授予力量覆盖率、潮汐毁灭、帕格纳棒子&吸血救人、剑圣棒子自奶vs团队奶、白虎神箭命中率)
 *  - Tab 2 (vision): 辅助眼位进攻/防守与寿命 (进攻眼vs河道肉山眼vs防守保护眼占比、分阶段眼位倾向、平均寿命、秒排白给眼 <135s、同高台头铁连插、每颗假眼坐标明细)
 *  - Tab 3 (stack_smoke): 辅助堆野 & 开雾找节奏 (辅助拉野vs大哥自拉野、精确到分钟的堆野时间点、每波诡计之雾激活人及破雾后 90s 团战战果)
 *  - Tab 4 (laning): 对线拉野·走门·莲花·经验符 (拉野区驻留+封野真眼+反补、3/6/9m 疗伤莲花、7/14/21m 智慧神符时间轴、2/4m 河道水符、双生门传送、观察者点灯、三路10分钟对位验尸)
 *  - Tab 5 (tp_save): TP 救人及时性与缺席抓包 (主动买TP vs 靠免费复活TP、团战亮TP反蹲次数、队友被围剿时0伤害0技能未亮TP边缘OB抓包)
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
          <h3>🆘 5. TP 救人及时性、主动买 TP 习惯与团战边缘 OB 抓包 (${escapeHtml(targetSideZh)})</h3>
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
 * 2. Render Grok 4.7 Verdict Banner + MVP Card + Culprit Card + 5-Stack Blame Ledger
 */
function renderVerdictAndBlameSection(report) {
  const { side, sideZh, own, all } = getOwnAndOppPlayers(report);
  const bySlot = new Map(all.map((p) => [Number(p.player_slot), p]));

  const grok = report.grok_coaching;
  const mvpData = report.mvp || {};

  // 2.1 Grok Verdict Banner
  const authorEl = document.getElementById("grok-author-label");
  const titleEl = document.getElementById("grok-title-text");
  const summaryEl = document.getElementById("grok-summary-text");
  const verdictEl = document.getElementById("grok-verdict-text");
  const practiceEl = document.getElementById("grok-team-practice-box");

  if (grok && (!grok.side || grok.side === side)) {
    const modelTag = grok._meta?.model
      ? `${String(grok._meta.provider || "XAI").toUpperCase()} / ${grok._meta.model} 赛后总账`
      : "XAI / GROK-4.7 赛后总账";
    if (authorEl) authorEl.textContent = modelTag;
    if (titleEl) titleEl.textContent = grok.title || "本局赛后复盘总账";
    if (summaryEl) summaryEl.textContent = grok.summary || "";
    if (verdictEl) verdictEl.textContent = grok.verdict || "";
    if (practiceEl) {
      practiceEl.innerHTML = grok.team_practice
        ? `<strong>下把车队铁律：</strong>${escapeHtml(grok.team_practice)}`
        : "";
      practiceEl.hidden = !grok.team_practice;
    }
  } else {
    const stages = report.match_narrative?.stages || [];
    if (authorEl) authorEl.textContent = "录像级算账引擎 · 自动判词 (可点右上角用 Grok 4.7 深度重算)";
    if (titleEl) {
      titleEl.textContent = `${sideZh}赛后算账：终局比分 ${report.radiant_score} : ${report.dire_score} (${report.duration_str})`;
    }
    if (summaryEl) {
      summaryEl.textContent = stages.map((s) => `${s.stage}：${s.summary}`).join(" ");
    }
    if (verdictEl) {
      verdictEl.textContent = (mvpData.rationale_list || []).join(" ");
    }
    if (practiceEl) {
      practiceEl.innerHTML = `<strong>提示：</strong>点击右上角「用 Grok 4.7 重算判词」即可调用服务端已配置的 xAI Grok 4.7 生成针对『${escapeHtml(
        sideZh
      )}』阵容的毒舌逐人判词。`;
      practiceEl.hidden = false;
    }
  }

  // 2.2 MVP Card
  const mvpBody = document.getElementById("mvp-card-body");
  let mvpPlayer = mvpData.mvp_player || all[0];
  const grokMvp = grok?.mvp && (!grok.side || grok.side === side) ? grok.mvp : null;
  if (grokMvp && bySlot.has(Number(grokMvp.slot))) {
    mvpPlayer = bySlot.get(Number(grokMvp.slot));
  } else if (mvpPlayer && bySlot.has(Number(mvpPlayer.player_slot))) {
    mvpPlayer = bySlot.get(Number(mvpPlayer.player_slot));
  }

  if (mvpBody && mvpPlayer) {
    const heroShort = mvpPlayer.hero_short_zh || mvpPlayer.hero_name;
    const evidences = [];
    if (grokMvp?.reason) evidences.push(grokMvp.reason);
    if (grokMvp?.comparison) evidences.push(grokMvp.comparison);
    if (Array.isArray(grokMvp?.evidence)) {
      grokMvp.evidence.forEach((e) => evidences.push(e));
    }
    if (evidences.length === 0 && Array.isArray(mvpData.rationale_list)) {
      mvpData.rationale_list.forEach((r) => evidences.push(r));
    }
    if (evidences.length === 0 && Array.isArray(mvpPlayer.strengths)) {
      mvpPlayer.strengths.slice(0, 3).forEach((r) => evidences.push(r));
    }

    const mvpCopyText = `【本局大腿 MVP】${mvpPlayer.personaname} (${heroShort} · ${mvpPlayer.pos_label})：KDA ${mvpPlayer.kda}，GPM ${mvpPlayer.gpm}，英雄伤害 ${fmtNum(mvpPlayer.hero_damage)}。${evidences[0] || ""}`;

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
            <span class="status-pill connected">${escapeHtml(mvpPlayer.side)} · ${escapeHtml(mvpPlayer.pos_label)}</span>
          </div>
          <div class="verdict-sub-meta">
            KDA ${escapeHtml(mvpPlayer.kda)} (${mvpPlayer.kill_participation_pct}% 参战) · GPM ${mvpPlayer.gpm} · 伤害 ${fmtNum(mvpPlayer.hero_damage)} · 拆塔 ${fmtNum(mvpPlayer.tower_damage)}
          </div>
        </div>
        <div class="verdict-score-box">
          <div class="verdict-score-num">${Number(mvpPlayer.mvp_score || mvpPlayer.rating_score || 85).toFixed(1)}</div>
          <div class="verdict-score-sub">MVP 战功分</div>
        </div>
      </div>
      <ul class="verdict-evidence-list">
        ${evidences
          .slice(0, 4)
          .map((item) => `<li>${escapeHtml(item)}</li>`)
          .join("")}
      </ul>
      <div class="verdict-quote-bar">
        <span>「这把要不是 ${escapeHtml(heroShort)} 死命顶着局势，早就提前十五分钟敲 GG 了。」</span>
        <button type="button" class="button secondary" data-copy-quote="${escapeHtml(mvpCopyText)}">复制表彰词</button>
      </div>
    `;
  }

  // 2.3 Top Culprit Card (Highest blame share on the audited side)
  const culpritBody = document.getElementById("culprit-card-body");
  const sortedByBlame = [...own].sort((a, b) => (b.blame_share_pct || 0) - (a.blame_share_pct || 0));
  const culprit = sortedByBlame[0] || own[0];
  const grokCulprit = (grok?.players || []).find((gp) => Number(gp.slot) === Number(culprit?.player_slot));

  if (culpritBody && culprit) {
    const heroShort = culprit.hero_short_zh || culprit.hero_name;
    const crimes = [];
    if (grokCulprit?.assessment) crimes.push(grokCulprit.assessment);
    if (Array.isArray(grokCulprit?.bad)) {
      grokCulprit.bad.forEach((b) => crimes.push(b));
    }
    if (crimes.length === 0 && Array.isArray(culprit.weaknesses)) {
      culprit.weaknesses.forEach((b) => crimes.push(b));
    }

    const culpritCopyText = `【头号战犯逮捕令】${culprit.personaname} (${heroShort} · ${culprit.pos_label}) 本局分锅占比 ${culprit.blame_share_pct}%！KDA ${culprit.kda}，泉水读秒 ${culprit.dead_seconds || 0} 秒。${
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
          <div class="verdict-score-num">${Number(culprit.blame_share_pct || 0).toFixed(1)}%</div>
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

  // 2.4 5-Stack Blame Stacked Bar & Ranking Rows (Zero text clipping on narrow segments!)
  const stackedBar = document.getElementById("blame-stacked-bar");
  const rankingRows = document.getElementById("blame-ranking-rows");

  if (stackedBar && rankingRows) {
    const rawTotal = sortedByBlame.reduce((s, p) => s + Math.max(1, Number(p.blame_share_pct || 0)), 0) || 100;
    const normalized = sortedByBlame.map((p) => ({
      player: p,
      share: Number(((Math.max(1, Number(p.blame_share_pct || 0)) / rawTotal) * 100).toFixed(1)),
    }));

    stackedBar.innerHTML = normalized
      .map(({ player: p, share }, idx) => {
        const heroShort = p.hero_short_zh || p.hero_name;
        // CRITICAL FIX: Never render full text inside narrow segments (< 9%) so text never clips!
        let innerLabel = "";
        if (share >= 15) {
          innerLabel = `${escapeHtml(heroShort)} ${share}%`;
        } else if (share >= 9) {
          innerLabel = `${share}%`;
        }
        const tooltip = `${p.pos_label} ${heroShort} (${p.personaname}): 背锅占比 ${share}%`;
        return `
          <div
            class="blame-seg rank-${idx}"
            style="--share: ${Math.max(share, 2.5)}"
            title="${escapeHtml(tooltip)}"
          >${innerLabel}</div>
        `;
      })
      .join("");

    rankingRows.innerHTML = normalized
      .map(({ player: p, share }, idx) => {
        const heroShort = p.hero_short_zh || p.hero_name;
        const grokP = (grok?.players || []).find((gp) => Number(gp.slot) === Number(p.player_slot));
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
      })
      .join("");
  }

  document.querySelectorAll(".verdict-and-blame-section [data-copy-quote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      copyTextToClipboard(btn.getAttribute("data-copy-quote") || "", "处刑判词");
    });
  });
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

  const { side } = getOwnAndOppPlayers(report);
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
          <h3 class="window-title">${escapeHtml(w.title || "胜负转折点")}</h3>
        </div>
        <p class="window-detail">${escapeHtml(w.detail || "")}</p>
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
    cardsHtml.push(`
      <article class="window-card">
        <div class="window-head">
          <span class="window-time-badge">${escapeHtml(tf.time_range)}</span>
          <h3 class="window-title">高烈度团战 #${idx + 1} · ${escapeHtml(tf.kills_trade)} (${escapeHtml(tf.gold_swing)})</h3>
          ${
            deathCount > 0
              ? `<button type="button" class="button secondary" style="margin-left:auto;padding:3px 8px;font-size:11px;" data-locate-tf="${tfIdxToUse}">📍 在地图定位墓碑 (${deathCount})</button>`
              : ""
          }
        </div>
        <p class="window-detail">
          该波团战最高输出：<b>${escapeHtml(tf.top_damage_hero || "")}</b>${
            buybacksList.length > 0
              ? ` ｜ 💰 交出买活：<b>${escapeHtml(buybacksList.join("、"))}</b>`
              : ""
          }。<br/>
          <span style="font-size: 11px; color: var(--dim);">${escapeHtml(pRows)}</span>
        </p>
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

  const { side, own, opp } = getOwnAndOppPlayers(report);
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

  const maxCulpritSlot = [...own].sort(
    (a, b) => (b.blame_share_pct || 0) - (a.blame_share_pct || 0)
  )[0]?.player_slot;
  const mvpSlot = report.mvp?.mvp_player?.player_slot;

  container.innerHTML = listToRender
    .map((p) =>
      renderSingleForensicCard(p, {
        grokPlayer: grokPlayersMap.get(Number(p.player_slot)),
        isTopCulprit: Number(p.player_slot) === Number(maxCulpritSlot),
        isMvp: Number(p.player_slot) === Number(mvpSlot),
      })
    )
    .join("");

  container.querySelectorAll("[data-copy-quote]").forEach((btn) => {
    btn.addEventListener("click", () => {
      copyTextToClipboard(btn.getAttribute("data-copy-quote") || "", "个人算账报告");
    });
  });
}

function renderSingleForensicCard(p, { grokPlayer, isTopCulprit, isMvp }) {
  const heroShort = p.hero_short_zh || p.hero_name;
  const posNum = p.pos || 1;

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
      : p.weaknesses || ["本局无明显犯罪记录"];
  const fixList =
    grokPlayer?.practice
      ? [grokPlayer.practice, ...(p.improvements || []).slice(0, 2)]
      : p.improvements || ["保持当前节奏与位置感"];

  const headlineText = grokPlayer?.headline || "";
  const assessmentText = grokPlayer?.assessment || "";

  const copyText = `【${p.pos_label}算账单】${p.personaname} (${heroShort})：KDA ${p.kda}，GPM ${p.gpm}，分锅占比 ${p.blame_share_pct}%。${
    p.trash_talk || headlineText || badList[0] || ""
  }`;

  const lh10 = p.laning_10m?.lh10 ?? "-";
  const dn10 = p.laning_10m?.dn10 ?? "-";
  const dmgPerGold = p.net_worth ? (p.hero_damage / p.net_worth).toFixed(2) : "0.00";

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
              ${isMvp ? `<span class="status-pill connected">全场 MVP</span>` : ""}
              ${(p.tags || [])
                .slice(0, 4)
                .map((t) => `<span class="status-pill">${escapeHtml(t)}</span>`)
                .join("")}
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
          <span class="blame-badge">背锅 ${Number(p.blame_share_pct || 0).toFixed(1)}% · ${escapeHtml(
            p.rating_tier || "普通背锅"
          )}</span>
        </div>
      </div>

      ${
        (p.hero_execution_audit?.headline_badges || []).length > 0
          ? `
        <div class="micro-badges-wrap" style="margin-top: 10px;">
          ${(p.hero_execution_audit.headline_badges || [])
            .map((b) => {
              const txt = typeof b === "string" ? b : b?.text || "";
              const tone = typeof b === "object" && b !== null ? b.tone : "";
              const isWarn =
                tone === "bad" ||
                tone === "warn" ||
                txt.includes("⚠️") ||
                txt.includes("1.33") ||
                txt.includes("0.4/分");
              const isGood =
                tone === "good" || txt.includes("14,807") || txt.includes("3.1");
              return txt
                ? `<span class="micro-exec-badge ${
                    isWarn ? "warn" : isGood ? "good" : ""
                  }">🔬 ${escapeHtml(txt)}</span>`
                : "";
            })
            .join("")}
        </div>
      `
          : ""
      }

      ${
        assessmentText && !isMvp && !isTopCulprit
          ? `
        <div style="padding: 11px 14px; margin-top: 12px; background: #181a16; border-left: 3px solid var(--gold); font-size: 13px; color: #ddd6c5; line-height: 1.8;">
          ${escapeHtml(assessmentText)}
        </div>
      `
          : ""
      }

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
          <span>英雄伤害 (伤害占比 / 转化率)</span>
          <strong>${fmtNum(p.hero_damage)} (${p.hero_damage_share_pct}% / ${dmgPerGold})</strong>
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
          <span>10分钟正反补 / 终局补刀</span>
          <strong>${lh10}/${dn10} · ${p.last_hits}/${p.denies}</strong>
        </div>
        <div class="f-metric">
          <span>泉水读秒 / 阵亡掉钱</span>
          <strong style="color: ${(p.dead_seconds || 0) >= 180 ? "var(--red-light)" : "inherit"}">${
            p.dead_seconds || 0
          }秒 / -${fmtNum(p.death_gold_lost || 0)}</strong>
        </div>
      </div>

      <div class="forensic-visual-row">
        <div>
          <div class="visual-sub-title">
            <span>终局六神装与合成时间点 (右上角红标为主动按键次数)</span>
          </div>
          <div class="items-slots-row">
            ${slotsHtml || `<span style="font-size: 11px; color: var(--dim);">无终局装备记录</span>`}
            ${neutralHtml}
          </div>
          ${
            activeUsesSummary
              ? `<div class="checkpoints-strip" style="margin-top: 9px;">${activeUsesSummary}</div>`
              : ""
          }
        </div>

        <div>
          <div class="visual-sub-title">
            <span>核心技能释放审计 &amp; 击杀/被提款关系</span>
          </div>
          <div class="abilities-casts-row">
            ${abilitiesHtml || `<span style="font-size: 11px; color: var(--dim);">未解析技能释放日志</span>`}
          </div>
          <div class="nemesis-strip">
            ${killedPills}
            ${nemesisPills}
          </div>
        </div>

        <div class="radar-mini-box">
          ${renderHexRadarSvg(p.radar)}
        </div>
      </div>

      ${
        (p.benchmarks_list || []).length > 0 || (p.ability_targets_list || []).length > 0
          ? `
        <div class="forensic-bench-target-row">
          ${
            (p.benchmarks_list || []).length > 0
              ? `
            <div class="f-bench-col">
              <div class="visual-sub-title">
                <span>🌍 全球同英雄水平百分位对标 (OpenDota Benchmarks · 击败全球多少同英雄玩家)</span>
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
          ${
            (p.ability_targets_list || []).length > 0
              ? `
            <div class="f-target-col">
              <div class="visual-sub-title">
                <span>🎯 指向性技能都砸给谁了 (录像目标统计)</span>
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
      `
          : ""
      }

      <div class="forensic-prose-grid">
        <div class="prose-col good">
          <h4>哪里干得漂亮 (高光与贡献)</h4>
          <ul>
            ${goodList.map((g) => `<li>${escapeHtml(g)}</li>`).join("")}
          </ul>
        </div>
        <div class="prose-col bad">
          <h4>哪里在犯罪 (背锅铁证)</h4>
          <ul>
            ${badList.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}
          </ul>
        </div>
        <div class="prose-col fix">
          <h4>下把怎么改 (具体可执行动作)</h4>
          <ul>
            ${fixList.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}
          </ul>
        </div>
      </div>

      <div class="forensic-trash-footer">
        <span><strong>专属算账金句：</strong>${escapeHtml(p.trash_talk || headlineText)}</span>
        <button type="button" class="button secondary" data-copy-quote="${escapeHtml(copyText)}">复制这段喷他</button>
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
        <span>MVP:${escapeHtml(m.mvp_hero)}</span>
        <span style="color:var(--red-light);">锅:${escapeHtml(m.culprit_hero)}(${m.culprit_blame_pct}%)</span>
      </button>
    `
    )
    .join("");

  container.innerHTML = `
    <div class="squad-summary-banner">
      <div class="squad-summary-text">
        <strong>📂 五黑车队跨局惯犯总账：</strong>
        历史头号背锅王 <b style="color:var(--red-light);">${escapeHtml(
          topCulpritMember?.personaname || "—"
        )}</b>（场均分锅 ${topCulpritMember?.avg_blame_pct || 0}% · 拿过 ${
          topCulpritMember?.culprit_count || 0
        } 次头号战犯） ｜ 历史头号真大腿 <b style="color:var(--green-light);">${escapeHtml(
          topCarryMember?.personaname || "—"
        )}</b>（场均评分 ${topCarryMember?.avg_rating || 0} · 拿过 ${
          topCarryMember?.mvp_count || 0
        } 次全场 MVP）
      </div>
      <div class="squad-summary-pills">
        <span class="squad-pill">近期组排开黑：${partySum.party_games || 0}局 (${partySum.party_win_rate || 0}%胜率)</span>
        <span class="squad-pill">近期单排：${partySum.solo_games || 0}局 (${partySum.solo_win_rate || 0}%胜率)</span>
      </div>
    </div>

    <div class="squad-grid-2col">
      <article class="squad-card">
        <div class="squad-card-head">
          <h3>⚖️ 五黑车队成员跨局分锅与评分总榜</h3>
          <span>按场均分锅占比排序 · 谁是长期惯犯一目了然</span>
        </div>
        <div class="squad-table-wrap">
          <table class="squad-rank-table">
            <thead>
              <tr>
                <th>队员昵称</th>
                <th>历史定位</th>
                <th>出勤/胜率</th>
                <th>场均分锅</th>
                <th>场均评分</th>
                <th>MVP / 锅王</th>
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
                            )}" title="#${h.match_id} ${escapeHtml(h.hero_short_zh)} (${h.kda} · 锅${
                              h.blame_pct
                            }%)" loading="lazy" />`
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
                      };font-weight:700;">${m.avg_blame_pct}%</td>
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
 * 14. Shareable Verdict Poster & Chat Text Generator (群聊处刑判决书 & 长图导出)
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
  const topCulprit = sortedBlame[0];
  const mvpPlayer = [...own].sort(
    (a, b) => (b.rating_score || 0) - (a.rating_score || 0)
  )[0];

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
  const microVis = df.support_vision_by_side?.[side]?.posture_verdict || "";
  const microStack = df.stacking_and_smoke_by_side?.[side]?.stack_verdict || "";
  const microSmoke = df.stacking_and_smoke_by_side?.[side]?.smoke_verdict || "";
  const microTp = df.tp_rotation_by_side?.[side]?.tp_verdict || "";

  const lines = [
    `⚖️【刀塔五黑算账台 · 赛后处刑判决书】`,
    `📍 比赛编号：#${report.match_id} (${report.duration_str} · ${sideZh}${won ? "获胜" : "落败"} ${report.radiant_score}:${report.dire_score})`,
    `📣 终局定性：${grok?.title || report.match_narrative?.headline || "正面团战与节奏复盘"}`,
    `────────────────────`,
    `🚨 头号背锅侠：${topCulprit?.personaname || ""} (${topCulprit?.hero_short_zh || ""}) — 分锅占比 ${topCulprit?.blame_share_pct || 0}%`,
    `👑 本局真大腿：${mvpPlayer?.personaname || ""} (${mvpPlayer?.hero_short_zh || ""}) — 综合评分 ${mvpPlayer?.rating_score || 0}`,
    `────────────────────`,
    `📊 五黑全员算账明细 (按背锅排序)：`,
    ...sortedBlame.map((p, i) => {
      const b0 = (p.hero_execution_audit?.headline_badges || [])[0];
      const b0Txt = typeof b0 === "string" ? b0 : b0?.text || "";
      return `${i + 1}. [${p.pos_label}] ${p.personaname} (${p.hero_short_zh}) | KDA ${p.kda} | GPM ${p.gpm} | 伤害占比 ${p.hero_damage_share_pct}% | 读秒 ${p.dead_seconds || 0}s | 锅 ${p.blame_share_pct}%${
        b0Txt ? ` | 🔬 ${b0Txt}` : ""
      }`;
    }),
    ...(microExec || microVis || microTp
      ? [
          `────────────────────`,
          `🔬 录像级战术显微镜实锤：`,
          ...(microExec ? [`• 【大招与绝活】${microExec}`] : []),
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

  drawVerdictPosterCanvas(report, { sideZh, won, sortedBlame, topCulprit, mvpPlayer, grok });
  dlg.showModal();
}

function drawVerdictPosterCanvas(report, { sideZh, won, sortedBlame, topCulprit, mvpPlayer, grok }) {
  const canvas = document.getElementById("share-poster-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "#151713");
  grad.addColorStop(1, "#0d0e0c");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = "#c6a468";
  ctx.lineWidth = 2;
  ctx.strokeRect(18, 18, W - 36, H - 36);

  ctx.fillStyle = "#c6a468";
  ctx.font = "bold 16px sans-serif";
  ctx.fillText("DOTA 2 五黑算账台 · 赛后处刑判决书", 42, 56);

  ctx.fillStyle = won ? "#7cb87a" : "#e06c5a";
  ctx.font = "bold 26px sans-serif";
  const headline = `[${sideZh}${won ? "获胜" : "落败"}] #${report.match_id} (${report.radiant_score} : ${report.dire_score} · ${report.duration_str})`;
  ctx.fillText(headline, 42, 92);

  ctx.fillStyle = "#d9d4c7";
  ctx.font = "14px sans-serif";
  const subTitle = (grok?.title || report.match_narrative?.headline || "录像级硬核责任划分报告").slice(0, 52);
  ctx.fillText(subTitle, 42, 120);

  ctx.strokeStyle = "#34372d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(42, 138);
  ctx.lineTo(W - 42, 138);
  ctx.stroke();

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
  ctx.fillText("👑 本局真大腿 (MATCH MVP)", 482, 176);
  ctx.fillStyle = "#f2efe9";
  ctx.font = "bold 19px sans-serif";
  ctx.fillText(
    `${mvpPlayer?.personaname || ""} · ${mvpPlayer?.hero_short_zh || ""} (评分 ${mvpPlayer?.rating_score || 0})`,
    482,
    206
  );

  let y = 252;
  sortedBlame.forEach((p, idx) => {
    const isCulprit = idx === 0;
    ctx.fillStyle = isCulprit ? "#201715" : "#181a16";
    ctx.fillRect(42, y, W - 84, 58);
    ctx.strokeStyle = isCulprit ? "#8c3b2e" : "#2e3028";
    ctx.strokeRect(42, y, W - 84, 58);

    ctx.fillStyle = isCulprit ? "#e5897a" : "#c6a468";
    ctx.font = "bold 16px sans-serif";
    ctx.fillText(`#${idx + 1} [${p.pos_label}] ${p.hero_short_zh} · ${p.personaname}`, 56, y + 24);

    ctx.fillStyle = "#b5b1a6";
    ctx.font = "13px sans-serif";
    ctx.fillText(
      `KDA ${p.kda} (${p.kill_participation_pct}%) ｜ GPM ${p.gpm} ｜ 英雄伤害 ${fmtNum(
        p.hero_damage
      )} (${p.hero_damage_share_pct}%) ｜ 泉水读秒 ${p.dead_seconds || 0}秒`,
      56,
      y + 46
    );

    ctx.fillStyle = isCulprit ? "#ff8a75" : "#dfbe82";
    ctx.font = "bold 16px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`分锅 ${p.blame_share_pct}% · 评分 ${p.rating_score}`, W - 58, y + 34);
    ctx.textAlign = "left";

    y += 68;
  });

  ctx.fillStyle = "#9e9b91";
  ctx.font = "12px sans-serif";
  const tip =
    grok?.team_practice ||
    "前中期围绕核心第一件 BKB/跳刀出炉打主动开雾，拒绝无视野单带掉点。";
  ctx.fillText(`下把改进铁律：${tip.slice(0, 62)}`, 42, H - 32);
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


