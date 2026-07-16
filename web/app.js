/* gnomAD API-backed variant browser */

const DEFAULT_API = ""; // same-origin when served from FastAPI /ui; else set ?api=
const $ = (sel, el = document) => el.querySelector(sel);

function apiBase() {
  const fromQuery = new URLSearchParams(location.search).get("api");
  if (fromQuery) return fromQuery.replace(/\/$/, "");
  // When opened as /ui/ on the API host, use same origin
  if (location.pathname.startsWith("/ui")) return "";
  // Local skill static serve → point at deployed API
  return "http://10.221.12.63:8923";
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fmtInt(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US");
}

function fmtAf(af) {
  if (af == null) return "—";
  if (af === 0) return "0";
  if (af >= 0.01) return Number(af).toPrecision(4).replace(/0+$/, "").replace(/\.$/, "");
  return Number(af).toExponential(3);
}

function fmtScore(x) {
  if (x == null) return "—";
  return Number(x).toPrecision(3);
}

function pill(block) {
  if (!block || !block.present) return `<span class="pill fail">No data</span>`;
  const kind = block.filter_kind || "pass";
  return `<span class="pill ${kind}">${escapeHtml(block.filter_display || "Pass")}</span>`;
}

function metricCell(block, key) {
  if (!block || !block.present) return "—";
  if (key === "filters") return pill(block);
  if (key === "af" || key === "faf95") return fmtAf(block[key]);
  return fmtInt(block[key]);
}

function renderSummary(summary) {
  if (!summary) return "";
  const cols = [summary.exome, summary.genome, summary.joint].filter(Boolean);
  if (!cols.length) return "";
  const rows = [
    ["Filters", "filters"],
    ["Allele Count", "ac"],
    ["Allele Number", "an"],
    ["Allele Frequency", "af"],
    ["Grpmax Filtering AF (95%)", "faf95"],
    ["Number of homozygotes", "homozygote_count"],
  ];
  const head = cols.map((c) => `<th class="num">${escapeHtml(c.label || "")}</th>`).join("");
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
    return `<p class="section-note">No ancestry frequency rows for this slice.</p>`;
  }
  const body = rows
    .map(
      (r) => `<tr>
        <td>${escapeHtml(r.label || r.id || "")}</td>
        <td class="num">${fmtInt(r.ac)}</td>
        <td class="num">${fmtInt(r.an)}</td>
        <td class="num">${fmtInt(r.homozygote_count)}</td>
        <td class="num">${fmtAf(r.af)}</td>
      </tr>`
    )
    .join("");
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Genetic Ancestry Group</th>
            <th class="num">Allele Count</th>
            <th class="num">Allele Number</th>
            <th class="num">Homozygotes</th>
            <th class="num">Allele Frequency</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function renderResources(v) {
  const chrom = String(v.chrom || "").replace(/^chr/i, "");
  const items = [];
  for (const r of v.rsids || []) {
    items.push(`<a class="resource" href="https://www.ncbi.nlm.nih.gov/snp/${escapeHtml(r)}" target="_blank" rel="noopener">
      <div class="k">dbSNP</div><div class="v">${escapeHtml(r)}</div></a>`);
  }
  if (v.caid) {
    items.push(`<a class="resource" href="https://reg.clinicalgenome.org/redmine/projects/registry/genboree_registry/by_caid?caid=${encodeURIComponent(v.caid)}" target="_blank" rel="noopener">
      <div class="k">ClinGen</div><div class="v">${escapeHtml(v.caid)}</div></a>`);
  }
  if (v.variant_id) {
    items.push(`<a class="resource" href="https://gnomad.broadinstitute.org/variant/${encodeURIComponent(v.variant_id)}?dataset=gnomad_r4" target="_blank" rel="noopener">
      <div class="k">gnomAD.org</div><div class="v">Official page</div></a>`);
  }
  items.push(`<a class="resource" href="https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr${encodeURIComponent(chrom)}%3A${v.pos}-${v.pos}" target="_blank" rel="noopener">
    <div class="k">UCSC</div><div class="v">chr${escapeHtml(chrom)}:${v.pos}</div></a>`);
  return `
    <h2 class="section-title">External resources</h2>
    <div class="resources">${items.join("")}</div>`;
}

function alleleType(alleles) {
  const ref = (alleles && alleles[0]) || "";
  const alt = (alleles && alleles[1]) || "";
  return ref.length === 1 && alt.length === 1 ? "SNV" : "InDel";
}

function renderVariant(v, meta) {
  const alleles = v.alleles || [];
  const ref = alleles[0] || "?";
  const alt = alleles[1] || "?";
  const atype = alleleType(alleles);
  const title = `${atype}:${v.variant_id}(GRCh38)`;
  const geneBits = [];
  if (v.primary_gene) geneBits.push(`<strong>${escapeHtml(v.primary_gene)}</strong>`);
  if (v.consequence) geneBits.push(escapeHtml(v.consequence));
  if (v.hgvsc) geneBits.push(escapeHtml(v.hgvsc));
  if (v.hgvsp) geneBits.push(escapeHtml(v.hgvsp));
  const pred = v.predictors || {};
  const predBits = [
    pred.cadd_phred != null || v.cadd_phred != null
      ? `CADD ${fmtScore(pred.cadd_phred ?? v.cadd_phred)}`
      : null,
    pred.revel_max != null || v.revel_max != null
      ? `REVEL ${fmtScore(pred.revel_max ?? v.revel_max)}`
      : null,
    pred.spliceai_ds_max != null || v.spliceai_ds_max != null
      ? `SpliceAI ${fmtScore(pred.spliceai_ds_max ?? v.spliceai_ds_max)}`
      : null,
  ].filter(Boolean);

  const chroms = (meta && meta.chroms) || [];
  return `
    <div class="v-head">
      <div>
        <h1 class="v-id">${escapeHtml(title)}</h1>
        <div class="badges">
          <span class="badge teal">${escapeHtml((meta && meta.dataset) || "gnomAD local")}</span>
          ${(v.rsids || []).map((r) => `<span class="badge">${escapeHtml(r)}</span>`).join("")}
          ${v.caid ? `<span class="badge">${escapeHtml(v.caid)}</span>` : ""}
        </div>
        ${geneBits.length ? `<p class="gene-line">${geneBits.join(" · ")}</p>` : ""}
        ${predBits.length ? `<p class="gene-line">${predBits.join(" · ")}</p>` : ""}
      </div>
      <div class="actions">
        <button type="button" id="copy-id">Copy variant ID</button>
      </div>
    </div>

    ${renderSummary(v.summary)}

    <h2 class="section-title">Genetic Ancestry Group Frequencies</h2>
    <p class="section-note">From local Parquet API · partitions: ${escapeHtml(chroms.join(", ") || "—")}</p>
    <div class="tabs" id="anc-tabs" role="tablist">
      <button type="button" class="tab active" data-slice="joint">Total</button>
      <button type="button" class="tab" data-slice="exome">Exomes</button>
      <button type="button" class="tab" data-slice="genome">Genomes</button>
    </div>
    <div id="ancestry-panel">${renderAncestry((v.ancestry && v.ancestry.joint) || [])}</div>

    ${renderResources(v)}

    <div class="status-bar">API ${escapeHtml(apiBase() || location.origin)} · ref ${escapeHtml(ref)}&gt;${escapeHtml(alt)}</div>
  `;
}

async function fetchJson(path) {
  const base = apiBase();
  const url = `${base}${path}`;
  const res = await fetch(url);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function loadHealth() {
  try {
    const h = await fetchJson("/health");
    const sub = $("#brand-sub");
    const chroms = (h.chroms || []).join(", ");
    sub.textContent = `${h.dataset || "API"} · chrom=${chroms || "?"} · ${fmtInt(h.chrY_variants)} Y variants`;
    return h;
  } catch (err) {
    $("#brand-sub").textContent = `API offline: ${err.message}`;
    return null;
  }
}

async function loadVariant(query, meta) {
  const page = $("#page");
  if (!query) {
    page.innerHTML = `<p class="hint">Search a variant (e.g. Y:2781489). Current API has chrom=Y.</p>`;
    return;
  }
  page.innerHTML = `<p class="hint">Loading ${escapeHtml(query)}…</p>`;
  try {
    const data = await fetchJson(`/variant?q=${encodeURIComponent(query)}`);
    const v = (data.variants || [])[0];
    if (!v) {
      page.innerHTML = `<div class="error">No match for <strong>${escapeHtml(query)}</strong>.</div>`;
      return;
    }
    page.innerHTML = renderVariant(v, meta || {});
    document.title = `${v.variant_id} · gnomAD`;

    $("#copy-id")?.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(v.variant_id);
        $("#copy-id").textContent = "Copied";
        setTimeout(() => {
          if ($("#copy-id")) $("#copy-id").textContent = "Copy variant ID";
        }, 1200);
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
      panel.innerHTML = renderAncestry((v.ancestry && v.ancestry[btn.dataset.slice]) || []);
    });
  } catch (err) {
    page.innerHTML = `<div class="error">${escapeHtml(err.message)}<br><span style="opacity:.8">Try Y:2781489 — server currently has chrom=Y only.</span></div>`;
  }
}

function currentQuery() {
  return new URLSearchParams(location.search).get("q") || "";
}

async function boot() {
  const meta = await loadHealth();
  const input = $("#q");
  const q = currentQuery() || "Y:2781489";
  input.value = q;
  if (!currentQuery()) {
    const params = new URLSearchParams(location.search);
    params.set("q", q);
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }
  await loadVariant(q, meta);

  $("#search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const next = input.value.trim();
    const params = new URLSearchParams(location.search);
    params.set("q", next);
    history.pushState(null, "", `${location.pathname}?${params}`);
    loadVariant(next, meta);
  });

  window.addEventListener("popstate", () => {
    const next = currentQuery();
    input.value = next;
    loadVariant(next, meta);
  });
}

boot();
