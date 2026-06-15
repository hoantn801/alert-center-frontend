#!/usr/bin/env python3
"""Phase F multi-page builder - supersedes build_alert_center_page.py.

Builds from the SAME production home-shell snapshot + shared al-* widgets:
  alert_center.html    -> Web Page alert-center,   route /alerts (Dashboard v2 + alert list KEPT)
  alert_policies.html  -> Web Page alert-policies, route /alerts/policies
Output: 100% ASCII (entities / \\uXXXX), no Jinja, no external libs.
Usage: python3 build_alert_pages.py <home_snapshot_html> <out_dir>
"""
import re
import sys

SNAPSHOT, OUTDIR = sys.argv[1], sys.argv[2]


def demojibake(s):
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def to_entities(s):
    return "".join(c if ord(c) < 128 else "&#%d;" % ord(c) for c in s)


def js_escape(s):
    return "".join(c if ord(c) < 128 else "\\u%04x" % ord(c) for c in s)


def H(vn):
    return to_entities(vn)


src = open(SNAPSHOT, encoding="utf-8").read()


def block(a_pat, b_pat):
    a = src.find(a_pat)
    assert a >= 0, a_pat
    b = src.find(b_pat, a)
    assert b >= 0, b_pat
    return src[a:b + len(b_pat)]


csrf_patch = block('<script id="ec-csrf-fetch-patch">', "</script>")
a = src.find("function setActive")
nav_active = src[src.rfind("<script>", 0, a):src.find("</script>", a) + 9]
a = src.find("Hide Frappe default navbar")
hide_style = src[src.rfind("<style>", 0, a):src.find("</style>", a) + 8]
styles = [(m.start(), src.find("</style>", m.start()) + 8) for m in re.finditer(r"<style>", src)]
ma, mb = max(styles, key=lambda t: t[1] - t[0])
master_css = src[ma:mb]
svg_defs = block('<svg width="0" height="0"', "</svg>")
aside = block("<aside", "</aside>")
aside = re.sub(r"\{% if approvals_count %\}.*?\{% endif %\}", "", aside, flags=re.S)
aside = aside.replace('href="/app/user/{{ user_email }}"', 'href="/me" id="al-user-card"')
aside = aside.replace("{{ initials }}", "").replace("{{ full_name }}", "")
# MODULE SHELL: swap the generic homepage nav-section for an Alert Center menu
# (same shell/brand/search/footer; only the nav list changes - mirrors how the
# Approval page ships an approval-specific nav inside the same .ec-sidebar).
aside = re.sub(r"<nav class=\"nav-section\">.*?</nav>", "%%AC_NAV%%", aside, flags=re.S)

SHELL = "\n".join(to_entities(demojibake(p)) for p in (csrf_patch, hide_style, master_css, svg_defs))
ASIDE_TEMPLATE = to_entities(demojibake(aside))   # contains %%AC_NAV%% placeholder
NAV_ACTIVE = to_entities(demojibake(nav_active))


# Alert Center module menu (ASCII; svg icons from the shell's <defs>).
_AC_NAV = [
    ("group", "Alert Center"),
    ("/alerts", "i-grid", "Overview"),
    ("/alerts#al-alert-list", "i-bell", "Alerts"),  # Alerts subview on the /alerts page (hash subview)
    ("/alerts/policies", "i-wallet", "Price Setup"),
    ("/alerts/rules", "i-settings", "Rules"),
    ("/alerts/locks", "i-target", "Stock Safety"),  # route unchanged; Automation Pauses live inside this page
    ("group", "Operations"),
    ("/alerts/integration-health", "i-sparkles", "Integration Health"),  # G1: brand readiness page
    ("group", "Workspace"),
    ("/", "i-home", "Back to Workspace"),
]


def ac_aside(active_route):
    """Return the module aside with the Alert Center nav, active item marked
    for the current route (the nav-active script also re-marks on load)."""
    parts = ['<nav class="nav-section">']
    seen_routes = set()
    for entry in _AC_NAV:
        if entry[0] == "group":
            parts.append('<div class="nav-label">%s</div>' % to_entities(entry[1]))
            continue
        route, icon, label = entry
        # mark active only for the first link of the active route, and only for
        # real AC routes (not the catch-all /alerts shared by Dashboard+Alerts)
        is_active = (route == active_route and route not in seen_routes
                     and label in ("Overview", "Price Setup", "Rules", "Stock Safety",
                                   "Integration Health"))
        seen_routes.add(route)
        cls = "nav-item active" if is_active else "nav-item"
        parts.append(
            '<a href="%s" class="%s"><svg class="icon"><use href="#%s"/></svg>'
            '<span>%s</span></a>' % (route, cls, icon, to_entities(label)))
    parts.append("</nav>")
    return ASIDE_TEMPLATE.replace("%%AC_NAV%%", "\n".join(parts))

SHARED_CSS = """
<style id="ec-alert-center-css">
.al-filters{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px;border-bottom:1px solid var(--gray-200);align-items:flex-end}
.al-filters label{display:block;font-size:10.5px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px}
.al-filters select,.al-filters input{padding:7px 10px;border:1px solid var(--gray-200);border-radius:8px;font-size:13px;background:#fff;font-family:inherit;min-width:110px}
.al-filters select:focus,.al-filters input:focus{outline:none;border-color:var(--navy)}
.al-btn{padding:8px 14px;border-radius:8px;border:1px solid var(--gray-200);background:#fff;font-size:13px;font-weight:600;color:var(--gray-700);cursor:pointer;font-family:inherit}
.al-btn:hover{background:var(--gray-50)}
.al-btn.primary{background:var(--navy);border-color:var(--navy);color:#fff}
.al-btn.danger{background:var(--pink);border-color:var(--pink);color:#fff}
.al-btn:disabled{opacity:.5;cursor:not-allowed}
.al-tbl-wrap{overflow-x:auto}
.al-tbl{width:100%;border-collapse:collapse;font-size:13px}
.al-tbl th{position:sticky;top:0;background:var(--gray-50);text-align:left;padding:9px 10px;font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--gray-500);border-bottom:1px solid var(--gray-200);white-space:nowrap}
.al-tbl td{padding:9px 10px;border-bottom:1px solid var(--gray-100);color:var(--gray-800);white-space:nowrap}
.al-tbl tbody tr{cursor:pointer}
.al-tbl tbody tr:hover{background:var(--navy-50)}
.al-badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:700}
.al-b-critical{background:var(--pink-50);color:var(--pink)}
.al-b-warning{background:var(--yellow-50);color:#8a6d00}
.al-b-info{background:var(--gray-100);color:var(--gray-600)}
.al-b-open{background:var(--navy-50);color:var(--navy)}
.al-b-review{background:var(--yellow-50);color:#8a6d00}
.al-b-resolved{background:#e7f6ee;color:var(--green)}
.al-b-ignored{background:var(--gray-100);color:var(--gray-500)}
.al-b-dryrun{background:var(--navy-50);color:var(--navy)}
.al-b-pending{background:var(--yellow-50);color:#8a6d00}
.al-b-skipped{background:var(--gray-100);color:var(--gray-500)}
.al-b-draft{background:var(--gray-100);color:var(--gray-600)}
.al-b-active{background:#e7f6ee;color:var(--green)}
.al-b-paused{background:var(--yellow-50);color:#8a6d00}
.al-b-expired{background:var(--gray-100);color:var(--gray-500)}
.al-pager{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;font-size:12.5px;color:var(--gray-500)}
.al-drawer{position:fixed;top:0;right:0;width:460px;max-width:94vw;height:100vh;background:#fff;border-left:1px solid var(--gray-200);box-shadow:-12px 0 36px rgba(15,23,42,.12);z-index:60;display:flex;flex-direction:column}
.al-drawer-head{padding:14px 18px;border-bottom:1px solid var(--gray-200);display:flex;justify-content:space-between;align-items:center}
.al-drawer-body{padding:14px 18px;overflow-y:auto;flex:1}
.al-kv{display:grid;grid-template-columns:130px 1fr;gap:6px 10px;font-size:13px;margin-bottom:14px}
.al-kv dt{color:var(--gray-500)}.al-kv dd{margin:0;color:var(--gray-900);font-weight:500;word-break:break-word;white-space:normal}
.al-drawer-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 18px;border-top:1px solid var(--gray-200)}
.al-more{position:relative;margin-left:auto}
.al-more-menu{position:absolute;right:0;bottom:calc(100% + 6px);background:#fff;border:1px solid var(--gray-200);border-radius:8px;box-shadow:0 10px 28px rgba(15,23,42,.16);padding:6px;min-width:150px;z-index:80}
.al-more-menu .al-btn{width:100%;justify-content:flex-start}
.al-overlay{position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:55}
.al-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border-radius:14px;box-shadow:0 24px 64px rgba(15,23,42,.25);z-index:70;width:460px;max-width:94vw;max-height:88vh;overflow-y:auto;padding:18px}
.al-modal.wide{width:760px}
.al-modal h3{margin:0 0 10px;font-size:15px;color:var(--gray-900)}
.al-modal textarea,.al-modal input,.al-modal select{width:100%;padding:8px 10px;border:1px solid var(--gray-200);border-radius:8px;font-size:13px;font-family:inherit;margin-bottom:10px}
.al-modal-foot{display:flex;justify-content:flex-end;gap:8px}
.al-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--gray-900);color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;z-index:90;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.al-empty{padding:46px 16px;text-align:center;color:var(--gray-500);font-size:13.5px}
.al-noaccess{max-width:480px;margin:80px auto;text-align:center;color:var(--gray-600)}
.al-actrows{font-size:12.5px;border-top:1px dashed var(--gray-200);padding-top:10px;margin-top:6px}
/* Phase F additions - tokens only, no new visual language */
.al-subnav{display:flex;gap:4px;padding:10px 24px 0;border-bottom:1px solid var(--gray-200);background:#fff}
.al-subnav a{padding:9px 14px;border-radius:8px 8px 0 0;font-size:13px;font-weight:600;color:var(--gray-600);text-decoration:none}
.al-subnav a:hover{background:var(--gray-50);color:var(--gray-900)}
.al-subnav a.active{color:var(--navy);border:1px solid var(--gray-200);border-bottom:2px solid #fff;background:#fff;margin-bottom:-1px}
.al-dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin-bottom:14px}
.al-bars{display:flex;flex-direction:column;gap:7px;padding:12px 16px}
.al-bar-row{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--gray-700)}
.al-bar-key{width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.al-bar-track{flex:1;background:var(--gray-100);border-radius:6px;height:14px;overflow:hidden}
.al-bar-fill{height:14px;border-radius:6px;background:var(--navy);transition:width .2s}
.al-bar-fill.warn{background:#c9a200}.al-bar-fill.crit{background:var(--pink)}
/* SLA aging: progressively stronger warning colours for older buckets */
.al-bar-fill.age0{background:#5b9bd5}.al-bar-fill.age1{background:#e0a800}
.al-bar-fill.age2{background:#e8590c}.al-bar-fill.age3{background:var(--pink)}
.al-bar-n{width:40px;text-align:right;font-weight:700;color:var(--gray-900)}
.al-csv-ok{color:var(--green);font-weight:700}.al-csv-err{color:var(--pink);font-weight:700}
.al-rowlink{cursor:pointer}.al-rowlink:hover{background:var(--gray-50)}
.al-rowlink:focus-visible{outline:2px solid var(--navy);outline-offset:-2px}
.al-banner{margin:0 0 14px;padding:10px 14px;border:1px solid var(--yellow);background:var(--yellow-50);border-radius:10px;font-size:12.5px;color:#8a6d00;font-weight:600}
.al-note{margin:0 0 12px;padding:8px 12px;border:1px solid var(--gray-200);background:var(--gray-50);border-radius:8px;font-size:12px;color:var(--gray-600);line-height:1.4;display:flex;gap:8px;align-items:flex-start}
.al-note .al-note-ic{flex:0 0 auto;color:var(--gray-400);font-weight:700}
/* G1.1 Drop 2: bulk actions + occurrence column + evidence breakdown */
.al-bulkbar{display:flex;align-items:center;gap:8px;margin-left:auto;margin-right:12px;font-size:12.5px;color:var(--gray-700);background:var(--navy-50);padding:5px 10px;border-radius:8px}
.al-bulkbar #al-bulk-n{font-weight:700;color:var(--navy)}
.al-chk-col{width:30px;text-align:center}
.al-tbl td.al-chk-col input,.al-tbl th.al-chk-col input{cursor:pointer}
.al-occ-n{display:inline-block;min-width:20px;padding:1px 7px;border-radius:999px;background:var(--navy-50);color:var(--navy);font-weight:700;font-size:12px;text-align:center}
/* UX polish 2026-06-10: occurrence count prominent; multi-order cases pop */
.al-occ-n.multi{background:var(--pink);color:#fff;font-size:13px;min-width:24px}
.al-case-pill{display:inline-block;margin-left:8px;padding:2px 10px;border-radius:999px;background:var(--pink);color:#fff;font-weight:700;font-size:12px;vertical-align:middle}
.al-occ-wrap.hl{border:1px solid var(--pink);border-radius:10px;padding:8px 10px;background:#fff}
.al-breakdown{margin:6px 0 14px;border:1px solid var(--gray-200);border-radius:10px;padding:10px 12px;font-size:12.5px;background:var(--gray-50)}
.al-breakdown table{width:100%;border-collapse:collapse}
.al-breakdown td{padding:2px 0}
.al-breakdown td.r{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.al-breakdown tr.eff td{border-top:1px solid var(--gray-300);padding-top:5px;color:var(--navy);font-weight:700}
.al-breakdown td.minus{color:var(--pink)}
.al-occ-wrap{margin-top:8px}
.al-occ-wrap .al-fsec{margin:14px 0 6px}
.al-occ-tbl{width:100%;border-collapse:collapse;font-size:11.5px}
.al-occ-tbl th{position:sticky;top:0;background:var(--gray-50);text-align:left;padding:6px 7px;font-size:10px;text-transform:uppercase;letter-spacing:.4px;color:var(--gray-500);border-bottom:1px solid var(--gray-200);white-space:nowrap}
.al-occ-tbl td{padding:6px 7px;border-bottom:1px solid var(--gray-100);white-space:nowrap}
.al-occ-tbl td.r{text-align:right;font-variant-numeric:tabular-nums}
/* B2: selectable evidence rows drive the calculation panel */
.al-calc{position:sticky;top:0;background:#fff;z-index:3;padding-top:2px}
.al-occ-row{cursor:pointer}
.al-occ-tbl tbody tr.al-occ-row:hover{background:var(--gray-50)}
.al-occ-tbl tbody tr.al-occ-sel{background:var(--navy-50);box-shadow:inset 3px 0 0 var(--navy)}
.al-occ-row:focus-visible{outline:2px solid var(--navy);outline-offset:-2px}
/* G1.1 Drop 2 polish: alert detail as a centered wide modal */
.al-modal.al-modal-xl{width:1140px;max-width:96vw;max-height:85vh;padding:0;display:flex;flex-direction:column;overflow:hidden}
.al-modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:14px 20px;border-bottom:1px solid var(--gray-200)}
.al-modal-head strong{font-size:15px;color:var(--gray-900)}
.al-d-sub{font-size:12.5px;color:var(--gray-500);margin-top:3px}
.al-modal-body{padding:16px 20px;overflow-y:auto;flex:1}
.al-modal-foot{display:flex;flex-wrap:wrap;gap:8px;padding:12px 20px;border-top:1px solid var(--gray-200)}
.al-kv-wide{grid-template-columns:repeat(3, max-content 1fr);gap:7px 16px}
@media (max-width:820px){.al-kv-wide{grid-template-columns:max-content 1fr}}
.al-occ-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.al-occ-head .al-btn{padding:5px 10px;font-size:12px}
/* hourly trend chart (top-right of /alerts) */
.al-top-row{display:flex;gap:14px;align-items:stretch;flex-wrap:wrap;margin-bottom:14px}
.al-top-row .stats-strip{flex:1 1 520px;margin-bottom:0}
.al-hour-panel{flex:1 1 360px;min-width:300px;display:flex;flex-direction:column}
.al-hour-chart{padding:8px 12px 4px;flex:1;display:flex;align-items:flex-end}
.al-hour-chart svg{width:100%;height:140px}
.al-hour-legend{display:flex;gap:14px;padding:0 12px 8px;font-size:11px;color:var(--gray-500)}
/* Policy/rule drawer form (redesign) - sectioned 2-col grid, helper text */
.al-drawer-wide{width:620px;max-width:96vw}
.al-fsec{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--navy);border-bottom:1px solid var(--gray-200);padding:6px 0;margin:16px 0 10px}
.al-fsec:first-child{margin-top:0}
.al-fgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px}
.al-fld{display:flex;flex-direction:column;min-width:0}
.al-fld.al-col2{grid-column:1 / -1}
.al-fld label{font-size:11px;font-weight:600;color:var(--gray-600);margin-bottom:4px}
.al-fld input,.al-fld select{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--gray-200);border-radius:8px;font-size:13px;font-family:inherit;background:#fff;height:38px}
.al-fld input:focus,.al-fld select:focus{outline:none;border-color:var(--navy)}
.al-help{font-size:11px;color:var(--gray-500);margin-top:4px;line-height:1.35}
.al-req{color:var(--pink);font-weight:700}
.al-opt{color:var(--gray-400);font-weight:400}
.al-lockbox{margin-top:10px;padding:10px 12px;border:1px dashed var(--gray-300);border-radius:8px;background:var(--gray-50)}
.al-check{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--gray-800)}
.al-check input{width:auto;height:auto}\n.al-inline{display:flex;gap:8px}\n.al-inline input{flex:1}\n.al-inline .al-btn{white-space:nowrap}
/* G1 Integration Health - status pills (tokens only) + blocker list + snippet */
.al-st{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11.5px;font-weight:700;white-space:nowrap}
.al-st-ready{background:#e7f6ee;color:var(--green)}
.al-st-blocked{background:var(--pink-50);color:var(--pink)}
.al-st-warning{background:var(--yellow-50);color:#8a6d00}
.al-st-running{background:var(--navy-50);color:var(--navy)}
.al-st-sched{background:#e7f6ee;color:var(--green);border:1px solid var(--green)}
.al-st-manual{background:var(--yellow-50);color:#8a6d00;border:1px dashed #c9a200}
.al-run-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--navy);margin-left:6px;vertical-align:middle;animation:al-pulse 1.2s infinite}
@keyframes al-pulse{0%,100%{opacity:.3}50%{opacity:1}}
.al-blk{list-style:none;padding:0;margin:8px 0}
.al-blk li{padding:7px 10px;border-radius:8px;margin-bottom:6px;font-size:12.5px;border:1px solid var(--gray-200)}
.al-blk li.blocker{background:var(--pink-50);border-color:var(--pink-50);color:var(--pink)}
.al-blk li.warning{background:var(--yellow-50);border-color:var(--yellow-50);color:#8a6d00}
.al-action-box{margin:10px 0;padding:10px 12px;border-radius:8px;background:var(--navy-50);color:var(--navy);font-size:13px;font-weight:600}
.al-tech{margin-top:14px;border-top:1px solid var(--gray-200);padding-top:4px}
.al-tech>summary{list-style:none;color:var(--gray-500);outline:none}
.al-tech>summary::-webkit-details-marker{display:none}
.al-tech[open]>summary{color:var(--navy)}
.al-snippet{background:var(--gray-900);color:#e6edf3;border-radius:8px;padding:10px 12px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all;margin:6px 0}
.al-cap{display:flex;align-items:center;gap:10px;font-size:12.5px;color:var(--gray-600)}
.al-cap-track{flex:1;max-width:260px;background:var(--gray-100);border-radius:6px;height:12px;overflow:hidden}
.al-cap-fill{height:12px;background:var(--navy);border-radius:6px;min-width:2px}
.al-cap-fill.warn{background:#c9a200}
@media (max-width:560px){.al-fgrid{grid-template-columns:1fr}}
/* ===========================================================================
   AC-POLISH-2026-06-14 - shared Alert Center visual layer.
   Maps 1:1 to ERP Homepage tokens (navy/gray/yellow/pink; radius 8/12px;
   Inter). Additive refinements only: no new palette, no gradients, no
   external libs, no behaviour change. Improves button/control consistency,
   toolbar alignment, table density, chips, KPI rhythm, focus/hover states.
   =========================================================================== */
/* Buttons: one control height + clear interactive states */
.ecentric-app .al-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:34px;padding:0 14px;line-height:1;white-space:nowrap;transition:background .15s,border-color .15s,color .15s,box-shadow .15s}
.ecentric-app .al-btn:hover{border-color:var(--gray-300)}
.ecentric-app .al-btn.primary:hover{background:var(--navy-700);border-color:var(--navy-700)}
.ecentric-app .al-btn.danger:hover{filter:brightness(.96)}
.ecentric-app .al-btn:active{transform:translateY(1px)}
.ecentric-app .al-btn:disabled{opacity:.45;cursor:not-allowed}
.ecentric-app .al-btn:focus-visible,.ecentric-app .al-filters input:focus-visible,.ecentric-app .al-filters select:focus-visible,.ecentric-app .al-fld input:focus-visible,.ecentric-app .al-fld select:focus-visible,.ecentric-app .al-chip:focus-visible,.ecentric-app .al-tbl tbody tr:focus-visible{outline:2px solid var(--navy);outline-offset:2px}
/* Quiet icon/close buttons in drawer + modal headers */
.ecentric-app .al-drawer-head .al-btn,.ecentric-app .al-modal-head .al-btn{height:30px;padding:0 9px;color:var(--gray-500)}
.ecentric-app .al-drawer-head .al-btn:hover,.ecentric-app .al-modal-head .al-btn:hover{background:var(--gray-100);color:var(--gray-900);border-color:var(--gray-200)}
/* Toolbar action group inside a panel header (consistent gap + alignment) */
.ecentric-app .al-hdr-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ecentric-app .panel-header{min-height:52px;gap:12px}
/* Filters: every control on one baseline height, tidy spacing */
.ecentric-app .al-filters{gap:10px 12px;padding:14px 16px;align-items:end}
.ecentric-app .al-filters select,.ecentric-app .al-filters input{height:34px;box-sizing:border-box}
.ecentric-app .al-filters .al-btn{align-self:end}
/* Brand / coverage chips: clearly clickable, count pill inside */
.ecentric-app .al-chip{display:inline-flex;align-items:center;gap:8px;height:30px;padding:0 6px 0 12px;border:1px solid var(--gray-200);border-radius:999px;background:#fff;font-size:12.5px;font-weight:600;color:var(--gray-700);cursor:pointer;font-family:inherit;transition:border-color .15s,background .15s,color .15s}
.ecentric-app .al-chip:hover{border-color:var(--navy);color:var(--navy);background:var(--navy-50)}
.ecentric-app .al-chip .al-chip-n{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:20px;padding:0 6px;border-radius:999px;background:var(--gray-100);color:var(--gray-600);font-size:11.5px;font-weight:700}
.ecentric-app .al-chip.warn{border-color:var(--yellow)}
.ecentric-app .al-chip.warn .al-chip-n{background:var(--yellow-50);color:#8a6d00}
.ecentric-app .al-chip.ok{color:var(--green)}
.ecentric-app .al-chip.ok .al-chip-n{background:#e7f6ee;color:var(--green)}
/* Tables: quality scrollbar, sticky-header rule, subtle zebra, mid-align */
.ecentric-app .al-tbl-wrap{scrollbar-width:thin;scrollbar-color:var(--gray-300) transparent}
.ecentric-app .al-tbl-wrap::-webkit-scrollbar{height:9px;width:9px}
.ecentric-app .al-tbl-wrap::-webkit-scrollbar-thumb{background:var(--gray-300);border-radius:6px}
.ecentric-app .al-tbl-wrap::-webkit-scrollbar-thumb:hover{background:var(--gray-400)}
.ecentric-app .al-tbl th{box-shadow:inset 0 -1px 0 var(--gray-200);z-index:1}
.ecentric-app .al-tbl td,.ecentric-app .al-tbl th{vertical-align:middle}
.ecentric-app .al-tbl tbody tr:nth-child(even){background:var(--gray-50)}
.ecentric-app .al-tbl tbody tr:hover{background:var(--navy-50)}
/* Status badges: even vertical rhythm */
.ecentric-app .al-badge{line-height:1.5;letter-spacing:.2px;vertical-align:middle}
/* KPI strip on the dashboard (6 cards): even, equal-height grid */
.ecentric-app .al-top-row .stats-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.ecentric-app .stat-value{font-variant-numeric:tabular-nums}
@media (max-width:1100px){.ecentric-app .al-top-row .stats-strip{grid-template-columns:repeat(2,1fr)}}
/* Pager controls: compact + equal */
.ecentric-app .al-pager .al-btn{height:30px;min-width:34px;padding:0 10px}
/* Notes / banners: vertical centering for one-line messages */
.ecentric-app .al-note{align-items:center}
/* Drawer + modal titles to homepage scale */
.ecentric-app .al-drawer-head strong,.ecentric-app .al-modal-head strong{font-size:15px;font-weight:700;color:var(--gray-900)}
/* Pre-E2E 2026-06-14: interactive KPI cards + advanced filter zone + chips */
.ecentric-app .stat-card.kpi{cursor:pointer;user-select:none;transition:border-color .15s,box-shadow .15s}
.ecentric-app .stat-card.kpi:hover{border-color:var(--gray-300);box-shadow:0 4px 12px rgba(0,0,0,.06)}
.ecentric-app .stat-card.kpi:focus-visible{outline:2px solid var(--navy);outline-offset:2px}
.ecentric-app .stat-card.kpi.kpi-active{border-color:var(--navy);box-shadow:0 0 0 1px var(--navy) inset}
.ecentric-app .stat-card.s-gray::before{background:var(--gray-400)}
.ecentric-app .al-adv{display:flex;flex-wrap:wrap;gap:10px 12px;padding:14px 16px;margin:6px 12px 12px;align-items:end;background:var(--gray-50);border:1px solid var(--gray-100);border-radius:10px}
.ecentric-app .al-adv[hidden]{display:none}
.ecentric-app .al-adv label{display:block;font-size:10.5px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px}
.ecentric-app .al-adv select,.ecentric-app .al-adv input{height:34px;box-sizing:border-box;padding:7px 10px;border:1px solid var(--gray-200);border-radius:8px;font-size:13px;background:#fff;font-family:inherit;min-width:110px}
.ecentric-app .al-adv select:focus,.ecentric-app .al-adv input:focus{outline:none;border-color:var(--navy)}
.ecentric-app .al-fchips{display:flex;flex-wrap:wrap;gap:6px;padding:10px 16px;align-items:center}
.ecentric-app .al-fchip{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 4px 0 10px;border:1px solid var(--gray-200);border-radius:999px;background:var(--gray-50);font-size:12px;color:var(--gray-600)}
.ecentric-app .al-fchip b{font-weight:700;color:var(--gray-900)}
.ecentric-app .al-fchip button{border:none;background:transparent;cursor:pointer;color:var(--gray-400);font-size:15px;line-height:1;padding:0 3px;height:auto}
.ecentric-app .al-fchip button:hover{color:var(--pink)}
.ecentric-app .al-fchip-clear{height:26px;padding:0 10px;font-size:12px}
/* UI/UX consolidation 2026-06-15: Overview Alert Distribution card + secondary KPI */
/* ECharts 2026-06-15: Alert Distribution (3 mini donuts) + trend combo */
.ecentric-app .al-charts3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:8px 12px 12px}
.ecentric-app .al-chartbox{border:1px solid var(--gray-100);border-radius:10px;padding:6px 6px 2px}
.ecentric-app .al-chart-h{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--gray-500);text-align:center;padding:4px 0 0}
.ecentric-app .al-chart{width:100%;height:200px}
.ecentric-app .al-chart-trend{height:240px;padding:0 8px}
.ecentric-app .al-chart-fb{padding:6px 10px 10px}
.ecentric-app .al-chart-fbt{width:100%;font-size:12px}
.ecentric-app .al-chart-fbt td,.ecentric-app .al-chart-fbt th{padding:4px 8px;border-bottom:1px solid var(--gray-100)}
.ecentric-app .al-chart-fbt .r{text-align:right}
.ecentric-app .al-chart-days{font-size:12px;color:var(--gray-500);display:inline-flex;align-items:center;gap:6px}
.ecentric-app .al-chart-days select{height:28px;border:1px solid var(--gray-200);border-radius:6px;font-family:inherit;font-size:12px;padding:0 6px}
@media (max-width:1100px){.ecentric-app .al-charts3{grid-template-columns:1fr}}
.ecentric-app .al-help-i{display:inline-flex;align-items:center;justify-content:center;cursor:help;color:var(--gray-400);font-size:12px;margin-left:7px;vertical-align:middle;line-height:1;transition:color .15s}
.ecentric-app .al-help-i:hover{color:var(--navy)}
.ecentric-app .al-help-i:focus-visible{outline:2px solid var(--navy);outline-offset:2px;border-radius:3px;color:var(--navy)}
.ecentric-app .al-tierleg{display:inline-flex;align-items:center;gap:2px;cursor:help;font-size:12.5px;color:var(--gray-600)}
.ecentric-app .al-tierleg:hover{color:var(--navy)}
.ecentric-app .al-tierleg:focus-visible{outline:2px solid var(--navy);outline-offset:2px;border-radius:4px}
.ecentric-app .ru-brand{margin-bottom:14px;border:1px solid var(--gray-200);border-radius:10px;overflow:hidden}
.ecentric-app .ru-brand-h{font-size:13px;font-weight:700;color:var(--gray-900);padding:8px 14px;background:var(--gray-50);border-bottom:1px solid var(--gray-200)}
/* E2 brand-card behaviour editor */
.ecentric-app .ru-beh{padding:8px 0;border-bottom:1px solid var(--gray-100)}
.ecentric-app .ru-beh:last-child{border-bottom:0}
.ecentric-app .ru-beh-row{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px}
.ecentric-app .ru-beh-h{font-weight:700;font-size:13px;min-width:160px;color:var(--gray-900)}
.ecentric-app .ru-beh-all{display:flex;align-items:center;gap:8px;font-size:13px}
.ecentric-app .ru-pf{display:inline-block;min-width:96px;font-size:12px;color:var(--gray-500)}
.ecentric-app .ru-pf-all{font-weight:600;color:var(--gray-700)}
.ecentric-app .ru-ovrow{display:flex;align-items:center;gap:8px;padding:3px 0 3px 8px;font-size:12.5px}
.ecentric-app .ru-inh{color:var(--gray-400);font-style:italic}
.ecentric-app .ru-cust{margin:4px 0 0 8px;border-top:0;padding-top:0}
.ecentric-app .ru-cust .al-btn{height:26px;font-size:12px;padding:0 8px}
.ecentric-app .al-adv-sec{margin-top:14px;border-top:1px solid var(--gray-200);padding-top:6px}
.ecentric-app .al-adv-sec>summary{cursor:pointer;color:var(--navy)}
.ecentric-app .al-modesw{display:inline-flex;margin-left:10px;vertical-align:middle}
.ecentric-app .al-modesw .al-btn{height:26px;font-size:12px;border-radius:0;padding:0 12px}
.ecentric-app .al-modesw .al-btn:first-child{border-radius:6px 0 0 6px}
.ecentric-app .al-modesw .al-btn:last-child{border-radius:0 6px 6px 0;border-left:0}
.ecentric-app .stat-card.kpi-sec{opacity:.85}
.ecentric-app .stat-card.kpi-sec .stat-value{font-size:21px}
[hidden]{display:none !important}
@media (max-width:760px){.al-drawer{width:100vw}.al-kv{grid-template-columns:110px 1fr}.al-dash-grid{grid-template-columns:1fr}}
</style>
"""

