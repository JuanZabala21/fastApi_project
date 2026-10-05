// Frontend mínimo sin frameworks: habla con la API por fetch(). Los textos salen de i18n.js (t()).
// Seguridad: el contenido de los todos se pinta con textContent (nunca innerHTML) para evitar XSS,
// y el token vive en sessionStorage (se borra al cerrar la pestaña).

const $ = (id) => document.getElementById(id);
const TOKEN_KEY = "token";
const FILTER_IDS = ["f-priority", "f-sort", "f-from", "f-to", "f-scheduled", "f-overdue"];

let mode = "login"; // "login" | "register"
let filter = "all"; // estado: "all" | "true" (hechas) | "false" (pendientes)

const getToken = () => sessionStorage.getItem(TOKEN_KEY);

function showMessage(text, ok = false) {
  const el = $("message");
  el.textContent = text;
  el.className = ok ? "ok" : "";
}

// Wrapper de fetch: añade el token, y si la API responde 401 cierra la sesión.
async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form); // /auth/login espera form-urlencoded
  } else if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 401 && token) {
    logout(t("auth.expired"));
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    // FastAPI devuelve detail como texto o como lista (errores 422)
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(translateApiError(detail) || t("error.generic", { status: res.status }));
  }
  return res.status === 204 ? null : res.json();
}

function setMode(next) {
  mode = next;
  $("tab-login").classList.toggle("active", mode === "login");
  $("tab-register").classList.toggle("active", mode === "register");
  $("name-row").hidden = mode !== "register";
  $("auth-submit").textContent = mode === "login" ? t("auth.login") : t("auth.createAccount");
  $("password").autocomplete = mode === "login" ? "current-password" : "new-password";
  showMessage("");
}

async function login(email, password) {
  const data = await api("/auth/login", { method: "POST", form: { username: email, password } });
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
}

async function onAuthSubmit(event) {
  event.preventDefault();
  const email = $("email").value.trim();
  const password = $("password").value;
  try {
    if (mode === "register") {
      await api("/users", { method: "POST", body: { email, password, full_name: $("full-name").value.trim() || null } });
    }
    await login(email, password);
    $("password").value = "";
    await showTodos();
  } catch (err) {
    showMessage(err.message);
  }
}

function logout(message = "") {
  document.body.classList.remove("logged-in"); // vuelve a la tarjeta pequeña del login
  closeUserMenu();
  $("user-menu").hidden = true;
  sessionStorage.removeItem(TOKEN_KEY);
  $("todos-view").hidden = true;
  $("auth-view").hidden = false;
  showMessage(message, true);
}

async function showTodos() {
  const me = await api("/auth/me");
  const label = me.full_name || me.email;
  $("user-name").textContent = label;
  $("user-email").textContent = me.email;
  $("user-initial").textContent = label.trim().charAt(0).toUpperCase() || "?";
  $("user-menu").hidden = false;
  document.body.classList.add("logged-in"); // la tarjeta se ensancha
  $("auth-view").hidden = true;
  $("todos-view").hidden = false;
  showMessage("");
  await loadTodos();
}

// Fecha de hoy en hora local, formato YYYY-MM-DD (igual que <input type="date">).
function today() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Construye la query con los filtros de la pantalla; los vacíos no se envían.
function buildQuery() {
  const params = new URLSearchParams({ limit: "100", sort_by: $("f-sort").value });
  if (filter !== "all") params.set("done", filter);
  const optional = { priority: "f-priority", due_from: "f-from", due_to: "f-to", has_due_date: "f-scheduled" };
  for (const [name, id] of Object.entries(optional)) {
    if ($(id).value) params.set(name, $(id).value);
  }
  if ($("f-overdue").checked) params.set("overdue", "true");
  return params.toString();
}

// Muestra en el título del acordeón cuántos filtros hay activos (así se ve aunque esté cerrado).
function updateFilterCount() {
  const active =
    (filter !== "all" ? 1 : 0) +
    ["f-priority", "f-from", "f-to", "f-scheduled"].filter((id) => $(id).value).length +
    ($("f-overdue").checked ? 1 : 0);
  $("f-count").textContent = active;
  $("f-count").hidden = active === 0;
  return active;
}

