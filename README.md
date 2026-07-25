# statuslineclaude

[![CI](https://github.com/Isangi74/statuslineclaude/actions/workflows/ci.yml/badge.svg)](https://github.com/Isangi74/statuslineclaude/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](#installation)

A custom status line for [Claude Code](https://claude.com/claude-code):
model, current activity, context usage, token counts, session cost and the
5-hour / 7-day rate-limit windows — on one line that shrinks gracefully to
fit any terminal.

```text
Claude Opus 5 │ ⚡ Editing │ ctx 73% (145.5K) │ 93.5K↑ 1.3K↓ │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
```

No dependencies beyond Python itself. One command to install, one to
remove.

> 💡 The design of this status line is based on **an original idea by
> Mario Álvarez**.

**📖 [Español](#español) · [English](#english)**

---

<a name="español"></a>

# Español

## Qué muestra

| Segmento | Ejemplo | Significado |
|---|---|---|
| Modelo | `Claude Opus 5` | Modelo en uso, en cian negrita |
| Actividad | `⚡ Editing` | Qué está haciendo Claude *ahora mismo*; desaparece a los 10 s |
| Contexto | `ctx 73% (145.5K)` | Porcentaje de la ventana de contexto consumido, y tokens absolutos |
| Tokens | `93.5K↑ 1.3K↓` | Tokens de entrada y de salida acumulados en la sesión |
| Coste | `$4.27` | Coste acumulado de la sesión |
| Ventana 5 h | `5h 38% ↻14:28-25.07` | Rate limit de 5 horas usado, y hora del reset |
| Ventana 7 d | `7d 72% ↻11:28-29.07` | Rate limit de 7 días usado, y hora del reset |

**Colores.** El contexto y los porcentajes de rate limit van en verde por
debajo del 50 %, amarillo por debajo del 80 % y rojo a partir de ahí. La
hora de reset se colorea según lo que queda de ciclo: verde si queda más
de la mitad, amarillo más de un cuarto, naranja más de un décimo, y rojo
cuando está a punto de renovarse.

### Escalera de compactación

Si la línea no cabe en tu terminal, va soltando lastre por orden de menor
importancia, en lugar de partirse en dos filas:

```text
200 cols  Claude Opus 5 │ ⚡ Editing │ ctx 73% (145.5K) │ 93.5K↑ 1.3K↓ │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
100 cols  Claude Opus 5 │ ⚡ Editing │ ctx 73% (145.5K) │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
 95 cols  Claude Opus 5 │ ⚡ Editing │ ctx 73% │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
 80 cols  Claude Opus 5 │ ctx 73% │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
 55 cols  Claude Opus 5 │ ctx 73% │ $4.27 │ 5h 38% │ 7d 72%
```

El orden en que se descartan es: tokens ↑↓ → contexto absoluto → etiqueta
de actividad → horas de reset. El modelo, el `%` de contexto, el coste y
los `%` de rate limit no se pierden nunca.

---

## Instalación

Los pasos 1 y 2 dependen de tu sistema operativo. El paso 3 es igual en
todos.

### Paso 1 · Requisitos

Necesitas **Claude Code** y **Python 3.9 o superior**. Elige tu sistema:

<details open>
<summary><b>🐧 Linux</b></summary>

Casi todas las distribuciones traen Python 3 de fábrica. Compruébalo:

```bash
python3 --version
```

Si no lo tienes:

```bash
sudo apt install python3            # Debian / Ubuntu
sudo dnf install python3            # Fedora / RHEL
sudo pacman -S python               # Arch
sudo zypper install python3         # openSUSE
```
</details>

<details>
<summary><b>🍎 macOS</b></summary>

macOS incluye Python 3. Compruébalo:

```bash
python3 --version
```

Si falta o es muy antiguo, instálalo con [Homebrew](https://brew.sh):

```bash
brew install python
```

> En macOS puede que la primera vez te pida instalar las herramientas de
> línea de comandos de Xcode. Acepta, o ejecuta `xcode-select --install`.
</details>

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

Instala Python desde la Microsoft Store, desde
[python.org](https://www.python.org/downloads/) o con winget:

```powershell
winget install Python.Python.3.12
```

> ⚠️ Si usas el instalador de python.org, marca la casilla
> **«Add python.exe to PATH»**. Sin eso el instalador no lo encontrará.

Comprueba que funciona:

```powershell
python --version
```
</details>

<details>
<summary><b>🪟 Windows (WSL o Git Bash)</b></summary>

Si ejecutas Claude Code dentro de **WSL**, sigue las instrucciones de
**Linux** dentro de tu distribución de WSL — no las de Windows.

Si usas **Git Bash**, necesitas un Python de Windows en el `PATH`; sigue
las instrucciones de Windows (PowerShell) y luego usa `./install.sh`.
</details>

### Paso 2 · Instalar

<details open>
<summary><b>🐧 Linux · 🍎 macOS · WSL · Git Bash</b></summary>

```bash
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude
./install.sh
```

Si `./install.sh` no arranca por permisos:

```bash
bash install.sh
```
</details>

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude
.\install.ps1
```

Si PowerShell bloquea el script por la política de ejecución, puedes
saltártela solo para esta ejecución:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

O llamar directamente al instalador de Python, que no depende de la
política:

```powershell
python install.py
```
</details>

### Paso 3 · Comprobar (igual en todos los sistemas)

Reinicia Claude Code (o abre una sesión nueva) y deberías ver la línea
abajo del todo.

Antes de instalar puedes ver **qué cambiaría**, sin tocar nada:

```bash
./install.sh --dry-run          # Linux / macOS / WSL
.\install.ps1 -DryRun           # Windows PowerShell
```

### Qué hace el instalador

- Copia `statusline.py` y `state_collector.py` a `~/.claude/scripts/`
  (en Windows, `C:\Users\<tú>\.claude\scripts\`).
- Añade a `~/.claude/settings.json` la entrada `statusLine` y los hooks
  `PreToolUse`, `PostToolUse` y `Stop`, **sin tocar** nada más del fichero.

Es seguro volver a ejecutarlo: actualiza la instalación en lugar de
duplicar entradas. Si guardas la configuración en otro sitio, exporta
`CLAUDE_CONFIG_DIR` antes de instalar:

```bash
CLAUDE_CONFIG_DIR=/ruta/a/tu/.claude ./install.sh
```

---

## Configuración (opcional)

Crea `~/.claude/statusline.config.json` para ajustar la línea sin editar
el script. Solo hace falta poner las claves que quieras cambiar:

```json
{
  "separator": " | ",
  "show_io": false,
  "usage_warn_pct": 60,
  "usage_alert_pct": 85,
  "reset_time_format": "%H:%M"
}
```

| Clave | Por defecto | Qué hace |
|---|---|---|
| `activity_max_age_s` | `10` | Segundos que la etiqueta de actividad sigue visible |
| `context_window` | `200000` | Tamaño de la ventana de contexto estándar |
| `context_window_1m` | `1000000` | Ventana para los modelos de contexto largo |
| `usage_warn_pct` | `50` | A partir de aquí, amarillo |
| `usage_alert_pct` | `80` | A partir de aquí, rojo |
| `separator` | `" │ "` | Separador entre segmentos |
| `show_activity` | `true` | Mostrar la etiqueta `⚡` |
| `show_context` | `true` | Mostrar el segmento de contexto |
| `show_io` | `true` | Mostrar los tokens ↑↓ |
| `show_cost` | `true` | Mostrar el coste |
| `show_rate_limits` | `true` | Mostrar las ventanas 5 h y 7 d |
| `reset_time_format` | `"%H:%M-%d.%m"` | Formato de la hora de reset |

También se respeta la convención [`NO_COLOR`](https://no-color.org): si esa
variable de entorno existe, la línea sale sin códigos de color.

---

## Desinstalar

```bash
./install.sh --uninstall        # Linux / macOS / WSL / Git Bash
.\install.ps1 -Uninstall        # Windows PowerShell
```

Quita solo los hooks y el `statusLine` que apuntan a estos scripts, y los
borra de `~/.claude/scripts/`. El resto de tu `settings.json` se queda
exactamente como estaba — hay tests que lo comprueban.

---

## Cómo funciona por dentro

**`scripts/state_collector.py`** — hook que se dispara en `PreToolUse`,
`PostToolUse` y `Stop`. Mientras Claude usa una herramienta escribe el
nombre de esa herramienta y un timestamp en un fichero de estado; en
`Stop` lo borra y limpia los que hayan quedado huérfanos.

**`scripts/statusline.py`** — el comando de `statusLine`. Recibe por
stdin el JSON de Claude Code (modelo, coste, ruta del transcript, rate
limits), lee el estado de la sesión para la etiqueta de actividad, y saca
el contexto del último mensaje `assistant` del transcript.

El fichero de estado vive en el directorio temporal del sistema, en una
carpeta propia de tu usuario con permisos `0700`, para que en un equipo
compartido nadie más pueda leer tus `session_id`. Puedes cambiar su
ubicación con `CLAUDE_STATUSLINE_STATE_DIR`.

### Sobre el rendimiento

Un transcript puede pesar decenas de megabytes y la statusline se repinta
constantemente, así que el fichero **nunca se lee entero**:

- el último bloque `usage` se busca haciendo *seek* hacia atrás desde el
  final, en bloques pequeños;
- los totales de tokens se acumulan en una caché incremental que solo
  parsea los bytes añadidos desde el repintado anterior.

Sobre un transcript real de 42 MB, esto supone **~6× menos tiempo y ~3×
menos memoria** por repintado frente a leer el fichero completo. Además,
todos los datos se recopilan una sola vez y la escalera de compactación
solo re-renderiza texto, así que estrechar la terminal no cuesta E/S extra.

---

## Solución de problemas

**No aparece nada.** Reinicia Claude Code: `settings.json` se lee al
arrancar la sesión. Comprueba que la entrada existe:

```bash
python3 -c "import json,pathlib;print(json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()).get('statusLine'))"
```

**Ejecuta el script a mano** para ver el error directamente:

```bash
echo '{"model":{"display_name":"Test"}}' | python3 ~/.claude/scripts/statusline.py
```

**`ctx 0%` siempre.** El porcentaje sale del transcript de la sesión; en
un mensaje recién empezado todavía no hay ningún mensaje `assistant` que
leer. Manda un par de mensajes y vuelve a mirar.

**La etiqueta `⚡` no sale nunca.** Solo se ve mientras una herramienta
está corriendo y desaparece a los 10 s. Verifica que los hooks están
puestos y que el fichero de estado se crea:

```bash
ls "$(python3 -c "import tempfile,getpass,os;print(os.path.join(tempfile.gettempdir(),'claude-statusline-'+getpass.getuser()))")"
```

**Los caracteres se ven como cuadraditos.** Tu fuente de terminal no tiene
los símbolos `⚡ ↑ ↓ ↻ │`. Usa una fuente con buena cobertura Unicode
(cualquier Nerd Font, Cascadia Code, JetBrains Mono…) o cambia
`separator` en la configuración.

**Windows: `python no se reconoce como un comando`.** Python no está en el
`PATH`. Reinstálalo marcando «Add python.exe to PATH», o usa la ruta
completa: `C:\Python312\python.exe install.py`.

---

<a name="english"></a>

# English

## What it shows

| Segment | Example | Meaning |
|---|---|---|
| Model | `Claude Opus 5` | Model in use, in bold cyan |
| Activity | `⚡ Editing` | What Claude is doing *right now*; fades after 10 s |
| Context | `ctx 73% (145.5K)` | Share of the context window used, plus absolute tokens |
| Tokens | `93.5K↑ 1.3K↓` | Input and output tokens accumulated this session |
| Cost | `$4.27` | Running cost of the session |
| 5-hour window | `5h 38% ↻14:28-25.07` | 5-hour rate limit used, and when it resets |
| 7-day window | `7d 72% ↻11:28-29.07` | 7-day rate limit used, and when it resets |

**Colours.** Context and rate-limit percentages are green below 50 %,
yellow below 80 %, red above. Reset stamps are coloured by how much of the
cycle is left: green above half, yellow above a quarter, orange above a
tenth, red when it is about to roll over.

### Compaction ladder

When the line doesn't fit, it sheds the least important pieces instead of
wrapping onto a second row:

```text
200 cols  Claude Opus 5 │ ⚡ Editing │ ctx 73% (145.5K) │ 93.5K↑ 1.3K↓ │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
100 cols  Claude Opus 5 │ ⚡ Editing │ ctx 73% (145.5K) │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
 95 cols  Claude Opus 5 │ ⚡ Editing │ ctx 73% │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
 80 cols  Claude Opus 5 │ ctx 73% │ $4.27 │ 5h 38% ↻14:28-25.07 │ 7d 72% ↻11:28-29.07
 55 cols  Claude Opus 5 │ ctx 73% │ $4.27 │ 5h 38% │ 7d 72%
```

The drop order is: ↑↓ tokens → absolute context → activity label → reset
stamps. The model, context %, cost and rate-limit %s are never lost.

---

<a name="installation"></a>

## Installation

Steps 1 and 2 depend on your operating system. Step 3 is the same
everywhere.

### Step 1 · Requirements

You need **Claude Code** and **Python 3.9 or newer**. Pick your system:

<details open>
<summary><b>🐧 Linux</b></summary>

Nearly every distribution ships Python 3. Check with:

```bash
python3 --version
```

If it is missing:

```bash
sudo apt install python3            # Debian / Ubuntu
sudo dnf install python3            # Fedora / RHEL
sudo pacman -S python               # Arch
sudo zypper install python3         # openSUSE
```
</details>

<details>
<summary><b>🍎 macOS</b></summary>

macOS ships Python 3. Check with:

```bash
python3 --version
```

If it is missing or too old, install it with [Homebrew](https://brew.sh):

```bash
brew install python
```

> macOS may ask to install the Xcode command line tools the first time.
> Accept, or run `xcode-select --install`.
</details>

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

Install Python from the Microsoft Store, from
[python.org](https://www.python.org/downloads/), or with winget:

```powershell
winget install Python.Python.3.12
```

> ⚠️ If you use the python.org installer, tick **"Add python.exe to
> PATH"**. Without it the installer cannot find Python.

Verify it works:

```powershell
python --version
```
</details>

<details>
<summary><b>🪟 Windows (WSL or Git Bash)</b></summary>

If you run Claude Code inside **WSL**, follow the **Linux** instructions
inside your WSL distribution — not the Windows ones.

If you use **Git Bash**, you need a Windows Python on `PATH`: follow the
Windows (PowerShell) instructions, then use `./install.sh`.
</details>

### Step 2 · Install

<details open>
<summary><b>🐧 Linux · 🍎 macOS · WSL · Git Bash</b></summary>

```bash
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude
./install.sh
```

If `./install.sh` won't start because of permissions:

```bash
bash install.sh
```
</details>

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude
.\install.ps1
```

If PowerShell blocks the script because of the execution policy, bypass it
for this run only:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Or call the Python installer directly, which the policy does not affect:

```powershell
python install.py
```
</details>

### Step 3 · Check it (same everywhere)

Restart Claude Code (or open a new session) and the line should appear at
the bottom.

You can preview **what would change** before installing anything:

```bash
./install.sh --dry-run          # Linux / macOS / WSL
.\install.ps1 -DryRun           # Windows PowerShell
```

### What the installer does

- Copies `statusline.py` and `state_collector.py` into `~/.claude/scripts/`
  (on Windows, `C:\Users\<you>\.claude\scripts\`).
- Adds the `statusLine` entry and the `PreToolUse`, `PostToolUse` and
  `Stop` hooks to `~/.claude/settings.json`, **without touching** anything
  else in that file.

Re-running it is safe: it refreshes the install rather than duplicating
entries. If your config lives elsewhere, export `CLAUDE_CONFIG_DIR` first:

```bash
CLAUDE_CONFIG_DIR=/path/to/your/.claude ./install.sh
```

---

## Configuration (optional)

Create `~/.claude/statusline.config.json` to tweak the line without editing
the script. Only include the keys you want to change:

```json
{
  "separator": " | ",
  "show_io": false,
  "usage_warn_pct": 60,
  "usage_alert_pct": 85,
  "reset_time_format": "%H:%M"
}
```

| Key | Default | What it does |
|---|---|---|
| `activity_max_age_s` | `10` | Seconds the activity label stays visible |
| `context_window` | `200000` | Standard context window size |
| `context_window_1m` | `1000000` | Window for long-context models |
| `usage_warn_pct` | `50` | Turn yellow from here |
| `usage_alert_pct` | `80` | Turn red from here |
| `separator` | `" │ "` | Separator drawn between segments |
| `show_activity` | `true` | Show the `⚡` label |
| `show_context` | `true` | Show the context segment |
| `show_io` | `true` | Show the ↑↓ token counts |
| `show_cost` | `true` | Show the cost |
| `show_rate_limits` | `true` | Show the 5 h and 7 d windows |
| `reset_time_format` | `"%H:%M-%d.%m"` | Reset timestamp format |

The [`NO_COLOR`](https://no-color.org) convention is honoured too: set that
environment variable and the line is printed without colour codes.

---

## Uninstall

```bash
./install.sh --uninstall        # Linux / macOS / WSL / Git Bash
.\install.ps1 -Uninstall        # Windows PowerShell
```

This removes only the hooks and the `statusLine` entry that point at these
scripts, and deletes them from `~/.claude/scripts/`. The rest of your
`settings.json` is left byte-for-byte as it was — there are tests for that.

---

## How it works

**`scripts/state_collector.py`** — a hook fired on `PreToolUse`,
`PostToolUse` and `Stop`. While a tool is running it writes that tool's
name and a timestamp to a state file; on `Stop` it deletes the file and
prunes any left behind by sessions that ended abruptly.

**`scripts/statusline.py`** — the `statusLine` command. It reads Claude
Code's JSON on stdin (model, cost, transcript path, rate limits), reads the
session state file for the activity label, and derives context usage from
the last `assistant` message in the transcript.

The state file lives in the system temp directory, inside a per-user folder
created with `0700` permissions, so on a shared machine nobody else can
read your session ids. Override its location with
`CLAUDE_STATUSLINE_STATE_DIR`.

### On performance

A transcript can be tens of megabytes and the status line is repainted
constantly, so the file is **never read in full**:

- the last `usage` block is found by seeking backwards from the end of the
  file in small blocks;
- token totals are accumulated in an incremental cache that only parses the
  bytes appended since the previous repaint.

On a real 42 MB transcript this is **~6× faster and uses ~3× less memory**
per repaint than reading the whole file. All data is gathered once and the
compaction ladder only re-renders text, so narrowing the terminal costs no
extra I/O.

---

## Troubleshooting

**Nothing shows up.** Restart Claude Code — `settings.json` is read when
the session starts. Check the entry is there:

```bash
python3 -c "import json,pathlib;print(json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()).get('statusLine'))"
```

**Run the script by hand** to see the error directly:

```bash
echo '{"model":{"display_name":"Test"}}' | python3 ~/.claude/scripts/statusline.py
```

**Always `ctx 0%`.** The percentage comes from the session transcript, and
a brand-new session has no `assistant` message to read yet. Send a couple
of messages and look again.

**The `⚡` label never appears.** It only shows while a tool is running and
fades after 10 s. Check the hooks are wired and that the state file is
created:

```bash
ls "$(python3 -c "import tempfile,getpass,os;print(os.path.join(tempfile.gettempdir(),'claude-statusline-'+getpass.getuser()))")"
```

**Characters render as boxes.** Your terminal font lacks the `⚡ ↑ ↓ ↻ │`
glyphs. Use a font with good Unicode coverage (any Nerd Font, Cascadia
Code, JetBrains Mono…) or change `separator` in the config.

**Windows: `python is not recognized`.** Python is not on your `PATH`.
Reinstall it with "Add python.exe to PATH" ticked, or use the full path:
`C:\Python312\python.exe install.py`.

---

## Credits

The design of this status line is based on an original idea by **Mario
Álvarez**.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python3 run_tests.py          # unit tests
python3 tests/verify_cli.py   # end-to-end check
ruff check .                  # lint
```

## License

MIT — see [LICENSE](LICENSE).
