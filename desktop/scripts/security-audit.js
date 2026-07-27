const { spawnSync } = require("node:child_process");

const TEMPORARY_ALLOWLIST = new Map([
  [
    "GHSA-mh99-v99m-4gvg",
    {
      package: "brace-expansion",
      reason:
        "No compatible patched release is available in the current Electron build dependency chains.",
    },
  ],
]);

const BLOCKING_SEVERITIES = new Set(["high", "critical"]);
const GHSA_PATTERN = /GHSA-[a-z0-9-]+/i;

function advisoryId(via) {
  const match = String(via.url || "").match(GHSA_PATTERN);
  return match
    ? `GHSA-${match[0].slice(5).toLowerCase()}`
    : `NPM:${via.source || via.name || "UNKNOWN"}`;
}

function collectRootAdvisories(packageName, vulnerabilities, trail = new Set()) {
  if (trail.has(packageName)) {
    return [];
  }

  const vulnerability = vulnerabilities[packageName];
  if (!vulnerability) {
    return [];
  }

  const nextTrail = new Set(trail);
  nextTrail.add(packageName);
  const roots = [];

  for (const via of vulnerability.via || []) {
    if (typeof via === "string") {
      roots.push(...collectRootAdvisories(via, vulnerabilities, nextTrail));
      continue;
    }

    roots.push({
      id: advisoryId(via),
      package: via.name || via.dependency || packageName,
      severity: via.severity || vulnerability.severity,
      title: via.title || "Security advisory",
    });
  }

  return roots;
}

function uniqueAdvisories(advisories) {
  const unique = new Map();
  for (const advisory of advisories) {
    unique.set(`${advisory.id}:${advisory.package}`, advisory);
  }
  return [...unique.values()];
}

function analyzeAudit(report, allowlist = new Map()) {
  const vulnerabilities = report?.vulnerabilities || {};
  const blocked = [];
  const allowed = [];
  const usedAllowlist = new Set();

  for (const [packageName, vulnerability] of Object.entries(vulnerabilities)) {
    if (!BLOCKING_SEVERITIES.has(vulnerability.severity)) {
      continue;
    }

    const roots = collectRootAdvisories(packageName, vulnerabilities);
    if (roots.length === 0) {
      blocked.push({
        id: `UNCLASSIFIED:${packageName}`,
        package: packageName,
        severity: vulnerability.severity,
        title: "High-severity vulnerability without a root advisory",
      });
      continue;
    }

    for (const root of roots) {
      const exception = allowlist.get(root.id);
      if (exception && exception.package === root.package) {
        usedAllowlist.add(root.id);
        allowed.push(root);
      } else {
        blocked.push(root);
      }
    }
  }

  const stale = [...allowlist.keys()].filter((id) => !usedAllowlist.has(id));
  const uniqueBlocked = uniqueAdvisories(blocked);
  const uniqueAllowed = uniqueAdvisories(allowed);

  return {
    ok: uniqueBlocked.length === 0 && stale.length === 0,
    blocked: uniqueBlocked,
    allowed: uniqueAllowed,
    stale,
  };
}

function runNpmAudit(extraArgs) {
  const npmCli = process.env.npm_execpath;
  if (!npmCli) {
    throw new Error("npm_execpath is unavailable; run this check with npm run security:audit");
  }

  const result = spawnSync(
    process.execPath,
    [npmCli, "audit", ...extraArgs, "--audit-level=high", "--json"],
    {
      cwd: process.cwd(),
      encoding: "utf8",
      windowsHide: true,
    },
  );

  if (result.error) {
    throw result.error;
  }

  if (![0, 1].includes(result.status)) {
    throw new Error(result.stderr || `npm audit exited with status ${result.status}`);
  }

  try {
    return JSON.parse(result.stdout);
  } catch {
    throw new Error(`npm audit did not return valid JSON: ${result.stderr || "unknown error"}`);
  }
}

function printResult(label, result) {
  for (const advisory of result.blocked) {
    console.error(
      `[security:audit] ${label} blocked ${advisory.id} (${advisory.package}, ${advisory.severity})`,
    );
  }
  for (const advisory of result.allowed) {
    console.warn(
      `[security:audit] ${label} temporarily allowed ${advisory.id} (${advisory.package})`,
    );
  }
  for (const id of result.stale) {
    console.error(
      `[security:audit] ${label} exception ${id} is stale; remove it from security-audit.js`,
    );
  }
}

function main() {
  try {
    const productionResult = analyzeAudit(runNpmAudit(["--omit=dev"]), new Map());
    printResult("production dependencies", productionResult);
    if (!productionResult.ok) {
      process.exitCode = 1;
      return;
    }

    const fullResult = analyzeAudit(runNpmAudit([]), TEMPORARY_ALLOWLIST);
    printResult("all dependencies", fullResult);
    if (!fullResult.ok) {
      process.exitCode = 1;
      return;
    }

    console.log("[security:audit] No unapproved high or critical advisories found.");
  } catch (error) {
    console.error(`[security:audit] ${error.message}`);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  TEMPORARY_ALLOWLIST,
  analyzeAudit,
};
