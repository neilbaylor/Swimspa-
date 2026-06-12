# Swim Spa Control

A simple web app to view and control the water temperature of a **Gecko
in.touch2** Wi‑Fi spa — the current temperature with **+ / –** buttons to
change the setpoint, accessible from any phone or browser on your home network.

## How it works

Gecko's in.touch2 Wi‑Fi module does **not** expose a normal HTTP API. The only
practical way to talk to it (the same approach the Home Assistant Gecko
integration uses) is the reverse‑engineered
[`geckolib`](https://github.com/gazoodle/geckolib) library, which speaks the
spa's UDP protocol **over your local network**.

```
 Browser / phone  ──HTTP──▶  FastAPI app  ──geckolib/UDP──▶  Gecko in.touch2 spa
                              (this repo)        (LAN only)
```

**Important:** because it uses the local protocol, the app must run on a machine
(laptop, Raspberry Pi, NAS, mini‑PC…) connected to the **same Wi‑Fi / LAN as the
spa**. It cannot reach the spa over the public internet — exactly like the
official app falling back to local control. (If you want remote access, run it on
an always‑on device at home and reach it via your own VPN.)

## Quick start (demo mode — no spa needed)

```bash
pip install -r requirements.txt
SPA_DEMO=1 ./run.sh
```

Open <http://localhost:8000>. You'll get a fake spa whose water temperature
drifts toward whatever setpoint you choose — handy for trying the UI.

## Connect to your real spa

Run it on a device on the same network as the spa:

```bash
pip install -r requirements.txt
./run.sh
```

Then open `http://<that-device-ip>:8000` from your phone.

The app auto‑discovers the spa via a UDP broadcast. If your spa is on a
different subnet/VLAN (so broadcast doesn't reach it), pin its IP address:

```bash
SPA_ADDRESS=192.168.1.50 ./run.sh
```

It keeps retrying discovery in the background, so it's fine to start the app
before the spa is reachable; the UI shows the connection state.

## Configuration

| Variable      | Default | Description                                            |
| ------------- | ------- | ------------------------------------------------------ |
| `SPA_DEMO`    | _unset_ | Set to `1` to use the built‑in fake spa.               |
| `SPA_ADDRESS` | _unset_ | Fixed spa IP address (use if auto‑discovery fails).    |
| `PORT`        | `8000`  | Port the web server listens on.                        |
| `LOG_LEVEL`   | `INFO`  | Python logging level (`DEBUG` for verbose geckolib).   |

## API

The web UI is backed by a tiny REST API you can also call directly:

| Method | Path                    | Description                          |
| ------ | ----------------------- | ------------------------------------ |
| GET    | `/api/status`           | Current/target temp, unit, state.    |
| POST   | `/api/temperature/up`   | Raise setpoint by one step.          |
| POST   | `/api/temperature/down` | Lower setpoint by one step.          |
| POST   | `/api/temperature`      | Set exact value: `{"value": 38.5}`.  |

The step size follows the spa's units: 1° in Fahrenheit, 0.5° in Celsius, and
setpoints are clamped to the spa's own min/max.

## Project layout

```
backend/
  main.py   FastAPI app: routes + startup/shutdown lifecycle
  spa.py    SpaController (real, via geckolib) + DemoSpaController
frontend/
  index.html  Single-page UI (no build step)
```

## Notes & limitations

- Built and tested against `geckolib` 0.4.20.
- This is unofficial and not affiliated with Gecko Alliance.
- Only temperature is exposed here; `geckolib` also supports pumps, blowers,
  lights and water‑care if you want to extend it.
