# FastAPI Basics: usuarios, login y todos

API de aprendizaje con FastAPI. Incluye:

- CRUD de **usuarios** guardados en **PostgreSQL**
- **Login** con JWT (contraseñas hasheadas con Argon2)
- CRUD de **todos** en PostgreSQL, privados: cada usuario solo ve los suyos
- Tests automáticos con pytest

## Con Docker (app + base de datos)

```powershell
copy .env.example .env      # y rellena SECRET_KEY y, si quieres el chat, ANTHROPIC_API_KEY
docker compose up -d --build
```

Abre http://127.0.0.1:8000/app. Un solo comando levanta PostgreSQL y la app (imagen en `Dockerfile`).

- **Secretos:** nunca van dentro de la imagen. `.dockerignore` deja fuera `.env`, `.git`, `.venv` y `tests`; Compose los inyecta al arrancar desde tu `.env` (ignorado por git).
- **Base de datos:** dentro de Docker la app usa `db:5432` (Compose sobrescribe `DATABASE_URL`); tu `.env` puede seguir con `localhost:5433` para correr uvicorn en tu máquina.
- **Espera a Postgres:** la app arranca solo cuando la base está lista (`healthcheck` + `depends_on`).
- **Seguridad del contenedor:** corre como usuario no root (`appuser`) y tiene `HEALTHCHECK`.
- **Un solo worker** a propósito: los límites de login y del asistente viven en memoria (con varios workers harían falta Redis).
- **Puertos y contraseña** configurables: `APP_PORT`, `DB_PORT`, `POSTGRES_PASSWORD` (variables de entorno o `.env`).
- **Datos:** el volumen `pgdata` los conserva. El `name: fastapi_basics` de `docker-compose.yml` hace que se reutilice el volumen que ya tenías. Ver logs: `docker compose logs -f app`. Parar: `docker compose down` (con `-v` borra los datos).
- **Reconstruir tras cambios de código:** `docker compose up -d --build`.

## Cómo arrancarlo sin Docker para la app (desarrollo)

```powershell
# 1. Entorno virtual e instalación (solo la primera vez)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Solo la base de datos (PostgreSQL en Docker, puerto 5433)
docker compose up -d db

# 3. Servidor
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs
  (botón **Authorize** para iniciar sesión: usuario = email)

Tests: `pytest` (no necesitan Postgres, usan SQLite en memoria).

Apagar la base de datos: `docker compose down` (añade `-v` para borrar también los datos).

## Configuración (.env)

| Variable | Para qué sirve |
|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL |
| `SECRET_KEY` | Clave con la que se firman los JWT. Mantenerla secreta |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token (30 por defecto) |
| `ANTHROPIC_API_KEY` | **Secreto.** Clave de la API de Claude para el asistente. Vacía = asistente desactivado |
| `ANTHROPIC_MODEL` | Modelo del asistente (`claude-sonnet-5-5` por defecto; `claude-opus-5-5` es más capaz y más caro) |
| `ASSISTANT_EFFORT` | `low` / `medium` / `high`: cuánto razona (más bajo = más barato y rápido) |
| `ASSISTANT_MESSAGES_PER_HOUR` | Mensajes al asistente por usuario y hora (tope de gasto) |
| `ASSISTANT_MODE` | `mcp` (por defecto): el chat usa nuestro servidor MCP, FastAPI es el cliente MCP. `direct`: las herramientas corren dentro del proceso |
| `ASSISTANT_API_URL` | URL desde la que el servidor MCP llama a esta API (`http://127.0.0.1:8000`; debe coincidir con host y puerto de uvicorn) |
| `ASSISTANT_ALLOW_DELETE` | `true` deja que el asistente borre tareas (apagado por defecto) |

**Secretos y git:** los valores reales viven solo en `.env`, que está en `.gitignore` (igual que `.env.*`, `.mcp.json`, `*.key`, `*.pem`). `.env.example` sí se sube: es la plantilla y nunca lleva valores reales. Cópiala a `.env` y cambia `SECRET_KEY`. Comprobar antes de un commit: `git status` no debe mostrar `.env`; `git check-ignore -v .env` debe responder con la regla. Si una clave llegó a subirse alguna vez, regenérala: borrar el commit no basta.

