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
        ${v.interpretation ? `<p class="gene-line"><strong>Interpret:</strong> ${escapeHtml(v.interpretation)}</p>` : ""}
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
    const err = new Error(
      typeof data.detail === "string"
        ? data.detail
        : (data.detail && data.detail.message) || res.statusText
    );
    err.status = res.status;
    err.detail = data.detail;
    throw err;
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

function parseLocusQuery(q) {
  const m = String(q).trim().match(/^(?:chr)?([0-9]+|X|Y|MT|M):(\d+)$/i);
  if (!m) return null;
  return { chrom: m[1], pos: parseInt(m[2], 10) };
}

function renderNotFound(query, detail) {
  const locus = parseLocusQuery(query);
  const msg =
    (detail && typeof detail === "object" && detail.message) ||
    (typeof detail === "string" ? detail : null) ||
    `No variant found for ${query}.`;
  const chrom = (locus && locus.chrom) || (detail && detail.chrom);
  const pos = (locus && locus.pos) || (detail && detail.pos);
  const canNearby = chrom != null && pos != null;
  const actions = canNearby
    ? `
      <p style="margin-top:0.75rem">
        <button type="button" class="tab" id="btn-nearby"
          data-chrom="${escapeHtml(String(chrom))}" data-pos="${pos}">
          Browse nearby ±1 kb
        </button>
      </p>
      <p class="section-note" style="margin-top:0.5rem">
        Prefer a full variant ID (e.g. <code>Y-2781489-C-T</code>) or rsID — same as gnomAD.org.
      </p>`
    : `<p class="section-note" style="margin-top:0.75rem">
        Try a full variant ID or rsID.
      </p>`;
  return `
    <div class="error">
      <strong>Variant not found</strong>
      <p style="margin:0.5rem 0 0;font-weight:400;color:inherit">${escapeHtml(msg)}</p>
      ${actions}
    </div>
    <div id="nearby-panel"></div>
  `;
}

function renderNearbyTable(chrom, pos, variants) {
  if (!variants.length) {
    return `<p class="section-note">No variants within ±1 kb of chr${escapeHtml(chrom)}:${pos}.</p>`;
  }
  const rows = variants
    .map((v) => {
      const alleles = v.alleles || [];
      const ref = alleles[0] || "?";
      const alt = alleles[1] || "?";
      return `<tr class="click-row" data-q="${escapeHtml(v.variant_id)}" style="cursor:pointer">
        <td class="num">${fmtInt(v.pos)}</td>
        <td><code>${escapeHtml(v.variant_id)}</code></td>
        <td>${escapeHtml(ref)}&gt;${escapeHtml(alt)}</td>
        <td class="num">${fmtAf(v.joint_af)}</td>
        <td class="num">${fmtScore(v.cadd_phred)}</td>
      </tr>`;
    })
    .join("");
  return `
    <h2 class="section-title">Nearby variants (±1 kb)</h2>
    <p class="section-note">Optional region browse — not the default gnomAD search result.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="num">pos</th>
            <th>variant_id</th>
            <th>alleles</th>
            <th class="num">joint AF</th>
            <th class="num">CADD</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function loadVariant(query, meta) {
  const page = $("#page");
  if (!query) {
    page.innerHTML = `<p class="hint">Search a variant ID or rsID (e.g. Y-2781489-C-T). Current API has chrom=Y.</p>`;
    return;
  }
  page.innerHTML = `<p class="hint">Loading ${escapeHtml(query)}…</p>`;
  try {
    const data = await fetchJson(`/variant?q=${encodeURIComponent(query)}`);
    const hits = data.variants || [];
    if (!hits.length) {
      page.innerHTML = renderNotFound(query, { message: "No match." });
      return;
    }

    const v = hits[0];
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
    page.innerHTML = renderNotFound(query, err.detail);
    document.title = "Not found · gnomAD";

    $("#btn-nearby")?.addEventListener("click", async () => {
      const btn = $("#btn-nearby");
      const chrom = btn.dataset.chrom;
      const pos = btn.dataset.pos;
      const panel = $("#nearby-panel");
      panel.innerHTML = `<p class="hint">Loading nearby…</p>`;
      try {
        const data = await fetchJson(
          `/locus?chrom=${encodeURIComponent(chrom)}&pos=${encodeURIComponent(pos)}&window_kb=1&limit=20`
        );
        panel.innerHTML = renderNearbyTable(chrom, pos, data.variants || []);
        panel.querySelectorAll(".click-row").forEach((row) => {
          row.addEventListener("click", () => {
            const next = row.dataset.q;
            $("#q").value = next;
            const params = new URLSearchParams(location.search);
            params.set("q", next);
            history.pushState(null, "", `${location.pathname}?${params}`);
            loadVariant(next, meta);
          });
        });
      } catch (e2) {
        panel.innerHTML = `<div class="error">${escapeHtml(e2.message)}</div>`;
      }
    });
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
