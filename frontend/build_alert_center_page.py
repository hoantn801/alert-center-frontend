#!/usr/bin/env python3
"""Build ALERT_CENTER/frontend/alert_center.html (Phase E).

Assembles the page from the REAL production shell (latest home snapshot:
csrf-fetch patch, navbar-hide style, master CSS, svg defs, .ec-sidebar
markup) + Alert Center content (al-* CSS/HTML/JS) defined below.
Output is 100% ASCII (entities / \\uXXXX) -> PS5-safe. Static page: all
Jinja is stripped from the sidebar copy; user card filled client-side.
Usage: python3 build_alert_center_page.py <home_snapshot_html> <out_html>
"""
import re
import sys

SNAPSHOT, OUT = sys.argv[1], sys.argv[2]


def demojibake(s):
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def to_entities(s):
    return "".join(c if ord(c) < 128 else "&#%d;" % ord(c) for c in s)


def js_escape(s):
    return "".join(c if ord(c) < 128 else "\\u%04x" % ord(c) for c in s)


src = open(SNAPSHOT, encoding="utf-8").read()


def block(start_pat, end_pat, from_pos=0):
    a = src.find(start_pat, from_pos)
    assert a >= 0, start_pat
    b = src.find(end_pat, a)
    assert b >= 0, end_pat
    return src[a:b + len(end_pat)]


csrf_patch = block('<script id="ec-csrf-fetch-patch">', "</script>")
a = src.find("function setActive")
nav_active = src[src.rfind("<script>", 0, a):src.find("</script>", a) + 9]
a = src.find("Hide Frappe default navbar")
hide_style = src[src.rfind("<style>", 0, a):src.find("</style>", a) + 8]
styles = [(m.start(), src.find("</style>", m.start()) + 8)
          for m in re.finditer(r"<style>", src)]
ma, mb = max(styles, key=lambda t: t[1] - t[0])
master_css = src[ma:mb]
svg_defs = block('<svg width="0" height="0"', "</svg>")
app_open = '<div class="ecentric-app">'
aside = block("<aside", "</aside>")

# De-Jinja the sidebar copy (this page is static - no server-side preamble).
aside = re.sub(r"\{% if approvals_count %\}.*?\{% endif %\}", "", aside, flags=re.S)
aside = aside.replace('href="/app/user/{{ user_email }}"', 'href="/me" id="al-user-card"')
aside = aside.replace("{{ initials }}", "").replace("{{ full_name }}", "")

shell = "\n".join(to_entities(demojibake(p))
                  for p in (csrf_patch, hide_style, master_css, svg_defs))
aside = to_entities(demojibake(aside))
nav_active = to_entities(demojibake(nav_active))

CUSTOM_CSS = """
<style id="ec-alert-center-css">
.al-filters{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px;border-bottom:1px solid var(--gray-200);align-items:flex-end}
.al-filters label{display:block;font-size:10.5px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px}
.al-filters select,.al-filters input{padding:7px 10px;border:1px solid var(--gray-200);border-radius:8px;font-size:13px;background:#fff;font-family:inherit;min-width:110px}
.al-filters select:focus,.al-filters input:focus{outline:none;border-color:var(--navy)}
.al-btn{padding:8px 14px;border-radius:8px;border:1px solid var(--gray-200);background:#fff;font-size:13px;font-weight:600;color:var(--gray-700);cursor:pointer;font-family:inherit}
.al-btn:hover{background:var(--gray-50)}
.al-btn.primary{background:var(--navy);border-color:var(--navy);color:#fff}
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
.al-pager{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;font-size:12.5px;color:var(--gray-500)}
.al-drawer{position:fixed;top:0;right:0;width:430px;max-width:94vw;height:100vh;background:#fff;border-left:1px solid var(--gray-200);box-shadow:-12px 0 36px rgba(15,23,42,.12);z-index:60;display:flex;flex-direction:column}
.al-drawer-head{padding:14px 18px;border-bottom:1px solid var(--gray-200);display:flex;justify-content:space-between;align-items:center}
.al-drawer-body{padding:14px 18px;overflow-y:auto;flex:1}
.al-kv{display:grid;grid-template-columns:130px 1fr;gap:6px 10px;font-size:13px;margin-bottom:14px}
.al-kv dt{color:var(--gray-500)}.al-kv dd{margin:0;color:var(--gray-900);font-weight:500;word-break:break-word;white-space:normal}
.al-drawer-actions{display:flex;flex-wrap:wrap;gap:8px;padding:12px 18px;border-top:1px solid var(--gray-200)}
.al-overlay{position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:55}
.al-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border-radius:14px;box-shadow:0 24px 64px rgba(15,23,42,.25);z-index:70;width:420px;max-width:92vw;padding:18px}
.al-modal h3{margin:0 0 10px;font-size:15px;color:var(--gray-900)}
.al-modal textarea,.al-modal input,.al-modal select{width:100%;padding:8px 10px;border:1px solid var(--gray-200);border-radius:8px;font-size:13px;font-family:inherit;margin-bottom:10px}
.al-modal-foot{display:flex;justify-content:flex-end;gap:8px}
.al-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--gray-900);color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;z-index:90;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.al-empty{padding:46px 16px;text-align:center;color:var(--gray-500);font-size:13.5px}
.al-noaccess{max-width:480px;margin:80px auto;text-align:center;color:var(--gray-600)}
.al-actrows{font-size:12.5px;border-top:1px dashed var(--gray-200);padding-top:10px;margin-top:6px}
[hidden]{display:none !important}
@media (max-width:760px){.al-drawer{width:100vw}.al-kv{grid-template-columns:110px 1fr}}
</style>
"""

