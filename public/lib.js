export const normalize = (text) =>
  String(text ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
export const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const money = (value) =>
  Number.isFinite(value)
    ? new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value)
    : "未核验";
export const formatTime = (value) =>
  value
    ? new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(value))
    : "未核验";
export function safeUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password ? u.href : "#";
  } catch {
    return "#";
  }
}
export function distance(a, b) {
  let row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const next = [i];
    for (let j = 1; j <= b.length; j++)
      next[j] = Math.min(
        next[j - 1] + 1,
        row[j] + 1,
        row[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    row = next;
  }
  return row[b.length];
}
export function matchScore(model, query, brands = []) {
  const q = normalize(query);
  if (!q) return 1;
  const brand = brands.find((b) => b.brand_id === model.brand_id);
  const aliases = [
    model.name,
    ...model.aliases,
    ...(brand ? [brand.name_en, brand.name_zh, ...brand.aliases] : []),
  ].map(normalize);
  if (aliases.includes(q)) return 5;
  if (aliases.some((a) => a.startsWith(q))) return 4;
  if (aliases.some((a) => a.includes(q))) return 3;
  const digits = q.replace(/\D/g, "");
  if (
    q.length >= 3 &&
    aliases.some(
      (a) =>
        (!digits || a.replace(/\D/g, "") === digits) &&
        distance(a, q) <= Math.max(1, Math.floor(q.length * 0.2)),
    )
  )
    return 2;
  return 0;
}
export function filterModels(
  models,
  { brand = "", query = "", modelId = "", sort = "default" } = {},
  brands = [],
) {
  const selected = models.filter(
    (m) =>
      (!brand || m.brand_id === brand) &&
      (!modelId || m.model_id === modelId) &&
      matchScore(m, query, brands) > 0,
  );
  return selected.sort((a, b) => {
    const ap = a.promo.min_rub ?? a.msrp.min_rub,
      bp = b.promo.min_rub ?? b.msrp.min_rub;
    if (sort === "name") return a.name.localeCompare(b.name);
    if (ap === null && bp !== null) return 1;
    if (bp === null && ap !== null) return -1;
    if (sort === "asc" || sort === "desc")
      return ap === bp
        ? a.name.localeCompare(b.name)
        : (ap - bp) * (sort === "desc" ? -1 : 1);
    return (
      Number(b.status === "verified") - Number(a.status === "verified") ||
      matchScore(b, query, brands) - matchScore(a, query, brands) ||
      a.brand_id.localeCompare(b.brand_id) ||
      a.name.localeCompare(b.name)
    );
  });
}
export function offerStatus(offer, now = new Date()) {
  const day = new Date(now.getTime() + 3 * 3600000).toISOString().slice(0, 10);
  if (offer.valid_until && offer.valid_until < day) return "expired";
  if (offer.effective_date && offer.effective_date > day) return "needs_review";
  if (now - new Date(offer.verified_at) > 3 * 86400000) return "stale";
  return offer.status;
}
export function refreshModels(models, now = new Date()) {
  return models.map((m) => {
    const offers = m.offers.map((o) => ({ ...o, status: offerStatus(o, now) }));
    const bounds = (kind) => {
      const rows = offers
        .filter((o) => o.price_kind === kind && o.status === "verified")
        .sort((a, b) => a.price_rub - b.price_rub);
      return {
        min_rub: rows[0]?.price_rub ?? null,
        max_rub:
          rows.length && rows.every((o) => o.price_basis === "exact_trim")
            ? rows.at(-1).price_rub
            : null,
        min_offer: rows[0] ?? null,
        max_offer:
          rows.length && rows.every((o) => o.price_basis === "exact_trim")
            ? rows.at(-1)
            : null,
        coverage: "observed_trims_only",
      };
    };
    const status = offers.some((o) => o.status === "verified")
      ? "verified"
      : offers.some((o) => o.status === "stale")
        ? "stale"
        : offers.some((o) => o.status === "expired")
          ? "expired"
          : "needs_review";
    return {
      ...m,
      offers,
      status,
      promo: bounds("official_promotional_reference"),
      msrp: bounds("msrp"),
    };
  });
}
export function csvCell(value) {
  let text = String(value ?? "");
  if (/^[\s\x00-\x1f]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text))
    text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
export function toCsv(models) {
  const headers = [
    "品牌",
    "车型",
    "价格口径",
    "RUB价格",
    "价格状态",
    "年款",
    "生产年",
    "配置",
    "条件",
    "地区",
    "生效日",
    "到期日",
    "核验时间",
    "来源",
    "来源类型",
    "金额口径",
  ];
  const rows = [headers];
  for (const m of models) {
    if (!m.offers.length) rows.push([m.brand_id, m.name, "", null, m.status]);
    for (const o of m.offers)
      rows.push([
        m.brand_id,
        m.name,
        o.price_kind,
        o.price_rub,
        o.status,
        o.model_year,
        o.production_year,
        o.trim,
        o.conditions,
        o.region,
        o.effective_date,
        o.valid_until,
        o.verified_at,
        o.source_url,
        o.source_type,
        o.price_basis,
      ]);
  }
  return (
    "\ufeff" +
    rows
      .map((row) => headers.map((_, i) => csvCell(row[i])).join(","))
      .join("\r\n")
  );
}
export function historyGroups(observations, modelId, days, now = new Date()) {
  const cutoff = now.getTime() - days * 86400000,
    groups = new Map();
  for (const o of observations
    .filter((o) => o.model_id === modelId && new Date(o.at).getTime() >= cutoff)
    .sort((a, b) => a.at.localeCompare(b.at))) {
    const key = o.comparison_key;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(o);
  }
  return [...groups.values()];
}
export function latestOfferChange(history, modelId, offer) {
  if (!offer) return "暂无可比价格";
  const rows = history.observations
    .filter(
      (o) =>
        o.model_id === modelId &&
        o.offer.trim === offer.trim &&
        o.offer.price_kind === offer.price_kind,
    )
    .slice()
    .sort((a, b) => a.at.localeCompare(b.at));
  if (rows.length >= 2) {
    const previous = rows.at(-2),
      latest = rows.at(-1);
    if (latest.offer.price_rub !== offer.price_rub) return "历史数据同步中";
    if (previous.comparison_key !== latest.comparison_key) return "口径变更";
    const delta = latest.offer.price_rub - previous.offer.price_rub;
    if (delta === 0) return "与上次可比核验持平";
    return `${delta >= 0 ? "+" : "−"}${money(Math.abs(delta))} ₽ (${delta >= 0 ? "+" : ""}${((delta / previous.offer.price_rub) * 100).toFixed(2)}%)`;
  }
  const event = history.changes
    .filter(
      (c) =>
        c.model_id === modelId &&
        c.offer.trim === offer.trim &&
        c.offer.price_kind === offer.price_kind,
    )
    .at(-1);
  return event?.kind === "scope_change" ? "口径变更" : "历史数据积累中";
}
