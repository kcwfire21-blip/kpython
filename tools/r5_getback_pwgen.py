# KPython password generator (Get back, round 5): secure passwords, passphrases (built-in wordlist), hex/urlsafe tokens and PINs via `secrets`, with an entropy strength meter and a checker for passwords you type. Nothing is saved or logged; no files, no network.
import secrets, string, math, re

WORDS = tuple(sorted(set("""
able acid acorn actor adapt admit adopt adult after aged agent agree ahead alarm album alert alien
alike alive alley allow alone along alpha also amber amuse angel anger angle angry ankle apple apron
area arena argue arise armor army aroma arrow aside asset atlas attic audio audit avoid awake award
aware away baby back bacon badge bagel bake baker ball band banjo bank barn base basic basin batch
bath beach bead beam bean bear beard beast beat beef begin being bell belt bench bend berry best
bike bill bingo birch bird birth bite black blade blame blank blast blaze blend bless blink block
bloom blown blue bluff blunt blush board boast boat body bold bolt bone bonus book boost boot booth
born boss bound bowl brag brain brake brand brass brave bread break brew brick bride brief brim
bring brisk broad broke brook broom brown brush buck buddy build bulb bull bump bunch bunny burn
burst bush busy cabin cable cacao cafe cage cake calf call calm camel camp canal candy cane canoe
cape card care cargo carol carry cart carve case cash cast catch cause cave cedar cell chain chair
chalk champ charm chart chase cheap check cheek cheer chef chess chest chick chief child chili chill
chimp chin chip choir chord chunk cider cigar city civic clad claim clam clamp clap clash class claw
clay clean clear clerk click cliff climb cling clip cloak clock close cloth cloud clown club clue
coach coal coast coat cobra cocoa code coin cold colt comb comet comic cone cook cool cope copy
coral cord core corn cost couch cough count court cover cozy crab crack craft crane crash crate
crawl crazy cream creek crest crew crisp crop cross crow crowd crown crumb crush crust cube cubic
cult curb cure curl curve cute cycle daily dairy daisy dame damp dance dare dark dart dash data date
dawn deal dealt dear debt decal deck decoy deep deer delta dense depot depth desk dial diary dice
diet digit dine diner dirt disco dish ditch dive diver dizzy dock dodge dome donor donut door dose
dove down doze dozen draft drag drain drama drank draw dream dress dried drift drill drink drip
drive drone drop drum dryer duck dude duke dull dune dusk dust duty each eagle early earn earth ease
easel east easy eaten ebony echo edge edit eight elbow elder elect elite elves email ember empty
enjoy enter entry epic equal equip erase error essay even event ever every exact exist exit extra
fable face fact fade faint fair fairy faith fall false fame fancy farm fast fatal favor fawn fear
feast feed feel fence fern ferry fest fever fiber field fifth fifty fight file fill film final find
fine fire firm first fish fist five flag flame flank flash flask flat flaw flea fled fleet flesh
flick fling flint flip float flock flood floor flour flow fluid flush flute foam focus foggy fold
folk fond font food fool foot force forge fork form fort forth forty forum foul found four fowl
frame free fresh fried frog from frost froze fruit fudge fuel full fully fund funny fuse gain gala
gale game gang gate gauge gave gaze gear genre ghost giant gift gild girl give given glad glare
glass gleam glide globe gloom glory glove glow glue goal goat going gold golf gone good gown grab
grace grade grain gram grand grant grape graph grasp grass grave gravy gray great greed green greet
grew grid grill grim grin grind grip grit groan groom group grove grow growl grown guard guess guest
guide guild gulf gust habit hail hair half hall halt hand hang happy hard hardy hare harp harsh hash
haste hatch haven hawk haze head heal heap hear heart heat heavy hedge heel held hello helm help
herb herd hero hide high hike hill hint hippo hire hive hobby hold hole holy home honey honor hood
hook hope horn horse hose host hotel hound hour house hover huge hull human humid humor hump hung
hunt hurry hush hyena icing icon idea ideal igloo image imply inch index inner input into iron irony
isle issue item ivory jade jail jazz jeep jelly jest jets jewel jobs join joint joke joker jolly
jolt judge juice juicy jump june junk jury just kayak kebab keen keep kelp kept kick kind king kiss
kite kiwi knack knee kneel knife knit knob knock knot know koala label labor lace lack ladle lady
laid lake lamb lamp land lane lard large lark laser last latch late laugh lava lawn layer lazy lead
leaf leak lean leap learn lease least leave ledge left lemon lend lens less level lever lick lift
light like lilac lily limb lime limit limp line linen liner link lion list live lived llama load
loaf loan lobby local lock lodge loft logic logo long look loop loose lord lorry lost lotus loud
love lover lower loyal luck lucky lump lunar lunch lung lure lush lying lyric magic mail main major
make maker male mall malt mane mango manor many maple march mark mars marsh mask mast match mate
math mayor maze meal mean meat medal media meet melon melt memo mend menu mercy merit merry mesh
metal meter might mild milk mill mime mimic mind mine minor mint minty mirth mist mitt mixer moat
mode model moist mold mole money monk month mood moon moor moose moral moss most moth motor motto
mound mount mouse mouth move movie much muddy mule mural muse music must myth nail naive name nanny
navy near neat neck need nerve nest never newly news next nice night nine ninja noble node noise
none noon norm north nose notch note noun nova novel nurse nylon oasis oath oboe ocean odor offer
often olive omega once onion only onto open opera orbit order organ other otter ounce outer oval
oven over owner oxide ozone pace pack paddy page paid pail pain paint pair pale palm panda pane
panel panic paper park parka part party pass past pasta paste patch path patio pause pave peace
peach peak pear pearl peas pecan pedal peel penny perch peril pest petal phase phone photo piano
pick piece pier pike pile pilot pinch pine pink pint pipe pixel pizza place plaid plain plan plane
plank plant plate play plaza plead plot plow pluck plug plum plumb plume plus plush poach poem poet
point polar pole polka poll polo pond pony pool poor pork port pose post pouch pound pour power pray
prep press prey price pride prime print prism prize probe proof prop proud prune pull pulp pulse
puma pump punch punk pupil puppy pure purse push quack quail quake queen query quest quick quiet
quilt quirk quiz quota quote race rack radar radio raft rage raid rail rain rally ramp ranch rang
range rank rapid rare rash rate rave raven razor reach react read ready real realm rebel recap reed
reef reel relax relay rely remix renew rent repay reply rest rhyme rice rich ride rider ridge rifle
rift right rigid ring rinse riot ripen rise risen risk rival river road roam roar roast robe robin
robot rock rocky rode rodeo rogue role roll roof room roomy roost root rope rose rosy rouge rough
round route rover royal ruby rude rug rugby rule ruler rumor rung rural rush rust rusty sack sadly
safe saga sage said sail salad salon salsa salt salty same sand sandy sane sang sash satin sauce
sauna save scale scan scarf scene scent scoop scope score scout scrap scrub seal seam seat sedan
seed seek seem seen seize self sell send sense serve setup seven shade shady shaft shake shall shape
share shark sharp shave shawl shed sheep sheet shelf shell shift shine shiny ship shirt shock shoe
shop shore short shot shout show shrub shut sick side sift sight sign silk silky silly since sing
sink siren site sixty size skate skill skip skirt skull slab slam slate sled sleep slice slid slide
slim slip slope slot sloth slow slug small smart smell smile smoke snack snail snake snap sneak
snore snow soak soap soar sock sofa soft soil solar sold sole solid solo solve some song sonic soon
sort soul sound soup sour south space spade span spare spark speak spear speed spell spend spice
spicy spike spin spine spoon sport spot spray spur squad squid stack staff stage stain stair stake
stamp stand star stare start state stay steam steel steep steer stem step stew stick still sting
stir stock stone stool stop storm story stove straw strip stuck study stuff style such sugar suit
suite sung sunk sunny super sure surf surge swamp swan swap swarm sway sweat sweep sweet swift swim
swing sword syrup table tack taco tail take taken tale talk tall tally talon tame tango tank tape
taper task tasty taxi teach teal team tear tech teen teeth tell tempo tend tenor tense tent tenth
term test text than thank that thaw them theme then they thick thief thin thing think third this
thorn three throw thumb thus tick tide tidy tiger tight tile till tilt time timer tiny tire tired
title toad toast today tofu token told toll tomb tone took tool tooth topic tops torch torn toss
total touch tough tour towel tower town toys trace track trade trail train trait tram trap tray
tread treat tree trek trend trial tribe trick tried trim trio trip troop trout truck true truly
trunk trust truth tuba tube tuck tulip tuna tune tuner turf turn tusk twice twig twin twirl twist
type ultra uncle under unify union unit unite unity until upon upper upset urban urge usage used
user usher usual utter vague valid valor value valve vapor vase vast vault vegan veil vein venue
verb verse very vest veto video view vigor vine vinyl viola viral visa visit vital vivid vocal voice
void volt vote voter wade wafer wage wagon waist wait wake walk wall waltz wand want ward warm warn
wash wasp water wave wavy waxy weak wear weave wedge weed week weigh weird well went west whale what
wheat wheel when where which while whip whirl whisk white whole wide widen width wife wild will wilt
wind wine wing wink wipe wire wise wish witch with woken wolf woman wood wool word wore work world
worm worn worry worth would wound woven wrap wrath wreck wrist write wrong yacht yard yarn year
yearn yeast yell yield yoga yolk young your youth zebra zero zesty zinc zone zoom
""".split())))

