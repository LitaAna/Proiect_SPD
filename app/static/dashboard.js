/* Evaluare reala prin serviciul laborator; fara valori simulate. */
(() => {
  const root = document.createElement('section');
  root.className = 'dashboard';
  root.innerHTML = `
  <nav class="dash-tabs" aria-label="Secțiuni laborator"><a href="#monitoring">Starea sistemului</a><a href="#benchmark">Teste de performanță</a><a href="#saved-tests">Rezultate și istoric</a></nav>
  <section id="monitoring" class="dash-block"><div class="dash-heading"><h2>Starea sistemului</h2><button id="refresh-status" class="button outline">Actualizează ↻</button></div><div id="services" class="service-grid" aria-live="polite">Se verifică serviciile…</div><div id="memory" class="memory-summary"></div><p id="status-time" class="status-time"></p><details><summary>Vezi cheile din memoria cache și expirarea lor</summary><p class="dash-note">Eșantion de maximum 50 de chei dintr-o pagină SCAN. TTL reprezintă secundele rămase; cheile expirate dispar. Dimensiunea valorii JSON diferă de memoria totală Redis.</p><div id="keys" class="key-list"></div></details></section>
  <section id="benchmark" class="dash-block"><div class="eyebrow">CERERI HTTP REALE / REZULTATE SALVATE</div><h2 style="margin-top:12px">Teste de performanță</h2><p class="dash-note">Compară timpul de răspuns și capacitatea aplicației. Testele rulează pe rând, într-un generator separat de instanțele măsurate. Pentru început: 2.000 de cereri, 10 clienți și cele patru configurații.</p>
  <form id="benchmark-form"><fieldset id="benchmark-fields" style="border:0;padding:0;margin:0"><div class="config-grid">
  <label>Cereri per rulare<input name="requests" type="number" min="100" max="20000" value="2000" required></label>
  <label>Clienți simultani<input name="concurrency" type="number" min="1" max="100" value="10" required></label>
  <label>Produse distincte (ID 1…N)<input name="products" type="number" min="1" max="10000" value="100" required></label>
  <label>Repetări per configurație<input name="repeats" type="number" min="1" max="5" value="1" required></label>
  <label>Configurație<select name="mode"><option value="all">Compară toate cele 4 configurații</option><option value="single-no-cache">O instanță · fără cache</option><option value="single-cache">O instanță · cu cache</option><option value="distributed-no-cache">Două instanțe · fără cache</option><option value="distributed-cache">Două instanțe · cu cache</option></select></label>
  <label>Starea inițială a cache-ului<select name="cache_state"><option value="cold">Gol la începutul fiecărei rulări</option><option value="warm">Preîncărcat înaintea măsurării</option></select></label>
  <label>TTL pentru intrările testului (secunde)<input name="ttl" type="number" min="1" max="600" value="60" required></label>
  </div><div class="dash-actions"><button class="button dark" type="submit" id="start-benchmark">Pornește experimentul ↗</button><button class="button outline" type="button" id="seed-benchmark">Pregătește datele</button></div></fieldset></form>
  <p class="dash-note">„Pregătește datele” adaugă produsele lipsă până la N, fără a modifica produsele existente. Fiecare rulare golește cache-ul comun de produse. Pentru rezultate comparabile, evită navigarea în catalog și alte teste simultane. TTL se aplică intrărilor create de test; catalogul folosește implicit 60 s. Preîncărcarea nu este cronometrată, dar intrările pot expira deja în timpul ei dacă TTL-ul este mic.</p>
  <div id="benchmark-progress" class="progress-panel" hidden><p id="benchmark-message" role="status"></p><progress id="benchmark-meter" value="0" max="100" aria-label="Progres experiment"></progress><button class="button outline" id="stop-benchmark">Oprește experimentul</button></div><p id="benchmark-error" class="dash-note dash-error" role="alert"></p></section>
  <section id="saved-tests" class="dash-block"><div class="dash-heading"><h2>Rezultate și istoric</h2><button class="button outline" id="refresh-history">Actualizează ↻</button></div><div class="history-select"><label for="experiment-select">Experiment salvat</label><select id="experiment-select"><option value="">Niciun experiment încă</option></select></div><p id="result-description" class="dash-note">Pornește un experiment pentru a vedea rezultatele aici.</p><div id="result-content"></div><div class="export-buttons" id="exports" hidden><button class="button outline" id="export-json">Descarcă JSON ↓</button><button class="button outline" id="export-csv">Descarcă CSV ↓</button></div><p class="dash-note">Rezultatele sunt păstrate în MongoDB, inclusiv după reîncărcarea paginii. Sunt afișate ultimele 50 de experimente. Datele JSON din testele vechi din terminal rămân în folderul results și nu sunt importate automat.</p></section>`;
  document.querySelector('.project-intro').after(root);
  const q = selector => root.querySelector(selector);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (value, digits=2) => value == null ? '—' : Number(value).toLocaleString('ro-RO', {maximumFractionDigits:digits});
  const names = {'single-no-cache':'1 API · fără cache','single-cache':'1 API · cu cache','distributed-no-cache':'2 API · fără cache','distributed-cache':'2 API · cu cache'};
  const statuses = {queued:'În așteptare',running:'În curs',completed:'Finalizat',failed:'Eșuat',cancelled:'Oprit',interrupted:'Întrerupt la repornire'};
  let selected = null, active = null, history = [], polling = false;
  async function api(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let message = `Serviciul nu a răspuns corect (${response.status}).`;
      try { const body = await response.json(); if (typeof body.detail === 'string') message = body.detail; } catch {}
      throw Error(message);
    }
    return response.json();
  }
  async function refreshStatus() {
    q('#refresh-status').disabled = true;
    try {
      const state = await api('/lab/status');
      q('#services').innerHTML = ['Nginx','API 1','API 2','Redis','MongoDB'].map(name => {const service=state.services[name] || {}; return `<div class="service ${service.online ? '' : 'offline'}"><strong>${name}</strong><span>${service.online?'● Disponibil':'● Indisponibil'}</span><small>${escape(service.instance || (service.products != null ? fmt(service.products,0)+' produse' : ''))}</small></div>`;}).join('');
      const r = state.redis;
      q('#memory').innerHTML = r ? `<span>Memorie Redis <b>${fmt(r.used_memory/1048576)} MB</b></span><span>Limită <b>${fmt(r.maxmemory/1048576)} MB</b></span><span>Chei în baza Redis <b>${fmt(r.keys_total,0)}</b></span><span>Politică <b>${escape(r.policy)}</b></span>` : 'Redis indisponibil; memoria nu poate fi citită.';
      q('#keys').innerHTML = state.keys.length ? `<table><thead><tr><th>Cheie</th><th>TTL rămas</th><th>Valoare JSON</th></tr></thead><tbody>${state.keys.map(k=>`<tr><td><code>${escape(k.key)}</code></td><td>${k.ttl===-1?'Fără expirare':k.ttl+' s'}</td><td>${fmt(k.bytes,0)} B</td></tr>`).join('')}</tbody></table>${state.keys_truncated?'<p class="dash-note">Eșantion parțial; există și alte chei.</p>':''}` : '<p class="dash-note">Nicio cheie de produs în eșantion. Solicită un produs sau rulează un test cu cache.</p>';
      q('#status-time').textContent = 'Ultima verificare: '+new Date(state.updated_at).toLocaleString('ro-RO')+'. Actualizarea este manuală pentru a nu adăuga trafic în timpul testelor.';
    } catch(error) { q('#status-time').textContent=error.message; }
    finally { q('#refresh-status').disabled=false; }
  }
  const settings = () => {const values=Object.fromEntries(new FormData(q('#benchmark-form'))); for(const key of ['requests','concurrency','products','repeats','ttl']) values[key]=Number(values[key]); return values;};
  function setActive(job) {
    active = job && ['running','queued'].includes(job.status) ? job : null;
    q('#benchmark-fields').disabled = !!active;
    q('#benchmark-progress').hidden = !job;
    q('#stop-benchmark').hidden = !active;
    if (!job) return;
    const total=job.total_runs || (job.configuration.mode==='all'?4:1)*job.configuration.repeats;
    const progress = Math.min(100,((job.completed_runs||0)+(job.phase==='measuring'?(job.current_requests||0)/job.configuration.requests:0))/total*100);
    q('#benchmark-meter').value = job.status==='completed'?100:progress;
    q('#benchmark-message').textContent = `${statuses[job.status] || job.status} · ${job.completed_runs||0}/${total} rulări · ${names[job.current_mode]||'Pregătire'} · ${job.phase==='preparing'?'golire / preîncărcare':fmt(job.current_requests||0,0)+' cereri în rularea curentă'}${job.message?' · '+job.message:''}`;
  }
  function groups(job) {
    const map = new Map();
    for(const r of job.results || []) {
      if(r.partial) continue;
      if(!map.has(r.mode)) map.set(r.mode,[]);
      map.get(r.mode).push(r);
    }
    return [...map].map(([mode,runs]) => {
      const avg=key=>{const values=runs.map(r=>r[key]).filter(v=>v!=null); return values.length?values.reduce((a,b)=>a+b,0)/values.length:null;};
      return {mode,n:runs.length,mean_ms:avg('mean_ms'),p95_ms:avg('p95_ms'),rps:avg('successful_requests_per_second'),hit_rate:avg('hit_rate'),errors:runs.reduce((sum,r)=>sum+Object.values(r.errors).reduce((a,b)=>a+b,0),0)};
    });
  }
  function chart(data,key,title,unit) {
    const max=Math.max(...data.map(r=>r[key]||0),0.001);
    return `<div class="chart"><h3>${title}</h3>${data.map(r=>`<div class="bar-item"><div class="bar-label"><span>${names[r.mode]}</span><b>${fmt(r[key])} ${unit}</b></div><div class="bar-track"><div class="bar-fill ${r.mode.endsWith('no-cache')?'no-cache':''} ${r[key]?'':'zero'}" style="width:${Math.max(0,(r[key]||0)/max*100)}%"></div></div></div>`).join('')}</div>`;
  }
  function renderResults(job) {
    selected=job;
    q('#exports').hidden=!job;
    const c=job.configuration;
    q('#result-description').textContent=`${new Date(job.created_at).toLocaleString('ro-RO')} · ${statuses[job.status]||job.status} · ${fmt(c.requests,0)} cereri/rulare · ${c.concurrency} clienți · ${c.products} produse · ${c.repeats} repetări · TTL ${c.ttl}s · cache ${c.cache_state==='cold'?'inițial gol':'preîncărcat'}.`;
    if(!job.results?.length) {q('#result-content').innerHTML='<p class="dash-note">Rezultatele apar după prima rulare finalizată.</p>'; return;}
    const data=groups(job);
    const latest=job.results.at(-1);
    let notes='';
    for(const prefix of ['single','distributed']) {
      const without=data.find(r=>r.mode===prefix+'-no-cache'), withCache=data.find(r=>r.mode===prefix+'-cache');
      if(without && withCache && without.mean_ms && without.rps) {
        const latency=(without.mean_ms-withCache.mean_ms)/without.mean_ms*100;
        const speed=(withCache.rps-without.rps)/without.rps*100;
        notes+=`${prefix==='single'?'O instanță':'Două instanțe'}: cu cache, latența medie ${latency>=0?'scade':'crește'} cu ${fmt(Math.abs(latency))}%, iar cererile/s ${speed>=0?'cresc':'scad'} cu ${fmt(Math.abs(speed))}%. `;
      }
    }
    const totalErrors=job.results.reduce((s,r)=>s+Object.values(r.errors).reduce((a,b)=>a+b,0),0);
    q('#result-content').innerHTML=`<div class="result-cards"><div class="result-card"><small>ULTIMA RULARE · MEDIE</small><strong>${fmt(latest.mean_ms)} ms</strong></div><div class="result-card"><small>ULTIMA RULARE · CERERI/S</small><strong>${fmt(latest.successful_requests_per_second)}</strong></div><div class="result-card"><small>ULTIMA RULARE · HIT</small><strong>${latest.hit_rate==null?'—':fmt(latest.hit_rate*100)+'%'}</strong></div><div class="result-card"><small>ERORI ÎN EXPERIMENT</small><strong>${fmt(totalErrors,0)}</strong></div></div>
    ${notes?`<p class="comparison-note">${notes}Aceste procente descriu numai acest experiment; verifică și p95, erorile și repetările.</p>`:''}
    ${data.length?`<div class="chart-grid">${chart(data,'mean_ms','Timp mediu · mai mic este mai bine','ms')}${chart(data,'rps','Cereri reușite/secundă · mai mare este mai bine','')}${chart(data,'p95_ms','p95 · mai mic este mai bine','ms')}${chart(data.map(r=>({...r,hit:r.hit_rate==null?null:r.hit_rate*100})),'hit','Rată HIT · numai pentru cache activ','%')}</div><p class="dash-note">Barele arată media aritmetică a indicatorilor per rulare, inclusiv media valorilor p95; nu reprezintă p95 calculat peste toate cererile reunite. Rulările oprite parțial sunt excluse. Lipsa unei valori nu înseamnă zero. ${data.some(r=>r.n<3)?'Ai sub 3 repetări pentru cel puțin o configurație; rezultatele sunt preliminare.':''}</p>`:''}
    <div class="run-table"><table><thead><tr><th>Configurație / repetare</th><th>Medie ms</th><th>p95 ms</th><th>Cereri/s</th><th>HIT %</th><th>Erori</th><th>Instanțe observate</th></tr></thead><tbody>${job.results.map(r=>`<tr><td>${names[r.mode]} / ${r.repeat}${r.partial?' (parțial)':''}</td><td>${fmt(r.mean_ms)}</td><td>${fmt(r.p95_ms)}</td><td>${fmt(r.successful_requests_per_second)}</td><td>${r.hit_rate==null?'—':fmt(r.hit_rate*100)}</td><td>${Object.values(r.errors).reduce((a,b)=>a+b,0)}</td><td>${Object.entries(r.instances||{}).map(([k,v])=>`${escape(k)}: ${v}`).join('<br>')}</td></tr>`).join('')}</tbody></table></div><p class="dash-note">Rapoartele JSON includ tipurile de erori, numărul de HIT/MISS/BYPASS și cererile procesate de fiecare instanță. Măsurarea pornește din containerul laborator, nu din browser sau din terminalul Windows; compară doar rulări obținute prin aceeași metodă. „Fără cache” ocolește Redis, fără a opri serviciul. Ambele configuratii trec prin Nginx: o instanta foloseste numai API 1, doua instante distribuie cererile intre API 1 si API 2. Toate containerele împart calculatorul.</p>`;
  }
  async function refreshHistory(preferred) {
    history=await api('/lab/experiments');
    const chosen=preferred || selected?.id || history[0]?.id;
    q('#experiment-select').innerHTML=history.length?history.map(job=>`<option value="${job.id}">${escape(new Date(job.created_at).toLocaleString('ro-RO'))} · ${statuses[job.status]||job.status} · ${job.configuration.concurrency} clienți</option>`).join(''):'<option value="">Niciun experiment încă</option>';
    const job=history.find(j=>j.id===chosen)||history[0];
    if(job){q('#experiment-select').value=job.id;renderResults(job);}
    const running=history.find(j=>['running','queued'].includes(j.status));
    if(running) {setActive(running);poll();} else {setActive(job || null);}
  }
  async function poll() {
    if(polling)return;
    polling=true;
    try {
      while(active) {
        const job=await api('/lab/experiments/'+active.id);
        setActive(job);
        if(!selected || selected.id===job.id) renderResults(job);
        if(!active) {await refreshHistory(job.id);await refreshStatus();break;}
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
    } catch(error){q('#benchmark-error').textContent=error.message+' Apasă Actualizează în istoric pentru reconectare.';}
    finally {polling=false;}
  }
  q('#benchmark-form').addEventListener('submit',async event=>{
    event.preventDefault();q('#benchmark-error').textContent='';q('#benchmark-fields').disabled=true;
    try {const response=await api('/lab/experiments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settingsFromDisabledForm())});await refreshHistory(response.id);}
    catch(error){q('#benchmark-error').textContent=error.message;if(!active)q('#benchmark-fields').disabled=false;}
  });
  function settingsFromDisabledForm(){q('#benchmark-fields').disabled=false;const values=settings();q('#benchmark-fields').disabled=true;return values;}
  q('#seed-benchmark').addEventListener('click',async()=>{
    q('#seed-benchmark').disabled=true;
    try{const result=await api('/demo/seed?count='+settings().products,{method:'POST'});q('#benchmark-error').textContent=`Date pregătite: ${result.inserted} produse noi. Poți porni experimentul.`;await refreshStatus();}
    catch(error){q('#benchmark-error').textContent=error.message;}
    finally{q('#seed-benchmark').disabled=false;}
  });
  q('#stop-benchmark').addEventListener('click',async()=>{if(!active)return;try{await api('/lab/experiments/'+active.id+'/stop',{method:'POST'});q('#benchmark-message').textContent='Se oprește după cererile aflate în curs…';}catch(error){q('#benchmark-error').textContent=error.message;}});
  q('#refresh-status').addEventListener('click',refreshStatus);
  q('#refresh-history').addEventListener('click',()=>refreshHistory().catch(error=>q('#benchmark-error').textContent=error.message));
  q('#experiment-select').addEventListener('change',()=>{const job=history.find(j=>j.id===q('#experiment-select').value);if(job)renderResults(job);});
  function download(text,type,extension){const url=URL.createObjectURL(new Blob([text],{type}));const anchor=document.createElement('a');anchor.href=url;anchor.download=`experiment-${selected.id}.${extension}`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  q('#export-json').addEventListener('click',()=>{if(selected)download(JSON.stringify(selected,null,2),'application/json','json');});
  q('#export-csv').addEventListener('click',()=>{
    if(!selected)return;
    const c=selected.configuration;
    const rows=[['mode','repeat','partial','requests','concurrency','products','ttl','cache_state','successes','errors','mean_ms','p95_ms','requests_per_second','hit_rate'],...selected.results.map(r=>[r.mode,r.repeat,r.partial,c.requests,c.concurrency,c.products,c.ttl,c.cache_state,r.successful_requests,Object.values(r.errors).reduce((a,b)=>a+b,0),r.mean_ms,r.p95_ms,r.successful_requests_per_second,r.hit_rate])];
    download(rows.map(row=>row.map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(',')).join('\r\n'),'text/csv;charset=utf-8','csv');
  });
  refreshStatus();refreshHistory().catch(error=>q('#benchmark-error').textContent=error.message);
})();