VN = {
    "loading": "Đang tải...",
    "no_rows": "Không có dữ liệu khớp bộ lọc.",
    "note_required": "Cần nhập ghi chú.",
    "done": "Đã cập nhật.",
    "pause_done": "Đã tạo automation pause.",
    "saved": "Đã lưu.",
    "imported": "Import xong: ",
    "err": "Lỗi: ",
    "copy_ok": "Đã copy lỗi vào clipboard.",
}
VNJ = {k: js_escape(v) for k, v in VN.items()}

# Canonical business-label map for rule codes (UI/UX consolidation 2026-06-15).
# Backend codes are unchanged; the FE shows these labels and keeps the raw code
# only in tooltips / technical detail. Self-contained for now; a future
# EC Field Description DocType can supersede this via a read-only API.
_RULE_LABELS = {
    "below_min": "Thấp hơn giá tối thiểu",
    "above_high": "Cao hơn ngưỡng cảnh báo",
    "severe_price_drop": "Giảm giá nghiêm trọng",
    "possible_missing_zero": "Nghi thiếu số 0",
    "missing_brand_mapping": "Thiếu cấu hình brand",
    "missing_policy": "Thiếu Price Policy",
    "ingestion_api_failed": "Lỗi đồng bộ dữ liệu",
    "missing_integration_credential": "Thiếu thông tin kết nối",
    "stock_lock_api_failed": "Lỗi xử lý Stock Safety",
}
_RULE_LABELS_JS = "{" + ",".join(
    '"%s":"%s"' % (k, js_escape(v)) for k, v in _RULE_LABELS.items()) + "}"

# Shared JS namespace - every page loads this once.
SHARED_JS = """
<script id="ec-alert-shared">
window.AL=(function(){
"use strict";
var API="/api/method/ecentric_workspace.alerts.";
function call(m,args){return fetch(API+m,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json","Accept":"application/json"},body:JSON.stringify(args||{})}).then(function(r){return r.json().catch(function(){return {};}).then(function(j){if(!r.ok){var msg="HTTP "+r.status;try{if(j._server_messages){var arr=JSON.parse(j._server_messages);msg=arr.map(function(s){return JSON.parse(s).message;}).join("; ");}else if(j.exception){msg=j.exception.split(":").pop();}}catch(e){}var err=new Error(msg);err.status=r.status;throw err;}return j.message;});});}
function $(id){return document.getElementById(id);}
function esc(s){var d=document.createElement("div");d.textContent=(s==null?"":String(s));return d.innerHTML;}
var fmtN=new Intl.NumberFormat("vi-VN");
function money(v){return (v==null||v==="")?"-":fmtN.format(Math.round(v));}
function dt(v){if(!v)return "-";return String(v).slice(5,16);}
function toast(m){var t=$("al-toast");t.textContent=m;t.hidden=false;setTimeout(function(){t.hidden=true;},2800);}
function badge(v,map,fb){if(!v)return "-";return '<span class="al-badge '+(map[v]||fb||"al-b-info")+'">'+esc(v)+'</span>';}
function sevBadge(v){return badge(v,{Critical:"al-b-critical",Warning:"al-b-warning",Info:"al-b-info"});}
function stBadge(v){return badge(v,{"Open":"al-b-open","In Review":"al-b-review","Resolved":"al-b-resolved","Ignored":"al-b-ignored"});}
function actBadge(v){return badge(v,{"Dry Run":"al-b-dryrun","Pending":"al-b-pending","Skipped":"al-b-skipped","Success":"al-b-resolved","Failed":"al-b-critical","Cancelled":"al-b-ignored","Processing":"al-b-pending"});}
function polBadge(v){return badge(v,{"Draft":"al-b-draft","Active":"al-b-active","Paused":"al-b-paused","Expired":"al-b-expired","Inactive":"al-b-ignored"});}
function fillUser(route){fetch("/api/method/frappe.auth.get_logged_user",{credentials:"include"}).then(function(r){return r.json();}).then(function(j){var u=j.message||"";if(u==="Guest"){window.location.href="/login?redirect-to="+route;return;}var card=$("al-user-card");if(card){var nm=card.querySelector(".user-name"),av=card.querySelector(".avatar");if(nm)nm.textContent=u.split("@")[0];if(av)av.textContent=(u[0]||"?").toUpperCase();}}).catch(function(){});}
function noAccess(){document.querySelector(".content").innerHTML='<div class="al-noaccess"><h2>Alert Center</h2><p>T\\u00e0i kho\\u1ea3n c\\u1ee7a b\\u1ea1n ch\\u01b0a \\u0111\\u01b0\\u1ee3c g\\u00e1n brand n\\u00e0o trong Brand Approver. Li\\u00ean h\\u1ec7 System Manager.</p></div>';}
function initScope(route,cb){fillUser(route);loadFieldHelp();call("api_alerts.my_scope").then(function(scope){cb(scope);}).catch(function(e){if(e.status===403){noAccess();}else{toast("%(err)s"+e.message);}});}
function dateStr(d){function p(n){return (n<10?"0":"")+n;}return d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate());}
function stHealth(s){var m={"Ready":"al-st-ready","Blocked":"al-st-blocked","Warning":"al-st-warning","Delayed":"al-st-warning","Running":"al-st-running","Scheduler Enabled":"al-st-sched","Manual Pull Required":"al-st-manual","Not Configured":"al-st-manual"};return '<span class="al-st '+(m[s]||"al-st-warning")+'">'+esc(s)+'</span>';}
function daysAgo(n){var d=new Date();d.setDate(d.getDate()-n);return dateStr(d);}
function fillBrandSelect(sel,scope,opts){opts=opts||{};if(!sel)return;sel.innerHTML="";
  if(opts.allOption){var a=document.createElement("option");a.value="";a.textContent=opts.allOption;sel.appendChild(a);}
  var brands=Object.keys((scope&&scope.brands)||{});
  if(opts.extra&&brands.indexOf(opts.extra)<0)brands.push(opts.extra);
  brands.forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;sel.appendChild(o);});
  if(!brands.length&&!opts.allOption){var d=document.createElement("option");d.value="";d.textContent=opts.emptyText||"Kh\\u00f4ng c\\u00f3 brand trong scope";d.disabled=true;sel.appendChild(d);}
  if(opts.value)sel.value=opts.value;}
var RULE_LABELS=%(rule_labels)s;
// EC Field Description adapter: ONE cached, defensive read of the custom DocType
// (DB-only; not in app source). Records keyed "alert.rule.<code>" with a label /
// description OVERRIDE the built-in fallback labels; if the DocType, fields, or
// permission are unavailable the read fails silently and the fallback is used.
var FIELD_HELP={};
function fieldHelp(key){return FIELD_HELP[key]||null;}
function loadFieldHelp(){return fetch("/api/method/frappe.client.get_list?doctype=EC%%20Field%%20Description&fields=[%%22name%%22,%%22label%%22,%%22description%%22]&limit_page_length=0",{credentials:"include",headers:{Accept:"application/json"}}).then(function(r){return r.ok?r.json():null;}).then(function(j){var rows=(j&&j.message)||[];rows.forEach(function(x){if(x&&x.name)FIELD_HELP[x.name]={label:x.label||"",help:x.description||""};});}).catch(function(){});}
function ruleLabel(c){var h=FIELD_HELP["alert.rule."+c];return (h&&h.label)||RULE_LABELS[c]||c||"-";}
function ruleCell(c){if(!c)return "-";var l=ruleLabel(c);if(l===c)return esc(c);return '<span title="'+esc(c)+'">'+esc(l)+'</span>';}
// Relabel a <select> of raw rule_code options to business labels in place. The
// option VALUE stays the raw code (backend filter unchanged); only the visible
// text becomes the business label, with the raw code kept in a title tooltip.
// E1 FIX: an <option> with no value attribute returns its TEXT as .value, so
// relabelling the text used to make the select submit the localized label as the
// rule_code ("Rule Code cannot be ..."). Pin the raw code onto o.value FIRST so
// the canonical code is always what gets sent, then change only the display text.
function relabelRuleOptions(sel){if(!sel)return;Array.prototype.forEach.call(sel.options,function(o){var raw=o.value;if(!raw)return;o.value=raw;var l=ruleLabel(raw);if(l&&l!==raw){o.textContent=l;o.title=raw;}});}
return {call:call,$:$,esc:esc,money:money,dt:dt,toast:toast,sevBadge:sevBadge,stBadge:stBadge,actBadge:actBadge,polBadge:polBadge,initScope:initScope,daysAgo:daysAgo,dateStr:dateStr,fillBrandSelect:fillBrandSelect,stHealth:stHealth,ruleLabel:ruleLabel,ruleCell:ruleCell,relabelRuleOptions:relabelRuleOptions,fieldHelp:fieldHelp,loadFieldHelp:loadFieldHelp};
})();
</script>
""" % dict(VNJ, rule_labels=_RULE_LABELS_JS)


def subnav(active):
    items = [("/alerts", "Overview"), ("/alerts#al-alert-list", "Alerts"),
             ("/alerts/policies", "Price Setup"),
             ("/alerts/rules", "Rules"), ("/alerts/locks", "Stock Safety"),
             ("/alerts/integration-health", "Integration Health")]
    links = "".join('<a href="%s"%s>%s</a>' % (r, ' class="active"' if r == active else "", t)
                    for r, t in items)
    return '<div class="al-subnav">%s</div>' % links


def topbar(crumb):
    return """
    <div class="topbar">
      <div class="breadcrumb">Workspace / <strong>Alert Center</strong> / %s</div>
      <div class="topbar-actions">
        <a href="/help" class="icon-btn"><svg class="icon icon-sm"><use href="#i-help"/></svg></a>
        <a href="/app/notification-log" class="icon-btn"><svg class="icon icon-sm"><use href="#i-bell"/></svg></a>
      </div>
    </div>""" % crumb

# ============================== PAGE 1: /alerts ==============================
PAGE1_CONTENT = """
  <!-- ERP-wide chart assets (pinned local, NOT a CDN), loaded in dependency
       order: vendor -> theme -> common -> alert. Palettes/styling/lifecycle and
       the option construction live in these shared assets, NOT in this builder.
       If any asset fails to load the page shows a readable table fallback. -->
  <script src="/assets/ecentric_workspace/charts/vendor/echarts.min.js"></script>
  <script src="/assets/ecentric_workspace/charts/chart_theme.js"></script>
  <script src="/assets/ecentric_workspace/charts/chart_common.js"></script>
  <script src="/assets/ecentric_workspace/charts/alert_charts.js"></script>
  <div class="ec-main">
    %(topbar)s
    %(subnav)s
    <div class="content">
      <div class="greeting"><h1>Alert Center</h1><p id="al-scope-line"></p></div>
      <div class="al-top-row">
      <div class="stats-strip" id="al-kpis">
        <div class="stat-card s-navy kpi" data-kpi="open" role="button" tabindex="0" aria-pressed="false" title="%(kpi_hint)s"><div class="stat-label">%(c_open)s</div><div class="stat-value" id="al-c-open">-</div><div class="stat-meta">Open + In Review</div></div>
        <div class="stat-card s-pink kpi" data-kpi="critical" role="button" tabindex="0" aria-pressed="false" title="%(kpi_hint)s"><div class="stat-label">Critical</div><div class="stat-value" id="al-c-critical">-</div><div class="stat-meta">%(m_open)s</div></div>
        <div class="stat-card s-yellow kpi" data-kpi="warning" role="button" tabindex="0" aria-pressed="false" title="%(kpi_hint)s"><div class="stat-label">Warning</div><div class="stat-value" id="al-c-warning">-</div><div class="stat-meta">%(m_open)s</div></div>
        <div class="stat-card s-navy kpi" data-kpi="locks" role="button" tabindex="0" title="%(kpi_locks_hint)s"><div class="stat-label">%(c_lockrev)s</div><div class="stat-value" id="al-c-lockrev">-</div><div class="stat-meta">%(m_pending_ss)s</div></div>
        <div class="stat-card s-gray kpi" data-kpi="setup" role="button" tabindex="0" aria-pressed="false" title="%(kpi_setup_hint)s"><div class="stat-label">%(c_setup)s</div><div class="stat-value" id="al-c-setup">-</div><div class="stat-meta">missing_brand_mapping</div></div>
        <div class="stat-card s-green kpi kpi-sec" data-kpi="resolved" role="button" tabindex="0" aria-pressed="false" title="%(kpi_hint)s"><div class="stat-label">Resolved</div><div class="stat-value" id="al-c-resolved">-</div><div class="stat-meta">%(m_range)s</div></div>
      </div>
      </div>
      <div class="panel" style="margin-bottom:14px">
        <div class="al-filters">
          <div><label>%(preset)s</label><select id="f-preset"><option value="7">7 %(days_l)s</option><option value="14" selected>14 %(days_l)s</option><option value="30">30 %(days_l)s</option><option value="">%(custom)s</option></select></div>
          <div><label>Brand</label><select id="f-brand"><option value="">%(all)s</option></select></div>
          <div><label>Platform</label><select id="f-platform"><option value="">%(all)s</option><option>Shopee</option><option>Lazada</option><option>TikTok</option><option>Other</option></select></div>
          <div><label>Severity</label><select id="f-severity"><option value="">%(all)s</option><option>Critical</option><option>Warning</option><option>Info</option></select></div>
          <div style="flex:1 1 160px"><label>%(search_l)s</label><input id="f-sku" type="text" placeholder="%(sku_ph)s" title="%(sku_ph)s"></div>
          <button class="al-btn primary" id="al-apply">%(apply)s</button>
          <button class="al-btn" id="al-adv-toggle" aria-controls="al-adv" aria-expanded="false">%(advanced)s</button>
          <button class="al-btn" id="al-clear">%(clear)s</button>
        </div>
        <div class="al-adv" id="al-adv" hidden>
          <div><label>Status</label><select id="f-status"><option value="">%(all)s</option><option>Open</option><option>In Review</option><option>Closed</option><option>Resolved</option><option>Ignored</option></select></div>
          <div><label>Rule</label><select id="f-rule_code"><option value="">%(all)s</option><option>below_min</option><option>above_high</option><option>severe_price_drop</option><option>possible_missing_zero</option><option>missing_policy</option><option>missing_brand_mapping</option><option>missing_integration_credential</option><option>ingestion_api_failed</option><option>stock_lock_api_failed</option></select></div>
          <div><label>Owner</label><input id="f-owner" type="text" placeholder="user@email"></div>
          <div><label>%(from)s</label><input id="f-from" type="date"></div>
          <div><label>%(to)s</label><input id="f-to" type="date"></div>
        </div>
        <div class="al-fchips" id="al-fchips" hidden></div>
      </div>
      <div class="panel" id="ov-trend" style="margin-bottom:14px">
        <div class="panel-header"><div><div class="panel-title">%(trend_main)s</div><div class="al-help" style="margin-top:2px">%(trend_basis)s</div></div>
          <label class="al-chart-days">%(period_l)s <select id="ov-trend-days"><option value="7">7</option><option value="14" selected>14</option><option value="30">30</option></select></label></div>
        <div class="al-chart al-chart-trend" id="ec-trend" role="img" aria-label="%(trend_main)s"></div>
        <div class="al-chart-fb" id="ec-trend-fb" hidden></div>
      </div>
      <div class="al-dash-grid" id="ov-dash">
        <div class="panel" style="grid-column:1 / -1"><div class="panel-header"><div class="panel-title">%(distribution)s</div><span style="font-size:12px;color:var(--gray-500)">%(dist_basis)s</span></div>
          <div class="al-charts3">
            <div class="al-chartbox"><div class="al-chart-h">%(by_brand)s</div><div class="al-chart al-chart-donut" id="ec-brand" role="img" aria-label="%(by_brand)s"></div><div class="al-chart-fb" id="ec-brand-fb" hidden></div></div>
            <div class="al-chartbox"><div class="al-chart-h">%(by_platform)s</div><div class="al-chart al-chart-donut" id="ec-platform" role="img" aria-label="%(by_platform)s"></div><div class="al-chart-fb" id="ec-platform-fb" hidden></div></div>
            <div class="al-chartbox"><div class="al-chart-h">%(by_rule)s</div><div class="al-chart al-chart-donut" id="ec-rule" role="img" aria-label="%(by_rule)s"></div><div class="al-chart-fb" id="ec-rule-fb" hidden></div></div>
          </div></div>
        <div class="panel"><div class="panel-header"><div class="panel-title">%(top_sku)s</div></div>
          <div class="al-tbl-wrap"><table class="al-tbl"><thead><tr><th>SKU</th><th>Brand</th><th>%(alerts_n)s</th><th>%(latest)s</th></tr></thead><tbody id="dash-topsku"></tbody></table></div></div>
        <div class="panel"><div class="panel-header"><div class="panel-title">%(aging)s</div></div><div class="al-bars" id="dash-aging"></div></div>
      </div>
      <div class="al-note" id="al-snapshot-note"><span class="al-note-ic">&#9432;</span><span>Alerts l&#224; snapshot t&#7841;i th&#7901;i &#273;i&#7875;m ph&#225;t hi&#7879;n. T&#7841;o/s&#7917;a policy ch&#7881; &#225;p d&#7909;ng cho l&#7847;n &#273;&#225;nh gi&#225; / pull ti&#7871;p theo, kh&#244;ng c&#7853;p nh&#7853;t l&#7841;i alert c&#361;.</span></div>
      <div class="panel" id="ov-recent">
        <div class="panel-header"><div class="panel-title">%(recent_crit)s</div>
          <button class="al-btn primary" id="ov-viewall">%(view_all)s</button></div>
        <div class="al-tbl-wrap"><table class="al-tbl"><thead><tr><th>%(detected)s</th><th>Severity</th><th>Brand</th><th>SKU</th><th>Rule</th><th>Gap</th><th>Status</th></tr></thead><tbody id="ov-recent-rows"></tbody></table></div>
      </div>
      <div class="panel" id="al-alert-list" hidden>
        <div class="panel-header"><div class="panel-title">Alerts <span class="al-modesw" id="al-modesw"><button class="al-btn primary" id="al-mode-op">%(mode_op)s</button><button class="al-btn" id="al-mode-setup">%(mode_setup)s</button></span></div>
          <div class="al-bulkbar" id="al-bulkbar" hidden><span id="al-bulk-n">0</span> %(selected)s
            <button class="al-btn" id="al-bulk-review">%(review)s</button>
            <button class="al-btn primary" id="al-bulk-resolve">Resolve</button>
            <button class="al-btn" id="al-bulk-ignore">Ignore</button></div>
          <button class="al-btn" id="al-refresh">%(refresh)s</button></div>
        <div class="al-tbl-wrap">
          <table class="al-tbl">
            <thead><tr><th class="al-chk-col"><input type="checkbox" id="al-chk-all" title="%(sel_all)s"></th><th>%(detected)s</th><th>Severity</th><th>Status</th><th>Rule</th><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU</th><th>%(actual)s</th><th>%(minref)s</th><th>Gap</th><th>%(rec)s</th><th>Owner</th></tr></thead>
            <tbody id="al-rows"></tbody>
          </table>
        </div>
        <div class="al-pager"><span id="al-count">-</span><span><button class="al-btn" id="al-prev">&#8249;</button> <button class="al-btn" id="al-next">&#8250;</button></span></div>
      </div>
    </div>
  </div>
</div>
<div class="al-overlay" id="al-overlay" hidden></div>
<div class="al-modal al-modal-xl" id="al-drawer" hidden>
  <div class="al-modal-head"><div><strong id="al-d-title"></strong><div class="al-d-sub" id="al-d-sub"></div></div><button class="al-btn" id="al-d-close">&#10005;</button></div>
  <div class="al-modal-body"><div id="al-d-kv"></div><div id="al-d-occ"></div><div id="al-d-acts"></div></div>
  <div class="al-modal-foot">
    <button class="al-btn primary" id="al-d-claim" hidden>%(claim_l)s</button>
    <button class="al-btn primary" id="al-d-resolve" hidden>%(resolve_l)s</button>
    <div class="al-more" id="al-d-more-wrap" hidden>
      <button class="al-btn" id="al-d-more" aria-haspopup="true" aria-expanded="false">%(more_l)s</button>
      <div class="al-more-menu" id="al-d-more-menu" hidden><button class="al-btn" id="al-d-ignore">%(ignore_l)s</button></div>
    </div>
  </div>
</div>
<div class="al-modal" id="al-note-modal" hidden>
  <h3><span id="al-note-title"></span> &#8212; %(note_label)s</h3>
  <textarea id="al-note-text" rows="4" placeholder="%(note_ph)s"></textarea>
  <div class="al-modal-foot"><button class="al-btn" id="al-note-cancel">%(cancel)s</button><button class="al-btn primary" id="al-note-ok">%(confirm)s</button></div>
</div>
<div class="al-toast" id="al-toast" hidden></div>
""" % {
    "topbar": "%(TOPBAR)s", "subnav": "%(SUBNAV)s",
    "c_open": H("Đang mở"), "c_setup": H("Vấn đề cấu hình"),
    "c_lockrev": H("Lock chờ duyệt"), "m_open": H("đang mở"),
    "m_range": H("trong khoảng lọc"),
    "kpi_hint": H("Bấm để lọc danh sách theo thẻ này (bấm lại để bỏ)"),
    "kpi_locks_hint": H("Mở trang Locks (hàng đợi dry-run chờ duyệt)"),
    "kpi_setup_hint": H("Xem các alert cấu hình (vd: shop chưa map brand) - tách khỏi alert giá vận hành"),
    "preset": H("Khoảng thời gian"), "days_l": H("ngày"),
    "custom": H("Tuỳ chỉnh"), "search_l": H("Tìm SKU"),
    "advanced": H("Bộ lọc nâng cao"),
    "from": H("Từ"), "to": H("Đến"), "all": H("Tất cả"),
    "apply": H("Lọc"), "clear": H("Xoá lọc"),
    "by_brand": H("Theo brand"), "by_platform": H("Theo platform"),
    "by_rule": H("Theo rule"), "top_sku": H("Top SKU vi phạm"),
    "m_pending_ss": H("Stock Safety chờ duyệt"),
    "trend_main": H("Xu hướng cảnh báo"),
    "trend_basis": H("Theo ngày trong khoảng đã chọn (New / Resolved / Ignored)"),
    "distribution": H("Phân bố cảnh báo"),
    "dist_basis": H("Brand (ngoài) · Platform (giữa) · Rule (trong) · cùng mẫu số tổng alert"),
    "alerts_n": H("Số alert"), "latest": H("Gần nhất"),
    "aging": H("SLA - tuổi alert chưa xử lý"), "trend": H("Xu hướng 14 ngày"),
    "new_l": H("Mới"), "refresh": H("Làm mới"), "period_l": H("Khoảng"),
    "actual": H("Giá thực"), "rec": H("Đề xuất"), "detected": H("Lần gần nhất"),
    "recent_crit": H("Cảnh báo nghiêm trọng gần đây"),
    "view_all": H("Xem tất cả alerts"),
    "mode_op": H("Operational"), "mode_setup": H("Setup Issues"),
    "minref": H("Min / Ref"),
    "review": H("Nhận xử lý"), "pause": H("Tạm dừng tự động"),
    "claim_l": H("Nhận xử lý"), "resolve_l": H("Hoàn tất"),
    "ignore_l": H("Bỏ qua"), "more_l": H("Thêm"),
    "selected": H("đã chọn:"), "sel_all": H("Chọn tất cả trong trang"),
    "occ": H("Số đơn vi phạm"),
    "sku_ph": H("P02056 = chính xác, P020* = mở rộng"),
    "hour_title": H("Alert trend theo giờ"),
    "hour_sub": H("Cột = tổng alert, đường = Critical"),
    "source": H("Đơn nguồn"), "note_label": H("ghi chú bắt buộc"),
    "note_ph": H("Lý do / cách xử lý..."), "cancel": H("Huỷ"),
    "confirm": H("Xác nhận"), "pause_title": H("Tạm dừng Stock Safety Lock"),
    "optional": H("tuỳ chọn"), "reason": H("Lý do"),
}

