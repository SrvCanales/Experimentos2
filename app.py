"""Rectas y planos en R³ · visualizador interactivo (Streamlit + Plotly)."""
import json
import pathlib
import tempfile

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.offline import get_plotlyjs

try:  # opcional: permite graficar mientras se escribe (tecla a tecla)
    from st_keyup import st_keyup
except Exception:
    st_keyup = None

st.set_page_config(page_title="Rectas y planos en R³", page_icon="📐", layout="wide")

BG, DEEP, PANEL, LINE = "#12141c", "#0d0f16", "#181b26", "#272b3a"
TEXT, MUTED, SOL = "#eeeae2", "#8c92a4", "#e8b94e"
COLORS = ["#e0674f", "#3fa796", "#8b7fd6", "#d45a94"]
NAMES = {"punto": "Punto", "recta": "Recta", "plano": "Plano"}

st.markdown(
    f"""<style>
[data-testid="stSidebar"][aria-expanded="true"]{{min-width:400px}}
[data-testid="stSidebar"]{{border-right:1px solid {LINE}}}
.stButton>button{{width:100%;background:{DEEP};border:1px solid {LINE};color:{TEXT};border-radius:8px}}
.stButton>button:hover{{border-color:{SOL};color:{SOL}}}
.cab{{display:flex;align-items:center;gap:.55rem;font-weight:600;padding-top:.35rem}}
.dot{{width:.7rem;height:.7rem;border-radius:50%;display:inline-block}}
[data-baseweb="input"],[data-baseweb="base-input"]{{background:{DEEP}!important}}
footer,#MainMenu{{visibility:hidden}}
</style>""",
    unsafe_allow_html=True,
)