**Protección automática:** `.githooks/pre-commit` bloquea el commit si detecta un `.env`, una clave (`sk-ant-…`, claves AWS/GitHub, claves privadas) o un valor en `ANTHROPIC_API_KEY` dentro de `.env.example`. Actívalo una vez por clone con `git config core.hooksPath .githooks`.

## Estructura

```
fastapi_basics/
├── app/
│   ├── main.py                    # punto de entrada
│   ├── core/
│   │   ├── config.py              # lee las variables del .env
│   │   └── security.py            # hash de contraseñas y JWT
│   ├── db/
│   │   └── session.py             # conexión a la BD y sesión por petición
│   ├── models/
│   │   ├── user.py                # tabla `users` (SQLAlchemy)
│   │   └── todo.py                # tabla `todos` (con clave foránea a users)
│   ├── schemas/
│   │   ├── user.py                # modelos Pydantic de usuarios y token
│   │   └── todo.py                # modelos Pydantic de todos
│   ├── services/
│   │   ├── user_service.py        # lógica de usuarios (consultas a la BD)
│   │   └── todo_service.py        # lógica de todos (siempre filtrada por dueño)
│   └── api/
│       ├── deps.py                # dependencias reutilizables
│       └── routes/
│           ├── auth.py            # /auth/login, /auth/me
│           ├── users.py           # /users
│           └── todos.py           # /todos
├── frontend/                      # index.html, app.js, style.css (servido en /app)
├── mcp_server/                    # servidor MCP (ver sección más abajo)
├── tests/
│   ├── test_todo_schedule.py      # fechas, prioridad, filtros, orden, migración de columnas
│   ├── test_security.py           # scopes, límite de login, cabeceras
│   ├── test_assistant.py          # asistente con cliente de Anthropic falso
│   ├── test_mcp_server.py         # herramientas MCP y sus protecciones
│   ├── conftest.py                # fixture `client` (BD SQLite en memoria)
│   ├── helpers.py                 # register / login / auth_header
│   ├── test_users.py              # registro, login, permisos
│   └── test_todos.py              # CRUD de todos y aislamiento entre usuarios
├── docker-compose.yml             # PostgreSQL local
├── requirements.txt
├── .env / .env.example
└── README.md
```

## Qué hace cada archivo

| Archivo | Responsabilidad |
|---|---|
| `app/main.py` | Crea la app FastAPI, registra los routers y crea las tablas al arrancar (`lifespan`). |
| `app/core/config.py` | Clase `Settings` (pydantic-settings). Lee `.env` y expone `settings.database_url`, `settings.secret_key`, etc. |
| `app/core/security.py` | `hash_password` / `verify_password` (Argon2) y `create_access_token` / `decode_access_token` (JWT). |
| `app/db/session.py` | Crea el `engine`, la clase `Base` de la que heredan los modelos, y `get_db()`: una sesión por petición que se cierra sola. |
| `app/models/user.py` | Clase `User`: columnas de la tabla `users` (id, email único, full_name, hashed_password, is_active) y la relación `todos`. |
| `app/models/todo.py` | Clase `Todo`: tabla `todos` (id, title, done, `user_id` → `users.id` con `ON DELETE CASCADE`). |
| `app/schemas/user.py` | Qué entra y qué sale de la API. `UserRead` no tiene campo de contraseña, así que nunca se filtra. |
| `app/schemas/todo.py` | Igual, para los todos. `from_attributes=True` permite devolver objetos del ORM directamente. |
| `app/services/user_service.py` | Funciones que hablan con la BD: crear, buscar, listar, actualizar, borrar y autenticar. Las rutas las llaman y no escriben SQL. |
| `app/services/todo_service.py` | Consultas de todos. Todas reciben `user_id`, así que es imposible leer o tocar el todo de otro usuario. |
| `app/api/deps.py` | `get_db` y `get_current_user` (valida el token y devuelve el usuario). |
| `app/api/routes/auth.py` | Login y "quién soy". |
| `app/api/routes/users.py` | Registro y CRUD de usuarios. |
| `app/api/routes/todos.py` | CRUD de todos del usuario autenticado. |
| `tests/` | Pruebas. `conftest.py` sustituye la BD real por SQLite con `dependency_overrides`. |

