const MCW_BRANDS = ["M1", "B1", "K1", "M2", "B2", "B4", "B3", "TK", "B5", "JY"];
const CX_BRANDS = ["CX", "MB", "MP", "JBG", "DZP", "SB", "SLB", "JWAY", "BJD", "KVP", "HBJ"];

let latestData = {};
let historyData = [];

const $ = (id) => document.getElementById(id);

function num(value) {
  if (value === null || value === undefined) return 0;
  if (typeof value === "number") return value;
  return Number(String(value).replace(/[^\d.-]/g, "")) || 0;
}

function fmt(value) {
  return num(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function pct(value) {
  return `${num(value).toFixed(1)}%`;
}

function getUpdatedTime(data) {
  return data.updated_at || data.last_updated || data.timestamp || data.time || "";
}

function normalizeRows(raw, type) {
  if (!raw) return [];

  if (Array.isArray(raw)) return raw;

  if (Array.isArray(raw[type])) return raw[type];
  if (Array.isArray(raw[`${type}s`])) return raw[`${type}s`];

  if (raw.data && Array.isArray(raw.data[type])) return raw.data[type];
  if (raw.data && Array.isArray(raw.data[`${type}s`])) return raw.data[`${type}s`];

  if (raw.summary && Array.isArray(raw.summary[type])) return raw.summary[type];
  if (raw.summary && Array.isArray(raw.summary[`${type}s`])) return raw.summary[`${type}s`];

  return [];
}

function getBrand(row) {
  return String(
    row.brand ||
    row.Brand ||
    row.brand_code ||
    row.code ||
    row.name ||
    ""
  ).trim().toUpperCase();
}

function getAmount(row) {
  return num(
    row.amount ||
    row.total ||
    row.value ||
    row.total_amount ||
    row.deposit ||
    row.withdrawal ||
    row.count_amount ||
    0
  );
}

function buildBrandMap(data) {
  const depositRows = normalizeRows(data, "deposit");
  const withdrawalRows = normalizeRows(data, "withdrawal");

  const map = {};

  [...MCW_BRANDS, ...CX_BRANDS].forEach((brand) => {
    map[brand] = {
      brand,
      group: MCW_BRANDS.includes(brand) ? "MCW" : "CX",
      deposit: 0,
      withdrawal: 0
    };
  });

  depositRows.forEach((row) => {
    const brand = getBrand(row);
    if (!brand) return;
    if (!map[brand]) {
      map[brand] = { brand, group: "Other", deposit: 0, withdrawal: 0 };
    }
    map[brand].deposit += getAmount(row);
  });

  withdrawalRows.forEach((row) => {
    const brand = getBrand(row);
    if (!brand) return;
    if (!map[brand]) {
      map[brand] = { brand, group: "Other", deposit: 0, withdrawal: 0 };
    }
    map[brand].withdrawal += getAmount(row);
  });

  return map;
}

function totalByGroup(map, brands, field) {
  return brands.reduce((sum, brand) => sum + num(map[brand]?.[field]), 0);
}

function riskStatus(row) {
  const pressure = row.deposit > 0 ? (row.withdrawal / row.deposit) * 100 : row.withdrawal > 0 ? 999 : 0;
  const net = row.deposit - row.withdrawal;

  if (pressure >= 120 || net < -500000) return { label: "High Risk", cls: "badge-red" };
  if (pressure >= 90 || net < 0) return { label: "Watch", cls: "badge-yellow" };
  return { label: "Normal", cls: "badge-green" };
}

function renderSummary(map) {
  const mcwDeposit = totalByGroup(map, MCW_BRANDS, "deposit");
  const mcwWithdrawal = totalByGroup(map, MCW_BRANDS, "withdrawal");
  const cxDeposit = totalByGroup(map, CX_BRANDS, "deposit");
  const cxWithdrawal = totalByGroup(map, CX_BRANDS, "withdrawal");

  const totalDeposit = mcwDeposit + cxDeposit;
  const totalWithdrawal = mcwWithdrawal + cxWithdrawal;
  const net = totalDeposit - totalWithdrawal;
  const pressure = totalDeposit > 0 ? (totalWithdrawal / totalDeposit) * 100 : 0;

  $("mcwDeposit").textContent = fmt(mcwDeposit);
  $("mcwWithdrawal").textContent = fmt(mcwWithdrawal);
  $("cxDeposit").textContent = fmt(cxDeposit);
  $("cxWithdrawal").textContent = fmt(cxWithdrawal);
  $("netFlow").textContent = fmt(net);
  $("withdrawalPressure").textContent = pct(pressure);

  $("m1Deposit").textContent = fmt(map.M1?.deposit);
  $("m1Withdrawal").textContent = fmt(map.M1?.withdrawal);
  $("cxOnlyDeposit").textContent = fmt(map.CX?.deposit);
  $("cxOnlyWithdrawal").textContent = fmt(map.CX?.withdrawal);
}

function renderTable(map) {
  const keyword = $("searchInput").value.trim().toUpperCase();

  const rows = Object.values(map)
    .filter((row) => !keyword || row.brand.includes(keyword) || row.group.includes(keyword))
    .sort((a, b) => (b.deposit + b.withdrawal) - (a.deposit + a.withdrawal));

  $("brandTable").innerHTML = rows.map((row) => {
    const net = row.deposit - row.withdrawal;
    const pressure = row.deposit > 0 ? (row.withdrawal / row.deposit) * 100 : row.withdrawal > 0 ? 999 : 0;
    const status = riskStatus(row);

    return `
      <tr>
        <td><strong>${row.brand}</strong></td>
        <td>${row.group}</td>
        <td>${fmt(row.deposit)}</td>
        <td>${fmt(row.withdrawal)}</td>
        <td class="${net < 0 ? "negative" : "positive"}">${fmt(net)}</td>
        <td>${pct(pressure)}</td>
        <td><span class="badge ${status.cls}">${status.label}</span></td>
      </tr>
    `;
  }).join("");
}

function renderAlerts(map) {
  const alerts = [];

  Object.values(map).forEach((row) => {
    const pressure = row.deposit > 0 ? (row.withdrawal / row.deposit) * 100 : row.withdrawal > 0 ? 999 : 0;
    const net = row.deposit - row.withdrawal;

    if (pressure >= 120) {
      alerts.push(`${row.brand}: Withdrawal pressure very high (${pct(pressure)})`);
    } else if (pressure >= 90) {
      alerts.push(`${row.brand}: Withdrawal pressure needs monitoring (${pct(pressure)})`);
    }

    if (net < 0) {
      alerts.push(`${row.brand}: Negative net flow (${fmt(net)})`);
    }
  });

  if (!alerts.length) {
    $("alerts").innerHTML = `<div class="alert good">No major risk detected right now.</div>`;
    return;
  }

  $("alerts").innerHTML = alerts.slice(0, 8).map((x) => `<div class="alert">${x}</div>`).join("");
}

function normalizeHistory(raw) {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw.history)) return raw.history;
  if (Array.isArray(raw.data)) return raw.data;
  return [];
}