# ───────────────────── visor R³ persistente (no se reinicia) ─────────────────────
# Un componente propio mantiene el gráfico montado entre ejecuciones: cada cambio
# llega como datos nuevos y Plotly.react actualiza en el sitio, conservando la cámara.
_VIEW_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#12141c;overflow:hidden}#g{width:100%}</style>
<script src="plotly.min.js"></script></head><body><div id="g"></div><script>
const send=(t,d)=>window.parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
const gd=document.getElementById("g");
let cam=null,bound=false;
window.addEventListener("message",e=>{
  if(!e.data||e.data.type!=="streamlit:render")return;
  const a=e.data.args,fig=a.figure;
  gd.style.height=a.height+"px";
  if(cam)fig.layout.scene.camera=cam;
  Plotly.react(gd,fig.data,fig.layout,{displaylogo:false,responsive:true}).then(()=>{
    if(!bound){bound=true;
      gd.on("plotly_relayout",ev=>{if(ev["scene.camera"])cam=ev["scene.camera"];});}
    send("streamlit:setFrameHeight",{height:a.height});
  });
});
send("streamlit:componentReady",{apiVersion:1});
send("streamlit:setFrameHeight",{height:680});
</script></body></html>"""


@st.cache_resource
def _viewer():
    d = pathlib.Path(tempfile.gettempdir()) / "r3_viewer_v1"
    d.mkdir(exist_ok=True)
    js = d / "plotly.min.js"
    if not js.exists():
        js.write_text(get_plotlyjs(), encoding="utf-8")
    (d / "index.html").write_text(_VIEW_HTML, encoding="utf-8")
    return components.declare_component("r3_viewer", path=str(d))


ss = st.session_state
if "objs" not in ss:
    ss.objs = [{"id": 1, "kind": "plano", "n": 1}]
    ss.next_id = 2
    ss.counts = {"punto": 0, "recta": 0, "plano": 1}


def add(kind):
    ss.counts[kind] += 1
    ss.objs.append({"id": ss.next_id, "kind": kind, "n": ss.counts[kind]})
    ss.next_id += 1


def remove(oid):
    ss.objs = [o for o in ss.objs if o["id"] != oid]


# ───────────────────────── utilidades de texto ─────────────────────────
def g(x):
    return f"{x + 0.0:g}"


def vs(v):
    return "(" + ", ".join(g(c) for c in v) + ")"


def join_terms(items):
    """[(coef, cuerpo)] → 'x - 2y + 3' (LaTeX simple)."""
    s = ""
    for c, body in items:
        if abs(c) < 1e-12:
            continue
        m = abs(c)
        t = ("" if (body and abs(m - 1) < 1e-12) else f"{m:g}") + body
        if not s:
            s = ("-" if c < 0 else "") + t
        else:
            s += (" - " if c < 0 else " + ") + t
    return s or "0"


def shift(v, p):
    return v if abs(p) < 1e-12 else (f"{v}-{p:g}" if p > 0 else f"{v}+{-p:g}")


def sym_latex(P0, d):
    fr, ct = [], []
    for v, p, di in zip("xyz", P0, d):
        if abs(di) < 1e-12:
            ct.append(f"{v}={g(p)}")
        else:
            fr.append(r"\frac{" + shift(v, p) + "}{" + g(di) + "}")
    s = " = ".join(fr)
    if ct:
        s += (r",\quad " if s else "") + r",\ ".join(ct)
    return s


# ───────────────────────── entradas numéricas ─────────────────────────
def num(key, label, default):
    """Campo numérico. Con streamlit-keyup se actualiza en cada tecla."""
    if st_keyup is None:
        return st.number_input(label, value=float(default), step=1.0, format="%g", key=key)
    raw = st_keyup(label, value=g(default), key=key, debounce=150)
    try:
        v = float(str(raw).replace(",", ".").strip()) + 0.0
        if not np.isfinite(v):
            raise ValueError
        ss[key + "_ok"] = v
    except ValueError:
        v = ss.get(key + "_ok", float(default))
    return v


def nums(o, form, prefix, labels, defaults):
    cols = st.columns(len(labels))
    out = []
    for i, (c, lab, d) in enumerate(zip(cols, labels, defaults)):
        with c:
            out.append(num(f"{o['id']}_{form}_{prefix}{i}", lab, d))
    return np.array(out, float)


def nota(md):
    with st.expander("Interpretación", expanded=True):
        st.markdown(md)


# ───────────────────────── geometría y dibujo ─────────────────────────
CUBE = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
EDGES = [(i, j) for i in range(8) for j in range(i + 1, 8) if np.sum(CUBE[i] != CUBE[j]) == 1]


def clip_line(p, d, L):
    t0, t1 = -1e9, 1e9
    for k in range(3):
        if abs(d[k]) < 1e-12:
            if abs(p[k]) > L:
                return None
        else:
            a, b = sorted(((-L - p[k]) / d[k], (L - p[k]) / d[k]))
            t0, t1 = max(t0, a), min(t1, b)
    return (t0, t1) if t0 < t1 else None


def plane_polygon(n, d, L):
    """Corte del plano n·x = d con el cubo [-L, L]³."""
    nn = np.linalg.norm(n)
    n, d = n / nn, d / nn
    V = CUBE * L
    f = V @ n - d
    pts = [V[i] for i in range(8) if abs(f[i]) < 1e-9]
    for i, j in EDGES:
        if f[i] * f[j] < 0:
            pts.append(V[i] + f[i] / (f[i] - f[j]) * (V[j] - V[i]))
    if not pts:
        return None
    pts = np.unique(np.round(np.array(pts), 6), axis=0)
    if len(pts) < 3:
        return None
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(n, a)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    c = pts.mean(axis=0)
    ang = np.arctan2((pts - c) @ e2, (pts - c) @ e1)
    return pts[np.argsort(ang)]


def base_fig(L):
    """Ejes que cruzan en el origen, planos coordenados tenues: se ven los 8 octantes."""
    dt = 1 if L <= 8 else 2 if L <= 16 else 5
    ticks = [c for c in np.arange(-L, L + 1e-9, dt) if abs(c) > 1e-9]
    fig = go.Figure()
    for k in range(3):  # cuadrícula tenue en cada plano coordenado
        i, j = [m for m in range(3) if m != k]
        rows = []
        for c in np.arange(-L, L + 1e-9, dt):
            for s0, s1 in ((i, j), (j, i)):
                p, q = np.zeros(3), np.zeros(3)
                p[s0] = q[s0] = c
                p[s1], q[s1] = -L, L
                rows += [p, q, [np.nan] * 3]
        R = np.array(rows)
        fig.add_trace(go.Scatter3d(x=R[:, 0], y=R[:, 1], z=R[:, 2], mode="lines",
                                   line=dict(color=LINE, width=1), hoverinfo="skip"))
    for k, name in enumerate("xyz"):  # ejes completos (negativos y positivos)
        e = np.zeros(3)
        e[k] = 1
        add_arrow(fig, -L * e, 2 * L * e, MUTED, L, width=3)
        P = np.outer(ticks, e)
        fig.add_trace(go.Scatter3d(x=P[:, 0], y=P[:, 1], z=P[:, 2], mode="text",
                                   text=[f"{c:g}" for c in ticks], textposition="top center",
                                   textfont=dict(color=MUTED, size=9), hoverinfo="skip"))
        E = 1.1 * L * e
        fig.add_trace(go.Scatter3d(x=[E[0]], y=[E[1]], z=[E[2]], mode="text", text=[name],
                                   textfont=dict(color=TEXT, size=15), hoverinfo="skip"))
    hid = dict(visible=False, range=[-1.15 * L, 1.15 * L])
    fig.update_layout(
        paper_bgcolor=BG, margin=dict(l=0, r=0, t=0, b=0), height=680, showlegend=False,
        uirevision="r3",
        scene=dict(xaxis=hid, yaxis=hid, zaxis=hid, aspectmode="cube", bgcolor=BG,
                   uirevision="r3", camera=dict(eye=dict(x=1.5, y=1.5, z=0.9))),
    )
    return fig


def add_point(fig, p, color, text="", size=6, drop=False):
    if drop and abs(p[2]) > 1e-9:
        fig.add_trace(go.Scatter3d(x=[p[0]] * 2, y=[p[1]] * 2, z=[p[2], 0], mode="lines",
                                   line=dict(color=color, width=2, dash="dash"),
                                   opacity=0.6, hoverinfo="skip"))
    fig.add_trace(go.Scatter3d(x=[p[0]], y=[p[1]], z=[p[2]], mode="markers+text", text=[text],
                               textposition="top center", textfont=dict(color=color, size=12),
                               marker=dict(color=color, size=size), hoverinfo="skip"))


def add_line(fig, p, d, color, L, width=5):
    r = clip_line(p, d, L)
    if r is None:
        return False
    a, b = p + r[0] * d, p + r[1] * d
    fig.add_trace(go.Scatter3d(x=[a[0], b[0]], y=[a[1], b[1]], z=[a[2], b[2]], mode="lines",
                               line=dict(color=color, width=width), hoverinfo="skip"))
    return True


def add_plane(fig, n, d, color, L):
    poly = plane_polygon(n, d, L)
    if poly is None:
        return False
    m = len(poly)
    fig.add_trace(go.Mesh3d(x=poly[:, 0], y=poly[:, 1], z=poly[:, 2], i=[0] * (m - 2),
                            j=list(range(1, m - 1)), k=list(range(2, m)), color=color,
                            opacity=0.28, flatshading=True, hoverinfo="skip",
                            lighting=dict(ambient=1, diffuse=0, specular=0)))
    c = np.vstack([poly, poly[:1]])
    fig.add_trace(go.Scatter3d(x=c[:, 0], y=c[:, 1], z=c[:, 2], mode="lines",
                               line=dict(color=color, width=2), opacity=0.7, hoverinfo="skip"))
    return True


def add_arrow(fig, p, v, color, L, label=None, width=5):
    p, v = np.asarray(p, float), np.asarray(v, float)
    nv = np.linalg.norm(v)
    if nv < 1e-9:
        return
    q, u = p + v, v / nv
    h = min(0.10 * L, 0.35 * nv)
    a = np.array([1.0, 0, 0]) if abs(u[0]) < 0.9 else np.array([0, 1.0, 0])
    w1 = np.cross(u, a)
    w1 /= np.linalg.norm(w1)
    w2 = np.cross(u, w1)
    base, r, nan = q - h * u, 0.38 * h, [np.nan] * 3
    rows = [p, q, nan]
    for w in (w1, -w1, w2, -w2):
        rows += [q, base + r * w, nan]
    R = np.array(rows)
    fig.add_trace(go.Scatter3d(x=R[:, 0], y=R[:, 1], z=R[:, 2], mode="lines",
                               line=dict(color=color, width=width), hoverinfo="skip"))
    if label:
        fig.add_trace(go.Scatter3d(x=[q[0]], y=[q[1]], z=[q[2]], mode="text", text=[label],
                                   textposition="top center", textfont=dict(color=color, size=12),
                                   hoverinfo="skip"))


# ───────────────────────── objetos ─────────────────────────
def ui_punto(o, fig, L, color):
    p = nums(o, "pt", "p", ["x", "y", "z"], [2, 1, 3])
    st.latex(rf"P = ({g(p[0])},\ {g(p[1])},\ {g(p[2])})")
    add_point(fig, p, color, vs(p), size=7, drop=True)


def ui_recta(o, fig, L, color):
    form = st.radio("Forma", ["General", "Paramétrica", "Simétrica"], horizontal=True,
                    key=f"form_{o['id']}", label_visibility="collapsed")
    if form == "General":
        A, B, C, z0 = nums(o, "g", "c", ["A", "B", "C", "z₀"], [1, 1, -2, 0])
        st.latex(join_terms([(A, "x"), (B, "y"), (C, "")]) + " = 0")
        if np.hypot(A, B) < 1e-9:
            st.warning("A y B no pueden ser ambos 0.")
            return
        n2 = A * A + B * B
        foot = np.array([-C * A / n2, -C * B / n2, z0])
        if st.checkbox("Mostrar el plano vertical que define", key=f"{o['id']}_gv"):
            add_plane(fig, np.array([A, B, 0.0]), -C, color, L)
        if not add_line(fig, foot, np.array([-B, A, 0.0]), color, L):
            st.caption("La recta queda fuera de la ventana: cambia z₀ o amplía el alcance.")
        add_arrow(fig, foot, np.array([A, B, 0.0]) / np.sqrt(n2) * 0.3 * L, SOL, L, f"n = ({g(A)}, {g(B)})")
        dist = abs(C) / np.sqrt(n2)
        nota(
            rf"""- Los puntos $(x,y)$ que cumplen la ecuación forman una recta.
