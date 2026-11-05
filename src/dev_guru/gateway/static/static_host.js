// In a report, there's no server: a recording made by dev explore answers the pages instead. See reports/snapshot.py.
"use strict";

window.DEV_GURU_STATIC = (() => {
  const data = window.parent.DEV_GURU_REPORT;
  const denied = (message) => { const e = new Error(message); e.code = "NOT_IN_THIS_REPORT"; e.status = 404; return e; };
  const nearestDirectory = (depth) => {
    for (let d = depth; d >= 1; d--) if (data.code[`directory|${d}|`]) return data.code[`directory|${d}|`];
    return null;
  };
  return (path, body) => {
    if (body !== undefined) throw denied("This is a report, so it can't start anything. Run dev serve to analyse, check for vulnerabilities or start a run.");
    const url = new URL(path, "http://report.invalid");
    const q = url.searchParams;
    const route = url.pathname.replace(/^\/api\/v1\//, "");
    if (route === "session") return { csrf_token: "", csrf_header: "" };
    if (route === "workspaces") return { workspaces: [data.workspace] };
    if (route === "health") return data.health;
    if (route === "capabilities") return data.capabilities;
    if (route === "documents") return { documents: data.documents };
    if (route === "learning") return { candidates: Object.keys(data.learning) };
    if (route.startsWith("learning/") && data.learning[decodeURIComponent(route.slice(9))]) return data.learning[decodeURIComponent(route.slice(9))];
    if (route === "context") return data.context;
    if (route === "runs") return data.runs;
    if (route === "intel") return { ...data.intel };
    if (route === "sources") {
      const words = (q.get("q") || "").toLowerCase();
      return { capabilities: data.sources.capabilities.filter((c) => JSON.stringify(c).toLowerCase().includes(words)) };
    }
    if (route === "source") {
      const lines = data.source_text[q.get("path") || ""];
      if (!lines) throw denied("This file's source isn't in this report.");
      const start = Math.max(1, Number(q.get("start")) || 1);
      const end = Math.min(lines.length, Number(q.get("end")) || lines.length);
      return { path: q.get("path"), start, end, total_lines: lines.length, truncated: end < lines.length, lines: lines.slice(start - 1, end) };
    }
    if (route === "code") {
      const collapse = q.get("collapse") || "none";
      const found = collapse === "directory"
        ? nearestDirectory(Number(q.get("depth")) || 1)
        : data.code[`${collapse}|0|${q.get("path") || ""}`];
      if (found) return found;
      // a part of a bigger view: the same answer, narrowed here
      const whole = data.code[`${collapse}|0|`];
      const prefix = q.get("path") || "";
      if (!whole || !prefix) throw denied("This view isn't in this report. Run dev serve to see it.");
      const nodes = whole.nodes.filter((n) => n.path === prefix || String(n.path).startsWith(`${prefix}/`));
      const ids = new Set(nodes.map((n) => n.node_id));
      return { ...whole, nodes, edges: whole.edges.filter((e) => ids.has(e.source) || ids.has(e.target)) };
    }
    const run = route.match(/^runs\/([^/]+)(?:\/(events|artifacts))?$/);
    if (run && data.details[run[1]]) {
      const detail = data.details[run[1]];
      return run[2] ? detail[run[2]] : detail.run;
    }
    throw denied("This isn't in this report. Run dev serve to see it.");
  };
})();
