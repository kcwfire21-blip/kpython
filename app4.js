/* KPython v4: editor power tools, REPL, docs, Dev tab, import/export */
/* ---- traceback links ---- */
function scriptForFile(f){f=f.replace(/^.*\//,'').replace(/\.py$/,'');if(f==='__kp_run__')return null;return Object.keys(scripts).find(n=>modname(n)===f)||null}
function linkify(span,t){const re=/File "([^"]+)", line (\d+)/g;let last=0,m;
 while((m=re.exec(t))){span.appendChild(document.createTextNode(t.slice(last,m.index)));const name=scriptForFile(m[1]);
  if(name){const a=document.createElement('a');a.className='tb';a.textContent=m[0];const ln=+m[2];a.onclick=()=>jumpTo(name,ln);span.appendChild(a)}else span.appendChild(document.createTextNode(m[0]));last=re.lastIndex}
 span.appendChild(document.createTextNode(t.slice(last)))}
let errLine=null;
function clearErr(){if(errLine!==null){cm.removeLineClass(errLine,'background','errline');errLine=null}}
function jumpTo(name,ln){if(name!==cur){scripts[cur]=cm.getValue();cur=name;refresh()}showView('v-code');clearErr();
 setTimeout(()=>{const l=Math.max(0,Math.min(ln-1,cm.lineCount()-1));errLine=cm.getLineHandle(l);cm.addLineClass(errLine,'background','errline');cm.setCursor({line:l,ch:0});cm.scrollIntoView({line:l,ch:0},120);cm.focus()},60)}
cm.on('change',()=>clearErr());
/* ---- editor settings: font size, wrap ---- */
const ED=J('kp_ed',{fs:14,wrap:false});
function applyEd(){document.querySelector('.CodeMirror').style.fontSize=ED.fs+'px';cm.setOption('lineWrapping',!!ED.wrap);$('e-wrap').classList.toggle('on',!!ED.wrap);S('kp_ed',ED);cm.refresh()}
$('e-fsm').onclick=()=>{ED.fs=Math.max(10,ED.fs-1);applyEd()};$('e-fsp').onclick=()=>{ED.fs=Math.min(26,ED.fs+1);applyEd()};$('e-wrap').onclick=()=>{ED.wrap=!ED.wrap;applyEd()};applyEd();
/* ---- find / replace ---- */
$('e-find').onclick=()=>{const f=$('findbar');f.hidden=!f.hidden;if(!f.hidden){const s=cm.getSelection();if(s&&!s.includes('\n'))$('f-q').value=s;$('f-q').focus()}};
let fcur=null;
function fq(){return $('f-q').value}
function fopts(){return !$('f-case').checked}
function findNext(back){const q=fq();if(!q)return false;let c=cm.getSearchCursor(q,back?cm.getCursor('from'):cm.getCursor('to'),{caseFold:fopts()});
 if(!(back?c.findPrevious():c.findNext())){c=cm.getSearchCursor(q,back?{line:cm.lastLine()}:{line:0,ch:0},{caseFold:fopts()});if(!(back?c.findPrevious():c.findNext())){$('f-msg').textContent='Not found';return false}}
 cm.setSelection(c.from(),c.to());cm.scrollIntoView({from:c.from(),to:c.to()},80);$('f-msg').textContent=countMatches()+' matches';return true}
