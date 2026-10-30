import os, sqlite3, uuid
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string, flash, send_from_directory
from werkzeug.utils import secure_filename

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
DB = os.environ.get("DATABASE_PATH", "app.db")
UPLOAD = os.environ.get("UPLOAD_FOLDER", "uploads")
os.makedirs(UPLOAD, exist_ok=True)
ALLOWED = {".pdf", ".txt", ".md"}

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS docs(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, stored TEXT NOT NULL,
            content TEXT NOT NULL, created TEXT NOT NULL)""")
init()

def extract(path, ext):
    if ext == ".pdf":
        if not PdfReader: raise ValueError("PDF support unavailable; install requirements.txt")
        reader = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    with open(path, "r", encoding="utf-8", errors="ignore") as f: return f.read()

def summarize(text):
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    return ". ".join(sentences[:3]) + ("." if sentences else "No readable text found.")

def actions(text):
    lines = [x.strip(" •-*") for x in text.splitlines() if x.strip()]
    hits = [x for x in lines if any(k in x.lower() for k in ["todo","action","must","should","deadline","submit","complete"])]
    return hits[:8] or ["No explicit action items detected. Review the document and add your own tasks."]

PAGE = """
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}}</title><style>
:root{--bg:#0b1020;--panel:#141d33;--muted:#9aa8c7;--ink:#edf2ff;--accent:#8b9cff;--line:#293653}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#1d2c55,transparent 35%),var(--bg);color:var(--ink);font:15px Inter,system-ui}
main{max-width:1050px;margin:36px auto;padding:0 20px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px}.brand{font-size:24px;font-weight:800;letter-spacing:-1px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:24px}
.card{background:#141d33dd;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 15px 45px #0003}
h1{font-size:34px;letter-spacing:-1.5px;margin:26px 0 8px}h2{font-size:18px;margin:0 0 15px}
input,textarea,button{font:inherit;border-radius:10px}input[type=file],input[type=text],textarea{width:100%;padding:12px;background:#0b1326;color:var(--ink);border:1px solid var(--line);margin:8px 0}
button,.btn{border:0;background:var(--accent);color:#0b1020;font-weight:750;padding:11px 16px;cursor:pointer;text-decoration:none;display:inline-block}
.item{border-top:1px solid var(--line);padding:13px 0}.item a{color:#b9c5ff;text-decoration:none;font-weight:700}
.small{font-size:13px}.pill{font-size:12px;color:#c8d2ff;background:#27345a;padding:4px 8px;border-radius:99px}
.flash{padding:12px;border-radius:10px;background:#25365b;margin:10px 0}
@media(max-width:700px){.grid{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}h1{font-size:28px}}
</style></head><body><main>
<div class="top"><div class="brand">◈ {{title}}</div><span class="pill">FREE • LOCAL INTELLIGENCE</span></div>
<h1>{{headline}}</h1><p class="muted">{{subtitle}}</p>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
{{body|safe}}
</main></body></html>
"""

@app.get("/")
def home():
    with db() as c: docs=c.execute("SELECT * FROM docs ORDER BY created DESC").fetchall()
    body = """
    <div class="grid"><section class="card"><h2>Upload a document</h2>
    <form method="post" action="/upload" enctype="multipart/form-data">
    <input type="file" name="file" accept=".pdf,.txt,.md" required><button>Upload document</button></form>
    <p class="muted small">PDF, TXT and Markdown. Processing runs locally; no external AI API is used.</p></section>
    <section class="card"><h2>Your library <span class="pill">{{count}} files</span></h2>
    {% for d in docs %}<div class="item"><a href="/doc/{{d['id']}}">{{d['name']}}</a><div class="muted small">{{d['created']}}</div></div>{% else %}<p class="muted">No documents yet. Upload one to get started.</p>{% endfor %}</section></div>
    """
    return render_template_string(PAGE, title="DocuMind AI", headline="Understand every document.", subtitle="A lightweight document intelligence workspace that works without paid AI keys.", body=render_template_string(body,docs=docs,count=len(docs)))

@app.post("/upload")
def upload():
    f=request.files.get("file")
    if not f or not f.filename: flash("Choose a file first."); return redirect("/")
    name=secure_filename(f.filename); ext=os.path.splitext(name)[1].lower()
    if ext not in ALLOWED: flash("Only PDF, TXT and MD files are supported."); return redirect("/")
    stored=str(uuid.uuid4())+ext; path=os.path.join(UPLOAD,stored); f.save(path)
    try: content=extract(path,ext)
    except Exception as e:
        os.remove(path); flash("Could not read file: "+str(e)); return redirect("/")
    if not content: content="[No selectable text found in this file. Scanned PDFs need OCR.]"
    with db() as c: c.execute("INSERT INTO docs VALUES(?,?,?,?,?)",(str(uuid.uuid4()),name,stored,content,datetime.utcnow().isoformat(timespec="minutes")))
    flash("Document uploaded and indexed."); return redirect("/")

@app.get("/doc/<doc_id>")
def detail(doc_id):
    with db() as c: d=c.execute("SELECT * FROM docs WHERE id=?",(doc_id,)).fetchone()
    if not d: return "Document not found",404
    body=render_template_string("""
    <div class="card"><a class="btn" href="/">← Library</a> <form style="display:inline" method="post" action="/delete/{{d['id']}}"><button>Delete</button></form>
    <h2 style="margin-top:20px">{{d['name']}}</h2><p class="muted small">{{d['created']}}</p>
    <h2>Quick summary</h2><p>{{summary}}</p><h2>Possible action items</h2><ul>{% for a in actions %}<li>{{a}}</li>{% endfor %}</ul>
    <h2>Ask this document</h2><form method="post" action="/ask/{{d['id']}}"><input type="text" name="question" placeholder="e.g. What is the deadline?" required><button>Find answer</button></form>
    {% if answer %}<div class="flash">{{answer}}</div>{% endif %}
    <h2>Extracted text preview</h2><pre style="white-space:pre-wrap;max-height:300px;overflow:auto;color:#cbd5ef">{{d['content'][:5000]}}</pre></div>
    """,d=d,summary=summarize(d["content"]),actions=actions(d["content"]),answer=request.args.get("answer"))
    return render_template_string(PAGE,title="DocuMind AI",headline="Document workspace",subtitle="Local extraction and transparent heuristic assistance.",body=body)

@app.post("/ask/<doc_id>")
def ask(doc_id):
    q=request.form.get("question","").strip()
    with db() as c: d=c.execute("SELECT * FROM docs WHERE id=?",(doc_id,)).fetchone()
    if not d:return "Not found",404
    terms=[w.lower() for w in q.split() if len(w)>3]
    chunks=[s.strip() for s in d["content"].replace("\n"," ").split(".") if s.strip()]
    ranked=sorted(chunks,key=lambda s:sum(t in s.lower() for t in terms),reverse=True)
    answer=(" ".join(ranked[:2])[:900] if ranked and terms and any(t in " ".join(ranked[:2]).lower() for t in terms) else "I couldn't find a direct matching passage. Try using key terms from the document.")
    from urllib.parse import quote
    return redirect(url_for("detail",doc_id=doc_id)+"?answer="+quote("Local keyword result (not generative AI): "+answer))

@app.post("/delete/<doc_id>")
def delete(doc_id):
    with db() as c:
        d=c.execute("SELECT stored FROM docs WHERE id=?",(doc_id,)).fetchone()
        if d:
            try: os.remove(os.path.join(UPLOAD,d["stored"]))
            except OSError: pass
            c.execute("DELETE FROM docs WHERE id=?",(doc_id,))
    flash("Document deleted."); return redirect("/")
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
