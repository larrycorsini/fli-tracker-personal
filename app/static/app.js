/* ═══════════════════════════════════════════════════════════════════════════
   Travel Planner Pro — App Logic
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────
const state = {
  flightResults: [],
  hotelResults: [],
  trackedFlights: [],
  activeTab: 'flights',
  eventSource: null,
  tripType: 'round_trip',
  pendingTrack: null,
  currency: 'USD',
  exchangeRates: { USD: 1.0 },
  combinedResults: [],
};

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setDefaultDates();
  initTabs();
  initTripTypeToggles();
  initAutocompletes();
  initForms();
  initAdvancedFilters();
  initTrackerForm();
  restoreFromStorage();
  fetchRates();
});

async function fetchRates() {
  try {
    const res = await fetch('/api/rates');
    const data = await res.json();
    if (data.success && data.rates) {
      state.exchangeRates = data.rates;
    }
  } catch (err) {
    console.error('Failed to fetch exchange rates:', err);
  }
}

function updateCurrency() {
  const select = document.getElementById('currency-select');
  if (select) {
    state.currency = select.value;
    saveToStorage();
  }
  
  // Re-render UI
  // Flights
  const fGrid = document.getElementById('flights-results');
  if (fGrid) {
    fGrid.innerHTML = '';
    state.flightResults.forEach(f => appendFlightCard(f));
  }
  // Hotels
  const hGrid = document.getElementById('hotels-results');
  if (hGrid) {
    hGrid.innerHTML = '';
    state.hotelResults.forEach(h => hGrid.appendChild(buildHotelCard(h)));
  }
  // Combined
  const cGrid = document.getElementById('combined-results');
  if (cGrid) {
    cGrid.innerHTML = '';
    state.combinedResults.forEach(c => appendTripCard(c));
  }
  // Tracker & Trips
  if (state.activeTab === 'tracker') fetchTrackedFlights();
  if (state.activeTab === 'trips') fetchTrips();
}

function formatPrice(val) {
  if (val === null || val === undefined || val === 'N/A' || val === '') return 'N/A';
  let num = typeof val === 'number' ? val : parseFloat(String(val).replace(/[$,a-zA-Z\s]/g, ''));
  if (isNaN(num)) return val;
  const rate = state.exchangeRates[state.currency] || 1.0;
  return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: state.currency,
      maximumFractionDigits: 0
  }).format(num * rate);
}

function setDefaultDates() {
  const today = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;

  const t = new Date(today); t.setDate(t.getDate() + 14);
  const end = new Date(today); end.setDate(today.getDate() + 35);
  const ret = new Date(t); ret.setDate(t.getDate() + 5);

  const fields = {
    'f-start': fmt(t), 'f-end': fmt(ret),
    'c-start': fmt(t), 'c-end': fmt(end),
    'd-start': fmt(t), 'd-end': fmt(end),
    'h-checkin': fmt(t), 'h-checkout': fmt(ret),
  };
  for (const [id, val] of Object.entries(fields)) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }
}

// ── Tab Navigation ─────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const id = tab.dataset.tab;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${id}`).classList.add('active');
      state.activeTab = id;
      if (id === 'tracker') loadTrackedFlights();
      if (id === 'trips') loadTrips();
    });
  });
}

// ── Trip Type Toggle (Flights) ─────────────────────────────────────────────
function initTripTypeToggles() {
  document.querySelectorAll('.trip-type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.closest('.trip-type-toggle');
      group.querySelectorAll('.trip-type-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.tripType = btn.dataset.trip;
      updateFlightFormForTripType();
    });
  });
}

function updateFlightFormForTripType() {
  const isOneWay = state.tripType === 'one_way';
  const endGroup = document.getElementById('f-end-group');
  const durGroup = document.getElementById('f-dur-group');
  const endInput = document.getElementById('f-end');
  if (endGroup) endGroup.classList.toggle('hidden', isOneWay);
  if (durGroup) durGroup.classList.toggle('hidden', isOneWay);
  if (endInput) endInput.required = !isOneWay;
}

// ── Autocomplete ──────────────────────────────────────────────────────────
const AC_CONFIGS = [
  { inputId: 'f-origins',      listId: 'ac-f-origins',      multi: true,  cityFill: false },
  { inputId: 'f-destinations', listId: 'ac-f-destinations',  multi: true,  cityFill: false },
  { inputId: 'c-origins',      listId: 'ac-c-origins',       multi: true,  cityFill: false },
  { inputId: 'c-destinations', listId: 'ac-c-destinations',  multi: true,  cityFill: false },
  { inputId: 'd-origin',       listId: 'ac-d-origin',        multi: false, cityFill: false },
  { inputId: 'd-destination',  listId: 'ac-d-destination',   multi: false, cityFill: false },
  { inputId: 'h-city',         listId: 'ac-h-city',          multi: false, cityFill: true  },
  { inputId: 't-origin',       listId: 'ac-t-origin',        multi: false, cityFill: false },
  { inputId: 't-destination',  listId: 'ac-t-destination',   multi: false, cityFill: false },
];

function initAutocompletes() {
  AC_CONFIGS.forEach(cfg => bindAutocomplete(cfg));
}

function bindAutocomplete({ inputId, listId, multi, cityFill }) {
  const input = document.getElementById(inputId);
  const list = document.getElementById(listId);
  if (!input || !list) return;

  let debounceTimer;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      let query = input.value;
      if (multi && query.includes(',')) {
        const parts = query.split(',');
        query = parts[parts.length - 1].trim();
      }
      if (query.length < 2) { list.classList.remove('visible'); return; }

      fetch(`/api/airports?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(items => renderAutocomplete(input, list, items, multi, cityFill))
        .catch(() => list.classList.remove('visible'));
    }, 180);
  });

  input.addEventListener('blur', () => setTimeout(() => list.classList.remove('visible'), 200));
  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') list.classList.remove('visible');
  });
}

function renderAutocomplete(input, list, items, multi, cityFill) {
  if (!items.length) { list.classList.remove('visible'); return; }
  list.innerHTML = '';
  items.forEach(item => {
    const li = document.createElement('li');
    li.className = `autocomplete-item${item.type === 'STATE_BULK' ? ' state-bulk' : ''}`;
    li.innerHTML = `<div class="autocomplete-title">${item.title}</div>
                    <div class="autocomplete-sub">${item.subtitle || ''}</div>`;
    li.addEventListener('mousedown', e => {
      e.preventDefault();
      const val = cityFill ? item.subtitle : item.code;
      if (multi) {
        const parts = input.value.split(',');
        parts[parts.length - 1] = ' ' + val;
        input.value = parts.join(',').replace(/^,\s*/, '');
      } else {
        input.value = val;
      }
      list.classList.remove('visible');
      // Auto-fill hotel city when destination changes in combined tab
      if (input.id === 'c-destinations') resolveHotelCity(val.split(',')[0].trim());
    });
    list.appendChild(li);
  });
  list.classList.add('visible');
}