## Endpoints

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| POST | `/users` | Público | Registrar usuario |
| POST | `/auth/login` | Público | Devuelve el token (form: `username`=email, `password`) |
| GET | `/auth/me` | Token | Usuario actual |
| GET | `/users` | Token | Listar (`skip`, `limit`) |
| GET | `/users/{id}` | Token | Ver un usuario |
| PATCH | `/users/{id}` | Token, solo el propio | Actualizar |
| DELETE | `/users/{id}` | Token, solo el propio | Borrar |
| GET/POST | `/todos` | Token | Listar con filtros (ver abajo) / crear mis todos (`title`, `due_date`, `priority`) |
| GET/PATCH/DELETE | `/todos/{id}` | Token, solo los propios | Ver / actualizar / borrar |
| DELETE | `/todos?confirm=true` | Token completo (no el del MCP) | Borra TODAS mis tareas; sin `confirm=true` responde 400 |

Filtros de `GET /todos`: `done`, `priority` (`low|medium|high`), `due_from` / `due_to` (YYYY-MM-DD),
`overdue=true` (vencidas y sin hacer), `has_due_date` (true = con día, false = sin día),
`sort_by` (`id` | `due_date` = más próxima primero, sin fecha al final | `priority` = alta primero) y `limit` (1-100).
Para quitar el día de un todo: `PATCH` con `{"due_date": null}`.

Códigos habituales: `401` sin token o token inválido, `403` intentar modificar a otro usuario, `404` no existe (también si el todo es de otro usuario, para no revelar que existe), `409` email duplicado, `422` datos inválidos.

## Flujo de una petición

```
Cliente → main.py → router (api/routes) → dependencias (api/deps.py)
        → service (lógica y BD) → schema (respuesta validada) → Cliente
```

Ejemplo, `GET /auth/me`:
1. El router `auth.py` declara `current_user: CurrentUser`.
2. FastAPI ejecuta `get_current_user`, que lee el header `Authorization: Bearer <token>`.
3. Decodifica el JWT, saca el id y busca el usuario con `user_service.get_by_id`.
4. Si todo está bien, el endpoint devuelve el usuario filtrado por `UserRead`. Si no, responde 401.

## Conceptos clave para ir aprendiendo

- **Pydantic (schemas)**: valida los datos de entrada y da forma a los de salida.
- **SQLAlchemy (models)**: cada clase es una tabla y cada atributo, una columna.
- **Dependency injection (`Depends`)**: FastAPI ejecuta y entrega lo que el endpoint pide (sesión de BD, usuario actual). Se puede reemplazar en tests.
- **JWT**: un token firmado que dice "soy el usuario X hasta tal hora". El servidor no guarda sesiones; solo valida la firma.
- **Hash de contraseñas**: la contraseña real nunca se guarda ni se puede recuperar. Solo se compara su hash.

## Frontend de prueba

HTML + CSS + JS puro (sin frameworks) en `frontend/`, servido por la propia API: http://127.0.0.1:8000/app
Permite registrarse, entrar, crear tareas con día y prioridad, editarlas en la fila, filtrar (estado, prioridad, rango de fechas, vencidas, con/sin fecha), ordenar y borrar. El token se guarda en `sessionStorage`
y los textos se pintan con `textContent` (sin XSS). La CSP del frontend solo permite archivos propios.

Incluye **modo oscuro** (botón arriba a la derecha; recuerda tu elección y, si no has elegido, sigue el del sistema) y la caja del asistente.

## Idiomas

La interfaz está en **inglés (por defecto) y español**. Selector con banderas (EE. UU. / España, dibujadas en SVG porque Windows no muestra emojis de banderas) arriba a la derecha; la elección se guarda en el navegador.
Los textos viven en `frontend/i18n.js` (`I18N.en` / `I18N.es`): para añadir un idioma, copia un bloque y tradúcelo. El chat envía el idioma elegido (`lang`) y Claude responde en él.

## Asistente con IA (chat)

Caja de chat en el frontend. Le puedes decir "agrega comprar leche el viernes con prioridad alta" o "organiza mi semana, lo urgente primero" y Claude crea, mueve, prioriza y marca tareas.

