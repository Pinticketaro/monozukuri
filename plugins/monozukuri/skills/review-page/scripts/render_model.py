"""立体モデル（STL / OBJ / 3MF / GLB / STEP）を影付きで描画して1枚のPNGにする。
モックでも、Fusion などで人が作ったモデルの書き出しでも同じように使える。

使い方
  python3 render_model.py --scene scene.json --out preview.png [--glb model.glb]
  python3 render_model.py frame.stl:#d9d4cb plate.stl:#bcd6e4:0.6 --out preview.png --title "v03 外観"

部品の指定は  ファイル[:色[:不透明度[:粗さ[:金属感]]]]  （色は #rrggbb、不透明度 0〜1）
scene.json の形
  {"title": "...", "up": "z", "views": ["iso", "back", "side"],
   "parts": [{"file": "parts/frame.stl", "name": "枠", "color": "#d9d4cb",
              "opacity": 1, "roughness": 0.8, "metalness": 0}]}
  file は scene.json からの相対パス。up はモデルの上方向（Fusion・多くのCADは z）。
  views に使える名前: iso（斜め上）, back（斜め後ろ）, front（正面）, side（右横）, top（真上）
  先頭のビューが大きく、残りが下に並ぶ。平行投影（front・side・top）は地面の影を描かず、
  ビューごとに枠いっぱいに合わせ、隅に縮尺の目安（例「目盛 20mm」）を入れる。
  --same-scale を付けると、平行投影のビューの縮尺をそろえる（真上と正面の大きさを見比べるとき）。
--glb を付けると、確認ページで回して見るための GLB も書き出す。

前提: setup スキルで trimesh・playwright・three.js を入れておく（STEP は cascadio も）
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading

import numpy as np
import trimesh

CACHE = os.environ.get("MONOZUKURI_CACHE", os.path.expanduser("~/.cache/monozukuri"))
VIEW_LABEL = {"iso": "斜め上から", "back": "斜め後ろから", "front": "正面から", "side": "右横から", "top": "真上から"}
BG = "#f4f5f2"


def hex2rgba(h, a=1.0):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [float(a)]


def parse_part(spec):
    bits = spec.split(":")
    # Windowsのドライブ名（C:\...）は使わない前提。ファイル名に : を含めない
    p = {"file": bits[0]}
    if len(bits) > 1 and bits[1]:
        p["color"] = bits[1]
    if len(bits) > 2 and bits[2]:
        p["opacity"] = float(bits[2])
    if len(bits) > 3 and bits[3]:
        p["roughness"] = float(bits[3])
    if len(bits) > 4 and bits[4]:
        p["metalness"] = float(bits[4])
    return p


def load_mm(path):
    """メッシュとして読み、mm にそろえる。STEP は cascadio 経由でメートルになるので換算する
    （組み立て STEP はシーンとして読まれるので、シーンの単位で換算してから1つにまとめる）。"""
    obj = trimesh.load(path)
    units = getattr(obj, "units", None)
    if units and units not in ("millimeters", "mm"):
        obj = obj.convert_units("millimeters")
    if isinstance(obj, trimesh.Scene):
        obj = obj.to_mesh() if hasattr(obj, "to_mesh") else obj.dump(concatenate=True)
    return obj


def load_mesh(path):
    m = load_mm(path)
    if m.is_empty:
        raise SystemExit(f"中身が空です: {path}")
    return m


def report_size(scene, up):
    """全体の大きさを mm で出す。読み込みのたびに既知の寸法と見比べる（単位の取り違え＝25.4倍・1000倍などを止める）"""
    ext = scene.extents
    if up == "z":                       # three.js 座標（Y上）から元の X・Y・Z に戻して表示
        ext = [ext[0], ext[2], ext[1]]
    print(f"全体の大きさ X {ext[0]:.1f} × Y {ext[1]:.1f} × Z {ext[2]:.1f} mm")
    big = max(ext)
    if big < 5 or big > 2000:
        print("!! 大きさが不自然です。単位（mm・m・インチ）の取り違えを疑ってください。"
              "既知の寸法と比べ、25.4倍・1000倍・1/1000 になっていないか確認")


def build_scene(parts, base, up):
    scene = trimesh.Scene()
    # three.js は Y が上。Z上のモデルは X軸まわりに -90° 回して合わせる
    R = np.eye(4)
    if up == "z":
        R = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    for i, p in enumerate(parts):
        f = p["file"] if os.path.isabs(p["file"]) else os.path.join(base, p["file"])
        m = load_mesh(f)
        m.apply_transform(R)
        rgba = hex2rgba(p.get("color", "#c9ccc6"), p.get("opacity", 1.0))
        mat = trimesh.visual.material.PBRMaterial(
            baseColorFactor=rgba, roughnessFactor=p.get("roughness", 0.7), metallicFactor=p.get("metalness", 0.0),
            alphaMode="BLEND" if rgba[3] < 1 else "OPAQUE", doubleSided=True)
        m.visual = trimesh.visual.TextureVisuals(material=mat)
        # 確認ページの「書き出す」が部品を見分けられるよう、ノード名は p<番号>_<キー>（英数字）にする
        key = p.get("key") or os.path.splitext(os.path.basename(f))[0]
        scene.add_geometry(m, node_name=f"p{i}_{key}")
    return scene


HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:__BG__;font-family:'Noto Sans CJK JP','Hiragino Sans',sans-serif}
#c{display:block}.lab{position:absolute;font-size:15px;color:#3b4540}
.bar{position:absolute;height:6px;border:2px solid #3b4540;border-top:0}
.barlab{position:absolute;font-size:13px;color:#3b4540;white-space:nowrap}</style></head><body>
<canvas id="c" width="__W__" height="__H__"></canvas>
<div class="lab" style="left:24px;top:14px;font-size:20px">__TITLE__</div>
__LABELS__
<script type="importmap">{"imports":{"three":"./three/build/three.module.js","three/addons/":"./three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const VIEWS=__VIEWS__, CELLS=__CELLS__, SAME=__SAME__, PAD=__PAD__, H=__H__;
const canvas=document.getElementById('c');
const r=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
r.setPixelRatio(1); r.shadowMap.enabled=true; r.shadowMap.type=THREE.PCFSoftShadowMap;
r.outputColorSpace=THREE.SRGBColorSpace; r.setClearColor(new THREE.Color('__BG__'),1); r.autoClear=false;
const s=new THREE.Scene();
s.add(new THREE.HemisphereLight(0xffffff,0xd6d9d2,1.4));
new GLTFLoader().load('./model.glb',(gl)=>{
  gl.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;
    if(o.material.transparent){o.material.depthWrite=false;}}});
  s.add(gl.scene);
  // 平行投影（真上・正面・横）では面の陰影だけだと穴や段差が見えないので、稜線を重ねる
  const edges=new THREE.Group(); gl.scene.updateMatrixWorld(true);
  gl.scene.traverse(o=>{if(o.isMesh){const e=new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry,30),
    new THREE.LineBasicMaterial({color:0x2f3a34,transparent:true,opacity:0.55}));
    e.applyMatrix4(o.matrixWorld); edges.add(e);}});
  edges.visible=false; s.add(edges);
  const box=new THREE.Box3().setFromObject(gl.scene), c=box.getCenter(new THREE.Vector3()), sz=box.getSize(new THREE.Vector3());
  const R=Math.max(sz.x,sz.y,sz.z);
  // 主の光は右手前の上から。斜め上（左手前）から見たとき、影が左奥に見える（見る側と同じ向きからだと影が物の後ろに隠れる）
  const d=new THREE.DirectionalLight(0xffffff,2.2); d.position.set(c.x+0.5*R,c.y+1.2*R,c.z+0.8*R); d.target.position.copy(c);
  d.castShadow=true; d.shadow.mapSize.set(4096,4096); const sc=d.shadow.camera;
  sc.left=-R;sc.right=R;sc.top=R;sc.bottom=-R;sc.near=1;sc.far=6*R; d.shadow.bias=-0.0005; s.add(d); s.add(d.target);
  const fill=new THREE.DirectionalLight(0xffffff,0.6); fill.position.set(c.x+0.8*R,c.y+0.4*R,c.z-0.7*R); s.add(fill);
  // 横からの光：右横の図でも、面の向き（面取り・斜面）で明暗が付くように
  const sideL=new THREE.DirectionalLight(0xffffff,0.7); sideL.position.set(c.x+1.0*R,c.y+0.35*R,c.z+0.25*R); s.add(sideL);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(20*R,20*R),new THREE.ShadowMaterial({opacity:0.18}));
  ground.rotation.x=-Math.PI/2; ground.position.y=box.min.y-0.01; ground.receiveShadow=true; s.add(ground);
  const dirs={iso:[-0.55,0.62,1.0],back:[0.6,0.28,-1.0],front:[0,0,1],side:[1,0,0],top:[0,1,0.0001]};
  const ortho={side:1,top:1,front:1};
  // 平行投影：見える2辺の長さで、ビューごとに枠いっぱいに合わせる（PAD＝図に対する枠の大きさ）。
  // --same-scale のときは、いちばん小さく写るビューの縮尺にそろえる
  const fit={};
  VIEWS.forEach((v,i)=>{
    if(!ortho[v]) return;
    const [x,y,w,h]=CELLS[i], asp=w/h;
    const span = v==='side' ? [sz.z,sz.y] : v==='top' ? [sz.x,sz.z] : [sz.x,sz.y];
    let hw=Math.max(span[0],1e-3)*PAD/2, hh=Math.max(span[1],1e-3)*PAD/2; if(hw/hh>asp) hh=hw/asp; else hw=hh*asp;
    fit[i]={hw,hh,ppm:h/(2*hh)};
  });
  if(SAME){
    const ppm=Math.min(...Object.values(fit).map(f=>f.ppm));
    for(const i in fit){ const [x,y,w,h]=CELLS[i]; fit[i]={hw:w/2/ppm,hh:h/2/ppm,ppm}; }
  }
  // 縮尺の目安：1・2・5×10^k mm のうち、枠の幅の1割前後になる長さ
  const barLen=(w,ppm)=>{ let L=0.1; for(const c of [0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000,2000]){ if(c*ppm<=Math.max(60,w*0.12)) L=c; } return L; };
  const sameL=SAME&&Object.keys(fit).length ? Math.min(...Object.keys(fit).map(i=>barLen(CELLS[i][2],fit[i].ppm))) : 0;
  for(const i in fit){
    const [x,y,w,h]=CELLS[i], ppm=fit[i].ppm, L=sameL||barLen(w,ppm);
    const bar=document.createElement('div'); bar.className='bar';
    bar.style.left=(x+18)+'px'; bar.style.top=(H-y-22)+'px'; bar.style.width=Math.round(L*ppm)+'px'; document.body.appendChild(bar);
    const lab=document.createElement('div'); lab.className='barlab'; lab.textContent=`目盛 ${L}mm`;
    lab.style.left=(x+18)+'px'; lab.style.top=(H-y-44)+'px'; document.body.appendChild(lab);
  }
  VIEWS.forEach((v,i)=>{
    const [x,y,w,h]=CELLS[i]; const asp=w/h; const dv=new THREE.Vector3(...dirs[v]).normalize();
    let cam;
    if(ortho[v]){
      const {hw,hh}=fit[i];
      cam=new THREE.OrthographicCamera(-hw,hw,hh,-hh,0.1,10*R);
      cam.position.copy(c).addScaledVector(dv,3*R); if(v==='top') cam.up.set(0,0,-1); cam.lookAt(c);
    } else {
      cam=new THREE.PerspectiveCamera(24,asp,0.1,20*R);
      const sph=box.getBoundingSphere(new THREE.Sphere()).radius;
      const dist=sph/Math.sin(THREE.MathUtils.degToRad(Math.min(24,24*asp)/2))*0.92;
      cam.position.copy(c).addScaledVector(dv,dist); cam.lookAt(c);
    }
    edges.visible=!!ortho[v];
    ground.visible=!ortho[v];          // 真上・正面・横では地面の影を描かない（大きな灰色の形になって読みにくい）
    r.setViewport(x,y,w,h); r.setScissor(x,y,w,h); r.setScissorTest(true); r.clear(); r.render(s,cam);
  });
  window.DONE=true;
},undefined,(e)=>{window.ERR=String(e);});
</script></body></html>"""


