import Decimal from 'decimal.js';
import { hashValue, requireThat } from '../contracts/validate.mjs';
const D=Decimal.clone({precision:100,rounding:Decimal.ROUND_HALF_UP});
const value=x=>{requireThat(typeof x==='string'&&/^(0|[1-9][0-9]*)(\.[0-9]{1,10})?$/.test(x)&&new D(x).gt(0),'METRIC_PRICE_INVALID');return new D(x);};
const bps=(p,entry)=>p.div(entry).minus(1).times(10000).toDecimalPlaces(10).toFixed();
/** Retrospective outcomes only. The caller supplies an explicit calendar; never a weekday guess. */
export function pathMetrics({entry_price,entry_date,entry_timing,bars,calendar_dates}) {
  const entry=value(entry_price);
  requireThat(['SESSION_OPEN','INTRADAY_UNKNOWN'].includes(entry_timing),'ENTRY_TIMING_REQUIRED');
  requireThat(Array.isArray(calendar_dates)&&calendar_dates.length&&calendar_dates.every((d,i)=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&(!i||d>calendar_dates[i-1])),'METRIC_CALENDAR_REQUIRED');
  requireThat(calendar_dates.includes(entry_date),'ENTRY_NOT_TRADING_SESSION');
  const eligible=calendar_dates.filter(d=>entry_timing==='SESSION_OPEN'?d>=entry_date:d>entry_date);
  requireThat(Array.isArray(bars),'METRIC_BARS_REQUIRED');
  const byDate=new Map();
  for(const bar of bars){requireThat(calendar_dates.includes(bar.trade_date)&&!byDate.has(bar.trade_date),'METRIC_BAR_CALENDAR_OR_DUPLICATE');const low=value(bar.low),high=value(bar.high),close=value(bar.close);requireThat(low.lte(high)&&close.gte(low)&&close.lte(high),'METRIC_OHLC_INVALID');byDate.set(bar.trade_date,bar);}
  // A missing session is a gap, not a shorter window silently relabeled 5D.
  const path=[];for(const date of eligible){if(!byDate.has(date))break;path.push(byDate.get(date));}
  const out={contract_name:'PathMetrics',contract_version:'1.0.0',entry_price,entry_date,entry_timing,mae_resolution:'DAILY_APPROXIMATION',mfe_resolution:'DAILY_APPROXIMATION',usage:'RETROSPECTIVE_OUTCOME_ONLY',horizon_basis:'TRADING_SESSIONS',sample_sessions:path.length,window_status:{}};
  for(const n of [5,10,20,40]){
    const complete=path.length>=n;out.window_status[`${n}D`]=complete?'COMPLETE':'INCOMPLETE';const window=path.slice(0,n);
    if(n!==40)out[`MAE_${n}D`]=complete?bps(D.min(entry,...window.map(b=>value(b.low))),entry):null;
    out[`MFE_${n}D`]=complete?bps(D.max(entry,...window.map(b=>value(b.high))),entry):null;
  }
  out.days_to_positive=null;out.days_to_MFE=null;
  let peak=entry,underwater=0,maxUnder=0,peakUnder=0,maxPeakUnder=0,highest=entry;
  path.forEach((bar,i)=>{const c=value(bar.close),h=value(bar.high);if(out.days_to_positive===null&&c.gt(entry))out.days_to_positive=i+1;if(h.gt(highest)){highest=h;out.days_to_MFE=i+1;}underwater=c.lt(entry)?underwater+1:0;maxUnder=Math.max(maxUnder,underwater);peakUnder=c.lt(peak)?peakUnder+1:0;maxPeakUnder=Math.max(maxPeakUnder,peakUnder);peak=D.max(peak,c);});
  out.drawdown_duration=maxPeakUnder;out.max_underwater_days=maxUnder;out.duration_resolution='SESSION_CLOSE';out.positive_basis='CLOSE_ABOVE_ENTRY_PRICE_EXCLUDING_FEES';out.censored=path.length<eligible.length;out.path_hash=hashValue(path);
  return out;
}
