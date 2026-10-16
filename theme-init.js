/* KPython v10: apply the saved theme before first paint (external file: the CSP allows no inline scripts). */
(function(){try{var t=localStorage.getItem('kp-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);}catch(e){}
var d=document.documentElement.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');
var m=document.querySelector('meta[name=theme-color]');if(m)m.content=d==='light'?'#ffffff':'#0d1117';})();
