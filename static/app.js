/**
 * AuraFit Frontend Application Logic
 * Implements the interactive features defined in Nutrition Pseudocode.txt
 */

let appState = {
  onboarded: false,
  profile: null,
  dashboard: null,
  recipes: [],
  safeFoods: [],
  currentTab: 'dashboard',
  // Active workout state
  activeWorkout: null,
  workoutTimerInterval: null,
  weightUnit: 'lbs', // 'lbs' or 'kg'
};

document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) lucide.createIcons();
  registerServiceWorker();
  await loadProfile();
  await refreshDashboard();
  await loadSafeFoods();
  await loadCookbook();
});

function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(err => {
      console.log('SW registration note:', err);
    });
  }
}

// --- Navigation ---
function switchTab(tabName) {
  appState.currentTab = tabName;
  const tabs = ['dashboard', 'workouts', 'meals', 'recipes', 'profile'];
  tabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const navBtn = document.getElementById(`nav-${t}`);
    if (el) {
      if (t === tabName) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
    if (navBtn) {
      if (t === tabName) {
        navBtn.classList.remove('text-slate-400');
        navBtn.classList.add('text-brand-400');
      } else {
        navBtn.classList.remove('text-brand-400');
        navBtn.classList.add('text-slate-400');
      }
    }
  });

  if (tabName === 'dashboard') refreshDashboard();
  if (tabName === 'workouts') loadWorkoutsHistory();
  if (tabName === 'recipes') loadCookbook();
  if (tabName === 'profile') populateProfileTab();

  if (window.lucide) lucide.createIcons();
}

// --- API Calls & Data Refresh ---

async function loadProfile() {
  try {
    const res = await fetch('/api/profile');
    const data = await res.json();
    appState.onboarded = data.onboarded;
    appState.profile = data.profile;

    if (!data.onboarded) {
      document.getElementById('onboardingModal').classList.remove('hidden');
    } else {
      populateProfileTab();
      if (appState.profile.gemini_api_key) {
        document.getElementById('geminiApiKeyInput').value = appState.profile.gemini_api_key;
      }
    }
  } catch (err) {
    console.error('Failed to load profile', err);
  }
}

async function refreshDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();
    if (!data.onboarded) return;

    appState.dashboard = data;
    renderDashboard(data);
  } catch (err) {
    console.error('Failed to refresh dashboard', err);
  }
}

function renderDashboard(data) {
  const target = data.target;
  const consumed = data.consumed;
  const remaining = data.remaining;

  // Calorie gauge
  document.getElementById('dashTargetCal').textContent = Math.round(target.calories);
  document.getElementById('dashEatenCal').textContent = Math.round(consumed.calories);
  document.getElementById('dashRemainingCal').textContent = Math.round(remaining.calories);

  const calPct = Math.min(100, Math.max(0, (consumed.calories / (target.calories || 2000)) * 100));
  document.getElementById('calProgressBar').style.width = `${calPct}%`;

  // Macro preference display toggle (Section 1.1.8)
  const macroContainer = document.getElementById('macroContainer');
  if (data.display_preference === 'calories') {
    macroContainer.classList.add('hidden');
  } else {
    macroContainer.classList.remove('hidden');
    document.getElementById('dashProteinTarget').textContent = `${Math.round(target.protein_g)}g`;
    document.getElementById('dashProteinEaten').innerHTML = `${Math.round(consumed.protein_g)}<span class="text-xs font-normal text-slate-400">g</span>`;
    document.getElementById('dashProteinLeft').textContent = `${Math.max(0, Math.round(remaining.protein_g))}g left`;
    const pPct = Math.min(100, (consumed.protein_g / (target.protein_g || 1)) * 100);
    document.getElementById('proteinProgressBar').style.width = `${pPct}%`;

    document.getElementById('dashCarbsTarget').textContent = `${Math.round(target.carbs_g)}g`;
    document.getElementById('dashCarbsEaten').innerHTML = `${Math.round(consumed.carbs_g)}<span class="text-xs font-normal text-slate-400">g</span>`;
    document.getElementById('dashCarbsLeft').textContent = `${Math.max(0, Math.round(remaining.carbs_g))}g left`;
    const cPct = Math.min(100, (consumed.carbs_g / (target.carbs_g || 1)) * 100);
    document.getElementById('carbsProgressBar').style.width = `${cPct}%`;

    document.getElementById('dashFatTarget').textContent = `${Math.round(target.fat_g)}g`;
    document.getElementById('dashFatEaten').innerHTML = `${Math.round(consumed.fat_g)}<span class="text-xs font-normal text-slate-400">g</span>`;
    document.getElementById('dashFatLeft').textContent = `${Math.max(0, Math.round(remaining.fat_g))}g left`;
    const fPct = Math.min(100, (consumed.fat_g / (target.fat_g || 1)) * 100);
    document.getElementById('fatProgressBar').style.width = `${fPct}%`;

    if (appState.profile && appState.profile.macro_category) {
      document.getElementById('dashMacroCategory').textContent = appState.profile.macro_category;
    }
  }

  // Check for notifications (e.g. adaptive rebalance)
  const notifs = data.notifications || [];
  const notifBadge = document.getElementById('notifBadge');
  if (notifs.length > 0) {
    notifBadge.classList.remove('hidden');
    const firstNotif = notifs[0];
    document.getElementById('rebalanceAlertText').textContent = firstNotif.message;
    document.getElementById('rebalanceAlert').classList.remove('hidden');
  } else {
    notifBadge.classList.add('hidden');
    document.getElementById('rebalanceAlert').classList.add('hidden');
  }

  // Today's Meals
  const mealsList = document.getElementById('todayMealsList');
  const fullMealsList = document.getElementById('fullMealsLogList');
  if (data.meals && data.meals.length > 0) {
    const html = data.meals.map(m => `
      <div class="flex items-center justify-between p-3 bg-surface-850 rounded-xl border border-slate-800 text-xs">
        <div>
          <span class="font-bold text-white">${m.name}</span>
          <div class="text-[11px] text-slate-400 mt-0.5">
            ${m.calories} kcal &bull; P: ${m.protein_g}g | C: ${m.carbs_g}g | F: ${m.fat_g}g
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="copyMeal(${m.id})" title="Copy Meal" class="p-1 text-slate-400 hover:text-brand-400">
            <i data-lucide="copy" class="w-3.5 h-3.5"></i>
          </button>
          <button onclick="deleteMeal(${m.id})" title="Delete Meal" class="p-1 text-slate-400 hover:text-rose-400">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `).join('');
    mealsList.innerHTML = html;
    if (fullMealsList) fullMealsList.innerHTML = html;
    const totalCal = data.meals.reduce((sum, m) => sum + m.calories, 0);
    const tag = document.getElementById('mealsTotalCaloriesTag');
    if (tag) tag.textContent = `${Math.round(totalCal)} kcal total`;
  } else {
    mealsList.innerHTML = `<p class="text-xs text-slate-500 py-3 text-center">No meals logged yet today.</p>`;
    if (fullMealsList) fullMealsList.innerHTML = `<p class="text-xs text-slate-500 py-3 text-center">No meals logged yet today.</p>`;
  }

  // Today's Workouts
  const workoutsList = document.getElementById('todayWorkoutsList');
  if (data.workouts && data.workouts.length > 0) {
    workoutsList.innerHTML = data.workouts.map(w => `
      <div class="p-3 bg-surface-850 rounded-xl border border-slate-800 text-xs space-y-1">
        <div class="flex justify-between items-center">
          <span class="font-bold text-amber-400">${w.duration_minutes} min Session</span>
          <div class="flex items-center space-x-2">
            <span class="text-slate-400 font-semibold">${w.calories_burned} kcal burned</span>
            <button onclick="deleteWorkout(${w.id})" title="Delete Workout" class="p-1 text-slate-400 hover:text-rose-400">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
        <p class="text-[11px] text-slate-300 font-medium">${w.comparison_text || ''}</p>
      </div>
    `).join('');
  } else {
    workoutsList.innerHTML = `<p class="text-xs text-slate-500 py-3 text-center">No workouts recorded yet today.</p>`;
  }

  if (window.lucide) lucide.createIcons();
}