PAGE1_JS = """
<script id="ec-alert-center">
(function(){
"use strict";
var A=window.AL,$=A.$;
var S={start:0,pageLen:50,total:0,scope:null,rows:[],current:null,noteAction:null,sel:{},occ:[]};
// UX polish 2026-06-10: rules with no price context render "-" instead of 0
var NOPRICE={missing_policy:1,missing_brand_mapping:1};
function pmoney(r,v){return NOPRICE[r.rule_code]?"-":A.money(v);}
function pgap(r){if(NOPRICE[r.rule_code])return "-";return r.gap_percent!=null?A.esc(Math.round(r.gap_percent))+"%%":"-";}
function occBadge(n){n=n||0;return '<span class="al-occ-n'+(n>1?" multi":"")+'">'+n+'</span>';}
// Context filters = the visible/advanced controls (date, brand, severity,
// status, search, platform, rule, owner). Feeds the KPI overview + aggregates.
function filters(){var f={};
[["f-severity","severity"],["f-status","status"],["f-rule_code","rule_code"],["f-brand","brand"],["f-platform","platform"]].forEach(function(p){var el=$(p[0]);var v=el?el.value:"";if(v)f[p[1]]=v;});
var sku=$("f-sku").value.trim();if(sku)f.seller_sku=sku;
var ow=$("f-owner");var o=ow?ow.value.trim():"";if(o)f.owner_user=o;
var a=$("f-from").value,b=$("f-to").value;if(a)f.from_date=a;if(b)f.to_date=b;return f;}
// KPI-card drill = an extra filter layer applied to the ALERTS LIST only, so a
// card click narrows the list without rewriting the overview cards. Backend
// accepts a status list (IN) and setup_only (Setup Issues view).
var KPI_DRILL={open:{status:["Open","In Review"]},critical:{status:["Open","In Review"],severity:"Critical"},warning:{status:["Open","In Review"],severity:"Warning"},resolved:{status:["Closed","Resolved"]}};
function listFilters(){var f=filters();
if(S.kpi==="setup"){delete f.rule_code;f.setup_only=1;return f;}
var d=KPI_DRILL[S.kpi];if(d){Object.keys(d).forEach(function(k){f[k]=d[k];});}return f;}
function presetDays(){var el=$("f-preset");if(!el)return 14;var v=el.value;return v===""?null:parseInt(v,10);}
function syncPresetDates(){var d=presetDays();if(d!=null){$("f-from").value=A.daysAgo(d);$("f-to").value=A.dateStr(new Date());}}
function setDefaultRange(){var el=$("f-preset");if(el)el.value="14";$("f-from").value=A.daysAgo(14);$("f-to").value=A.dateStr(new Date());}
function syncKpiActive(){Array.prototype.forEach.call(document.querySelectorAll("#al-kpis .stat-card.kpi"),function(c){var on=(c.getAttribute("data-kpi")===S.kpi);c.classList.toggle("kpi-active",on);if(c.hasAttribute("aria-pressed"))c.setAttribute("aria-pressed",on?"true":"false");});
var op=$("al-mode-op"),su=$("al-mode-setup");if(op&&su){var isS=(S.kpi==="setup");op.classList.toggle("primary",!isS);su.classList.toggle("primary",isS);}}
function setMode(setup){if(setup){S.kpi="setup";}else if(S.kpi==="setup"){S.kpi=null;}syncKpiActive();S.start=0;loadRows();renderChips();}
function applyKpi(key){if(!key)return;
if(key==="locks"){window.location.href="/alerts/locks";return;}
S.kpi=(S.kpi===key)?null:key;syncKpiActive();S.start=0;loadRows();renderChips();
// a KPI drill shows the full work queue -> switch to the Alerts subview
if(S.kpi&&window.location.hash!=="#al-alert-list"){window.location.hash="al-alert-list";}}
var KPI_LABEL={open:"%(c_open)s",critical:"Critical",warning:"Warning",resolved:"Resolved",setup:"%(c_setup)s"};
function renderChips(){var box=$("al-fchips");if(!box)return;var items=[];
function add(lbl,val,clear){items.push({lbl:lbl,val:val,clear:clear});}
if(S.kpi&&KPI_LABEL[S.kpi])add("%(kpi_l)s",KPI_LABEL[S.kpi],function(){S.kpi=null;syncKpiActive();});
[["f-brand","Brand"],["f-severity","Severity"],["f-status","Status"],["f-platform","Platform"],["f-rule_code","Rule"],["f-owner","Owner"]].forEach(function(p){var el=$(p[0]);if(el&&el.value)add(p[1],el.value,function(){el.value="";});});
var sk=$("f-sku").value.trim();if(sk)add("%(search_l)s",sk,function(){$("f-sku").value="";});
var pd=$("f-preset")?$("f-preset").value:"14";if(pd!=="14")add("%(preset)s",pd===""?"%(custom)s":(pd+" %(days)s"),function(){$("f-preset").value="14";syncPresetDates();});
box.innerHTML="";if(!items.length){box.hidden=true;return;}box.hidden=false;
items.forEach(function(it){var sp=document.createElement("span");sp.className="al-fchip";var t=document.createElement("span");t.innerHTML=A.esc(it.lbl)+': <b>'+A.esc(String(it.val))+'</b>';sp.appendChild(t);
if(it.clear){var b=document.createElement("button");b.type="button";b.setAttribute("aria-label","%(remove_l)s");b.textContent="\\u00d7";b.onclick=function(){it.clear();S.start=0;reload();};sp.appendChild(b);}box.appendChild(sp);});
var clr=document.createElement("button");clr.type="button";clr.className="al-fchip-clear al-btn";clr.textContent="%(clear)s";clr.onclick=clearAll;box.appendChild(clr);}
function clearAll(){S.kpi=null;["f-severity","f-status","f-rule_code","f-brand","f-platform"].forEach(function(id){var el=$(id);if(el)el.value="";});$("f-sku").value="";var ow=$("f-owner");if(ow)ow.value="";setDefaultRange();syncKpiActive();S.start=0;reload();}
function toggleAdv(){var a=$("al-adv");if(!a)return;var hidden=a.hasAttribute("hidden");if(hidden)a.removeAttribute("hidden");else a.setAttribute("hidden","");var t=$("al-adv-toggle");if(t)t.setAttribute("aria-expanded",hidden?"true":"false");}
// Bar width is relative to the largest bucket: 0 -> no fill; a positive value
// -> at least a visible minimum width; the max bucket -> 100%%. Per-row `cls`
// (e.g. SLA aging age0..age3) overrides the group class for progressive colour.
function bars(el,rows,cls){var max=0;rows.forEach(function(r){if(r.n>max)max=r.n;});
el.innerHTML=rows.length?rows.map(function(r){var w=(r.n>0)?Math.max(8,Math.round(r.n*100/(max||1))):0;return '<div class="al-bar-row"><span class="al-bar-key" title="'+A.esc(r.key)+'">'+A.esc(r.key)+'</span><span class="al-bar-track"><span class="al-bar-fill '+(r.cls||cls||"")+'" style="width:'+w+'%%"></span></span><span class="al-bar-n">'+r.n+'</span></div>';}).join(""):'<div class="al-empty">%(no_rows)s</div>';}
// ===== Charts: containers + API data + AlertCharts calls ======================
// Palettes, styling, option construction and the generic chart lifecycle live in
// the shared ERP assets (ECChartTheme / ECCharts / AlertCharts). This builder
// only: fetches data, does a MINIMAL page-specific transform, calls AlertCharts,
// and wires the resulting filter/drill-down callback. If the asset bundle failed
// to load entirely (no AlertCharts), a minimal page-level table fallback shows.
var DONUT_FILT={brand:"f-brand",platform:"f-platform",rule:"f-rule_code"};
function applyDimFilter(filtId,raw){var el=$(filtId);if(el){el.value=raw;S.start=0;reload();}}
function rawFB(boxId,fbId,html){var b=$(boxId),fb=$(fbId);if(b)b.style.display="none";if(fb){fb.hidden=false;fb.innerHTML=html;}}
function loadCharts(f){[["brand","ec-brand","ec-brand-fb","%(by_brand)s"],["platform","ec-platform","ec-platform-fb","%(by_platform)s"],["rule_code","ec-rule","ec-rule-fb","%(by_rule)s"]].forEach(function(c){var dim=(c[0]==="rule_code")?"rule":c[0];
A.call("api_dashboard.by_dimension",{dim:c[0],filters:f}).then(function(r){drawDonut(dim,c[1],c[2],c[3],r.rows||[]);}).catch(function(){drawDonut(dim,c[1],c[2],c[3],[]);});});}
function drawDonut(dim,boxId,fbId,label,rows){
if(window.AlertCharts){AlertCharts.renderDistributionDonut($(boxId),dim,rows,{
label:label,totalLabel:"%(total_l)s",otherLabel:"%(other_l)s",noneLabel:"%(none_l)s",
labelFor:(dim==="rule")?function(k){return A.ruleLabel(k);}:null,
fallbackEl:$(fbId),onClick:function(raw){applyDimFilter(DONUT_FILT[dim],raw);}});return;}
// asset bundle unavailable -> minimal page fallback (top 4 categories)
var tot=rows.reduce(function(s,x){return s+x.n;},0);
rawFB(boxId,fbId,tot?('<table class="al-tbl al-chart-fbt"><tbody>'+rows.slice(0,4).map(function(x){return '<tr><td>'+A.esc(dim==="rule"?A.ruleLabel(x.key):(x.key||"%(none_l)s"))+'</td><td class="r"><b>'+x.n+'</b></td></tr>';}).join("")+'</tbody></table>'):'<div class="al-empty">%(no_rows)s</div>');}
function trendDays(){var el=$("ov-trend-days");return el?(parseInt(el.value,10)||14):14;}
function loadTrend(f){A.call("api_dashboard.trend",{filters:f,days:trendDays()}).then(function(r){drawTrend(r.rows||[]);}).catch(function(){drawTrend([]);});}
function drawTrend(rows){
// TRUTHFUL series only: api_dashboard.trend returns New / Resolved / Ignored per
// day (no per-day severity split and no historical backlog exist), so none are
// fabricated. The series/option assembly lives in AlertCharts.renderTrend.
if(window.AlertCharts){AlertCharts.renderTrend($("ec-trend"),rows,{
labels:{"new":"%(new_l)s",resolved:"Resolved",ignored:"Ignored",date:"%(date_l)s",title:"%(trend_main)s"},
fallbackEl:$("ec-trend-fb"),onPointClick:function(day){$("f-preset").value="";$("f-from").value=day;$("f-to").value=day;S.start=0;reload();window.location.hash="al-alert-list";}});return;}
rawFB("ec-trend","ec-trend-fb",(rows&&rows.length)?('<table class="al-tbl al-chart-fbt"><thead><tr><th>%(date_l)s</th><th class="r">%(new_l)s</th><th class="r">Resolved</th><th class="r">Ignored</th></tr></thead><tbody>'+rows.map(function(d){return '<tr><td>'+A.esc(d.day)+'</td><td class="r">'+d.new+'</td><td class="r">'+d.resolved+'</td><td class="r">'+d.ignored+'</td></tr>';}).join("")+'</tbody></table>'):'<div class="al-empty">%(no_rows)s</div>');}
function loadDash(){var f=filters();
A.call("api_dashboard.kpis",{filters:f}).then(function(c){$("al-c-open").textContent=c.open;$("al-c-critical").textContent=c.critical;$("al-c-warning").textContent=c.warning;$("al-c-setup").textContent=(c.setup_issues!=null?c.setup_issues:c.missing_policy);$("al-c-lockrev").textContent=c.lock_pending_review;$("al-c-resolved").textContent=c.resolved;}).catch(function(){});
loadCharts(f);loadTrend(f);
A.call("api_dashboard.top_skus",{filters:f,limit:10}).then(function(r){var tb=$("dash-topsku");tb.innerHTML=r.rows.length?r.rows.map(function(x){return '<tr><td>'+A.esc(x.seller_sku)+'</td><td>'+A.esc(x.brand||"-")+'</td><td><b>'+x.n+'</b></td><td>'+A.esc(A.dt(x.latest))+'</td></tr>';}).join(""):'<tr><td colspan="4" class="al-empty">%(no_rows)s</td></tr>';}).catch(function(){});
A.call("api_dashboard.aging",{filters:f}).then(function(b){bars($("dash-aging"),[{key:"< 4h",n:b.lt_4h||0,cls:"age0"},{key:"4-24h",n:b.h4_24||0,cls:"age1"},{key:"1-3 %(days)s",n:b.d1_3||0,cls:"age2"},{key:"> 3 %(days)s",n:b.gt_3d||0,cls:"age3"}]);}).catch(function(){});}
function loadRows(){var tb=$("al-rows");tb.innerHTML='<tr><td colspan="14" class="al-empty">%(loading)s</td></tr>';
A.call("api_alerts.list_alerts",{filters:listFilters(),start:S.start,page_len:S.pageLen}).then(function(res){S.rows=res.rows;S.total=res.total;S.sel={};syncBulk();
if(!res.rows.length){tb.innerHTML='<tr><td colspan="14" class="al-empty">%(no_rows)s</td></tr>';}
else{tb.innerHTML=res.rows.map(function(r,i){return '<tr data-i="'+i+'">'+
'<td class="al-chk-col"><input type="checkbox" class="al-row-chk" data-name="'+A.esc(r.name)+'"></td>'+
'<td>'+A.esc(A.dt(r.last_seen_at||r.detected_at))+'</td>'+
'<td>'+A.sevBadge(r.severity)+'</td><td>'+A.stBadge(r.status)+'</td><td>'+A.ruleCell(r.rule_code)+'</td>'+
'<td>'+A.esc(r.brand||"-")+'</td><td>'+A.esc(r.platform||"-")+'</td><td>'+A.esc(r.shop||"-")+'</td><td>'+A.esc(r.seller_sku||r.item||"-")+'</td>'+
'<td>'+pmoney(r,r.effective_check_price!=null?r.effective_check_price:r.actual_price)+'</td><td>'+pmoney(r,r.min_price)+'</td><td>'+pgap(r)+'</td>'+
'<td>'+A.esc(r.recommended_action||"-")+'</td><td>'+A.esc(r.owner_user||"-")+'</td></tr>';}).join("");}
$("al-chk-all").checked=false;
var from=S.total?S.start+1:0;$("al-count").textContent=from+"-"+Math.min(S.start+S.pageLen,S.total)+" / "+S.total;$("al-prev").disabled=S.start<=0;$("al-next").disabled=S.start+S.pageLen>=S.total;}).catch(function(e){tb.innerHTML='<tr><td colspan="14" class="al-empty">%(err)s'+A.esc(e.message)+'</td></tr>';});}
function syncBulk(){var n=Object.keys(S.sel||{}).length;$("al-bulk-n").textContent=n;$("al-bulkbar").hidden=(n===0);}
function bulkStatus(status){var names=Object.keys(S.sel||{});if(!names.length)return;
var note=null;if(status!=="In Review"){note=window.prompt("%(bulk_note)s");if(note===null)return;if(!note.trim()){A.toast("%(note_required)s");return;}}
A.call("api_alerts.bulk_set_status",{names:names,new_status:status,note:note}).then(function(res){A.toast("%(bulk_done)s "+(res.ok?res.ok.length:0)+" / "+names.length);S.sel={};reload();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function reload(){loadDash();loadRows();renderChips();}
function openDrawer(r){S.current=r;S.occ=[];$("al-d-title").textContent=r.name;
var occn=r.occurrence_count||0;
$("al-d-sub").innerHTML=A.stBadge(r.status)+' &middot; '+A.esc(r.seller_sku||r.item||"-")+' &middot; '+A.ruleCell(r.rule_code)+' '+A.sevBadge(r.severity)+(occn>1?' <span class="al-case-pill">'+occn+' %(case_pill)s</span>':'');
function kvdl(rows){return '<dl class="al-kv al-kv-wide">'+rows.map(function(p){return "<dt>"+p[0]+"</dt><dd>"+p[1]+"</dd>";}).join("")+'</dl>';}
var dSummary=[["Rule",A.ruleCell(r.rule_code)],["Severity",A.sevBadge(r.severity)],["Status",A.stBadge(r.status)],["%(c_rec)s",A.esc(r.recommended_action||"-")]];
var dEvidence=[["%(c_eff)s",pmoney(r,r.effective_check_price!=null?r.effective_check_price:r.actual_price)],["Min",pmoney(r,r.min_price)],["%(c_ref)s",pmoney(r,r.baseline_price)],["Gap",pgap(r)]];
var dScope=[["Brand",A.esc(r.brand||"-")],["Platform",A.esc(r.platform||"-")],["Shop",A.esc(r.shop||"-")],["SKU",A.esc(r.seller_sku||r.item||"-")],["%(c_title)s",A.esc(r.title)]];
// Raw price_components_used string lives ONLY in Technical Details (and CSV) -
// business users see the friendly breakdown rows, not the raw code string.
var dTech=[["%(c_rawrule)s",A.esc(r.rule_code)],["%(c_comp)s",A.esc(r.price_components_used||"-")],["Ref doctype",A.esc(r.reference_doctype||"-")],["Ref name",A.esc(r.reference_name||"-")],["Owner",A.esc(r.owner_user||"-")],["%(c_occ)s",occBadge(occn)],["%(c_first)s",A.esc(A.dt(r.first_seen_at||r.detected_at))],["%(c_last)s",A.esc(A.dt(r.last_seen_at||r.detected_at))],["Action",A.actBadge(r.action_status)]];
$("al-d-kv").innerHTML='<div class="al-fsec">%(s_summary)s</div>'+kvdl(dSummary)+'<div class="al-fsec">%(s_evi)s</div>'+kvdl(dEvidence)+'<div class="al-fsec">%(s_scope3)s</div>'+kvdl(dScope)+'<details class="al-tech"><summary class="al-fsec" style="cursor:pointer">%(s_tech)s</summary>'+kvdl(dTech)+'</details>';
refreshAlertFooter(r.status);
$("al-d-occ").innerHTML='<div class="al-help">%(loading)s</div>';
A.call("api_alerts.alert_occurrences",{alert:r.name,page_len:50}).then(function(res){renderOcc(res.rows||[],res.total||0);}).catch(function(e){$("al-d-occ").innerHTML='<div class="al-help">%(err)s'+A.esc(e.message)+'</div>';});
$("al-d-acts").innerHTML="";A.call("api_actions.list_for_alert",{alert:r.name}).then(function(rows){if(!rows||!rows.length)return;$("al-d-acts").innerHTML='<div class="al-actrows"><b>Actions</b><br>'+rows.map(function(a2){return A.esc(a2.name)+" "+A.actBadge(a2.status)+" "+A.esc(a2.lock_reason||a2.error_message||"");}).join("<br>")+"</div>";}).catch(function(){});
$("al-overlay").hidden=false;$("al-drawer").hidden=false;}
function brk(label,val,cls){return '<tr><td>'+label+'</td><td class="r '+(cls||"")+'">'+(val?("-"+A.money(val)):A.money(0))+'</td></tr>';}
// B2: the price-calculation panel is sourced from the SELECTED EC Alert Occurrence
// row (defaults to the latest violating occurrence = rows[0]). Every value comes
// from that row; nothing is fabricated and the alert-summary values are not used
// once a row is selected. CSV export stays based on the FULL list (S.occ).
function renderCalc(o){if(!o)return;
$("al-calc").innerHTML='<div class="al-fsec">%(s_breakdown)s &middot; '+A.esc(o.external_order_id||"-")+'</div><div class="al-breakdown"><table>'+
'<tr><td>RSP</td><td class="r">'+A.money(o.rsp_price)+'</td></tr>'+
brk("%(b_sd)s",o.seller_discount_amount,"minus")+
brk("%(b_sv)s",o.seller_voucher_amount,"minus")+
brk("%(b_pd)s",o.platform_discount_amount,"minus")+
brk("%(b_pv)s",o.platform_voucher_amount,"minus")+
'<tr class="eff"><td>= %(b_eff)s</td><td class="r">'+A.money(o.effective_check_price)+'</td></tr>'+
'<tr><td>Min</td><td class="r">'+A.money(o.min_price_at_check)+'</td></tr>'+
'<tr><td>%(c_ref)s</td><td class="r">'+A.money(o.baseline_price_at_check)+'</td></tr>'+
'<tr><td>Gap</td><td class="r">'+(o.gap_percent!=null?A.esc(Math.round(o.gap_percent))+"%%":"-")+'</td></tr>'+
'</table><div class="al-help" title="'+A.esc(o.price_components_used||"")+'">'+A.esc(A.dt(o.order_datetime))+' &middot; '+A.esc(o.order_status||"-")+'</div></div>';}
function selectOcc(i){if(!S.occ||!S.occ[i])return;S.selOcc=i;renderCalc(S.occ[i]);
var bd=$("al-occ-body");if(bd)Array.prototype.forEach.call(bd.querySelectorAll("tr[data-oi]"),function(tr){tr.classList.toggle("al-occ-sel",+tr.getAttribute("data-oi")===i);});}
function renderOcc(rows,total){
S.occ=rows||[];S.selOcc=0;
if(!rows.length){$("al-d-occ").innerHTML='<div class="al-fsec">%(s_evidence)s</div><div class="al-help">%(no_occ)s</div>';return;}
var head='<tr><th>%(h_order)s</th><th>%(h_time)s</th><th>%(h_st)s</th><th>SKU</th><th class="r">RSP</th><th class="r">%(b_sd)s</th><th class="r">%(b_sv)s</th><th class="r">%(b_pd)s</th><th class="r">%(b_pv)s</th><th class="r">%(b_eff)s</th><th class="r">Min</th><th class="r">Gap</th><th>Rule</th></tr>';
var body=rows.map(function(x,i){return '<tr class="al-occ-row'+(i===0?" al-occ-sel":"")+'" data-oi="'+i+'" tabindex="0" role="button" aria-label="%(sel_order_l)s '+A.esc(x.external_order_id||"-")+'">'+
'<td>'+A.esc(x.external_order_id||"-")+'</td><td>'+A.esc(A.dt(x.order_datetime))+'</td><td>'+A.esc(x.order_status||"-")+'</td>'+
'<td title="'+A.esc(x.product_name||"")+'">'+A.esc(x.seller_sku||"-")+'</td>'+
'<td class="r">'+A.money(x.rsp_price)+'</td><td class="r">'+A.money(x.seller_discount_amount)+'</td><td class="r">'+A.money(x.seller_voucher_amount)+'</td><td class="r">'+A.money(x.platform_discount_amount)+'</td><td class="r">'+A.money(x.platform_voucher_amount)+'</td>'+
'<td class="r"><b>'+A.money(x.effective_check_price)+'</b></td><td class="r">'+A.money(x.min_price_at_check)+'</td><td class="r">'+(x.gap_percent!=null?A.esc(Math.round(x.gap_percent))+"%%":"-")+'</td>'+
'<td title="'+A.esc(x.price_components_used||"")+'">'+A.ruleCell(x.rule_code)+' '+A.sevBadge(x.severity)+'</td></tr>';}).join("");
$("al-d-occ").innerHTML='<div id="al-calc" class="al-calc"></div><div class="al-occ-wrap'+(total>1?" hl":"")+'"><div class="al-occ-head"><div class="al-fsec" style="margin:0">%(s_evidence)s ('+total+')</div><div><button class="al-btn" id="al-occ-export">%(export_csv)s</button> <button class="al-btn" id="al-occ-copy">%(copy_csv)s</button></div></div><div class="al-tbl-wrap"><table class="al-occ-tbl"><thead>'+head+'</thead><tbody id="al-occ-body">'+body+'</tbody></table></div></div>';
renderCalc(rows[0]); // default selection = latest violating occurrence
var bd=$("al-occ-body");if(bd){bd.addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-oi]");if(tr)selectOcc(+tr.getAttribute("data-oi"));});
bd.addEventListener("keydown",function(ev){if(ev.key!=="Enter"&&ev.key!==" "&&ev.key!=="Spacebar")return;var tr=ev.target.closest("tr[data-oi]");if(tr){ev.preventDefault();selectOcc(+tr.getAttribute("data-oi"));}});}
var ex=$("al-occ-export");if(ex)ex.onclick=exportOccCsv;var cp=$("al-occ-copy");if(cp)cp.onclick=copyOccCsv;}
var OCC_CSV_COLS=["external_order_id","order_datetime","order_status","seller_sku","product_name","rsp_price","seller_discount_amount","seller_voucher_amount","platform_discount_amount","platform_voucher_amount","effective_check_price","min_price_at_check","baseline_price_at_check","gap_percent","rule_code","severity","detected_at","price_components_used"];
function occCsv(){var rows=S.occ||[];var q=function(v){v=(v==null?"":String(v));if(/[",\\n]/.test(v))v='"'+v.replace(/"/g,'""')+'"';return v;};
var lines=[OCC_CSV_COLS.join(",")];rows.forEach(function(x){lines.push(OCC_CSV_COLS.map(function(c){return q(x[c]);}).join(","));});return lines.join("\\n");}
function exportOccCsv(){if(!S.current||!(S.occ&&S.occ.length)){A.toast("%(no_occ)s");return;}
var blob=new Blob(["\\ufeff"+occCsv()],{type:"text/csv;charset=utf-8;"});var url=URL.createObjectURL(blob);
var a=document.createElement("a");a.href=url;a.download="alert_occurrences_"+S.current.name+".csv";document.body.appendChild(a);a.click();document.body.removeChild(a);
setTimeout(function(){URL.revokeObjectURL(url);},1000);A.toast("%(csv_exported)s");}
function copyOccCsv(){if(!(S.occ&&S.occ.length)){A.toast("%(no_occ)s");return;}var csv=occCsv();
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(csv).then(function(){A.toast("%(csv_copied)s");}).catch(function(){A.toast("%(err)s");});}else{A.toast("%(err)s");}}
function closeDrawer(){$("al-overlay").hidden=true;$("al-drawer").hidden=true;S.current=null;}
function setStatus(status){if(!S.current)return;
if(status==="In Review"){A.call("api_alerts.set_status",{alert:S.current.name,new_status:status}).then(function(){A.toast("%(done)s");closeDrawer();reload();}).catch(function(e){A.toast("%(err)s"+e.message);});return;}
S.noteAction=status;$("al-note-title").textContent=status;$("al-note-text").value="";$("al-note-modal").hidden=false;$("al-overlay").hidden=false;}
function confirmNote(){var note=$("al-note-text").value.trim();if(!note){A.toast("%(note_required)s");return;}
A.call("api_alerts.set_status",{alert:S.current.name,new_status:S.noteAction,note:note}).then(function(){$("al-note-modal").hidden=true;A.toast("%(done)s");closeDrawer();reload();}).catch(function(e){A.toast("%(err)s"+e.message);});}
// Lifecycle footer visibility by state: Open -> Claim (primary); In Review ->
// Resolve (primary); Ignore lives in the More menu for active cases; terminal
// cases have no primary action. (Automation Pause is NOT here - it belongs to
// Stock Safety / Automation Pauses only.)
function refreshAlertFooter(st){var claim=$("al-d-claim"),res=$("al-d-resolve"),mw=$("al-d-more-wrap"),mm=$("al-d-more-menu");
if(mm){mm.hidden=true;}var mb=$("al-d-more");if(mb)mb.setAttribute("aria-expanded","false");
var terminal=(st==="Closed"||st==="Ignored"||st==="Cancelled"||st==="Resolved");
if(claim)claim.hidden=(st!=="Open");
if(res)res.hidden=(st!=="In Review");
if(mw)mw.hidden=terminal;}
function loadRecent(){var tb=$("ov-recent-rows");if(!tb)return;
A.call("api_alerts.list_alerts",{filters:{severity:"Critical",status:["Open","In Review"]},start:0,page_len:5}).then(function(res){var rows=res.rows||[];S.recent=rows;
tb.innerHTML=rows.length?rows.map(function(r,i){return '<tr class="al-rowlink" data-ri="'+i+'" tabindex="0" role="button" aria-label="%(open_alert_l)s '+A.esc(r.name)+'"><td>'+A.esc(A.dt(r.last_seen_at||r.detected_at))+'</td><td>'+A.sevBadge(r.severity)+'</td><td>'+A.esc(r.brand||"-")+'</td><td>'+A.esc(r.seller_sku||r.item||"-")+'</td><td>'+A.ruleCell(r.rule_code)+'</td><td>'+pgap(r)+'</td><td>'+A.stBadge(r.status)+'</td></tr>';}).join(""):'<tr><td colspan="7" class="al-empty">%(no_crit)s</td></tr>';}).catch(function(){tb.innerHTML='<tr><td colspan="7" class="al-empty">-</td></tr>';});}
function openRecent(i){var r=(S.recent||[])[i];if(r)openDrawer(r);}
function applyHashNav(){
  var atList=(window.location.hash==="#al-alert-list");
  // Overview (no hash) vs Alerts (#al-alert-list) subviews on /alerts.
  var links=document.querySelectorAll(".ec-sidebar a.nav-item");
  links.forEach(function(a){var hrefp=(a.getAttribute("href")||"");
    if(hrefp==="/alerts"){a.classList.toggle("active",!atList);}
    else if(hrefp.indexOf("#al-alert-list")>=0){a.classList.toggle("active",atList);}});
  document.querySelectorAll(".al-subnav a").forEach(function(a){var h=a.getAttribute("href")||"";
    if(h==="/alerts")a.classList.toggle("active",!atList);
    else if(h.indexOf("#al-alert-list")>=0)a.classList.toggle("active",atList);});
  var ov=$("ov-dash"),rec=$("ov-recent"),note=$("al-snapshot-note"),list=$("al-alert-list"),tr=$("ov-trend");
  if(ov)ov.hidden=atList;if(rec)rec.hidden=atList;if(note)note.hidden=atList;if(list)list.hidden=!atList;if(tr)tr.hidden=atList;
  if(atList){if(list)list.scrollIntoView({behavior:"smooth",block:"start"});}else{loadRecent();setTimeout(function(){if(window.ECCharts)ECCharts.resizeAll();},60);}
}
function init(){setDefaultRange();
A.initScope("/alerts",function(scope){S.scope=scope;
$("al-scope-line").textContent=scope.supervisor?"Supervisor scope: all brands":("Brands: "+Object.keys(scope.brands).join(", "));
var bsel=$("f-brand");Object.keys(scope.brands||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;bsel.appendChild(o);});
A.relabelRuleOptions($("f-rule_code"));
syncKpiActive();renderChips();
reload();
applyHashNav();});
window.addEventListener("hashchange",applyHashNav);
var _va=$("ov-viewall");if(_va)_va.onclick=function(){window.location.hash="al-alert-list";};
var _rr=$("ov-recent-rows");if(_rr){_rr.addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-ri]");if(tr)openRecent(+tr.getAttribute("data-ri"));});
_rr.addEventListener("keydown",function(ev){if(ev.key!=="Enter"&&ev.key!==" "&&ev.key!=="Spacebar")return;var tr=ev.target.closest("tr[data-ri]");if(tr){ev.preventDefault();openRecent(+tr.getAttribute("data-ri"));}});}
var _mo=$("al-mode-op");if(_mo)_mo.onclick=function(){setMode(false);};
var _ms=$("al-mode-setup");if(_ms)_ms.onclick=function(){setMode(true);};
$("al-apply").onclick=function(){S.start=0;reload();};
$("al-clear").onclick=clearAll;
$("f-preset").onchange=function(){syncPresetDates();S.start=0;reload();};
$("al-adv-toggle").onclick=toggleAdv;
$("al-kpis").addEventListener("click",function(ev){var c=ev.target.closest(".stat-card.kpi");if(c)applyKpi(c.getAttribute("data-kpi"));});
$("al-kpis").addEventListener("keydown",function(ev){if(ev.key!=="Enter"&&ev.key!==" "&&ev.key!=="Spacebar")return;var c=ev.target.closest(".stat-card.kpi");if(c){ev.preventDefault();applyKpi(c.getAttribute("data-kpi"));}});
// Charts: one debounced window-resize listener (owned by ECCharts; idempotent);
// reload only the trend when the 7/14/30-day preset changes.
if(window.ECCharts)ECCharts.attachResize();
var _td=$("ov-trend-days");if(_td)_td.onchange=function(){loadTrend(filters());};
$("al-refresh").onclick=reload;
$("al-prev").onclick=function(){S.start=Math.max(0,S.start-S.pageLen);loadRows();};
$("al-next").onclick=function(){S.start+=S.pageLen;loadRows();};
$("al-rows").addEventListener("click",function(ev){if(ev.target.classList.contains("al-row-chk"))return;var tr=ev.target.closest("tr[data-i]");if(tr)openDrawer(S.rows[+tr.getAttribute("data-i")]);});
$("al-rows").addEventListener("change",function(ev){var c=ev.target;if(!c.classList.contains("al-row-chk"))return;var nm=c.getAttribute("data-name");if(c.checked)S.sel[nm]=1;else delete S.sel[nm];syncBulk();
var all=Array.prototype.slice.call(document.querySelectorAll(".al-row-chk"));$("al-chk-all").checked=all.length>0&&all.every(function(x){return x.checked;});});
$("al-chk-all").onchange=function(){var on=$("al-chk-all").checked;document.querySelectorAll(".al-row-chk").forEach(function(c){c.checked=on;var nm=c.getAttribute("data-name");if(on)S.sel[nm]=1;else delete S.sel[nm];});syncBulk();};
$("al-bulk-review").onclick=function(){bulkStatus("In Review");};
$("al-bulk-resolve").onclick=function(){bulkStatus("Resolved");};
$("al-bulk-ignore").onclick=function(){bulkStatus("Ignored");};
$("al-d-close").onclick=closeDrawer;
$("al-overlay").onclick=function(){closeDrawer();$("al-note-modal").hidden=true;};
$("al-d-claim").onclick=function(){setStatus("In Review");};
$("al-d-resolve").onclick=function(){setStatus("Closed");};
$("al-d-ignore").onclick=function(){setStatus("Ignored");};
$("al-d-more").onclick=function(){var m=$("al-d-more-menu"),h=m.hidden;m.hidden=!h;$("al-d-more").setAttribute("aria-expanded",h?"true":"false");};
$("al-note-ok").onclick=confirmNote;$("al-note-cancel").onclick=function(){$("al-note-modal").hidden=true;};}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init);}else{init();}
})();
</script>
""" % dict(VNJ, days=js_escape("ngày"),
    by_brand=js_escape("Theo brand"), by_platform=js_escape("Theo platform"),
    by_rule=js_escape("Theo rule"), other_l=js_escape("Khác"),
    none_l=js_escape("(không có)"), total_l=js_escape("Tổng alert"),
    new_l=js_escape("Mới"), trend_main=js_escape("Xu hướng cảnh báo"),
    date_l=js_escape("Ngày"), open_alert_l=js_escape("Mở alert"),
    sel_order_l=js_escape("Chọn đơn"),
    c_open=js_escape("Đang mở"), c_setup=js_escape("Vấn đề cấu hình"),
    no_crit=js_escape("Không có cảnh báo nghiêm trọng đang mở."),
    kpi_l=js_escape("Thẻ KPI"), search_l=js_escape("Tìm SKU"),
    preset=js_escape("Khoảng thời gian"), custom=js_escape("Tuỳ chỉnh"),
    remove_l=js_escape("Bỏ lọc"), clear=js_escape("Xoá lọc"),
    bulk_note=js_escape("Ghi chú (bắt buộc cho Resolve/Ignore):"),
    bulk_done=js_escape("Đã cập nhật"),
    c_eff=js_escape("Giá check"), c_comp=js_escape("Thành phần giá"), c_occ=js_escape("Số đơn vi phạm"),
    c_first=js_escape("Phát hiện đầu"), c_last=js_escape("Lần gần nhất"),
    c_rec=js_escape("Đề xuất xử lý"), c_ref=js_escape("Baseline / Reference"),
    c_title=js_escape("Tiêu đề"), c_rawrule=js_escape("Rule code (raw)"),
    s_summary=js_escape("Tóm tắt"), s_evi=js_escape("Bằng chứng giá"),
    s_scope3=js_escape("Phạm vi"), s_tech=js_escape("Chi tiết kỹ thuật"),
    case_pill=js_escape("đơn vi phạm"),
    s_breakdown=js_escape("Cách tính giá check"), s_evidence=js_escape("Bằng chứng theo đơn"),
    no_occ=js_escape("Chưa có occurrence cho case này."),
    b_sd=js_escape("Seller discount"), b_sv=js_escape("Seller voucher"),
    b_pd=js_escape("Platform discount"), b_pv=js_escape("Platform voucher"),
    b_eff=js_escape("Giá check hiệu lực"),
    h_order=js_escape("Đơn"), h_time=js_escape("Thời gian"), h_st=js_escape("Trạng thái"),
    export_csv=js_escape("Xuất CSV"), copy_csv=js_escape("Copy CSV"),
    csv_exported=js_escape("Đã xuất CSV."), csv_copied=js_escape("Đã copy CSV."))

