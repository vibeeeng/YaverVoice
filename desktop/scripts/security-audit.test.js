const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const analyzerPath = path.join(__dirname, "security-audit.js");

function loadAnalyzer() {
  assert.equal(
    fs.existsSync(analyzerPath),
    true,
    "The security audit analyzer must exist",
  );
  return require(analyzerPath);
}

function reportWith(vulnerabilities) {
  return {
    auditReportVersion: 2,
    vulnerabilities,
  };
}

test("allows only a high-severity chain rooted in the temporary brace-expansion advisory", () => {
  const { analyzeAudit, TEMPORARY_ALLOWLIST } = loadAnalyzer();
  const report = reportWith({
    "brace-expansion": {
      name: "brace-expansion",
      severity: "high",
      via: [
        {
          name: "brace-expansion",
          severity: "high",
          title: "Uncontrolled resource consumption",
          url: "https://github.com/advisories/GHSA-mh99-v99m-4gvg",
        },
      ],
    },
    glob: {
      name: "glob",
      severity: "high",
      via: ["brace-expansion"],
    },
  });

  const result = analyzeAudit(report, TEMPORARY_ALLOWLIST);

  assert.equal(result.ok, true);
  assert.deepEqual(result.blocked, []);
  assert.deepEqual(result.stale, []);
  assert.deepEqual(result.allowed.map((item) => item.id), [
    "GHSA-mh99-v99m-4gvg",
  ]);
});

test("blocks an unrelated high-severity advisory", () => {
  const { analyzeAudit, TEMPORARY_ALLOWLIST } = loadAnalyzer();
  const report = reportWith({
    postcss: {
      name: "postcss",
      severity: "high",
      via: [
        {
          name: "postcss",
          severity: "high",
          title: "Path traversal",
          url: "https://github.com/advisories/GHSA-r28c-9q8g-f849",
        },
      ],
    },
  });

  const result = analyzeAudit(report, TEMPORARY_ALLOWLIST);

  assert.equal(result.ok, false);
  assert.deepEqual(result.blocked.map((item) => item.id), [
    "GHSA-r28c-9q8g-f849",
  ]);
});

test("fails closed when a high-severity vulnerability cannot be classified", () => {
  const { analyzeAudit } = loadAnalyzer();
  const report = reportWith({
    mystery: {
      name: "mystery",
      severity: "critical",
      via: [],
    },
  });

  const result = analyzeAudit(report, new Map());

  assert.equal(result.ok, false);
  assert.deepEqual(result.blocked.map((item) => item.id), [
    "UNCLASSIFIED:mystery",
  ]);
});

test("reports an unused temporary exception as stale", () => {
  const { analyzeAudit, TEMPORARY_ALLOWLIST } = loadAnalyzer();

  const result = analyzeAudit(reportWith({}), TEMPORARY_ALLOWLIST);

  assert.equal(result.ok, false);
  assert.deepEqual(result.stale, ["GHSA-mh99-v99m-4gvg"]);
});
