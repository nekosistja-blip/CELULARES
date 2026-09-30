import sqlite3, os, re, json, html, urllib.parse
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template_string

BASE=os.path.dirname(os.path.abspath(__file__)); DB=os.path.join(BASE,'phones.db')
app=Flask(__name__)
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
 c=db(); c.executescript('''
 CREATE TABLE IF NOT EXISTS brands(id INTEGER PRIMARY KEY,name TEXT UNIQUE,slug TEXT UNIQUE);
 CREATE TABLE IF NOT EXISTS phones(id INTEGER PRIMARY KEY,brand_id INTEGER,model TEXT,slug TEXT UNIQUE,release_year INTEGER,release_date TEXT,status TEXT DEFAULT 'released',os_initial TEXT,ui_skin TEXT,support_years REAL,support_until TEXT,chipset TEXT,cpu TEXT,gpu TEXT,process_nm REAL,ram_gb TEXT,storage_gb TEXT,storage_type TEXT,display_type TEXT,display_inches REAL,resolution TEXT,refresh_hz INTEGER,brightness_nits INTEGER,rear_cameras TEXT,front_camera TEXT,video TEXT,battery_mah INTEGER,wired_charge_w REAL,wireless_charge_w REAL,reverse_charge TEXT,height_mm REAL,width_mm REAL,thickness_mm REAL,weight_g REAL,materials TEXT,ip_rating TEXT,network TEXT,wifi TEXT,bluetooth TEXT,nfc TEXT,usb TEXT,sim TEXT,esim TEXT,sensors TEXT,source_url TEXT,source_name TEXT,verification_status TEXT DEFAULT 'internet',verified_at TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS phone_sources(id INTEGER PRIMARY KEY,phone_id INTEGER,url TEXT,title TEXT,domain TEXT,is_official INTEGER DEFAULT 0,fetched_at TEXT,raw_excerpt TEXT);
 CREATE TABLE IF NOT EXISTS updater_runs(id INTEGER PRIMARY KEY,started_at TEXT,finished_at TEXT,status TEXT,found_count INTEGER DEFAULT 0,updated_count INTEGER DEFAULT 0,notes TEXT);
 CREATE INDEX IF NOT EXISTS idx_model ON phones(model); CREATE INDEX IF NOT EXISTS idx_year ON phones(release_year);
 ''')
 for b in ['Apple','Samsung','Xiaomi','Redmi','POCO','Realme','OPPO','OnePlus','Honor','Huawei','Motorola','Google','Vivo','iQOO','ASUS','Sony','Nokia','ZTE','Nubia','TCL','Infinix','Tecno','Lenovo','Meizu','LG','HTC','Nothing']:
  c.execute('INSERT OR IGNORE INTO brands(name,slug) VALUES(?,?)',(b,b.lower().replace(' ','-')))
 c.commit(); c.close()

def brand_of(q):
 ql=q.lower(); aliases={'iphone':'Apple','galaxy':'Samsung','pixel':'Google','redmi':'Redmi','poco':'POCO','oneplus':'OnePlus','realme':'Realme','oppo':'OPPO','honor':'Honor','huawei':'Huawei','motorola':'Motorola','moto ':'Motorola','xiaomi':'Xiaomi','vivo':'Vivo','iqoo':'iQOO','asus':'ASUS','sony':'Sony','nokia':'Nokia','zte':'ZTE','nubia':'Nubia','infinix':'Infinix','tecno':'Tecno','nothing':'Nothing'}
 for k,v in aliases.items():
  if k in ql:return v
 return q.split()[0].title() if q else 'Unknown'

def official_domains(brand):
 return {'Apple':['apple.com'],'Samsung':['samsung.com'],'Xiaomi':['mi.com'],'Redmi':['mi.com'],'POCO':['mi.com','po.co'],'Google':['store.google.com','support.google.com'],'Motorola':['motorola.com'],'OnePlus':['oneplus.com'],'OPPO':['oppo.com'],'Realme':['realme.com'],'Honor':['honor.com'],'Huawei':['huawei.com'],'Vivo':['vivo.com'],'ASUS':['asus.com'],'Sony':['sony.com'],'Nothing':['nothing.tech']}.get(brand,[])

def search_web(query,limit=8):
 url='https://html.duckduckgo.com/html/?q='+urllib.parse.quote(query)
 r=requests.get(url,headers=UA,timeout=12); r.raise_for_status(); s=BeautifulSoup(r.text,'html.parser'); out=[]
 for a in s.select('.result__a')[:limit]:
  href=a.get('href',''); parsed=urllib.parse.urlparse(href)
  if 'duckduckgo.com' in parsed.netloc:
   href=urllib.parse.parse_qs(parsed.query).get('uddg',[href])[0]
  out.append({'title':a.get_text(' ',strip=True),'url':href})
 return out

