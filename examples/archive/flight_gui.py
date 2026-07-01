#!/usr/bin/env python3
import json
import subprocess
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
from app.hotels import search_hotels_core

# Load airport mapping for destination city searches
AIRPORT_CITY_MAP = {}
try:
    with open('airports.json', 'r') as f:
        data = json.load(f)
        for code, info in data.items():
            iata = info.get('iata')
            if iata:
                # Store as "City, State" for quality Google Hotel searches
                AIRPORT_CITY_MAP[iata] = f"{info.get('city', '')}, {info.get('state', '')}"
except Exception as e:
    print(f"Warning: Could not load airports.json: {e}")

# Premium Dark Mode Glassmorphism HTML and CSS
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Travel Planner Pro</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        :root {
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --accent: #8b5cf6;
            --accent-hover: #7c3aed;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --success: #10b981;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-color);
            background-image: radial-gradient(circle at top right, #1e1b4b, #0f172a);
            background-attachment: fixed;
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            min-height: 100vh;
        }

        .container { max-width: 1200px; margin: 0 auto; }

        h1 {
            font-weight: 700;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #c4b5fd, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .tab-container {
            display: flex;
            gap: 10px;
            margin-bottom: 24px;
        }

        .tab {
            padding: 12px 24px;
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            color: var(--text-sub);
            transition: all 0.2s ease;
        }

        .tab.active {
            background: var(--accent);
            color: white;
            border-color: var(--accent);
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .trip-itinerary-card {
            background: rgba(30, 41, 59, 0.9);
            border: 1px solid var(--border-color);
            border-left: 5px solid var(--accent);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .booking-actions {
            display: flex;
            gap: 12px;
            margin-top: 12px;
        }

        .btn-book {
            flex: 1;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }

        .btn-flight {
            background: rgba(139, 92, 246, 0.2);
            color: #c4b5fd;
            border: 1px solid var(--accent);
        }

        .btn-flight:hover {
            background: var(--accent);
            color: white;
        }

        .btn-hotel {
            background: rgba(16, 185, 129, 0.2);
            color: #6ee7b7;
            border: 1px solid var(--success);
        }

        .btn-hotel:hover {
            background: var(--success);
            color: white;
        }
        
        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        label {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-sub);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        input {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 10px 14px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 1rem;
            transition: all 0.2s ease;
            width: 100%;
            box-sizing: border-box;
        }

        input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
        }

        /* Autocomplete UI */
        .autocomplete-wrapper { position: relative; }
        .autocomplete-list {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            max-height: 250px;
            overflow-y: auto;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid var(--accent);
            border-radius: 8px;
            margin-top: 4px;
            z-index: 50;
            list-style: none;
            padding: 0;
            display: none;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }
        .autocomplete-item {
            padding: 10px 14px;
            cursor: pointer;
            border-bottom: 1px solid var(--border-color);
        }
        .autocomplete-item:hover { background: rgba(139, 92, 246, 0.2); }
        .autocomplete-item:last-child { border-bottom: none; }
        .autocomplete-title { font-weight: 600; color: var(--text-main); }
        .autocomplete-sub { font-size: 0.8rem; color: var(--text-sub); margin-top: 2px;}


        button {
            background: var(--accent);
            color: white;
            border: none;
            padding: 12px 24px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s ease, transform 0.1s ease;
            width: 100%;
            margin-top: 24px;
        }

        button:hover { background: var(--accent-hover); }
        button:active { transform: scale(0.98); }
        button:disabled { background: #475569; cursor: not-allowed; transform: none; }

        .status-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .progress-text { margin: 0; color: var(--accent); font-weight: 600; }
        .log-text { color: var(--text-sub); font-size: 0.9rem; }

        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }

        .flight-card {
            background: rgba(30, 41, 59, 0.9);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s ease, border-color 0.2s ease;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .flight-card:hover {
            transform: translateY(-4px);
            border-color: var(--accent);
        }

        .flight-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 12px;
        }

        .price { font-size: 1.5rem; font-weight: 700; color: var(--success); }
        .trip-name { font-weight: 600; color: var(--text-main); font-size: 1.1rem; }
        
        .flight-details {
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 0.9rem;
            color: var(--text-sub);
        }
        
        .flight-link {
            text-decoration: none;
            color: var(--accent);
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            margin-top: auto;
        }
        
        .flight-link:hover { text-decoration: underline; }

        .tag {
            background: rgba(139, 92, 246, 0.2);
            color: var(--accent);
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            white-space: nowrap;
        }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .scanning { animation: pulse 1.5s infinite ease-in-out; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Travel Planner Pro</h1>
        <p style="color: var(--text-sub); margin-top: 0; margin-bottom: 30px;">Premium end-to-end trip logic via Native Engine</p>

        <div class="tab-container">
            <div class="tab active" onclick="switchTab('flights')">Flights Only</div>
            <div class="tab" onclick="switchTab('combined')">Combined Trip Planner</div>
        </div>
        
        <div class="glass-panel" id="resultsPanel" style="display: block; margin-bottom: 16px;">
            <div class="status-container" style="margin: 0;">
                <div class="progress-text scanning" id="progressStatus">Downloading Global Airports Dataset...</div>
                <div class="log-text" id="currentTrip"></div>
            </div>
        </div>

        <!-- FLIGHTS TAB -->
        <div id="flightsTab" class="tab-content active">
            <div class="glass-panel">
                <form id="searchForm">
                    <div class="form-grid">
                        <div class="input-group">
                            <label>Origins (Comma separated)</label>
                            <input type="text" id="origins" value="PVU" autocomplete="off" required>
                        </div>
                        <div class="input-group">
                            <label>Destination(s) (Comma separated)</label>
                            <input type="text" id="dest" value="DFW" autocomplete="off" required>
                        </div>
                        <div class="input-group">
                            <label>Date Window Start</label>
                            <input type="date" id="start" value="2026-04-17" required>
                        </div>
                        <div class="input-group">
                            <label>Date Window End</label>
                            <input type="date" id="end" value="2026-04-25" required>
                        </div>
                        <div class="input-group">
                            <label>Trip Durations (Days)</label>
                            <input type="text" id="durations" value="5, 6, 7" required>
                        </div>
                        <div class="input-group">
                            <label>Airline Required</label>
                            <input type="text" id="airline" value="American">
                        </div>
                        <div class="input-group">
                            <label>Max Stops</label>
                            <select id="stops" class="glass-input" style="height: 48px; width: 100%; border-radius: 8px; background: rgba(15,23,42,0.6); color: white; border: 1px solid var(--border-color); padding: 0 16px;">
                                <option value="NON_STOP" selected>Nonstop Only</option>
                                <option value="1">Up to 1 Stop</option>
                                <option value="ANY">Any Stops</option>
                            </select>
                        </div>
                    </div>
                    <button type="submit" id="submitBtn">Start Scanning Flights</button>
                </form>
            </div>
            <div id="flightResults" class="results-grid"></div>
        </div>

        <!-- COMBINED TAB -->
        <div id="combinedTab" class="tab-content">
            <div class="glass-panel">
                <form id="combinedForm">
                    <div class="form-grid">
                        <div class="input-group">
                            <label>Origins</label>
                            <input type="text" id="c_origins" value="PVU" autocomplete="off" required>
                        </div>
                        <div class="input-group">
                            <label>Destination Airport(s)</label>
                            <input type="text" id="c_dest" value="DFW" autocomplete="off" required>
                        </div>
                        <div class="input-group">
                            <label>Hotel Search City</label>
                            <input type="text" id="c_city" value="Dallas TX" required>
                        </div>
                        <div class="input-group">
                            <label>Start Date</label>
                            <input type="date" id="c_start" value="2026-04-18" required>
                        </div>
                        <div class="input-group">
                            <label>End Date</label>
                            <input type="date" id="c_end" value="2026-04-25" required>
                        </div>
                        <div class="input-group">
                            <label>Durations (Days)</label>
                            <input type="text" id="c_durations" value="5, 6" required>
                        </div>
                        <div class="input-group">
                            <label>Max Stops</label>
                            <select id="c_stops" class="glass-input" style="height: 48px; width: 100%; border-radius: 8px; background: rgba(15,23,42,0.6); color: white; border: 1px solid var(--border-color); padding: 0 16px;">
                                <option value="NON_STOP">Nonstop Only</option>
                                <option value="1">Up to 1 Stop</option>
                                <option value="ANY" selected>Any Stops (Recommended)</option>
                            </select>
                        </div>
                    </div>
                    <button type="submit" id="combinedBtn">Run Complete Trip Analysis</button>
                </form>
            </div>
            <div id="combinedResults"></div>
        </div>
    </div>

    <script>
        // === AUTOCOMPLETE LOGIC ===
        let globalAirports = [];
        const loadingIndicator = document.getElementById('progressStatus');

        fetch('https://raw.githubusercontent.com/mwgg/Airports/master/airports.json')
            .then(r => r.json())
            .then(data => {
                const valid = [];
                for (let key in data) {
                    let a = data[key];
                    if (a.country === 'US' && a.iata && a.iata.length === 3) {
                        valid.push({
                            iata: a.iata.toUpperCase(),
                            name: a.name,
                            city: a.city || '',
                            state: a.state || ''
                        });
                    }
                }
                globalAirports = valid;
                loadingIndicator.textContent = `✅ Ready! Loaded ${valid.length} robust US airports. Type states or codes.`;
                loadingIndicator.classList.remove('scanning');
            })
            .catch(err => {
                loadingIndicator.textContent = `Warning: Couldn't fetch autocomplete database.`;
                loadingIndicator.classList.remove('scanning');
            });

        function buildSuggestions(inputStr) {
            if (!inputStr || inputStr.length < 2) return [];
            inputStr = inputStr.toLowerCase().trim();
            const matches = [];
            
            const allInState = globalAirports.filter(a => a.state.toLowerCase() === inputStr);
            if (allInState.length >= 1) {
                matches.push({
                    type: 'STATE_BULK',
                    title: `Select all ${allInState.length} airports in ${allInState[0].state}`,
                    sub: allInState.map(x => x.iata).join(', '),
                    code: allInState.map(x => x.iata).join(', ')
                });
            }

            let count = 0;
            for (let i = 0; i < globalAirports.length; i++) {
                let a = globalAirports[i];
                if (a.iata.toLowerCase().includes(inputStr) ||
                    a.city.toLowerCase().includes(inputStr) ||
                    a.state.toLowerCase().includes(inputStr) ||
                    a.name.toLowerCase().includes(inputStr)) 
                {
                    matches.push({
                        type: 'SINGLE',
                        title: `${a.name} (${a.iata})`,
                        sub: `${a.city}, ${a.state}`,
                        code: a.iata
                    });
                    count++;
                }
                if (count >= 15) break; 
            }
            return matches;
        }

        function bindAutocomplete(inputId, isMulti, fillSub) {
            const inp = document.getElementById(inputId);
            const wrapper = inp.parentElement;
            wrapper.classList.add('autocomplete-wrapper');
            const list = document.createElement('ul');
            list.className = 'autocomplete-list';
            wrapper.appendChild(list);
            
            inp.addEventListener('input', (e) => {
                let val = e.target.value;
                let currentSearch = val;
                let prefix = "";
                if (isMulti && val.includes(',')) {
                    let parts = val.split(',');
                    currentSearch = parts[parts.length - 1].trim();
                    prefix = parts.slice(0, -1).join(', ') + ', ';
                } else if (isMulti) {
                    currentSearch = val.trim();
                    prefix = "";
                }
                const hints = buildSuggestions(currentSearch);
                if (hints.length === 0) {
                    list.style.display = 'none';
                    return;
                }
                list.style.display = 'block';
                list.innerHTML = '';
                hints.forEach(h => {
                    const li = document.createElement('li');
                    li.className = 'autocomplete-item';
                    if (h.type === 'STATE_BULK') li.style.borderLeft = "4px solid var(--success)";
                    li.innerHTML = `<div class="autocomplete-title">${h.title}</div><div class="autocomplete-sub">${h.sub}</div>`;
                    li.addEventListener('mousedown', (evt) => {
                        evt.preventDefault();
                        inp.value = isMulti ? (prefix + (fillSub ? h.sub : h.code)) : (fillSub ? h.sub : h.code);
                        list.style.display = 'none';
                    });
                    list.appendChild(li);
                });
            });
            inp.addEventListener('blur', () => { setTimeout(() => { list.style.display = 'none'; }, 200); });
        }

        bindAutocomplete('origins', true, false);
        bindAutocomplete('dest', true, false);
        bindAutocomplete('c_origins', true, false);
        bindAutocomplete('c_dest', true, false);
        bindAutocomplete('c_city', false, true);

        function switchTab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(id + 'Tab').classList.add('active');
        }

        // === ENGINE SUBMIT LOGIC ===
        let eventSource = null;

        document.getElementById('searchForm').addEventListener('submit', function(e) {
            e.preventDefault();
            if (eventSource) { eventSource.close(); }
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('submitBtn').innerHTML = 'Scaling Parallel Scan <span class="scanning">...</span>';
            document.getElementById('flightResults').innerHTML = '';
            document.getElementById('progressStatus').textContent = 'Initializing engine...';
            document.getElementById('progressStatus').classList.add('scanning');
            
            const origins = document.getElementById('origins').value;
            const dest = document.getElementById('dest').value;
            const start = document.getElementById('start').value;
            const end = document.getElementById('end').value;
            const durations = document.getElementById('durations').value;
            const airline = document.getElementById('airline').value;
            const stops = document.getElementById('stops').value;

            const url = `/scan?origins=${encodeURIComponent(origins)}&dest=${encodeURIComponent(dest)}&start=${start}&end=${end}&durations=${encodeURIComponent(durations)}&airline=${encodeURIComponent(airline)}&stops=${encodeURIComponent(stops)}`;
            
            eventSource = new EventSource(url);
            eventSource.addEventListener('status', (e) => {
                const data = JSON.parse(e.data);
                document.getElementById('progressStatus').textContent = data.message;
            });
            eventSource.addEventListener('progress', (e) => {
                const data = JSON.parse(e.data);
                document.getElementById('progressStatus').textContent = `Scanning (${data.current}/${data.total})`;
                document.getElementById('currentTrip').textContent = data.trip;
            });
            eventSource.addEventListener('flight_found', (e) => {
                const f = JSON.parse(e.data);
                addCard(f);
            });
            eventSource.addEventListener('complete', (e) => {
                const data = JSON.parse(e.data);
                document.getElementById('progressStatus').textContent = "Scan Complete ✅";
                document.getElementById('progressStatus').classList.remove('scanning');
                document.getElementById('submitBtn').disabled = false;
                document.getElementById('submitBtn').textContent = 'Scan Complete! Re-scan';
                document.getElementById('currentTrip').textContent = "";
                if(document.getElementById('flightResults').children.length === 0) {
                    document.getElementById('flightResults').innerHTML = '<p style="color: var(--text-sub)">No results found.</p>';
                }
                eventSource.close();
            });
            eventSource.onerror = (e) => {
                document.getElementById('progressStatus').textContent = "Connection Terminated ❌ (Check Engine Logs)";
                document.getElementById('progressStatus').classList.remove('scanning');
                document.getElementById('submitBtn').disabled = false;
                eventSource.close();
            };
        });

        function addCard(res) {
            const grid = document.getElementById('flightResults');
            const card = document.createElement('div');
            card.className = 'flight-card';
            card.innerHTML = `
                <div class="flight-header">
                    <span class="trip-name">${res.trip.name}</span>
                    <span class="price">$${res.price.toFixed(0)}</span>
                </div>
                <div class="flight-details">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span>🛫 Depart: <span style="color:var(--text-main); font-weight:600;">${res.out_depart}</span></span>
                        <div class="tag">${res.airline}</div>
                    </div>
                </div>
                <a href="${res.url}" class="flight-link" target="_blank">View on Google Flights ↗</a>
            `;
            grid.appendChild(card);
        }

        document.getElementById('combinedForm').addEventListener('submit', function(e) {
            e.preventDefault();
            if (eventSource) { eventSource.close(); }
            const btn = document.getElementById('combinedBtn');
            btn.disabled = true;
            btn.textContent = 'Analyzing Combined Trip...';
            document.getElementById('combinedResults').innerHTML = '';
            document.getElementById('progressStatus').textContent = 'Starting parallel trip scans...';
            document.getElementById('progressStatus').classList.add('scanning');

            const o = document.getElementById('c_origins').value;
            const d = document.getElementById('c_dest').value;
            const c = document.getElementById('c_city').value;
            const s = document.getElementById('c_start').value;
            const e_d = document.getElementById('c_end').value;
            const st = document.getElementById('c_stops').value;
            const dur = document.getElementById('c_durations').value;

            const url = `/scan_combined?origins=${encodeURIComponent(o)}&dest=${encodeURIComponent(d)}&city=${encodeURIComponent(c)}&start=${s}&end=${e_d}&durations=${encodeURIComponent(dur)}&stops=${encodeURIComponent(st)}`;
            
            eventSource = new EventSource(url);
            eventSource.addEventListener('status', (e) => {
                const data = JSON.parse(e.data);
                document.getElementById('progressStatus').textContent = data.message;
            });
            eventSource.addEventListener('progress', (e) => {
                const data = JSON.parse(e.data);
                document.getElementById('progressStatus').textContent = `Scanning (${data.current}/${data.total})`;
                document.getElementById('currentTrip').textContent = data.trip;
            });
            eventSource.addEventListener('trip_found', (e) => {
                const data = JSON.parse(e.data);
                addTripCard(data);
            });
            eventSource.addEventListener('complete', (e) => {
                document.getElementById('progressStatus').textContent = "Optimization Complete ✅";
                document.getElementById('progressStatus').classList.remove('scanning');
                btn.disabled = false;
                btn.textContent = 'Refresh Analysis';
                eventSource.close();
            });
        });

        function addTripCard(data) {
            const container = document.getElementById('combinedResults');
            const card = document.createElement('div');
            card.className = 'trip-itinerary-card';
            const total = data.flight.price + data.hotel.total_f;
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <h2 style="margin:0; font-size:1.4rem;">${data.dates}</h2>
                        <div style="color:var(--text-sub); margin-top:4px;">Total Trip Estimate: <span style="color:var(--success); font-weight:700; font-size:1.2rem;">$${total.toFixed(0)}</span></div>
                    </div>
                    <div class="tag" style="background:rgba(255,255,255,0.05)">${data.hotel.city}</div>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
                    <div style="background:rgba(15,23,42,0.4); padding:12px; border-radius:8px; border-left: 3px solid var(--accent);">
                        <div style="font-weight:700; color:var(--accent); font-size:0.8rem; text-transform:uppercase; margin-bottom:8px;">Flight</div>
                        <div style="font-size:1.1rem; font-weight:600;">$${data.flight.price}</div>
                        <div style="font-size:0.85rem; color:var(--text-sub); margin-top:4px;">${data.flight.airline}</div>
                    </div>
                    <div style="background:rgba(15,23,42,0.4); padding:12px; border-radius:8px; border-left: 3px solid var(--success);">
                        <div style="font-weight:700; color:var(--success); font-size:0.8rem; text-transform:uppercase; margin-bottom:8px;">Hotel</div>
                        <div style="font-size:1.1rem; font-weight:600;">$${data.hotel.total_f.toFixed(0)} Total</div>
                        <div style="font-size:0.85rem; color:var(--text-main); margin-top:4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${data.hotel.name}</div>
                        <div style="font-size:0.85rem; color:var(--text-sub);">${data.hotel.rating} Stars</div>
                    </div>
                </div>
                <div class="booking-actions">
                    <a href="${data.flight.url}" target="_blank" class="btn-book btn-flight">Book Flight 🛫</a>
                    <a href="${data.hotel.url}" target="_blank" class="btn-book btn-hotel">Book Hotel 🏨</a>
                </div>
            `;
            container.appendChild(card);
        }
    </script>
</body>
</html>
"""

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread so requests don't block each other."""
    allow_reuse_address = True

class FlightRequestHandler(BaseHTTPRequestHandler):
    _sse_lock = threading.Lock()

    def log_message(self, format, *args):
        return

    def _send_sse(self, event, data):
        with self._sse_lock:
            try:
                self.wfile.write(f"event: {event}\n".encode('utf-8'))
                self.wfile.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
        elif self.path.startswith('/scan_combined'):
            self.handle_combined_scan()
        elif self.path.startswith('/scan'):
            self.handle_scan()
        else:
            self.send_error(404)
            
    def handle_scan(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        send_event = self._send_sse
        
        origins = [o.strip() for o in params.get('origins', ['PVU'])[0].split(',') if o.strip()]
        dests = [d.strip() for d in params.get('dest', ['DFW'])[0].split(',') if d.strip()]
        start_date_str = params.get('start', ['2026-04-17'])[0]
        end_date_str = params.get('end', ['2026-04-25'])[0]
        
        try:
            durations = [int(float(d.strip())) for d in params.get('durations', ['4,5,6'])[0].split(',')]
        except:
            durations = [4, 5, 6]
            
        airline_filter = params.get('airline', ['American'])[0]
        stops_filter = params.get('stops', ['NON_STOP'])[0]
        
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        except:
            send_event('status', {'message': 'Invalid dates.'})
            send_event('complete', {'results': []})
            return

        trips = []
        for orig in origins:
            for dest in dests:
                for duration in durations:
                    curr = start_dt
                    while curr <= end_dt:
                        ret_dt = curr + timedelta(days=duration)
                        if ret_dt <= end_dt:
                            trips.append({
                                "name": f"{orig}->{dest} ({curr.strftime('%b %d')})",
                                "origin": orig,
                                "destination": dest,
                                "depart": curr.strftime('%Y-%m-%d'),
                                "return": ret_dt.strftime('%Y-%m-%d'),
                                "url": f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{orig}%20on%20{curr.strftime('%Y-%m-%d')}%20through%20{ret_dt.strftime('%Y-%m-%d')}"
                            })
                        curr += timedelta(days=1)
                    
        send_event('status', {'message': f'Total Trips: {len(trips)}. Scanning {len(dests)} hubs in parallel...'})
        
        counter = 0
        def process_flight(t):
            nonlocal counter
            cmd = ["uv", "run", "fli", "flights", t["origin"], t["destination"], t["depart"], "-r", t["return"], "--stops", stops_filter, "--format", "json"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    flights = data.get("flights", [])
                    if airline_filter and airline_filter.lower() != 'any':
                        flights = [f for f in flights if airline_filter.lower() in f["outbound"]["legs"][0]["airline"]["name"].lower()]
                    
                    if flights:
                        flights.sort(key=lambda x: x.get("price", 99999))
                        res = {
                            "trip": t,
                            "price": flights[0].get("price", 0),
                            "airline": flights[0]["outbound"]["legs"][0]["airline"]["name"],
                            "out_depart": flights[0]["outbound"]["legs"][0]["departure_time"].split("T")[1][:5],
                            "url": t["url"]
                        }
                        send_event('flight_found', res)
            except: pass
            counter += 1
            send_event('progress', {'current': counter, 'total': len(trips), 'trip': t['name']})

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(process_flight, trips)
        send_event('complete', {'results': []})

    def handle_combined_scan(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        send_event = self._send_sse
        
        origins = [o.strip() for o in params.get('origins', ['PVU'])[0].split(',') if o.strip()]
        dests = [d.strip() for d in params.get('dest', ['DFW'])[0].split(',') if d.strip()]
        city = params.get('city', ['Dallas TX'])[0].strip()
        start_date = params.get('start', ['2026-04-18'])[0]
        end_date = params.get('end', ['2026-04-25'])[0]
        stops_filter = params.get('stops', ['ANY'])[0]
        try:
            durations = [int(float(d.strip())) for d in params.get('durations', ['4,5,6'])[0].split(',')]
        except:
            durations = [4, 5, 6]

        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        itineraries = []
        for orig in origins:
            for dest in dests:
                for duration in durations:
                    curr = start_dt
                    while curr <= end_dt:
                        ret_dt = curr + timedelta(days=duration)
                        if ret_dt <= end_dt:
                            itineraries.append({
                                "origin": orig, "dest": dest, "depart": curr.strftime('%Y-%m-%d'), "return": ret_dt.strftime('%Y-%m-%d'),
                                "name": f"{orig}->{dest} ({curr.strftime('%b %d')})"
                            })
                        curr += timedelta(days=1)

        total = len(itineraries)
        send_event('status', {'message': f'Generated {total} combos. Starting parallel trip scans...'})
        counter = 0

        results = []
        def process_combined(it):
            nonlocal counter
            try:
                # Find destination city
                dest_city = AIRPORT_CITY_MAP.get(it["dest"], city)
                
                # Flight Search
                cmd = ["uv", "run", "fli", "flights", it["origin"], it["dest"], it["depart"], "-r", it["return"], "--stops", stops_filter, "--format", "json"]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    flights = data.get("flights", [])
                    if flights:
                        flights.sort(key=lambda x: x.get("price", 99999))
                        best_f = flights[0]
                        f_price = best_f.get("price", 0)
                        
                        # Hotel Search at Destination
                        hotels = search_hotels_core(dest_city, it["depart"], it["return"])
                        if hotels:
                            best_h = hotels[0]
                            h_total = float(best_h["total_price"].replace("$", "").replace(",", "")) if "$" in best_h["total_price"] else 0
                            
                            # Deep Links
                            f_url = f"https://www.google.com/travel/flights?q=flights+from+{it['origin']}+to+{it['dest']}+on+{it['depart']}+returning+{it['return']}"
                            h_url = f"https://www.google.com/travel/hotels?q=hotels+in+{urllib.parse.quote(dest_city)}+checkin+{it['depart']}+checkout+{it['return']}"

                            results.append({
                                "total_estimate": f_price + h_total,
                                "dates": it["name"],
                                "flight": {
                                    "price": f_price, 
                                    "airline": best_f["outbound"]["legs"][0]["airline"]["name"],
                                    "url": f_url
                                },
                                "hotel": {
                                    "name": best_h["name"], 
                                    "rating": best_h["rating"], 
                                    "total_f": h_total,
                                    "url": h_url,
                                    "city": dest_city
                                }
                            })
            except: pass
            counter += 1
            send_event('progress', {'current': counter, 'total': total, 'trip': it['name']})

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(process_combined, itineraries)

        # Final Sort: Least to most expensive
        results.sort(key=lambda x: x["total_estimate"])
        
        # Batch send results
        for res in results:
            send_event('trip_found', res)
            
        send_event('complete', {})

if __name__ == "__main__":
    server = ThreadedHTTPServer(('localhost', 8000), FlightRequestHandler)
    print("🛫 Dashboard: http://localhost:8000")
    webbrowser.open("http://localhost:8000")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    server.server_close()
