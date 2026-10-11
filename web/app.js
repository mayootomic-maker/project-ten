/* PROJECT TEN — accessible, dependency-free, read-only agent command center. */
'use strict';
let DATA=null, VIEW='overview', OPEN_AGENT=null;
const $=s=>document.querySelector(s);
const $$=s=>Array.from(document.querySelectorAll(s));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const amount=(x,d=2)=>Number.isFinite(+x)?`CHF ${Number(x).toFixed(d)}`:'—';
const pct=x=>Number.isFinite(+x)?`${x>=0?'+':''}${Number(x).toFixed(2)}%`:'—';
const signed=x=>Number.isFinite(+x)?`${x>=0?'+':''}${Number(x).toFixed(2)}`:'—';
const dataKind=()=>DATA?.meta?.mode?.startsWith('SYNTHETIC')?'SYNTHETIC DATA':'REAL PRICE DATA';
const date=t=>Number.isFinite(+t)?new Date(t*1000).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}):'—';
function logo(a){
 const s=a.sig; const k=s.sigil, p=s.stamp, num=s.number;
 const outside=['<circle cx="50" cy="50" r="35"/>','<rect x="18" y="18" width="64" height="64"/>','<path d="M50 12 L88 50 50 88 12 50Z"/>','<path d="M50 11 L87 30 87 70 50 89 13 70 13 30Z"/>'][num%4];
 const motifs=[
 '<path d="M50 16L50 84M16 50L84 50M25 25L75 75M75 25L25 75"/>',
 '<path d="M25 72L50 25 75 72M35 56H65"/>',
 '<circle cx="50" cy="50" r="23"/><circle cx="50" cy="50" r="8"/>',
 '<path d="M25 75L75 25M25 25L75 75M22 50H78"/>',
 '<path d="M20 40L50 20 80 40 50 80Z"/><path d="M50 20V80"/>',
 '<path d="M18 65L35 30 50 65 65 30 82 65"/>',
 '<path d="M25 25H75V75H25Z M36 36H64V64H36Z"/>',
 '<path d="M20 30H80L50 52 80 74H20L50 52Z"/>',
 '<path d="M21 50Q50 4 79 50 Q50 96 21 50Z"/><circle cx="50" cy="50" r="10"/>',
 '<path d="M50 17L80 80H20Z"/><path d="M50 17V80"/>',
 '<path d="M25 25L75 25 75 75M25 25V75H75"/><path d="M35 65L65 35"/>',
 '<path d="M20 50L40 30L60 70L80 50 M40 30L60 30 M40 70L60 70"/>'
 ];
 let points='';for(let i=0;i<4;i++){let xx=22+i*18,yy=(p*5+i*9)%13+80;points+=`<circle cx="${xx}" cy="${yy}" r="${i===p%4?2.3:1.15}" fill="currentColor" stroke="none"/>`;}
 return `<svg class="agent-avatar" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="Emblem of ${esc(s.name)}"><g fill="none" stroke="currentColor" stroke-width="${num%3+1.4}" stroke-linejoin="miter" stroke-linecap="square">${outside}${motifs[k]}<path d="M10 ${15+p*2} H${20+p*2} M80 ${82-p}H92" stroke-width="1"/></g>${points}<text x="50" y="96" font-size="5" font-family="monospace" text-anchor="middle" fill="currentColor">${esc(s.code)}</text></svg>`;
}
function lineChart(arr,wide=false){
 if(!arr?.length)return '<div class="empty">No forward simulation recorded yet.</div>';
 const vals=arr.map(Number), min0=Math.min(...vals),max0=Math.max(...vals),pad=Math.max((max0-min0)*.15,.7);
 const mn=min0-pad,mx=max0+pad,w=wide?920:430,h=wide?230:105;
 const xs=i=>30+i*(w-55)/Math.max(1,vals.length-1),ys=v=>13+(mx-v)*(h-34)/(mx-mn);
 const path=vals.map((v,i)=>`${i?'L':'M'}${xs(i).toFixed(2)} ${ys(v).toFixed(2)}`).join(' ');
 const grid=Array.from({length:4},(_,i)=>{const v=mn+(mx-mn)*i/3,y=ys(v);return `<line x1="30" y1="${y}" x2="${w-20}" y2="${y}" stroke="#33383c" stroke-dasharray="3 6" stroke-width=".8"/>${wide?`<text x="1" y="${y+3}" class="chart-label">${v.toFixed(0)}</text>`:''}`}).join('');
 const last=vals.at(-1),endpoint=`<circle cx="${xs(vals.length-1)}" cy="${ys(last)}" r="3.5" fill="#e8e8e4" stroke="#111" stroke-width="2"/>`;
 return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Virtual equity line chart" role="img">${grid}<path d="${path}" fill="none" stroke="#e7e6df" stroke-width="${wide?2:1.65}" vector-effect="non-scaling-stroke"/>${endpoint}</svg>`;
}
function card(a){let p=a.paper, status=a.qualified?'QUALIFIED':'RESEARCH',value=pct(p.net_pct);
 return `<button class="agent-card" data-agent="${esc(a.id)}" aria-label="Open ${esc(a.sig.name)} information"><div class="agent-card-top">${logo(a)}<span class="agent-code">${esc(a.sig.code)}</span></div><h3>${esc(a.sig.name)}</h3><div class="agent-sub">${esc(a.asset)} · ${esc(a.sig.family_label)}</div><div class="agent-card-foot"><div><div class="value">${value}</div><div class="hint" style="text-align:left;margin-top:5px">FORWARD NET</div></div><div class="hint">${esc(status)}<br>${p.trades} TRADES</div></div></button>`;
}
function activity(ev,limited=true){let arr=(ev||[]).slice().reverse();if(limited)arr=arr.slice(0,5);
 if(!arr.length)return '<div class="empty">No shared portfolio orders. Qualification may have selected cash as the best action.</div>';
 return arr.map(e=>`<div class="activity-item"><span class="event-badge">${esc(e.status?.toUpperCase())}</span><div><div class="evt-main"><b>${esc(e.asset)}</b> · ${esc(e.action?.toUpperCase())} · ${esc(e.agent)}</div><div class="evt-sub">${esc(e.reason|| (e.status==='filled'?`Size ${Number(e.qty).toPrecision(5)} · Fee USD ${Number(e.fee).toFixed(3)}`:'Unfilled'))}</div></div><span class="evt-time">${date(e.t)}</span></div>`).join('');
}
function renderOverview(){
 const d=DATA,s=d.shared;
 $('#heroAgents').textContent=d.stats.total;
 $('#mainBalance').textContent=amount(s.balance_chf);$('#mainReturn').textContent=pct(s.net_pct)+' NET SINCE FORWARD START';
 $('#agentCount').textContent=d.stats.total;$('#passing').textContent=d.stats.qualified;
 $('#executions').textContent=d.stats.total_agent_trades;$('#drawdown').textContent=s.max_dd_pct.toFixed(2)+'%';
 $('#mainChart').innerHTML=lineChart(s.curve,true);$('#endBalance').textContent='LATEST  '+amount(s.balance_chf);
 $('#featuredAgents').innerHTML=[...d.agents].sort((a,b)=>b.paper.net_pct-a.paper.net_pct).slice(0,4).map(card).join('');
 $('#pipeline').innerHTML=[['01','CANDIDATES',d.stats.total],['02','TRAIN PASSED',d.stats.passed_train],['03','QUALIFIED',d.stats.qualified],['04','SHARED ALLOCATIONS',d.stats.shortlist]].map(([n,label,val])=>`<div class="gate"><span class="gate-num">${val}</span><div class="gate-label">${n} / ${label}</div></div>`).join('');
 $('#activity').innerHTML=activity(d.event_log||[]);
 const initial=Number(d.meta.initial_chf||100),cash=Number(s.cash_chf),portion=Math.min(100,Math.max(0,100*cash/Math.max(1,s.balance_chf)));
 $('#donut').style.setProperty('--fill',portion);$('#cashPct').textContent=portion.toFixed(0)+'%';
 $('#cashLabel').textContent=amount(s.cash_chf);$('#investedLabel').textContent=amount(Math.max(0,s.balance_chf-s.cash_chf));
 $('#deployed').textContent=Object.keys(s.positions).length+' / '+d.stats.shortlist;
 $('#allocationFoot').textContent=d.stats.shortlist===0?'No agents passed every qualification gate. The shared portfolio correctly remains in cash.':'Only independently qualified agents may request shared capital. Exposure per asset is capped.';
}
function renderRoster(){
 let arr=[...DATA.agents];const search=$('#agentSearch').value.toLowerCase().trim(),fam=$('#familyFilter').value,asset=$('#assetFilter').value,sort=$('#sortSelect').value;
 arr=arr.filter(a=>(fam==='all'||a.family===fam)&&(asset==='all'||a.asset===asset)&&(!search||[a.sig.name,a.sig.code,a.asset,a.sig.family_label,a.family,a.id].join(' ').toLowerCase().includes(search)));
 if(sort==='net')arr.sort((a,b)=>b.paper.net_pct-a.paper.net_pct);
 else if(sort==='rank')arr.sort((a,b)=>a.sig.number-b.sig.number);
 else if(sort==='trades')arr.sort((a,b)=>b.paper.trades-a.paper.trades);
 else if(sort==='drawdown')arr.sort((a,b)=>a.paper.max_dd_pct-b.paper.max_dd_pct);
 $('#visibleCount').textContent=arr.length;$('#rosterCounts').textContent=`${arr.length} / ${DATA.agents.length} AGENTS`;
 $('#agentGrid').innerHTML=arr.length?arr.map(card).join(''):'<div class="empty">No matching agents. Try clearing the filters.</div>';
}
function renderLab(){
 const d=DATA,c=d.costs;
 $('#labNotice').textContent=`${dataKind()} / PAPER-ONLY / ${d.meta.forward_days} forward observation days. ${d.selection_note}`;
 const steps=[['01','Historical screening',`${d.stats.total} hypotheses compete against fee-aware buy-and-hold, with drawdown and trade-count gates.`],
 ['02','Training gate',`${d.stats.passed_train} passed. Trading costs are charged at every simulated fill.`],
 ['03','Unseen holdout',`Candidates must beat the benchmark on later data without parameter changes.`],
 ['04','Cost stress',`A candidate must still show positive return under doubled fees, spreads, slippage and injected execution failures.`],
 ['05','Shared simulation',`${d.stats.shortlist} different-asset strategy choices control one CHF 100 virtual portfolio, with a 25% freeze threshold.`]];
 $('#labGates').innerHTML=steps.map(([n,h,p])=>`<div class="lab-step"><span class="badge-number">${n}</span><div><strong>${esc(h)}</strong><p>${esc(p)}</p></div></div>`).join('');
 $('#costModel').innerHTML=[['Taker fee per side',(100*c.taker_fee).toFixed(2)+'%'],['Modeled bid-ask spread',(100*c.spread).toFixed(2)+'%'],['Additional slippage per side',(100*c.slippage).toFixed(2)+'%'],['Configured minimum order','USD '+Number(c.min_order_usd).toFixed(2)],['Maximum available capital',amount(100)],['Leverage','NONE'],['Real brokerage execution','DISABLED']].map(([name,val])=>`<div class="cost-line"><span>${esc(name)}</span><b>${esc(val)}</b></div>`).join('')+'<div class="cost-caption">Fees are a configurable venue model, not proof of a live executable quote. The spread and slippage are assumptions. Minimum lot sizes, funding, taxes and exchange-specific precision can differ. Real fills are never claimed.</div>';
 $('#candidateIncubator').innerHTML=(d.proposals||[]).map(p=>`<div class="incubator-item"><strong>${esc(p.id)}</strong><p>${esc(p.hypothesis)}</p><span class="pill">UNTESTED · RESEARCH ONLY</span></div>`).join('')||'<div class="empty">No candidates yet.</div>';
 $('#benchmarkTable').innerHTML='<table><thead><tr><th>ASSET</th><th>OBSERVED BARS</th><th>REGIME</th><th>TRAIN HOLD RETURN</th><th>HOLDOUT BUY & HOLD</th></tr></thead><tbody>'+Object.entries(d.benchmarks).map(([asset,b])=>`<tr><td>${asset}</td><td>${b.count}</td><td>${esc(b.regime)}</td><td>${pct(b.train_pct)}</td><td>${pct(b.holdout_pct)}</td></tr>`).join('')+'</tbody></table>';
}
function visibleJournal(){
 const term=$('#journalSearch').value.toLowerCase().trim(),book=$('#journalBook').value;
 return (DATA.event_log||[]).filter(e=>(book==='all'||e.book===book)&&(!term||[e.agent,e.asset,e.action,e.status,e.reason||''].join(' ').toLowerCase().includes(term))).slice().reverse();
}
function renderJournal(){
 const list=visibleJournal();
 $('#journalCount').textContent=`${list.length} VISIBLE / ${DATA.audit_events} AUDITED EVENTS`;
 $('#journalEntries').innerHTML=list.length?list.slice(0,150).map(e=>`<div class="journal-row"><span class="event-badge">${esc(e.action?.toUpperCase())}</span><div><strong>${esc(e.asset)} · ${esc(e.agent)}</strong><br><span>${esc(e.book==='individual'?'PERSONAL AGENT':'SHARED CAPITAL')} · ${esc(e.status)}${e.reason?' · '+esc(e.reason):''}</span></div><span class="hide-mobile">${e.status==='filled'? 'USD '+Number(e.gross).toFixed(2):'NO FILL'}</span><span class="right">${date(e.t)}</span></div>`).join('')+(list.length>150?`<div class="empty">Showing the latest 150 of ${list.length} matches. The CSV download includes all visible matches.</div>`:''):'<div class="empty">No recorded transactions match. Clear the filters or wait for the next evaluated day.</div>';
}
function detail(a){const p=a.paper,s=a.sig;
 let sigText=p.signal==='LONG'?`Current strategy preference: buy/hold ${a.asset}. This is not a verified profitable forecast.`:`Current strategy preference: remain in cash for ${a.asset}.`;
 const sections=[['RESEARCH — TRAINING',a.train],['RESEARCH — HOLDOUT',a.holdout],['RESEARCH — COST STRESS',a.stress]].map(([title,r])=>`<div class="cost-line"><span>${title}</span><b>${pct(r.net_pct)}</b></div>`).join('');
 $('#detailCode').textContent=s.code;$('#detailContent').innerHTML=`<div class="detail-hero"><div class="detail-headline">${logo(a)}<span class="pill">${a.qualified?'QUALIFIED':'UNQUALIFIED'}</span></div><h2 id="detailTitle">${esc(s.name)}</h2><p>${esc(s.thesis)}</p><div class="pill-row"><span class="pill">${esc(a.asset)}</span><span class="pill">${esc(s.family_label)}</span><span class="pill">${esc(p.signal)}</span></div></div>
 <div class="detail-section"><h3>PERSONAL VIRTUAL ACCOUNT</h3><div class="detail-number"><div class="mini-metric"><label>STARTING CAPITAL</label><strong>CHF 100</strong></div><div class="mini-metric"><label>CURRENT EQUITY</label><strong>${amount(p.balance_chf)}</strong></div><div class="mini-metric"><label>NET RETURN</label><strong>${pct(p.net_pct)}</strong></div><div class="mini-metric"><label>TRADING FEES</label><strong>${amount(p.fees_chf,3)}</strong></div></div><div class="smallcurve" style="margin-top:19px">${lineChart(p.curve)}</div></div>
 <div class="detail-section"><h3>WHAT THIS AGENT ACTUALLY DOES</h3><p class="explanation">${esc(sigText)}</p><div class="notice"><b>WHY RIGHT NOW</b><div style="padding-top:8px">${esc(p.decision_reason||'No evaluation available')}</div></div><p class="explanation">${esc(s.thesis)} The short lookback is <b>${a.params.n} days</b>; the second parameter is <b>${a.params.m}</b>. All signals use only completed previous-day prices. If no signal or no permitted executable order exists, it does nothing.</p><div class="cost-line"><span>Last decision</span><b>${esc(p.last_action)}</b></div><div class="cost-line"><span>Completed trades</span><b>${p.trades}</b></div><div class="cost-line"><span>Rejected orders</span><b>${p.rejects}</b></div><div class="cost-line"><span>Maximum drawdown</span><b>${p.max_dd_pct.toFixed(2)}%</b></div></div>
 <div class="detail-section"><h3>HISTORICAL SCREENING</h3>${sections}<p class="explanation">${esc(a.rejection_reason)}. These are historical research results, not future profits. <b>${a.evidence==='screened'?'Training difference survives exploratory multiple-comparison correction.':'No strong corrected statistical evidence was established.'}</b></p></div>
 <div class="detail-section"><h3>RECENT VIRTUAL EXECUTIONS</h3><div class="agent-trades">${p.events.length?p.events.slice().reverse().map(e=>`<div>${date(e.t)} · ${esc(e.action.toUpperCase())} ${esc(e.asset)} · ${esc(e.status)} ${e.fee?'· fee USD '+Number(e.fee).toFixed(3):''}</div>`).join(''):'<div>No orders. Agent is observing.</div>'}</div></div>`;
 $('#overlay').classList.remove('hidden');$('#detailClose').focus();document.body.style.overflow='hidden';
}
function closeDetail(){$('#overlay').classList.add('hidden');document.body.style.overflow='';OPEN_AGENT=null;}
function setView(view){VIEW=view;$$('.screen').forEach(el=>el.classList.toggle('hidden',el.id!==`screen-${view}`));$$('.rail-link').forEach(el=>el.classList.toggle('selected',el.dataset.view===view));if(view==='agents')renderRoster();if(view==='laboratory')renderLab();if(view==='journal')renderJournal();window.scrollTo({top:0,behavior:'instant'});}
function renderAll(){
 if(!DATA)return;const d=DATA;
 $('#lastDay').textContent=d.meta.last_day||'NOT STARTED';$('#footerDate').textContent=d.meta.last_day||'—';
 $('#modePill').textContent=d.meta.mode.startsWith('SYNTHETIC')?'SYNTHETIC DEMO':'VIRTUAL / REAL DATA';
 const synthetic=d.meta.mode.startsWith('SYNTHETIC');
 const hoursSinceQuote=d.meta.quote_at?(Date.now()/1000-Number(d.meta.quote_at))/3600:null;
 const staleWarning=!synthetic&&(hoursSinceQuote===null||hoursSinceQuote>8)
   ?` <b>DATA NOT CURRENT:</b> ${hoursSinceQuote===null?'No public quote recorded.':`Last quote ${Math.round(hoursSinceQuote)} hours ago.`} These figures must not be read as a live account balance.`:'';
 const missedWarning=!synthetic&&Number(d.meta.skipped_days)>0?` <b>MISSED EVALUATIONS:</b> ${Number(d.meta.skipped_days)} market day(s) skipped; no retrospective orders were recorded.`:'';
 $('#notice').innerHTML=synthetic?'<b>SIMULATED MARKET HISTORY, NOT REAL RESULTS.</b> Prices and fills on this dashboard are synthetic and exist to demonstrate the system. To switch to real Kraken market data, use the documented sync + init commands.':`<b>REAL HISTORICAL PRICES, SIMULATED EXECUTION.</b> Future-order fills are modeled, not confirmed. CHF/USD reference rate is frozen and returns exclude taxes and funding costs. ${esc(d.meta.fx_label)} <b>LAST OBSERVED QUOTE:</b> ${d.meta.quote_at ? esc(new Date(d.meta.quote_at*1000).toLocaleString()) : 'NOT RECEIVED'}. <b>FORWARD EVALUATIONS:</b> ${Number(d.meta.forward_days)||0}.${staleWarning}${missedWarning}`;
 renderOverview();renderRoster();renderLab();renderJournal();
}
document.addEventListener('click',e=>{const a=e.target.closest('[data-agent]');if(a&&DATA){const item=DATA.agents.find(x=>x.id===a.dataset.agent);if(item)detail(item);return;}const v=e.target.closest('[data-view]');if(v){setView(v.dataset.view);return;}const go=e.target.closest('[data-go]');if(go){setView(go.dataset.go);return;}});
$('#detailClose').addEventListener('click',closeDetail);$('#overlayScrim').addEventListener('click',closeDetail);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#overlay').classList.contains('hidden'))closeDetail();});
for(const sel of ['#journalSearch','#journalBook']){$(sel).addEventListener('input',()=>DATA&&renderJournal());}
for(const sel of ['#agentSearch','#familyFilter','#assetFilter','#sortSelect']){$(sel).addEventListener('input',()=>DATA&&renderRoster());}
$('#exportJournal').addEventListener('click',()=>{if(!DATA)return;const text=['day,agent,asset,side,status,qty,price,fee,reason',...visibleJournal().map(e=>[date(e.t),e.agent,e.asset,e.action,e.status,e.qty??'',e.price??'',e.fee??'',e.reason??''].join(','))].join('\n');const url=URL.createObjectURL(new Blob([text],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='project-ten-shared-events.csv';a.click();URL.revokeObjectURL(url);});
async function load(){try{let r=await fetch('./dashboard.json',{cache:'no-store'});if(!r.ok){r=await fetch('/api/state',{cache:'no-store'});}if(!r.ok)throw Error(`Dashboard data missing (HTTP ${r.status}). No verified report has been published yet.`);DATA=await r.json();if(!DATA.agents?.length)throw Error('No agents in report.');renderAll();}catch(e){$('#error').textContent=`Unable to load the agent command center. ${e.message}`;$('#error').classList.remove('hidden');}}
load();
// Only reload the public read-only report; this does not start or execute trades.
if(typeof __PROJECT_TEN__==='undefined')setInterval(()=>{if($('#overlay').classList.contains('hidden'))load();},90000);