- **El vector $(A,B)=({g(A)},{g(B)})$ es normal a la recta**: es perpendicular a ella. Su dirección es $(-B,A)=({g(-B)},{g(A)})$.
- $C$ la desplaza: su distancia al origen es $\frac{{|C|}}{{\sqrt{{A^2+B^2}}}}={dist:.3g}$.
- En R³ la ecuación no tiene $z$, así que describe un plano vertical; la recta que ves es su corte con $z={g(z0)}$. La flecha amarilla marca la dirección de la normal."""
        )
        return

    key = "p" if form == "Paramétrica" else "s"
    st.caption("Punto P₀ de la recta")
    P0 = nums(o, key, "p", ["x₀", "y₀", "z₀"], [1, 0, 1])
    st.caption("Vector dirección d")
    d = nums(o, key, "d", ["a", "b", "c"], [1, 2, 1])
    if np.linalg.norm(d) < 1e-9:
        st.warning("El vector dirección no puede ser (0, 0, 0).")
        return
    add_line(fig, P0, d, color, L)
    add_point(fig, P0, color, "P₀", size=5)
    add_arrow(fig, P0, d, color, L, "d")

    if form == "Paramétrica":
        st.latex(rf"(x,y,z) = {vs(P0)} + t\,{vs(d)}".replace("(", r"\left(").replace(")", r"\right)"))
        t = st.slider("Parámetro t", -5.0, 5.0, 1.0, 0.1, key=f"{o['id']}_p_t")
        Pt = P0 + t * d
        add_point(fig, Pt, SOL, f"t = {g(t)}", size=8)
        nota(
            rf"""- $P_0$ es un punto de la recta y $\vec d$ su dirección: $P(t)=P_0+t\,\vec d$.