// --- Onboarding Flow ---

function toggleHrtFields() {
  const isHrt = document.getElementById('obHrtStatus').checked;
  const fields = document.getElementById('obHrtFields');
  if (isHrt) fields.classList.remove('hidden');
  else fields.classList.add('hidden');
}

function toggleObSafeFoods() {
  const isChecked = document.getElementById('obSafeTracker').checked;
  const area = document.getElementById('obSafeFoodsInputArea');
  if (isChecked) area.classList.remove('hidden');
  else area.classList.add('hidden');
}

async function handleOnboardingSubmit(e) {
  e.preventDefault();
  const height = parseFloat(document.getElementById('obHeight').value);
  const weight = parseFloat(document.getElementById('obWeight').value);
  const age = parseInt(document.getElementById('obAge').value);
  const sex = document.getElementById('obSex').value;
  const hrtStatus = document.getElementById('obHrtStatus').checked;
  const hrtType = document.getElementById('obHrtType').value;
  const hrtMonths = parseInt(document.getElementById('obHrtMonths').value) || 0;
  const bfVal = document.getElementById('obBodyFat').value;
  const bodyFat = bfVal ? parseFloat(bfVal) : null;
  const activity = document.getElementById('obActivity').value;
  const goal = document.getElementById('obGoal').value;
  const displayPref = document.getElementById('obDisplayPref').value;
  const safeTracker = document.getElementById('obSafeTracker').checked;

  let safeFoods = [];
  if (safeTracker) {
    const inputVal = document.getElementById('obSafeFoodsList').value;
    if (inputVal) {
      safeFoods = inputVal.split(',').map(s => ({ name: s.trim(), ranking: 'safe' })).filter(s => s.name);
    }
  }

  const payload = {
    height_cm: height,
    weight_kg: weight,
    age: age,
    sex: sex,
    hrt_status: hrtStatus,
    hrt_type: hrtType,
    hrt_months: hrtMonths,
    body_fat_pct: bodyFat,
    activity_level: activity,
    goal: goal,
    display_preference: displayPref,
    safe_food_tracker_enabled: safeTracker,
    safe_foods: safeFoods,
  };

  try {
    const res = await fetch('/api/profile/onboarding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (result.success) {
      appState.onboarded = true;
      appState.profile = result.profile;
      closeModal('onboardingModal');
      await refreshDashboard();
      await loadSafeFoods();
      populateProfileTab();
    }
  } catch (err) {
    alert('Error saving setup: ' + err);
  }
}

function restartOnboarding() {
  document.getElementById('onboardingModal').classList.remove('hidden');
}

// --- Active Workout Session ---

