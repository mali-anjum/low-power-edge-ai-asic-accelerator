import gdstk, numpy as np
from PIL import Image, ImageDraw, ImageFilter
lib=gdstk.read_gds("results/int8_parallel/accelerator_top_project_run_02.gds")
top=lib.top_level()[0]
(x0,y0),(x1,y1)=top.bounding_box()
SC=8.0  # px per um
W,H=int((x1-x0)*SC)+1,int((y1-y0)*SC)+1
layers=[ # (layer,dt), rgb, alpha
 ((67,20),(40,70,140),0.35),   # li1
 ((68,20),(0,229,255),0.55),   # met1 cyan
 ((69,20),(255,46,200),0.60),  # met2 magenta
 ((70,20),(255,196,0),0.70),   # met3 gold
 ((71,20),(57,255,120),0.75),  # met4 green
 ((72,20),(220,235,255),0.35), # met5
]
by={}
for p in top.get_polygons(): by.setdefault((p.layer,p.datatype),[]).append(p.points)
canvas=np.zeros((H,W,3),np.float32); canvas[:]=np.array([11,15,25],np.float32)
for key,rgb,a in layers:
    m=Image.new("L",(W,H),0); d=ImageDraw.Draw(m)
    for pts in by.get(key,[]):
        q=[((x-x0)*SC,(y1-y)*SC) for x,y in pts]
        d.polygon(q,fill=255)
    al=(np.asarray(m,np.float32)/255.0*a)[...,None]
    canvas=canvas*(1-al)+np.array(rgb,np.float32)*al
    print(key,len(by.get(key,[])))
img=Image.fromarray(np.clip(canvas,0,255).astype(np.uint8))
img.save("banner/chip_render_full.png")
print(img.size)