async function resolveHotelCity(iata) {
  if (!iata || iata.length !== 3) return;
  try {
    const r = await fetch(`/api/resolve-city?iata=${iata}`);
    const data = await r.json();
    if (data.city) document.getElementById('c-hotel-city').value = data.city;
  } catch (_) {}
}

// ── Advanced Filters ──────────────────────────────────────────────────────
function initAdvancedFilters() {
  const btn = document.getElementById('flightsAdvToggle');
  const panel = document.getElementById('flightsAdvFilters');
  if (!btn || !panel) return;
  btn.addEventListener('click', () => {
    btn.classList.toggle('open');
    panel.classList.toggle('visible');
  });
}

// ── Form Submissions ──────────────────────────────────────────────────────
function initForms() {
  document.getElementById('flightsForm').addEventListener('submit', handleFlightSearch);
  document.getElementById('hotelsForm').addEventListener('submit', handleHotelSearch);
  document.getElementById('combinedForm').addEventListener('submit', handleCombinedSearch);
  document.getElementById('datesForm').addEventListener('submit', handleDatesSearch);
}

function cancelActiveSearch() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
}

// ── Flights Search ─────────────────────────────────────────────────────────
function handleFlightSearch(e) {
  e.preventDefault();
  cancelActiveSearch();
  state.flightResults = [];

  const origins = document.getElementById('f-origins').value;
  const destinations = document.getElementById('f-destinations').value;
  const startDate = document.getElementById('f-start').value;
  const endDate = state.tripType === 'one_way' ? startDate : (document.getElementById('f-end').value || startDate);
  const durations = document.getElementById('f-durations').value || '5';
  const stops = document.getElementById('f-stops').value;
  const cabin = document.getElementById('f-cabin').value;
  const airline = document.getElementById('f-airline').value;

  if (!origins || !destinations) { showToast('Please enter origin and destination', 'error'); return; }

  // Save to Recent Searches
  const searchParams = { origins, destinations, startDate, endDate, cabin, timestamp: Date.now() };
  let recentSearches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
  recentSearches = recentSearches.filter(s => s.origins !== origins || s.destinations !== destinations || s.startDate !== startDate).slice(0, 4);
  recentSearches.unshift(searchParams);
  localStorage.setItem('recentSearches', JSON.stringify(recentSearches));
  renderRecentSearches();

  document.getElementById('flights-results').innerHTML = '';
  document.getElementById('flights-results-header').classList.add('hidden');
  const insightsBanner = document.getElementById('flights-insights');
  insightsBanner.classList.add('hidden');
  insightsBanner.innerHTML = '';
  
  // Fetch insights
  fetch(`/api/search/insights?origin=${origins}&destination=${destinations}`)
    .then(r => r.json())
    .then(data => {
      if (data.success && data.insights) {
        const ins = data.insights;
        insightsBanner.innerHTML = `
          <div class="insights-icon">📊</div>
          <div class="insights-content" style="flex:1;">
            <h4>Best Time to Book</h4>
            <p>Based on our tracking history for <strong>${origins} &rarr; ${destinations}</strong>. Typical prices are around ${formatPrice(ins.avg)}.</p>
            <div class="insights-price-bar">
              <span class="insights-price-marker great">Great: &lt; ${formatPrice(ins.great)}</span>
              <span class="insights-price-marker">Typical</span>
              <span class="insights-price-marker high">High: &gt; ${formatPrice(ins.high)}</span>
            </div>
          </div>
        `;
        insightsBanner.classList.remove('hidden');
      }
    }).catch(console.error);
  setSearching(true, 'Starting flight search...');
  setBtn('flightsBtn', true, 'Searching...');

  const params = new URLSearchParams({ origins, destinations, start_date: startDate, end_date: endDate, durations, max_stops: stops, cabin_class: cabin, airline, trip_type: state.tripType });
  const es = new EventSource(`/api/search/flights?${params}`);
  state.eventSource = es;

  es.addEventListener('status', e => setStatus(JSON.parse(e.data).message));
  es.addEventListener('progress', e => {
    const d = JSON.parse(e.data);
    setStatus(`Scanning ${d.current}/${d.total}`, d.trip);
  });
  es.addEventListener('flight_found', e => {
    const data = JSON.parse(e.data);
    
    // If the backend sent all_results (array of flights), use them
    if (data.all_results && data.all_results.length > 0) {
      // Just take the best one or all of them? The stream yields the 'best' flight summary for a trip,
      // but we attached all_results to it. Let's push all of them to give user full filterability.
      data.all_results.forEach(f => {
         // Merge in trip info if missing
         if(!f.depart_date) f.depart_date = data.depart_date;
         if(!f.return_date && data.return_date) f.return_date = data.return_date;
         if(!f.origin) f.origin = data.origin;
         if(!f.destination) f.destination = data.destination;
         state.flightResults.push(f);
      });
    } else {
      state.flightResults.push(data);
    }
    
    scheduleRenderFlights();
  });
  es.addEventListener('complete', e => {
    const d = JSON.parse(e.data);
    setSearching(false, `✅ Found ${state.flightResults.length} results`);
    setBtn('flightsBtn', false, 'Search Flights');
    renderFlights();
    if (!state.flightResults.length) showEmpty('flights-results', '✈️', 'No flights found for these parameters. Try adjusting your dates or stops filter.');
    es.close();
  });
  es.onerror = () => {
    setSearching(false, '❌ Connection error — check console');
    setBtn('flightsBtn', false, 'Search Flights');
    showToast('Search failed — see console for details', 'error');
    es.close();
  };
}

let renderTimer = null;
function scheduleRenderFlights() {
  if (renderTimer) cancelAnimationFrame(renderTimer);
  renderTimer = requestAnimationFrame(() => renderFlights());
}