function countMatches(){const q=fq();if(!q)return 0;let n=0;const c=cm.getSearchCursor(q,{line:0,ch:0},{caseFold:fopts()});while(c.findNext()&&n<9999)n++;return n}
$('f-next').onclick=()=>findNext(false);$('f-prev').onclick=()=>findNext(true);$('f-q').onkeydown=e=>{if(e.key==='Enter')findNext(e.shiftKey)};
$('f-rep').onclick=()=>{const q=fq(),sel=cm.getSelection();if(q&&(fopts()?sel.toLowerCase()===q.toLowerCase():sel===q))cm.replaceSelection($('f-r').value);findNext(false)};
$('f-all').onclick=()=>{const q=fq();if(!q)return;let n=0;cm.operation(()=>{const c=cm.getSearchCursor(q,{line:0,ch:0},{caseFold:fopts()});while(c.findNext()){c.replace($('f-r').value);n++}});$('f-msg').textContent=`Replaced ${n}`};
$('f-x').onclick=()=>{$('findbar').hidden=true;cm.focus()};
/* ---- go to line ---- */
$('e-goto').onclick=()=>{const v=prompt(`Go to line (1-${cm.lineCount()})`);if(v&&+v)jumpTo(cur,+v)};
/* ---- autocomplete ---- */
const PYWORDS='False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield abs all any ascii bin bool breakpoint bytearray bytes callable chr classmethod compile complex delattr dict dir divmod enumerate eval exec filter float format frozenset getattr globals hasattr hash help hex id input int isinstance issubclass iter len list locals map max memoryview min next object oct open ord pow print property range repr reversed round set setattr slice sorted staticmethod str sum super tuple type vars zip self Exception ValueError TypeError KeyError IndexError RuntimeError StopIteration ZeroDivisionError FileNotFoundError __name__ __main__ __init__'.split(' ');
function pyHint(ed){const c=ed.getCursor(),line=ed.getLine(c.line);let s=c.ch;while(s&&/\w/.test(line[s-1]))s--;const w=line.slice(s,c.ch);if(!w)return null;
 const local=new Set(ed.getValue().match(/[A-Za-z_]\w{2,}/g)||[]);local.delete(w);const all=[...new Set([...local,...PYWORDS])];
 const list=all.filter(x=>x.startsWith(w)&&x!==w).sort((a,b)=>a.length-b.length).slice(0,30);return list.length?{list,from:CodeMirror.Pos(c.line,s),to:c}:null}
cm.on('inputRead',(ed,ch)=>{if(ED.ac===false)return;if(ch.origin!=='+input'||!/\w/.test(ch.text.join('')))return;const c=ed.getCursor(),line=ed.getLine(c.line);let s=c.ch;while(s&&/\w/.test(line[s-1]))s--;
 if(c.ch-s>=2)ed.showHint({hint:pyHint,completeSingle:false})});
cm.setOption('extraKeys',{...cm.getOption('extraKeys'),'Ctrl-Space':ed=>ed.showHint({hint:pyHint,completeSingle:false}),'Ctrl-F':()=>$('e-find').click(),'Cmd-F':()=>$('e-find').click(),'Ctrl-G':()=>$('e-goto').click()});
/* ---- export / import .py ---- */
$('e-share').onclick=async()=>{scripts[cur]=cm.getValue();persist();const name=modname(cur)+'.py',file=new File([cm.getValue()],name,{type:'text/x-python'});
 if(navigator.canShare&&navigator.canShare({files:[file]})){try{await navigator.share({files:[file],title:name});return}catch(e){if(e.name==='AbortError')return}}
 const a=document.createElement('a');a.href=URL.createObjectURL(file);a.download=name;document.body.appendChild(a);a.click();a.remove();log('Exported '+name,'sys')};
