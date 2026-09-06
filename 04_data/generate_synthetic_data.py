"""
Synthetic Loan Portfolio Dataset Generator
Harvest Trust Financial (HTF) — fictional agricultural lender, portfolio project.

Generates a small star-schema-ready dataset:
  - dim_borrower.csv               one row per borrower
  - dim_loan.csv                   one row per loan (static attributes)
  - fact_loan_monthly_snapshot.csv one row per loan per month (24-month history)
  - dim_risk_tier.csv              lookup: risk tier label + sort order
  - dim_dpd_bucket.csv             lookup: days-past-due bucket label + sort order
  - dim_calendar.csv               lookup: monthly calendar dimension

All data is entirely fictional. No real client, loan, or institution data is used.
Random seed is fixed for reproducibility.
"""

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import date

RNG = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
N_BORROWERS = 380
SNAPSHOT_MONTHS = 24
LAST_SNAPSHOT_MONTH = date(2026, 7, 1)  # most recent complete month before "today" (Aug 4, 2026)

REGIONS = ["Saskatchewan", "Alberta", "Manitoba"]
REGION_WEIGHTS = [0.45, 0.33, 0.22]
REGION_RISK_MULT = {"Saskatchewan": 1.00, "Alberta": 1.05, "Manitoba": 0.95}

SECTORS = ["Grain & Oilseed", "Livestock", "Dairy", "Mixed Farming"]
SECTOR_WEIGHTS = [0.45, 0.18, 0.10, 0.27]
SECTOR_RISK_MULT = {"Grain & Oilseed": 1.00, "Livestock": 1.15, "Dairy": 0.85, "Mixed Farming": 0.90}

LOAN_TYPES = ["Term Loan", "Operating Line of Credit", "Equipment Loan", "Farm Mortgage"]
LOAN_TYPE_WEIGHTS = [0.40, 0.30, 0.20, 0.10]
LOAN_TYPE_PARAMS = {
    # (principal_low, principal_high, rate_low, rate_high, amort_years_choices)
    "Term Loan": (100_000, 1_500_000, 0.065, 0.085, [5, 7, 10]),
    "Operating Line of Credit": (50_000, 500_000, 0.070, 0.090, [1]),
    "Equipment Loan": (50_000, 800_000, 0.060, 0.080, [5, 7]),
    "Farm Mortgage": (200_000, 3_000_000, 0.055, 0.070, [15, 20, 25]),
}
COLLATERAL_BY_TYPE = {
    "Term Loan": ["Farmland", "General Security Agreement"],
    "Operating Line of Credit": ["General Security Agreement"],
    "Equipment Loan": ["Equipment"],
    "Farm Mortgage": ["Farmland"],
}

RISK_TIER_LABELS = {1: "Tier 1 - Low Risk", 2: "Tier 2 - Moderate Risk", 3: "Tier 3 - Elevated Risk", 4: "Tier 4 - High Risk / Watch List"}

DPD_BUCKETS = ["Current", "1-29 Days", "30-59 Days", "60-89 Days", "90+ Days"]
DPD_SORT = {b: i for i, b in enumerate(DPD_BUCKETS)}

LOAN_OFFICERS = [
    "J. Halvorsen", "M. Reimer", "A. Dubois", "S. Kowalski", "T. Braun",
    "R. Yaremko", "K. Lund", "P. Anholt", "C. Friesen", "D. Sorensen",
]

