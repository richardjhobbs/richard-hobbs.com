/* Pacific Risk Advisors. Content comes from data/knowledge.json, the same file the MCP server reads. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const el = (tag, attrs = {}, html = '') => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    n.innerHTML = html;
    return n;
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const sleep = ms => new Promise(r => setTimeout(r, still ? 0 : ms));
  const pad = n => String(n).padStart(2, '0');

  /* ---------- nav ---------- */
  const nav = $('#nav');
  const onScroll = () => nav.classList.toggle('solid', scrollY > 40);
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  const menuBtn = $('#menuBtn');
  menuBtn.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    nav.classList.toggle('solid', open || scrollY > 40);
    menuBtn.setAttribute('aria-expanded', open);
  });
  $$('#navList a').forEach(a => a.addEventListener('click', () => nav.classList.remove('open')));
  $('#year').textContent = new Date().getFullYear();

  /* ---------- reveal on scroll ---------- */
  const seen = new IntersectionObserver(entries => entries.forEach(e => {
    if (!e.isIntersecting) return;
    e.target.classList.add('in');
    e.target.dispatchEvent(new CustomEvent('seen'));
    seen.unobserve(e.target);
  }), { threshold: 0.15 });
  const watch = () => $$('.rv:not(.in)').forEach(n => seen.observe(n));
  watch();

  /* ---------- count up ---------- */
  $$('[data-count], [data-count-since]').forEach(n => {
    const target = n.dataset.countSince ? new Date().getFullYear() - +n.dataset.countSince : +n.dataset.count;
    n.textContent = target;
    if (still || 'plain' in n.dataset) return;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const tick = t => {
        const p = Math.min(1, (t - t0) / 1100);
        n.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    io.observe(n);
  });

  /* ---------- engagement run ---------- */
  const steps = $$('#steps li');
  if (steps.length) {
    let token = 0;
    const play = async () => {
      const mine = ++token;
      steps.forEach(s => s.classList.remove('on'));
      $('#runBar').style.width = '0';
      for (let i = 0; i < steps.length; i++) {
        await sleep(i ? 950 : 300);
        if (mine !== token) return;
        steps[i].classList.add('on');
        $('#runBar').style.width = ((i + 1) / steps.length * 100) + '%';
      }
    };
    $('#run').addEventListener('seen', play);
    $('#replay').addEventListener('click', play);
  }

  /* ---------- match bars ---------- */
  const match = $('#match');
  if (match) match.addEventListener('seen', () => $$('.bar i', match).forEach((b, i) =>
    setTimeout(() => { b.style.width = b.dataset.w + '%'; }, still ? 0 : 250 + i * 180)));

  /* ---------- knowledge-driven content ---------- */
  fetch('data/knowledge.json').then(r => r.json()).then(k => {
    if ($('#caps')) home(k);
    watch();
  }).catch(() => {});

  function home(k) {
    // lifecycle
    const tabs = $('#stageTabs');
    const show = id => {
      const stage = k.stages.find(s => s.id === id);
      $$('button', tabs).forEach(b => b.setAttribute('aria-selected', b.dataset.id === id));
      $('#stageSum').textContent = stage.summary;
      $('#caps').replaceChildren(...k.capabilities.filter(c => c.stage === id).map((c, i) => {
        const card = el('article', { class: 'cap', style: `animation-delay:${i * 70}ms` },
          `<h3>${esc(c.name)}</h3><p>${esc(c.summary)}</p><ul>${c.includes.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`);
        return card;
      }));
    };
    k.stages.forEach((s, i) => {
      const b = el('button', { role: 'tab', type: 'button', 'data-id': s.id }, `<small>STAGE ${pad(i + 1)}</small><b>${esc(s.label)}</b>`);
      b.addEventListener('click', () => show(s.id));
      tabs.append(b);
    });
    show(k.stages[0].id);

    // standards ticker (duplicated once for a seamless loop)
    const items = k.standards.map(s => `<li>${esc(s.name)}</li>`).join('');
    $('#ticker').innerHTML = items + items;

    // agents and safeguards
    $('#agents').innerHTML = k.operating_model.agents.map((a, i) => `
      <div class="agent-row"><span class="n">${pad(i + 1)}</span><div>
        <h3>${esc(a.name)}</h3><p>${esc(a.does)}</p><p class="gain">${esc(a.client_benefit)}</p>
        ${a.id === 'door' ? '<p style="margin-top:14px"><a class="btn ghost" href="agents.html">Connect your agent <span class="arr">→</span></a></p>' : ''}
      </div></div>`).join('');
    $('#guards').innerHTML = k.operating_model.safeguards.map((g, i) =>
      `<div class="guard"><span class="n">${pad(i + 1)}</span><h3>${esc(g.title)}</h3><p>${esc(g.detail)}</p></div>`).join('');

    // clients
    $('#clientsCapital').innerHTML = k.clients.capital.map(c => `<li>${esc(c)}</li>`).join('');
    $('#clientsIndustry').innerHTML = k.clients.industry.map(c => `<li>${esc(c)}</li>`).join('');

    // reach
    $('#regions').innerHTML = k.coverage.map(r => `
      <div class="region"><h3>${esc(r.region)} <i>${pad(r.countries.length)}</i></h3>
      <ul>${r.countries.map(c => `<li>${esc(c)}</li>`).join('')}</ul></div>`).join('');
    $('#partners').innerHTML = k.partners.map(p => `<div class="partner"><h3>${esc(p.name)}</h3><p>${esc(p.role)}</p></div>`).join('');
    const clocks = $('#clocks');
    const tick = () => {
      clocks.innerHTML = k.firm.offices.map(o => {
        const now = new Date();
        const time = now.toLocaleTimeString('en-GB', { timeZone: o.timezone, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const hour = +now.toLocaleString('en-GB', { timeZone: o.timezone, hour: '2-digit', hour12: false });
        const day = now.toLocaleDateString('en-GB', { timeZone: o.timezone, weekday: 'short' });
        const open = !['Sat', 'Sun'].includes(day) && hour >= 9 && hour < 18;
        return `<div class="clock"><small>${esc(o.city)} office</small><b>${time}</b><span>${open ? 'Office open' : 'Out of office hours'}</span></div>`;
      }).join('');
    };
    tick();
    setInterval(tick, 1000);

    // firm credentials
    $('#creds').innerHTML =
      `<a href="${esc(k.firm.pri_listing)}" rel="noopener"><b>Signatory, Principles for Responsible Investment</b><span>Listing ↗</span></a>` +
      `<div><b>Associate, Inogen Alliance</b><span>Global EHS&amp;S network</span></div>` +
      k.firm.documents.map(d => `<a href="${esc(d.url)}" rel="noopener"><b>${esc(d.title)}</b><span>PDF ↗</span></a>`).join('');

    // offices
    $('#offices').innerHTML = k.firm.offices.map(o =>
      `<div class="office"><b>${esc(o.city)}</b>${esc(o.address)}<br><a href="tel:${o.phone.replace(/\s/g, '')}">${esc(o.phone)}</a></div>`).join('') +
      `<div class="office"><b>Email</b><a href="mailto:${esc(k.firm.email)}">${esc(k.firm.email)}</a></div>`;

    ask(k);
  }

  /* ---------- ask console ---------- */
  function ask(k) {
    const body = $('#consoleBody'), input = $('#askInput'), form = $('#askForm');
    const STOP = new Set('a an and are as at be by can do does for from how i in is it my of on or our so that the their to us we what when where which who with would you your'.split(' '));
    const toks = t => (t.toLowerCase().match(/[a-z0-9&]+/g) || []).filter(w => !STOP.has(w) && w.length > 1);
    const best = q => {
      const qs = new Set(toks(q));
      let top = null, score = 0;
      for (const f of k.faqs) {
        const s = 2 * f.keywords.filter(w => qs.has(w)).length + toks(f.q).filter(w => qs.has(w)).length;
        if (s > score) { score = s; top = f; }
      }
      const country = k.coverage.flatMap(r => r.countries.map(c => ({ c, r: r.region })))
        .find(x => q.toLowerCase().includes(x.c.toLowerCase()));
      const hit = list => list.map(x => ({ x, n: toks(x.name || x).filter(w => qs.has(w)).length })).sort((a, b) => b.n - a.n)[0];
      const cap = hit(k.capabilities), sector = hit([...k.clients.industry, ...k.clients.capital]);
      return { faq: score >= 2 ? top : null, country, cap: cap.n ? cap.x : null, sector: sector.n ? sector.x : null };
    };
    let token = 0, auto = true;

    const answer = async (q, user) => {
      const mine = ++token;
      const { faq, country, cap, sector } = best(q);
      const partial = !faq && (cap || sector || country);
      body.replaceChildren(el('p', { class: 'msg-q' }, esc(q)));
      const trace = el('ul', { class: 'trace' });
      body.append(trace);
      const lines = ['Searching published knowledge', faq ? `Matched: ${faq.q}` : partial ? 'Partial match in capabilities and coverage' : 'No published answer matched',
        faq ? `${faq.sources.length} source${faq.sources.length > 1 ? 's' : ''} attached` : 'The rest goes to an advisor'];
      for (const line of lines) {
        const li = el('li', {}, esc(line));
        trace.append(li);
        await sleep(60);
        li.classList.add('on');
        await sleep(380);
        if (mine !== token) return;
      }
      let text = faq ? faq.a : '';
      if (!faq && cap) text += `${cap.name}: ${cap.summary} `;
      if (!faq && sector) text += `PRA's clients include ${sector[0].toLowerCase() + sector.slice(1)}. `;
      if (country && !(faq && faq.a.includes(country.c))) text += `${faq ? ' ' : ''}PRA has advisors in ${country.c}. `;
      if (!faq) text += partial ? 'For the specifics, send a short brief and an advisor will reply.' : 'That is one for an advisor. Send a short brief and a person will reply, with the open questions listed.';
      const out = el('p', { class: 'msg-a typing' });
      body.append(out);
      if (still) out.textContent = text;
      else for (let i = 0; i <= text.length; i += 3) {
        out.textContent = text.slice(0, i + 3);
        await sleep(12);
        if (mine !== token) return;
      }
      out.classList.remove('typing');
      const srcs = el('div', { class: 'srcs' }, (faq ? faq.sources : [...(cap ? [[cap.name, '#work']] : []), ...(sector ? [['Clients', '#clients']] : []), ...(country ? [['Coverage', '#reach']] : []), ['Brief PRA', '#brief']])
        .map(([label, href]) => `<a href="${esc(href)}">${esc(label)} ↗</a>`).join(''));
      body.append(srcs);
      if (user) return;
      await sleep(5200);
      if (mine === token && auto) cycle();
    };

    const demo = k.faqs.filter(f => ['deal', 'ai', 'data', 'standards', 'mcp'].includes(f.id));
    let idx = 0;
    const cycle = () => answer(demo[idx++ % demo.length].q, false);

    const chips = $('#askChips');
    ['deal', 'ai', 'data', 'where', 'mcp'].forEach(id => {
      const f = k.faqs.find(x => x.id === id);
      const b = el('button', { type: 'button' }, esc(f.q));
      b.addEventListener('click', () => { auto = false; answer(f.q, true); });
      chips.append(b);
    });
    form.addEventListener('submit', e => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      auto = false;
      input.value = '';
      answer(q, true);
    });
    input.addEventListener('focus', () => { auto = false; });
    cycle();
  }

  /* ---------- brief form ---------- */
  const form = $('#briefForm');
  if (form) form.addEventListener('submit', async e => {
    e.preventDefault();
    const msg = $('#briefMsg'), btn = $('button[type=submit]', form);
    const data = Object.fromEntries(new FormData(form));
    const say = (text, err) => { msg.hidden = false; msg.textContent = text; msg.classList.toggle('err', !!err); };
    if (!data.name || !data.email || !data.summary) return say('Please add your name, email and what you need.', true);
    btn.disabled = true;
    try {
      const r = await fetch('api/enquiry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const j = await r.json();
      if (!r.ok) return say(j.error ? j.error[0].toUpperCase() + j.error.slice(1) + '.' : 'That did not go through.', true);
      form.reset();
      say(`Received, reference ${j.reference}. An advisor will reply by email.`);
    } catch {
      say('That did not go through. Please email enquiries@pacificriskadvisors.com.', true);
    } finally { btn.disabled = false; }
  });

  /* ---------- agents page: live MCP client ---------- */
  if ($('#tools')) mcpPage();

  function mcpPage() {
    const url = new URL('mcp', location.href).href;
    $('#endpoint').textContent = url;
    $$('[data-endpoint]').forEach(n => { n.textContent = n.textContent.replaceAll('{url}', url); });
    $$('[data-copy]').forEach(b => b.addEventListener('click', async () => {
      await navigator.clipboard.writeText($(b.dataset.copy).textContent).catch(() => {});
      b.textContent = 'Copied';
      setTimeout(() => { b.textContent = 'Copy'; }, 1400);
    }));

    let id = 0;
    const rpc = async (method, params = {}) => {
      const t0 = performance.now();
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream' },
        body: JSON.stringify({ jsonrpc: '2.0', id: ++id, method, params }),
      });
      const j = await r.json();
      return { j, ms: Math.round(performance.now() - t0) };
    };
    const status = $('#status');
    const samples = {
      list_capabilities: { stage: 'commit' }, get_capability: { id: 'deal-diligence' }, get_coverage: { country: 'Vietnam' },
      search_knowledge: { query: 'ESMS for a bank' },
      submit_enquiry: { name: 'Your name', email: 'you@example.com', organisation: 'Your fund', summary: 'ESDD on a manufacturer in Vietnam to IFC Performance Standards.', via_agent: 'Website console' },
    };
    let current = null;

    (async () => {
      try {
        const init = await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'pra-site-console', version: '1' } });
        const info = init.j.result;
        const list = await rpc('tools/list');
        const tools = list.j.result.tools;
        status.classList.add('up');
        $('span', status).textContent = `Live · ${info.serverInfo.name} ${info.serverInfo.version} · protocol ${info.protocolVersion} · ${tools.length} tools · ${init.ms} ms`;
        $('#tools').replaceChildren(...tools.map(t => {
          const args = Object.keys(t.inputSchema.properties || {});
          const req = new Set(t.inputSchema.required || []);
          const b = el('button', { class: 'tool', type: 'button', 'aria-pressed': 'false' },
            `<code>${esc(t.name)}</code><p>${esc(t.description)}</p><span class="args">${args.length ? args.map(a => esc(a) + (req.has(a) ? '' : '?')).join(', ') : 'no arguments'}</span>`);
          b.addEventListener('click', () => {
            current = t.name;
            $$('.tool').forEach(x => x.setAttribute('aria-pressed', x === b));
            $('#pgTool').textContent = `tools/call · ${t.name}`;
            $('#pgArgs').value = JSON.stringify(samples[t.name] || {}, null, 2);
            if (t.annotations && t.annotations.readOnlyHint) run();
            else $('#pgOut').textContent = 'This tool sends a real enquiry to PRA. Edit the details, then press Run.';
          });
          return b;
        }));
      } catch {
        status.classList.add('down');
        $('span', status).textContent = 'The server did not answer from this page';
        $('#tools').innerHTML = '<p class="lede">The tool list loads from the live server and is not available right now.</p>';
      }
    })();

    const run = async () => {
      const out = $('#pgOut');
      if (!current) { out.textContent = 'Select a tool above first.'; return; }
      let args;
      try { args = JSON.parse($('#pgArgs').value || '{}'); } catch { out.textContent = 'The arguments are not valid JSON.'; return; }
      out.textContent = 'Calling…';
      try {
        const { j, ms } = await rpc('tools/call', { name: current, arguments: args });
        $('#pgMeta').textContent = `${ms} ms`;
        out.textContent = j.error ? `Error ${j.error.code}: ${j.error.message}` : j.result.content.map(c => c.text).join('\n');
      } catch { out.textContent = 'The server did not answer.'; }
    };
    $('#pgRun').addEventListener('click', run);
  }
})();
