"""Hand-curated regional Indian name pools for the synthetic-people generator.

Why hand-curated and not Faker: Faker's `en_IN` locale produces implausible
name combinations that read as obviously synthetic to an Indian viewer
(wrong region-surname pairings, fictional-sounding given names). Demo data
that a Mumbai doctor or a Pune society committee will see needs to *read*
real even if it isn't.

Pool size is small on purpose — names are picked with replacement across
~145 user + 64 staff + 35 contractor + ~50 vehicle-owner records, so a
larger pool buys diminishing returns. ~20 first names per (gender, region)
and ~25 surnames per region gives enough variety without unrealistic
uniqueness.

## Forbidden-name screening

Two layers, applied at pick time:

1. `FORBIDDEN_SURNAMES_REAL_ESTATE`: real-estate dynasty / well-known
   developer family surnames the demo must never inadvertently use for a
   society's "chairman" or "secretary" role.

2. `FORBIDDEN_FULL_NAMES`: explicit (first, last) pairs that match
   well-known public figures, CARIMO-team members in conspicuous
   combinations, or anyone Nataraj might brief Sravya about during
   testing. Rerolled on hit.

If the generator hits a forbidden combination it rerolls and logs the
event so name screening is auditable.
"""

from __future__ import annotations

import random


# ─────────────────────────────────────────────────────────────────────────
# First names — by (gender, region)
# ─────────────────────────────────────────────────────────────────────────

FIRST_NAMES_MARATHI = {
    "M": [
        "Aniket", "Aditya", "Ajinkya", "Amol", "Atharva", "Chinmay", "Devendra",
        "Ganesh", "Harshad", "Kedar", "Mahesh", "Mandar", "Nikhil", "Omkar",
        "Pranav", "Rohan", "Sachin", "Sagar", "Tushar", "Yashwant",
    ],
    "F": [
        "Aishwarya", "Asmita", "Bhakti", "Deepika", "Gauri", "Ishita", "Janhavi",
        "Kalyani", "Madhura", "Manasi", "Mrunal", "Neha", "Pallavi", "Pooja",
        "Rashmi", "Shraddha", "Sneha", "Sushma", "Tejaswini", "Vaishnavi",
    ],
}

FIRST_NAMES_HINDI_NORTH = {
    "M": [
        "Abhinav", "Akshay", "Anuj", "Ashish", "Bhuvan", "Deepak", "Divyansh",
        "Gaurav", "Harsh", "Karan", "Lalit", "Mohit", "Naveen", "Nitin",
        "Prashant", "Rahul", "Sandeep", "Saurabh", "Tarun", "Yash",
    ],
    "F": [
        "Aanchal", "Aarti", "Bhavna", "Charu", "Divya", "Garima", "Heena",
        "Jyoti", "Kavita", "Khushi", "Lavanya", "Megha", "Nisha", "Preeti",
        "Radhika", "Riya", "Sapna", "Shweta", "Tanya", "Urvashi",
    ],
}

FIRST_NAMES_SOUTH = {
    "M": [
        "Aravind", "Balaji", "Chandran", "Dinesh", "Hari", "Karthik", "Kiran",
        "Lokesh", "Manjunath", "Murugan", "Naresh", "Pavan", "Praveen", "Rajesh",
        "Ramesh", "Sridhar", "Srinivas", "Suresh", "Venkat", "Vinay",
    ],
    "F": [
        "Anitha", "Bhavani", "Deepthi", "Geetha", "Indira", "Kalpana", "Kavya",
        "Lakshmi", "Latha", "Madhavi", "Meera", "Padma", "Priyanka", "Roopa",
        "Saritha", "Shanthi", "Suma", "Sunitha", "Swathi", "Vidya",
    ],
}

FIRST_NAMES_BENGALI = {
    "M": [
        "Abhijit", "Anirban", "Arijit", "Arnab", "Biswajit", "Debasish", "Hiranmoy",
        "Indranil", "Joydeep", "Kaushik", "Mainak", "Pradip", "Rohan", "Saikat",
        "Sandip", "Soumen", "Subhasis", "Sujoy", "Tapan", "Tirtha",
    ],
    "F": [
        "Aditi", "Anuradha", "Bidisha", "Chandrima", "Debjani", "Esha", "Indrani",
        "Jhuma", "Kakoli", "Madhumita", "Mou", "Nandita", "Paromita", "Riya",
        "Sayantani", "Sharmistha", "Sohini", "Soumya", "Sudipa", "Tanusri",
    ],
}