function startNewWorkout() {
  switchTab('workouts');
  appState.activeWorkout = {
    startTime: new Date(),
    exercises: [],
    musclesWorked: [],
  };

  document.getElementById('startWorkoutPrompt').classList.add('hidden');
  document.getElementById('activeWorkoutCard').classList.remove('hidden');

  if (appState.workoutTimerInterval) clearInterval(appState.workoutTimerInterval);
  appState.workoutTimerInterval = setInterval(updateWorkoutTimer, 1000);
  renderActiveExercises();
  if (window.lucide) lucide.createIcons();
}

function updateWorkoutTimer() {
  if (!appState.activeWorkout) return;
  const now = new Date();
  const diffSec = Math.floor((now - appState.activeWorkout.startTime) / 1000);
  const mins = String(Math.floor(diffSec / 60)).padStart(2, '0');
  const secs = String(diffSec % 60).padStart(2, '0');
  document.getElementById('workoutTimer').textContent = `Duration: ${mins}:${secs}`;
}

function openAddExerciseModal() {
  document.getElementById('addExerciseModal').classList.remove('hidden');
  filterExercisesByMuscle('');
}

async function filterExercisesByMuscle(muscle) {
  try {
    const url = muscle ? `/api/exercises?muscle=${encodeURIComponent(muscle)}` : '/api/exercises';
    const res = await fetch(url);
    const data = await res.json();
    const list = document.getElementById('exerciseLibraryList');
    list.innerHTML = data.exercises.map(ex => `
      <div class="flex items-center justify-between p-2.5 bg-surface-850 hover:bg-slate-700/60 rounded-xl border border-slate-800 cursor-pointer" onclick="addExerciseToActiveWorkout('${ex.name}', '${ex.category}', '${ex.target_muscles.join(', ')}')">
        <div>
          <span class="font-bold text-white">${ex.name}</span>
          <span class="text-[10px] text-slate-400 block">${ex.target_muscles.join(', ')} &bull; ${ex.equipment_type || ''}</span>
        </div>
        <span class="text-xs font-bold text-brand-400">+ Add</span>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error fetching exercises', err);
  }
}

function addCustomExerciseToActiveWorkout() {
  const name = document.getElementById('customExerciseInput').value.trim();
  if (!name) return;
  addExerciseToActiveWorkout(name, 'strength', 'Custom');
  document.getElementById('customExerciseInput').value = '';
}

async function addExerciseToActiveWorkout(name, category, muscles) {
  closeModal('addExerciseModal');
  if (!appState.activeWorkout) startNewWorkout();

  // Look up previous performance for this exercise (sets & reps from last workout)
  let initialSets = [
    { set_number: 1, weight_lbs: category === 'cardio' ? 0 : 45, reps: 10, distance_miles: 0, duration_minutes: 0 }
  ];
  let previousSummary = null;

  try {
    const res = await fetch(`/api/exercises/previous-performance?name=${encodeURIComponent(name)}`);
    const perf = await res.json();
    if (perf.found && perf.sets && perf.sets.length > 0) {
      initialSets = perf.sets.map((s, idx) => ({
        set_number: idx + 1,
        weight_lbs: s.weight_lbs !== undefined ? s.weight_lbs : 45,
        reps: s.reps !== undefined ? s.reps : 10,
        distance_miles: s.distance_miles || 0,
        duration_minutes: s.duration_minutes || 0,
      }));
      const summaryList = initialSets.map(s => `${s.weight_lbs} lbs × ${s.reps}`).join(', ');
      previousSummary = `Previous session (${perf.last_date}): ${summaryList}`;
    }
  } catch (err) {
    console.log('No previous performance found', err);
  }

  appState.activeWorkout.exercises.push({
    exercise_name: name,
    category: category || 'strength',
    sets: initialSets,
    previousSummary: previousSummary,
  });

  if (muscles) {
    muscles.split(',').forEach(m => {
      const clean = m.trim();
      if (clean && !appState.activeWorkout.musclesWorked.includes(clean)) {
        appState.activeWorkout.musclesWorked.push(clean);
      }
    });
  }

  renderActiveExercises();
}

function renderActiveExercises() {
  const container = document.getElementById('activeExercisesList');
  if (!appState.activeWorkout || appState.activeWorkout.exercises.length === 0) {
    container.innerHTML = `<p class="text-xs text-slate-500 text-center py-4">No exercises added yet. Tap "+ Add Exercise" or snap a photo of a gym machine!</p>`;
    return;
  }

  container.innerHTML = appState.activeWorkout.exercises.map((ex, exIdx) => `
    <div class="bg-surface-850 rounded-xl p-3 border border-slate-800 space-y-2">
      <div class="flex items-center justify-between border-b border-slate-800 pb-1.5">
        <div>
          <h4 class="font-bold text-xs text-brand-400">${ex.exercise_name}</h4>
          ${ex.previousSummary ? `
            <p class="text-[10px] text-amber-400/90 font-medium mt-0.5 flex items-center gap-1">
              <i data-lucide="history" class="w-3 h-3"></i> ${ex.previousSummary}
            </p>
          ` : ''}
        </div>
        <button onclick="removeExercise(${exIdx})" class="text-[11px] text-rose-400 hover:underline">Remove</button>
      </div>

      <!-- Sets Table -->
      <div class="space-y-1.5">
        ${ex.sets.map((s, sIdx) => `
          <div class="grid grid-cols-12 gap-1 items-center text-xs">
            <span class="col-span-2 text-slate-400 text-center font-bold">#${s.set_number}</span>
            <div class="col-span-4 flex items-center bg-surface-900 rounded-lg px-2 py-1 border border-slate-700">
              <input type="number" step="0.5" value="${s.weight_lbs}" onchange="updateSetVal(${exIdx}, ${sIdx}, 'weight_lbs', this.value)" class="w-full bg-transparent text-white text-center font-semibold" />
              <span class="text-[10px] text-slate-400 ml-1">${appState.weightUnit}</span>
            </div>
            <div class="col-span-4 flex items-center bg-surface-900 rounded-lg px-2 py-1 border border-slate-700">
              <input type="number" value="${s.reps}" onchange="updateSetVal(${exIdx}, ${sIdx}, 'reps', this.value)" class="w-full bg-transparent text-white text-center font-semibold" />
              <span class="text-[10px] text-slate-400 ml-1">reps</span>
            </div>
            <button onclick="removeSet(${exIdx}, ${sIdx})" class="col-span-2 text-slate-500 hover:text-rose-400 text-center">
              &times;
            </button>
          </div>
        `).join('')}
      </div>

      <button onclick="addSet(${exIdx})" class="w-full py-1 bg-surface-900 hover:bg-slate-800 text-[11px] font-semibold text-slate-300 rounded-lg border border-slate-800">
        + Add Another Set
      </button>
    </div>
  `).join('');

  if (window.lucide) lucide.createIcons();
}

function addSet(exIdx) {
  const ex = appState.activeWorkout.exercises[exIdx];
  const lastSet = ex.sets[ex.sets.length - 1];
  const nextNum = ex.sets.length + 1;
  ex.sets.push({
    set_number: nextNum,
    weight_lbs: lastSet ? lastSet.weight_lbs : 45,
    reps: lastSet ? lastSet.reps : 10,
    distance_miles: 0,
    duration_minutes: 0,
  });
  renderActiveExercises();
}

function removeSet(exIdx, sIdx) {
  const ex = appState.activeWorkout.exercises[exIdx];
  ex.sets.splice(sIdx, 1);
  ex.sets.forEach((s, idx) => s.set_number = idx + 1);
  renderActiveExercises();
}

function removeExercise(exIdx) {
  appState.activeWorkout.exercises.splice(exIdx, 1);
  renderActiveExercises();
}

function updateSetVal(exIdx, sIdx, field, val) {
  appState.activeWorkout.exercises[exIdx].sets[sIdx][field] = parseFloat(val) || 0;
}

async function finishActiveWorkout() {
  if (!appState.activeWorkout || appState.activeWorkout.exercises.length === 0) {
    alert('Please add at least one exercise before ending workout.');
    return;
  }

  const durationMin = Math.max(1, Math.round((new Date() - appState.activeWorkout.startTime) / 60000));
  clearInterval(appState.workoutTimerInterval);

  const payload = {
    duration_minutes: durationMin,
    exercises: appState.activeWorkout.exercises,
    muscles_worked: appState.activeWorkout.musclesWorked,
  };

  try {
    const res = await fetch('/api/workouts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (result.success) {
      document.getElementById('activeWorkoutCard').classList.add('hidden');
      document.getElementById('startWorkoutPrompt').classList.remove('hidden');
      appState.activeWorkout = null;

      // Display fun Volume Comparison Table result (Section 3.5.2)
      document.getElementById('wfComparisonText').textContent = result.comparison_text;
      document.getElementById('wfCaloriesText').textContent = `Burned approx ${result.calories_burned} kcal across ${durationMin} minutes.`;
      document.getElementById('workoutFinishedModal').classList.remove('hidden');
      await refreshDashboard();
      await loadWorkoutsHistory();
    }
  } catch (err) {
    alert('Error saving workout: ' + err);
  }
}

async function loadWorkoutsHistory() {
  try {
    const res = await fetch('/api/workouts');
    const data = await res.json();
    const list = document.getElementById('pastWorkoutsList');
    if (data.workouts && data.workouts.length > 0) {
      list.innerHTML = data.workouts.map(w => `
        <div class="bg-surface-850 p-3.5 rounded-xl border border-slate-800 text-xs space-y-1.5">
          <div class="flex justify-between items-center">
            <span class="font-bold text-amber-400">${w.date_str} &bull; ${w.duration_minutes} min</span>
            <div class="flex items-center space-x-2">
              <span class="text-brand-400 font-semibold">${w.calories_burned} kcal</span>
              <button onclick="deleteWorkout(${w.id})" title="Delete Workout" class="p-1 text-slate-400 hover:text-rose-400">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              </button>
            </div>
          </div>
          <p class="text-slate-200 font-medium">${w.comparison_text || `Total weight lifted: ${w.total_weight_lifted_lbs} lbs`}</p>
        </div>
      `).join('');
    } else {
      list.innerHTML = `<p class="text-xs text-slate-500 py-3 text-center">No workout history logged yet.</p>`;
    }
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error('Error loading workout history', err);
  }
}

async function deleteWorkout(workoutId) {
  if (!confirm('Are you sure you want to delete this workout?')) return;
  try {
    const res = await fetch(`/api/workouts/${workoutId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      await refreshDashboard();
      await loadWorkoutsHistory();
    }
  } catch (err) {
    alert('Failed to delete workout: ' + err);
  }
}

// --- Gemini Machine Identifier ---

function openMachineIdentifierModal() {
  document.getElementById('machineIdentifierModal').classList.remove('hidden');
  document.getElementById('machineIdentifyResult').classList.add('hidden');
}

async function executeIdentifyMachine() {
  const fileInput = document.getElementById('machineImageFileInput');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Please choose or snap a photo of the gym machine.');
    return;
  }

  const btn = document.getElementById('identifyMachineBtn');
  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin inline-block mr-1">&#9696;</span> Gemini Vision analyzing machine...`;

  const formData = new FormData();
  formData.append('image', fileInput.files[0]);

  try {
    const res = await fetch('/api/vision/identify-machine', {
      method: 'POST',
      body: formData,
    });
    const result = await res.json();
    if (result.success && result.data) {
      const data = result.data;
      const resBox = document.getElementById('machineIdentifyResult');
      resBox.classList.remove('hidden');
      resBox.innerHTML = `
        <h4 class="font-bold text-brand-400 text-sm">${data.machine_name || 'Machine Detected'}</h4>
        <p class="text-[11px] text-slate-300"><strong>Exercise:</strong> ${data.exercise_name || data.machine_name}</p>
        <p class="text-[11px] text-slate-300"><strong>Primary Muscles:</strong> ${(data.primary_muscles || []).join(', ')}</p>
        <p class="text-[11px] text-slate-400"><strong>Form Tip:</strong> ${data.instructions || ''}</p>
        <button onclick="addIdentifiedMachineToWorkout('${data.exercise_name || data.machine_name}', '${(data.primary_muscles || []).join(', ')}')" class="mt-2 w-full py-1.5 bg-brand-500 hover:bg-brand-600 text-black font-bold text-xs rounded-lg">
          Add This Exercise to Workout
        </button>
      `;
    } else {
      alert('Recognition issue: ' + (result.error || 'Could not recognize equipment'));
    }
  } catch (err) {
    alert('Gemini API call failed: ' + err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="sparkles" class="w-4 h-4"></i> Identify Machine & Target Muscles`;
    if (window.lucide) lucide.createIcons();
  }
}

function addIdentifiedMachineToWorkout(name, muscles) {
  closeModal('machineIdentifierModal');
  addExerciseToActiveWorkout(name, 'strength', muscles);
}

// --- Gemini Nutrition Label Scanner ---

function openLabelScannerModal() {
  document.getElementById('labelScannerModal').classList.remove('hidden');
  document.getElementById('labelScanStatus').classList.add('hidden');
}

async function executeScanNutritionLabel() {
  const fileInput = document.getElementById('labelImageFileInput');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Please select or capture a photo of the nutrition label.');
    return;
  }

  const btn = document.getElementById('scanLabelBtn');
  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin inline-block mr-1">&#9696;</span> Extracting facts from label...`;

  const formData = new FormData();
  formData.append('image', fileInput.files[0]);

  try {
    const res = await fetch('/api/vision/scan-label', {
      method: 'POST',
      body: formData,
    });
    const result = await res.json();
    if (result.success && result.data) {
      const data = result.data;
      closeModal('labelScannerModal');
      openLogMealModal();
      document.getElementById('mealNameInput').value = data.product_name || 'Scanned Food Item';
      document.getElementById('mealCalInput').value = data.calories || 0;
      document.getElementById('mealProteinInput').value = data.protein_g || 0;
      document.getElementById('mealCarbsInput').value = data.carbs_g || 0;
      document.getElementById('mealFatInput').value = data.fat_g || 0;
    } else {
      alert('Label extraction issue: ' + (result.error || 'Could not extract nutrition facts'));
    }
  } catch (err) {
    alert('Gemini API label scan failed: ' + err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="sparkles" class="w-4 h-4"></i> Analyze Label Photo`;
    if (window.lucide) lucide.createIcons();
  }
}

// --- Meal Logging & Food Database Search ---

function openLogMealModal() {
  document.getElementById('logMealModal').classList.remove('hidden');
}

async function handleFoodSearch() {
  const q = document.getElementById('foodSearchInput').value.trim();
  if (!q) return;

  const resultsDiv = document.getElementById('foodSearchResults');
  resultsDiv.innerHTML = `<p class="text-xs text-slate-400 py-1">Searching food databases...</p>`;

  try {
    const res = await fetch(`/api/foods/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (data.results && data.results.length > 0) {
      resultsDiv.innerHTML = data.results.map(item => `
        <div class="flex justify-between items-center p-2 bg-surface-850 hover:bg-slate-700/60 rounded-lg border border-slate-800 cursor-pointer text-xs" onclick='selectFoodItem(${JSON.stringify(item)})'>
          <div>
            <span class="font-bold text-white">${item.name}</span>
            <span class="text-[10px] text-slate-400 block">${item.calories_per_100g} kcal/100g (P: ${item.protein_g || item.protein_per_100g}g)</span>
          </div>
          <span class="text-[11px] text-brand-400 font-bold">Select</span>
        </div>
      `).join('');
    } else {
      resultsDiv.innerHTML = `<p class="text-xs text-slate-500 py-1">No matching food found. You can enter manually below.</p>`;
    }
  } catch (err) {
    resultsDiv.innerHTML = `<p class="text-xs text-rose-400 py-1">Search failed.</p>`;
  }
}

function selectFoodItem(item) {
  document.getElementById('mealNameInput').value = item.name;
  document.getElementById('mealCalInput').value = item.calories_per_100g;
  document.getElementById('mealProteinInput').value = item.protein_per_100g;
  document.getElementById('mealCarbsInput').value = item.carbs_per_100g;
  document.getElementById('mealFatInput').value = item.fat_per_100g;
  document.getElementById('foodSearchResults').innerHTML = '';
}

async function handleLogMealSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('mealNameInput').value;
  const cal = parseFloat(document.getElementById('mealCalInput').value);
  const p = parseFloat(document.getElementById('mealProteinInput').value);
  const c = parseFloat(document.getElementById('mealCarbsInput').value);
  const f = parseFloat(document.getElementById('mealFatInput').value);

  try {
    const res = await fetch('/api/meals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        calories: cal,
        protein_g: p,
        carbs_g: c,
        fat_g: f,
      }),
    });
    const result = await res.json();
    if (result.success) {
      closeModal('logMealModal');
      document.getElementById('logMealForm').reset();
      await refreshDashboard();
    }
  } catch (err) {
    alert('Error logging meal: ' + err);
  }
}

