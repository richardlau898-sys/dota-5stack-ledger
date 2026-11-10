// ES Module: 各标签页与工作台切换渲染器 (Tab & Workspace Renderers)
import { state, applyToneModeUI } from "./state_api.js";

export const POSTGAME_TAB_SECTION_MAP = {
  summary: ["ws-top3-fixes-container", "ws-top3-replay-moments", "ws-factcheck-section", "verdict-and-blame-section"],
  timeline: ["charts-hub-section"],
  phases: ["draft-and-phases-section", "windows-section"],
  microscope: ["tactical-microscope-section"],
  players: ["players-forensics-section"],
  all: [
    "ws-top3-fixes-container",
    "ws-top3-replay-moments",
    "ws-factcheck-section",
    "verdict-and-blame-section",
    "charts-hub-section",
    "draft-and-phases-section",
    "windows-section",
    "tactical-microscope-section",
    "players-forensics-section",
  ],
};

export function getVisibleSectionIdsForTab(tabKey = state.wsPostgameTab) {
  return POSTGAME_TAB_SECTION_MAP[tabKey] || POSTGAME_TAB_SECTION_MAP.summary;
}

export function syncPostgameTabButtons(activeTab = state.wsPostgameTab) {
  if (typeof document === "undefined") return;
  document.querySelectorAll("[data-postgame-tab]").forEach((btn) => {
    const t = btn.getAttribute("data-postgame-tab");
    const isAct = t === activeTab;
    btn.classList.toggle("is-active", isAct);
    btn.setAttribute("aria-selected", isAct ? "true" : "false");
  });
  applyToneModeUI(state);
}