function renderFlights() {
  const grid = document.getElementById('flights-results');
  
  // Update filter dropdowns if this is the first render or if new airlines arrived
  const airlineSelect = document.getElementById('local-filter-airline');
  const currentAirline = airlineSelect.value;
  const uniqueAirlines = [...new Set(state.flightResults.map(f => f.airline_name || f.airline).filter(Boolean))].sort();
  
  airlineSelect.innerHTML = '<option value="any">All Airlines</option>' + 
    uniqueAirlines.map(a => `<option value="${a}" ${currentAirline === a ? 'selected' : ''}>${a}</option>`).join('');

  // Get active filters
  const stopsFilter = document.getElementById('local-filter-stops').value;
  const cabinFilter = document.getElementById('local-filter-cabin').value;
  
  // Filter results
  let filtered = state.flightResults.filter(f => {
    if (stopsFilter !== 'any') {
      const stops = parseInt(stopsFilter, 10);
      if (f.stops > stops) return false;
    }
    if (currentAirline !== 'any' && currentAirline !== '') {
      const name = f.airline_name || f.airline || '';
      if (name !== currentAirline) return false;
    }
    if (cabinFilter !== 'any' && cabinFilter !== '') {
      if (f.cabin_class !== cabinFilter) return false;
    }
    return true;
  });

  // Sort results
  const mode = document.getElementById('flights-sort').value;
  filtered.sort((a, b) => {
    if (mode === 'price') return parseFloat(a.price) - parseFloat(b.price);
    if (mode === 'price-desc') return parseFloat(b.price) - parseFloat(a.price);
    if (mode === 'departure') return (a.departure_time || '').localeCompare(b.departure_time || '');
    if (mode === 'airline') return (a.airline || '').localeCompare(b.airline || '');
    if (mode === 'route') {
      const routeA = `${a.origin}-${a.destination}`;
      const routeB = `${b.origin}-${b.destination}`;
      const routeCmp = routeA.localeCompare(routeB);
      if (routeCmp !== 0) return routeCmp;
      return parseFloat(a.price) - parseFloat(b.price);
    }
    return 0;
  });

  // Render
  grid.innerHTML = filtered.map(f => buildFlightCardHTML(f)).join('');
  updateResultsHeader('flights-results-header', 'flights-count', filtered.length, 'flights');
}

