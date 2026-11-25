import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Image, Keyboard, Pressable, SafeAreaView, ScrollView,
  StyleSheet, Text, TextInput, View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

const C = { bg: '#eef2f7', card: '#fff', tx: '#16202c', mut: '#667487', bd: '#dbe3ec', ac: '#0f6fd1',
  ok: '#168a4a', mal: '#d23b3b', warn: '#c77d0a', head: '#0f3d63' };

const limpiarUrl = (u) => (u || '').trim().replace(/\/+$/, '').replace(/\/panel$/i, '').replace(/\/healthz$/i, '');
const leerJson = async (r) => {
  const texto = await r.text();
  try { return JSON.parse(texto); }
  catch (_) { throw new Error(texto.slice(0, 120) || ('Respuesta inesperada del servidor (' + r.status + ')')); }
};

export default function App() {
  const [tab, setTab] = useState('captura');
  const [servidor, setServidor] = useState('');
  const [token, setToken] = useState('');
  const [email, setEmail] = useState('');
  const [modo, setModo] = useState('login');
  const [clave, setClave] = useState('');
  const [correo, setCorreo] = useState('');
  const [authCargando, setAuthCargando] = useState(false);
  const [zona, setZona] = useState('Zona 1');
  const [cargando, setCargando] = useState(false);
  const [estado, setEstado] = useState('');
  const [gps, setGps] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [falloImagen, setFalloImagen] = useState(false);
  const [intentoImagen, setIntentoImagen] = useState(0);
  const [eventos, setEventos] = useState([]);
  const [errorEv, setErrorEv] = useState('');

  useEffect(() => {
    AsyncStorage.multiGet(['servidor', 'token', 'email', 'zona']).then((p) => {
      const d = Object.fromEntries(p);
      if (d.servidor) setServidor(d.servidor);
      if (d.token) setToken(d.token);
      if (d.email) setEmail(d.email);
      if (d.zona) setZona(d.zona);
    });
  }, []);
  const guardar = (k, v) => AsyncStorage.setItem(k, v).catch(() => {});
  const base = limpiarUrl(servidor);
  const urlImagen = (u) => (u && (u.startsWith('http') || u.startsWith('data:')) ? u : base + (u || ''));

  const api = useCallback(async (ruta, opciones = {}) => {
    const h = token ? { Authorization: 'Bearer ' + token } : {};
    const r = await fetch(base + ruta, { ...opciones, headers: { ...h, ...(opciones.headers || {}) } });
    if (r.status === 401) { setToken(''); setEmail(''); guardar('token', ''); guardar('email', ''); }
    return r;
  }, [base, token]);

  async function autenticar() {
    if (!base) return Alert.alert('Falta el servidor', 'Escribe la dirección del servidor.');
    if (!correo.includes('@') || clave.length < 6) return Alert.alert('Revisa los datos', 'Correo válido y contraseña de al menos 6 caracteres.');
    setAuthCargando(true);
    try {
      const r = await fetch(base + (modo === 'registro' ? '/api/registro' : '/api/login'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: correo.trim().toLowerCase(), password: clave }),
      });
      const j = await leerJson(r);
      if (!r.ok) throw new Error(j.error || 'No se pudo completar la acción');
      if (!j.token) {
        Alert.alert('Cuenta creada', 'Revisa tu correo para confirmar la cuenta y luego inicia sesión.');
        setModo('login'); setClave('');
        return;
      }
      setToken(j.token); setEmail(j.usuario || correo); setClave('');
      guardar('token', j.token); guardar('email', j.usuario || correo);
    } catch (e) { Alert.alert('No se pudo entrar', String(e.message || e)); }
    finally { setAuthCargando(false); }
  }

  function cerrarSesion() {
    setToken(''); setEmail(''); setClave('');
    guardar('token', ''); guardar('email', '');
    setModo('login');
  }

  const ubicar = useCallback(async () => {
    const p = await Location.requestForegroundPermissionsAsync();
    if (p.status !== 'granted') { setGps(null); return null; }
    try {
      // getLastKnownPositionAsync no espera a que el GPS fije la posición (puede tardar varios segundos).
      const l = await Location.getLastKnownPositionAsync({ maxAge: 60000 })
        || await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const g = { lat: l.coords.latitude, lon: l.coords.longitude, prec: l.coords.accuracy };
      setGps(g);
      return g;
    } catch (_) { setGps(null); return null; }
  }, []);
  useEffect(() => {
    const id = requestAnimationFrame(() => { ubicar(); });
    return () => cancelAnimationFrame(id);
  }, [ubicar]);

  async function enviar(asset) {
    if (!base) { Alert.alert('Falta el servidor', 'Escribe la dirección del servidor en Ajustes.'); setTab('ajustes'); return; }
    if (!token) return;
    setCargando(true); setResultado(null); setFalloImagen(false); setIntentoImagen(0); setEstado('Obteniendo ubicación…');
    const control = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const temporizador = control ? setTimeout(() => control.abort(), 90000) : null;
    try {
      const g = await ubicar();
      const esVideo = asset.type === 'video' || (asset.mimeType || '').startsWith('video');
      let uri = asset.uri;
      if (!esVideo) {
        setEstado('Preparando foto…');
        // Reducir la foto antes de subirla: el túnel es lento con imágenes de 10+ MP.
        try {
          const contexto = ImageManipulator.manipulate(asset.uri, { maxWidth: 1280 });
          contexto.resize({ width: 960 });
          const render = await contexto.renderAsync();
          const salida = await render.saveAsync({ compress: 0.7, format: SaveFormat.JPEG });
          uri = salida.uri;
        } catch (_) { /* si falla el redimensionado, se envía la original */ }
      }
      const fd = new FormData();
      const archivo = new File(uri);
      fd.append('archivo', archivo, esVideo ? (asset.fileName || 'video.mp4') : 'foto.jpg');
      fd.append('zona', zona.trim() || 'Zona 1');
      if (g) { fd.append('lat', String(g.lat)); fd.append('lon', String(g.lon)); fd.append('precision', String(g.prec ?? '')); }
      setEstado(esVideo ? 'Subiendo y analizando video…' : 'Subiendo foto y analizando…');
      const r = await api('/api/analizar', { method: 'POST', body: fd, signal: control ? control.signal : undefined });
      const j = await leerJson(r);
      if (!r.ok) throw new Error(j.error || 'Error ' + r.status);
      setResultado(j);
    } catch (e) {
      if (e && (e.name === 'AbortError' || /cancel/i.test(String(e.message || '')))) {
        Alert.alert('Tiempo agotado', 'El servidor tardó demasiado. Revisa la conexión y vuelve a intentar.');
      } else {
        Alert.alert('No se pudo analizar', String(e.message || e));
      }
    } finally {
      if (temporizador) clearTimeout(temporizador);
      setCargando(false); setEstado('');
    }
  }

  async function foto() {
    const p = await ImagePicker.requestCameraPermissionsAsync();
    if (!p.granted) return Alert.alert('Permiso necesario', 'Permite el acceso a la cámara.');
    const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!r.canceled) enviar(r.assets[0]);
  }
  async function video() {
    const p = await ImagePicker.requestCameraPermissionsAsync();
    if (!p.granted) return Alert.alert('Permiso necesario', 'Permite el acceso a la cámara.');
    const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['videos'], videoMaxDuration: 60 });
    if (!r.canceled) enviar(r.assets[0]);
  }
  async function galeria() {
    const p = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!p.granted) return Alert.alert('Permiso necesario', 'Permite el acceso a tus fotos.');
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images', 'videos'], quality: 0.8 });
    if (!r.canceled) enviar(r.assets[0]);
  }

  const cargarEventos = useCallback(async () => {
    if (!base || !token) { setErrorEv('Inicia sesión para ver los eventos.'); return; }
    try {
      const r = await api('/api/eventos');
      const j = await leerJson(r);
      if (!r.ok) throw new Error(j.error || 'Error ' + r.status);
      setEventos(j.eventos || []); setErrorEv('');
    } catch (e) { setErrorEv(String(e.message || e)); }
  }, [base, token, api]);
  useEffect(() => {
    if (!token || tab !== 'eventos') return undefined;
    const id = requestAnimationFrame(() => { cargarEventos(); });
    return () => cancelAnimationFrame(id);
  }, [token, tab, cargarEventos]);

  if (!token) {
    return (
      <SafeAreaView style={s.safe}>
        <StatusBar style="light" />
        <View style={s.head}>
          <Text style={s.h1}>Reporte de EPP</Text>
          <Text style={s.h2}>{modo === 'registro' ? 'Crea tu cuenta' : 'Inicia sesión para continuar'}</Text>
        </View>
        <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
          <View style={s.card}>
            <Text style={s.lab}>Dirección del servidor</Text>
            <TextInput style={s.input} value={servidor} autoCapitalize="none" autoCorrect={false} keyboardType="url"
              placeholder="https://xxxx.lhr.life" onChangeText={(t) => { setServidor(t); guardar('servidor', t); }} />
            <Text style={s.lab}>Correo</Text>
            <TextInput style={s.input} value={correo} autoCapitalize="none" autoCorrect={false} keyboardType="email-address"
              placeholder="nombre@empresa.com" onChangeText={setCorreo} />
            <Text style={s.lab}>Contraseña</Text>
            <TextInput style={s.input} value={clave} autoCapitalize="none" secureTextEntry
              onChangeText={setClave} onSubmitEditing={autenticar} />
            {authCargando && <ActivityIndicator size="small" color={C.ac} style={{ marginTop: 12 }} />}
            <Pressable style={[s.btn, { marginTop: 16 }]} onPress={autenticar} disabled={authCargando}>
              <Text style={s.btnT}>{modo === 'registro' ? 'Crear cuenta' : 'Iniciar sesión'}</Text>
            </Pressable>
            <Pressable style={{ marginTop: 12, alignItems: 'center' }} onPress={() => setModo(modo === 'registro' ? 'login' : 'registro')}>
              <Text style={{ color: C.ac, fontWeight: '700' }}>
                {modo === 'registro' ? 'Ya tengo cuenta → iniciar sesión' : '¿No tienes cuenta? Crear una'}
              </Text>
            </Pressable>
          </View>
          <Text style={s.mut}>La cuenta se crea con Supabase Auth. Si pide confirmación, revisa tu correo antes de entrar.</Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  const alerta = resultado && resultado.incumplimientos > 0;
  const sinP = resultado && resultado.personas === 0;
  const colorRes = alerta ? C.mal : sinP ? C.mut : C.ok;
  const tituloRes = alerta ? 'ALERTA: falta EPP' : sinP ? 'Sin personas detectadas' : 'EPP completo';

  return (
    <SafeAreaView style={s.safe}>
      <StatusBar style="light" />
      <View style={s.head}>
        <Text style={s.h1}>Reporte de EPP</Text>
        <Text style={s.h2}>{email} · foto o video con ubicación</Text>
      </View>
      <View style={s.tabs}>
        {[['captura', 'Capturar'], ['eventos', 'Eventos'], ['ajustes', 'Ajustes']].map(([k, t]) => (
          <Pressable key={k} style={[s.tab, tab === k && s.tabOn]} onPress={() => { Keyboard.dismiss(); setTab(k); }}>
            <Text style={[s.tabT, tab === k && s.tabTOn]}>{t}</Text>
          </Pressable>
        ))}
      </View>

      {tab === 'captura' && (
        <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
          <View style={s.card}>
            <View style={s.chips}>
              <Pressable onPress={ubicar} style={s.chip}>
                <View style={[s.dot, { backgroundColor: gps ? C.ok : C.mal }]} />
                <Text style={s.chipT}>{gps ? `Ubicación ±${Math.round(gps.prec || 0)} m` : 'Sin ubicación (toca para reintentar)'}</Text>
              </Pressable>
            </View>
            <Text style={s.lab}>Zona o frente de obra</Text>
            <TextInput style={s.input} value={zona} onChangeText={(t) => { setZona(t); guardar('zona', t); }} />
          </View>
          <View style={s.card}>
            <Pressable style={s.btn} onPress={foto} disabled={cargando}><Text style={s.btnT}>Tomar foto</Text></Pressable>
            <View style={s.dos}>
              <Pressable style={[s.btn, s.sec, { flex: 1 }]} onPress={video} disabled={cargando}><Text style={s.secT}>Video</Text></Pressable>
              <Pressable style={[s.btn, s.sec, { flex: 1 }]} onPress={galeria} disabled={cargando}><Text style={s.secT}>Galería</Text></Pressable>
            </View>
          </View>
          {cargando && (
            <View style={[s.card, { alignItems: 'center' }]}>
              <ActivityIndicator size="large" color={C.ac} />
              <Text style={s.mut}>{estado}</Text>
            </View>
          )}
          {resultado && (
            <View style={s.card}>
              <View style={[s.badge, { backgroundColor: colorRes }]}><Text style={s.badgeT}>{tituloRes}</Text></View>
              <View style={s.stats}>
                {[['personas', resultado.personas], ['cascos', resultado.cascos ?? 0], ['chalecos', resultado.chalecos ?? 0]].map(([n, v]) => (
                  <View key={n} style={s.stat}><Text style={s.statN}>{v}</Text><Text style={s.statL}>{n}</Text></View>
                ))}
              </View>
              {alerta && <Text style={s.mut}>{resultado.eventos.length} evento(s) guardado(s) en la base de datos.</Text>}
              {sinP && (resultado.cascos + resultado.chalecos) > 0 && (
                <Text style={s.mut}>Se detectó equipo pero ninguna persona: suele pasar con personas muy juntas. Toma la foto un poco más lejos.</Text>
              )}
              {!resultado.con_ubicacion && <Text style={[s.mut, { color: C.mal }]}>Guardado sin ubicación.</Text>}
              {!!resultado.imagen && (
                <Image
                  source={{ uri: `${urlImagen(resultado.imagen)}?v=${intentoImagen}` }}
                  style={s.img}
                  resizeMode="contain"
                  onError={() => setFalloImagen(true)}
                />
              )}
              {falloImagen && (
                <View style={{ marginTop: 8 }}>
                  <Text style={[s.mut, { color: C.mal }]}>
                    La imagen con las cajas tarda en bajar por el túnel. Puedes reintentar:
                  </Text>
                  <Pressable style={[s.btn, s.sec, { marginTop: 8 }]} onPress={() => {
                    setFalloImagen(false); setIntentoImagen((n) => n + 1);
                  }}>
                    <Text style={s.secT}>Reintentar imagen</Text>
                  </Pressable>
                </View>
              )}
            </View>
          )}
        </ScrollView>
      )}

      {tab === 'eventos' && (
        <FlatList
          contentContainerStyle={s.body}
          data={eventos}
          keyExtractor={(e) => String(e.id)}
          onRefresh={cargarEventos}
          refreshing={false}
          ListHeaderComponent={<Text style={s.mut}>{errorEv || `${eventos.length} evento(s). Desliza hacia abajo para actualizar.`}</Text>}
          renderItem={({ item: e }) => (
            <View style={[s.card, s.fila]}>
              {!!e.imagen && <Image source={{ uri: urlImagen(e.imagen) }} style={s.mini} />}
              <View style={{ flex: 1 }}>
                <Text style={s.evT}>#{e.id} · {e.zona}</Text>
                <Text style={s.mut}>{String(e.momento).replace('T', ' ')}</Text>
                <Text style={{ color: C.mal, fontWeight: '700' }}>
                  {[e.falta_casco ? 'sin casco' : '', e.falta_chaleco ? 'sin chaleco' : ''].filter(Boolean).join(' y ')}
                </Text>
                <Text style={s.mut}>{e.latitud != null ? `${e.latitud.toFixed(5)}, ${e.longitud.toFixed(5)}` : 'Sin ubicación'}</Text>
              </View>
            </View>
          )}
        />
      )}

      {tab === 'ajustes' && (
        <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
          <View style={s.card}>
            <Text style={s.lab}>Dirección del servidor</Text>
            <TextInput style={s.input} value={servidor} autoCapitalize="none" autoCorrect={false} keyboardType="url"
              placeholder="https://xxxx.lhr.life" onChangeText={(t) => { setServidor(t); guardar('servidor', t); }} />
            <Text style={s.lab}>Sesión iniciada como</Text>
            <Text style={{ color: C.tx, fontWeight: '700' }}>{email}</Text>
            <Pressable style={[s.btn, s.sec, { marginTop: 14 }]} onPress={async () => {
              try { const r = await fetch(base + '/healthz'); Alert.alert(r.ok ? 'Servidor listo' : 'Respondió ' + r.status); }
              catch (_) { Alert.alert('No se pudo conectar', 'Revisa la dirección y tu internet.'); }
            }}><Text style={s.secT}>Probar conexión</Text></Pressable>
            <Pressable style={[s.btn, { marginTop: 8, backgroundColor: C.mal }]} onPress={cerrarSesion}>
              <Text style={s.btnT}>Cerrar sesión</Text>
            </Pressable>
          </View>
          <Text style={s.mut}>La cuenta se crea desde esta app o desde la web. Las capturas muestran personas y ubicaciones: úsalas con autorización de la empresa.</Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  head: { backgroundColor: C.head, paddingHorizontal: 16, paddingTop: 36, paddingBottom: 14 },
  h1: { color: '#fff', fontSize: 21, fontWeight: '800' },
  h2: { color: '#cfe0f3', fontSize: 12.5, marginTop: 2 },
  tabs: { flexDirection: 'row', backgroundColor: C.card, borderBottomWidth: 1, borderColor: C.bd },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center', borderBottomWidth: 3, borderColor: 'transparent' },
  tabOn: { borderColor: C.ac }, tabT: { color: C.mut, fontWeight: '600' }, tabTOn: { color: C.ac },
  body: { padding: 14, paddingBottom: 40, gap: 12 },
  card: { backgroundColor: C.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: C.bd },
  chips: { flexDirection: 'row' },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#e8eef6', paddingHorizontal: 12, paddingVertical: 7, borderRadius: 99 },
  chipT: { fontSize: 12.5, color: C.tx }, dot: { width: 9, height: 9, borderRadius: 5 },
  lab: { color: C.mut, fontSize: 12.5, marginTop: 12, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: C.bd, borderRadius: 10, padding: 12, fontSize: 16, color: C.tx, backgroundColor: C.bg },
  btn: { backgroundColor: C.ac, borderRadius: 14, paddingVertical: 16, alignItems: 'center' },
  btnT: { color: '#fff', fontWeight: '700', fontSize: 16.5 },
  sec: { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: C.ac, paddingVertical: 13 },
  secT: { color: C.ac, fontWeight: '700', fontSize: 15.5 },
  dos: { flexDirection: 'row', gap: 8, marginTop: 8 },
  badge: { alignSelf: 'flex-start', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 99 },
  badgeT: { color: '#fff', fontWeight: '800', fontSize: 16 },
  stats: { flexDirection: 'row', gap: 8, marginVertical: 12 },
  stat: { flex: 1, backgroundColor: '#e8eef6', borderRadius: 12, paddingVertical: 10, alignItems: 'center' },
  statN: { fontSize: 26, fontWeight: '800', color: C.tx }, statL: { fontSize: 11.5, color: C.mut },
  img: { width: '100%', height: 320, borderRadius: 12, marginTop: 8, backgroundColor: '#000' },
  mut: { color: C.mut, fontSize: 13.5, marginVertical: 4 },
  fila: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  mini: { width: 84, height: 84, borderRadius: 10, backgroundColor: '#000' },
  evT: { fontWeight: '800', color: C.tx, fontSize: 15 },
});