async function copyMeal(mealId) {
  try {
    const res = await fetch('/api/meals/copy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meal_id: mealId }),
    });
    const data = await res.json();
    if (data.success) {
      await refreshDashboard();
    }
  } catch (err) {
    alert('Failed to copy meal');
  }
}

async function deleteMeal(mealId) {
  if (!confirm('Remove this logged meal?')) return;
  try {
    await fetch(`/api/meals/${mealId}`, { method: 'DELETE' });
    await refreshDashboard();
  } catch (err) {
    alert('Failed to delete meal');
  }
}

// --- Recipe Creation & Scaling (Section 4.1) ---

let currentRecipeIngredients = [];

function openCreateRecipeModal() {
  document.getElementById('createRecipeModal').classList.remove('hidden');
  currentRecipeIngredients = [];
  addRecipeIngredientRow();
}

function addRecipeIngredientRow() {
  currentRecipeIngredients.push({ name: '', weight_g: 100, calories: 150, protein_g: 20, carbs_g: 5, fat_g: 2 });
  renderRecipeIngredientRows();
}

function removeRecipeIngredientRow(idx) {
  currentRecipeIngredients.splice(idx, 1);
  renderRecipeIngredientRows();
}

function renderRecipeIngredientRows() {
  const container = document.getElementById('recipeIngredientsRows');
  container.innerHTML = currentRecipeIngredients.map((ing, idx) => `
    <div class="bg-surface-850 p-2.5 rounded-xl border border-slate-800 space-y-1.5 text-xs">
      <div class="flex space-x-1.5 items-center">
        <input type="text" placeholder="Ingredient name (e.g. Chicken breast)" value="${ing.name}" onchange="updateRecipeIng(${idx}, 'name', this.value)" class="flex-1 bg-surface-900 border border-slate-700 rounded p-1 text-white" />
        <button type="button" onclick="removeRecipeIngredientRow(${idx})" class="text-rose-400 p-1 text-xs">&times;</button>
      </div>
      <div class="grid grid-cols-4 gap-1">
        <div>
          <label class="text-[10px] text-slate-400 block">Weight (g)</label>
          <input type="number" value="${ing.weight_g}" oninput="updateRecipeIng(${idx}, 'weight_g', this.value)" class="w-full bg-surface-900 border border-slate-700 rounded p-1 text-white text-center" />
        </div>
        <div>
          <label class="text-[10px] text-slate-400 block">Calories</label>
          <input type="number" value="${ing.calories}" oninput="updateRecipeIng(${idx}, 'calories', this.value)" class="w-full bg-surface-900 border border-slate-700 rounded p-1 text-white text-center" />
        </div>
        <div>
          <label class="text-[10px] text-slate-400 block">Protein (g)</label>
          <input type="number" value="${ing.protein_g}" oninput="updateRecipeIng(${idx}, 'protein_g', this.value)" class="w-full bg-surface-900 border border-slate-700 rounded p-1 text-white text-center" />
        </div>
        <div>
          <label class="text-[10px] text-slate-400 block">Carbs (g)</label>
          <input type="number" value="${ing.carbs_g}" oninput="updateRecipeIng(${idx}, 'carbs_g', this.value)" class="w-full bg-surface-900 border border-slate-700 rounded p-1 text-white text-center" />
        </div>
      </div>
    </div>
  `).join('');

  // Total Batch Weight calculation (Pseudocode Section 4.1.4.1)
  const totalBatchWeight = currentRecipeIngredients.reduce((sum, i) => sum + (parseFloat(i.weight_g) || 0), 0);
  const totalBatchCal = currentRecipeIngredients.reduce((sum, i) => sum + (parseFloat(i.calories) || 0), 0);
  document.getElementById('recipeBatchWeightDisplay').textContent = `${Math.round(totalBatchWeight)} g`;
  document.getElementById('recipeBatchCalDisplay').textContent = `${Math.round(totalBatchCal)} kcal`;
}

