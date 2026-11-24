import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Image, Keyboard, Pressable, SafeAreaView, ScrollView,
  StyleSheet, Text, TextInput, View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';

const C = { bg: '#eef2f7', card: '#fff', tx: '#16202c', mut: '#667487', bd: '#dbe3ec', ac: '#0f6fd1',
  ok: '#168a4a', mal: '#d23b3b', warn: '#c77d0a', head: '#0f3d63' };

const limpiarUrl = (u) => (u || '').trim().replace(/\/+$/, '');
const basic = (clave) => 'Basic ' + btoa('epp:' + clave);

export default function App() {
  const [tab, setTab] = useState('captura');
  const [servidor, setServidor] = useState('');
  const [clave, setClave] = useState('');
  const [zona, setZona] = useState('Zona 1');
  const [cargando, setCargando] = useState(false);
  const [estado, setEstado] = useState('');
  const [gps, setGps] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [eventos, setEventos] = useState([]);
  const [errorEv, setErrorEv] = useState('');

  useEffect(() => {
    AsyncStorage.multiGet(['servidor', 'clave', 'zona']).then((p) => {
      const d = Object.fromEntries(p);
      if (d.servidor) setServidor(d.servidor);
      if (d.clave) setClave(d.clave);
      if (d.zona) setZona(d.zona);
    });
  }, []);
  const guardar = (k, v) => AsyncStorage.setItem(k, v).catch(() => {});
  const headers = { Authorization: basic(clave) };
  const base = limpiarUrl(servidor);

  const ubicar = useCallback(async () => {
    const p = await Location.requestForegroundPermissionsAsync();
    if (p.status !== 'granted') { setGps(null); return null; }
    try {
      const l = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const g = { lat: l.coords.latitude, lon: l.coords.longitude, prec: l.coords.accuracy };
      setGps(g);
      return g;
    } catch (e) { setGps(null); return null; }
  }, []);
  useEffect(() => { ubicar(); }, [ubicar]);

  async function enviar(asset) {
    if (!base) { Alert.alert('Falta el servidor', 'Escribe la dirección del servidor en Ajustes.'); setTab('ajustes'); return; }
    setCargando(true); setResultado(null); setEstado('Obteniendo ubicación…');
    try {
      const g = await ubicar();
      setEstado('Analizando…');
      const esVideo = asset.type === 'video' || (asset.mimeType || '').startsWith('video');
      const fd = new FormData();
      fd.append('archivo', { uri: asset.uri, name: asset.fileName || (esVideo ? 'video.mp4' : 'foto.jpg'),
        type: asset.mimeType || (esVideo ? 'video/mp4' : 'image/jpeg') });
      fd.append('zona', zona.trim() || 'Zona 1');
      if (g) { fd.append('lat', String(g.lat)); fd.append('lon', String(g.lon)); fd.append('precision', String(g.prec ?? '')); }
      const r = await fetch(base + '/api/analizar', { method: 'POST', headers, body: fd });
      if (r.status === 401) throw new Error('Usuario o clave incorrectos (revisa Ajustes).');
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || 'Error ' + r.status);
      setResultado(j);
    } catch (e) {
      Alert.alert('No se pudo analizar', String(e.message || e));
    } finally { setCargando(false); setEstado(''); }
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
    if (!base) { setErrorEv('Configura el servidor en Ajustes.'); return; }
    try {
      const r = await fetch(base + '/api/eventos', { headers: { Authorization: basic(clave) } });
      if (r.status === 401) throw new Error('Usuario o clave incorrectos.');
      const j = await r.json();
      setEventos(j.eventos || []); setErrorEv('');
    } catch (e) { setErrorEv(String(e.message || e)); }
  }, [base, clave]);
  useEffect(() => { if (tab === 'eventos') cargarEventos(); }, [tab, cargarEventos]);

  const alerta = resultado && resultado.incumplimientos > 0;
  const sinP = resultado && resultado.personas === 0;
  const colorRes = alerta ? C.mal : sinP ? C.mut : C.ok;
  const tituloRes = alerta ? '⚠️ ALERTA: falta EPP' : sinP ? 'Sin personas detectadas' : '✅ EPP completo';

  return (
    <SafeAreaView style={s.safe}>
      <StatusBar style="light" />
      <View style={s.head}>
        <Text style={s.h1}>🦺 Reporte de EPP</Text>
        <Text style={s.h2}>Foto o video con ubicación → alerta de casco y chaleco</Text>
      </View>
      <View style={s.tabs}>
        {[['captura', '📷 Capturar'], ['eventos', '📋 Eventos'], ['ajustes', '⚙️ Ajustes']].map(([k, t]) => (
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
            <Pressable style={s.btn} onPress={foto} disabled={cargando}><Text style={s.btnT}>📷  Tomar foto</Text></Pressable>
            <View style={s.dos}>
              <Pressable style={[s.btn, s.sec, { flex: 1 }]} onPress={video} disabled={cargando}><Text style={s.secT}>🎥  Video</Text></Pressable>
              <Pressable style={[s.btn, s.sec, { flex: 1 }]} onPress={galeria} disabled={cargando}><Text style={s.secT}>🖼️  Galería</Text></Pressable>
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
              {!!resultado.imagen && <Image source={{ uri: base + resultado.imagen, headers }} style={s.img} resizeMode="contain" />}
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
              {!!e.imagen && <Image source={{ uri: base + e.imagen, headers }} style={s.mini} />}
              <View style={{ flex: 1 }}>
                <Text style={s.evT}>#{e.id} · {e.zona}</Text>
                <Text style={s.mut}>{String(e.momento).replace('T', ' ')}</Text>
                <Text style={{ color: C.mal, fontWeight: '700' }}>
                  {[e.falta_casco ? 'sin casco' : '', e.falta_chaleco ? 'sin chaleco' : ''].filter(Boolean).join(' y ')}
                </Text>
                <Text style={s.mut}>{e.latitud != null ? `📍 ${e.latitud.toFixed(5)}, ${e.longitud.toFixed(5)}` : 'Sin ubicación'}</Text>
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
            <Text style={s.lab}>Clave de acceso (usuario: epp)</Text>
            <TextInput style={s.input} value={clave} autoCapitalize="none" autoCorrect={false} secureTextEntry
              onChangeText={(t) => { setClave(t); guardar('clave', t); }} />
            <Pressable style={[s.btn, { marginTop: 14 }]} onPress={async () => {
              try { const r = await fetch(base + '/healthz'); Alert.alert(r.ok ? 'Servidor listo ✅' : 'Respondió ' + r.status); }
              catch (e) { Alert.alert('No se pudo conectar', 'Revisa la dirección y tu internet.'); }
            }}><Text style={s.btnT}>Probar conexión</Text></Pressable>
          </View>
          <Text style={s.mut}>La dirección y la clave las da quien ejecuta el servidor (python app.py --publico). Las capturas muestran personas y ubicaciones: úsalas con autorización de la empresa.</Text>
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
