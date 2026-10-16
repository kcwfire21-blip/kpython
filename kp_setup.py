import sys, io, base64, builtins, js, os
os.environ['MPLBACKEND']='AGG'
def _kp_input(prompt=''):
    sys.stdout.flush()
    if prompt: print(prompt, end='')
    sys.stdout.flush()
    v = js.prompt(str(prompt) or 'input()')
    if v is None:
        print()
        raise KeyboardInterrupt('input cancelled')
    v = str(v)
    print(v)
    return v
builtins.input = _kp_input
def _kp_show(*a, **k):
    import matplotlib.pyplot as plt
    for n in plt.get_fignums():
        f = plt.figure(n); b = io.BytesIO()
        f.savefig(b, format='png', dpi=110, bbox_inches='tight')
        js.kpShowImg(base64.b64encode(b.getvalue()).decode())
    plt.close('all')
def _kp_mpl_patch():
    if 'matplotlib' in sys.modules:
        import matplotlib; matplotlib.use('AGG')
        import matplotlib.pyplot as plt
        plt.show = _kp_show
_TURTLE = '''
import js, math
class Turtle:
    def __init__(s):
        s.x = s.y = 0.0; s.h = 0.0; s.pen = True; s.col = "#9fef00"; s.w = 2; js.kpT("reset")
    def forward(s, d):
        nx = s.x + d*math.cos(math.radians(s.h)); ny = s.y + d*math.sin(math.radians(s.h))
        if s.pen: js.kpT("line", s.x, s.y, nx, ny, s.col, s.w)
        s.x, s.y = nx, ny
    fd = forward
    def backward(s, d): s.forward(-d)
    bk = back = backward
    def left(s, a): s.h += a
    lt = left
    def right(s, a): s.h -= a
    rt = right
    def penup(s): s.pen = False
    pu = up = penup
    def pendown(s): s.pen = True
    pd = down = pendown
    def goto(s, x, y=None):
        if y is None: x, y = x
        if s.pen: js.kpT("line", s.x, s.y, x, y, s.col, s.w)
        s.x, s.y = float(x), float(y)
    setpos = setposition = goto
    def setheading(s, a): s.h = a
    seth = setheading
    def heading(s): return s.h
    def position(s): return (s.x, s.y)
    pos = position
    def home(s): s.goto(0, 0); s.h = 0
    def color(s, c, *a): s.col = c if isinstance(c, str) else "#%02x%02x%02x" % tuple(int(v*255 if v <= 1 else v) for v in c)
    pencolor = color
    def width(s, w): s.w = w
    pensize = width
    def circle(s, r, extent=360, steps=None):
        steps = steps or max(12, int(abs(r)/3)+12); seg = 2*math.pi*abs(r)*extent/360/steps; turn = extent/steps*(1 if r > 0 else -1)
        for _ in range(steps): s.left(turn/2); s.forward(seg); s.left(turn/2)
    def dot(s, size=8, c=None): js.kpT("dot", s.x, s.y, size, c or s.col)
    def write(s, t, *a, **k): js.kpT("text", s.x, s.y, str(t), s.col)
    def clear(s): js.kpT("clear")
    reset = clear
    def bgcolor(s, c): js.kpT("bg", c)
    def speed(s, *a): pass
    def hideturtle(s): pass
    ht = showturtle = st = hideturtle
    def begin_fill(s): pass
    end_fill = fillcolor = begin_fill
    def done(s): pass
    mainloop = exitonclick = done
_t = None
def _g():
    global _t
    if _t is None: _t = Turtle()
    return _t
def Screen(): return _g()
Pen = RawTurtle = Turtle
for _n in [n for n in dir(Turtle) if not n.startswith("_")]:
    globals()[_n] = (lambda n: lambda *a, **k: getattr(_g(), n)(*a, **k))(_n)
def done(): pass
mainloop = exitonclick = done
'''
os.makedirs('/home/pyodide/kplib', exist_ok=True)
open('/home/pyodide/kplib/turtle.py', 'w').write(_TURTLE)
sys.path.insert(0, '/home/pyodide/kplib')
def _kp_reset_turtle():
    if 'turtle' in sys.modules: sys.modules['turtle']._t = None

