import {
  escapeHtml as e,
  money,
  formatTime,
  safeUrl,
  filterModels,
  matchScore,
  refreshModels,
  toCsv,
  historyGroups,
  latestOfferChange,
} from "./lib.js";

const $ = (selector) => document.querySelector(selector);
const statuses = {
  verified: "已核验",
  needs_review: "待核验",
  stale: "旧数据 / 待更新",
  expired: "已过期",
};
const kinds = {
  official_promotional_reference: "官网公开优惠后参考价 / TP 参考",
  msrp: "官方 MSRP / RRP 指导价",
  dealer_offer: "经销商报价",
  verified_transaction: "已证明的成交 TP",
};
let dataset,
  history = { observations: [], changes: [] },
  shown = [],
  currentPage = "catalog",
  days = 30,
  detailId = null;
const badge = (status) =>
  `<span class="badge ${e(status)}">${e(statuses[status] || status)}</span>`;
const sourceLink = (url) =>
  `<a href="${e(safeUrl(url))}" target="_blank" rel="noopener noreferrer">查看官方来源 ↗</a>`;
const typeLabel = (o) =>
  o.source_type === "manual_verified"
    ? "经人工审核导入"
    : o.source_type === "official_pdf"
      ? "官方 PDF 自动采集"
      : "官方网页自动采集";
