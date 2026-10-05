// Modo claro/oscuro. Se carga en <head> (antes de pintar) para evitar el parpadeo de tema equivocado.
// Orden de prioridad: elección guardada del usuario > preferencia del sistema operativo.
(function () {
  const KEY = "theme";
  const root = document.documentElement;

  function stored() {
    try {
      const v = localStorage.getItem(KEY);
      return v === "dark" || v === "light" ? v : null;
    } catch {
      return null; // localStorage bloqueado: seguimos sin guardar
    }
  }

  function systemTheme() {
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.textContent = theme === "dark" ? "☀️" : "🌙";
      const tr = window.t || ((k) => k); // t() llega con i18n.js; antes de eso, la clave
      btn.setAttribute("aria-label", tr(theme === "dark" ? "theme.toLight" : "theme.toDark"));
    }
  }

  apply(stored() || systemTheme());

  document.addEventListener("DOMContentLoaded", () => {
    apply(root.getAttribute("data-theme"));
    document.getElementById("theme-toggle").addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      try { localStorage.setItem(KEY, next); } catch { /* sin almacenamiento: solo dura esta visita */ }
    });
  });

  document.addEventListener("langchange", () => apply(root.getAttribute("data-theme"))); // retraduce el aria-label

  // Si el usuario nunca eligió, sigue los cambios del sistema.
  if (window.matchMedia) {
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (!stored()) apply(systemTheme());
    });
  }
})();
