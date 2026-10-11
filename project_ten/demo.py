"""Deterministic synthetic data for interface demonstrations only. NOT market history."""
from datetime import datetime,timezone,timedelta
from math import exp,cos,sin
import random
from .data import validate

START=datetime(2023,10,1,tzinfo=timezone.utc)

def generate_asset(asset, days=900):
    rng=random.Random({'BTC':101,'ETH':202,'SOL':303}[asset]); price={'BTC':26000.,'ETH':1500.,'SOL':23.}[asset]
    drift={'BTC':.0008,'ETH':.00055,'SOL':.0003}[asset]
    volatility={'BTC':.028,'ETH':.038,'SOL':.056}[asset]
    rows=[]
    for i in range(days):
        regime= .002* sin(i/72.) + .0012 * cos(i/19.)
        change=max(-.23,min(.23,drift + regime + volatility*rng.gauss(0,1)))
        op=price; price=op*exp(change)
        hi=max(op,price)*(1+rng.uniform(.0001,.025))
        lo=min(op,price)*(1-rng.uniform(.0001,.025))
        t=int((START+timedelta(days=i)).timestamp())
        rows.append({'t':t,'o':op,'h':hi,'l':lo,'c':price,'v':rng.uniform(100,900)})
    return validate(rows)

def generate(days=900):return {a:generate_asset(a,days) for a in ('BTC','ETH','SOL')}