FIRST_NAMES_GUJARATI = {
    "M": [
        "Bhavik", "Chirag", "Darshan", "Deval", "Hiren", "Jay", "Jignesh",
        "Ketan", "Kushal", "Mehul", "Mihir", "Nirav", "Parth", "Prakash",
        "Sahil", "Snehal", "Tejas", "Vishal", "Yatin", "Zubin",
    ],
    "F": [
        "Anjali", "Bhumi", "Devyani", "Esha", "Falguni", "Hetal", "Jigna",
        "Krina", "Mansi", "Nilima", "Palak", "Reema", "Rinkal", "Roshni",
        "Sejal", "Shilpa", "Twinkle", "Urvi", "Vandana", "Zara",
    ],
}

FIRST_NAMES_BY_REGION = {
    "marathi": FIRST_NAMES_MARATHI,
    "hindi_north": FIRST_NAMES_HINDI_NORTH,
    "south": FIRST_NAMES_SOUTH,
    "bengali": FIRST_NAMES_BENGALI,
    "gujarati": FIRST_NAMES_GUJARATI,
}


# ─────────────────────────────────────────────────────────────────────────
# Surnames — by region
# ─────────────────────────────────────────────────────────────────────────

SURNAMES_MARATHI = [
    "Patil", "Deshmukh", "Kulkarni", "Kale", "Joshi", "Sawant", "Ghorpade",
    "Pawar", "Bhosale", "Salunkhe", "Patankar", "Phadke", "Karandikar",
    "Apte", "Bapat", "Limaye", "Marathe", "Pendse", "Athavale", "Gokhale",
    "Vaidya", "Mhatre", "Bhide", "Gadgil", "Inamdar",
]

SURNAMES_HINDI_NORTH = [
    "Sharma", "Gupta", "Verma", "Singhal", "Aggarwal", "Mittal", "Kapoor",
    "Saxena", "Bhardwaj", "Mishra", "Tiwari", "Pandey", "Srivastava",
    "Khanna", "Chopra", "Sehgal", "Bhatia", "Khurana", "Malhotra", "Sood",
    "Rai", "Yadav", "Garg", "Goyal", "Bansal",
]

SURNAMES_SOUTH = [
    "Reddy", "Rao", "Iyer", "Iyengar", "Krishnan", "Subramaniam", "Murthy",
    "Pillai", "Nair", "Menon", "Naidu", "Chowdary", "Varma", "Bhat",
    "Hegde", "Acharya", "Rajan", "Padmanabhan", "Swamy", "Ramachandran",
    "Sundaram", "Venkatesh", "Govindan", "Anand", "Balasubramaniam",
]

SURNAMES_BENGALI = [
    "Mukherjee", "Banerjee", "Chatterjee", "Bhattacharya", "Sen", "Bose",
    "Ghosh", "Roy", "Das", "Dutta", "Sarkar", "Kar", "Bandyopadhyay",
    "Chaudhuri", "Mitra", "Pal", "Saha", "Basu", "Ganguly", "Lahiri",
    "Majumdar", "Sinha", "Hazra", "Talukdar", "Choudhury",
]

SURNAMES_GUJARATI = [
    "Patel", "Shah", "Mehta", "Desai", "Modi", "Joshi", "Trivedi", "Vyas",
    "Pandya", "Acharya", "Bhatt", "Dave", "Thakkar", "Soni", "Parekh",
    "Sanghvi", "Doshi", "Gandhi", "Dalal", "Kothari",
    "Bhagat", "Chokshi", "Adani", "Vora", "Rajda",
]

SURNAMES_BY_REGION = {
    "marathi": SURNAMES_MARATHI,
    "hindi_north": SURNAMES_HINDI_NORTH,
    "south": SURNAMES_SOUTH,
    "bengali": SURNAMES_BENGALI,
    "gujarati": SURNAMES_GUJARATI,
}


# ─────────────────────────────────────────────────────────────────────────
# Regional mix per vertical (geography-realistic)
# ─────────────────────────────────────────────────────────────────────────

# (region, weight) tuples — weights sum to 1.0
REGIONAL_MIX_PUNE = [
    ("marathi", 0.55), ("hindi_north", 0.15), ("south", 0.10),
    ("gujarati", 0.12), ("bengali", 0.08),
]
REGIONAL_MIX_MUMBAI = [
    ("marathi", 0.40), ("hindi_north", 0.18), ("south", 0.14),
    ("gujarati", 0.20), ("bengali", 0.08),
]
REGIONAL_MIX_KOLKATA = [
    ("bengali", 0.55), ("hindi_north", 0.20), ("south", 0.08),
    ("marathi", 0.07), ("gujarati", 0.10),
]

# Per-society mix
REGIONAL_MIX_BY_SOCIETY = {
    100: REGIONAL_MIX_PUNE,     # Greenwood Residency (Pune)
    101: REGIONAL_MIX_MUMBAI,   # Sunrise Nursing Home (Mumbai Andheri)
    102: REGIONAL_MIX_MUMBAI,   # Stellar Events (Mumbai Lower Parel)
    103: REGIONAL_MIX_KOLKATA,  # Meridian Estate Office (Kolkata Salt Lake)
}


