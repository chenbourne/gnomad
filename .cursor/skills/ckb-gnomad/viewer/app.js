/* global fetch, history, location */

const $ = (sel, el = document) => el.querySelector(sel);

function fmtInt(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US");
}

function fmtAf(af) {
  if (af == null) return "—";
  if (af === 0) return "0.000";
  if (af >= 0.01) return af.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return af.toPrecision(4);
}

function pill(block) {
  if (!block || !block.present) return `<span class="pill fail">No data</span>`;
  const kind = block.filter_kind || "pass";
  return `<span class="pill ${kind}">${escapeHtml(block.filter_display)}</span>`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function metricCell(block, key) {
  if (!block || !block.present) return "—";
  if (key === "filters") return pill(block);
  if (key === "af" || key === "faf95") return fmtAf(block[key]);
  return fmtInt(block[key]);
}

function renderSummary(summary) {
  const cols = [summary.exome, summary.genome, summary.joint];
  const rows = [
    ["Filters", "filters"],
    ["Allele Count", "ac"],
    ["Allele Number", "an"],
    ["Allele Frequency", "af"],
    ["Grpmax Filtering AF (95% confidence)", "faf95"],
    ["Number of homozygotes", "homozygote_count"],
  ];
  const head = cols.map((c) => `<th class="num">${escapeHtml(c.label)}</th>`).join("");
  const body = rows
    .map(([label, key]) => {
      const cells = cols.map((c) => `<td>${metricCell(c, key)}</td>`).join("");
      return `<tr><td class="row-label">${escapeHtml(label)}</td>${cells}</tr>`;
    })
    .join("");
  return `
    <h2 class="section-title">Variant summary</h2>
    <div class="table-wrap">
      <table class="metric-table">
        <thead><tr><th></th>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function renderAncestry(rows) {
  if (!rows || !rows.length) {
    return `<p class="section-note">No ancestry frequency rows for this dataset slice.</p>`;
  }
  const body = rows
    .map((r) => {
      return `<tr>
        <td>${escapeHtml(r.label)}</td>
        <td class="num">${fmtInt(r.ac)}</td>
        <td class="num">${fmtInt(r.an)}</td>
        <td class="num">${fmtInt(r.homozygote_count)}</td>
        <td class="num">${fmtAf(r.af)}</td>
      </tr>`;
    })
    .join("");
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Genetic Ancestry Group</th>
            <th class="num">Allele Count</th>
            <th class="num">Allele Number</th>
            <th class="num">Number of Homozygotes</th>
            <th class="num">Allele Frequency</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function renderResources(v) {
  const items = [];
  for (const d of v.resources.dbsnp || []) {
    items.push(`<a class="resource" href="${d.url}" target="_blank" rel="noopener">
      <div class="k">dbSNP</div><div class="v">${escapeHtml(d.id)}</div></a>`);
  }
  if (v.resources.ucsc) {
    items.push(`<a class="resource" href="${v.resources.ucsc}" target="_blank" rel="noopener">
      <div class="k">UCSC</div><div class="v">chr${escapeHtml(v.chrom)}:${v.pos}</div></a>`);
  }
  if (v.resources.clingen) {
    items.push(`<a class="resource" href="${v.resources.clingen.url}" target="_blank" rel="noopener">
      <div class="k">ClinGen</div><div class="v">${escapeHtml(v.resources.clingen.id)}</div></a>`);
  }
  if (v.resources.gnomad) {
    items.push(`<a class="resource" href="${v.resources.gnomad}" target="_blank" rel="noopener">
      <div class="k">gnomAD.org</div><div class="v">Open official page</div></a>`);
  }
  if (!items.length) return "";
  return `
    <h2 class="section-title">External resources</h2>
    <div class="resources">${items.join("")}</div>`;
}

function renderVariant(v) {
  const geneBits = [];
  if (v.primary_gene) geneBits.push(`<strong>${escapeHtml(v.primary_gene)}</strong>`);
  if (v.consequence) geneBits.push(escapeHtml(v.consequence));
  if (v.hgvsc) geneBits.push(escapeHtml(v.hgvsc));
  if (v.hgvsp) geneBits.push(escapeHtml(v.hgvsp));

  const pred = v.predictors || {};
  const predBits = [
    pred.cadd_phred != null ? `CADD ${Number(pred.cadd_phred).toPrecision(3)}` : null,
    pred.revel_max != null ? `REVEL ${Number(pred.revel_max).toPrecision(3)}` : null,
    pred.spliceai_ds_max != null ? `SpliceAI ${Number(pred.spliceai_ds_max).toPrecision(3)}` : null,
  ].filter(Boolean);

  const title = `${v.allele_type}:${v.variant_id}(${v.reference_genome})`;
  return `
    <div class="v-head">
      <div>
        <h1 class="v-id">${escapeHtml(title)}</h1>
        <div class="badges">
          <span class="badge teal">${escapeHtml(v.dataset_label)}</span>
          ${(v.rsids || []).map((r) => `<span class="badge">${escapeHtml(r)}</span>`).join("")}
        </div>
        ${geneBits.length ? `<p class="gene-line">${geneBits.join(" · ")}</p>` : ""}
        ${predBits.length ? `<p class="gene-line">${predBits.join(" · ")}</p>` : ""}
      </div>
      <div class="actions">
        ${v.primary_gene ? `<a href="?q=${encodeURIComponent(v.primary_gene)}">Gene: ${escapeHtml(v.primary_gene)}</a>` : ""}
        <button type="button" id="copy-id">Copy variant ID</button>
      </div>
    </div>

    ${renderSummary(v.summary)}

    <h2 class="section-title">Genetic Ancestry Group Frequencies</h2>
    <p class="section-note">Local sample export — joint frequencies match gnomAD browser “Total”.</p>
    <div class="tabs" id="anc-tabs" role="tablist">
      <button type="button" class="tab active" data-slice="joint">Total</button>
      <button type="button" class="tab" data-slice="exome">Exomes</button>
      <button type="button" class="tab" data-slice="genome">Genomes</button>
    </div>
    <div id="ancestry-panel">${renderAncestry(v.ancestry.joint)}</div>

    ${renderResources(v)}
  `;
}

async function loadVariant(query) {
  const page = $("#page");
  if (!query) {
    page.innerHTML = `<p class="hint" id="empty-hint">Search an rsID or variant ID (e.g. rs429358).</p>`;
    return;
  }
  page.innerHTML = `<p class="hint">Loading ${escapeHtml(query)}…</p>`;
  const res = await fetch(`/api/variant?q=${encodeURIComponent(query)}`);
  const data = await res.json();
  if (!res.ok || !data.ok) {
    page.innerHTML = `<div class="error">No match for <strong>${escapeHtml(query)}</strong> in the local sample. Try rs429358 or 19-44908684-T-C.</div>`;
    return;
  }
  const v = data.variant;
  page.innerHTML = renderVariant(v);
  document.title = `${v.allele_type}:${v.variant_id}(${v.reference_genome}) · gnomAD local`;

  $("#copy-id")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(v.variant_id);
      $("#copy-id").textContent = "Copied";
      setTimeout(() => ($("#copy-id").textContent = "Copy variant ID"), 1200);
    } catch {
      /* ignore */
    }
  });

  const tabs = $("#anc-tabs");
  const panel = $("#ancestry-panel");
  tabs?.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    tabs.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    const slice = btn.dataset.slice;
    panel.innerHTML = renderAncestry(v.ancestry[slice] || []);
  });
}

function currentQuery() {
  return new URLSearchParams(location.search).get("q") || "";
}

async function boot() {
  const input = $("#q");
  const q = currentQuery() || "19-44908684-T-C";
  input.value = q;
  if (!currentQuery()) {
    history.replaceState(null, "", `?q=${encodeURIComponent(q)}`);
  }
  await loadVariant(q);

  $("#search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const next = input.value.trim();
    history.pushState(null, "", `?q=${encodeURIComponent(next)}`);
    loadVariant(next);
  });

  window.addEventListener("popstate", () => {
    const next = currentQuery();
    input.value = next;
    loadVariant(next);
  });
}

boot().catch((err) => {
  $("#page").innerHTML = `<div class="error">Failed to start viewer: ${escapeHtml(err.message)}. Run serve_viewer.py from the skill scripts.</div>`;
});