# ========================= PAGE 2: /alerts/policies =========================
PAGE2_CONTENT = """
  <div class="ec-main">
    %(TOPBAR)s
    %(SUBNAV)s
    <div class="content">
      <div class="greeting"><h1>%(title)s</h1><p id="al-scope-line"></p></div>
      <div class="panel" id="pl-missing-panel">
        <div class="panel-header"><div class="panel-title">%(cov_sum_title)s<span class="al-help-i" data-help="price_setup.coverage" title="%(cov_help)s" tabindex="0" role="img" aria-label="%(cov_help)s">&#9432;</span></div>
          <span style="font-size:12px;color:var(--gray-500)">%(cov_basis)s</span></div>
        <div class="stats-strip" id="pl-cov-kpis">
          <div class="stat-card s-green"><div class="stat-label">%(cov_covered)s</div><div class="stat-value" id="pl-cov-covered">-</div><div class="stat-meta">%(cov_covered_meta)s</div></div>
          <div class="stat-card s-yellow kpi" id="pl-cov-missing-card" data-cov="missing" role="button" tabindex="0" title="%(cov_missing_hint)s"><div class="stat-label">%(cov_missing)s</div><div class="stat-value" id="pl-cov-missing">-</div><div class="stat-meta">%(cov_missing_meta)s</div></div>
          <div class="stat-card s-navy"><div class="stat-label">%(cov_pct)s</div><div class="stat-value" id="pl-cov-pct">-</div><div class="stat-meta">%(cov_basis)s</div></div>
        </div>
        <details class="al-adv-sec" id="pl-cov-bybrand" style="margin-top:10px">
          <summary class="al-fsec" style="cursor:pointer">%(cov_bybrand)s</summary>
          <div id="pl-missing-rows" class="al-inline" style="flex-wrap:wrap;gap:10px;padding:6px 2px"><span class="al-empty">-</span></div>
        </details>
      </div>
      <div class="panel">
        <div class="panel-header"><div class="panel-title">%(title)s</div>
          <span class="al-hdr-actions">
            <button class="al-btn" id="pl-template">%(dl_template)s</button>
            <button class="al-btn" id="pl-upload">%(upload_csv)s</button>
            <button class="al-btn primary" id="pl-new">+ Policy</button>
          </span></div>
        <div class="al-filters">
          <div><label>Brand</label><select id="f-brand"><option value="">%(all)s</option></select></div>
          <div><label>Platform</label><select id="f-platform"><option value="">%(all)s</option><option>All</option><option>Shopee</option><option>Lazada</option><option>TikTok</option></select></div>
          <div><label>SKU</label><input id="f-sku" type="text"></div>
          <div><label>Status</label><select id="f-status"><option value="">%(all)s</option><option>Draft</option><option>Active</option><option>Paused</option><option>Expired</option><option>Inactive</option></select></div>
          <div><label>Owner</label><input id="f-owner" type="text" placeholder="user@email"></div>
          <button class="al-btn primary" id="pl-apply">%(apply)s</button>
        </div>
        <div class="al-tbl-wrap">
          <table class="al-tbl">
            <thead><tr><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU</th><th>%(product)s</th><th>Min</th><th>Target/RSP</th><th>Ref</th><th>Status</th><th>Owner</th><th>%(effective)s</th></tr></thead>
            <tbody id="pl-rows"></tbody>
          </table>
        </div>
        <div class="al-pager"><span id="pl-count">-</span><span><button class="al-btn" id="pl-prev">&#8249;</button> <button class="al-btn" id="pl-next">&#8250;</button></span></div>
      </div>
    </div>
  </div>
</div>
<div class="al-overlay" id="al-overlay" hidden></div>
<div class="al-drawer al-drawer-wide" id="pl-drawer" hidden>
  <div class="al-drawer-head"><strong id="pl-d-title">Policy</strong> <span id="pl-d-status"></span><button class="al-btn" id="pl-d-close">&#10005;</button></div>
  <div class="al-drawer-body">
    <div class="al-fsec">%(s_scope)s</div>
    <div class="al-fgrid">
      <div class="al-fld"><label>Brand <span class="al-req">*</span></label><select id="e-brand"></select></div>
      <div class="al-fld"><label>Platform <span class="al-req">*</span></label><select id="e-platform"><option>All</option><option>Shopee</option><option>Lazada</option><option>TikTok</option></select></div>
      <div class="al-fld al-col2"><label>Shop <span class="al-opt">(%(optional)s)</span><span class="al-help-i" data-help="price_setup.shop" title="%(h_shop)s" tabindex="0" role="img" aria-label="%(h_shop)s">&#9432;</span></label><input id="e-shop" type="text" placeholder="EC Marketplace Shop"></div>
      <div class="al-fld al-col2"><label>Seller SKU <span class="al-req">*</span><span class="al-help-i" data-help="price_setup.seller_sku" title="%(h_sku)s" tabindex="0" role="img" aria-label="%(h_sku)s">&#9432;</span></label>
        <div class="al-inline"><input id="e-seller_sku" type="text"><button type="button" class="al-btn" id="e-sku-search">%(sku_btn)s</button></div></div>
      <!-- C1: ERP Item is hidden from the normal KAM workflow. Seller SKU is the
           business input; ERP Item auto-maps in the background (the value carries
           through on edit) and is not required in the UI. -->
      <input id="e-item" type="hidden">
    </div>
    <div class="al-note" id="e-scope-preview"><span class="al-note-ic">&#9432;</span><span class="al-sp-text">%(scope_default)s</span></div>
    <div class="al-help">%(priority_line)s</div>

    <div class="al-fsec">%(s_product)s</div>
    <div class="al-fgrid">
      <div class="al-fld al-col2"><label>%(product)s<span class="al-help-i" data-help="price_setup.product_name" title="%(h_product)s" tabindex="0" role="img" aria-label="%(h_product)s">&#9432;</span></label><input id="e-product_name" type="text"></div>
    </div>

    <div class="al-fsec">%(s_price)s</div>
    <div class="al-fgrid">
      <div class="al-fld"><label>Min price <span class="al-req">*</span><span class="al-help-i" data-help="price_setup.minimum_price" title="%(h_min)s" tabindex="0" role="img" aria-label="%(h_min)s">&#9432;</span></label><input id="e-min_price" type="number"></div>
      <div class="al-fld"><label>%(lbl_ref)s<span class="al-help-i" data-help="price_setup.reference_price" title="%(h_ref)s" tabindex="0" role="img" aria-label="%(h_ref)s">&#9432;</span></label><input id="e-reference_price" type="number"></div>
      <div class="al-fld al-col2"><label>%(lbl_target)s<span class="al-help-i" data-help="price_setup.rsp" title="%(h_target)s" tabindex="0" role="img" aria-label="%(h_target)s">&#9432;</span></label><input id="e-target_price" type="number"></div>
    </div>

    <!-- C2: alert thresholds (high_alert/severe_drop) are owned by Rules now and
         removed from the Price Setup UI; C3: effective dates removed (policies
         stay active until paused/changed). Backend fields are PRESERVED as hidden
         inputs so existing values are not lost and Active validation never sees a
         missing field. Rules is the single source of truth for thresholds. -->
    <input id="e-high_alert_percent" type="hidden">
    <input id="e-severe_drop_percent" type="hidden">
    <input id="e-effective_from" type="hidden">
    <input id="e-effective_to" type="hidden">

    <details class="al-adv-sec">
      <summary class="al-fsec" style="list-style:revert">%(s_advanced)s</summary>
      <div class="al-fgrid" style="margin-top:8px">
        <div class="al-fld"><label>Owner (KAM)</label><input id="e-owner_user" type="text" placeholder="user@email"></div>
        <div class="al-fld"><label>Status</label><div id="pl-status-line" style="padding-top:6px;font-size:13px"></div></div>
      </div>
      <div class="al-lockbox">
        <label class="al-check"><input id="e-enable_lock" type="checkbox"> %(enable_lock)s</label>
        <div class="al-help">%(h_lock)s</div>
      </div>
    </details>
  </div>
  <div class="al-drawer-actions">
    <button class="al-btn primary" id="pl-save">%(save)s</button>
    <button class="al-btn" id="pl-life" hidden></button>
    <div class="al-more" id="pl-more-wrap" hidden>
      <button class="al-btn" id="pl-more" aria-haspopup="true" aria-expanded="false">%(more_l)s</button>
      <div class="al-more-menu" id="pl-more-menu" hidden><button class="al-btn" id="pl-st-draft">%(to_draft_l)s</button></div>
    </div>
  </div>
</div>
<div class="al-modal wide" id="pl-csv-modal" hidden>
  <h3>%(import_title)s</h3>
  <p style="font-size:12.5px;color:var(--gray-500)">%(csv_hint)s</p>
  <div class="al-inline" style="gap:16px;margin-bottom:8px">
    <label class="al-check"><input type="radio" name="imp-src" id="imp-src-file" value="file" checked> %(src_file)s</label>
    <label class="al-check"><input type="radio" name="imp-src" id="imp-src-paste" value="paste"> %(src_paste)s</label>
  </div>
  <input type="file" id="csv-file" accept=".csv,text/csv">
  <textarea id="csv-paste" rows="6" placeholder="%(paste_ph)s" style="display:none;width:100%%;font-family:monospace;font-size:12px;box-sizing:border-box"></textarea>
  <div class="al-modal-foot" style="justify-content:flex-start">
    <button class="al-btn primary" id="csv-preview">%(preview)s</button>
    <span id="csv-stats" style="font-size:13px;align-self:center"></span>
  </div>
  <div class="al-tbl-wrap" style="max-height:300px;overflow-y:auto">
    <table class="al-tbl"><thead><tr><th><input type="checkbox" id="csv-all" title="%(select_all)s"></th><th>#</th><th>%(action_l)s</th><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU/Item</th><th>Status</th><th class="r">Min</th><th class="r">High %%</th><th class="r">Severe %%</th><th>%(errors)s</th></tr></thead>
    <tbody id="csv-rows"></tbody></table>
  </div>
  <textarea id="csv-errbox" rows="2" readonly placeholder="%(errbox_ph)s" style="margin-top:10px"></textarea>
  <div class="al-modal-foot">
    <span id="csv-summary" style="font-size:13px;align-self:center;flex:1"></span>
    <button class="al-btn" id="csv-copy">%(copy_err)s</button>
    <button class="al-btn" id="csv-cancel">%(cancel)s</button>
    <button class="al-btn primary" id="csv-import" disabled>%(do_import)s</button>
  </div>
  <div id="csv-result" style="margin-top:8px;font-size:13px"></div>
</div>
<div class="al-modal wide" id="pl-sku-modal" hidden>
  <h3>%(sku_btn)s</h3>
  <p style="font-size:12.5px;color:var(--gray-500)" id="pl-sku-scope"></p>
  <div class="al-inline"><input id="pl-sku-kw" type="text" placeholder="%(sku_kw_ph)s"><button class="al-btn primary" id="pl-sku-go">%(search)s</button></div>
  <div class="al-tbl-wrap" style="max-height:340px;overflow-y:auto;margin-top:10px">
    <table class="al-tbl"><thead><tr><th>Seller SKU</th><th>%(product)s</th><th class="r">RSP</th><th>Platform</th><th>Shop</th></tr></thead>
    <tbody id="pl-sku-rows"></tbody></table>
  </div>
  <div class="al-modal-foot"><button class="al-btn" id="pl-sku-cancel">%(cancel)s</button></div>
</div>
<div class="al-modal wide" id="pl-cov-modal" hidden>
  <h3>%(cov_title)s</h3>
  <div class="al-inline"><select id="pl-cov-brand"></select><button class="al-btn primary" id="pl-cov-go">%(search)s</button><button class="al-btn" id="pl-cov-export">%(export_tpl)s</button></div>
  <div id="pl-cov-summary" style="margin:8px 0;font-size:13px"></div>
  <div class="al-tbl-wrap" style="max-height:320px;overflow-y:auto">
    <table class="al-tbl"><thead><tr><th>Seller SKU</th><th>%(product)s</th><th class="r">RSP</th><th class="r">%(order_lines)s</th><th>%(last_order)s</th></tr></thead>
    <tbody id="pl-cov-rows"></tbody></table>
  </div>
  <div class="al-modal-foot"><button class="al-btn" id="pl-cov-cancel">%(cancel)s</button></div>
</div>
<div class="al-toast" id="al-toast" hidden></div>
""" % {
    "TOPBAR": "%(TOPBAR)s", "SUBNAV": "%(SUBNAV)s",
    "title": H("Price Setup"),
    "search": H("Tìm"),
    "sku_kw_ph": H("Gõ SKU hoặc tên sản phẩm..."),
    "cov_title": H("SKU có đơn gần đây nhưng thiếu Active policy"),
    "export_tpl": H("Export CSV template"),
    "order_lines": H("Dòng đơn"), "last_order": H("Đơn gần nhất"),
    "dl_template": H("Tải CSV Template"), "upload_csv": H("Upload CSV"),
    "all": H("Tất cả"), "apply": H("Lọc"), "product": H("Sản phẩm"),
    "effective": H("Hiệu lực"), "optional": H("tuỳ chọn"),
    "enable_lock": H("Tạo đề xuất Stock Safety Lock dry-run khi vi phạm nghiêm trọng"),
    "eff_from": H("Hiệu lực từ"), "eff_to": H("Đến"), "save": H("Lưu"),
    "more_l": H("Thêm"), "to_draft_l": H("Chuyển về Draft"),
    "csv_hint": H("Tải template, điền dữ liệu (Excel: Save As CSV UTF-8), tối đa 500 dòng. Số tiền chấp nhận 5000000 / 5,000,000 / 5.000.000."),
    "preview": H("Kiểm tra (preview)"), "errors": H("Lỗi"),
    "errbox_ph": H("Lỗi sẽ hiện ở đây để copy..."),
    "copy_err": H("Copy lỗi"), "cancel": H("Huỷ"),
    "do_import": H("Import dòng đã chọn"),
    "import_title": H("Nhập hàng loạt (CSV / Paste)"),
    "src_file": H("Tải file CSV"), "src_paste": H("Dán bảng (TSV/CSV)"),
    "paste_ph": H("Dán từ Excel/Sheets (có header). Cột: brand, platform, shop, seller_sku, item, ..., min_price, high_alert_percent, severe_drop_percent, status"),
    "select_all": H("Chọn/bỏ tất cả dòng hợp lệ"), "action_l": H("Hành động"),
    "missing_sum_title": H("Thiếu Price Policy theo brand (theo đơn 30 ngày)"),
    "missing_sum_hint": H("Số SKU distinct chưa có Price Policy active, tính theo đơn hàng 30 ngày gần nhất. Bấm để xem SKU thiếu policy."),
    # Coverage summary (compact KPIs). Basis = distinct seller_sku that appear in
    # orders within the last 30 days, per brand in scope (canonical coverage
    # service - same numbers as the per-brand chips and the modal).
    "cov_sum_title": H("Độ phủ Price Policy"),
    "cov_help": H("Covered = SKU đã có Price Policy active in-effect. Missing = SKU chưa có. Coverage % = Covered / tổng SKU distinct có đơn trong 30 ngày gần nhất. Cơ sở tính theo từng (brand, seller_sku) trong phạm vi của bạn; KHÔNG bịa mẫu số - nếu không có đơn nào thì hiển thị n/a."),
    "cov_basis": H("Cơ sở: SKU distinct có đơn trong 30 ngày gần nhất"),
    "cov_covered": H("Covered SKUs"), "cov_covered_meta": H("đã có Price Policy active"),
    "cov_missing": H("Missing SKUs"), "cov_missing_meta": H("bấm để xem SKU thiếu policy"),
    "cov_missing_hint": H("Mở danh sách SKU thiếu Price Policy (theo brand)"),
    "cov_pct": H("Coverage %"),
    "cov_bybrand": H("Chi tiết thiếu policy theo brand"),
    # drawer sections + helpers (UX hotfix 2)
    "s_scope": H("1. Phạm vi áp dụng"),
    "h_all_fallback": H("Platform=All thường nên để Shop trống. Policy theo platform/shop cụ thể sẽ OVERRIDE policy All. Hệ thống chặn 2 Active policy trùng y hệt scope."),
    "s_product": H("2. Thông tin sản phẩm"),
    "s_price": H("3. Giá (Chính sách giá)"),
    "s_alert_beh": H("4. Hành vi cảnh báo"),
    "s_advanced": H("Cài đặt nâng cao"),
    "scope_default": H("Brand Default — áp dụng cho tất cả sản phẩm của brand"),
    "priority_line": H("Ưu tiên áp dụng: SKU > Shop > Platform > Brand"),
    "alert_beh_copy": H("Các ngưỡng này giúp phát hiện sai lệch giá. Price Setup định nghĩa giá đúng; Rules quyết định hệ thống phản ứng thế nào."),
    "s_thresh": H("4. Ngưỡng cảnh báo"),
    "h_active_req": H("Draft cho phep de trong Min / High % / Severe %. Khi chuyen Active bat buoc du ca ba va dung range: Min > 0, 0 < High % <= 100, 0 < Severe % <= 100. Backend la nguon xac thuc cuoi cung."),
    "s_eff": H("5. Hiệu lực & Owner"),
    "h_shop": H("Shop cụ thể trên sàn. Nếu để trống, policy áp dụng cho toàn platform của brand. (Giữ Shop để hỗ trợ nhiều shop/sàn về sau.)"),
    "sku_btn": H("Tìm SKU từ Omisell"),
    "sku_soon": H("Sắp có - sẽ tải SKU từ Omisell theo Brand/Platform/Shop"),
    "h_sku": H("Tạm thời nhập tay. Sắp có: tìm/chọn SKU từ Omisell sau khi chọn Brand + Platform + Shop, tự điền tên sản phẩm & giá niêm yết nếu có."),
    "h_product": H("Sẽ tự điền từ Omisell/SKU catalog khi có dữ liệu; có thể chỉnh tay nếu cần."),
    "h_min": H("Giá bán thấp nhất được phép sau voucher/giảm giá."),
    "lbl_ref": H("Reference / Benchmark price"),
    "h_ref": H("Giá tham chiếu để so sánh, có thể là giá bán trung bình gần đây hoặc benchmark thị trường."),
    "lbl_target": H("Listed price / RSP"),
    "h_target": H("Giá niêm yết/giá gạch trên sàn, dùng để tính % giảm giá và hiển thị/report. (Tương lai: tự sync từ Omisell nếu có.)"),
    "h_high": H("Cảnh báo khi giá CAO hơn ngưỡng cho phép."),
    "h_severe": H("Cảnh báo nghiêm trọng khi giá giảm SÂU HƠN ngưỡng này so với BASELINE (median 30 ngày; nếu chưa đủ dữ liệu thì dùng Reference price, cuối cùng là Min price). VD severe=50% + baseline 200K thì alert nghiêm trọng khi giá < 100K."),
    "h_lock": H("Chỉ tạo đề xuất để KAM/Lead review. Không khoá tồn thật. Không gửi lệnh sang Omisell. Real stock write vẫn bị khoá bởi DS1."),
}

