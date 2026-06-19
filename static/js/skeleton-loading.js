/**
 * Finaliza o estado de carregamento visual quando a página já está pronta.
 */

(function(){
  let finished = false;

  /** Finishloading. Usada pelo fluxo principal da aplicação. */
  const finishLoading = () => {
    if (finished) return;
    finished = true;
    document.body?.classList.remove('loading');
    window.dispatchEvent(new CustomEvent('app:skeleton-hidden'));
  };

  if (document.readyState === 'complete') {
    requestAnimationFrame(() => requestAnimationFrame(finishLoading));
  } else {
    window.addEventListener('load', () => requestAnimationFrame(() => requestAnimationFrame(finishLoading)), { once: true });
  }

  setTimeout(finishLoading, 1800);
})();
