// 앱 화면만 기억해 두고(네트워크 먼저, 끊기면 저장본), 음성은 그대로 스트리밍합니다.
const CACHE = 'thai-srt-work-v1';
const SHELL = ['./', './index.html', './manifest.webmanifest', './talks.json', './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;
  if (r.headers.has('range') || /\.(mp3|m4a|aac|wav|ogg|oga|opus|flac)$/i.test(u.pathname)) return;
  e.respondWith(
    fetch(r).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(r, copy)); }
      return res;
    }).catch(() => caches.match(r))
  );
});