PAGE2_JS = """
<script id="ec-alert-policies">
(function(){
"use strict";
var A=window.AL,$=A.$;
var S={start:0,pageLen:50,total:0,scope:null,rows:[],current:null,
       caps:null,capsAll:false,prev:null,prevContent:null,missingLoaded:false};
// ----- permission caps (BACKEND is the source of truth, never role text) -----
function cap(brand){if(S.capsAll)return{can_manage:true,can_activate:true};
return (S.caps&&S.caps[brand])||{can_manage:false,can_activate:false};}
function loadCaps(){return A.call("api_policies.policy_caps",{}).then(function(r){
S.capsAll=!!r.all_brands;S.caps=r.caps||{};
$("pl-new").disabled=!(S.capsAll||Object.keys(S.caps).some(function(b){return S.caps[b].can_manage;}));}).catch(function(){});}
// applyCaps now just refreshes the contextual footer (caps are read inside).
function applyCaps(brand){refreshFooter();}
// Contextual lifecycle footer: at most TWO visible lifecycle buttons, chosen by
// the record's CURRENT status. No arrow glyphs. "Set to Draft" (a real backend
// transition) lives under a small More menu for Active/Paused records only.
function curStatus(){return (S.current&&S.current.status)||"Draft";}
function refreshFooter(){var c=cap($("e-brand").value);var st=curStatus();
var life=$("pl-life"),mw=$("pl-more-wrap");
$("pl-save").disabled=!c.can_manage;
$("pl-save").textContent=(!S.current||st==="Draft")?"%(save)s":"%(save_changes)s";
$("pl-more-menu").hidden=true;if($("pl-more"))$("pl-more").setAttribute("aria-expanded","false");
if(!S.current){life.hidden=true;mw.hidden=true;$("pl-st-draft").disabled=!c.can_manage;return;}
if(st==="Active"){life.hidden=false;life.textContent="%(pause_l)s";life.setAttribute("data-to","Paused");life.disabled=!c.can_manage;mw.hidden=false;}
else if(st==="Paused"){life.hidden=false;life.textContent="%(resume_l)s";life.setAttribute("data-to","Active");life.disabled=!c.can_activate;life.title=c.can_activate?"":"%(no_activate)s";mw.hidden=false;}
else{life.hidden=false;life.textContent="%(activate_l)s";life.setAttribute("data-to","Active");life.disabled=!c.can_activate;life.title=c.can_activate?"":"%(no_activate)s";mw.hidden=true;}
$("pl-st-draft").disabled=!c.can_manage;}
// ----- per-brand missing-policy summary (unknown/not-loaded -> '-', confirmed 0 -> '0') -----
function loadMissing(){var box=$("pl-missing-rows");
A.call("api_policies.missing_policy_summary",{}).then(function(res){S.missingLoaded=true;var sum=res.summary||{};
var brands=(S.scope&&S.scope.supervisor)?Object.keys(sum):(S.scope&&S.scope.brands?Object.keys(S.scope.brands):[]);
if(!brands.length){box.innerHTML='<span class="al-empty">-</span>';return;}
box.innerHTML=brands.sort().map(function(b){var n=(b in sum)?sum[b]:0;
return '<button class="al-chip '+(n>0?"warn":"ok")+'" data-mbrand="'+A.esc(b)+'" title="%(chip_title)s"><span>'+A.esc(b)+'</span><span class="al-chip-n">'+n+'</span></button>';}).join("");
}).catch(function(){box.innerHTML='<span class="al-empty">-</span>';});}
// ----- compact coverage summary (Covered / Missing / Coverage pct) -----
// Aggregates the CANONICAL per-brand coverage_report across the user's scoped
// brands (one existing endpoint, no backend change). missing_count and checked
// are FULL distinct counts regardless of the list limit, so limit:1 keeps the
// payload tiny while the numbers stay exact. Denominator = total distinct
// ordered seller_sku in the 30d window; if there are NO orders, pct shows n/a
// (never a fabricated denominator).
function loadCoverageSummary(){
var brands=Object.keys((S.scope&&S.scope.brands)||{});S.covBrands=brands;
var cov=$("pl-cov-covered"),mis=$("pl-cov-missing"),pct=$("pl-cov-pct");
if(!brands.length){cov.textContent="0";mis.textContent="0";pct.textContent="n/a";return;}
cov.textContent=mis.textContent=pct.textContent="\\u2026";
Promise.all(brands.map(function(b){return A.call("api_sku_catalog.policy_missing_skus",{brand:b,days:30,limit:1}).then(function(r){return {checked:+r.checked||0,missing:+r.missing_count||0};}).catch(function(){return {checked:0,missing:0};});})).then(function(res){
var tc=0,tm=0;res.forEach(function(x){tc+=x.checked;tm+=x.missing;});
var covered=Math.max(0,tc-tm);
cov.textContent=covered;mis.textContent=tm;
pct.textContent=tc?(Math.round(1000*(tc-tm)/tc)/10+"%%"):"n/a";});}
function openMissingView(){var brands=S.covBrands||[];
if(brands.length===1){openCoverageFor(brands[0]);return;}
var d=$("pl-cov-bybrand");if(d){d.open=true;if(!S.missingLoaded)loadMissing();d.scrollIntoView({behavior:"smooth",block:"nearest"});}}
// ----- bulk import workbench helpers -----
function actChip(a,detail){var col={Create:"#16a34a",Update:"#2563eb",Skip:"#6b7280",Conflict:"#d97706",Invalid:"#dc2626"}[a]||"#6b7280";
var t=(a==="Update"&&detail)?(" \\u2192 "+A.esc(detail)):((a==="Conflict"&&detail)?(" ("+A.esc(detail)+")"):"");
return '<span style="font-weight:600;color:'+col+'">'+a+'</span>'+t;}
function selectedLines(){var out=[];Array.prototype.forEach.call(document.querySelectorAll("#csv-rows .csv-pick:checked"),function(cb){out.push(+cb.getAttribute("data-line"));});return out;}
function refreshImportBtn(){$("csv-import").disabled=(!S.prev)||selectedLines().length===0;}
function toggleSrc(){var paste=$("imp-src-paste").checked;$("csv-paste").style.display=paste?"block":"none";$("csv-file").style.display=paste?"none":"block";}
function invalidatePreview(){S.prev=null;S.prevContent=null;$("csv-import").disabled=true;
if($("csv-rows").innerHTML)$("csv-summary").innerHTML="%(changed_repreview)s";}
function importContent(cb){if($("imp-src-paste").checked){cb($("csv-paste").value||"");return;}
var f=$("csv-file").files[0];if(!f){cb(null);return;}var rd=new FileReader();rd.onload=function(){cb(rd.result);};rd.readAsText(f,"utf-8");}
function showLifecycle(msg,res){var lc=res&&res.lifecycle;
if(lc&&((lc.closed&&lc.closed.length)||lc.policy_status==="Active")){
var n=(lc.closed||[]).length;var rem=(lc.remaining_missing==null?"-":lc.remaining_missing);
A.toast(msg+" \\u00b7 %(lc_closed)s "+n+" \\u00b7 %(lc_remaining)s "+rem);}else{A.toast(msg);}}
function loadConflicts(rows){var brands={};(rows||[]).forEach(function(r){if(r.brand)brands[r.brand]=1;});
Object.keys(brands).forEach(function(b){A.call("api_policies.policy_conflicts",{brand:b}).then(function(res){var f=(res&&res.flags)||{};
Object.keys(f).forEach(function(nm){var el=document.querySelector('.al-conf-badge[data-conf="'+nm.replace(/["\\\\]/g,"")+'"]');if(!el)return;var tags=f[nm];
if(tags.indexOf("duplicate")>=0){el.innerHTML='<span class="al-badge al-b-critical" title="%(dup_t)s">%(dup_b)s</span>';}
else if(tags.indexOf("overridden")>=0){el.innerHTML='<span class="al-badge al-b-warning" title="%(ovr_t)s">%(ovr_b)s</span>';}});}).catch(function(){});});}
function filters(){var f={};
[["f-brand","brand"],["f-platform","platform"],["f-status","status"]].forEach(function(p){var v=$(p[0]).value;if(v)f[p[1]]=v;});
var sku=$("f-sku").value.trim();if(sku)f.seller_sku=sku;
var o=$("f-owner").value.trim();if(o)f.owner_user=o;return f;}
function polScope(r){var t=(r.seller_sku||r.item)?"%(ps_sku)s":r.shop?"%(ps_shop)s":(r.platform&&r.platform!=="All")?"%(ps_platform)s":"%(ps_brand)s";return '<span class="al-badge al-b-info" title="%(ps_priority)s">'+t+'</span>';}
function load(){var tb=$("pl-rows");tb.innerHTML='<tr><td colspan="11" class="al-empty">%(loading)s</td></tr>';
A.call("api_policies.list_policies",{filters:filters(),start:S.start,page_len:S.pageLen}).then(function(res){S.rows=res.rows;S.total=res.total;
if(!res.rows.length){tb.innerHTML='<tr><td colspan="11" class="al-empty">%(no_rows)s</td></tr>';}
else{tb.innerHTML=res.rows.map(function(r,i){return '<tr data-i="'+i+'">'+
'<td>'+A.esc(r.brand)+' '+polScope(r)+'</td><td>'+A.esc(r.platform)+'</td><td>'+A.esc(r.shop||"-")+'</td><td>'+A.esc(r.seller_sku||r.item||"-")+' <span class="al-conf-badge" data-conf="'+A.esc(r.name)+'"></span></td><td>'+A.esc(r.product_name||"-")+'</td>'+
'<td>'+A.money(r.min_price)+'</td><td>'+A.money(r.target_price)+'</td><td>'+A.money(r.reference_price)+'</td>'+
'<td>'+A.polBadge(r.status)+'</td><td>'+A.esc(r.owner_user||"-")+'</td><td>'+A.esc((r.effective_from||"")+(r.effective_to?(" \\u2192 "+r.effective_to):""))+'</td></tr>';}).join("");loadConflicts(res.rows);}
var from=S.total?S.start+1:0;$("pl-count").textContent=from+"-"+Math.min(S.start+S.pageLen,S.total)+" / "+S.total;
$("pl-prev").disabled=S.start<=0;$("pl-next").disabled=S.start+S.pageLen>=S.total;}).catch(function(e){tb.innerHTML='<tr><td colspan="11" class="al-empty">%(err)s'+A.esc(e.message)+'</td></tr>';});}
var FIELDS=["platform","shop","seller_sku","item","product_name","min_price","reference_price","target_price","high_alert_percent","severe_drop_percent","effective_from","effective_to","owner_user"];
function openDrawer(r){S.current=r||null;
$("pl-d-title").textContent=r?r.name:"New Policy";
A.fillBrandSelect($("e-brand"),S.scope,{extra:(r&&r.brand)||null,value:(r&&r.brand)||null});
FIELDS.forEach(function(k){var el=$("e-"+k);if(el)el.value=(r&&r[k]!=null)?r[k]:"";});
$("e-enable_lock").checked=!!(r&&r.enable_stock_safety_lock);
$("pl-d-status").innerHTML=A.polBadge(curStatus());
$("pl-status-line").innerHTML=(r&&r.import_batch)?("batch "+A.esc(r.import_batch)):"";
applyCaps($("e-brand").value);
updateScopePreview();applyFieldHelp($("pl-drawer"));
$("al-overlay").hidden=false;$("pl-drawer").hidden=false;}
// Live scope preview (informational only; backend resolution unchanged).
function updateScopePreview(){var sp=$("e-scope-preview");if(!sp)return;var t=sp.querySelector(".al-sp-text");if(!t)return;
var b=$("e-brand").value||"(brand)",pf=$("e-platform").value,sh=$("e-shop").value.trim(),sk=($("e-seller_sku").value.trim()||$("e-item").value.trim());
var scope,msg;
if(sk){scope="%(ps_sku)s";msg=b+" \\u2192 SKU "+sk;}
else if(sh){scope="%(ps_shop)s";msg=b+" \\u2192 shop "+sh;}
else if(pf&&pf!=="All"){scope="%(ps_platform)s";msg=b+" \\u2192 "+pf;}
else{scope="%(ps_brand)s";msg="t\\u1ea5t c\\u1ea3 "+b;}
t.textContent=scope+" \\u2014 "+msg;}
// Upgrade info-icon tooltips from EC Field Description when a record exists.
function applyFieldHelp(root){var els=(root||document).querySelectorAll("[data-help]");Array.prototype.forEach.call(els,function(el){var h=A.fieldHelp(el.getAttribute("data-help"));if(h&&h.help){el.title=h.help;el.setAttribute("aria-label",h.help);}});}
function closeDrawer(){$("al-overlay").hidden=true;$("pl-drawer").hidden=true;}
function save(){var data={brand:$("e-brand").value};
FIELDS.forEach(function(k){var v=$("e-"+k).value;if(v!=="")data[k]=v;});
data.enable_stock_safety_lock=$("e-enable_lock").checked?1:0;
A.call("api_policies.save_policy",{policy:data,name:S.current?S.current.name:null}).then(function(res){showLifecycle("%(saved)s",res);closeDrawer();load();loadMissing();loadCoverageSummary();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function setStatus(st){if(!S.current){A.toast("Save first");return;}
if(st==="Active"){var miss=[];["min_price","high_alert_percent","severe_drop_percent"].forEach(function(k){if(!$("e-"+k).value)miss.push(k);});if(miss.length){A.toast("%(warn_active)s"+miss.join(", "));}}
A.call("api_policies.set_policy_status",{name:S.current.name,status:st}).then(function(res){showLifecycle("%(saved)s",res);closeDrawer();load();loadMissing();loadCoverageSummary();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function dlTemplate(){A.call("api_policies.csv_template").then(function(t){
var a=document.createElement("a");a.href="data:text/csv;charset=utf-8,"+encodeURIComponent(t.content);a.download=t.filename;document.body.appendChild(a);a.click();a.remove();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function openCsv(){$("csv-file").value="";$("csv-paste").value="";$("csv-rows").innerHTML="";$("csv-stats").textContent="";$("csv-summary").textContent="";$("csv-errbox").value="";$("csv-result").innerHTML="";$("csv-import").disabled=true;S.prev=null;S.prevContent=null;
$("imp-src-file").checked=true;toggleSrc();
$("al-overlay").hidden=false;$("pl-csv-modal").hidden=false;}
function preview(){importContent(function(text){
if(text==null){A.toast("%(need_input)s");return;}
S.prevContent=text;S.prev=null;var src=$("imp-src-paste").checked?"paste":"csv";
A.call("api_policies.preview_policy_csv",{content:text,source:src}).then(function(res){
if(res.file_errors){$("csv-stats").innerHTML='<span style="color:#dc2626">'+A.esc(res.file_errors.join("; "))+'</span>';$("csv-rows").innerHTML="";$("csv-summary").textContent="";$("csv-import").disabled=true;return;}
S.prev=res;var errs=[];
$("csv-rows").innerHTML=res.rows.map(function(r){var sel=(r.action==="Create"||r.action==="Update");var rw=r.row||{};
if(r.errors&&r.errors.length)errs=errs.concat(r.errors);
return '<tr data-line="'+r.line+'">'+
'<td>'+(sel?'<input type="checkbox" class="csv-pick" data-line="'+r.line+'" checked>':'')+'</td>'+
'<td>'+r.line+'</td><td>'+actChip(r.action,r.detail)+'</td>'+
'<td>'+A.esc(rw.brand||"")+'</td><td>'+A.esc(rw.platform||"")+'</td><td>'+A.esc(rw.shop||"-")+'</td>'+
'<td>'+A.esc(rw.seller_sku||rw.item||"")+'</td><td>'+A.esc(rw.status||"Draft")+'</td>'+
'<td class="r">'+A.esc(rw.min_price||"")+'</td><td class="r">'+A.esc(rw.high_alert_percent||"")+'</td><td class="r">'+A.esc(rw.severe_drop_percent||"")+'</td>'+
'<td style="white-space:normal;color:#dc2626">'+A.esc((r.errors||[]).join("; "))+'</td></tr>';}).join("");
var c=res.counts||{};
$("csv-stats").textContent="";
$("csv-summary").innerHTML="%(sum_total)s "+res.rows.length+" \\u00b7 Create "+(c.create||0)+" \\u00b7 Update "+(c.update||0)+" \\u00b7 Skip "+(c.skip||0)+" \\u00b7 Conflict "+(c.conflict||0)+" \\u00b7 Invalid "+(c.invalid||0);
$("csv-errbox").value=errs.join("\\n");$("csv-all").checked=true;refreshImportBtn();
}).catch(function(e){A.toast("%(err)s"+e.message);});});}
function doImport(){if(!S.prev||!S.prevContent)return;var lines=selectedLines();if(!lines.length){A.toast("%(need_pick)s");return;}
$("csv-import").disabled=true;var src=$("imp-src-paste").checked?"paste":"csv";
A.call("api_policies.import_policy_csv",{content:S.prevContent,source:src,lines:JSON.stringify(lines)}).then(function(r){
var html="%(res_created)s "+r.created+" \\u00b7 %(res_updated)s "+r.updated+" \\u00b7 %(res_skipped)s "+r.skipped+" \\u00b7 %(res_failed)s "+(r.failed?r.failed.length:0);
if(r.closed_alerts)html+=" \\u00b7 %(lc_closed)s "+r.closed_alerts;
if(r.failed&&r.failed.length){html+='<div class="al-tbl-wrap" style="max-height:140px;overflow:auto;margin-top:6px"><table class="al-tbl"><thead><tr><th>#</th><th>%(act_l)s</th><th>%(err_l)s</th></tr></thead><tbody>'+
r.failed.map(function(f){return '<tr><td>'+f.line+'</td><td>'+A.esc(f.action)+'</td><td style="white-space:normal">'+A.esc((f.errors||[]).join("; "))+'</td></tr>';}).join("")+'</tbody></table></div>';}
$("csv-result").innerHTML=html;A.toast("%(imported)s");
load();loadMissing();refreshImportBtn();   // partial: keep modal + rows open
}).catch(function(e){A.toast("%(err)s"+e.message);$("csv-import").disabled=false;});}
function copyErrs(){var box=$("csv-errbox");box.select();try{document.execCommand("copy");A.toast("%(copy_ok)s");}catch(e){}}
function openSkuSearch(){var b=$("e-brand").value;if(!b){A.toast("%(need_brand)s");return;}
$("pl-sku-scope").textContent=b+" / "+($("e-platform").value||"All")+" / "+($("e-shop").value||"-");
$("pl-sku-kw").value=$("e-seller_sku").value||"";$("pl-sku-rows").innerHTML="";
$("pl-sku-modal").hidden=false;$("al-overlay").hidden=false;doSkuSearch();}
function doSkuSearch(){var b=$("e-brand").value;var args={brand:b,keyword:$("pl-sku-kw").value,limit:30};
var pf=$("e-platform").value;if(pf&&pf!=="All")args.platform=pf;var sh=$("e-shop").value;if(sh)args.shop=sh;
A.call("api_sku_catalog.search_skus",args).then(function(res){var rows=res.rows||[];S.skuRows=rows;
$("pl-sku-rows").innerHTML=rows.length?rows.map(function(x,i){return '<tr data-si="'+i+'"><td>'+A.esc(x.seller_sku)+'</td><td>'+A.esc(x.product_name||"-")+'</td><td class="r">'+A.money(x.rsp_price)+'</td><td>'+A.esc(x.platform||"-")+'</td><td>'+A.esc(x.shop||"-")+'</td></tr>';}).join(""):'<tr><td colspan="5" class="al-empty">%(no_rows)s</td></tr>';}).catch(function(e){A.toast("%(err)s"+e.message);});}
function selectSku(x){$("e-seller_sku").value=x.seller_sku||"";if(x.product_name)$("e-product_name").value=x.product_name;
if(x.rsp_price!=null&&x.rsp_price!=="")$("e-target_price").value=x.rsp_price;
if(x.platform&&!$("e-platform").value)$("e-platform").value=x.platform;
if(x.shop&&!$("e-shop").value)$("e-shop").value=x.shop;
$("pl-sku-modal").hidden=true;$("al-overlay").hidden=true;A.toast("%(sku_picked)s");}
function ensureCovBrand(brand){var sel=$("pl-cov-brand");
var has=Array.prototype.some.call(sel.options,function(o){return o.value===brand;});
if(!has){var o=document.createElement("option");o.value=brand;o.textContent=brand;sel.appendChild(o);}
sel.value=brand;}
function openCoverageFor(brand){if(!brand)return;
A.fillBrandSelect($("pl-cov-brand"),S.scope,{});   // base options (scoped users)
ensureCovBrand(brand);                              // guarantee clicked brand present+selected (supervisor)
$("pl-cov-summary").textContent="";$("pl-cov-rows").innerHTML="";
$("pl-cov-modal").hidden=false;$("al-overlay").hidden=false;loadCoverage();}
function loadCoverage(){var b=$("pl-cov-brand").value;if(!b){A.toast("%(need_brand)s");return;}
A.call("api_sku_catalog.policy_missing_skus",{brand:b,days:30,limit:200}).then(function(res){S.cov=res;
$("pl-cov-summary").innerHTML="%(coverage)s: <b>"+(res.coverage_pct==null?"n/a":res.coverage_pct+"%%")+"</b> &middot; %(missing)s: <b>"+res.missing_count+"</b> / "+res.checked;
var rows=res.missing||[];$("pl-cov-rows").innerHTML=rows.length?rows.map(function(x){return '<tr><td>'+A.esc(x.seller_sku)+'</td><td>'+A.esc(x.product_name||"-")+'</td><td class="r">'+A.money(x.rsp_price)+'</td><td class="r">'+(x.order_lines||0)+'</td><td>'+A.esc(A.dt(x.last_order))+'</td></tr>';}).join(""):'<tr><td colspan="5" class="al-empty">%(no_rows)s</td></tr>';}).catch(function(e){A.toast("%(err)s"+e.message);});}
function exportCovTemplate(){if(!(S.cov&&S.cov.missing&&S.cov.missing.length)){A.toast("%(no_rows)s");return;}
var b=$("pl-cov-brand").value;var cols=["brand","platform","shop","seller_sku","product_name","min_price","reference_price","target_price"];
var q=function(v){v=(v==null?"":String(v));if(/[",\\n]/.test(v))v='"'+v.replace(/"/g,'""')+'"';return v;};
var lines=[cols.join(",")];S.cov.missing.forEach(function(x){lines.push([b,"","",x.seller_sku,x.product_name||"","",x.rsp_price||"",x.rsp_price||""].map(q).join(","));});
var blob=new Blob(["\\ufeff"+lines.join("\\n")],{type:"text/csv;charset=utf-8;"});var url=URL.createObjectURL(blob);var a=document.createElement("a");a.href=url;a.download="missing_policy_"+b+".csv";document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(url);},1000);A.toast("%(csv_exported)s");}
function init(){A.initScope("/alerts/policies",function(scope){S.scope=scope;
$("al-scope-line").textContent=scope.supervisor?"Supervisor scope: all brands":("Brands: "+Object.keys(scope.brands).join(", "));
var bsel=$("f-brand");Object.keys(scope.brands||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;bsel.appendChild(o);});
load();loadCaps();loadMissing();loadCoverageSummary();applyFieldHelp($("pl-missing-panel"));});
$("pl-cov-kpis").addEventListener("click",function(ev){if(ev.target.closest('[data-cov="missing"]'))openMissingView();});
$("pl-cov-kpis").addEventListener("keydown",function(ev){if((ev.key==="Enter"||ev.key===" ")&&ev.target.closest('[data-cov="missing"]')){ev.preventDefault();openMissingView();}});
$("pl-apply").onclick=function(){S.start=0;load();};
$("pl-prev").onclick=function(){S.start=Math.max(0,S.start-S.pageLen);load();};
$("pl-next").onclick=function(){S.start+=S.pageLen;load();};
$("pl-rows").addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-i]");if(tr)openDrawer(S.rows[+tr.getAttribute("data-i")]);});
$("pl-new").onclick=function(){openDrawer(null);};
$("pl-d-close").onclick=closeDrawer;
$("al-overlay").onclick=function(){closeDrawer();$("pl-csv-modal").hidden=true;$("pl-sku-modal").hidden=true;$("pl-cov-modal").hidden=true;};
$("e-sku-search").onclick=openSkuSearch;
$("pl-sku-go").onclick=doSkuSearch;
$("pl-sku-kw").addEventListener("keydown",function(e){if(e.key==="Enter")doSkuSearch();});
$("pl-sku-cancel").onclick=function(){$("pl-sku-modal").hidden=true;$("al-overlay").hidden=true;};
$("pl-sku-rows").addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-si]");if(tr&&S.skuRows)selectSku(S.skuRows[+tr.getAttribute("data-si")]);});
$("pl-cov-go").onclick=loadCoverage;
$("pl-cov-cancel").onclick=function(){$("pl-cov-modal").hidden=true;$("al-overlay").hidden=true;};
$("pl-cov-export").onclick=exportCovTemplate;
$("pl-save").onclick=save;
$("pl-life").onclick=function(){setStatus($("pl-life").getAttribute("data-to"));};
$("pl-more").onclick=function(){var m=$("pl-more-menu"),h=m.hidden;m.hidden=!h;$("pl-more").setAttribute("aria-expanded",h?"true":"false");};
$("pl-st-draft").onclick=function(){setStatus("Draft");};
$("pl-template").onclick=dlTemplate;
$("pl-upload").onclick=openCsv;
$("csv-preview").onclick=preview;
$("csv-import").onclick=doImport;
$("csv-cancel").onclick=function(){$("pl-csv-modal").hidden=true;$("al-overlay").hidden=true;};
$("csv-copy").onclick=copyErrs;
$("imp-src-file").onclick=function(){toggleSrc();invalidatePreview();};
$("imp-src-paste").onclick=function(){toggleSrc();invalidatePreview();};
$("csv-paste").addEventListener("input",invalidatePreview);
$("csv-file").addEventListener("change",invalidatePreview);
$("csv-all").onclick=function(){var on=$("csv-all").checked;Array.prototype.forEach.call(document.querySelectorAll("#csv-rows .csv-pick"),function(cb){cb.checked=on;});refreshImportBtn();};
$("csv-rows").addEventListener("change",function(ev){if(ev.target.classList&&ev.target.classList.contains("csv-pick"))refreshImportBtn();});
$("pl-missing-rows").addEventListener("click",function(ev){var el=ev.target.closest("[data-mbrand]");if(!el)return;openCoverageFor(el.getAttribute("data-mbrand"));});
$("e-brand").addEventListener("change",function(){applyCaps($("e-brand").value);});
["e-brand","e-platform","e-shop","e-seller_sku","e-item"].forEach(function(id){var el=$(id);if(el){el.addEventListener("change",updateScopePreview);el.addEventListener("input",updateScopePreview);}});}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init);}else{init();}
})();
</script>
""" % dict(VNJ, errors_l=js_escape("lỗi"), created_l=js_escape("tạo mới"),
           updated_l=js_escape("cập nhật"),
           save=js_escape("Lưu"), save_changes=js_escape("Lưu thay đổi"),
           activate_l=js_escape("Kích hoạt"), pause_l=js_escape("Tạm dừng"),
           resume_l=js_escape("Tiếp tục"),
           need_brand=js_escape("Chọn Brand trước."),
           ps_sku=js_escape("SKU-specific"), ps_shop=js_escape("Shop Policy"),
           ps_platform=js_escape("Platform Policy"), ps_brand=js_escape("Brand fallback"),
           ps_priority=js_escape("Ưu tiên: SKU > Shop > Platform > Brand"),
           chip_title=js_escape("Bấm để xem SKU thiếu Active policy"),
           sku_picked=js_escape("Đã chọn SKU."),
           coverage=js_escape("Coverage"), missing=js_escape("Thiếu policy"),
           csv_exported=js_escape("Đã xuất CSV."),
           no_activate=js_escape("Bạn không có quyền Active/Inactive policy brand này."),
           changed_repreview=js_escape("Nội dung đã đổi - bấm Preview lại trước khi Import."),
           lc_closed=js_escape("Đã đóng missing_policy:"),
           lc_remaining=js_escape("SKU còn thiếu:"),
           need_input=js_escape("Chọn file CSV hoặc dán dữ liệu."),
           need_pick=js_escape("Chọn ít nhất 1 dòng để import."),
           warn_active=js_escape("Active cần đủ (backend kiểm tra): "),
           sum_total=js_escape("Tổng"),
           res_created=js_escape("Tạo:"), res_updated=js_escape("Cập nhật:"),
           res_skipped=js_escape("Bỏ qua:"), res_failed=js_escape("Lỗi:"),
           act_l=js_escape("Hành động"), err_l=js_escape("Lỗi"),
           dup_b=js_escape("TRÙNG"), dup_t=js_escape("Có Active policy khác trùng y hệt scope + chồng hiệu lực. Inactivate bớt 1."),
           ovr_b=js_escape("fallback"), ovr_t=js_escape("Bị policy cụ thể hơn override (Shop+Platform+SKU > Platform+SKU > All+SKU)."))


# ========================= PAGE 3: /alerts/rules ============================
PAGE3_CONTENT = """
  <div class="ec-main">
    %(TOPBAR)s
    %(SUBNAV)s
    <div class="content">
      <div class="greeting"><h1>%(title)s</h1><p id="al-scope-line"></p></div>
      <div class="al-note"><span class="al-note-ic">&#9432;</span><span>%(intro_copy)s</span></div>
      <!-- D: ONE concise scope-priority line; each tier label carries its own
           EC Field Description tooltip. The duplicate sentence + panel-header copy
           were removed. -->
      <div class="al-help" style="margin:-6px 0 12px;display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-weight:600" id="ru-tier-legend">
        <span class="al-tierleg" data-help="rules.sku_exception" title="%(h_sku_exception)s" tabindex="0" role="img" aria-label="%(h_sku_exception)s">SKU Exception <span class="al-help-i">&#9432;</span></span> &gt;
        <span class="al-tierleg" data-help="rules.shop_override" title="%(h_shop_override)s" tabindex="0" role="img" aria-label="%(h_shop_override)s">Shop Override <span class="al-help-i">&#9432;</span></span> &gt;
        <span class="al-tierleg" data-help="rules.platform_override" title="%(h_platform_override)s" tabindex="0" role="img" aria-label="%(h_platform_override)s">Platform Override <span class="al-help-i">&#9432;</span></span> &gt;
        <span class="al-tierleg" data-help="rules.brand_default" title="%(h_brand_default)s" tabindex="0" role="img" aria-label="%(h_brand_default)s">Brand Default <span class="al-help-i">&#9432;</span></span>
      </div>
      <div class="al-banner">%(banner)s</div>
      <div class="panel">
        <div class="panel-header"><div class="panel-title">%(s_defaults)s</div>
          <button class="al-btn primary" id="ru-new">+ Rule</button></div>
        <div class="al-filters">
          <div><label>Brand</label><select id="f-brand"><option value="">%(all)s</option></select></div>
          <div><label>Rule</label><select id="f-rule_code"><option value="">%(all)s</option><option>below_min</option><option>above_high</option><option>severe_price_drop</option><option>possible_missing_zero</option></select></div>
          <div><label>Status</label><select id="f-status"><option value="">%(all)s</option><option>Draft</option><option>Active</option><option>Paused</option></select></div>
          <button class="al-btn primary" id="ru-apply">%(apply)s</button>
        </div>
        <div id="ru-defaults" style="padding:4px 0"></div>
      </div>
      <details class="al-adv-sec" id="ru-exc-sec" style="margin-top:14px">
        <summary class="panel-title" style="cursor:pointer;padding:8px 0;list-style:revert">%(s_exceptions)s</summary>
        <div class="panel" style="margin-top:6px">
          <div class="al-help" style="padding:8px 16px 0">%(exc_help)s</div>
          <div class="al-tbl-wrap">
            <table class="al-tbl">
              <thead><tr><th>Rule</th><th>%(tier)s</th><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU</th><th>Severity</th><th>%(threshold)s</th><th>%(rec_lock)s</th><th>Status</th><th>%(approved)s</th><th>%(effective)s</th></tr></thead>
              <tbody id="ru-rows"></tbody>
            </table>
          </div>
        </div>
      </details>
    </div>
  </div>
</div>
<div class="al-overlay" id="al-overlay" hidden></div>
<!-- E3 simplified KAM rule editor: only Brand + Behaviour + the ONE behaviour-
     specific All-platforms threshold + optional per-platform overrides + Save/
     Cancel. Raw rule_code / scope mechanics / severity override / lifecycle
     buttons / effective period are NOT shown - canonical codes stay in JS/API
     payloads only. -->
<div class="al-drawer al-drawer-wide" id="ru-drawer" hidden>
  <div class="al-drawer-head"><strong id="ru-d-title">%(rule_title)s</strong><button class="al-btn" id="ru-d-close">&#10005;</button></div>
  <div class="al-drawer-body">
    <div class="al-fgrid">
      <div class="al-fld"><label>Brand <span class="al-req">*</span></label><select id="r-brand"></select></div>
      <div class="al-fld"><label>%(behaviour_l)s <span class="al-req">*</span></label><select id="r-behaviour"><option value="below_min">%(b_belowmin)s</option><option value="severe_price_drop">%(b_severe)s</option><option value="above_high">%(b_above)s</option></select></div>
    </div>
    <div class="al-fsec">%(all_platforms_l)s</div>
    <div class="al-fgrid">
      <div class="al-fld al-col2"><label id="r-thr-all-lbl">%(threshold_l)s %%</label><input id="r-thr-all" type="number" step="0.01" min="0" max="100"></div>
    </div>
    <details class="al-adv-sec" id="ru-cust-sec">
      <summary class="al-fsec" style="cursor:pointer;list-style:revert">%(customize_l)s</summary>
      <div id="ru-cust-rows" style="padding:4px 0"></div>
    </details>
    <div id="ru-status-line" style="margin:10px 0 0;font-size:12.5px;color:var(--gray-600)"></div>
    <!-- internal-only (never shown to the KAM): preserved on save so existing
         values are not lost; canonical scope = brand + behaviour + platform. -->
    <input id="r-severity_override" type="hidden">
    <input id="r-effective_from" type="hidden">
    <input id="r-effective_to" type="hidden">
  </div>
  <div class="al-drawer-actions">
    <button class="al-btn primary" id="ru-save">%(save_l)s</button>
    <button class="al-btn" id="ru-cancel">%(cancel)s</button>
  </div>
</div>
<div class="al-toast" id="al-toast" hidden></div>
""" % {
    "TOPBAR": "%(TOPBAR)s", "SUBNAV": "%(SUBNAV)s",
    "title": H("Cấu hình rule cảnh báo"),
    "banner": H("Rule chỉ ảnh hưởng việc ĐÁNH GIÁ ALERT và ĐỀ XUẤT DRY-RUN stock lock. Không có thao tác khoá kho thật — DS1 đang khoá. Không rule nào thì engine giữ nguyên hành vi mặc định."),
    "prio_label": H("Ưu tiên scope"), "all": H("Tất cả"), "apply": H("Lọc"),
    "tier": H("Tầng scope"), "threshold": H("Ngưỡng %"),
    "intro_copy": H("Price Setup định nghĩa giá đúng. Rules định nghĩa khi nào sai lệch giá sẽ tạo cảnh báo hoặc đề xuất Stock Safety."),
    "prio_chain": H("Ưu tiên áp dụng: SKU Exception > Shop Override > Platform Override > Brand Default"),
    "s_defaults": H("Brand Defaults"), "s_exceptions": H("Advanced Exceptions"),
    # E3 simplified rule editor (drawer) labels
    "rule_title": H("Cấu hình rule theo brand"), "behaviour_l": H("Hành vi"),
    "threshold_l": H("Ngưỡng"), "save_l": H("Lưu"),
    "all_platforms_l": H("Tất cả platform"), "customize_l": H("Tùy chỉnh theo platform"),
    "b_belowmin": H("Dưới giá tối thiểu"), "b_severe": H("Rớt giá mạnh"),
    "b_above": H("Vượt benchmark"), "cancel": H("Huỷ"),
    "exc_help": H("Rule theo Platform / Shop / SKU sẽ override Brand Default theo thứ tự ưu tiên."),
    "rec_lock": H("Đề xuất lock"), "approved": H("Duyệt bởi"),
    "effective": H("Hiệu lực"), "optional": H("tuỳ chọn"),
    "keep_default": H("Giữ mặc định"),
    "threshold_hint": H("below_min: gap >= X% dưới min thì Critical · severe_price_drop: % rơi so baseline · above_high: % vượt tham chiếu"),
    "generic": H("chung"),
    "rs_scope": H("1. Phạm vi áp dụng"), "rs_rule": H("2. Rule & mức độ"),
    "rs_thresh": H("3. Ngưỡng (Rules sở hữu)"), "rs_lock": H("4. Dry-run lock"),
    "rs_eff": H("5. Hiệu lực & trạng thái"),
    "rs_advanced": H("Nâng cao (hiệu lực, trạng thái, công cụ)"),
    # EC Field Description help-icon static fallbacks (overridden live by the
    # EC Field Description adapter when present; these are the offline copy).
    "h_rule_type": H("Loại rule quyết định engine đánh giá điều kiện giá nào: below_min (dưới giá sàn), above_high (cao bất thường), severe_price_drop (rớt giá sâu), possible_missing_zero (nghi giá 0/thiếu)."),
    "h_threshold": H("Ngưỡng % do Rules sở hữu. severe drop = % rớt so với baseline; high alert = % cao so với reference. Để trống = fallback Price Policy rồi mặc định hệ thống."),
    "h_action": H("Hành động của rule: chỉ tạo Alert, hoặc kèm đề xuất Stock Safety Lock dạng DRY-RUN (mô phỏng). Không có thao tác khoá kho thật — DS1 đang khoá."),
    "h_recommend_ss": H("Khi bật, vi phạm nghiêm trọng sẽ tạo một đề xuất Stock Safety Lock để KAM/Lead review. Đây là MÔ PHỎNG, không gửi lệnh sang Omisell."),
    "h_scope_priority": H("Khi nhiều rule cùng khớp, engine chọn rule cụ thể nhất theo thứ tự: SKU Exception > Shop Override > Platform Override > Brand Default."),
    "h_brand_default": H("Brand Default: rule áp cho toàn brand (không chỉ định Platform/Shop/SKU). Là tầng nền, bị override bởi các tầng cụ thể hơn."),
    "h_platform_override": H("Platform Override: rule chỉ định Platform (vd Shopee) — override Brand Default cho platform đó."),
    "h_shop_override": H("Shop Override: rule chỉ định Shop — override Brand Default và Platform Override cho shop đó."),
    "h_sku_exception": H("SKU Exception: rule chỉ định Seller SKU / Item — tầng ưu tiên cao nhất, override mọi tầng còn lại."),
    "rh_scope": H("Ưu tiên scope khi engine chọn rule: SKU > Shop > Platform > Brand. Để trống = áp cho cả brand."),
    "rh_own": H("Rules sở hữu các ngưỡng này. Price Policy chỉ giữ dữ liệu giá gốc (Min/Reference/RSP/lock). Để trống = fallback Policy (cũ) rồi mặc định hệ thống."),
    "rh_severe": H("severe_price_drop: cảnh báo khi giá rơi SÂU HƠN % này so với baseline. Trống = fallback Policy rồi mặc định 70%."),
    "rh_high": H("above_high: cảnh báo khi giá CAO hơn % này so với reference. Trống = fallback Policy."),
    "rec_lock_label": H("Đề xuất Stock Safety Lock (dry-run)"),
    "lock_hint": H("Chỉ áp dụng cho severe_price_drop / possible_missing_zero và chỉ THU HẸP — vẫn cần policy bật lock. below_min/above_high không bao giờ lock (cứng trong code)."),
    "eff_from": H("Hiệu lực từ"), "eff_to": H("Đến"),
    "check_overlap": H("Kiểm tra trùng/override"),
    "save_draft": H("Lưu (Draft)"),
}