def fetch_text(url):
 r=requests.get(url,headers=UA,timeout=12); r.raise_for_status();
 if 'text/html' not in r.headers.get('content-type',''): return ''
 s=BeautifulSoup(r.text,'html.parser')
 for x in s(['script','style','noscript','svg']):x.decompose()
 return re.sub(r'\s+',' ',s.get_text(' ',strip=True))[:180000]

def first(patterns,text,flags=re.I):
 for p in patterns:
  m=re.search(p,text,flags)
  if m:return m.group(1).strip()
 return None

def num(v,typ=float):
 if not v:return None
 try:return typ(str(v).replace(',','.'))
 except:return None

def parse_specs(text, query):
 d={}
 d['release_year']=num(first([r'(?:announced|released|launch(?:ed)?)[^0-9]{0,35}(20(?:1[8-9]|2[0-9]))',r'\b(20(?:1[8-9]|2[0-9]))\b'],text),int)
 d['chipset']=first([r'(?:chipset|platform|processor)\s*[:\-]?\s*((?:Qualcomm )?Snapdragon[^|;,]{2,45})',r'(Apple A\d{1,2}(?: Pro)?(?: Bionic)?)',r'(MediaTek Dimensity\s*\d+[A-Za-z+ ]*)',r'(Exynos\s*\d+[A-Za-z0-9 ]*)',r'(Google Tensor\s*G?\d*)'],text)
 d['gpu']=first([r'GPU\s*[:\-]?\s*(Adreno\s*\d+[A-Za-z0-9 ]*)',r'GPU\s*[:\-]?\s*(Mali-[A-Za-z0-9 -]+)',r'(Immortalis-[A-Za-z0-9 -]+)'],text)
 d['ram_gb']=first([r'(?:RAM|Memory)\s*[:\-]?\s*(\d{1,2}\s*GB)',r'\b(\d{1,2}\s*GB)\s+RAM\b'],text)
 d['storage_gb']=first([r'(?:Internal|Storage)\s*[:\-]?\s*((?:\d+\s*(?:GB|TB))(?:\s*/\s*\d+\s*(?:GB|TB))*)'],text)
 d['display_inches']=num(first([r'(?:display|screen|size)[^0-9]{0,25}(\d\.\d{1,2})\s*(?:inch|\")',r'(\d\.\d{1,2})[”\"]'],text))
 d['display_type']=first([r'\b((?:Dynamic |Super )?AMOLED(?: 2X)?|LTPO OLED|OLED|IPS LCD|LCD)\b'],text)
 d['resolution']=first([r'(\d{3,4}\s*[x×]\s*\d{3,4})'],text)
 d['refresh_hz']=num(first([r'(\d{2,3})\s*Hz'],text),int)
 d['rear_cameras']=first([r'(?:rear|main|primary) camera[^0-9]{0,25}((?:\d{1,3}(?:\.\d)?\s*MP)(?:[^.;]{0,100}))',r'camera[^0-9]{0,15}(\d{1,3}(?:\.\d)?\s*MP[^.;]{0,100})'],text)
 d['front_camera']=first([r'(?:front|selfie) camera[^0-9]{0,25}(\d{1,3}(?:\.\d)?\s*MP[^.;]{0,60})'],text)
 d['battery_mah']=num(first([r'(\d{3,5})\s*mAh'],text),int)
 d['wired_charge_w']=num(first([r'(?:wired|fast|charging|charge)[^0-9]{0,20}(\d{1,3}(?:\.\d)?)\s*W'],text))
 d['wireless_charge_w']=num(first([r'(?:wireless charging|wireless charge)[^0-9]{0,20}(\d{1,3}(?:\.\d)?)\s*W'],text))
 d['weight_g']=num(first([r'(?:weight|peso)[^0-9]{0,10}(\d{2,3}(?:\.\d)?)\s*g\b'],text))
 dims=first([r'(\d{2,3}(?:\.\d)?\s*[x×]\s*\d{2,3}(?:\.\d)?\s*[x×]\s*\d{1,2}(?:\.\d)?)\s*mm'],text)
 if dims:
  z=re.split(r'\s*[x×]\s*',dims); d['height_mm'],d['width_mm'],d['thickness_mm']=map(float,z)
 d['ip_rating']=first([r'\b(IP[5-6][0-9K]?)\b'],text)
 d['bluetooth']=first([r'Bluetooth\s*(?:v|version)?\s*(\d(?:\.\d)?)'],text)
 d['wifi']=first([r'(Wi[‑-]?Fi\s*(?:6E|7|6|5))'],text)
 d['nfc']='Sí' if re.search(r'\bNFC\b',text,re.I) else None
 d['esim']='Sí' if re.search(r'\beSIM\b',text,re.I) else None
 d['network']='5G' if re.search(r'\b5G\b',text) else ('4G LTE' if re.search(r'\b(?:4G|LTE)\b',text) else None)
 d['os_initial']=first([r'\b(Android\s*\d{1,2})\b',r'\b(iOS\s*\d{1,2})\b'],text)
 d['ui_skin']=first([r'\b(One UI\s*\d+(?:\.\d)?)\b',r'\b(HyperOS\s*\d+(?:\.\d)?)\b',r'\b(ColorOS\s*\d+(?:\.\d)?)\b',r'\b(MagicOS\s*\d+(?:\.\d)?)\b',r'\b(OxygenOS\s*\d+(?:\.\d)?)\b'],text)
 d['support_years']=num(first([r'(\d)\s+years?\s+(?:of\s+)?(?:OS|Android|software|security)\s+updates?',r'(\d)\s+años?\s+de\s+(?:actualizaciones|soporte)'],text))
 return {k:v for k,v in d.items() if v not in (None,'')}