function updateRecipeIng(idx, field, val) {
  currentRecipeIngredients[idx][field] = field === 'name' ? val : (parseFloat(val) || 0);
  if (field === 'weight_g' || field === 'calories') {
    const totalBatchWeight = currentRecipeIngredients.reduce((sum, i) => sum + (parseFloat(i.weight_g) || 0), 0);
    const totalBatchCal = currentRecipeIngredients.reduce((sum, i) => sum + (parseFloat(i.calories) || 0), 0);
    document.getElementById('recipeBatchWeightDisplay').textContent = `${Math.round(totalBatchWeight)} g`;
    document.getElementById('recipeBatchCalDisplay').textContent = `${Math.round(totalBatchCal)} kcal`;
  }
}

async function handleCreateRecipeSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('recipeNameInput').value;
  const category = document.getElementById('recipeCategoryInput').value;
  const addToSafe = document.getElementById('recipeAddToSafeFoods').checked;

  const validIngredients = currentRecipeIngredients.filter(i => i.name.trim());
  if (validIngredients.length === 0) {
    alert('Please add at least one ingredient.');
    return;
  }

  const payload = {
    name: name,
    meal_type: category,
    ingredients: validIngredients,
    add_to_safe_foods: addToSafe,
    safe_ranking: 'safe',
  };

  try {
    const res = await fetch('/api/recipes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (result.success) {
      closeModal('createRecipeModal');
      await loadCookbook();
      await loadSafeFoods();
    }
  } catch (err) {
    alert('Error saving recipe: ' + err);
  }
}