```
Navegador → POST /assistant/chat → Claude (tu API key) ⇄ herramientas → todos del usuario logueado
```

- Código: `app/api/routes/assistant.py` (endpoint), `app/services/assistant_mcp.py` (modo MCP) y `app/services/assistant_service.py` (modo directo).
- **Modo MCP (por defecto):** por cada mensaje, FastAPI emite un token restringido `todos` para el usuario, arranca `mcp_server` en memoria, se conecta como **cliente MCP**, le pregunta qué herramientas ofrece y se las da a Claude. Las llamadas de Claude pasan por el MCP, que llama a la API REST con ese token. Las mismas herramientas las usan Claude Code y Desktop: una sola definición, una sola validación.
  `Claude <-> FastAPI (cliente MCP) <-> mcp_server <-> API REST`
- Herramientas: `get_today`, `list_todos` (con filtros), `create_todos`, `update_todos` (en lote) y `delete_todos` (solo con `ASSISTANT_ALLOW_DELETE=true`).
- Las herramientas se ejecutan en el servidor con el id del usuario logueado: el modelo no ve tokens ni ids de usuario y no puede tocar tareas ajenas. Los datos pasan por los mismos schemas que la API.
- Límites: 8 pasos por mensaje, 40 cambios por mensaje, 20 mensajes de historial, 2000 caracteres por mensaje, 4000 tokens de salida y `ASSISTANT_MESSAGES_PER_HOUR` por usuario.
- Los títulos se tratan como datos, no como órdenes (prompt injection). La key nunca llega al navegador ni se escribe en logs.
- Sin `ANTHROPIC_API_KEY` el endpoint responde 503 y el resto de la app funciona igual. Los tests usan un cliente falso: no gastan créditos.

## Seguridad

| Medida | Dónde |
|---|---|
| Tokens con **scope**: `full` (todo) o `todos` (solo `/todos`). Se pide con `scope=todos` en el login. Los `todos` caducan antes (`MCP_TOKEN_EXPIRE_MINUTES`) | `core/security.py`, `api/deps.py` |
| JWT exige `exp`, scope válido e id numérico | `core/security.py` |
| **Límite de intentos de login** por IP+email (429 + `Retry-After`) | `core/rate_limit.py`. En memoria: con varios workers usa Redis |
| Login sin fuga por tiempo (hash falso si el email no existe) | `services/user_service.py` |
| Cabeceras `nosniff`, `X-Frame-Options`, `no-store`, CSP en `/app` | `main.py` |
| CORS cerrado por defecto (`CORS_ORIGINS` para abrirlo) | `core/config.py` |

## Servidor MCP (para que Claude use los todos)

`mcp_server/` es un servidor **stdio** (sin puerto de red) que llama a la API.

```
mcp_server/
├── server.py     # get_today, list_todos (filtros), create_todo, set_todo_done, rename_todo, schedule_todo, plan_todos (+ delete_todo opcional)
├── client.py     # cliente HTTP: login con scope=todos, renueva el token, errores sin detalles internos
└── security.py   # config desde env, validación/limpieza de entradas, rate limit
```

Medidas: usa un token `todos` (no puede tocar usuarios ni contraseñas); credenciales solo por variables
de entorno (nunca como argumento de una herramienta); lista cerrada de herramientas, `delete_todo` desactivado
salvo `MCP_ALLOW_DELETE=true`; títulos validados y sin caracteres de control/bidi; 30 llamadas/min
(`MCP_RATE_LIMIT`); auditoría en stderr; exige https salvo localhost; las instrucciones avisan de que los
títulos son datos, no órdenes (prompt injection). Crea una **cuenta dedicada** para el MCP.

Registrarlo en Claude Code (con la API arrancada):

```powershell
claude mcp add todo-api --env MCP_EMAIL=mcp@example.com --env MCP_PASSWORD=... -- .\.venv\Scripts\python.exe -m mcp_server.server
```

## Pendientes / siguientes pasos

- Migraciones con **Alembic**. Hoy `create_all` crea tablas y `ensure_columns()` (app/db/session.py) solo añade columnas nuevas; no sirve para renombrar o borrar columnas.
- Roles (por ejemplo, admin).
- Refresh tokens y revocación de tokens.
- Rate limit global en la API y política de contraseñas más fuerte.
