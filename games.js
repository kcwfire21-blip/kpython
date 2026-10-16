(()=>{const hi=J('kp_hi',{snake:0,g2048:0});const saveHi=()=>S('kp_hi',hi);
function swipe(el,cb){let sx,sy;el.addEventListener('touchstart',e=>{sx=e.touches[0].clientX;sy=e.touches[0].clientY;e.preventDefault()},{passive:false});
 el.addEventListener('touchend',e=>{const dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.max(Math.abs(dx),Math.abs(dy))<20)return;cb(Math.abs(dx)>Math.abs(dy)?(dx>0?'r':'l'):(dy>0?'d':'u'))},{passive:false})}
const keyDir={ArrowUp:'u',ArrowDown:'d',ArrowLeft:'l',ArrowRight:'r'};
/* Snake */
const sc=$('sn-c'),sx=sc.getContext('2d'),N=16,C=sc.width/N;let snake,dir,next,food,timer,score,alive=false;
$('sn-best').textContent=hi.snake;
function place(){do{food=[Math.random()*N|0,Math.random()*N|0]}while(snake.some(p=>p[0]==food[0]&&p[1]==food[1]))}
function drawSnake(){sx.fillStyle='#010409';sx.fillRect(0,0,sc.width,sc.height);sx.fillStyle='#f85149';sx.beginPath();sx.arc((food[0]+.5)*C,(food[1]+.5)*C,C*.4,0,7);sx.fill();
 snake.forEach((p,i)=>{sx.fillStyle=i?'#3fb950':'#ffd43b';sx.fillRect(p[0]*C+1,p[1]*C+1,C-2,C-2)});
 if(!alive){sx.fillStyle='rgba(0,0,0,.6)';sx.fillRect(0,0,sc.width,sc.height);sx.fillStyle='#fff';sx.font='bold 22px sans-serif';sx.textAlign='center';sx.fillText(score?'Game over · '+score:'Tap Start',sc.width/2,sc.height/2)}}
function step(){dir=next;const h=[snake[0][0]+(dir=='r')-(dir=='l'),snake[0][1]+(dir=='d')-(dir=='u')];
 if(h[0]<0||h[1]<0||h[0]>=N||h[1]>=N||snake.some(p=>p[0]==h[0]&&p[1]==h[1])){alive=false;clearInterval(timer);if(navigator.vibrate)navigator.vibrate(120);if(score>hi.snake){hi.snake=score;saveHi();$('sn-best').textContent=score}drawSnake();return}
 snake.unshift(h);if(h[0]==food[0]&&h[1]==food[1]){score++;$('sn-score').textContent=score;place();clearInterval(timer);timer=setInterval(step,Math.max(70,150-score*4))}else snake.pop();drawSnake()}
function startSnake(){snake=[[8,8],[7,8],[6,8]];dir=next='r';score=0;$('sn-score').textContent=0;place();alive=true;clearInterval(timer);timer=setInterval(step,150);drawSnake()}
function turn(d){const opp={u:'d',d:'u',l:'r',r:'l'};if(alive&&d!==opp[dir])next=d}
$('sn-start').onclick=startSnake;swipe(sc,turn);document.querySelectorAll('.dpad button').forEach(b=>b.onclick=()=>turn(b.dataset.d));
snake=[[8,8],[7,8],[6,8]];score=0;food=[12,8];drawSnake();
/* 2048 */
const gc=$('g2-c'),gx=gc.getContext('2d');let grid,g2s=0;$('g2-best').textContent=hi.g2048;
const COL={0:'#21262d',2:'#eee4da',4:'#ede0c8',8:'#f2b179',16:'#f59563',32:'#f67c5f',64:'#f65e3b',128:'#edcf72',256:'#edcc61',512:'#edc850',1024:'#edc53f',2048:'#edc22e'};
function add(){const e=[];grid.forEach((r,i)=>r.forEach((v,j)=>{if(!v)e.push([i,j])}));if(e.length){const[i,j]=e[Math.random()*e.length|0];grid[i][j]=Math.random()<.9?2:4}}
function drawG(over){const s=gc.width,p=8,t=(s-p*5)/4;gx.fillStyle='#0d1117';gx.fillRect(0,0,s,s);gx.textAlign='center';gx.textBaseline='middle';
 grid.forEach((r,i)=>r.forEach((v,j)=>{const x=p+j*(t+p),y=p+i*(t+p);gx.fillStyle=COL[v]||'#3c3a32';gx.beginPath();gx.roundRect?gx.roundRect(x,y,t,t,8):gx.rect(x,y,t,t);gx.fill();
  if(v){gx.fillStyle=v<=4?'#776e65':'#fff';gx.font=`bold ${v<100?32:v<1000?26:20}px sans-serif`;gx.fillText(v,x+t/2,y+t/2+1)}}));
 if(over){gx.fillStyle='rgba(0,0,0,.6)';gx.fillRect(0,0,s,s);gx.fillStyle='#fff';gx.font='bold 24px sans-serif';gx.fillText('Game over',s/2,s/2)}}
function slide(row){const a=row.filter(v=>v);for(let i=0;i<a.length-1;i++)if(a[i]==a[i+1]){a[i]*=2;g2s+=a[i];a.splice(i+1,1)}while(a.length<4)a.push(0);return a}
function move(d){if(!grid)return;const before=JSON.stringify(grid);const rot=g=>g[0].map((_,i)=>g.map(r=>r[i]));
 if(d=='l')grid=grid.map(slide);if(d=='r')grid=grid.map(r=>slide([...r].reverse()).reverse());
 if(d=='u')grid=rot(rot(grid).map(slide));if(d=='d')grid=rot(rot(grid).map(r=>slide([...r].reverse()).reverse()));
 if(JSON.stringify(grid)!==before){add();if(navigator.vibrate)navigator.vibrate(6)}$('g2-score').textContent=g2s;if(g2s>hi.g2048){hi.g2048=g2s;saveHi();$('g2-best').textContent=g2s}
 const can=grid.some((r,i)=>r.some((v,j)=>!v||v==r[j+1]||(grid[i+1]&&v==grid[i+1][j])));drawG(!can)}
function start2048(){grid=[[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];g2s=0;add();add();$('g2-score').textContent=0;drawG()}
$('g2-start').onclick=start2048;swipe(gc,move);start2048();
document.addEventListener('keydown',e=>{const d=keyDir[e.key];if(!d||!$('v-fun').classList.contains('on'))return;e.preventDefault();if($('f-snake').classList.contains('on'))turn(d);else if($('f-2048').classList.contains('on'))move(d)});
window.KPG={startSnake,start2048,move,state:()=>({alive,score,grid,g2s})};})();