function buildFlightCardHTML(f) {
  const grid = document.getElementById('flights-results');
  const stopsLabel = f.stops === 0 ? '<span class="tag tag-nonstop">Nonstop</span>' : `<span class="tag tag-stops">${f.stops} stop${f.stops > 1 ? 's' : ''}</span>`;
  const returnRow = f.return_date ? `<div class="card-detail-row"><span>🛏 Return</span><span>${f.return_date}</span></div>` : '';

  // Layover warnings
  let layoverWarnings = '';
  const allLayovers = (f.layovers || []).concat(f.return_layovers || []);
  allLayovers.forEach(lay => {
    if (lay.duration < 60) layoverWarnings += `<div class="card-warning">⚠️ Short layover: ${lay.duration}m in ${lay.airport}</div>`;
    else if (lay.duration > 240) layoverWarnings += `<div class="card-warning">⏳ Long layover: ${Math.floor(lay.duration/60)}h ${lay.duration%60}m in ${lay.airport}</div>`;
  });

  // Refund eligibility badge
  let refundBadge = '';
  if (f.refund_badge) {
    refundBadge = `<span class="refund-badge badge-${f.refund_badge}" title="${f.refund_type || ''}">${f.refund_badge_label || f.refund_badge}</span>`;
  }

  // Track button
  const trackData = JSON.stringify({
    origin: f.origin || '', destination: f.destination || '',
    depart_date: f.depart_date || '', return_date: f.return_date || '',
    airline: f.airline_name || f.airline || '', price: f.price,
    cabin_class: 'ECONOMY'
  }).replace(/"/g, '&quot;');
  const trackBtn = `<button class="btn-track" onclick='openTrackModal(${trackData})'>📊 Track</button>`;

  return `
  <div class="flight-card" data-price="${f.price}" data-departure="${f.departure_time || ''}" data-airline="${f.airline || ''}" data-route="${f.origin}-${f.destination}">
    <div class="card-header">
      <div>
        <div class="card-route">${f.origin || ''} → ${f.destination || ''}</div>
        <div class="card-dates">${f.depart_date}${f.return_date ? ' – ' + f.return_date : ''}</div>
      </div>
      <div class="card-price-group">
        <div class="card-price">${formatPrice(f.price)}</div>
        <div class="card-price-level">${priceBadge}</div>
      </div>
    </div>
    <div class="card-actions">
        ${trackBtn}
        <button class="btn-outline" onclick='openAddToTripModal("flight", ${trackData})'>🎒 Add to Trip</button>
        ${f.refund_badge ? `<span class="tag tag-${f.refund_badge}">${f.refund_badge_label}</span>` : ''}
    </div>
    <div class="card-details">
      ${layoverWarnings}
      <div class="card-detail-row">
        <span>🛫 ${f.departure_time || '—'} → ${f.arrival_time || '—'}</span>
        ${stopsLabel}
      </div>
      ${returnRow}
      <div class="card-detail-row">
        <span class="tag tag-airline">${f.airline || 'Unknown'}</span>
        ${f.cabin_class ? `<span class="tag tag-stops">${f.cabin_class.replace('_', ' ')}</span>` : ''}
        <span>${f.duration ? Math.floor(f.duration/60)+'h '+(f.duration%60)+'m' : ''}</span>
      </div>
    </div>
    <a href="${f.url}" target="_blank" class="card-link">View on Google Flights ↗</a>
  </div>`;
}

// ── Hotels Search ──────────────────────────────────────────────────────────
async function handleHotelSearch(e) {
  e.preventDefault();
  const city = document.getElementById('h-city').value;
  const checkin = document.getElementById('h-checkin').value;
  const checkout = document.getElementById('h-checkout').value;
  if (!city || !checkin || !checkout) { showToast('Please fill in all hotel fields', 'error'); return; }

  document.getElementById('hotels-results').innerHTML = '';
  document.getElementById('hotels-results-header').classList.add('hidden');
  setSearching(true, 'Searching hotels...');
  setBtn('hotelsBtn', true, 'Searching...');

  try {
    const params = new URLSearchParams({ city, checkin, checkout });
    const r = await fetch(`/api/search/hotels?${params}`);
    const data = await r.json();
    setSearching(false, `✅ Found ${data.hotels?.length || 0} hotels`);
    setBtn('hotelsBtn', false, 'Search Hotels');
    if (!data.success) { showToast(data.error || 'Hotel search failed', 'error'); return; }
    state.hotelResults = data.hotels || [];
    renderHotels(state.hotelResults);
    updateResultsHeader('hotels-results-header', 'hotels-count', state.hotelResults.length, 'hotels');
  } catch (err) {
    setSearching(false, '❌ Hotel search failed');
    setBtn('hotelsBtn', false, 'Search Hotels');
    showToast('Hotel search failed', 'error');
  }
}

function renderHotels(hotels) {
  const grid = document.getElementById('hotels-results');
  grid.innerHTML = '';
  if (!hotels.length) { showEmpty('hotels-results', '🏨', 'No hotels found. Try a different city or dates.'); return; }
  hotels.forEach(h => grid.appendChild(buildHotelCard(h)));
}

function buildHotelCard(h) {
  const stars = h.rating !== 'N/A' ? '★'.repeat(Math.round(parseFloat(h.rating) || 0)) : '';
  const card = document.createElement('div');
  card.className = 'hotel-card';
  card.dataset.price = parseFloat((h.total_price || '0').replace(/[$,]/g, '')) || 0;
  card.dataset.rating = parseFloat(h.rating) || 0;
  card.dataset.name = h.name || '';
  card.innerHTML = `
    <div class="hotel-name" title="${h.name}">${h.name}</div>
    <div class="hotel-rating">${stars} <span style="color:var(--text-muted);font-size:0.8rem">${h.rating !== 'N/A' ? h.rating + ' stars' : ''}</span></div>
    <div>
      <div class="hotel-price">${formatPrice(h.total_price)} <span style="font-size:0.8rem;font-weight:400;color:var(--text-muted)">total</span></div>
      <div class="hotel-per-night">${h.price_per_night ? formatPrice(h.price_per_night) + ' / night' : ''}</div>
    </div>
    <div style="display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap;">
      <a href="${h.url}" target="_blank" class="card-link" style="padding: 6px 12px; background: rgba(255,255,255,0.05); border-radius: 4px; text-decoration: none;">View ↗</a>
      <button class="btn-outline" style="padding: 6px 12px;" onclick='openAddToTripModal("hotel", ${JSON.stringify({...h, price: card.dataset.price}).replace(/"/g, '&quot;')})'>🎒 Add to Trip</button>
    </div>`;
  return card;
}

// ── Combined Search ────────────────────────────────────────────────────────
function handleCombinedSearch(e) {
  e.preventDefault();
  cancelActiveSearch();

  const origins = document.getElementById('c-origins').value;
  const destinations = document.getElementById('c-destinations').value;
  const hotelCity = document.getElementById('c-hotel-city').value;
  const startDate = document.getElementById('c-start').value;
  const endDate = document.getElementById('c-end').value;
  const durations = document.getElementById('c-durations').value || '5';
  const stops = document.getElementById('c-stops').value;

  if (!origins || !destinations) { showToast('Please enter origin and destination', 'error'); return; }

  document.getElementById('combined-results').innerHTML = '';
  setSearching(true, 'Starting combined trip analysis...');
  setBtn('combinedBtn', true, 'Analyzing...');

  const params = new URLSearchParams({ origins, destinations, start_date: startDate, end_date: endDate, durations, max_stops: stops, hotel_city: hotelCity });
  const es = new EventSource(`/api/search/combined?${params}`);
  state.eventSource = es;

  let count = 0;
  es.addEventListener('status', e => setStatus(JSON.parse(e.data).message));
  es.addEventListener('progress', e => {
    const d = JSON.parse(e.data);
    setStatus(`Analyzing ${d.current}/${d.total}`, d.trip);
  });
  es.addEventListener('trip_found', e => {
    appendTripCard(JSON.parse(e.data));
    count++;
  });
  es.addEventListener('complete', () => {
    setSearching(false, `✅ Found ${count} trip combos`);
    setBtn('combinedBtn', false, 'Find Best Trip Combos');
    if (!count) showEmpty('combined-results', '🎯', 'No combined results. Try wider date ranges or removing stops filters.');
    es.close();
  });
  es.onerror = () => {
    setSearching(false, '❌ Search error');
    setBtn('combinedBtn', false, 'Find Best Trip Combos');
    es.close();
  };
}

function appendTripCard(d) {
  const container = document.getElementById('combined-results');
  const total = d.total_estimate || 0;
  const card = document.createElement('div');
  card.className = 'trip-card';
  card.innerHTML = `
    <div class="trip-card-header">
      <div>
        <div style="font-weight:700;font-size:1.1rem">${d.label || ''}</div>
        <div style="color:var(--text-muted);font-size:0.82rem;margin-top:4px">${d.depart_date} – ${d.return_date}</div>
      </div>
      <div>
        <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:.8px;color:var(--text-muted);text-align:right">Total Est.</div>
        <div class="trip-total">${formatPrice(total)}</div>
      </div>
    </div>
    <div class="trip-grid">
      <div class="trip-segment">
        <div class="segment-label flight-label">✈️ Flight</div>
        <div class="segment-price">${formatPrice(d.flight?.price)}</div>
        <div class="segment-detail">${d.flight?.airline || ''} · ${d.flight?.departure_time || ''} · ${d.flight?.stops === 0 ? 'Nonstop' : (d.flight?.stops || 0) + ' stop(s)'}</div>
      </div>
      <div class="trip-segment hotel-segment">
        <div class="segment-label hotel-label">🏨 Hotel</div>
        <div class="segment-price">${formatPrice(d.hotel?.total_price)}</div>
        <div class="segment-detail" title="${d.hotel?.name || ''}">${(d.hotel?.name || '').substring(0, 32)}${(d.hotel?.name || '').length > 32 ? '…' : ''}</div>
        <div class="segment-detail">${d.hotel?.rating !== 'N/A' ? d.hotel?.rating + ' ★' : ''} · ${d.hotel?.city || ''}</div>
      </div>
    </div>
    <div class="booking-actions">
      <a href="${d.flight?.url || '#'}" target="_blank" class="btn-book btn-book-flight">Book Flight ✈️</a>
      <a href="${d.hotel?.url || '#'}" target="_blank" class="btn-book btn-book-hotel">Book Hotel 🏨</a>
    </div>`;
  container.appendChild(card);
}

// ── Cheapest Dates Search ──────────────────────────────────────────────────
async function handleDatesSearch(e) {
  e.preventDefault();
  const origin = document.getElementById('d-origin').value;
  const destination = document.getElementById('d-destination').value;
  const startDate = document.getElementById('d-start').value;
  const endDate = document.getElementById('d-end').value;
  const duration = document.getElementById('d-duration').value || 5;
  const stops = document.getElementById('d-stops').value;

  if (!origin || !destination) { showToast('Please enter origin and destination', 'error'); return; }

  document.getElementById('dates-results').innerHTML = '';
  setSearching(true, 'Searching for cheapest dates...');
  setBtn('datesBtn', true, 'Searching...');

  try {
    const params = new URLSearchParams({ origin, destination, start_date: startDate, end_date: endDate, durations: duration, is_round_trip: 'true', max_stops: stops });
    const r = await fetch(`/api/search/dates?${params}`);
    const data = await r.json();
    setSearching(false, data.success ? `✅ Found prices for ${data.count} dates` : '❌ Search failed');
    setBtn('datesBtn', false, 'Find Cheapest Dates');
    if (!data.success) { showToast(data.error || 'Date search failed', 'error'); return; }
    renderDateGrid(data.dates || [], origin, destination);
  } catch (err) {
    setSearching(false, '❌ Date search failed');
    setBtn('datesBtn', false, 'Find Cheapest Dates');
    showToast('Date search failed', 'error');
  }
}

function renderDateGrid(dates, origin, dest) {
  const container = document.getElementById('dates-results');
  container.innerHTML = '';
  if (!dates.length) { showEmpty('dates-results', '📅', 'No date prices found. Try a wider date range or different route.'); return; }

  const prices = dates.map(d => d.price);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const header = document.createElement('div');
  header.className = 'results-header';
  header.innerHTML = `<span class="results-count">${dates.length} dates · ${origin} → ${dest}</span><span style="color:var(--success);font-weight:700">Cheapest: ${formatPrice(minP)}</span>`;
  container.appendChild(header);

  // Check if it's 1D (one-way) or 2D (round-trip)
  const isRoundTrip = dates.some(d => d.return_date);

  if (!isRoundTrip) {
    const grid = document.createElement('div');
    grid.className = 'dates-grid';
    dates.forEach(d => {
      const ratio = (d.price - minP) / range;
      const cls = ratio < 0.25 ? 'cheapest' : ratio > 0.75 ? 'expensive' : '';
      const priceCls = ratio < 0.25 ? '' : ratio > 0.75 ? 'high' : 'mid';
      const label = fmtShortDate(d.date);
      const cell = document.createElement('div');
      cell.className = `date-cell ${cls}`;
      cell.innerHTML = `<div class="date-label">${label}</div><div class="date-price ${priceCls}">${formatPrice(d.price)}</div>`;
      grid.appendChild(cell);
    });
    container.appendChild(grid);
    return;
  }

  // 2D Heatmap for round-trip
  const depDatesSet = new Set();
  const retDatesSet = new Set();
  const priceMap = {};

  dates.forEach(d => {
    depDatesSet.add(d.date);
    retDatesSet.add(d.return_date);
    if (!priceMap[d.date]) priceMap[d.date] = {};
    priceMap[d.date][d.return_date] = d.price;
  });

  const depDates = Array.from(depDatesSet).sort();
  const retDates = Array.from(retDatesSet).sort();

  const tableWrapper = document.createElement('div');
  tableWrapper.style.overflowX = 'auto';
  tableWrapper.style.marginTop = '16px';

  let html = '<table class="heatmap-table"><thead><tr><th>Return →<br>Depart ↓</th>';
  retDates.forEach(rd => {
    html += `<th>${fmtShortDate(rd)}</th>`;
  });
  html += '</tr></thead><tbody>';

  depDates.forEach(dd => {
    html += `<tr><th>${fmtShortDate(dd)}</th>`;
    retDates.forEach(rd => {
      const price = priceMap[dd] ? priceMap[dd][rd] : null;
      if (price) {
        const ratio = (price - minP) / range;
        let bg = 'var(--bg-glass)';
        let color = 'var(--text)';
        if (ratio < 0.25) { bg = 'var(--success-bg)'; color = 'var(--success)'; }
        else if (ratio > 0.75) { bg = 'var(--danger-bg)'; color = 'var(--danger)'; }
        html += `<td style="background:${bg};color:${color};text-align:center;padding:12px;border:1px solid var(--border);border-radius:4px;">${formatPrice(price)}</td>`;
      } else {
        html += `<td style="background:var(--bg-glass);color:var(--text-muted);text-align:center;padding:12px;border:1px solid var(--border);border-radius:4px;">—</td>`;
      }
    });
    html += '</tr>';
  });
  html += '</tbody></table>';

  tableWrapper.innerHTML = html;
  container.appendChild(tableWrapper);
}

function fmtShortDate(str) {
  if (!str) return '';
  const [, m, d] = str.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(m,10)-1]} ${parseInt(d,10)}`;
}

// ── Sort ───────────────────────────────────────────────────────────────────

function sortHotelResults() {
  const mode = document.getElementById('hotels-sort').value;
  const grid = document.getElementById('hotels-results');
  const cards = [...grid.querySelectorAll('.hotel-card')];
  cards.sort((a, b) => {
    if (mode === 'price') return parseFloat(a.dataset.price) - parseFloat(b.dataset.price);
    if (mode === 'price-desc') return parseFloat(b.dataset.price) - parseFloat(a.dataset.price);
    if (mode === 'rating') return parseFloat(b.dataset.rating) - parseFloat(a.dataset.rating);
    if (mode === 'name') return (a.dataset.name || '').localeCompare(b.dataset.name || '');
    return 0;
  });
  cards.forEach(c => grid.appendChild(c));
}

// ── UI Helpers ─────────────────────────────────────────────────────────────
function setStatus(text, trip = '') {
  document.getElementById('statusText').textContent = text;
  document.getElementById('statusTrip').textContent = trip;
}

function setSearching(active, msg = '') {
  const dot = document.getElementById('statusDot');
  dot.className = 'status-dot' + (active ? ' searching' : '');
  if (msg) setStatus(msg);
}

function setBtn(id, disabled, label) {
  const btn = document.getElementById(id);
  if (!btn) return;
  btn.disabled = disabled;
  btn.textContent = label;
}

function updateResultsHeader(headerId, countId, n, noun) {
  document.getElementById(headerId).classList.remove('hidden');
  document.getElementById(countId).textContent = `${n} ${noun} found`;
}

function showEmpty(containerId, icon, msg) {
  document.getElementById(containerId).innerHTML =
    `<div class="empty-state"><div class="icon">${icon}</div><p>${msg}</p></div>`;
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Local Storage ──────────────────────────────────────────────────────────
function restoreFromStorage() {
  const saved = localStorage.getItem('tpp-prefs');
  if (!saved) return;
  try {
    const prefs = JSON.parse(saved);
    if (prefs.origins) {
      ['f-origins', 'c-origins'].forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.value) el.value = prefs.origins;
      });
    }
    if (prefs.currency) {
      state.currency = prefs.currency;
      const select = document.getElementById('currency-select');
      if (select) select.value = prefs.currency;
    }
  } catch (_) {}
}

function saveToStorage() {
  try {
    localStorage.setItem('tpp-prefs', JSON.stringify({
      origins: document.getElementById('f-origins')?.value || '',
      currency: state.currency
    }));
  } catch (_) {}
}

window.addEventListener('beforeunload', saveToStorage);

// ══════════════════════════════════════════════════════════════════════════════
// TRACKER — My Flights Price Drop Monitoring
// ══════════════════════════════════════════════════════════════════════════════

function initTrackerForm() {
  const form = document.getElementById('trackerAddForm');
  if (form) form.addEventListener('submit', handleTrackerAdd);
}

async function handleTrackerAdd(e) {
  e.preventDefault();
  const origin = document.getElementById('t-origin').value.trim().toUpperCase();
  const destination = document.getElementById('t-destination').value.trim().toUpperCase();
  const departDate = document.getElementById('t-depart').value;
  const returnDate = document.getElementById('t-return').value;
  const airline = document.getElementById('t-airline').value;
  const price = parseFloat(document.getElementById('t-price').value);
  const fareClass = document.getElementById('t-fare').value;
  const confirmation = document.getElementById('t-confirmation').value.trim();

  if (!origin || !destination || !departDate || !airline || isNaN(price)) {
    showToast('Please fill in all required fields', 'error');
    return;
  }

  setBtn('trackerAddBtn', true, 'Adding...');
  try {
    const r = await fetch('/api/tracker/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin, destination,
        departure_date: departDate,
        return_date: returnDate || null,
        airline, booked_price: price,
        fare_class: fareClass,
        cabin_class: 'ECONOMY',
        confirmation_code: confirmation,
      }),
    });
    const data = await r.json();
    if (data.success) {
      showToast('✅ Flight added to tracking!', 'success');
      document.getElementById('trackerAddForm').reset();
      loadTrackedFlights();
    } else {
      showToast(data.error || 'Failed to add flight', 'error');
    }
  } catch (err) {
    showToast('Error adding flight: ' + err.message, 'error');
  } finally {
    setBtn('trackerAddBtn', false, '📊 Start Tracking');
  }
}

async function loadTrackedFlights() {
  try {
    const r = await fetch('/api/tracker/list');
    const data = await r.json();
    if (data.success) {
      state.trackedFlights = data.flights || [];
      renderTrackerStats(data.stats || {});
      renderTrackedFlights(state.trackedFlights);
    }
  } catch (err) {
    console.error('Failed to load tracked flights:', err);
  }
}

function renderTrackerStats(stats) {
  document.getElementById('stat-active').textContent = stats.active_count || 0;
  document.getElementById('stat-savings').textContent = `$${Math.round(stats.total_savings || 0)}`;
  document.getElementById('stat-drops').textContent = stats.price_drops || 0;
}

function renderTrackedFlights(flights) {
  const grid = document.getElementById('tracker-results');
  grid.innerHTML = '';
  if (!flights.length) {
    showEmpty('tracker-results', '📊', 'No flights being tracked yet. Add a booked flight above to start monitoring for price drops.');
    return;
  }
  flights.forEach(f => grid.appendChild(buildTrackerCard(f)));
}

function buildTrackerCard(f) {
  const card = document.createElement('div');
  const hasSavings = (f.savings || 0) > 0;
  const departed = f.status === 'departed';
  card.className = `tracker-card${hasSavings ? ' has-savings' : ''}${departed ? ' departed' : ''}`;

  const delta = f.booked_price - (f.current_price || f.booked_price);
  let deltaHtml = '';
  if (delta > 0) deltaHtml = `<span class="tracker-delta positive">↓ $${Math.round(delta)} saved</span>`;
  else if (delta < 0) deltaHtml = `<span class="tracker-delta negative">↑ $${Math.round(Math.abs(delta))} more</span>`;
  else deltaHtml = `<span class="tracker-delta neutral">— No change</span>`;

  const confirmHtml = f.confirmation_code
    ? `<div class="tracker-confirmation">🎫 ${f.confirmation_code}</div>` : '';

  const lastChecked = f.last_checked
    ? `<div class="tracker-last-checked">Last checked: ${fmtRelative(f.last_checked)}</div>` : '';

  // Sparkline SVG
  const sparkline = f.price_history && f.price_history.length > 1
    ? buildSparklineSVG(f.price_history, f.booked_price) : '';

  // Refund badge
  let refundBadge = '';
  if (f.refund_badge) {
    refundBadge = `<span class="refund-badge badge-${f.refund_badge}">${f.refund_badge_label || ''}</span>`;
  }

  // Manage booking URL
  const claimBtn = hasSavings && f.manage_url
    ? `<a href="${f.manage_url}" target="_blank" class="btn-claim">💰 Claim Savings</a>` : '';

  card.innerHTML = `
    <div class="tracker-card-header">
      <div>
        <div class="tracker-route">${f.origin} → ${f.destination}</div>
        <div class="tracker-dates">${fmtShortDate(f.departure_date)}${f.return_date ? ' – ' + fmtShortDate(f.return_date) : ''}</div>
        <div class="tracker-airline">${f.airline} ${refundBadge}</div>
      </div>
      ${deltaHtml}
    </div>
    <div class="tracker-prices">
      <div class="tracker-price-item">
        <div class="tracker-price-label">You Paid</div>
        <div class="tracker-price-value booked">${formatPrice(f.booked_price)}</div>
      </div>
      <div class="tracker-price-item">
        <div class="tracker-price-label">Current</div>
        <div class="tracker-price-value current">${f.current_price ? formatPrice(f.current_price) : '—'}</div>
      </div>
      <div class="tracker-price-item">
        <div class="tracker-price-label">Savings</div>
        <div class="tracker-price-value ${hasSavings ? 'savings' : ''}">${hasSavings ? formatPrice(f.savings) : '—'}</div>
      </div>
    </div>
    ${sparkline}
    ${confirmHtml}
    ${lastChecked}
    <div class="tracker-card-actions">
      <button class="btn-check-now" onclick="checkOneFlight(${f.id})">🔄 Check Now</button>
      ${claimBtn}
      <button class="btn-remove" onclick="removeTrackedFlight(${f.id})">🗑 Remove</button>
    </div>`;
  return card;
}

// ── Sparkline SVG ──────────────────────────────────────────────────────────
function buildSparklineSVG(history, bookedPrice) {
  if (!history || history.length < 2) return '';
  const w = 300, h = 40, pad = 2;
  const prices = history.map(p => p.price);
  const allVals = [...prices, bookedPrice];
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;

  const xScale = (w - pad * 2) / (prices.length - 1);
  const yScale = (v) => h - pad - ((v - minV) / range) * (h - pad * 2);

  const points = prices.map((p, i) => `${pad + i * xScale},${yScale(p)}`);
  const linePath = `M${points.join('L')}`;
  const fillPath = `${linePath}L${pad + (prices.length - 1) * xScale},${h}L${pad},${h}Z`;
  const bookedY = yScale(bookedPrice);

  return `<svg class="tracker-sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <path class="spark-fill" d="${fillPath}"/>
    <path class="spark-line" d="${linePath}"/>
    <line class="spark-booked" x1="${pad}" y1="${bookedY}" x2="${w - pad}" y2="${bookedY}"/>
  </svg>`;
}

// ── Tracker Actions ───────────────────────────────────────────────────────
async function checkOneFlight(flightId) {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '⏳ Checking...';
  try {
    const r = await fetch(`/api/tracker/check/${flightId}`, { method: 'POST' });
    const data = await r.json();
    if (data.success) {
      showToast('✅ Price check complete', 'success');
      loadTrackedFlights();
    } else {
      showToast(data.error || 'Check failed', 'error');
    }
  } catch (err) {
    showToast('Check failed: ' + err.message, 'error');
  }
}

async function checkAllTracked() {
  const btn = document.getElementById('checkAllBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Checking all...';
  try {
    const r = await fetch('/api/tracker/check-all', { method: 'POST' });
    const data = await r.json();
    if (data.success) {
      showToast(`✅ Checked ${data.checked} flights. ${data.drops_found} drop(s), ${formatPrice(data.new_savings)} new savings`, 'success');
      loadTrackedFlights();
    } else {
      showToast('Batch check failed', 'error');
    }
  } catch (err) {
    showToast('Batch check failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🔄 Check All Now';
  }
}

async function removeTrackedFlight(flightId) {
  if (!confirm('Remove this flight from tracking?')) return;
  try {
    const r = await fetch(`/api/tracker/${flightId}`, { method: 'DELETE' });
    const data = await r.json();
    if (data.success) {
      showToast('Flight removed', 'info');
      loadTrackedFlights();
    } else {
      showToast(data.error || 'Remove failed', 'error');
    }
  } catch (err) {
    showToast('Remove failed: ' + err.message, 'error');
  }
}

// ── Track from Search Modal ───────────────────────────────────────────────
function openTrackModal(flightData) {
  state.pendingTrack = flightData;
  document.getElementById('modalRoute').textContent =
    `${flightData.origin} → ${flightData.destination} · ${flightData.depart_date || ''}${flightData.return_date ? ' – ' + flightData.return_date : ''} · ${flightData.airline}`;
  document.getElementById('modal-price').value = Math.round(flightData.price);
  document.getElementById('modal-origin').value = flightData.origin;
  document.getElementById('modal-destination').value = flightData.destination;
  document.getElementById('modal-depart').value = flightData.depart_date || '';
  document.getElementById('modal-return').value = flightData.return_date || '';
  document.getElementById('modal-airline').value = flightData.airline;
  document.getElementById('modal-cabin').value = flightData.cabin_class || 'ECONOMY';
  document.getElementById('trackModal').style.display = 'flex';
}

function closeTrackModal() {
  document.getElementById('trackModal').style.display = 'none';
  state.pendingTrack = null;
}

async function submitTrackModal() {
  const price = parseFloat(document.getElementById('modal-price').value);
  if (isNaN(price) || price <= 0) { showToast('Enter the price you paid', 'error'); return; }

  const body = {
    origin: document.getElementById('modal-origin').value,
    destination: document.getElementById('modal-destination').value,
    departure_date: document.getElementById('modal-depart').value,
    return_date: document.getElementById('modal-return').value || null,
    airline: document.getElementById('modal-airline').value,
    booked_price: price,
    fare_class: document.getElementById('modal-fare').value,
    cabin_class: document.getElementById('modal-cabin').value,
    confirmation_code: document.getElementById('modal-confirmation').value.trim(),
  };

  try {
    const r = await fetch('/api/tracker/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (data.success) {
      showToast('✅ Flight added to tracking!', 'success');
      closeTrackModal();
    } else {
      showToast(data.error || 'Failed', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// Close modal on backdrop click
document.addEventListener('click', e => {
  if (e.target.id === 'trackModal') closeTrackModal();
});

// ── Recent Searches ────────────────────────────────────────────────────────
function renderRecentSearches() {
  const container = document.getElementById('recent-searches-container');
  if (!container) return;
  const recentSearches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
  if (!recentSearches.length) {
    container.innerHTML = '';
    return;
  }
  let html = '<div class="recent-searches-title" style="font-size:0.8rem;color:var(--text-muted);margin-bottom:8px;">Recent Searches:</div><div class="recent-searches-chips" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">';
  recentSearches.forEach(s => {
    const label = `${s.origins} → ${s.destinations} (${s.startDate})`;
    html += `<button type="button" class="tag tag-typical" onclick="loadRecentSearch('${s.origins}', '${s.destinations}', '${s.startDate}', '${s.endDate}', '${s.cabin}')" style="cursor:pointer;border:none;background:var(--bg-glass);color:var(--text);">${label}</button>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