$('e-imp').onclick=()=>$('e-file').click();
$('e-file').onchange=async e=>{for(const f of e.target.files){if(f.size>2e6){log(f.name+' too big (2 MB max)','err');continue}newScript(f.name.replace(/\.py$/,''),await f.text());toast2('Imported '+f.name);log('Imported '+f.name,'sys')}e.target.value=''};
/* ---- REPL ---- */
const RH=J('kp_rhist',[]);let rhi=RH.length,rbuf=[];
function rlog(t,c){const s=document.createElement('span');if(c)s.className=c;s.textContent=t+'\n';$('r-out').appendChild(s);$('r-out').scrollTop=1e9}
async function replSend(){const src=$('r-in').value;if(running)return toast('Python is busy');const lines=src.split('\n');$('r-in').value='';
 const TOKRE=/(eyJ[\w-]+\.[\w-]+\.[\w-]*|gh[pousr]_\w{20,}|github_pat_\w{20,}|sk-[\w-]{16,}|AKIA[0-9A-Z]{16}|xox[abprs]-[\w-]{10,}|(authorization|password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+)/i;
 if(src.trim()&&!TOKRE.test(src)){RH.push(src);if(RH.length>200)RH.shift();S('kp_rhist',RH)}rhi=RH.length;
 for(const ln of lines){rlog(($('r-ps').textContent)+' '+ln,'echo');kpJobNext='The console (REPL)';const r=await job({cmd:'repl',line:ln,files:allFiles()},{target:$('r-out')});
  $('r-ps').textContent=r.more?'...':'>>>';if(!r.ok)break}
 if(lines.length>1&&$('r-ps').textContent==='...'){const r=await job({cmd:'repl',line:'',files:allFiles()},{target:$('r-out')});$('r-ps').textContent=r.more?'...':'>>>'}
 $('r-out').scrollTop=1e9;$('r-in').focus()}
$('r-go').onclick=replSend;
$('r-in').onkeydown=e=>{const ta=e.target;
 if(e.key==='Enter'&&!e.shiftKey){const v=ta.value;if(!v.includes('\n')&&!/[:\\,(\[{]\s*$/.test(v)){e.preventDefault();replSend()}}
 else if(e.key==='ArrowUp'&&!ta.value.slice(0,ta.selectionStart).includes('\n')){if(rhi>0){e.preventDefault();ta.value=RH[--rhi]}}
 else if(e.key==='ArrowDown'&&!ta.value.slice(ta.selectionEnd).includes('\n')){e.preventDefault();rhi=Math.min(RH.length,rhi+1);ta.value=RH[rhi]||''}};
$('r-up').onclick=()=>{if(rhi>0)$('r-in').value=RH[--rhi]};$('r-down').onclick=()=>{rhi=Math.min(RH.length,rhi+1);$('r-in').value=RH[rhi]||''};
$('r-clr').onclick=()=>{if(inputMsg){dropOut=true;obuf=[];answerInput(null)}$('r-out').textContent=''};
$('r-reset').onclick=async()=>{if(!confirm('Clear all console variables?'))return;await job({cmd:'call',fn:'_kp_repl_reset',args:[]});$('r-ps').textContent='>>>';rlog('Console reset.','sys')};
/* ---- Docs ---- */
const QREF={'str':"s.split(sep) s.join(list) s.strip() s.replace(a,b) s.find(x) s.startswith(x) s.upper()/lower() f\"{x:,.2f}\" s.splitlines() s.isdigit()",
'list / dict':"l.append(x) l.extend(it) l.pop(i) l.sort(key=f) sorted(it, reverse=True) l[a:b:c]  d.get(k, default) d.items() d.setdefault(k, []) {k: v for ...} d | other",
'os / pathlib':"os.listdir('.') os.makedirs(p, exist_ok=True) os.path.join(a,b) os.path.exists(p)  Path('x').read_text() Path('x').write_text(s) Path('.').glob('*.py')   (files live in /home/pyodide)",
'json / csv':"json.loads(s) json.dumps(o, indent=2) json.load(f) json.dump(o, f)  csv.reader(f) csv.DictReader(f) csv.writer(f).writerow(row)",
're':"re.search(p, s) re.findall(p, s) re.sub(p, repl, s) re.compile(p, re.I) m.group(1) r'\\d+' r'\\w+' r'^...$'",
'datetime':"datetime.now() date.today() timedelta(days=7) d.strftime('%Y-%m-%d %H:%M') datetime.strptime(s, '%Y-%m-%d') (d2-d1).days",
'collections / itertools':"Counter(it).most_common(3) defaultdict(list) deque(maxlen=n) namedtuple('P','x y')  itertools.chain combinations permutations groupby product islice",
'math / random / statistics':"math.sqrt floor ceil pi log  random.randint(a,b) random.choice(l) random.shuffle(l)  statistics.mean median stdev",
'functools / typing':"@lru_cache(None) partial(f, x) reduce(f, it)  @dataclass  from typing import List, Dict, Optional",
'sqlite3':"con = sqlite3.connect('db.sqlite'); cur = con.execute('SELECT * FROM t WHERE id=?', (1,)); cur.fetchall(); con.commit()",
'unittest / doctest':"class T(unittest.TestCase): def test_x(self): self.assertEqual(f(1), 2)   (Dev ▸ Tests runs them)  doctest: >>> f(1)\\n2",
'asyncio':"await asyncio.sleep(1) at top level works here  asyncio.gather(a(), b())  from pyodide.http import pyfetch; r = await pyfetch(url); await r.json()"};
$('d-ref').innerHTML=Object.entries(QREF).map(([k,v])=>`<details><summary>${esc(k)}</summary><pre class="inv">${esc(v.split(/ {2,}|(?<=\)) /).join('\n'))}</pre></details>`).join('');
$('d-go').onclick=async()=>{const q=$('d-q').value.trim();if(!q)return;$('d-out').textContent='Looking up…';$('d-out').textContent=await pycall('_kp_doc',q)};
$('d-q').onkeydown=e=>{if(e.key==='Enter')$('d-go').click()};
document.querySelectorAll('.dq').forEach(b=>b.onclick=()=>{$('d-q').value=b.textContent;$('d-go').click()});
/* ---- Dev tab ---- */
const devOut=()=>$('dv-out');
// v9: Cancel on an input() prompt ends any tool cleanly ("Cancelled."), and a tool can never leave a tracer (debugger) running.
function devWrap(code){return 'import sys as _kp_sys\ntry:\n'+code.split('\n').map(l=>'    '+l).join('\n')+'\nexcept (KeyboardInterrupt, EOFError) as _kp_e:\n    if isinstance(_kp_e, KeyboardInterrupt) and "input cancelled" not in str(_kp_e): raise\n    print("\\n⏹ Cancelled.")\nfinally:\n    _kp_sys.settrace(None)\n'}
async function dev(label,code){kpJobNext='The Dev tool "'+label+'"';devOut().textContent='';log('— '+label+' —','sys');const t=devOut();const r=await job({cmd:'run',code:'from __main__ import _kp_lint, _kp_tests, _kp_outline, _kp_diff, _kp_profile, _kp_debug, _kp_metrics, _kp_types, _kp_snapshot, _kp_cover, _kp_memory, _kp_secrets, _kp_imports\n'+devWrap(code),files:allFiles(),fname:'__kp_run__.py'},{target:t});const s=document.createElement('span');s.className='sys';s.textContent=(r.ok?'— done —':(/Stopped|KeyboardInterrupt/.test(r.err||'')?'— stopped —':'— error —'))+'\n';t.appendChild(s);return r}
const J2=s=>JSON.stringify(s);
const curSrc=()=>{scripts[cur]=cm.getValue();persist();return cm.getValue()};
const DEV={
 lint:()=>dev('Lint '+cur,`print("Lint: ${cur.replace(/[\\"]/g,'')}  (Eight's checker, never runs your code)")\n_kp_lint(${J2(curSrc())})`),
 tests:()=>!confirm(`Run tests? This executes "${cur}".`)?(devOut().textContent='Cancelled.'):dev('Tests '+cur,`_kp_tests(${J2(curSrc())}, ${J2(cur)})`),
 outline:()=>dev('Outline '+cur,`_kp_outline(${J2(curSrc())})`),
 rename:async()=>{const o=prompt('Rename which name? (token-safe: skips strings and comments)');if(!o)return;const n=prompt(`Rename "${o}" to:`);if(!n)return;
  const r=await pycall('_kp_rename',curSrc(),o.trim(),n.trim());if(typeof r==='string'&&!r.startsWith('Error')){cm.setValue(r);scripts[cur]=r;persist();devOut().textContent=`Renamed ${o} → ${n} in ${cur}. Undo with ↶ in the editor.`}else devOut().textContent=r},
 profile:()=>!confirm(`Profile? This executes "${cur}".`)?(devOut().textContent='Cancelled.'):dev('Profile '+cur,`print("This runs your code under cProfile. Tap Stop if it hangs.")\n_kp_profile(${J2(curSrc())})`),
 diff:()=>{const a=$('dv-a').value,b=$('dv-b').value;allFiles();dev('Diff',`_kp_diff(${J2(scripts[a]||'')}, ${J2(scripts[b]||'')}, ${J2(a)}, ${J2(b)}, ${$('dv-side').checked?'True':'False'})`)},
 sql:()=>dev('SQL','import sqlite3\nimport r2_getback_sql as m; m.main()'),
 http:()=>dev('HTTP','import r2_forlor_http as m; m.main()'),
 data:()=>dev('Data viewer','import r2_bot2help_data as m; m.main()'),
 projects:()=>dev('Projects','import r2_bot_projects as m; m.main()'),
 bench:()=>dev('Benchmark','import r7_bot_benchq as m; m.main()'),
 format:async()=>{const src=curSrc();const r=await pycall('_kp_format',src);if(typeof r!=='string'||r.startsWith('Error')){devOut().textContent=String(r);return}
  if(r===src){devOut().textContent='Already formatted. No changes.';return}await dev('Format preview',`_kp_diff(${J2(src)}, ${J2(r)}, 'before', 'after', False)`);
  if(confirm('Apply formatting to "'+cur+'"? (Undo with ↶)')){cm.replaceRange(r,{line:0,ch:0},{line:cm.lastLine()});scripts[cur]=r;persist();devOut().append('\nApplied.')}},
 debug:()=>!confirm(`Debug "${cur}"? This runs your code line by line.`)?(devOut().textContent='Cancelled.'):dev('Debug '+cur,`_kp_debug(${J2(curSrc())})`),
 metrics:()=>dev('Metrics '+cur,`_kp_metrics(${J2(curSrc())})`),
 types:()=>dev('Type check '+cur,`_kp_types(${J2(curSrc())})`),
 snap:()=>{const msg=prompt('Version note (optional)','');if(msg===null)return;dev('Save version',`_kp_snapshot(${J2(cur)}, ${J2(curSrc())}, ${J2(msg)})`)},
 history:()=>dev('History','import r3_drop_history as m; m.main()'),
 regex:()=>dev('Regex','import r3_dyno_regex as m; m.main()'),
 json:()=>dev('JSON','import r3_forlor_json as m; m.main()'),
 codec:()=>dev('Encode/Hash','import r3_getback_codec as m; m.main()'),
 templates:()=>dev('Templates','import r3_bot2_snippets as m; m.main()'),
 cover:()=>!confirm(`Coverage runs "${cur}" and its tests. Continue?`)?(devOut().textContent='Cancelled.'):dev('Coverage '+cur,`_kp_cover(${J2(curSrc())})`),
 memory:()=>!confirm(`Memory profile runs "${cur}". Continue?`)?(devOut().textContent='Cancelled.'):dev('Memory '+cur,`_kp_memory(${J2(curSrc())})`),
 docgen:async()=>{const src=curSrc();const r=await pycall('_kp_docgen',src);if(typeof r!=='string'||r.startsWith('Error')){devOut().textContent=String(r);return}
  if(r===src){devOut().textContent='Every function already has a docstring.';return}await dev('Docstrings preview',`_kp_diff(${J2(src)}, ${J2(r)}, 'before', 'after', False)`);
  if(confirm('Add these docstrings to "'+cur+'"? (Undo with ↶)')){cm.replaceRange(r,{line:0,ch:0},{line:cm.lastLine()});scripts[cur]=r;persist();devOut().append('\nApplied.')}else devOut().append('\nCancelled.')},
 secrets:()=>dev('Secret scan',`_kp_secrets(${J2(JSON.stringify(allFiles()))})`),
 imports:()=>dev('Import map','_kp_imports()'),
 markdown:async()=>{const html=await pycall('_kp_markdown',curSrc());const box=$('dv-md');
  // Eight's renderer escapes all raw HTML; it is still shown in a fully sandboxed iframe (no scripts, no same-origin) as a second layer.
  box.hidden=false;box.srcdoc='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data: https:"><style>body{font:15px -apple-system,sans-serif;color:#e6edf3;background:#0d1117;padding:8px}pre,code{background:#161b22;border-radius:6px}pre{padding:8px;overflow:auto}a{color:#58a6ff}table{border-collapse:collapse}td,th{border:1px solid #30363d;padding:4px}</style>'+String(html);devOut().textContent='Markdown preview of "'+cur+'" below.'},
 convert:()=>dev('Convert','import r4_forlor_convert as m; m.main()'),
 katas:()=>dev('Katas','import r4_bot2_katas as m; m.main()'),
 packages:()=>dev('Packages','import r4_drop_packages as m\nawait m.amain()'),
 patch:()=>dev('Diff & patch','import r2_drop_diff as m; m.main()'),
 help:()=>dev('❓ Help guide','import r6_eight_help as m\nm.main()'),
 tour:()=>dev('🧭 Getting-started tour','import r7_bot2_tour as m\nm.main()'),
 selftestall:()=>dev('🧪 Self-test all tools','import r7_dyno_selftest_all as m\nm.main()'),
 cells:()=>dev('🧩 Cell runner (# %%)','import r6_dyno_cells as m\nm.main()'),
 time:()=>dev('🕒 Time & cron','import tzdata  # loads time-zone data in the browser\nimport r6_forlor_time as m\nm.main()'),
 audit:()=>dev('🛡 Dependency audit','import r6_getback_audit as m\nm.main()'),
 merge:()=>dev('🔀 3-way merge','import r6_drop_merge as m\nawait m.amain()'),
 bigo:()=>dev('📈 Big-O estimator','import r6_bot3_bigo as m\nm.main()'),
 cheats:()=>dev('📝 Cheat sheets','import r6_bot2_cheats as m\nm.main()'),
 logs:()=>dev('📜 Log analyzer','import r6_bot2help_logs as m\nm.main()'),

 board:()=>dev('✅ Task board','import r5_eight_todo as m\nm.main()'),
 testgen:()=>dev('🧪 Test generator','import r5_dyno_testgen as m\nm.main()'),
 apis:()=>dev('📮 API collections','import r5_forlor_apiclient as m\nf = m.main()\nif f is not None: await f'),
 pwgen:()=>dev('🔑 Passwords','import r5_getback_pwgen as m\nm.main()'),
 search:()=>dev('🔍 Project search','import r5_drop_search as m\nm.main()'),
 savedrepl:()=>dev('✏️ Replace in saved scripts','import r5_drop_search as m\nawait m.saved_replace()'),
 compare:()=>dev('⏱ Compare speed','import r5_bot3_timeit as m\nm.main()'),
 explain:()=>dev('📖 Explain code','import r5_bot2_explain as m\nm.main()'),
 chart:()=>dev('📊 Charts','import r5_bot2help_chart as m\nm.main()'),
 refactor:()=>dev('🛠 Refactor','import r5_bot_refactor as m\nm.main()')};
document.querySelectorAll('[data-dev]').forEach(b=>b.onclick=()=>{if(running)return toast('Python is busy (tap ⏹ Stop)');DEV[b.dataset.dev]()});
function devSelects(){const o=Object.keys(scripts).map(n=>`<option>${esc(n)}</option>`).join('');['dv-a','dv-b'].forEach((id,i)=>{const v=$(id).value;$(id).innerHTML=o;$(id).value=v&&v in scripts?v:Object.keys(scripts)[Math.min(i,Object.keys(scripts).length-1)]})}
window.addEventListener('click',e=>{if(e.target.closest('#tabs [data-v="v-dev"]'))devSelects()});devSelects();
$('dv-clr').onclick=()=>{if(inputMsg){dropOut=true;obuf=[];answerInput(null)}devOut().textContent=''};
/* ---- cross-origin isolation (SharedArrayBuffer for Stop + input) ---- */
if('serviceWorker'in navigator&&isSecureContext){
 if(!self.crossOriginIsolated&&!sessionStorage.kp_coi){if(navigator.serviceWorker.controller){sessionStorage.kp_coi=1;location.reload()}
  else navigator.serviceWorker.addEventListener('controllerchange',()=>{if(!sessionStorage.kp_coi){sessionStorage.kp_coi=1;location.reload()}})}}

/* small tips from bot2/bot3 */
const ci=cm.getInputField();['autocapitalize','autocorrect'].forEach(k=>ci.setAttribute(k,'off'));ci.setAttribute('spellcheck','false');
navigator.storage?.persist?.().catch(()=>{});
if(!navigator.standalone&&!matchMedia('(display-mode: standalone)').matches&&!LS.getItem('kp_a2hs')){LS.setItem('kp_a2hs','1');log('Tip: add KPython to your Home Screen (Share ▸ Add to Home Screen). Safari can erase data for sites that are not installed after ~7 days unused. Export backups in Files.','sys')}
const HINTS=[[/IndentationError|TabError/,'Hint: the spaces at the start of a line are off. Lines inside an if/for/def need 4 more spaces than the line above.'],
 [/NameError: name '(\w+)'/,m=>`Hint: Python doesn't know "${m[1]}". Check the spelling, or define/import it before this line.`],
 [/ModuleNotFoundError: No module named '([\w.]+)'/,m=>`Hint: "${m[1]}" isn't installed. Try 📦 Packages, or check that a saved script has that name.`],
 [/TypeError/,'Hint: a value has the wrong type, e.g. adding text to a number. Use int(), float() or str() to convert.'],
 [/SyntaxError/,"Hint: Python can't read this line. Look for a missing : ) ] or quote near it."],
 [/KeyError|IndexError/,"Hint: the key or position you asked for isn't in that dict/list."],
 [/ZeroDivisionError/,'Hint: something was divided by zero.']];
const _log=log;log=function(t,c){_log(t,c);if(c==='err'){for(const [re,h] of HINTS){const m=String(t).match(re);if(m){_log(typeof h==='function'?h(m):h,'ehint');break}}}};

$('f-new').onclick=()=>{const n=prompt('New script name?');if(n){newScript(n.trim()||'script','print("hi")\n');showView('v-code')}};$('f-imp').onclick=()=>$('e-file').click();

/* v6: offline-ready indicator (asks the service worker whether every app + Python file is cached) */
async function offStatus(){const el=$('offstat');if(!('serviceWorker'in navigator)){el.textContent='⚠️ No offline';return}
 const reg=await navigator.serviceWorker.ready.catch(()=>null);const sw=navigator.serviceWorker.controller||reg?.active;if(!sw){el.textContent='…';return setTimeout(offStatus,3000)}
 const ch=new MessageChannel();const r=await new Promise(res=>{ch.port1.onmessage=e=>res(e.data);sw.postMessage({kpStatus:1},[ch.port2]);setTimeout(()=>res(null),4000)});
 if(r&&r.ok&&r.ver!==KP_APPV&&!window.kpUpdatePending&&(offStatus.n=(offStatus.n||0)+1)<10){el.textContent='⏳ Updating…';el.classList.remove('ok');el.title='Finishing the update to '+KP_APPV;return setTimeout(offStatus,3000)}
 if(r&&r.ok){el.textContent='✈️ Offline ready';el.classList.add('ok');el.title=(r.ver===KP_APPV?'':'⚠️ page '+KP_APPV+' vs ')+'cache '+r.ver+': everything is cached'+(r.ver===KP_APPV?'':' (reload to finish updating)')}else{el.textContent=navigator.onLine?'⏳ Caching…':'⚠️ Offline (partial)';el.classList.remove('ok');el.title=r?r.missing+' files not cached yet':'no answer';setTimeout(offStatus,5000)}}
offStatus();

$('go-scan').onclick=e=>{e.preventDefault();showView('v-dev');DEV.secrets()};

/* v6.1: Allowed sites (page UI only). Stored in kp_sites, validated on load, sent to the service worker, which builds the worker CSP. */
const SITE_DEFAULTS=['this app (self)','https://api.github.com','https://cdn.jsdelivr.net/pyodide/v0.26.4/full/','https://pypi.org','https://files.pythonhosted.org'];
function getSites(){const raw=J('kp_sites',[]);const c=kpCleanSites(raw);if(JSON.stringify(c)!==JSON.stringify(raw))S('kp_sites',c);return c}
function swMsg(msg){return new Promise(async(res,rej)=>{const reg=await navigator.serviceWorker?.ready;const sw=navigator.serviceWorker?.controller||reg?.active;if(!sw)return rej(new Error('no service worker'));
 const ch=new MessageChannel();ch.port1.onmessage=e=>res(e.data);sw.postMessage(msg,[ch.port2]);setTimeout(()=>rej(new Error('timeout')),3000)})}
async function syncSites(){if(!('serviceWorker'in navigator))return;const l=getSites();const r=await Promise.race([swMsg({kpSites:{list:l}}),new Promise((_,j)=>setTimeout(()=>j(new Error('timeout')),2000))]);return r}
function renderSites(){const l=getSites();$('st-list').innerHTML=l.map((s,i)=>`<div class="item"><span>${esc(s)}</span><button data-i="${i}">✕</button></div>`).join('')||'<p class="hint">None added.</p>';
 $('st-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{const s=l[+b.dataset.i];if(!confirm('Remove '+s+'?'))return;S('kp_sites',l.filter(x=>x!==s));applySites('Removed '+s)});
 $('st-def').innerHTML=SITE_DEFAULTS.map(esc).join('<br>')}
async function applySites(msg){sitesBusy=true;$('st-add').disabled=true;try{await applySites0(msg)}finally{sitesBusy=false;$('st-add').disabled=false}}
async function applySites0(msg){renderSites();$('st-msg').textContent=msg+'. Restarting Python to apply…';toast2('Restarting Python to apply');
 try{await syncSites()}catch(e){$('st-msg').textContent=msg+'. (Service worker not ready; reload the app to apply.)';return}
 if(running){W.terminate();Object.values(pend).forEach(p=>p({ok:false,err:'⏹ Restarted to apply Allowed sites.'}));pend={};inputMsg=null}else W.terminate();
 startWorker();await pyReady;$('st-msg').textContent=msg+'. Applied.'}
let sitesBusy=false;
$('st-add').onclick=()=>{if(sitesBusy){$('st-msg').textContent='Still applying the last change… try again in a moment.';return}const r=kpParseSite($('st-in').value);if(r.error){$('st-msg').textContent='❌ '+r.error;return}
 const l=getSites();if(l.includes(r.origin)){$('st-msg').textContent='Already in the list.';return}if(l.length>=KP_SITES_MAX){$('st-msg').textContent='List is full (50).';return}
 let warn='';if(r.kind==='ip')warn='\n\n⚠️ This is a raw IP address. Only allow it if you know exactly what it is.';
 if(r.kind==='local')warn='\n\n⚠️ Private network address (localhost, Tailscale 100.x, or a home/office network like 10.x, 172.16–31.x, 192.168.x). Scripts will be able to talk to that device.';
 if(r.origin.includes('*.'))warn+='\n\nThe * allows every subdomain of that site.';
 if(r.kind==='ip'&&prompt(`Raw IP address ${r.origin}. Type IP to confirm it's intended:`)!=='IP'){$('st-msg').textContent='Cancelled.';return}
 const t=prompt(`Allow Python to connect to\n${r.origin}${warn}\n\nType yes to add:`);if((t||'').trim().toLowerCase()!=='yes'){$('st-msg').textContent='Cancelled.';return}
 S('kp_sites',[...l,r.origin]);$('st-in').value='';applySites('Added '+r.origin)};
$('st-in').onkeydown=e=>{if(e.key==='Enter')$('st-add').click()};
$('st-reset').onclick=()=>{if(prompt('Remove all your sites and keep only the defaults? Type RESET:')!=='RESET')return;S('kp_sites',[]);applySites('Reset to defaults')};
renderSites();

/* v8: undo the last saved-script change made through the Python bridge (page-side snapshots, last 20) */
$('bk-undo').onclick=()=>{let s=[];try{s=JSON.parse(LS.getItem('kp_snaps')||'[]')}catch(e){}if(!Array.isArray(s)||!s.length){toast2('No Python changes to undo');return}
 const last=s[s.length-1];const BAD=['__proto__','constructor','prototype'];
 if(!last||typeof last.name!=='string'||typeof last.text!=='string'||typeof last.ts!=='string'||BAD.includes(last.name)){s.pop();LS.setItem('kp_snaps',JSON.stringify(s));toast2('Skipped a damaged undo entry');return}
 if(last.name===cur){clearTimeout(dirtyT);scripts[cur]=cm.getValue();persist()}
 const exists=Object.hasOwn(scripts,last.name);const changed=exists&&typeof last.after==='string'&&scripts[last.name]!==last.after;
 let q=`Restore "${last.name}" to how it was before the Python change at ${last.ts.slice(0,16).replace('T',' ')} UTC?`;
 if(!exists)q=`"${last.name}" no longer exists (deleted or renamed).\nRecreate it with the text from before the Python change at ${last.ts.slice(0,16).replace('T',' ')} UTC?`;
 else if(changed)q+=`\n\n⚠️ You have edited "${last.name}" since then. Your newer edits will be replaced (a copy of them is kept, so Undo again brings them back).`;
 if(!confirm(q))return;
 s.pop();if(exists&&changed)s.push({name:last.name,text:scripts[last.name],after:last.text,ts:new Date().toISOString()});
 try{LS.setItem('kp_snaps',JSON.stringify(s))}catch(e){toast2('Not enough storage for undo');return}
 scripts[last.name]=last.text;persist();refresh();if(last.name===cur)cm.setValue(last.text);toast2('Restored "'+last.name+'"')};
// v9: offer the getting-started tour once, on first launch (after unlock and once Python is ready)
(async()=>{try{if(LS.getItem('kp_toured'))return;for(let i=0;i<600&&!$('pystat').classList.contains('ok');i++)await new Promise(r=>setTimeout(r,500));
 for(let i=0;i<600&&$('lock')&&getComputedStyle($('lock')).display!=='none';i++)await new Promise(r=>setTimeout(r,500));
 if(LS.getItem('kp_toured')||running)return;LS.setItem('kp_toured','1');
 if(confirm('Welcome to KPython! Take the 1-minute getting-started tour?\n\n(You can open it any time from Dev › 🧭 Getting-started tour.)')){showView('v-dev');DEV.tour()}}catch(e){console.error(e)}})();
// v9 perf: the games and the GitHub panel aren't needed for the first paint; load them once the page is idle
(()=>{const load=()=>['games.js','github.js'].forEach(f=>{const s=document.createElement('script');s.src=f;document.body.appendChild(s)});
 const go=()=>window.requestIdleCallback?requestIdleCallback(load,{timeout:2000}):setTimeout(load,300);
 if(document.readyState==='complete')go();else window.addEventListener('load',go)})();