# ---------------------------------------------------------------------------
# Fictional business name generator
# ---------------------------------------------------------------------------
SURNAMES = [
    "Whitmore", "Bergen", "Halvorsen", "Kowalski", "Dubois", "Reimer", "Novak", "Fischer",
    "Larsen", "Petrov", "O'Neil", "Schmidt", "Braun", "Kessler", "Voss", "Iverson",
    "Thorsen", "Radke", "Yaremko", "Lund", "Baumann", "Kristoff", "Novikov", "Anholt",
    "Marchand", "Whitfield", "Sorensen", "Klassen", "Friesen", "Toews", "Dueck", "Janzen",
    "Wiebe", "Enns", "Peters", "Giesbrecht", "Loewen", "Harder", "Neufeld", "Martens",
]
DESCRIPTORS = [
    "Prairie", "Golden Field", "Northern", "Twin Creek", "Wheatland", "Meadowbrook",
    "Silver Birch", "Bluestem", "Coulee", "Rolling Hills", "Sunrise", "Big Sky",
    "Red River", "Elk Valley", "Cypress Hills", "Qu'Appelle Valley", "Assiniboine",
    "Whitecap", "Harvest Moon", "Rimrock", "Stonebridge", "Long Grass",
]
ENTITY_BY_SECTOR = {
    "Grain & Oilseed": ["Grain Farms Ltd.", "Grain Co.", "Farms Ltd."],
    "Livestock": ["Ranch Ltd.", "Livestock Co.", "Cattle Co."],
    "Dairy": ["Dairy Farm Ltd.", "Dairy Ltd."],
    "Mixed Farming": ["Farms Ltd.", "Family Farm", "AgriBusiness Ltd."],
}

def make_borrower_name(sector, used_names):
    for _ in range(20):
        name = f"{RNG.choice(SURNAMES)} {RNG.choice(DESCRIPTORS)} {RNG.choice(ENTITY_BY_SECTOR[sector])}"
        if name not in used_names:
            used_names.add(name)
            return name
    # fallback with numeric suffix if we somehow collide 20x
    name = f"{name} #{len(used_names)}"
    used_names.add(name)
    return name

# ---------------------------------------------------------------------------
# 1. dim_borrower
# ---------------------------------------------------------------------------
used_names = set()
borrower_rows = []
for i in range(1, N_BORROWERS + 1):
    borrower_id = f"BOR-{1000 + i}"
    region = RNG.choice(REGIONS, p=REGION_WEIGHTS)
    sector = RNG.choice(SECTORS, p=SECTOR_WEIGHTS)
    name = make_borrower_name(sector, used_names)
    years_in_operation = int(np.clip(RNG.gamma(shape=4, scale=5), 2, 60))
    relationship_start = LAST_SNAPSHOT_MONTH - relativedelta(years=int(RNG.integers(1, min(years_in_operation, 15) + 1)))
    operation_size_acres = None
    herd_size_head = None
    if sector in ("Grain & Oilseed", "Mixed Farming"):
        operation_size_acres = int(np.clip(RNG.gamma(shape=3, scale=650), 160, 12000))
    if sector in ("Livestock", "Dairy", "Mixed Farming"):
        herd_size_head = int(np.clip(RNG.gamma(shape=3, scale=90), 20, 2500))
    loan_officer = RNG.choice(LOAN_OFFICERS)

    # latent credit-quality driver: combination of sector/region risk multipliers + idiosyncratic noise
    idio_noise = RNG.lognormal(mean=0.0, sigma=0.35)
    risk_score = SECTOR_RISK_MULT[sector] * REGION_RISK_MULT[region] * idio_noise

    borrower_rows.append({
        "borrower_id": borrower_id,
        "borrower_name": name,
        "region": region,
        "sector": sector,
        "years_in_operation": years_in_operation,
        "operation_size_acres": operation_size_acres,
        "herd_size_head": herd_size_head,
        "relationship_start_date": relationship_start,
        "primary_loan_officer": loan_officer,
        "_risk_score": risk_score,  # internal, dropped before export
    })

dim_borrower = pd.DataFrame(borrower_rows)

# assign base risk tier from risk_score quantiles (higher score = higher risk)
q = dim_borrower["_risk_score"].rank(pct=True)
def tier_from_pct(p):
    if p < 0.40:
        return 1
    elif p < 0.75:
        return 2
    elif p < 0.93:
        return 3
    return 4
dim_borrower["_base_tier"] = q.apply(tier_from_pct)

