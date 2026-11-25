/* Acceso con correo y contraseña (Supabase Auth). Se usa en captura.html y panel.html. */
(function () {
  const TK = 'epp_token', EM = 'epp_email';
  const token = () => localStorage.getItem(TK) || '';
  const email = () => localStorage.getItem(EM) || '';
  let caja = null;

  function nodo() {
    if (!caja) {
      caja = document.createElement('div');
      caja.id = 'accesoEPP';
      Object.assign(caja.style, {
        position: 'fixed', inset: '0', zIndex: 9999, background: 'rgba(8,16,28,.72)',
        display: 'none', alignItems: 'center', justifyContent: 'center', padding: '16px'
      });
      document.body.appendChild(caja);
    }
    return caja;
  }

  function ocultar() { nodo().style.display = 'none'; }

  function mostrar(mensaje, modo) {
    const c = nodo();
    const registro = modo === 'registro';
    c.style.display = 'flex';
    c.innerHTML =
      '<form id="formaAcceso" style="width:100%;max-width:380px;background:#fff;color:#16202c;border-radius:18px;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.35);font:15px/1.4 system-ui,sans-serif">' +
      '<div style="background:linear-gradient(135deg,#0f3d63,#0f6fd1);color:#fff;padding:18px 20px 15px">' +
      '<h2 style="margin:2px 0;font-size:1.18rem">Acceso al reporte de EPP</h2>' +
      '<div style="font-size:.82rem;opacity:.85">' +
      (registro ? 'Crea tu cuenta para reportar eventos.' : 'Entra con tu cuenta para continuar.') + '</div></div>' +
      '<div style="padding:16px 20px 20px">' +
      '<label style="display:block;font-size:.8rem;color:#667487;margin:8px 0 4px">Correo</label>' +
      '<input id="acEmail" type="email" required autocomplete="username" style="width:100%;box-sizing:border-box;padding:12px;border:1px solid #dbe3ec;border-radius:10px">' +
      '<label style="display:block;font-size:.8rem;color:#667487;margin:12px 0 4px">Contraseña</label>' +
      '<input id="acClave" type="password" required minlength="6" autocomplete="' + (registro ? 'new-password' : 'current-password') + '" style="width:100%;box-sizing:border-box;padding:12px;border:1px solid #dbe3ec;border-radius:10px">' +
      '<p id="acMsg" style="min-height:1.2em;font-size:.85rem;color:#d23b3b;margin:10px 0 0">' + (mensaje || '') + '</p>' +
      '<button type="submit" style="width:100%;padding:14px;border:0;border-radius:12px;background:linear-gradient(135deg,#0f6fd1,#0a4f99);color:#fff;font-weight:700;font-size:1rem;margin-top:6px;box-shadow:0 6px 14px rgba(15,111,209,.25)">' +
      (registro ? 'Crear cuenta' : 'Iniciar sesión') + '</button>' +
      '<button type="button" id="acCambiar" style="width:100%;padding:10px;border:0;background:transparent;color:#0f6fd1;font-weight:600;cursor:pointer">' +
      (registro ? 'Ya tengo cuenta → iniciar sesión' : '¿No tienes cuenta? Crear una') + '</button>' +
      '</div></form>';
    document.getElementById('acCambiar').onclick = () => mostrar('', registro ? 'login' : 'registro');
    document.getElementById('formaAcceso').onsubmit = async (ev) => {
      ev.preventDefault();
      const e = document.getElementById('acEmail').value.trim().toLowerCase();
      const p = document.getElementById('acClave').value;
      const msg = document.getElementById('acMsg');
      msg.textContent = 'Un momento…';
      try {
        const r = await fetch(registro ? '/api/registro' : '/api/login', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: e, password: p })
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || 'No se pudo completar la acción');
        if (!j.token) {
          mostrar('Cuenta creada. Revisa tu correo para confirmarla y luego inicia sesión.', 'login');
          return;
        }
        localStorage.setItem(TK, j.token);
        localStorage.setItem(EM, j.usuario || e);
        ocultar();
        document.dispatchEvent(new CustomEvent('sesion', { detail: j }));
      } catch (err) { msg.textContent = String(err.message || err); }
    };
  }

  async function api(url, opciones) {
    const op = Object.assign({}, opciones || {});
    const h = new Headers(op.headers || {});
    if (token()) h.set('Authorization', 'Bearer ' + token());
    op.headers = h;
    const r = await fetch(url, op);
    if (r.status === 401 && !url.includes('/api/login') && !url.includes('/api/registro')) {
      salir();
      mostrar('Tu sesión venció. Vuelve a entrar.');
    }
    return r;
  }

  function salir() {
    localStorage.removeItem(TK);
    localStorage.removeItem(EM);
    document.dispatchEvent(new CustomEvent('sesion', { detail: null }));
    mostrar('Sesión cerrada.');
  }

  function iniciar() {
    if (!token()) { mostrar(); return; }
    fetch('/api/yo', { headers: { Authorization: 'Bearer ' + token() } })
      .then(r => r.ok ? ocultar() : (salirSilencioso(), mostrar('Tu sesión venció. Vuelve a entrar.')))
      .catch(() => {});
  }
  function salirSilencioso() {
    localStorage.removeItem(TK);
    localStorage.removeItem(EM);
    document.dispatchEvent(new CustomEvent('sesion', { detail: null }));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
  window.Sesion = { token, email, api, salir, mostrar, ocultar };
})();
