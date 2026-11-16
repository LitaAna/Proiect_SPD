const $ = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat('ro-RO', {style:'currency', currency:'RON', maximumFractionDigits:0}).format(value);
let catalog = [], category = 'Toate', currentProduct = null;
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Sunt acceptate doar imaginile locale ale aplicatiei.
const imageURL = (value) => /^\/static\/images\/[a-zA-Z0-9._-]+$/.test(value) ? value : '/static/images/headphones.jpg';

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`Cererea a eșuat (${response.status}). Încearcă din nou.`);
  return response;
}
function render() {
  const search = $('#search').value.trim().toLocaleLowerCase('ro');
  const filtered = catalog.filter(p => (category === 'Toate' || p.category === category) && `${p.name} ${p.category}`.toLocaleLowerCase('ro').includes(search));
  $('#product-count').textContent = `${filtered.length} produse`;
  $('#catalog-status').textContent = filtered.length ? '' : 'Niciun produs găsit. Încearcă altă categorie sau alt nume.';
  $('#product-grid').innerHTML = filtered.map(p => `<article class="product-card"><button class="product-image" data-product="${p.id}" aria-label="Vezi ${escapeHTML(p.name)}"><img src="${imageURL(p.image)}" alt="${escapeHTML(p.name)} — fotografie ilustrativă" loading="lazy"><span class="product-badge">${escapeHTML(p.badge)}</span><span class="product-arrow" aria-hidden="true">↗</span></button><div class="product-info"><div><h3>${escapeHTML(p.name)}</h3><small>${escapeHTML(p.category)}</small></div><span class="price">${money(p.price)}</span></div></article>`).join('');
}
async function loadCatalog() {
  try {
    catalog = await (await request('/catalog')).json();
    if (!catalog.length) { $('#catalog-status').textContent = 'Colecția nu este disponibilă momentan. Revino puțin mai târziu.'; $('#product-count').textContent = '0 produse'; return; }
    render();
  } catch (error) {
    $('#catalog-status').textContent = `${error.message} Reîncarcă pagina pentru a relua conectarea.`;
  }
}
let productRequest = 0;
async function openProduct(id) {
  const version = ++productRequest;
  currentProduct = id;
  if (!$('#product-dialog').open) $('#product-dialog').showModal();
  $('#product-detail').innerHTML = '<div class="detail-loading" role="status">Pregătim detaliile produsului…</div>';
  const useCache = true;
  try {
    const response = await request(`/products/${id}?use_cache=${useCache}`);
    const product = await response.json();
    if (version !== productRequest) return;
    $('#product-detail').innerHTML = `<div class="detail-layout"><img src="${imageURL(product.image)}" alt="${escapeHTML(product.name)}"><div class="detail-copy"><div class="eyebrow">FORMA / ${escapeHTML(product.category)}</div><h2>${escapeHTML(product.name)}</h2><p>${escapeHTML(product.description)}</p><div class="detail-price">${money(product.price)}</div><div class="detail-meta">Colecția FORMA · Fotografie ilustrativă</div></div></div>`;
  } catch (error) {
    if (version !== productRequest) return;
    $('#product-detail').innerHTML = `<div class="detail-loading">${escapeHTML(error.message)}<br><br><button id="reload-product" class="button dark">Încearcă din nou ↻</button></div>`;
  }
}
document.addEventListener('click', event => {
  const product = event.target.closest('[data-product]');
  if (product) openProduct(Number(product.dataset.product));
  const filter = event.target.closest('[data-category]');
  if (filter) { category = filter.dataset.category; document.querySelectorAll('[data-category]').forEach(b => {b.classList.toggle('selected', b === filter); b.setAttribute('aria-pressed', String(b === filter));}); render(); }
  if (event.target.closest('#reload-product')) openProduct(currentProduct);
});
$('#search').addEventListener('input', render);
$('#dialog-close').addEventListener('click', () => $('#product-dialog').close());
$('#product-dialog').addEventListener('click', event => { if (event.target === $('#product-dialog')) { const box = event.target.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) event.target.close(); } });
loadCatalog();