# ---------------------------------------------------------------------------
# 2. dim_loan
# ---------------------------------------------------------------------------
loan_rows = []
loan_counter = 20001
for _, b in dim_borrower.iterrows():
    n_loans = RNG.choice([1, 2, 3], p=[0.62, 0.30, 0.08])
    chosen_types = RNG.choice(LOAN_TYPES, size=n_loans, replace=(n_loans > len(LOAN_TYPES)), p=LOAN_TYPE_WEIGHTS)
    for lt in chosen_types:
        loan_id = f"LN-{loan_counter}"
        loan_counter += 1
        p_low, p_high, r_low, r_high, amort_choices = LOAN_TYPE_PARAMS[lt]
        original_principal = round(float(RNG.uniform(p_low, p_high)), -2)
        interest_rate = round(float(RNG.uniform(r_low, r_high)), 4)
        amortization_years = int(RNG.choice(amort_choices))

        earliest_origination = max(b["relationship_start_date"], LAST_SNAPSHOT_MONTH - relativedelta(years=10))
        latest_origination = LAST_SNAPSHOT_MONTH - relativedelta(months=1)
        span_days = max((latest_origination - earliest_origination).days, 30)
        origination_date = earliest_origination + pd.Timedelta(days=int(RNG.integers(0, span_days)))
        origination_date = pd.Timestamp(origination_date).to_pydatetime().date().replace(day=1)

        if lt == "Operating Line of Credit":
            # Revolving facility: renews annually. Display the *next* renewal date on/after the
            # reporting window's last month, rather than the original+1yr (which could be years
            # in the past for an older relationship) — it is never treated as "matured" below.
            maturity_date = origination_date + relativedelta(years=1)
            while maturity_date < LAST_SNAPSHOT_MONTH:
                maturity_date += relativedelta(years=1)
        else:
            maturity_date = origination_date + relativedelta(years=amortization_years)

        collateral_type = RNG.choice(COLLATERAL_BY_TYPE[lt])
        if collateral_type == "Farmland":
            collateral_value = round(original_principal * float(RNG.uniform(1.3, 2.2)), -2)
        elif collateral_type == "Equipment":
            collateral_value = round(original_principal * float(RNG.uniform(1.0, 1.4)), -2)
        else:
            collateral_value = round(original_principal * float(RNG.uniform(1.1, 1.6)), -2)

        loan_rows.append({
            "loan_id": loan_id,
            "borrower_id": b["borrower_id"],
            "loan_type": lt,
            "origination_date": origination_date,
            "maturity_date": maturity_date,
            "original_principal": original_principal,
            "interest_rate": interest_rate,
            "amortization_years": amortization_years,
            "collateral_type": collateral_type,
            "collateral_value": collateral_value,
            "_base_tier": b["_base_tier"],
        })

dim_loan = pd.DataFrame(loan_rows)

# ---------------------------------------------------------------------------
# 3. Monthly snapshot simulation (fact_loan_monthly_snapshot)
# ---------------------------------------------------------------------------
snapshot_months = [LAST_SNAPSHOT_MONTH - relativedelta(months=k) for k in range(SNAPSHOT_MONTHS - 1, -1, -1)]

def seasonality_mult(month_num):
    if month_num in (3, 4, 5):       # Mar-May: pre-seeding cash crunch
        return 1.45
    if month_num in (10, 11, 12):    # Oct-Dec: post-harvest cash flush
        return 0.65
    return 1.00

# Target (stationary) DPD-bucket distribution per risk tier — [Current, 1-29, 30-59, 60-89, 90+].
# A loan's monthly state is drawn as: persist in its current bucket most months (delinquency
# tends to cluster for a few months at a time), or "redraw" toward this target distribution.
# Because every redraw pulls back toward the same target, the portfolio-level delinquency rate
# stays stable over time instead of drifting — it only moves with seasonality, as intended.
TARGET_DPD_DIST = {
    1: [0.980, 0.0140, 0.0040, 0.0015, 0.0005],
    2: [0.940, 0.0350, 0.0150, 0.0075, 0.0025],
    3: [0.850, 0.0750, 0.0450, 0.0225, 0.0075],
    4: [0.650, 0.1400, 0.1050, 0.0700, 0.0350],
}
PERSIST_PROB = 0.72          # chance a loan stays in its current DPD bucket this month
DEFAULT_EXIT_PROB_FROM_90 = 0.07  # monthly chance a 90+ Days loan exits to Default/Charged Off