def import_phone(query):
 brand=brand_of(query); domains=official_domains(brand); candidates=[]
 searches=[]
 if domains: searches.append(query+' specifications site:'+domains[0])
 searches += [query+' specifications phone', query+' specs GSMArena']
 seen=set()
 for sq in searches:
  try:
   for x in search_web(sq,6):
    if x['url'] not in seen: seen.add(x['url']); candidates.append(x)
  except Exception: pass
 texts=[]
 for x in candidates[:10]:
  try:
   t=fetch_text(x['url'])
   if len(t)>500: texts.append((x,t))
  except Exception: pass
 if not texts: raise RuntimeError('No se pudieron leer fuentes de Internet para este modelo.')
 # merge fields, official first
 def score(item): return 0 if any(d in urllib.parse.urlparse(item[0]['url']).netloc for d in domains) else 1
 texts.sort(key=score); merged={}; sources=[]
 for x,t in texts:
  specs=parse_specs(t,query)
  for k,v in specs.items(): merged.setdefault(k,v)
  sources.append((x,t[:1200],score((x,t))==0))
 # model cleaned conservatively
 model=query.strip();
 for prefix in [brand]:
  if model.lower().startswith(prefix.lower()+' '): model=model[len(prefix):].strip()
 c=db(); row=c.execute('SELECT id FROM brands WHERE lower(name)=lower(?)',(brand,)).fetchone()
 if not row:
  c.execute('INSERT INTO brands(name,slug) VALUES(?,?)',(brand,re.sub(r'\W+','-',brand.lower()))); bid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
 else: bid=row['id']
 slug=re.sub(r'[^a-z0-9]+','-',(brand+'-'+model).lower()).strip('-')
 merged.update({'brand_id':bid,'model':model,'slug':slug,'source_url':sources[0][0]['url'],'source_name':urllib.parse.urlparse(sources[0][0]['url']).netloc,'verification_status':'official+web' if sources[0][2] else 'web-crosscheck','verified_at':now()})
 cols=list(merged); vals=[merged[k] for k in cols]
 existing=c.execute('SELECT id FROM phones WHERE slug=?',(slug,)).fetchone()
 if existing:
  pid=existing['id']; sets=','.join(f'{k}=?' for k in cols if k not in ('brand_id','model','slug'))
  upd=[merged[k] for k in cols if k not in ('brand_id','model','slug')]; c.execute(f'UPDATE phones SET {sets},updated_at=CURRENT_TIMESTAMP WHERE id=?',upd+[pid])
 else:
  c.execute('INSERT INTO phones('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',vals); pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
 c.execute('DELETE FROM phone_sources WHERE phone_id=?',(pid,))
 for x,excerpt,official in sources[:6]: c.execute('INSERT INTO phone_sources(phone_id,url,title,domain,is_official,fetched_at,raw_excerpt) VALUES(?,?,?,?,?,?,?)',(pid,x['url'],x['title'],urllib.parse.urlparse(x['url']).netloc,1 if official else 0,now(),excerpt))
 c.commit(); phone=dict(c.execute('SELECT p.*,b.name brand FROM phones p JOIN brands b ON b.id=p.brand_id WHERE p.id=?',(pid,)).fetchone()); phone['sources']=[dict(r) for r in c.execute('SELECT url,title,domain,is_official,fetched_at FROM phone_sources WHERE phone_id=?',(pid,))]; c.close(); return phone

PAGE='''<!doctype html><html lang=es><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>PhoneCatalog V2</title><style>
body{font-family:system-ui;margin:0;background:#f4f6f8;color:#17202a}header{background:#0f172a;color:white;padding:22px}main{max-width:1280px;margin:auto;padding:20px}.search{display:flex;gap:8px;flex-wrap:wrap}.search input{flex:1;min-width:300px}.btn,input,select{padding:11px;border:1px solid #cbd5e1;border-radius:9px}.btn{background:#0f172a;color:#fff;cursor:pointer}.green{background:#047857}.card{background:#fff;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 1px 4px #0002}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.muted{color:#64748b}.pill{background:#e2e8f0;border-radius:999px;padding:3px 8px;font-size:12px}table{width:100%;border-collapse:collapse;background:white}th,td{border:1px solid #ddd;padding:8px;text-align:left}.status{padding:10px;margin-top:10px;border-radius:8px;background:#e0f2fe}.comparebar{position:sticky;bottom:10px;background:#fff;padding:10px;border-radius:12px;box-shadow:0 2px 12px #0003}</style></head><body><header><h1>PhoneCatalog V2 · Internet</h1><div>Busca en Internet → contrasta fuentes → guarda automáticamente → compara</div></header><main>
<div class=card><div class=search><input id=q placeholder="Ej.: Samsung Galaxy A54 5G, iPhone 15 Pro, Redmi Note 13 Pro"><button class="btn green" onclick=internet()>BUSCAR EN INTERNET Y GUARDAR</button><button class=btn onclick=local()>Buscar guardados</button></div><div id=status class="status" style="display:none"></div></div>
<div class=search><select id=brand onchange=local()><option value="">Todas las marcas</option></select><select id=year onchange=local()><option value="">Todos los años</option></select></div><div id=results></div><div class=comparebar><b>Comparar:</b> marca hasta 4 equipos <button class=btn onclick=compare()>Comparar seleccionados</button><div id=comparison></div></div>
<script>
let selected=new Set();async function setup(){let b=await(await fetch('/api/brands')).json();b.forEach(x=>brand.add(new Option(x.name,x.id)));for(let y=2026;y>=2018;y--)year.add(new Option(y,y));local()}
function esc(s){return String(s??'-').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function card(p){return `<div class=card><label><input type=checkbox onchange="pick(${p.id},this.checked)"> Comparar</label> <b>#${p.id} ${esc(p.brand)} ${esc(p.model)}</b> <span class=pill>${esc(p.release_year||'año s/d')}</span><div class=grid><div><b>Procesador:</b> ${esc(p.chipset)}<br><b>CPU:</b> ${esc(p.cpu)}<br><b>GPU:</b> ${esc(p.gpu)}<br><b>RAM:</b> ${esc(p.ram_gb)}<br><b>Almacenamiento:</b> ${esc(p.storage_gb)}</div><div><b>Pantalla:</b> ${esc(p.display_inches)}” ${esc(p.display_type)}<br><b>Resolución:</b> ${esc(p.resolution)}<br><b>Refresco:</b> ${esc(p.refresh_hz)} Hz<br><b>Cámara:</b> ${esc(p.rear_cameras)}<br><b>Frontal:</b> ${esc(p.front_camera)}</div><div><b>Batería:</b> ${esc(p.battery_mah)} mAh<br><b>Carga:</b> ${esc(p.wired_charge_w)} W<br><b>Inalámbrica:</b> ${esc(p.wireless_charge_w)} W<br><b>Sistema:</b> ${esc(p.os_initial)} ${esc(p.ui_skin)}<br><b>Soporte:</b> ${esc(p.support_years)} años</div><div><b>Dimensiones:</b> ${esc(p.height_mm)}×${esc(p.width_mm)}×${esc(p.thickness_mm)} mm<br><b>Peso:</b> ${esc(p.weight_g)} g<br><b>IP:</b> ${esc(p.ip_rating)}<br><b>Red:</b> ${esc(p.network)}<br><b>Fuente principal:</b> ${esc(p.source_name)}<br><small>${esc(p.verified_at)}</small></div></div></div>`}
async function local(){let u=new URL('/api/phones',location.origin);if(q.value)u.searchParams.set('q',q.value);if(brand.value)u.searchParams.set('brand_id',brand.value);if(year.value)u.searchParams.set('year',year.value);let d=await(await fetch(u)).json();results.innerHTML=d.length?d.map(card).join(''):'<div class=card>No está guardado. Escribe el modelo y pulsa <b>BUSCAR EN INTERNET Y GUARDAR</b>.</div>'}
async function internet(){if(!q.value.trim())return alert('Escribe marca y modelo.');status.style.display='block';status.textContent='Buscando y contrastando fuentes de Internet. Puede tardar unos segundos...';try{let r=await fetch('/api/internet/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q.value})});let d=await r.json();if(!r.ok)throw Error(d.error||'Error');status.innerHTML='Guardado automáticamente: <b>'+esc(d.brand+' '+d.model)+'</b> · '+(d.sources?.length||0)+' fuentes consultadas.';await local()}catch(e){status.textContent='No se pudo importar: '+e.message}}
function pick(id,on){if(on){if(selected.size>=4){event.target.checked=false;return alert('Máximo 4 celulares.')}selected.add(id)}else selected.delete(id)}
async function compare(){if(selected.size<2)return alert('Selecciona al menos 2.');let d=await(await fetch('/api/compare?ids='+[...selected].join(','))).json();let f=['release_year','chipset','gpu','ram_gb','storage_gb','display_inches','display_type','resolution','refresh_hz','rear_cameras','front_camera','battery_mah','wired_charge_w','wireless_charge_w','os_initial','ui_skin','support_years','weight_g','ip_rating','network'];comparison.innerHTML='<table><tr><th>Dato</th>'+d.map(x=>'<th>'+esc(x.brand+' '+x.model)+'</th>').join('')+'</tr>'+f.map(k=>'<tr><th>'+k+'</th>'+d.map(x=>'<td>'+esc(x[k])+'</td>').join('')+'</tr>').join('')+'</table>'}
setup()</script></main></body></html>'''

@app.route('/')
def home():return render_template_string(PAGE)
@app.route('/api/brands')
def brands():
 c=db();r=[dict(x) for x in c.execute('SELECT * FROM brands ORDER BY name')];c.close();return jsonify(r)
@app.route('/api/phones')
def phones():
 c=db();sql='SELECT p.*,b.name brand FROM phones p JOIN brands b ON b.id=p.brand_id WHERE 1=1';v=[]
 if request.args.get('q'):
  z='%'+request.args['q']+'%';sql+=' AND (p.model LIKE ? OR b.name LIKE ? OR p.chipset LIKE ? OR p.gpu LIKE ?)';v += [z,z,z,z]
 if request.args.get('brand_id'):sql+=' AND p.brand_id=?';v.append(request.args['brand_id'])
 if request.args.get('year'):sql+=' AND p.release_year=?';v.append(request.args['year'])
 sql+=' ORDER BY p.release_year DESC,b.name,p.model LIMIT 500';r=[dict(x) for x in c.execute(sql,v)];c.close();return jsonify(r)
@app.route('/api/internet/import',methods=['POST'])
def internet_import():
 q=(request.json or {}).get('query','').strip()
 if len(q)<3:return jsonify(error='Escribe una marca y modelo específicos.'),400
 try:return jsonify(import_phone(q))
 except Exception as e:return jsonify(error=str(e)),502
@app.route('/api/compare')
def compare_api():
 ids=[x for x in request.args.get('ids','').split(',') if x.isdigit()][:4]
 if not ids:return jsonify([])
 c=db();ph=','.join('?'*len(ids));rows=[dict(x) for x in c.execute(f'SELECT p.*,b.name brand FROM phones p JOIN brands b ON b.id=p.brand_id WHERE p.id IN ({ph})',ids)];c.close();return jsonify(rows)
@app.route('/api/updater/run',methods=['POST'])
def updater():
 c=db(); models=[(r['brand']+' '+r['model']) for r in c.execute('SELECT p.model,b.name brand FROM phones p JOIN brands b ON b.id=p.brand_id ORDER BY p.updated_at ASC LIMIT 10')];c.close();ok=0;errs=[]
 for m in models:
  try:import_phone(m);ok+=1
  except Exception as e:errs.append(m+': '+str(e))
 return jsonify(updated=ok,errors=errs,status='completed')

if __name__=='__main__':init_db();app.run(host='127.0.0.1',port=5050,debug=False)
