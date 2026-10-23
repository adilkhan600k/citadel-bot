import os,json,urllib.request,urllib.error,time
T=os.environ['DISCORD_BOT_TOKEN'];G='1543420245916655716'
def dapi(m,p,d=None,tries=6):
    for i in range(tries):
        r=urllib.request.Request('https://discord.com/api/v10'+p,method=m,data=json.dumps(d).encode() if d is not None else None,headers={'Authorization':'Bot '+T,'Content-Type':'application/json','User-Agent':'DiscordBot (x,1)'})
        try:
            with urllib.request.urlopen(r,timeout=30) as x: b=x.read(); return json.loads(b) if b else None
        except urllib.error.HTTPError as e:
            body=e.read().decode(errors='ignore')
            if e.code==429:
                try: w=json.loads(body).get('retry_after',2)
                except: w=2
                time.sleep(float(w)+0.5); continue
            if e.code>=500 and i<tries-1: time.sleep(2); continue
            raise RuntimeError(f'{m} {p} -> {e.code} {body[:300]}')
    raise RuntimeError('too many retries')