# ---- tool engines (Python) ----
import json, datetime, random
EXTRAS = {"Windows (interior)": 40, "Fridge / microwave": 25, "Restroom deep clean": 35, "Carpet vacuum deep": 30, "Trash haul-away": 20, "Floor mop & shine": 45}
FREQ = {"once": ("One-time", 1), "weekly": ("Weekly", 52/12), "biweekly": ("Every 2 weeks", 26/12), "monthly": ("Monthly", 1)}
def make_invoice(client, sqft, rate, freq, extras_json, notes=""):
    extras = json.loads(extras_json)
    sqft = max(float(sqft or 0), 0); rate = max(float(rate or 0), 0)
    label, visits = FREQ.get(freq, FREQ["once"])
    base = max(sqft * rate, 75.0)
    ex = [(e, EXTRAS[e]) for e in extras if e in EXTRAS]
    per_visit = base + sum(p for _, p in ex)
    now = datetime.datetime.now()
    L = []
    L.append("KEIVON WHITFIELD CLEANING")
    L.append("Commercial cleaning - St. Louis, MO")
    L.append("314-283-1189 | kcwfire21@gmail.com")
    L.append("-" * 34)
    L.append(f"INVOICE  INV-{now:%Y%m%d}-{random.randint(100,999)}")
    L.append(f"Date:    {now:%b %d, %Y}")
    L.append(f"Client:  {client or 'Client'}")
    L.append(f"Service: {label}")
    L.append("-" * 34)
    L.append(f"{'Base clean':<22}{'$'+format(base,',.2f'):>12}")
    L.append(f"  {sqft:,.0f} sq ft x ${rate:.3f}" + ("  (min $75)" if sqft*rate < 75 else ""))
    for e, p in ex: L.append(f"{e[:22]:<22}{'$'+format(p,',.2f'):>12}")
    L.append("-" * 34)
    L.append(f"{'PER VISIT':<22}{'$'+format(per_visit,',.2f'):>12}")
    if freq != "once":
        L.append(f"{'Est. monthly':<22}{'$'+format(per_visit*visits,',.2f'):>12}")
        L.append(f"  (~{visits:.2f} visits/month)")
    if notes: L.append(f"Notes: {notes}")
    L.append("")
    L.append("Payment due on receipt. Thank you!")
    return "\n".join(L)
def tip_calc(bill, pct, people):
    bill = float(bill or 0); pct = float(pct or 0); people = max(int(float(people or 1)), 1)
    tip = bill * pct / 100; total = bill + tip
    out = [f"Tip ({pct:g}%):  ${tip:,.2f}", f"Total:       ${total:,.2f}"]
    if people > 1: out.append(f"Each of {people}:   ${total/people:,.2f}")
    out.append("")
    for p in (15, 18, 20, 25): out.append(f"  {p}% -> tip ${bill*p/100:,.2f}, total ${bill*(1+p/100):,.2f}")
    return "\n".join(out)
UNITS = {"mi→km": (lambda v: v*1.609344, "km"), "km→mi": (lambda v: v/1.609344, "mi"), "lb→kg": (lambda v: v*0.45359237, "kg"), "kg→lb": (lambda v: v/0.45359237, "lb"),
 "°F→°C": (lambda v: (v-32)*5/9, "°C"), "°C→°F": (lambda v: v*9/5+32, "°F"), "gal→L": (lambda v: v*3.785411784, "L"), "L→gal": (lambda v: v/3.785411784, "gal"),
 "ft→m": (lambda v: v*0.3048, "m"), "m→ft": (lambda v: v/0.3048, "ft"), "in→cm": (lambda v: v*2.54, "cm"), "cm→in": (lambda v: v/2.54, "in"),
 "sq ft→sq m": (lambda v: v*0.09290304, "sq m"), "sq m→sq ft": (lambda v: v/0.09290304, "sq ft"), "oz→g": (lambda v: v*28.349523, "g"), "fl oz→mL": (lambda v: v*29.5735296, "mL"),
 "mph→km/h": (lambda v: v*1.609344, "km/h"), "hours→minutes": (lambda v: v*60, "min")}
def convert(v, unit):
    f, u = UNITS[unit]; v = float(v or 0)
    return f"{v:g} {unit.split('→')[0]} = {f(v):,.4g} {u}"
ANSWERS = ["It is certain.", "Without a doubt.", "Yes, definitely.", "You may rely on it.", "Most likely.", "Outlook good.", "Signs point to yes.", "Yes.",
 "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
 "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."]
def eight_ball(): return random.choice(ANSWERS)
