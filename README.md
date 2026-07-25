# statuslineclaude

A custom `statusLine` for [Claude Code](https://claude.com/claude-code): model,
current activity, context usage, token counts, session cost and the 5h/7d
rate-limit windows, all in one line that gracefully shrinks to fit narrow
terminals.

> The original idea for this design was copied from an idea by **Mario Álvarez**.

---

## Español

### ¿Para qué sirve?

Sustituye la statusLine por defecto de Claude Code por una línea con:

1. **Modelo** en uso.
2. **Actividad actual** (p. ej. `⚡ Editing`, `⚡ Running`) mientras Claude está
   usando una herramienta — desaparece a los 10s de inactividad.
3. **Contexto usado** (`ctx 24%`) calculado sobre el último mensaje del
   transcript, coloreado por umbral (verde/amarillo/rojo).
4. **Tokens de entrada/salida** de la sesión.
5. **Coste** acumulado de la sesión en `$`.
6. **Ventana de 5 horas** y **ventana de 7 días** de rate limit, con
   porcentaje usado y hora de reset, coloreados según cuánto queda.

Si la línea no cabe en el ancho de tu terminal, va quitando piezas por orden
de importancia (tokens in/out → valor absoluto de contexto → etiqueta de
actividad → horas de reset) hasta que encaja, sin perder nunca los datos
esenciales (modelo, `%` de contexto, coste, `%` de las ventanas de rate
limit).

### Instalación

Requiere `python3` y `bash`. No hay dependencias externas.

```bash
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude
./install.sh
```

Esto:

- copia `scripts/statusline.py` y `scripts/state_collector.py` a
  `~/.claude/scripts/`;
- añade (o actualiza) los hooks `PreToolUse`, `PostToolUse` y `Stop`, y la
  entrada `statusLine`, en `~/.claude/settings.json` — **sin tocar** el resto
  de tu configuración. Es seguro volver a ejecutarlo (no duplica entradas).

Reinicia Claude Code (o abre una sesión nueva) para verla activa.

Si usas una ubicación de config distinta, exporta `CLAUDE_CONFIG_DIR` antes
de instalar:

```bash
CLAUDE_CONFIG_DIR=/ruta/a/tu/.claude ./install.sh
```

### Desinstalar

```bash
./install.sh --uninstall
```

Quita únicamente los hooks y el `statusLine` que apuntan a estos scripts, y
los borra de `~/.claude/scripts/`. El resto de tu `settings.json` queda
intacto.

### Cómo funciona por dentro

- `scripts/state_collector.py`: hook que se dispara en `PreToolUse`,
  `PostToolUse` y `Stop`. Mientras Claude usa una herramienta, escribe
  `/tmp/claude-state/{session_id}.json` con el nombre de la herramienta y un
  timestamp; en `Stop`, borra ese fichero.
- `scripts/statusline.py`: el comando de `statusLine`. Recibe por stdin el
  JSON que le pasa Claude Code (modelo, coste, ruta del transcript,
  rate limits...), lee el fichero de estado de la sesión para mostrar la
  actividad si es reciente (<10s), y calcula el contexto usado leyendo el
  último mensaje `assistant` del transcript JSONL.

---

## English

### What is this?

Replaces Claude Code's default statusLine with a single line showing:

1. **Model** currently in use.
2. **Current activity** (e.g. `⚡ Editing`, `⚡ Running`) while Claude is using
   a tool — disappears after 10s of inactivity.
3. **Context used** (`ctx 24%`), computed from the last transcript message,
   colored by threshold (green/yellow/red).
4. **Session input/output token counts**.
5. **Session cost** in `$`.
6. **5-hour** and **7-day** rate-limit windows, with percentage used and
   reset time, colored by how much of the cycle is left.

If the line doesn't fit your terminal width, it drops pieces in order of
importance (input/output tokens → absolute context value → activity label →
reset timestamps) until it fits, always keeping the essentials (model,
context %, cost, rate-limit %s).

### Install

Requires `python3` and `bash`. No external dependencies.

```bash
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude
./install.sh
```

This:

- copies `scripts/statusline.py` and `scripts/state_collector.py` into
  `~/.claude/scripts/`;
- adds (or updates) the `PreToolUse`, `PostToolUse` and `Stop` hooks, and the
  `statusLine` entry, in `~/.claude/settings.json` — **without touching**
  the rest of your config. Safe to re-run (it won't duplicate entries).

Restart Claude Code (or start a new session) to see it.

If you use a non-default config location, export `CLAUDE_CONFIG_DIR` before
installing:

```bash
CLAUDE_CONFIG_DIR=/path/to/your/.claude ./install.sh
```

### Uninstall

```bash
./install.sh --uninstall
```

Removes only the hooks and `statusLine` entry that point to these scripts,
and deletes them from `~/.claude/scripts/`. The rest of your `settings.json`
is left untouched.

### How it works

- `scripts/state_collector.py`: hook fired on `PreToolUse`, `PostToolUse`
  and `Stop`. While Claude is using a tool it writes
  `/tmp/claude-state/{session_id}.json` with the tool name and a timestamp;
  on `Stop` it deletes that file.
- `scripts/statusline.py`: the `statusLine` command. Reads the JSON Claude
  Code feeds it on stdin (model, cost, transcript path, rate limits...),
  reads the session's state file to show the activity label if recent
  (<10s), and computes context usage from the last `assistant` message in
  the transcript JSONL.

## License

MIT, see [LICENSE](LICENSE).
