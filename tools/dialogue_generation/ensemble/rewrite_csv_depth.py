"""One-shot depth pass over the 88-character CSV.

This is authoring code, not a runtime generator. It rewrites templated
psychology, relationship history and quest material using each character's
unique secret, occupation, place and named ties. Run from the repo root:

    PYTHONPATH=tools python -m dialogue_generation.ensemble.rewrite_csv_depth
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV = ROOT / "docs/characters/DMB_Character_Profiles_88_Disco_Elysium_Depth.csv"

# Balanced so >=30 distinct targets and no indegree > 4.
RESPONSIBILITY = {
    "NPC_001": "NPC_006", "NPC_002": "NPC_007", "NPC_003": "NPC_004", "NPC_004": "NPC_008",
    "NPC_005": "NPC_006", "NPC_006": "NPC_007", "NPC_007": "NPC_005", "NPC_008": "NPC_003",
    "NPC_009": "NPC_013", "NPC_010": "NPC_015", "NPC_011": "NPC_012", "NPC_012": "NPC_013",
    "NPC_013": "NPC_016", "NPC_014": "NPC_015", "NPC_015": "NPC_011", "NPC_016": "NPC_014",
    "NPC_017": "NPC_021", "NPC_018": "NPC_024", "NPC_019": "NPC_023", "NPC_020": "NPC_021",
    "NPC_021": "NPC_024", "NPC_022": "NPC_023", "NPC_023": "NPC_018", "NPC_024": "NPC_020",
    "NPC_025": "NPC_028", "NPC_026": "NPC_031", "NPC_027": "NPC_028", "NPC_028": "NPC_031",
    "NPC_029": "NPC_030", "NPC_030": "NPC_032", "NPC_031": "NPC_026", "NPC_032": "NPC_029",
    "NPC_033": "NPC_039", "NPC_034": "NPC_038", "NPC_035": "NPC_039", "NPC_036": "NPC_037",
    "NPC_037": "NPC_040", "NPC_038": "NPC_035", "NPC_039": "NPC_034", "NPC_040": "NPC_033",
    "NPC_041": "NPC_042", "NPC_042": "NPC_047", "NPC_043": "NPC_044", "NPC_044": "NPC_047",
    "NPC_045": "NPC_042", "NPC_046": "NPC_048", "NPC_047": "NPC_043", "NPC_048": "NPC_041",
    "NPC_049": "NPC_055", "NPC_050": "NPC_054", "NPC_051": "NPC_055", "NPC_052": "NPC_054",
    "NPC_053": "NPC_050", "NPC_054": "NPC_049", "NPC_055": "NPC_051", "NPC_056": "NPC_053",
    "NPC_057": "NPC_060", "NPC_058": "NPC_062", "NPC_059": "NPC_063", "NPC_060": "NPC_064",
    "NPC_061": "NPC_060", "NPC_062": "NPC_057", "NPC_063": "NPC_061", "NPC_064": "NPC_059",
    "NPC_065": "NPC_072", "NPC_066": "NPC_068", "NPC_067": "NPC_068", "NPC_068": "NPC_071",
    "NPC_069": "NPC_072", "NPC_070": "NPC_071", "NPC_071": "NPC_066", "NPC_072": "NPC_070",
    "NPC_073": "NPC_075", "NPC_074": "NPC_076", "NPC_075": "NPC_079", "NPC_076": "NPC_078",
    "NPC_077": "NPC_079", "NPC_078": "NPC_080", "NPC_079": "NPC_073", "NPC_080": "NPC_075",
    "NPC_081": "NPC_086", "NPC_082": "NPC_087", "NPC_083": "NPC_087", "NPC_084": "NPC_088",
    "NPC_085": "NPC_087", "NPC_086": "NPC_082", "NPC_087": "NPC_088", "NPC_088": "NPC_083",
}

# Same-district "cross_district" links retargeted to a real other district.
CROSS_DISTRICT_OVERRIDE = {
    "NPC_013": ("Hew Marr", "trade", "Odo needs Hew's barley before the cistern water turns the mash and Alis notices the beer thinning."),
    "NPC_028": ("Pate Wren", "apprenticeship", "Cadrin still owes Pate a winter of joint framing after claiming carpenter hours on a clay-and-timber cottage they finished together."),
    "NPC_043": ("Della Marr", "trade", "Ora weaves the flour-sacks Della stamps; a missed dye lot would leave the baker short at the same moment the mill over-claims grain."),
    "NPC_058": ("Sister Eline", "worship", "Tebb rations shrine wash-water from the cistern; Eline's rites fail if he keeps the contamination scare to himself."),
    "NPC_072": ("Haro Keld", "family", "Ria is paid to mourn in Haro's kitchen on the nights he still sets a place for the dead spouse, and she knows which nights he cannot bear witnesses."),
    "NPC_073": ("Joryn Pike", "debt", "Etta's household credit is on Joryn's slate; he can starve the house without ever raising his voice in the lane."),
    "NPC_086": ("Siva Noll", "old crime", "Tali buys objects Siva pulls from the wastes; one relic they moved together is the disappearance Siva will not surrender."),
    "NPC_087": ("Old Mere", "past employment", "Nox walked the bone-piles with Mere before claiming to be new in the village, and Mere can prove the dates if anyone asks."),
}

ROLE_MATERIAL = {
    "Reeve": ("parish ruling", "grazing mark", "a grazing ruling that put a household on parish grain", "annotated parish ledger"),
    "Elder": ("custom-book", "family precedent", "protecting a respected family from a public consequence", "remembered oath"),
    "Watchkeeper": ("gate log", "night alarm", "waiting for a second confirmation while a cart went through unchallenged", "who-passed-where slate"),
    "Messenger": ("sealed pouch", "relay route", "opening other people's sentences before they arrived", "doorstep pause"),
    "Assessor": ("tax roll", "older script", "years of hiding that one older script is unreadable", "red-ink correction"),
    "Petitioner": ("grievance slip", "council step", "a grazing right written off the parish book", "older mark kept in a coat"),
    "Bell Keeper": ("warning bell", "hour-rope", "a panic peal that preceded a death", "tower stair"),
    "Clerk": ("copied minute", "altered seal", "keeping private transcripts because official copies get changed", "document chest"),
    "Storekeeper": ("credit slate", "back-room measure", "kindness disguised as price so the family would not look soft", "family store key"),
    "Innkeeper": ("common-room ear", "private booth", "knowing secret meetings and being treated as furniture", "spare key"),
    "Trader": ("shortage ledger", "road weight", "profiting from a shortage then giving stock away as penance", "warehouse tally"),
    "Baker": ("dawn oven", "sibling debt", "quietly paying a sibling's debts while refusing the reputation of being soft", "flour sack stamp"),
    "Brewer": ("mash tun", "failing spring", "a water source failing under the inn", "barrel mark"),
    "Provisioner": ("winter stock", "shortage list", "being valued only when a shortage needs solving", "useful crate"),
    "Peddler": ("pack of stories", "road trinket", "no longer knowing which stories actually happened to him", "half-true route"),
    "Dice Maker": ("loaded pip", "bone cube", "loaded dice made for someone powerful and later used to ruin a family", "workshop vice"),
    "Woodcutter": ("protected stump", "famine cut", "crew mark", "coppice bound"),
    "Sawmiller": ("worn axle", "mill-debt household", "blade scream", "stoppage that starves wages"),
    "Charcoal Burner": ("coppice grave", "clamp fire", "old bone under roots", "smoke that hides a name"),
    "Furnisher": ("copied chair-back", "wealthy pattern", "mocking sketch", "commission she wanted"),
    "Carpenter": ("weak roof-beam", "signed off joint", "brace he never admitted", "ladder to someone else's eaves"),
    "Resin Gatherer": ("youth's observation", "tap-scar", "withheld drip-count", "adults who will not listen"),
    "Clay Worker": ("rich seam", "disliked family's claim", "wet pit", "brick that remembers a border"),
    "Mason": ("shaking chisel", "fine joint", "stone that will not forgive tremor", "scaffold pride"),
    "Builder": ("charged timber", "poor-house brace", "scaffold knot", "work billed to the wrong door"),
    "Potter / Lime Burner": ("bad lime", "hidden repaired wall", "kiln crack", "glaze that hides a fault"),
    "Smelter": ("replaceable labour", "apprentice who will surpass him", "crucible heat", "ore he treats as people"),
    "Lime Carrier": ("aunt's roof", "leaving pack", "burned wrist", "load she will not carry home"),
    "Surveyor": ("boundary stone", "tax map", "contradicting mark", "chain that shortens a field"),
    "Farmer": ("thinning soil", "promised field", "yield pushed too hard", "second child's claim"),
    "Miller": ("false weight", "hungry household extra", "toll dish", "flour that was never owed"),
    "Food Preserver": ("hidden reserve", "salt-house barrel", "famine nobody else believes", "lid she will not lift in public"),
    "Distiller": ("accidental genius", "still-worm", "intuition that was luck", "cask he will not let others taste"),
    "Field Hand": ("anonymous complaint", "other people's letters", "hire-row", "ink she pretends not to own"),
    "Seed Keeper": ("lost heritage line", "disease lie", "jar with a false label", "hand that slipped once"),
    "Shepherd": ("dangerous ram", "dead friend's animal", "assumed simplicity", "hill-count at dusk"),
    "Weaver": ("coded ceremonial cloth", "scandal pattern", "loom that records names", "thread only she can read"),
    "Fuller / Dyer": ("banned mordant", "illegal blue", "vat she will not name", "cloth that should not be that colour"),
    "Tanner": ("compensation coin", "stink-neighbour", "pit lime", "quiet payment after dark"),
    "Armourer": ("craft that wants a throne", "fitting beyond her writ", "mail she treats as law", "hammer that ends arguments"),
    "Spinner": ("overheard secret", "exact adult sentence", "child's wheel", "thread she can repeat forever"),
    "Cloth Merchant": ("heirloom sold as import", "declining trade", "false origin stamp", "chest of family stock"),
    "Miner": ("unsafe gallery", "proof kept private", "debt to the dead", "prop that will not hold"),
    "Blacksmith": ("famous blade she cannot remake", "anvil lie", "quench she no longer trusts", "name stamped on other steel"),
    "Metalworker": ("stolen travelling technique", "fear of recognition", "file pattern", "visitor who would know"),
    "Refiner": ("poisoned ditch", "slag heap", "cost of admission", "runoff she can taste"),
    "Ore Assayer": ("nonsense pattern that came true", "sample tray", "vision she should not trust", "mark in the stone"),
    "Forge Apprentice": ("anonymous repair", "journeyman proof", "tool left perfect at dawn", "work she cannot sign"),
    "Mine Overseer": ("order after the warning", "identity of never-wrong", "continued shift", "name on a dead list"),
    "Scavenger": ("object from a disappearance", "unsurrendered find", "waste-pit claim", "thing that should have been reported"),
    "Cistern Keeper": ("unauthorised ration", "coming contamination", "measure-stick", "water he will not release"),
    "Reclamation Worker": ("respectable dumping", "condemned object", "who throws what", "pit that knows the better houses"),
    "Rag Picker": ("letter of private kindness", "refused weapon", "bundle of names", "proof she will not sell"),
    "Watchpost Keeper": ("disbelieved threat", "overcalled sign", "empty horizon", "report nobody filed"),
    "Bone Collector": ("identified old remains", "refused explanation", "how she knows the bones", "name in the marrow"),
    "Night Soil Carter": ("everyone's private routine", "work treated as dirt", "lane at first light", "who is never home when they claim"),
    "Boundary Forager": ("forbidden plant", "relative's pain", "edge-path", "leaf that is not legal"),
    "Shrine Keeper": ("doubted doctrine", "needed ritual", "envy of easy doubt", "incense that still has to burn"),
    "Healer": ("scarce medicine choice", "unforgiven patient", "who received the last dose", "bed she still walks past"),
    "Healer's Assistant": ("unauthorised treatment", "alone with a patient", "skill beyond the licence", "door shut on the healer"),
    "Midwife": ("family-transforming confidence", "birth-house silence", "name she will not give", "oath stronger than kinship"),
    "Grave Tender": ("empty grave", "afraid to open it", "false earth", "stone that should be heavier"),
    "Herbalist": ("ritual remedy sold as medicine", "insistence of the sick", "jar of almost-nothing", "leaf that comforts and does not cure"),
    "Mourner-for-Hire": ("counterfeit grief", "perfect performance", "hired tears", "feeling she cannot find at home"),
    "Householder": ("hidden insolvency", "obedience mistaken for love", "kitchen ledger", "door she keeps closed on the figures"),
    "Apprentice": ("terror of being ordinary", "exaggerated talent", "task too loudly claimed", "master's tool used too soon"),
    "Child": ("after-dark visitor game", "tracked doors", "game that is evidence", "window that sees the lane"),
    "Retired Soldier": ("omitted order", "heroic version of a battle", "regretted obedience", "story that leaves a name out"),
    "Caretaker": ("resentment of the cared-for", "exhaustion", "night-watch chair", "love that has turned to duty"),
    "Widower": ("place set for the dead", "unwatched table", "second bowl", "name said only to the empty stool"),
    "Boarder": ("changed surname", "debt that was not hers", "rented room", "old name under the new one"),
    "Travelling Scholar": ("disastrous last expedition", "concealed anomaly", "notebook of failure", "question he came to ask anyway"),
    "Map Seller": ("deliberate omissions", "complete map as leverage", "blank that is the real goods", "road that is not drawn"),
    "Pilgrim": ("arrival as failure", "revelation deferred", "road that must not end", "shrine she will not enter"),
    "Entertainer": ("recognised scandal face", "unsung identification", "song that is a warning", "person from elsewhere"),
    "Retired Wizard": ("lost control of a spell", "doctrine against chance", "forty-year denial", "working that must never be luck"),
    "Relic Broker": ("fake relic", "staked reputation", "object she cannot un-sell", "provenance that will not hold"),
    "Unknown Drifter": ("prior knowledge of the village", "arrival that is a return", "name she will not use", "lane she already knows"),
    "Natural Philosopher": ("theory that needs the ecosystem", "ignored inconvenient evidence", "sample that should not fit", "proof he will not collect"),
}

CONTACT_REASONS = (
    "trade", "family", "past employment", "debt", "worship", "apprenticeship",
    "shared military service", "disputed land", "medical care", "secret affair",
    "political obligation", "transport route", "shared hobby", "old crime", "mutual friend",
)


CONCRETE_SECRETS = {
    "NPC_001": "she ruled against Selka Mora's household on a grazing mark that followed precedent and left Selka's mother dependent on parish grain",
    "NPC_003": "on the night the south gate alarm was real he waited for a second confirmation and a cart went through unchallenged",
    "NPC_004": "she has opened and resealed three pouches this year to know what she was carrying, and has not told the senders",
    "NPC_006": "her mother's grazing rights were written off the parish book and she still carries the older mark in her coat",
    "NPC_014": "she held back a winter crate from the official list so that her usefulness could be demonstrated on demand",
    "NPC_024": "she has begun withholding drip-counts from the adults who treat youth as ignorance",
    "NPC_030": "he has started pricing ordinary craftspeople as replaceable while knowing his best apprentice will surpass him",
    "NPC_041": "she keeps biting remarks behind her teeth whenever someone explains her own hills back to her as if she were simple",
    "NPC_046": "she used an armour fitting as an excuse to overrule a watch decision she had no writ to touch",
    "NPC_066": "he has been repeating a doctrine he no longer believes because doubt makes him physically sick",
    "NPC_074": "he has been rewarding obedience in the household as if it were affection, and only now sees the difference",
    "NPC_075": "he signed his name to a repair he had not yet been taught so that nobody would call him ordinary",
    "NPC_083": "she has walked past every shrine that would have ended the pilgrimage because arriving would prove there was no further revelation",
}


def _pronouns(row: dict[str, str]) -> tuple[str, str, str]:
    first = (row.get("Pronouns") or "they/them").split("/")[0].strip().lower()
    return {
        "he": ("he", "him", "his"),
        "she": ("she", "her", "her"),
        "they": ("they", "them", "their"),
    }.get(first, ("they", "them", "their"))


def _pick(key: str, *options: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).digest()[0]
    return options[digest % len(options)]


def _role_bits(row: dict[str, str]) -> tuple[str, str, str, str]:
    role = row["Village_Role"]
    return ROLE_MATERIAL.get(role, (role.lower(), row["Home_or_Base"].lower(), "work", "standing"))


def _secret(row: dict[str, str]) -> str:
    override = CONCRETE_SECRETS.get(row["Character_ID"])
    text = (override or row["Secret"]).rstrip(".")
    lowered = text.lower()
    if not override and text[:1].islower() and not lowered.startswith(("the ", "a ", "an ")):
        text = f"{row['Display_Name']} {text}"
        lowered = text.lower()
    if lowered.startswith(("the fact that ", "a ", "an ")):
        return text
    return f"the fact that {text}"


def _by_name(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["Display_Name"]: row for row in rows}


def _by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["Character_ID"]: row for row in rows}


def rewrite_row(row: dict[str, str], rows: list[dict[str, str]]) -> dict[str, str]:
    out = dict(row)
    names = _by_name(rows)
    ids = _by_id(rows)
    they, them, their = _pronouns(row)
    name = row["Display_Name"]
    role = row["Village_Role"]
    district = row["District"]
    home = row["Home_or_Base"]
    secret = _secret(row)
    shame = row["Shame_or_Vulnerability"].rstrip(".")
    wound = row.get("Formative_Wound", "").rstrip(".")
    noun, tool, fault, token = _role_bits(row)
    ally = names[row["Key_Ally"]]
    rival = names[row["Key_Rival"]]
    cid = row["Character_ID"]

    resp_id = RESPONSIBILITY[cid]
    dependent = ids[resp_id]
    out["Dependent_or_Responsibility"] = dependent["Display_Name"]

    if cid in CROSS_DISTRICT_OVERRIDE:
        target_name, reason, history = CROSS_DISTRICT_OVERRIDE[cid]
        out["Cross_District_Connection"] = target_name
        out["Cross_District_Reason"] = reason
        xd = names[target_name]
        xd_history = history
    else:
        xd = names[row["Cross_District_Connection"]]
        reason = CONTACT_REASONS[int(cid[-3:]) % len(CONTACT_REASONS)]
        out["Cross_District_Reason"] = reason
        xd_history = _cross_history(row, xd, reason, they, their)

    out["Core_Desire"] = _core_desire(row, noun, tool, they, their)
    out["Immediate_Want"] = _immediate_want(row, ally, rival, tool, they)
    out["Core_Fear"] = _core_fear(row, noun, fault, they, their)
    out["False_Belief"] = _false_belief(row, they, their)
    out["Central_Contradiction"] = _contradiction(row, noun, they, their)
    out["Moral_Boundary"] = _moral_boundary(row, they)
    out["Protective_Lie"] = _protective_lie(row, tool)
    out["Secret"] = _secret(row)
    out["Post_Quest_State"] = _post_quest(row, rival, dependent, they, their)
    out["Shame_or_Vulnerability"] = shame[0].upper() + shame[1:] + "."
    out["Formative_Event"] = _formative_event(row, rival, tool, fault)
    out["Self_Image"] = _self_image(row, noun, they, their)
    out["Private_Need"] = _private_need(row, ally, they, them)
    out["Social_Mask"] = _social_mask(row, role, they)
    out["Specific_Regret"] = _specific_regret(row, they, their)
    out["Specific_Hope"] = _specific_hope(row, dependent, they, their)
    out["Relationship_Wound"] = _relationship_wound(row, rival, they, their)
    out["Pressure_Behaviour"] = _pressure_behaviour(row, tool, they)
    out["Repair_Behaviour"] = _repair_behaviour(row, ally, they)
    out["Misjudges_Others_By"] = _misjudges(row, they, their)
    out["Ally_Relationship"] = _ally_history(row, ally, they, their)
    out["Rival_Relationship"] = _rival_history(row, rival, they, their)
    out["Cross_District_Relationship"] = xd_history
    out["Dependency_Relationship"] = _resp_history(row, dependent, they, their)
    out["Quest_Hook"] = _quest_hook(row, rival, tool, fault)
    out["Quest_Complication"] = _quest_complication(row, ally, rival, xd, they)
    out["Quest_Alternate_Solution"] = _quest_alternate(row, ally, rival, dependent, tool, they, their)
    out["Prized_Object"] = _prized_object(row, tool, token)
    out["Daily_Routine"] = _daily_routine(row, ally, they, their)
    return out


def _core_desire(row: dict[str, str], noun: str, tool: str, they: str, their: str) -> str:
    role, home, secret = row["Village_Role"], row["Home_or_Base"], _secret(row)
    return _pick(
        row["Character_ID"] + "desire",
        f"to keep {home} functioning on {their} terms so that {secret} never becomes the village's explanation of {their} {role.lower()} work",
        f"to make {noun} in {row['District']} answer to {their} judgement rather than to panic, gossip or a louder office",
        f"to secure enough standing as {role} that {they} can protect {tool} without being owned by the people who use it",
        f"to finish one concrete piece of {role.lower()} work at {home} that would let {_pronouns(row)[1]} live with {secret}",
    )


def _immediate_want(row: dict[str, str], ally: dict[str, str], rival: dict[str, str], tool: str, they: str) -> str:
    return _pick(
        row["Character_ID"] + "want",
        f"wants {ally['Display_Name']} to confirm what happened to {tool} before {rival['Display_Name']} turns it into a public accusation",
        f"wants the player to inspect {row['Home_or_Base']} quietly and report only to {they} and {ally['Display_Name']}",
        f"wants {rival['Display_Name']} stopped from touching {tool} until {row['Display_Name']} has a second witness",
        f"wants a written account of {_secret(row)} kept out of {rival['Display_Name']}'s hands for one more work cycle",
    )


def _core_fear(row: dict[str, str], noun: str, fault: str, they: str, their: str) -> str:
    secret = _secret(row)
    home = row["Home_or_Base"]
    role = row["Village_Role"]
    _, them, _ = _pronouns(row)
    return _pick(
        row["Character_ID"] + "fear",
        f"fears that someone will prove {secret}, and that {home} will remember {them} only as the {role.lower()} who let {fault} happen",
        f"fears a public inspection of {noun} that would make {secret} the official story of {their} working life",
        f"fears that {row['Key_Rival']} will be the one to name {fault} in {row['District']} and attach it permanently to {their} {role.lower()} name",
        f"fears waking to find {fault} already visible at {home}, confirming {secret} before {they} can contain it",
    )


def _false_belief(row: dict[str, str], they: str, their: str) -> str:
    secret = _secret(row)
    role = row["Village_Role"]
    return _pick(
        row["Character_ID"] + "belief",
        f"If I keep {secret} inside the {role.lower()} role, the village will treat the harm as weather rather than a choice.",
        f"People will forgive a {role.lower()} who is useful; they will not forgive one who asks them to share {secret}.",
        f"Naming {secret} out loud would make it true in a way that silence still lets {_pronouns(row)[1]} bargain with.",
        f"{their.capitalize()} {role.lower()} procedure is cleaner than anyone else's conscience, so {they} may skip the part that would expose {secret}.",
        f"If {row['Key_Ally']} still works with me, then {secret} cannot be as damning as it feels at {row['Home_or_Base']}.",
        f"A {role.lower()} who controls the timing of the truth controls the size of the damage.",
    )


def _contradiction(row: dict[str, str], noun: str, they: str, their: str) -> str:
    secret = _secret(row)
    role = row["Village_Role"]
    return _pick(
        row["Character_ID"] + "contra",
        f"Insists the village needs an honest {role.lower()} while structuring every day at {row['Home_or_Base']} around not having {secret} examined.",
        f"Uses {noun} to claim independence, then becomes unavailable the moment {secret} would require a witness.",
        f"Demands that {row['Key_Rival']} answer for small faults, then treats {secret} as a private {role.lower()} technicality.",
        f"Performs care for {row['District']} in public and solitude around {secret} so completely that even {row['Key_Ally']} is only trusted with the useful half.",
        f"Wants to be judged on years of {role.lower()} work, but will burn a relationship rather than let {secret} become part of that record.",
        f"Preaches that {noun} must be shared, then keeps the one fact that would let others share the cost of {secret}.",
    )


def _moral_boundary(row: dict[str, str], they: str) -> str:
    noun, tool, fault, token = _role_bits(row)
    return _pick(
        row["Character_ID"] + "moral",
        f"will not falsify {tool} or {token}, even to bury {_secret(row)}",
        f"will not send someone else to take the blame for {fault} at {row['Home_or_Base']}",
        f"will not sell {row['Key_Ally']}'s confidence to win a point against {row['Key_Rival']}",
        f"will not let a child or dependent walk into {fault} to keep {row['Village_Role'].lower()} pride intact",
        f"will not destroy {noun} that other households still need, even to hide {_secret(row)}",
    )


def _protective_lie(row: dict[str, str], tool: str) -> str:
    secret = _secret(row)
    home = row["Home_or_Base"]
    rival = row["Key_Rival"]
    return _pick(
        row["Character_ID"] + "lie",
        f"That is only a {row['Village_Role'].lower()} matter; {tool} at {home} is not your concern.",
        f"I already told the people who needed to know. Nothing further at {home} touches {secret}.",
        f"{rival} is guessing. What happened around {tool} is finished business.",
        f"This is ordinary work in {row['District']}, not a confession about {secret}.",
        f"You would be wasting daylight asking anyone else; the only accurate account of {tool} is mine.",
    )


def _post_quest(row: dict[str, str], rival: dict[str, str], dependent: dict[str, str], they: str, their: str) -> str:
    return _pick(
        row["Character_ID"] + "post",
        f"After resolution, {row['Display_Name']}'s route through {row['District']} changes to include or avoid {rival['Display_Name']}, and {dependent['Display_Name']} is treated as someone whose future was part of the cost.",
        f"If exposed, {they} stops repeating the protective lie about {_secret(row)} but becomes harsher about who may stand at {row['Home_or_Base']}.",
        f"If protected, {they} owes the player a practical favour in {row['Village_Role'].lower()} work and cannot pretend {rival['Display_Name']} was imagining {fault_word(row)}.",
        f"Ambient talk in {row['District']} should mention {their} {row['Village_Role'].lower()} standing relative to {rival['Display_Name']}, not reset to the pre-quest loop.",
    )


def fault_word(row: dict[str, str]) -> str:
    return _role_bits(row)[2]


def _formative_event(row: dict[str, str], rival: dict[str, str], tool: str, fault: str) -> str:
    wound = row.get("Formative_Wound", "").rstrip(".")
    return (
        f"{row['Display_Name']} chose to keep {_secret(row)} rather than put {tool} under "
        f"{rival['Display_Name']}'s inspection the first time {fault} became visible at {row['Home_or_Base']}. {wound}."
    )


def _self_image(row: dict[str, str], noun: str, they: str, their: str) -> str:
    _, them, _ = _pronouns(row)
    reflexive = "themselves" if them == "them" else f"{them}self"
    return (
        f"{they.capitalize()} still pictures {reflexive} as the {row['Village_Role'].lower()} "
        f"{row['District']} cannot spare, the person who understands {noun} better than the people who judge {them}."
    )


def _private_need(row: dict[str, str], ally: dict[str, str], they: str, them: str) -> str:
    return (
        f"Needs one person — ideally {ally['Display_Name']} — to know {_secret(row)} without turning it into a verdict, "
        f"so {they} can keep working at {row['Home_or_Base']} without performing innocence."
    )


def _social_mask(row: dict[str, str], role: str, they: str) -> str:
    return _pick(
        row["Character_ID"] + "mask",
        f"Performs unbothered competence: a {role.lower()} who has already accounted for everything.",
        f"Performs tired practicality, as if {row['Home_or_Base']} were only ever a workplace.",
        f"Performs loyalty to {row['District']} loudly enough that questions about {_secret(row)} feel ungrateful.",
        f"Performs mild contempt for gossip so that nobody notices how carefully {they} tracks it.",
    )


def _specific_regret(row: dict[str, str], they: str, their: str) -> str:
    return f"{they.capitalize()} regrets the moment {they} decided {_secret(row)} was safer than a record at {row['Home_or_Base']} that other people could read."


def _specific_hope(row: dict[str, str], dependent: dict[str, str], they: str, their: str) -> str:
    return (
        f"Hopes {dependent['Display_Name']} will not inherit the same {row['Village_Role'].lower()} corner "
        f"that made {_secret(row)} feel necessary."
    )


def _relationship_wound(row: dict[str, str], rival: dict[str, str], they: str, their: str) -> str:
    return (
        f"{rival['Display_Name']} once came close enough to {fault_word(row)} that {row['Display_Name']} still hears {their} name "
        f"as an inspection. The wound is not dislike; it is the memory of nearly being correctly described."
    )


def _pressure_behaviour(row: dict[str, str], tool: str, they: str) -> str:
    _, them, _ = _pronouns(row)
    return _pick(
        row["Character_ID"] + "pressure",
        f"Talks faster about procedure and puts {tool} between {them} and the question.",
        f"Goes still, then invents an errand that takes {them} back to {row['Home_or_Base']}.",
        f"Becomes suddenly generous with irrelevant {row['Village_Role'].lower()} facts.",
        f"Turns the conversation onto {row['Key_Rival']}'s faults before {_secret(row)} can be named.",
    )


def _repair_behaviour(row: dict[str, str], ally: dict[str, str], they: str) -> str:
    return (
        f"Repairs by doing a piece of {row['Village_Role'].lower()} work {ally['Display_Name']} actually needed, "
        f"then pretending the help was always part of the job."
    )


def _misjudges(row: dict[str, str], they: str, their: str) -> str:
    return _pick(
        row["Character_ID"] + "misjudge",
        f"Assumes anyone who asks about {row['Home_or_Base']} already wants to own {_secret(row)}.",
        f"Reads hesitation in others as the same cowardice {they} practices around {fault_word(row)}.",
        f"Treats practical questions as moral verdicts, because that is how {they} uses {their} own {row['Village_Role'].lower()} questions.",
        f"Cannot believe {row['Key_Ally']} might disagree without becoming {row['Key_Rival']}.",
    )


def _ally_history(row: dict[str, str], ally: dict[str, str], they: str, their: str) -> str:
    a_noun = _role_bits(ally)[0]
    return (
        f"{row['Display_Name']} and {ally['Display_Name']} learned to keep each other standing after a shared scare at "
        f"{row['Home_or_Base']}: {ally['Display_Name']}'s {ally['Village_Role'].lower()} work with {a_noun} covered a gap "
        f"while {row['Display_Name']} contained {_secret(row)}. Publicly they are simply useful to one another in {row['District']}. "
        f"Privately {ally['Display_Name']} has seen the unperformed version of {row['Display_Name']} and has not used it. "
        f"{row['Display_Name']} now wants {ally['Display_Name']}'s witness without {their} judgement; {ally['Display_Name']} wants the same cover if {ally['Secret']} ever surfaces."
    )


def _rival_history(row: dict[str, str], rival: dict[str, str], they: str, their: str) -> str:
    r_fault = _role_bits(rival)[2]
    return (
        f"The break with {rival['Display_Name']} is specific: {rival['Display_Name']} described {fault_word(row)} in {row['District']} "
        f"in a way that would have made {_secret(row)} obvious if anyone had followed the sentence to {row['Home_or_Base']}. "
        f"{row['Display_Name']} answered by finding {r_fault} in {rival['Display_Name']}'s {rival['Village_Role'].lower()} work. "
        f"Each now needs the other to be slightly wrong in public. The player should be able to see the point on which {rival['Display_Name']} is actually right."
    )


def _cross_history(row: dict[str, str], xd: dict[str, str], reason: str, they: str, their: str) -> str:
    return (
        f"{reason.capitalize()} ties {row['Display_Name']} in {row['District']} to {xd['Display_Name']} in {xd['District']}: "
        f"{row['Village_Role'].lower()} work at {row['Home_or_Base']} still depends on {xd['Village_Role'].lower()} work at {xd['Home_or_Base']}. "
        f"They met when {reason} first forced a handoff neither office wanted to write down. "
        f"{row['Display_Name']} still needs {xd['Display_Name']} because {_secret(row)} would travel faster along any official route; "
        f"{xd['Display_Name']} needs the unofficial {reason} to continue because {xd['Secret']} is easier to keep off a second district's books."
    )


def _resp_history(row: dict[str, str], dep: dict[str, str], they: str, their: str) -> str:
    if row["Character_ID"] == "NPC_001" and dep["Character_ID"] == "NPC_006":
        return (
            "Five winters ago Mara ruled against Selka's household in a grazing dispute. The ruling followed precedent but left "
            "Selka's mother dependent on parish grain. Mara has quietly expedited Selka's petitions ever since. Selka interprets "
            "this as patronising guilt; Mara believes she is repaying a debt she cannot acknowledge publicly."
        )
    return (
        f"{row['Display_Name']} took on {dep['Display_Name']} after {fault_word(row)} at {row['Home_or_Base']} made it impossible "
        f"to pretend the cost stayed inside {row['Village_Role'].lower()} work. {dep['Display_Name']} now relies on {row['Display_Name']} "
        f"for access, coin, testimony or a door that will open in {row['District']}. {row['Display_Name']} calls it duty; "
        f"{dep['Display_Name']} can feel the control in it. The relationship can produce care, resentment or sacrifice, but the origin is this unpaid practical debt, not a temperament."
    )


def _quest_hook(row: dict[str, str], rival: dict[str, str], tool: str, fault: str) -> str:
    if row["Character_ID"] == "NPC_035":
        return (
            "Nim has been adjusting mill weights to favour hungry households. Prove which sacks were light, who ate because of it, "
            "and whether the village will call him a thief or a quiet relief officer."
        )
    return _pick(
        row["Character_ID"] + "hook",
        f"Find the physical trace of {fault} at {row['Home_or_Base']} — {tool} will not match the story {row['Display_Name']} is telling — then decide who may know {_secret(row)}.",
        f"Settle the live dispute between {row['Display_Name']} and {rival['Display_Name']} over {tool} without letting {fault} be renamed as a personality clash.",
        f"Recover the object or record that makes {_secret(row)} checkable, then choose whether {row['District']} is safer with it public.",
        f"Follow {row['Village_Role'].lower()} work through one complete cycle at {row['Home_or_Base']} until the missing step is obviously {fault}.",
    )


def _quest_complication(row: dict[str, str], ally: dict[str, str], rival: dict[str, str], xd: dict[str, str], they: str) -> str:
    return (
        f"The fast solution lets {row['Display_Name']} keep {_secret(row)} and pushes the material cost onto {rival['Display_Name']}'s "
        f"{rival['Village_Role'].lower()} work. A fuller solution needs {ally['Display_Name']}'s {ally['Village_Role'].lower()} knowledge "
        f"or {xd['Display_Name']}'s {xd['District']} access, and it will change who still eats, works or sleeps at {row['Home_or_Base']}."
    )


def _quest_alternate(row: dict[str, str], ally: dict[str, str], rival: dict[str, str], dep: dict[str, str], tool: str, they: str, their: str) -> str:
    if row["Character_ID"] == "NPC_035":
        return (
            "Instead of exposing the false weights, the player can prove which households received the extra flour and convince "
            "the farmer, miller and reeve to record the discrepancy as emergency relief. This protects hungry households but "
            "forces Nim to admit he altered the scales."
        )
    return _pick(
        row["Character_ID"] + "alt",
        f"Instead of exposing {_secret(row)}, the player can walk {tool} through {ally['Display_Name']}'s {ally['Village_Role'].lower()} check and have {row['District']} record the discrepancy as a named repair. {dep['Display_Name']} keeps cover; {row['Display_Name']} must admit the {fault_word(row)} to {ally['Display_Name']}; {rival['Display_Name']} loses the scandal but not the grievance.",
        f"Instead of a public confrontation with {rival['Display_Name']}, the player can move the disputed {tool} into {ally['Home_or_Base']} under joint inventory. {dep['Display_Name']} benefits immediately; {row['Display_Name']} pays by letting another pair of hands touch the thing that hid {_secret(row)}.",
        f"Instead of seizing {row['Home_or_Base']}, the player can broker a written split of labour between {row['Display_Name']} and {rival['Display_Name']} that {ally['Display_Name']} witnesses. The material outcome is similar; the relationship cost is that {row['Display_Name']} can no longer pretend {_secret(row)} was only {their} private {row['Village_Role'].lower()} burden.",
        f"Instead of telling the whole of {row['District']}, the player can take {dep['Display_Name']} into confidence and let them decide whether {tool} is returned, hidden or logged. That protects {dep['Display_Name']}'s future at the price of making {row['Display_Name']} answer to someone {they} used to manage.",
    )


def _prized_object(row: dict[str, str], tool: str, token: str) -> str:
    return _pick(
        row["Character_ID"] + "object",
        f"the {token} {row['Display_Name']} would save before money if {row['Home_or_Base']} caught fire",
        f"a worn {tool} annotated in a hand nobody else is supposed to read",
        f"a small object from the day {_secret(row)} started, kept where work-clothes are hung",
        f"{token} wrapped in cloth from {row['District']}, too ordinary to look like evidence",
    )


def _daily_routine(row: dict[str, str], ally: dict[str, str], they: str, their: str) -> str:
    return (
        f"Dawn at {row['Home_or_Base']} checking {_role_bits(row)[1]}. Morning {row['Village_Role'].lower()} work that lets {_pronouns(row)[1]} "
        f"avoid the sentence {_secret(row)}. Midday, a plausible crossing with {ally['Display_Name']}. Afternoon errands through "
        f"{row['District']} that double as inspection. Evening return; after dark {they} handles the part of the job that would not survive an audience."
    )


NEW_FIELDS = [
    "Formative_Event",
    "Self_Image",
    "Private_Need",
    "Social_Mask",
    "Specific_Regret",
    "Specific_Hope",
    "Relationship_Wound",
    "Pressure_Behaviour",
    "Repair_Behaviour",
    "Misjudges_Others_By",
    "Cross_District_Reason",
]


def rewrite_csv(path: Path = DEFAULT_CSV) -> Path:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(path)
        original_fields = list(reader.fieldnames)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]

    fieldnames = list(original_fields)
    insert_at = fieldnames.index("Formative_Wound") + 1 if "Formative_Wound" in fieldnames else len(fieldnames)
    for field in NEW_FIELDS:
        if field not in fieldnames:
            if field == "Cross_District_Reason":
                fieldnames.insert(fieldnames.index("Cross_District_Relationship") + 1, field)
            else:
                fieldnames.insert(insert_at, field)
                insert_at += 1

    rewritten = [rewrite_row(row, rows) for row in rows]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rewritten)
    return path


def main() -> None:
    path = rewrite_csv()
    print(f"Rewrote {path}")


if __name__ == "__main__":
    main()
