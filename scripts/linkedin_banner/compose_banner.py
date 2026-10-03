import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
import os
# Inter isn't vendored (separate OFL licence); point INTER_DIR at its extras/ttf folder.
F=os.environ.get("INTER_DIR","")
DEJAVU={"Bold":"DejaVuSans-Bold","Light":"DejaVuSans-ExtraLight"}
def font(w,s):
    try: return ImageFont.truetype(os.path.join(F,f"Inter-{w}.ttf"),s)
    except OSError: return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{DEJAVU.get(w,'DejaVuSans')}.ttf",s)
W,H=1584,396
BG=np.array([11,15,25],np.float32)
chip=Image.open("banner/chip_render_full.png").convert("RGB")

def background():
    y,x=np.mgrid[0:H,0:W].astype(np.float32)
    g=np.zeros((H,W,3),np.float32)+BG
    # subtle dark-blue glow toward upper-centre and right
    r1=np.exp(-(((x-1150)/650)**2+((y-120)/320)**2))
    r2=np.exp(-(((x-350)/700)**2+((y-60)/260)**2))
    g+=r1[...,None]*np.array([6,18,42])+r2[...,None]*np.array([4,10,26])
    return Image.fromarray(np.clip(g,0,255).astype(np.uint8)).convert("RGBA")

def glow_paste(base,img,xy,glow=(0,200,255),strength=0.55,radius=22,shadow=True):
    w,h=img.size; pad=radius*3
    layer=Image.new("RGBA",(w+2*pad,h+2*pad),(0,0,0,0))
    if shadow:
        sh=Image.new("RGBA",layer.size,(0,0,0,0)); ImageDraw.Draw(sh).rectangle([pad+8,pad+14,pad+w+8,pad+h+14],fill=(0,0,0,200))
        layer=Image.alpha_composite(layer,sh.filter(ImageFilter.GaussianBlur(radius*0.8)))
    gl=Image.new("RGBA",layer.size,(0,0,0,0)); ImageDraw.Draw(gl).rectangle([pad,pad,pad+w,pad+h],fill=glow+(int(255*strength),))
    layer=Image.alpha_composite(layer,gl.filter(ImageFilter.GaussianBlur(radius)))
    base.alpha_composite(layer,(xy[0]-pad,xy[1]-pad))
    base.alpha_composite(img.convert("RGBA"),xy)

def hfade(img,fade_px,side="left"):
    w,h=img.size; a=np.ones(w,np.float32)
    ramp=np.linspace(0,1,fade_px)**1.6
    if side=="left": a[:fade_px]=ramp
    a=np.tile(a,(h,1)); im=img.convert("RGBA"); arr=np.array(im); arr[...,3]=(arr[...,3]*a).astype(np.uint8)
    return Image.fromarray(arr)

def text(d,xy,s,f,fill): d.text(xy,s,font=f,fill=fill)
L1="Physics → Silicon → Software"; L2="Full-Stack · AI Agents · RTL-to-GDSII"
CAP="INT8 NN Accelerator · SKY130 · 0.247 mm²"
WHITE=(255,255,255,255); GRAY=(176,186,204,255); CAPC=(122,138,165,255); ACC=(0,229,255,255)

# ---------- v1: full chip on right half ----------
b=background(); s=292
c=chip.resize((int(s*chip.width/chip.height),s),Image.LANCZOS)
cx=1188-c.width//2; glow_paste(b,c,(cx,30))
d=ImageDraw.Draw(b); fc=font("Medium",15)
tw=d.textlength(CAP,font=fc); text(d,(1188-tw/2,345),CAP,fc,CAPC)
f1=font("Bold",50); f2=font("Regular",24)
text(d,(64,62),L1,f1,WHITE)
d.rectangle([66,134,66+56,137],fill=ACC)
text(d,(64,152),L2,f2,GRAY)
b.convert("RGB").save("banner/banner_v1.png")

# ---------- v2: detail region fills right 60% ----------
b=background(); rw=int(W*0.6); x0=W-rw
k=rw/1500  # sample a 1500-px-wide window of the 8 px/um render
crop=chip.crop((1250,1700,1250+1500,1700+int(H/k))).resize((rw,H),Image.LANCZOS)
crop=hfade(crop,260); b.alpha_composite(crop,(x0,0))
# vignette bottom so the caption reads
vg=np.zeros((H,rw,4),np.uint8); vg[...,:3]=BG.astype(np.uint8); vg[...,3]=(np.clip((np.arange(H)-260)/136,0,1)**1.4*235).astype(np.uint8)[:,None]
b.alpha_composite(Image.fromarray(vg),(x0,0))
d=ImageDraw.Draw(b)
tw=d.textlength(CAP,font=fc); text(d,(W-40-tw,356),CAP,fc,(170,184,208,255))
f1=font("Bold",44); f2=font("Regular",22)
text(d,(56,58),L1,f1,WHITE); d.rectangle([58,124,58+56,127],fill=ACC); text(d,(56,140),L2,f2,GRAY)
b.convert("RGB").save("banner/banner_v2.png")

# ---------- v3: minimal, chip full-width faded ----------
b=background(); k=W/chip.width
band=chip.resize((W,int(chip.height*k)),Image.LANCZOS)
top=(band.height-H)//2; band=band.crop((0,top,W,top+H)).convert("RGBA")
arr=np.array(band).astype(np.float32)
xs=np.linspace(0,1,W); op=0.16+0.30*np.clip((xs-0.25)/0.75,0,1)  # fainter behind the text
arr[...,3]=255*op[None,:]; b.alpha_composite(Image.fromarray(arr.astype(np.uint8)))
d=ImageDraw.Draw(b); f1=font("Bold",48); f2=font("Light",23)
X=508; text(d,(X,118),L1,f1,WHITE); d.rectangle([X+2,188,X+2+56,190],fill=ACC); text(d,(X,204),L2,f2,GRAY)
text(d,(X,248),CAP,font("Medium",15),CAPC)
b.convert("RGB").save("banner/banner_v3.png")