LOOKALIKE = set("Il1O0o|`'\"")
SETS = {"lower": string.ascii_lowercase, "upper": string.ascii_uppercase,
        "digits": string.digits, "symbols": "!@#$%^&*()-_=+[]{};:,.?/~"}
COMMON = {"password", "123456", "12345678", "qwerty", "abc123", "letmein", "monkey", "dragon", "iloveyou",
          "admin", "welcome", "login", "princess", "football", "baseball", "master", "sunshine", "shadow",
          "trustno1", "passw0rd", "superman", "starwars", "hello", "freedom", "whatever", "qwertyuiop", "111111"}
SEQS = ["abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm"]


def _pool(sets, no_lookalike):
    groups = []
    for name in sets:
        chars = "".join(c for c in SETS[name] if not (no_lookalike and c in LOOKALIKE))
        if chars: groups.append(chars)
    return groups


def password(length=16, sets=("lower", "upper", "digits", "symbols"), no_lookalike=False):
    """Random password with at least one char from every chosen set."""
    groups = _pool(sets, no_lookalike)
    if not groups: raise ValueError("Pick at least one character set")
    if not 4 <= length <= 256: raise ValueError("Length must be 4-256")
    if length < len(groups): raise ValueError("Length too short for the chosen sets")
    allc = "".join(groups)
    chars = [secrets.choice(g) for g in groups] + [secrets.choice(allc) for _ in range(length - len(groups))]
    for i in range(len(chars) - 1, 0, -1):  # Fisher-Yates with secrets
        j = secrets.randbelow(i + 1); chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars), length * math.log2(len(allc))