function loadRecentSearch(origins, destinations, startDate, endDate, cabin) {
  document.getElementById('f-origins').value = origins;
  document.getElementById('f-destinations').value = destinations;
  document.getElementById('f-start').value = startDate;
  if (document.getElementById('f-end')) document.getElementById('f-end').value = endDate;
  if (document.getElementById('f-cabin')) document.getElementById('f-cabin').value = cabin;
  document.getElementById('flightsForm').dispatchEvent(new Event('submit'));
}

document.addEventListener('DOMContentLoaded', renderRecentSearches);


function fmtRelative(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ── Trips Logic ────────────────────────────────────────────────────────────

let allTrips = [];
let pendingTripItem = null;

async function loadTrips() {
  try {
    const res = await fetch('/api/trips');
    const data = await res.json();
    if (data.success) {
      allTrips = data.trips;
      renderTrips();
    }
  } catch (err) {
    console.error('Failed to load trips:', err);
  }
}

function renderTrips() {
  const container = document.getElementById('trips-container');
  if (!allTrips.length) {
    container.innerHTML = '<div class="empty-state">No trips planned yet. Click + New Trip to start.</div>';
    return;
  }

  container.innerHTML = allTrips.map(trip => `
    <div class="card" style="padding: 20px;">
      <div class="flex-between" style="margin-bottom: 15px;">
        <h3 style="margin: 0;">${trip.name}</h3>
        <button class="btn-outline" style="color: #ef4444; border-color: #ef4444;" onclick="deleteTrip(${trip.id})">Delete</button>
      </div>
      ${trip.items.length ? `
        <div style="display: flex; flex-direction: column; gap: 10px;">
          ${trip.items.map(item => {
            const d = item.data;
            if (item.type === 'flight') {
              return `
                <div class="card flight-card" style="margin: 0; padding: 10px; background: rgba(255,255,255,0.03); cursor: grab;" 
                     draggable="true" data-trip-id="${trip.id}" data-item-id="${item.id}" 
                     ondragstart="handleDragStart(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)"
                     ondrop="handleDrop(event)" ondragend="handleDragEnd(event)">
                  <div class="flex-between">
                    <div>
                      <div class="card-detail-row" style="margin-bottom: 5px;">
                        <span>🛫 ${d.origin} → 🛬 ${d.destination}</span>
                        <span style="color: var(--accent); font-weight: 600;">${formatPrice(d.price)}</span>
                      </div>
                      <div class="card-detail-row" style="font-size: 0.85em; opacity: 0.8;">
                        <span>🗓 ${d.depart_date} ${d.return_date ? `— ${d.return_date}` : ''}</span>
                        <span>${d.airline}</span>
                      </div>
                    </div>
                    <button class="btn-outline" style="padding: 4px 8px; font-size: 0.8em;" onclick="deleteTripItem(${item.id})">Remove</button>
                  </div>
                </div>
              `;
            } else {
              return `
                <div class="card hotel-card" style="margin: 0; padding: 10px; background: rgba(255,255,255,0.03); cursor: grab;"
                     draggable="true" data-trip-id="${trip.id}" data-item-id="${item.id}" 
                     ondragstart="handleDragStart(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)"
                     ondrop="handleDrop(event)" ondragend="handleDragEnd(event)">
                  <div class="flex-between">
                    <div>
                      <div class="card-detail-row" style="margin-bottom: 5px;">
                        <span>🏨 ${d.name || d.hotel}</span>
                        <span style="color: var(--accent); font-weight: 600;">${formatPrice(d.price)}</span>
                      </div>
                      <div class="card-detail-row" style="font-size: 0.85em; opacity: 0.8;">
                        <span>⭐ ${d.rating}</span>
                      </div>
                    </div>
                    <button class="btn-outline" style="padding: 4px 8px; font-size: 0.8em;" onclick="deleteTripItem(${item.id})">Remove</button>
                  </div>
                </div>
              `;
            }
          }).join('')}
          <div style="text-align: right; margin-top: 10px; font-weight: bold; color: var(--accent);">
            Total: ${formatPrice(trip.items.reduce((sum, item) => sum + (parseFloat(item.data.price) || 0), 0))}
          </div>
        </div>
      ` : '<div style="opacity:0.6; font-size:0.9em;">No items added to this trip yet.</div>'}
    </div>
  `).join('');
}

// ── Drag and Drop Logic ──────────────────────────────────────────────────
let draggedElement = null;

function handleDragStart(e) {
  draggedElement = e.currentTarget;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', e.currentTarget.dataset.itemId);
  setTimeout(() => e.currentTarget.style.opacity = '0.5', 0);
}

function handleDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const target = e.currentTarget;
  if (target && target !== draggedElement && target.dataset.tripId === draggedElement.dataset.tripId) {
    target.style.borderTop = '2px solid var(--accent)';
  }
  return false;
}