async function loadTodos() {
  const activeFilters = updateFilterCount();
  const todos = await api(`/todos?${buildQuery()}`);
  const list = $("todo-list");
  list.replaceChildren(...todos.map(renderTodo));
  $("empty").hidden = todos.length > 0;

  // "Eliminar todas" solo tiene sentido si existe alguna tarea. Si los filtros dejan la vista vacía,
  // comprobamos si hay tareas fuera del filtro para no esconder el botón por error.
  let hasAny = todos.length > 0;
  if (!hasAny && activeFilters > 0) hasAny = (await api("/todos?limit=1")).length > 0;
  document.querySelector(".list-actions").hidden = !hasAny;
}

function renderTodo(todo) {
  const li = document.createElement("li");
  const isOverdue = !todo.done && todo.due_date && todo.due_date < today();
  li.className = [todo.done ? "done" : "", isOverdue ? "overdue" : ""].join(" ").trim();

  const patch = (body) => run(() => api(`/todos/${todo.id}`, { method: "PATCH", body }));

  const check = document.createElement("input");
  check.type = "checkbox";
  check.checked = todo.done;
  check.addEventListener("change", () => patch({ done: check.checked }));

  const title = document.createElement("span");
  title.className = "title";
  title.textContent = todo.title; // textContent: el texto nunca se interpreta como HTML

  // Día planificado: vaciar el campo quita la fecha (null en la API).
  const when = document.createElement("input");
  when.type = "date";
  when.className = "when";
  when.value = todo.due_date || "";
  when.setAttribute("aria-label", t("todo.day"));
  when.addEventListener("change", () => patch({ due_date: when.value || null }));

  const prio = document.createElement("select");
  prio.className = `prio ${todo.priority}`;
  prio.setAttribute("aria-label", t("todo.priority"));
  for (const value of ["high", "medium", "low"]) {
    const label = t(`prio.${value}`);
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    opt.selected = value === todo.priority;
    prio.append(opt);
  }
  prio.addEventListener("change", () => patch({ priority: prio.value }));

  const del = document.createElement("button");
  del.type = "button";
  del.className = "del";
  del.textContent = "✕";
  del.setAttribute("aria-label", t("todo.deleteOne", { title: todo.title }));
  del.addEventListener("click", () => run(() => api(`/todos/${todo.id}`, { method: "DELETE" })));

  li.append(check, title, when, prio, del);
  return li;
}

// Ejecuta una acción contra la API y refresca la lista.
async function run(action) {
  try {
    await action();
    await loadTodos();
  } catch (err) {
    if (err.message !== "unauthorized") showMessage(err.message);
  }
}

async function onAddTodo(event) {
  event.preventDefault();
  const input = $("new-title");
  const title = input.value.trim();
  if (!title) return;
  const body = { title, priority: $("new-priority").value };
  if ($("new-date").value) body.due_date = $("new-date").value;
  await run(() => api("/todos", { method: "POST", body }));
  input.value = "";
}

function onFilterClick(event) {
  const btn = event.target.closest("button[data-filter]");
  if (!btn) return;
  filter = btn.dataset.filter;
  document.querySelectorAll(".filters button").forEach((b) => b.classList.toggle("active", b === btn));
  run(async () => {});
}

function resetFilters() {
  for (const id of ["f-priority", "f-from", "f-to", "f-scheduled"]) $(id).value = "";
  $("f-overdue").checked = false;
  $("f-sort").value = "due_date";
  run(async () => {});
}

$("tab-login").addEventListener("click", () => setMode("login"));
$("tab-register").addEventListener("click", () => setMode("register"));
$("auth-form").addEventListener("submit", onAuthSubmit);
$("todo-form").addEventListener("submit", onAddTodo);
$("logout").addEventListener("click", () => logout(t("auth.loggedOut")));

// --- Menú de usuario (desplegable del avatar) ---
function closeUserMenu() {
  $("user-dropdown").hidden = true;
  $("user-btn").setAttribute("aria-expanded", "false");
}