def seasonal_dpd_dist(base_tier, month_num):
    """Target distribution adjusted for seasonality: delinquent buckets scaled by the
    seasonality multiplier, Current absorbs the remainder so probabilities still sum to 1."""
    base = TARGET_DPD_DIST[base_tier]
    season = seasonality_mult(month_num)
    delinq = [p * season for p in base[1:]]
    delinq_sum = sum(delinq)
    if delinq_sum >= 0.95:  # safety clamp, should not trigger at these parameters
        scale = 0.95 / delinq_sum
        delinq = [p * scale for p in delinq]
        delinq_sum = 0.95
    current = 1.0 - delinq_sum
    return [current] + delinq

def monthly_payment(principal, annual_rate, amort_years):
    r = annual_rate / 12
    n = amort_years * 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** (-n))

snapshot_rows = []
loan_status_final = {}  # loan_id -> final status (Active / Paid Off / Default/Charged Off)

for _, loan in dim_loan.iterrows():
    loan_id = loan["loan_id"]
    lt = loan["loan_type"]
    base_tier = int(loan["_base_tier"])
    origination = loan["origination_date"]
    maturity = loan["maturity_date"]
    principal = loan["original_principal"]
    rate = loan["interest_rate"]
    amort_years = loan["amortization_years"]

    # A loan that already existed before the reporting window starts should enter the window
    # already at its stationary DPD mix (not artificially "Current") — otherwise every loan
    # looks freshly clean in month 1 and the portfolio delinquency rate ramps up as an artifact
    # of initialization rather than reflecting real risk. Genuinely new loans (originated inside
    # the window) do start Current, since they have no payment history yet.
    if origination < snapshot_months[0]:
        state = RNG.choice(DPD_BUCKETS, p=seasonal_dpd_dist(base_tier, snapshot_months[0].month))
    else:
        state = "Current"
    exited = False
    status = "Active"

    is_loc = (lt == "Operating Line of Credit")
    pmt = 0.0 if is_loc else monthly_payment(principal, rate, amort_years)

    for month in snapshot_months:
        if month < origination or exited:
            continue
        if (not is_loc) and month >= maturity:
            # term/equipment/mortgage loan matured within the window -> stop appearing
            loan_status_final[loan_id] = "Paid Off"
            exited = True
            continue
        # Operating Lines of Credit are revolving and renew annually — never exit via maturity.

        elapsed_months = (month.year - origination.year) * 12 + (month.month - origination.month)

        # --- DPD state: persist, or redraw toward the tier's seasonally-adjusted target mix ---
        if RNG.random() >= PERSIST_PROB:
            dist = seasonal_dpd_dist(base_tier, month.month)
            state = RNG.choice(DPD_BUCKETS, p=dist)

        if state == "90+ Days" and RNG.random() < DEFAULT_EXIT_PROB_FROM_90:
            status = "Default/Charged Off"

        days_past_due = {"Current": 0, "1-29 Days": int(RNG.integers(1, 30)),
                          "30-59 Days": int(RNG.integers(30, 60)), "60-89 Days": int(RNG.integers(60, 90)),
                          "90+ Days": int(RNG.integers(90, 240))}[state]

        # risk tier responds to sustained severe delinquency
        severity_bump = 1 if state in ("60-89 Days", "90+ Days") else 0
        risk_tier = int(np.clip(base_tier + severity_bump, 1, 4))

        # --- balance ---
        if is_loc:
            util_base = 0.55 + (0.20 if month.month in (3, 4, 5, 6) else 0.0) - (0.15 if month.month in (10, 11, 12) else 0.0)
            utilization = float(np.clip(RNG.normal(util_base, 0.10), 0.15, 0.98))
            outstanding_balance = round(principal * utilization, 2)
            scheduled_payment = round(outstanding_balance * rate / 12, 2)
        else:
            n = amort_years * 12
            r_m = rate / 12
            k = min(elapsed_months, n)
            if r_m == 0:
                balance = principal * (1 - k / n)
            else:
                balance = principal * ((1 + r_m) ** n - (1 + r_m) ** k) / ((1 + r_m) ** n - 1)
            outstanding_balance = round(max(balance, 0.0), 2)
            scheduled_payment = round(pmt, 2)

        snapshot_rows.append({
            "loan_id": loan_id,
            "snapshot_month": month,
            "outstanding_balance": outstanding_balance,
            "scheduled_payment": scheduled_payment,
            "days_past_due": days_past_due,
            "dpd_bucket": state,
            "risk_tier": risk_tier,
            "loan_status_snapshot": "Delinquent - Default Pending" if status == "Default/Charged Off" else "Active",
        })

        if status == "Default/Charged Off":
            loan_status_final[loan_id] = "Default/Charged Off"
            exited = True

    if loan_id not in loan_status_final:
        loan_status_final[loan_id] = "Active"