PAGE3_JS = """
<script id="ec-alert-rules">
(function(){
"use strict";
var A=window.AL,$=A.$;
var S={scope:null,rows:[],current:null};
var RFIELDS=["rule_code","platform","shop","seller_sku","item","severity_override","threshold_percent","severe_drop_percent","high_alert_percent","effective_from","effective_to"];
function tierOf(o){if(o.seller_sku||o.item)return "SKU";if(o.shop)return "Shop";if(o.platform&&o.platform!=="All")return "Platform";return "Brand";}
// ===== Canonical scope-precedence resolver (frontend mirror of the backend
// services/rule_overlay._match_score + find_rules). The threshold for a rule_code
// is taken from the MOST SPECIFIC matching rule (SKU 8 > Shop 4 > Platform 2 >
// Brand 1), resolved INDEPENDENTLY per rule_code. No merging, no implicit
// "stricter value". "All platforms" = the platform=All (Brand Default) row.
var RULE_THRESHOLD_FIELD={below_min:"threshold_percent",severe_price_drop:"severe_drop_percent",above_high:"high_alert_percent"};
function ruleMatchScore(r,ctx){var s=1;
if(r.platform&&r.platform!=="All"){if(!ctx.platform||r.platform!==ctx.platform)return null;s+=2;}
if(r.shop){if(!ctx.shop||r.shop!==ctx.shop)return null;s+=4;}
if(r.seller_sku||r.item){var skuOk=r.seller_sku&&ctx.seller_sku&&r.seller_sku===ctx.seller_sku;var itemOk=r.item&&ctx.item&&r.item===ctx.item;if(!(skuOk||itemOk))return null;s+=8;}
return s;}
function resolveRule(rules,ctx,code){var best=null,bs=-1;(rules||[]).forEach(function(r){if(r.rule_code!==code)return;var sc=ruleMatchScore(r,ctx);if(sc===null)return;if(sc>bs){bs=sc;best=r;}});return best;}
function resolveThreshold(rules,ctx,code){var r=resolveRule(rules,ctx,code);if(!r)return null;var f=RULE_THRESHOLD_FIELD[code];var v=(f&&r[f]!=null&&r[f]!=="")?r[f]:(r.threshold_percent!=null&&r.threshold_percent!==""?r.threshold_percent:null);return v==null?null:parseFloat(v);}
// threshold value of ONE rule row, by its rule_code's canonical field.
function ruleThrVal(r){if(!r)return null;var f=RULE_THRESHOLD_FIELD[r.rule_code];var v=(f&&r[f]!=null&&r[f]!=="")?r[f]:(r.threshold_percent!=null&&r.threshold_percent!==""?r.threshold_percent:null);return v==null?null:v;}
// Deterministic precedence self-test (50/60/70 example for ALL three rule codes;
// throws if precedence ever merges or picks the wrong tier). Runs once at load.
function rulePrecedenceSelfTest(){
function ds(p){return {rule_code:"severe_price_drop",platform:p.pf,seller_sku:p.sku,severe_drop_percent:p.t};}
var SD=[ds({pf:"All",t:50}),ds({pf:"Shopee",t:60}),{rule_code:"severe_price_drop",seller_sku:"SKU1",severe_drop_percent:70}];
function eq(a,b,m){if(a!==b)throw new Error("precedence "+m+": "+a+"!="+b);}
eq(resolveThreshold(SD,{platform:"Lazada"},"severe_price_drop"),50,"brand");
eq(resolveThreshold(SD,{platform:"Shopee"},"severe_price_drop"),60,"platform");
eq(resolveThreshold(SD,{platform:"Shopee",seller_sku:"SKU1"},"severe_price_drop"),70,"sku");
if(!(55>=resolveThreshold(SD,{platform:"Lazada"},"severe_price_drop")))throw new Error("55 must alert generic");
if(55>=resolveThreshold(SD,{platform:"Shopee"},"severe_price_drop"))throw new Error("55 must NOT alert Shopee");
if(55>=resolveThreshold(SD,{platform:"Shopee",seller_sku:"SKU1"},"severe_price_drop"))throw new Error("55 must NOT alert SKU");
var BM=[{rule_code:"below_min",platform:"All",threshold_percent:50},{rule_code:"below_min",platform:"Shopee",threshold_percent:60},{rule_code:"below_min",seller_sku:"SKU1",threshold_percent:70}];
eq(resolveThreshold(BM,{platform:"Lazada"},"below_min"),50,"bm-brand");eq(resolveThreshold(BM,{platform:"Shopee"},"below_min"),60,"bm-platform");eq(resolveThreshold(BM,{platform:"Shopee",seller_sku:"SKU1"},"below_min"),70,"bm-sku");
var AH=[{rule_code:"above_high",platform:"All",high_alert_percent:50},{rule_code:"above_high",platform:"Shopee",high_alert_percent:60},{rule_code:"above_high",seller_sku:"SKU1",high_alert_percent:70}];
eq(resolveThreshold(AH,{platform:"Lazada"},"above_high"),50,"ah-brand");eq(resolveThreshold(AH,{platform:"Shopee"},"above_high"),60,"ah-platform");eq(resolveThreshold(AH,{platform:"Shopee",seller_sku:"SKU1"},"above_high"),70,"ah-sku");
return true;}
function tierBadge(t){var m={SKU:"al-b-critical",Shop:"al-b-pending",Platform:"al-b-dryrun",Brand:"al-b-info"};var L={SKU:"%(t_sku)s",Shop:"%(t_shop)s",Platform:"%(t_platform)s",Brand:"%(t_brand)s"};return '<span class="al-badge '+(m[t]||"al-b-info")+'" title="'+t+'">'+(L[t]||t)+'</span>';}
function ruBadge(v){return '<span class="al-badge '+({Draft:"al-b-draft",Active:"al-b-active",Paused:"al-b-paused"}[v]||"al-b-info")+'">'+A.esc(v)+'</span>';}
function filters(){var f={};[["f-brand","brand"],["f-rule_code","rule_code"],["f-status","status"]].forEach(function(p){var v=$(p[0]).value;if(v)f[p[1]]=v;});return f;}
function canActivate(){if(!S.scope)return false;if(S.scope.supervisor)return true;var b=$("r-brand")?$("r-brand").value:null;var role=b&&S.scope.brands?S.scope.brands[b]:null;return role==="manager"||role==="leader";}
function findRule(nm){for(var i=0;i<S.rows.length;i++){if(S.rows[i].name===nm)return S.rows[i];}return null;}
var BEHAVIORS=[["below_min","%(b_belowmin)s"],["severe_price_drop","%(b_severe)s"],["above_high","%(b_above)s"]];
function ruleAction(r){return r.recommend_stock_lock?"%(act_ss)s":"%(act_alert)s";}
function ruleThreshold(r){var t=(r.severe_drop_percent||r.high_alert_percent||r.threshold_percent);return (t!=null&&t!=="")?(A.esc(t)+"%%"):"-";}
// E2 business editor: per brand, each behaviour shows the "All platforms" Brand
// Default threshold + an optional "Customize by platform" panel (Shopee/Lazada/
// TikTok). A platform with its own rule is OVERRIDDEN (replaces the brand default
// for that rule type only); otherwise it INHERITS the brand default. "All
// platforms" is purely the UI name for the platform=All Brand Default row - no
// new rule code / scope type is introduced.
var RU_PLATFORMS=["Shopee","Lazada","TikTok"];
function thrTxt(r){var v=ruleThrVal(r);return (v!=null&&v!=="")?(A.esc(v)+"%%"):"-";}
function renderDefaults(rows){var brands={};
rows.forEach(function(r){var bb=(brands[r.brand]=brands[r.brand]||{});var cc=(bb[r.rule_code]=bb[r.rule_code]||{ov:{}});
if(!r.platform||r.platform==="All")cc.def=r;else cc.ov[r.platform]=r;});
var blist=Object.keys((S.scope&&S.scope.brands)||{});Object.keys(brands).forEach(function(b){if(blist.indexOf(b)<0)blist.push(b);});
var dd=$("ru-defaults");
if(!blist.length){dd.innerHTML='<div class="al-empty">%(no_rows)s</div>';return;}
dd.innerHTML=blist.sort().map(function(b){var m=brands[b]||{};
var beh=BEHAVIORS.map(function(bh){var code=bh[0];var c=m[code]||{ov:{}};var dr=c.def;var allV=ruleThrVal(dr);
var allCell=dr?('<b>'+thrTxt(dr)+'</b> '+ruBadge(dr.status)+' <button class="al-btn" data-edit="'+A.esc(dr.name)+'">%(edit_l)s</button>')
  :('<span class="al-badge al-b-ignored">%(notcfg)s</span> <button class="al-btn" data-new="'+A.esc(b)+'~'+code+'~All">%(configure_l)s</button>');
var nOv=0;var ovHtml=RU_PLATFORMS.map(function(pf){var orr=c.ov[pf];
if(orr){nOv++;return '<div class="ru-ovrow"><span class="ru-pf">'+pf+'</span><span class="al-badge al-b-dryrun" title="%(overridden_l)s">'+thrTxt(orr)+' &middot; %(overridden_l)s</span> <button class="al-btn" data-edit="'+A.esc(orr.name)+'">%(edit_l)s</button> <button class="al-btn" data-rm="'+A.esc(orr.name)+'">%(remove_l)s</button></div>';}
return '<div class="ru-ovrow"><span class="ru-pf">'+pf+'</span><span class="ru-inh" title="%(inherited_l)s">'+(allV!=null?("%(inherits_l)s "+A.esc(allV)+"%%"):"%(notcfg)s")+'</span> <button class="al-btn" data-new="'+A.esc(b)+'~'+code+'~'+pf+'">%(add_ov_l)s</button></div>';}).join("");
var custLabel="%(customize_l)s"+(nOv?(' <span class="al-chip-n">'+nOv+'</span>'):'');
return '<div class="ru-beh"><div class="ru-beh-row"><div class="ru-beh-h">'+bh[1]+'</div><div class="ru-beh-all"><span class="ru-pf ru-pf-all">%(all_platforms_l)s</span> '+allCell+'</div></div><details class="al-adv-sec ru-cust"'+(nOv?" open":"")+'><summary class="al-fsec" style="cursor:pointer;list-style:revert;margin:6px 0 4px">'+custLabel+'</summary>'+ovHtml+'</details></div>';}).join("");
return '<div class="ru-brand"><div class="ru-brand-h">'+A.esc(b)+'</div><div style="padding:8px 14px">'+beh+'</div></div>';}).join("");}
function renderExceptions(exc){var tb=$("ru-rows");
if(!exc.length){tb.innerHTML='<tr><td colspan="12" class="al-empty">%(no_exc)s</td></tr>';return;}
tb.innerHTML=exc.map(function(r){return '<tr data-rn="'+A.esc(r.name)+'">'+
'<td>'+A.ruleCell(r.rule_code)+'</td><td>'+tierBadge(tierOf(r))+'</td><td>'+A.esc(r.brand)+'</td><td>'+A.esc(r.platform||"All")+'</td><td>'+A.esc(r.shop||"-")+'</td><td>'+A.esc(r.seller_sku||r.item||"-")+'</td>'+
'<td>'+A.esc(r.severity_override||"-")+'</td><td>'+ruleThreshold(r)+'</td>'+
'<td>'+(r.recommend_stock_lock?'<span class="al-badge al-b-dryrun">%(act_ss)s</span>':"-")+'</td>'+
'<td>'+ruBadge(r.status)+'</td><td>'+A.esc(r.approved_by||"-")+'</td><td>'+A.esc((r.effective_from||"")+(r.effective_to?(" \\u2192 "+r.effective_to):""))+'</td></tr>';}).join("");}
function load(){$("ru-defaults").innerHTML='<div class="al-empty">%(loading)s</div>';$("ru-rows").innerHTML='<tr><td colspan="12" class="al-empty">%(loading)s</td></tr>';
A.call("api_rules.list_rules",{filters:filters()}).then(function(res){S.rows=res.rows;
// E2: Brand Default (All) + Platform overrides feed the brand-card editor; Shop /
// SKU exceptions remain in the Advanced Exceptions table.
var defs=[],exc=[];res.rows.forEach(function(r){var t=tierOf(r);if(t==="Brand"||t==="Platform")defs.push(r);else exc.push(r);});
renderDefaults(defs);renderExceptions(exc);}).catch(function(e){$("ru-defaults").innerHTML='<div class="al-empty">%(err)s'+A.esc(e.message)+'</div>';});}
function refreshTier(){var o={platform:$("r-platform").value,shop:$("r-shop").value,seller_sku:$("r-seller_sku").value,item:$("r-item").value};
$("ru-tier-line").innerHTML="%(tier_label)s: "+tierBadge(tierOf(o))+" &#183; SKU &gt; Shop &gt; Platform &gt; Brand";}
function refreshLockBox(){var rc=$("r-rule_code").value;var ok=(rc==="severe_price_drop"||rc==="possible_missing_zero");
$("r-recommend_lock").disabled=!ok;if(!ok)$("r-recommend_lock").checked=false;}
// EC Field Description adapter: override the static title/aria-label fallbacks
// with the live description when the doctype is present (loaded by initScope).
function applyFieldHelp(root){var els=(root||document).querySelectorAll("[data-help]");Array.prototype.forEach.call(els,function(el){var h=A.fieldHelp(el.getAttribute("data-help"));if(h&&h.help){el.title=h.help;el.setAttribute("aria-label",h.help);}});}
// E3 editor: a (brand, behaviour) unit = the All-platforms Brand Default rule +
// the Shopee/Lazada/TikTok override rules. The rule API (EDITABLE) only persists
// `threshold_percent`, so every behaviour writes that single field; the backend
// overlay maps it to the right behaviour by rule_code. The per-behaviour fields
// (severe_drop_percent/high_alert_percent) are doctype-only / read-fallback and
// are NOT in the rule API - writing them would need a backend change (out of
// scope). So the editor shows exactly ONE threshold input per behaviour.
var RU_OV_PF=["Shopee","Lazada","TikTok"];
var RULE_SAVE_THR_FIELD="threshold_percent"; // the only EDITABLE threshold field
function rulesFor(brand,code){return (S.rows||[]).filter(function(r){return r.brand===brand&&r.rule_code===code;});}
function brandDefaultRule(brand,code){var rs=rulesFor(brand,code);for(var i=0;i<rs.length;i++){if(!rs[i].platform||rs[i].platform==="All")return rs[i];}return null;}
function platformRule(brand,code,pf){var rs=rulesFor(brand,code);for(var i=0;i<rs.length;i++){if(rs[i].platform===pf&&!rs[i].shop&&!rs[i].seller_sku&&!rs[i].item)return rs[i];}return null;}
function isActiveRule(r){return !!r&&r.status!=="Paused";}
function curBehaviour(){return $("r-behaviour").value;}
function fillDrawer(){var brand=$("r-brand").value,code=curBehaviour();
var def=brandDefaultRule(brand,code);
$("r-thr-all").value=(isActiveRule(def)&&ruleThrVal(def)!=null)?ruleThrVal(def):"";
$("r-severity_override").value=(def&&def.severity_override)||"";
var allV=$("r-thr-all").value;
$("ru-cust-rows").innerHTML=RU_OV_PF.map(function(pf){var orr=platformRule(brand,code,pf);var hasOv=isActiveRule(orr)&&ruleThrVal(orr)!=null;
return '<div class="ru-ovrow"><span class="ru-pf">'+pf+'</span><input class="r-thr-pf" data-pf="'+pf+'" type="number" step="0.01" min="0" max="100" value="'+(hasOv?A.esc(ruleThrVal(orr)):"")+'" placeholder="'+(allV!==""?("%(inherits_l)s "+A.esc(allV)+"%%"):"%(inherits_l)s")+'">'+(hasOv?(' <button type="button" class="al-btn" data-clrpf="'+pf+'">%(remove_cust_l)s</button>'):"")+'</div>';}).join("")+'<div class="al-help">%(remove_cust_help)s</div>';
$("ru-status-line").innerHTML=def?("Status: "+ruBadge(def.status)):"";}
function openRule(brand,code){S.ruCode=code||"below_min";
var bsel=$("r-brand");bsel.innerHTML="";Object.keys((S.scope&&S.scope.brands)||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;bsel.appendChild(o);});
if(brand&&!Array.prototype.some.call(bsel.options,function(o){return o.value===brand;})){var ox=document.createElement("option");ox.value=brand;ox.textContent=brand;bsel.appendChild(ox);}
if(brand)bsel.value=brand;else if(bsel.options.length)bsel.value=bsel.options[0].value;
S.ruBrand=$("r-brand").value;$("r-behaviour").value=S.ruCode;$("ru-cust-sec").open=false;
fillDrawer();$("al-overlay").hidden=false;$("ru-drawer").hidden=false;}
function closeDrawer(){$("al-overlay").hidden=true;$("ru-drawer").hidden=true;}
function upsertRule(brand,code,platform,thrVal,existing){var data={brand:brand,rule_code:code,platform:platform};
data[RULE_SAVE_THR_FIELD]=thrVal;return A.call("api_rules.save_rule",{rule:data,name:existing?existing.name:null});}
function save(){var brand=$("r-brand").value,code=curBehaviour();if(!brand){A.toast("%(err)sBrand");return;}
var allV=$("r-thr-all").value;if(allV===""){A.toast("%(need_thr_l)s");return;}
var chain=upsertRule(brand,code,"All",allV,brandDefaultRule(brand,code));
Array.prototype.forEach.call(document.querySelectorAll("#ru-cust-rows .r-thr-pf"),function(inp){var pf=inp.getAttribute("data-pf"),v=inp.value;
chain=chain.then(function(){if(v==="")return null;return upsertRule(brand,code,pf,v,platformRule(brand,code,pf));});});
chain.then(function(){A.toast("%(saved)s");closeDrawer();load();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function clearOverride(pf){var orr=platformRule(S.ruBrand,S.ruCode,pf);if(!orr)return;
// "Bo tuy chinh": pause the override so it stops applying -> the All-platforms
// Brand Default value is used again (no delete API exists; not shown as "Pause").
A.call("api_rules.set_rule_status",{name:orr.name,status:"Paused"}).then(function(){A.toast("%(saved)s");
A.call("api_rules.list_rules",{filters:filters()}).then(function(res){S.rows=res.rows;fillDrawer();
var defs=[],exc=[];res.rows.forEach(function(r){var t=tierOf(r);if(t==="Brand"||t==="Platform")defs.push(r);else exc.push(r);});renderDefaults(defs);renderExceptions(exc);});}).catch(function(e){A.toast("%(err)s"+e.message);});}
function setStatus(st){if(!S.current)return;A.call("api_rules.set_rule_status",{name:S.current.name,status:st}).then(function(){A.toast("%(saved)s");load();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function init(){A.initScope("/alerts/rules",function(scope){S.scope=scope;
$("al-scope-line").textContent=scope.supervisor?"Supervisor scope: all brands":("Brands: "+Object.keys(scope.brands).join(", "));
var bsel=$("f-brand");Object.keys(scope.brands||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;bsel.appendChild(o);});
A.relabelRuleOptions($("f-rule_code"));
try{rulePrecedenceSelfTest();}catch(e){if(window.console)console.error("rule precedence self-test FAILED:",e&&e.message);}
load();applyFieldHelp($("ru-tier-legend"));});
$("ru-apply").onclick=load;
$("ru-rows").addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-rn]");if(tr){var r=findRule(tr.getAttribute("data-rn"));if(r)openRule(r.brand,r.rule_code);}});
$("ru-defaults").addEventListener("click",function(ev){
  var eb=ev.target.closest("[data-edit]");if(eb){var r=findRule(eb.getAttribute("data-edit"));if(r)openRule(r.brand,r.rule_code);return;}
  // E2: remove a platform override -> Paused so it stops applying and the brand
  // default (All Platforms) takes over. No delete API / no backend change.
  var rb=ev.target.closest("[data-rm]");if(rb){var rr=findRule(rb.getAttribute("data-rm"));if(rr){S.current=rr;setStatus("Paused");}return;}
  // E2: data-new = "brand~rule_code~platform"; open the behaviour editor.
  var nb=ev.target.closest("[data-new]");if(nb){var p=nb.getAttribute("data-new").split("~");openRule(p[0],p[1]);}});
$("ru-new").onclick=function(){openRule(null,"below_min");};
$("ru-d-close").onclick=closeDrawer;
$("ru-cancel").onclick=closeDrawer;
$("al-overlay").onclick=closeDrawer;
$("ru-save").onclick=save;
$("r-behaviour").onchange=fillDrawer;
$("r-brand").onchange=function(){S.ruBrand=$("r-brand").value;fillDrawer();};
$("ru-cust-rows").addEventListener("click",function(ev){var cb=ev.target.closest("[data-clrpf]");if(cb)clearOverride(cb.getAttribute("data-clrpf"));});}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init);}else{init();}
})();
</script>
""" % dict(VNJ,
    t_brand=js_escape("Brand Default"), t_platform=js_escape("Platform Override"),
    t_shop=js_escape("Shop Override"), t_sku=js_escape("SKU Exception"),
    b_belowmin=js_escape("Dưới giá tối thiểu"), b_severe=js_escape("Rớt giá mạnh"),
    b_above=js_escape("Vượt benchmark"),
    act_alert=js_escape("Alert Only"), act_ss=js_escape("Recommend Stock Safety"),
    edit_l=js_escape("Sửa"), configure_l=js_escape("Cấu hình"),
    notcfg=js_escape("Chưa cấu hình"), no_exc=js_escape("Không có exception nào."),
    all_platforms_l=js_escape("Tất cả platform"), customize_l=js_escape("Tùy chỉnh theo platform"),
    overridden_l=js_escape("override"), inherited_l=js_escape("kế thừa Brand Default"),
    inherits_l=js_escape("kế thừa"), add_ov_l=js_escape("Thêm override"),
    remove_l=js_escape("Gỡ override"),
    rule_title=js_escape("Cấu hình rule theo brand"), behaviour_l=js_escape("Hành vi"),
    threshold_l=js_escape("Ngưỡng"), save_l=js_escape("Lưu"),
    need_thr_l=js_escape("Nhập ngưỡng All platforms trước."),
    remove_cust_l=js_escape("Bỏ tùy chỉnh"),
    remove_cust_help=js_escape("Sẽ dùng lại giá trị All platforms"),
    behavior_l=js_escape("Hành vi"), action_l=js_escape("Hành động"),
    threshold=js_escape("Ngưỡng"),
    tier_label=js_escape("Tầng scope hiện tại"),
    approved_l=js_escape("duyệt bởi"),
    need_lead=js_escape("Activate/Pause cần Lead/System Manager"),
    no_overlap=js_escape("Không trùng rule Active nào."),
    overlap_found=js_escape("Rule Active liên quan:"),
    new_tier_l=js_escape("Rule mới ở tầng"),
    rel_overridden=js_escape("sẽ BỊ rule mới override (rule mới cụ thể hơn)"),
    rel_overrides=js_escape("sẽ OVERRIDE rule mới (rule kia cụ thể hơn)"),
    rel_same=js_escape("cùng tầng — rule sửa gần nhất thắng"))



# ========================= PAGE 4: /alerts/locks ============================
PAGE4_CONTENT = """
  <div class="ec-main">
    %(TOPBAR)s
    %(SUBNAV)s
    <div class="content">
      <div class="greeting"><h1>%(title)s</h1><p id="al-scope-line"></p></div>
      <div class="greeting" style="margin-top:-8px"><p style="margin:0">%(ss_copy)s</p></div>
      <div class="al-banner"><b>%(sim_mode)s</b> (DRY-RUN ONLY) &#8212; %(banner)s</div>
      <div class="stats-strip" id="ss-kpis">
        <div class="stat-card s-yellow kpi" data-ss="pending|Pending Review" role="button" tabindex="0"><div class="stat-label">%(c_pending)s</div><div class="stat-value" id="lk-c-pending">-</div><div class="stat-meta">Pending Review</div></div>
        <div class="stat-card s-green kpi" data-ss="history|Approved" role="button" tabindex="0"><div class="stat-label">%(c_approved)s</div><div class="stat-value" id="lk-c-approved">-</div><div class="stat-meta">dry-run approved</div></div>
        <div class="stat-card s-pink kpi" data-ss="history|Rejected" role="button" tabindex="0"><div class="stat-label">%(c_rejected)s</div><div class="stat-value" id="lk-c-rejected">-</div><div class="stat-meta">&#8594; Cancelled</div></div>
        <div class="stat-card s-navy kpi" data-ss="history|" role="button" tabindex="0"><div class="stat-label">Skipped</div><div class="stat-value" id="lk-c-skipped">-</div><div class="stat-meta">pause/credential</div></div>
      </div>
      <div class="al-modesw" id="ss-tabs" role="tablist" style="margin:0 0 12px">
        <button class="al-btn primary" id="ss-tab-pending" role="tab" aria-selected="true">%(tab_pending)s</button>
        <button class="al-btn" id="ss-tab-history" role="tab" aria-selected="false">%(tab_history)s</button>
        <button class="al-btn" id="ss-tab-pauses" role="tab" aria-selected="false">%(tab_pauses)s</button>
      </div>
      <div class="panel" id="ss-queue" style="margin-bottom:14px">
        <div class="panel-header"><div class="panel-title" id="ss-queue-title">%(queue_title)s</div><button class="al-btn" id="lk-refresh">%(refresh)s</button></div>
        <div class="al-filters">
          <div><label>Brand</label><select id="f-brand"><option value="">%(all)s</option></select></div>
          <div><label>Review</label><select id="f-review_status"><option value="">%(all)s</option><option>Pending Review</option><option>Approved</option><option>Rejected</option></select></div>
          <div><label>%(h_outcome)s</label><select id="f-status"><option value="">%(all)s</option><option value="Pending">%(ss_pending)s</option><option value="Dry Run">%(ss_sim)s</option><option value="Skipped">%(ss_skipped)s</option><option value="Cancelled">%(ss_cancelled)s</option></select></div>
          <div><label>SKU</label><input id="f-sku" type="text"></div>
          <button class="al-btn primary" id="lk-apply">%(apply)s</button>
        </div>
        <div class="al-tbl-wrap">
          <table class="al-tbl">
            <thead><tr><th>Action</th><th>Alert</th><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU</th><th>%(qty)s</th><th>Lock until</th><th>%(release)s</th><th>Review</th><th>%(reviewed)s</th><th>%(h_outcome)s</th></tr></thead>
            <tbody id="lk-rows"></tbody>
          </table>
        </div>
        <div class="al-pager"><span id="lk-count">-</span><span><button class="al-btn" id="lk-prev">&#8249;</button> <button class="al-btn" id="lk-next">&#8250;</button></span></div>
      </div>
      <div class="panel" id="ss-pauses" hidden>
        <div class="panel-header"><div class="panel-title">%(pause_title)s</div><button class="al-btn primary" id="pz-new">+ Pause</button></div>
        <div class="al-tbl-wrap">
          <table class="al-tbl">
            <thead><tr><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU</th><th>%(from)s</th><th>%(to)s</th><th>Status</th><th>%(by)s</th><th>%(reason)s</th><th></th></tr></thead>
            <tbody id="pz-rows"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="al-overlay" id="al-overlay" hidden></div>
<div class="al-drawer" id="lk-drawer" hidden>
  <div class="al-drawer-head"><strong id="lk-d-title"></strong><button class="al-btn" id="lk-d-close">&#10005;</button></div>
  <div class="al-drawer-body">
    <div class="al-banner" style="margin-bottom:10px">DRY-RUN &#8212; %(drawer_note)s</div>
    <div id="lk-d-kv"></div>
  </div>
  <div class="al-drawer-actions">
    <button class="al-btn primary" id="lk-approve">%(approve)s</button>
    <button class="al-btn danger" id="lk-reject">%(reject)s</button>
    <button class="al-btn" id="lk-open-alert">%(open_alert)s</button>
  </div>
</div>
<div class="al-modal" id="lk-approve-modal" hidden>
  <h3>%(approve)s &#8212; DRY-RUN</h3>
  <div class="al-banner" style="margin-bottom:10px">
    &#8226; %(ap_line1)s<br>
    &#8226; %(ap_line2)s<br>
    &#8226; %(ap_line3)s
  </div>
  <label>%(note_opt)s</label><textarea id="lk-ap-note" rows="3"></textarea>
  <div class="al-modal-foot"><button class="al-btn" id="lk-ap-cancel">%(cancel)s</button><button class="al-btn primary" id="lk-ap-ok">%(confirm_dry)s</button></div>
</div>
<div class="al-modal" id="lk-reject-modal" hidden>
  <h3>%(reject)s</h3>
  <label>%(note_req)s</label><textarea id="lk-rj-note" rows="3" placeholder="%(rj_ph)s"></textarea>
  <div class="al-modal-foot"><button class="al-btn" id="lk-rj-cancel">%(cancel)s</button><button class="al-btn danger" id="lk-rj-ok">%(confirm)s</button></div>
</div>
<div class="al-modal" id="pz-modal" hidden>
  <h3>%(pause_title)s</h3>
  <label>Brand</label><select id="z-brand"></select>
  <label>Platform</label><select id="z-platform"><option>All</option><option>Shopee</option><option>Lazada</option><option>TikTok</option></select>
  <label>Seller SKU (%(optional)s)</label><input id="z-sku" type="text">
  <label>%(from)s</label><input id="z-from" type="datetime-local">
  <label>%(to)s</label><input id="z-until" type="datetime-local">
  <label>%(reason)s</label><textarea id="z-reason" rows="2"></textarea>
  <div class="al-modal-foot"><button class="al-btn" id="pz-cancel">%(cancel)s</button><button class="al-btn primary" id="pz-ok">%(confirm)s</button></div>
</div>
<div class="al-toast" id="al-toast" hidden></div>
""" % {
    "TOPBAR": "%(TOPBAR)s", "SUBNAV": "%(SUBNAV)s",
    "title": H("Stock Safety Actions"),
    "sim_mode": H("Simulation Mode"),
    "ss_copy": H("Xem các đề xuất bảo vệ tồn kho. Không có cập nhật tồn thật nào được gửi khi Simulation Mode đang bật."),
    "banner": H("Toàn bộ action ở đây là MÔ PHỎNG. Không có lệnh khoá kho / cập nhật buffer nào được gửi sang Omisell. Real stock write đang bị khoá bởi DS1 gate."),
    "c_pending": H("Chờ duyệt"), "c_approved": H("Đã duyệt"),
    "c_rejected": H("Từ chối"),
    "queue_title": H("Hàng đợi review (dry-run)"), "refresh": H("Làm mới"),
    "tab_pending": H("Pending Actions"), "tab_history": H("Action History"),
    "tab_pauses": H("Automation Pauses"),
    "h_outcome": H("Kết quả mô phỏng"),
    "ss_pending": H("Chờ xử lý"), "ss_sim": H("Mô phỏng"),
    "ss_skipped": H("Bỏ qua"), "ss_cancelled": H("Đã huỷ"),
    "all": H("Tất cả"), "apply": H("Lọc"), "qty": H("SL đề xuất"),
    "release": H("Release"), "reviewed": H("Duyệt bởi / lúc"),
    "pause_title": H("Tạm dừng tự động (Automation Pause)"),
    "from": H("Từ"), "to": H("Đến"), "by": H("Bởi"), "reason": H("Lý do"),
    "drawer_note": H("review này KHÔNG gửi gì sang Omisell"),
    "approve": H("Duyệt (dry-run)"), "reject": H("Từ chối"),
    "open_alert": H("Mở alert"),
    "ap_line1": H("Thao tác này CHỈ duyệt kết quả DRY-RUN review."),
    "ap_line2": H("KHÔNG có cập nhật stock/buffer nào được gửi sang Omisell."),
    "ap_line3": H("Real stock write đang bị khoá bởi DS1 gate."),
    "note_opt": H("Ghi chú (tuỳ chọn)"), "note_req": H("Ghi chú (bắt buộc)"),
    "rj_ph": H("Vì sao từ chối đề xuất này..."),
    "cancel": H("Huỷ"), "confirm": H("Xác nhận"),
    "confirm_dry": H("Xác nhận duyệt DRY-RUN"),
    "optional": H("tuỳ chọn"),
}