async function loadCookbook() {
  try {
    const res = await fetch('/api/recipes');
    const data = await res.json();
    appState.recipes = data.recipes || [];
    const list = document.getElementById('cookbookList');
    if (appState.recipes.length > 0) {
      list.innerHTML = appState.recipes.map(r => `
        <div class="bg-surface-850 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
          <div class="flex justify-between items-start">
            <div>
              <h4 class="font-bold text-white text-sm">${r.name}</h4>
              <span class="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded uppercase font-semibold">${r.meal_type}</span>
            </div>
            <button onclick="deleteRecipe(${r.id})" title="Delete Recipe" class="p-1 text-slate-400 hover:text-rose-400">
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
          <div class="text-slate-300 text-[11px] space-y-0.5">
            <p><strong>Batch:</strong> ${r.batch_weight_g}g &bull; ${r.total_calories} kcal</p>
            <p>P: ${r.total_protein_g}g | C: ${r.total_carbs_g}g | F: ${r.total_fat_g}g</p>
          </div>
          <button onclick="openPortionRecipeModal(${r.id})" class="w-full py-1.5 bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 font-bold rounded-lg border border-brand-500/30">
            Log Portion Eaten
          </button>
        </div>
      `).join('');
    } else {
      list.innerHTML = `<p class="col-span-2 text-xs text-slate-500 py-6 text-center">No recipes in cookbook. Tap "+ Add Recipe" to batch-scale your first meal.</p>`;
    }
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error('Error loading cookbook', err);
  }
}

