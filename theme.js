/* KPython v10: theme picker (System / Light / Dark). */
(function(){var root=document.documentElement,sel=document.getElementById('theme-sel'),mq=matchMedia('(prefers-color-scheme: light)');
function eff(){return root.getAttribute('data-theme')||(mq.matches?'light':'dark');}
function sync(){var d=eff();var m=document.querySelector('meta[name=theme-color]');if(m)m.content=d==='light'?'#ffffff':'#0d1117';
  root.style.colorScheme=d;try{window.KP&&KP.cm&&KP.cm().refresh()}catch(e){}}
function apply(v){if(v==='light'||v==='dark')root.setAttribute('data-theme',v);else root.removeAttribute('data-theme');
  try{v==='system'?localStorage.removeItem('kp-theme'):localStorage.setItem('kp-theme',v);}catch(e){}sync();}
sel.value=root.getAttribute('data-theme')||'system';sel.addEventListener('change',function(){apply(sel.value);});
mq.addEventListener('change',function(){if(!root.hasAttribute('data-theme'))sync();});sync();})();
