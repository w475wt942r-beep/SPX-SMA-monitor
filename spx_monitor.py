"""Free SPX SMA monitor. Data: Yahoo Finance ^GSPC (unofficial, may fail/delay)."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf

PERIODS = (10, 20, 30, 40, 50)
TIMEFRAMES = (20, 10, 5, 1)
TZ = 'America/New_York'


def fetch():
    raw = yf.download('^GSPC', period='7d', interval='1m', auto_adjust=False, progress=False, prepost=False, threads=False)
    if raw.empty:
        raise RuntimeError('Yahoo returned no 1-minute ^GSPC bars')
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw[['Close']].dropna()
    if raw.index.tz is None:
        raise RuntimeError('Yahoo returned timezone-naive candles')
    raw.index = raw.index.tz_convert(TZ)
    raw = raw.between_time('09:30', '15:59')
    return raw


def completed_bars(data, minutes, now=None):
    # Aggregate in exchange local time, anchored to 09:30 each session.
    now = now or pd.Timestamp.now(tz=TZ)
    out = []
    for _, day in data.groupby(data.index.date):
        bars = day.resample(f'{minutes}min', origin='start_day', offset='9h30min', label='left', closed='left').agg({'Close': ['last', 'count']})
        bars.columns = ['Close', 'count']
        # 20-minute timeframe has a 10-minute final partial bar: discard it.
        bars = bars[bars['count'] == minutes]
        bars = bars[(bars.index + pd.Timedelta(minutes=minutes)) <= now]
        out.append(bars[['Close']])
    return pd.concat(out).sort_index() if out else pd.DataFrame(columns=['Close'])


def evaluate(data, minutes, now=None):
    bars = completed_bars(data, minutes, now)
    if len(bars) < 51:
        return {'timeframe': minutes, 'status': 'insufficient_data', 'bars': len(bars)}
    close = bars['Close']
    averages = {n: close.rolling(n).mean() for n in PERIODS}
    slopes = {str(n): ('up' if averages[n].iloc[-1] > averages[n].iloc[-2] else 'down' if averages[n].iloc[-1] < averages[n].iloc[-2] else 'flat') for n in PERIODS}
    values = [averages[n].iloc[-1] for n in PERIODS]
    ordered_up = all(a > b for a, b in zip(values, values[1:]))
    ordered_down = all(a < b for a, b in zip(values, values[1:]))
    bullish = ordered_up and all(v == 'up' for v in slopes.values())
    bearish = ordered_down and all(v == 'down' for v in slopes.values())
    return {'timeframe': minutes, 'status': 'ok', 'bar_time_et': bars.index[-1].isoformat(), 'bars': len(bars), 'slopes': slopes, 'rising': list(slopes.values()).count('up'), 'falling': list(slopes.values()).count('down'), 'strict_bullish_order': ordered_up, 'strict_bearish_order': ordered_down, 'full_alignment': 'bullish' if bullish else 'bearish' if bearish else 'none'}


def main():
    output = Path('output')
    output.mkdir(exist_ok=True)
    report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'ticker': '^GSPC', 'source': 'Yahoo Finance (unofficial)', 'timeframes': {}}
    try:
        data = fetch()
        report['source_last_bar_et'] = data.index[-1].isoformat()
        now = pd.Timestamp.now(tz=TZ)
        age = (now - data.index[-1]).total_seconds() / 60
        # Do not flag stale on historical/off-hours runs; include age transparently.
        report['source_age_minutes'] = round(age, 1)
        for tf in TIMEFRAMES:
            report['timeframes'][str(tf)] = evaluate(data, tf, now)
        data.to_csv(output / 'spx_1m.csv')
    except Exception as exc:
        report['error'] = str(exc)
    (output / 'latest.json').write_text(json.dumps(report, indent=2))
    symbols = {'up':'🟢', 'down':'🔴', 'flat':'⚪'}
    lines = ['# SPX SMA alignment', '', f"Source: {report['source']}", f"Checked UTC: {report['checked_utc']}", f"Latest candle ET: {report.get('source_last_bar_et', 'unavailable')}", '', '| SMA | 20-min | 10-min | 5-min | 1-min |', '|---|:---:|:---:|:---:|:---:|']
    for n in PERIODS:
        cells = []
        for tf in TIMEFRAMES:
            d = report['timeframes'].get(str(tf), {})
            cells.append(symbols.get(d.get('slopes', {}).get(str(n)), '⚪'))
        lines.append(f'| {n} | ' + ' | '.join(cells) + ' |')
    lines += ['', 'Gray = neutral or unavailable; see JSON for status.', '']
    for tf in TIMEFRAMES:
        d = report['timeframes'].get(str(tf), {})
        lines.append(f"- {tf}-minute: {d.get('full_alignment', d.get('status', 'unavailable'))}; rising={d.get('rising', 'unknown')}, falling={d.get('falling', 'unknown')}; bars={d.get('bars', 'unknown')}")
    if 'error' in report:
        lines.append('Data error: ' + report['error'])
    (output / 'report.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write('\n'.join(lines) + '\n')
    # Don't report an alignment from stale data or an unavailable source.
    if report.get('error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