function years(o) {
  return `${o.model_year ? `${o.model_year} 年款` : "年款未公布"} · ${o.production_year ? `${o.production_year} 年生产` : "生产年未公布"}`;
}
function latestChange(model, offer) {
  return latestOfferChange(history, model.model_id, offer);
}
function renderStats() {
  $("#brand-count").textContent = dataset.brands.length;
  $("#model-count").textContent = dataset.models.length;
  const count = dataset.models.filter((m) => m.status === "verified").length;
  $("#verified-count").textContent = count;
  $("#pending-count").textContent = dataset.models.length - count;
  $("#updated").textContent = formatTime(dataset.generated_at);
}
function dropdown() {
  const previous = $("#model").value;
  const models = dataset.models.filter(
    (m) =>
      (!$("#brand").value || m.brand_id === $("#brand").value) &&
      matchScore(m, $("#keyword").value, dataset.brands) > 0,
  );
  $("#model").innerHTML =
    '<option value="">全部车型 / 所有候选</option>' +
    models
      .map(
        (m) =>
          `<option value="${e(m.model_id)}">${e(m.brand_id.toUpperCase())} · ${e(m.name)}</option>`,
      )
      .join("");
  if (models.some((m) => m.model_id === previous)) $("#model").value = previous;
}
function card(m) {
  const brand = dataset.brands.find((b) => b.brand_id === m.brand_id);
  const o = m.promo.min_offer,
    msrp = m.msrp.min_offer;
  const old = m.offers.find(
    (o) => o.price_kind === "official_promotional_reference",
  );
  return `<article class="price-card ${e(m.status)}"><div class="card-top"><span class="brand-name">${e(brand.name_en)} / ${e(brand.name_zh)}</span>${badge(m.status)}</div><h3>${e(m.name)}</h3><div class="model-meta">${e(o ? years(o) : msrp ? years(msrp) : "官方新乘用车 · 价格等待核验")}</div><div class="price-label">官网公开优惠后参考价 / TP 参考</div><div class="price ${o ? "" : "pending"}">${o ? `${money(o.price_rub)}<small>₽${o.price_basis === "starting_at" ? " 起" : ""}</small>` : "暂未核验价格"}</div><div class="price-note">${o ? (m.promo.max_rub && m.promo.max_rub !== m.promo.min_rub ? `已收录配置：${money(m.promo.min_rub)} – ${money(m.promo.max_rub)} ₽` : "仅已核验配置，最高价未核验") : old ? `保留上次记录，当前${e(statuses[old.status])}` : "不使用广告数字推断成交价"}<br>MSRP：${msrp ? `${money(msrp.price_rub)} ₽ 起` : "未核验 / 未公布"}</div><div class="tags">${
    o
      ? (o.condition_labels.length ? o.condition_labels : ["查看报价条件"])
          .slice(0, 3)
          .map((t) => `<span class="tag">${e(t)}</span>`)
          .join("")
      : '<span class="tag">等待完整价格证据</span>'
  }</div><div class="card-bottom"><span>${e(latestChange(m, o))}</span><button data-detail="${e(m.model_id)}">条件与来源 ↗</button></div></article>`;
}
function renderCatalog() {
  shown = filterModels(
    dataset.models,
    {
      brand: $("#brand").value,
      query: $("#keyword").value,
      modelId: $("#model").value,
      sort: $("#sort").value,
    },
    dataset.brands,
  );
  $("#result-count").textContent = shown.length;
  $("#cards").innerHTML = shown.length
    ? shown.map(card).join("")
    : '<div class="empty">没有匹配车型。<br>试试更短的关键词，或切换到全部品牌。</div>';
}
function renderSources() {
  $("#sources").innerHTML = dataset.sources
    .map((s) => {
      const b = dataset.brands.find((b) => b.brand_id === s.brand_id);
      return `<article class="source-card"><h3>${e(b.name_en)} ${badge(s.verified_models.length ? "verified" : "needs_review")}</h3><p>当前核验覆盖：${s.verified_models.length ? e(s.verified_models.map((id) => dataset.models.find((m) => m.model_id === id)?.name || id).join("、")) : "暂无完整价格证据"}</p><p>${e(s.reason)}</p><small>最近尝试：${formatTime(s.last_run?.at)} · ${e(s.last_run?.status || "尚未运行")}</small>${sourceLink(s.source_url)}<details><summary>解析器与允许的官方域名</summary>${e(s.adapter)} v${e(s.parser_version)}<br>${s.allowed_hosts.map(e).join("<br>")}</details></article>`;
    })
    .join("");
}
function chartGroup(group) {
  const first = group[0].offer;
  const label = `${first.trim} · ${first.production_year || first.model_year || "年款未公布"} · ${first.price_kind === "msrp" ? "MSRP" : "TP 参考"}`;
  if (new Set(group.map((o) => o.day)).size < 2)
    return `<div class="chart-box"><h3>${e(label)}</h3><div class="empty">历史数据积累中<br>至少需要两个不同日期的可比核验记录。</div></div>`;
  const vals = group.map((o) => o.offer.price_rub),
    low = Math.min(...vals),
    high = Math.max(...vals),
    span = high - low || Math.max(low * 0.01, 1),
    start = new Date(group[0].at).getTime(),
    end = new Date(group.at(-1).at).getTime();
  const points = group.map((o) => [
    65 + ((new Date(o.at).getTime() - start) / (end - start || 1)) * 525,
    175 - ((o.offer.price_rub - low) / span) * 130,
  ]);
  const ticks = [low, low + span * 0.5, low + span];
  return `<div class="chart-box"><h3>${e(label)}</h3><svg viewBox="0 0 650 225" role="img" aria-label="${e(label)}的同口径价格历史">${ticks.map((t, i) => `<line x1="65" y1="${175 - i * 65}" x2="590" y2="${175 - i * 65}" stroke="#e4e9df"/><text x="57" y="${179 - i * 65}" text-anchor="end" font-size="10" fill="#738079">${(t / 10000).toFixed(1)}万</text>`).join("")}<polyline points="${points.map((p) => p.join(",")).join(" ")}" fill="none" stroke="#57765a" stroke-width="2"/>${points.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#57765a"><title>${e(group[i].at.slice(0, 10))}：${money(vals[i])} ₽</title></circle>`).join("")}<text x="65" y="207" font-size="10" fill="#738079">${e(group[0].day)}</text><text x="590" y="207" text-anchor="end" font-size="10" fill="#738079">${e(group.at(-1).day)}</text></svg><small>单位 RUB ₽ · 条件一致的独立序列；不同口径不连线。</small></div>`;
}
function historyHtml(id, period) {
  const groups = historyGroups(history.observations, id, period),
    cutoff = Date.now() - period * 86400000;
  const changes = history.changes
    .filter((c) => c.model_id === id && new Date(c.at).getTime() >= cutoff)
    .slice()
    .reverse();
  return (
    (groups.length
      ? groups.map(chartGroup).join("")
      : '<div class="empty">历史数据积累中<br>该车型尚无可比核验记录。</div>') +
    `<h3 style="font-size:14px;margin-top:25px">变动记录</h3>` +
    (changes.length
      ? changes
          .map(
            (c) =>
              `<div class="log-row"><time>${formatTime(c.at)}</time><span>${e(c.offer.trim)} · ${c.offer.price_kind === "msrp" ? "MSRP" : "TP 参考"}<small>${e(c.kind === "scope_change" ? "年款、配置、有效期或条件发生变化，不计算涨跌" : c.kind === "baseline" ? "首次取得价格证据" : "同口径价格变动")}</small></span><span>${c.kind === "scope_change" ? "口径变更" : c.kind === "baseline" ? `${money(c.offer.price_rub)} ₽` : `${c.delta_rub >= 0 ? "+" : "−"}${money(Math.abs(c.delta_rub))} ₽ (${c.delta_percent >= 0 ? "+" : ""}${Number(c.delta_percent).toFixed(2)}%)`}</span></div>`,
          )
          .join("")
      : '<div class="empty">此时间段没有价格变动记录。</div>')
  );
}
function offerHtml(o) {
  return `<article class="offer"><div class="card-top"><h3>${e(kinds[o.price_kind])}</h3>${badge(o.status)}</div><div class="price">${money(o.price_rub)} <small>₽${o.price_basis === "starting_at" ? " 起" : ""}</small></div><dl><dt>车型口径</dt><dd>${e(years(o))} · ${e(o.trim)}</dd><dt>报价条件</dt><dd>${e(o.condition_labels.join(" / ") || "详见官方原文")}</dd><dt>地区</dt><dd>${e(o.region)}</dd><dt>有效期</dt><dd>${e(o.effective_date || "起始日未公布")} 至 ${e(o.valid_until || "结束日未公布；以官方确认为准")}</dd><dt>核验时间</dt><dd>${formatTime(o.verified_at)} · ${e(typeLabel(o))}</dd><dt>最后成功</dt><dd>${formatTime(o.last_success_at || o.verified_at)}</dd><dt>价格来源</dt><dd>${sourceLink(o.source_url)}</dd>${o.failure_reason ? `<dt>更新失败</dt><dd>${e(o.failure_reason)}</dd>` : ""}</dl><details><summary>查看完整俄文条件与原始价格</summary><div class="raw-conditions" lang="ru">${e(o.conditions)}</div><p>原始价格：${e(o.raw_price)} · ${e(o.price_basis === "starting_at" ? "广告起价，仅该配置下限" : "已核验配置价格")}<br>证据 SHA-256：${e(o.evidence_sha256)}</p></details></article>`;
}
function openDetail(id) {
  detailId = id;
  const m = dataset.models.find((m) => m.model_id === id);
  if (!m) return;
  const source = dataset.sources.find((s) => s.brand_id === m.brand_id);
  $("#detail-body").innerHTML =
    `<span class="brand-name">${e(m.brand_id.toUpperCase())}</span><h2>${e(m.name)}</h2><p>官网公开优惠后参考价用于 TP 参考，不代表真实成交价。区间仅覆盖已收录配置。</p>${m.promo.min_rub !== null ? `<div class="detail-range">已核验配置参考价：${money(m.promo.min_rub)} ₽${m.promo.max_rub ? ` – ${money(m.promo.max_rub)} ₽` : " 起 / 最高价未核验"}</div>` : ""}${
      m.offers.length
        ? m.offers
            .slice()
            .sort(
              (a, b) =>
                Number(a.price_kind === "msrp") -
                  Number(b.price_kind === "msrp") || a.price_rub - b.price_rub,
            )
            .map(offerHtml)
            .join("")
        : `<div class="empty">暂未核验价格<br>${e(source.reason)}<br>${sourceLink(source.source_url)}</div>`
    }<h3 style="font-size:15px;margin-top:24px">历史趋势</h3><div class="range-buttons" id="detail-range"><button data-days="7">7 天</button><button data-days="30" class="selected">30 天</button><button data-days="90">90 天</button></div><div id="detail-history">${historyHtml(id, 30)}</div>`;
  if (!$("#detail").open) $("#detail").showModal();
}
function showPage(name) {
  currentPage = name;
  document
    .querySelectorAll(".page")
    .forEach((el) => (el.hidden = el.id !== `${name}-page`));
  document
    .querySelectorAll("[data-page]")
    .forEach((b) => b.classList.toggle("active", b.dataset.page === name));
  $("#page-label").textContent = {
    catalog: "车型价格",
    changes: "变动日志",
    sources: "数据来源",
  }[name];
  if (name === "changes")
    $("#history-content").innerHTML = historyHtml(
      $("#history-model").value,
      days,
    );
}
function offlineNotice() {
  if (!navigator.onLine) {
    $("#data-notice").classList.add("offline");
    $("#data-notice").innerHTML =
      '<span class="notice-icon">i</span><div><strong>离线旧快照</strong><span>当前查看的是缓存数据。报价按原核验时间计算有效性，请联网刷新后确认价格。</span></div>';
  }
}
async function boot() {
  try {
    const [currentResponse, historyResponse] = await Promise.all([
      fetch("./data/current.json", { cache: "no-cache" }),
      fetch("./data/history.json", { cache: "no-cache" }).catch(() => null),
    ]);
    if (!currentResponse.ok) throw new Error("价格数据暂时无法读取");
    dataset = await currentResponse.json();
    if (dataset.schema_version !== 1 || !Array.isArray(dataset.models))
      throw new Error("数据格式暂时不可用");
    dataset.models = refreshModels(dataset.models);
    for (const s of dataset.sources)
      s.verified_models = dataset.models
        .filter((m) => m.brand_id === s.brand_id && m.status === "verified")
        .map((m) => m.model_id);
    if (historyResponse?.ok) {
      try {
        history = await historyResponse.json();
      } catch {
        history = { observations: [], changes: [] };
      }
    }
    $("#load-status").textContent = "";
    renderStats();
    $("#brand").innerHTML += [...dataset.brands]
      .map(
        (b) =>
          `<option value="${e(b.brand_id)}">${e(b.name_en)} · ${e(b.name_zh)}</option>`,
      )
      .join("");
    $("#history-model").innerHTML = dataset.models
      .map(
        (m) =>
          `<option value="${e(m.model_id)}">${e(m.brand_id.toUpperCase())} · ${e(m.name)}</option>`,
      )
      .join("");
    const first = dataset.models.find((m) => m.status === "verified");
    if (first) $("#history-model").value = first.model_id;
    dropdown();
    renderCatalog();
    renderSources();
    offlineNotice();
    setInterval(() => {
      dataset.models = refreshModels(dataset.models);
      renderStats();
      renderCatalog();
      if (detailId && $("#detail").open) openDetail(detailId);
    }, 60000);
  } catch (error) {
    $("#load-status").innerHTML =
      `${e(error.message)}。<button id="retry" class="secondary">重新加载</button>`;
    $("#cards").innerHTML =
      '<div class="empty">暂时无法加载记录。请检查网络后重试。</div>';
    $("#retry").onclick = () => location.reload();
  }
}
$("#brand").addEventListener("change", () => {
  if (!dataset) return;
  $("#keyword").value = "";
  $("#model").value = "";
  dropdown();
  renderCatalog();
});
$("#keyword").addEventListener("input", () => {
  if (!dataset) return;
  $("#model").value = "";
  dropdown();
  renderCatalog();
});
$("#query-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (dataset) renderCatalog();
});
$("#sort").addEventListener("change", () => {
  if (dataset) renderCatalog();
});
$("#cards").addEventListener("click", (event) => {
  const button = event.target.closest("[data-detail]");
  if (button) openDetail(button.dataset.detail);
});
document.querySelectorAll("[data-page]").forEach(
  (b) =>
    (b.onclick = () => {
      if (dataset) showPage(b.dataset.page);
    }),
);
$("#export").onclick = () => {
  if (!dataset) return;
  const url = URL.createObjectURL(
    new Blob([toCsv(shown)], { type: "text/csv;charset=utf-8;" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `russia-auto-prices-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$("#history-model").onchange = () => {
  if (dataset)
    $("#history-content").innerHTML = historyHtml(
      $("#history-model").value,
      days,
    );
};
$("#history-range").onclick = (event) => {
  const b = event.target.closest("[data-days]");
  if (!b || !dataset) return;
  days = Number(b.dataset.days);
  $("#history-range")
    .querySelectorAll("button")
    .forEach((x) => x.classList.toggle("selected", x === b));
  $("#history-content").innerHTML = historyHtml(
    $("#history-model").value,
    days,
  );
};
$("#detail-body").onclick = (event) => {
  const b = event.target.closest("#detail-range [data-days]");
  if (!b) return;
  $("#detail-range")
    .querySelectorAll("button")
    .forEach((x) => x.classList.toggle("selected", x === b));
  $("#detail-history").innerHTML = historyHtml(
    detailId,
    Number(b.dataset.days),
  );
};
$("#close-detail").onclick = () => $("#detail").close();
$("#install-help").onclick = () => $("#install").showModal();
$("#install-help-mobile").onclick = () => $("#install").showModal();
$("#close-install").onclick = () => $("#install").close();
for (const dialog of document.querySelectorAll("dialog"))
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (
        event.clientX < r.left ||
        event.clientX > r.right ||
        event.clientY < r.top ||
        event.clientY > r.bottom
      )
        dialog.close();
    }
  });
window.addEventListener("offline", offlineNotice);
window.addEventListener("online", () => location.reload());
if ("serviceWorker" in navigator)
  navigator.serviceWorker.register("./sw.js").catch(() => {});
boot();
