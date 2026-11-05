const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


function loadApp(elements = {}) {
  const sandbox = {
    clearTimeout() {},
    console,
    document: {
      addEventListener() {},
      getElementById(id) {
        return elements[id] || null;
      }
    },
    setTimeout() {
      return 1;
    }
  };
  const source = fs.readFileSync(path.join(__dirname, "..", "app.js"), "utf8");
  const hooks = `
    globalThis.__testHooks = {
      buildHourlyRows,
      getBrands: () => ({ mcw: [...MCW_BRANDS], all: [...ALL_BRANDS] }),
      normalizeLatest,
      renderTable,
      setLatest: (latest) => { state.latest = latest; },
      setRows: (rows) => { state.rows = rows; }
    };
  `;

  vm.createContext(sandbox);
  vm.runInContext(source + hooks, sandbox, { filename: "app.js" });
  return sandbox.__testHooks;
}


test("FW is included once as an MCW brand without changing existing brands", () => {
  const app = loadApp();
  const brands = app.getBrands();

  assert.equal(brands.mcw.filter((brand) => brand === "FW").length, 1);
  assert.deepEqual(
    Array.from(brands.mcw.slice(0, -1)),
    ["M1", "B1", "K1", "M2", "B2", "B4", "B3", "TK", "B5", "JY"]
  );
});

test("frontend normalizes and renders FW using existing table and risk rules", () => {
  const elements = {
    brandSearch: { value: "FW" },
    groupFilter: { value: "all" },
    brandTableBody: { innerHTML: "" }
  };
  const app = loadApp(elements);
  const rows = app.normalizeLatest({
    brands: {
      M1: { deposit_amount: 300000.75, withdrawal_amount: 100000.50 },
      FW: { deposit_amount: "125,678.91", withdrawal_amount: "65,432.19" },
      EXTRA: { deposit_amount: 9999, withdrawal_amount: 8888 }
    }
  });
  const fw = rows.find((row) => row.brand === "FW");

  assert.equal(fw.group, "MCW");
  assert.equal(fw.deposit, 125678.91);
  assert.equal(fw.withdrawal, 65432.19);
  assert.equal(fw.risk, "Normal");
  assert.equal(rows.some((row) => row.brand === "EXTRA"), false);

  app.setRows(rows);
  app.renderTable();
  assert.match(elements.brandTableBody.innerHTML, /<strong>FW<\/strong>/);
});

test("frontend zero-fills temporarily missing FW data", () => {
  const app = loadApp();
  const rows = app.normalizeLatest({ brands: { M1: { deposit_amount: 10, withdrawal_amount: 5 } } });
  const fw = rows.find((row) => row.brand === "FW");

  assert.equal(fw.deposit, 0);
  assert.equal(fw.withdrawal, 0);
  assert.equal(fw.net, 0);
  assert.equal(fw.risk, "Normal");
});

test("hourly frontend includes every FW time slot and tolerates a missing point", () => {
  const app = loadApp();
  app.setLatest({
    hourly: {
      deposit: {
        FW: {
          "2026-11-05": {
            "01:00": { amount: "1,000.10", difference: "10.01" },
            "16:00": { amount: "1,600.20", difference: "16.02" },
            "17:00": { amount: "1,700.30", difference: "17.03" },
            "23:59": { amount: "2,359.40", difference: "23.59" }
          }
        }
      },
      withdrawal: {
        FW: {
          "2026-11-05": {
            "01:00": { amount: "500.05", difference: "5.01" },
            "16:00": { amount: "800.10", difference: "8.02" },
            "23:59": { amount: "1,000.20", difference: "10.59" }
          }
        }
      }
    }
  });

  const rows = app.buildHourlyRows("2026-11-05", ["FW"]);

  assert.deepEqual(Array.from(rows, (row) => row.hour), ["01:00", "16:00", "17:00", "23:59"]);
  assert.equal(rows.find((row) => row.hour === "01:00").depositAmount, 1000.10);
  assert.equal(rows.find((row) => row.hour === "17:00").withdrawalAmount, 0);
  assert.equal(rows.find((row) => row.hour === "23:59").net, 1359.20);
});