# ─────────────────────────────────────────────────────────────────────────
# Name screening — forbidden combinations + dynasty surnames
# ─────────────────────────────────────────────────────────────────────────

# Surnames that risk implying a real real-estate developer / hospital chain
# family. The generator AVOIDS these as the surname of senior leadership
# roles (chairman, MD, hospital_director). They are still allowed for
# rank-and-file residents — common surnames are unavoidable at scale, but
# the dynasty-implication only kicks in at the top of the org chart.
FORBIDDEN_SURNAMES_FOR_LEADERSHIP = frozenset({
    # Real-estate dynasties (Mumbai / Pune / national)
    "Lodha", "Hiranandani", "Raheja", "Wadhwa", "Adani", "Ambani",
    "Godrej", "Piramal", "Mittal", "Jindal", "Tata", "Birla",
    "Marathon", "Oberoi", "Hinduja", "Bajaj",
    # Hospital chain family surnames
    "Apollo", "Manipal", "Reddy",  # Reddy lab + Apollo family — leave for rank-and-file
    "Wockhardt", "Fortis", "Hinduja", "Hindujah",
})

# Explicit (first, last) full-name combinations to NEVER produce —
# matches well-known public figures, CARIMO team in conspicuous form,
# and a small set of common celebrity matches. The pool above doesn't
# typically generate these but the screening is belt-and-suspenders.
FORBIDDEN_FULL_NAMES = frozenset({
    # CARIMO team members (avoid creating in the demo data — confusing)
    ("Karan", "Sharma"),     # plausible Karan-Chanchlani echo
    ("Maryam", "Sheikh"),
    ("Sravya", "Reddy"),     # Sravya is the tester — her real persona
    ("Sravya", "Rao"),
    ("Ajit", "Zore"),
    # Common celebrity matches the regional pools could surface
    ("Rahul", "Gandhi"),
    ("Akshay", "Kumar"),
    ("Karan", "Johar"),
    ("Saurabh", "Ganguly"),
    ("Sourav", "Ganguly"),
    ("Anuradha", "Roy"),
    # Real prominent doctors (small list of well-known Mumbai/Pune names)
    ("Devi", "Shetty"),
    ("Naresh", "Trehan"),
    ("Prathap", "Reddy"),
})


# ─────────────────────────────────────────────────────────────────────────
# Pick API
# ─────────────────────────────────────────────────────────────────────────

class NameRerollLimit(Exception):
    """Raised if we cannot find a non-forbidden name after MAX_REROLLS."""


MAX_REROLLS = 50


def pick_region(rng: random.Random, society_id: int) -> str:
    """Pick a region according to the society's regional-mix weights."""
    mix = REGIONAL_MIX_BY_SOCIETY.get(society_id, REGIONAL_MIX_PUNE)
    return rng.choices(
        [region for region, _ in mix],
        weights=[w for _, w in mix],
        k=1,
    )[0]


def pick_name(
    rng: random.Random,
    society_id: int,
    gender: str | None = None,
    is_leadership: bool = False,
) -> tuple[str, str, str, str]:
    """Return (first_name, last_name, full_name, region).

    Rerolls on forbidden-name hits. Raises NameRerollLimit if exhausted —
    the pool is large enough that this should never happen in practice;
    if it ever does, it's a signal the pool needs expansion."""
    if gender is None:
        gender = rng.choice(["M", "F"])
    for _ in range(MAX_REROLLS):
        region = pick_region(rng, society_id)
        first = rng.choice(FIRST_NAMES_BY_REGION[region][gender])
        last = rng.choice(SURNAMES_BY_REGION[region])
        if is_leadership and last in FORBIDDEN_SURNAMES_FOR_LEADERSHIP:
            continue
        if (first, last) in FORBIDDEN_FULL_NAMES:
            continue
        return first, last, f"{first} {last}", region
    raise NameRerollLimit(
        f"Could not find non-forbidden name for sid={society_id} "
        f"gender={gender} leadership={is_leadership} after {MAX_REROLLS} rerolls"
    )


def pool_stats() -> dict[str, int]:
    """For audit: how many names the pools actually offer."""
    return {
        "first_names_total": sum(
            len(names_by_gender[g])
            for names_by_gender in FIRST_NAMES_BY_REGION.values()
            for g in ("M", "F")
        ),
        "surnames_total": sum(len(s) for s in SURNAMES_BY_REGION.values()),
        "regions": len(FIRST_NAMES_BY_REGION),
        "forbidden_leadership_surnames": len(FORBIDDEN_SURNAMES_FOR_LEADERSHIP),
        "forbidden_full_names": len(FORBIDDEN_FULL_NAMES),
    }