function handleDragLeave(e) {
  e.currentTarget.style.borderTop = '';
}

async function handleDrop(e) {
  e.stopPropagation();
  const target = e.currentTarget;
  target.style.borderTop = '';
  
  if (draggedElement !== target && target.dataset.tripId === draggedElement.dataset.tripId) {
    const parent = target.parentNode;
    const allItems = [...parent.querySelectorAll('[data-item-id]')];
    const draggedIdx = allItems.indexOf(draggedElement);
    const targetIdx = allItems.indexOf(target);
    
    if (draggedIdx < targetIdx) {
      parent.insertBefore(draggedElement, target.nextSibling);
    } else {
      parent.insertBefore(draggedElement, target);
    }
    
    const newOrder = [...parent.querySelectorAll('[data-item-id]')].map((el, idx) => ({
      id: parseInt(el.dataset.itemId),
      order_index: idx
    }));
    
    try {
      await fetch(`/api/trips/${target.dataset.tripId}/items/order`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: newOrder })
      });
      allTrips.find(t => t.id == target.dataset.tripId).items.sort((a,b) => {
        const idxA = newOrder.find(o => o.id == a.id)?.order_index || 0;
        const idxB = newOrder.find(o => o.id == b.id)?.order_index || 0;
        return idxA - idxB;
      });
    } catch (err) {
      console.error('Failed to update order', err);
      loadTrips(); // Revert visual change on error
    }
  }
  return false;
}

