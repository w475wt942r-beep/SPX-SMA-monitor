import os, json, sys, urllib.request, urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

PERIODS = (5, 10, 20, 30, 40, 50)
TIMEFRAMES = (20, 10, 5, 1)
NY = ZoneInfo('America/New_York')
HI = ZoneInfo('Pacific/Honolulu')
REPO = os.getenv('GITHUB_REPOSITORY', '')
TOKEN = os.getenv('GITHUB_TOKEN', '')
MARKER = '<!-- spx-sma-signal-state -->'

def api(method, path, payload=None):
    url = 'https://api.github.com/repos/' + REPO + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Accept':'application/vnd.github+json','User-Agent':'spx-sma-monitor','X-GitHub-Api-Version':'2022-11-28'}
    if TOKEN: headers['Authorization'] = 'Bearer ' + TOKEN
    if data: headers['Content-Type']='application/json'
    with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=20) as r:
        return json.load(r)

def get_state():
    if not REPO or not TOKEN: raise RuntimeError('GitHub token/repository unavailable; cannot safely deduplicate')
    for item in api('GET','/issues?state=all&per_page=100'):
        if MARKER in (item.get('body') or '') and 'pull_request' not in item:
            return item['number'], json.loads((item['body'] or '').split('\n',1)[1])
    return None, {'signal':'none','session':''}

def save_state(number, state):
    payload={'body':MARKER+'\n'+json.dumps(state)}
    if number: api('PATCH',f'/issues/{number}',payload)
    else: api('POST','/issues',dict(payload,title='SPX SMA monitor signal state'))

def push(message, direction):
    topic=os.getenv('NTFY_TOPIC','').strip()
    if not topic: raise RuntimeError('NTFY_TOPIC GitHub secret missing; push not configured')
    server=os.getenv('NTFY_SERVER','https://ntfy.sh').rstrip('/')
    if not server.startswith('https://'): raise RuntimeError('NTFY_SERVER must use HTTPS')
    request=urllib.request.Request(server+'/'+topic,data=message.encode('utf-8'),headers={'Title':'SPX '+direction.upper()+' SMA alignment','Priority':'high','Tags':'chart_with_upwards_trend' if direction=='bullish' else 'chart_with_downwards_trend'},method='POST')
    with urllib.request.urlopen(request,timeout=20) as r: r.read()

def analyze(raw, minutes, now):
    frames=[]
    for _,day in raw.groupby(raw.index.date):
        grouped=day['Close'].resample(f'{minutes}min',origin='start_day',offset='9h30min',label='left',closed='left').agg(['last','count'])
        grouped=grouped[(grouped['count']==minutes)&(grouped.index+pd.Timedelta(minutes=minutes)<=now)]
        frames.append(grouped['last'])
    close=pd.concat(frames).sort_index() if frames else pd.Series(dtype=float)
    if len(close)<51: return {'status':'insufficient','slopes':{}}
    slopes={}
    for p in PERIODS:
        ma=close.rolling(p).mean()
        slopes[p]='🟢' if ma.iloc[-1]>ma.iloc[-2] else '🔴' if ma.iloc[-1]<ma.iloc[-2] else '⚪'
    return {'status':'ok','slopes':slopes,'bar_end':(close.index[-1]+pd.Timedelta(minutes=minutes)).isoformat()}

def main():
    now=pd.Timestamp.now(tz=NY)
    # Runs are UTC-scheduled; skip outside regular U.S. trading session, including weekends.
    if now.weekday()>4 or not (now.replace(hour=9,minute=30,second=0,microsecond=0)<=now<now.replace(hour=16,minute=0,second=0,microsecond=0)):
        print('Outside regular U.S. session; no alert'); return
    raw=yf.download('^GSPC',period='7d',interval='1m',auto_adjust=False,progress=False,prepost=False,threads=False)
    if raw.empty: raise RuntimeError('No SPX data')
    if isinstance(raw.columns,pd.MultiIndex):raw.columns=raw.columns.get_level_values(0)
    if raw.index.tz is None:raise RuntimeError('Data timezone missing')
    raw.index=raw.index.tz_convert(NY)
    raw=raw[['Close']].dropna().between_time('09:30','15:59')
    latest=raw.index[-1]
    age=(now-latest).total_seconds()/60
    if age>8 or age<0: raise RuntimeError(f'Stale/future data: {age:.1f} minutes old')
    results={tf:analyze(raw,tf,now) for tf in TIMEFRAMES}
    def aligned(tf, color):return results[tf]['status']=='ok' and all(results[tf]['slopes'].get(p)==color for p in PERIODS)
    direction='bullish' if aligned(5,'🟢') and aligned(10,'🟢') else 'bearish' if aligned(5,'🔴') and aligned(10,'🔴') else 'none'
    lines=['SPX SMA slopes (completed bars)',f'Checked: {now.strftime("%Y-%m-%d %I:%M %p ET")} / {now.tz_convert(HI).strftime("%I:%M %p HST")}',f'Last source bar: {latest.isoformat()} ({age:.1f} min old)','SMA | 20m | 10m | 5m | 1m']
    for p in PERIODS:lines.append(f'{p} | '+' | '.join(results[tf]['slopes'].get(p,'⚪') for tf in TIMEFRAMES))
    lines.append('Combined 5m+10m: '+direction.upper())
    msg='\n'.join(lines)
    print(msg)
    with open(os.getenv('GITHUB_STEP_SUMMARY','/dev/null'),'a') as f:f.write('```\n'+msg+'\n```\n')
    number, state=get_state()
    session=now.strftime('%Y-%m-%d')
    # Reset dedup state on new session. Alert on transitions into either qualifying alignment.
    previous=state.get('signal','none') if state.get('session')==session else 'none'
    if direction != previous:
        if direction!='none':
            push(msg,direction)  # Only save after successful delivery, so a failed push can retry.
        save_state(number,{'signal':direction,'session':session,'updated':now.isoformat()})
    else:print('No new signal; no push')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('MONITOR ERROR:',str(e),file=sys.stderr)
        raise