VN = {
    "loading": "Đang tải...",
    "no_rows": "Không có alert nào khớp bộ lọc.",
    "note_required": "Cần nhập ghi chú khi Resolve/Ignore.",
    "done": "Đã cập nhật.",
    "pause_done": "Đã tạo automation pause.",
    "err": "Lỗi: ",
}

# NOTE: JS kept free of backticks and ${} (template-literal / Jinja safety).
CUSTOM_JS = """
<script id="ec-alert-center">
(function(){
"use strict";
var API="/api/method/ecentric_workspace.alerts.";
function call(m,args){return fetch(API+m,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json","Accept":"application/json"},body:JSON.stringify(args||{})}).then(function(r){return r.json().catch(function(){return {};}).then(function(j){if(!r.ok){var msg="HTTP "+r.status;try{if(j._server_messages){var arr=JSON.parse(j._server_messages);msg=arr.map(function(s){return JSON.parse(s).message;}).join("; ");}else if(j.exception){msg=j.exception.split(":").pop();}}catch(e){}var err=new Error(msg);err.status=r.status;throw err;}return j.message;});});}
var S={start:0,pageLen:50,total:0,scope:null,rows:[],current:null,noteAction:null};
var fmtN=new Intl.NumberFormat("vi-VN");
function $(id){return document.getElementById(id);}
function esc(s){var d=document.createElement("div");d.textContent=(s==null?"":String(s));return d.innerHTML;}
function money(v){return (v==null||v==="")?"-":fmtN.format(Math.round(v));}
function dt(v){if(!v)return "-";return String(v).slice(5,16);}
function toast(m){var t=$("al-toast");t.textContent=m;t.hidden=false;setTimeout(function(){t.hidden=true;},2600);}
function sevBadge(v){var c={Critical:"al-b-critical",Warning:"al-b-warning",Info:"al-b-info"}[v]||"al-b-info";return '<span class="al-badge '+c+'">'+esc(v)+'</span>';}
function stBadge(v){var c={"Open":"al-b-open","In Review":"al-b-review","Resolved":"al-b-resolved","Ignored":"al-b-ignored"}[v]||"al-b-info";return '<span class="al-badge '+c+'">'+esc(v)+'</span>';}
function actBadge(v){if(!v)return "-";var c={"Dry Run":"al-b-dryrun","Pending":"al-b-pending","Skipped":"al-b-skipped","Success":"al-b-resolved","Failed":"al-b-critical","Cancelled":"al-b-ignored","Processing":"al-b-pending"}[v]||"al-b-info";return '<span class="al-badge '+c+'">'+esc(v)+'</span>';}
function filters(){var f={};["status","severity","alert_type","rule_code","brand","platform"].forEach(function(k){var v=$("f-"+k).value;if(v)f[k]=v;});var o=$("f-owner").value.trim();if(o)f.owner_user=o;var a=$("f-from").value,b=$("f-to").value;if(a)f.from_date=a;if(b)f.to_date=b;return f;}
function loadCards(){call("api_alerts.get_cards").then(function(c){$("al-c-open").textContent=c.open;$("al-c-critical").textContent=c.critical;$("al-c-warning").textContent=c.warning;$("al-c-missing").textContent=c.missing_policy;$("al-c-lock").textContent=c.lock_pending;$("al-c-resolved").textContent=c.resolved_today;}).catch(function(){});}
function loadRows(){var tb=$("al-rows");tb.innerHTML='<tr><td colspan="15" class="al-empty">'+"%(loading)s"+'</td></tr>';call("api_alerts.list_alerts",{filters:filters(),start:S.start,page_len:S.pageLen}).then(function(res){S.rows=res.rows;S.total=res.total;
if(!res.rows.length){tb.innerHTML='<tr><td colspan="15" class="al-empty">'+"%(no_rows)s"+'</td></tr>';}
else{tb.innerHTML=res.rows.map(function(r,i){return '<tr data-i="'+i+'">'+
'<td>'+sevBadge(r.severity)+'</td><td>'+stBadge(r.status)+'</td><td>'+esc(r.rule_code)+'</td><td>'+esc(r.brand||"-")+'</td><td>'+esc(r.platform||"-")+'</td><td>'+esc(r.shop||"-")+'</td><td>'+esc(r.seller_sku||r.item||"-")+'</td>'+
'<td>'+money(r.actual_price)+'</td><td>'+money(r.min_price)+'</td><td>'+money(r.baseline_price)+'</td><td>'+(r.gap_percent!=null?esc(Math.round(r.gap_percent))+"%%":"-")+'</td>'+
'<td>'+esc(r.recommended_action||"-")+'</td><td>'+esc(r.owner_user||"-")+'</td><td>'+esc(dt(r.detected_at))+'</td><td>'+actBadge(r.action_status)+'</td></tr>';}).join("");}
var from=S.total?S.start+1:0;$("al-count").textContent=from+"-"+Math.min(S.start+S.pageLen,S.total)+" / "+S.total;$("al-prev").disabled=S.start<=0;$("al-next").disabled=S.start+S.pageLen>=S.total;}).catch(function(e){tb.innerHTML='<tr><td colspan="15" class="al-empty">'+"%(err)s"+esc(e.message)+'</td></tr>';});}
function reload(){loadCards();loadRows();}
function openDrawer(r){S.current=r;$("al-d-title").textContent=r.name;
var kv=[["Severity",sevBadge(r.severity)],["Status",stBadge(r.status)],["Rule",esc(r.rule_code)],["Title",esc(r.title)],["Brand",esc(r.brand||"-")],["Platform",esc(r.platform||"-")],["Shop",esc(r.shop||"-")],["SKU",esc(r.seller_sku||r.item||"-")],["Actual",money(r.actual_price)],["Min",money(r.min_price)],["Baseline",money(r.baseline_price)],["Gap",(r.gap_percent!=null?esc(Math.round(r.gap_percent))+"%%":"-")],["Recommended",esc(r.recommended_action||"-")],["Owner",esc(r.owner_user||"-")],["Detected",esc(dt(r.detected_at))],["Action",actBadge(r.action_status)]];
$("al-d-kv").innerHTML=kv.map(function(p){return "<dt>"+p[0]+"</dt><dd>"+p[1]+"</dd>";}).join("");
var srcb=$("al-d-source");if(r.reference_doctype==="EC Marketplace Order Log"&&r.reference_name){srcb.hidden=false;srcb.onclick=function(){window.open("/app/ec-marketplace-order-log/"+encodeURIComponent(r.reference_name),"_blank");};}else{srcb.hidden=true;}
$("al-d-acts").innerHTML="";call("api_actions.list_for_alert",{alert:r.name}).then(function(rows){if(!rows||!rows.length)return;$("al-d-acts").innerHTML='<div class="al-actrows"><b>Actions</b><br>'+rows.map(function(a2){return esc(a2.name)+" "+actBadge(a2.status)+" "+esc(a2.lock_reason||a2.error_message||"");}).join("<br>")+"</div>";}).catch(function(){});
$("al-overlay").hidden=false;$("al-drawer").hidden=false;}
function closeDrawer(){$("al-overlay").hidden=true;$("al-drawer").hidden=true;S.current=null;}
function setStatus(status){if(!S.current)return;
if(status==="In Review"){call("api_alerts.set_status",{alert:S.current.name,new_status:status}).then(function(){toast("%(done)s");closeDrawer();reload();}).catch(function(e){toast("%(err)s"+e.message);});return;}
S.noteAction=status;$("al-note-title").textContent=status;$("al-note-text").value="";$("al-note-modal").hidden=false;$("al-overlay").hidden=false;}
function confirmNote(){var note=$("al-note-text").value.trim();if(!note){toast("%(note_required)s");return;}
call("api_alerts.set_status",{alert:S.current.name,new_status:S.noteAction,note:note}).then(function(){$("al-note-modal").hidden=true;toast("%(done)s");closeDrawer();reload();}).catch(function(e){toast("%(err)s"+e.message);});}
function openPause(){if(!S.current)return;var br=$("p-brand");br.innerHTML="";
Object.keys((S.scope&&S.scope.brands)||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;br.appendChild(o);});
if(S.scope&&S.scope.supervisor&&S.current.brand){var o2=document.createElement("option");o2.value=S.current.brand;o2.textContent=S.current.brand;br.appendChild(o2);}
if(S.current.brand)br.value=S.current.brand;
$("p-platform").value=S.current.platform||"All";$("p-sku").value=S.current.seller_sku||"";
function fmt(d){function p(n){return (n<10?"0":"")+n;}return d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate())+"T"+p(d.getHours())+":"+p(d.getMinutes());}
var now=new Date();$("p-from").value=fmt(now);$("p-until").value=fmt(new Date(now.getTime()+2*3600*1000));$("p-reason").value="";
$("al-pause-modal").hidden=false;$("al-overlay").hidden=false;}
function confirmPause(){call("api_pauses.create_pause",{brand:$("p-brand").value,platform:$("p-platform").value,seller_sku:$("p-sku").value||null,pause_from:$("p-from").value.replace("T"," ")+":00",pause_until:$("p-until").value.replace("T"," ")+":00",reason:$("p-reason").value}).then(function(){$("al-pause-modal").hidden=true;toast("%(pause_done)s");closeDrawer();}).catch(function(e){toast("%(err)s"+e.message);});}
function noAccess(){document.querySelector(".content").innerHTML='<div class="al-noaccess"><h2>Alert Center</h2><p>T\\u00e0i kho\\u1ea3n c\\u1ee7a b\\u1ea1n ch\\u01b0a \\u0111\\u01b0\\u1ee3c g\\u00e1n brand n\\u00e0o trong Brand Approver (kam_owner / manager_email / leader_email). Li\\u00ean h\\u1ec7 System Manager \\u0111\\u1ec3 \\u0111\\u01b0\\u1ee3c c\\u1ea5p quy\\u1ec1n.</p></div>';}
function fillUser(){fetch("/api/method/frappe.auth.get_logged_user",{credentials:"include"}).then(function(r){return r.json();}).then(function(j){var u=j.message||"";if(u==="Guest"){window.location.href="/login?redirect-to=/alerts";return;}var card=$("al-user-card");if(card){var nm=card.querySelector(".user-name"),av=card.querySelector(".avatar");if(nm)nm.textContent=u.split("@")[0];if(av)av.textContent=(u[0]||"?").toUpperCase();}}).catch(function(){});}
function init(){fillUser();
call("api_alerts.my_scope").then(function(scope){S.scope=scope;
$("al-scope-line").textContent=scope.supervisor?"Supervisor scope: all brands":("Brands: "+Object.keys(scope.brands).join(", "));
var bsel=$("f-brand");Object.keys(scope.brands||{}).forEach(function(b){var o=document.createElement("option");o.value=b;o.textContent=b;bsel.appendChild(o);});
reload();}).catch(function(e){if(e.status===403){noAccess();}else{toast("%(err)s"+e.message);}});
$("al-apply").onclick=function(){S.start=0;loadRows();};
$("al-clear").onclick=function(){["f-status","f-severity","f-alert_type","f-rule_code","f-brand","f-platform"].forEach(function(id){$(id).value="";});$("f-owner").value="";$("f-from").value="";$("f-to").value="";S.start=0;reload();};
$("al-refresh").onclick=reload;
$("al-prev").onclick=function(){S.start=Math.max(0,S.start-S.pageLen);loadRows();};
$("al-next").onclick=function(){S.start+=S.pageLen;loadRows();};
$("al-rows").addEventListener("click",function(ev){var tr=ev.target.closest("tr[data-i]");if(tr)openDrawer(S.rows[+tr.getAttribute("data-i")]);});
$("al-d-close").onclick=closeDrawer;
$("al-overlay").onclick=function(){closeDrawer();$("al-note-modal").hidden=true;$("al-pause-modal").hidden=true;};
$("al-d-review").onclick=function(){setStatus("In Review");};
$("al-d-resolve").onclick=function(){setStatus("Resolved");};
$("al-d-ignore").onclick=function(){setStatus("Ignored");};
$("al-d-pause").onclick=openPause;
$("al-note-ok").onclick=confirmNote;$("al-note-cancel").onclick=function(){$("al-note-modal").hidden=true;};
$("al-pause-ok").onclick=confirmPause;$("al-pause-cancel").onclick=function(){$("al-pause-modal").hidden=true;};}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init);}else{init();}
})();
</script>
""" % {k: js_escape(v) for k, v in VN.items()}


