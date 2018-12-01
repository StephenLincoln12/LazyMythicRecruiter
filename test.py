import dryscrape as ds
import bs4 as bs
import time
import requests
from pprint import pprint as p

url = "https://www.wowprogress.com/guild/us/bleeding-hollow/Olympia?roster"

page = requests.get(url).content


soup = bs.BeautifulSoup(page, 'lxml')

print soup.prettify()

rows = soup.find_all('tr')

roster = {}
for row in rows[1:]:
    d = {}
    d['_class'] = row["class"][0]
    print row["class"][0]
    cols = row.find_all('td')
    d['rank'] = int(cols[0].text)
    race = cols[1].a["aria-label"]
    if "demon hunter" in race:
        d['race'] = ' '.join(x for x in race.split()[0:-2])
    else:
        d['race'] = ' '.join(x for x in race.split()[0:-1])
    character = cols[1].a.text
    d['href'] = cols[1].a['href']
    pve_score = cols[2].text
    try:
        d['pve_score'] = float(pve_score)
    except:
        d['pve_score'] = pve_score
    ilvl = cols[3].text
    try:
        d['ilvl'] = float(ilvl)
    except:
        d['ilvl'] = ilvl
    d['azerite'] = cols[4].span.text
    sim_dps = cols[5].text
    try:
        d['sim_dps'] = float(sim_dps)
    except:
        d['sim_dps'] = ''
    mplus_score = cols[6].text
    try:
        d['mplus_score'] = float(mplus_score)
    except:
        d['mplus_score'] = ''
    roster[character] = d