function handleDragEnd(e) {
  e.currentTarget.style.opacity = '1';
  draggedElement = null;
  document.querySelectorAll('[data-item-id]').forEach(el => el.style.borderTop = '');
}


function openTripModal() {
  document.getElementById('tripModal').style.display = 'flex';
  document.getElementById('new-trip-name').focus();
}

function closeTripModal() {
  document.getElementById('tripModal').style.display = 'none';
  document.getElementById('new-trip-name').value = '';
}

async function createTrip() {
  const name = document.getElementById('new-trip-name').value.trim();
  if (!name) return;
  
  try {
    const res = await fetch('/api/trips', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name })
    });
    if (res.ok) {
      closeTripModal();
      loadTrips();
      showToast('Trip created!');
    }
  } catch (err) {
    showToast('Failed to create trip', 'error');
  }
}

async function deleteTrip(id) {
  if (!confirm('Delete this trip and all its items?')) return;
  try {
    const res = await fetch(`/api/trips/${id}`, { method: 'DELETE' });
    if (res.ok) {
      loadTrips();
      showToast('Trip deleted');
    }
  } catch (err) {
    showToast('Failed to delete trip', 'error');
  }
}

async function deleteTripItem(id) {
  if (!confirm('Remove this item from the trip?')) return;
  try {
    const res = await fetch(`/api/trips/items/${id}`, { method: 'DELETE' });
    if (res.ok) {
      loadTrips();
    }
  } catch (err) {
    showToast('Failed to remove item', 'error');
  }
}