$("user-btn").addEventListener("click", (event) => {
  event.stopPropagation(); // que el clic no llegue al "cerrar al hacer clic fuera"
  const open = $("user-dropdown").hidden;
  $("user-dropdown").hidden = !open;
  $("user-btn").setAttribute("aria-expanded", String(open));
  if (open) $("logout").focus();
});
document.addEventListener("click", (event) => {
  if (!$("user-menu").contains(event.target)) closeUserMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("user-dropdown").hidden) {
    closeUserMenu();
    $("user-btn").focus();
  }
});
document.querySelector(".filters").addEventListener("click", onFilterClick);
FILTER_IDS.forEach((id) => $(id).addEventListener("change", () => run(async () => {})));
$("f-reset").addEventListener("click", resetFilters);

// Si ya había sesión en esta pestaña, entra directo.
if (getToken()) {
  document.body.classList.add("logged-in"); // evita el salto de tamaño al recargar con sesión
  showTodos().catch(() => logout());
}

// --- Asistente con IA -------------------------------------------------------------------------
// La conversación vive aquí (el servidor no guarda nada) y se envía completa en cada mensaje.
let chatHistory = []; // [{role: "user" | "assistant", content}]
const MAX_HISTORY = 20; // igual que el límite del servidor

function addChatLine(kind, text) {
  const p = document.createElement("p");
  p.className = kind;
  p.textContent = text; // textContent: la respuesta del modelo nunca se interpreta como HTML
  $("chat-log").append(p);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
  return p;
}

async function onChatSubmit(event) {
  event.preventDefault();
  const input = $("chat-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addChatLine("me", text);
  chatHistory.push({ role: "user", content: text });
  chatHistory = chatHistory.slice(-MAX_HISTORY);

  $("chat-send").disabled = true;
  const thinking = addChatLine("bot", t("chat.thinking"));
  try {
    const data = await api("/assistant/chat", { method: "POST", body: { messages: chatHistory, lang: getLang() } });
    thinking.textContent = data.reply;
    chatHistory.push({ role: "assistant", content: data.reply });
    if (data.changed) await loadTodos(); // el asistente tocó tareas: refresca la lista
  } catch (err) {
    thinking.className = "err";
    thinking.textContent = err.message === "unauthorized" ? t("chat.expired") : err.message;
    chatHistory.pop(); // el mensaje no se procesó: no lo dejes en el historial
  } finally {
    $("chat-send").disabled = false;
    input.focus();
  }
}

function clearChat() {
  chatHistory = [];
  const welcome = document.createElement("p");
  welcome.className = "bot";
  welcome.id = "chat-welcome";
  welcome.setAttribute("data-i18n", "chat.welcome"); // se retraduce al cambiar de idioma
  welcome.textContent = t("chat.welcome");
  $("chat-log").replaceChildren(welcome);
}

$("chat-form").addEventListener("submit", onChatSubmit);
$("chat-clear").addEventListener("click", clearChat);

// --- Eliminar todas las tareas (con modal de confirmación) -------------------------------------
const dialog = $("confirm-dialog");

$("delete-all").addEventListener("click", () => dialog.showModal()); // el foco empieza en "Cancelar"

// Clic fuera de la caja (en el fondo oscuro) = cancelar.
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});

$("dlg-confirm").addEventListener("click", async () => {
  const confirmBtn = $("dlg-confirm");
  confirmBtn.disabled = true; // evita un doble clic mientras se borra
  try {
    const { deleted } = await api("/todos?confirm=true", { method: "DELETE" });
    dialog.close();
    await loadTodos();
    showMessage(deleted === 1 ? t("dlg.deletedOne") : t("dlg.deletedMany", { n: deleted }), true);
  } catch (err) {
    dialog.close();
    if (err.message !== "unauthorized") showMessage(err.message);
  } finally {
    confirmBtn.disabled = false;
  }
});

// --- Cambio de idioma: re-pinta lo que se genera desde JS (el HTML estático lo traduce i18n.js) ---
document.addEventListener("langchange", () => {
  setMode(mode); // texto del botón de enviar del login
  if (getToken() && !$("todos-view").hidden) loadTodos().catch(() => {}); // etiquetas de prioridad y aria
});
