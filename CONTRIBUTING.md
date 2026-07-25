# Contributing

Thanks for taking a look! This is a small project — issues and pull
requests are welcome.

*(Español más abajo — [ir a la versión en castellano](#contribuir-en-castellano))*

## Ground rules

- **Standard library only.** The scripts are copied into the user's
  `~/.claude/scripts/` and run on every status-line repaint. They must work
  on a bare Python install, with no `pip install` step.
- **Python 3.9+.** CI runs the suite on 3.9, 3.11 and 3.13 across Linux,
  macOS and Windows.
- **The status line must never crash.** A traceback would leave the user
  with no status line at all. Anything that touches the filesystem, parses
  JSON or does arithmetic on external data needs a fallback.
- **Performance matters.** The transcript can be tens of megabytes and the
  line is repainted constantly, so never read a file in full when seeking
  to the end or resuming from a cached offset will do.

## Development

```bash
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude

python3 run_tests.py          # unit tests
python3 run_tests.py -v       # ... verbose
python3 tests/verify_cli.py   # end-to-end check of the CLI entry points
ruff check .                  # lint (pip install ruff)
```

Try a change without touching your real configuration by pointing the
installer and the state directory somewhere disposable:

```bash
export CLAUDE_CONFIG_DIR=/tmp/fake-claude
export CLAUDE_STATUSLINE_STATE_DIR=/tmp/fake-state
./install.sh --dry-run        # show what would change
./install.sh                  # install into the fake config dir
```

To see the line for a given payload, feed it the same JSON Claude Code
does:

```bash
echo '{"model":{"display_name":"Claude Opus 5","id":"claude-opus-5"},
       "cost":{"total_cost_usd":0.42}}' | COLUMNS=120 python3 scripts/statusline.py
```

Set `COLUMNS` to a narrow value to exercise the compaction ladder.

## Pull requests

- Add a test for the behaviour you change. `tests/helpers.py` has small
  builders (`assistant()`, `user()`, `write_transcript()`) for transcripts.
- Run `python3 run_tests.py`, `python3 tests/verify_cli.py` and
  `ruff check .` before pushing.
- Keep the two `state_dir()` helpers in `scripts/statusline.py` and
  `scripts/state_collector.py` in sync. They are duplicated on purpose so
  each script stays a standalone file; a test asserts they agree.
- If you change what the line shows, update **both** the English and the
  Spanish sections of the README.

---

<a name="contribuir-en-castellano"></a>

# Contribuir (castellano)

¡Gracias por pasarte! Es un proyecto pequeño: las issues y los pull
requests son bienvenidos.

## Reglas básicas

- **Solo biblioteca estándar.** Los scripts se copian a
  `~/.claude/scripts/` y se ejecutan en cada repintado de la statusline.
  Tienen que funcionar con un Python recién instalado, sin `pip install`.
- **Python 3.9+.** El CI ejecuta la suite en 3.9, 3.11 y 3.13 sobre Linux,
  macOS y Windows.
- **La statusline no puede romperse nunca.** Un traceback dejaría al
  usuario sin línea de estado. Todo lo que toque el disco, parsee JSON o
  haga cuentas con datos externos necesita un camino de respaldo.
- **El rendimiento importa.** El transcript puede pesar decenas de
  megabytes y la línea se repinta constantemente: nunca leas un fichero
  entero si basta con buscar desde el final o retomar desde un offset
  cacheado.

## Desarrollo

```bash
git clone https://github.com/Isangi74/statuslineclaude.git
cd statuslineclaude

python3 run_tests.py          # tests unitarios
python3 run_tests.py -v       # ... en modo verboso
python3 tests/verify_cli.py   # comprobación de los puntos de entrada
ruff check .                  # linter (pip install ruff)
```

Para probar un cambio sin tocar tu configuración real, apunta el
instalador y el directorio de estado a un sitio desechable:

```bash
export CLAUDE_CONFIG_DIR=/tmp/fake-claude
export CLAUDE_STATUSLINE_STATE_DIR=/tmp/fake-state
./install.sh --dry-run        # muestra qué cambiaría
./install.sh                  # instala en el config falso
```

Para ver la línea con un payload concreto, dale el mismo JSON que le pasa
Claude Code:

```bash
echo '{"model":{"display_name":"Claude Opus 5","id":"claude-opus-5"},
       "cost":{"total_cost_usd":0.42}}' | COLUMNS=120 python3 scripts/statusline.py
```

Baja `COLUMNS` para ejercitar la escalera de compactación.

## Pull requests

- Añade un test del comportamiento que cambies. En `tests/helpers.py`
  tienes constructores (`assistant()`, `user()`, `write_transcript()`)
  para montar transcripts.
- Ejecuta `python3 run_tests.py`, `python3 tests/verify_cli.py` y
  `ruff check .` antes de hacer push.
- Mantén sincronizados los dos `state_dir()` de `scripts/statusline.py` y
  `scripts/state_collector.py`. Están duplicados a propósito para que cada
  script siga siendo un fichero autónomo; hay un test que lo comprueba.
- Si cambias lo que muestra la línea, actualiza **las dos** secciones del
  README, la inglesa y la castellana.
