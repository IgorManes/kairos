/*
  Service worker do Kairos: roda em segundo plano no aparelho, mesmo com o app fechado.
  Só faz duas coisas: mostrar o aviso que chega por push e, no toque, abrir o Kairos na
  tela certa. NÃO guarda páginas em cache (o Kairos depende do PC de qualquer forma).
  Servido em /sw.js (raiz) para valer no app inteiro.
*/

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", evento => evento.waitUntil(self.clients.claim()));

self.addEventListener("push", evento => {
  const aviso = evento.data ? evento.data.json() : {};
  evento.waitUntil(
    self.registration.showNotification(aviso.title || "Kairos", {
      body: aviso.body || "",
      icon: "/static/img/kairos-app-192.png",
      lang: "pt-BR",
      data: { url: aviso.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", evento => {
  evento.notification.close();
  const url = new URL(evento.notification.data?.url || "/", self.location.origin).href;
  evento.waitUntil((async () => {
    // App já aberto: traz para a frente e vai para a tela do aviso.
    const janelas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const janela of janelas) {
      try {
        await janela.focus();
        await janela.navigate(url);
        return;
      } catch { /* janela que não aceita navegar: tenta a próxima */ }
    }
    return self.clients.openWindow(url);
  })());
});
