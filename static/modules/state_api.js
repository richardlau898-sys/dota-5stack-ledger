// ES Module: 状态管理、语气模式与后端接口契约 (State & API Module)
export const state = {
  accountId: null,
  roster: null,
  profileData: null,
  squadLedger: null,
  heroesCatalog: [],
  workspaceMode: "postgame",
  homeFilter: "all",
  wsSidebarFilter: "all",
  wsSidebarCollapsed: false,
  wsPostgameTab: "summary",
  pregameOwnPicks: [
    { pos: 1, hero_id: 8, player_name: "" },
    { pos: 2, hero_id: 45, player_name: "" },
    { pos: 3, hero_id: 97, player_name: "" },
    { pos: 4, hero_id: 9, player_name: "" },
    { pos: 5, hero_id: 26, player_name: "" },
  ],
  pregameEnemyPicks: [
    { pos: 1, hero_id: 44 },
    { pos: 2, hero_id: 76 },
    { pos: 3, hero_id: 29 },
    { pos: 4, hero_id: 86 },
    { pos: 5, hero_id: 5 },
  ],
  pregameActiveSide: "own",
  pregameActivePos: 1,
  pregameHeroQuery: "",
  pregamePlan: null,
  isGeneratingPregameGrok: false,
  currentMatchId: null,
  currentReport: null,
  pendingMatchId: null,
  pendingMatchMeta: null,
  scrubberMinute: 15,
  scrubberSecond: 900,
  scrubSyncMapMinute: null,
  scrubberPlaying: false,
  scrubberSpeed: 1,
  scrubberTimer: null,
  perspective: "auto",
  toneMode: "coach",
  nwFilter: "cores",
  mapMode: "wards_obs",
  selectedTeamfightIndex: null,
  focusMatrixSide: "own",
  microTab: "hero_ult",
  microSide: "own",
  activePhaseKey: "lane",
  activeTeamTab: "own",
  verdictActiveCard: "focus",
  phaseSelectedPos: "focus",
  tfActiveWaveIdx: 0,
  tfSelectedPosMap: {},
  microExecSelectedPos: "focus",
  forensicSelectedSlot: "focus",
  llmStatus: null,
  isGeneratingGrok: false,
  posterArtCache: new Map(),
};

export function applyToneModeUI(appState = state) {
  const isRoast = appState.toneMode === "roast";
  if (typeof document !== "undefined" && document.body && document.body.dataset) {
    document.body.dataset.toneMode = appState.toneMode;
  }
  const toneBtn = typeof document !== "undefined" ? document.getElementById("btn-toggle-tone-mode") : null;
  if (toneBtn) {
    toneBtn.setAttribute("data-tone-mode", appState.toneMode);
    toneBtn.textContent = isRoast ? "🌶️ 毒舌模式" : "🎓 教练模式";
    toneBtn.classList?.toggle("active", isRoast);
  }
  if (typeof document !== "undefined") {
    ["btn-open-share-poster", "btn-open-share-poster-2"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.hidden = !isRoast;
    });
    document
      .querySelectorAll("[data-player-poster-slot], [data-habit-poster-idx]")
      .forEach((btn) => {
        btn.hidden = !isRoast;
      });
  }
}

export function getAuditedSide(report, appState = state) {
  if (!report) return "dire";
  if (appState.perspective === "dire" || appState.perspective === "radiant") {
    return appState.perspective;
  }
  if (report.focus_side === "radiant" || report.focus_side === "dire") {
    return report.focus_side;
  }
  return "dire";
}

export async function apiFetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `请求失败 (${res.status})`);
  }
  return data;
}