PAGE4_JS = """
<script id="ec-alert-locks">
(function(){
"use strict";
var A=window.AL,$=A.$;
var S={start:0,pageLen:50,total:0,scope:null,rows:[],pauses:[],current:null};
var DS1="&#8212;(DS1)";
function ds1(v){return (v==null||v===""||v===0)?DS1:A.esc(A.money(v));}
// Truthful review labels: review_action performs NO Omisell write (DS1 gate
// closed), so an "Approved" record is approved FOR SIMULATION only - never a
// live inventory lock. Raw enum kept in the title tooltip.
var RV_LABEL={"Pending Review":"%(rv_pending)s","Approved":"%(rv_approved)s","Rejected":"%(rv_rejected)s"};
function rvBadge(v){return v?('<span class="al-badge '+({"Pending Review":"al-b-pending","Approved":"al-b-active","Rejected":"al-b-critical"}[v]||"al-b-info")+'" title="'+A.esc(v)+'">'+A.esc(RV_LABEL[v]||v)+'</span>'):"-";}
// Truthful outcome labels for the action's processing status. DS1 is closed and
// no executor is wired to this UI, so every state here is a SIMULATION. "Live"
// is reserved for a future real executor and only when backend proof exists
// (no such proof today) - current DS1-disabled records always read Simulation.
var SS_LABEL={"Dry Run":"%(ss_sim)s","Success":"%(ss_simdone)s","Pending":"%(ss_pending)s","Processing":"%(ss_processing)s","Skipped":"%(ss_skipped)s","Failed":"%(ss_failed)s","Cancelled":"%(ss_cancelled)s"};
function ssStatusBadge(r){var s=r.status;var cls={"Dry Run":"al-b-dryrun","Pending":"al-b-pending","Skipped":"al-b-skipped","Success":"al-b-resolved","Failed":"al-b-critical","Cancelled":"al-b-ignored","Processing":"al-b-pending"}[s]||"al-b-info";return '<span class="al-badge '+cls+'" title="'+A.esc(s||"-")+'">'+A.esc(SS_LABEL[s]||s||"-")+'</span>';}
function filters(){var f={};[["f-brand","brand"],["f-review_status","review_status"],["f-status","status"]].forEach(function(p){var v=$(p[0]).value;if(v)f[p[1]]=v;});
var sku=$("f-sku").value.trim();if(sku)f.seller_sku=sku;return f;}
function loadCounts(){[["Pending Review","lk-c-pending"],["Approved","lk-c-approved"],["Rejected","lk-c-rejected"]].forEach(function(p){
A.call("api_actions.list_actions",{filters:{review_status:p[0]},page_len:1}).then(function(r){$(p[1]).textContent=r.total;}).catch(function(){});});
A.call("api_actions.list_actions",{filters:{status:"Skipped"},page_len:1}).then(function(r){$("lk-c-skipped").textContent=r.total;}).catch(function(){});}
function load(){var tb=$("lk-rows");tb.innerHTML='<tr><td colspan="12" class="al-empty">%(loading)s</td></tr>';
A.call("api_actions.list_actions",{filters:filters(),start:S.start,page_len:S.pageLen}).then(function(res){S.rows=res.rows;S.total=res.total;
if(!res.rows.length){tb.innerHTML='<tr><td colspan="12" class="al-empty">%(no_rows)s</td></tr>';}
else{tb.innerHTML=res.rows.map(function(r,i){return '<tr data-i="'+i+'">'+
'<td>'+A.esc(r.name)+'</td><td>'+A.esc(r.alert||"-")+'</td><td>'+A.esc(r.brand)+'</td><td>'+A.esc(r.platform||"-")+'</td><td>'+A.esc(r.shop||"-")+'</td><td>'+A.esc(r.seller_sku||r.item||"-")+'</td>'+
'<td>'+ds1(r.locked_quantity)+'</td><td>'+A.esc(A.dt(r.lock_until))+'</td><td>'+A.esc(r.release_strategy||"-")+'</td>'+
'<td>'+rvBadge(r.review_status)+'</td><td>'+A.esc(r.reviewed_by?(r.reviewed_by+" "+A.dt(r.reviewed_at)):"-")+'</td><td>'+ssStatusBadge(r)+'</td></tr>';}).join("");}
var from=S.total?S.start+1:0;$("lk-count").textContent=from+"-"+Math.min(S.start+S.pageLen,S.total)+" / "+S.total;
$("lk-prev").disabled=S.start<=0;$("lk-next").disabled=S.start+S.pageLen>=S.total;}).catch(function(e){tb.innerHTML='<tr><td colspan="12" class="al-empty">%(err)s'+A.esc(e.message)+'</td></tr>';});}
function loadPauses(){A.call("api_pauses.list_pauses",{}).then(function(rows){S.pauses=rows;var tb=$("pz-rows");
if(!rows.length){tb.innerHTML='<tr><td colspan="10" class="al-empty">%(no_rows)s</td></tr>';return;}
tb.innerHTML=rows.map(function(z,i){return '<tr>'+
'<td>'+A.esc(z.brand)+'</td><td>'+A.esc(z.platform||"All")+'</td><td>'+A.esc(z.shop||"-")+'</td><td>'+A.esc(z.seller_sku||z.item||"-")+'</td>'+
'<td>'+A.esc(A.dt(z.pause_from))+'</td><td>'+A.esc(A.dt(z.pause_until))+'</td>'+
'<td><span class="al-badge '+({Active:"al-b-active",Expired:"al-b-expired",Cancelled:"al-b-ignored"}[z.status]||"al-b-info")+'">'+A.esc(z.status)+'</span></td>'+
'<td>'+A.esc(z.paused_by||"-")+'</td><td style="white-space:normal">'+A.esc(z.reason||"-")+'</td>'+
'<td>'+(z.status==="Active"?('<button class="al-btn" data-pz="'+i+'">%(cancel_pause)s</button>'):"")+'</td></tr>';}).join("");}).catch(function(){});}
function kvdl(rows){return '<dl class="al-kv">'+rows.map(function(p){return "<dt>"+p[0]+"</dt><dd>"+p[1]+"</dd>";}).join("")+'</dl>';}
function openDrawer(r){S.current=r;$("lk-d-title").textContent=r.name;
var trig=[["%(d_alert)s",A.esc(r.alert||"-")],["Brand",A.esc(r.brand)],["Platform",A.esc(r.platform||"-")],["Shop",A.esc(r.shop||"-")],["SKU",A.esc(r.seller_sku||r.item||"-")],["%(reason_l)s",A.esc(r.lock_reason||"-")]];
var reqa=[["%(qty_l)s",ds1(r.locked_quantity)],["Lock until",A.esc(A.dt(r.lock_until))],["Release strategy",A.esc(r.release_strategy||"-")],["Release required",r.release_required?"Yes":"-"]];
var rev=[["%(d_outcome)s",ssStatusBadge(r)],["Review",rvBadge(r.review_status)],["%(d_reviewed)s",A.esc(r.reviewed_by?(r.reviewed_by+" / "+A.dt(r.reviewed_at)):"-")],["%(d_note)s",A.esc(r.review_note||"-")]];
var tech=[["Actual stock before",ds1(r.actual_stock_before)],["Available before",ds1(r.available_stock_before)],["Buffer before",ds1(r.buffer_stock_before)],["Buffer after",ds1(r.buffer_stock_after)],["API response",A.esc(r.api_response||"-")]];
$("lk-d-kv").innerHTML='<div class="al-fsec">%(d_trigger)s</div>'+kvdl(trig)+'<div class="al-fsec">%(d_reqaction)s</div>'+kvdl(reqa)+'<div class="al-action-box">%(d_simstate)s</div><div class="al-fsec">%(d_review)s</div>'+kvdl(rev)+'<details class="al-tech"><summary class="al-fsec" style="cursor:pointer">%(d_tech)s</summary>'+kvdl(tech)+'</details>';
var can=(r.status==="Dry Run"||r.status==="Pending"||r.status==="Skipped");
$("lk-approve").disabled=!can;$("lk-reject").disabled=!can;
$("al-overlay").hidden=false;$("lk-drawer").hidden=false;}
function closeDrawer(){$("al-overlay").hidden=true;$("lk-drawer").hidden=true;}
function review(decision,note){A.call("api_actions.review_action",{name:S.current.name,decision:decision,note:note||null}).then(function(){A.toast("%(done)s");
$("lk-approve-modal").hidden=true;$("lk-reject-modal").hidden=true;closeDrawer();load();loadCounts();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function openPauseModal(){var br=$("z-brand");br.innerHTML="";
Object.keys((S.scope&&S.scope.brands)||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;br.appendChild(o);});
function fmt(d){function p(n){return (n<10?"0":"")+n;}return d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate())+"T"+p(d.getHours())+":"+p(d.getMinutes());}
var now=new Date();$("z-from").value=fmt(now);$("z-until").value=fmt(new Date(now.getTime()+2*3600*1000));$("z-sku").value="";$("z-reason").value="";
$("al-overlay").hidden=false;$("pz-modal").hidden=false;}
function createPause(){A.call("api_pauses.create_pause",{brand:$("z-brand").value,platform:$("z-platform").value,seller_sku:$("z-sku").value||null,pause_from:$("z-from").value.replace("T"," ")+":00",pause_until:$("z-until").value.replace("T"," ")+":00",reason:$("z-reason").value}).then(function(){
$("pz-modal").hidden=true;$("al-overlay").hidden=true;A.toast("%(pause_done)s");loadPauses();}).catch(function(e){A.toast("%(err)s"+e.message);});}
function setStockTab(tab){
["pending","history","pauses"].forEach(function(t){var b=$("ss-tab-"+t);if(b){b.classList.toggle("primary",t===tab);b.setAttribute("aria-selected",t===tab?"true":"false");}});
var q=$("ss-queue"),p=$("ss-pauses");
if(tab==="pauses"){if(q)q.hidden=true;if(p)p.hidden=false;loadPauses();window.location.hash="stock-pauses";return;}
if(p)p.hidden=true;if(q)q.hidden=false;
$("f-review_status").value=(tab==="history")?"":"Pending Review";
$("ss-queue-title").textContent=(tab==="history")?"%(hist_title)s":"%(queue_title)s";
S.start=0;load();loadCounts();
window.location.hash=(tab==="history")?"stock-history":"stock-pending";}
function restoreTab(){var h=window.location.hash;setStockTab(h==="#stock-pauses"?"pauses":(h==="#stock-history"?"history":"pending"));}
function init(){A.initScope("/alerts/locks",function(scope){S.scope=scope;
$("al-scope-line").textContent=scope.supervisor?"Supervisor scope: all brands":("Brands: "+Object.keys(scope.brands).join(", "));
var bsel=$("f-brand");Object.keys(scope.brands||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;bsel.appendChild(o);});
loadCounts();restoreTab();});
["pending","history","pauses"].forEach(function(t){var b=$("ss-tab-"+t);if(b)b.onclick=function(){setStockTab(t);};});
$("ss-tabs").addEventListener("keydown",function(ev){if(ev.key==="Enter"||ev.key===" "||ev.key==="Spacebar"){var b=ev.target.closest("[role=tab]");if(b){ev.preventDefault();b.click();}}});
$("ss-kpis").addEventListener("click",function(ev){var c=ev.target.closest(".stat-card[data-ss]");if(!c)return;var p=c.getAttribute("data-ss").split("|");if(p[0]==="history"){setStockTab("history");$("f-review_status").value=p[1]||"";S.start=0;load();}else setStockTab("pending");});
$("ss-kpis").addEventListener("keydown",function(ev){if(ev.key==="Enter"||ev.key===" "||ev.key==="Spacebar"){var c=ev.target.closest(".stat-card[data-ss]");if(c){ev.preventDefault();c.click();}}});
window.addEventListener("hashchange",restoreTab);
$("lk-apply").onclick=function(){S.start=0;load();};
$("lk-refresh").onclick=function(){load();loadCounts();loadPauses();};
$("lk-prev").onclick=function(){S.start=Math.max(0,S.start-S.pageLen);load();};
$("lk-next").onclick=function(){S.start+=S.pageLen;load();};
$("lk-rows").addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-i]");if(tr)openDrawer(S.rows[+tr.getAttribute("data-i")]);});
$("lk-d-close").onclick=closeDrawer;
$("al-overlay").onclick=function(){closeDrawer();$("lk-approve-modal").hidden=true;$("lk-reject-modal").hidden=true;$("pz-modal").hidden=true;};
$("lk-approve").onclick=function(){$("lk-ap-note").value="";$("lk-approve-modal").hidden=false;$("al-overlay").hidden=false;};
$("lk-reject").onclick=function(){$("lk-rj-note").value="";$("lk-reject-modal").hidden=false;$("al-overlay").hidden=false;};
$("lk-ap-ok").onclick=function(){review("Approve",$("lk-ap-note").value.trim());};
$("lk-ap-cancel").onclick=function(){$("lk-approve-modal").hidden=true;};
$("lk-rj-ok").onclick=function(){var n=$("lk-rj-note").value.trim();if(!n){A.toast("%(note_required)s");return;}review("Reject",n);};
$("lk-rj-cancel").onclick=function(){$("lk-reject-modal").hidden=true;};
$("lk-open-alert").onclick=function(){if(S.current&&S.current.alert)window.open("/alerts","_blank");};
$("pz-new").onclick=openPauseModal;
$("pz-ok").onclick=createPause;
$("pz-cancel").onclick=function(){$("pz-modal").hidden=true;$("al-overlay").hidden=true;};
$("pz-rows").addEventListener("click",function(ev){var b=ev.target.closest("button[data-pz]");if(!b)return;
var z=S.pauses[+b.getAttribute("data-pz")];
A.call("api_pauses.cancel_pause",{name:z.name}).then(function(){A.toast("%(done)s");loadPauses();}).catch(function(e){A.toast("%(err)s"+e.message);});});}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init);}else{init();}
})();
</script>
""" % dict(VNJ,
    cancel_pause=js_escape("Huỷ pause"),
    qty_l=js_escape("SL đề xuất khoá"),
    reason_l=js_escape("Lý do lock"),
    queue_title=js_escape("Hàng đợi review (dry-run)"),
    hist_title=js_escape("Lịch sử action"),
    d_alert=js_escape("Alert nguồn"), d_reviewed=js_escape("Duyệt bởi / lúc"),
    d_note=js_escape("Ghi chú duyệt"),
    d_trigger=js_escape("Trigger & bằng chứng"), d_reqaction=js_escape("Hành động đề xuất"),
    d_simstate=js_escape("Simulation Mode — không có cập nhật tồn nào gửi sang Omisell."),
    d_review=js_escape("Quyết định duyệt"), d_tech=js_escape("Chi tiết kỹ thuật"),
    d_outcome=js_escape("Kết quả mô phỏng"),
    rv_pending=js_escape("Chờ duyệt"), rv_approved=js_escape("Duyệt cho mô phỏng"),
    rv_rejected=js_escape("Từ chối"),
    ss_sim=js_escape("Mô phỏng"), ss_simdone=js_escape("Mô phỏng hoàn tất"),
    ss_pending=js_escape("Chờ xử lý"), ss_processing=js_escape("Đang xử lý"),
    ss_skipped=js_escape("Bỏ qua"), ss_failed=js_escape("Lỗi (mô phỏng)"),
    ss_cancelled=js_escape("Đã huỷ"))


# =================== PAGE 5: /alerts/integration-health (G1) =================
PAGE5_CONTENT = """
  <div class="ec-main">
    %(topbar)s
    %(subnav)s
    <div class="content">
      <div class="greeting"><h1>%(title)s</h1><p id="ih-scope-line"></p></div>
      <div class="al-note"><span class="al-note-ic">&#9432;</span><span>%(intro)s</span></div>
      <div class="stats-strip">
        <div class="stat-card s-green"><div class="stat-label">%(c_ready)s</div><div class="stat-value" id="ih-c-ready">-</div><div class="stat-meta">Ready / Scheduler Enabled</div></div>
        <div class="stat-card s-pink"><div class="stat-label">Blocked</div><div class="stat-value" id="ih-c-blocked">-</div><div class="stat-meta">%(m_blocked)s</div></div>
        <div class="stat-card s-yellow"><div class="stat-label">Warning</div><div class="stat-value" id="ih-c-warning">-</div><div class="stat-meta">%(m_warning)s</div></div>
        <div class="stat-card s-navy"><div class="stat-label">%(c_manual)s</div><div class="stat-value" id="ih-c-manual">-</div><div class="stat-meta">%(m_manual)s</div></div>
      </div>
      <div class="panel" id="ih-cap-panel" hidden style="margin-bottom:14px">
        <div class="panel-header"><div class="panel-title">%(cap_title)s</div></div>
        <div style="padding:12px 16px">
          <div class="al-cap"><span id="ih-cap-text">-</span><div class="al-cap-track"><div class="al-cap-fill" id="ih-cap-fill" style="width:0%%"></div></div><span id="ih-cap-pct">-</span></div>
          <div class="al-help" id="ih-cap-help"></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header"><div class="panel-title">%(tbl_title)s</div><button class="al-btn" id="ih-refresh">%(refresh)s</button></div>
        <div class="al-tbl-wrap"><table class="al-tbl">
          <thead><tr><th>Brand</th><th>%(status)s</th><th>%(next)s</th><th>KAM</th><th title="Brand Approver">%(h_setup)s</th><th title="Brand Integration Settings (BIS)">%(h_integration)s</th><th title="Credential">%(h_cred)s</th><th title="BIS enabled">%(h_enabled)s</th><th title="DS1 dry-run gate">%(h_stocksafety)s</th><th>%(lastsync)s</th><th>Breaker</th><th title="In scheduler allowlist">%(h_scheduler)s</th><th>%(lastrun)s</th><th>Alerts</th><th>Orders</th><th>Items</th><th>Cov%%</th></tr></thead>
          <tbody id="ih-rows"></tbody>
        </table></div>
      </div>
    </div>
  </div>
</div>
<div class="al-overlay" id="al-overlay" hidden></div>
<div class="al-drawer al-drawer-wide" id="ih-drawer" hidden>
  <div class="al-drawer-head"><strong id="ih-d-title">Brand</strong><button class="al-btn" id="ih-d-close">&#10005;</button></div>
  <div class="al-drawer-body" id="ih-d-body"></div>
</div>
<div class="al-toast" id="al-toast" hidden></div>
""" % {
    "topbar": "%(TOPBAR)s", "subnav": "%(SUBNAV)s",
    "title": H("Integration Health"),
    "intro": H("Trang chỉ ĐỌC: chẩn đoán mức sẵn sàng của brand. Không sửa site_config, không ghi Omisell/stock, DS1 vẫn khoá."),
    "c_ready": H("Sẵn sàng"), "c_manual": H("Chưa cấu hình"),
    "h_setup": H("Brand Setup"), "h_integration": H("Integration"),
    "h_cred": H("Credential"), "h_enabled": H("Pull Enabled"),
    "h_stocksafety": H("Stock Safety"), "h_scheduler": H("Scheduler"),
    "m_blocked": H("cần khắc phục"), "m_warning": H("cần chú ý"),
    "m_manual": H("preview rồi pull"),
    "cap_title": H("Dung lượng dữ liệu (Log + Item) vs ngưỡng review 2M"),
    "tbl_title": H("Mức sẵn sàng theo brand"), "refresh": H("Làm mới"),
    "status": H("Trạng thái"), "next": H("Việc kế tiếp"),
    "lastsync": H("Sync gần nhất"), "lastrun": H("Lần chạy"),
}

PAGE5_JS = """
<script id="ec-alert-health">
(function(){
"use strict";
var A=window.AL,$=A.$;
var S={sm:false,rows:[],th:{}};

function yn(v){return v?'<span class="al-st al-st-ready">yes</span>':'<span class="al-st al-st-blocked">no</span>';}
function cred(v){if(v==="Active")return '<span class="al-badge al-b-active">Active</span>';return '<span class="al-badge al-b-warning">'+A.esc(v||"-")+'</span>';}

function init(){
  A.initScope("/alerts/integration-health",function(scope){
    S.sm=!!scope.supervisor;
    $("ih-scope-line").textContent=S.sm?"%(sm_line)s":"%(kam_line)s";
    load();
  });
  $("ih-refresh").onclick=load;
  $("ih-d-close").onclick=close;
  $("al-overlay").onclick=close;
}

function load(){
  $("ih-rows").innerHTML='<tr><td colspan="17"><div class="al-empty">%(loading)s</div></td></tr>';
  A.call("api_brands.list_brand_readiness").then(render).catch(function(e){A.toast("%(err)s"+e.message);});
}

// Frontend readiness classification (truthful, from the existing payload):
// a brand with NO integration settings reads "Not Configured" rather than the
// backend's "Blocked" (which is meant for a configured-but-failing brand).
function ihStatus(r){if(!r.bis_exists&&(r.status==="Blocked"||!r.status))return "Not Configured";return r.status;}
function render(d){
  S.rows=d.brands||[]; S.th=d.thresholds||{};
  var c={ready:0,blocked:0,warning:0,manual:0};
  S.rows.forEach(function(r){var s=ihStatus(r);
    if(s==="Not Configured")c.manual++; else if(s==="Blocked")c.blocked++;
    else if(s==="Warning"||s==="Delayed"||s==="Manual Pull Required")c.warning++; else c.ready++;});
  $("ih-c-ready").textContent=c.ready;$("ih-c-blocked").textContent=c.blocked;
  $("ih-c-warning").textContent=c.warning;$("ih-c-manual").textContent=c.manual;
  if(d.capacity){var cap=d.capacity;$("ih-cap-panel").hidden=false;
    var pct=Math.min(100,Math.round(cap.log_plus_item/cap.archive_review_trigger*100));
    $("ih-cap-text").textContent="Log+Item: "+A.money(cap.log_plus_item)+" / "+A.money(cap.archive_review_trigger);
    $("ih-cap-pct").textContent=pct+"%%";
    var fill=$("ih-cap-fill");fill.style.width=pct+"%%";
    fill.className=cap.archive_review_due?"al-cap-fill warn":"al-cap-fill";
    $("ih-cap-help").textContent=cap.archive_review_due?"%(cap_due)s":"%(cap_ok)s";
  }
  var html=S.rows.map(function(r,i){
    var run=r.running?'<span class="al-run-dot" title="running"></span>':"";
    return '<tr data-i="'+i+'">'+
      '<td><strong>'+A.esc(r.brand)+'</strong></td>'+
      '<td>'+A.stHealth(ihStatus(r))+run+'</td>'+
      '<td>'+A.esc((r.action&&r.action.label)||"-")+'</td>'+
      '<td>'+A.esc(r.kam_owner||"-")+'</td>'+
      '<td>'+A.esc(r.ba_status||"-")+'</td>'+
      '<td>'+yn(r.bis_exists)+'</td>'+
      '<td>'+cred(r.credential_status)+'</td>'+
      '<td>'+yn(A.money(r.enabled)!=="-"&&Number(r.enabled)===1)+'</td>'+
      '<td>'+yn(Number(r.dry_run_stock_lock)===1)+'</td>'+
      '<td>'+A.dt(r.last_sync_at)+'</td>'+
      '<td>'+(r.consecutive_failures||0)+'</td>'+
      '<td>'+yn(r.in_allowlist)+'</td>'+
      '<td>'+A.esc(r.last_run_state||"-")+'</td>'+
      '<td>'+((r.counts&&r.counts.alerts_open)||0)+'</td>'+
      '<td>'+A.money((r.counts&&r.counts.order_log)||0)+'</td>'+
      '<td>'+A.money((r.counts&&r.counts.order_item)||0)+'</td>'+
      '<td>'+(r.counts&&r.counts.policies_active!=null?r.counts.policies_active:0)+'</td>'+
    '</tr>';
  }).join("");
  $("ih-rows").innerHTML=html||'<tr><td colspan="17"><div class="al-empty">%(no_rows)s</div></td></tr>';
  $("ih-rows").querySelectorAll("tr[data-i]").forEach(function(tr){
    tr.onclick=function(){openDrawer(S.rows[+tr.getAttribute("data-i")].brand);};});
}

function openDrawer(brand){
  $("ih-d-title").textContent=brand;
  $("ih-d-body").innerHTML='<div class="al-empty">%(loading)s</div>';
  $("ih-drawer").hidden=false;$("al-overlay").hidden=false;
  A.call("api_brands.brand_readiness",{brand:brand}).then(function(r){renderDrawer(brand,r);})
   .catch(function(e){$("ih-d-body").innerHTML='<div class="al-empty">'+A.esc(e.message)+'</div>';});
}

function blockerList(bl){
  if(!bl||!bl.length)return '<div class="al-help">%(no_blockers)s</div>';
  return '<ul class="al-blk">'+bl.map(function(b){
    return '<li class="'+(b.severity==="blocker"?"blocker":"warning")+'">'+A.esc(b.label)+'</li>';}).join("")+'</ul>';
}

function kv(label,val){return '<dt>'+A.esc(label)+'</dt><dd>'+A.esc(val==null||val===""?"-":val)+'</dd>';}

function renderDrawer(brand,r){
  var bis=r.bis||{}; var cov=r.coverage||{}; var cnt=r.counts||{}; var ba=r.brand_approver||{};
  var run=r.running?'<span class="al-run-dot"></span>':"";
  var parts=[];
  parts.push('<div style="margin-bottom:8px">'+A.stHealth(r.status)+run+'</div>');
  parts.push('<div class="al-action-box">&#8594; '+A.esc((r.action&&r.action.label)||"-")+'</div>');
  parts.push('<div class="al-fsec">%(s_blockers)s</div>'+blockerList(r.blockers));
  parts.push('<div class="al-fsec">%(s_scope)s</div><dl class="al-kv">'+
    kv("Brand Approver",ba.status)+kv("KAM owner",ba.kam_owner)+
    kv("Manager",ba.manager_email)+kv("Leader",ba.leader_email)+'</dl>');
  parts.push('<div class="al-fsec">%(s_integration)s</div><dl class="al-kv">'+
    kv("BIS",r.bis_exists?"yes":"no")+kv("enabled",bis.enabled)+
    kv("credential_status",bis.credential_status)+kv("dry_run_stock_lock",bis.dry_run_stock_lock)+
    kv("base_url",bis.base_url)+kv("last_sync_at",bis.last_sync_at)+
    kv("consecutive_failures",bis.consecutive_failures)+
    kv("scheduler allowlist",r.in_allowlist?"yes":"no")+kv("last run",r.last_run_state)+'</dl>');
  parts.push('<div class="al-fsec">%(s_data)s</div><dl class="al-kv">'+
    kv("Order Log",A.money(cnt.order_log||0))+kv("Order Item",A.money(cnt.order_item||0))+
    kv("Alerts (open)",cnt.alerts_open||0)+kv("Alerts (total)",cnt.alerts_total||0)+
    kv("Active policies",cnt.policies_active||0)+
    kv("Policy coverage",cov.pct==null?"n/a":(cov.pct+"%% ("+cov.covered+"/"+cov.distinct_skus+", "+cov.days+"d)"))+'</dl>');
  // links (everyone)
  parts.push('<div class="al-fsec">%(s_links)s</div><div class="al-drawer-actions" style="border:0;padding:0">'+
    '<a class="al-btn" href="/alerts/policies?brand='+encodeURIComponent(brand)+'">%(l_policies)s</a>'+
    '<a class="al-btn" href="/alerts#al-alert-list">%(l_alerts)s</a>'+
    (S.sm?'<a class="al-btn" href="/app/ec-brand-integration-settings/new?brand='+encodeURIComponent(brand)+'">%(l_bis)s</a>':'')+
    '</div>');
  // diagnostic actions (SM only, read-only)
  if(S.sm){
    parts.push('<div class="al-fsec">%(s_diag)s</div><div class="al-drawer-actions" style="border:0;padding:0">'+
      '<button class="al-btn" id="ih-prev"'+((r.bis_exists&&bis.base_url)?"":" disabled")+' title="'+((r.bis_exists&&bis.base_url)?"":"%(t_needbase)s")+'">%(b_preview)s</button>'+
      '<button class="al-btn" id="ih-pstat">%(b_status)s</button></div>'+
      '<div class="al-help" id="ih-diag-out"></div>');
    // gated (no auto-write) snippets
    parts.push('<div class="al-fsec">%(s_gated)s</div>'+
      '<div class="al-help">%(g_pull)s</div>'+
      '<div class="al-snippet">.\\\\onboard_lof_pull.ps1 -Brand '+A.esc(brand)+' -Confirm</div>'+
      '<div class="al-help">%(g_sched)s</div>'+
      '<div class="al-snippet">ec_alerts_scheduled_pull_brands: [..., "'+A.esc(brand)+'"]</div>');
  }
  $("ih-d-body").innerHTML=parts.join("");
  if(S.sm){
    var pv=$("ih-prev"); if(pv)pv.onclick=function(){runPreview(brand);};
    var ps=$("ih-pstat"); if(ps)ps.onclick=function(){runStatus(brand);};
  }
}

function runPreview(brand){
  $("ih-diag-out").textContent="%(running)s";
  A.call("api_omisell.pull_preview",{brand:brand,hours:1}).then(function(p){
    $("ih-diag-out").textContent="would_list = "+(p.would_list==null?"?":p.would_list)+" ["+(p.window?p.window.join(" -> "):"")+"]";
  }).catch(function(e){$("ih-diag-out").textContent="%(err)s"+e.message;});
}
function runStatus(brand){
  $("ih-diag-out").textContent="%(running)s";
  A.call("api_omisell.pull_status",{brand:brand}).then(function(s){
    var lr=s.last_run||{};
    $("ih-diag-out").textContent="state="+(lr.state||"none")+" running="+(s.running_since?"yes":"no")+
      " breaker="+(s.consecutive_failures||0)+" last_sync="+(s.last_sync_at||"-");
  }).catch(function(e){$("ih-diag-out").textContent="%(err)s"+e.message;});
}

function close(){$("ih-drawer").hidden=true;$("al-overlay").hidden=true;}

if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init);}else{init();}
})();
</script>
""" % dict(VNJ,
    sm_line=js_escape("System Manager - xem tất cả brand."),
    kam_line=js_escape("Hiển thị các brand trong phạm vi của bạn."),
    cap_due=js_escape("Đã chạm ngưỡng review 2M - lên kế hoạch archive (vẫn chỉ đo, chưa xoá)."),
    cap_ok=js_escape("Chỉ đo lường; chưa có code archive/xoá."),
    no_blockers=js_escape("Không có blocker."),
    s_blockers=js_escape("Blockers / cảnh báo"),
    s_scope=js_escape("Scope (Brand Approver)"),
    s_integration=js_escape("Tích hợp Omisell (BIS - không lộ key)"),
    s_data=js_escape("Dữ liệu & coverage"),
    s_links=js_escape("Liên kết"),
    s_diag=js_escape("Chẩn đoán (read-only, SM)"),
    s_gated=js_escape("Hành động cần thao tác thủ công (gated)"),
    l_policies=js_escape("Xem policies"),
    l_alerts=js_escape("Xem alerts"),
    l_bis=js_escape("Tạo/sửa BIS"),
    b_preview=js_escape("Chạy preview"),
    b_status=js_escape("Xem pull_status"),
    g_pull=js_escape("Manual pull chạy qua runbook (không trigger từ trang này):"),
    g_sched=js_escape("Thêm vào scheduler = sửa site_config trên FC dashboard (gated, G4 sẽ tự động):"),
    t_needbase=js_escape("Cần base_url trong BIS trước khi preview/pull"),
    running=js_escape("Đang chạy..."))


