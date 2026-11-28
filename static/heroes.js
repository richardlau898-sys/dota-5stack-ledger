(function () {
  "use strict";
  const ATTR = { 0: "力量", 1: "敏捷", 2: "智力", 3: "全才" };
  const MIN_WR_N = 20;
  let DATA = null, attr = "all", sel = null, scope = "all";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (v) => (v == null ? "—" : `${v}%`);
  const wrText = (wr, n) => (n >= MIN_WR_N && wr != null ? `胜率 <b>${wr}%</b>` : `<span class="low-n">胜率样本不足</span>`);
  const fmtDate = (t) => (t ? new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(t * 1000)) : "—");

  function renderGrid() {
    const q = $("q").value.trim().toLowerCase();
    const list = DATA.heroes.filter((h) => (attr === "all" || String(h.attr) === attr) &&
      (!q || h.zh.toLowerCase().includes(q) || h.en.toLowerCase().includes(q) || h.short.includes(q)));
    $("grid").innerHTML = list.map((h) => `
      <button class="tile${h.games < 12 ? " low" : ""}${sel && sel.id === h.id ? " sel" : ""}" data-id="${h.id}" title="${esc(h.zh)}（${h.games} 场）">
        <img src="${esc(h.img)}" alt="" loading="lazy"><em class="num">${h.games}</em><span>${esc(h.zh)}</span>
      </button>`).join("") || `<div class="empty">没有匹配的英雄</div>`;
  }

  function abilityMap(h) {
    const m = {};
    h.abilities.forEach((a, i) => { m[a.key] = Object.assign({ row: i }, a); });
    return m;
  }

  function skillsBlock(h, s) {
    const am = abilityMap(h);
    const pts = s.points;
    if (!pts.length) return `<p class="sub">样本不足，无法给出加点。</p>`;
    const head = pts.map((p) => `<th title="第 ${p.i} 次加点">${p.lvl == null ? "?" : p.lvl}</th>`).join("");
    const rows = h.abilities.map((a) => {
      const cells = pts.map((p) => {
        const t = p.top[0];
        if (t.k === a.key) return `<td class="on" title="${esc(a.zh)} · ${t.pct}% 的玩家在这一点加它">${Math.round(t.pct)}</td>`;
        const second = p.top[1];
        if (second && second.k === a.key && second.pct >= 25) return `<td class="weak" title="${esc(a.zh)} · ${second.pct}%">${Math.round(second.pct)}</td>`;
        return `<td></td>`;
      }).join("");
      return `<tr><td class="rowh"><img src="${esc(a.img)}" alt="">${esc(a.zh)}</td>${cells}</tr>`;
    }).join("");
    const talRow = `<tr><td class="rowh">天赋</td>${pts.map((p) => (p.top[0].k === "__talent__" ? `<td class="tal" title="${p.top[0].pct}% 的玩家在这一点点天赋">天</td>` : `<td></td>`)).join("")}</tr>`;
    const orders = (s.orders || []).map((o, idx) => `
      <div class="order"><span class="pill">常见顺序 ${idx + 1}</span>
        <span class="seq">${o.order.map((k) => (am[k] ? `<img src="${esc(am[k].img)}" alt="${esc(am[k].zh)}" title="${esc(am[k].zh)}">` : "")).join("")}</span>
        <span class="num">${o.pct}% · ${o.n} 场 · ${wrText(o.wr, o.n)}</span></div>`).join("");
    const maxFirst = (s.max_first || []).map((m) => `${esc((am[m.k] || {}).zh || m.k)} <span class="num">${m.pct}%</span>`).join("　");
    return `
      <div class="skills"><table class="sk"><thead><tr><th></th>${head}</tr></thead><tbody>${rows}${talRow}</tbody></table></div>
      <div class="orders">${maxFirst ? `<div class="order"><span class="pill">先主</span>${maxFirst}</div>` : ""}${orders}</div>`;
  }

  function talentsBlock(s) {
    const tiers = s.talents.slice().reverse();
    return `<div class="talents">${tiers.map((t) => {
      const [a, b] = t.options;
      const best = a && b && (a.n || 0) !== (b.n || 0) ? ((a.n || 0) > (b.n || 0) ? 0 : 1) : -1;
      const opt = (o, i) => !o ? `<div class="topt"></div>` : `
        <div class="topt${best === i ? " best" : ""}">${esc(o.zh)}
          <div class="bar"><i style="width:${o.pct || 0}%"></i></div>
          <div class="nums num">${t.taken ? `选择率 ${pct(o.pct)} · ${o.n} 场 · ${wrText(o.wr, o.n)}` : "暂无样本"}</div></div>`;
      return `<div class="trow">${opt(a, 0)}<div class="tlv">${t.level}</div>${opt(b, 1)}</div>`;
    }).join("")}</div>`;
  }

  function itemList(items, showPctLabel) {
    if (!items || !items.length) return `<div class="low-n">暂无样本</div>`;
    return items.map((i) => `
      <div class="it"><img src="${esc(i.img)}" alt="" loading="lazy"><span>${esc(i.zh)}</span>
        <span class="r num">${showPctLabel} <b>${pct(i.pct)}</b> · ${i.n} 场<br>${wrText(i.wr, i.n)}</span></div>`).join("");
  }

  function notesBlock(h) {
    const notes = h.patch_notes || [];
    if (!DATA.has_patch_notes) return "";
    if (!notes.length) return `<section class="panel block"><h2>本版本改动</h2><p class="sub">${esc(DATA.patch_name || "")} 官方更新日志里没有这个英雄的改动。</p></section>`;
    const groups = [];
    notes.forEach((n) => { const g = groups.find((x) => x.sec === n.sec); if (g) g.items.push(n); else groups.push({ sec: n.sec, items: [n] }); });
    return `<section class="panel block"><h2>本版本改动</h2>
      <p class="sub">来自 Valve 官方 ${esc(DATA.patch_name || "")} 中文更新日志，共 ${notes.length} 条。</p>
      <div class="notes">${groups.map((g) => `<div class="ng"><h3>${esc(g.sec)}</h3><ul>${g.items.map((n) => `<li>${esc(n.t)}${n.info ? `<span class="info">${esc(n.info)}</span>` : ""}</li>`).join("")}</ul></div>`).join("")}</div></section>`;
  }

  function renderDetail() {
    const h = sel;
    if (!h || !h.scopes) return;
    const scopes = h.scopes || {};
    if (!scopes[scope]) scope = "all";
    const s = scopes[scope];
    if (!s || !s.n) {
      $("detail").innerHTML = `<div class="panel empty">${esc(h.zh)} 在当前样本里还没有对局。</div>`;
      return;
    }
    const tabs = [["all", "全部"], ["core", "核心（推断）"], ["support", "辅助（推断）"]]
      .filter(([k]) => scopes[k]).map(([k, label]) => `<button class="chip${scope === k ? " on" : ""}" data-scope="${k}">${label} · ${scopes[k].n} 场</button>`).join("");
    const lowWarn = s.n < 30 ? `<div class="warn">样本只有 ${s.n} 场，下面的比例仅供参考；7.42 刚更新，样本会每天增加。</div>` : "";
    $("detail").innerHTML = `
      <div class="panel hero-head">
        <img src="${esc(h.img)}" alt="">
        <div>
          <h1>${esc(h.zh)}<small>${esc(h.en)} · ${ATTR[h.attr] || ""}</small></h1>
          <div class="stats">
            <div class="stat"><b class="num">${s.n}</b><span>样本场数</span></div>
            <div class="stat"><b class="num">${s.n >= MIN_WR_N ? pct(s.wr) : "—"}</b><span>胜率</span></div>
            <div class="stat"><b class="num">${pct(h.pick_pct)}</b><span>出场率</span></div>
            <div class="stat"><b class="num">${pct(s.scepter_pct)}</b><span>终局身上有 A 杖</span></div>
            <div class="stat"><b class="num">${pct(s.shard_pct)}</b><span>终局有魔晶</span></div>
          </div>
          <div class="tabs">${tabs}</div>${lowWarn}
        </div>
      </div>
      ${notesBlock(h)}
      <section class="panel block"><h2>技能加点</h2>
        <p class="sub">表头是英雄等级；格子里的数字是在这一次加点选这个技能的玩家比例，金框为最多人的选择，淡框为第二选择（≥25%）。</p>
        ${skillsBlock(h, s)}</section>
      <section class="panel block"><h2>天赋</h2>
        <p class="sub">金框为选择更多的一侧。比例只统计点了这一级天赋的对局。</p>
        ${talentsBlock(s)}</section>
      <section class="panel block"><h2>中立物品</h2>
        <p class="sub">比赛结束时携带的那一件，按等级分开统计；比例为同等级内的占比。</p>
        <div class="cols">${(s.neutral || []).map((t) => `<div class="col"><h3>${t.tier} 级<span>${t.n} 场</span></h3>${itemList(t.items, "")}</div>`).join("") || `<div class="low-n">暂无样本</div>`}</div></section>
      <section class="panel block"><h2>附魔</h2>
        <p class="sub">比赛结束时的附魔，${s.ench.n} 场有记录。</p>
        <div class="cols"><div class="col">${itemList(s.ench.items, "")}</div></div></section>
      <section class="panel block"><h2>终局出装</h2>
        <p class="sub">比赛结束时身上和背包里的装备（不含消耗品和便宜的小件）；比例为该英雄样本里出了这件的场数占比。</p>
        <div class="cols">
          <div class="col"><h3>核心装备</h3>${itemList(s.items, "出装率")}</div>
          <div class="col"><h3>鞋子</h3>${itemList(s.boots, "")}</div>
        </div></section>`;
    $("detail").querySelectorAll("[data-scope]").forEach((b) => b.addEventListener("click", () => { scope = b.dataset.scope; renderDetail(); }));
  }

  const heroCache = {};
  function pick(id) {
    const base = DATA.heroes.find((h) => h.id === id) || null;
    if (!base) return;
    sel = base;
    scope = "all";
    renderGrid();
    const show = (full) => { if (sel && sel.id === id) { sel = Object.assign({}, base, full); renderDetail(); } };
    if (heroCache[id]) show(heroCache[id]);
    else {
      $("detail").innerHTML = `<div class="panel empty">正在加载 ${esc(base.zh)}…</div>`;
      fetch(`/api/hero_builds/${id}`)
        .then((r) => r.json().then((body) => { if (!r.ok || !body.ok) throw new Error(body.error || r.status); return body.hero; }))
        .then((full) => { heroCache[id] = full; show(full); })
        .catch(() => { if (sel && sel.id === id) $("detail").innerHTML = `<div class="panel empty">${esc(base.zh)} 的数据加载失败，请重试。</div>`; });
    }
    try { history.replaceState(null, "", `#${sel.short}`); } catch (e) { /* ignore */ }
    if (window.innerWidth < 860) $("detail").scrollIntoView({ behavior: "smooth" });
  }

  function init(d) {
    DATA = d;
    const tiers = Object.entries(d.rank_tier_mix || {}).map(([k, v]) => `${{ 6: "超凡", 7: "神话", 8: "冠绝" }[k] || k}${v}`).join(" / ");
    $("meta").innerHTML = `版本 <b>${esc(d.patch_name || "未知")}</b>（OpenDota 补丁编号 ${d.patch_id}）· 天梯全英雄选择 · ${tiers} · 共 <b>${d.matches}</b> 场 · 对局时间 ${fmtDate(d.first_match_time)} 至 ${fmtDate(d.last_match_time)} · 生成于 ${fmtDate(d.generated_at)}`;
    $("attrs").innerHTML = [["all", "全部"], ["0", "力量"], ["1", "敏捷"], ["2", "智力"], ["3", "全才"]]
      .map(([k, l]) => `<button class="chip${attr === k ? " on" : ""}" data-attr="${k}">${l}</button>`).join("");
    $("attrs").addEventListener("click", (e) => {
      const b = e.target.closest("[data-attr]"); if (!b) return;
      attr = b.dataset.attr; $("attrs").querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === b)); renderGrid();
    });
    $("q").addEventListener("input", renderGrid);
    $("grid").addEventListener("click", (e) => { const t = e.target.closest("[data-id]"); if (t) pick(Number(t.dataset.id)); });
    $("foot").innerHTML = `数据来源：OpenDota 公开天梯比赛（加点、终局装备、中立物品、附魔）；中文名、中立物品等级和版本改动来自 Valve 官方数据。${esc(d.role_note)}。${esc(d.neutral_note)}。胜率在样本少于 ${MIN_WR_N} 场时不显示。Dota 2 是 Valve 公司的商标，本站为玩家自用工具，与 Valve 无关。`;
    renderGrid();
    const openFromHash = () => {
      const hash = decodeURIComponent(location.hash.slice(1));
      const target = d.heroes.find((h) => h.short === hash) || null;
      if (target && (!sel || sel.id !== target.id)) pick(target.id);
    };
    window.addEventListener("hashchange", openFromHash);
    openFromHash();
  }

  fetch("/api/hero_builds")
    .then((r) => r.json().then((body) => ({ ok: r.ok && body.ok, body })))
    .then(({ ok, body }) => {
      if (!ok) { $("meta").textContent = body.error || "攻略数据加载失败，请稍后刷新。"; return; }
      init(body.index);
      if (body.stale) $("meta").insertAdjacentHTML("beforeend", ` · <span class="stale">数据更新暂时失败，显示的是上一次的数据</span>`);
    })
    .catch(() => { $("meta").textContent = "攻略数据加载失败，请稍后刷新。"; });
})();