def H(vn):
    return to_entities(vn)


CONTENT = """
  <div class="ec-main">
    <div class="topbar">
      <div class="breadcrumb">Workspace / <strong>Alert Center</strong></div>
      <div class="topbar-actions">
        <a href="/help" class="icon-btn"><svg class="icon icon-sm"><use href="#i-help"/></svg></a>
        <a href="/app/notification-log" class="icon-btn"><svg class="icon icon-sm"><use href="#i-bell"/></svg></a>
      </div>
    </div>
    <div class="content">
      <div class="greeting">
        <h1>Alert Center</h1>
        <p id="al-scope-line"></p>
      </div>
      <div class="stats-strip">
        <div class="stat-card s-navy"><div class="stat-label">%(c_open)s</div><div class="stat-value" id="al-c-open">-</div><div class="stat-meta">Open + In Review</div></div>
        <div class="stat-card s-pink"><div class="stat-label">Critical</div><div class="stat-value" id="al-c-critical">-</div><div class="stat-meta">%(m_open)s</div></div>
        <div class="stat-card s-yellow"><div class="stat-label">Warning</div><div class="stat-value" id="al-c-warning">-</div><div class="stat-meta">%(m_open)s</div></div>
        <div class="stat-card s-yellow"><div class="stat-label">%(c_missing)s</div><div class="stat-value" id="al-c-missing">-</div><div class="stat-meta">missing_policy / mapping</div></div>
        <div class="stat-card s-navy"><div class="stat-label">%(c_lock)s</div><div class="stat-value" id="al-c-lock">-</div><div class="stat-meta">Pending + Dry Run</div></div>
        <div class="stat-card s-green"><div class="stat-label">%(c_resolved)s</div><div class="stat-value" id="al-c-resolved">-</div><div class="stat-meta">%(m_today)s</div></div>
      </div>
      <div class="panel">
        <div class="panel-header"><div class="panel-title">Alerts</div><button class="al-btn" id="al-refresh">%(refresh)s</button></div>
        <div class="al-filters">
          <div><label>Status</label><select id="f-status"><option value="">%(all)s</option><option>Open</option><option>In Review</option><option>Resolved</option><option>Ignored</option></select></div>
          <div><label>Severity</label><select id="f-severity"><option value="">%(all)s</option><option>Critical</option><option>Warning</option><option>Info</option></select></div>
          <div><label>Type</label><select id="f-alert_type"><option value="">%(all)s</option><option>Price Compliance</option><option>Price Anomaly</option><option>Stock</option><option>SLA</option><option>Approval</option><option>Task</option></select></div>
          <div><label>Rule</label><select id="f-rule_code"><option value="">%(all)s</option><option>below_min</option><option>above_high</option><option>severe_price_drop</option><option>possible_missing_zero</option><option>missing_policy</option><option>missing_brand_mapping</option><option>missing_integration_credential</option><option>stock_lock_api_failed</option></select></div>
          <div><label>Brand</label><select id="f-brand"><option value="">%(all)s</option></select></div>
          <div><label>Platform</label><select id="f-platform"><option value="">%(all)s</option><option>Shopee</option><option>Lazada</option><option>TikTok</option><option>Other</option></select></div>
          <div><label>Owner</label><input id="f-owner" type="text" placeholder="user@email"></div>
          <div><label>%(from)s</label><input id="f-from" type="date"></div>
          <div><label>%(to)s</label><input id="f-to" type="date"></div>
          <button class="al-btn primary" id="al-apply">%(apply)s</button>
          <button class="al-btn" id="al-clear">%(clear)s</button>
        </div>
        <div class="al-tbl-wrap">
          <table class="al-tbl">
            <thead><tr><th>Severity</th><th>Status</th><th>Rule</th><th>Brand</th><th>Platform</th><th>Shop</th><th>SKU</th><th>%(actual)s</th><th>Min</th><th>Baseline</th><th>Gap</th><th>%(rec)s</th><th>Owner</th><th>%(detected)s</th><th>Action</th></tr></thead>
            <tbody id="al-rows"></tbody>
          </table>
        </div>
        <div class="al-pager"><span id="al-count">-</span><span><button class="al-btn" id="al-prev">&#8249;</button> <button class="al-btn" id="al-next">&#8250;</button></span></div>
      </div>
    </div>
  </div>
</div>

<div class="al-overlay" id="al-overlay" hidden></div>
<div class="al-drawer" id="al-drawer" hidden>
  <div class="al-drawer-head"><strong id="al-d-title"></strong><button class="al-btn" id="al-d-close">&#10005;</button></div>
  <div class="al-drawer-body"><dl class="al-kv" id="al-d-kv"></dl><div id="al-d-acts"></div></div>
  <div class="al-drawer-actions">
    <button class="al-btn" id="al-d-review">%(review)s</button>
    <button class="al-btn primary" id="al-d-resolve">Resolve</button>
    <button class="al-btn" id="al-d-ignore">Ignore</button>
    <button class="al-btn" id="al-d-pause">%(pause)s</button>
    <button class="al-btn" id="al-d-source" hidden>%(source)s</button>
  </div>
</div>
<div class="al-modal" id="al-note-modal" hidden>
  <h3><span id="al-note-title"></span> &#8212; %(note_label)s</h3>
  <textarea id="al-note-text" rows="4" placeholder="%(note_ph)s"></textarea>
  <div class="al-modal-foot"><button class="al-btn" id="al-note-cancel">%(cancel)s</button><button class="al-btn primary" id="al-note-ok">%(confirm)s</button></div>
</div>
<div class="al-modal" id="al-pause-modal" hidden>
  <h3>%(pause_title)s</h3>
  <label>Brand</label><select id="p-brand"></select>
  <label>Platform</label><select id="p-platform"><option>All</option><option>Shopee</option><option>Lazada</option><option>TikTok</option></select>
  <label>Seller SKU (%(optional)s)</label><input id="p-sku" type="text">
  <label>%(from)s</label><input id="p-from" type="datetime-local">
  <label>%(to)s</label><input id="p-until" type="datetime-local">
  <label>%(reason)s</label><textarea id="p-reason" rows="2"></textarea>
  <div class="al-modal-foot"><button class="al-btn" id="al-pause-cancel">%(cancel)s</button><button class="al-btn primary" id="al-pause-ok">%(confirm)s</button></div>
</div>
<div class="al-toast" id="al-toast" hidden></div>
""" % {
    "c_open": H("Đang mở"), "c_missing": H("Thiếu policy"),
    "c_lock": H("Lock chờ xử lý"), "c_resolved": H("Đã xử lý hôm nay"),
    "m_open": H("đang mở"), "m_today": H("hôm nay"),
    "refresh": H("Làm mới"), "all": H("Tất cả"), "from": H("Từ"),
    "to": H("Đến"), "apply": H("Lọc"), "clear": H("Xoá lọc"),
    "actual": H("Giá thực"), "rec": H("Đề xuất"), "detected": H("Phát hiện"),
    "review": H("Nhận xử lý"), "pause": H("Tạm dừng tự động"),
    "source": H("Đơn nguồn"), "note_label": H("ghi chú bắt buộc"),
    "note_ph": H("Lý do / cách xử lý..."), "cancel": H("Huỷ"),
    "confirm": H("Xác nhận"), "pause_title": H("Tạm dừng Stock Safety Lock"),
    "optional": H("tuỳ chọn"), "reason": H("Lý do"),
}

page = "\n".join([
    "<!-- ec-alert-center : Alert Center page (Phase E). Built by",
    "     build_alert_center_page.py from the production home shell snapshot.",
    "     DO NOT hand-edit shell sections - re-run the builder instead. -->",
    shell, nav_active, CUSTOM_CSS, app_open, aside, CONTENT, CUSTOM_JS,
])

bad = [c for c in page if ord(c) > 127]
assert not bad, "non-ascii leaked: %r" % bad[:20]
assert "{{" not in page and "{%" not in page, "Jinja tokens leaked"
assert page.count("<style") == page.count("</style>")
assert page.count("<script") == page.count("</script>")
with open(OUT, "w", newline="\n") as f:
    f.write(page)
print("[OK] built", OUT, len(page), "bytes, ASCII-only, no Jinja")
