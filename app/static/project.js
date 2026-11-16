const $ = selector => document.querySelector(selector);
const history = [];
const safe = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function request(url, options) {
  const result = await fetch(url, options);
  if (!result.ok) throw Error(`Cererea a eșuat (${result.status}). Încearcă din nou.`);
  return result;
}
async function loadProducts() {
  try {
    const products = await (await request('/catalog')).json();
    $('#test-product').innerHTML = products.map(p => `<option value="${p.id}">${safe(p.name)}</option>`).join('');
    $('#test-product').disabled = !products.length;
    $('#request-product').disabled = !products.length;
    if (!products.length) $('#lab-log').textContent = 'Catalogul este gol. Încarcă produsele cu POST /demo/catalog din documentația API.';
  } catch (error) { $('#lab-log').textContent = error.message; }
}
function busy(value) {
  $('#request-product').disabled = value || $('#test-product').disabled;
  $('#clear-cache').disabled = value;
}
$('#request-product').addEventListener('click', async () => {
  busy(true);
  try {
    const start = performance.now();
    const result = await request(`/products/${$('#test-product').value}?use_cache=${$('#cache-enabled').checked}`);
    const product = await result.json();
    const elapsed = (performance.now() - start).toFixed(1);
    const source = result.headers.get('X-Cache') || '—';
    const instance = result.headers.get('X-Instance') || '—';
    $('#lab-source').textContent = source;
    $('#lab-time').textContent = `${elapsed} ms`;
    $('#lab-instance').textContent = instance;
    $('#lab-log').textContent = `${product.name}: ${source === 'HIT' ? 'date primite din memoria Redis.' : source === 'BYPASS' ? 'cache ocolit; date primite direct din MongoDB.' : 'date citite din MongoDB; vor fi păstrate temporar în Redis dacă este disponibil.'}`;
    history.unshift({name: product.name, source, elapsed, instance});
    history.splice(10);
    $('#request-history').innerHTML = `<h3>Ultimele cereri</h3><div class="history-scroll"><table><thead><tr><th>Produs</th><th>Sursă</th><th>Timp</th><th>Instanță</th></tr></thead><tbody>${history.map(row => `<tr><td>${safe(row.name)}</td><td>${safe(row.source)}</td><td>${row.elapsed} ms</td><td><code>${safe(row.instance)}</code></td></tr>`).join('')}</tbody></table></div>`;
  } catch (error) { $('#lab-log').textContent = error.message; }
  finally { busy(false); }
});
$('#clear-cache').addEventListener('click', async () => {
  busy(true);
  try { await request('/demo/cache', {method:'DELETE'}); $('#lab-source').textContent = '—'; $('#lab-time').textContent = '—'; $('#lab-instance').textContent = '—'; $('#lab-log').textContent = 'Cache golit. Apasă „Solicită produsul” cu Redis activ: următoarea cerere va produce MISS.'; }
  catch (error) { $('#lab-log').textContent = error.message; }
  finally { busy(false); }
});
loadProducts();
