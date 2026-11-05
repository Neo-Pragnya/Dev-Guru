// Workflows, Documentation and Learning review. All decisions are Ananke's: this page edits a draft and asks.
"use strict";

(() => {
  const { el, api, scoped, page, showError, views } = window.DevGuru;
  const download = (name, text, type) => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([text], { type }));
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const table = (id, heads, rows) => el("table", { id }, el("thead", {}, el("tr", {}, ...heads.map((h) => el("th", { text: h })))),
    el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((c) => (c instanceof Node ? el("td", {}, c) : el("td", { text: c === null || c === undefined ? "" : String(c) })))))));
  const inReport = () => !!window.DEV_GURU_STATIC;
  const field = (label, control) => el("label", { class: "field" }, label, control);

  // ---------------------------------------------------------------- workflows
  const parsePorts = (text) => text.split(",").map((part) => part.trim()).filter(Boolean).map((part) => {
    const [name, schema] = part.split(":").map((s) => s.trim());
    return { name, schema_ref: schema || "any/v1" };
  });
  const showPorts = (ports) => (ports || []).map((p) => `${p.name}:${p.schema_ref}`).join(", ");
  const blankNode = (number, ref = "") => ({ id: `step-${number}`, capability_ref: ref, kind: "skill", inputs: [], outputs: [], config: {} });
  const PRESETS = {
    blank: { title: "New workflow", nodes: [] },
    single: { title: "One step", nodes: [{ ...blankNode(1), outputs: [{ name: "result", schema_ref: "markdown/v1" }] }] },
    review: {
      title: "Plan, then review",
      nodes: [
        { ...blankNode(1), id: "plan", outputs: [{ name: "plan", schema_ref: "markdown/v1" }] },
        { ...blankNode(2), id: "review", inputs: [{ name: "plan", schema_ref: "markdown/v1" }], outputs: [{ name: "findings", schema_ref: "markdown/v1" }], approval_class: "HUMAN" },
      ],
    },
  };
  const linkMatching = (draft) => {
    const edges = [];
    draft.nodes.forEach((node, index) => {
      for (const input of node.inputs || []) {
        for (let back = index - 1; back >= 0; back--) {
          const from = draft.nodes[back];
          const output = (from.outputs || []).find((o) => o.schema_ref === input.schema_ref);
          if (output) {
            edges.push({ id: `e${edges.length + 1}`, source: from.id, source_port: output.name, target: node.id, target_port: input.name });
            break;
          }
        }
      }
    });
    return edges;
  };

  views.workflows = async () => {
    page("Workflows", "Put capabilities in order, and Ananke checks the draft and shows what would run. Previewing runs nothing.");
    const root = document.querySelector("#main section");
    let offered = [];
    try {
      offered = (await api(scoped("/api/v1/sources", { q: "" }))).capabilities || [];
    } catch { /* the list only helps with typing */ }
    const options = el("datalist", { id: "capability-options" }, ...offered.slice(0, 500).map((c) => el("option", { value: c.ref || c.id || c.name || "" })));
    const draft = { schema_version: "1.0.0", workflow_id: "my/workflow", title: "New workflow", nodes: [], edges: [] };
    const steps = el("div", { id: "workflow-steps" });
    const links = el("div", { id: "workflow-links" });
    const result = el("div", { id: "workflow-result", "aria-live": "polite" });
    const title = el("input", { id: "workflow-title", value: draft.title, on: { input: (e) => { draft.title = e.target.value; } } });
    const identity = el("input", { id: "workflow-id", value: draft.workflow_id, on: { input: (e) => { draft.workflow_id = e.target.value; } } });
    const drawLinks = () => {
      links.replaceChildren(el("h2", { text: "Links" }), draft.edges.length
        ? table("workflow-edges", ["From", "To"], draft.edges.map((e) => [`${e.source}.${e.source_port}`, `${e.target}.${e.target_port}`]))
        : el("p", { class: "muted", text: "None yet. Steps with an input join to an earlier output of the same type." }));
    };
    const relink = () => { draft.edges = linkMatching(draft); drawLinks(); };
    const drawSteps = () => {
      steps.replaceChildren(...draft.nodes.map((node, index) => {
        const set = (key, parse = (v) => v) => (event) => { node[key] = parse(event.target.value); relink(); };
        const move = (by) => () => {
          const target = index + by;
          if (target < 0 || target >= draft.nodes.length) return;
          [draft.nodes[index], draft.nodes[target]] = [draft.nodes[target], draft.nodes[index]];
          drawSteps();
          relink();
        };
        return el("fieldset", { class: "card workflow-step" }, el("legend", { text: `Step ${index + 1}` }),
          el("div", { class: "row" },
            field("Name", el("input", { class: "step-id", value: node.id, on: { input: set("id") } })),
            field("Capability", el("input", { class: "step-capability", list: "capability-options", value: node.capability_ref, placeholder: "source/name@1.0.0", on: { input: set("capability_ref") } })),
            field("Kind", el("select", { class: "step-kind", on: { change: set("kind") } }, ...["skill", "tool", "agent", "workflow"].map((k) => el("option", { value: k, text: k, selected: node.kind === k }))))),
          el("div", { class: "row" },
            field("Inputs (name:type, comma separated)", el("input", { class: "step-inputs", value: showPorts(node.inputs), on: { change: set("inputs", parsePorts) } })),
            field("Outputs (name:type)", el("input", { class: "step-outputs", value: showPorts(node.outputs), on: { change: set("outputs", parsePorts) } }))),
          el("div", { class: "row" },
            el("button", { type: "button", class: "ghost", text: "Move up", on: { click: move(-1) } }),
            el("button", { type: "button", class: "ghost", text: "Move down", on: { click: move(1) } }),
            el("button", { type: "button", class: "ghost", text: "Remove", on: { click: () => { draft.nodes.splice(index, 1); drawSteps(); relink(); } } })));
      }));
    };
    const load = (next) => {
      Object.assign(draft, { nodes: [], ...next });
      if (!next.edges) draft.edges = linkMatching(draft); // an imported draft keeps the links it came with
      title.value = draft.title || "";
      identity.value = draft.workflow_id || "";
      drawSteps();
      drawLinks();
      result.replaceChildren();
    };
    const preview = async () => {
      result.replaceChildren(el("p", { class: "muted", text: "Asking Ananke..." }));
      try {
        const done = await api("/api/v1/plans/prepare", { draft: JSON.parse(JSON.stringify(draft)) });
        const parts = [];
        if ((done.issues || []).length) {
          parts.push(el("h2", { text: "Ananke found problems" }), table("workflow-issues", ["Problem", "Step", "What's wrong", "What to do"], done.issues.map((i) => [i.code, i.node, i.message, i.remediation])));
        }
        if ((done.warnings || []).length) parts.push(el("h2", { text: "Warnings" }), table("workflow-warnings", ["Warning", "Step", "What's wrong"], done.warnings.map((i) => [i.code, i.node, i.message])));
        if (done.plan_hash) {
          parts.push(el("h2", { text: "What would run" }), el("p", {}, "Plan ", el("code", { id: "workflow-hash", text: done.plan_hash })),
            table("workflow-plan", ["Step", "Capability", "Trust", "Permissions", "Approval"], (done.steps || []).map((s) => [s.node, s.capability, s.trust, (s.permissions || []).join(", "), s.approval_class])),
            el("p", { class: "muted", text: "Nothing has run. To run it, export the draft, then:" }),
            el("pre", { class: "source" }, el("code", { text: `ananke app workflow-run workflow.json --backend BACKEND --plan-hash ${done.plan_hash} --key my-first-run` })));
        }
        result.replaceChildren(...parts);
      } catch (error) {
        result.replaceChildren();
        showError(result, error);
      }
    };
    const importer = el("input", { type: "file", id: "workflow-import", accept: "application/json,.json", on: { change: async (event) => {
      const file = event.target.files[0];
      if (!file) return;
      try {
        load(JSON.parse(await file.text()));
      } catch (error) {
        result.replaceChildren();
        showError(result, Object.assign(error, { code: "NOT_A_DRAFT" }));
      }
    } } });
    root.append(options,
      el("div", { class: "row" }, field("Title", title), field("ID", identity),
        field("Start from", el("select", { id: "workflow-preset", on: { change: (e) => load(JSON.parse(JSON.stringify(PRESETS[e.target.value]))) } },
          ...[["blank", "A blank draft"], ["single", "One step"], ["review", "Plan, then review"]].map(([value, text]) => el("option", { value, text }))))),
      steps,
      el("div", { class: "row" },
        el("button", { type: "button", class: "ghost", id: "workflow-add", text: "Add a step", on: { click: () => { draft.nodes.push(blankNode(draft.nodes.length + 1)); drawSteps(); drawLinks(); } } }),
        el("button", { type: "button", id: "workflow-preview", text: inReport() ? "Preview (needs dev serve)" : "Preview", on: { click: preview } }),
        el("button", { type: "button", class: "ghost", id: "workflow-export", text: "Export", on: { click: () => download(`${String(draft.workflow_id).replace(/[^\w-]+/g, "-")}.json`, JSON.stringify(draft, null, 2), "application/json") } }),
        field("Import", importer)),
      links, result);
    drawLinks();
  };

  // ---------------------------------------------------------------- documentation
  views.docs = async () => {
    page("Documentation", "Turn a Markdown file into an offline deck, or a diagram of what it states. Each comes back as a file, and nothing else changes.");
    const root = document.querySelector("#main section");
    let files = [];
    try {
      files = (await api(scoped("/api/v1/documents"))).documents;
    } catch (error) {
      showError(root, error);
      return;
    }
    if (!files.length) { root.append(el("p", { id: "documents-none", text: "No Markdown files here." })); return; }
    const result = el("div", { id: "document-result", "aria-live": "polite" });
    const build = (path, what) => async () => {
      result.replaceChildren(el("p", { class: "muted", text: `Building from ${path}...` }));
      try {
        const done = await api("/api/v1/documents/build", { path, what });
        download(done.name, done.content, done.media_type);
        result.replaceChildren(el("p", { id: "document-built", text: `${done.name} is in your downloads. ${done.summary}` }),
          ...(done.problems.length ? [el("h2", { text: "Problems" }), el("ul", {}, ...done.problems.map((p) => el("li", { text: p })))] : []));
      } catch (error) {
        result.replaceChildren();
        showError(result, error);
      }
    };
    root.append(table("documents", ["File", "Lines", "", ""], files.map((f) => [f.path, f.lines,
      el("button", { type: "button", class: "ghost", text: "Make a deck", "aria-label": `Make a deck from ${f.path}`, on: { click: build(f.path, "deck") } }),
      el("button", { type: "button", class: "ghost", text: "Make a diagram", "aria-label": `Make a diagram from ${f.path}`, on: { click: build(f.path, "diagram") } })])),
    result, el("p", { class: "muted", text: "A deck splits on lines of ---. A diagram draws only what the document states, and cites it." }));
  };

  // ---------------------------------------------------------------- learning review
  views.learning = async (_main, query) => {
    page("Learning review", "What Ananke learned, before it becomes reusable. Reviewing changes nothing, and rejecting never publishes.");
    const root = document.querySelector("#main section");
    const wanted = query.get("name");
    try {
      if (!wanted) {
        const found = (await api(scoped("/api/v1/learning"))).candidates;
        root.append(found.length
          ? table("learning-list", ["Candidate"], found.map((name) => [el("a", { href: `#/learning?${new URLSearchParams({ name })}`, text: name })]))
          : el("p", { id: "learning-none", text: "No candidates yet. Ananke creates one with ananke learning capture." }));
        return;
      }
      const c = await api(scoped(`/api/v1/learning/${encodeURIComponent(wanted)}`));
      root.append(el("p", {}, el("a", { href: "#/learning", text: "All candidates" })), el("h2", { id: "candidate-name", text: c.name }),
        c.problems.length
          ? el("div", { class: "card warning", id: "candidate-problems" }, el("strong", { text: "Not ready" }), el("ul", {}, ...c.problems.map((p) => el("li", { text: p }))))
          : el("p", { id: "candidate-ready", text: "Ananke's gate found no problems." }),
        el("h3", { text: "What it would add" }), el("pre", { class: "source" }, el("code", { text: c.skill_md })),
        el("h3", { text: "Evidence" }), c.cases.length
          ? table("candidate-cases", ["Case", "Result"], c.cases.map((k) => [k.name || k.id || JSON.stringify(k), k.passed === undefined ? (k.result || "") : (k.passed ? "passed" : "failed")]))
          : el("p", { class: "muted", id: "candidate-no-cases", text: "It hasn't been evaluated, so there's no evidence yet." }),
        el("h3", { text: "Where it would go" }), c.destinations.length
          ? el("div", { id: "candidate-destinations" }, ...c.destinations.map((d) => el("div", { class: "card" }, el("strong", { text: d.source }),
            el("p", { class: "muted", text: `${d.visibility}, ${d.writable ? "writable" : "read-only"}${d.existing_version ? `, replaces ${d.existing_version}` : ", new here"}` }),
            d.diff ? el("pre", { class: "source" }, el("code", { text: d.diff })) : null)))
          : el("p", { class: "muted", text: "No writable destination is configured." }),
        el("h3", { text: "To decide" }), el("pre", { class: "source" }, el("code", { text: `ananke learning review ${c.name}\nananke learning promote ${c.name}` })));
    } catch (error) {
      showError(root, error);
    }
  };
})();
