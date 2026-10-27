import html
import json
from pathlib import Path

AGG_PATH = Path("examples/outputs/aggregated/combined_metadata.json")
OUT_HTML = Path("examples/outputs/aggregated/dashboard.html")


def make_row(lib: str, entry: dict) -> str:
    d = entry["data"]
    file = entry["file"]
    title = d.get("metadata", {}).get("Title") or Path(file).stem
    n_pages = d.get("n_pages")
    text_len = (d.get("details") or {}).get("text_length")
    images = (d.get("details") or {}).get("image_count")

    # extra data attributes for richer client-side charts
    fonts = (d.get("details") or {}).get("fonts") or []
    attachments = (d.get("attachments") or []) or []
    annotations = (d.get("details") or {}).get("annotations_count") or 0

    md_path = Path(file).with_name(Path(file).stem + "_metadata.md")
    md_content = None
    if md_path.exists():
        md_content = md_path.read_text(encoding="utf-8")
    md_html = (
        f"<pre>{html.escape(md_content)}</pre>" if md_content else "<em>no markdown available</em>"
    )

    # escape JSON-serializable values for data-attributes
    import json as _json

    fonts_attr = html.escape(_json.dumps(fonts))
    attachments_attr = html.escape(_json.dumps(attachments))

    return f"""
    <tr data-fonts='{fonts_attr}' data-attachments='{attachments_attr}' data-annotations='{annotations}'>
      <td>{html.escape(lib)}</td>
      <td>{html.escape(title)}</td>
      <td>{n_pages}</td>
      <td>{text_len or ""}</td>
      <td>{images or ""}</td>
      <td><a href="{html.escape(file)}">JSON</a></td>
      <td class="md-preview">{md_html}</td>
    </tr>
    """