ORTHO = ("front", "side", "top")
PAD = 1.1           # 平行投影の枠は図の 1.1 倍（図が枠の約9割を占める）
PERSP_ASPECT = 1.6  # 斜めの図の枠の縦横比の目安


def view_aspect(v, ext):
    """ビューに写る形の横÷縦（ext は three.js の座標＝Y上の大きさ）"""
    x, y, z = (max(float(e), 1e-3) for e in ext)
    return {"side": z / y, "top": x / z, "front": x / y}.get(v, PERSP_ASPECT)


def layout(views, W, ext):
    """先頭のビューを大きく、残りを下に1列に並べる。three.js のビューポートは左下原点。
    下の列は、形の縦横比に合う高さにする（細長い枠に縦長の正面図が小さく入るのを避ける）。"""
    big_h = int(W * 0.42)
    rest = views[1:]
    n, gap = len(rest), 10
    small_h, widths = 0, []
    if rest:
        avail = W - gap * (n + 1)
        asp = [min(4.0, max(0.3, view_aspect(v, ext))) for v in rest]
        cap = big_h if all(v in ORTHO for v in rest) else int(W * 0.3)
        small_h = int(max(W * 0.24, min(cap, avail / (sum(asp) * PAD))))
        natural = [a * PAD * small_h for a in asp]
        if sum(natural) <= avail:                       # 縦横比どおりの幅に、余りを等しく足す
            extra = (avail - sum(natural)) / n
            widths = [int(w + extra) for w in natural]
        else:                                           # 入りきらないときは等分（従来どおり）
            widths = [avail // n] * n
    H = 40 + big_h + (small_h + 40 if rest else 0) + 10
    cells, labels = [], []
    cells.append([0, H - 40 - big_h, W, big_h])
    x = gap
    for i, w in enumerate(widths):
        cells.append([x, 10, w, small_h])
        labels.append(f'<div class="lab" style="left:{x + 14}px;top:{H - 10 - small_h - 30}px">{VIEW_LABEL[rest[i]]}</div>')
        x += w + gap
    labels.insert(0, f'<div class="lab" style="left:24px;top:44px">{VIEW_LABEL[views[0]]}</div>')
    return H, cells, "\n".join(labels)


def three_dir():
    d = os.environ.get("THREE_DIR") or os.path.join(CACHE, "three", "node_modules", "three")
    if not os.path.isfile(os.path.join(d, "build", "three.module.js")):
        raise SystemExit("three.js が見つかりません。setup スキル（setup.sh）を実行してください")
    return d


def render(scene, title, views, out, width=1800, bg=BG, same_scale=False):
    work = tempfile.mkdtemp()
    os.symlink(three_dir(), os.path.join(work, "three"))
    scene.export(os.path.join(work, "model.glb"))
    H, cells, labels = layout(views, width, scene.extents)
    html = (HTML.replace("__TITLE__", title).replace("__LABELS__", labels).replace("__W__", str(width))
            .replace("__H__", str(H)).replace("__VIEWS__", json.dumps(views)).replace("__CELLS__", json.dumps(cells))
            .replace("__BG__", bg).replace("__SAME__", "true" if same_scale else "false").replace("__PAD__", str(PAD)))
    open(os.path.join(work, "index.html"), "w", encoding="utf-8").write(html)

    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=work, **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Q)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            pg = br.new_page(viewport={"width": width, "height": H})
            pg.goto(f"http://127.0.0.1:{port}/index.html")
            pg.wait_for_function("window.DONE===true || window.ERR", timeout=180000)
            err = pg.evaluate("window.ERR")
            if err:
                raise SystemExit(f"描画に失敗しました: {err}")
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            pg.screenshot(path=out)
            br.close()
    finally:
        httpd.shutdown()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", nargs="*", help="ファイル[:色[:不透明度[:粗さ[:金属感]]]]")
    ap.add_argument("--scene", help="scene.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--views", default=None, help="カンマ区切り。例: iso,back,side")
    ap.add_argument("--up", default=None, choices=["z", "y"])
    ap.add_argument("--glb", help="確認ページ用のGLBも書き出す")
    ap.add_argument("--width", type=int, default=1800)
    ap.add_argument("--same-scale", action="store_true", help="平行投影のビューの縮尺をそろえる")
    a = ap.parse_args()

    if a.scene:
        sc = json.load(open(a.scene, encoding="utf-8"))
        base = os.path.dirname(os.path.abspath(a.scene))
        parts = sc["parts"]
    else:
        sc, base, parts = {}, os.getcwd(), [parse_part(s) for s in a.parts]
    if not parts:
        raise SystemExit("部品がありません（--scene か ファイル名を指定）")
    up = a.up or sc.get("up", "z")
    views = (a.views.split(",") if a.views else sc.get("views")) or ["iso", "back", "side"]
    for v in views:
        if v not in VIEW_LABEL:
            raise SystemExit(f"ビュー名が違います: {v}（{', '.join(VIEW_LABEL)}）")
    title = a.title or sc.get("title", "")
    scene = build_scene(parts, base, up)
    report_size(scene, up)
    if a.glb:
        os.makedirs(os.path.dirname(os.path.abspath(a.glb)), exist_ok=True)
        scene.export(a.glb)
    render(scene, title, views, a.out, a.width, same_scale=a.same_scale)
    print(a.out)


if __name__ == "__main__":
    main()