async function openAddToTripModal(type, data) {
  pendingTripItem = { type, data };
  
  // Make sure trips are loaded
  if (!allTrips.length) {
    const res = await fetch('/api/trips');
    const json = await res.json();
    if (json.success) allTrips = json.trips;
  }
  
  const select = document.getElementById('add-trip-select');
  select.innerHTML = allTrips.length ? 
    allTrips.map(t => `<option value="${t.id}">${t.name}</option>`).join('') :
    '<option disabled>No trips available. Create one first.</option>';
    
  document.getElementById('addToTripModal').style.display = 'flex';
}

function closeAddToTripModal() {
  document.getElementById('addToTripModal').style.display = 'none';
  pendingTripItem = null;
}

async function saveToTrip() {
  if (!pendingTripItem) return;
  const select = document.getElementById('add-trip-select');
  const tripId = select.value;
  if (!tripId) {
    showToast('Please select a trip or create one first.', 'error');
    return;
  }
  
  try {
    const res = await fetch(`/api/trips/${tripId}/items`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        item_type: pendingTripItem.type,
        item_data: pendingTripItem.data
      })
    });
    if (res.ok) {
      closeAddToTripModal();
      loadTrips();
      showToast('Added to trip!');
    }
  } catch (err) {
    showToast('Failed to add to trip', 'error');
  }
}
