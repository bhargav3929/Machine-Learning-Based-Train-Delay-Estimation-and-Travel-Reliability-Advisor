# Machine Learning Based Train Delay Estimation and Travel Reliability Advisor

This app tells you how reliable an Indian Railways journey is before you plan a connection around it. Enter a train (for example `12301 Howrah Rajdhani`) or any `Origin -> Destination` corridor, a travel date and the buffer you have planned. It combines bundled corridor priors (junction congestion, fog and monsoon vulnerability, train priority) with **live weather from Open-Meteo** at the origin, the junctions on the way and the destination. A small interpretable ML model then estimates the **median delay (P50)**, the **worst-case delay (P90)**, the **on-time probability** and a **safer connection buffer**. A Groq AI strategist turns those numbers into a plain-English plan. It is meant for students, commuters and anyone catching a flight, a second train or an exam after a long rail journey.

## 1. What you need

- **Python 3.10 or newer** - download from https://www.python.org/downloads/ (on Windows tick "Add python.exe to PATH").
- **A free Groq key** - get one in about a minute, no card needed, at https://console.groq.com/keys.
- An internet connection (for Open-Meteo weather and Groq). Open-Meteo needs no key.

## 2. Run it (one command)

- **macOS / Linux:** `chmod +x start.sh && ./start.sh`
- **Windows:** double-click `start.bat` (or run it in a terminal)

The first run creates a private `.venv`, installs the requirements quietly and copies `.env.example` to `.env`. Your browser then opens at `http://127.0.0.1:8007`. Running the script again starts in seconds.

## 3. Add your Groq key

Click **API Keys** in the app and paste your key (it starts with `gsk_`). It is saved only on your computer. Or open `.env` and set `GROQ_API_KEY=gsk_your_key`, then restart. Until a key is added you can still open the four sample scenarios and see their saved results.

## 4. How to use it

1. Click a **sample slip** on the left (for example *12301 Howrah - New Delhi Rajdhani Express*). Its saved result appears instantly and nothing is used up. The Mumbai - Ahmedabad Shatabdi slip is a punctuality control: you should see a high on-time score and a small delay. The *99999 Starship Express* slip shows how a train that doesn't exist is rejected with a clear message and no invented numbers.
2. Press **Estimate Corridor Delay** to get fresh weather and a fresh Groq plan. The **execution tracker** shows the four stages as they finish.
3. Type your own train number, train name, or corridor such as `Patna -> Lucknow`. Pick the travel date, the connection type (flight, onward train, exam or event, or plain travel) and your planned buffer in minutes.
4. Read the **four KPI cells**: on-time score, median delay, 90th-percentile delay and the safe buffer with a Safe / Tight / Risky verdict against your plan.
5. Hover a station in the **timeline** to see its weather and the delay built up so far. Open **Telemetry & ML Verification Audit** to see the exact coordinates, weather values and formula inputs.
6. Use the **Train vs. Train Compare** tab to compare two options, and the **Buffer Calculator** tab to see your chance of making the connection for any buffer.
7. The **History** button lists your earlier runs. You get 15 live runs per hour; a run that fails (unknown station, AI busy) does not use one up.

## 5. How it works

1. **Stage 1 - resolve the corridor** (`app/corridor.py`, `app/data.py`): train numbers and names come from the bundled table of trains and stations. Other places are looked up with the Open-Meteo geocoding API.
2. **Stage 2 - live weather** (`app/weather.py`): one Open-Meteo forecast request returns temperature, rain, wind and visibility for every waypoint. If the travel date is within 16 days the forecast for that day is used; otherwise today's live conditions are blended with the seasonal prior.
3. **Stage 3 - ML delay model** (`app/model.py`): an additive ensemble of boosted decision stumps scores distance, junction congestion, weather and season. A priority multiplier and a log-normal spread then give P50, P90, on-time probability and the buffer needed. The stump scales are hand-calibrated planning priors, not trained on live Railways running data, so treat results as guidance and check live running status before you travel.
4. **Stage 4 - Groq advisor** (`app/ai_groq.py`, `app/pipeline.py`): the numbers are sent to Groq, which writes the summary, buffer advice and backup plan. It retries busy responses, switches to a backup model and never shows raw provider errors.
5. **Limits and history** (`app/access.py`, `app/db.py`): a sliding 15-per-hour limit and your history live in a local SQLite file under `data/`.
6. **Routes and screen** (`app/main.py`, `static/`): FastAPI serves the API and the plain HTML/CSS/JS page.

Sample results in `samples/results/` were recorded with `scripts/record_samples.py`.

## 6. Project structure

```
Machine-Learning-Based-Train-Delay-Estimation-and-Travel-Reliability-Advisor/
├── app/
│   ├── __init__.py
│   ├── access.py        # hourly run limit and access checks
│   ├── ai_groq.py       # the only place that talks to Groq
│   ├── config.py        # reads .env
│   ├── corridor.py      # stage 1: train / station resolver
│   ├── data.py          # bundled stations, trains, seasonal priors
│   ├── db.py            # SQLite (keys, history, run log)
│   ├── errors.py
│   ├── main.py          # FastAPI routes
│   ├── model.py         # stage 3: ML delay model
│   ├── pipeline.py      # stages 2-4 glue and Groq prompts
│   └── weather.py       # stage 2: Open-Meteo
├── samples/
│   ├── *.json           # four sample scenarios
│   └── results/*.json   # their saved results
├── scripts/
│   └── record_samples.py
├── static/
│   ├── index.html
│   ├── styles.css
│   └── js/ (api.js, app.js, charts.js, render.js)
├── .env.example
├── .gitattributes
├── .gitignore
├── requirements.txt
├── start.bat
├── start.sh
└── README.md
```

## 7. Troubleshooting

- **Port already in use:** another program is using 8007. Close it, or change `PORT` in `.env` and run the start script again.
- **"The AI service is busy right now":** Groq's free tier is overloaded. Wait a minute and try again; your run is not counted.
- **"Your Groq key was rejected":** open **API Keys** and paste a fresh key from https://console.groq.com/keys.
- **Python not found:** install Python 3.10+ from https://www.python.org/downloads/ and open a new terminal.
- **Install failed on a slow connection:** run the start script again; it resumes where it stopped.
- **Weather shows "unreachable":** Open-Meteo could not be reached, so the model used seasonal priors only. Check your internet and run again.
- **"Couldn't find a station":** check the spelling or use the nearest big city name.

Timetable times, distances and station coordinates are approximate planning data bundled with the app. This tool estimates risk; it does not know the live position of any train.