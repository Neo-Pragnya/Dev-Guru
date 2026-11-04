// Code map and end-to-end flows.
"use strict";

(() => {
  const { page, views, withAnalysis, el } = window.DevGuru;
  views.map = async (main) => {
    page("Code map", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
  views.flows = async (main) => {
    page("End-to-end flows", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
})();
