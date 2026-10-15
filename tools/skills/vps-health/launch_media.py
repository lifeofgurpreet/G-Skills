#!/usr/bin/env python3
"""Build caption-first launch films from actual synthetic-only product captures.

Developer tool, not a dependency of the installed skill. No account, provider,
customer workspace or arbitrary URL can be selected. No social upload occurs.
Pillow + Playwright + ffmpeg/ffprobe are required only for rendering media.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import wave

ROOT=Path(__file__).resolve().parents[3]
RELEASE_REF='vps-health/v0.8.0'
FORMATS={'landscape':(1920,1080),'portrait':(1080,1350)}
SCENES=[
 {'id':'hook','duration':4,'headline':['Slow VPS.','Wrong suspect?'],'caption':'Your workload? Your limits? The host? Start with evidence.','kind':'title'},
 {'id':'agent','duration':7,'headline':['Your agent does','the setup.'],'caption':'You approve the target, access and consequential actions.','kind':'workflow'},
 {'id':'charts','duration':9,'headline':['Two views.','One timeline.'],'caption':'CPU accounting and workload pressure, seen together.','kind':'product'},
 {'id':'gaps','duration':7,'headline':['Missing data','stays missing.'],'caption':'Retained gaps and evidence holds. No invented healthy defaults.','kind':'product'},
 {'id':'attention','duration':7,'headline':['A next step.','Not a verdict.'],'caption':'An attention inbox helps separate collection problems from performance.','kind':'product'},
 {'id':'support','duration':8,'headline':['Share the minimum.','Keep the evidence.'],'caption':'A local support report. No node IDs, endpoints or raw measurements.','kind':'support'},
 {'id':'end','duration':11,'headline':['Evidence','before blame.'],'caption':'VPS Health · G-Skills · Open-source technical preview','kind':'end'}]


def sha(data):return hashlib.sha256(data).hexdigest()


def validate_story(scenes=SCENES):
    if not scenes or sum(x['duration'] for x in scenes)>60:raise ValueError('short launch film must be at most 60 seconds')
    ids=set()
    for scene in scenes:
        if scene['id'] in ids or scene['kind'] not in ('title','workflow','product','support','end'):raise ValueError('invalid scene identity/type')
        ids.add(scene['id'])
        if not 1<=scene['duration']<=15 or not scene['headline'] or not scene['caption']:raise ValueError('invalid scene timing/caption')
    return sum(x['duration'] for x in scenes)


def scene_at(t,scenes=SCENES):
    total=validate_story(scenes);t=max(0,min(float(t),total-1e-6));start=0
    for i,scene in enumerate(scenes):
        if t<start+scene['duration']:return i,scene,(t-start)/scene['duration']
        start+=scene['duration']
    raise AssertionError('scene not found')


def srt(scenes=SCENES):
    def stamp(t):
        ms=int(t*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    lines=[];cursor=0
    for i,scene in enumerate(scenes,1):
        lines += [str(i),stamp(cursor)+' --> '+stamp(cursor+scene['duration']),
                  ' '.join(scene['headline'])+' '+scene['caption'],'']
        cursor+=scene['duration']
    return '\n'.join(lines)


def capture_product(out):
    """Capture actual source UI through only a freshly created synthetic fixture."""
    from playwright.sync_api import sync_playwright,expect
    sys.path.insert(0,str(ROOT/'skills/vps-health/scripts'))
    import vps_workspace as ws
    out.mkdir();receipt={'synthetic_only':True,'native_agent_trace':False,'events':[],'images':{}}
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
        root=Path(temp)/'demo'
        ws.bootstrap(SimpleNamespace(workspace=root,mode='demo',node='example',profile=None,url=None,loki_url=None,
           token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,investigate_below=.8))
        value=ws.status(root)
        if not value['synthetic'] or sorted(x['id'] for x in value['assets'])!=['example-contended','example-offline','example-stable']:
            raise ValueError('media may contain only the built-in synthetic example')
        server=ws.make_server(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        browser=playwright.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1200},device_scale_factor=1,accept_downloads=True,reduced_motion='reduce')
        page=context.new_page();requests=[];errors=[];page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
        base=f'http://127.0.0.1:{server.server_port}'
        def shot(name,selector):
            raw=page.locator(selector).screenshot();(out/(name+'.png')).write_bytes(raw);receipt['images'][name]={'sha256':sha(raw),'selector':selector}
        try:
            page.goto(base,wait_until='networkidle');expect(page.locator('#history-chart canvas')).to_have_count(1)
            expect(page.locator('#node-selector')).to_have_value('example-contended')
            page.screenshot(path=str(out/'overview.png'));receipt['images']['overview']={'sha256':sha((out/'overview.png').read_bytes()),'selector':'viewport'}
            shot('charts','.chart-panel')
            for i,x in enumerate((.18,.32,.49,.64,.79,.90)):
                box=page.locator('#history-chart .u-over').bounding_box()
                page.locator('#history-chart .u-over').hover(position={'x':box['width']*x,'y':55})
                shot(f'charts-{i}','.chart-panel')
                from PIL import Image
                panel=page.locator('.chart-panel').bounding_box();top=page.locator('#history-chart').bounding_box();bottom=page.locator('#context-chart').bounding_box()
                image=Image.open(out/f'charts-{i}.png');image=image.crop((18,max(0,round(top['y']-panel['y']-44)),image.width-18,min(image.height,round(bottom['y']-panel['y']+bottom['height']+45))))
                image.save(out/f'charts-detail-{i}.png');receipt['images'][f'charts-detail-{i}']={'sha256':sha((out/f'charts-detail-{i}.png').read_bytes()),'selector':'pixel crop of actual paired charts, no data/text edited'}
            receipt['events'].append('actual chart hover updates retained sample readout')
            page.get_by_label('Inspect node',exact=True).select_option('example-offline')
            expect(page.locator('#selected-status')).to_contain_text('On hold')
            shot('gaps','.focus-layout');shot('gap-card','.action-panel');shot('gap-chart','.chart-panel')
            receipt['events'].append('actual selection of missing/stale synthetic subject remains HOLD')
            page.get_by_role('link',name='Attention',exact=False).click();expect(page.locator('#view-attention')).to_be_visible()
            shot('attention','#view-attention');shot('finding','.finding:first-child')
            receipt['events'].append('actual Attention navigation')
            with page.expect_download() as event:page.get_by_role('button',name='Save minimal support report').click()
            support=json.loads(Path(event.value.path()).read_text())
            if support.get('contains_private_workspace_data') is True:raise ValueError('unexpected support projection')
            (out/'support-report.json').write_text(json.dumps(support,indent=2)+'\n')
            shot('support-header','.heading-actions')
            receipt['events'].append('actual support-report button downloaded its fixed read-only response; nothing uploaded')
            page.get_by_role('link',name='Setup',exact=True).click();page.get_by_role('button',name='Explore the demo',exact=True).click()
            shot('setup','#view-setup')
            if errors:raise ValueError('actual viewer errors: '+repr(errors))
            if not all(url.startswith(base+'/') or url==base+'/' or url.startswith('blob:') for url in requests):raise ValueError('unexpected external capture request')
            receipt['external_asset_requests']=False;receipt['actual_viewer_checks']='PASS'
        finally:
            context.close();browser.close();server.shutdown();server.server_close();thread.join(3)
    (out/'capture-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def original_audio(path,seconds):
    """An original low-key instrumental bed: synthesized tones, no samples."""
    from array import array
    rate=24000;data=array('h');chords=((130.8128,164.8138,195.9977),(110.,130.8128,164.8138),(146.8324,174.6141,220.),(130.8128,164.8138,195.9977))
    for n in range(int(rate*seconds)):
        t=n/rate;segment=int(t/6.625)%4;within=t%6.625
        env=min(1,within/.65,(6.625-within)/1.1)*min(1,t/1.5,(seconds-t)/2)
        pad=sum(math.sin(2*math.pi*f*t)+.18*math.sin(4*math.pi*f*t) for f in chords[segment])*.022*max(0,env)
        beat=t%(.625*2);bell=.023*math.exp(-beat*7)*math.sin(2*math.pi*523.251*t)*min(1,t/2,(seconds-t)/3)
        data.append(int(max(-1,min(1,pad+bell))*32767))
    if sys.byteorder!='little':data.byteswap()
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(data.tobytes())


class Film:
    def __init__(self,captures,width,height):
        from PIL import Image,ImageDraw,ImageFont
        self.Image=Image;self.Draw=ImageDraw;self.Font=ImageFont;self.w=width;self.h=height;self.portrait=height>width
        self.scale=width/(1080 if self.portrait else 1920)
        self.faces={}
        for key,family in (('bold','Lato:style=Heavy'),('regular','Lato:style=Regular'),('mono','DejaVu Sans Mono:style=Book')):
            result=subprocess.check_output(['fc-match','-f','%{file}',family],text=True).strip()
            if not result or not Path(result).is_file():raise ValueError('a local font is required; no font download is attempted')
            self.faces[key]=result
        self.fonts={};self.images={p.stem:Image.open(p).convert('RGB') for p in captures.glob('*.png')};self.scaled={}
        self.support=json.loads((captures/'support-report.json').read_text())
        self.bg=(8,15,29);self.white=(243,247,255);self.muted=(151,168,197);self.accent=(132,161,255)

    def font(self,size,face='regular'):
        size=round(size*self.scale);key=(size,face)
        if key not in self.fonts:self.fonts[key]=self.Font.truetype(self.faces[face],max(1,size))
        return self.fonts[key]

    def text(self,draw,xy,value,size=32,fill=None,face='regular',spacing=1):
        x,y=(int(v*self.scale) for v in xy);font=self.font(size,face)
        for line in value.split('\n'):
            draw.text((x,y),line,font=font,fill=fill or self.white,stroke_width=0)
            y+=round(size*spacing*self.scale)

    def wrapped(self,text,width,size,face='regular'):
        font=self.font(size,face);words=text.split();lines=[];line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if font.getlength(candidate)>width*self.scale and line:lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        return '\n'.join(lines)

    def rounded(self,im,box,radius=20,fill=None,outline=None,width=1):
        d=self.Draw.Draw(im);box=tuple(int(v*self.scale) for v in box)
        d.rounded_rectangle(box,radius=int(radius*self.scale),fill=fill,outline=outline,width=width)

    def photo(self,im,name,box,progress=0,fit='contain'):
        x,y,w,h=[int(v*self.scale) for v in box];image=self.images[name]
        key=(name,w,h,fit)
        if key not in self.scaled:
            # Every product image is a verified capture; no value/text editing.
            scale=min(w/image.width,h/image.height) if fit=='contain' else max(w/image.width,h/image.height)
            layer=self.Image.new('RGB',(w,h),(249,251,255))
            resized=image.resize((round(image.width*scale),round(image.height*scale)),self.Image.Resampling.LANCZOS)
            layer.paste(resized,((w-resized.width)//2,0))
            self.scaled[key]=layer
        layer=self.scaled[key]
        # Editorial camera movement, not a claim that this is an uncut live trace.
        inset=round(min(w,h)*.006*progress)
        if inset>0:layer=layer.crop((inset,inset,w-inset,h-inset)).resize((w,h),self.Image.Resampling.BICUBIC)
        mask=self.Image.new('L',(w,h),0);self.Draw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=round(18*self.scale),fill=255)
        im.paste(layer,(x,y),mask)

    def base(self,index,t):
        im=self.Image.new('RGB',(self.w,self.h),self.bg);d=self.Draw.Draw(im)
        W=1080 if self.portrait else 1920;H=1350 if self.portrait else 1080
        margin=60 if self.portrait else 84
        self.rounded(im,(margin,50,margin+46,96),12,fill=self.white)
        self.text(d,(margin+11,56),'G',32,fill=self.bg,face='bold')
        self.text(d,(margin+64,49),'G-SKILLS',23,face='bold')
        self.text(d,(margin+64,79),'VPS HEALTH',13,fill=self.muted,face='mono')
        badge='DEMO DATA  /  TECHNICAL PREVIEW'
        size=17 if self.portrait else 19
        bw=self.font(size,'mono').getlength(badge)/self.scale
        self.text(d,(W-margin-bw,62),badge,size,fill=self.accent,face='mono')
        d.line((margin*self.scale,124*self.scale,(W-margin)*self.scale,124*self.scale),fill=(36,48,72),width=max(1,round(self.scale)))
        self.text(d,(margin,H-54),'PRODUCT CAPTURES + MOTION DESIGN · DEMO DATA',14 if self.portrait else 18,fill=self.muted,face='mono')
        self.text(d,(W-margin-58,H-54),f'{index+1:02d}/07',14 if self.portrait else 18,fill=self.muted,face='mono')
        d.rectangle((0,self.h-round(4*self.scale),round(self.w*t/53),self.h),fill=self.accent)
        return im

    def frame(self,t):
        i,scene,p=scene_at(t);im=self.base(i,t);d=self.Draw.Draw(im);portrait=self.portrait
        W=1080 if portrait else 1920;H=1350 if portrait else 1080;M=60 if portrait else 84
        if scene['kind'] in ('title','end'):
            top=275 if portrait else 255;size=116 if portrait else 156
            elapsed=p*scene['duration']
            one=scene['headline'][0] if scene['kind']=='end' else scene['headline'][0][:max(0,int((elapsed+.12)*14))]
            two=scene['headline'][1] if scene['kind']=='end' else scene['headline'][1][:max(0,int((elapsed-.42)*17))]
            self.text(d,(M,top),one,size,face='bold')
            self.text(d,(M,top+size*1.03),two,size,fill=self.accent,face='bold')
            if scene['kind']=='title':
                self.text(d,(M,top+size*2.7),self.wrapped(scene['caption'],W-2*M,38 if portrait else 42),38 if portrait else 42,fill=self.muted,spacing=1.35)
                self.text(d,(M,H-195),'A useful question beats a premature accusation.',24 if portrait else 30,fill=self.white)
            else:
                self.text(d,(M,top+size*2.6),'VPS Health',51 if portrait else 58,face='bold')
                self.text(d,(M,top+size*3.25),'One skill in the G-Skills collection.',27 if portrait else 34,fill=self.muted)
                self.rounded(im,(M,H-308,W-M,H-202),18,fill=(24,39,67),outline=(67,89,130))
                self.text(d,(M+26,H-283),'lifeofgurpreet / G-Skills',36 if portrait else 47,face='bold')
                self.text(d,(M,H-162),'Try the demo. Share feedback. Build with us.',27 if portrait else 34,fill=self.white)
        elif scene['kind']=='workflow':
            size=84 if portrait else 106;top=215
            self.text(d,(M,top),scene['headline'][0],size,face='bold');self.text(d,(M,top+size*1.08),scene['headline'][1],size,fill=self.accent,face='bold')
            self.text(d,(M,top+size*2.55),self.wrapped(scene['caption'],W-2*M,31 if portrait else 38),31 if portrait else 38,fill=self.muted,spacing=1.35)
            names=['PLAN','START','VERIFY','STOP'];step=(W-2*M)/4;cy=760 if portrait else 710
            for j,name in enumerate(names):
                ready=p>j*.16;fill=(26,47,82) if ready else (16,27,46)
                x=M+j*step;self.rounded(im,(x,cy,x+step-16,cy+124),15,fill=fill,outline=self.accent if ready else (40,51,69))
                self.text(d,(x+24,cy+23),f'0{j+1}',17,fill=self.accent,face='mono')
                self.text(d,(x+24,cy+60),name,25 if portrait else 33,face='bold')
            self.text(d,(M,cy+164),'Private handoff. Bounded runtime. Your approval.',25 if portrait else 30,fill=self.white)
            self.text(d,(M,H-116),'WORKFLOW ILLUSTRATION — NOT A RECORDED AGENT SESSION',13 if portrait else 17,fill=self.muted,face='mono')
        else:
            size=69 if portrait else 85;top=192 if portrait else 250
            maxw=W-2*M if portrait else 605
            for j,line in enumerate(scene['headline']):self.text(d,(M,top+j*size*1.10),line,size,fill=self.accent if j==1 else self.white,face='bold')
            self.text(d,(M,top+size*2.65),self.wrapped(scene['caption'],maxw,29 if portrait else 33),29 if portrait else 33,fill=self.muted,spacing=1.40)
            box=(M,565,W-2*M,605) if portrait else (780,185,1056,745)
            name=scene['id']
            if name=='charts':name=('charts-detail-' if p>.24 else 'charts-')+str(min(5,int(p*6)))
            if scene['kind']=='support':
                self.rounded(im,(box[0],box[1],box[0]+box[2],box[1]+box[3]),22,fill=(244,247,252))
                x,y,w,h=box
                self.text(d,(x+34,y+34),'SUPPORT EXPORT · FIELD SUMMARY',22,fill=(48,65,95),face='mono')
                self.text(d,(x+34,y+92),'Useful context. Less exposure.',32 if portrait else 40,fill=(13,29,55),face='bold')
                for j,(label,value) in enumerate([('Software + source IDs','Included'),('Categorical checks','Included'),('Aggregate counts','Included'),('Node names + endpoints','Excluded'),('Raw measurements','Excluded')]):
                    yy=y+186+j*64
                    d.line(((x+34)*self.scale,(yy-17)*self.scale,(x+w-34)*self.scale,(yy-17)*self.scale),fill=(214,222,234),width=1)
                    self.text(d,(x+34,yy),label,23 if portrait else 29,fill=(28,44,71))
                    self.text(d,(x+w-194,yy),value,22 if portrait else 26,fill=(43,70,142),face='bold')
                self.text(d,(x+34,y+h-66),'LOCAL DOWNLOAD · REVIEW BEFORE SHARING',17 if portrait else 20,fill=(67,84,115),face='mono')
                # It is a designed explanation of the actual downloaded JSON,
                # not a fabricated new product panel or a purported redaction.
            else:
                if name=='gaps':name='gap-chart' if portrait else 'gaps'
                if name=='attention' and portrait:name='finding'
                self.photo(im,name,box,p,fit='cover' if portrait and scene['id']=='gaps' else 'contain')
            if not portrait:
                self.text(d,(M,820),{'charts':'Context changes the question.','gaps':'Unknown is a useful answer.','attention':'Investigate before escalating.','support':'No automatic uploads.'}[scene['id']],25,fill=self.white)
            else:self.text(d,(M,1210),'Downloaded fields · editorial summary' if scene['kind']=='support' else 'Local viewer · actual product · demo data',21,fill=self.muted)
        # Brief scene-entry fade, while persistent disclosure remains readable.
        seconds=p*scene['duration']
        if seconds<.20:im=self.Image.blend(self.base(i,t),im,max(.15,seconds/.20))
        return im


def front_loaded_metadata(path):
    with Path(path).open('rb') as handle:
        for _ in range(32):
            header=handle.read(8)
            if len(header)!=8:return False
            size,name=struct.unpack('>I4s',header)
            overhead=8
            if size==1:
                extended=handle.read(8)
                if len(extended)!=8:return False
                size=struct.unpack('>Q',extended)[0];overhead=16
            if name==b'moov':return True
            if name==b'mdat' or size<overhead:return False
            handle.seek(size-overhead,1)
    return False


def probe(path):
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],text=True))
    video=next(s for s in data['streams'] if s['codec_type']=='video')
    audio=next((s for s in data['streams'] if s['codec_type']=='audio'),None)
    return {'width':video['width'],'height':video['height'],'video_codec':video['codec_name'],
            'pixel_format':video['pix_fmt'],'fps':video['avg_frame_rate'],
            'audio_codec':audio['codec_name'] if audio else None,'duration_seconds':float(data['format']['duration']),'fast_start':front_loaded_metadata(path)}


def encode(captures,out,kind,audio,fps=24):
    size=FORMATS[kind];film=Film(captures,*size);duration=validate_story();path=out/f'vps-health-launch-{kind}.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s',f'{size[0]}x{size[1]}',
       '-r',str(fps),'-i','-','-i',str(audio),'-map','0:v:0','-map','1:a:0','-t',str(duration),
       '-c:v','libx264','-preset','fast','-crf','20','-profile:v','high','-pix_fmt','yuv420p',
       '-c:a','aac','-b:a','128k','-movflags','+faststart','-threads','2','-y',str(path)]
    with (out/f'{kind}-encode.log').open('wb') as error:
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=error)
        try:
            for n in range(duration*fps):
                frame=film.frame(n/fps);proc.stdin.write(frame.tobytes())
                if n in (fps*2,fps*8,fps*15,fps*24,fps*30,fps*38,fps*47):
                    frame.save(out/f'{kind}-frame-{n//fps:02d}.jpg',quality=90)
                if n%(fps*10)==0:print(f'{kind}: {n//fps}/{duration} seconds rendered',flush=True)
            proc.stdin.close()
            if proc.wait(timeout=180):raise ValueError('ffmpeg encoding failed; inspect private media log')
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    info=probe(path)
    if (info['width'],info['height'])!=size or info['video_codec']!='h264' or info['audio_codec']!='aac' or info['pixel_format']!='yuv420p' or abs(info['duration_seconds']-duration)>.1 or not info['fast_start']:
        raise ValueError('output does not meet the reviewed media format')
    # Decode the complete file, not just its metadata or first frame.
    subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:v','-f','null','-'],check=True,stdout=subprocess.DEVNULL,timeout=120)
    return {**info,'bytes':path.stat().st_size,'sha256':sha(path.read_bytes()),'full_video_decode':'PASS'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--format',choices=('both',*FORMATS),default='both')
    parser.add_argument('--stills-only',action='store_true')
    args=parser.parse_args(argv);out=args.out.expanduser().absolute()
    if out.exists() or ROOT==out or ROOT in out.parents:parser.error('use a NEW artifact directory outside the repository')
    for tool in ('ffmpeg','ffprobe','fc-match'):
        if not shutil.which(tool):parser.error('missing developer-only media tool: '+tool)
    subprocess.run(['git','diff','--exit-code',RELEASE_REF,'HEAD','--','skills/vps-health'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    out.mkdir(parents=True,mode=0o700)
    receipt=capture_product(out/'captures')
    (out/'vps-health-launch.srt').write_text(srt())
    kinds=list(FORMATS) if args.format=='both' else [args.format]
    if args.stills_only:
        for kind in kinds:
            film=Film(out/'captures',*FORMATS[kind])
            for t in (2,8,15,24,30,38,47):film.frame(t).save(out/f'{kind}-frame-{t:02d}.jpg',quality=94)
        print(json.dumps({'result':'STILLS_ONLY_NOT_A_VIDEO','output':str(out)}));return 0
    audio=out/'original-instrumental.wav';original_audio(audio,validate_story())
    movies={}
    for kind in kinds:movies[kind]=encode(out/'captures',out,kind,audio)
    shutil.copyfile(out/'landscape-frame-02.jpg' if 'landscape' in kinds else out/'portrait-frame-02.jpg',out/'vps-health-launch-poster.jpg')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    skill_hashes={p.relative_to(ROOT/'skills/vps-health').as_posix():sha(p.read_bytes()) for p in (ROOT/'skills/vps-health').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    manifest={'schema':'g-skills.launch-media.v1','source_commit':commit,'renderer_sha256':sha(Path(__file__).read_bytes()),'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'released_skill_ref':RELEASE_REF,'skill_version':'0.8.0','synthetic_only':True,
              'native_agent_trace':False,'physical_host_claim':False,'publication_sent':False,'captioned':True,
              'style':'motion design over actual product captures; workflow diagram is explicitly illustrative',
              'audio':'original procedurally synthesized instrumental; no voice impersonation or third-party samples',
              'scenes':SCENES,'product_capture_receipt':receipt,'skill_files_sha256':sha(json.dumps(skill_hashes,sort_keys=True).encode()),'videos':movies}
    (out/'media-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'result':'RENDERED_AND_VERIFIED','videos':movies,'publication_sent':False},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