fact_snapshot = pd.DataFrame(snapshot_rows)
fact_snapshot = fact_snapshot.sort_values(["loan_id", "snapshot_month"]).reset_index(drop=True)

# watch_list_flag: risk tier worsened OR dpd bucket rank worsened vs prior month for same loan
fact_snapshot["_dpd_rank"] = fact_snapshot["dpd_bucket"].map(DPD_SORT)
fact_snapshot["_prev_tier"] = fact_snapshot.groupby("loan_id")["risk_tier"].shift(1)
fact_snapshot["_prev_dpd_rank"] = fact_snapshot.groupby("loan_id")["_dpd_rank"].shift(1)
fact_snapshot["watch_list_flag"] = np.where(
    (fact_snapshot["_prev_tier"].notna()) &
    ((fact_snapshot["risk_tier"] > fact_snapshot["_prev_tier"]) | (fact_snapshot["_dpd_rank"] > fact_snapshot["_prev_dpd_rank"])),
    "Y", "N"
)
fact_snapshot = fact_snapshot.drop(columns=["_dpd_rank", "_prev_tier", "_prev_dpd_rank"])

# finalize dim_loan.loan_status
dim_loan["loan_status"] = dim_loan["loan_id"].map(loan_status_final).fillna("Active")
dim_loan = dim_loan.drop(columns=["_base_tier"])
dim_borrower = dim_borrower.drop(columns=["_risk_score", "_base_tier"])

# ---------------------------------------------------------------------------
# 4. Lookup / dimension tables
# ---------------------------------------------------------------------------
dim_risk_tier = pd.DataFrame([
    {"risk_tier": k, "risk_tier_label": v, "sort_order": k} for k, v in RISK_TIER_LABELS.items()
])

dim_dpd_bucket = pd.DataFrame([
    {"dpd_bucket": b, "sort_order": i, "is_delinquent": 0 if b == "Current" else 1}
    for i, b in enumerate(DPD_BUCKETS)
])

dim_calendar = pd.DataFrame([
    {
        "snapshot_month": m,
        "year": m.year,
        "month_number": m.month,
        "month_name": m.strftime("%B"),
        "quarter": f"Q{(m.month - 1) // 3 + 1}",
        "month_year_label": m.strftime("%b %Y"),
    }
    for m in snapshot_months
])

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
dim_borrower.to_csv("raw/dim_borrower.csv", index=False)
dim_loan.to_csv("raw/dim_loan.csv", index=False)
fact_snapshot.to_csv("raw/fact_loan_monthly_snapshot.csv", index=False)
dim_risk_tier.to_csv("raw/dim_risk_tier.csv", index=False)
dim_dpd_bucket.to_csv("raw/dim_dpd_bucket.csv", index=False)
dim_calendar.to_csv("raw/dim_calendar.csv", index=False)

print("Rows generated:")
print(f"  dim_borrower:               {len(dim_borrower):,}")
print(f"  dim_loan:                   {len(dim_loan):,}")
print(f"  fact_loan_monthly_snapshot: {len(fact_snapshot):,}")
print(f"  dim_risk_tier:              {len(dim_risk_tier):,}")
print(f"  dim_dpd_bucket:             {len(dim_dpd_bucket):,}")
print(f"  dim_calendar:               {len(dim_calendar):,}")
print("done")