- Cada valor de $t$ da un punto distinto. $t=0$ es $P_0$; $t>0$ avanza en el sentido de $\vec d$ y $t<0$ retrocede.
- Con $t={g(t)}$ estás en $P={vs(Pt)}$ (punto amarillo). Mueve el deslizador y verás recorrer toda la recta."""
        )
    else:
        st.latex(sym_latex(P0, d))
        nota(
            rf"""- Sale de despejar $t$ en cada coordenada de la forma paramétrica e igualar: las fracciones valen lo mismo, ese $t$.
- Los denominadores $(a,b,c)={vs(d)}$ son el **vector dirección**; los números restados en el numerador son las coordenadas del punto $P_0={vs(P0)}$.
- Si una componente de $\vec d$ es $0$ no se puede dividir entre ella: esa coordenada es constante y se escribe aparte (por ejemplo $z=z_0$)."""
        )


def ui_plano(o, fig, L, color):
    form = st.radio("Forma", ["General", "Paramétrica", "Punto normal"], horizontal=True,
                    key=f"form_{o['id']}", label_visibility="collapsed")
    if form == "General":
        A, B, C, D = nums(o, "g", "c", ["A", "B", "C", "D"], [1, 1, 1, -3])
        st.latex(join_terms([(A, "x"), (B, "y"), (C, "z"), (D, "")]) + " = 0")
        n = np.array([A, B, C])
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            st.warning("A, B y C no pueden ser todos 0.")
            return
        p0 = -D * n / nn**2
        if not add_plane(fig, n, -D, color, L):
            st.caption("El plano queda fuera de la ventana: amplía el alcance.")
        add_arrow(fig, p0, n / nn * 0.3 * L, SOL, L, f"n = {vs(n)}")
        nota(
            rf"""- Los puntos $(x,y,z)$ que cumplen la ecuación forman un plano.
