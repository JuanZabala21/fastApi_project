// Multi-idioma sin librerías. Idioma por defecto: inglés. La elección se guarda en localStorage.
//
// En el HTML se marcan los textos con atributos data-i18n*:
//   data-i18n="clave"               -> textContent
//   data-i18n-placeholder="clave"   -> placeholder
//   data-i18n-title="clave"         -> title
//   data-i18n-aria-label="clave"    -> aria-label
// En JS se usa t("clave", { n: 3 }). Para añadir un idioma: copia un bloque de I18N y tradúcelo.
(function () {
  const KEY = "lang";
  const DEFAULT = "en";

  const I18N = {
    en: {
      "lang.label": "Language",
      "theme.toLight": "Switch to light mode",
      "theme.toDark": "Switch to dark mode",
      "user.menu": "User menu",
      "user.logout": "⎋ Log out",

      "auth.login": "Log in",
      "auth.register": "Sign up",
      "auth.email": "Email",
      "auth.name": "Name",
      "auth.password": "Password",
      "auth.createAccount": "Create account",
      "auth.expired": "Session expired, please log in again.",
      "auth.loggedOut": "Signed out.",

      "todo.new": "New task…",
      "todo.dayTitle": "Day you'll do it",
      "todo.priority": "Priority",
      "todo.add": "Add",
      "todo.day": "Day",
      "todo.deleteOne": "Delete {title}",
      "todo.empty": "No tasks.",
      "todo.deleteAll": "🗑 Delete all",

      "prio.high": "High",
      "prio.medium": "Medium",
      "prio.low": "Low",

      "filters.title": "Filters",
      "filters.all": "All",
      "filters.pending": "Pending",
      "filters.done": "Done",
      "filters.priority": "Priority",
      "filters.sortBy": "Sort by",
      "filters.sortDate": "Date",
      "filters.sortPriority": "Priority",
      "filters.sortCreated": "Created",
      "filters.from": "From",
      "filters.to": "To",
      "filters.date": "Date",
      "filters.withDate": "With date",
      "filters.noDate": "No date",
      "filters.overdue": "Overdue only",
      "filters.reset": "Clear filters",

      "chat.welcome": "Hi! I can add, organize and plan your tasks. Try: \"plan my week, most urgent first\".",
      "chat.placeholder": "Message the assistant…",
      "chat.send": "Send",
      "chat.clear": "New conversation",
      "chat.thinking": "Thinking…",
      "chat.expired": "Session expired.",

      "dlg.title": "⚠️ Delete all tasks?",
      "dlg.text1": "All your tasks will be deleted, including the ones hidden by the filters.",
      "dlg.text2": "This cannot be undone.",
      "dlg.cancel": "Cancel",
      "dlg.confirm": "Yes, delete all",
      "dlg.deletedOne": "1 task deleted.",
      "dlg.deletedMany": "{n} tasks deleted.",

      "error.generic": "Error {status}",
    },

    es: {
      "lang.label": "Idioma",
      "theme.toLight": "Cambiar a modo claro",
      "theme.toDark": "Cambiar a modo oscuro",
      "user.menu": "Menú de usuario",
      "user.logout": "⎋ Cerrar sesión",

      "auth.login": "Entrar",
      "auth.register": "Registrarse",
      "auth.email": "Email",
      "auth.name": "Nombre",
      "auth.password": "Contraseña",
      "auth.createAccount": "Crear cuenta",
      "auth.expired": "Sesión caducada, vuelve a entrar.",
      "auth.loggedOut": "Sesión cerrada.",

      "todo.new": "Nueva tarea…",
      "todo.dayTitle": "Día en que la harás",
      "todo.priority": "Prioridad",
      "todo.add": "Añadir",
      "todo.day": "Día",
      "todo.deleteOne": "Borrar {title}",
      "todo.empty": "No hay tareas.",
      "todo.deleteAll": "🗑 Eliminar todas",

      "prio.high": "Alta",
      "prio.medium": "Media",
      "prio.low": "Baja",

      "filters.title": "Filtros",
      "filters.all": "Todas",
      "filters.pending": "Pendientes",
      "filters.done": "Hechas",
      "filters.priority": "Prioridad",
      "filters.sortBy": "Ordenar por",
      "filters.sortDate": "Fecha",
      "filters.sortPriority": "Prioridad",
      "filters.sortCreated": "Creación",
      "filters.from": "Desde",
      "filters.to": "Hasta",
      "filters.date": "Fecha",
      "filters.withDate": "Con fecha",
      "filters.noDate": "Sin fecha",
      "filters.overdue": "Solo vencidas",
      "filters.reset": "Limpiar filtros",

      "chat.welcome": "¡Hola! Puedo agregar, ordenar y planificar tus tareas. Prueba: \"organiza mi semana, lo urgente primero\".",
      "chat.placeholder": "Escríbele al asistente…",
      "chat.send": "Enviar",
      "chat.clear": "Nueva conversación",
      "chat.thinking": "Pensando…",
      "chat.expired": "Sesión caducada.",

      "dlg.title": "⚠️ ¿Eliminar todas las tareas?",
      "dlg.text1": "Se borrarán todas tus tareas, también las que ahora no ves por los filtros.",
      "dlg.text2": "Esta acción no se puede deshacer.",
      "dlg.cancel": "Cancelar",
      "dlg.confirm": "Sí, eliminar todas",
      "dlg.deletedOne": "Se eliminó 1 tarea.",
      "dlg.deletedMany": "Se eliminaron {n} tareas.",

      "error.generic": "Error {status}",
    },
  };

  // Mensajes que devuelve la API (en inglés) y su traducción. Lo que no esté aquí se muestra tal cual.
  const API_ERRORS = {
    es: {
      "Incorrect email or password": "Email o contraseña incorrectos",
      "Email already registered": "Ese email ya está registrado",
      "Too many failed attempts, try again later": "Demasiados intentos fallidos, inténtalo más tarde",
      "Assistant message limit reached, try again later": "Límite de mensajes del asistente alcanzado, inténtalo más tarde",
      "The assistant is not configured (missing ANTHROPIC_API_KEY)": "El asistente no está configurado (falta ANTHROPIC_API_KEY)",
      "The assistant is unavailable right now, try again in a moment": "El asistente no está disponible ahora, inténtalo en un momento",
      "Could not validate credentials": "No se pudieron validar las credenciales",
    },
  };

  function stored() {
    try {
      const v = localStorage.getItem(KEY);
      return v in I18N ? v : null;
    } catch {
      return null; // localStorage bloqueado
    }
  }

  let lang = stored() || DEFAULT;

  // t("clave", {n: 3}) -> texto en el idioma actual (si falta la clave, cae a inglés y luego a la propia clave)
  function t(key, vars = {}) {
    const text = (I18N[lang] && I18N[lang][key]) ?? I18N[DEFAULT][key] ?? key;
    return text.replace(/\{(\w+)\}/g, (_, name) => (name in vars ? vars[name] : `{${name}}`));
  }

  function translateApiError(message) {
    return (API_ERRORS[lang] && API_ERRORS[lang][message]) || message;
  }

  function apply() {
    document.documentElement.lang = lang;
    const targets = [
      ["data-i18n", (el, v) => (el.textContent = v)],
      ["data-i18n-placeholder", (el, v) => el.setAttribute("placeholder", v)],
      ["data-i18n-title", (el, v) => el.setAttribute("title", v)],
      ["data-i18n-aria-label", (el, v) => el.setAttribute("aria-label", v)],
    ];
    for (const [attr, set] of targets) {
      document.querySelectorAll(`[${attr}]`).forEach((el) => set(el, t(el.getAttribute(attr))));
    }
    // Bandera del botón + marca del idioma activo dentro de la lista
    document.getElementById("lang-current").setAttribute("href", lang === "es" ? "#flag-es" : "#flag-us");
    document.querySelectorAll("#lang-list [data-lang]").forEach((item) => {
      item.setAttribute("aria-checked", String(item.dataset.lang === lang));
    });
    document.dispatchEvent(new CustomEvent("langchange", { detail: lang })); // app.js y theme.js se reajustan
  }

  function setLang(next) {
    if (!(next in I18N)) return;
    lang = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* sin almacenamiento: solo dura esta visita */
    }
    apply();
  }

  window.t = t;
  window.translateApiError = translateApiError;
  window.getLang = () => lang;

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("lang-btn");
    const list = document.getElementById("lang-list");
    const close = () => {
      list.hidden = true;
      btn.setAttribute("aria-expanded", "false");
    };
    btn.addEventListener("click", (event) => {
      event.stopPropagation(); // que no lo cierre el "clic fuera"
      const open = list.hidden;
      list.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      if (open) list.querySelector('[aria-checked="true"]').focus();
    });
    list.querySelectorAll("[data-lang]").forEach((item) =>
      item.addEventListener("click", () => {
        setLang(item.dataset.lang);
        close();
        btn.focus();
      }),
    );
    document.addEventListener("click", (event) => {
      if (!document.getElementById("lang-menu").contains(event.target)) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !list.hidden) {
        close();
        btn.focus();
      }
    });
    apply();
  });
})();