async function deleteRecipe(recipeId) {
  if (!confirm('Are you sure you want to delete this recipe?')) return;
  try {
    const res = await fetch(`/api/recipes/${recipeId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      await loadCookbook();
    }
  } catch (err) {
    alert('Failed to delete recipe: ' + err);
  }
}

// --- Recipe Portioned Meal Logging (Section 4.1.4) ---

function openPortionRecipeModal(preselectedId) {
  document.getElementById('portionRecipeModal').classList.remove('hidden');
  const sel = document.getElementById('portionRecipeSelect');
  sel.innerHTML = appState.recipes.map(r => `
    <option value="${r.id}" ${preselectedId === r.id ? 'selected' : ''}>${r.name} (Batch: ${r.batch_weight_g}g)</option>
  `).join('');
  updatePortionPreview();
}

function updatePortionPreview() {
  const sel = document.getElementById('portionRecipeSelect');
  const recipeId = parseInt(sel.value);
  const portionGrams = parseFloat(document.getElementById('portionWeightGrams').value) || 0;
  const recipe = appState.recipes.find(r => r.id === recipeId);
  const preview = document.getElementById('portionCalculationPreview');

  if (!recipe || portionGrams <= 0) {
    preview.innerHTML = `<p class="text-slate-400">Enter portion weight to calculate scaled macros.</p>`;
    return;
  }

  const fraction = portionGrams / (recipe.batch_weight_g || portionGrams);
  const cal = Math.round(recipe.total_calories * fraction);
  const p = Math.round(recipe.total_protein_g * fraction * 10) / 10;
  const c = Math.round(recipe.total_carbs_g * fraction * 10) / 10;
  const f = Math.round(recipe.total_fat_g * fraction * 10) / 10;

  preview.innerHTML = `
    <div class="flex justify-between font-bold text-white">
      <span>Fraction of Batch: ${(fraction * 100).toFixed(1)}%</span>
      <span class="text-brand-400">${cal} kcal</span>
    </div>
    <p class="text-[11px] text-slate-300">P: ${p}g | C: ${c}g | F: ${f}g</p>
  `;
}

async function executeLogRecipePortion() {
  const sel = document.getElementById('portionRecipeSelect');
  const recipeId = parseInt(sel.value);
  const portionGrams = parseFloat(document.getElementById('portionWeightGrams').value);
  if (!portionGrams || portionGrams <= 0) {
    alert('Please enter a portion weight in grams.');
    return;
  }

  try {
    const res = await fetch('/api/meals/log-recipe-portion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipe_id: recipeId,
        portion_weight_g: portionGrams,
      }),
    });
    const result = await res.json();
    if (result.success) {
      closeModal('portionRecipeModal');
      await refreshDashboard();
      switchTab('dashboard');
    }
  } catch (err) {
    alert('Failed to log portion: ' + err);
  }
}

// --- Smart Recipe Recommendation (Section 4.2) ---

function openRecommendRecipeModal() {
  document.getElementById('recommendRecipeModal').classList.remove('hidden');
}

async function executeRecipeRecommendation() {
  const mealType = document.getElementById('recMealType').value;
  const prioritize = document.getElementById('recPrioritize').value;
  const filterMode = document.getElementById('recFilterMode').value;
  const familiar = document.getElementById('recFamiliarOnly').checked;

  const payload = {
    meal_type: mealType,
    prioritize: prioritize,
    filter_mode: filterMode,
    prefer_familiar: familiar,
    use_safe_foods: true,
  };

  try {
    const res = await fetch('/api/recipes/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    const resultsDiv = document.getElementById('recipeRecommendationResults');

    if (data.recipes && data.recipes.length > 0) {
      resultsDiv.innerHTML = data.recipes.map((r, i) => `
        <div class="bg-surface-850 p-3 rounded-xl border border-slate-800 space-y-1 text-xs">
          <div class="flex justify-between items-center">
            <span class="font-bold text-white">${i + 1}. ${r.name}</span>
            <span class="text-brand-400 font-bold">${Math.round(r.calories)} kcal</span>
          </div>
          <p class="text-[11px] text-slate-300">P: ${r.protein_g}g | C: ${r.carbs_g}g | F: ${r.fat_g}g</p>
          <div class="flex justify-between items-center pt-1">
            <span class="text-[10px] ${r.all_safe ? 'text-emerald-400 font-semibold' : 'text-slate-400'}">
              ${r.all_safe ? '✓ Safe Foods Match' : 'Neutral Ingredients'}
            </span>
            <button onclick="closeModal('recommendRecipeModal'); openPortionRecipeModal(${r.id});" class="text-[11px] text-sky-400 font-bold hover:underline">
              Log Portion &rarr;
            </button>
          </div>
        </div>
      `).join('');
    } else {
      resultsDiv.innerHTML = `<p class="text-xs text-slate-500 py-3 text-center">No matching recipes found under criteria.</p>`;
    }
  } catch (err) {
    alert('Recommendation query failed: ' + err);
  }
}

// --- Safe Food Tracker List (Section 1.1.7) ---

async function loadSafeFoods() {
  try {
    const res = await fetch('/api/safe-foods');
    const data = await res.json();
    appState.safeFoods = data.safe_foods || [];
    const container = document.getElementById('safeFoodBadges');

    if (appState.safeFoods.length > 0) {
      container.innerHTML = appState.safeFoods.map(f => {
        let badgeColor = 'bg-brand-500/20 text-brand-300 border-brand-500/30';
        if (f.ranking === 'mostly_safe') badgeColor = 'bg-slate-800 text-slate-300 border-slate-700';
        if (f.ranking === 'always_safe') badgeColor = 'bg-emerald-500/30 text-emerald-200 border-emerald-500/50';

        return `
          <span class="inline-flex items-center text-[11px] px-2.5 py-1 rounded-lg border ${badgeColor} space-x-1.5">
            <span>${f.name}</span>
            <button onclick="removeSafeFood(${f.id})" class="hover:text-rose-400 ml-1">&times;</button>
          </span>
        `;
      }).join('');
    } else {
      container.innerHTML = `<p class="text-xs text-slate-500">No safe foods added yet.</p>`;
    }
  } catch (err) {
    console.error('Error loading safe foods', err);
  }
}

function openAddSafeFoodModal() {
  document.getElementById('addSafeFoodModal').classList.remove('hidden');
}

async function executeAddSafeFood() {
  const name = document.getElementById('safeFoodNameInput').value.trim();
  const rank = document.getElementById('safeFoodRankInput').value;
  if (!name) return;

  try {
    await fetch('/api/safe-foods', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, ranking: rank }),
    });
    closeModal('addSafeFoodModal');
    document.getElementById('safeFoodNameInput').value = '';
    await loadSafeFoods();
  } catch (err) {
    alert('Failed to save safe food');
  }
}

async function removeSafeFood(id) {
  try {
    await fetch(`/api/safe-foods/${id}`, { method: 'DELETE' });
    await loadSafeFoods();
  } catch (err) {
    alert('Failed to remove safe food');
  }
}

// --- Profile / Settings Tab & Gemini API Key ---

function populateProfileTab() {
  const p = appState.profile;
  if (!p) return;

  document.getElementById('profHeightWeight').textContent = `${p.height_cm} cm / ${p.weight_kg} kg`;
  let hrtText = '';
  if (p.hrt_status) {
    hrtText = ` (HRT: ${p.hrt_type}, ${p.hrt_months}m)`;
  }
  document.getElementById('profAgeSex').textContent = `${p.age}y / ${p.sex}${hrtText}`;
  document.getElementById('profBodyFat').textContent = p.body_fat_pct ? `${p.body_fat_pct}%` : 'Not specified';
  document.getElementById('profBMR').textContent = `${p.bmr} kcal`;
  document.getElementById('profTDEE').textContent = `${p.baseline_tdee} kcal (${p.activity_level})`;
  document.getElementById('profGoalTarget').textContent = `${p.daily_target_calories} kcal (${p.goal})`;
}

async function saveApiKey() {
  const key = document.getElementById('geminiApiKeyInput').value.trim();
  try {
    const res = await fetch('/api/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gemini_api_key: key }),
    });
    const data = await res.json();
    if (data.success) {
      alert('Google Gemini API Key saved successfully!');
    }
  } catch (err) {
    alert('Failed to save API key');
  }
}

function dismissNotificationAlert() {
  document.getElementById('rebalanceAlert').classList.add('hidden');
}

function openNotificationsModal() {
  if (appState.dashboard && appState.dashboard.notifications.length > 0) {
    const msg = appState.dashboard.notifications.map(n => n.message).join('\n\n');
    alert('Adaptive Updates:\n\n' + msg);
  } else {
    alert('No unread notifications. Your metabolic baseline is actively tracking workout volume.');
  }
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}
