// ES Module: 全屏报告与 PDF 打印样式导出（复用页面 DOM + @media print）
import { state, getAuditedSide } from "./state_api.js";

export function buildStructuredFullReportHtmlFromDom(report, ranking, escapeHtmlFn = (s) => String(s ?? "")) {
  if (!report) return "";
  const side = getAuditedSide(report);
  const sideZh = side === "radiant" ? "天辉" : "夜魇";
  const ownWon = Boolean(ranking?.ownWon);
  const mvpP = ranking?.mvpPlayer;
  const culpritP = ranking?.culpritPlayer;
  const headlinePlayer = ownWon ? mvpP : culpritP;
  const headlineHero = headlinePlayer?.hero_short_zh || headlinePlayer?.hero_name || "未知英雄";
  const headlinePersona = headlinePlayer?.personaname || "匿名玩家";

  const domSectionIds = [
    "ws-top3-fixes-container",
    "ws-top3-replay-moments",
    "ws-factcheck-section",
    "verdict-and-blame-section",
    "draft-and-phases-section",
    "windows-section",
    "tactical-microscope-section",
    "players-forensics-section",
  ];
  const reusedDomBlocks = domSectionIds
    .map((id) => {
      const el = typeof document !== "undefined" ? document.getElementById(id) : null;
      return el && el.innerHTML ? `<section class="fs-reused-dom-block" data-source-id="${id}">${el.innerHTML}</section>` : "";
    })
    .filter(Boolean)
    .join("\n");

  return `
    <article class="fs-dom-reuse-report print-ready-dossier">
      <header class="fs-dom-reuse-header">
        <div class="fs-dom-meta">比赛 #${escapeHtmlFn(report.match_id)} · ${sideZh}视角 · ${escapeHtmlFn(report.duration_str || "")}</div>
        <h1 class="fs-dom-title">${sideZh}${ownWon ? "凯旋庆功" : "败局复盘"}报告 · 焦点：${escapeHtmlFn(headlineHero)} (${escapeHtmlFn(headlinePersona)})</h1>
        <p class="fs-dom-sub">頭号首功 MVP：${escapeHtmlFn(mvpP?.hero_short_zh || "")} (${escapeHtmlFn(mvpP?.personaname || "")}) ｜ 重点复盘对象：${escapeHtmlFn(culpritP?.hero_short_zh || "")} (${escapeHtmlFn(culpritP?.personaname || "")})</p>
      </header>
      <div class="fs-dom-reuse-body">
        ${reusedDomBlocks}
      </div>
    </article>
  `;
}

export function triggerNativePrintReport(report = state.currentReport) {
  if (!report || typeof window === "undefined") return;
  if (typeof window.print === "function") {
    window.print();
  }
}