- **El vector $(A,B,C)={vs(n)}$ es normal al plano**: es perpendicular a todo vector contenido en él.
- $D$ lo desplaza: su distancia al origen es $\frac{{|D|}}{{|\vec n|}}={abs(D) / nn:.3g}$, y su punto más cercano al origen es ${vs(p0)}$."""
        )
        return

    key = "p" if form == "Paramétrica" else "n"
    st.caption("Punto P₀ del plano")
    P0 = nums(o, key, "p", ["x₀", "y₀", "z₀"], [1, 0, 1] if key == "p" else [1, 1, 1])
    if form == "Paramétrica":
        st.caption("Vectores directores u y v")
        u = nums(o, key, "u", ["u₁", "u₂", "u₃"], [1, 1, 0])
        v = nums(o, key, "v", ["v₁", "v₂", "v₃"], [0, 1, 1])
        n = np.cross(u, v)
        s_ = st.slider("Parámetro s", -3.0, 3.0, 1.0, 0.1, key=f"{o['id']}_p_s")
        t_ = st.slider("Parámetro t", -3.0, 3.0, 1.0, 0.1, key=f"{o['id']}_p_t")
        st.latex(rf"(x,y,z) = {vs(P0)} + s\,{vs(u)} + t\,{vs(v)}".replace("(", r"\left(").replace(")", r"\right)"))
        if np.linalg.norm(n) < 1e-9:
            st.warning("u y v no pueden ser paralelos (ni nulos): no generan un plano.")
            return
        add_plane(fig, n, n @ P0, color, L)
        add_arrow(fig, P0, u, color, L, "u")
        add_arrow(fig, P0, v, color, L, "v")
        A_ = P0 + s_ * u
        Pt = A_ + t_ * v
        fig.add_trace(go.Scatter3d(x=[P0[0], A_[0], Pt[0]], y=[P0[1], A_[1], Pt[1]], z=[P0[2], A_[2], Pt[2]],
                                   mode="lines", line=dict(color=SOL, width=3, dash="dash"), hoverinfo="skip"))
        add_point(fig, P0, color, "P₀", size=5)
        add_point(fig, Pt, SOL, f"s={g(s_)}, t={g(t_)}", size=8)
        D = -(n @ P0)
        nota(
            rf"""- $P_0$ es un punto del plano; $\vec u$ y $\vec v$ (no paralelos) marcan dos direcciones dentro de él: $P(s,t)=P_0+s\,\vec u+t\,\vec v$.
