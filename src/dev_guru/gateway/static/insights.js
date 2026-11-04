// Data, API pathways, architecture, quality, coverage and CVEs.
"use strict";

(() => {
  const { page, views, withAnalysis, el } = window.DevGuru;
  views.data = async (main) => {
    page("Data", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
  views.apis = async (main) => {
    page("API pathways", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
  views.architecture = async (main) => {
    page("Architecture", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
  views.quality = async (main) => {
    page("Quality", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
  views.coverage = async (main) => {
    page("Coverage", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
  views.cves = async (main) => {
    page("CVEs", "");
    await withAnalysis(document.querySelector("#main"), (report) => {
      document.querySelector("#main").append(el("p", { text: `Analysis ${report.run_id} found.` }));
    });
  };
})();
