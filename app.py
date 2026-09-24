
from flask import Flask, request, redirect, url_for, session, render_template_string, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, math
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY","ticso-demo-secret")
DB="ticso.db"
ORIGINS=["ATLAS","NODUS","CARGA GLOBAL","FORZA"]
REQUIRED=["Embarque","Código","Descripción","Ubicación","Teórico","Precio","Costo"]

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def init():
    c=conn(); q=c.cursor()
    q.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,name TEXT,role TEXT,password_hash TEXT);
    CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,name TEXT,client TEXT,origin TEXT,destination TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,project_id INTEGER,shipment TEXT,code TEXT,description TEXT,location TEXT,theoretical REAL,price REAL,cost REAL,physical REAL,location_ok INTEGER,status TEXT DEFAULT 'Pendiente',is_manual INTEGER DEFAULT 0,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS recounts(id INTEGER PRIMARY KEY,item_id INTEGER,assigned_to INTEGER,count_no INTEGER DEFAULT 2,quantity REAL,status TEXT DEFAULT 'Pendiente',created_at TEXT,completed_at TEXT);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,item_id INTEGER,user_id INTEGER,action TEXT,old_value TEXT,new_value TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS locks(item_id INTEGER PRIMARY KEY,user_id INTEGER,expires_at TEXT);
    """)
    for u,n,r in [("supervisor","Supervisor TICSO","supervisor"),("auxiliar","Auxiliar TICSO","auxiliar")]:
        if not q.execute("SELECT 1 FROM users WHERE username=?",(u,)).fetchone():
            q.execute("INSERT INTO users(username,name,role,password_hash) VALUES(?,?,?,?)",(u,n,r,generate_password_hash("ticso123")))
    c.commit(); c.close()
init()

def me():
    if not session.get("uid"): return None
    c=conn(); u=c.execute("SELECT * FROM users WHERE id=?",(session["uid"],)).fetchone(); c.close(); return u
def sup(): return me() and me()["role"]=="supervisor"

STYLE="""
<style>
:root{--n:#102f53;--b:#1769ff;--g:#159b55;--r:#dc3947;--bg:#f4f7fb;--p:#5a35d5}
*{box-sizing:border-box}body{margin:0;font-family:Arial;background:var(--bg);color:#17304d}
.side{position:fixed;inset:0 auto 0 0;width:230px;background:var(--n);color:white;padding:22px 14px}
.brand{font-size:23px;font-weight:800;margin-bottom:24px}.nav a{display:block;color:white;text-decoration:none;padding:12px;border-radius:9px;margin:4px 0}.nav a:hover{background:var(--b)}
.main{margin-left:230px}.top{height:64px;background:white;border-bottom:1px solid #dde4ed;padding:20px 28px;text-align:right}.content{padding:26px}
.card{background:white;border:1px solid #dde4ed;border-radius:14px;padding:18px;margin-bottom:15px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.k{font-size:13px;color:#65758c}.v{font-size:28px;font-weight:800;margin-top:6px}.good{color:var(--g)}.bad{color:var(--r)}.purple{color:var(--p)}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.field{display:flex;flex-direction:column;gap:6px;min-width:170px;flex:1}
input,select{padding:10px;border:1px solid #cfd8e4;border-radius:8px}.btn{padding:10px 14px;border:0;border-radius:8px;font-weight:700;cursor:pointer}.blue{background:var(--b);color:white}.green{background:var(--g);color:white}.light{background:#edf2f8}.red{background:var(--r);color:white}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:10px;border-bottom:1px solid #e5eaf0;text-align:left;font-size:13px}th{background:#eef3f8}
.badge{padding:5px 9px;border-radius:20px;font-weight:700;font-size:12px}.ok{background:#dff6e8;color:#126f40}.no{background:#fde3e5;color:#ad2430}.wait{background:#fff0c8;color:#8a6200}
.flash{padding:10px;border-radius:8px;background:#e4efff;margin-bottom:12px}
@media(max-width:900px){.side{width:80px}.brand{font-size:15px}.nav a{font-size:0}.nav a:before{content:"•";font-size:28px}.main{margin-left:80px}.grid{grid-template-columns:1fr 1fr}.content{padding:14px}}
</style>
"""

def page(title,body):
    u=me()
    if not u: return render_template_string(STYLE+body)
    nav = """
    <a href='/dashboard'>Dashboard</a><a href='/project'>Proyectos</a><a href='/count'>Conteo</a>
    <a href='/recounts'>Reconteos</a><a href='/audit'>Auditoría</a><a href='/reports'>Reportes</a>
    """ if u["role"]=="supervisor" else "<a href='/count'>Conteo</a><a href='/count?tab=recounts'>Reconteos asignados</a>"
    shell=f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title>{STYLE}</head>
    <body><aside class='side'><div class='brand'>TICSO<br><small>INVENTARIOS</small></div><nav class='nav'>{nav}<a href='/logout'>Cerrar sesión</a></nav></aside>
    <main class='main'><div class='top'>{u['name']} · {u['role'].capitalize()}</div><section class='content'>
    {{% with m=get_flashed_messages() %}}{{% for x in m %}}<div class='flash'>{{{{x}}}}</div>{{% endfor %}}{{% endwith %}}
    {body}</section></main></body></html>"""
    return render_template_string(shell)

@app.route("/",methods=["GET"])
def root(): return redirect("/dashboard" if sup() else "/count") if me() else redirect("/login")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=conn(); u=c.execute("SELECT * FROM users WHERE username=?",(request.form["username"],)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"],request.form["password"]):
            session["uid"]=u["id"]; return redirect("/")
        flash("Usuario o contraseña incorrectos")
    return page("Login","""
    <div style='min-height:100vh;display:flex;justify-content:center;align-items:center;background:linear-gradient(135deg,#102f53,#5a35d5)'>
    <div class='card' style='width:390px'><h1>TICSO Inventarios</h1><p>Inicia sesión</p>
    <form method='post'><div class='field'><label>Usuario</label><input name='username' required></div>
    <div class='field' style='margin-top:10px'><label>Contraseña</label><input name='password' type='password' required></div>
    <button class='btn blue' style='width:100%;margin-top:15px'>Ingresar</button></form>
    <p style='font-size:12px'>Supervisor: supervisor / ticso123<br>Auxiliar: auxiliar / ticso123</p></div></div>""")

@app.route("/logout")
def logout(): session.clear(); return redirect("/login")

@app.route("/dashboard")
def dashboard():
    if not sup(): return redirect("/count")
    c=conn(); p=c.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1").fetchone()
    st=dict(total=0,sq=0,diff=0,ira=0,prec=0,rec=0,manual=0,cost=0,price=0)
    if p:
        rows=c.execute("SELECT * FROM items WHERE project_id=?",(p["id"],)).fetchall()
        normal=[r for r in rows if not r["is_manual"]]; counted=[r for r in normal if r["physical"] is not None]
        st["total"]=len(normal); st["sq"]=sum(abs(r["physical"]-r["theoretical"])<1e-9 for r in counted); st["diff"]=len(counted)-st["sq"]
        st["ira"]=st["sq"]/len(counted)*100 if counted else 0
        loc=[r for r in counted if r["location_ok"] is not None]; st["prec"]=sum(r["location_ok"]==1 for r in loc)/len(loc)*100 if loc else 0
        st["manual"]=sum(r["is_manual"] for r in rows); st["cost"]=sum((r["physical"]-r["theoretical"])*(r["cost"] or 0) for r in counted)
        st["price"]=sum((r["physical"]-r["theoretical"])*(r["price"] or 0) for r in counted)
        st["rec"]=c.execute("SELECT COUNT(*) n FROM recounts rc JOIN items i ON i.id=rc.item_id WHERE i.project_id=? AND rc.status!='Finalizado'",(p["id"],)).fetchone()["n"]
    c.close()
    body=f"""<h1>Dashboard</h1><p>Resumen general del inventario</p><div class='grid'>
    <div class='card'><div class='k'>Total códigos</div><div class='v'>{st['total']}</div></div>
    <div class='card'><div class='k'>IRA</div><div class='v purple'>{st['ira']:.2f}%</div></div>
    <div class='card'><div class='k'>Precisión</div><div class='v good'>{st['prec']:.2f}%</div></div>
    <div class='card'><div class='k'>Reconteos pendientes</div><div class='v bad'>{st['rec']}</div></div>
    <div class='card'><div class='k'>Diferencias</div><div class='v bad'>{st['diff']}</div></div>
    <div class='card'><div class='k'>Sobrantes manuales</div><div class='v'>{st['manual']}</div></div>
    <div class='card'><div class='k'>Dif. acumulada a costo</div><div class='v'>Q{st['cost']:.2f}</div></div>
    <div class='card'><div class='k'>Dif. acumulada a precio</div><div class='v'>Q{st['price']:.2f}</div></div></div>"""
    return page("Dashboard",body)

@app.route("/project",methods=["GET","POST"])
def project():
    if not sup(): return redirect("/")
    if request.method=="POST":
        c=conn(); c.execute("INSERT INTO projects(name,client,origin,destination,created_at) VALUES(?,?,?,?,?)",(request.form["name"],"CEMACO",request.form["origin"],"NODUS",now())); c.commit(); pid=c.execute("SELECT last_insert_rowid() x").fetchone()["x"]; c.close()
        return redirect(f"/upload/{pid}")
    options="".join(f"<option>{o}</option>" for o in ORIGINS)
    return page("Proyecto",f"""<h1>Crear proyecto</h1><div class='card'><form method='post'><div class='row'>
    <div class='field'><label>Nombre</label><input name='name' value='Inventario Bodega Central' required></div>
    <div class='field'><label>Cliente</label><input value='CEMACO' disabled></div>
    <div class='field'><label>Bodega origen</label><select name='origin'>{options}</select></div>
    <div class='field'><label>Destino</label><input value='NODUS' disabled></div>
    <button class='btn blue'>Crear y cargar Excel</button></div></form></div>""")

@app.route("/upload/<int:pid>",methods=["GET","POST"])
def upload(pid):
    if not sup(): return redirect("/")
    if request.method=="POST":
        f=request.files.get("file")
        if not f: flash("Selecciona un Excel"); return redirect(request.url)
        try:
            # Detecta automáticamente la fila de encabezados dentro de las primeras 10 filas.
            raw = pd.read_excel(f, header=None)
            header_row = None
            for i in range(min(10, len(raw))):
                vals = [str(v).strip() if pd.notna(v) else "" for v in raw.iloc[i].tolist()]
                if all(col in vals for col in REQUIRED):
                    header_row = i
                    break
            if header_row is None:
                flash("No se encontraron los encabezados requeridos. Deben aparecer: "+", ".join(REQUIRED))
                return redirect(request.url)
            f.seek(0)
            df = pd.read_excel(f, header=header_row)
            df.columns = [str(c).strip() for c in df.columns]
        except Exception:
            flash("No se pudo leer el Excel. Verifica que sea un archivo .xlsx válido.")
            return redirect(request.url)
        missing=[x for x in REQUIRED if x not in df.columns]
        if missing: flash("Faltan columnas: "+", ".join(missing)); return redirect(request.url)
        errors=[]; rows=[]; seen=set()
        for idx,r in df[REQUIRED].iterrows():
            ship="" if pd.isna(r["Embarque"]) else str(r["Embarque"]).strip(); code="" if pd.isna(r["Código"]) else str(r["Código"]).strip()
            if not ship or not code or pd.isna(r["Teórico"]) or (ship,code) in seen: errors.append(idx+2); continue
            seen.add((ship,code))
            rows.append((pid,ship,code,str(r["Descripción"]) if pd.notna(r["Descripción"]) else "",str(r["Ubicación"]) if pd.notna(r["Ubicación"]) else "",float(r["Teórico"]),None if pd.isna(r["Precio"]) else float(r["Precio"]),None if pd.isna(r["Costo"]) else float(r["Costo"])))
        if errors: flash("Hay errores críticos en filas: "+", ".join(map(str,errors[:20]))); return redirect(request.url)
        c=conn(); c.execute("DELETE FROM items WHERE project_id=?",(pid,))
        c.executemany("INSERT INTO items(project_id,shipment,code,description,location,theoretical,price,cost) VALUES(?,?,?,?,?,?,?,?)",rows); c.commit(); c.close()
        flash(f"Excel cargado: {len(rows)} registros"); return redirect(f"/count?project_id={pid}")
    return page("Cargar Excel",f"""<h1>Cargar Excel</h1><div class='card'><p>Columnas requeridas: {", ".join(REQUIRED)}</p>
    <form method='post' enctype='multipart/form-data'><input type='file' name='file' accept='.xlsx,.xls' required> <button class='btn blue'>Validar y cargar</button></form></div>""")

@app.route("/count")
def count():
    u=me()
    if not u: return redirect("/login")
    c=conn(); ps=c.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    pid=request.args.get("project_id",type=int) or (ps[0]["id"] if ps else None); tab=request.args.get("tab","count")
    if tab=="recounts" and u["role"]=="auxiliar":
        rs=c.execute("""SELECT rc.id rid,i.* FROM recounts rc JOIN items i ON i.id=rc.item_id WHERE rc.assigned_to=? AND rc.status!='Finalizado'""",(u["id"],)).fetchall(); c.close()
        trs="".join(f"<tr><td>{r['shipment']}</td><td>{r['code']}</td><td>{r['description']}</td><td>{r['location']}</td><td><input id='rq{r['rid']}' type='number'></td><td><button class='btn blue' onclick='saveR({r['rid']})'>Guardar</button></td></tr>" for r in rs)
        return page("Reconteos",f"""<h1>Reconteos asignados</h1><div class='card'><table><tr><th>Embarque</th><th>Código</th><th>Descripción</th><th>Ubicación</th><th>Reconteo</th><th></th></tr>{trs or "<tr><td colspan=6>No tienes reconteos asignados.</td></tr>"}</table></div>
        <script>async function saveR(id){{let q=document.getElementById('rq'+id).value;let r=await fetch('/api/recount/'+id,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{quantity:q}})}});if(r.ok)location.reload();}}</script>""")
    ships=[x["shipment"] for x in c.execute("SELECT DISTINCT shipment FROM items WHERE project_id=? ORDER BY shipment",(pid,)).fetchall()] if pid else []
    ship=request.args.get("shipment") or (ships[0] if ships else None)
    rows=c.execute("SELECT * FROM items WHERE project_id=? AND shipment=? ORDER BY code",(pid,ship)).fetchall() if pid and ship else []; c.close()
    opts="".join(f"<option {'selected' if s==ship else ''}>{s}</option>" for s in ships)
    trs=""
    for r in rows:
        theo=f"<td>{r['theoretical']}</td>" if u["role"]=="supervisor" else ""
        diff=f"<td id='d{r['id']}'>{'' if r['physical'] is None else r['physical']-r['theoretical']}</td>" if u["role"]=="supervisor" else ""
        disabled="disabled" if r["status"]=="Auditado" and u["role"]!="supervisor" else ""
        trs+=f"""<tr><td>{r['code']}</td><td>{r['description']}</td><td>{r['location']}</td>{theo}
        <td><input id='p{r['id']}' type='number' value='{"" if r["physical"] is None else r["physical"]}' {disabled} onfocus='lock({r["id"]},this)' onchange='save({r["id"]})'></td>
        <td><input id='l{r['id']}' type='checkbox' {'checked' if r['location_ok']==1 else ''} {disabled} onchange='save({r["id"]})'></td>{diff}<td id='s{r["id"]}'>{r["status"]}</td></tr>"""
    heads="<th>Teórico</th>" if u["role"]=="supervisor" else ""; dh="<th>Diferencia</th>" if u["role"]=="supervisor" else ""
    manual = f"""<button type='button' class='btn light' onclick="document.getElementById('m').style.display='block'">+ Ingresar código manual</button>
    <div id='m' class='card' style='display:none;margin-top:12px'>
      <h3>Ingresar código manual</h3>
      <div class='row'>
        <input id='ms' placeholder='Embarque' value='{ship or ""}'>
        <input id='mc' placeholder='Código'>
        <input id='md' placeholder='Descripción'>
        <input id='ml' placeholder='Ubicación'>
        <input id='mq' type='number' placeholder='Cantidad física'>
        <button type='button' class='btn green' onclick='manual()'>Agregar código</button>
      </div>
    </div>""" if pid else ""
    return page("Conteo",f"""<h1>Conteo físico</h1><div class='card'><form method='get'><input type='hidden' name='project_id' value='{pid or ""}'><select name='shipment' onchange='this.form.submit()'>{opts}</select> {manual}</form></div>
    <div class='card'><table><tr><th>Código</th><th>Descripción</th><th>Ubicación</th>{heads}<th>Físico</th><th>Ubicación correcta</th>{dh}<th>Estado</th></tr>{trs}</table></div>
    <script>
    async function lock(id,e){{let r=await fetch('/api/lock/'+id,{{method:'POST'}});let d=await r.json();if(!d.ok){{e.blur();alert('Bloqueado por '+d.by)}}}}
    async function save(id){{let p=document.getElementById('p'+id).value;if(p==='')return;let l=document.getElementById('l'+id).checked;let r=await fetch('/api/count/'+id,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{physical:p,location_ok:l}})}});let d=await r.json();if(d.ok){{let s=document.getElementById('s'+id);s.innerText=d.status;let x=document.getElementById('d'+id);if(x)x.innerText=d.diff;}}}}
    async function manual(){{
      let shipment=document.getElementById('ms').value.trim();
      let code=document.getElementById('mc').value.trim();
      let qty=document.getElementById('mq').value;
      if(!shipment){{alert('Ingresa el embarque');return;}}
      if(!code){{alert('Ingresa el código');return;}}
      if(qty===''){{alert('Ingresa la cantidad física');return;}}
      let r=await fetch('/api/manual',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{project_id:{pid or 0},shipment:shipment,code:code,description:md.value,location:ml.value,physical:qty}})}});
      let d=await r.json();
      if(d.ok)location.href='/count?project_id={pid or 0}&shipment='+encodeURIComponent(shipment);else alert(d.message);
    }}
    </script>""")

@app.route("/api/lock/<int:i>",methods=["POST"])
def lock(i):
    u=me(); c=conn(); c.execute("DELETE FROM locks WHERE expires_at<?",(now(),)); x=c.execute("SELECT l.*,u.name FROM locks l JOIN users u ON u.id=l.user_id WHERE item_id=?",(i,)).fetchone()
    if x and x["user_id"]!=u["id"]: c.close(); return jsonify(ok=False,by=x["name"])
    exp=(datetime.now()+timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S"); c.execute("INSERT OR REPLACE INTO locks VALUES(?,?,?)",(i,u["id"],exp)); c.commit(); c.close(); return jsonify(ok=True)

@app.route("/api/count/<int:i>",methods=["POST"])
def save_count(i):
    u=me(); d=request.get_json(); qty=float(d["physical"]); c=conn(); r=c.execute("SELECT * FROM items WHERE id=?",(i,)).fetchone()
    if r["status"]=="Auditado" and u["role"]!="supervisor": c.close(); return jsonify(ok=False),403
    diff=qty-r["theoretical"]; cd=diff*(r["cost"] or 0); status="Cuadrado" if abs(diff)<1e-9 else ("Positiva" if diff>0 else "Negativa")
    c.execute("UPDATE items SET physical=?,location_ok=?,status=?,updated_at=? WHERE id=?",(qty,1 if d.get("location_ok") else 0,status,now(),i))
    if abs(cd)>500 and not c.execute("SELECT 1 FROM recounts WHERE item_id=? AND status!='Finalizado'",(i,)).fetchone(): c.execute("INSERT INTO recounts(item_id,count_no,created_at) VALUES(?,2,?)",(i,now()))
    c.execute("INSERT INTO history(item_id,user_id,action,old_value,new_value,created_at) VALUES(?,?,?,?,?,?)",(i,u["id"],"Conteo actualizado",r["physical"],qty,now())); c.execute("DELETE FROM locks WHERE item_id=?",(i,)); c.commit(); c.close()
    return jsonify(ok=True,diff=diff,status=status)

@app.route("/api/manual",methods=["POST"])
def manual():
    u=me(); d=request.get_json(); c=conn()
    if c.execute("SELECT 1 FROM items WHERE project_id=? AND shipment=? AND code=?",(d["project_id"],d["shipment"],d["code"])).fetchone(): c.close(); return jsonify(ok=False,message="El código ya existe en la data")
    c.execute("INSERT INTO items(project_id,shipment,code,description,location,theoretical,physical,status,is_manual,updated_at) VALUES(?,?,?,?,?,0,?,'Sobrante',1,?)",(d["project_id"],d["shipment"],d["code"],d.get("description",""),d.get("location",""),float(d["physical"]),now())); c.commit(); c.close(); return jsonify(ok=True)

@app.route("/recounts",methods=["GET","POST"])
def recounts():
    if not sup(): return redirect("/")
    c=conn()
    if request.method=="POST": c.execute("UPDATE recounts SET assigned_to=?,status='Asignado' WHERE id=?",(request.form["assigned_to"],request.form["rid"])); c.commit()
    rs=c.execute("""SELECT rc.*,i.shipment,i.code,i.description,i.theoretical,i.physical,i.cost,u.name aname FROM recounts rc JOIN items i ON i.id=rc.item_id LEFT JOIN users u ON u.id=rc.assigned_to WHERE rc.status!='Finalizado'""").fetchall()
    aux=c.execute("SELECT * FROM users WHERE role='auxiliar'").fetchall(); c.close()
    trs=""
    for r in rs:
        opts="".join(f"<option value='{a['id']}'>{a['name']}</option>" for a in aux); cd=(r["physical"]-r["theoretical"])*(r["cost"] or 0)
        trs+=f"<tr><td>{r['shipment']}</td><td>{r['code']}</td><td>{r['description']}</td><td>{r['physical']}</td><td>Q{cd:.2f}</td><td>{r['aname'] or 'Pendiente'}</td><td><form method='post'><input type='hidden' name='rid' value='{r['id']}'><select name='assigned_to'>{opts}</select><button class='btn blue'>Asignar</button></form></td></tr>"
    return page("Reconteos",f"<h1>Reconteos</h1><p>Automáticos si |diferencia a costo| &gt; Q500.</p><div class='card'><table><tr><th>Embarque</th><th>Código</th><th>Descripción</th><th>Conteo</th><th>Dif. costo</th><th>Asignado</th><th>Acción</th></tr>{trs or '<tr><td colspan=7>No hay reconteos pendientes.</td></tr>'}</table></div>")

@app.route("/api/recount/<int:rid>",methods=["POST"])
def save_recount(rid):
    u=me(); d=request.get_json(); c=conn(); r=c.execute("SELECT * FROM recounts WHERE id=?",(rid,)).fetchone()
    if u["role"]=="auxiliar" and r["assigned_to"]!=u["id"]: c.close(); return jsonify(ok=False),403
    q=float(d["quantity"]); c.execute("UPDATE recounts SET quantity=?,status='Finalizado',completed_at=? WHERE id=?",(q,now(),rid)); c.execute("INSERT INTO history(item_id,user_id,action,new_value,created_at) VALUES(?,?,?,?,?)",(r["item_id"],u["id"],"Reconteo",q,now())); c.commit(); c.close(); return jsonify(ok=True)

@app.route("/audit",methods=["GET","POST"])
def audit():
    if not sup(): return redirect("/")
    c=conn()
    if request.method=="POST":
        i=int(request.form["item"]); dec=request.form["decision"]; it=c.execute("SELECT * FROM items WHERE id=?",(i,)).fetchone(); rr=c.execute("SELECT * FROM recounts WHERE item_id=? AND quantity IS NOT NULL ORDER BY count_no",(i,)).fetchall()
        if dec=="third": c.execute("INSERT INTO recounts(item_id,count_no,created_at) VALUES(?,3,?)",(i,now())); c.commit()
        else:
            final=it["physical"] if dec=="original" else rr[-1]["quantity"]; c.execute("UPDATE items SET physical=?,status='Auditado',updated_at=? WHERE id=?",(final,now(),i)); c.execute("INSERT INTO history(item_id,user_id,action,new_value,created_at) VALUES(?,?,?,?,?)",(i,me()["id"],"Auditado",final,now())); c.commit()
    rs=c.execute("""SELECT i.*,r.quantity rq FROM items i JOIN recounts r ON r.item_id=i.id WHERE r.status='Finalizado' AND i.status!='Auditado' ORDER BY r.completed_at DESC""").fetchall(); c.close()
    trs="".join(f"<tr><td>{r['shipment']}</td><td>{r['code']}</td><td>{r['physical']}</td><td>{r['rq']}</td><td><form method='post'><input type='hidden' name='item' value='{r['id']}'><button class='btn light' name='decision' value='original'>Aceptar original</button> <button class='btn blue' name='decision' value='recount'>Aceptar reconteo</button> <button class='btn red' name='decision' value='third'>Tercer conteo</button></form></td></tr>" for r in rs)
    return page("Auditoría",f"<h1>Auditoría</h1><div class='card'><table><tr><th>Embarque</th><th>Código</th><th>Original</th><th>Reconteo</th><th>Decisión</th></tr>{trs or '<tr><td colspan=5>No hay auditorías pendientes.</td></tr>'}</table></div>")

@app.route("/reports")
def reports():
    if not sup(): return redirect("/")
    c=conn(); p=c.execute("SELECT * FROM projects ORDER BY id DESC LIMIT 1").fetchone()
    if not p: c.close(); return page("Reportes","<h1>Reportes</h1><div class='card'>No hay proyectos.</div>")
    rows=c.execute("SELECT * FROM items WHERE project_id=?",(p["id"],)).fetchall(); normal=[r for r in rows if not r["is_manual"]]; counted=[r for r in normal if r["physical"] is not None]; sq=sum(abs(r["physical"]-r["theoretical"])<1e-9 for r in counted); ira=sq/len(counted)*100 if counted else 0
    loc=[r for r in counted if r["location_ok"] is not None]; prec=sum(r["location_ok"]==1 for r in loc)/len(loc)*100 if loc else 0; pieces=sum(abs(r["physical"]-r["theoretical"]) for r in counted); cost=sum((r["physical"]-r["theoretical"])*(r["cost"] or 0) for r in counted); price=sum((r["physical"]-r["theoretical"])*(r["price"] or 0) for r in counted)
    recs=c.execute("""SELECT i.id,i.physical,GROUP_CONCAT(rc.quantity) q FROM items i JOIN recounts rc ON rc.item_id=i.id WHERE i.project_id=? AND rc.quantity IS NOT NULL GROUP BY i.id""",(p["id"],)).fetchall(); hit=0
    for r in recs:
        vals=[r["physical"]]+[float(x) for x in (r["q"] or "").split(",") if x]; hit+=1 if any(vals.count(v)>=2 for v in set(vals)) else 0
    moda=hit/len(recs)*100 if recs else 0; manual=[r for r in rows if r["is_manual"]]; c.close()
    mtrs="".join(f"<tr><td>{r['shipment']}</td><td>{r['code']}</td><td>{r['description']}</td><td>{r['location']}</td><td>{r['physical']}</td></tr>" for r in manual)
    return page("Reportes",f"""<h1>Reportes consolidados</h1><div class='grid'>
    <div class='card'><div class='k'>IRA</div><div class='v purple'>{ira:.2f}%</div></div><div class='card'><div class='k'>Precisión</div><div class='v good'>{prec:.2f}%</div></div>
    <div class='card'><div class='k'>% Moda</div><div class='v good'>{moda:.2f}%</div></div><div class='card'><div class='k'>Diferencias piezas</div><div class='v bad'>{pieces}</div></div>
    <div class='card'><div class='k'>Dif. acumulada costo</div><div class='v'>Q{cost:.2f}</div></div><div class='card'><div class='k'>Dif. acumulada precio</div><div class='v'>Q{price:.2f}</div></div></div>
    <div class='card'><h3>Sobrantes / códigos no encontrados en data</h3><table><tr><th>Embarque</th><th>Código</th><th>Descripción</th><th>Ubicación</th><th>Cantidad</th></tr>{mtrs or '<tr><td colspan=5>Sin sobrantes manuales.</td></tr>'}</table></div>""")

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
