"""Complaint text templates for the synthetic complaints generator.

Templates are organised as
   `TEMPLATES[(vertical_or_common, category)][language] = [template, ...]`

`vertical_or_common = "common"` templates apply across all verticals;
vertical-specific keys override / extend. Categories use the same names
as the Part 1 configs so the generator can dispatch directly.

Languages:
  - "en"        English (the default; every category has en templates)
  - "hi"        Hindi in Devanagari (most-common categories only)
  - "hinglish"  Roman-script Hindi-English mix (common categories)
  - "te"        Telugu in Telugu script (small sample, urgency-only)

Templates may include placeholders that the generator substitutes:
  {unit}    the complaint's unit_number
  {detail}  a small randomized detail (which appliance, where, etc.)
  {time}    a time-of-day reference

Photo-only + voice-note templates are stored under the "[meta]" key.
"""

from __future__ import annotations

import random


# ─────────────────────────────────────────────────────────────────────────
# Cross-vertical (common) templates
# ─────────────────────────────────────────────────────────────────────────

COMMON = {

    "Plumbing": {
        "en": [
            "Water leakage from kitchen sink in {unit}, dripping since morning, please send plumber urgently.",
            "Bathroom drain in {unit} is completely blocked, water not going down at all.",
            "Toilet flush not working in {unit} since yesterday.",
            "Constant water dripping from ceiling in {unit}, looks like leak from above unit.",
            "Tap broken in {unit}'s master bedroom bathroom, can't shut off properly.",
        ],
        "hi": [
            "{unit} में बाथरूम का नल टूट गया है, पानी रुक नहीं रहा।",
            "{unit} की रसोई में पानी का पाइप लीक हो रहा है।",
            "{unit} में टॉयलेट का फ्लश काम नहीं कर रहा।",
        ],
        "hinglish": [
            "{unit} mein bathroom ka tap kharab hai, paani band nahi ho raha. Plz urgently fix karwa do.",
            "{unit} ke kitchen sink se paani leak ho raha hai subah se.",
            "Drainage block ho gaya hai {unit} mein, paani jam ho raha.",
        ],
    },

    "Electrical": {
        "en": [
            "Power failure in {unit} since 2 hours, only some sockets working.",
            "Sparking from main switch in {unit}, please send electrician immediately.",
            "Living room fan in {unit} making loud noise and slowing down.",
            "Geyser tripping the MCB whenever switched on in {unit}.",
            "Two bedroom plug points dead in {unit}, others fine.",
        ],
        "hi": [
            "{unit} में बिजली नहीं आ रही, मुख्य स्विच में चिंगारी निकल रही है।",
            "{unit} के बेडरूम का पंखा आवाज कर रहा है।",
        ],
        "hinglish": [
            "{unit} mein power chala gaya hai sirf one room mein. MCB ka issue lag raha.",
            "Geyser on karne par MCB trip ho raha {unit} mein, electrician bhejo.",
        ],
    },

    "AC/Cooling": {
        "en": [
            "Living room AC in {unit} not cooling at all since yesterday evening.",
            "AC in master bedroom of {unit} dripping water from indoor unit on the bed.",
            "Strange burning smell from AC compressor in {unit}'s balcony, switched off as precaution.",
            "AC remote completely dead in {unit}, batteries already replaced.",
        ],
        "hi": [
            "{unit} का AC ठंडा नहीं कर रहा, कमरा गरम हो रहा है।",
        ],
        "hinglish": [
            "{unit} ka AC paani tapka raha bed pe, kal raat se. Bahot mushkil ho rahi.",
            "Master bedroom AC band ho gaya, garmi mein bahut takleef ho rahi {unit} mein.",
        ],
    },

    "Water Supply": {
        "en": [
            "No water supply in {unit} since morning. Other units also reporting same.",
            "Water pressure extremely low in {unit}, only trickle from tap.",
            "Water coming yellow/brown from tap in {unit}.",
        ],
        "hi": [
            "{unit} में सुबह से पानी नहीं आ रहा है।",
        ],
        "hinglish": [
            "{unit} mein paani nahi aa raha subah se, society overhead tank check karwao.",
        ],
    },

    "Lighting": {
        "en": [
            "Common-area lights in B-wing corridor not working since last evening.",
            "Staircase light between floor 3-4 fused, very dark at night.",
            "Lobby light at main entrance flickering badly.",
        ],
        "hinglish": [
            "Corridor light kharab hai B-wing mein, raat ko bahut andhera ho jata.",
        ],
    },

    "Housekeeping": {
        "en": [
            "Common-area near {unit} not cleaned today, dust everywhere.",
            "Garbage not collected from our floor since 2 days.",
            "Lift floor very dirty, looks like someone vomited last night.",
            "Cobwebs in staircase landing near {unit}, please clean.",
        ],
        "hi": [
            "{unit} के पास का गलियारा साफ नहीं हुआ है आज।",
        ],
    },

    "Garbage/Waste": {
        "en": [
            "Garbage bin overflowing near {unit}, smell very bad.",
            "Wet waste not separated by housekeeping, mixed with dry.",
        ],
        "hinglish": [
            "Garbage 2 din se collect nahi hua, badbu aa rahi {unit} ke paas.",
        ],
    },

    "Pest Control": {
        "en": [
            "Cockroaches in kitchen of {unit}, pest control needed urgently.",
            "Rats spotted in basement parking near pillar P-12.",
            "Mosquito problem severe in {unit}, fogging not done last month.",
        ],
    },

    "Elevator": {
        "en": [
            "Lift in {unit}'s tower stuck on 7th floor, alarm bell ringing.",
            "Lift door not closing properly in C-wing, stays open 30 seconds.",
            "Lift light off inside, can't see buttons. Tower B.",
        ],
        "hinglish": [
            "Tower-C ka lift stuck ho gaya 7th floor pe, alarm baj raha.",
        ],
    },

    "Security": {
        "en": [
            "Unknown person seen loitering near {unit} for past hour.",
            "Main gate guard not present at his post, gate left unattended.",
            "CCTV at parking entrance not recording (last night incident no footage).",
        ],
        "hinglish": [
            "Guard duty pe nahi hai gate par, security risk hai.",
        ],
    },

    "Noise/Visitor": {
        "en": [
            "Loud music from {unit} after 11pm, neighbours unable to sleep.",
            "Construction noise from {unit} starting before 7am, breaks society rules.",
            "Excessive visitor parking blocking residents' designated slots.",
        ],
    },

    "Parking Management": {
        "en": [
            "Vehicle {plate} parked in my allotted slot, owner contact?",
            "Unknown car blocking my exit at {slot}, can't move my own vehicle.",
            "Visitor vehicle parked overnight in visitor zone — past 4-hour limit.",
        ],
        "hinglish": [
            "Visitor ki gaadi {plate} meri slot pe khadi hai, hata do.",
        ],
    },

    "Fire Safety": {
        "en": [
            "Fire extinguisher near staircase {detail} appears empty / pressure gauge red.",
            "Fire exit door on 4th floor padlocked — safety violation.",
            "Smoke detector beeping continuously in {unit}'s corridor.",
        ],
    },

    "Carpentry": {
        "en": [
            "Bedroom door hinge broken in {unit}, door won't close.",
            "Cupboard shutter fell off in {unit}'s kitchen.",
        ],
        "hinglish": [
            "{unit} ka bedroom darwaza kharab ho gaya hai, hinge tut gaya.",
        ],
    },

    "Painting": {
        "en": [
            "Paint peeling badly in common corridor near {unit}, looks shabby.",
            "Lift lobby walls have many scratches and patches.",
        ],
    },

    "CCTV/Intercom": {
        "en": [
            "Intercom from {unit} to main gate not working, can't authorize visitors.",
            "CCTV camera at parking exit appears broken — cable cut?",
        ],
    },

    "Gardening": {
        "en": [
            "Lawn not mowed for over 2 weeks, looks unkempt.",
            "Plants near {unit}'s window dying, need watering / replacement.",
        ],
    },

    "Generator/Power Backup": {
        "en": [
            "Generator did not start during last night's power cut, lifts stopped.",
            "Generator noise extremely loud, disturbs sleep — needs servicing.",
        ],
    },

    "Sewage/Drainage": {
        "en": [
            "Sewage smell from drain near {unit}, severe.",
            "Open drain near children's play area, mosquito breeding risk.",
        ],
        "hinglish": [
            "{unit} ke baahar drainage se badbu aa rahi, blockage hoga.",
        ],
    },

    "Civil/Structural": {
        "en": [
            "Crack appearing on living-room wall in {unit}, getting bigger.",
            "Tile cracked in {unit}'s bathroom floor, water seeping under.",
        ],
    },

    "Swimming Pool": {
        "en": [
            "Pool water looks cloudy / green-tinged, hasn't been cleaned this week.",
            "Pool chemical smell very strong, kids' eyes were stinging yesterday.",
        ],
    },

    "Sports/Gym/Clubhouse": {
        "en": [
            "Treadmill in gym belt slipping badly, unsafe to use.",
            "AC in clubhouse function room not working — booked for event tomorrow.",
        ],
    },

    "Children's Play Area": {
        "en": [
            "Swing chain broken in play area, dangerous for small kids.",
            "Sand pit needs refilling — almost no sand left.",
        ],
    },

    "Other": {
        "en": [
            "{detail} — please look into when possible.",
            "Issue near {unit} that I want to flag, not sure which category.",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────
# Hospital-specific (Sunrise) — vertical=101
# ─────────────────────────────────────────────────────────────────────────

SUNRISE = {

    "Patient Room AC": {
        "en": [
            "AC in {unit} not cooling, patient family complaining of stuffy room.",
            "AC in {unit} dripping water onto patient's bed — immediate attention.",
            "AC making loud rattling noise in {unit}, disturbing patient rest.",
        ],
        "hinglish": [
            "{unit} ka AC band ho gaya hai, room garam ho raha. Family complain kar rahi.",
            "{unit} ke AC se paani tapak raha bed pe, urgent maintenance.",
        ],
    },

    "Bed/Mattress Issue": {
        "en": [
            "Bed in {unit} not raising properly with controls, motor seems jammed.",
            "Mattress cover torn in {unit}, hygiene risk.",
            "Bed wheel broken in {unit}, can't move bed for procedures.",
        ],
    },

    "Nurse Call System": {
        "en": [
            "Nurse-call button at {unit} not working, patient unable to call for help.",
            "Nurse-call station at A-ward 2F shows {unit} red but no actual signal — false alarm.",
            "Entire nurse-call panel dead at B-wing ICU station, urgent.",
        ],
    },

    "Pharmacy Stock-Out": {
        "en": [
            "Insulin (rapid-acting) stock at zero in pharmacy, urgent procurement needed.",
            "Surgical gloves size M completely out, OT requested urgent restock.",
            "Antibiotics stock low — ward 2F flagged shortage.",
        ],
    },

    "Equipment Calibration": {
        "en": [
            "ECG machine in {unit} showing inconsistent readings, needs calibration check.",
            "BP monitor in nursing station 3F reading 20 points higher than manual cuff.",
            "Infusion pump in {unit} flow-rate accuracy needs verification.",
        ],
    },

    "Medical Gas / Oxygen": {
        "en": [
            "Oxygen flow at {unit} bedside outlet seems low, gauge not reading correctly.",
            "Suction unit in {unit} not generating enough negative pressure.",
            "Central O2 supply pressure alarm sounded twice this hour at B-ICU panel.",
        ],
    },

    "Linen / Laundry": {
        "en": [
            "{unit} bedsheets not changed today, patient family complaining.",
            "Linen delivery from laundry contractor short by 20 sets for ward 1F.",
            "Stained sheets received from laundry in this morning's delivery.",
        ],
    },

    "Food Service / Diet": {
        "en": [
            "Diet tray for {unit} delivered cold and 45 minutes late.",
            "Diabetic patient in {unit} received regular meal by mistake.",
            "Catering vendor's serving cart wheel broken, blocking corridor.",
        ],
        "hinglish": [
            "{unit} ka diet tray bahut late aaya aur thanda tha, family upset.",
        ],
    },

    "Cleanliness — Critical Area": {
        "en": [
            "ICU floor in {unit} not mopped since night shift — infection control risk.",
            "OT-2 disinfectant residue visible on floor after procedure, needs re-clean.",
            "NICU corridor near {unit} has visible smudges and footmarks.",
        ],
    },

    "Cleanliness — General": {
        "en": [
            "Waiting area near {unit} needs urgent cleaning, food wrappers and tissues.",
            "Patient bathroom on 2F not cleaned since morning shift.",
        ],
        "hi": [
            "{unit} के पास का बाथरूम साफ नहीं है, मरीज़ के परिजन शिकायत कर रहे हैं।",
        ],
        "hinglish": [
            "{unit} ka bathroom subah se clean nahi hua, family complaint kar rahi.",
        ],
    },


    "Lift Down": {
        "en": [
            "Stretcher lift in B-wing stuck between floors, urgent — patient transfer affected.",
            "Visitor lift in A-wing displaying error code 'E-04', not functioning.",
        ],
    },

    "Biomedical Waste": {
        "en": [
            "Biomedical waste bin overflowing at {unit} ward, yellow bag pickup overdue.",
            "Sharps disposal box at OT-3 full and not replaced.",
        ],
    },

    "IT / Patient Records System": {
        "en": [
            "EMR system slow / freezing at {unit} workstation since morning.",
            "Printer at nursing station 3F not printing discharge summaries.",
            "Network slow at pharmacy terminals, billing affected.",
        ],
    },

    "HVAC — Critical Area": {
        "en": [
            "ICU room temperature reading 26°C, should be 22°C — HVAC issue suspected.",
            "OT-1 humidity above acceptable range, needs immediate attention.",
            "NICU temperature dropped 3°C overnight, isolettes compensating.",
        ],
    },

    "Wheelchair / Stretcher": {
        "en": [
            "Wheelchair wheel jammed at A-wing trolley bay, can't be used.",
            "Stretcher wheel-lock broken, slides when applied.",
        ],
    },

    "Other": {
        "en": [
            "Issue at {unit} — {detail} — please assign appropriately.",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────
# Event-company-specific (Stellar) — vertical=102
# ─────────────────────────────────────────────────────────────────────────

STELLAR = {

    "AV / Sound": {
        "en": [
            "Mic feedback issue during sound check for {unit}, screeching every few minutes.",
            "Wireless mic battery died during ceremony at {unit}, no spare on stage.",
            "PA system dropped out twice during speech at {unit}, audience could not hear.",
            "Subwoofer at {unit} stage producing distorted bass, vendor needs to check.",
        ],
        "hinglish": [
            "{unit} mein mic ki feedback aa rahi continuously, sound team ko call karo urgent.",
        ],
    },

    "Lighting": {
        "en": [
            "Stage spotlights at {unit} not aligned, presenter face in shadow.",
            "Decorative fairy lights at entrance of {unit} half not working.",
            "Par-can light malfunction during ceremony, flickering ON-OFF.",
        ],
    },

    "Stage Setup": {
        "en": [
            "Stage backdrop at {unit} not yet mounted, ceremony in 2 hours.",
            "Stage railing loose at {unit}, safety risk for guests.",
            "Stage steps installed unevenly, brides's family flagged tripping hazard.",
        ],
        "hinglish": [
            "{unit} mein stage backdrop abhi tak nahi laga, ceremony 2 hours mein hai.",
        ],
    },

    "Catering — Food Quality": {
        "en": [
            "Hot starter served cold at {unit}, multiple guest complaints.",
            "Vegetarian guest received non-veg item at {unit} — major service failure.",
            "Dessert ice cream melted before service at {unit}, vendor's chiller failed.",
        ],
        "hinglish": [
            "{unit} mein khaana thanda aa raha guests ko, complaint aa rahi multiple times.",
        ],
    },

    "Catering — Service Delay": {
        "en": [
            "Lunch service at {unit} 90 minutes late, guests visibly frustrated.",
            "Beverages running out at {unit} bar, supply not replenished.",
        ],
    },

    "Decor": {
        "en": [
            "Floral centrepieces at {unit} wilting, vendor used poor-quality flowers.",
            "Drape behind stage at {unit} sagging visibly, looks unprofessional.",
            "Wrong colour scheme for tablecloths at {unit} vs client brief — yellow not gold.",
        ],
        "hinglish": [
            "{unit} ke decor mein flowers murjha gaye, vendor ne fresh nahi diye.",
        ],
    },


    "Photography / Videography": {
        "en": [
            "Photographer late for groom-side shoot at {unit}, family unhappy.",
            "Drone shoot at {unit} cancelled — venue does not permit, vendor should have checked.",
        ],
    },

    "Security": {
        "en": [
            "Bouncer count at {unit} entrance only 2, brief was for 4. Crowd getting unmanageable.",
            "Uninvited guest tried entering {unit} reception, security stopped but follow-up needed.",
        ],
    },

    "Transport / Logistics": {
        "en": [
            "Bride's family transport bus 45 minutes late to {unit}.",
            "Equipment van for {unit} stuck in traffic, AV setup delayed.",
        ],
    },

    "Vendor No-Show": {
        "en": [
            "Florist for {unit} not arrived, ceremony at 5pm, no contact from vendor.",
            "Catering team for {unit} 2 hours late, food setup not started.",
        ],
    },

    "Equipment Broken": {
        "en": [
            "Generator at {unit} venue tripping every 15 mins, backup also failing.",
            "Lectern microphone stand wobbly at {unit}, can't be used reliably.",
        ],
    },

    "Power / Generator": {
        "en": [
            "Diesel generator at {unit} ran out of fuel mid-event, lights and sound went down.",
            "Backup generator at {unit} not starting on test, only primary running.",
        ],
    },

    "Crew Shortage / No-Show": {
        "en": [
            "Two runners for {unit} did not report, AV setup short-handed.",
            "Hostess team for {unit} short by 3 people, registration line backed up.",
        ],
        "hinglish": [
            "{unit} ke 2 runner aaye hi nahi, AV setup mein bahut dikkat ho rahi.",
        ],
    },

    "Schedule Slip": {
        "en": [
            "Wedding ceremony at {unit} delayed by 90 mins, vendors waiting paid time.",
            "Speaker session at {unit} overran by 30 mins, next slot affected.",
        ],
    },

    "Permit / Authority Issue": {
        "en": [
            "Noise complaint at {unit} from neighbouring society, police visited.",
            "Pyro permit for {unit} not received in time, ceremony plan affected.",
        ],
    },

    "Client Complaint": {
        "en": [
            "Client family at {unit} unhappy with stage backdrop, demanding rework.",
            "Bride at {unit} extremely upset with floral choice, escalation expected.",
        ],
    },

    "Safety Incident": {
        "en": [
            "Guest slipped on wet floor near {unit} bar area, minor injury, first aid given.",
            "Small fire from candle decor at {unit}, extinguished immediately by AV crew.",
        ],
    },

    "Pyrotechnics / SFX": {
        "en": [
            "Pyro at {unit} entrance misfired, sparkler veered toward guests — paused remainder.",
            "Cold-spark device at {unit} stage not igniting during cue.",
        ],
    },

    "Backstage / Green Room": {
        "en": [
            "Green room at {unit} has no AC, performers complaining of heat.",
            "Bridal-suite mirror at {unit} broken on arrival, bride unable to use.",
        ],
    },

    "Hostess / Usher": {
        "en": [
            "Hostess at {unit} entry-desk arguing with guest, escalation by client.",
        ],
    },

    "Other": {
        "en": [
            "Issue at {unit} — {detail} — please look into.",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────
# Office-estate-specific (Meridian) — vertical=103
# ─────────────────────────────────────────────────────────────────────────

MERIDIAN = {

    "HVAC": {
        "en": [
            "HVAC in {unit} not cooling, office staff complaining of stuffiness.",
            "Conference-room AC in {unit} dripping, water on the carpet.",
            "Cold-spot in {unit} near the window, employees moved desks away.",
        ],
        "hinglish": [
            "{unit} ka AC theek nahi kar raha, office mein bahut garmi.",
        ],
    },

    "IT / Network": {
        "en": [
            "Wifi extremely slow in {unit} since morning, work affected.",
            "Network outage in {unit} since 11am, helpdesk ticket not yet acknowledged.",
            "Wifi signal completely dead in {unit} corner office, can't connect.",
        ],
        "hinglish": [
            "{unit} mein internet bahut slow hai, kaam nahi ho pa raha.",
        ],
    },

    "Lift": {
        "en": [
            "B1-Lift-1 stuck between floors 4-5, alarm pressed by occupant.",
            "B2-Lift-2 closing prematurely, almost trapped a hand.",
        ],
        "hinglish": [
            "B1 ka lift floor 4-5 ke beech stuck hai, alarm baj raha, andar log hain.",
        ],
    },

    "Security": {
        "en": [
            "Stranger in {unit} corridor, no visitor pass, security unaware.",
            "Main lobby security guard absent at his post.",
            "After-hours card access denied for legitimate employee of {unit}.",
        ],
    },

    "Washroom": {
        "en": [
            "Men's washroom on B1-F3 has no soap, paper towels also out.",
            "Women's washroom on B2-F7 — tap not closing, water wastage.",
            "Washroom on B1-F5 not cleaned since morning, smells strongly.",
        ],
        "hinglish": [
            "B1-F3 ke washroom mein soap nahi hai, paper towel bhi khatam.",
        ],
    },

    "Pantry / Cafeteria": {
        "en": [
            "Coffee machine in pantry at {unit} broken, queue forming.",
            "Refrigerator in B1 cafeteria not cooling, food spoilage risk.",
        ],
    },

    "Cleanliness — Common Area": {
        "en": [
            "B1 lobby floor very dirty today, looks like spill not cleaned.",
            "B2 staircase between F5-F6 not cleaned since yesterday.",
        ],
    },

    "Cleanliness — Suite": {
        "en": [
            "Cleaning of {unit} skipped today, dustbins overflowing.",
            "Carpet stain in {unit} from yesterday's spill not addressed.",
        ],
    },

    "Meeting Room Booking": {
        "en": [
            "{unit} double-booked conference room with another suite — clash at 3pm.",
            "Booking system not allowing my suite {unit} to book conference room B1-F4.",
        ],
    },

    "Parking": {
        "en": [
            "Visitor parked in slot allotted to {unit}, owner unreachable.",
            "Vehicle blocking exit ramp at B2 basement.",
            "EV charging port at EV-003 not energizing my car.",
        ],
    },

    "Power Outage": {
        "en": [
            "Power outage in {unit} 30 mins, generator did not auto-start.",
            "B2 tower partial outage — F7 to F10 affected, work disrupted.",
        ],
    },

    "Plumbing": {
        "en": [
            "Washroom on B1-F5 tap leaking, water on floor.",
            "Pantry sink in {unit} blocked, water not draining.",
        ],
    },

    "Electrical — Suite": {
        "en": [
            "Multiple power sockets dead in {unit}, only half the suite working.",
            "Conference-room projector tripping breaker when switched on, {unit}.",
        ],
    },

    "Card Access / Door": {
        "en": [
            "Card access at {unit} entrance not recognising my employee card.",
            "Main lobby turnstile B1 jammed in closed position.",
        ],
    },

    "Cafeteria Food Quality": {
        "en": [
            "B1 cafeteria served stale rice today, multiple employees noticed.",
            "Cafeteria vegetarian counter ran out by 1pm, tenant employees stuck.",
        ],
    },

    "Conference Room AV": {
        "en": [
            "Projector in {unit}'s conference room not connecting to laptops over HDMI.",
            "Video-conference camera in {unit} board room mis-aligned, shows ceiling.",
        ],
    },

    "Reception / Visitor Mgmt": {
        "en": [
            "Reception desk unattended at lunch, visitors waiting unregistered.",
            "Visitor card printer at reception out of toner.",
        ],
    },

    "Building Maintenance": {
        "en": [
            "Cracked window at {unit} corner — safety risk during rain.",
            "Lobby ceiling tile fell down in {unit} corridor.",
        ],
    },

    "Fire Safety": {
        "en": [
            "Fire alarm in B2-F8 sounded for 5 mins, no apparent cause — false alarm?",
            "Fire extinguisher near {unit} appears below required pressure.",
        ],
    },

    "Pest Control": {
        "en": [
            "Rat seen in pantry on B1-F4, multiple employees confirmed.",
            "Cockroaches in {unit}'s washroom, pest control needed urgently.",
        ],
    },

    "Other": {
        "en": [
            "{detail} at {unit} — flagging for facility manager.",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────
# Photo-only / voice-note / Telugu samples
# ─────────────────────────────────────────────────────────────────────────

PHOTO_ONLY_TEMPLATES = [
    "[Photo attached: overflowing dustbin near {unit}]",
    "[Photo attached: water leaking from ceiling in {unit}]",
    "[Photo attached: broken tile in {unit}'s bathroom]",
    "[Photo attached: cracked wall in {unit}'s living room]",
    "[Photo attached: cobwebs in staircase near {unit}]",
    "[Photo attached: vehicle blocking exit, plate visible]",
]

VOICE_NOTE_TRANSCRIPT_TEMPLATES = [
    "[Voice note 28s, Hindi transcript]: \"{unit} mein lift kharab hai bhai, 2nd floor pe stuck ho gaya. Andar bachcha hai mere padosi ka, bahot ghabra raha. Jaldi bhejo electrician.\"",
    "[Voice note 22s, Marathi transcript]: \"{unit} chya bathroom madhe paani galta aahe, kalpa pasun. Pani jat naahi, badbu yete aahe. Plumber pathva.\"",
    "[Voice note 35s, English transcript]: \"Hello, this is from {unit}, our AC has been making a really weird noise since last night, like a grinding sound, and now it's not cooling either. We have an elderly person here, can someone please come urgently.\"",
    "[Voice note 41s, Hindi transcript]: \"{unit} mein kal raat se paani nahi aa raha. Subah humne main tank check karwaya, dikkat society side se hai. Plumber bhejo aur tank check karwao.\"",
    "[Voice note 19s, Hinglish transcript]: \"Bhai {unit} mein generator ki noise aa rahi continuously, neend nahi aa rahi. Servicing kab hogi? Already 2 baar bola hai.\"",
]

# Categories where a voice-note delivery channel actually makes sense.
# A nurse-call system complaint is not the kind of thing a ward admin
# voice-notes — it goes through structured intake. Same for pharmacy
# stock-outs and equipment calibration. Voice notes belong to the
# resident-facing "I can see and describe the problem" complaint types.
CATEGORIES_SUPPORTING_VOICE = frozenset({
    "Plumbing", "Plumbing — General", "Electrical", "Electrical — General",
    "Electrical — Suite", "AC/Cooling", "Water Supply", "Sewage/Drainage",
    "Lighting", "Housekeeping", "Garbage/Waste", "Pest Control",
    "Carpentry", "Painting", "Civil/Structural", "CCTV/Intercom",
    "Elevator", "Lift", "Lift Down",
    "Security", "Noise/Visitor",
    "Patient Room AC", "Bed/Mattress Issue", "HVAC", "HVAC — Ward",
    "Cleanliness — General",
    "AV / Sound", "Lighting", "Power / Generator", "Stage Setup",
    "IT / Network", "Washroom", "Pantry / Cafeteria",
    "Cafeteria Food Quality", "Generator/Power Backup", "Power Outage",
})

# Photos are universal — most categories can carry a photo. The exclusion
# list is short: process-y categories that aren't visual.
CATEGORIES_NOT_SUPPORTING_PHOTO = frozenset({
    "Pharmacy Stock-Out", "Equipment Calibration", "IT / Patient Records System",
    "Meeting Room Booking", "Permit / Authority Issue", "Schedule Slip",
    "Crew Shortage / No-Show", "Vendor No-Show", "Card Access / Door",
})

TELUGU_SAMPLES = {
    "Water Supply": [
        "{unit} లో నీళ్లు రావడం లేదు ఉదయం నుండి. తొందరగా చూడండి.",
    ],
    "Electrical": [
        "{unit} లో కరెంట్ పోయింది, MCB ట్రిప్ అవుతోంది. వెంటనే పంపండి.",
    ],
    "Patient Room AC": [
        "{unit} లో AC పనిచేయడం లేదు, పేషెంట్‌కి ఇబ్బందిగా ఉంది.",
    ],
}


# ─────────────────────────────────────────────────────────────────────────
# Picker
# ─────────────────────────────────────────────────────────────────────────

VERTICAL_OVERRIDES = {
    "hospital_facility": SUNRISE,
    "event_company": STELLAR,
    "office_estate": MERIDIAN,
}


def pick_template(
    rng: random.Random,
    vertical: str,
    category: str,
    language: str = "en",
) -> tuple[str | None, str]:
    """Return (template, actual_language_used).

    Resolution order: vertical-specific → common → None.
    Falls back to English if the requested language isn't available;
    actual_language_used reflects what was actually picked. Returns
    (None, requested_language) if no template exists at all."""
    pools = []
    if vertical in VERTICAL_OVERRIDES:
        v_cat = VERTICAL_OVERRIDES[vertical].get(category)
        if v_cat:
            pools.append(v_cat)
    c_cat = COMMON.get(category)
    if c_cat:
        pools.append(c_cat)
    for pool in pools:
        if language in pool and pool[language]:
            return rng.choice(pool[language]), language
    # Fallback: try English in any pool
    for pool in pools:
        if "en" in pool and pool["en"]:
            return rng.choice(pool["en"]), "en"
    return None, language


def category_supports_voice(category: str) -> bool:
    return category in CATEGORIES_SUPPORTING_VOICE


def category_supports_photo(category: str) -> bool:
    return category not in CATEGORIES_NOT_SUPPORTING_PHOTO


def pick_photo_only(rng: random.Random) -> str:
    return rng.choice(PHOTO_ONLY_TEMPLATES)


def pick_voice_note(rng: random.Random) -> str:
    return rng.choice(VOICE_NOTE_TRANSCRIPT_TEMPLATES)


def pick_telugu(rng: random.Random, category: str) -> str | None:
    pool = TELUGU_SAMPLES.get(category)
    if not pool:
        return None
    return rng.choice(pool)


def bank_stats() -> dict[str, int]:
    """Audit visibility."""
    n_common = sum(
        len(lang_pool)
        for cat in COMMON.values()
        for lang_pool in cat.values()
    )
    n_vert = sum(
        len(lang_pool)
        for vmap in VERTICAL_OVERRIDES.values()
        for cat in vmap.values()
        for lang_pool in cat.values()
    )
    return {
        "common_templates": n_common,
        "vertical_templates": n_vert,
        "photo_only": len(PHOTO_ONLY_TEMPLATES),
        "voice_note": len(VOICE_NOTE_TRANSCRIPT_TEMPLATES),
        "telugu_samples": sum(len(v) for v in TELUGU_SAMPLES.values()),
    }