def build_dashboard(agg_path: Path, out: Path):
    if not agg_path.exists():
        raise SystemExit("Run `scripts/collect_metadata.py` first to generate aggregated data.")
    data = json.loads(agg_path.read_text(encoding="utf-8"))
    rows = []
    for lib, entries in data.items():
        for e in entries:
            rows.append(make_row(lib, e))

    template = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>PDF Toolkit — Aggregated metadata</title>
      <style>
        body{font-family:Inter,Segoe UI,Helvetica,Arial,sans-serif;margin:20px}
        .toolbar{display:flex;gap:12px;align-items:center;margin-bottom:12px}
        input[type=search]{padding:8px;border-radius:6px;border:1px solid #ccc;width:320px}
        table{border-collapse:collapse;width:100%;border:1px solid #e6e6e6;border-radius:6px;overflow:hidden}
        th{background:#fafafa;text-align:left;padding:10px;border-bottom:1px solid #eee}
        td{padding:10px;border-top:1px solid #f1f1f1;vertical-align:top}
        pre{white-space:pre-wrap;max-height:200px;overflow:auto;background:#fbfbfb;padding:8px;border-radius:4px}
        .small{font-size:90%;color:#666}
        .badge{display:inline-block;background:#eef6ff;color:#0366d6;padding:2px 6px;border-radius:4px;font-size:90%}
        tr.hidden{display:none}
        .md-preview{max-width:420px}
      </style>
    </head>
    <body>
      <h1>PDF Toolkit — Aggregated metadata</h1>
      <div class="toolbar">
        <label class="small">Filter:</label>
        <input id="q" type="search" placeholder="search library, title, file..." oninput="filterTable()">
        <button id="export-csv" onclick="exportCSV()" title="Export visible rows as CSV">Export CSV</button>
        <button id="download-chart" onclick="downloadChartPNG()" title="Download summary chart as PNG">Download chart PNG</button>
        <div style="flex:1"></div>
        <div class="small">Rows: <span id="count">%%ROW_COUNT%%</span></div>
      </div>

      <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:12px">
        <div id="summary-chart" style="width:420px;height:180px;border:1px solid #eee;padding:8px;border-radius:6px;background:#fff"></div>
        <div style="flex:1">
          <div class="small">Legend: <span class="badge">pages</span> <span class="badge">images</span></div>
          <div style="margin-top:8px" id="summary-stats"></div>
        </div>
      </div>

      <table id="agg">
        <thead><tr>
          <th onclick="sortTable(0,false)">Library ▲/▼</th>
          <th onclick="sortTable(1,false)">Title / File ▲/▼</th>
          <th onclick="sortTable(2,true)">Pages ▲/▼</th>
          <th onclick="sortTable(3,true)">Text length ▲/▼</th>
          <th onclick="sortTable(4,true)">Images ▲/▼</th>
          <th>JSON</th>
          <th>Markdown preview</th>
        </tr></thead>
        <tbody>
        %%ROWS_HTML%%
        </tbody>
      </table>
      <p class="small">Generated from %%AGG_PATH%%</p>

      <script>
        function textOf(node){ return (node||'').toString().toLowerCase(); }
        function matches(row, q){
          q = q.trim().toLowerCase(); if(!q) return true;
          const tds = row.querySelectorAll('td');
          for(let i=0;i<tds.length;i++){ if(textOf(tds[i].innerText).includes(q)) return true; }
          return false;
        }
        function filterTable(){
          const q = document.getElementById('q').value || '';
          const rows = document.querySelectorAll('#agg tbody tr');
          let visible = 0;
          rows.forEach(r => {
            if(matches(r,q)) { r.classList.remove('hidden'); visible++; } else { r.classList.add('hidden'); }
          });
          document.getElementById('count').innerText = visible;
        }
        // simple expand/collapse for md previews
        document.addEventListener('click', function(e){
          const t = e.target;
          const cb = t.closest('.md-toggle');
          if(cb){ const pre = cb.parentElement.querySelector('pre'); pre.style.display = pre.style.display==='none'? 'block':'none'; }
        });
        // initialize: hide long previews
        document.querySelectorAll('#agg tbody pre').forEach(p=>{ p.style.display = p.innerText.length>300 ? 'none' : 'block'; });

        // CSV export (exports currently visible rows)
        function exportCSV(){
          const rows = Array.from(document.querySelectorAll('#agg tbody tr')).filter(r=>!r.classList.contains('hidden'));
          const header = ['library','title','pages','text_length','images','json_file'];
          const out = [header.join(',')];
          rows.forEach(r=>{
            const tds = r.querySelectorAll('td');
            const lib = tds[0].innerText.trim();
            const title = tds[1].innerText.trim().replace(/"/g,'""');
            const pages = tds[2].innerText.trim();
            const textlen = tds[3].innerText.trim();
            const images = tds[4].innerText.trim();
            const jsonLink = tds[5].querySelector('a') ? tds[5].querySelector('a').getAttribute('href') : '';
            out.push([lib, '"'+title+'"', pages, textlen, images, jsonLink].join(','));
          });
          const csv = out.join('\n');
          const a = document.createElement('a');
          a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
          a.download = 'aggregated_visible.csv';
          document.body.appendChild(a); a.click(); a.remove();
        }

        // Sorting (client-side) + persist state in URL
        let _sortDir = 1; let _sortCol = -1;
        function loadStateFromUrl(){
          try{
            const params = new URLSearchParams(location.search);
            const q = params.get('q') || '';
            const sc = params.get('sort_col');
            const sd = params.get('sort_dir');
            if(q){ document.getElementById('q').value = q; filterTable(); }
            if(sc!==null){ _sortCol = parseInt(sc); _sortDir = parseInt(sd)||1; sortTable(_sortCol, _sortCol>1); }
          }catch(e){/*ignore*/}
        }
        function saveStateToUrl(){
          try{
            const params = new URLSearchParams(location.search);
            const q = document.getElementById('q').value || '';
            if(q) params.set('q', q); else params.delete('q');
            if(_sortCol>=0) { params.set('sort_col', _sortCol); params.set('sort_dir', _sortDir); } else { params.delete('sort_col'); params.delete('sort_dir'); }
            const s = params.toString();
            const url = s ? (location.pathname + '?' + s) : location.pathname;
            history.replaceState({}, '', url);
          }catch(e){/*ignore*/}
        }
        function sortTable(colIndex, numeric){
          const tbody = document.querySelector('#agg tbody');
          const rows = Array.from(tbody.querySelectorAll('tr'));
          if(_sortCol===colIndex) _sortDir = -_sortDir; else { _sortDir = 1; _sortCol = colIndex; }
          rows.sort((a,b)=>{
            const ta = a.children[colIndex].innerText.trim();
            const tb = b.children[colIndex].innerText.trim();
            if(numeric){
              const na = parseFloat(ta.replace(/[^\n0-9.-]+/g,''))||0;
              const nb = parseFloat(tb.replace(/[^\n0-9.-]+/g,''))||0;
              return (na-nb)*_sortDir;
            }
            return ta.localeCompare(tb)*_sortDir;
          });
          rows.forEach(r=>tbody.appendChild(r));
          saveStateToUrl();
          renderSummary();
        }

        // Simple SVG summary: pages/images per library + fonts/attachments chart
        function renderSummary(){
          const rows = Array.from(document.querySelectorAll('#agg tbody tr'));
          const data = {};
          const fontsCount = {};
          let totalAttachments = 0;
          let totalAnnotations = 0;
          rows.forEach(r=>{
            if(r.classList.contains('hidden')) return;
            const tds = r.querySelectorAll('td');
            const lib = tds[0].innerText.trim();
            const pages = parseInt(tds[2].innerText.trim()) || 0;
            const imgs = parseInt(tds[4].innerText.trim()) || 0;
            data[lib] = data[lib] || {pages:0, images:0};
            data[lib].pages += pages;
            data[lib].images += imgs;

            // fonts and attachments from data-attributes
            try{
              const f = JSON.parse(r.getAttribute('data-fonts')||'[]');
              f.forEach(fn=>{ fontsCount[fn] = (fontsCount[fn]||0)+1; });
              const at = JSON.parse(r.getAttribute('data-attachments')||'[]');
              totalAttachments += at.length;
              totalAnnotations += parseInt(r.getAttribute('data-annotations')||0) || 0;
            }catch(e){/*ignore*/}
          });

          // bar chart for pages/images per library (as before)
          const libs = Object.keys(data);
          const maxPages = Math.max(...libs.map(l=>data[l].pages), 1);
          const svgW = 400, svgH = 140, barH = 16, gap = 8;
          let svg = `<svg width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}" xmlns="http://www.w3.org/2000/svg">`;
          libs.forEach((l,i)=>{
            const y = i*(barH+gap)+8;
            const pw = Math.round((data[l].pages/maxPages)*(svgW-140));
            svg += `<text x="8" y="${y+12}" font-size="11" fill="#333">${l}</text>`;
            svg += `<rect x="120" y="${y}" width="${pw}" height="8" fill="#0366d6" />`;
            svg += `<text x="${120+pw+6}" y="${y+8}" font-size="11" fill="#333">${data[l].pages}</text>`;
            svg += `<text x="${svgW-50}" y="${y+12}" font-size="11" fill="#666">img:${data[l].images}</text>`;
          });
          svg += `</svg>`;
          document.getElementById('summary-chart').innerHTML = svg;

          // fonts top-5
          const fontEntries = Object.entries(fontsCount).sort((a,b)=>b[1]-a[1]).slice(0,5);
          const fontsHtml = fontEntries.length ? '<div><strong>Top fonts:</strong><ul>'+fontEntries.map(f=>`<li>${f[0]} (${f[1]})</li>`).join('')+'</ul></div>' : '';
          document.getElementById('summary-stats').innerHTML = `<div><strong>Total attachments:</strong> ${totalAttachments}</div><div><strong>Total annotations:</strong> ${totalAnnotations}</div>` + fontsHtml;
        }
        renderSummary();

        // allow downloading the current chart SVG as PNG
        function downloadChartPNG(){
          const svgEl = document.querySelector('#summary-chart svg');
          if(!svgEl) return alert('No chart to download');
          const svgData = new XMLSerializer().serializeToString(svgEl);
          const img = new Image();
          const svgBlob = new Blob([svgData], {type:'image/svg+xml;charset=utf-8'});
          const url = URL.createObjectURL(svgBlob);
          img.onload = function(){
            const canvas = document.createElement('canvas');
            canvas.width = img.width; canvas.height = img.height;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff'; ctx.fillRect(0,0,canvas.width,canvas.height);
            ctx.drawImage(img,0,0);
            URL.revokeObjectURL(url);
            const png = canvas.toDataURL('image/png');
            const a = document.createElement('a'); a.href = png; a.download = 'summary_chart.png'; document.body.appendChild(a); a.click(); a.remove();
          };
          img.src = url;
        }

        // wire filter -> persist
        document.getElementById('q').addEventListener('input', function(){ filterTable(); saveStateToUrl(); renderSummary(); });
        // load state from URL on init
        loadStateFromUrl();
      </script>
    </body>
    </html>
    """
    html_doc = (
        template.replace("%%ROWS_HTML%%", "".join(rows))
        .replace("%%AGG_PATH%%", html.escape(str(agg_path)))
        .replace("%%ROW_COUNT%%", str(len(rows)))
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    out = build_dashboard(AGG_PATH, OUT_HTML)
    print("Wrote:", out)