# ============================ assembly + asserts ============================
PAGES = [
    {"file": "alert_center.html", "marker": "ec-alert-center",
     "route": "/alerts", "crumb": "Dashboard",
     "content": PAGE1_CONTENT, "js": PAGE1_JS},
    {"file": "alert_policies.html", "marker": "ec-alert-policies",
     "route": "/alerts/policies", "crumb": "Policies",
     "content": PAGE2_CONTENT, "js": PAGE2_JS},
    {"file": "alert_rules.html", "marker": "ec-alert-rules",
     "route": "/alerts/rules", "crumb": "Rules",
     "content": PAGE3_CONTENT, "js": PAGE3_JS},
    {"file": "alert_locks.html", "marker": "ec-alert-locks",
     "route": "/alerts/locks", "crumb": "Locks",
     "content": PAGE4_CONTENT, "js": PAGE4_JS},
    {"file": "alert_health.html", "marker": "ec-alert-health",
     "route": "/alerts/integration-health", "crumb": "Integration Health",
     "content": PAGE5_CONTENT, "js": PAGE5_JS},
]

import os
for pg in PAGES:
    # .replace (not %) - page bodies may contain literal % after first format
    content = (pg["content"].replace("%(TOPBAR)s", topbar(pg["crumb"]))
                            .replace("%(SUBNAV)s", subnav(pg["route"])))
    page = "\n".join([
        "<!-- %s : built by build_alert_pages.py (Phase F) from the production" % pg["marker"],
        "     home shell snapshot. DO NOT hand-edit shell sections. -->",
        SHELL, NAV_ACTIVE, SHARED_CSS, '<div class="ecentric-app">',
        ac_aside(pg["route"]),
        content, SHARED_JS, pg["js"],
    ])
    bad = [c for c in page if ord(c) > 127]
    assert not bad, "%s non-ascii: %r" % (pg["file"], bad[:10])
    assert "{{" not in page and "{%" not in page, pg["file"] + " jinja leak"
    assert page.count("<style") == page.count("</style>"), pg["file"] + " style imbalance"
    assert page.count("<script") == page.count("</script>"), pg["file"] + " script imbalance"
    assert 'id="%s"' % pg["marker"] in page, pg["file"] + " marker missing"
    # AC-POLISH-2026-06-14: shared visual layer must ship in every page
    assert "AC-POLISH-2026-06-14" in page, pg["file"] + " polish layer missing"
    assert ".al-hdr-actions" in page, pg["file"] + " toolbar-group css missing"
    assert ".al-chip" in page, pg["file"] + " chip component css missing"
    out = os.path.join(OUTDIR, pg["file"])
    open(out, "w", newline="\n").write(page)
    print("[OK] built %s (%d bytes)" % (out, len(page)))

import html as _h
pol = open(os.path.join(OUTDIR, "alert_policies.html")).read()
for needle in ("al-drawer-wide", "al-fgrid", "al-fsec", "al-help", "al-lockbox", "al-req"):
    assert needle in pol, "policies drawer missing " + needle
polu = _h.unescape(pol)
for vn in ("Phạm vi áp dụng", "Chính sách giá",
           "Giá bán thấp nhất",
           "Reference / Benchmark price", "Listed price / RSP",
           "Tìm SKU từ Omisell",
           "Real stock write vẫn bị khoá bởi DS1",
           # RC3 2026: Alert Behavior thresholds removed from Price Setup (Rules
           # owns them); only scope + price facts + Advanced remain.
           "Cài đặt nâng cao",
           "Ưu tiên áp dụng: SKU > Shop > Platform > Brand"):
    assert vn in polu, "policies drawer missing helper/section: " + vn
# grouped drawer structure: live scope preview + collapsed Advanced + info icons
assert 'id="e-scope-preview"' in pol, "Price Setup live scope preview missing"
assert "al-adv-sec" in pol and "updateScopePreview" in pol, "Price Setup grouped sections / Advanced collapse missing"
assert 'data-help="price_setup.minimum_price"' in pol and "applyFieldHelp" in pol, "Price Setup info-icon (EC Field Description) help missing"
assert 'id="e-sku-search"' in pol and 'id="e-sku-search" disabled' not in pol, "G2.1: SKU search button must be ENABLED"
assert '<select id="e-brand">' in pol, "brand dropdown not in grid form"
# RC3 2026 (C1/C2/C3): ERP Item, the alert thresholds and the effective-period
# UI are removed from the Price Setup form. Backend fields are PRESERVED only as
# hidden inputs (values persist; Rules owns thresholds; policies stay active until
# paused/changed). No VISIBLE threshold / effective / ERP-Item control remains.
assert '<input id="e-item" type="hidden">' in pol, "C1: ERP Item must be hidden from Price Setup"
assert '<input id="e-high_alert_percent" type="hidden">' in pol, "C2: high_alert threshold must be hidden (Rules owns it)"
assert '<input id="e-severe_drop_percent" type="hidden">' in pol, "C2: severe_drop threshold must be hidden (Rules owns it)"
assert '<input id="e-effective_from" type="hidden">' in pol and '<input id="e-effective_to" type="hidden">' in pol, "C3: effective-period UI must be removed from Price Setup"
assert 'data-help="price_setup.high_alert_percent"' not in pol, "C2: visible high_alert threshold field must be gone"
assert 'data-help="price_setup.severe_drop_percent"' not in pol, "C2: visible severe_drop threshold field must be gone"
assert 'type="date"' not in pol, "C3: no date picker should remain in the Price Setup drawer"
print("[OK] M2c policy-drawer asserts pass (Price Setup simplified: no thresholds / effective / ERP Item)")

p1 = open(os.path.join(OUTDIR, "alert_center.html")).read()
assert "daysAgo(14)" in p1
for el in ("dash-topsku", "dash-aging",
           "al-rows", "al-subnav", "list_alerts", 'id="al-alert-list"',
           "applyHashNav", 'id="al-snapshot-note"',
           # G1.1 Drop 2: bulk + occurrence column + occurrences drawer
           'id="al-bulkbar"', 'id="al-chk-all"', "al-row-chk", "al-occ-n",
           'id="al-d-occ"', "api_alerts.bulk_set_status",
           "api_alerts.alert_occurrences", "renderOcc",
           # G1.1 Drop 2 polish: centered modal + CSV export
           "al-modal-xl", 'id="al-d-sub"', 'id="al-occ-export"',
           "exportOccCsv", "OCC_CSV_COLS",
           # UI/UX consolidation 2026-06-15: hourly panel REMOVED and consolidated
           # into one main trend card + Alert Distribution card + Operational/Setup
           # switch (the obsolete id="dash-hourly" assert is dropped; negative
           # assert below confirms its removal).
           'id="ov-trend"', 'id="al-modesw"', 'id="al-mode-setup"',
           "al-top-row",
           # ECharts 2026-06-15 (shared-asset architecture): the 4 pinned chart
           # assets load in order; the builder only renders containers + fallbacks,
           # fetches data and calls the shared AlertCharts (palettes/options/
           # lifecycle live in ECChartTheme / ECCharts / AlertCharts).
           "/assets/ecentric_workspace/charts/vendor/echarts.min.js",
           "/assets/ecentric_workspace/charts/chart_theme.js",
           "/assets/ecentric_workspace/charts/chart_common.js",
           "/assets/ecentric_workspace/charts/alert_charts.js",
           'id="ec-brand"', 'id="ec-platform"', 'id="ec-rule"', 'id="ec-trend"',
           'id="ec-brand-fb"', 'id="ec-platform-fb"', 'id="ec-rule-fb"',
           'id="ec-trend-fb"', "loadCharts", "loadTrend", "drawDonut", "drawTrend",
           "applyDimFilter", "AlertCharts.renderDistributionDonut",
           "AlertCharts.renderTrend", "ECCharts.attachResize", 'id="ov-trend-days"',
           # UX polish 2026-06-10: occ prominence + last_seen + dash for
           # no-price rules + exact SKU search + case pill
           "al-occ-n.multi", "occBadge", "NOPRICE", "pmoney(", "pgap(",
           "last_seen_at", "first_seen_at", "al-case-pill",
           # Pre-E2E 2026-06-14: Setup Issues KPI (replaces stale "Thieu policy"),
           # interactive KPI cards, simplified filters + advanced zone + chips.
           'id="al-kpis"', 'id="al-c-setup"', 'data-kpi="setup"',
           'data-kpi="open"', "applyKpi", "listFilters", "setup_only",
           'id="f-preset"', 'id="al-adv"', 'id="al-fchips"', "renderChips",
           "kpi-active",
           # UI/UX consolidation 2026-06-15: Overview/Alerts subview split +
           # Recent Critical + EC Field Description adapter.
           'id="ov-dash"', 'id="ov-recent"', 'id="ov-recent-rows"',
           'id="ov-viewall"', "loadRecent", "loadFieldHelp", "FIELD_HELP",
           # RC 2026-06-15: business-label terminology (raw rule_code dropdowns
           # relabelled to business labels at runtime; values stay raw codes).
           "RULE_LABELS", "ruleCell", "relabelRuleOptions"):
    assert el in p1, "page1 missing " + el
assert 'id="al-alert-list" hidden' in p1, "Alerts work-queue must be a hidden subview (not on Overview)"
# ECharts charts: a graceful fallback per chart, click-to-filter/drill-down
# callbacks wired by the builder, the shared single resize listener, and the
# trend truthfulness note must all be present.
assert p1.count("al-chart-fb") >= 4, "each chart needs a table/text fallback container"
assert "onClick:function(raw){applyDimFilter" in p1, "donut click-to-filter callback must be wired"
assert "onPointClick:function(day){" in p1, "trend click-to-day drill-down callback must be wired"
assert "ECCharts.attachResize()" in p1, "charts must use the shared single debounced resize listener"
assert "TRUTHFUL series only" in p1, "trend truthfulness note must remain in the builder"
# the builder must NOT hardcode palettes / generic lifecycle / option objects any
# more (they live in the shared assets) and the obsolete custom SVG must be gone.
for gone in ('id="ov-donut"', "donutArc", "al-dist3", "al-trend-day",
             'id="dash-trend"', "renderHourly", "DONUT_PAL", "function ecGet",
             "function ecResizeAll", 'radius:["54'):
    assert gone not in p1, "builder must not contain moved/obsolete chart code: " + gone
# the standalone hourly panel was consolidated into the main trend card.
assert 'id="dash-hourly"' not in p1, "obsolete standalone hourly panel must be removed"
assert 'class="panel al-hour-panel"' not in p1, "obsolete al-hour-panel must be removed"
# stale KPI label must be gone (missing_brand_mapping is NOT "missing policy")
assert "al-c-missing" not in p1, "stale al-c-missing KPI id must be removed"
assert 'placeholder="seller_sku"' not in p1, "old SKU placeholder must be replaced"
assert "snapshot t" in _h.unescape(p1), "snapshot disclaimer note missing on /alerts"
# ---- RC3 Pass 1 (Overview + Alert drawer) ----------------------------------
# A1: advanced filter no longer flush to a divider + collapses with no height.
assert '.al-adv[hidden]{display:none}' in p1, "A1: advanced filter must collapse to zero height"
# A2: SLA aging bars render relative to the max bucket with progressive colours
# and zero => no fill (the old 2px min-width floor is gone).
assert ".al-bar-fill.age0" in p1 and ".al-bar-fill.age3" in p1, "A2: progressive aging bar colours missing"
assert ".al-bar-fill{height:14px;border-radius:6px;background:var(--navy);transition:width .2s}" in p1, "A2: SLA bar fill must drop the min-width floor (zero = no fill)"
assert 'cls:"age0"' in p1 and 'cls:"age3"' in p1, "A2: aging buckets must pass progressive colour classes"
# A3: Recent Critical rows are interactive (click + keyboard) and open the drawer.
assert "al-rowlink" in p1 and "openRecent" in p1, "A3: recent rows must be clickable"
assert 'data-ri="' in p1 and 'role="button"' in p1, "A3: recent rows need role/index for keyboard"
# B1: the raw price_components_used string is NOT in the visible Evidence KV
# (it lives in Technical Details + CSV + tooltips only).
assert "dEvidence=" in p1 and "%(c_comp)s" not in p1.split("dEvidence=")[1].split("dScope=")[0] \
    if "dEvidence=" in p1 else True, "B1: raw price components must not show in the Evidence KV"
# B3: contextual lifecycle footer (Claim / Resolve / Ignore-in-More); the Resolve
# button now sends the VALID 'Closed' status (not the rejected 'Resolved'); Pause
# Automation + Source Order are gone from the alert drawer.
for el in ('id="al-d-claim"', 'id="al-d-resolve"', 'id="al-d-more"', 'id="al-d-ignore"',
           "refreshAlertFooter", 'setStatus("Closed")'):
    assert el in p1, "B3: alert lifecycle footer element missing " + el
for gone in ('id="al-d-pause"', 'id="al-d-source"', 'id="al-pause-modal"',
             "openPause", 'setStatus("Resolved")'):
    assert gone not in p1, "B3/F: must be removed from the alert drawer: " + gone
# B4: the evidence table shows the MARKETPLACE order id (external_order_id), and
# no Omisell/warehouse order id is surfaced as the primary value.
assert "external_order_id" in p1, "B4: marketplace order id (external_order_id) must be shown"
# E1: relabelRuleOptions pins the raw code onto o.value BEFORE relabelling the
# text, so a localized display label can never be submitted as the rule_code.
assert "o.value=raw;var l=ruleLabel(raw)" in p1, "E1: relabelRuleOptions must pin the canonical rule_code value"
# ---- RC3 Pass 2 (B2: selected evidence row -> calc panel) -------------------
for el in ('id="al-calc"', "al-occ-row", 'data-oi="', "function selectOcc", "function renderCalc",
           "renderCalc(rows[0])"):
    assert el in p1, "B2: selected-evidence element missing " + el
# the calc heading concatenates the SELECTED occurrence's marketplace order id,
# and the panel reads that row's own fields (not the alert-summary values).
assert "+A.esc(o.external_order_id" in p1, "B2: calc heading must include the marketplace order id"
assert "renderCalc(S.occ[i])" in p1, "B2: selecting a row must re-render the calc from that row"
assert "o.min_price_at_check" in p1 and "o.baseline_price_at_check" in p1, "B2: calc must use the occurrence row values"
print("[OK] M2/M2b dashboard asserts pass")

for el in ("pl-template", "pl-upload", "csv-preview", "csv-import", "csv-errbox",
           "csv-copy", "pl-rows", "api_policies.csv_template", "api_policies.preview_policy_csv",
           # G2.1: SKU catalog search/autofill + coverage panel
           'id="pl-sku-modal"', "api_sku_catalog.search_skus", "openSkuSearch",
           'id="pl-cov-modal"', "api_sku_catalog.policy_missing_skus",
           "exportCovTemplate",
           # Policy Conflict Guard: badge + fallback note
           "al-conf-badge", "api_policies.policy_conflicts", "loadConflicts",
           # Price Setup mini-phase 2026-06-14: relabel + thresholds back on the
           # form + paste-grid import workbench + per-brand missing summary +
           # backend permission caps + lifecycle feedback.
           "Price Setup", 'id="e-high_alert_percent"', 'id="e-severe_drop_percent"',
           'id="csv-paste"', 'id="imp-src-paste"', 'id="csv-summary"',
           'id="csv-result"', "actChip", "selectedLines", "refreshImportBtn",
           'id="pl-missing-rows"', "api_policies.missing_policy_summary",
           "api_policies.policy_caps", "applyCaps", "showLifecycle",
           "openCoverageFor", "ensureCovBrand",
           # AC-POLISH-2026-06-14: toolbar action group + brand coverage chips
           "al-hdr-actions", "al-chip-n",
           # RC 2026-06-15: compact coverage summary (Covered / Missing / Coverage %)
           # built from the canonical coverage_report; Missing card is clickable
           # to the existing missing-policy view; basis labelled + info tooltip.
           'id="pl-cov-kpis"', 'id="pl-cov-covered"', 'id="pl-cov-missing"',
           'id="pl-cov-pct"', 'data-cov="missing"', "loadCoverageSummary",
           "openMissingView", 'data-help="price_setup.coverage"',
           "api_sku_catalog.policy_missing_skus"):
    assert el in pol, "page2 missing " + el
# coverage basis must be truthfully labelled (distinct ordered SKUs, last 30 days)
polc = _h.unescape(pol)
assert ("30" in polc and ("đơn" in polc or "ordered" in polc.lower())), \
    "Price Setup coverage must label its 30-day ordered-SKU basis"
# the per-brand missing detail is kept but demoted to a drill-down (not dominant)
assert 'id="pl-cov-bybrand"' in pol, "per-brand missing detail must remain as a drill-down"
# RC polish 2026-06-15: contextual lifecycle footer + status badge near the title.
for el in ('id="pl-d-status"', 'id="pl-life"', 'id="pl-more"', 'id="pl-st-draft"',
           "refreshFooter", "curStatus", "set_policy_status", "function save()"):
    assert el in pol, "page2 missing contextual-footer element " + el
# the old simultaneous Active/Paused/Draft footer buttons are gone (max 2 lifecycle
# buttons; Draft moved under a More menu), and no arrow glyphs remain on them.
assert 'id="pl-st-active"' not in pol and 'id="pl-st-paused"' not in pol, \
    "Price Setup must not show simultaneous Active/Paused status buttons"
for arrow in ("&#8594; Active", "&#8594; Paused", "&#8594; Draft"):
    assert arrow not in pol, "lifecycle buttons must not carry arrow glyphs: " + arrow
print("[OK] M2d Price Setup contextual-footer asserts pass")

p3 = open(os.path.join(OUTDIR, "alert_rules.html")).read()
for el in ("ru-rows", "al-banner", "api_rules.set_rule_status", "api_rules.save_rule",
           'al-drawer-wide" id="ru-drawer"',
           'id="ru-defaults"', 'id="ru-exc-sec"', "renderDefaults",
           "renderExceptions", "BEHAVIORS", "ru-brand-h",
           'id="ru-tier-legend"', "applyFieldHelp", "relabelRuleOptions",
           'data-help="rules.brand_default"',
           'data-help="rules.platform_override"', 'data-help="rules.shop_override"',
           'data-help="rules.sku_exception"',
           # E3 simplified KAM editor: Brand + Behaviour + ONE All-platforms
           # threshold + optional per-platform overrides + Save/Cancel.
           'id="r-behaviour"', 'id="r-thr-all"', 'id="ru-cust-sec"',
           'id="ru-cust-rows"', 'id="ru-save"', 'id="ru-cancel"'):
    assert el in p3, "page3 missing " + el
# E3: the KAM editor exposes NO raw rule-code/scope selector, NO severity-override
# SELECT, only ONE behaviour threshold input (not three), no lifecycle buttons,
# no overlap/advanced tooling.
for gone in ('id="r-rule_code"', 'id="r-platform"', 'id="r-shop"', 'id="r-seller_sku"',
             'id="r-severe_drop_percent"', 'id="r-high_alert_percent"',
             'id="r-threshold_percent"', '<select id="r-severity_override">',
             'id="ru-overlap"', 'id="ru-adv-sec"', 'id="ru-st-active"'):
    assert gone not in p3, "E3: KAM rule editor must not expose: " + gone
# the four scope-tier tooltips remain (D); the behaviour->field map + the user-
# facing remove text ("Bỏ tùy chỉnh", helper) must be present, never "Pause rule".
assert p3.count('data-help="rules.') >= 4, "scope-tier tooltips must remain"
assert "RULE_SAVE_THR_FIELD" in p3 and "rule_code:code" in p3, "E3: canonical rule_code + threshold_percent must be submitted"
assert "DS1" in _h.unescape(p3)
p3u = _h.unescape(p3)
assert "B\\u1ecf t\\u00f9y ch\\u1ec9nh" in p3 and "S\\u1ebd d\\u00f9ng l\\u1ea1i" in p3, "E3: remove-override must use the business wording (Bo tuy chinh)"
assert 'data-clrpf="' in p3 and "clearOverride" in p3, "E3: remove-override control must be wired (pauses the override)"
assert "Pause rule" not in p3 and ">Pause<" not in p3, "E3: must NOT expose 'Pause rule' as the business action"
# D: each scope tier appears ONCE as a tooltipped label in the single priority
# line (the duplicate sentence + panel-header copy were removed).
for vn in ("Brand Defaults", "Advanced Exceptions",
           "SKU Exception", "Shop Override", "Platform Override", "Brand Default",
           "Rules định nghĩa khi nào sai lệch giá"):
    assert vn in p3u, "rules page missing copy: " + vn
assert "Brand Defaults &#183;" not in p3, "D: the duplicated panel-header priority label must be removed"
# E1: the behaviour <select> carries explicit canonical rule_code values so a
# localized label is never submitted as the rule_code (raw code stays internal).
assert '<select id="r-behaviour"><option value="below_min">' in p3, "E1: behaviour select must carry explicit canonical rule_code values"
# E4: the rule effective-period inputs are hidden (rules stay active until changed
# or paused); backend fields kept as hidden inputs.
assert '<input id="r-effective_from" type="hidden">' in p3, "E4: rule effective-period UI must be removed"
assert p3.count('type="date"') == 0, "E4: no date picker should remain in the rule drawer"
# ---- RC3 Pass 2 (E2/E3 + precedence) ---------------------------------------
# E2: brand-card behaviour editor = All Platforms (Brand Default) + per-platform
# overrides, with the canonical precedence resolver + deterministic self-test.
for el in ("ruleMatchScore", "resolveRule", "resolveThreshold", "ruleThrVal",
           "RULE_THRESHOLD_FIELD", "rulePrecedenceSelfTest", "RU_PLATFORMS",
           "function renderDefaults", 'data-rm="', 'data-new="', "ru-beh", "ru-ovrow"):
    assert el in p3, "E2/precedence element missing " + el
# the canonical behaviour->threshold-field map mirrors the backend exactly
assert '{below_min:"threshold_percent",severe_price_drop:"severe_drop_percent",above_high:"high_alert_percent"}' in p3, \
    "E2: behaviour->threshold field map must match the backend rule_overlay"
# the self-test is invoked at load (never crashes the page)
assert "rulePrecedenceSelfTest();" in p3, "precedence self-test must run on the Rules page"
# E3: severity override is hidden from the KAM-facing drawer.
assert '<input id="r-severity_override" type="hidden">' in p3, "E3: severity override must be hidden"
assert '<select id="r-severity_override">' not in p3, "E3: severity override select must be removed from the drawer"
print("[OK] M3 asserts pass")

p4 = open(os.path.join(OUTDIR, "alert_locks.html")).read()
for el in ("DRY-RUN ONLY", "lk-rows", "lk-approve-modal", "lk-reject-modal", "pz-rows",
           "pz-modal", "api_actions.review_action", "api_pauses.cancel_pause", "#8212;(DS1)",
           # UI/UX 2026-06-15: Stock Safety restructured into three internal tabs
           # (Pending Actions / Action History / Automation Pauses) with hash state,
           # a clickable KPI strip and a sectioned detail drawer.
           'id="ss-tabs"', 'id="ss-tab-pending"', 'id="ss-tab-history"',
           'id="ss-tab-pauses"', 'id="ss-queue"', 'id="ss-pauses"', 'id="ss-kpis"',
           "setStockTab", "restoreTab", "stock-pending", "stock-history", "stock-pauses",
           'data-ss=', 'role="tablist"', 'role="tab"',
           # sectioned drawer: grouped <dl> sections + collapsed Technical Details
           'id="lk-d-kv"', "al-fsec", "al-action-box", 'class="al-tech"', "kvdl("):
    assert el in p4, "page4 missing " + el
# Simulation Mode banner must be prominent and clearly NON-executing.
u4 = _h.unescape(p4)
assert "DS1" in u4 and "Omisell" in u4
assert "Simulation Mode" in u4, "Stock Safety must show a prominent Simulation Mode banner"
assert "Stock Safety Actions" in u4, "Stock Safety page title missing"
assert p4.count("al-fsec") >= 4, "stock drawer should group >=4 sections"
# Automation Pauses must live INSIDE this page, not as a standalone global nav item.
assert "stock-pauses" in p4 and 'href="/alerts/pauses"' not in p4, \
    "Automation Pauses must be an internal Stock Safety tab, not a global nav route"
# RC 2026-06-15 truthfulness: outcomes are labelled as SIMULATION (review_action
# performs no Omisell write; DS1 closed). The simulation-truthful label maps must
# be present, and the page must NOT label any record "Live" (no backend proof of
# a live write exists today).
for el in ("ssStatusBadge", "var RV_LABEL", "var SS_LABEL"):
    assert el in p4, "page4 missing truthful-label helper " + el
assert ">Live<" not in p4, "Stock Safety must not present a 'Live' status (no live write occurs)"
assert "ph\\u1ecfng" in p4, "Stock Safety outcome labels must read as simulation"
print("[OK] M4 asserts pass")

p5 = open(os.path.join(OUTDIR, "alert_health.html")).read()
for el in ("ih-rows", "ih-drawer", "ih-cap-panel", "ec-alert-health",
           "api_brands.list_brand_readiness", "api_brands.brand_readiness",
           "stHealth", "al-st-blocked",
           '/alerts/integration-health'):
    assert el in p5, "page5 missing " + el
# G1 must NOT auto-write the scheduler allowlist or auto-trigger a pull from the page
assert "set-config" not in p5, "page5 must not embed a site_config write"
assert "api_omisell.pull_recent" not in p5, "page5 must NOT trigger pull_recent (read+diagnose only)"
# read-only diagnostics that ARE allowed:
assert "api_omisell.pull_preview" in p5 and "api_omisell.pull_status" in p5
u5 = _h.unescape(p5)
assert "DS1" in u5
print("[OK] G1 integration-health asserts pass")

for fn in ("alert_center.html", "alert_policies.html", "alert_rules.html",
           "alert_locks.html", "alert_health.html"):
    pg2 = open(os.path.join(OUTDIR, fn)).read()
    assert "ec-sidebar" in pg2
    assert "Price Setup" in pg2           # relabelled nav (route alerts/policies unchanged)
    assert "Back to Workspace" in pg2
    assert "coming-soon?tool=" not in pg2, fn + " generic nav leak"
    assert ">Integration Health<" in pg2, fn + " missing Integration Health nav slot"
    # UI/UX consolidation 2026-06-15: renamed nav + terminology layer.
    assert ">Overview<" in pg2, fn + " missing Overview nav (renamed from Dashboard)"
    assert ">Stock Safety<" in pg2, fn + " missing Stock Safety nav (renamed from Locks)"
    # Automation Pauses must not be a standalone SIDEBAR nav anchor (it now lives
    # as an internal Stock Safety tab, which is a <button>, not an <a> nav link).
    assert "Automation Pauses</a>" not in pg2, fn + " Automation Pauses standalone nav must be removed"
    assert "RULE_LABELS" in pg2 and "ruleCell" in pg2, fn + " business-label terminology layer missing"
print("[OK] module-shell asserts pass")
print("[OK] UI/UX consolidation nav + terminology asserts pass")