def passphrase(words=5, sep="-", capitalize=False, add_digit=False):
    if not 2 <= words <= 20: raise ValueError("Words must be 2-20")
    ws = [secrets.choice(WORDS) for _ in range(words)]
    if capitalize: ws = [w.capitalize() for w in ws]
    bits = words * math.log2(len(WORDS))
    if add_digit:
        i = secrets.randbelow(words); ws[i] += str(secrets.randbelow(10)); bits += math.log2(10)
    return sep.join(ws), bits


def token(kind="hex", n=32):
    if kind == "hex":
        if not 4 <= n <= 256: raise ValueError("Bytes must be 4-256")
        return secrets.token_hex(n), n * 8
    if kind == "urlsafe":
        if not 4 <= n <= 256: raise ValueError("Bytes must be 4-256")
        return secrets.token_urlsafe(n), n * 8
    if kind == "pin":
        if not 4 <= n <= 12: raise ValueError("PIN length must be 4-12")
        return "".join(str(secrets.randbelow(10)) for _ in range(n)), n * math.log2(10)
    raise ValueError("kind must be hex, urlsafe or pin")


def rating(bits):
    if bits < 28: return "very weak"
    if bits < 36: return "weak"
    if bits < 60: return "fair"
    if bits < 80: return "strong"
    return "very strong"


