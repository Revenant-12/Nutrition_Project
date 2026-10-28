# AuraFit — Adaptive Nutrition & Fitness Tracker

An adaptive nutrition, workout, and recipe tracking Progressive Web App (PWA) faithfully implementing all features defined in `Nutrition Pseudocode.txt`.

---

## 🌟 Key Features

1. **Metabolic Engine & Personalized Onboarding**:
   - **Mifflin-St Jeor & Katch-McArdle equations**: Automatically uses body fat percentage for Lean Body Mass (LBM) calculations when provided.
   - **HRT-Aware Calculations**: Supports feminizing and masculinizing hormone therapy transitions with the $>12$ month metabolic threshold rule.
   - **Dynamic TDEE & Goals**: Calculates deficit/surplus offsets for Weight Loss (-20%), Maintenance, Musculature Retention, and Muscle Gain (+400 kcal).
   - **Macro Target Allocations**: Supports Sedentary, Active/Fitness, Resistance/Strength, Endurance, and Hypoenergetic Weight Loss tiers with High Body Fat LBM reference weight thresholds.

2. **Daily Dashboard (Midnight Resets)**:
   - Real-time calorie and macronutrient intake balance (eaten vs. remaining).
   - Preference toggle between Calories Only, Macros Only, or Both.
   - Resets automatically at 00:00 local time.

3. **Active Workout Logger & Volume Comparison Table**:
   - Live session timer, exercise search, and muscle group tagging.
   - Set logging with weight (lbs/kg toggle), reps, distance, and duration.
   - **Fun Volume Comparisons**: Upon finishing, calculates total volume lifted and displays exact tier matches from `Nutrition Pseudocode.txt` (*giant panda*, *vending machine*, *classic VW Beetle*, *African bush elephant*, *T-Rex*, *NASA Space Shuttle Orbiter*).
   - Estimates calories burned for strength training ($duration \times weight \times 0.06$) and cardio.

4. **Adaptive Activity & TDEE Rebalancing Engine (Weekly Update)**:
   - Tracks a rolling 14-day average of workout calories burned.
   - Automatically re-evaluates baseline TDEE every 7 days:
     $$\text{Calculated TDEE} = (\text{BMR} \times 1.2) + \text{Average 14-day Exercise Burn}$$
   - Clamps changes to a safe maximum of $\pm 150\text{ kcal/week}$ and displays notification banner to the user.

5. **Smart Recipe Cookbook & Safe Food Tracker**:
   - **Batch Raw Weight Scaling**: Sums ingredients to establish total batch weight and scales macros accurately by portion consumed:
     $$\text{Portion Macros} = \left(\frac{\text{Portion Consumed (g)}}{\text{Total Batch Weight (g)}}\right) \times \text{Total Batch Macros}$$
   - **Safe Food Rankings**: 3-tier safety tracking (*Mostly Safe*, *Safe*, *Always Safe*).
   - **Recipe Recommender**: Supports Hard filtering (strictly safe ingredients) and Soft filtering (ranks safe recipes first), specific ingredient searches, familiarity matching, and macro vs. calorie prioritization.

6. **Computer Vision & Camera Integration (Google Gemini Vision API)**:
   - **Gym Machine Identifier**: Snap a picture of any machine to detect its name, targeted muscles, setup tips, and automatically add it to your live workout.
   - **Nutrition Label Scanner**: Snap a picture of food packaging to automatically extract calories, protein, carbs, and fat.

7. **Food Database**:
   - Built-in instant staple foods database + real-time search from **Open Food Facts API**.

---

## 🚀 How to Run the App

1. Ensure the Python virtual environment is activated:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Run the application:
   ```powershell
   python run.py
   ```

3. Open in your browser:
   - On your computer: `http://127.0.0.1:8000`
   - On your phone (connected to same Wi-Fi): `http://<your-local-ip>:8000`

### Installing as a Mobile App (PWA)
- **iPhone / iPad**: Open in Safari $\rightarrow$ tap the **Share** button $\rightarrow$ tap **Add to Home Screen**.
- **Android**: Open in Chrome $\rightarrow$ tap the three dots $\rightarrow$ tap **Install App** / **Add to Home Screen**.

---

## 🧪 Running the Automated Test Suites

- **Core Metabolic Calculations Test**:
  ```powershell
  .\.venv\Scripts\python -m unittest tests/test_calculations.py
  ```

- **Full End-to-End API Workflow Test**:
  ```powershell
  .\.venv\Scripts\python -m unittest tests/test_endpoints.py
  ```