- $s$ dice cuánto avanzas en la dirección de $\vec u$ y $t$ cuánto en la de $\vec v$ (camino punteado amarillo). Al variar ambos recorres todo el plano.
- Un vector normal es $\vec u\times\vec v={vs(n)}$, así que el plano es ${join_terms([(n[0], "x"), (n[1], "y"), (n[2], "z"), (D, "")])}=0$."""
        )
        return

    n = nums(o, key, "n", ["a", "b", "c"], [1, 2, -1])
    if np.linalg.norm(n) < 1e-9:
        st.warning("El vector normal no puede ser (0, 0, 0).")
        return
    body = [(n[0], "(" + shift("x", P0[0]) + ")"), (n[1], "(" + shift("y", P0[1]) + ")"),
            (n[2], "(" + shift("z", P0[2]) + ")")]
    st.latex(join_terms(body) + " = 0")
    add_plane(fig, n, n @ P0, color, L)
    add_point(fig, P0, color, "P₀", size=5)
    add_arrow(fig, P0, n / np.linalg.norm(n) * 0.3 * L, SOL, L, f"n = {vs(n)}")
    D = -(n @ P0)
    nota(
        rf"""- Un punto $P$ está en el plano si el vector que va de $P_0$ a $P$ es **perpendicular a la normal**: $\vec n\cdot(P-P_0)=0$.
- Aquí $\vec n={vs(n)}$ (flecha amarilla) y $P_0={vs(P0)}$.
- Al desarrollar se obtiene la forma general con $(A,B,C)=\vec n$ y $D=-\vec n\cdot P_0={g(D)}$: ${join_terms([(n[0], "x"), (n[1], "y"), (n[2], "z"), (D, "")])}=0$."""
    )


RENDER = {"punto": ui_punto, "recta": ui_recta, "plano": ui_plano}

# ───────────────────────── interfaz ─────────────────────────
with st.sidebar:
    st.markdown("### Rectas y planos en R³")
    st.caption("Añade objetos y cambia sus valores: la gráfica se actualiza al momento.")
    cols = st.columns(3)
    for c, kind in zip(cols, ("punto", "recta", "plano")):
        with c:
            st.button(f"+ {NAMES[kind]}", key=f"add_{kind}", on_click=add, args=(kind,))
    if st_keyup is None:
        st.caption("Tip: instala `streamlit-keyup` para graficar mientras escribes (sin Enter).")
    L = st.slider("Alcance de los ejes (±)", 3, 20, 6)
    fig = base_fig(L)
    if not ss.objs:
        st.caption("Aún no hay objetos. Añade un punto, una recta o un plano.")
    for o in list(ss.objs):
        color = COLORS[(o["id"] - 1) % 4]
        with st.container(border=True):
            h1, h2, h3 = st.columns([5, 1, 1])
            vis = h2.toggle("Visible", value=True, key=f"vis_{o['id']}", label_visibility="collapsed",
                            help="Mostrar u ocultar en R³")
            h1.markdown(
                f'<div class="cab"><span class="dot" style="background:{color};opacity:{1 if vis else .3}"></span>'
                f'{NAMES[o["kind"]]} {o["n"]}</div>',
                unsafe_allow_html=True,
            )
            h3.button("✕", key=f"del_{o['id']}", on_click=remove, args=(o["id"],), help="Eliminar")
            RENDER[o["kind"]](o, fig if vis else go.Figure(), L, color)

_viewer()(figure=json.loads(fig.to_json()), height=680, key="r3")
st.caption("Arrastra para rotar · rueda o pellizco para acercar · las flechas amarillas son vectores normales.")