def meter(bits):
    n = max(0, min(20, int(bits / 128 * 20)))
    return "[" + "#" * n + "." * (20 - n) + "] %.0f bits, %s" % (bits, rating(bits))


def check(pw):
    """Estimate entropy of a typed password: charset size x length, minus penalties for patterns."""
    if not pw: return 0.0, ["empty"]
    size = 0
    if re.search(r"[a-z]", pw): size += 26
    if re.search(r"[A-Z]", pw): size += 26
    if re.search(r"\d", pw): size += 10
    if re.search(r"[^A-Za-z0-9]", pw): size += 33
    bits = len(pw) * math.log2(max(size, 2))
    notes = []
    low = pw.lower()
    tr = str.maketrans("@4310$5!7", "aaeiossit")
    leet = low.translate(tr)
    base = re.sub(r"[\d\W_]+$", "", low).translate(tr)
    if low in COMMON or leet in COMMON or base in COMMON:
        bits = min(bits, 10); notes.append("common password")
    else:
        for w in COMMON:
            if len(w) >= 5 and w in leet:
                bits = min(bits, 10 + (len(pw) - len(w)) * math.log2(max(size, 2))); notes.append("contains '%s'" % w); break
    if re.search(r"(.)\1{2,}", pw): bits -= 10; notes.append("repeated characters")
    for s in SEQS:
        for k in range(len(s) - 3):
            if s[k:k + 4] in low or s[k:k + 4][::-1] in low:
                bits -= 12; notes.append("keyboard/alphabet sequence"); break
        else: continue
        break
    if re.search(r"(19|20)\d\d", pw): bits -= 6; notes.append("looks like a year")
    if len(set(pw)) <= max(2, len(pw) // 4): bits -= 10; notes.append("few distinct characters")
    if len(pw) < 8: notes.append("shorter than 8")
    return max(bits, 0.0), notes


def _ask_int(prompt, default, lo, hi):
    while True:
        s = input("%s [%d]: " % (prompt, default)).strip()
        if not s: return default
        if s.isdigit() and lo <= int(s) <= hi: return int(s)
        print("Enter a number %d-%d." % (lo, hi))


def _yes(prompt, default=True):
    while True:  # KPython: only blank, y/yes or n/no are accepted
        s = input("%s (%s): " % (prompt, "Y/n" if default else "y/N")).strip().lower()
        if not s: return default
        if s in ("y", "yes"): return True
        if s in ("n", "no"): return False
        print("Please type y or n.")


def self_test():
    ok = True
    def t(cond, label):
        nonlocal ok; ok = ok and bool(cond); print(("PASS " if cond else "FAIL ") + label)
    t(len(WORDS) >= 1000, "wordlist has %d words" % len(WORDS))
    for _ in range(200):
        p, b = password(8, ("lower", "upper", "digits", "symbols"))
        if not (any(c.islower() for c in p) and any(c.isupper() for c in p) and any(c.isdigit() for c in p) and any(c in SETS["symbols"] for c in p)):
            t(False, "every set present"); break
    else: t(True, "every chosen set present (200 runs)")
    p, b = password(64, ("lower", "upper", "digits"), no_lookalike=True)
    t(len(p) == 64 and not (set(p) & LOOKALIKE), "look-alikes excluded")
    t(abs(b - 64 * math.log2(len("".join(_pool(("lower", "upper", "digits"), True))))) < 1e-9, "password entropy math")
    t(len({password(20)[0] for _ in range(50)}) == 50, "passwords are unique")
    for bad in (dict(length=2), dict(sets=()), dict(length=3, sets=("lower", "upper", "digits", "symbols"))):
        try: password(**bad); t(False, "reject %s" % bad)
        except ValueError: t(True, "reject %s" % bad)
    pp, b = passphrase(4, ".", True, True)
    parts = pp.split(".")
    t(len(parts) == 4 and all(x[0].isupper() for x in parts) and sum(any(c.isdigit() for c in x) for x in parts) == 1, "passphrase options")
    t(abs(b - (4 * math.log2(len(WORDS)) + math.log2(10))) < 1e-9, "passphrase entropy")
    h, b = token("hex", 16); t(len(h) == 32 and all(c in "0123456789abcdef" for c in h) and b == 128, "hex token")
    u, b = token("urlsafe", 24); t(re.fullmatch(r"[A-Za-z0-9_-]+", u) and b == 192, "urlsafe token")
    pin, b = token("pin", 6); t(pin.isdigit() and len(pin) == 6, "PIN")
    t(rating(20) == "very weak" and rating(50) == "fair" and rating(100) == "very strong", "ratings")
    t(check("password")[0] <= 10 and check("P@ssw0rd!")[0] <= 10, "common + leet passwords penalised")
    t(check("abcd1234")[0] < check("q7Rz#mK2")[0], "sequences penalised")
    t("repeated characters" in check("aaaaaaa1")[1], "repeats noted")
    t(rating(check(password(20)[0])[0]) in ("strong", "very strong"), "random 20-char rated strong")
    t(check("")[0] == 0, "empty")
    t("[" in meter(64) and "strong" in meter(64), "meter")
    print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
    return ok


def main():
    print("🔑 Password generator. Uses Python's `secrets`. Nothing is saved, copied or logged.")
    while True:
        print("\n1) Password  2) Passphrase  3) Token (hex/urlsafe/PIN)  4) Check a password  t) Self-tests  q) Quit")
        c = input("Choice: ").strip().lower()
        try:
            if c == "q": break
            elif c == "1":
                n = _ask_int("Length", 16, 4, 256)
                sets = [s for s in SETS if _yes("Include " + s)]
                p, b = password(n, sets, _yes("Exclude look-alikes (I l 1 O 0)", False))
                print("\n" + p + "\n" + meter(b))
            elif c == "2":
                n = _ask_int("Words", 5, 2, 20)
                sep = input("Separator [-]: ")[:3] or "-"
                p, b = passphrase(n, sep, _yes("Capitalize", False), _yes("Add a digit", False))
                print("\n" + p + "\n" + meter(b))
            elif c == "3":
                k = (input("hex / urlsafe / pin [hex]: ").strip().lower() or "hex")
                n = _ask_int("PIN digits" if k == "pin" else "Bytes", 6 if k == "pin" else 32, 4, 12 if k == "pin" else 256)
                p, b = token(k, n); print("\n" + p + "\n" + meter(b))
            elif c == "4":
                b, notes = check(input("Password to rate (not stored): "))
                print(meter(b) + ("\n  issues: " + ", ".join(notes) if notes else ""))
            elif c == "t": self_test()
            elif c: print("Pick 1-4, t or q.")
        except ValueError as e:
            print("Error:", e)


# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse", "explain", "gen_tests", "scan_code", "to_fstrings", "extract", "inline", "check"):
    if callable(globals().get(_n)) and not isinstance(globals()[_n], type): globals()[_n] = _kp_cap(globals()[_n])
if "Debugger" in globals():
    _kp_dinit = Debugger.__init__
    def _kp_dinit2(self, source, *a, **k):
        if len(source) > _KP_MAX: raise ValueError("code too big to debug (max 500 KB)")
        _kp_dinit(self, source, *a, **k)
    Debugger.__init__ = _kp_dinit2

# --- KPython v5 security wrapper: every path also goes through the app's shared kp_safe_path (/home/pyodide only) ---
import builtins as _kp_b
def _kp_wrap(fn):
    def w(*a, **k):
        r = fn(*a, **k)
        return _kp_b.kp_safe_path(r) if hasattr(_kp_b, "kp_safe_path") and isinstance(r, str) and r.startswith("/") and all(globals().get(v, "/home/pyodide") == "/home/pyodide" for v in ("BASE", "BASE_DIR", "SAFE_ROOT")) else r
    return w
for _n in ("safe_path", "_safe_path", "_safe"):
    if callable(globals().get(_n)): globals()[_n] = _kp_wrap(globals()[_n])

if __name__ == "__main__":
    main()