function pointValue(item, type) {
  const map = buildBrandMap(item);
  const deposit = totalByGroup(map, [...MCW_BRANDS, ...CX_BRANDS], "deposit");
  const withdrawal = totalByGroup(map, [...MCW_BRANDS, ...CX_BRANDS], "withdrawal");

  if (type === "withdrawal") return withdrawal;
  if (type === "net") return deposit - withdrawal;
  return deposit;
}

function renderTrend() {
  const canvas = $("trendCanvas");
  const ctx = canvas.getContext("2d");
  const type = $("trendType").value;

  const parentWidth = canvas.parentElement.clientWidth - 40;
  canvas.width = Math.max(parentWidth, 320);

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const history = normalizeHistory(historyData).slice(-168);
  if (!history.length) {
    ctx.fillText("No history data found yet.", 20, 50);
    return;
  }

  const values = history.map((item) => pointValue(item, type));
  const max = Math.max(...values.map(Math.abs), 1);
  const padding = 28;
  const width = canvas.width - padding * 2;
  const height = canvas.height - padding * 2;

  ctx.beginPath();
  ctx.moveTo(padding, padding);
  ctx.lineTo(padding, canvas.height - padding);
  ctx.lineTo(canvas.width - padding, canvas.height - padding);
  ctx.stroke();

  values.forEach((value, i) => {
    const x = padding + (i / Math.max(values.length - 1, 1)) * width;
    const y = canvas.height - padding - ((value + max) / (max * 2)) * height;

    if (i === 0) ctx.beginPath(), ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillText(`Latest: ${fmt(values[values.length - 1])}`, padding, 18);
}

async function loadData() {
  try {
    const [latestRes, historyRes] = await Promise.all([
      fetch("data/latest.json?t=" + Date.now()),
      fetch("data/history.json?t=" + Date.now())
    ]);

    latestData = await latestRes.json();
    historyData = await historyRes.json();

    const map = buildBrandMap(latestData);

    renderSummary(map);
    renderTable(map);
    renderAlerts(map);
    renderTrend();

    const updated = getUpdatedTime(latestData);
    $("lastUpdated").textContent = updated ? `Updated: ${updated}` : "Updated successfully";
  } catch (err) {
    console.error(err);
    $("lastUpdated").textContent = "Data loading failed";
    $("alerts").innerHTML = `<div class="alert">Could not load latest.json or history.json.</div>`;
  }
}

$("refreshBtn").addEventListener("click", loadData);
$("searchInput").addEventListener("input", () => renderTable(buildBrandMap(latestData)));
$("trendType").addEventListener("change", renderTrend);
window.addEventListener("resize", renderTrend);

loadData();
